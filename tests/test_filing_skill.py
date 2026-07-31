from __future__ import annotations

import re
from pathlib import Path

import pytest

from .conftest import load_filing_module

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "filing-requests"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "reference"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def _frontmatter() -> str:
    match = re.match(r"^---\n(.*?)\n---\n", SKILL_PATH.read_text(), re.DOTALL)
    assert match is not None, "skill missing YAML frontmatter"
    return match.group(1)


def _description() -> str:
    return re.search(r"^description:\s*(.+)$", _frontmatter(), re.MULTILINE).group(1)


def test_skill_has_frontmatter() -> None:
    fm = _frontmatter()
    assert re.search(r"^name:\s*filing-requests\s*$", fm, re.MULTILINE)
    assert re.search(r"^description:\s*.{30,}$", fm, re.MULTILINE)


@pytest.mark.parametrize("trigger", ["file", "report", "bug", "feature request"])
def test_description_carries_the_filing_trigger_phrases(trigger: str) -> None:
    assert trigger in _description().lower()


@pytest.mark.parametrize("sibling_trigger", ["build", "implement"])
def test_description_disambiguates_from_brainstorming(sibling_trigger: str) -> None:
    # both skills fire on the word "feature"; the description has to say which verb is whose,
    # or both trigger on "I want a feature that..."
    description = _description().lower()
    assert sibling_trigger in description
    assert "brainstorming" in description


def test_skill_names_the_three_stages() -> None:
    body = SKILL_PATH.read_text()
    for stage in ("Orient", "Establish", "Emit"):
        assert re.search(rf"^## Stage \d+ — {stage}$", body, re.MULTILINE), stage


def test_skill_documents_every_provenance_value() -> None:
    body = SKILL_PATH.read_text()
    for provenance in ("observed", "reported", "inferred", "missing"):
        assert f"`{provenance}`" in body


def test_skill_invokes_every_script_that_has_a_cli() -> None:
    body = SKILL_PATH.read_text()
    for script in (
        "template_resolve.py",
        "canonical_schema.py",
        "secret_scan.py",
        "markdown_render.py",
        "drift_apply.py",
        "github_file.py",
    ):
        assert script in body, f"SKILL.md never invokes {script}"


def test_skill_references_every_reference_doc() -> None:
    body = SKILL_PATH.read_text()
    for doc in sorted(REFERENCE_DIR.glob("*.md")):
        assert doc.name in body, f"SKILL.md never points at reference/{doc.name}"


def test_every_referenced_script_exists() -> None:
    body = SKILL_PATH.read_text()
    for name in set(re.findall(r"scripts/([a-z_]+\.py)", body)):
        assert (SCRIPTS_DIR / name).exists(), name


def test_skill_documents_the_shared_exit_codes() -> None:
    body = SKILL_PATH.read_text()
    for code in ("0", "1", "2", "3", "5", "6", "8"):
        assert re.search(rf"^\| {code} \|", body, re.MULTILINE), f"exit code {code} undocumented"


def test_skill_states_the_two_gates_that_block_emission() -> None:
    body = SKILL_PATH.read_text()
    assert "non-waivable" in body.lower()
    assert "--for-emission" in body
    assert "--execute" in body


def test_skill_forbids_filing_a_headless_document_automatically() -> None:
    body = SKILL_PATH.read_text()
    assert "headless" in body.lower()
    assert re.search(r"never filed to a tracker automatically", body, re.IGNORECASE)


def test_skill_forbids_duplicate_detection() -> None:
    # logic.md rules this out entirely -- the skill inspects the code, not the tracker
    assert "duplicate" in SKILL_PATH.read_text().lower()


@pytest.mark.parametrize("name", ["field-catalogs.md", "guardrails.md", "template-resolution.md"])
def test_reference_doc_exists_and_is_substantive(name: str) -> None:
    path = REFERENCE_DIR / name
    assert path.exists(), f"missing reference/{name}"
    assert len(path.read_text().split()) > 200


def test_field_catalogs_covers_every_core_and_optional_field() -> None:
    common = load_filing_module("_common")
    body = (REFERENCE_DIR / "field-catalogs.md").read_text()
    for table in (common.CORE_FIELDS, common.OPTIONAL_FIELDS):
        for request_type, names in table.items():
            for name in names:
                assert f"`{name}`" in body, f"{request_type}: {name} missing from field-catalogs.md"


def test_guardrails_names_every_secret_scan_pattern() -> None:
    secret_scan = load_filing_module("secret_scan")
    body = (REFERENCE_DIR / "guardrails.md").read_text().lower()
    for name, _pattern in secret_scan._PATTERNS:
        # the doc paraphrases for a human reader, so match on the distinctive token
        token = name.split("_")[0]
        assert token in body, f"guardrails.md never mentions the {name} pattern"
