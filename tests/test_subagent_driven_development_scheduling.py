"""Load-bearing rules of SDD's per-task scheduler, pinned by the step that owns each one.

The scheduler replaced level-by-level waves. These assertions guard the parts a paraphrase could
silently drop: readiness that ignores unrelated work, checkpoints that hold merges rather than
dispatches, the explicit rework rule, and the journal fields that let a run be replayed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD_DIR = REPO_ROOT / "skills" / "subagent-driven-development"
SDD_SKILL = SDD_DIR / "SKILL.md"
WRITING_PLANS = REPO_ROOT / "skills" / "writing-plans" / "SKILL.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def sdd_step(number: int) -> str:
    body = SDD_SKILL.read_text()
    start = re.search(rf"^### Step {number}: ", body, re.MULTILINE)
    assert start is not None, f"SDD SKILL.md has no Step {number}"
    end = re.search(r"^### ", body[start.end():], re.MULTILINE)
    return body[start.start():start.end() + end.start()] if end else body[start.start():]


def test_readiness_depends_only_on_a_tasks_own_inputs() -> None:
    schedule = flat(sdd_step(4))
    assert "There are no waves and no barriers" in schedule
    assert ("ready** when every dependency and ordering predecessor is merged into `GREEN_HEAD` "
            "and its `scope.files` are disjoint from every held lock") in schedule
    assert "Readiness ignores checkpoints" in schedule


def test_scope_lock_lasts_until_the_merge_is_green() -> None:
    schedule = flat(sdd_step(4))
    assert "from dispatch until its merge is inside `GREEN_HEAD`" in schedule
    assert "no two concurrent tasks share a file" in schedule
    assert 'no "small overlap" exemption' in schedule


def test_fixers_supersede_rather_than_wait_on_a_held_lock() -> None:
    schedule = flat(sdd_step(4))
    assert "A fixer never waits on a task's lock" in schedule
    assert "could deadlock" in schedule
    assert "only change that may merge onto a red tip" in schedule


def test_width_cap_counts_dispatches_and_is_journaled() -> None:
    schedule = flat(sdd_step(4))
    assert "`WIDTH_CAP`" in schedule and "4–6" in schedule
    assert "holds a lock and a branch but no slot" in schedule
    assert "`cap-bind`" in schedule
    assert "longest downstream path" in schedule and "plan task order" in schedule


def test_the_pass_merges_then_gates_then_dispatches() -> None:
    schedule = sdd_step(4)
    pass_text = schedule[schedule.index("#### The scheduling pass"):schedule.index("#### Checkpoints")]
    order = [pass_text.index(token) for token in
             ("Step 6's audit", "mergeable", "merge gate (Step 7)", "Open a checkpoint",
              "Dispatch every ready task")]
    assert order == sorted(order)
    assert "`GATE_BASE_<g>`" in pass_text
    assert "never forks" not in pass_text and "keep forking from the last green head" in flat(pass_text)


def test_checkpoints_cover_windows_and_hold_only_dependents() -> None:
    checkpoints = flat(sdd_step(4).split("#### Checkpoints", 1)[1])
    for token in ("**Subject.**", "dependency edge", "never opens a checkpoint and never holds anything",
                  "`CHECKPOINT_BASE_<k>..CHECKPOINT_HEAD_<k>`", "`CHECKPOINT_CAP`",
                  "holds the *merge*, never the dispatch", "own `$WORK` directory"):
        assert token in checkpoints
    assert "does not wait for the full suite" in flat(sdd_step(4))


def test_rework_rule_is_explicit_and_bounded() -> None:
    checkpoints = flat(sdd_step(4).split("#### Checkpoints", 1)[1])
    for token in ("**Rework rule.**", "**superseded**", "touches a path in the dependent's `scope.files`",
                  "status code", "return 409", "**merge as-is**", "discarded, not patched",
                  "fresh attempt, not the task's one retry", "revised contract excerpt", "`tech.md`",
                  "Rule as early as you can", "any supersede ruling wins",
                  "not ready again until the checkpoint that superseded it has closed"):
        assert token in checkpoints
    assert "**Why dependents proceed, but only one level deep.**" in checkpoints
    assert "the longer of build time and review time instead of their sum" in checkpoints


def test_overlap_only_edges_become_ordering_edges_not_deletions() -> None:
    decompose = flat(sdd_step(3))
    assert "**ordering edge**" in decompose
    assert "does not hold the target's merge behind the source's checkpoint" in decompose
    assert "A cycle is a plan defect" in decompose
    assert "wave(source)" not in SDD_SKILL.read_text()


def test_each_task_gets_its_own_worktree_from_green_head() -> None:
    dispatch = flat(sdd_step(5))
    assert "one worktree and branch per task, forked from `GREEN_HEAD`" in dispatch
    assert "`TASK_BASE_<n>`" in dispatch and "TASK_HEAD_<n>" in dispatch
    assert "Create worktrees serially" in dispatch


def test_claude_binding_backgrounds_from_the_main_session_with_a_liveness_bound() -> None:
    dispatch = flat(sdd_step(5))
    assert "`run_in_background: true`, one call per task" in dispatch
    assert "orchestrator must be the main session" in dispatch
    assert "older than 30 minutes" in dispatch
    assert "fall back to the foreground mode" in dispatch


def test_commit_must_equal_the_audited_and_accepted_tree() -> None:
    audit = flat(sdd_step(6))
    order = [audit.index(token) for token in
             ("**1. HEAD-check.**", "**2. Scope audit.**", "**3. Acceptance.**", "**4. Commit.**",
              "**5. Merge.**")]
    assert order == sorted(order)
    assert "must equal WORKTREE_TREE_<n>" in audit
    assert "`INTEGRATION_HEAD`" in audit
    assert "git merge --no-ff --no-edit" in audit
    assert "**A conflict means the precondition was violated**" in audit
    assert "every returned attempt, including one reported as `BLOCKED` or `FAILED`" in audit


def test_checkpoint_review_targets_its_window() -> None:
    review = sdd_step(8)
    assert '"$CHECKPOINT_BASE_<k>" "$CHECKPOINT_HEAD_<k>"' in review
    assert '`"$CHECKPOINT_BASE_<k>..$CHECKPOINT_HEAD_<k>"` at a checkpoint' in review
    assert "close the checkpoint (Step 4)" in flat(review)


def test_journal_can_replay_what_ran_when() -> None:
    preflight = flat(sdd_step(1))
    assert "append-only event log" in preflight and "timestamped" in preflight
    for token in ("`dispatch` / `return`", "`TASK_BASE_<n>`", "`TASK_HEAD_<n>`", "`WORKTREE_TREE_<n>`",
                  "`TASK_COMMIT_<n>`", "`INTEGRATION_HEAD`", "`GATE_BASE_<g>`", "`GREEN_HEAD`",
                  "`CHECKPOINT_BASE_<k>`", "`CHECKPOINT_HEAD_<k>`", "`supersede`", "`cap-bind`"):
        assert token in preflight


@pytest.mark.parametrize("path", [
    SDD_SKILL,
    SDD_DIR / "assets" / "implementer-prompt.md",
    SDD_DIR / "assets" / "fixer-prompt.md",
    WRITING_PLANS,
    REPO_ROOT / "skills" / "writing-plans" / "plan-document-reviewer-prompt.md",
])
def test_no_wave_scheduling_vocabulary_survives(path: Path) -> None:
    body = path.read_text()
    for stale in ("WAVE_BASE", "CHAIN_SNAPSHOT", "wave gate", "wave-gate", "wave-end", "mid-chain",
                  "mid-wave", "same wave", "successor wave", "compute waves", "computing waves",
                  "wave width", "first wave", "per wave", "each wave", "this wave", "the wave's",
                  "last wave", "single-wave"):
        assert stale not in body, f"{path.name} still says {stale!r}"


def test_writing_plans_prices_dependencies_against_checkpoint_holds() -> None:
    independence = flat(WRITING_PLANS.read_text().split("## Task Independence", 1)[1]
                        .split("## Plan Document Header", 1)[0])
    assert "dispatch each task the moment its own dependencies merge" in independence
    assert "A dependency costs more than ordering" in independence
    economics = flat(WRITING_PLANS.read_text().split("### Task-Boundary Granularity Economics", 1)[1]
                     .split("## Bite-Sized", 1)[0])
    assert "start as soon as that half merges" in economics
