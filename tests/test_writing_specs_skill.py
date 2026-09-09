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
    """`docs/` is excluded: shipped specs are historical records of the pre-split name."""
    candidates = [
        *REPO_ROOT.joinpath("skills").rglob("*.md"),
        *REPO_ROOT.joinpath("commands").rglob("*.md"),
        *REPO_ROOT.joinpath(".claude-plugin").glob("*.json"),
        REPO_ROOT / "README.md",
    ]
    stale = [path for path in candidates if "writing-tech-spec" in path.read_text()]
    assert not stale, f"stale writing-tech-spec references: {stale}"


def test_callers_point_at_the_writing_specs_skill() -> None:
    """The three callers resolve the hub by name; a rename here strands the whole pipeline."""
    callers = {
        "brainstorming": "logic-spec.md",
        "subagent-driven-development": "tech-spec.md",
        "executing-plans": "tech-spec.md",
    }
    for skill, rubric in callers.items():
        body = (REPO_ROOT / "skills" / skill / "SKILL.md").read_text()
        assert "quirk:writing-specs" in body, f"{skill} lost its quirk:writing-specs pointer"
        assert rubric in body, f"{skill} does not name the {rubric} rubric it needs"


def _heading_slugs(body: str) -> set:
    slugs = set()
    for heading in re.findall(r"^#{1,6}\s+(.*)$", body, re.MULTILINE):
        text = heading.replace("`", "").lower()
        slugs.add(re.sub(r"[^a-z0-9\s-]", "", text).strip().replace(" ", "-"))
    return slugs


def test_cross_file_links_and_anchors_resolve() -> None:
    """The split turned prose into pointers; a renamed heading breaks them silently."""
    sources = [
        *sorted(SKILL_DIR.glob("*.md")),
        *(
            REPO_ROOT / "skills" / skill / "SKILL.md"
            for skill in ("brainstorming", "subagent-driven-development", "executing-plans")
        ),
    ]
    broken = []
    for source in sources:
        body = source.read_text()
        for _, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", body):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            relative, _, anchor = target.partition("#")
            resolved = (source.parent / relative) if relative else source
            if not resolved.is_file():
                broken.append(f"{source.relative_to(REPO_ROOT)} -> {target} (no such file)")
                continue
            if anchor and anchor not in _heading_slugs(resolved.read_text()):
                broken.append(f"{source.relative_to(REPO_ROOT)} -> {target} (no such heading)")
    assert not broken, f"unresolvable links: {broken}"
