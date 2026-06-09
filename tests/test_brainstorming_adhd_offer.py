from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "brainstorming" / "SKILL.md"


def test_skill_file_exists() -> None:
    assert SKILL_PATH.is_file(), "brainstorming SKILL.md not found"


def test_gray_area_discovery_offer_present() -> None:
    """The Gray Areas section offers adhd before surfacing areas (Step 0)."""
    body = SKILL_PATH.read_text()
    assert "### Step 0 — Offer adhd divergent discovery (optional)" in body, \
        "missing Step 0 adhd discovery offer heading"
    assert "Find gray areas" in body, "missing AskUserQuestion header for the offer"
    assert "Use the standard set (Recommended)" in body, \
        "missing recommended cheap-path option"
    assert "Run adhd first" in body, "missing adhd opt-in option"


def test_offer_uses_discovery_framing() -> None:
    """adhd is delegated to find ambiguities, not solutions."""
    body = SKILL_PATH.read_text()
    assert "latent ambiguous decisions" in body, \
        "missing discovery-framing instruction for the adhd delegation"


def test_offer_merges_and_labels() -> None:
    """adhd-surfaced areas merge into the multiSelect, labeled."""
    body = SKILL_PATH.read_text()
    assert "prefixing each adhd-surfaced entry with `adhd:`" in body, \
        "missing merge+label instruction for adhd-surfaced areas"
    assert "truly-trivial" in body or "truly trivial" in body, \
        "missing trivial-work suppression rule"


def test_checklist_step_4_reworded() -> None:
    """Checklist step 4 mentions the optional adhd pass."""
    body = SKILL_PATH.read_text()
    assert "optionally surface non-obvious areas via the `adhd` skill first" in body, \
        "checklist step 4 not reworded for the adhd pass"


def test_approaches_advisory_bullet_removed() -> None:
    """The old silent advisory bullet at the approaches step is gone."""
    body = SKILL_PATH.read_text()
    assert "consider using the `adhd` skill to surface non-obvious options" not in body, \
        "old approaches-step advisory adhd bullet still present"
