"""Fold an SDD run's stored state into the view model the companion's run tab renders.

``fold`` is a pure function of plain dicts and lists: no clock, no I/O, no randomness, so the same
input always gives the same view. Every status, mismatch, missing, blocked-by and stale rule lives
here. ``run_view`` is the only function that reads disk. It loads the run store and calls ``fold``.
"""
from __future__ import annotations

import copy
import math
import os
import re
import time
from typing import Any, Iterable

STALE_AFTER_S = 180
TAB_FALLBACK_AFTER_S = 120

STATUSES = (
    "queued", "running", "needs-you", "retrying", "passed", "failed", "skipped", "stopped", "missing",
)
_TERMINAL = frozenset({"passed", "failed", "skipped", "stopped"})
_WORKING = frozenset({"running", "retrying", "needs-you"})
_TASK_KINDS = frozenset({
    "dispatch", "return", "retry", "commit", "merge", "fail", "stop", "skip", "supersede", "hold",
})


def levels(tasks: list[dict], extra_below: dict[str, list[str]] | None = None) -> dict[str, int]:
    """Map each task id to its 1-based level: the longest chain of dependency edges up to a root.

    Ordering edges never raise a level. ``extra_below`` names additional ids a task must sit above,
    which is how a fix task lands after the tasks its review round covers.
    """
    ids = {t["id"] for t in tasks}
    below = {
        t["id"]: [d for d in [*t.get("deps", []), *(extra_below or {}).get(t["id"], [])] if d in ids]
        for t in tasks
    }
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def level_of(tid: str) -> int:
        if tid in memo:
            return memo[tid]
        if tid in visiting:
            return 0
        visiting.add(tid)
        value = max((level_of(b) for b in below[tid]), default=0) + 1
        visiting.discard(tid)
        memo[tid] = value
        return value

    return {t["id"]: level_of(t["id"]) for t in tasks}


def chains(tasks: list[dict], level: dict[str, int]) -> list[dict]:
    """Maximal paths of ordering edges between tasks on one level, as ``{id: "c1", tasks: [...]}``.

    A task with no same-level ordering edge belongs to no chain. Ids follow the plan order of each
    chain's first task.
    """
    order = [t["id"] for t in tasks]
    succ: dict[str, list[str]] = {i: [] for i in order}
    has_pred: set[str] = set()
    for t in tasks:
        tid = t["id"]
        for p in t.get("order_after", []):
            if p in succ and p != tid and level.get(p) == level.get(tid):
                succ[p].append(tid)
                has_pred.add(tid)
    used: set[str] = set()
    paths: list[list[str]] = []
    for start in [*(i for i in order if i not in has_pred), *(i for i in order if i in has_pred)]:
        if start in used:
            continue
        path = [start]
        used.add(start)
        while (nxt := next((n for n in succ[path[-1]] if n not in used), None)) is not None:
            path.append(nxt)
            used.add(nxt)
        if len(path) > 1:
            paths.append(path)
    index = {tid: i for i, tid in enumerate(order)}
    paths.sort(key=lambda p: index[p[0]])
    return [{"id": f"c{n}", "tasks": p} for n, p in enumerate(paths, 1)]


def _mentions(text: Any, tid: str) -> bool:
    if not isinstance(text, str):
        return False
    pattern = rf"(?<![.A-Za-z0-9_-]){re.escape(tid)}(?![A-Za-z0-9_-]|\.[A-Za-z0-9])"
    return re.search(pattern, text) is not None


def _replay(task_reports: list[dict]) -> dict:
    """Replay one task's reports in order into its reported status, attempts and hold."""
    st: dict[str, Any] = {
        "status": "queued", "attempt": 0, "reason": None, "attempts": [], "held_by": None,
        "reported": bool(task_reports), "last_at": None, "has_dispatch": False, "gap": False,
    }

    def close(at: float, outcome: str) -> None:
        if st["attempts"] and "end" not in st["attempts"][-1]:
            st["attempts"][-1].update(end=at, outcome=outcome)

    for r in task_reports:
        kind, at = r["kind"], r["at"]
        if kind == "dispatch":
            attempt = r.get("attempt", 1)
            st["attempts"].append({"n": attempt, "start": at})
            st["attempt"] = attempt
            st["status"] = "retrying" if attempt > 1 else "running"
            if attempt <= 1:
                st["reason"] = None
            st["has_dispatch"] = True
        elif kind == "retry":
            close(at, "failed")
            st["attempt"] = r.get("attempt", st["attempt"] + 1)
            st["status"] = "retrying"
            st["reason"] = r.get("reason")
        elif kind == "commit":
            close(at, "passed")
            st["status"], st["reason"] = "passed", None
        elif kind == "fail":
            close(at, "failed")
            st["status"], st["reason"] = "failed", r.get("reason")
        elif kind == "stop":
            st["held_by"] = None
            if st["status"] == "failed":
                continue
            close(at, "stopped")
            st["status"], st["reason"] = "stopped", r.get("reason")
        elif kind == "skip":
            close(at, "skipped")
            st["status"], st["reason"] = "skipped", r.get("reason")
        elif kind == "supersede":
            close(at, "queued")
            st["status"], st["reason"] = "queued", r.get("reason")
            st["held_by"] = None
        elif kind == "hold":
            st["held_by"] = r.get("round")
            continue
        elif kind == "merge":
            st["held_by"] = None
            continue
        elif kind == "return":
            continue
        st["last_at"] = at
    kinds = {r["kind"] for r in task_reports}
    st["gap"] = not st["has_dispatch"] and bool(kinds & {"commit", "return"})
    return st


def fold(
    run: dict,
    reports: list[dict],
    git: dict | None,
    questions: list[dict],
    actions: list[dict],
    now: float,
    stale_after_s: float = STALE_AFTER_S,
) -> dict:
    """Turn a run's stored state into the RunView the tab renders.

    ``reports`` are the run's report lines, ``git`` the watcher's facts (or None), ``questions`` the
    stored questions with their state, ``actions`` the ``run-stop`` and ``run-retry`` events from the
    app event log. Pure: the caller supplies ``now``.
    """
    reports = sorted(reports, key=lambda r: r.get("n", 0))
    git_tasks: dict[str, dict] = (git or {}).get("tasks", {}) if git else {}

    plan = [copy.deepcopy(t) for t in run.get("tasks", [])]
    task_round: dict[str, str] = {}
    known = {t["id"] for t in plan}
    for r in reports:
        if r["kind"] == "task-add" and isinstance(r.get("task"), dict) and r["task"].get("id") not in known:
            t = copy.deepcopy(r["task"])
            t.setdefault("deps", [])
            t.setdefault("order_after", [])
            plan.append(t)
            known.add(t["id"])
            task_round[t["id"]] = r.get("round")
    order = [t["id"] for t in plan]
    by_id = {t["id"]: t for t in plan}

    rounds: dict[str, dict] = {}
    for r in reports:
        if r["kind"] == "round-open":
            rounds[r["round"]] = {
                "id": r["round"], "kind": r.get("round_kind"), "title": r.get("title"),
                "covers": list(r.get("covers", [])), "findings": [],
            }
        elif r["kind"] == "round-close" and r.get("round") in rounds:
            rounds[r["round"]]["outcome"] = r.get("outcome")
            rounds[r["round"]]["findings"] = copy.deepcopy(r.get("findings", []))

    extra_below = {
        tid: list(rounds[rid]["covers"]) for tid, rid in task_round.items() if rid in rounds
    }
    level = levels(plan, extra_below)
    chain_list = chains(plan, level)
    chain_of = {tid: c["id"] for c in chain_list for tid in c["tasks"]}

    per_task: dict[str, list[dict]] = {tid: [] for tid in order}
    for r in reports:
        tid = r.get("task")
        if r["kind"] in _TASK_KINDS and isinstance(tid, str) and tid in per_task:
            per_task[tid].append(r)
    replay = {tid: _replay(per_task[tid]) for tid in order}

    ended = next(
        ({"at": r["at"], "outcome": r.get("outcome"), **({"next_step": r["next_step"]} if r.get("next_step") else {})}
         for r in reversed(reports) if r["kind"] == "run-end"),
        None,
    )

    status = {tid: replay[tid]["status"] for tid in order}
    git_only: set[str] = set()
    for tid in order:
        entry = git_tasks.get(tid)
        if not replay[tid]["reported"] and entry and (entry.get("commits", 0) > 0 or entry.get("merged")):
            status[tid] = "passed"
            git_only.add(tid)

    def deps_passed(tid: str) -> bool:
        return all(status.get(d) == "passed" for d in by_id[tid].get("deps", []) if d in by_id)

    open_question: dict[str, dict] = {}
    for q in sorted(questions, key=lambda q: q.get("asked_at", 0)):
        if q.get("state") == "open" and q.get("task") in per_task:
            open_question.setdefault(q["task"], q)

    unheard = {
        tid for tid in order
        if not replay[tid]["reported"] and tid not in git_tasks and tid not in git_only and deps_passed(tid)
    }
    by_level: dict[int, list[str]] = {}
    for tid in order:
        by_level.setdefault(level[tid], []).append(tid)
    # a ready task nobody has dispatched is only missing once the run is quiet: with no level-mate to compare
    # against, or any task still working, it may simply not have been dispatched yet
    working = any(status[tid] in _WORKING for tid in order) or bool(open_question)
    for tid in sorted(unheard, key=order.index):
        others = [o for o in by_level[level[tid]] if o != tid]
        level_done = bool(others) and not working and all(status[o] in _TERMINAL for o in others)
        if ended is not None or level_done:
            status[tid] = "missing"

    for tid in open_question:
        status[tid] = "needs-you"

    succ: dict[str, list[str]] = {tid: [] for tid in order}
    edges: list[dict] = []
    for t in plan:
        for kind, key in (("dep", "deps"), ("order", "order_after")):
            for p in t.get(key, []):
                if p in succ:
                    edges.append({"from": p, "to": t["id"], "kind": kind})
                    succ[p].append(t["id"])

    def downstream(tid: str) -> list[str]:
        seen: set[str] = set()
        stack = list(succ[tid])
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(succ[n])
        return [n for n in order if n in seen and status[n] != "passed"]

    def blocking(tid: str, seen: set[str]) -> set[str]:
        found: set[str] = set()
        for d in by_id[tid].get("deps", []):
            if d not in by_id or d in seen:
                continue
            seen.add(d)
            if status[d] == "failed":
                found.add(d)
            elif status[d] != "passed":
                found |= blocking(d, seen)
        return found

    fix_labels = _fix_labels(task_round, rounds)
    pending = _pending_actions(actions, reports, set(order))

    last_report_at = max((r["at"] for r in reports), default=None)
    candidates = [x for x in (last_report_at, (git or {}).get("changed_at") if git else None) if x is not None]
    last_update_at = max(candidates) if candidates else None
    stale = None
    if ended is None and last_update_at is not None and now - last_update_at > stale_after_s:
        stale = {"since": now - last_update_at}

    view_tasks = []
    counts = {s: 0 for s in STATUSES}
    for tid in order:
        t, st = by_id[tid], replay[tid]
        entry = git_tasks.get(tid)
        blocked = sorted(blocking(tid, set()), key=order.index) if status[tid] == "queued" else []
        labels: list[str] = []
        if tid in git_only:
            labels.append("seen in git, not reported")
        if st["gap"]:
            labels.append("dispatch not reported")
        if tid in fix_labels:
            labels.append(fix_labels[tid])
        labels.extend(f"blocked by {b}" for b in blocked)
        if st["held_by"]:
            labels.append(f"merge held by {st['held_by']}")

        view: dict[str, Any] = {
            "id": tid, "title": t.get("title"), "level": level[tid], "status": status[tid],
            "attempt": st["attempt"], "attempts": st["attempts"],
            "files": len(entry.get("files", [])) if entry else 0,
            "ready": deps_passed(tid), "blocked_by": blocked, "downstream": downstream(tid),
            "labels": labels,
            "mismatch": _mismatch(tid, status[tid], st, entry, git),
        }
        if "contract_md" in t:
            view["contract_md"] = t["contract_md"]
        if tid in chain_of:
            view["chain"] = chain_of[tid]
        if st["reason"] is not None and status[tid] in ("failed", "stopped", "skipped", "retrying", "queued"):
            view["reason"] = st["reason"]
        if st["attempts"]:
            view["started_at"] = st["attempts"][0]["start"]
            if status[tid] in _TERMINAL and "end" in st["attempts"][-1]:
                view["ended_at"] = st["attempts"][-1]["end"]
        if tid in task_round:
            view["round"] = task_round[tid]
        if tid in open_question:
            view["question"] = open_question[tid]["id"]
        if tid in pending:
            view["pending_action"] = pending[tid]
        if st["held_by"]:
            view["held_by"] = st["held_by"]
        view_tasks.append(view)
        counts[status[tid]] += 1

    status_text = next((r.get("text") for r in reversed(reports) if r["kind"] == "status"), None)
    result: dict[str, Any] = {
        "run_id": run.get("run_id"), "branch": run.get("branch"),
        "started_at": reports[0]["at"] if reports else None,
        "counts": counts, "last_update_at": last_update_at, "stale": stale,
        "stale_after_s": stale_after_s, "now": now,
        "tasks": view_tasks, "edges": edges, "chains": chain_list,
        "rounds": list(rounds.values()),
        "questions": [copy.deepcopy(q) for q in sorted(questions, key=lambda q: q.get("asked_at", 0))],
    }
    if status_text is not None:
        result["status_text"] = status_text
    if ended is not None:
        result["ended"] = ended
    return result


def _fix_labels(task_round: dict[str, str], rounds: dict[str, dict]) -> dict[str, str]:
    """Label each fix task with its round, naming a covered task only when the finding names exactly one."""
    labels: dict[str, str] = {}
    for tid, rid in task_round.items():
        label = f"fix · {rid}"
        round_ = rounds.get(rid)
        finding = next((f for f in (round_ or {}).get("findings", []) if f.get("fix_task") == tid), None)
        if finding is not None:
            named = [c for c in round_["covers"] if _mentions(finding.get("reason"), c)]
            if len(named) == 1:
                label = f"fix {named[0]} · {rid}"
        labels[tid] = label
    return labels


def _pending_actions(actions: Iterable[dict], reports: list[dict], task_ids: set[str]) -> dict[str, str]:
    """Tab actions SDD has not yet answered, as ``task id -> "stop" | "retry"`` (latest event wins)."""
    handled = {r.get("seq") for r in reports if r["kind"] == "action"}
    pending: dict[str, str] = {}
    for event in sorted(actions, key=lambda e: e.get("seq", 0)):
        kind = event.get("type")
        tid = (event.get("payload") or {}).get("task")
        if kind not in ("run-stop", "run-retry") or tid not in task_ids or event.get("seq") in handled:
            continue
        word = kind.removeprefix("run-")
        since = event.get("timestamp", 0)
        if any(r["kind"] in ("stop", "retry") and r.get("task") == tid and r["at"] > since for r in reports):
            continue
        pending[tid] = word
    return pending


def _mismatch(tid: str, status: str, st: dict, entry: dict | None, git: dict | None) -> dict | None:
    """SDD-versus-git disagreement for one task, judged only on git facts newer than SDD's report."""
    if not git or not st["reported"] or st["last_at"] is None or git.get("observed_at", 0) <= st["last_at"]:
        return None
    if entry is not None and entry.get("error"):
        return None
    if status == "passed":
        if entry is None or (entry.get("commits", 0) == 0 and not entry.get("merged")):
            return {"sdd": status, "git": "no commit", "text": f"SDD says passed; git has no commit for {tid} yet"}
    elif entry is not None and entry.get("merged"):
        return {"sdd": status, "git": "merged", "text": f"git shows {tid} merged; SDD says {status}"}
    elif status == "running" and entry is not None and entry.get("worktree_present") is False:
        return {"sdd": status, "git": "no worktree", "text": f"SDD says running; git has no worktree for {tid}"}
    return None


def _stale_after_from_env() -> float:
    raw = os.environ.get("QUIRK_RUN_STALE_AFTER_S")
    try:
        value = float(raw) if raw else 0.0
    except ValueError:
        return STALE_AFTER_S
    return value if math.isfinite(value) and value > 0 else STALE_AFTER_S


def run_view(session: os.PathLike) -> dict | None:
    """The folded view of the run registered in ``session``, or None when there is none.

    ``QUIRK_RUN_STALE_AFTER_S`` (a positive number) overrides the stale threshold, for tests.
    """
    from .appstate import AppState
    from .runstate import RunStore

    store = RunStore(session)
    run = store.run()
    if run is None:
        return None
    actions = [e for e in AppState(session).events_after(0) if e.get("type") in ("run-stop", "run-retry")]
    return fold(
        run, store.reports(), store.git_facts(), store.questions(), actions,
        now=time.time(), stale_after_s=_stale_after_from_env(),
    )
