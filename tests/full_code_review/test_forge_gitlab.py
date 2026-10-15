import json
import subprocess

import pytest

import post_reviewer_review as reviewer
import prepare_diff
from forge import ForgeError, gitlab
from forge.gitlab import GitLabForge

HEAD = "a" * 40
REFS = {"base_sha": "b" * 40, "start_sha": "c" * 40, "head_sha": HEAD}


def test_write_calls_send_a_json_content_type_and_reads_do_not():
    seen = []

    def run(cmd, input_text=None, timeout=120):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    gitlab.api(run, "gitlab.example", "POST", "projects/x/merge_requests/1/draft_notes", {"note": "n"})
    gitlab.api(run, "gitlab.example", "GET", "user")
    post, get = seen
    # GitLab answers 415 to a JSON body without this header
    assert post[post.index("-H") + 1] == "Content-Type: application/json"
    assert "-H" not in get


def test_change_diff_records_files_whose_diff_the_forge_truncated(monkeypatch):
    class Forge:
        name = "gitlab"

        def change_records(self, number):
            return {"number": 1, "title": "t", "description": "", "web_url": "", "author": "a",
                    "source_branch": "f", "refs": {"base": "b" * 40, "start": "c" * 40, "head": HEAD},
                    "records": [{"old_path": "big.json", "new_path": "big.json", "diff": "", "too_large": True},
                                {"old_path": "ok.py", "new_path": "ok.py", "collapsed": False,
                                 "diff": "@@ -1 +1 @@\n-x\n+y\n"}],
                    "reported_count": 2, "overflow": False}

    monkeypatch.setattr(
        prepare_diff, "_git_diff_path",
        lambda *a, **k: "diff --git a/big.json b/big.json\n--- a/big.json\n+++ b/big.json\n@@ -1 +1 @@\n-1\n+2\n")
    metadata = {}
    assert prepare_diff.change_diff(Forge(), 1, ".", metadata) is not None
    assert metadata["unanchorable_files"] == ["big.json"]


def test_plan_moves_findings_on_unanchorable_files_to_the_overview():
    prepared = {"meta": {"head_sha": HEAD}, "findings": [
        {"id": "F1", "severity": "Must fix", "file": "big.json", "line": "2", "title": "Bad",
         "impact": "Breaks.", "fix_md": "Fix."},
        {"id": "F2", "severity": "Must fix", "file": "ok.py", "line": "1", "title": "Fine",
         "impact": "Breaks.", "fix_md": "Fix."}]}
    by_id = {fid: {"id": fid, "slot": "fix", "disposition": "Blocking", "note": ""} for fid in ("F1", "F2")}
    context = {"diff": "", "unanchorable_files": ["big.json"]}
    posted, omitted, warnings = reviewer._plan(prepared, by_id, context, REFS)
    assert [item["finding_id"] for item in posted] == ["F2"]
    assert omitted[0]["id"] == "F1" and "collapsed" in omitted[0]["reason"]
    assert any("F1" in w for w in warnings)


def _runner(stdout="", stderr="", returncode=0, seen=None):
    def run(cmd, input_text=None, timeout=120):
        if seen is not None:
            seen.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
    return run


def _mr(**overrides):
    data = {"iid": 7, "state": "opened", "author": {"id": 1, "username": "author"},
            "source_branch": "feature", "target_branch": "main", "sha": HEAD,
            "diff_refs": {"base_sha": "b" * 40, "start_sha": "c" * 40, "head_sha": HEAD},
            "web_url": "https://gitlab.example/o/r/-/merge_requests/7",
            "source_project_id": 10, "target_project_id": 10}
    data.update(overrides)
    return data


@pytest.mark.parametrize("overrides, is_fork", [
    ({}, False),
    ({"source_project_id": 99}, True),
    ({"source_project_id": None}, True),
    ({"target_project_id": None}, True),
    ({"source_project_id": None, "target_project_id": None}, True),
])
def test_mr_details_marks_forks_and_fails_closed_on_missing_project_ids(overrides, is_fork):
    forge = GitLabForge("gitlab.example", "o/r", run=_runner(json.dumps(_mr(**overrides))))
    details = forge.change_details(7)
    assert details["is_fork"] is is_fork
    assert details["author_trusted"] is None
    assert details["open"] is True and details["number"] == 7


def test_find_mr_for_branch_pins_the_host_through_the_repository_url_not_a_flag():
    seen = []
    run = _runner(json.dumps([{"iid": 9}]), seen=seen)
    assert gitlab.find_mr_for_branch(run, "feature", "o/r", "gitlab.example") == 9
    cmd = seen[0]
    assert "--hostname" not in cmd
    assert cmd[cmd.index("-R") + 1] == "https://gitlab.example/o/r"


def test_read_failures_keep_a_stderr_snippet():
    noisy = "x" * 600
    run = _runner(stderr="401 Unauthorized " + noisy, returncode=1)
    data, error = gitlab.fetch_changes(run, "gitlab.example", "o/r", 7)
    assert data is None and "401 Unauthorized" in error and len(error) < 500
    with pytest.raises(ForgeError, match="401 Unauthorized"):
        gitlab.mr_details(run, "gitlab.example", "o/r", 7)
    with pytest.raises(ForgeError, match="401 Unauthorized"):
        gitlab.current_user(run, "gitlab.example")


def test_forge_wrappers_still_return_none_when_the_read_fails():
    forge = GitLabForge("gitlab.example", "o/r", run=_runner(stderr="boom", returncode=1))
    assert forge.change_details(7) is None
    assert forge.current_user() is None


def test_last_error_records_the_failure_cause_and_clears_on_success():
    forge = GitLabForge("gitlab.example", "o/r", run=_runner(stderr="401 Unauthorized", returncode=1))
    assert forge.change_details(7) is None and "401 Unauthorized" in forge.last_error
    assert forge.current_user() is None and "401 Unauthorized" in forge.last_error
    assert forge.change_details(None) is None and "required" in forge.last_error

    forge._run = _runner(json.dumps(_mr()))
    assert forge.change_details(7) is not None and forge.last_error is None
    forge._run = _runner(stderr="timeout", returncode=1)
    assert forge.current_user() is None and forge.last_error
    forge._run = _runner(json.dumps({"id": 2, "username": "me"}))
    assert forge.current_user()["username"] == "me" and forge.last_error is None


DIFF = ("diff --git a/old.py b/new.py\nsimilarity index 80%\nrename from old.py\nrename to new.py\n"
        "--- a/old.py\n+++ b/new.py\n@@ -3,3 +3,3 @@\n keep\n-gone\n+added\n tail\n")


def test_inline_target_anchors_new_and_old_sides_and_rejects_off_diff_lines():
    forge = GitLabForge("gitlab.example", "o/r")
    new = forge.inline_target(REFS, "old.py", "new.py", 4, DIFF)
    assert new["new_line"] == 4 and "old_line" not in new
    assert new["old_path"] == "old.py" and new["new_path"] == "new.py"
    old = forge.inline_target(REFS, "old.py", "new.py", 4, DIFF, "old")
    assert old["old_line"] == 4 and "new_line" not in old
    assert forge.inline_target(REFS, "old.py", "new.py", 40, DIFF) is None
    assert forge.inline_target(REFS, "old.py", "new.py", 40, DIFF, "old") is None
    assert forge.inline_target(REFS, "other.py", "other.py", 4, DIFF) is None


def _live_mr(**overrides):
    return _mr(**dict({"diff_refs": dict(REFS)}, **overrides))


@pytest.mark.parametrize("overrides, message", [
    ({"state": "merged"}, "not open"),
    ({"state": "closed"}, "not open"),
    ({"iid": 8}, "unexpected shape or iid"),
    ({"sha": "d" * 40}, "does not match"),
    ({"diff_refs": None}, "missing diff_refs"),
])
def test_merge_request_rejects_unusable_metadata(overrides, message):
    with pytest.raises(ForgeError, match=message):
        gitlab.merge_request(lambda *a, **k: _live_mr(**overrides), "gitlab.example", "o/r", 7)


def test_list_drafts_rejects_malformed_and_duplicate_pages():
    def pages(*bodies):
        iterator = iter(bodies)
        return lambda host, method, endpoint, payload=None: next(iterator)

    with pytest.raises(ForgeError, match="not a JSON list"):
        gitlab.list_drafts(pages({"oops": 1}), "gitlab.example", "o/r", 7)
    with pytest.raises(ForgeError, match="malformed item"):
        gitlab.list_drafts(pages(["nope"]), "gitlab.example", "o/r", 7)
    full = [{"id": i} for i in range(1, 101)]
    with pytest.raises(ForgeError, match="duplicate id 1"):
        gitlab.list_drafts(pages(full, [{"id": 1}]), "gitlab.example", "o/r", 7)
