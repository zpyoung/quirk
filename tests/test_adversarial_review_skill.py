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
    assert "`Agent` path" in body


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
    assert "--stage tiebreak" in step[:900]


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


def test_the_documented_pipeline_files_chain_together() -> None:
    """The written commands drifted into a pipeline that could not run: `claims` read a
    file promote never wrote, and `gate` read the pre-merge findings."""
    body = SKILL_PATH.read_text()
    steps = body[body.index("## Data flow"):body.index("## Depth")]
    # These three are collected from a model dispatch rather than a shell redirect.
    dispatched = {"findings.json", "refute.json", "tiebreak.json"}
    for name in dispatched:
        assert name in steps, f"{name} is consumed but never named as a dispatch target"
    produced = set(re.findall(r'> "\$WORK/([a-z]+\.json)"', steps)) | dispatched
    consumed = set(re.findall(r'--(?:findings|judgments|model|prepass|gate|resolve) '
                              r'"\$WORK/([a-z]+\.json)"', steps))
    assert consumed <= produced, (
        f"these steps read files no earlier step writes: {sorted(consumed - produced)}"
    )
    assert "merged.json" in produced and "merged.json" in consumed


def test_the_gate_is_fed_merge_output_not_raw_promote_output() -> None:
    body = SKILL_PATH.read_text()
    gate_step = body[body.index("**7. Evidence gate.**"):body.index("**8. Tiebreak.**")]
    assert '--findings "$WORK/merged.json"' in gate_step


def test_the_skill_does_not_claim_the_chain_proves_a_dispatch() -> None:
    """Nothing here observes a dispatch; the chain orders stages and binds files. The
    earlier "shape is the provenance" framing claimed more than the code can support."""
    for path in (SKILL_PATH, ASSETS_DIR / "composition-contract.md"):
        body = path.read_text()
        assert "shape is the provenance" not in body.lower()
        assert "not the same as unforgeability" in body or "does not authenticate content" in body


def test_sdd_does_not_overstate_what_the_verdict_proves() -> None:
    body = (REPO_ROOT / "skills/subagent-driven-development/SKILL.md").read_text()
    assert "not proof the dispatches happened" in body


# --- the prompts must produce what the script accepts -------------------------------
#
# The seam these guard is the one no unit test reaches: a reviewer copies the shape the
# prompt shows it, and the script either takes it or refuses the whole dispatch. A real
# run lost six findings here — the prompt told the reviewer to prove an absence with a
# `command` item, and `command` rejects the empty output an absence has by definition.

def _ar_module():
    import importlib.machinery
    import importlib.util

    spec = importlib.util.spec_from_loader(
        "ar", importlib.machinery.SourceFileLoader(
            "ar", str(SKILL_DIR / "scripts" / "adversarial-review"))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _example_findings() -> list:
    """The JSON array the promote prompt shows the reviewer, parsed as a reviewer would
    copy it: comments stripped, since the prompt annotates its example."""
    import json

    text = (ASSETS_DIR / "promote-prompt.md").read_text()
    blocks = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert blocks, "promote-prompt.md shows no ```json output example"
    for block in blocks:
        stripped = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and parsed:
            return parsed
    pytest.fail("no parseable findings array in promote-prompt.md")


def test_the_promote_examples_pass_the_scripts_own_validator() -> None:
    """A prompt whose example the validator rejects costs the caller a whole dispatch,
    and the reviewer is blamed for what the asset told it to do."""
    ar = _ar_module()
    for index, finding in enumerate(_example_findings()):
        ar.validate_finding(finding, index)


def test_the_promote_prompt_names_every_evidence_kind_the_script_accepts() -> None:
    """A kind the reviewer is never shown is a kind it will not emit — and it will reach
    for a wrong one that the validator refuses."""
    ar = _ar_module()
    prompt = (ASSETS_DIR / "promote-prompt.md").read_text()
    for kind in ar.EVIDENCE_REQUIRED_FIELDS:
        assert f"`{kind}`" in prompt, f"promote-prompt.md never names evidence kind {kind}"


def test_the_promote_prompt_does_not_route_absence_claims_through_command() -> None:
    """The exact regression: `prove the absence with a separate `command` item`."""
    prompt = (ASSETS_DIR / "promote-prompt.md").read_text()
    assert not re.search(r"absence with a separate `command`", prompt)
    assert re.search(r"absence.{0,80}`absence`", prompt, re.DOTALL)


def _json_array(asset: str) -> list:
    import json

    text = (ASSETS_DIR / asset).read_text()
    for block in re.findall(r"```json\n(.*?)```", text, re.DOTALL):
        try:
            parsed = json.loads(re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and parsed:
            return parsed
    pytest.fail(f"no parseable JSON array in {asset}")


@pytest.mark.parametrize("asset,stage", [
    ("refute-prompt.md", "refute"),
    ("tiebreak-prompt.md", "tiebreak"),
])
def test_the_judgment_examples_survive_the_merge_validator(tmp_path, asset, stage) -> None:
    """The `absence` bug was a prompt promising a shape the script refuses. These two
    assets have judgment examples with the same exposure and had no equivalent test."""
    import json
    import subprocess
    import sys

    judgments = _json_array(asset)
    # `merge` rules on what it was given, so the staged findings have to be the ones the
    # example judges — and for tiebreak they have to be contested, which is its mandate.
    disposition = "contested" if stage == "tiebreak" else "standing"
    findings = [{
        "id": j["id"], "severity": "HIGH", "confidence": "HIGH", "category": "correctness",
        "claim": f"claim {j['id']}", "remediation": "fix",
        "evidence": [{"kind": "command", "command": "pytest -q", "output": "1 failed"}],
        "patch": None, "stage": "refute", "disposition": disposition,
    } for j in judgments]
    chain = {"run_id": "0" * 16, "artifact_hash": "a" * 64, "predecessor": "0" * 64,
             "step": "claims" if stage == "refute" else "merge"}
    if stage == "tiebreak":
        # The refute stage it adjudicates is named on the chain link, not the envelope.
        chain["stage"] = "refute"
    envelope = {"findings": findings, "chain": chain}
    if stage == "tiebreak":
        envelope["stage"] = "refute"
        envelope["judged"] = len(findings)

    findings_file = tmp_path / "f.json"
    findings_file.write_text(json.dumps(envelope))
    judgments_file = tmp_path / "j.json"
    judgments_file.write_text(json.dumps(judgments))
    proc = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "adversarial-review"), "merge",
         "--findings", str(findings_file), "--judgments", str(judgments_file),
         "--stage", stage],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"{asset}'s own example is refused by `merge --stage {stage}`: {proc.stderr}"
    )


# --- the decision tables must keep up with what the gate emits ----------------------
#
# Every defect this skill's own review rounds rated most serious was the same shape: the
# caller-facing contract promising something the code no longer did, or staying silent
# about something it had started doing. A field that bounds what a verdict covers is
# useless if the tables a caller gates on never mention it.

CALLER_FACING = (
    SKILL_PATH,
    ASSETS_DIR / "composition-contract.md",
)

DECISION_BLOCK = "Distinguishing a clean review from a crashed one"


def _scope_bounding_fields() -> tuple:
    """Read the set from the script instead of restating it.

    A second copy is a second thing to forget when a field joins the set — which is how
    `limitations` and `questions` stayed out of the decision tables while a guard that
    was supposed to catch exactly that reported green.
    """
    return _ar_module().SCOPE_BOUNDING_FIELDS


def _fenced_block_after(text: str, heading: str) -> str:
    """The first fenced block below a heading, and nothing else.

    Slicing a character window instead let prose *after* the fence satisfy the check: a
    table with no rows for a field passed as long as some later sentence named it.
    """
    start = text.index(heading)
    fence = text.index("```", start)
    return text[fence + 3:text.index("```", fence + 3)]


def test_the_scope_bounding_set_is_not_silently_narrowed() -> None:
    """The constant is the contract these guards enforce; an empty or truncated one
    would make every assertion below pass by covering nothing."""
    fields = _scope_bounding_fields()
    assert len(fields) >= 5, f"scope-bounding set shrank to {fields}"
    for expected in ("contested_count", "unreviewed_paths", "advisory_count",
                     "limitations", "questions"):
        assert expected in fields, f"{expected} dropped out of the scope-bounding set"


@pytest.mark.parametrize("doc", CALLER_FACING, ids=lambda p: p.name)
def test_scope_bounding_fields_appear_in_the_caller_facing_docs(doc) -> None:
    text = doc.read_text()
    for field in _scope_bounding_fields():
        assert field in text, (
            f"{doc.name} never mentions `{field}`, so a caller reading it cannot know "
            f"the verdict's scope is bounded by it"
        )


def test_every_scope_bounding_field_has_its_own_decision_row() -> None:
    """The table a caller gates on, and a row is what it must have — not a mention.

    Presence anywhere in the document is what the earlier version of this guard checked,
    and a doc that named a field only to tell the reader to ignore it satisfied it. The
    same "presence is not content" trap the evidence validator names.
    """
    contract = (ASSETS_DIR / "composition-contract.md").read_text()
    table = _fenced_block_after(contract, DECISION_BLOCK)
    rows = [line for line in table.splitlines() if "->" in line]
    assert rows, "the clean-versus-crashed block has no decision rows at all"
    for field in _scope_bounding_fields():
        owning = [line for line in table.splitlines() if field in line]
        assert owning, (
            f"`{field}` narrows what a PASS covers but has no row in the "
            f"clean-versus-crashed decision block"
        )
        # The row has to be the one that *decides* something, not a continuation line
        # of some other row's prose.
        index = table.splitlines().index(owning[0])
        window = table.splitlines()[index:index + 2]
        assert any("->" in line for line in window), (
            f"`{field}` appears in the block but not on a line that decides anything"
        )


def test_the_worktree_promise_is_scoped_to_capture_time() -> None:
    """`WORKTREE` used to claim it covered *all* uncommitted work. Since the artifact is
    fixed at capture, that is now true only as of `resolve`, and a caller told otherwise
    would read a `PASS` as covering files no stage ever saw."""
    skill = SKILL_PATH.read_text()
    assert "covers **all** uncommitted work" not in skill
    assert re.search(r"WORKTREE` covers all uncommitted work \*\*as of this moment\*\*", skill)


# --- the specs must describe the contract the script implements ---------------------
#
# All three findings from the PR review were this shape: a doc asserting behaviour the
# code does not have. The logic spec is the design record the implementation is read
# against, so drift there is not cosmetic — a caller trusting it plans around a
# guarantee that does not exist.

SPEC_DIR = REPO_ROOT / "docs" / "quirk" / "specs" / "2026-07-27-adversarial-review"


def test_the_logic_spec_names_the_author_families_the_script_accepts() -> None:
    """The spec claimed there was no unknown-family case and that a wrong guess degrades
    safely. The script rejects anything outside a closed set with exit 2, precisely
    because the independence guarantee turns on one string comparison."""
    logic = (SPEC_DIR / "logic.md").read_text()
    for family in _ar_module().AUTHOR_FAMILIES:
        assert f"`{family}`" in logic, f"logic.md never names the `{family}` author family"
    assert "no \"unknown\" case" not in logic, (
        "logic.md still claims unknown families degrade safely; they are exit 2"
    )


def test_the_logic_spec_does_not_claim_the_gate_moves_severity() -> None:
    """`apply_evidence_gate` caps confidence and leaves severity alone — the two are
    independent axes and proof speaks only to likelihood. A spec saying an unproven
    finding is 'downgraded' reads as a severity change and contradicts its own later text."""
    logic = (SPEC_DIR / "logic.md").read_text()
    assert "lacking a reproduction is downgraded" not in logic
    assert re.search(r"confidence capped at `LOW`.{0,40}severity does not move", logic,
                     re.DOTALL | re.IGNORECASE)


def test_the_slash_command_adds_no_target_semantics_of_its_own() -> None:
    """It declares itself a thin entry point. It had also invented a default — reviewing
    the branch diff against main — that the script does not implement."""
    command = COMMAND_PATH.read_text()
    assert "branch diff against main" not in command, (
        "the command reintroduced a default target the script does not implement"
    )
    assert "WORKTREE" in command


def _section(text: str, heading: str, next_heading: str) -> str:
    """Keep protocol assertions local to the section that governs the decision."""
    return text[text.index(heading):text.index(next_heading, text.index(heading) + len(heading))]


@pytest.mark.parametrize("path", [
    PROFILES_DIR / "code-diff.md",
    ASSETS_DIR / "promote-prompt.md",
    ASSETS_DIR / "refute-prompt.md",
], ids=lambda p: p.name)
def test_passing_prepass_forbids_full_suite_reproductions(path: Path) -> None:
    body = path.read_text().lower()
    assert re.search(r"(?:pre-?pass|prepass).{0,160}(?:status.{0,12})?[`\" ]pass", body, re.DOTALL)
    assert re.search(r"(?:must not|never|do not) run the full test suite", body)
    assert re.search(r"(?:narrowest|narrow|single).{0,100}(?:test|reproduction)", body, re.DOTALL)
    assert "targeted" in body


@pytest.mark.parametrize("asset,source,field", [
    ("refute-prompt.md", "claims.json", "diff_excerpts"),
    ("tiebreak-prompt.md", "gate.json", "contested_excerpts"),
])
def test_later_stages_stage_evidence_excerpts(asset: str, source: str, field: str) -> None:
    body = (ASSETS_DIR / asset).read_text()
    instructions = body[:body.index("---")]
    artifact = _section(body, "## The artifact", "## The ")
    for section in (instructions, artifact):
        assert source in section and field in section
        assert "{{ARTIFACT}}" in section
    assert "±15" in artifact
    assert "excluded_paths" in artifact
    assert "full files" in artifact.lower() and "`read`" in artifact
    if field == "contested_excerpts":
        assert "counter_evidence" in artifact


def test_composition_contract_exposes_shared_inputs_and_scope_outputs() -> None:
    body = (ASSETS_DIR / "composition-contract.md").read_text()
    inputs = _section(body, "## Input", "## Output")
    for field in ("id_prefix?", "resolve_file?", "prepass_file?", "reuse_check?", "include_all?"):
        assert field in _fenced_block_after(inputs, "## Input")
    assert "### Closure Round Verification" in inputs and "id_prefix" in inputs
    outputs = _section(body, "## Output", "## Depth")
    for field in ("excluded_paths[]", "contested_excerpts?", "prepass.tree_hash",
                  "prepass.checks[].reused", "duration_ms"):
        assert field in outputs
    table = _fenced_block_after(body, DECISION_BLOCK)
    assert re.search(r"^any exit\s+\+ excluded_paths nonempty\s+->", table, re.MULTILINE)


def test_review_data_flow_documents_hygiene_verified_reuse_and_shared_round_inputs() -> None:
    body = " ".join(_section(SKILL_PATH.read_text(), "## Data flow", "## Verdict contract").split())
    for path in ("vendor/", "node_modules/", "dist/", "build/", ".venv/", "__pycache__/",
                 "*.min.js", "*.min.css", "*.bundle.js", "*.lock", "pnpm-lock.yaml",
                 "package-lock.json", "yarn.lock", "Cargo.lock", "poetry.lock", "uv.lock"):
        assert path in body
    for field in ("--include-all", "excluded_paths", "full_worktree_hash", "--reuse-check",
                  "HEAD^{tree}", "clean_tree", "exit_code", "observed_artifact_hash",
                  '"reused": true', "duration_ms", "manifest.prepass"):
        assert field in body
    assert "command coverage" in body and "once" in body
    assert "C" in body and "S" in body and "X" in body and "--id-prefix" in body
    assert "diff_excerpts" in body and "contested_excerpts" in body


def test_review_dispatch_caps_stage_effort_without_rewriting_model_identity() -> None:
    dispatch = _section(SKILL_PATH.read_text(), "## Dispatch", "## Composing this skill")
    for token in ("promote", "refute", "tiebreak", "high", "medium", "low < medium < high",
                  "--thinking", "ceiling", "manifest.reviewer.thinking", "model.json"):
        assert token in dispatch
    assert "lower" in dispatch and "`Agent`" in dispatch


def test_closure_protocol_keeps_accepted_findings_out_of_dismissals() -> None:
    rounds = _section(SKILL_PATH.read_text(), "## Running rounds", "## Red Flags")
    for token in ("LAST_ROUND_HEAD..HEAD", "id_prefix", "### Closure Round Verification",
                  "dismissed[]", "original", '"id": null'):
        assert token in rounds
    assert re.search(r"never.{0,30}dismissed", rounds, re.IGNORECASE | re.DOTALL)
    for prefix in ("C1", "S1", "X1"):
        assert prefix in rounds
    profile = (PROFILES_DIR / "code-diff.md").read_text().split("## Attack surface")[0]
    for token in ("LAST_ROUND_HEAD..HEAD", "### Closure Round Verification", "original",
                  '"id": null'):
        assert token in profile
    output = " ".join((ASSETS_DIR / "promote-prompt.md").read_text().split("## Output")[1].split())
    assert "### Closure Round Verification" in output
    assert "original" in output and "fixed" in output and "lens prefix" in output


def test_sdd_preflight_probes_before_one_consolidated_card() -> None:
    preflight = " ".join(sdd_step(1).split())
    for token in ("git rev-parse --abbrev-ref HEAD", "git status --porcelain", "pi-watch --check",
                  "codex", "gemini", "terra", "opus", "sonnet", "flash", "scratch",
                  "single consolidated Tier 1", "orca ask", "AskUserQuestion",
                  "backend_pairing", "dirty_tree_action", "env_readiness", "task-fallback",
                  "stash_untracked", "commit_existing", "abort",
                  "git stash push --include-untracked", "reduced independence"):
        assert token in preflight
    assert preflight.index("pi-watch --check") < preflight.index("backend_pairing")
    assert preflight.index("git status --porcelain") < preflight.index("backend_pairing")
    for pair in ("claude-task + codex (Recommended)", "claude-task + gemini",
                 "claude-task + terra", "pi-codex + opus", "pi-codex + gemini"):
        assert pair in preflight
    assert "tree_test_cache" in preflight and "ROUND_<r>_HEAD" in preflight
    assert "LAST_ROUND_HEAD" in preflight


def test_sdd_cache_requires_verified_tree_identity_and_command() -> None:
    body = SDD_SKILL.read_text()
    audit = " ".join(_section(body, "### Step 6:", "### Step 7:").split())
    for token in ("worktree_tree_identity", "WAVE_BASE", "HEAD^{tree}",
                  "sha256(canonical_json(CHAIN_SNAPSHOT_AFTER))", "acceptance_cmd",
                  "tree_test_cache", "orchestrator", "prepass", "a claim never overrides a run"):
        assert token in audit
    assert "worker's text claim alone" in audit and "once" in audit
    gates = sdd_step(7)
    for token in ('((HEAD^{tree}, "clean"), full_suite_cmd)', "tree_test_cache",
                  "$WORK/gate-check.json", "ReusedCheckInput", "tree_hash",
                  "clean_tree: true", "duration_ms"):
        assert token in gates


def test_sdd_wave_gate_automatically_fixes_only_replaced_test_contracts() -> None:
    gates = " ".join(sdd_step(7).split())
    for token in ("unowned test file", "scope.files", "pre-wave behavior", "intentionally replaced",
                  "automatically dispatch", "wave-gate fixer", 'effort: "high"', "Step 6",
                  "Tier 2", "--timeout-ms 600000", "contract conflict"):
        assert token in gates


def test_sdd_logs_slow_wave_gate_and_prepass_advisory_without_config_edits() -> None:
    gates, review = sdd_step(7), sdd_step(8)
    for section in (gates, review):
        for token in ("300", "run journal", "final summary", "pytest-xdist", "-n auto",
                      "BrowserContext"):
            assert token in section
    assert "checks[].duration_ms > 300000" in review
    assert "without mutating" in gates


def test_sdd_review_uses_stage_sized_depth_and_one_shared_prepass() -> None:
    review = sdd_step(8)
    checkpoint = _section(review, "**Checkpoint**", "**Final loop**")
    assert "--depth standard" in checkpoint
    final = review[review.index("**Final loop**"):]
    assert "Final Round 1" in final and "--depth deep" in final and "RUN_BASE..HEAD" in final
    for token in ("resolve.json", "prepass.json", "once per round", '--check-cmd "$FULL_SUITE_CMD"',
                  '--reuse-check "$WORK/gate-check.json"', "exits 2", "without `--reuse-check`"):
        assert token in review
    assert re.search(r"all three.{0,100}share", review, re.IGNORECASE | re.DOTALL)
    assert re.search(r"\| any exit \+ `excluded_paths` non-empty \|", review)


def test_sdd_closure_rounds_filter_each_lens_and_bound_discovery_fallback() -> None:
    review = sdd_step(8)
    for token in ("Final Rounds 2–5", "ROUND_<r>_HEAD", "ROUND_<r-1>_HEAD", "LAST_ROUND_HEAD..HEAD",
                  "closure mode", "### Closure Round Verification", "id_prefix", "C*", "S*", "X*",
                  "scope.files", "dismissed[]", "full discovery", "outside"):
        assert token in review
    assert re.search(r"Never.{0,60}prior accepted findings.{0,30}dismissed", review, re.DOTALL)


def test_sdd_adjudication_is_nonblocking_and_escalates_repeated_failed_fixes() -> None:
    adjudication = sdd_step(9)
    for token in ("Tier 3", "GateResult", "run journal", "ID | Lens | Effective Severity | Ruling",
                  "One-line Reason", "without asking a blocking question", 'effort: "high"',
                  "veto", "next batch", "in-flight", "r >= 3", "r-2", "r-1", "category",
                  "contract seam", "root-cause design task", "Tier 2", "--timeout-ms 600000"):
        assert token in adjudication
    exit_step = sdd_step(10)
    assert "Tier 1" in exit_step and "blocked handoff" in exit_step
    assert "CRITICAL" in exit_step and "HIGH" in exit_step and "five rounds" in exit_step


def test_sdd_three_tier_human_gates_handle_statuses_and_pending_cards() -> None:
    failure = _section(SDD_SKILL.read_text(), "## Failure routing", "## Red Flags")
    for token in ("Three-tier human gate", "ORCA_PANE_KEY", "ORCA_WORKSPACE_ID", "orca ask",
                  "AskUserQuestion", "unavailable", "Tier 1", "Tier 2", "Tier 3",
                  "--timeout-ms 600000", "default", "declined", "partial", "timed_out",
                  "assumed, timed_out", "orca ask wait", "0 wait"):
        assert token in failure
    assert "never end a turn" in failure.lower()
    never = SDD_SKILL.read_text().split("**Never:**")[1]
    assert "start wave dispatch on a dirty tree" in never
    assert "orca ask" in never and "pending" in never
    assert "worker's text claim alone" in never


def test_sdd_role_effort_pins_and_task_dispatch_are_explicit() -> None:
    roles = _section(SDD_SKILL.read_text(), "## Roles", "## The Process")
    for role, effort in (("Implementer", "high"), ("Promote", "high"), ("Refute", "high"),
                         ("Fixer", "high"), ("Tiebreak", "medium"), ("Explore", "low")):
        assert re.search(rf"\| {role}[^\n]*\b{effort}\b", roles)
    assert "model.json" in roles and "ceiling" in roles
    assert 'effort: "high"' in sdd_step(5)
    assert "--thinking high" in sdd_step(5)


@pytest.mark.parametrize("asset", ["implementer-prompt.md", "fixer-prompt.md"])
def test_workers_run_only_owned_acceptance_not_the_full_repository_suite(asset: str) -> None:
    body = (SDD_DIR / "assets" / asset).read_text()
    acceptance = " ".join(_section(body, "## Acceptance", "## Method").split())
    for token in ("{{ACCEPTANCE}}", "owned test files", "exactly as written",
                  "never run the full repository test suite", "Step 7"):
        assert token in acceptance


def test_writing_plans_assigns_single_owner_tests_and_task_scoped_acceptance() -> None:
    body = (REPO_ROOT / "skills/writing-plans/SKILL.md").read_text()
    for heading, end in (("## File Structure", "## Bite-Sized Task Granularity"),
                         ("## Task Independence", "## Plan Document Header")):
        section = _section(body, heading, end)
        assert "single-owner" in section and "test file" in section
        assert "scope.files" in section and "serialized component chain" in section
    structure = _section(body, "## Task Structure", "## No Vagueness")
    assert "owned test files" in structure and "full-suite" in structure and "Step 7" in structure
    review = _section(body, "## Self-Review", "## After the plan")
    for item, end in (("**6.", "**7."), ("**8.", "If you find issues")):
        section = " ".join(_section(review, item, end).split())
        assert "owned test files" in section or "single owner" in section
    after = body[body.index("## After the plan"):]
    for token in ("standalone", "quirk:executing-plans", "plan-document-reviewer-prompt.md",
                  "quirk:subagent-driven-development", "inline decomposition",
                  "skips plan-document review", "quirk:adversarial-review"):
        assert token in after
