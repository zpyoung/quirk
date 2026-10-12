"""Structure checks for the using-apps-like-a-user skill package."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SKILL_DIR = SKILLS_DIR / "using-apps-like-a-user"
SKILL_PATH = SKILL_DIR / "SKILL.md"
SCRIPTS_DIR = SKILL_DIR / "scripts"
REFERENCES = [SKILL_DIR / "references" / "surfaces.md", SKILL_DIR / "references" / "safety.md"]
PRESSURE_SCENARIOS = [SKILL_DIR / f"test-pressure-{n}.md" for n in (1, 2, 3)]
TECH_SPEC_PATH = REPO_ROOT / "docs" / "quirk" / "specs" / "2026-10-11-using-apps-like-a-user" / "tech.md"
README_PATH = REPO_ROOT / "README.md"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DESCRIPTION_RE = re.compile(r'^description:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
TRIGGER_PHRASES = ("dogfood", "like a user", "try it in the app")


def _read_skill() -> str:
    return SKILL_PATH.read_text()


def _frontmatter_block(body: str) -> str:
    match = FRONTMATTER_RE.match(body)
    assert match is not None, "SKILL.md missing YAML frontmatter"
    return match.group(1)


def _description() -> str:
    match = DESCRIPTION_RE.search(_frontmatter_block(_read_skill()))
    assert match is not None, "frontmatter missing 'description'"
    return match.group(1)


def _act_statuses() -> List[str]:
    """Statuses listed in the `act` output SCHEMA of the tech spec."""
    spec = TECH_SPEC_PATH.read_text()
    block = re.search(r"SCHEMA: `act` output\n```\n(.*?)\n```", spec, re.DOTALL)
    assert block is not None, "act output SCHEMA not found in tech.md"
    line = re.search(r"^status:\s*(.+)$", block.group(1), re.MULTILINE)
    assert line is not None, "act output SCHEMA has no status line"
    statuses = re.findall(r'"([A-Z_]+)"', line.group(1))
    assert len(statuses) >= 12, f"expected the full status list, parsed {statuses}"
    return statuses


def test_frontmatter_name_matches_directory() -> None:
    fm_body = _frontmatter_block(_read_skill())
    name_match = re.search(r"^name:\s*(.+?)\s*$", fm_body, re.MULTILINE)
    assert name_match, "frontmatter missing 'name'"
    assert name_match.group(1) == SKILL_DIR.name


def test_description_length_and_trigger_phrases() -> None:
    description = _description()
    assert 50 <= len(description) <= 1024, f"description length {len(description)} out of range [50, 1024]"
    assert description.startswith("Use when"), "description must start with 'Use when'"
    for phrase in TRIGGER_PHRASES:
        assert phrase in description, f"description missing trigger phrase {phrase!r}"
    for surface in ("web", "Electron", "native macOS"):
        assert surface in description, f"description does not name the {surface!r} surface"


def test_skill_stays_under_line_budget() -> None:
    assert len(_read_skill().splitlines()) <= 400


def test_reference_and_pressure_files_exist_and_are_nonempty() -> None:
    for path in REFERENCES + PRESSURE_SCENARIOS:
        assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"
        assert path.read_text().strip(), f"empty {path.relative_to(REPO_ROOT)}"


def test_skill_links_to_both_references() -> None:
    body = _read_skill()
    for path in REFERENCES:
        assert f"references/{path.name}" in body, f"SKILL.md never links references/{path.name}"


def test_relative_links_resolve_within_skill_directory() -> None:
    skill_root = SKILL_DIR.resolve()
    documents = [SKILL_PATH] + REFERENCES
    assert LINK_RE.findall(_read_skill()), "SKILL.md must contain at least one markdown link"
    for document in documents:
        for target in LINK_RE.findall(document.read_text()):
            where = f"{document.name}: {target!r}"
            assert target == target.strip(), f"link target is not bare: {where}"
            assert not target.startswith(("@", "/", "#")), f"link target is not relative: {where}"
            assert "://" not in target, f"link target is not relative: {where}"
            path_text, _, _fragment = target.partition("#")
            assert path_text, f"link has no relative file target: {where}"
            resolved = (document.parent / path_text).resolve()
            try:
                resolved.relative_to(skill_root)
            except ValueError:
                raise AssertionError(f"link escapes the skill directory: {where}") from None
            assert resolved.is_file(), f"relative link does not resolve: {where}"


def test_every_named_script_exists() -> None:
    names = set()
    for document in [SKILL_PATH] + REFERENCES:
        names |= set(re.findall(r"scripts/([A-Za-z_]+\.py)", document.read_text()))
    assert "likeuser.py" in names, "SKILL.md never names likeuser.py"
    for name in names:
        assert (SCRIPTS_DIR / name).is_file(), f"scripts/{name} does not exist"


def test_skill_invokes_the_guard_script_through_the_plugin_root() -> None:
    body = _read_skill()
    assert 'python3 "${CLAUDE_PLUGIN_ROOT}/skills/using-apps-like-a-user/scripts/likeuser.py"' in body


def test_skill_documents_every_exit_code() -> None:
    body = _read_skill()
    for code in range(6):
        assert re.search(rf"^\| {code} \|", body, re.MULTILINE), f"exit code {code} undocumented"


def test_skill_mentions_every_act_status() -> None:
    body = _read_skill()
    for status in _act_statuses():
        assert status in body, f"SKILL.md never mentions act status {status}"


def test_skill_never_tells_the_agent_to_bypass_the_guard() -> None:
    body = _read_skill()
    assert "orca computer click" not in body
    assert "cua-driver call" not in body
    assert "playwright-cli click" not in body


def test_readme_skill_count_matches_skill_directories() -> None:
    readme = README_PATH.read_text()
    skill_dirs = [path for path in SKILLS_DIR.iterdir() if (path / "SKILL.md").exists()]
    match = re.search(r"\*\*(\d+) skills\*\*", readme)
    assert match, "README missing skill count in What ships section"
    assert int(match.group(1)) == len(skill_dirs), (
        f"README claims {match.group(1)} skills, found {len(skill_dirs)} skills/*/SKILL.md directories"
    )


def test_readme_what_ships_bullet_mentions_the_skill() -> None:
    bullet = next(line for line in README_PATH.read_text().splitlines() if "**26 skills**" in line)
    assert "like a user" in bullet.lower()
