from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "filing-requests" / "canonical"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture(scope="module")
def common():
    return load_filing_module("_common")


@pytest.fixture(scope="module")
def canonical_schema():
    return load_filing_module("canonical_schema")


# ---- _common.py --------------------------------------------------------


def test_current_schema_version(common) -> None:
    assert common.CURRENT_SCHEMA_VERSION == 1


def test_core_fields_verbatim(common) -> None:
    assert common.CORE_FIELDS == {
        "bug": ["current_behavior", "expected_behavior", "steps_to_reproduce", "environment"],
        "feature": ["problem", "who_benefits", "current_behavior", "acceptance_criteria"],
        "code-change": ["scope", "why_now", "blast_radius"],
    }


def test_optional_fields_verbatim(common) -> None:
    assert common.OPTIONAL_FIELDS == {
        "bug": ["stack_trace", "frequency", "regression_range", "workaround"],
        "feature": ["value_or_impact", "constraints", "out_of_scope", "prior_art"],
        "code-change": ["migration", "rollback", "test_plan", "perf_impact"],
    }


def test_non_waivable_verbatim(common) -> None:
    assert common.NON_WAIVABLE == {"feature": ["problem", "acceptance_criteria"]}


def test_slugify_lowercases_and_collapses_non_alnum(common) -> None:
    assert common.slugify("  --Multiple   Spaces--  ") == "multiple-spaces"


def test_slugify_custom_separator(common) -> None:
    assert common.slugify("Steps To Reproduce", sep="_") == "steps_to_reproduce"


def test_slugify_caps_at_60_chars(common) -> None:
    result = common.slugify("word " * 30)
    assert len(result) <= 60
    assert not result.endswith("-")


def test_read_json_arg_from_path(common, tmp_path: Path) -> None:
    p = tmp_path / "doc.json"
    p.write_text('{"a": 1}')
    assert common.read_json_arg(str(p)) == {"a": 1}


def test_read_json_arg_from_stdin(common, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"a": 1}'))
    assert common.read_json_arg("-") == {"a": 1}


def test_read_json_arg_missing_file_raises(common, tmp_path: Path) -> None:
    with pytest.raises(OSError):
        common.read_json_arg(str(tmp_path / "nope.json"))


def test_read_json_arg_malformed_json_raises(common, tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        common.read_json_arg(str(p))


def test_check_schema_version_passes_for_current(common) -> None:
    common.check_schema_version({"schema_version": 1})


def test_check_schema_version_tolerates_missing_key(common) -> None:
    common.check_schema_version({})


def test_check_schema_version_raises_when_too_new(common) -> None:
    with pytest.raises(common.SchemaVersionError):
        common.check_schema_version({"schema_version": 999})


def test_check_schema_version_excludes_bool_from_int_check(
    common, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # bool subclasses int in Python; schema_version: true must never be compared as if it were 1
    monkeypatch.setattr(common, "CURRENT_SCHEMA_VERSION", 0)
    common.check_schema_version({"schema_version": True})


# ---- canonical_schema.validate() ---------------------------------------


def test_valid_bug_fixture_passes_for_emission(canonical_schema) -> None:
    doc = _load_fixture("valid-bug.json")
    assert canonical_schema.validate(doc, for_emission=True) == {
        "valid": True, "errors": [], "halted": None,
    }


def test_valid_feature_fixture_passes_for_emission(canonical_schema) -> None:
    doc = _load_fixture("valid-feature.json")
    assert canonical_schema.validate(doc, for_emission=True) == {
        "valid": True, "errors": [], "halted": None,
    }


def test_headless_bug_fixture_passes_for_emission(canonical_schema) -> None:
    doc = _load_fixture("headless.json")
    assert canonical_schema.validate(doc, for_emission=True) == {
        "valid": True, "errors": [], "halted": None,
    }


def test_halted_feature_fixture_is_structurally_valid_without_for_emission(canonical_schema) -> None:
    doc = _load_fixture("halted-feature.json")
    assert canonical_schema.validate(doc, for_emission=False) == {
        "valid": True, "errors": [], "halted": None,
    }


def test_halted_feature_fixture_halts_on_for_emission(canonical_schema) -> None:
    doc = _load_fixture("halted-feature.json")
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert result["halted"] == {
        "field": "acceptance_criteria",
        "reason": "no testable pass/fail condition established",
    }


def test_bug_missing_steps_to_reproduce_resolves_without_halt(canonical_schema) -> None:
    doc = _load_fixture("valid-bug.json")
    doc["fields"] = [f for f in doc["fields"] if f["name"] != "steps_to_reproduce"]
    doc["fields"].append({
        "name": "steps_to_reproduce",
        "provenance": "missing",
        "reason": "intermittent; no reliable trigger identified",
    })
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is True
    assert result["halted"] is None


def test_observed_missing_source_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "environment", "provenance": "observed", "value": "x"}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].source" for e in result["errors"])


def test_missing_with_value_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "frequency", "provenance": "missing", "reason": "x", "value": "y"}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].value" for e in result["errors"])


def test_polarity_on_non_observed_field_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{
            "name": "current_behavior", "provenance": "reported", "value": "x", "polarity": "negative",
        }],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].polarity" for e in result["errors"])


def test_verified_against_must_cite_a_source(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{
            "name": "environment", "provenance": "observed", "value": "x", "source": "pyproject.toml",
        }],
        "verified_against": ["some/other/file.py"],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "verified_against[0]" for e in result["errors"])


def test_verified_against_matching_a_source_is_valid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{
            "name": "environment", "provenance": "observed", "value": "x",
            "source": "poetry.lock, pyproject.toml",
        }],
        "verified_against": ["poetry.lock"],
    }
    assert canonical_schema.validate(doc) == {"valid": True, "errors": [], "halted": None}


def test_verified_against_error_redacts_the_entry(canonical_schema) -> None:
    secret_looking_entry = "ghp_" + "A" * 36
    doc = {
        "schema_version": 1,
        "fields": [{
            "name": "environment", "provenance": "observed", "value": "x", "source": "pyproject.toml",
        }],
        "verified_against": [secret_looking_entry],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    message = next(e["message"] for e in result["errors"] if e["path"] == "verified_against[0]")
    assert secret_looking_entry not in message
    assert message.startswith("'ghp_")


# ---- F0: template.fields drives the union gate, never _common.CORE_FIELDS ----


def test_template_fields_absent_fails_emission_structurally(canonical_schema) -> None:
    doc = _load_fixture("valid-bug.json")
    del doc["template"]["fields"]
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert any(e["path"] == "template.fields" for e in result["errors"])


def test_template_fields_empty_fails_emission_structurally(canonical_schema) -> None:
    doc = _load_fixture("valid-bug.json")
    doc["template"]["fields"] = []
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert any(e["path"] == "template.fields" for e in result["errors"])


def test_template_fields_omitting_a_core_field_does_not_fall_back_to_core_fields_table(
    canonical_schema,
) -> None:
    # if the gate fell back to _common.CORE_FIELDS, dropping "environment" from both
    # template.fields and fields[] would still be flagged as an unresolved core field
    doc = _load_fixture("valid-bug.json")
    doc["template"]["fields"] = [f for f in doc["template"]["fields"] if f["name"] != "environment"]
    doc["fields"] = [f for f in doc["fields"] if f["name"] != "environment"]
    doc["verified_against"] = []  # was citing environment's source; drop it along with the field
    assert canonical_schema.validate(doc, for_emission=True) == {
        "valid": True, "errors": [], "halted": None,
    }


def test_template_field_entry_missing_name_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "template": {"applied": False, "path": None, "fields": [{"required": True, "source": "core"}]},
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "template.fields[0].name" for e in result["errors"])


def test_template_field_entry_bad_source_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "template": {
            "applied": False, "path": None,
            "fields": [{"name": "problem", "required": True, "source": "elsewhere"}],
        },
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "template.fields[0].source" for e in result["errors"])


# ---- F1: field sibling values must be non-empty strings, not merely present ----


def test_reported_field_with_null_value_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "problem", "provenance": "reported", "value": None}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].value" for e in result["errors"])


def test_reported_field_with_blank_value_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "problem", "provenance": "reported", "value": "   "}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].value" for e in result["errors"])


def test_observed_field_with_non_string_source_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "environment", "provenance": "observed", "value": "x", "source": []}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].source" for e in result["errors"])


def test_missing_field_with_non_string_reason_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "fields": [{"name": "frequency", "provenance": "missing", "reason": 42}],
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "fields[0].reason" for e in result["errors"])


# ---- F2: disclosure_required is derived from target, never trusted ----


def test_disclosure_required_false_on_public_target_is_invalid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "target": {
            "kind": "github", "repo": "acme/app", "writable": True,
            "third_party": "no", "visibility": "public",
        },
        "disclosure_required": False,
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "disclosure_required" for e in result["errors"])


def test_disclosure_required_matching_derivation_is_valid(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "target": {
            "kind": "github", "repo": "acme/app", "writable": True,
            "third_party": "no", "visibility": "public",
        },
        "disclosure_required": True,
    }
    result = canonical_schema.validate(doc)
    assert not any(e["path"] == "disclosure_required" for e in result["errors"])


# ---- F3: the non-waivable gate is stricter than ordinary core resolution ----


def test_non_waivable_gate_rejects_inferred_provenance(canonical_schema) -> None:
    doc = _load_fixture("valid-feature.json")
    doc["fields"] = [
        {**f, "provenance": "inferred"} if f["name"] == "problem" else f for f in doc["fields"]
    ]
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert result["halted"] == {
        "field": "problem",
        "reason": "an inferred value is not sufficient for a non-waivable field",
    }


def test_non_waivable_gate_rejects_needs_confirmation(canonical_schema) -> None:
    doc = _load_fixture("valid-feature.json")
    for f in doc["fields"]:
        if f["name"] == "acceptance_criteria":
            f["needs_confirmation"] = True
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert result["halted"] == {
        "field": "acceptance_criteria",
        "reason": "value needs user confirmation before it can be treated as resolved",
    }


# ---- F4: a malformed "fields" key fails cleanly, never crashes emission checks ----


def test_fields_null_fails_structurally_without_crash(canonical_schema) -> None:
    doc = {"schema_version": 1, "fields": None}
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert any(e["path"] == "fields" for e in result["errors"])


def test_fields_wrong_type_fails_structurally_without_crash(canonical_schema) -> None:
    doc = {"schema_version": 1, "fields": 1}
    result = canonical_schema.validate(doc, for_emission=True)
    assert result["valid"] is False
    assert any(e["path"] == "fields" for e in result["errors"])


# ---- F5: target.repo must be exactly "owner/repo" ----


@pytest.mark.parametrize("repo", ["", "repo", "a/b/c", "/repo", "owner/"])
def test_repo_shape_rejected(canonical_schema, repo: str) -> None:
    doc = {
        "schema_version": 1,
        "target": {
            "kind": "github", "repo": repo, "writable": True,
            "third_party": "no", "visibility": "private",
        },
    }
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "target.repo" for e in result["errors"])


def test_repo_shape_accepted(canonical_schema) -> None:
    doc = {
        "schema_version": 1,
        "target": {
            "kind": "github", "repo": "acme/app", "writable": True,
            "third_party": "no", "visibility": "private",
        },
    }
    result = canonical_schema.validate(doc)
    assert not any(e["path"] == "target.repo" for e in result["errors"])


# ---- F6: schema_version: true is not an integer ----


def test_schema_version_true_is_invalid(canonical_schema) -> None:
    doc = {"schema_version": True}
    result = canonical_schema.validate(doc)
    assert result["valid"] is False
    assert any(e["path"] == "schema_version" for e in result["errors"])


# ---- CLI contract -------------------------------------------------------


def test_cli_valid_bug_exits_0(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", "--for-emission",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": True, "errors": [], "halted": None}


def test_cli_halted_feature_exits_3(tmp_path: Path) -> None:
    doc = _load_fixture("halted-feature.json")
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", "--for-emission",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["halted"]["field"] == "acceptance_criteria"


def test_cli_fields_null_exits_3_not_a_crash(tmp_path: Path) -> None:
    doc = {"schema_version": 1, "fields": None}
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", "--for-emission",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    assert "Traceback" not in result.stderr


def test_cli_malformed_json_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", cwd=tmp_path, stdin="{not json",
    )
    assert result.returncode == 2


def test_cli_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "canonical_schema.py", "--input", str(tmp_path / "missing.json"), cwd=tmp_path,
    )
    assert result.returncode == 2


def test_cli_non_utf8_file_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_bytes(b'{"a": "\x80bad"}')
    result = run_filing_script(
        "canonical_schema.py", "--input", str(bad), cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_cli_deeply_nested_json_exits_2(tmp_path: Path) -> None:
    nested = "[" * 200_000 + "]" * 200_000
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", cwd=tmp_path, stdin=nested,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_cli_schema_version_too_new_exits_8(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    doc["schema_version"] = 999
    result = run_filing_script(
        "canonical_schema.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 8


def test_cli_reads_from_file_path(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    input_path = tmp_path / "doc.json"
    input_path.write_text(json.dumps(doc))
    result = run_filing_script(
        "canonical_schema.py", "--input", str(input_path), "--for-emission", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
