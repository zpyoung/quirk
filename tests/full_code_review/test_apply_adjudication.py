"""Contract tests for the adjudication prepare, jobs, and apply script."""

import copy
import importlib
import json
import re
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts" / "apply_adjudication.py"
IDENTITY_WORDS = re.compile(r"(?i)\b(adjudicat\w*|lens(es)?|opus|sonnet|reviewer)\b")
NO_VERDICT = "no-verdict"
DIFF = "```diff\n-a\n+b\n```"


def module():
    assert SCRIPT.is_file(), SCRIPT
    return importlib.import_module("apply_adjudication")


def finding(n, **overrides):
    item = {"severity": "Should fix", "dimension": "correctness", "dimensions": ["correctness"],
            "file": "f%d.py" % n, "line": str(10 + n), "title": "Title %d" % n,
            "issue": "Issue text %d" % n, "recommendation": "Fix text %d" % n,
            "recommendation_md": "Fix md %d" % n, "fix_md": "Short fix %d" % n,
            "impact": "Impact %d" % n, "verified": False, "assumptions": ["assumed %d" % n]}
    item.update(overrides)
    return item


def agree(fid, **overrides):
    item = {"id": fid, "ruling": "agree", "production": {"label": "Common path", "path": "POST /x -> handler"},
            "severity": None, "severity_reason": None, "objection": None,
            "lens_trigger_path": None, "replacement": None}
    item.update(overrides)
    return item


def issue_wrong(fid, **overrides):
    return agree(fid, ruling="issue_wrong", objection="The caller guards it at users.py:12.", **overrides)


def fix_wrong(fid, **overrides):
    replacement = {"fix_md": "Clamp the end index", "recommendation": DIFF}
    return agree(fid, ruling="fix_wrong", objection="The fix reads past the end.",
                 replacement=overrides.pop("replacement", replacement), **overrides)


def unreachable(fid, **overrides):
    return agree(fid, ruling="unreachable", objection="Only tests/helpers.py:9 calls it.",
                 lens_trigger_path="client.fetch called from production code",
                 production={"label": "Unreachable", "path": "only a test helper calls it"}, **overrides)


def write(path, value):
    path.write_text(json.dumps(value))
    return str(path)


def run(mod, capsys, *argv):
    code = mod.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def build(tmp_path, capsys, findings, rulings, merges=(), seed=7):
    """Run prepare and jobs; return (module, paths, input_doc, jobs_doc)."""
    mod = module()
    paths = {name: str(tmp_path / (name + ".json")) for name in ("findings", "input", "rulings", "jobs", "verdicts", "out")}
    write(Path(paths["findings"]), findings)
    assert run(mod, capsys, "prepare", "--findings", paths["findings"], "--out", paths["input"], "--seed", str(seed))[0] == 0
    write(Path(paths["rulings"]), {"rulings": rulings, "merges": list(merges)})
    return mod, paths


def pipeline(tmp_path, capsys, findings, rulings, verdicts=None, merges=(), seed=7):
    """Full run. `verdicts` maps finding id to "lens" | "adjudicator" | "inconclusive" | NO_VERDICT or a dict."""
    mod, paths = build(tmp_path, capsys, findings, rulings, merges, seed)
    code, _ = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                  "--out", paths["jobs"], "--seed", str(seed))
    assert code == 0
    jobs = json.loads(Path(paths["jobs"]).read_text())["jobs"]
    entries = []
    for job in jobs:
        spec = (verdicts or {}).get(job["finding"], NO_VERDICT)
        if spec == NO_VERDICT:
            continue
        if isinstance(spec, str):
            spec = {"winner": spec}
        spec = dict(spec)
        winner = spec.pop("winner")
        choice = "inconclusive" if winner == "inconclusive" else (
            "A" if job["a_is"] == winner else "B")
        entry = {"job": job["job"], "verdict": choice, "evidence_kind": "quote",
                 "evidence": "users.py:12 `if not row.email: raise`", "production_path": None,
                 "what_would_settle": None}
        entry.update(spec)
        entries.append(entry)
    write(Path(paths["verdicts"]), {"verdicts": entries})
    code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 0, out
    return json.loads(Path(paths["out"]).read_text())


def by_title(result):
    return {item["title"]: item for item in result["findings"]}


def test_prepare_keeps_every_finding_unchanged_and_is_deterministic_per_seed(tmp_path, capsys):
    mod = module()
    findings = [finding(n) for n in range(1, 13)]
    source = write(tmp_path / "in.json", findings)
    outputs = []
    for seed, name in ((3, "a"), (3, "b"), (4, "c")):
        target = str(tmp_path / (name + ".json"))
        assert run(mod, capsys, "prepare", "--findings", source, "--out", target, "--seed", str(seed))[0] == 0
        outputs.append(json.loads(Path(target).read_text()))
    assert outputs[0] == outputs[1]
    assert [item["id"] for item in outputs[0]["findings"]] != [item["id"] for item in outputs[2]["findings"]]
    assert outputs[0]["seed"] == 3
    shuffled = outputs[0]["findings"]
    assert sorted(item["id"] for item in shuffled) == sorted("A%d" % n for n in range(1, 13))
    assert [item["id"] for item in shuffled] != ["A%d" % n for n in range(1, 13)]
    for item in shuffled:
        original = findings[int(item["id"][1:]) - 1]
        assert {key: value for key, value in item.items() if key != "id"} == original


def test_prepare_assigns_ids_in_input_order_and_accepts_wrapped_findings(tmp_path, capsys):
    mod = module()
    findings = [finding(n) for n in range(1, 4)]
    source = write(tmp_path / "in.json", {"findings": findings})
    target = str(tmp_path / "out.json")
    assert run(mod, capsys, "prepare", "--findings", source, "--out", target, "--seed", "1")[0] == 0
    doc = json.loads(Path(target).read_text())
    assert {item["id"]: item["title"] for item in doc["findings"]} == {
        "A1": "Title 1", "A2": "Title 2", "A3": "Title 3"}


def test_prepare_without_seed_records_one(tmp_path, capsys):
    mod = module()
    source = write(tmp_path / "in.json", [finding(1), finding(2)])
    target = str(tmp_path / "out.json")
    assert run(mod, capsys, "prepare", "--findings", source, "--out", target)[0] == 0
    doc = json.loads(Path(target).read_text())
    assert isinstance(doc["seed"], int) and not isinstance(doc["seed"], bool)


def test_prepare_rejects_non_object_findings(tmp_path, capsys):
    mod = module()
    source = write(tmp_path / "in.json", [finding(1), "oops"])
    code, out = run(mod, capsys, "prepare", "--findings", source, "--out", str(tmp_path / "o.json"))
    assert code == 2 and "findings" in out["error"]


def test_jobs_emit_one_job_per_disagreement_with_exact_claims(tmp_path, capsys):
    findings = [finding(1), finding(2), finding(3), finding(4)]
    rulings = [agree("A1"), issue_wrong("A2"), fix_wrong("A3"), unreachable("A4")]
    mod, paths = build(tmp_path, capsys, findings, rulings)
    assert run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
               "--out", paths["jobs"], "--seed", "5")[0] == 0
    doc = json.loads(Path(paths["jobs"]).read_text())
    assert doc["seed"] == 5
    jobs = {job["finding"]: job for job in doc["jobs"]}
    assert sorted(jobs) == ["A2", "A3", "A4"]
    assert [job["job"] for job in doc["jobs"]] == ["J1", "J2", "J3"]
    assert {key: jobs[key]["packet"]["kind"] for key in jobs} == {"A2": "issue", "A3": "fix", "A4": "reachability"}

    def claims(fid):
        packet = jobs[fid]["packet"]
        a_is = jobs[fid]["a_is"]
        assert a_is in ("lens", "adjudicator")
        lens_side, adjudicator_side = ((packet["claim_a"], packet["claim_b"]) if a_is == "lens"
                                       else (packet["claim_b"], packet["claim_a"]))
        return lens_side, adjudicator_side

    assert claims("A2") == ("Issue text 2", "The caller guards it at users.py:12.")
    assert claims("A3") == ("Fix text 3", "```diff\n-a\n+b\n```")
    lens_side, adjudicator_side = claims("A4")
    assert lens_side.startswith("Issue text 4") and "client.fetch called from production code" in lens_side
    assert adjudicator_side == "Only tests/helpers.py:9 calls it."
    packet = jobs["A2"]["packet"]
    assert set(packet) == {"job", "file", "line", "kind", "claim_a", "claim_b", "execution"}
    assert packet["file"] == "f2.py" and packet["line"] == "12" and packet["job"] == jobs["A2"]["job"]
    assert packet["execution"] in ("enabled", "disabled")
    assert jobs["A2"]["ruling"]["ruling"] == "issue_wrong"


def test_jobs_randomize_sides_per_job_and_leak_nothing(tmp_path, capsys):
    count = 24
    findings = [finding(n, severity="Must fix", dimension="security-sentinel",
                        dimensions=["security-sentinel"]) for n in range(1, count + 1)]
    rulings = [issue_wrong("A%d" % n) for n in range(1, count + 1)]
    mod, paths = build(tmp_path, capsys, findings, rulings)
    sides = {}
    for seed in (1, 2):
        assert run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                   "--out", paths["jobs"], "--seed", str(seed))[0] == 0
        doc = json.loads(Path(paths["jobs"]).read_text())
        sides[seed] = [job["a_is"] for job in doc["jobs"]]
        assert len(set(sides[seed])) == 2
        for job in doc["jobs"]:
            text = json.dumps(job["packet"])
            assert not IDENTITY_WORDS.search(text)
            assert not re.search(r"Must fix|Should fix|Nit|security-sentinel|correctness", text)
    assert sides[1] != sides[2]


def test_jobs_are_deterministic_for_a_seed(tmp_path, capsys):
    findings = [finding(n) for n in range(1, 9)]
    rulings = [issue_wrong("A%d" % n) for n in range(1, 9)]
    mod, paths = build(tmp_path, capsys, findings, rulings)
    docs = []
    for _ in range(2):
        run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
            "--out", paths["jobs"], "--seed", "9")
        docs.append(Path(paths["jobs"]).read_text())
    assert docs[0] == docs[1]


@pytest.mark.parametrize("row,ruling_factory,winner,outcome", [
    ("issue_wrong/adjudicator", issue_wrong, "adjudicator", "dropped"),
    ("issue_wrong/lens", issue_wrong, "lens", "survived"),
    ("issue_wrong/inconclusive", issue_wrong, "inconclusive", "disputed"),
    ("issue_wrong/none", issue_wrong, NO_VERDICT, "disputed"),
    ("fix_wrong/adjudicator", fix_wrong, "adjudicator", "fix_replaced"),
    ("fix_wrong/lens", fix_wrong, "lens", "survived"),
    ("fix_wrong/inconclusive", fix_wrong, "inconclusive", "survived"),
    ("fix_wrong/none", fix_wrong, NO_VERDICT, "disputed"),
    ("unreachable/adjudicator", unreachable, "adjudicator", "unreachable"),
    ("unreachable/lens", unreachable, "lens", "survived"),
    ("unreachable/inconclusive", unreachable, "inconclusive", "disputed"),
    ("unreachable/none", unreachable, NO_VERDICT, "disputed"),
])
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_outcome_table_rows(tmp_path, capsys, row, ruling_factory, winner, outcome, seed):
    original = finding(1, severity="Must fix")
    ruling = ruling_factory("A1")
    result = pipeline(tmp_path, capsys, [original], [ruling], {"A1": winner}, seed=seed)
    tally = result["adjudication"]["tally"]
    if outcome == "dropped":
        assert result["findings"] == []
        assert result["adjudication"]["checked_and_dropped"] == [{
            "file": "f1.py", "line": "11", "title": "Title 1",
            "reason": ruling["objection"], "proof": "users.py:12 `if not row.email: raise`"}]
        assert tally["dropped"] == 1 and tally["checked"] == 1
        return
    assert result["adjudication"]["checked_and_dropped"] == []
    [out] = result["findings"]
    assert "id" not in out
    adjudication = out["adjudication"]
    assert adjudication["outcome"] == outcome
    assert adjudication["objection"] == ruling["objection"]
    if outcome == "disputed":
        expected = ("Prover did not return; check the objection by hand." if winner == NO_VERDICT
                    else adjudication["what_would_settle"])
        assert adjudication["what_would_settle"] == expected and expected
    else:
        assert adjudication["what_would_settle"] is None
    if outcome == "fix_replaced":
        assert out["recommendation"] == ruling["replacement"]["recommendation"]
        assert out["fix_md"] == "Clamp the end index"
        assert adjudication["original_fix"] == {"fix_md": "Short fix 1", "recommendation": "Fix text 1"}
    else:
        assert out["recommendation"] == "Fix text 1" and out["fix_md"] == "Short fix 1"
        assert adjudication["original_fix"] is None
    if outcome == "unreachable":
        assert out["severity"] == "Nit"
        assert adjudication["severity_change"]["from"] == "Must fix"
        assert adjudication["severity_change"]["to"] == "Nit"
        assert out["production"] == ruling["production"] and out["production"]["label"] == "Unreachable"
    else:
        assert out["severity"] == "Must fix" and adjudication["severity_change"] is None
    if ruling_factory is unreachable and outcome == "survived":
        assert out["production"] == {"label": "Edge case", "path": "client.fetch called from production code"}
    elif ruling_factory is unreachable and outcome == "disputed":
        assert out["production"] == {"label": "Edge case", "path": "client.fetch called from production code"}
    elif outcome != "unreachable":
        assert out["production"] == ruling["production"]
    if winner not in (NO_VERDICT,):
        assert adjudication["proof"] == "users.py:12 `if not row.email: raise`"
    else:
        assert adjudication["proof"] is None


def test_agree_keeps_finding_and_adds_production_with_null_adjudication_fields(tmp_path, capsys):
    result = pipeline(tmp_path, capsys, [finding(1)], [agree("A1")])
    [out] = result["findings"]
    assert out["adjudication"] == {"outcome": "agreed", "objection": None, "proof": None,
                                   "what_would_settle": None, "severity_change": None, "original_fix": None}
    assert out["production"] == {"label": "Common path", "path": "POST /x -> handler"}
    assert {key: value for key, value in out.items() if key not in ("production", "adjudication")} == finding(1)
    assert result["adjudication"] == {
        "status": "complete", "model": None, "reason": None,
        "tally": {"checked": 1, "agreed": 1, "dropped": 0, "fixes_replaced": 0, "unreachable": 0,
                  "survived": 0, "disputed": 0, "merged": 0},
        "checked_and_dropped": []}
    assert result["warnings"] == []


def test_unreachable_lens_win_prefers_the_provers_production_path(tmp_path, capsys):
    result = pipeline(tmp_path, capsys, [finding(1)], [unreachable("A1")],
                      {"A1": {"winner": "lens", "production_path": "cli run -> client.fetch"}})
    assert result["findings"][0]["production"] == {"label": "Edge case", "path": "cli run -> client.fetch"}


@pytest.mark.parametrize("winner", ["lens", "adjudicator"])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_verdict_side_maps_through_the_job_assignment(tmp_path, capsys, winner, seed):
    result = pipeline(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], {"A1": winner}, seed=seed)
    expected = "dropped" if winner == "adjudicator" else "survived"
    assert (result["findings"] == []) == (expected == "dropped")
    if expected == "survived":
        assert result["findings"][0]["adjudication"]["outcome"] == "survived"


@pytest.mark.parametrize("winner", ["lens", "adjudicator", "inconclusive"])
def test_evidence_kind_none_is_treated_as_inconclusive(tmp_path, capsys, winner):
    verdict = {"winner": winner, "evidence_kind": "none", "evidence": "I argue it is guarded.",
               "what_would_settle": "the deployed value of DEBUG"}
    result = pipeline(tmp_path, capsys, [finding(1), finding(2)], [issue_wrong("A1"), fix_wrong("A2")],
                      {"A1": verdict, "A2": verdict})
    outcomes = {item["title"]: item["adjudication"] for item in result["findings"]}
    assert outcomes["Title 1"]["outcome"] == "disputed"
    assert outcomes["Title 1"]["what_would_settle"] == "the deployed value of DEBUG"
    assert outcomes["Title 2"]["outcome"] == "survived"
    assert result["adjudication"]["checked_and_dropped"] == []


def test_inconclusive_without_settle_text_still_disputes_with_default_text(tmp_path, capsys):
    result = pipeline(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], {"A1": "inconclusive"})
    assert result["findings"][0]["adjudication"]["what_would_settle"]


def test_fix_replacement_updates_present_fields_only(tmp_path, capsys):
    bare = finding(1)
    for key in ("recommendation_md", "fix_md"):
        del bare[key]
    rich = finding(2)
    result = pipeline(tmp_path, capsys, [bare, rich], [fix_wrong("A1"), fix_wrong("A2")],
                      {"A1": "adjudicator", "A2": "adjudicator"})
    first, second = result["findings"]
    diff = "```diff\n-a\n+b\n```"
    assert first["recommendation"] == diff and "recommendation_md" not in first
    assert first["fix_md"] == "Clamp the end index"
    assert first["adjudication"]["original_fix"] == {"fix_md": None, "recommendation": "Fix text 1"}
    assert second["recommendation"] == diff and second["recommendation_md"] == diff
    assert second["fix_md"] == "Clamp the end index"
    assert second["adjudication"]["original_fix"] == {"fix_md": "Short fix 2", "recommendation": "Fix text 2"}


def test_severity_change_is_applied_and_recorded(tmp_path, capsys):
    result = pipeline(tmp_path, capsys, [finding(1, severity="Must fix"), finding(2)],
                      [agree("A1", severity="Should fix", severity_reason="Only a log line is wrong."),
                       agree("A2", severity="Should fix", severity_reason="same")])
    first, second = result["findings"]
    assert first["severity"] == "Should fix"
    assert first["adjudication"]["severity_change"] == {
        "from": "Must fix", "to": "Should fix", "reason": "Only a log line is wrong."}
    assert second["adjudication"]["severity_change"] is None


def test_severity_change_applies_to_disputed_and_survived_but_not_dropped(tmp_path, capsys):
    result = pipeline(
        tmp_path, capsys, [finding(n, severity="Must fix") for n in (1, 2, 3)],
        [issue_wrong("A1", severity="Nit", severity_reason="r1"),
         issue_wrong("A2", severity="Nit", severity_reason="r2"),
         issue_wrong("A3", severity="Nit", severity_reason="r3")],
        {"A1": "lens", "A2": "inconclusive", "A3": "adjudicator"})
    assert [item["severity"] for item in result["findings"]] == ["Nit", "Nit"]
    assert [item["adjudication"]["severity_change"]["reason"] for item in result["findings"]] == ["r1", "r2"]


def test_merge_across_agreed_findings(tmp_path, capsys):
    findings = [finding(1, dimension="correctness", dimensions=["correctness"], severity="Should fix"),
                finding(2, dimension="db", dimensions=["db"], severity="Must fix"),
                finding(3)]
    rulings = [agree("A1"), agree("A2"), agree("A3")]
    result = pipeline(tmp_path, capsys, findings, rulings,
                      merges=[{"ids": ["A1", "A2"], "anchor": "A2", "reason": "one missing transaction"}])
    assert [item["title"] for item in result["findings"]] == ["Title 2", "Title 3"]
    anchor = result["findings"][0]
    assert anchor["file"] == "f2.py" and anchor["line"] == "12"
    assert anchor["dimensions"] == ["correctness", "db"] and anchor["dimension"] == "correctness"
    assert anchor["severity"] == "Must fix"
    assert anchor["adjudication"]["merged_from"] == [{"file": "f1.py", "line": "11", "dimension": "correctness"}]
    assert result["adjudication"]["tally"]["merged"] == 1
    assert result["adjudication"]["tally"]["agreed"] == 3
    assert result["warnings"] == []


def test_merge_takes_the_strongest_severity_from_a_member(tmp_path, capsys):
    findings = [finding(1, severity="Must fix"), finding(2, severity="Nit")]
    result = pipeline(tmp_path, capsys, findings, [agree("A1"), agree("A2")],
                      merges=[{"ids": ["A1", "A2"], "anchor": "A2", "reason": "same root"}])
    [anchor] = result["findings"]
    assert anchor["severity"] == "Must fix"
    assert anchor["adjudication"]["severity_change"]["from"] == "Nit"
    assert anchor["adjudication"]["severity_change"]["to"] == "Must fix"


@pytest.mark.parametrize("bad", [
    {"ids": ["A1", "A2"], "anchor": "A1", "reason": "r"},
    {"ids": ["A1", "A9"], "anchor": "A1", "reason": "r"},
    {"ids": ["A1"], "anchor": "A1", "reason": "r"},
    {"ids": ["A1", "A3"], "anchor": "A2", "reason": "r"},
])
def test_bad_merges_are_skipped_with_a_warning_not_an_error(tmp_path, capsys, bad):
    findings = [finding(1), finding(2), finding(3)]
    rulings = [agree("A1"), issue_wrong("A2"), agree("A3")]
    result = pipeline(tmp_path, capsys, findings, rulings, {"A2": "lens"}, merges=[bad])
    assert [item["title"] for item in result["findings"]] == ["Title 1", "Title 2", "Title 3"]
    assert len(result["warnings"]) == 1
    assert result["adjudication"]["tally"]["merged"] == 0


def test_overlapping_merges_skip_the_second_with_a_warning(tmp_path, capsys):
    findings = [finding(1), finding(2), finding(3)]
    result = pipeline(tmp_path, capsys, findings, [agree("A1"), agree("A2"), agree("A3")],
                      merges=[{"ids": ["A1", "A2"], "anchor": "A1", "reason": "r"},
                              {"ids": ["A2", "A3"], "anchor": "A3", "reason": "r"}])
    assert [item["title"] for item in result["findings"]] == ["Title 1", "Title 3"]
    assert len(result["warnings"]) == 1


def test_output_restores_input_order_and_strips_ids(tmp_path, capsys):
    findings = [finding(n) for n in range(1, 11)]
    result = pipeline(tmp_path, capsys, findings, [agree("A%d" % n) for n in range(1, 11)], seed=11)
    assert [item["title"] for item in result["findings"]] == ["Title %d" % n for n in range(1, 11)]
    assert all("id" not in item and "production" in item and "adjudication" in item
               for item in result["findings"])


def test_dropped_entry_title_falls_back_to_the_start_of_the_issue(tmp_path, capsys):
    untitled = finding(1, issue="word " * 40)
    del untitled["title"]
    result = pipeline(tmp_path, capsys, [untitled], [issue_wrong("A1")], {"A1": "adjudicator"})
    [entry] = result["adjudication"]["checked_and_dropped"]
    assert entry["title"].startswith("word word") and 70 <= len(entry["title"]) <= 81


def test_tally_counts_every_outcome(tmp_path, capsys):
    findings = [finding(n) for n in range(1, 8)]
    rulings = [agree("A1"), issue_wrong("A2"), issue_wrong("A3"), fix_wrong("A4"), unreachable("A5"),
               issue_wrong("A6"), fix_wrong("A7")]
    result = pipeline(tmp_path, capsys, findings, rulings, {
        "A2": "adjudicator", "A3": "lens", "A4": "adjudicator", "A5": "adjudicator",
        "A6": "inconclusive", "A7": NO_VERDICT})
    assert result["adjudication"]["tally"] == {
        "checked": 7, "agreed": 1, "dropped": 1, "fixes_replaced": 1, "unreachable": 1,
        "survived": 1, "disputed": 2, "merged": 0}


def test_na_and_would_miss_labels_follow_the_dimension_rules(tmp_path, capsys):
    conventions = finding(1, dimension="conventions", dimensions=["conventions"])
    tests = finding(2, dimension="test-adequacy", dimensions=["test-adequacy"])
    result = pipeline(tmp_path, capsys, [conventions, tests], [
        agree("A1", production={"label": "N/A", "path": "conventions"}),
        agree("A2", production={"label": "Would miss", "path": "refunds over the charge being accepted"})])
    assert [item["production"]["label"] for item in result["findings"]] == ["N/A", "Would miss"]


def mutate(rulings, index, **changes):
    rulings = copy.deepcopy(rulings)
    rulings[index].update(changes)
    return rulings


def raw_rulings(rulings, merges=()):
    return {"rulings": rulings, "merges": list(merges)}


MALFORMED = [
    ("duplicate id", lambda r: r + [copy.deepcopy(r[0])], "A1"),
    ("missing id", lambda r: r[:-1], "A2"),
    ("unknown id", lambda r: r + [agree("A99")], "A99"),
    ("unknown ruling", lambda r: mutate(r, 0, ruling="maybe"), "ruling"),
    ("fix_wrong without replacement", lambda r: mutate(r, 1, ruling="fix_wrong", objection="o", replacement=None), "replacement"),
    ("replacement on agree", lambda r: mutate(r, 0, replacement={"fix_md": "x", "recommendation": "y"}), "replacement"),
    ("issue_wrong without objection", lambda r: mutate(r, 1, ruling="issue_wrong", objection=None), "objection"),
    ("objection on agree", lambda r: mutate(r, 0, objection="no"), "objection"),
    ("unreachable without trigger path", lambda r: mutate(r, 1, ruling="unreachable", objection="o",
                                                         production={"label": "Unreachable", "path": "p"},
                                                         lens_trigger_path=None), "lens_trigger_path"),
    ("unreachable with wrong label", lambda r: mutate(r, 1, ruling="unreachable", objection="o",
                                                      lens_trigger_path="t"), "production.label"),
    ("severity without reason", lambda r: mutate(r, 0, severity="Nit"), "severity_reason"),
    ("reason without severity", lambda r: mutate(r, 0, severity_reason="why"), "severity_reason"),
    ("bad severity", lambda r: mutate(r, 0, severity="Critical", severity_reason="r"), "severity"),
    ("bad label", lambda r: mutate(r, 0, production={"label": "Rare", "path": "p"}), "production.label"),
    ("missing production", lambda r: mutate(r, 0, production=None), "production"),
    ("over-cap production path", lambda r: mutate(r, 0, production={"label": "Common path", "path": "x" * 201}), "production.path"),
    ("multi-line production path", lambda r: mutate(r, 0, production={"label": "Common path", "path": "a\nb"}), "production.path"),
    ("empty production path", lambda r: mutate(r, 0, production={"label": "Common path", "path": " "}), "production.path"),
    ("N/A path not the dimension", lambda r: mutate(r, 0, production={"label": "N/A", "path": "comments"}), "production.path"),
    ("Would miss on a non-test finding", lambda r: mutate(r, 0, production={"label": "Would miss", "path": "p"}), "production.label"),
    ("over-cap replacement fix_md", lambda r: mutate(r, 1, ruling="fix_wrong", objection="o",
                                                     replacement={"fix_md": "x" * 161, "recommendation": DIFF}), "fix_md"),
    ("replacement without recommendation", lambda r: mutate(r, 1, ruling="fix_wrong", objection="o",
                                                            replacement={"fix_md": "x"}), "recommendation"),
    ("identity word in objection", lambda r: mutate(r, 1, ruling="issue_wrong", objection="The lens missed the guard."), "objection"),
    ("identity word in trigger path", lambda r: mutate(r, 1, ruling="unreachable", objection="o",
                                                       production={"label": "Unreachable", "path": "p"},
                                                       lens_trigger_path="Opus says it runs"), "lens_trigger_path"),
    ("identity word in replacement", lambda r: mutate(r, 1, ruling="fix_wrong", objection="o",
                                                      replacement={"fix_md": "x", "recommendation": "```diff\n+per the reviewer\n```"}), "replacement"),
    ("ruling not an object", lambda r: r + ["oops"], "rulings"),
    ("merge not an object", None, "merges"),
]


@pytest.mark.parametrize("name,change,needle", MALFORMED, ids=[m[0] for m in MALFORMED])
@pytest.mark.parametrize("command", ["jobs", "apply"])
def test_malformed_rulings_exit_2_naming_the_field(tmp_path, capsys, name, change, needle, command):
    findings = [finding(1), finding(2)]
    base = [agree("A1"), agree("A2")]
    mod, paths = build(tmp_path, capsys, findings, base)
    if change is None:
        write(Path(paths["rulings"]), {"rulings": base, "merges": ["oops"]})
    else:
        write(Path(paths["rulings"]), raw_rulings(change(base)))
    if command == "jobs":
        code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--out", paths["jobs"], "--seed", "1")
    else:
        write(Path(paths["jobs"]), {"seed": 1, "jobs": []})
        write(Path(paths["verdicts"]), {"verdicts": []})
        code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2
    assert needle in out["error"] and "rulings" in out["error"]
    assert not Path(paths["jobs" if command == "jobs" else "out"]).exists()


def test_identity_words_are_allowed_in_lens_text(tmp_path, capsys):
    lens_text = finding(1, issue="The lens variable shadows the adjudicator module.")
    mod, paths = build(tmp_path, capsys, [lens_text], [issue_wrong("A1")])
    assert run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
               "--out", paths["jobs"], "--seed", "1")[0] == 0


def test_unknown_job_in_verdicts_is_an_error(tmp_path, capsys):
    mod, paths = build(tmp_path, capsys, [finding(1)], [issue_wrong("A1")])
    run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"], "--out", paths["jobs"])
    write(Path(paths["verdicts"]), {"verdicts": [{"job": "J9", "verdict": "A", "evidence_kind": "quote", "evidence": "e"}]})
    code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2 and "J9" in out["error"] and "verdicts" in out["error"]
    assert not Path(paths["out"]).exists()


def test_unusable_verdict_becomes_disputed_with_a_warning_never_a_drop(tmp_path, capsys):
    mod, paths = build(tmp_path, capsys, [finding(1)], [issue_wrong("A1")])
    run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"], "--out", paths["jobs"])
    write(Path(paths["verdicts"]), {"verdicts": [{"job": "J1", "verdict": "maybe"}]})
    code, _ = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                  "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    result = json.loads(Path(paths["out"]).read_text())
    assert code == 0 and result["findings"][0]["adjudication"]["outcome"] == "disputed"
    assert result["warnings"]


def test_jobs_file_must_cover_every_disagreement(tmp_path, capsys):
    mod, paths = build(tmp_path, capsys, [finding(1)], [issue_wrong("A1")])
    write(Path(paths["jobs"]), {"seed": 1, "jobs": []})
    write(Path(paths["verdicts"]), {"verdicts": []})
    code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2 and "A1" in out["error"]


def test_missing_file_exits_2_naming_it(tmp_path, capsys):
    mod = module()
    code, out = run(mod, capsys, "jobs", "--input", str(tmp_path / "nope.json"),
                    "--rulings", str(tmp_path / "r.json"), "--out", str(tmp_path / "o.json"))
    assert code == 2 and "input" in out["error"]


def test_bad_arguments_exit_2_with_a_json_error(capsys):
    mod = module()
    code, out = run(mod, capsys, "prepare")
    assert code == 2 and "error" in out


def test_jobs_execution_defaults_to_disabled_and_can_be_enabled(tmp_path, capsys):
    findings = [finding(1), finding(2), finding(3)]
    mod, paths = build(tmp_path, capsys, findings, [issue_wrong("A1"), fix_wrong("A2"), unreachable("A3")])
    base = ["jobs", "--input", paths["input"], "--rulings", paths["rulings"], "--out", paths["jobs"], "--seed", "1"]
    assert run(mod, capsys, *base)[0] == 0
    packets = [job["packet"] for job in json.loads(Path(paths["jobs"]).read_text())["jobs"]]
    assert len(packets) == 3 and {packet["execution"] for packet in packets} == {"disabled"}
    assert run(mod, capsys, *base, "--execution", "enabled")[0] == 0
    packets = [job["packet"] for job in json.loads(Path(paths["jobs"]).read_text())["jobs"]]
    assert len(packets) == 3 and {packet["execution"] for packet in packets} == {"enabled"}


def test_jobs_execution_rejects_other_values(tmp_path, capsys):
    mod, paths = build(tmp_path, capsys, [finding(1)], [issue_wrong("A1")])
    code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--out", paths["jobs"], "--execution", "maybe")
    assert code == 2 and "execution" in out["error"]


def jobs_apply(tmp_path, capsys, findings, rulings, edit_jobs):
    """Build real jobs, let `edit_jobs` tamper with the job list, then run apply."""
    mod, paths = build(tmp_path, capsys, findings, rulings)
    assert run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
               "--out", paths["jobs"], "--seed", "1")[0] == 0
    doc = json.loads(Path(paths["jobs"]).read_text())
    doc["jobs"] = edit_jobs(doc["jobs"])
    write(Path(paths["jobs"]), doc)
    write(Path(paths["verdicts"]), {"verdicts": []})
    code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    return code, out, paths


def rejected(code, out, paths, *needles):
    assert code == 2
    assert "prover-jobs.json" in out["error"]
    for needle in needles:
        assert needle in out["error"]
    assert not Path(paths["out"]).exists()


def test_duplicate_job_id_is_rejected(tmp_path, capsys):
    findings = [finding(1), finding(2), finding(3)]
    rulings = [issue_wrong("A1"), issue_wrong("A2"), agree("A3")]

    def duplicate(jobs):
        jobs[1]["job"] = jobs[0]["job"]
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, findings, rulings, duplicate)
    rejected(code, out, paths, "job id")


def test_job_for_an_agreed_finding_is_rejected(tmp_path, capsys):
    findings = [finding(1), finding(2)]
    rulings = [issue_wrong("A1"), agree("A2")]

    def retarget(jobs):
        jobs.append({**jobs[0], "job": "J9", "finding": "A2"})
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, findings, rulings, retarget)
    rejected(code, out, paths, "J9", "A2")


def test_two_jobs_for_one_finding_are_rejected(tmp_path, capsys):
    findings = [finding(1)]

    def twice(jobs):
        jobs.append({**jobs[0], "job": "J2"})
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, findings, [issue_wrong("A1")], twice)
    rejected(code, out, paths, "J2", "A1")


def test_missing_job_for_a_disagreement_is_rejected_when_others_exist(tmp_path, capsys):
    findings = [finding(1), finding(2)]
    rulings = [issue_wrong("A1"), fix_wrong("A2")]

    def drop_one(jobs):
        return [job for job in jobs if job["finding"] == "A1"]

    code, out, paths = jobs_apply(tmp_path, capsys, findings, rulings, drop_one)
    rejected(code, out, paths, "A2")


@pytest.mark.parametrize("bad", ["both", None, ""])
def test_bad_a_is_is_rejected(tmp_path, capsys, bad):
    def corrupt(jobs):
        jobs[0]["a_is"] = bad
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], corrupt)
    rejected(code, out, paths, "a_is")


def test_job_ruling_that_differs_from_the_rulings_file_is_rejected(tmp_path, capsys):
    def swap(jobs):
        jobs[0]["ruling"] = {**jobs[0]["ruling"], "ruling": "fix_wrong"}
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], swap)
    rejected(code, out, paths, "J1", "A1")


def test_unknown_finding_in_a_job_is_rejected(tmp_path, capsys):
    def rename(jobs):
        jobs[0]["finding"] = "A7"
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], rename)
    rejected(code, out, paths, "A7")


def render_module():
    return importlib.import_module("render_report")


UNSAFE_CHARS = [" ", " ", "\r", "\n"]


def one_line_cases():
    return [
        ("production.path", lambda ch: issue_wrong("A1", production={"label": "Common path", "path": "a%sb" % ch})),
        ("fix_md", lambda ch: fix_wrong("A1", replacement={"fix_md": "a%sb" % ch, "recommendation": DIFF})),
        ("severity_reason", lambda ch: issue_wrong("A1", severity="Nit", severity_reason="a%sb" % ch)),
        ("lens_trigger_path", lambda ch: {**unreachable("A1"), "lens_trigger_path": "a%sb" % ch}),
    ]


@pytest.mark.parametrize("char", UNSAFE_CHARS, ids=["u2028", "u2029", "cr", "lf"])
@pytest.mark.parametrize("field,make", one_line_cases(), ids=[case[0] for case in one_line_cases()])
@pytest.mark.parametrize("command", ["jobs", "apply"])
def test_one_line_fields_reject_every_character_the_renderer_rejects(tmp_path, capsys, field, make, char, command):
    mod, paths = build(tmp_path, capsys, [finding(1)], [make(char)])
    if command == "jobs":
        code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--out", paths["jobs"], "--seed", "1")
    else:
        write(Path(paths["jobs"]), {"seed": 1, "jobs": []})
        write(Path(paths["verdicts"]), {"verdicts": []})
        code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2 and field in out["error"]


@pytest.mark.parametrize("char", [" ", " "])
def test_merge_reason_rejects_unicode_line_separators(tmp_path, capsys, char):
    mod, paths = build(tmp_path, capsys, [finding(1), finding(2)], [agree("A1"), agree("A2")],
                       merges=[{"ids": ["A1", "A2"], "anchor": "A1", "reason": "same%sbug" % char}])
    code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--out", paths["jobs"], "--seed", "1")
    assert code == 2 and "reason" in out["error"]


def test_apply_accepts_exactly_what_the_renderer_accepts(tmp_path, capsys):
    mod = module()
    renderer = render_module()
    assert mod.UNSAFE_LINE is renderer.UNSAFE_LINE
    path = "POST /x‧ handler \u0085\u000b\u000c end"
    fix_md = "Clamp​ the end\u0085 index"
    rulings = [agree("A1", production={"label": "Common path", "path": path}),
               fix_wrong("A2", replacement={"fix_md": fix_md, "recommendation": DIFF})]
    result = pipeline(tmp_path, capsys, [finding(1), finding(2)], rulings,
                      verdicts={"A2": "adjudicator"})
    for item in result["findings"]:
        renderer._validate_production(item["production"], "finding")
    assert result["findings"][0]["production"]["path"] == path
    renderer._validate_posted_text(result["findings"][1], "finding")
    assert result["findings"][1]["fix_md"] == fix_md


EDGE_CHARS = [" ", " ", "\n", "\r"]


def edge_cases():
    return [
        ("production.path", lambda text: agree("A1", production={"label": "Common path", "path": text})),
        ("fix_md", lambda text: fix_wrong("A1", replacement={"fix_md": text, "recommendation": DIFF})),
        ("objection", lambda text: {**issue_wrong("A1"), "objection": text}),
        ("severity_reason", lambda text: agree("A1", severity="Nit", severity_reason=text)),
        ("lens_trigger_path", lambda text: {**unreachable("A1"), "lens_trigger_path": text}),
    ]


@pytest.mark.parametrize("char", EDGE_CHARS, ids=["u2028", "u2029", "lf", "cr"])
@pytest.mark.parametrize("edge", ["leading", "trailing"])
@pytest.mark.parametrize("field,make", edge_cases(), ids=[case[0] for case in edge_cases()])
@pytest.mark.parametrize("command", ["jobs", "apply"])
def test_one_line_fields_reject_unsafe_characters_at_either_end(tmp_path, capsys, field, make, edge, char, command):
    text = char + "value" if edge == "leading" else "value" + char
    mod, paths = build(tmp_path, capsys, [finding(1)], [make(text)])
    if command == "jobs":
        code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--out", paths["jobs"], "--seed", "1")
    else:
        write(Path(paths["jobs"]), {"seed": 1, "jobs": []})
        write(Path(paths["verdicts"]), {"verdicts": []})
        code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2 and field in out["error"]
    assert not Path(paths["jobs" if command == "jobs" else "out"]).exists()


@pytest.mark.parametrize("command", ["jobs", "apply"])
@pytest.mark.parametrize("name,ruling,needle", [
    ("multi-line objection", lambda: {**issue_wrong("A1"), "objection": "first line\nsecond line"}, "objection"),
    ("unfenced recommendation", lambda: fix_wrong("A1", replacement={"fix_md": "x", "recommendation": "change a to b"}),
     "recommendation"),
    ("differently fenced recommendation",
     lambda: fix_wrong("A1", replacement={"fix_md": "x", "recommendation": "```python\na = b\n```"}), "recommendation"),
    ("fence info string only starts with diff",
     lambda: fix_wrong("A1", replacement={"fix_md": "x", "recommendation": "```different\n-a\n+b\n```"}), "recommendation"),
    ("fence info string has a suffix after diff",
     lambda: fix_wrong("A1", replacement={"fix_md": "x", "recommendation": "```diffx\n-a\n+b\n```"}), "recommendation"),
    ("unclosed diff fence",
     lambda: fix_wrong("A1", replacement={"fix_md": "x", "recommendation": "```diff\n-a\n+b"}), "recommendation"),
])
def test_prompt_contract_shapes_are_enforced(tmp_path, capsys, command, name, ruling, needle):
    mod, paths = build(tmp_path, capsys, [finding(1)], [ruling()])
    if command == "jobs":
        code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--out", paths["jobs"], "--seed", "1")
    else:
        write(Path(paths["jobs"]), {"seed": 1, "jobs": []})
        write(Path(paths["verdicts"]), {"verdicts": []})
        code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                        "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    assert code == 2 and needle in out["error"]


def test_recommendation_with_prose_around_a_diff_fence_is_accepted(tmp_path, capsys):
    recommendation = "Guard the index:\n```diff\n-a\n+b\n```"
    result = pipeline(tmp_path, capsys, [finding(1)],
                      [fix_wrong("A1", replacement={"fix_md": "x", "recommendation": recommendation})],
                      verdicts={"A1": "adjudicator"})
    assert result["findings"][0]["recommendation"] == recommendation


def test_recommendation_diff_fence_tolerates_trailing_whitespace(tmp_path, capsys):
    recommendation = "```diff \t\n-a\n+b\n```  "
    result = pipeline(tmp_path, capsys, [finding(1)],
                      [fix_wrong("A1", replacement={"fix_md": "x", "recommendation": recommendation})],
                      verdicts={"A1": "adjudicator"})
    assert result["findings"][0]["recommendation"] == recommendation.strip()


def test_unclosed_diff_fences_are_rejected_in_linear_time(tmp_path, capsys):
    recommendation = "```diff\n" * 20000
    mod, paths = build(tmp_path, capsys, [finding(1)],
                       [fix_wrong("A1", replacement={"fix_md": "x", "recommendation": recommendation})])
    started = time.monotonic()
    code, out = run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--out", paths["jobs"], "--seed", "1")
    assert code == 2 and "recommendation" in out["error"]
    assert time.monotonic() - started < 2


def stale_apply(tmp_path, capsys, findings, rulings, changed_rulings=None, changed_findings=None):
    """Build jobs from one rulings/input pair, then apply against a changed pair."""
    mod, paths = build(tmp_path, capsys, findings, rulings)
    assert run(mod, capsys, "jobs", "--input", paths["input"], "--rulings", paths["rulings"],
               "--out", paths["jobs"], "--seed", "1")[0] == 0
    jobs = json.loads(Path(paths["jobs"]).read_text())["jobs"]
    write(Path(paths["verdicts"]), {"verdicts": [
        {"job": job["job"], "verdict": "A" if job["a_is"] == "adjudicator" else "B", "evidence_kind": "quote",
         "evidence": "users.py:12", "production_path": None, "what_would_settle": None} for job in jobs]})
    if changed_rulings is not None:
        write(Path(paths["rulings"]), {"rulings": changed_rulings, "merges": []})
    if changed_findings is not None:
        doc = json.loads(Path(paths["input"]).read_text())
        doc["findings"] = changed_findings(doc["findings"])
        write(Path(paths["input"]), doc)
    code, out = run(mod, capsys, "apply", "--input", paths["input"], "--rulings", paths["rulings"],
                    "--jobs", paths["jobs"], "--verdicts", paths["verdicts"], "--out", paths["out"])
    return code, out, paths


def test_apply_with_unchanged_rulings_and_input_is_not_stale(tmp_path, capsys):
    findings = [finding(1), finding(2), finding(3)]
    rulings = [issue_wrong("A1"), fix_wrong("A2"), unreachable("A3")]
    code, out, paths = stale_apply(tmp_path, capsys, findings, rulings)
    assert code == 0, out
    assert Path(paths["out"]).exists()


@pytest.mark.parametrize("name,original,changed,finding_id", [
    ("objection", issue_wrong("A1"), {**issue_wrong("A1"), "objection": "A different guard at users.py:40."}, "A1"),
    ("replacement recommendation", fix_wrong("A1"),
     fix_wrong("A1", replacement={"fix_md": "Clamp the end index", "recommendation": "```diff\n-a\n+c\n```"}), "A1"),
    ("lens_trigger_path", unreachable("A1"),
     {**unreachable("A1"), "lens_trigger_path": "client.fetch called from a cron entry point"}, "A1"),
    ("unreachable objection", unreachable("A1"),
     {**unreachable("A1"), "objection": "Only tests/other.py:3 calls it."}, "A1"),
])
def test_apply_rejects_a_job_whose_rulings_changed_with_the_same_ruling_kind(
        tmp_path, capsys, name, original, changed, finding_id):
    code, out, paths = stale_apply(tmp_path, capsys, [finding(1)], [original], changed_rulings=[changed])
    assert code == 2
    assert "prover-jobs.json" in out["error"] and "J1" in out["error"] and "stale" in out["error"]
    assert not Path(paths["out"]).exists()


@pytest.mark.parametrize("key,rulings", [
    ("issue", [issue_wrong("A1")]),
    ("recommendation", [fix_wrong("A1")]),
    ("file", [issue_wrong("A1")]),
    ("line", [issue_wrong("A1")]),
])
def test_apply_rejects_a_job_whose_input_finding_changed(tmp_path, capsys, key, rulings):
    def change(items):
        items[0][key] = "changed"
        return items

    code, out, paths = stale_apply(tmp_path, capsys, [finding(1)], rulings, changed_findings=change)
    assert code == 2 and "stale" in out["error"] and "J1" in out["error"]
    assert not Path(paths["out"]).exists()


def test_apply_rejects_a_job_with_a_tampered_packet_side(tmp_path, capsys):
    def swap(jobs):
        packet = jobs[0]["packet"]
        packet["claim_a"], packet["claim_b"] = packet["claim_b"], packet["claim_a"]
        return jobs

    code, out, paths = jobs_apply(tmp_path, capsys, [finding(1)], [issue_wrong("A1")], swap)
    rejected(code, out, paths, "J1", "stale")
