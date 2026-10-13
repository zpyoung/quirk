"""Guards that quirk carries no Agent Isles integration after the move to the writing-html-artifacts companion."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

SCANNED = ["skills", "bin", "tests", "README.md", ".gitignore"]
FORBIDDEN = re.compile(r"agent_isles|Agent Isles|agent-isles|<agent-(option|choice|proceed)")

REMOVED_PATHS = [
    "bin/agent_isles.py",
    "packs/quirk",
    "examples/agent-isles",
    "docs/agent-isles-artifacts.md",
    "tests/test_agent_isles_bridge.py",
    "tests/test_agent_isles_wait.py",
    "tests/test_agent_isles_pack.py",
]

COMPANION_GUIDES = [
    "skills/brainstorming/visual-companion.md",
    "skills/exploring-ideas/visual-companion.md",
]


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for entry in SCANNED:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file()
                and "node_modules" not in p.parts
                and "__pycache__" not in p.parts
                and p.resolve() != SELF
            )
    return files


def test_no_isles_mentions() -> None:
    offenders = []
    for path in _scanned_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if FORBIDDEN.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_agent_instructions_tag_is_not_an_island() -> None:
    assert not FORBIDDEN.search("<agent-instructions>")


def test_removed_paths_are_gone() -> None:
    assert [p for p in REMOVED_PATHS if (ROOT / p).exists()] == []


def test_companion_guides_are_host_neutral() -> None:
    for rel in COMPANION_GUIDES:
        assert "CLAUDE_PLUGIN_ROOT" not in (ROOT / rel).read_text(encoding="utf-8"), rel
