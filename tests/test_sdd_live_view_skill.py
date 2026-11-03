"""Pins the SDD live-view protocol doc and its wiring into the SDD skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDD = REPO_ROOT / "skills" / "subagent-driven-development"
SKILL_PATH = SDD / "SKILL.md"
LIVE_VIEW_PATH = SDD / "live-view.md"
COMPANION_REF = REPO_ROOT / "skills" / "writing-html-artifacts" / "references" / "companion.md"

PROTOCOL_TERMS = [
    "run-start",
    "report",
    "ask",
    "await",
    "answer",
    "next",
    "orca ask cancel",
    "sdd/<run_id>/<task id>",
    "--no-view",
]


def test_skill_points_to_live_view() -> None:
    body = SKILL_PATH.read_text()
    assert "live-view.md" in body, "SDD SKILL.md does not link live-view.md"
    assert "--no-view" in body, "SDD SKILL.md does not document --no-view"


def test_live_view_exists_and_is_short() -> None:
    assert LIVE_VIEW_PATH.exists(), "live-view.md is missing"
    lines = len(LIVE_VIEW_PATH.read_text().splitlines())
    assert lines <= 160, f"live-view.md is {lines} lines, limit is 160"


def test_live_view_names_the_protocol_terms() -> None:
    body = LIVE_VIEW_PATH.read_text()
    missing = [term for term in PROTOCOL_TERMS if term not in body]
    assert not missing, f"live-view.md does not name: {missing}"


def test_live_view_has_no_banned_words() -> None:
    body = LIVE_VIEW_PATH.read_text()
    assert "wave" not in body.lower(), "live-view.md uses the word 'wave'"
    assert "CLAUDE_PLUGIN_ROOT" not in body, "live-view.md uses CLAUDE_PLUGIN_ROOT"


def test_companion_reference_has_run_view() -> None:
    assert "\n## Run view" in COMPANION_REF.read_text(), "companion.md lacks a '## Run view' heading"
