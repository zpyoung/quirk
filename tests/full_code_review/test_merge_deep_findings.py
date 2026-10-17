"""Contract tests for checked deep review finding assembly."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts" / "merge_deep_findings.py"


def merge(lens=None, candidates=None, verdicts=None, areas=None, trust=None, budget=None):
    assert SCRIPT.is_file(), SCRIPT
    module = importlib.import_module("merge_deep_findings")
    return module.merge_deep_run(
        lens if lens is not None else [], candidates if candidates is not None else [],
        verdicts if verdicts is not None else [], areas if areas is not None else {"areas": []},
        trust if trust is not None else {"allowed": True, "consent": True, "sandbox_kind": "sandbox-exec", "copy_kind": "clonefile"},
        budget if budget is not None else {"budget_minutes": 60, "elapsed_minutes": 8.5, "cutoff_reached": False},
    )


def candidate(identifier="A1.1", **overrides):
    item = {"id": identifier, "area": "A1", "file": "a.py", "line": "12", "summary": "Bad result",
            "failure_scenario": "The wrong result reaches users.", "recommendation": "Return the correct value."}
    item.update(overrides)
    return item


def verdict(identifier="A1.1", **overrides):
    item = {"id": identifier, "verdict": "confirmed", "severity": "Should fix", "evidence_tag": "read from code"}
    item.update(overrides)
    return item


def lens(identifier="L1", severity="Must fix", **overrides):
    item = {"id": identifier, "severity": severity, "dimension": "contract", "file": "a.py",
            "line": 12, "title": "Bad result", "issue": "The wrong result reaches users.",
            "recommendation_md": "Return the correct value."}
    item.update(overrides)
    return item


def test_confirmed_reproduction_uses_checker_refinements_and_report_shape():
    finding = merge(candidates=[candidate(fix_md="Original fix")], verdicts=[verdict(
        evidence_tag="reproduced", repro_command="python3 demo.py", repro_output="wrong output",
        severity="Must fix", refined_file="b.py", refined_line=13, refined_title="Refined title",
        refined_impact="Incorrect value escapes.", refined_fix_md="Change the calculation.",
        refined_issue="Calculation returns the wrong value.", refined_recommendation="Patch the calculation.",
    )])["findings"][0]
    assert finding == {
        "id": "A1.1", "area": "A1", "severity": "Must fix", "dimension": "correctness",
        "dimensions": ["correctness"], "file": "b.py", "line": "13", "title": "Refined title",
        "impact": "Incorrect value escapes.", "fix_md": "Change the calculation.",
        "issue": "Calculation returns the wrong value.", "body_md": "Calculation returns the wrong value.",
        "recommendation": "Patch the calculation.", "recommendation_md": "Patch the calculation.",
        "verification_status": "confirmed", "verified": True, "evidence": "reproduced",
        "repro": {"command": "python3 demo.py", "output": "wrong output"}, "what_would_confirm": None,
    }


def test_plausible_candidate_keeps_confirmation_condition_without_repro():
    finding = merge(candidates=[candidate(dimension="security", dimensions=["security", "contract"])],
                    verdicts=[verdict(verdict="plausible", what_would_confirm="Run against an affected account.")])["findings"][0]
    assert finding["verification_status"] == "plausible"
    assert finding["verified"] is False
    assert finding["evidence"] == "read from code"
    assert "repro" not in finding
    assert finding["what_would_confirm"] == "Run against an affected account."
    assert finding["dimensions"] == ["contract", "security"]
    assert finding["dimension"] == "contract"
    assert finding["issue"] == finding["body_md"] == "The wrong result reaches users."


def test_checker_refutes_deep_and_high_severity_lens_findings_with_reasons():
    result = merge(lens=[lens("L1", dimension="db"), lens("L2", "Should fix", line=14)],
                   candidates=[candidate()], verdicts=[verdict(verdict="refuted", reason="Guarded by caller."),
                   verdict("L1", verdict="refuted", reason="Deliberate policy."),
                   verdict("L2", verdict="refuted", reason="Cannot occur.")])
    assert result["findings"] == []
    assert result["deep"]["checked_and_dropped"] == [
        {"id": "A1.1", "area": "A1", "file": "a.py", "line": "12", "title": "Bad result", "reason": "Guarded by caller."},
        {"id": "L1", "area": "lens:db", "file": "a.py", "line": "12", "title": "Bad result", "reason": "Deliberate policy."},
        {"id": "L2", "area": "lens:contract", "file": "a.py", "line": "14", "title": "Bad result", "reason": "Cannot occur."},
    ]


@pytest.mark.parametrize("kind", ["deep", "Must fix", "Should fix"])
def test_unchecked_required_candidate_is_rejected_even_when_other_items_have_verdicts(kind):
    if kind == "deep":
        kwargs = {"candidates": [candidate("A1.1"), candidate("A1.2", line="20")],
                  "verdicts": [verdict("A1.2")]}
    else:
        kwargs = {"lens": [lens("L1", kind), lens("L2", kind, line=20)], "verdicts": [verdict("L2")]}
    with pytest.raises(ValueError, match="missing checker verdict for (A1.1|L1)"):
        merge(**kwargs)


def test_nit_without_verdict_is_preserved_unless_same_anchor_merges_into_stronger_finding():
    alone = merge(lens=[lens(severity="Nit", dimension="style")])["findings"][0]
    assert alone["severity"] == "Nit"
    assert alone["verification_status"] == "confirmed"
    assert alone["verified"] is True
    assert alone["evidence"] == "read from code"
    combined = merge(lens=[lens(severity="Nit", dimension="style")], candidates=[candidate()],
                     verdicts=[verdict()])["findings"]
    assert len(combined) == 1
    assert combined[0]["severity"] == "Should fix"
    assert combined[0]["dimensions"] == ["correctness", "style"]


def test_checked_nit_obeys_refutation():
    result = merge(lens=[lens(severity="Nit")], verdicts=[verdict("L1", verdict="refuted", reason="Already validated.")])
    assert not result["findings"]
    assert result["deep"]["checked_and_dropped"][0]["area"] == "lens:contract"


def test_dedup_merges_lens_contract_and_area_by_severity_status_evidence_and_dimensions():
    result = merge(
        lens=[lens("L1", "Must fix", dimension="db", line="12-14")],
        candidates=[candidate("A1.1", line="13", dimension="correctness"),
                    candidate("C1", line="13", area="contract", dimension="contract")],
        verdicts=[verdict("L1", severity="Must fix", verdict="plausible", what_would_confirm="Inspect production config."),
                  verdict("A1.1", evidence_tag="reproduced", repro_command="python3 repro.py", repro_output="failure"),
                  verdict("C1")],
    )
    assert len(result["findings"]) == 1
    found = result["findings"][0]
    assert found["severity"] == "Should fix"
    assert found["verification_status"] == "confirmed"
    assert found["verified"] is True
    assert found["what_would_confirm"] is None
    assert found["evidence"] == "reproduced"
    assert found["repro"] == {"command": "python3 repro.py", "output": "failure"}
    assert found["dimensions"] == ["contract", "correctness", "db"]
    assert found["dimension"] == "contract"


def test_dedup_representative_comes_from_verified_members_when_any_exist():
    result = merge(
        lens=[lens("L1", "Must fix", title="Plausible-only wording")],
        candidates=[candidate("A1.1", line="12", summary="Checked defect")],
        verdicts=[verdict("L1", severity="Must fix", verdict="plausible", what_would_confirm="Inspect config."),
                  verdict("A1.1")],
    )
    [found] = result["findings"]
    assert (found["severity"], found["title"], found["verified"]) == ("Should fix", "Checked defect", True)
    assert found["what_would_confirm"] is None


def test_dedup_of_only_plausible_members_keeps_strongest_severity_and_condition():
    result = merge(
        lens=[lens("L1", "Must fix")],
        candidates=[candidate("A1.1", line="12")],
        verdicts=[verdict("L1", severity="Must fix", verdict="plausible", what_would_confirm="Inspect config."),
                  verdict("A1.1", verdict="plausible", what_would_confirm="Run it.")],
    )
    [found] = result["findings"]
    assert found["severity"] == "Must fix"
    assert found["verified"] is False
    assert found["what_would_confirm"]


def test_same_file_overlapping_ranges_merge_only_when_title_or_key_matches():
    candidates = [candidate("A1.1", line="10-12", summary="First defect", dedup_key="shared"),
                  candidate("A1.2", line="11-13", summary="Other wording", dedup_key="shared"),
                  candidate("A1.3", line="12-14", summary="Distinct defect")]
    findings = merge(candidates=candidates, verdicts=[verdict(item["id"]) for item in candidates])["findings"]
    assert len(findings) == 2
    assert {finding["title"] for finding in findings} == {"First defect", "Distinct defect"}


def test_no_finding_cap_applies_to_checked_candidates():
    candidates = [candidate("A1.%s" % index, line=str(index + 100)) for index in range(70)]
    assert len(merge(candidates=candidates, verdicts=[verdict(item["id"]) for item in candidates])["findings"]) == 70


def test_adjacent_distinct_failures_are_not_merged_by_shared_title_words():
    candidates = [
        candidate("A1.1", line="10", summary="Invoice update drops customer identity"),
        candidate("A1.2", line="14", summary="Invoice update drops payment currency"),
    ]
    findings = merge(candidates=candidates, verdicts=[verdict(c["id"]) for c in candidates])["findings"]
    assert {f["line"] for f in findings} == {"10", "14"}


def test_checker_can_downgrade_a_confirmed_lens_claim():
    findings = merge(lens=[lens("L1", "Must fix")],
                     verdicts=[verdict("L1", severity="Nit")])["findings"]
    assert findings[0]["severity"] == "Nit"


def test_pending_area_never_becomes_complete_coverage():
    result = merge(areas={"areas": [{"id": "A1", "status": "pending"}]})
    assert result["incomplete"] is True
    assert result["deep"]["unreached_areas"] == ["A1"]


def test_candidate_ids_cannot_alias_a_different_lens_claim():
    with pytest.raises(ValueError, match="duplicate.*id"):
        merge(lens=[lens("A1.1")], candidates=[candidate()],
              verdicts=[verdict()])


def test_unknown_checker_id_cannot_supply_evidence():
    with pytest.raises(ValueError, match="unknown.*id"):
        merge(verdicts=[verdict("not-dispatched")])


def test_failed_checker_withholds_flagged_lens_nit_instead_of_publishing_it_as_verified():
    result = merge(
        lens=[lens("L1", "Nit")],
        budget={"budget_minutes": 60, "elapsed_minutes": 1, "cutoff_reached": False,
                "checker_failures": {"L1": "checker timed out"}},
    )
    assert result["findings"] == []
    assert result["incomplete"] is True
    assert "⚠ Unchecked claims withheld: L1" in result["coverage_notes"]


def test_failed_checker_withholds_only_its_claim_and_marks_review_incomplete():
    result = merge(
        candidates=[candidate("A1.1"), candidate("A1.2", line="20")],
        verdicts=[verdict("A1.1")],
        budget={"budget_minutes": 60, "elapsed_minutes": 60, "cutoff_reached": True,
                "checker_failures": {"A1.2": "checker timed out"}},
    )
    assert [f["id"] for f in result["findings"]] == ["A1.1"]
    assert result["incomplete"] is True
    assert result["deep"]["checker_failures"] == {"A1.2": "checker timed out"}
    assert result["verdict_override"] == "Incomplete review"


@pytest.mark.parametrize("bad", [
    {"verdict": "unknown"}, {"severity": "critical"}, {"evidence_tag": "guess"},
    {"verdict": "refuted", "reason": "   "},
    {"evidence_tag": "reproduced", "repro_command": "", "repro_output": "failure"},
    {"evidence_tag": "reproduced", "repro_command": "do it", "repro_output": " "},
    {"verdict": "plausible", "what_would_confirm": ""},
])
def test_invalid_checker_verdict_is_rejected(bad):
    with pytest.raises(ValueError):
        merge(candidates=[candidate()], verdicts=[verdict(**bad)])


@pytest.mark.parametrize("field,limit", [
    ("refined_title", 80), ("refined_impact", 200), ("refined_fix_md", 160),
])
def test_overlong_refinements_require_rewriting_instead_of_truncation(field, limit):
    with pytest.raises(ValueError, match="rewrite"):
        merge(candidates=[candidate()], verdicts=[verdict(**{field: "x" * (limit + 1)})])


def test_overlong_finder_text_is_shortened_instead_of_aborting_the_merge():
    long_summary = "Bad result " * 20
    long_scenario = "The wrong result reaches users. " * 10
    result = merge(
        candidates=[candidate("A1.1", summary=long_summary, failure_scenario=long_scenario),
                    candidate("A1.2", line="20", summary=long_summary)],
        verdicts=[verdict("A1.1"), verdict("A1.2", verdict="refuted", reason="Guarded by caller.")],
    )
    [found] = result["findings"]
    assert len(found["title"]) <= 80 and found["title"].endswith("…")
    assert len(found["impact"]) <= 200
    [dropped] = result["deep"]["checked_and_dropped"]
    assert len(dropped["title"]) <= 80


def test_overlong_refinement_error_names_the_candidate():
    with pytest.raises(ValueError, match="A1.1"):
        merge(candidates=[candidate()], verdicts=[verdict(refined_title="x" * 81)])


def test_lens_finding_without_title_gets_one_from_the_first_clause_of_its_issue():
    item = lens(severity="Nit", issue="Result is wrong. A second sentence follows.")
    del item["title"]
    [found] = merge(lens=[item])["findings"]
    assert found["title"] == "Result is wrong."
    refuted = lens("L2", "Should fix", issue="Other defect: details follow.")
    del refuted["title"]
    result = merge(lens=[refuted], verdicts=[verdict("L2", verdict="refuted", reason="Guarded.")])
    assert result["deep"]["checked_and_dropped"][0]["title"] == "Other defect:"


def test_titleless_candidate_without_issue_text_is_rejected_with_its_id():
    item = lens(severity="Nit")
    del item["title"], item["issue"]
    with pytest.raises(ValueError, match="title for L1"):
        merge(lens=[item])


def test_area_coverage_trust_and_budget_are_attached_without_mutating_inputs():
    areas = {"areas": [{"id": "A1", "status": "completed"},
                       {"id": "A2", "status": "read_only_degraded", "degraded_reason": "sandbox unavailable"},
                       {"id": "A3", "status": "unreached"}]}
    result = merge(areas=areas, budget={"budget_minutes": 60, "elapsed_minutes": 49, "cutoff_reached": True})
    assert result["deep"]["areas"] == areas["areas"]
    assert result["deep"]["budget_minutes"] == 60
    assert result["deep"]["elapsed_minutes"] == 49
    assert result["deep"]["cutoff_reached"] is True
    assert result["deep"]["execution_allowed"] is True
    assert result["deep"]["execution_consent"] is True
    assert result["deep"]["execution_enabled"] is True
    assert result["deep"]["unreached_areas"] == ["A3"]
    assert result["incomplete"] is True
    assert result["verdict_override"] == "Incomplete review"
    assert "⚠ Area A2 ran read-only: sandbox unavailable" in result["coverage_notes"]
    assert "⚠ Incomplete deep review: budget expired before reaching A3" in result["coverage_notes"]
    assert areas["areas"][2] == {"id": "A3", "status": "unreached"}


@pytest.mark.parametrize("budget", [
    {"elapsed_minutes": 2, "cutoff_reached": False},
    {"budget_minutes": 60, "elapsed_minutes": -1, "cutoff_reached": False},
    {"budget_minutes": 60, "elapsed_minutes": -0.5, "cutoff_reached": False},
    {"budget_minutes": 0, "elapsed_minutes": 1, "cutoff_reached": False},
    {"budget_minutes": 10 ** 400, "elapsed_minutes": float("nan"), "cutoff_reached": False},
    {"budget_minutes": 60, "elapsed_minutes": 1, "cutoff_reached": "no"},
])
def test_bad_budget_fields_are_rejected(budget):
    with pytest.raises(ValueError, match="budget"):
        merge(budget=budget)


def test_zero_elapsed_and_out_of_float_range_integers_are_accepted_and_compared_exactly():
    result = merge(budget={"budget_minutes": 10 ** 400, "elapsed_minutes": 10 ** 400 + 1, "cutoff_reached": False})
    assert result["incomplete"] is True
    assert merge(budget={"budget_minutes": 60, "elapsed_minutes": 0, "cutoff_reached": False})["incomplete"] is False


@pytest.mark.parametrize("area", [{"id": "A1"}, {"id": "A1", "status": "running"}, {"id": "A1", "status": "bogus"}])
def test_area_without_a_completed_status_is_unreached(area):
    result = merge(areas={"areas": [area]})
    assert result["deep"]["unreached_areas"] == ["A1"]
    assert result["incomplete"] is True


@pytest.mark.parametrize("trust,note", [
    ({"allowed": False, "consent": True, "reason": "author untrusted"}, "⚠ Deep repros disabled: author untrusted"),
    ({"allowed": True, "consent": False}, "⚠ Deep repros disabled: execution consent was declined"),
])
def test_disabled_execution_is_reported(trust, note):
    result = merge(trust=trust)
    assert result["deep"]["execution_enabled"] is False
    assert result["coverage_notes"] == [note]
    assert result["assumptions"] == []
    assert result["incomplete"] is False
    assert result["verdict_override"] is None


def test_isolation_warning_is_reported_only_when_execution_is_enabled():
    enabled = merge(trust={"allowed": True, "consent": True, "sandbox_kind": "worktree",
                           "copy_kind": "worktree", "isolation_warning": "not enforced"})
    assert "⚠ Deep execution isolation: not enforced" in enabled["coverage_notes"]
    assert "not enforced" in enabled["assumptions"]
    disabled = merge(trust={"allowed": True, "consent": False, "isolation_warning": "not enforced"})
    assert not any("isolation" in note for note in disabled["coverage_notes"])
    assert disabled["assumptions"] == []


def test_over_budget_run_is_incomplete_with_override_and_note():
    result = merge(budget={"budget_minutes": 60, "elapsed_minutes": 61, "cutoff_reached": False})
    assert result["incomplete"] is True
    assert result["verdict_override"] == "Incomplete review"
    assert "⚠ Deep review exceeded its time budget" in result["coverage_notes"]


def test_checker_verdict_and_failure_inputs_must_be_unambiguous():
    with pytest.raises(ValueError, match="duplicate checker verdict"):
        merge(candidates=[candidate()], verdicts=[verdict(), verdict()])
    base = {"budget_minutes": 60, "elapsed_minutes": 1, "cutoff_reached": False}
    with pytest.raises(ValueError, match="unchecked candidate"):
        merge(candidates=[candidate()], verdicts=[verdict()],
              budget=dict(base, checker_failures={"nope": "timed out"}))
    with pytest.raises(ValueError, match="unchecked candidate"):
        merge(candidates=[candidate()], verdicts=[verdict()],
              budget=dict(base, checker_failures={"A1.1": "timed out"}))


@pytest.mark.parametrize("trust", [
    {"allowed": "yes", "consent": True},
    {"allowed": True, "consent": "no"},
    {"allowed": True},
])
def test_non_boolean_trust_fields_are_rejected(trust):
    with pytest.raises(ValueError, match="booleans"):
        merge(trust=trust)


def test_disabled_trust_without_reason_is_rejected():
    with pytest.raises(ValueError, match="trust reason"):
        merge(trust={"allowed": False, "consent": False})


def test_trust_that_disallows_execution_needs_no_consent_field():
    result = merge(trust={"allowed": False, "reason": "fork author"})
    assert result["deep"]["execution_consent"] is False
    assert result["deep"]["execution_enabled"] is False
    assert result["coverage_notes"] == ["⚠ Deep repros disabled: fork author"]


def cli_run(tmp_path, consent=True, overrides=None, raw=None):
    """Write the six merge inputs under tmp_path and run the CLI; raw maps a flag to literal file text."""
    inputs = {"lens-findings": [], "deep-candidates": [candidate()],
              "checker-verdicts": [verdict()], "area-map": {"areas": []},
              "trust": {"allowed": True, "consent": consent},
              "budget": {"budget_minutes": 60, "elapsed_minutes": 0, "cutoff_reached": False}}
    inputs.update(overrides or {})
    argv = []
    for flag, content in inputs.items():
        path = tmp_path / (flag + ".json")
        if raw and flag in raw:
            if raw[flag] is not None:
                path.write_text(raw[flag], encoding="utf-8")
        else:
            path.write_text(json.dumps(content), encoding="utf-8")
        argv.extend(["--" + flag, str(path)])
    target = tmp_path / "nested" / "merged.json"
    result = subprocess.run([sys.executable, str(SCRIPT), *argv, "--out", str(target)], capture_output=True, text=True)
    return result, target


def test_cli_writes_json_via_report_helper(tmp_path):
    result, target = cli_run(tmp_path, consent=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(target.read_text(encoding="utf-8"))["findings"][0]["id"] == "A1.1"


def test_cli_deeply_nested_json_exits_two_with_json_error(tmp_path):
    result, _ = cli_run(tmp_path, raw={"deep-candidates": "[" * 100000})
    assert result.returncode == 2
    assert isinstance(json.loads(result.stdout)["error"], str)


@pytest.mark.parametrize("invalid_input", ["missing", "invalid-json", "wrong-type", "missing-verdict"])
def test_cli_invalid_input_exits_two_with_json_error(tmp_path, invalid_input):
    overrides = {"checker-verdicts": []} if invalid_input == "missing-verdict" else None
    raw = {"missing": {"deep-candidates": None}, "invalid-json": {"deep-candidates": "{broken"},
           "wrong-type": {"deep-candidates": "{}"}}.get(invalid_input)
    result, target = cli_run(tmp_path, overrides=overrides, raw=raw)
    assert result.returncode == 2
    assert isinstance(json.loads(result.stdout)["error"], str)
    assert not target.exists()


def test_unchecked_nit_does_not_displace_a_plausible_must_fix_at_the_same_line():
    result = merge(
        lens=[lens("L1", "Must fix"), lens("L2", "Nit", dimension="style")],
        verdicts=[verdict("L1", severity="Must fix", verdict="plausible", what_would_confirm="Inspect config.")],
    )
    [found] = result["findings"]
    assert (found["id"], found["severity"]) == ("L1", "Must fix")
    assert found["verification_status"] == "plausible"
    assert found["verified"] is False
    assert found["what_would_confirm"] == "Inspect config."
    assert found["dimensions"] == ["contract", "style"]
    assert "_checked" not in found


def test_unchecked_lens_nit_marked_unverified_stays_plausible_and_keeps_its_context():
    nit = lens("L1", "Nit", verified=False, assumptions=["Caller passes a list."], anchor_side="old")
    [found] = merge(lens=[nit])["findings"]
    assert found["verification_status"] == "plausible"
    assert found["verified"] is False
    assert found["what_would_confirm"] == "Caller passes a list."
    assert found["assumptions"] == ["Caller passes a list."]
    assert found["anchor_side"] == "old"
    assert found["evidence"] == "read from code"


def test_unverified_lens_nit_without_assumptions_still_names_a_confirmation_condition():
    [found] = merge(lens=[lens("L1", "Nit", verified=False)])["findings"]
    assert found["verification_status"] == "plausible"
    assert found["what_would_confirm"]


def test_dedup_preserves_assumptions_and_anchor_side_from_the_merged_members():
    result = merge(
        lens=[lens("L1", "Nit", assumptions=["Lens assumption."], anchor_side="old")],
        candidates=[candidate("A1.1", assumptions=["Deep assumption."])],
        verdicts=[verdict("A1.1")],
    )
    [found] = result["findings"]
    assert found["assumptions"] == ["Deep assumption.", "Lens assumption."]
    assert found["anchor_side"] == "old"


@pytest.mark.parametrize("overrides", [{"anchor_side": "left"}, {"assumptions": "text"}, {"assumptions": [1]}])
def test_malformed_anchor_side_or_assumptions_are_rejected_with_the_id(overrides):
    with pytest.raises(ValueError, match="L1"):
        merge(lens=[lens("L1", "Nit", **overrides)])


@pytest.mark.parametrize("value,expected", [
    (12, "12"), (" 12 ", "12"), ("12-14", "12-14"), ("12 - 14", "12-14"), ("12 -14", "12-14"),
])
def test_line_anchors_are_normalized_to_the_renderer_form(value, expected):
    [found] = merge(candidates=[candidate(line=value)], verdicts=[verdict()])["findings"]
    assert found["line"] == expected


@pytest.mark.parametrize("value", ["L12, L14", "L12", "12,14", "0", "12-", "-3", "a-b", True, 1.5, ""])
def test_non_numeric_line_anchors_are_rejected_naming_the_candidate(value):
    with pytest.raises(ValueError, match="line for A1.1 must be a line number or start-end range"):
        merge(candidates=[candidate(line=value)], verdicts=[verdict()])


def test_non_numeric_checker_refined_line_is_rejected_naming_the_candidate():
    with pytest.raises(ValueError, match="line for A1.1"):
        merge(candidates=[candidate()], verdicts=[verdict(refined_line="L12, L14")])


def test_same_line_findings_with_different_dedup_keys_stay_separate():
    candidates = [candidate("A1.1", summary="First defect", dedup_key="k1"),
                  candidate("A1.2", summary="Second defect", dedup_key="k2")]
    verdicts = [verdict("A1.1", severity="Should fix"), verdict("A1.2", severity="Must fix")]
    findings = merge(candidates=candidates, verdicts=verdicts)["findings"]
    assert sorted(finding["id"] for finding in findings) == ["A1.1", "A1.2"]


@pytest.mark.parametrize("value, expected", [("L40, 41", "40"), ("40-L41", "40"), ("n/a", "1"), (None, "1"), ("48-42", "48")])
def test_malformed_line_on_a_refuted_candidate_does_not_abort_the_merge(value, expected):
    result = merge(candidates=[candidate(line=value), candidate("A1.2", line="20")],
                   verdicts=[verdict(verdict="refuted", reason="Guarded."), verdict("A1.2")])
    assert [entry["line"] for entry in result["deep"]["checked_and_dropped"]] == [expected]
    assert [finding["id"] for finding in result["findings"]] == ["A1.2"]


@pytest.mark.parametrize("value", ["48-42", "10-0", "5-4"])
def test_descending_or_zero_ended_line_ranges_are_rejected(value):
    with pytest.raises(ValueError, match="line for A1.1 must be a line number or start-end range"):
        merge(candidates=[candidate(line=value)], verdicts=[verdict()])
