"""Structural assertions over the adversarial-review skill's prose surface.

These guard the things the script cannot: that the skill declares triggers it
will actually fire on, that every profile and stage asset the SKILL.md promises
exists, and that the parts migrated out of subagent-driven-development kept the
labels SDD's exit gate reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "adversarial-review"
SKILL_PATH = SKILL_DIR / "SKILL.md"
PROFILES_DIR = SKILL_DIR / "profiles"
ASSETS_DIR = SKILL_DIR / "assets"
COMMAND_PATH = REPO_ROOT / "commands" / "adversarial-review.md"

PROFILES = ("code-diff", "spec-design", "plan", "prose-claim")
STAGE_ASSETS = ("promote-prompt", "refute-prompt", "tiebreak-prompt")


def frontmatter(path: Path) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.DOTALL)
    assert match is not None, f"{path.name} missing YAML frontmatter"
    return match.group(1)


# --- SKILL.md ---------------------------------------------------------------------

def test_skill_has_frontmatter() -> None:
    fm = frontmatter(SKILL_PATH)
    assert re.search(r"^name:\s*adversarial-review\s*$", fm, re.MULTILINE)
    assert re.search(r"^description:\s*.{30,}$", fm, re.MULTILINE)


def test_skill_description_carries_trigger_phrases() -> None:
    """Never firing is the most common way a skill fails, so the triggers are asserted."""
    fm = frontmatter(SKILL_PATH)
    match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
    assert match is not None, "SKILL.md frontmatter has no description"
    description = match.group(1).lower()
    for trigger in ("adversarial", "review", "critique"):
        assert trigger in description, f"description missing trigger phrase: {trigger}"


def test_skill_documents_all_four_verdicts() -> None:
    body = SKILL_PATH.read_text()
    for verdict in ("PASS", "NEEDS_FIXES", "CRITICAL_ISSUES", "NOT_REVIEWABLE"):
        assert verdict in body


def test_skill_states_not_reviewable_is_not_a_pass() -> None:
    body = SKILL_PATH.read_text()
    assert re.search(r"NOT_REVIEWABLE`? is never a synonym for `?PASS", body)


def test_skill_states_the_independence_invariant() -> None:
    body = SKILL_PATH.read_text().lower()
    assert "never sees the author's reasoning" in body


def test_skill_derives_the_human_summary_from_gate_output() -> None:
    """The summary and the findings block must not be able to drift apart."""
    body = SKILL_PATH.read_text()
    assert "GateResult" in body
    assert re.search(r"[Dd]erive every line of it from", body)
    assert re.search(r"[Nn]ever author\w*[^.]*independently", body)


def test_skill_references_every_profile_and_asset() -> None:
    body = SKILL_PATH.read_text()
    for name in PROFILES:
        assert f"profiles/{name}.md" in body
    for name in STAGE_ASSETS:
        assert f"assets/{name}.md" in body
    assert "assets/composition-contract.md" in body


def test_skill_documents_both_dispatch_paths() -> None:
    body = SKILL_PATH.read_text()
    assert "pi-watch" in body
    assert "Task" in body


# --- profiles ---------------------------------------------------------------------

@pytest.mark.parametrize("name", PROFILES)
def test_profile_exists_and_declares_its_three_sections(name: str) -> None:
    body = (PROFILES_DIR / f"{name}.md").read_text()
    assert re.search(r"^##\s+Attack surface\s*$", body, re.MULTILINE)
    assert re.search(r"^##\s+Evidence rules\s*$", body, re.MULTILINE)
    assert re.search(r"^##\s+Pre-pass context\s*$", body, re.MULTILINE)


@pytest.mark.parametrize("name", PROFILES)
def test_profile_routes_unfalsifiable_claims_rather_than_inventing(name: str) -> None:
    body = (PROFILES_DIR / f"{name}.md").read_text()
    assert "unfalsifiable-claim" in body


def test_code_diff_profile_retains_sdd_severity_rubric() -> None:
    """SDD's exit gate reads these labels; re-tuning them changes when its loop ends."""
    body = (PROFILES_DIR / "code-diff.md").read_text()
    for tier, means in [
        ("CRITICAL", "Data loss, corruption, security hole, or a crash on a normal path."),
        ("HIGH", "Wrong behavior on a path a user will hit, or a contract in the spec not met."),
        ("MEDIUM", "Wrong behavior on an edge case, a missing error path, or a real maintainability trap."),
        ("LOW", "Style, naming, redundancy, a nit. Anything you would not block a merge for."),
    ]:
        assert f"`{tier}`" in body
        assert means in body, f"{tier} rubric wording drifted from SDD's"


def test_code_diff_profile_retains_location_and_evidence_requirement() -> None:
    body = (PROFILES_DIR / "code-diff.md").read_text()
    assert "**`LOCATION` and `EVIDENCE` are required.**" in body
    assert "will be dropped" in body


def test_code_diff_profile_retains_no_findings_token() -> None:
    body = (PROFILES_DIR / "code-diff.md").read_text()
    assert "NO_FINDINGS" in body
    assert "Silence is not the same as `NO_FINDINGS`" in body


def test_code_diff_profile_retains_all_three_lenses() -> None:
    body = (PROFILES_DIR / "code-diff.md").read_text()
    for lens in ("correctness / logic", "spec compliance", "security and failure modes"):
        assert lens in body


# --- stage assets -----------------------------------------------------------------

@pytest.mark.parametrize("name", STAGE_ASSETS)
def test_stage_asset_exists_and_fences_the_artifact_as_data(name: str) -> None:
    body = (ASSETS_DIR / f"{name}.md").read_text()
    assert "<<<ARTIFACT-BEGIN>>>" in body
    assert "<<<ARTIFACT-END>>>" in body
    assert "data under review" in body


@pytest.mark.parametrize("name", STAGE_ASSETS)
def test_stage_asset_states_the_read_only_constraint(name: str) -> None:
    body = (ASSETS_DIR / f"{name}.md").read_text().lower()
    assert "read-only" in body or "no** `bash`" in body


def test_refute_prompt_carries_the_kill_mandate() -> None:
    body = (ASSETS_DIR / "refute-prompt.md").read_text()
    assert "kill mandate" in body
    assert "assume each finding is\nfalse" in body or "assume each finding is false" in body


def test_refute_prompt_receives_claims_not_reasoning() -> None:
    body = (ASSETS_DIR / "refute-prompt.md").read_text()
    assert "{{CLAIMS}}" in body
    assert "fresh context" in body


def test_promote_prompt_withholds_author_reasoning() -> None:
    body = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert "author's reasoning" in body
    assert "{{CRITERIA}}" in body


def test_promote_prompt_carries_the_quick_mode_self_refute() -> None:
    """`quick` has no refute dispatch, so the self-refute has to live here."""
    body = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert "{{DEPTH}}" in body
    assert "quick" in body
    assert "suppressed" in body


def test_tiebreak_prompt_has_no_bash_grant() -> None:
    body = (ASSETS_DIR / "tiebreak-prompt.md").read_text()
    assert re.search(r"no\*?\*? `bash`", body), "tiebreak must state it holds no bash"


@pytest.mark.parametrize("name", STAGE_ASSETS + ("composition-contract",))
def test_no_asset_reinstates_the_inverse_sycophancy_posture(name: str) -> None:
    """`only critique` is the phrasing logic.md replaced; it manufactures findings."""
    body = (ASSETS_DIR / f"{name}.md").read_text()
    assert "only critique" not in body


def test_composition_contract_states_the_three_load_bearing_rules() -> None:
    body = (ASSETS_DIR / "composition-contract.md").read_text()
    assert re.search(r"`?NOT_REVIEWABLE`? is never a synonym for `?PASS", body)
    assert "verbatim" in body.lower() and "only author-supplied context" in body.lower()
    assert "read-only `bash`" in body


# --- slash command ----------------------------------------------------------------

def test_command_exists_with_description_frontmatter() -> None:
    fm = frontmatter(COMMAND_PATH)
    assert re.search(r"^description:\s*.{30,}$", fm, re.MULTILINE)
    assert "name:" not in fm, "commands take description-only frontmatter"


def test_command_resolves_the_script_through_plugin_root() -> None:
    body = COMMAND_PATH.read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/adversarial-review" in body
    assert "$ARGUMENTS" in body


def test_command_handles_every_gate_exit_code() -> None:
    body = COMMAND_PATH.read_text()
    for code in ("0", "1", "2", "3", "4"):
        assert re.search(rf"exit {code}\b", body), f"command does not handle exit {code}"


# --- SDD delegation (T8) ----------------------------------------------------------

SDD_DIR = REPO_ROOT / "skills" / "subagent-driven-development"
SDD_SKILL = SDD_DIR / "SKILL.md"


def sdd_step(number: int) -> str:
    """The text of one SDD step, so assertions cannot pass on a match elsewhere."""
    body = SDD_SKILL.read_text()
    start = re.search(rf"^### Step {number}: ", body, re.MULTILINE)
    assert start is not None, f"SDD SKILL.md has no Step {number}"
    end = re.search(r"^#{2,3} ", body[start.end():], re.MULTILINE)
    return body[start.start():start.end() + end.start()] if end else body[start.start():]


def test_sdd_step_8_delegates_to_adversarial_review() -> None:
    step = sdd_step(8)
    assert "adversarial-review" in step


def test_sdd_no_longer_dispatches_its_own_reviewer() -> None:
    """The inline pi-watch reviewer dispatch is what the delegation replaces."""
    assert "pi-watch --provider openai-codex" not in SDD_SKILL.read_text()


def test_sdd_step_8_passes_depth_explicitly() -> None:
    """Auto-selection reads size; a small wave diff would fall through to quick."""
    step = sdd_step(8)
    assert "depth" in step
    assert "explicit" in step.lower()


def test_sdd_step_8_stages_criteria_verbatim_and_withholds_reasoning() -> None:
    step = sdd_step(8)
    assert "verbatim" in step
    assert "reasoning" in step


def test_sdd_step_8_keeps_all_three_lenses_and_both_review_modes() -> None:
    """The delegation replaces how findings are produced, not the review's shape."""
    step = sdd_step(8)
    for lens in ("correctness / logic", "spec compliance", "security and failure modes"):
        assert lens in step
    assert "Checkpoint" in step and "Final loop" in step


def test_sdd_step_8_reexpresses_the_crashed_versus_clean_signal() -> None:
    step = sdd_step(8)
    assert "NOT_REVIEWABLE" in step
    assert re.search(r"exit 4", step)
    assert re.search(r"exit 2", step)
    assert "Retry once" in step or "retry once" in step


def test_sdd_step_8_discloses_the_wider_tool_grant() -> None:
    step = sdd_step(8)
    assert "bash" in step
    assert "composition-contract.md" in step


def test_sdd_step_9_consumes_structured_findings() -> None:
    step = sdd_step(9)
    assert "suppressed_count" in step
    assert "confidence" in step
    assert "independence" in step


def test_sdd_step_9_retains_its_own_adjudication_machinery() -> None:
    """SDD keeps ownership of everything the delegation was not supposed to move."""
    step = sdd_step(9)
    assert "effective severity" in step
    assert "connected components" in step
    assert "dismissed" in step
    assert "fixer-prompt.md" in step


def test_sdd_reviewer_prompt_is_now_a_delegation_pointer() -> None:
    body = (SDD_DIR / "assets" / "reviewer-prompt.md").read_text()
    assert "composition-contract.md" in body
    assert "profiles/code-diff.md" in body
    # The rubric moved; it must not be duplicated here, where it would drift.
    assert "Ship this and something breaks for real." not in body


def test_sdd_integration_list_names_the_skill() -> None:
    body = SDD_SKILL.read_text()
    assert "**quirk:adversarial-review**" in body
