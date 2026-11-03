"""Tests for the SDD run view fold (htmlkit.runfold).

``fold`` is pure, so most cases build plain dicts and compare the view. The fixture pairs under
``companion-app/fixtures/run`` are the contract the shell renders: ``fold(scenario) == view``.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import runfold  # noqa: E402
from htmlkit.runfold import STALE_AFTER_S, TAB_FALLBACK_AFTER_S, chains, fold, levels, run_view  # noqa: E402

FIXTURES = SKILL / "companion-app" / "fixtures" / "run"
SCENARIOS = FIXTURES / "scenarios"
VIEWS = FIXTURES / "views"

T0 = 1_000_000.0
STATUSES = ("queued", "running", "needs-you", "retrying", "passed", "failed", "skipped", "stopped", "missing")


# ---- builders --------------------------------------------------------------------------------


def task(tid, deps=(), order=(), **extra):
    return {"id": tid, "title": f"title {tid}", "deps": list(deps), "order_after": list(order), **extra}


def make_run(*tasks):
    return {
        "v": 1, "run_id": "r1", "repo": "/repo", "branch": "feature/x",
        "branch_pattern": "sdd/{run}/{task}", "base": "a" * 40, "tasks": list(tasks),
    }


class Reports:
    """Numbers reports in the order they are added, one second apart from T0 unless ``at`` is given."""

    def __init__(self):
        self.items: list[dict] = []

    def add(self, kind, at=None, **fields):
        n = len(self.items) + 1
        self.items.append({"n": n, "at": T0 + n if at is None else at, "kind": kind, **fields})
        return self

    def dispatch(self, tid, attempt=1, **kw):
        return self.add("dispatch", task=tid, attempt=attempt, branch=f"sdd/r1/{tid}",
                        worktree=f"/wt/{tid}", base="a" * 40, **kw)


def run_fold(run, reports=(), git=None, questions=(), actions=(), now=T0 + 100, **kw):
    reports = reports.items if isinstance(reports, Reports) else list(reports)
    return fold(run, reports, git, list(questions), list(actions), now, **kw)


def by_id(view):
    return {t["id"]: t for t in view["tasks"]}


def git_facts(observed_at, changed_at=None, **tasks):
    return {"observed_at": observed_at, "changed_at": changed_at if changed_at is not None else observed_at,
            "tasks": tasks}


def gt(commits=0, merged=False, files=(), worktree_present=True):
    return {"commits": commits, "merged": merged, "files": list(files), "worktree_present": worktree_present}


# ---- fixture pairs ---------------------------------------------------------------------------

REQUIRED = {
    "wave-start", "working", "needs-you", "retrying", "failed-blocked", "stop-pending", "review",
    "ended", "mismatch", "git-only", "missing", "stale", "answered-orca",
}


def _names(directory: Path) -> set[str]:
    return {p.stem for p in directory.glob("*.json")}


def test_every_scenario_has_a_view_and_every_view_a_scenario():
    scenarios, views = _names(SCENARIOS), _names(VIEWS)
    assert scenarios == views
    assert REQUIRED <= scenarios


@pytest.mark.parametrize("name", sorted(REQUIRED | _names(SCENARIOS)))
def test_fold_matches_fixture_view(name):
    scenario = json.loads((SCENARIOS / f"{name}.json").read_text(encoding="utf-8"))
    view = json.loads((VIEWS / f"{name}.json").read_text(encoding="utf-8"))
    assert fold(**scenario) == view


@pytest.mark.parametrize("name", sorted(_names(SCENARIOS)))
def test_fixture_files_are_pretty_printed_with_sorted_keys(name):
    for directory in (SCENARIOS, VIEWS):
        text = (directory / f"{name}.json").read_text(encoding="utf-8")
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


# ---- levels and chains -----------------------------------------------------------------------


def test_levels_count_dependency_edges_only_and_ordering_edges_do_not_raise_them():
    tasks = [
        task("A"),
        task("B", deps=["A"]),
        task("C", deps=["A"], order=["B"]),
        task("D", deps=["B", "C"]),
        task("E", order=["D"]),
    ]
    assert levels(tasks) == {"A": 1, "B": 2, "C": 2, "D": 3, "E": 1}


def test_chains_join_same_level_ordering_edges_in_plan_order_and_skip_cross_level_ones():
    tasks = [
        task("A"),
        task("B", deps=["A"]),
        task("C", deps=["A"], order=["B"]),
        task("D", deps=["B", "C"], order=["A"]),
        task("E", deps=["A"]),
        task("F", deps=["A"], order=["E"]),
        task("G", deps=["A"], order=["F"]),
    ]
    level = levels(tasks)
    assert chains(tasks, level) == [
        {"id": "c1", "tasks": ["B", "C"]},
        {"id": "c2", "tasks": ["E", "F", "G"]},
    ]


def test_fix_task_level_follows_the_highest_covered_task():
    reports = (
        Reports()
        .add("round-open", round="CP1", round_kind="checkpoint", title="Checkpoint 1", covers=["A", "B"])
        .add("task-add", task=task("F1", deps=["A"]), round="CP1")
    )
    view = run_fold(make_run(task("A"), task("B", deps=["A"])), reports)
    assert {t["id"]: t["level"] for t in view["tasks"]} == {"A": 1, "B": 2, "F1": 3}


# ---- status rules ----------------------------------------------------------------------------


def test_tasks_are_plan_order_then_fix_tasks_in_task_add_order_with_all_nine_counts():
    reports = (
        Reports()
        .add("task-add", task=task("F2"), round="CP1")
        .add("task-add", task=task("F1"), round="CP1")
    )
    view = run_fold(make_run(task("B"), task("A")), reports)
    assert [t["id"] for t in view["tasks"]] == ["B", "A", "F2", "F1"]
    assert view["counts"] == {s: 0 for s in STATUSES} | {"queued": 4}


def test_default_task_is_queued_attempt_zero_and_ready_without_deps():
    t = by_id(run_fold(make_run(task("A"), task("B", deps=["A"]))))
    assert (t["A"]["status"], t["A"]["attempt"], t["A"]["ready"]) == ("queued", 0, True)
    assert t["B"]["ready"] is False


def test_status_follows_the_latest_status_bearing_report():
    r = Reports().dispatch("A").add("return", task="A", attempt=1, word="DONE").add("commit", task="A", commit="c1")
    r.dispatch("B").add("fail", task="B", reason="bad")
    r.dispatch("C").add("skip", task="C", reason="not needed")
    r.dispatch("D").add("supersede", task="D", round="CP1", reason="redo")
    r.dispatch("E", attempt=2)
    r.dispatch("F").add("retry", task="F", attempt=2, reason="flaky")
    t = by_id(run_fold(make_run(*[task(x) for x in "ABCDEF"]), r))
    assert {k: v["status"] for k, v in t.items()} == {
        "A": "passed", "B": "failed", "C": "skipped", "D": "queued", "E": "retrying", "F": "retrying",
    }
    assert t["B"]["reason"] == "bad"
    assert t["F"]["attempt"] == 2


def test_a_stop_report_never_overrides_failed():
    r = Reports().dispatch("A").add("fail", task="A", reason="bad").add("stop", task="A", reason="chain", by="user")
    r.dispatch("B").add("stop", task="B", reason="chain", by="sdd")
    t = by_id(run_fold(make_run(task("A"), task("B")), r))
    assert t["A"]["status"] == "failed" and t["A"]["reason"] == "bad"
    assert t["B"]["status"] == "stopped" and t["B"]["reason"] == "chain"


def test_an_open_question_overrides_to_needs_you_until_answered():
    r = Reports().dispatch("A").add("question", question="q1", task="A")
    q = {"id": "q1", "task": "A", "prompt": "p", "options": [], "asked_at": T0 + 2, "state": "open"}
    view = run_fold(make_run(task("A")), r, questions=[q])
    assert by_id(view)["A"]["status"] == "needs-you" and by_id(view)["A"]["question"] == "q1"
    answered = q | {"state": "answered", "answer": {"question": "q1", "source": "tab", "pick": "x", "at": T0 + 3}}
    view = run_fold(make_run(task("A")), r, questions=[answered])
    assert by_id(view)["A"]["status"] == "running" and "question" not in by_id(view)["A"]
    assert view["questions"] == [answered]


def test_questions_are_listed_oldest_first():
    qs = [{"id": "late", "asked_at": 9.0, "state": "open"}, {"id": "early", "asked_at": 3.0, "state": "open"}]
    assert [q["id"] for q in run_fold(make_run(), questions=qs)["questions"]] == ["early", "late"]


def test_attempts_close_on_the_next_closing_report():
    r = (
        Reports()
        .dispatch("A", at=T0 + 1)
        .add("retry", at=T0 + 5, task="A", attempt=2, reason="flaky")
        .dispatch("A", attempt=2, at=T0 + 6)
        .add("commit", at=T0 + 9, task="A", commit="c")
    )
    a = by_id(run_fold(make_run(task("A")), r))["A"]
    assert a["attempts"] == [
        {"n": 1, "start": T0 + 1, "end": T0 + 5, "outcome": "failed"},
        {"n": 2, "start": T0 + 6, "end": T0 + 9, "outcome": "passed"},
    ]
    assert (a["started_at"], a["ended_at"]) == (T0 + 1, T0 + 9)


def test_a_running_attempt_stays_open_and_has_no_ended_at():
    a = by_id(run_fold(make_run(task("A")), Reports().dispatch("A", at=T0 + 1)))["A"]
    assert a["attempts"] == [{"n": 1, "start": T0 + 1}]
    assert "ended_at" not in a and a["started_at"] == T0 + 1


def test_files_come_from_git_else_zero():
    git = git_facts(T0 + 50, A=gt(files=["a.py", "b.py"]))
    t = by_id(run_fold(make_run(task("A"), task("B")), Reports().dispatch("A"), git))
    assert (t["A"]["files"], t["B"]["files"]) == (2, 0)


# ---- git-only and missing --------------------------------------------------------------------


def test_git_only_commit_is_passed_with_a_label_and_no_mismatch():
    git = git_facts(T0 + 50, A=gt(commits=1))
    a = by_id(run_fold(make_run(task("A")), git=git))["A"]
    assert a["status"] == "passed" and a["labels"] == ["seen in git, not reported"] and a["mismatch"] is None
    merged = by_id(run_fold(make_run(task("A")), git=git_facts(T0 + 50, A=gt(commits=0, merged=True))))["A"]
    assert merged["status"] == "passed"


def test_missing_when_deps_passed_and_every_other_task_on_the_level_is_terminal():
    r = Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B").add("commit", task="B", commit="c")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]), task("D", deps=["C"]))
    t = by_id(run_fold(run, r))
    assert t["C"]["status"] == "missing"
    assert t["D"]["status"] == "queued" and t["D"]["blocked_by"] == []


def test_not_missing_while_a_sibling_on_the_level_is_still_working():
    r = Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]))
    assert by_id(run_fold(run, r))["C"]["status"] == "queued"


def test_unheard_siblings_stay_queued_until_the_run_ends():
    r = Reports().dispatch("A").add("commit", task="A", commit="c")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]))
    t = by_id(run_fold(run, r))
    assert (t["B"]["status"], t["C"]["status"]) == ("queued", "queued")
    t = by_id(run_fold(run, r.add("run-end", outcome="blocked")))
    assert (t["B"]["status"], t["C"]["status"]) == ("missing", "missing")


def test_a_lone_dependency_free_task_is_not_missing_before_anything_has_run():
    assert by_id(run_fold(make_run(task("A"))))["A"]["status"] == "queued"


def test_missing_needs_passed_deps_a_lone_level_three_task_with_unpassed_deps_stays_queued():
    r = Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["B"]))
    c = by_id(run_fold(run, r))["C"]
    assert c["level"] == 3 and c["status"] == "queued"


def test_run_end_makes_an_unheard_ready_task_missing_even_with_siblings_working():
    r = Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B").add("run-end", outcome="blocked")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]), task("D", deps=["C"]))
    t = by_id(run_fold(run, r))
    assert t["C"]["status"] == "missing" and t["D"]["status"] == "queued"


def test_a_lone_ready_task_whose_deps_passed_stays_queued_until_the_run_ends():
    r = Reports().dispatch("A").add("commit", task="A", commit="c")
    run = make_run(task("A"), task("B", deps=["A"]))
    assert by_id(run_fold(run, r))["B"]["status"] == "queued"
    assert by_id(run_fold(run, r.add("run-end", outcome="blocked")))["B"]["status"] == "missing"


def test_level_mates_terminal_but_another_task_still_running_keeps_the_ready_task_queued():
    r = (Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B").add("commit", task="B", commit="c")
         .dispatch("X"))
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]), task("X"))
    t = by_id(run_fold(run, r))
    assert t["X"]["status"] == "running" and t["C"]["status"] == "queued"


def test_level_mates_terminal_and_nothing_running_makes_the_ready_task_missing():
    r = (Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B").add("commit", task="B", commit="c")
         .dispatch("X").add("commit", task="X", commit="c"))
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]), task("X"))
    assert by_id(run_fold(run, r))["C"]["status"] == "missing"


def test_an_open_question_on_another_task_keeps_the_ready_task_queued():
    r = Reports().dispatch("A").add("commit", task="A", commit="c").dispatch("B").add("commit", task="B", commit="c")
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["A"]), task("X"))
    q = {"id": "q1", "task": "X", "state": "open", "asked_at": T0}
    assert by_id(run_fold(run, r, questions=[q]))["C"]["status"] == "queued"


# ---- blocked by, downstream, edges -----------------------------------------------------------


def test_blocked_by_lists_nearest_failed_ancestors_and_clears_after_a_retry():
    run = make_run(task("A"), task("B", deps=["A"]), task("C", deps=["B"]), task("D", deps=["A", "B"]))
    r = Reports().dispatch("A").add("fail", task="A", reason="bad")
    t = by_id(run_fold(run, r))
    assert t["B"]["blocked_by"] == ["A"] and t["B"]["labels"] == ["blocked by A"]
    assert t["C"]["blocked_by"] == ["A"]
    assert t["D"]["blocked_by"] == ["A"]
    r.add("retry", task="A", attempt=2, reason="again")
    t = by_id(run_fold(run, r))
    assert all(t[x]["blocked_by"] == [] and t[x]["labels"] == [] for x in "BCD")


def test_one_blocked_by_label_per_failed_ancestor_in_plan_order():
    run = make_run(task("A"), task("B"), task("C", deps=["B", "A"]))
    r = Reports().dispatch("A").add("fail", task="A", reason="x").dispatch("B").add("fail", task="B", reason="y")
    c = by_id(run_fold(run, r))["C"]
    assert c["blocked_by"] == ["A", "B"] and c["labels"] == ["blocked by A", "blocked by B"]


def test_edges_and_downstream_cover_both_kinds_and_skip_passed_tasks():
    run = make_run(task("A"), task("B", deps=["A"]), task("C", order=["A"]), task("D", deps=["B"]))
    r = Reports().dispatch("B").add("commit", task="B", commit="c")
    view = run_fold(run, r)
    assert view["edges"] == [
        {"from": "A", "to": "B", "kind": "dep"},
        {"from": "A", "to": "C", "kind": "order"},
        {"from": "B", "to": "D", "kind": "dep"},
    ]
    assert by_id(view)["A"]["downstream"] == ["C", "D"]
    assert by_id(view)["B"]["downstream"] == ["D"]


# ---- mismatch and gaps -----------------------------------------------------------------------


def _passed(at):
    return Reports().dispatch("A", at=at - 5).add("commit", at=at, task="A", commit="c")


def test_mismatch_is_suppressed_when_git_was_observed_before_the_commit_report_and_shown_after():
    run = make_run(task("A"))
    before = run_fold(run, _passed(T0 + 50), git_facts(T0 + 49, A=gt(commits=0)))
    assert by_id(before)["A"]["mismatch"] is None
    after = run_fold(run, _passed(T0 + 50), git_facts(T0 + 51, A=gt(commits=0)))
    assert by_id(after)["A"]["mismatch"] == {
        "sdd": "passed", "git": "no commit", "text": "SDD says passed; git has no commit for A yet",
    }
    absent = run_fold(run, _passed(T0 + 50), git_facts(T0 + 51))
    assert by_id(absent)["A"]["mismatch"]["git"] == "no commit"
    agree = run_fold(run, _passed(T0 + 50), git_facts(T0 + 51, A=gt(commits=1)))
    assert by_id(agree)["A"]["mismatch"] is None


def test_no_mismatch_without_git_facts():
    assert by_id(run_fold(make_run(task("A")), _passed(T0 + 50)))["A"]["mismatch"] is None


def test_git_merged_while_sdd_says_anything_but_passed_is_a_mismatch_and_the_node_keeps_sdds_status():
    r = Reports().dispatch("A", at=T0 + 10)
    a = by_id(run_fold(make_run(task("A")), r, git_facts(T0 + 20, A=gt(commits=1, merged=True))))["A"]
    assert a["status"] == "running"
    assert a["mismatch"] == {"sdd": "running", "git": "merged", "text": "git shows A merged; SDD says running"}


def test_running_task_whose_worktree_is_gone_is_a_mismatch_only_after_a_later_poll():
    r = Reports().dispatch("A", at=T0 + 10)
    gone = gt(worktree_present=False)
    assert by_id(run_fold(make_run(task("A")), r, git_facts(T0 + 9, A=gone)))["A"]["mismatch"] is None
    a = by_id(run_fold(make_run(task("A")), r, git_facts(T0 + 11, A=gone)))["A"]
    assert a["mismatch"] == {
        "sdd": "running", "git": "no worktree", "text": "SDD says running; git has no worktree for A",
    }


def test_a_git_error_entry_raises_no_mismatch():
    git = git_facts(T0 + 51, A={**gt(), "error": "timeout"})
    assert by_id(run_fold(make_run(task("A")), _passed(T0 + 50), git))["A"]["mismatch"] is None


def test_dispatch_not_reported_for_a_commit_or_return_with_no_dispatch():
    r = Reports().add("commit", task="A", commit="c").add("return", task="B", attempt=1, word="DONE")
    r.dispatch("C").add("commit", task="C", commit="c")
    t = by_id(run_fold(make_run(task("A"), task("B"), task("C")), r))
    assert t["A"]["labels"] == ["dispatch not reported"]
    assert t["B"]["labels"] == ["dispatch not reported"]
    assert t["C"]["labels"] == []


# ---- rounds, fix tasks, holds ----------------------------------------------------------------


def _review_reports(reason, covers):
    return (
        Reports()
        .add("round-open", round="CP1", round_kind="checkpoint", title="Checkpoint 1", covers=covers)
        .add("round-close", round="CP1", outcome="fixes", findings=[
            {"id": "CP1-X1", "lens": "types", "severity": "high", "ruling": "accepted", "reason": reason,
             "fix_task": "F1"},
        ])
        .add("task-add", task=task("F1", title="fix"), round="CP1")
    )


def test_fix_task_label_names_the_one_covered_task_the_finding_is_about():
    run = make_run(task("T1"), task("T2"), task("T3"))
    view = run_fold(run, _review_reports("T3 type checks fail", ["T1", "T2", "T3"]))
    f1 = by_id(view)["F1"]
    assert f1["labels"] == ["fix T3 · CP1"] and f1["round"] == "CP1"
    assert view["rounds"] == [{
        "id": "CP1", "kind": "checkpoint", "title": "Checkpoint 1", "covers": ["T1", "T2", "T3"],
        "outcome": "fixes",
        "findings": [{"id": "CP1-X1", "lens": "types", "severity": "high", "ruling": "accepted",
                      "reason": "T3 type checks fail", "fix_task": "F1"}],
    }]


@pytest.mark.parametrize("reason", ["type checks fail", "T1 and T3 disagree", "T30 fails"])
def test_fix_task_label_drops_the_task_when_the_finding_names_none_or_several(reason):
    run = make_run(task("T1"), task("T2"), task("T3"), task("T30"))
    f1 = by_id(run_fold(run, _review_reports(reason, ["T1", "T2", "T3"])))["F1"]
    assert f1["labels"] == ["fix · CP1"]


def test_fix_task_label_ignores_a_finding_that_does_not_name_it_as_fix_task():
    reports = _review_reports("T3 fails", ["T3"])
    reports.items[1]["findings"][0]["fix_task"] = "other"
    assert by_id(run_fold(make_run(task("T3")), reports))["F1"]["labels"] == ["fix · CP1"]


def test_an_open_round_has_no_outcome_and_no_findings():
    r = Reports().add("round-open", round="CP1", round_kind="checkpoint", title="Checkpoint 1", covers=["A"])
    assert run_fold(make_run(task("A")), r)["rounds"] == [
        {"id": "CP1", "kind": "checkpoint", "title": "Checkpoint 1", "covers": ["A"], "findings": []},
    ]


def test_held_by_comes_from_the_latest_hold_and_clears_on_merge_supersede_or_stop():
    run = make_run(task("A"), task("B"), task("C"), task("D"))
    r = Reports()
    for tid in "ABCD":
        r.dispatch(tid).add("commit", task=tid, commit="c").add("hold", task=tid, round="CP1")
    r.add("merge", task="B", head="h")
    r.add("supersede", task="C", round="CP1", reason="redo")
    r.add("stop", task="D", reason="x", by="sdd")
    t = by_id(run_fold(run, r))
    assert t["A"]["held_by"] == "CP1" and t["A"]["labels"] == ["merge held by CP1"]
    assert all("held_by" not in t[x] and t[x]["labels"] == [] for x in "BCD")


# ---- pending actions -------------------------------------------------------------------------


def _event(seq, kind, tid, ts):
    return {"seq": seq, "type": kind, "timestamp": ts, "payload": {"task": tid}}


def test_pending_action_shows_until_an_action_report_or_a_later_stop_or_retry():
    run = make_run(task("A"), task("B"), task("C"))
    r = Reports().dispatch("A").add("fail", task="A", reason="x")
    r.dispatch("B").add("fail", task="B", reason="x").dispatch("C").add("fail", task="C", reason="x")
    actions = [_event(1, "run-retry", "A", T0 + 20), _event(2, "run-retry", "B", T0 + 20),
               _event(3, "run-stop", "C", T0 + 20)]
    t = by_id(run_fold(run, r, actions=actions))
    assert (t["A"]["pending_action"], t["B"]["pending_action"], t["C"]["pending_action"]) == ("retry", "retry", "stop")
    r.add("action", at=T0 + 30, seq=1, outcome="applied")
    r.add("retry", at=T0 + 31, task="B", attempt=2, reason="user")
    t = by_id(run_fold(run, r, actions=actions))
    assert "pending_action" not in t["A"] and "pending_action" not in t["B"]
    assert t["C"]["pending_action"] == "stop"


def test_an_old_stop_report_does_not_resolve_a_newer_action():
    run = make_run(task("A"))
    r = Reports().dispatch("A").add("stop", at=T0 + 5, task="A", reason="x", by="sdd")
    view = run_fold(run, r, actions=[_event(1, "run-stop", "A", T0 + 20)])
    assert by_id(view)["A"]["pending_action"] == "stop"


# ---- run level -------------------------------------------------------------------------------


def test_status_text_is_the_latest_status_report_and_ended_comes_only_from_run_end():
    r = Reports().add("status", text="Preflight").add("status", text="Gate 1")
    view = run_fold(make_run(task("A")), r)
    assert view["status_text"] == "Gate 1" and "ended" not in view
    r.add("run-end", at=T0 + 9, outcome="clean", next_step="pr")
    assert run_fold(make_run(task("A")), r)["ended"] == {"at": T0 + 9, "outcome": "clean", "next_step": "pr"}


def test_no_reports_means_no_status_text_start_or_staleness():
    view = run_fold(make_run(), now=T0 + 10_000)
    assert view["started_at"] is None and view["last_update_at"] is None and view["stale"] is None
    assert view["tasks"] == [] and view["edges"] == [] and view["chains"] == []
    assert "status_text" not in view


def test_last_update_is_the_later_of_the_last_report_and_git_changed_at():
    r = Reports().dispatch("A", at=T0 + 10)
    assert run_fold(make_run(task("A")), r)["last_update_at"] == T0 + 10
    git = git_facts(T0 + 40, changed_at=T0 + 30, A=gt())
    assert run_fold(make_run(task("A")), r, git)["last_update_at"] == T0 + 30
    assert run_fold(make_run(task("A")), r, git_facts(T0 + 40, changed_at=T0 + 5))["last_update_at"] == T0 + 10


def test_stale_boundary_exactly_the_threshold_is_not_stale_and_one_second_more_is():
    r = Reports().dispatch("A", at=T0)
    run = make_run(task("A"))
    at_limit = run_fold(run, r, now=T0 + STALE_AFTER_S)
    assert at_limit["stale"] is None
    over = run_fold(run, r, now=T0 + STALE_AFTER_S + 1)
    assert over["stale"] == {"since": STALE_AFTER_S + 1}
    assert (over["stale_after_s"], over["now"]) == (STALE_AFTER_S, T0 + STALE_AFTER_S + 1)
    assert by_id(over)["A"]["status"] == "running"
    custom = run_fold(run, r, now=T0 + 11, stale_after_s=10)
    assert custom["stale"] == {"since": 11} and custom["stale_after_s"] == 10


def test_a_run_with_run_end_is_never_stale():
    r = Reports().dispatch("A", at=T0).add("run-end", at=T0 + 1, outcome="clean")
    assert run_fold(make_run(task("A")), r, now=T0 + 99_999)["stale"] is None


def test_fold_is_deterministic():
    run = make_run(task("A"), task("B", deps=["A"], order=[]), task("C", deps=["A"], order=["B"]))
    r = Reports().dispatch("A").add("fail", task="A", reason="x").add("status", text="s")
    git = git_facts(T0 + 5, A=gt(commits=1, files=["x"]))
    first = json.dumps(run_fold(run, r, git, now=T0 + 500), sort_keys=True)
    second = json.dumps(run_fold(run, r, git, now=T0 + 500), sort_keys=True)
    assert first == second


def test_fold_does_not_mutate_its_input():
    run = make_run(task("A"), task("B", deps=["A"]))
    r = Reports().dispatch("A").add("task-add", task=task("F1"), round="CP1")
    qs = [{"id": "q", "task": "A", "asked_at": 1.0, "state": "open"}]
    before = json.dumps([run, r.items, qs], sort_keys=True)
    run_fold(run, r, git_facts(T0, A=gt()), qs)
    assert json.dumps([run, r.items, qs], sort_keys=True) == before


def test_config_constants():
    assert STALE_AFTER_S == 180 and TAB_FALLBACK_AFTER_S == 120


# ---- run_view --------------------------------------------------------------------------------


class _FakeStore:
    """Stands in for htmlkit.runstate.RunStore so run_view is testable without the real store."""

    run_doc: dict | None = None
    report_docs: list[dict] = []
    question_docs: list[dict] = []
    git_doc: dict | None = None

    def __init__(self, session):
        self.session = session

    def run(self):
        return self.run_doc

    def reports(self):
        return list(self.report_docs)

    def questions(self):
        return list(self.question_docs)

    def git_facts(self):
        return self.git_doc


@pytest.fixture
def fake_store(monkeypatch):
    module = types.ModuleType("htmlkit.runstate")
    store = type("FakeStore", (_FakeStore,), {})
    module.RunStore = store
    monkeypatch.setitem(sys.modules, "htmlkit.runstate", module)
    monkeypatch.delenv("QUIRK_RUN_STALE_AFTER_S", raising=False)
    return store


def test_run_view_is_none_without_a_registered_run(tmp_path, fake_store):
    assert run_view(tmp_path) is None


def test_run_view_folds_the_store_with_the_clock_and_run_stop_retry_events(tmp_path, fake_store, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    events = [
        {"seq": 1, "type": "chat", "timestamp": T0, "payload": {"text": "hi"}},
        {"seq": 2, "type": "run-stop", "timestamp": T0 + 2, "payload": {"task": "A"}},
    ]
    (state / "app-events").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    session = tmp_path
    fake_store.run_doc = make_run(task("A"))
    fake_store.report_docs = Reports().dispatch("A", at=T0).add("fail", at=T0 + 1, task="A", reason="x").items
    monkeypatch.setattr(runfold, "time", types.SimpleNamespace(time=lambda: T0 + 500))
    view = run_view(session)
    assert view["now"] == T0 + 500 and view["stale_after_s"] == STALE_AFTER_S
    a = by_id(view)["A"]
    assert a["status"] == "failed" and a["pending_action"] == "stop"
    assert view["stale"] == {"since": 499}


@pytest.mark.parametrize("value, expected", [("5", 5.0), ("0.5", 0.5), ("0", STALE_AFTER_S), ("-3", STALE_AFTER_S),
                                             ("soon", STALE_AFTER_S), ("", STALE_AFTER_S), ("nan", STALE_AFTER_S),
                                             ("inf", STALE_AFTER_S)])
def test_run_view_reads_the_stale_override_from_the_environment(tmp_path, fake_store, monkeypatch, value, expected):
    fake_store.run_doc = make_run(task("A"))
    fake_store.report_docs = Reports().dispatch("A", at=T0).items
    monkeypatch.setenv("QUIRK_RUN_STALE_AFTER_S", value)
    assert run_view(tmp_path)["stale_after_s"] == expected


def test_run_view_against_the_real_run_store(tmp_path, monkeypatch):
    runstate = pytest.importorskip("htmlkit.runstate")
    from htmlkit.appstate import AppState

    AppState(tmp_path).init()
    store = runstate.RunStore(tmp_path)
    assert run_view(tmp_path) is None
    repo = tmp_path / "repo"
    repo.mkdir()
    run = make_run(task("A"), task("B", deps=["A"]))
    run["repo"] = str(repo)
    store.start(run)
    store.report({"kind": "dispatch", "task": "A", "attempt": 1, "branch": "sdd/r1/A", "worktree": "/wt/A",
                  "base": "a" * 40})
    view = run_view(tmp_path)
    assert view["run_id"] == "r1"
    assert by_id(view)["A"]["status"] == "running" and by_id(view)["B"]["status"] == "queued"
