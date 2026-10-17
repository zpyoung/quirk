"""Contract checks for the deep review scoring CLI and answer key."""
import contextlib
import io
import json
from pathlib import Path

import pytest

import score_deep_report as scorer


ANSWER_KEY = (Path(__file__).resolve().parents[1] / "fixtures" / "full-code-review"
              / "answer-keys" / "pr50-3605fd8.json")


HEAD = "3605fd8" + "a" * 33


def _key(*defects):
    return {"schema_version": 1,
            "target": {"project": "example/review", "number": 50, "head_sha": HEAD},
            "defects": list(defects), "examined_non_defects": []}


def _defect(identifier="AK-01", **overrides):
    return dict({"id": identifier, "title": "Path fails", "severity": "Should fix",
                 "anchors": [{"file": "src/flow.py", "line_min": 20, "line_max": 35}],
                 "keywords": ["path"]}, **overrides)


def _finding(identifier="F1", **overrides):
    return dict({"id": identifier, "severity": "Should fix", "file": "src/flow.py",
                 "line": "25", "title": "Invalid path", "verification_status": "confirmed"},
                **overrides)


def _report(findings=None, *, elapsed=30, incomplete=False, enabled=True):
    return {"findings": [_finding()] if findings is None else findings,
            "meta": {"project": "example/review", "number": 50, "head_sha": HEAD},
            "run": {"incomplete": incomplete,
                    "deep": {"enabled": enabled, "elapsed_minutes": elapsed,
                             "areas": [{"id": "A1", "status": "completed"}],
                             "unreached_areas": []}}}


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


def test_answer_key_covers_every_candidate_once_with_unique_defect_ids():
    key = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
    assert key["schema_version"] == 1
    assert isinstance(key["target"]["project"], str)
    assert type(key["target"]["number"]) is int
    assert len(key["target"]["head_sha"]) in (7, 40)
    assert len({item["id"] for item in key["defects"]}) == len(key["defects"])
    assert all(item["severity"] in ("Must fix", "Should fix") and item["anchors"] and item["keywords"]
               and item["source_ids"] for item in key["defects"])
    assert all(all(anchor["line_min"] <= anchor["line_max"] for anchor in item["anchors"])
               for item in key["defects"])
    assert all(set(("source_id", "file", "line", "disposition", "reason")) <= set(item)
               for item in key["examined_non_defects"])
    expected = ({"B%d" % i for i in range(1, 62)} | {"F%d" % i for i in range(1, 9)} | {"F20"})
    covered = [source for defect in key["defects"] for source in defect["source_ids"]]
    covered += [item["source_id"] for item in key["examined_non_defects"]]
    assert expected <= set(covered)
    assert len(covered) == len(set(covered))


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
def test_spot_check_refutations_are_not_diluted_by_unchecked_findings(tmp_path, wrapped):
    report = _report([_finding(), _finding("F2", line="27"),
                      _finding("F3", line="29"), _finding("F4", line="30")])
    verdicts = {"F1": "refuted", "src/flow.py:27": "refuted", "F3": "confirmed"}
    check = {"verdicts": verdicts} if wrapped else verdicts
    original = json.dumps((report, check))
    code, score = _score_cli(tmp_path, report, _key(_defect()), check=check)
    assert code == 1
    assert score["shown_count"] == 4
    assert score["checked_count"] == 3
    assert score["refuted_count"] == 2
    assert score["refuted_share"] == 2 / 3
    assert score["spot_check_coverage"] == "partial"
    assert score["unchecked_finding_ids"] == ["F4"]
    assert score["caught"][0]["finding_id"] == "F3"
    assert json.dumps((report, check)) == original


def test_embedded_judgments_do_not_supply_independent_spot_check_proof():
    report = _report([_finding(spot_check="refuted"),
                      _finding("F2", verification_status="refuted"),
                      _finding("F3", spot_check="confirmed")])
    score = scorer.score_report(report, _key(_defect()))
    assert score["refuted_count"] == score["checked_count"] == 0
    assert score["refuted_share"] is None
    assert score["spot_check_coverage"] == "missing"
    assert score["caught"][0]["finding_id"] == "F3"
    assert score["passed"] is False


def test_budget_and_output_file_match_stdout(tmp_path):
    report = _report(elapsed=61)
    target = tmp_path / "nested" / "score.json"
    code, score = _score_cli(tmp_path, report, _key(_defect()), budget=60, out=target,
                             check={"F1": "confirmed"})
    assert code == 1
    assert score["elapsed_minutes"] == 61
    assert score["within_budget"] is False
    assert json.loads(target.read_text(encoding="utf-8")) == score
    assert scorer.score_report(report, _key(_defect()), {"F1": "confirmed"},
                               budget_minutes=61)["passed"] is True


def test_cli_passes_with_refuted_share_exactly_on_threshold(tmp_path):
    findings = [_finding(line=str(25 + offset), id="F%d" % (offset + 1))
                for offset in range(5)]
    check = {finding["id"]: "confirmed" for finding in findings}
    check["F1"] = "refuted"
    code, score = _score_cli(tmp_path, _report(findings), _key(_defect()), check=check)
    assert code == 0
    assert score["refuted_count"] == 1
    assert score["refuted_share"] == 0.2
    assert score["spot_check_coverage"] == "complete"
    assert score["passed"] is True


@pytest.mark.parametrize("refuted_ids", [("F1",), ("F1", "F2")])
def test_cli_fails_when_refuted_share_is_above_threshold(tmp_path, refuted_ids):
    findings = [_finding(line=str(25 + offset), id="F%d" % (offset + 1))
                for offset in range(5 if len(refuted_ids) == 2 else 4)]
    check = {finding["id"]: "confirmed" for finding in findings}
    check.update({identifier: "refuted" for identifier in refuted_ids})
    code, score = _score_cli(tmp_path, _report(findings), _key(_defect()), check=check)
    assert code == 1
    assert score["refuted_share"] > 0.2
    assert score["recall"] == 1.0
    assert score["passed"] is False


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


def test_deeply_nested_report_returns_json_error(tmp_path):
    report_path = tmp_path / "report.json"
    key_path = tmp_path / "key.json"
    report_path.write_text("[" * 100000, encoding="utf-8")
    key_path.write_text(json.dumps(_key(_defect())), encoding="utf-8")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = scorer.main(["--report", str(report_path), "--answer-key", str(key_path)])
    assert code == 2
    assert isinstance(json.loads(output.getvalue())["error"], str)


def test_empty_findings_do_not_create_spot_check_evidence():
    score = scorer.score_report(_report([]), _key(), {})
    assert score["recall"] == 1.0
    assert score["shown_count"] == score["total_defects"] == score["refuted_count"] == 0
    assert score["refuted_share"] is None
    assert score["spot_check_coverage"] == "empty"
    assert score["within_budget"] is True
    assert score["passed"] is False


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


@pytest.mark.parametrize("include_field", [True, False])
def test_missing_elapsed_time_never_passes(include_field):
    report = _report(elapsed=None)
    if not include_field:
        del report["run"]["deep"]["elapsed_minutes"]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["recall"] == 1.0
    assert score["within_budget"] is score["passed"] is False
    assert "elapsed_minutes_missing" in score["evidence_errors"]


def test_missing_proof_cli_fails_but_supplied_proof_is_evaluated(tmp_path):
    code, score = _score_cli(tmp_path, {"findings": [_finding()]}, _key(_defect()))
    assert code == 1
    assert score["recall"] == 1.0
    assert score["passed"] is False
    assert score["target_matches"] is score["complete_deep_run"] is False
    code, score = _score_cli(tmp_path, _report(), _key(_defect()),
                             check={"F1": "confirmed"})
    assert code == 0
    assert score["target_matches"] is score["complete_deep_run"] is True


@pytest.mark.parametrize("field,value", [
    ("project", "another/repo"), ("number", 51), ("head_sha", "b" * 40),
])
def test_target_mismatch_cannot_pass(field, value):
    report = _report()
    report["meta"][field] = value
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["recall"] == 1.0
    assert score["target_matches"] is score["passed"] is False


def test_historical_short_key_head_must_exactly_prefix_full_report_head():
    key = _key(_defect())
    key["target"]["head_sha"] = HEAD[:7]
    assert scorer.score_report(_report(), key, {"F1": "confirmed"})["passed"] is True
    key["target"]["head_sha"] = "3605fd9"
    assert scorer.score_report(_report(), key, {"F1": "confirmed"})["passed"] is False


@pytest.mark.parametrize("field", ["project", "number", "head_sha"])
def test_missing_target_binding_cannot_pass(field):
    report = _report()
    del report["meta"][field]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["target_matches"] is score["passed"] is False


@pytest.mark.parametrize("field", ["enabled", "areas"])
def test_missing_deep_completion_evidence_cannot_pass(field):
    report = _report()
    del report["run"]["deep"][field]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is False


@pytest.mark.parametrize("location,field,value", [
    ("run", "incomplete", True), ("run", "dimensions_failed", ["correctness"]),
    ("deep", "enabled", False), ("deep", "unreached_areas", ["A1"]),
    ("deep", "areas", [{"id": "A1", "status": "unreached"}]),
    ("deep", "areas", [{"id": "A1", "status": "pending"}]),
    ("deep", "checker_failures", {"C1": "checker timed out"}),
])
def test_partial_or_disabled_run_cannot_pass(location, field, value):
    report = _report()
    owner = report["run"] if location == "run" else report["run"]["deep"]
    owner[field] = value
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["recall"] == 1.0
    assert score["complete_deep_run"] is score["passed"] is False


def test_empty_area_map_is_not_a_complete_deep_run():
    report = _report()
    report["run"]["deep"]["areas"] = []
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is False


def test_read_only_degraded_area_counts_as_complete():
    report = _report()
    report["run"]["deep"]["areas"] = [
        {"id": "A1", "status": "read_only_degraded", "degraded_reason": "sandbox unavailable"}]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is True


def _hunk_area(examined, hunk_ids=("A1.h1", "A1.h2")):
    area = {"id": "A1", "status": "completed",
            "hunks": [{"id": hunk_id, "file": "a.py", "header": "@@"} for hunk_id in hunk_ids]}
    if examined is not None:
        area["examined"] = examined
    return area


@pytest.mark.parametrize("examined", [["A1.h1"], [], None])
def test_area_with_unexamined_hunks_is_not_a_complete_deep_run(examined):
    report = _report()
    report["run"]["deep"]["areas"] = [_hunk_area(examined)]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["recall"] == 1.0
    assert score["complete_deep_run"] is score["passed"] is False
    assert "deep_run_disabled_incomplete_or_unproven" in score["evidence_errors"]


def test_fully_examined_hunks_still_count_as_complete():
    report = _report()
    report["run"]["deep"]["areas"] = [_hunk_area(["A1.h2", "A1.h1"])]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is True


def test_reports_without_hunks_keep_passing():
    report = _report()
    assert "hunks" not in report["run"]["deep"]["areas"][0]
    assert scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})["passed"] is True


@pytest.mark.parametrize("area", [
    {"id": "A1", "status": "completed", "hunks": "A1.h1"},
    {"id": "A1", "status": "completed", "hunks": ["A1.h1"]},
    {"id": "A1", "status": "completed", "hunks": [{"id": 1}]},
    {"id": "A1", "status": "completed", "hunks": [], "examined": "A1.h1"},
    {"id": "A1", "status": "completed", "hunks": [], "examined": [1]},
])
def test_malformed_hunk_evidence_is_rejected(area):
    report = _report()
    report["run"]["deep"]["areas"] = [area]
    with pytest.raises(ValueError):
        scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})


def test_absent_completeness_flag_cannot_pass():
    report = _report()
    del report["run"]["incomplete"]
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is False


@pytest.mark.parametrize("overrides", [
    {"verification_status": "plausible"}, {"verification_status": "refuted"},
    {"verification_status": None}, {"verified": False}, {"spot_check": "refuted"},
])
def test_unconfirmed_or_embedded_refuted_claims_do_not_count_as_caught(overrides):
    finding = _finding(**overrides)
    if finding["verification_status"] is None:
        del finding["verification_status"]
    score = scorer.score_report(_report([finding]), _key(_defect()), {"F1": "confirmed"})
    assert score["recall"] == 0.0
    assert score["passed"] is False
    assert scorer.match_defect(_defect(), [finding]) is None


@pytest.mark.parametrize("verdict", ["refuted", "plausible"])
def test_spot_check_vetoes_matching_claims(verdict):
    score = scorer.score_report(_report(), _key(_defect()), {"F1": verdict})
    assert score["caught_count"] == 0
    assert score["missed"][0]["defect_id"] == "AK-01"


def test_partial_spot_check_coverage_is_explicit_and_uses_checked_denominator():
    report = _report([_finding(), _finding("F2", line="30")])
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["checked_count"] == 1
    assert score["spot_check_coverage"] == "partial"
    assert score["unchecked_finding_ids"] == ["F2"]
    assert score["refuted_share"] == 0.0
    assert score["passed"] is True


@pytest.mark.parametrize("check", [
    {"unknown": "confirmed"},
    {"F1": "confirmed", "src/flow.py:25": "confirmed"},
    {"F1": "confirmed", "src/flow.py:25": "refuted"},
    {"verdicts": []}, {"F1": ["confirmed"]}, {"F1": True},
])
def test_unknown_duplicate_or_malformed_judgments_are_rejected(check):
    with pytest.raises(ValueError):
        scorer.score_report(_report(), _key(_defect()), check)


def test_ambiguous_file_line_alias_is_rejected():
    findings = [_finding(), _finding("F2")]
    with pytest.raises(ValueError, match="ambiguous"):
        scorer.score_report(_report(findings), _key(_defect()),
                            {"src/flow.py:25": "confirmed"})


def test_authored_ids_are_not_spot_check_aliases():
    report = _report([_finding("src/flow.py:30"), _finding("A1.3", line="30")])
    score = scorer.score_report(report, _key(_defect()), {"src/flow.py:30": "refuted"})
    assert score["caught"][0]["finding_id"] == "F1"
    assert score["checked_count"] == 1
    with pytest.raises(ValueError, match="unknown"):
        scorer.score_report(report, _key(_defect()), {"A1.3": "confirmed"})


@pytest.mark.parametrize("mutate", [
    lambda report, key: report["findings"].append(_finding()),
    lambda report, key: key["defects"].append(_defect()),
    lambda report, key: report["findings"][0].update(id=""),
    lambda report, key: report["findings"][0].update(body_md={"path": "bad"}),
    lambda report, key: report["findings"][0].update(verification_status=[]),
    lambda report, key: key["defects"][0].update(keywords=[""]),
    lambda report, key: key["target"].update(number=True),
    lambda report, key: key["target"].update(head_sha="3605"),
    lambda report, key: report["meta"].update(head_sha="3605fd8"),
    lambda report, key: report["run"].update(incomplete="false"),
    lambda report, key: report["run"]["deep"].update(enabled="true"),
    lambda report, key: report["run"]["deep"].update(unreached_areas="A1"),
    lambda report, key: report["run"]["deep"].update(areas=[None]),
    lambda report, key: report["run"]["deep"].update(checker_failures=[]),
    lambda report, key: report["run"]["deep"].update(checker_failures={"C1": None}),
    lambda report, key: report["run"]["deep"].update(checker_failures={"C1": ""}),
    lambda report, key: report["run"]["deep"].update(checker_failures={"": "timeout"}),
    lambda report, key: report["run"]["deep"].update(areas=[{"id": "A1"}, {"id": "A1"}]),
    lambda report, key: report["run"]["deep"].update(cutoff_reached="no"),
])
def test_malformed_scoring_shapes_are_rejected(mutate):
    report, key = _report(), _key(_defect())
    mutate(report, key)
    with pytest.raises(ValueError):
        scorer.score_report(report, key, {"F1": "confirmed"})


@pytest.mark.parametrize("elapsed", [True, -1, "30", float("inf"), float("nan")])
def test_invalid_elapsed_measurements_are_rejected(elapsed):
    with pytest.raises(ValueError, match="elapsed_minutes"):
        scorer.score_report(_report(elapsed=elapsed), _key(_defect()), {"F1": "confirmed"})


@pytest.mark.parametrize("budget", [True, -1, "60", float("inf"), float("nan")])
def test_invalid_budgets_are_rejected(budget):
    with pytest.raises(ValueError, match="budget"):
        scorer.score_report(_report(), _key(_defect()), {"F1": "confirmed"}, budget)


def test_duplicate_json_judgment_keys_are_not_silently_discarded(tmp_path):
    report_path, key_path, check_path = (tmp_path / name for name in
                                       ("report.json", "key.json", "check.json"))
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    key_path.write_text(json.dumps(_key(_defect())), encoding="utf-8")
    check_path.write_text('{"F1": "refuted", "F1": "confirmed"}', encoding="utf-8")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = scorer.main(["--report", str(report_path), "--answer-key", str(key_path),
                            "--spot-check", str(check_path)])
    assert code == 2
    assert "duplicate" in json.loads(output.getvalue())["error"]


@pytest.mark.parametrize("line", ["0", "10-9", "-5", "25-extra", True, None])
def test_malformed_finding_line_is_rejected(line):
    with pytest.raises(ValueError, match="line"):
        scorer.score_report(_report([_finding(line=line)]), _key(_defect()))


def test_zero_elapsed_at_zero_budget_is_valid_measured_proof():
    score = scorer.score_report(_report(elapsed=0), _key(_defect()),
                                {"F1": "confirmed"}, budget_minutes=0)
    assert score["within_budget"] is score["passed"] is True


def test_empty_checker_failure_map_preserves_complete_run():
    report = _report()
    report["run"]["deep"]["checker_failures"] = {}
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["complete_deep_run"] is score["passed"] is True


@pytest.mark.parametrize("include_ids", [True, False])
def test_cli_spot_check_ids_follow_renderer_severity_ranking(tmp_path, include_ids):
    findings = [
        _finding("F1", severity="Should fix", line=25),
        _finding("F2", severity="Must fix", file="src/urgent.py", line=1),
    ]
    if not include_ids:
        for finding in findings:
            del finding["id"]
    report = _report(findings)
    before = json.dumps(report)
    code, score = _score_cli(tmp_path, report, _key(_defect()),
                             check={"F1": "refuted", "F2": "confirmed"})
    assert code == 1
    assert score["caught"][0]["finding_id"] == "F2"
    assert score["caught"][0]["file"] == "src/flow.py"
    assert score["caught"][0]["line"] == "25"
    assert score["refuted_count"] == 1
    assert score["checked_count"] == 2
    assert score["recall"] == 1.0
    assert json.dumps(report) == before
    score = scorer.score_report(report, _key(_defect()), {"F2": "refuted"})
    assert score["recall"] == 0.0


def test_merger_source_ids_become_rendered_ids_without_full_renderer_metadata():
    findings = [_finding("A1.1", line=25), _finding("A1.3", line=30)]
    report = {"findings": findings}
    score = scorer.score_report(report, _key(_defect()), {"F1": "confirmed"})
    assert score["caught"][0]["finding_id"] == "F1"
    assert score["unchecked_finding_ids"] == ["F2"]
    assert score["recall"] == 1.0
    assert score["passed"] is False


def test_integer_line_is_valid_for_direct_defect_matching():
    finding = _finding(line=25)
    assert scorer.match_defect(_defect(), [finding]) == finding
