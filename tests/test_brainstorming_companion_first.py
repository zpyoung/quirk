"""Pins the companion-first rewrite of quirk:brainstorming.

The skill runs a brainstorm inside the visual companion's app mode and keeps the
terminal flow only for `--terminal` and the fallback.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAINSTORMING = REPO_ROOT / "skills" / "brainstorming"
SKILL_PATH = BRAINSTORMING / "SKILL.md"
GUIDE_PATH = BRAINSTORMING / "visual-companion.md"
COVERAGE_PATH = BRAINSTORMING / "references" / "essential-coverage.md"

APP_MODE_SUBCOMMANDS = ["step", "next", "status", "decide", "say"]


def skill() -> str:
    return SKILL_PATH.read_text()


def guide() -> str:
    return GUIDE_PATH.read_text()


def test_terminal_opt_out_is_documented() -> None:
    assert "--terminal" in skill(), "SKILL.md does not document the --terminal opt-out"


def test_checklist_step_3_starts_the_companion() -> None:
    assert "Start the companion" in skill(), "checklist step 3 is not 'Start the companion'"


def test_app_mode_subcommands_are_named() -> None:
    body = skill()
    missing = [name for name in APP_MODE_SUBCOMMANDS if f"`{name}`" not in body]
    assert not missing, f"SKILL.md does not name app-mode subcommands: {missing}"


def test_consent_offer_is_gone() -> None:
    body = skill()
    assert "Offer visual companion" not in body, "the companion consent offer step survives"
    assert "own message, no other content" not in body, "the consent-offer message rule survives"


def test_guide_drops_per_question_browser_rule() -> None:
    assert "Decide per-question" not in guide(), "visual-companion.md still has the per-question rule"


def test_guide_is_the_app_mode_protocol() -> None:
    body = guide()
    assert "--app" in body, "visual-companion.md does not show `start --app`"
    assert "next" in body, "visual-companion.md does not document `next`"


def test_fast_track_is_never_a_companion_question() -> None:
    body = COVERAGE_PATH.read_text().lower()
    assert "companion question" in body, "essential-coverage.md lacks the companion fast-track rule"
    assert "chat" in body, "essential-coverage.md does not say a chat steer triggers the fast-track"
    assert '"assumed"' in body or "`assumed`" in body, \
        "essential-coverage.md does not say fast-tracked decisions are sent as status assumed"


def test_sdd_hand_off_keeps_the_tab() -> None:
    for name, body in (("SKILL.md", skill()), ("visual-companion.md", guide())):
        assert "Starting SDD in this tab" in body, f"{name} lacks the SDD hand-off message"
