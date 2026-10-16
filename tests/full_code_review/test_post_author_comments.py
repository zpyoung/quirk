import json

import pytest

import comment_body
import post_author_comments as m
from forge import ForgeError
from forge.github import GitHubForge
from forge.gitlab import GitLabForge
from .fakes import DIFF, HEAD, MERGE_BASE, FakeGitHub


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


def signed(bodies, value):
    """`bodies` bound to the report `value`, as comment_body.py author writes them."""
    return dict(bodies, report_sha256=comment_body._report_digest(value))


def context(forge="github"):
    return {"forge": forge, "seat": "author", "refs": {"base": MERGE_BASE, "start": MERGE_BASE, "head": HEAD},
            "change": {"number": 7, "host": "github.com", "project": "o/r"}, "diff": DIFF}


BODIES = {"findings": {"F1": {"body": "one", "post": True}, "F2": {"body": "two", "post": True},
                       "F3": {"body": "three", "post": False}},
          "overview": "summary"}


def test_github_posts_eligible_in_diff_findings_and_writes_receipts(tmp_path):
    fake = FakeGitHub()
    out = str(tmp_path / "receipts.json")
    receipts, warnings = m.post(report(), context(), signed(BODIES, report()), ["F1", "F2", "F3"], out,
                                overview=True, forge=GitHubForge("github.com", "o/r", api_call=fake))
    assert sorted(receipts) == ["F1"]
    assert json.loads(open(out).read()) == receipts
    assert json.loads(open(m.overview_receipt_path(out)).read())["published"] is True
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
        m.post(two_in_diff, context("gitlab"), signed(bodies, two_in_diff), ["F1", "F2"], out,
               forge=GitLabForge("gitlab.example", "o/r", api_call=api))
    assert sorted(json.loads(open(out).read())) == ["F1"]
    position = calls[0][2]["position"]
    assert calls[0][1] == "projects/o%2Fr/merge_requests/7/discussions"
    assert position["position_type"] == "text" and position["head_sha"] == HEAD and position["new_line"] == 2


def test_cli_rejects_a_reviewer_seat_context(tmp_path, capsys):
    paths = {}
    for name, value in (("report", report()), ("context", dict(context(), seat="reviewer")),
                        ("bodies", signed(BODIES, report()))):
        paths[name] = tmp_path / ("%s.json" % name)
        paths[name].write_text(json.dumps(value))
    rc = m.main(["--report", str(paths["report"]), "--context", str(paths["context"]),
                 "--bodies", str(paths["bodies"]), "--ids", "F1", "--out", str(tmp_path / "r.json")])
    assert rc == 2 and "author-seat" in json.loads(capsys.readouterr().out)["error"]


class RecordingForge:
    """Posts every in-diff line, failing the create numbers listed in `fail_on`."""

    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)
        self.posted = []
        self.targets = []

    def inline_target(self, refs, old_path, new_path, line, diff_text, side="new"):
        self.targets.append((old_path, new_path, line, side))
        return {"path": new_path, "line": line}

    def _create(self, body):
        if len(self.posted) + 1 in self.fail_on:
            self.fail_on.discard(len(self.posted) + 1)
            raise ForgeError("503 from the forge")
        self.posted.append(body)
        return {"published": True, "note_id": len(self.posted)}

    def post_inline(self, number, body, position, head_sha):
        return self._create(body)

    def post_overview(self, number, body):
        return self._create(body)


def two_finding_report():
    value = report("gitlab")
    value["findings"] = [dict(value["findings"][0]), dict(value["findings"][0], line="3", title="Second")]
    return value


TWO = {"findings": {"F1": {"body": "one", "post": True}, "F2": {"body": "two", "post": True}},
       "overview": "summary"}


def write_inputs(tmp_path, ctx=None):
    paths = {}
    for name, value in (("report", two_finding_report()), ("context", ctx or context("gitlab")),
                        ("bodies", signed(TWO, two_finding_report()))):
        paths[name] = tmp_path / ("%s.json" % name)
        paths[name].write_text(json.dumps(value))
    paths["out"] = tmp_path / "receipts.json"
    return paths


def cli_args(paths, ids="F1,F2", *extra):
    return ["--report", str(paths["report"]), "--context", str(paths["context"]),
            "--bodies", str(paths["bodies"]), "--ids", ids, "--out", str(paths["out"]), *extra]


RENAME_DIFF = ("diff --git a/old.py b/new.py\nsimilarity index 80%\nrename from old.py\nrename to new.py\n"
               "--- a/old.py\n+++ b/new.py\n@@ -1,3 +1,3 @@\n keep\n-gone\n+added\n tail\n")


def test_gitlab_rename_carries_both_paths(tmp_path):
    calls = []

    def api(host, method, endpoint, payload=None, timeout=120):
        calls.append(payload)
        return {"id": "d1", "notes": [{"id": 1, "type": "DiffNote"}]}

    value = two_finding_report()
    value["findings"] = [dict(value["findings"][0], file="new.py", line="2")]
    m.post(value, dict(context("gitlab"), diff=RENAME_DIFF),
           signed({"findings": {"F1": TWO["findings"]["F1"]}}, value),
           ["F1"], str(tmp_path / "r.json"), forge=GitLabForge("gitlab.example", "o/r", api_call=api))
    position = calls[0]["position"]
    assert position["old_path"] == "old.py" and position["new_path"] == "new.py"


def test_gitlab_off_diff_line_is_skipped_and_the_batch_continues(tmp_path):
    calls = []

    def api(host, method, endpoint, payload=None, timeout=120):
        calls.append(endpoint)
        return {"id": "d1", "notes": [{"id": 1, "type": "DiffNote"}]}

    value = two_finding_report()
    value["findings"][1]["line"] = "99"
    receipts, warnings = m.post(value, context("gitlab"), signed(TWO, value), ["F1", "F2"],
                                str(tmp_path / "r.json"), forge=GitLabForge("gitlab.example", "o/r", api_call=api))
    assert sorted(receipts) == ["F1"]
    assert any("F2" in w and "outside the diff" in w for w in warnings)
    assert len(calls) == 1


def test_findings_on_collapsed_files_are_skipped_with_a_warning(tmp_path):
    forge = RecordingForge()
    ctx = dict(context("gitlab"), unanchorable_files=["a.py"])
    receipts, warnings = m.post(two_finding_report(), ctx, signed(TWO, two_finding_report()),
                                ["F1", "F2"], str(tmp_path / "r.json"), forge=forge)
    assert receipts == {} and forge.posted == []
    assert [w for w in warnings if "collapsed" in w] and len(warnings) == 2


def test_unknown_id_is_rejected_before_anything_posts(tmp_path):
    forge = RecordingForge()
    with pytest.raises(ValueError, match="F9"):
        m.post(two_finding_report(), context("gitlab"), signed(TWO, two_finding_report()),
               ["F1", "F2", "F9"], str(tmp_path / "r.json"), forge=forge)
    assert forge.posted == [] and not (tmp_path / "r.json").exists()


def test_gitlab_overview_posts_a_plain_note_once(tmp_path):
    calls = []

    def api(host, method, endpoint, payload=None, timeout=120):
        calls.append((method, endpoint, payload))
        return {"id": 31}

    out = str(tmp_path / "r.json")
    forge = GitLabForge("gitlab.example", "o/r", api_call=api)
    only_overview = signed({"findings": {}, "overview": "summary"}, two_finding_report())
    m.post(two_finding_report(), context("gitlab"), only_overview, [], out, overview=True, forge=forge)
    assert calls == [("POST", "projects/o%2Fr/merge_requests/7/notes", {"body": "summary"})]
    assert json.loads(open(m.overview_receipt_path(out)).read())["note_id"] == 31
    m.post(two_finding_report(), context("gitlab"), only_overview, [], out, overview=True, forge=forge)
    assert len(calls) == 1


def test_retry_with_the_same_out_resumes_without_reposting(tmp_path, monkeypatch, capsys):
    paths = write_inputs(tmp_path)
    flaky = RecordingForge(fail_on={2})
    monkeypatch.setattr(m, "make_forge", lambda *a, **k: flaky)
    assert m.main(cli_args(paths, "F1,F2", "--overview")) == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure["posted"] == ["F1"] and failure["failed_id"] == "F2" and "F2" in failure["error"]
    assert sorted(json.loads(paths["out"].read_text())) == ["F1"]

    assert m.main(cli_args(paths, "F1,F2", "--overview")) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["posted"] == ["F1", "F2"]
    assert any("F1 already has a receipt" in w for w in done["warnings"])
    assert flaky.posted == ["one", "two", "summary"]
    assert sorted(json.loads(paths["out"].read_text())) == ["F1", "F2"]
    assert json.loads(open(m.overview_receipt_path(paths["out"])).read())["published"] is True


def test_failed_overview_is_named_in_the_failure(tmp_path, monkeypatch, capsys):
    paths = write_inputs(tmp_path)
    forge = RecordingForge(fail_on={3})
    monkeypatch.setattr(m, "make_forge", lambda *a, **k: forge)
    assert m.main(cli_args(paths, "F1,F2", "--overview")) == 2
    assert json.loads(capsys.readouterr().out)["failed_id"] == "overview"


def test_cli_rejects_an_unknown_id_before_the_first_create(tmp_path, monkeypatch, capsys):
    paths = write_inputs(tmp_path)
    forge = RecordingForge()
    monkeypatch.setattr(m, "make_forge", lambda *a, **k: forge)
    assert m.main(cli_args(paths, "F1,F2,F9")) == 2
    assert "F9" in json.loads(capsys.readouterr().out)["error"]
    assert forge.posted == [] and not paths["out"].exists()


def test_old_side_finding_is_anchored_on_the_removed_line(tmp_path):
    forge = RecordingForge()
    value = two_finding_report()
    value["findings"] = [dict(value["findings"][0], anchor_side="old", line="2")]
    m.post(value, dict(context("gitlab"), diff=DIFF), signed({"findings": {"F1": TWO["findings"]["F1"]}}, value),
           ["F1"], str(tmp_path / "r.json"), forge=forge)
    assert forge.targets == [("a.py", "a.py", 2, "old")]


def test_bodies_built_from_another_report_are_refused(tmp_path):
    forge = RecordingForge()
    stale = signed(TWO, report("gitlab"))
    with pytest.raises(ValueError, match="not built from this report"):
        m.post(two_finding_report(), context("gitlab"), stale, ["F1"], str(tmp_path / "r.json"), forge=forge)
    unsigned = dict(TWO)
    with pytest.raises(ValueError, match="not built from this report"):
        m.post(two_finding_report(), context("gitlab"), unsigned, ["F1"], str(tmp_path / "r.json"), forge=forge)
    assert forge.posted == []


def test_receipts_file_holds_only_finding_ids_so_memory_save_accepts_it(tmp_path):
    forge = RecordingForge()
    out = str(tmp_path / "r.json")
    m.post(two_finding_report(), context("gitlab"), signed(TWO, two_finding_report()), ["F1", "F2"], out,
           overview=True, forge=forge)
    receipts = json.loads(open(out).read())
    assert sorted(receipts) == ["F1", "F2"]
    assert all(receipt["published"] is True for receipt in receipts.values())
    assert forge.posted == ["one", "two", "summary"]


@pytest.mark.parametrize("name", ["report", "context", "bodies"])
def test_cli_reports_a_non_object_input_file_as_an_error(tmp_path, capsys, name):
    paths = write_inputs(tmp_path)
    paths[name].write_text("[]")
    assert m.main(cli_args(paths)) == 2
    assert name in json.loads(capsys.readouterr().out)["error"]


def test_failure_payload_keeps_warnings_collected_before_the_failure(tmp_path, monkeypatch, capsys):
    paths = write_inputs(tmp_path)
    bodies = signed({"findings": {"F1": dict(TWO["findings"]["F1"], post=False), "F2": TWO["findings"]["F2"]}},
                    two_finding_report())
    paths["bodies"].write_text(json.dumps(bodies))
    monkeypatch.setattr(m, "make_forge", lambda *a, **k: RecordingForge(fail_on={1}))
    assert m.main(cli_args(paths)) == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure["failed_id"] == "F2"
    assert any("F1 is not eligible" in w for w in failure["warnings"])


def test_plausible_finding_cannot_post_even_if_body_marks_it_eligible(tmp_path):
    value = two_finding_report()
    value["findings"][0].update(verification_status="plausible",
                                what_would_confirm="Re-run the input.")
    forge = RecordingForge()
    receipts, warnings = m.post(value, context("gitlab"), signed(TWO, value),
                                ["F1", "F2"], str(tmp_path / "receipts.json"), forge=forge)
    assert sorted(receipts) == ["F2"]
    assert forge.posted == ["two"]
    assert forge.targets == [("a.py", "a.py", 3, "new")]
    assert any("F1 is a plausible finding and cannot be posted; skipped" == w for w in warnings)
