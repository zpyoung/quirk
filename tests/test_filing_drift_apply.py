from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script


def _bug_doc(**overrides) -> dict:
    doc = {
        "schema_version": 1,
        "type": "bug",
        "headless": False,
        "depth": "read",
        "title": "Export fails with UnicodeDecodeError on reports containing em-dashes",
        "target": {
            "kind": "github", "repo": "acme/reports", "writable": True,
            "third_party": "no", "visibility": "private",
        },
        "template": {
            "applied": False, "path": None,
            "fields": [
                {"name": "current_behavior", "required": True, "source": "core"},
                {"name": "expected_behavior", "required": True, "source": "core"},
                {"name": "steps_to_reproduce", "required": True, "source": "core"},
                {"name": "environment", "required": True, "source": "core"},
            ],
        },
        "fields": [
            {
                "name": "current_behavior", "provenance": "reported",
                "value": "export as PDF raises UnicodeDecodeError when the title has an em-dash",
            },
            {
                "name": "expected_behavior", "provenance": "reported",
                "value": "the PDF export completes and the em-dash renders correctly",
            },
            {
                "name": "steps_to_reproduce", "provenance": "reported",
                "value": "1. create a report titled with an em-dash\n2. click Export as PDF",
            },
            {
                "name": "environment", "provenance": "observed",
                "value": "reports 2.4.1, Python 3.11.6", "source": "pyproject.toml",
            },
        ],
        "verified_against": ["pyproject.toml"],
        "disclosure_required": False,
    }
    doc.update(overrides)
    return doc


def _feature_doc(**overrides) -> dict:
    doc = {
        "schema_version": 1,
        "type": "feature",
        "headless": False,
        "depth": "read",
        "title": "Export reports as PDF",
        "target": {
            "kind": "github", "repo": "acme/reports", "writable": True,
            "third_party": "no", "visibility": "private",
        },
        "template": {
            "applied": False, "path": None,
            "fields": [
                {"name": "problem", "required": True, "source": "core"},
                {"name": "who_benefits", "required": True, "source": "core"},
                {"name": "current_behavior", "required": True, "source": "core"},
                {"name": "acceptance_criteria", "required": True, "source": "core"},
            ],
        },
        "fields": [
            {
                "name": "problem", "provenance": "reported",
                "value": "finance forwards reports to auditors who reject CSV",
            },
            {
                "name": "who_benefits", "provenance": "reported",
                "value": "finance team, ~6 people, monthly close",
            },
            {
                "name": "current_behavior", "provenance": "observed",
                "value": "no PDF export path exists; src/export/ implements CSV and JSON only",
                "source": "src/export/__init__.py",
            },
            {
                "name": "acceptance_criteria", "provenance": "reported",
                "value": "Given a report, When the user exports as PDF, Then a PDF downloads",
            },
        ],
        "verified_against": ["src/export/__init__.py"],
        "disclosure_required": False,
    }
    doc.update(overrides)
    return doc


def _code_change_doc(**overrides) -> dict:
    doc = {
        "schema_version": 1,
        "type": "code-change",
        "headless": False,
        "depth": "read",
        "title": "Refactor the export pipeline",
        "target": {
            "kind": "github", "repo": "acme/reports", "writable": True,
            "third_party": "no", "visibility": "private",
        },
        "template": {
            "applied": False, "path": None,
            "fields": [
                {"name": "scope", "required": True, "source": "core"},
                {"name": "why_now", "required": True, "source": "core"},
                {"name": "blast_radius", "required": True, "source": "core"},
            ],
        },
        "fields": [
            {"name": "scope", "provenance": "reported", "value": "src/export/ only"},
            {"name": "why_now", "provenance": "reported", "value": "blocking the PDF feature"},
            {"name": "blast_radius", "provenance": "reported", "value": "export module only"},
        ],
        "verified_against": [],
        "disclosure_required": False,
    }
    doc.update(overrides)
    return doc


def _field(fields: list, name: str) -> dict:
    return next(f for f in fields if f["name"] == name)


@pytest.fixture(scope="module")
def drift_apply():
    return load_filing_module("drift_apply")


@pytest.fixture(scope="module")
def canonical_schema():
    return load_filing_module("canonical_schema")


# ---- the two tables, verbatim from tech.md -------------------------------


def test_bug_to_feature_table_verbatim(drift_apply) -> None:
    assert drift_apply.BUG_TO_FEATURE == [
        {"from": "current_behavior", "to": "current_behavior", "mode": "identity"},
        {
            "from": "steps_to_reproduce", "to": "current_behavior", "mode": "append_or_become",
            "lead_in": "Steps to reproduce (from the original bug report):",
        },
        {"from": "expected_behavior", "to": "acceptance_criteria", "mode": "rename_reopen"},
        {"from": "environment", "to": "constraints", "mode": "identity_rename"},
    ]


def test_feature_to_bug_table_verbatim(drift_apply) -> None:
    assert drift_apply.FEATURE_TO_BUG == [
        {"from": "current_behavior", "to": "current_behavior", "mode": "identity"},
        {
            "from": "problem", "to": "current_behavior", "mode": "append_or_become",
            "lead_in": "Problem statement (from the original feature request):",
        },
        {"from": "acceptance_criteria", "to": "expected_behavior", "mode": "identity_rename"},
        {"from": "who_benefits", "to": "affected_users", "mode": "demote_optional"},
    ]


# ---- apply_drift(): bug -> feature ---------------------------------------


def test_identity_field_carried_with_same_value_and_provenance(drift_apply) -> None:
    doc = _bug_doc()
    doc["fields"] = [f for f in doc["fields"] if f["name"] != "steps_to_reproduce"]
    result = drift_apply.apply_drift(doc, "feature")
    current_behavior = _field(result["fields"], "current_behavior")
    original = _field(doc["fields"], "current_behavior")
    assert current_behavior["value"] == original["value"]
    assert current_behavior["provenance"] == original["provenance"]


def test_collision_append_lands_on_already_settled_current_behavior(drift_apply) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    current_behavior = _field(result["fields"], "current_behavior")
    assert current_behavior["value"] == (
        "export as PDF raises UnicodeDecodeError when the title has an em-dash"
        "\n\nSteps to reproduce (from the original bug report):"
        "\n1. create a report titled with an em-dash\n2. click Export as PDF"
    )
    # the append lands on current_behavior's own settled entry -- its provenance survives
    assert current_behavior["provenance"] == "reported"
    # only one current_behavior entry results from the collision, not two
    assert sum(1 for f in result["fields"] if f["name"] == "current_behavior") == 1


def test_append_becomes_when_destination_has_no_content(drift_apply) -> None:
    doc = _bug_doc()
    doc["fields"] = [
        {"name": "current_behavior", "provenance": "missing", "reason": "not yet observed"}
        if f["name"] == "current_behavior" else f
        for f in doc["fields"]
    ]
    result = drift_apply.apply_drift(doc, "feature")
    current_behavior = _field(result["fields"], "current_behavior")
    steps = _field(doc["fields"], "steps_to_reproduce")
    assert current_behavior["value"] == steps["value"]
    assert current_behavior["provenance"] == steps["provenance"]


def test_expected_behavior_maps_to_acceptance_criteria_and_reopens_confirmation(drift_apply) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    acceptance_criteria = _field(result["fields"], "acceptance_criteria")
    original = _field(doc["fields"], "expected_behavior")
    assert acceptance_criteria["value"] == original["value"]
    assert acceptance_criteria["provenance"] == original["provenance"]
    assert acceptance_criteria["needs_confirmation"] is True
    # this is the *only* mapping that sets needs_confirmation
    assert sum(1 for f in result["fields"] if f.get("needs_confirmation")) == 1


def test_environment_maps_to_constraints_identity_rename(drift_apply) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    constraints = _field(result["fields"], "constraints")
    original = _field(doc["fields"], "environment")
    assert constraints["value"] == original["value"]
    assert constraints["provenance"] == original["provenance"]
    assert constraints["source"] == original["source"]
    assert "needs_confirmation" not in constraints


def test_unmapped_field_retained_under_original_name(drift_apply) -> None:
    doc = _bug_doc()
    doc["fields"].append({
        "name": "root_cause", "provenance": "inferred",
        "value": "src/export.py:142 opens the output file without an encoding argument",
    })
    result = drift_apply.apply_drift(doc, "feature")
    root_cause = _field(result["fields"], "root_cause")
    assert root_cause["value"] == (
        "src/export.py:142 opens the output file without an encoding argument"
    )
    assert root_cause["provenance"] == "inferred"


def test_bug_to_feature_result_type_updated(drift_apply) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    assert result["type"] == "feature"


def test_apply_drift_does_not_mutate_input_doc(drift_apply) -> None:
    doc = _bug_doc()
    before = json.dumps(doc, sort_keys=True)
    drift_apply.apply_drift(doc, "feature")
    assert json.dumps(doc, sort_keys=True) == before


def test_bug_to_feature_result_is_structurally_valid(drift_apply, canonical_schema) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    assert canonical_schema.validate(result) == {"valid": True, "errors": [], "halted": None}


# ---- apply_drift(): feature -> bug ---------------------------------------


def test_problem_collision_append_lands_on_already_settled_current_behavior(drift_apply) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    current_behavior = _field(result["fields"], "current_behavior")
    assert current_behavior["value"] == (
        "no PDF export path exists; src/export/ implements CSV and JSON only"
        "\n\nProblem statement (from the original feature request):"
        "\nfinance forwards reports to auditors who reject CSV"
    )
    assert current_behavior["provenance"] == "observed"
    assert sum(1 for f in result["fields"] if f["name"] == "current_behavior") == 1


def test_acceptance_criteria_maps_to_expected_behavior_identity_rename(drift_apply) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    expected_behavior = _field(result["fields"], "expected_behavior")
    original = _field(doc["fields"], "acceptance_criteria")
    assert expected_behavior["value"] == original["value"]
    assert expected_behavior["provenance"] == original["provenance"]
    # only bug -> feature's expected_behavior -> acceptance_criteria mapping reopens confirmation
    assert "needs_confirmation" not in expected_behavior


def test_who_benefits_demoted_to_optional_affected_users(drift_apply) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    affected_users = _field(result["fields"], "affected_users")
    original = _field(doc["fields"], "who_benefits")
    assert affected_users["value"] == original["value"]
    assert affected_users["provenance"] == original["provenance"]
    assert not any(f["name"] == "who_benefits" for f in result["fields"])


def test_feature_to_bug_result_type_updated(drift_apply) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    assert result["type"] == "bug"


def test_feature_to_bug_result_is_structurally_valid(drift_apply, canonical_schema) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    assert canonical_schema.validate(result) == {"valid": True, "errors": [], "halted": None}


# ---- CLI contract ---------------------------------------------------------


def test_cli_bug_to_feature_end_to_end(tmp_path: Path) -> None:
    doc = _bug_doc()
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["type"] == "feature"
    assert any(f["name"] == "acceptance_criteria" for f in payload["fields"])


def test_cli_feature_to_bug_end_to_end(tmp_path: Path) -> None:
    doc = _feature_doc()
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "bug",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["type"] == "bug"
    assert any(f["name"] == "expected_behavior" for f in payload["fields"])


def test_cli_to_code_change_exits_2(tmp_path: Path) -> None:
    doc = _bug_doc()
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "code-change",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2


def test_cli_already_this_type_exits_2(tmp_path: Path) -> None:
    doc = _bug_doc()
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "bug",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2


def test_cli_from_code_change_is_undefined_exits_2(tmp_path: Path) -> None:
    doc = _code_change_doc()
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "bug",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2


def test_cli_schema_version_too_new_exits_8(tmp_path: Path) -> None:
    doc = _bug_doc(schema_version=999)
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 8


def test_cli_malformed_json_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin="{not json",
    )
    assert result.returncode == 2


def test_cli_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "drift_apply.py", "--input", str(tmp_path / "missing.json"), "--to", "feature",
        cwd=tmp_path,
    )
    assert result.returncode == 2


def test_cli_output_flag_writes_file_not_stdout(tmp_path: Path) -> None:
    doc = _bug_doc()
    out_path = tmp_path / "drifted.json"
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature", "--output", str(out_path),
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
    written = json.loads(out_path.read_text())
    assert written["type"] == "feature"


def test_cli_reads_from_file_path(tmp_path: Path) -> None:
    doc = _bug_doc()
    input_path = tmp_path / "doc.json"
    input_path.write_text(json.dumps(doc))
    result = run_filing_script(
        "drift_apply.py", "--input", str(input_path), "--to", "feature", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
