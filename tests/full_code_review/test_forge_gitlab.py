import json
import subprocess

import pytest

import post_reviewer_review as reviewer
import prepare_diff
from forge import ForgeError, StrayComment, gitlab
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
    context = {"diff": "diff --git a/ok.py b/ok.py\n--- a/ok.py\n+++ b/ok.py\n@@ -1 +1 @@\n-x\n+y\n",
               "unanchorable_files": ["big.json"]}
    posted, omitted, warnings = reviewer._plan(prepared, by_id, context, REFS,
                                               GitLabForge("gitlab.example", "group/project"))
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


def test_failed_commit_and_branch_lookups_record_the_cause_and_clear_it_on_success():
    forge = GitLabForge("gitlab.example", "o/r", run=_runner(stderr="429 Too Many Requests", returncode=1))
    assert forge.commit_authors(7) is None and "429 Too Many Requests" in forge.last_error
    assert forge.find_change_for_branch("feature") is None and "429 Too Many Requests" in forge.last_error
    forge._run = _runner(json.dumps([{"iid": 9}]))
    assert forge.find_change_for_branch("feature") == 9 and forge.last_error is None
    forge._run = _runner("[]")
    assert forge.find_change_for_branch("feature") is None and forge.last_error is None
    assert forge.commit_authors(7) == [] and forge.last_error is None


def test_commit_authors_raise_on_bad_pages_and_on_a_list_past_the_page_cap():
    with pytest.raises(ForgeError, match="not JSON"):
        gitlab.commit_authors(_runner("nope"), "gitlab.example", "o/r", 7)
    with pytest.raises(ForgeError, match="unexpected shape"):
        gitlab.commit_authors(_runner('{"a": 1}'), "gitlab.example", "o/r", 7)
    full = json.dumps([{"author_email": "a@x.io"}] * 100)
    with pytest.raises(ForgeError, match="exceeded 20 pages"):
        gitlab.commit_authors(_runner(full), "gitlab.example", "o/r", 7)


def test_read_failures_keep_a_stderr_snippet():
    noisy = "x" * 600
    run = _runner(stderr="401 Unauthorized " + noisy, returncode=1)
    data, error = gitlab.fetch_changes(run, "gitlab.example", "o/r", 7)
    assert data is None and "401 Unauthorized" in error and len(error) < 500
    with pytest.raises(ForgeError, match="401 Unauthorized"):
        gitlab.mr_details(run, "gitlab.example", "o/r", 7)
    with pytest.raises(ForgeError, match="401 Unauthorized"):
        gitlab.current_user(run, "gitlab.example")


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


def test_inline_target_sends_both_line_numbers_for_an_unchanged_line():
    forge = GitLabForge("gitlab.example", "o/r")
    # shifting the old side makes the context line differ between old and new numbering
    shifted = DIFF.replace("@@ -3,3 +3,3 @@", "@@ -2,3 +3,3 @@")
    context = forge.inline_target(REFS, "old.py", "new.py", 3, shifted)
    assert context["new_line"] == 3 and context["old_line"] == 2
    added = forge.inline_target(REFS, "old.py", "new.py", 4, shifted)
    assert added["new_line"] == 4 and "old_line" not in added
    removed = forge.inline_target(REFS, "old.py", "new.py", 3, shifted, "old")
    assert removed["old_line"] == 3 and "new_line" not in removed


def _compare_api(payload):
    return lambda host, method, endpoint, body=None, timeout=120: payload


def test_changed_paths_collects_old_and_new_names():
    payload = {"diffs": [{"old_path": "old.py", "new_path": "new.py"}]}
    assert gitlab.changed_paths(_compare_api(payload), "gitlab.example", "o/r", "a" * 40, "b" * 40) == {
        "old.py", "new.py"}


def test_a_timed_out_compare_is_an_incomplete_file_set_not_an_empty_one():
    # GitLab answers 200 with no diffs when the comparison could not finish
    timed_out = {"diffs": [], "compare_timeout": True}
    with pytest.raises(ForgeError, match="timed out"):
        gitlab.changed_paths(_compare_api(timed_out), "gitlab.example", "o/r", "a" * 40, "b" * 40)


def test_request_changes_reports_graphql_errors_when_the_mutation_result_is_null():
    body = json.dumps({"data": {"mergeRequestRequestChanges": None},
                       "errors": [{"message": "You are not allowed to request changes"}]})
    with pytest.raises(ForgeError, match="not allowed to request changes"):
        gitlab.request_changes(_runner(body), "gitlab.example", "o/r", 7)
    empty = json.dumps({"data": {"mergeRequestRequestChanges": None}})
    with pytest.raises(ForgeError, match="empty mutation result"):
        gitlab.request_changes(_runner(empty), "gitlab.example", "o/r", 7)


def test_request_changes_reports_graphql_errors_when_data_is_null():
    body = json.dumps({"data": None, "errors": [{"message": "You are not allowed to request changes"}]})
    with pytest.raises(ForgeError, match="not allowed to request changes"):
        gitlab.request_changes(_runner(body), "gitlab.example", "o/r", 7)
    with pytest.raises(ForgeError, match="invalid response"):
        gitlab.request_changes(_runner("[]"), "gitlab.example", "o/r", 7)


def test_a_plain_comment_instead_of_a_diffnote_names_the_stray_discussion():
    def api_call(host, method, endpoint, payload=None, timeout=120):
        return {"id": "d9", "notes": [{"id": 31, "type": "DiscussionNote"}]}

    forge = GitLabForge("gitlab.example", "o/r", api_call=api_call)
    with pytest.raises(StrayComment) as caught:
        forge.post_inline(7, "body", {"position_type": "text"}, HEAD)
    assert (caught.value.discussion_id, caught.value.note_id) == ("d9", 31)
    assert "31" in caught.value.url and "d9" in str(caught.value)


def test_complete_approves_with_the_head_sha_and_comment_only_calls_nothing():
    calls = []

    def api_call(host, method, endpoint, payload=None, timeout=120):
        calls.append((method, endpoint, payload))
        return {}

    forge = GitLabForge("gitlab.example", "o/r", api_call=api_call)
    forge.complete(7, "approve", HEAD, "")
    assert calls == [("POST", "projects/o%2Fr/merge_requests/7/approve", {"sha": HEAD})]
    assert forge.complete(7, "comment-only", HEAD, "") == {"comment_only": True}
    assert len(calls) == 1


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
    ids = iter(range(1, 10001))
    endless = lambda host, method, endpoint, payload=None: [{"id": next(ids)} for _ in range(100)]
    with pytest.raises(ForgeError, match="exceeded 100 pages"):
        gitlab.list_drafts(endless, "gitlab.example", "o/r", 7)


@pytest.mark.parametrize("failure", [FileNotFoundError("glab"), subprocess.TimeoutExpired("glab", 120)])
def test_get_json_wraps_launch_failures_and_timeouts_as_forge_errors(monkeypatch, failure):
    def boom(*args, **kwargs):
        raise failure

    monkeypatch.setattr(gitlab.subprocess, "run", boom)
    with pytest.raises(ForgeError, match="discussion request failed"):
        gitlab.get_json("gitlab.example", "projects/1/merge_requests/7/discussions")
