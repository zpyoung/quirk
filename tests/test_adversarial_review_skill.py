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


def test_code_diff_profile_keeps_silence_distinct_from_a_clean_review() -> None:
    """The distinction SDD's loop depends on. A literal token carried it once; the
    token was not JSON and nothing normalised it, so a clean review read as a crash."""
    body = (PROFILES_DIR / "code-diff.md").read_text()
    assert "Silence is not the same as `[]`" in body
    assert "failed dispatch" in body


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


def test_command_routes_to_the_skill_and_passes_arguments() -> None:
    body = COMMAND_PATH.read_text()
    assert "quirk:adversarial-review" in body
    assert "$ARGUMENTS" in body


def test_command_passes_every_flag_through() -> None:
    body = COMMAND_PATH.read_text()
    for flag in ("--profile", "--lens", "--depth", "--model"):
        assert flag in body, f"command does not pass through {flag}"


def test_command_does_not_duplicate_the_skills_protocol() -> None:
    """The command is an entry point, not a second home for the rules.

    An earlier version restated the exit-code table, the never-a-pass rule, and the
    kill-rate signal — four rules that then had to be edited in two files at once.
    SKILL.md owns the protocol; this guards the split that keeps them from drifting.
    """
    body = COMMAND_PATH.read_text()
    skill = SKILL_PATH.read_text()
    for rule in ("NOT_REVIEWABLE", "suppressed_count", "CRITICAL_ISSUES", "NEEDS_FIXES"):
        assert rule in skill, f"SKILL.md should own {rule}"
        assert rule not in body, (
            f"{rule} is duplicated in the command; it belongs only in SKILL.md"
        )
    assert not re.search(r"exit \d", body), "exit-code handling belongs in SKILL.md"


def test_command_stays_a_thin_entry_point() -> None:
    """Matches commands/explore.md in shape — routing, not procedure."""
    body = COMMAND_PATH.read_text()
    assert len(body.splitlines()) < 25, "command has grown into a second protocol document"


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


# ============ clean-path reachability ========================================

def test_the_summary_names_the_manifest_as_the_source_of_reviewer_fields() -> None:
    """GateResult carries verdict/findings/contested/suppressed/suppressed_count/depth
    and no reviewer identity at all. Telling the operator to derive the reviewer line
    from it, while forbidding a hand-written summary, described an impossible step."""
    body = SKILL_PATH.read_text()
    output = body[body.index("## Output"):]
    assert "manifest" in output
    assert "independence" in output
    assert "`GateResult` carries none of the reviewer fields" in output


def test_gate_result_really_does_lack_the_reviewer_fields() -> None:
    """Guards the claim above against the script growing them later and the prose
    quietly becoming wrong in the other direction."""
    import ast

    script = (SKILL_DIR / "scripts" / "adversarial-review").read_text()
    fn = next(n for n in ast.walk(ast.parse(script))
              if isinstance(n, ast.FunctionDef) and n.name == "run_gate")
    assign = next(n for n in ast.walk(fn)
                  if isinstance(n, ast.Assign)
                  and isinstance(n.value, ast.Dict)
                  and any(getattr(t, "id", "") == "payload" for t in n.targets))
    assert isinstance(assign.value, ast.Dict)
    keys = {k.value for k in assign.value.keys if isinstance(k, ast.Constant)}
    assert not keys & {"reviewer", "alias", "independence", "profile"}


def test_unparseable_reviewer_output_has_a_stated_recovery() -> None:
    """The Dispatch section classified it as failed output but stated the retry ladder
    only for the empty case, leaving a defined failure with no defined response."""
    dispatch = SKILL_PATH.read_text()
    dispatch = dispatch[dispatch.index("## Dispatch"):]
    assert "does not parse takes the same path" in dispatch
    assert "never hand-repair" in dispatch


def test_code_diff_profile_covers_a_whole_file_target() -> None:
    """`code-diff` is the catch-all, so a source-file path lands here with no diff to
    scope against; without this case the staged profile said to review nothing."""
    body = (PROFILES_DIR / "code-diff.md").read_text()
    assert "single source file" in body
    assert "whole file is the artifact" in body


def test_composition_contract_matches_the_script_on_unknown_families() -> None:
    """The caller-facing contract promised a graceful degrade where the script exits 2."""
    body = (ASSETS_DIR / "composition-contract.md").read_text()
    assert "exit 2" in body
    assert "`other`" in body
    assert "There is no unknown case" not in body


# ============ prompt/gate contract agreement =================================

@pytest.mark.parametrize("profile", PROFILES)
def test_a_clean_review_is_instructed_as_json_not_a_bare_token(profile: str) -> None:
    """Profiles told a clean reviewer to emit `NO_FINDINGS` while the enclosing prompt
    required `[]`. The token is not JSON and nothing ever normalized it, so a reviewer
    that followed the profile had its clean review read as a crashed dispatch and
    retried — the PASS path was unreachable through the staged instructions."""
    body = (PROFILES_DIR / f"{profile}.md").read_text()
    assert "NO_FINDINGS" not in body
    nothing = body[body.index("## When you find nothing"):]
    assert "[]" in nothing


def test_no_asset_promises_a_normalization_that_does_not_exist() -> None:
    script = (SKILL_DIR / "scripts" / "adversarial-review").read_text()
    assert "NO_FINDINGS" not in script
    for asset in ASSETS_DIR.glob("*.md"):
        assert "NO_FINDINGS" not in asset.read_text(), asset.name


@pytest.mark.parametrize("profile", ("plan", "spec-design", "prose-claim"))
def test_a_missing_citation_is_not_evidenced_by_pairing_it_with_its_own_target(
    profile: str,
) -> None:
    """These profiles instructed `file-line` evidence whose `ref` was the *cited* path
    and whose `quote` was the sentence doing the citing. The gate opens `ref` and looks
    for `quote` inside it, so the pairing falsified itself — and did so precisely when
    the cited path was missing, which is when the finding is true."""
    body = (PROFILES_DIR / f"{profile}.md").read_text()
    row = next(line for line in body.splitlines()
               if "citing sentence" in line and line.startswith("|"))
    assert "`file-line`" not in row
    assert "`quote` + `command`" in row


def test_the_promote_prompt_states_which_file_a_ref_names() -> None:
    body = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert "never the file the quote talks about" in body


def test_a_tiebreak_can_move_the_severity_it_was_asked_to_adjudicate() -> None:
    """Tiebreak may rule on severity, so its ruling has to be able to carry one."""
    body = (ASSETS_DIR / "tiebreak-prompt.md").read_text()
    assert "set `severity`" in body
    step = SKILL_PATH.read_text()
    step = step[step.index("**8. Tiebreak.**"):]
    assert "merge --stage tiebreak" in step[:700]


def test_the_declared_target_kinds_are_the_ones_the_script_can_produce() -> None:
    """tech.md declared an `inline` kind that classify_target cannot return, and
    prose-claim.md offered "a single claim submitted for testing" as a use case with
    no input mode behind it."""
    import ast

    script = (SKILL_DIR / "scripts" / "adversarial-review").read_text()
    fn = next(n for n in ast.walk(ast.parse(script))
              if isinstance(n, ast.FunctionDef) and n.name == "classify_target")
    produced = {n.value.value for n in ast.walk(fn)
                if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)}
    spec = (REPO_ROOT / "docs/quirk/specs/2026-07-27-adversarial-review/tech.md").read_text()
    declared = set(re.findall(r'"([a-z-]+)"',
                              next(line for line in spec.splitlines()
                                   if line.startswith("target_kind"))))
    assert declared == produced, f"spec declares {declared}, script produces {produced}"


def test_the_no_write_invariant_is_qualified_by_the_checks_it_runs() -> None:
    """`prepass` shells out to discovered test runners, which drop caches into the tree."""
    body = SKILL_PATH.read_text()
    assert "Nothing writes\nto the repository." not in body
    assert "as read-only as the commands themselves" in body


# ============ severity calibration and self-limiting review =======================

PROSE_PROFILES = ("spec-design", "plan", "prose-claim")


@pytest.mark.parametrize("profile", PROFILES)
def test_every_profile_defines_a_severity_rubric(profile: str) -> None:
    """Only code-diff had one. A reviewer working on prose had no anchor for what
    HIGH meant, and returned 5-of-5 HIGH on a round where about two were."""
    body = (PROFILES_DIR / f"{profile}.md").read_text()
    for tier in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        assert f"`{tier}`" in body, f"{profile} has no {tier} tier"


@pytest.mark.parametrize("profile", PROSE_PROFILES)
def test_every_prose_profile_states_what_is_not_a_finding(profile: str) -> None:
    """The floor is the point. Without it, "this sentence could be clearer" is a
    defect, and a prose review has an unbounded supply of those."""
    body = (PROFILES_DIR / f"{profile}.md").read_text()
    assert "**Not a finding at all:**" in body


@pytest.mark.parametrize("profile", PROSE_PROFILES)
def test_every_prose_profile_requires_a_witness_above_low(profile: str) -> None:
    """A grep proving a word is absent does not prove the behavior is unspecified."""
    body = (PROFILES_DIR / f"{profile}.md").read_text()
    assert "witness" in body
    assert "`MEDIUM` or higher must name three things" in body


def test_promote_is_told_its_severity_is_a_proposal() -> None:
    body = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert "Your severity is a **proposal**" in body


def test_promote_offers_limitation_and_question_as_first_class_outcomes() -> None:
    body = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert '`"limitation"`' in body and '`"question"`' in body
    assert "neither counts toward the verdict" in body


def test_refute_can_grade_severity_and_is_told_not_to_contest_it() -> None:
    body = (ASSETS_DIR / "refute-prompt.md").read_text()
    assert "Set `severity` to what the profile's rubric says" in body
    assert "A severity disagreement is no longer a reason to contest." in body


def test_refute_is_given_the_rubric_without_being_given_the_criteria() -> None:
    """The criteria stay withheld by design — whether a finding matters to this
    project is the caller's call. The rubric is a different question and rides in
    on the profile the stage already receives."""
    body = (ASSETS_DIR / "refute-prompt.md").read_text()
    assert "The criteria are **not** staged here" in body
    assert "{{PROFILE}}`, and it carries the severity rubric" in body


def test_pass_is_documented_as_a_bar_not_a_clean_bill_of_health() -> None:
    body = SKILL_PATH.read_text()
    assert "does not mean \"clean\"" in body
    assert "no unresolved finding met the blocking bar" in body.lower()


def test_the_skill_gives_callers_a_contract_for_running_rounds() -> None:
    """It disclaimed round counts and exit conditions while giving the caller nothing
    to implement them with, so the obvious loop — re-run discovery over a target that
    just changed — was the one that does not terminate."""
    body = SKILL_PATH.read_text()
    section = body[body.index("## Running rounds"):body.index("## Red Flags")]
    assert 'Do not target "review until clean."' in section
    for state in ("fixed", "still-open", "regression", "out-of-campaign-scope"):
        assert state in section
    assert "new, independently confirmed blockers" in section


def test_the_closure_pass_still_reviews_the_fix_delta() -> None:
    """Freezing the target outright would hide fix-induced regressions — which is
    exactly how the NO_FINDINGS defect surfaced."""
    body = SKILL_PATH.read_text()
    section = body[body.index("## Running rounds"):body.index("## Red Flags")]
    assert "Fixes introduce defects" in section


def test_the_composition_contract_points_callers_at_the_round_protocol() -> None:
    body = (ASSETS_DIR / "composition-contract.md").read_text()
    assert "Running rounds" in body


def test_the_composition_contract_output_matches_what_the_gate_emits() -> None:
    """The caller-facing schema is the thing most likely to drift silently, because
    nothing consumes it mechanically."""
    body = (ASSETS_DIR / "composition-contract.md").read_text()
    for field in ("limitations[]", "questions[]", "blocking", "effective_severity",
                  "adjudicated_severity", "severity_histogram", "advisory_count"):
        assert field in body, f"contract does not document {field}"
    assert "surviving **severity** only" not in body


def test_the_two_claude_facing_docs_do_not_restate_each_other() -> None:
    """SKILL.md and composition-contract.md drifted apart once already: the verdict
    rule changed in the script and only SKILL.md was updated, leaving the contract
    describing behaviour the gate no longer had. Relocating the overlap fixed that
    instance; this keeps it from growing back. Single shared sentences are fine —
    consecutive runs mean a passage was copied rather than cross-referenced."""
    def substantive(line: str) -> bool:
        line = re.sub(r"\s+", " ", line).strip()
        return len(line) > 40 and not line.startswith(("|", "-", "*", "#", "```"))

    def normalise(path: Path) -> list[str]:
        return [re.sub(r"\s+", " ", l).strip() for l in path.read_text().splitlines()]

    skill = normalise(SKILL_PATH)
    contract = {l for l in normalise(ASSETS_DIR / "composition-contract.md") if substantive(l)}

    runs, current = [], []
    for index, line in enumerate(skill, start=1):
        if substantive(line) and line in contract:
            current.append(index)
        else:
            if len(current) >= 2:
                runs.append((current[0], current[-1]))
            current = []
    if len(current) >= 2:
        runs.append((current[0], current[-1]))

    assert not runs, (
        f"SKILL.md restates composition-contract.md at line ranges {runs} — "
        "cross-reference the canonical copy instead of duplicating it"
    )
