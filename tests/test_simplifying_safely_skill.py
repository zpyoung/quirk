"""Packaging integrity checks for the simplifying-safely skill."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SKILL_DIR = SKILLS_DIR / "simplifying-safely"
SKILL_PATH = SKILL_DIR / "SKILL.md"
EVIDENCE_AND_LIMITS_PATH = SKILL_DIR / "evidence-and-limits.md"
README_PATH = REPO_ROOT / "README.md"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DESCRIPTION_RE = re.compile(r'^description:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)

def _read_skill() -> str:
    return SKILL_PATH.read_text()


def _frontmatter_block(body: str) -> str:
    match = FRONTMATTER_RE.match(body)
    assert match is not None, "SKILL.md missing YAML frontmatter"
    return match.group(1)


def _description(fm_body: str) -> str:
    match = DESCRIPTION_RE.search(fm_body)
    assert match is not None, "frontmatter missing 'description'"
    return match.group(1)


def test_frontmatter_has_name_and_description() -> None:
    """Frontmatter is delimited and carries the required package fields."""
    fm_body = _frontmatter_block(_read_skill())
    assert re.search(r"^name:\s*.+$", fm_body, re.MULTILINE), "frontmatter missing 'name'"
    assert re.search(r"^description:\s*.+$", fm_body, re.MULTILINE), (
        "frontmatter missing 'description'"
    )


def test_frontmatter_name_matches_directory() -> None:
    """Frontmatter name matches the skill directory."""
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    name_match = re.search(r"^name:\s*(.+?)\s*$", fm_body, re.MULTILINE)
    assert name_match, "frontmatter missing 'name'"
    expected = SKILL_PATH.parent.name
    assert name_match.group(1) == expected, f"frontmatter name {name_match.group(1)!r} != directory {expected!r}"


def test_frontmatter_description_length_in_range() -> None:
    """Description is non-trivial and within the frontmatter limit."""
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    description = _description(fm_body)
    assert 50 <= len(description) <= 1024, f"description length {len(description)} out of range [50, 1024]"


def test_relative_links_resolve_within_skill_directory() -> None:
    """Every Markdown reference is relative, contained, and resolves."""
    body = _read_skill()
    targets = re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)", body)
    assert targets, "SKILL.md must contain at least one markdown reference link"
    for target in targets:
        assert target == target.strip(), f"link target is not bare: {target!r}"
        assert not target.startswith(("@", "/", "#")), f"link target is not relative: {target!r}"
        assert "://" not in target, f"link target is not relative: {target!r}"
        path_text, _, _fragment = target.partition("#")
        assert path_text, f"link has no relative file target: {target!r}"
        resolved = (SKILL_DIR / path_text).resolve()
        try:
            resolved.relative_to(SKILL_DIR.resolve())
        except ValueError:
            raise AssertionError(f"link escapes the skill directory: {target!r}") from None
        assert resolved.is_file(), f"relative link does not resolve: {target!r}"


def test_evidence_and_limits_file_exists_and_nonempty() -> None:
    """The companion reference file exists and is non-empty."""
    assert EVIDENCE_AND_LIMITS_PATH.exists(), f"reference file not found: {EVIDENCE_AND_LIMITS_PATH}"
    assert len(EVIDENCE_AND_LIMITS_PATH.read_text().strip()) > 0, "evidence-and-limits.md is empty"


def test_readme_skill_count_matches_skill_directory() -> None:
    """README skill count matches the packaged skill directories."""
    readme = README_PATH.read_text()
    skill_dirs = [path for path in SKILLS_DIR.iterdir() if (path / "SKILL.md").exists()]

    match = re.search(r"\*\*(\d+) skills\*\*", readme)
    assert match, "README missing skill count in What ships section"
    assert int(match.group(1)) == len(skill_dirs), (
        f"README claims {match.group(1)} skills, found {len(skill_dirs)} skills/*/SKILL.md directories"
    )


