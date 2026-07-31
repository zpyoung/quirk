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


def test_problem_collision_appends_when_the_destination_is_no_stronger(drift_apply) -> None:
    doc = _feature_doc()
    doc["fields"] = [
        {"name": "current_behavior", "provenance": "reported",
         "value": "no PDF export path exists; src/export/ implements CSV and JSON only"}
        if f["name"] == "current_behavior" else f
        for f in doc["fields"]
    ]
    doc["verified_against"] = []
    result = drift_apply.apply_drift(doc, "bug")
    current_behavior = _field(result["fields"], "current_behavior")
    assert current_behavior["value"] == (
        "no PDF export path exists; src/export/ implements CSV and JSON only"
        "\n\nProblem statement (from the original feature request):"
        "\nfinance forwards reports to auditors who reject CSV"
    )
    assert current_behavior["provenance"] == "reported"
    assert sum(1 for f in result["fields"] if f["name"] == "current_behavior") == 1
    assert not any(f["name"] == "problem" for f in result["fields"])


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


# ---- wave-3 checkpoint regressions ---------------------------------------


def test_duplicate_source_field_names_are_all_carried(drift_apply) -> None:
    # collapsing fields into one entry per name silently drops every entry but the last,
    # and "nothing the user supplied is ever discarded on drift" admits no exceptions.
    doc = _bug_doc()
    doc["fields"].append({
        "name": "current_behavior", "provenance": "reported",
        "value": "it also drops the trailing page when the report is long",
    })
    result = drift_apply.apply_drift(doc, "feature")
    current_behavior = _field(result["fields"], "current_behavior")
    assert "it also drops the trailing page when the report is long" in current_behavior["value"]
    assert "export as PDF raises UnicodeDecodeError" in current_behavior["value"]
    assert sum(1 for f in result["fields"] if f["name"] == "current_behavior") == 1


def test_mapped_destination_colliding_with_an_existing_field_keeps_both(drift_apply) -> None:
    # environment (observed) -> constraints lands on a document that already carries a
    # `reported` constraints. Neither may be dropped, and neither may be relabelled as the
    # other's provenance, so they end up as two fields rather than one merged one.
    doc = _bug_doc()
    doc["fields"].append({
        "name": "constraints", "provenance": "reported",
        "value": "must keep working on the 2.3 LTS line",
    })
    result = drift_apply.apply_drift(doc, "feature")
    blob = json.dumps(result)
    assert "reports 2.4.1, Python 3.11.6" in blob
    assert "must keep working on the 2.3 LTS line" in blob
    carried = [f for f in result["fields"] if f["name"].startswith("constraints")]
    assert {f["provenance"] for f in carried} == {"observed", "reported"}


def test_colliding_fields_of_equal_provenance_do_merge(drift_apply) -> None:
    doc = _bug_doc()
    doc["fields"] = [
        {"name": "environment", "provenance": "reported", "value": "reports 2.4.1"}
        if f["name"] == "environment" else f
        for f in doc["fields"]
    ]
    doc["fields"].append({
        "name": "constraints", "provenance": "reported", "value": "2.3 LTS must keep working",
    })
    doc["verified_against"] = []
    result = drift_apply.apply_drift(doc, "feature")
    constraints = _field(result["fields"], "constraints")
    assert "reports 2.4.1" in constraints["value"]
    assert "2.3 LTS must keep working" in constraints["value"]
    assert sum(1 for f in result["fields"] if f["name"].startswith("constraints")) == 1


def test_weaker_incoming_is_retained_rather_than_relabelled(drift_apply) -> None:
    # a `reported` problem must not be folded into an `observed` current_behavior: the field
    # has one provenance slot, so the append would assert the problem statement was verified.
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")

    current_behavior = _field(result["fields"], "current_behavior")
    assert current_behavior["provenance"] == "observed"
    assert current_behavior["source"] == "src/export/__init__.py"
    assert "finance forwards reports" not in current_behavior["value"]

    problem = _field(result["fields"], "problem")
    assert problem["provenance"] == "reported"
    assert problem["value"] == "finance forwards reports to auditors who reject CSV"


def test_missing_field_reason_survives_a_mapped_drift(drift_apply) -> None:
    # a `missing` reason is the diagnostic content the spec defends -- folding it into a
    # settled destination would drop it, and dropping it discards what the user supplied
    doc = _bug_doc()
    doc["fields"] = [
        {"name": "steps_to_reproduce", "provenance": "missing",
         "reason": "intermittent; observed 3x over two weeks with no identified trigger"}
        if f["name"] == "steps_to_reproduce" else f
        for f in doc["fields"]
    ]
    result = drift_apply.apply_drift(doc, "feature")
    steps = _field(result["fields"], "steps_to_reproduce")
    assert steps["provenance"] == "missing"
    assert steps["reason"] == "intermittent; observed 3x over two weeks with no identified trigger"
    assert "value" not in steps


def test_append_of_equal_provenance_does_not_flag_the_merged_field(drift_apply) -> None:
    doc = _bug_doc()  # steps_to_reproduce and current_behavior are both `reported`
    result = drift_apply.apply_drift(doc, "feature")
    assert "needs_confirmation" not in _field(result["fields"], "current_behavior")


def test_collision_result_is_structurally_valid(drift_apply, canonical_schema) -> None:
    doc = _bug_doc()
    doc["fields"].append({
        "name": "constraints", "provenance": "reported", "value": "2.3 LTS must keep working",
    })
    result = drift_apply.apply_drift(doc, "feature")
    assert canonical_schema.validate(result) == {"valid": True, "errors": [], "halted": None}


# ---- template.fields carries across the drift ----------------------------


def _template_names(doc: dict) -> list:
    return [entry["name"] for entry in doc["template"]["fields"]]


def test_bug_to_feature_rewrites_template_fields_to_the_new_type(drift_apply) -> None:
    # left behind, template.fields still describes the *bug* union: --for-emission would
    # report steps_to_reproduce missing and never enforce the feature's own required fields.
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    names = _template_names(result)
    assert "steps_to_reproduce" not in names
    assert "expected_behavior" not in names
    assert "environment" not in names
    assert set(names) == {
        "current_behavior", "acceptance_criteria", "constraints", "problem", "who_benefits",
    }


def test_bug_to_feature_template_fields_force_the_non_waivable_pair_required(drift_apply) -> None:
    doc = _bug_doc()
    result = drift_apply.apply_drift(doc, "feature")
    by_name = {entry["name"]: entry for entry in result["template"]["fields"]}
    assert by_name["problem"]["required"] is True
    assert by_name["acceptance_criteria"]["required"] is True


def test_feature_to_bug_template_fields_demote_who_benefits(drift_apply) -> None:
    doc = _feature_doc()
    result = drift_apply.apply_drift(doc, "bug")
    by_name = {entry["name"]: entry for entry in result["template"]["fields"]}
    assert "who_benefits" not in by_name
    assert by_name["affected_users"]["required"] is False
    # the bug core is additive -- nothing the destination type requires is left out
    assert {"current_behavior", "expected_behavior", "steps_to_reproduce", "environment"} <= set(by_name)


def test_template_fields_keep_template_sourcing_across_the_rename(drift_apply) -> None:
    doc = _bug_doc()
    doc["template"] = {
        "applied": True, "path": ".github/ISSUE_TEMPLATE/bug.yml",
        "fields": [
            {"name": "current_behavior", "required": True, "source": "template"},
            {"name": "environment", "required": False, "source": "template"},
        ],
    }
    result = drift_apply.apply_drift(doc, "feature")
    by_name = {entry["name"]: entry for entry in result["template"]["fields"]}
    assert by_name["constraints"] == {
        "name": "constraints", "required": False, "source": "template",
    }
    assert by_name["current_behavior"]["source"] == "template"


def test_drift_does_not_invent_a_union_when_template_fields_is_absent(drift_apply) -> None:
    # an unsettled template resolution must stay unsettled: manufacturing the union here
    # is exactly the silent fallback the emission gate exists to refuse.
    doc = _bug_doc()
    doc["template"] = {"applied": False, "path": None}
    result = drift_apply.apply_drift(doc, "feature")
    assert "fields" not in result["template"]


def test_drifted_feature_missing_acceptance_criteria_halts_at_emission(
    drift_apply, canonical_schema,
) -> None:
    # the end-to-end payoff: the drifted document is validated against the feature union,
    # so the non-waivable gate fires instead of checking the bug's field list.
    doc = _bug_doc()
    doc["fields"] = [f for f in doc["fields"] if f["name"] != "expected_behavior"]
    result = drift_apply.apply_drift(doc, "feature")
    verdict = canonical_schema.validate(result, for_emission=True)
    assert verdict["valid"] is False
    assert verdict["halted"] is not None
    assert verdict["halted"]["field"] in ("problem", "acceptance_criteria")
    assert not any(e["path"].endswith("steps_to_reproduce") for e in verdict["errors"])


# ---- production-review round 2 -------------------------------------------


def test_stronger_incoming_is_retained_so_its_source_is_not_stranded(
    drift_apply, canonical_schema,
) -> None:
    # merging an `observed` field into a `reported` one understates the claim, which is safe --
    # but it drops the incoming's `source`, and verified_against cites that source, so the
    # drifted document would no longer validate
    doc = _feature_doc()
    doc["fields"] = [
        {"name": "current_behavior", "provenance": "reported",
         "value": "no PDF export path exists"}
        if f["name"] == "current_behavior" else f
        for f in doc["fields"]
    ]
    doc["fields"] = [
        dict(f, provenance="observed", source="docs/finance-workflow.md")
        if f["name"] == "problem" else f
        for f in doc["fields"]
    ]
    doc["verified_against"] = ["docs/finance-workflow.md"]
    assert canonical_schema.validate(doc)["valid"] is True

    result = drift_apply.apply_drift(doc, "bug")
    assert canonical_schema.validate(result) == {"valid": True, "errors": [], "halted": None}
    problem = _field(result["fields"], "problem")
    assert problem["provenance"] == "observed"
    assert problem["source"] == "docs/finance-workflow.md"


def test_two_observed_fields_merging_keep_both_sources(drift_apply, canonical_schema) -> None:
    doc = _bug_doc()
    doc["fields"] = [
        {"name": "steps_to_reproduce", "provenance": "observed",
         "value": "ran the export path directly", "source": "tests/test_export.py"}
        if f["name"] == "steps_to_reproduce" else f
        for f in doc["fields"]
    ]
    doc["fields"] = [
        dict(f, provenance="observed", source="src/export.py")
        if f["name"] == "current_behavior" else f
        for f in doc["fields"]
    ]
    doc["verified_against"] = ["src/export.py", "tests/test_export.py", "pyproject.toml"]

    result = drift_apply.apply_drift(doc, "feature")
    current_behavior = _field(result["fields"], "current_behavior")
    assert "src/export.py" in current_behavior["source"]
    assert "tests/test_export.py" in current_behavior["source"]
    # every verified_against entry still cites a live observed source
    assert canonical_schema.validate(result)["valid"] is True


def test_drift_drops_a_halt_computed_against_the_source_type(
    drift_apply, canonical_schema,
) -> None:
    # the halt named a field the destination type may not even have; carrying it over would
    # block the drifted document forever, and drift *is* the "keep working on it" exit
    doc = _feature_doc()
    doc["halted"] = {"field": "acceptance_criteria", "reason": "no testable condition"}
    result = drift_apply.apply_drift(doc, "bug")
    assert "halted" not in result
    assert canonical_schema.validate(result, for_emission=True)["halted"] is None


# ---- production-review round 4 -------------------------------------------


def test_cli_structurally_invalid_input_exits_3_and_drifts_nothing(tmp_path: Path) -> None:
    # the contract's first precondition is that the input passes canonical_schema without
    # --for-emission. Unenforced, the carry-over normalizes a malformed `fields` to empty and
    # reports success, so the user's answers vanish from what looks like a clean drift.
    doc = _bug_doc()
    doc["fields"] = {"name": "steps_to_reproduce", "provenance": "reported", "value": "the repro"}
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert any(e["path"] == "fields" for e in payload["errors"])
    assert "type" not in payload  # no drifted document was emitted


def test_cli_field_level_structural_error_exits_3(tmp_path: Path) -> None:
    doc = _bug_doc()
    # `source` is only legal when provenance == "observed"
    doc["fields"][0] = {
        "name": "current_behavior", "provenance": "reported", "value": "x", "source": "nope",
    }
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3


def test_cli_validation_does_not_require_emission_readiness(tmp_path: Path) -> None:
    # drift routinely fires mid-session, before the core fields are resolved -- the gate is
    # structural only, and tightening it to --for-emission would block the common case
    doc = _bug_doc()
    doc["fields"] = [
        {"name": "current_behavior", "provenance": "reported", "value": "it crashes"},
    ]
    doc["verified_against"] = []
    result = run_filing_script(
        "drift_apply.py", "--input", "-", "--to", "feature",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["type"] == "feature"


def test_drifted_fields_follow_the_rebuilt_union_order(drift_apply) -> None:
    # the renderer projects `fields` in document order, and the union is where the template's
    # structure and ordering live -- so a post-drift artifact that follows carry-table order
    # ignores the maintainer's section order for no reason but which row fired first
    doc = _feature_doc()
    doc["template"]["fields"] = [
        {"name": "who_benefits", "required": True, "source": "template"},
        {"name": "acceptance_criteria", "required": True, "source": "template"},
        {"name": "current_behavior", "required": True, "source": "template"},
        {"name": "problem", "required": True, "source": "template"},
    ]
    result = drift_apply.apply_drift(doc, "bug")
    union_order = [e["name"] for e in result["template"]["fields"]]
    field_order = [f["name"] for f in result["fields"]]
    ranked = [n for n in field_order if n in union_order]
    assert ranked == [n for n in union_order if n in field_order]


def test_fields_outside_the_union_keep_their_order_and_follow_behind(drift_apply) -> None:
    doc = _bug_doc()
    doc["fields"].append({
        "name": "root_cause", "provenance": "inferred", "value": "an encoding bug",
    })
    result = drift_apply.apply_drift(doc, "feature")
    union_names = {e["name"] for e in result["template"]["fields"]}
    field_order = [f["name"] for f in result["fields"]]
    assert "root_cause" not in union_names
    assert field_order[-1] == "root_cause"
