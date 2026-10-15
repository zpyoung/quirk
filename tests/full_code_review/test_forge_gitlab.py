import subprocess

import post_reviewer_review as reviewer
import prepare_diff
from forge import gitlab

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


def test_change_diff_records_files_whose_diff_the_forge_truncated():
    class Forge:
        name = "gitlab"

        def change_records(self, number):
            return {"number": 1, "title": "t", "description": "", "web_url": "", "author": "a",
                    "source_branch": "f", "refs": {"base": "b" * 40, "start": "c" * 40, "head": HEAD},
                    "records": [{"old_path": "big.json", "new_path": "big.json", "diff": "", "too_large": True},
                                {"old_path": "ok.py", "new_path": "ok.py", "collapsed": False,
                                 "diff": "@@ -1 +1 @@\n-x\n+y\n"}],
                    "reported_count": 2, "overflow": False}

    saved = prepare_diff._git_diff_path
    prepare_diff._git_diff_path = lambda *a, **k: "diff --git a/big.json b/big.json\n--- a/big.json\n+++ b/big.json\n@@ -1 +1 @@\n-1\n+2\n"
    try:
        metadata = {}
        assert prepare_diff.change_diff(Forge(), 1, ".", metadata) is not None
    finally:
        prepare_diff._git_diff_path = saved
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
