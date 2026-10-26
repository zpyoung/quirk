"""SKILL.md routing and guide structure checks for analyzing an app in building-mini-apps."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "building-mini-apps"
SKILL_PATH = SKILL_DIR / "SKILL.md"
GUIDE_PATH = SKILL_DIR / "references" / "analyzing-apps.md"
SCRIPTS_DIR = SKILL_DIR / "scripts"

GUIDE_SECTIONS = ["When this runs", "Preflight", "Core jobs (Stop 1)", "Survey", "Capture",
                  "Blueprint (Stop 2)", "Building approved proposals", "Resuming a run", "Rules"]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
H2_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
SCRIPT_REF_RE = re.compile(r"\$SKILL_DIR/scripts/([A-Za-z0-9_]+\.py)")


def _ordered_missing(titles: List[str], required: List[str]) -> List[str]:
    """Entries of `required` that are absent from `titles` or appear out of order."""
    missing = []
    cursor = 0
    for name in required:
        try:
            cursor = titles.index(name, cursor) + 1
        except ValueError:
            missing.append(name)
    return missing


def test_skill_has_analyzing_section_between_adding_a_pattern_and_rules() -> None:
    titles = H2_RE.findall(SKILL_PATH.read_text())
    assert "Analyzing an app" in titles
    assert titles.index("Adding a pattern") < titles.index("Analyzing an app") < titles.index("Rules")


def test_skill_analyzing_section_links_the_guide() -> None:
    text = SKILL_PATH.read_text()
    section = text.split("## Analyzing an app", 1)[1].split("\n## ", 1)[0]
    assert "(references/analyzing-apps.md)" in section


def test_skill_description_triggers_on_analyze() -> None:
    match = FRONTMATTER_RE.match(SKILL_PATH.read_text())
    assert match is not None
    description = DESCRIPTION_RE.search(match.group(1))
    assert description is not None
    lowered = description.group(1).lower()
    assert "analyze" in lowered
    assert "as a mini app" in lowered
    assert "build me" in lowered


def test_guide_exists_with_required_sections_in_order() -> None:
    assert GUIDE_PATH.is_file()
    assert _ordered_missing(H2_RE.findall(GUIDE_PATH.read_text()), GUIDE_SECTIONS) == []


def test_section_order_check_detects_a_missing_or_swapped_section() -> None:
    titles = list(GUIDE_SECTIONS)
    assert _ordered_missing([t for t in titles if t != "Survey"], GUIDE_SECTIONS) == ["Survey"]
    swapped = titles[:]
    swapped[3], swapped[4] = swapped[4], swapped[3]
    assert _ordered_missing(swapped, GUIDE_SECTIONS) != []


def test_guide_scripts_exist() -> None:
    names = sorted(set(SCRIPT_REF_RE.findall(GUIDE_PATH.read_text())))
    assert names, "guide names no scripts"
    for name in names:
        assert (SCRIPTS_DIR / name).is_file(), f"guide names missing script {name}"
