"""Contract tests for checked deep review finding assembly."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts" / "merge_deep_findings.py"


def merge(lens=None, candidates=None, verdicts=None, areas=None, trust=None, budget=None):
    assert SCRIPT.is_file(), "merge_deep_findings.py must be implemented"
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
    kwargs = {"candidates": [candidate()]} if kind == "deep" else {"lens": [lens(severity=kind)]}
    with pytest.raises(ValueError, match="verdict"):
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
    assert found["severity"] == "Must fix"
    assert found["verification_status"] == "confirmed"
    assert found["verified"] is True
    assert found["what_would_confirm"] is None
    assert found["evidence"] == "reproduced"
    assert found["repro"] == {"command": "python3 repro.py", "output": "failure"}
    assert found["dimensions"] == ["contract", "correctness", "db"]
    assert found["dimension"] == "contract"


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


def test_refinements_normalize_whitespace_and_length_limits():
    found = merge(candidates=[candidate()], verdicts=[verdict(
        refined_title="  First\n title  " + "x" * 100,
        refined_impact="  A  bad\n result.  This is a second sentence.",
        refined_fix_md="  Fix \n it  " + "y" * 170,
    )])["findings"][0]
    assert "\n" not in found["title"] + found["impact"] + found["fix_md"]
    assert len(found["title"]) <= 80
    assert found["impact"] == "A bad result."
    assert len(found["fix_md"]) <= 160


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
    assert result["assumptions"] == ["Deep mode execution consent granted: code ran in isolated throwaway copies (sandbox-exec, clonefile, budget 60m, no gh/glab)."]
    assert areas["areas"][2] == {"id": "A3", "status": "unreached"}


@pytest.mark.parametrize("budget", [
    {"elapsed_minutes": 2, "cutoff_reached": False},
    {"budget_minutes": 60, "elapsed_minutes": -1, "cutoff_reached": False},
    {"budget_minutes": 60, "elapsed_minutes": 1, "cutoff_reached": "no"},
])
def test_bad_budget_fields_are_rejected(budget):
    with pytest.raises(ValueError, match="budget"):
        merge(budget=budget)


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


def test_cli_writes_json_via_report_helper(tmp_path):
    inputs = {"lens-findings": [], "deep-candidates": [candidate()],
              "checker-verdicts": [verdict()], "area-map": {"areas": []},
              "trust": {"allowed": True, "consent": False},
              "budget": {"budget_minutes": 60, "elapsed_minutes": 0, "cutoff_reached": False}}
    argv = []
    for flag, content in inputs.items():
        path = tmp_path / (flag + ".json")
        path.write_text(json.dumps(content), encoding="utf-8")
        argv.extend(["--" + flag, str(path)])
    target = tmp_path / "nested" / "merged.json"
    result = subprocess.run([sys.executable, str(SCRIPT), *argv, "--out", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(target.read_text(encoding="utf-8"))["findings"][0]["id"] == "A1.1"


@pytest.mark.parametrize("invalid_input", ["missing", "invalid-json", "wrong-type", "missing-verdict"])
def test_cli_invalid_input_exits_two_with_json_error(tmp_path, invalid_input):
    inputs = {"lens-findings": [], "deep-candidates": [candidate()],
              "checker-verdicts": [verdict()], "area-map": {"areas": []},
              "trust": {"allowed": True, "consent": True},
              "budget": {"budget_minutes": 60, "elapsed_minutes": 0, "cutoff_reached": False}}
    if invalid_input == "missing-verdict":
        inputs["checker-verdicts"] = []
    argv = []
    for flag, content in inputs.items():
        path = tmp_path / (flag + ".json")
        if flag == "deep-candidates" and invalid_input == "missing":
            pass
        elif flag == "deep-candidates" and invalid_input == "invalid-json":
            path.write_text("{broken", encoding="utf-8")
        elif flag == "deep-candidates" and invalid_input == "wrong-type":
            path.write_text("{}", encoding="utf-8")
        else:
            path.write_text(json.dumps(content), encoding="utf-8")
        argv.extend(["--" + flag, str(path)])
    target = tmp_path / "out.json"
    result = subprocess.run([sys.executable, str(SCRIPT), *argv, "--out", str(target)], capture_output=True, text=True)
    assert result.returncode == 2
    assert isinstance(json.loads(result.stdout)["error"], str)
    assert not target.exists()
