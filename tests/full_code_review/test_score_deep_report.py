"""Contract checks for the deep review scoring CLI and answer key."""
import contextlib
import io
import json
from pathlib import Path

import pytest

import score_deep_report as scorer


ANSWER_KEY = (Path(__file__).resolve().parents[1] / "fixtures" / "full-code-review"
              / "answer-keys" / "pr50-3605fd8.json")


def _key(*defects):
    return {"schema_version": 1, "target": {"project": "example/review", "number": 50},
            "defects": list(defects), "examined_non_defects": []}


def _defect(identifier="AK-01", **overrides):
    return dict({"id": identifier, "title": "Path fails", "severity": "Should fix",
                 "anchors": [{"file": "src/flow.py", "line_min": 20, "line_max": 35}],
                 "keywords": ["path"]}, **overrides)


def _finding(identifier="F1", **overrides):
    return dict({"id": identifier, "severity": "Should fix", "file": "src/flow.py",
                 "line": "25", "title": "Invalid path"}, **overrides)


def _score_cli(tmp_path, report, key, *, check=None, budget=None, out=None):
    report_path = tmp_path / "report.json"
    key_path = tmp_path / "key.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    key_path.write_text(json.dumps(key), encoding="utf-8")
    argv = ["--report", str(report_path), "--answer-key", str(key_path)]
    if check is not None:
        check_path = tmp_path / "spot.json"
        check_path.write_text(json.dumps(check), encoding="utf-8")
        argv.extend(["--spot-check", str(check_path)])
    if budget is not None:
        argv.extend(["--budget-minutes", str(budget)])
    if out is not None:
        argv.extend(["--out", str(out)])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = scorer.main(argv)
    return code, json.loads(output.getvalue())


def test_answer_key_has_all_verified_defects_and_non_defect_dispositions():
    key = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
    assert key["schema_version"] == 1
    assert key["target"]["number"] == 50
    assert key["target"]["head_sha"] == "3605fd8"
    assert [item["id"] for item in key["defects"]] == ["AK-%02d" % i for i in range(1, 20)]
    assert all(item["severity"] == "Should fix" and item["anchors"] and item["keywords"]
               and item["source_ids"] for item in key["defects"])
    assert all(all(anchor["line_min"] <= anchor["line_max"] for anchor in item["anchors"])
               for item in key["defects"])
    assert all(set(("source_id", "file", "line", "disposition", "reason")) <= set(item)
               for item in key["examined_non_defects"])
    non_defects = {item["source_id"]: item["disposition"]
                   for item in key["examined_non_defects"]}
    nits = {"B%d" % i for i in (14, 15, *range(17, 24), *range(25, 62))}
    assert len(key["examined_non_defects"]) == len(nits) + 2
    assert non_defects == {"B11": "plausible", "B24": "refuted",
                           **{identifier: "confirmed_nit" for identifier in nits}}


def test_full_answer_key_recall_with_independent_findings():
    key = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
    findings = [{"id": "F%d" % i, "severity": "Should fix", "file": d["anchors"][0]["file"],
                 "line": str(d["anchors"][0]["line_min"]), "title": d["keywords"][0]}
                for i, d in enumerate(key["defects"], 1)]
    result = scorer.score_report({"findings": findings}, key)
    assert result["passed"] is True
    assert result["caught_count"] == result["total_defects"] == 19
    assert result["recall"] == 1.0
    assert result["missed"] == []


@pytest.mark.parametrize("fragment", ["title", "issue", "body_md", "impact", "fix_md",
                                      "recommendation", "recommendation_md"])
def test_match_defect_accepts_each_supported_explanation_field(fragment):
    finding = _finding(line="15-21", title="")
    finding[fragment] = "a PATH validation bug"
    assert scorer.match_defect(_defect(), [finding]) == finding


def test_match_defect_requires_eligible_severity_exact_file_overlap_and_keyword():
    defect = _defect()
    for finding in (_finding(severity="Nit"), _finding(file="src/other.py"),
                    _finding(line="10-19"), _finding(title="Not related")):
        assert scorer.match_defect(defect, [finding]) is None
    assert scorer.match_defect(_defect(keywords=[]), [_finding(title="Not related")]) is not None
    assert scorer.match_defect(defect, [_finding(severity="Must fix", line="35-40")]) is not None
    assert scorer.match_defect(defect, [_finding(line="36-40")]) is None


def test_one_finding_can_cover_multiple_defects_without_changing_inputs():
    report = {"findings": [_finding()]}
    key = _key(_defect(), _defect("AK-02"))
    before = json.dumps((report, key))
    result = scorer.score_report(report, key)
    assert result["caught"] == [
        {"defect_id": item, "title": "Path fails", "finding_id": "F1",
         "file": "src/flow.py", "line": "25"} for item in ("AK-01", "AK-02")]
    assert result["caught_count"] == 2
    assert json.dumps((report, key)) == before
    assert scorer.score_report(report, key) == result


def test_partial_recall_exits_one_with_missed_anchors(tmp_path):
    code, score = _score_cli(tmp_path, {"findings": [_finding()]},
                             _key(_defect(), _defect("AK-02", anchors=[
                                 {"file": "other.py", "line_min": 1, "line_max": 4}])))
    assert code == 1
    assert score["caught_count"] == 1
    assert score["total_defects"] == 2
    assert score["recall"] == 0.5
    assert score["missed"] == [{"defect_id": "AK-02", "title": "Path fails",
                                "anchors": [{"file": "other.py", "line_min": 1, "line_max": 4}]}]


@pytest.mark.parametrize("wrapped", [True, False])
def test_spot_check_refutes_by_id_or_file_line_and_overrides_embedded_status(tmp_path, wrapped):
    report = {"findings": [_finding(), _finding("F2", line="27"),
                           _finding("F3", line="29", verification_status="refuted"),
                           _finding("F4", line="30")]}
    verdicts = {"F1": "refuted", "src/flow.py:27": "refuted", "F3": "confirmed"}
    check = {"verdicts": verdicts} if wrapped else verdicts
    original = json.dumps((report, check))
    code, score = _score_cli(tmp_path, report, _key(_defect()), check=check)
    assert code == 1
    assert score["shown_count"] == 4
    assert score["refuted_count"] == 2
    assert score["refuted_share"] == 0.5
    assert json.dumps((report, check)) == original


def test_embedded_refutations_without_spot_check_include_both_fields():
    report = {"findings": [_finding(spot_check="refuted"),
                           _finding("F2", verification_status="refuted"), _finding("F3")]}
    score = scorer.score_report(report, _key(_defect()))
    assert score["refuted_count"] == 2
    assert score["refuted_share"] == 2 / 3
    assert score["passed"] is False


def test_budget_and_output_file_match_stdout(tmp_path):
    report = {"findings": [_finding()], "run": {"deep": {"elapsed_minutes": 61}}}
    target = tmp_path / "nested" / "score.json"
    code, score = _score_cli(tmp_path, report, _key(_defect()), budget=60, out=target)
    assert code == 1
    assert score["elapsed_minutes"] == 61
    assert score["within_budget"] is False
    assert json.loads(target.read_text(encoding="utf-8")) == score
    assert scorer.score_report(report, _key(_defect()), budget_minutes=61)["passed"] is True

def test_cli_passes_with_refuted_share_exactly_on_threshold(tmp_path):
    findings = [_finding(line=str(25 + offset), id="F%d" % (offset + 1))
                for offset in range(5)]
    code, score = _score_cli(tmp_path, {"findings": findings}, _key(_defect()),
                             check={"F1": "refuted"})
    assert code == 0
    assert score["refuted_count"] == 1
    assert score["refuted_share"] == 0.2
    assert score["passed"] is True


@pytest.mark.parametrize("args", [
    [],
    ["--report", "report.json", "--answer-key", "key.json", "--budget-minutes", "not-a-number"],
])
def test_invalid_cli_arguments_return_json_error(args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = scorer.main(args)
    assert code == 2
    assert isinstance(json.loads(output.getvalue())["error"], str)


def test_empty_answer_key_and_empty_findings_pass():
    score = scorer.score_report({"findings": []}, _key())
    assert score["recall"] == 1.0
    assert score["shown_count"] == score["total_defects"] == score["refuted_count"] == 0
    assert score["refuted_share"] == 0.0
    assert score["elapsed_minutes"] is None
    assert score["within_budget"] is score["passed"] is True


@pytest.mark.parametrize("report,key", [
    ({}, _key()),
    ({"findings": "not a list"}, _key()),
    ({"findings": ["not an object"]}, _key()),
    ({"findings": []}, {**_key(), "schema_version": 2}),
    ({"findings": []}, {"schema_version": 1, "defects": [], "examined_non_defects": []}),
    ({"findings": []}, _key({**_defect(), "anchors": [{"file": "src/flow.py", "line_min": 9}]})),
    ({"findings": []}, {**_key(), "examined_non_defects": ["not an object"]}),
])
def test_bad_schema_returns_error_json_and_exit_two(tmp_path, report, key):
    code, result = _score_cli(tmp_path, report, key)
    assert code == 2
    assert isinstance(result["error"], str) and result["error"]


def test_unreadable_or_malformed_input_returns_error_json(tmp_path):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = scorer.main(["--report", str(tmp_path / "missing.json"),
                            "--answer-key", str(tmp_path / "also-missing.json")])
    assert code == 2
    assert "error" in json.loads(output.getvalue())
