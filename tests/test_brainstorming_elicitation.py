"""Prose pins for the brainstorming skill's elicitation controller.

Spec: docs/quirk/specs/2026-09-14-brainstorming-elicitation/

These assertions pin the strings, not the prose. They prove the rules are
present in the skill; they do not prove the rules are followed once it loads.
That limit is recorded as a non-goal in the tech spec, not an oversight.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "brainstorming" / "SKILL.md"
COVERAGE_PATH = REPO_ROOT / "skills" / "brainstorming" / "references" / "essential-coverage.md"

BODY_LINE_BUDGET = 400

# The seven sites that carried the one-at-a-time framing before batching was
# extended. ":263" and ":319" both read "single-question dialogue", so one
# literal covers both. Absence-based on purpose: a count would let an eighth
# site hide, which is exactly how two sweeps missed :263.
STALE_CADENCE_LITERALS = (
    "ask questions one at a time to refine the idea",
    "one at a time, for anything not covered",
    "single-question dialogue",
    "Then ask any remaining clarifying questions one at a time",
    "Only one question per message",
    "**One question at a time**",
)

ESSENTIAL_ITEMS = (
    "Purpose",
    "Consumers",
    "Success criteria",
    "Hard constraints",
    "Scope boundary",
    "Primary behavior",
)


def skill() -> str:
    return SKILL_PATH.read_text()


def coverage() -> str:
    return COVERAGE_PATH.read_text()


# --- the reference file -------------------------------------------------


def test_reference_file_exists() -> None:
    assert COVERAGE_PATH.is_file(), "essential-coverage.md not found"


def test_essential_six_present() -> None:
    """All six Essential items are named in the reference file."""
    body = coverage()
    missing = [item for item in ESSENTIAL_ITEMS if item not in body]
    assert not missing, f"essential-coverage.md missing items: {missing}"


def test_essential_list_declared_original() -> None:
    """The list carries no borrowed evidence; the skill must say so."""
    body = coverage()
    assert "original" in body, "essential-coverage.md does not state the list is original"


def test_reference_file_is_linked_from_skill() -> None:
    """A reference nothing links to is a reference that never loads."""
    assert "references/essential-coverage.md" in skill(), \
        "SKILL.md does not link references/essential-coverage.md"


# --- the coverage gate --------------------------------------------------


def test_coverage_gate_is_a_checklist_step() -> None:
    body = skill()
    assert "Essential-coverage check" in body, "no coverage-gate checklist step"
    assert "12. **Transition to implementation**" in body, \
        "checklist not renumbered to 12 steps after inserting the gate"


def test_coverage_gate_in_flow_graph() -> None:
    """The gate must be visible in the diagram, not only the prose."""
    body = skill()
    assert "Essential-coverage\\ncheck" in body, "coverage gate missing from the digraph"


# --- the altitude rule --------------------------------------------------


def test_altitude_test_is_inline() -> None:
    """The test itself is always-in-effect, so it lives in the body."""
    assert "Would the answer change what the consumer observes, or only how it is built?" in skill(), \
        "the altitude test sentence is not inline in SKILL.md"


def test_altitude_is_consumer_relative() -> None:
    """Without this, the rule guts the API and CLI catalogs."""
    body = skill()
    assert "relative to" in body and "consumer" in body, \
        "altitude rule does not state that observable is consumer-relative"


def test_altitude_escape_clause() -> None:
    assert "is itself the user-facing decision" in skill(), \
        "missing the escape clause for implementation choices that ARE the decision"


def test_altitude_tie_breaker() -> None:
    """The ambiguous case needs a defined resolution, not a coin-flip."""
    assert "reframe the question in terms of what the consumer observes" in skill(), \
        "missing the reframe-or-route tie-breaker"


def test_build_only_questions_are_routed_not_dropped() -> None:
    assert "[tech-spec]" in skill(), \
        "build-only questions have no documented routing tag"


def test_catalog_altitude_cleanup() -> None:
    """auth-storage is build-only; auth-method is the observable question."""
    body = skill()
    assert "auth-storage" not in body, "build-only catalog entry auth-storage still present"
    assert "auth-method" in body, "auth-method replacement not present"


# --- ordering and research wiring ---------------------------------------


def test_ordering_rule_present() -> None:
    assert "forking" in skill().lower(), \
        "missing the most-forking-first ordering rule"


def test_research_findings_become_candidate_questions() -> None:
    """Bounded by construction: findings are candidates, not questions."""
    assert "candidate question" in skill().lower(), \
        "Result Integration does not route findings through candidate questions"


# --- batching -----------------------------------------------------------


def test_no_stale_cadence_instruction_survives() -> None:
    """Every one of the seven one-at-a-time sites is amended."""
    body = skill()
    stale = [lit for lit in STALE_CADENCE_LITERALS if lit in body]
    assert not stale, f"stale one-at-a-time instructions still present: {stale}"


# --- the fast-track -----------------------------------------------------


def test_fast_track_gated_on_essential_coverage() -> None:
    body = coverage().lower()
    assert "only once all six essential items are covered" in body, \
        "fast-track is not gated on Essential coverage"


def test_fast_track_is_never_a_question_option() -> None:
    """As an option it would be a delegation option, which is forbidden."""
    assert "never an option inside an `askuserquestion` call" in coverage().lower(), \
        "fast-track not excluded from AskUserQuestion option lists"


def test_fast_tracked_decisions_are_tagged() -> None:
    """An assumed decision must never read as an approved one."""
    assert "assumed — fast-tracked" in coverage(), \
        "missing the assumed — fast-tracked tag"


def test_delegation_versus_election_distinguished() -> None:
    """The skill may not OFFER to decide; the user may ELECT defaults."""
    body = skill()
    assert "may never offer to decide" in body, \
        "Checkpoint Rules does not forbid the skill offering to decide"
    assert "elect to accept stated defaults" in body, \
        "Checkpoint Rules does not permit the user electing stated defaults"


# --- budgets and invariants ---------------------------------------------


def test_body_within_line_budget() -> None:
    lines = len(SKILL_PATH.read_text().splitlines())
    assert lines <= BODY_LINE_BUDGET, f"SKILL.md is {lines} lines, over the {BODY_LINE_BUDGET} cap"


def test_cross_skill_section_names_preserved() -> None:
    """Guards the invariant in test_writing_specs_skill.py from this change."""
    body = skill()
    for section in ("Industry Insights", "Deferred Ideas"):
        assert section in body, f"SKILL.md lost the {section!r} section name"
