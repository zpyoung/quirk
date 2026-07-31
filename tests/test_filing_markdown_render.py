from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "filing-requests" / "canonical"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture(scope="module")
def markdown_render():
    return load_filing_module("markdown_render")


# ---- module-level constants: fixed wording, asserted verbatim ----------


def test_hedge_prefix_is_a_fixed_string(markdown_render) -> None:
    assert markdown_render.HEDGE_PREFIX == "Inferred, not directly confirmed — "


def test_attribution_line_is_a_fixed_string(markdown_render) -> None:
    assert markdown_render.ATTRIBUTION_LINE == (
        "*Proposed by the reporter, included as an open suggestion rather than a directive.*"
    )


def test_headless_banner_is_a_fixed_string(markdown_render) -> None:
    assert markdown_render.HEADLESS_BANNER == "> **Headless run: no human confirmed this artifact.**"


def test_disclosure_footer_is_a_fixed_string(markdown_render) -> None:
    assert markdown_render.DISCLOSURE_FOOTER == "*This report was drafted with AI assistance.*"


# ---- render(): provenance rendering rules -------------------------------


def _doc(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "type": "bug",
        "headless": False,
        "title": "Something broke",
        "fields": [],
        "verified_against": [],
        "disclosure_required": False,
    }
    base.update(overrides)
    return base


def test_title_renders_as_h1(markdown_render) -> None:
    text = markdown_render.render(_doc(title="Export fails on em-dashes"))
    assert text.startswith("# Export fails on em-dashes\n")


def test_reported_field_renders_plainly(markdown_render) -> None:
    doc = _doc(fields=[
        {"name": "current_behavior", "provenance": "reported", "value": "it crashes on export"},
    ])
    text = markdown_render.render(doc)
    assert "## Current Behavior\n\nit crashes on export" in text


def test_observed_field_renders_plainly_without_source(markdown_render) -> None:
    doc = _doc(fields=[
        {
            "name": "environment", "provenance": "observed", "value": "reports 2.4.1",
            "source": "pyproject.toml",
        },
    ])
    text = markdown_render.render(doc)
    assert "## Environment\n\nreports 2.4.1" in text
    # source is provenance metadata, not artifact content -- only "Verified against" surfaces it
    assert "pyproject.toml" not in text


def test_inferred_field_gets_hedge_prefix(markdown_render) -> None:
    doc = _doc(fields=[
        {"name": "root_cause", "provenance": "inferred", "value": "an encoding bug"},
    ])
    text = markdown_render.render(doc)
    assert "## Root Cause\n\nInferred, not directly confirmed — an encoding bug" in text


def test_missing_field_renders_its_reason_with_no_added_prefix(markdown_render) -> None:
    doc = _doc(fields=[
        {"name": "frequency", "provenance": "missing", "reason": "intermittent, no reliable trigger"},
    ])
    text = markdown_render.render(doc)
    assert "## Frequency\n\nintermittent, no reliable trigger" in text


def test_fields_render_in_field_set_order(markdown_render) -> None:
    doc = _doc(fields=[
        {"name": "current_behavior", "provenance": "reported", "value": "b"},
        {"name": "expected_behavior", "provenance": "reported", "value": "a"},
    ])
    text = markdown_render.render(doc)
    assert text.index("## Current Behavior") < text.index("## Expected Behavior")


# ---- render(): root-key rules -------------------------------------------


def test_empty_verified_against_is_pruned_not_rendered_empty(markdown_render) -> None:
    text = markdown_render.render(_doc(verified_against=[]))
    assert "Verified against" not in text


def test_nonempty_verified_against_lists_entries_verbatim(markdown_render) -> None:
    doc = _doc(verified_against=["src/export.py:142", "poetry.lock"])
    text = markdown_render.render(doc)
    assert "## Verified against\n\n- src/export.py:142\n- poetry.lock" in text


def test_proposed_solution_absent_omits_section(markdown_render) -> None:
    text = markdown_render.render(_doc())
    assert "Proposed approach" not in text


def test_proposed_solution_present_renders_after_fields_with_attribution(markdown_render) -> None:
    doc = _doc(
        fields=[{"name": "current_behavior", "provenance": "reported", "value": "x"}],
        proposed_solution={"value": "pass encoding='utf-8'", "attributed_to": "reporter"},
    )
    text = markdown_render.render(doc)
    fields_idx = text.index("## Current Behavior")
    proposed_idx = text.index("## Proposed approach")
    assert fields_idx < proposed_idx
    assert (
        "## Proposed approach\n\n"
        "*Proposed by the reporter, included as an open suggestion rather than a directive.*\n\n"
        "pass encoding='utf-8'"
    ) in text


def test_disclosure_required_false_renders_no_footer(markdown_render) -> None:
    text = markdown_render.render(_doc(disclosure_required=False))
    assert "AI assistance" not in text


def test_disclosure_required_true_renders_fixed_footer_last(markdown_render) -> None:
    text = markdown_render.render(_doc(disclosure_required=True))
    assert text.rstrip("\n").endswith("*This report was drafted with AI assistance.*")


def test_headless_true_renders_banner_above_title(markdown_render) -> None:
    text = markdown_render.render(_doc(headless=True))
    assert text.startswith("> **Headless run: no human confirmed this artifact.**\n")
    assert text.index("Headless run") < text.index("# Something broke")


def test_headless_false_renders_no_banner(markdown_render) -> None:
    text = markdown_render.render(_doc(headless=False))
    assert "Headless run" not in text


def test_never_rendered_keys_do_not_leak_into_output(markdown_render) -> None:
    doc = _doc(
        type="bug",
        depth="read",
        target={"kind": "github", "repo": "acme/app", "writable": True, "third_party": "no", "visibility": "private"},
        template={"applied": False, "path": None, "fields": [{"name": "x", "required": True, "source": "core"}]},
    )
    text = markdown_render.render(doc)
    assert "acme/app" not in text
    assert "read" not in text or "read" not in text.lower()


# ---- full fixture end-to-end renders ------------------------------------


def test_valid_bug_fixture_renders_all_field_sections(markdown_render) -> None:
    doc = _load_fixture("valid-bug.json")
    text = markdown_render.render(doc)
    assert text.startswith("# Export fails with UnicodeDecodeError")
    assert "## Current Behavior" in text
    assert "## Expected Behavior" in text
    assert "## Steps To Reproduce" in text
    assert "## Environment" in text
    assert "## Root Cause\n\nInferred, not directly confirmed —" in text
    assert "## Verified against\n\n- poetry.lock\n- pyproject.toml" in text


def test_valid_feature_fixture_renders_negative_observation_plainly(markdown_render) -> None:
    doc = _load_fixture("valid-feature.json")
    text = markdown_render.render(doc)
    assert "## Current Behavior\n\nno PDF export path exists" in text


def test_headless_fixture_renders_missing_field_and_banner(markdown_render) -> None:
    doc = _load_fixture("headless.json")
    text = markdown_render.render(doc)
    assert text.startswith("> **Headless run: no human confirmed this artifact.**")
    assert "## Expected Behavior\n\nno human in session" in text


# ---- CLI: precondition gate ----------------------------------------------


def test_cli_valid_bug_exits_0_and_prints_markdown(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("# Export fails with UnicodeDecodeError")


def test_cli_halted_feature_refuses_with_exit_3_and_validate_body_shape(tmp_path: Path) -> None:
    doc = _load_fixture("halted-feature.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["halted"] == {
        "field": "acceptance_criteria",
        "reason": "no testable pass/fail condition established",
    }


def test_cli_core_incomplete_document_refuses_with_exit_3(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    del doc["template"]["fields"]  # structurally incomplete for emission
    result = run_filing_script(
        "markdown_render.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3


def test_cli_schema_version_too_new_exits_8(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    doc["schema_version"] = 999
    result = run_filing_script(
        "markdown_render.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 8


def test_cli_malformed_json_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "markdown_render.py", "--input", "-", cwd=tmp_path, stdin="{not json",
    )
    assert result.returncode == 2


def test_cli_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "markdown_render.py", "--input", str(tmp_path / "missing.json"), cwd=tmp_path,
    )
    assert result.returncode == 2


# ---- CLI: --output / --write / --slug ------------------------------------


def test_cli_output_writes_to_path_instead_of_stdout(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    out_path = tmp_path / "draft.md"
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--output", str(out_path),
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert out_path.read_text().startswith("# Export fails with UnicodeDecodeError")


def test_cli_write_computes_dated_slugged_path_and_prints_it(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path),
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    printed = result.stdout.strip()
    assert re.fullmatch(r"docs/quirk/requests/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md", printed)
    written = tmp_path / printed
    assert written.exists()
    assert written.read_text().startswith("# Export fails with UnicodeDecodeError")


def test_cli_write_with_slug_override_uses_given_slug_verbatim(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path), "--slug", "custom-slug",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    printed = result.stdout.strip()
    assert printed.endswith("-custom-slug.md")
    assert (tmp_path / printed).exists()


# ---- wave-3 checkpoint regressions ---------------------------------------


def test_cli_write_rejects_a_slug_that_escapes_the_artifact_directory(tmp_path: Path) -> None:
    # --slug is user input that lands in a path. Unsanitized, `..` segments walk out of
    # docs/quirk/requests/ and overwrite an unrelated file under (or above) the root.
    doc = _load_fixture("valid-bug.json")
    root = tmp_path / "project"
    root.mkdir()
    victim = tmp_path / "PWNED.md"
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(root),
        "--slug", "../../../PWNED", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    printed = result.stdout.strip()
    assert ".." not in printed
    assert not victim.exists()
    written = (root / printed).resolve()
    assert written.exists()
    assert root.resolve() in written.parents


def test_cli_write_slug_override_is_slugified(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path),
        "--slug", "Nested/Path Segment", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("-nested-path-segment.md")


def test_cli_write_slug_with_no_usable_characters_exits_2(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path),
        "--slug", "../..", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2
    assert not list(tmp_path.rglob("*.md"))


def test_fixed_wordings_are_defined_in_common_not_this_module(markdown_render) -> None:
    # tech.md fixes all four in _common.py; markdown_render imports them, so there is never
    # a second copy that can drift from the one the contract names.
    common = load_filing_module("_common")
    names = ("HEDGE_PREFIX", "ATTRIBUTION_LINE", "HEADLESS_BANNER", "DISCLOSURE_FOOTER")
    scripts_dir = Path(markdown_render.__file__).parent
    render_source = (scripts_dir / "markdown_render.py").read_text(encoding="utf-8")
    common_source = (scripts_dir / "_common.py").read_text(encoding="utf-8")
    for name in names:
        assert getattr(markdown_render, name) == getattr(common, name)
        assert f"{name} = " in common_source
        assert f"{name} = " not in render_source


def test_cli_write_never_overwrites_an_existing_artifact(tmp_path: Path) -> None:
    # tech.md -> Rollback: "the markdown artifact write is additive ... nothing here mutates an
    # existing file". Two same-day requests whose titles slug alike must not collide.
    doc = _load_fixture("valid-bug.json")
    first = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path), "--slug", "collision",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert first.returncode == 0, first.stderr
    first_path = tmp_path / first.stdout.strip()
    original = first_path.read_text()

    second_doc = dict(doc, title="A completely different request")
    second = run_filing_script(
        "markdown_render.py", "--input", "-", "--write", str(tmp_path), "--slug", "collision",
        cwd=tmp_path, stdin=json.dumps(second_doc),
    )
    assert second.returncode == 0, second.stderr
    second_path = tmp_path / second.stdout.strip()

    assert second_path != first_path
    assert first_path.read_text() == original
    assert second_path.read_text().startswith("# A completely different request")
