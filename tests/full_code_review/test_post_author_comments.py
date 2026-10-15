import json

import pytest

import post_author_comments as m
from forge import ForgeError
from forge.github import GitHubForge
from forge.gitlab import GitLabForge
from .test_forge_github import DIFF, HEAD, MERGE_BASE, FakeGitHub


def report(forge="github"):
    return {"meta": {"target": "change", "forge": forge, "number": 7, "project": "o/r",
                     "head_sha": HEAD, "title": "Review", "verdict": "Fix first", "seat": "author"},
            "findings": [
                {"severity": "Must fix", "dimension": "correctness", "file": "a.py", "line": "2",
                 "title": "Bug", "body_md": "b", "impact": "Breaks.", "fix_md": "Fix."},
                {"severity": "Should fix", "dimension": "db", "file": "b.py", "line": "40",
                 "title": "Off-diff", "body_md": "b", "impact": "Slow.", "fix_md": "Index."},
                {"severity": "Should fix", "dimension": "db", "file": "b.py", "line": "7",
                 "title": "Ignored", "body_md": "b", "impact": "Slow.", "fix_md": "Index."}]}


def context(forge="github"):
    return {"forge": forge, "seat": "author", "refs": {"base": MERGE_BASE, "start": MERGE_BASE, "head": HEAD},
            "change": {"number": 7, "host": "github.com", "project": "o/r"}, "diff": DIFF}


BODIES = {"findings": {"F1": {"body": "one", "post": True}, "F2": {"body": "two", "post": True},
                       "F3": {"body": "three", "post": False}},
          "overview": "summary"}


def test_github_posts_eligible_in_diff_findings_and_writes_receipts(tmp_path):
    fake = FakeGitHub()
    out = str(tmp_path / "receipts.json")
    receipts, warnings = m.post(report(), context(), BODIES, ["F1", "F2", "F3"], out,
                                overview=True, forge=GitHubForge("github.com", "o/r", api_call=fake))
    assert sorted(receipts) == ["F1", "overview"]
    assert json.loads(open(out).read()) == receipts
    assert any("F2" in w and "outside the diff" in w for w in warnings)
    assert any("F3" in w and "not eligible" in w for w in warnings)
    inline = [c for c in fake.calls if c[1] == "repos/o/r/pulls/7/comments"]
    assert inline[0][2] == {"path": "a.py", "line": 2, "side": "RIGHT", "body": "one", "commit_id": HEAD}


def test_gitlab_requires_a_diffnote_and_keeps_earlier_receipts(tmp_path):
    calls = []

    def api(host, method, endpoint, payload=None, timeout=120):
        calls.append((method, endpoint, payload))
        kind = "DiffNote" if len(calls) == 1 else "DiscussionNote"
        return {"id": "d%d" % len(calls), "notes": [{"id": len(calls), "type": kind}]}

    out = str(tmp_path / "receipts.json")
    two_in_diff = dict(report("gitlab"))
    two_in_diff["findings"] = [dict(report("gitlab")["findings"][0]),
                               dict(report("gitlab")["findings"][0], line="3", title="Second")]
    bodies = {"findings": {"F1": {"body": "one", "post": True}, "F2": {"body": "two", "post": True}}}
    with pytest.raises(ForgeError):
        m.post(two_in_diff, context("gitlab"), bodies, ["F1", "F2"], out,
               forge=GitLabForge("gitlab.example", "o/r", api_call=api))
    assert sorted(json.loads(open(out).read())) == ["F1"]
    position = calls[0][2]["position"]
    assert calls[0][1] == "projects/o%2Fr/merge_requests/7/discussions"
    assert position["position_type"] == "text" and position["head_sha"] == HEAD and position["new_line"] == 2


def test_cli_rejects_a_reviewer_seat_context(tmp_path, capsys):
    paths = {}
    for name, value in (("report", report()), ("context", dict(context(), seat="reviewer")), ("bodies", BODIES)):
        paths[name] = tmp_path / ("%s.json" % name)
        paths[name].write_text(json.dumps(value))
    rc = m.main(["--report", str(paths["report"]), "--context", str(paths["context"]),
                 "--bodies", str(paths["bodies"]), "--ids", "F1", "--out", str(tmp_path / "r.json")])
    assert rc == 2 and "author-seat" in json.loads(capsys.readouterr().out)["error"]
