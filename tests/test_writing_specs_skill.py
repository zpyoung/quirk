"""The writing-specs split moved load-bearing literals between files.

Other skills read those exact strings — `writing-plans` plans from the paths, the tech-spec
complexity gate reads `Tech spec: requested` off the logic spec's Status line — so a paraphrase
during the move breaks the pipeline silently. These assertions pin the strings, not the prose.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "writing-specs"
HUB = SKILL_DIR / "SKILL.md"
LOGIC = SKILL_DIR / "logic-spec.md"
TECH = SKILL_DIR / "tech-spec.md"
REVIEWER = SKILL_DIR / "tech-spec-reviewer-prompt.md"


def test_skill_files_exist() -> None:
    for path in (HUB, LOGIC, TECH, REVIEWER):
        assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"


def test_frontmatter() -> None:
    match = re.search(r"^---\n(.*?)\n---\n", HUB.read_text(), re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter"
    block = match.group(1)
    assert re.search(r"^name: writing-specs$", block, re.MULTILINE)
    description = re.search(r"^description: (.+)$", block, re.MULTILINE)
    assert description and len(description.group(1)) >= 50


def test_logic_spec_contract_literals() -> None:
    body = LOGIC.read_text()
    for literal in (
        "Tech spec: requested",
        "## Status & amendments",
        "**Amendments:**",
        "docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md",
        "Decisions Locked",
        "Industry Insights",
        "Deferred Ideas",
        "No need to re-review",
    ):
        assert literal in body, f"logic-spec.md dropped {literal!r} in the move"


def test_brainstorming_section_names_match_logic_spec() -> None:
    """Brainstorming accumulates these lists in-session; the names must agree across the split."""
    brainstorming = (REPO_ROOT / "skills" / "brainstorming" / "SKILL.md").read_text()
    logic = LOGIC.read_text()
    for section in ("Industry Insights", "Deferred Ideas"):
        assert section in brainstorming and section in logic


def test_tech_spec_no_code_tags() -> None:
    body = TECH.read_text()
    for tag in ("CONTRACT:", "SCHEMA:", "COMMAND:", "REGEX:", "CONFIG:", "PSEUDOCODE"):
        assert tag in body, f"tech-spec.md dropped the {tag} No-Code tag"


def test_tech_spec_complexity_gate_intact() -> None:
    body = TECH.read_text()
    assert "more than one session" in body
    assert "crosses a subsystem boundary" in body
    assert "≳3 source files" in body
    assert "Tech spec: requested" in body


def test_ownership_paragraph_has_one_home() -> None:
    """The rubric forbids duplicating a paragraph across the pair -- it must obey itself."""
    assert "owns *where* and *contracts*" in HUB.read_text()
    assert "owns *where* and *contracts*" not in TECH.read_text()


def test_no_stale_skill_name_references() -> None:
    stale = [
        path
        for path in REPO_ROOT.joinpath("skills").rglob("*.md")
        if "writing-tech-spec" in path.read_text()
    ]
    assert not stale, f"stale writing-tech-spec references: {stale}"
