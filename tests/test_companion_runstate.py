"""Tests for the SDD run store (htmlkit.runstate).

Everything runs against a tmp_path session. The lock-busy test spawns a real interpreter so the
inter-process flock is exercised.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit.appstate import EVENT_TYPES, AppState  # noqa: E402
from htmlkit.runstate import TAB_FALLBACK_AFTER_S, RunError, RunStore  # noqa: E402


def _task(tid, deps=(), order_after=(), **extra):
    return {"id": tid, "title": f"Task {tid}", "deps": list(deps), "order_after": list(order_after), **extra}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return r


@pytest.fixture
def session(tmp_path):
    s = tmp_path / "session"
    s.mkdir()
    AppState(s).init()
    return s


@pytest.fixture
def app(session):
    return AppState(session)


@pytest.fixture
def store(session, app):
    return RunStore(session, app)


@pytest.fixture
def run_doc(repo):
    return {
        "v": 1,
        "run_id": "run-1",
        "repo": str(repo),
        "branch": "feature/x y",
        "branch_pattern": "sdd/{run}/{task}",
        "base": "abc1234",
        "tasks": [_task("T1"), _task("T2", deps=["T1"]), _task("T3", order_after=["T1"], contract_md="c")],
    }


def _rev(session):
    return json.loads((session / "state" / "counters.json").read_text())["rev"]


def _question(qid="q-1", **extra):
    q = {
        "id": qid,
        "prompt": "Pick one",
        "options": [{"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta", "description": "d"}],
    }
    q.update(extra)
    return q


# ---- AppState additions -------------------------------------------------------


def test_event_types_include_run_actions():
    for t in ("run-answer", "run-stop", "run-retry"):
        assert t in EVENT_TYPES


def test_bump_rev_returns_new_rev(session, app):
    before = _rev(session)
    assert app.bump_rev() == before + 1
    assert _rev(session) == before + 1


# ---- start / run --------------------------------------------------------------


def test_valid_run_round_trips(store, run_doc):
    assert store.run() is None
    assert store.start(run_doc) == {"run": "run-1", "resumed": False}
    assert store.run() == run_doc
    stored = json.loads((Path(store._app._dir) / "run" / "run.json").read_text())
    assert stored == run_doc


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda r: r.update(extra=1), "extra"),
        (lambda r: r.pop("branch"), "branch"),
        (lambda r: r.update(v=2), "v"),
        (lambda r: r.update(run_id="Bad_ID"), "run_id"),
        (lambda r: r.update(run_id="a" * 41), "run_id"),
        (lambda r: r.update(repo="relative/path"), "repo"),
        (lambda r: r.update(branch=""), "branch"),
        (lambda r: r.update(branch_pattern="sdd/{run}"), "branch_pattern"),
        (lambda r: r.update(base=""), "base"),
        (lambda r: r.update(tasks="nope"), "tasks"),
        (lambda r: r["tasks"][1].update(unknown=1), "tasks[1].unknown"),
        (lambda r: r["tasks"][1].update(id="bad id"), "tasks[1].id"),
        (lambda r: r["tasks"][1].update(id="T1"), "tasks[1].id"),
        (lambda r: r["tasks"][1].pop("title"), "tasks[1].title"),
        (lambda r: r["tasks"][1].update(contract_md=3), "tasks[1].contract_md"),
        (lambda r: r["tasks"][2].update(deps=["T9"]), "tasks[2].deps"),
        (lambda r: r["tasks"][2].update(order_after=["T9"]), "tasks[2].order_after"),
        (lambda r: r["tasks"][2].update(deps="T1"), "tasks[2].deps"),
        (lambda r: r["tasks"][0].update(deps=["T2"]), "tasks"),
        (lambda r: r["tasks"][0].update(order_after=["T1"]), "tasks"),
        (lambda r: r.update(tasks=[_task(f"T{i}") for i in range(201)]), "tasks"),
    ],
)
def test_invalid_run_rejected(store, run_doc, mutate, field):
    mutate(run_doc)
    with pytest.raises(RunError) as ei:
        store.start(run_doc)
    assert ei.value.field == field
    assert store.run() is None


def test_run_error_is_value_error():
    assert issubclass(RunError, ValueError)


def test_two_hundred_tasks_accepted(store, run_doc):
    run_doc["tasks"] = [_task(f"T{i}") for i in range(200)]
    assert store.start(run_doc)["run"] == "run-1"


def test_cycle_through_mixed_edges_rejected(store, run_doc):
    run_doc["tasks"] = [_task("A", deps=["C"]), _task("B", deps=["A"]), _task("C", order_after=["B"])]
    with pytest.raises(RunError) as ei:
        store.start(run_doc)
    assert ei.value.field == "tasks"


def test_resume_keeps_reports(store, run_doc):
    store.start(run_doc)
    store.report({"kind": "status", "text": "hi"})
    out = store.start(copy.deepcopy(run_doc))
    assert out == {"run": "run-1", "resumed": True}
    assert [r["n"] for r in store.reports()] == [1]


def test_resume_with_different_task_ids_rejected(store, run_doc):
    store.start(run_doc)
    run_doc["tasks"] = run_doc["tasks"][:2]
    with pytest.raises(RunError) as ei:
        store.start(run_doc)
    assert ei.value.field == "tasks"
    assert len(store.run()["tasks"]) == 3


def test_new_run_id_empties_state(store, run_doc, app):
    store.start(run_doc)
    store.report({"kind": "status", "text": "hi"})
    store.ask(_question())
    store.write_git_facts({"observed_at": 1, "changed_at": 1, "tasks": {}})
    store.touch_tab(now=100.0)
    run_dir = Path(app._dir) / "run"
    assert (run_dir / "reports.jsonl").exists()
    new = dict(run_doc, run_id="run-2")
    assert store.start(new) == {"run": "run-2", "resumed": False}
    assert store.reports() == []
    assert store.questions() == []
    assert store.git_facts() is None
    assert store.tab_seen_ago() is None
    assert store.run()["run_id"] == "run-2"


def test_preflight_start_then_plan_fills_tasks(store, run_doc):
    pre = dict(run_doc, tasks=[])
    assert store.start(pre) == {"run": "run-1", "resumed": False}
    assert store.run()["tasks"] == []
    store.report({"kind": "status", "text": "preflight"})
    out = store.start(run_doc)
    assert out == {"run": "run-1", "resumed": True}
    assert store.run() == run_doc
    assert len(store.reports()) == 1


def test_pointer_and_self_ignore(store, run_doc, repo, session):
    store.start(run_doc)
    sdd = repo / ".quirk" / "sdd"
    pointer = sdd / "feature-x-y.json"
    assert json.loads(pointer.read_text()) == {"session": os.path.abspath(session), "run_id": "run-1"}
    assert (sdd / ".gitignore").read_text().strip() == "*"


def test_pointer_slug_collapses_runs(store, run_doc, repo):
    run_doc["branch"] = "a//b @@ c.d_e-f"
    store.start(run_doc)
    assert (repo / ".quirk" / "sdd" / "a-b-c.d_e-f.json").exists()


# ---- reports ------------------------------------------------------------------


def test_report_numbers_and_stamps(store, run_doc):
    store.start(run_doc)
    t0 = time.time()
    outs = [store.report({"kind": "status", "text": f"s{i}"}) for i in range(3)]
    assert outs == [{"n": 1}, {"n": 2}, {"n": 3}]
    rs = store.reports()
    assert [r["n"] for r in rs] == [1, 2, 3]
    assert all(t0 - 1 <= r["at"] <= time.time() + 1 for r in rs)
    assert store.last_report_at() == rs[-1]["at"]
    lines = (Path(store._app._dir) / "run" / "reports.jsonl").read_text().splitlines()
    assert len(lines) == 3 and json.loads(lines[0])["kind"] == "status"


def test_report_without_run(store):
    with pytest.raises(RunError) as ei:
        store.report({"kind": "status", "text": "x"})
    assert ei.value.field == "run"


def test_last_report_at_none_without_reports(store, run_doc):
    assert store.last_report_at() is None
    store.start(run_doc)
    assert store.last_report_at() is None


VALID_REPORTS = [
    {"kind": "status", "text": "t"},
    {"kind": "dispatch", "task": "T1", "attempt": 1, "branch": "b", "worktree": "/w", "base": "abc"},
    {"kind": "return", "task": "T1", "attempt": 1, "word": "DONE"},
    {"kind": "return", "task": "T1", "attempt": 1, "word": "none"},
    {"kind": "retry", "task": "T1", "attempt": 2, "reason": "r"},
    {"kind": "commit", "task": "T1", "commit": "abc"},
    {"kind": "merge", "task": "T1", "head": "abc"},
    {"kind": "fail", "task": "T1", "reason": "r"},
    {"kind": "stop", "task": "T1", "reason": "r", "by": "user"},
    {"kind": "skip", "task": "T1", "reason": "r"},
    {"kind": "supersede", "task": "T1", "round": "r1", "reason": "r"},
    {"kind": "hold", "task": "T1", "round": "r1"},
    {"kind": "task-add", "task": _task("F1", deps=["T1"]), "round": "r1"},
    {"kind": "round-open", "round": "r1", "round_kind": "checkpoint", "title": "t", "covers": ["T1", "T2"]},
    {"kind": "round-close", "round": "r1", "outcome": "clean", "findings": []},
    {"kind": "action", "seq": 3, "outcome": "applied"},
    {"kind": "action", "seq": 3, "outcome": "declined", "reason": "r"},
    {"kind": "run-end", "outcome": "clean"},
    {"kind": "run-end", "outcome": "stopped", "next_step": "keep"},
]
# the schema's round-open {kind: checkpoint|final} cannot share a key with the report kind, so the
# store takes it as round_kind


@pytest.mark.parametrize("rep", VALID_REPORTS, ids=lambda r: r["kind"])
def test_every_report_kind_accepted(store, run_doc, rep):
    store.start(run_doc)
    assert store.report(copy.deepcopy(rep))["n"] == 1


def test_round_open_and_close_with_findings(store, run_doc):
    store.start(run_doc)
    with pytest.raises(RunError) as ei:
        store.report({"kind": "round-open", "round": "r1", "round_kind": "final", "title": "t", "covers": ["T9"]})
    assert ei.value.field == "covers"
    finding = {"id": "f1", "lens": "correctness", "severity": "high", "ruling": "accepted",
               "reason": "r", "fix_task": "F1"}
    assert store.report({"kind": "round-close", "round": "r1", "outcome": "fixes", "findings": [finding]}) == {"n": 1}
    bad = dict(finding, ruling="maybe")
    with pytest.raises(RunError) as ei:
        store.report({"kind": "round-close", "round": "r1", "outcome": "fixes", "findings": [bad]})
    assert ei.value.field == "findings[0].ruling"


@pytest.mark.parametrize(
    "rep, field",
    [
        ("notadict", "report"),
        ({"text": "x"}, "kind"),
        ({"kind": "bogus"}, "kind"),
        ({"kind": "status", "text": "x", "n": 5}, "n"),
        ({"kind": "status", "text": "x", "at": 5}, "at"),
        ({"kind": "status"}, "text"),
        ({"kind": "status", "text": ""}, "text"),
        ({"kind": "dispatch", "task": "T1", "attempt": 1, "branch": "b", "worktree": "/w"}, "base"),
        ({"kind": "dispatch", "task": "T9", "attempt": 1, "branch": "b", "worktree": "/w", "base": "x"}, "task"),
        ({"kind": "dispatch", "task": "T1", "attempt": 0, "branch": "b", "worktree": "/w", "base": "x"}, "attempt"),
        ({"kind": "dispatch", "task": "T1", "attempt": True, "branch": "b", "worktree": "/w", "base": "x"}, "attempt"),
        ({"kind": "return", "task": "T1", "attempt": 1, "word": "MAYBE"}, "word"),
        ({"kind": "stop", "task": "T1", "reason": "r", "by": "bot"}, "by"),
        ({"kind": "commit", "task": "T1"}, "commit"),
        ({"kind": "task-add", "task": _task("T1"), "round": "r1"}, "task.id"),
        ({"kind": "task-add", "task": _task("F1", deps=["Z"]), "round": "r1"}, "task.deps"),
        ({"kind": "task-add", "task": _task("F1"), "round": "bad round"}, "round"),
        ({"kind": "run-end", "outcome": "done"}, "outcome"),
        ({"kind": "run-end", "outcome": "clean", "next_step": "ship"}, "next_step"),
        ({"kind": "action", "seq": "3", "outcome": "applied"}, "seq"),
        ({"kind": "action", "seq": 3, "outcome": "nope"}, "outcome"),
        ({"kind": "round-open", "round": "r1", "title": "t", "covers": ["T1"]}, "round_kind"),
        ({"kind": "round-open", "round": "r1", "round_kind": "x", "title": "t", "covers": ["T1"]}, "round_kind"),
    ],
)
def test_invalid_report_rejected(store, run_doc, rep, field):
    store.start(run_doc)
    with pytest.raises(RunError) as ei:
        store.report(rep)
    assert ei.value.field == field
    assert store.reports() == []


def test_fix_task_becomes_known_after_task_add(store, run_doc):
    store.start(run_doc)
    fail = {"kind": "fail", "task": "F1", "reason": "r"}
    with pytest.raises(RunError) as ei:
        store.report(fail)
    assert ei.value.field == "task"
    store.report({"kind": "task-add", "task": _task("F1", deps=["T1"]), "round": "r1"})
    assert store.report(fail) == {"n": 2}


def test_report_lock_busy_returns_within_deadline(store, run_doc, session):
    store.start(run_doc)
    holder = subprocess.Popen(
        [
            sys.executable, "-c",
            "import fcntl, os, sys, time\n"
            "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "print('locked', flush=True)\n"
            "time.sleep(10)\n",
            str(session / "state" / "app.lock"),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        rev = _rev(session)
        t0 = time.monotonic()
        out = store.report({"kind": "status", "text": "x"})
        elapsed = time.monotonic() - t0
        assert out == {"dropped": "lock-busy"}
        assert 0.9 <= elapsed <= 1.5
        assert _rev(session) == rev
    finally:
        holder.kill()
        holder.wait()
    assert store.reports() == []
    assert store.report({"kind": "status", "text": "x"}) == {"n": 1}


def test_report_returns_dropped_on_os_error(store, run_doc, monkeypatch):
    store.start(run_doc)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("htmlkit.runstate.os.fsync", boom)
    assert store.report({"kind": "status", "text": "x"}) == {"dropped": "disk full"}


def test_torn_report_line_is_skipped_and_not_extended(store, run_doc):
    store.start(run_doc)
    store.report({"kind": "status", "text": "a"})
    path = Path(store._app._dir) / "run" / "reports.jsonl"
    with open(path, "a") as fh:
        fh.write('{"n": 2, "kind"')
    assert store.report({"kind": "status", "text": "b"}) == {"n": 2}
    assert [r["text"] for r in store.reports()] == ["a", "b"]


def test_torn_multibyte_report_line_is_skipped(store, run_doc):
    store.start(run_doc)
    store.report({"kind": "status", "text": "a"})
    path = Path(store._app._dir) / "run" / "reports.jsonl"
    with open(path, "ab") as fh:
        fh.write(b'{"n": 2, "kind": "status", "text": "\xe2\x82\n')
    assert [r["text"] for r in store.reports()] == ["a"]
    assert store.report({"kind": "status", "text": "b"}) == {"n": 2}
    assert [r["text"] for r in store.reports()] == ["a", "b"]


# ---- questions and answers ----------------------------------------------------


def test_ask_fallback_follows_tab_check_in(store, run_doc):
    store.start(run_doc)
    out = store.ask(_question("q-1"))
    assert out == {"question": "q-1", "tab_seen_ago": None, "fallback": True}
    store.touch_tab()
    out = store.ask(_question("q-2"))
    assert out["fallback"] is False
    assert 0 <= out["tab_seen_ago"] < 5


def test_ask_fallback_when_check_in_is_old(store, run_doc):
    store.start(run_doc)
    now = time.time()
    store.touch_tab(now=now - TAB_FALLBACK_AFTER_S - 10)
    assert store.ask(_question())["fallback"] is True


def test_ask_stores_open_question_and_report(store, run_doc, app):
    store.start(run_doc)
    q = _question("q-1", task="T2", header="H", recommended="a", default="b")
    store.ask(q)
    (stored,) = store.questions()
    assert stored["state"] == "open" and "answer" not in stored
    assert isinstance(stored["asked_at"], float)
    assert {k: stored[k] for k in q} == q
    (rep,) = store.reports()
    assert rep["kind"] == "question" and rep["question"] == "q-1" and rep["task"] == "T2"
    assert rep["n"] == 1


def test_ask_report_omits_task_when_absent(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    assert "task" not in store.reports()[0]


def test_ask_without_run(store):
    with pytest.raises(RunError) as ei:
        store.ask(_question())
    assert ei.value.field == "run"


def test_ask_duplicate_id_rejected(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    with pytest.raises(RunError) as ei:
        store.ask(_question())
    assert ei.value.field == "id"
    assert len(store.questions()) == 1 and len(store.reports()) == 1


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda q: q.update(extra=1), "extra"),
        (lambda q: q.pop("id"), "id"),
        (lambda q: q.update(id="Bad Id"), "id"),
        (lambda q: q.pop("prompt"), "prompt"),
        (lambda q: q.update(task="T9"), "task"),
        (lambda q: q.update(header=3), "header"),
        (lambda q: q.update(options=[q["options"][0]]), "options"),
        (lambda q: q.update(options=[{"value": str(i), "label": "l"} for i in range(7)]), "options"),
        (lambda q: q.update(options=[{"value": "a", "label": "l"}, {"value": "a", "label": "m"}]), "options[1].value"),
        (lambda q: q["options"][0].pop("label"), "options[0].label"),
        (lambda q: q["options"][0].update(extra=1), "options[0].extra"),
        (lambda q: q.update(recommended="zzz"), "recommended"),
        (lambda q: q.update(default="zzz"), "default"),
        (lambda q: q.update(recommended=["a"]), "recommended"),
        (lambda q: q.update(recommended={"a": 1}), "recommended"),
        (lambda q: q.update(recommended=1), "recommended"),
        (lambda q: q.update(default=["a"]), "default"),
        (lambda q: q.update(default={"a": 1}), "default"),
        (lambda q: q.update(default=1), "default"),
    ],
)
def test_invalid_question_rejected(store, run_doc, mutate, field):
    store.start(run_doc)
    q = _question()
    mutate(q)
    with pytest.raises(RunError) as ei:
        store.ask(q)
    assert ei.value.field == field
    assert store.questions() == []


def test_answer_pick_records_label_and_report(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    ans, recorded = store.answer("q-1", "tab", pick="b")
    assert recorded is True
    assert ans["question"] == "q-1" and ans["source"] == "tab"
    assert ans["pick"] == "b" and ans["label"] == "Beta" and "text" not in ans
    assert isinstance(ans["at"], float)
    (q,) = store.questions()
    assert q["state"] == "answered" and q["answer"] == ans
    last = store.reports()[-1]
    assert last["kind"] == "answered" and last["question"] == "q-1" and last["source"] == "tab"


def test_answer_text(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    ans, recorded = store.answer("q-1", "orca", text="free form")
    assert recorded and ans["text"] == "free form" and "pick" not in ans and "label" not in ans


def test_answer_first_wins(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    first, rec1 = store.answer("q-1", "tab", pick="a")
    second, rec2 = store.answer("q-1", "orca", pick="b")
    assert rec1 is True and rec2 is False
    assert second == first
    assert len([r for r in store.reports() if r["kind"] == "answered"]) == 1


def test_answer_first_wins_across_threads(store, run_doc):
    store.start(run_doc)
    store.ask(_question())
    results = []
    barrier = threading.Barrier(2)

    def go(source, pick):
        barrier.wait()
        results.append(store.answer("q-1", source, pick=pick))

    ts = [threading.Thread(target=go, args=("tab", "a")), threading.Thread(target=go, args=("orca", "b"))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(r[1] for r in results) == [False, True]
    assert results[0][0] == results[1][0]
    assert len([r for r in store.reports() if r["kind"] == "answered"]) == 1


def test_answer_first_wins_across_store_instances(session, run_doc):
    a, b = RunStore(session), RunStore(session)
    a.start(run_doc)
    a.ask(_question())
    results = []
    barrier = threading.Barrier(2)

    def go(s, source, pick):
        barrier.wait()
        results.append(s.answer("q-1", source, pick=pick))

    ts = [threading.Thread(target=go, args=(a, "tab", "a")), threading.Thread(target=go, args=(b, "sdd", "b"))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(r[1] for r in results) == [False, True]
    assert results[0][0] == results[1][0]


@pytest.mark.parametrize(
    "kwargs, field",
    [
        ({"source": "tab", "pick": "zzz"}, "pick"),
        ({"source": "tab"}, "pick"),
        ({"source": "tab", "pick": "a", "text": "t"}, "pick"),
        ({"source": "tab", "text": ""}, "text"),
        ({"source": "robot", "pick": "a"}, "source"),
    ],
)
def test_invalid_answer_rejected(store, run_doc, kwargs, field):
    store.start(run_doc)
    store.ask(_question())
    with pytest.raises(RunError) as ei:
        store.answer("q-1", **kwargs)
    assert ei.value.field == field
    assert store.questions()[0]["state"] == "open"


def test_answer_unknown_question(store, run_doc):
    store.start(run_doc)
    with pytest.raises(RunError) as ei:
        store.answer("nope", "tab", pick="a")
    assert ei.value.field == "question"


# ---- tab check-ins ------------------------------------------------------------


def test_touch_tab_throttles_writes(store, run_doc):
    store.start(run_doc)
    path = Path(store._app._dir) / "run" / "tab-seen"
    assert store.tab_seen_ago() is None
    store.touch_tab(now=1000.0)
    assert float(path.read_text()) == 1000.0
    mtime = path.stat().st_mtime_ns
    time.sleep(0.02)
    store.touch_tab(now=1003.0)
    assert path.stat().st_mtime_ns == mtime
    assert float(path.read_text()) == 1000.0
    store.touch_tab(now=1005.5)
    assert float(path.read_text()) == 1005.5
    assert store.tab_seen_ago(now=1007.5) == pytest.approx(2.0)


def test_touch_tab_without_run_dir_is_harmless(store):
    store.touch_tab(now=5.0)
    assert store.tab_seen_ago(now=6.0) == pytest.approx(1.0)


# ---- git facts ----------------------------------------------------------------


def test_git_facts_round_trip(store, run_doc):
    store.start(run_doc)
    assert store.git_facts() is None
    facts = {"observed_at": 5.0, "changed_at": 5.0, "tasks": {"T1": {"commits": 1, "merged": False,
             "files": ["a"], "worktree_present": True}}}
    store.write_git_facts(facts)
    assert store.git_facts() == facts
    assert json.loads((Path(store._app._dir) / "run" / "git.json").read_text()) == facts


# ---- rev ----------------------------------------------------------------------


def test_every_write_bumps_rev_except_touch_tab(store, run_doc, session):
    steps = [
        lambda: store.start(run_doc),
        lambda: store.report({"kind": "status", "text": "x"}),
        lambda: store.ask(_question()),
        lambda: store.answer("q-1", "tab", pick="a"),
        lambda: store.write_git_facts({"observed_at": 1, "changed_at": 1, "tasks": {}}),
    ]
    for step in steps:
        before = _rev(session)
        step()
        assert _rev(session) == before + 1
    before = _rev(session)
    store.touch_tab(now=time.time())
    store.answer("q-1", "orca", pick="b")  # lost the race: nothing changed
    assert _rev(session) == before


def test_store_methods_are_reentrant_under_app_lock(store, run_doc, app):
    with app.lock():
        store.start(run_doc)
        store.ask(_question())
        store.answer("q-1", "tab", pick="a")
        store.touch_tab()
    assert store.questions()[0]["state"] == "answered"
