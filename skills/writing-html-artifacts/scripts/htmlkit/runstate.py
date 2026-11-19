"""On-disk store for one companion session's SDD run, under ``<session>/state/run/``.

``RunStore`` validates RUN.json, reports and questions, persists them, arbitrates which answer to a
question wins, and records tab check-ins. It never folds status into a view (that is ``runfold``)
and never runs git (that is ``gitwatch``); the companion CLI and server call it.

Files: ``run.json``, ``reports.jsonl`` (append-only), ``questions.json``, ``tab-seen`` and
``git.json``. Every write except ``touch_tab`` bumps the snapshot ``rev`` inside the same hold of
the shared ``state/app.lock``, so a poller always sees a change. ``report`` is the one method that
must never stall its caller: it waits for the lock only briefly and drops the report instead.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from .appstate import AppState
from .fsutil import atomic_write, ensure_self_ignoring

try:
    from .runfold import TAB_FALLBACK_AFTER_S
except ModuleNotFoundError as _exc:
    if _exc.name != f"{__package__}.runfold":
        raise
    TAB_FALLBACK_AFTER_S = 120

TAB_TOUCH_INTERVAL_S = 5.0
_LOCK_POLL_S = 0.02

_RUN_ID_RE = re.compile(r"[a-z0-9-]{1,40}")
_TASK_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,40}")
_ROUND_RE = re.compile(r"[A-Za-z0-9-]{1,20}")
_QUESTION_ID_RE = re.compile(r"[a-z0-9-]{1,40}")
_BRANCH_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")

_RUN_KEYS = ("v", "run_id", "repo", "branch", "branch_pattern", "base", "tasks")
_TASK_REQUIRED = ("id", "title", "deps", "order_after")
_TASK_KEYS = (*_TASK_REQUIRED, "contract_md")
_QUESTION_KEYS = ("id", "task", "header", "prompt", "options", "recommended", "default")
_OPTION_KEYS = ("value", "label", "description")
_MAX_TASKS = 200
_SOURCES = ("tab", "orca", "sdd")
_WORDS = ("DONE", "NEEDS_CONTEXT", "BLOCKED", "FAILED", "none")
_FINDING_RULINGS = ("accepted", "dismissed")


class RunError(ValueError):
    """Invalid input to a RunStore call; ``field`` names the offending key, e.g. ``tasks[2].deps``."""

    def __init__(self, field: str, message: str | None = None):
        self.field = field
        super().__init__(message or f"invalid {field}")


# ---- validation ---------------------------------------------------------------


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _is_nonempty(v: Any) -> bool:
    return isinstance(v, str) and bool(v)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_attempt(v: Any) -> bool:
    return _is_int(v) and v >= 1


def _matches(pattern: re.Pattern) -> Callable[[Any], bool]:
    return lambda v: isinstance(v, str) and bool(pattern.fullmatch(v))


def _one_of(*values: str) -> Callable[[Any], bool]:
    return lambda v: isinstance(v, str) and v in values


def _check_id_list(value: Any, field: str, known: set[str] | None) -> None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise RunError(field)
    if known is not None and any(x not in known for x in value):
        raise RunError(field)


def _validate_task(task: Any, prefix: str, known: set[str] | None) -> None:
    """Shape-check one task; edges are checked against ``known`` only when it is given."""
    if not isinstance(task, dict):
        raise RunError(prefix)
    for key in task:
        if key not in _TASK_KEYS:
            raise RunError(f"{prefix}.{key}")
    for key in _TASK_REQUIRED:
        if key not in task:
            raise RunError(f"{prefix}.{key}")
    if not _matches(_TASK_ID_RE)(task["id"]):
        raise RunError(f"{prefix}.id")
    if not _is_nonempty(task["title"]):
        raise RunError(f"{prefix}.title")
    if "contract_md" in task and not _is_str(task["contract_md"]):
        raise RunError(f"{prefix}.contract_md")
    _check_id_list(task["deps"], f"{prefix}.deps", known)
    _check_id_list(task["order_after"], f"{prefix}.order_after", known)


def _acyclic(tasks: list[dict]) -> bool:
    edges = {t["id"]: set(t["deps"]) | set(t["order_after"]) for t in tasks}
    remaining = {k: set(v) for k, v in edges.items()}
    while remaining:
        free = [k for k, v in remaining.items() if not v]
        if not free:
            return False
        for k in free:
            del remaining[k]
        for v in remaining.values():
            v.difference_update(free)
    return True


def _validate_run(run: Any) -> None:
    if not isinstance(run, dict):
        raise RunError("run")
    for key in run:
        if key not in _RUN_KEYS:
            raise RunError(str(key))
    for key in _RUN_KEYS:
        if key not in run:
            raise RunError(key)
    if run["v"] != 1 or isinstance(run["v"], bool):
        raise RunError("v")
    if not _matches(_RUN_ID_RE)(run["run_id"]):
        raise RunError("run_id")
    if not (_is_nonempty(run["repo"]) and os.path.isabs(run["repo"])):
        raise RunError("repo")
    if not _is_nonempty(run["branch"]):
        raise RunError("branch")
    if not (_is_str(run["branch_pattern"]) and "{task}" in run["branch_pattern"]):
        raise RunError("branch_pattern")
    if not (_is_nonempty(run["base"]) and not any(c.isspace() for c in run["base"])):
        raise RunError("base")
    tasks = run["tasks"]
    if not isinstance(tasks, list) or len(tasks) > _MAX_TASKS:
        raise RunError("tasks")
    ids: set[str] = set()
    for i, task in enumerate(tasks):
        _validate_task(task, f"tasks[{i}]", None)
        if task["id"] in ids:
            raise RunError(f"tasks[{i}].id")
        ids.add(task["id"])
    for i, task in enumerate(tasks):
        _check_id_list(task["deps"], f"tasks[{i}].deps", ids)
        _check_id_list(task["order_after"], f"tasks[{i}].order_after", ids)
    if not _acyclic(tasks):
        raise RunError("tasks")


def _validate_findings(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise RunError(field)
    for i, f in enumerate(value):
        p = f"{field}[{i}]"
        if not isinstance(f, dict):
            raise RunError(p)
        for key in ("id", "lens", "severity"):
            if not _is_nonempty(f.get(key)):
                raise RunError(f"{p}.{key}")
        if f.get("ruling") not in _FINDING_RULINGS:
            raise RunError(f"{p}.ruling")
        if not _is_str(f.get("reason")):
            raise RunError(f"{p}.reason")
        if "fix_task" in f and not _is_nonempty(f["fix_task"]):
            raise RunError(f"{p}.fix_task")


# kind -> ((field, predicate), ...) for required fields; ``task`` and ``covers`` are checked
# against the known task ids separately.
_REPORT_FIELDS: dict[str, tuple[tuple[str, Callable[[Any], bool]], ...]] = {
    "status": (("text", _is_nonempty),),
    "dispatch": (("task", _is_nonempty), ("attempt", _is_attempt), ("branch", _is_nonempty),
                 ("worktree", _is_nonempty), ("base", _is_nonempty)),
    "return": (("task", _is_nonempty), ("attempt", _is_attempt), ("word", _one_of(*_WORDS))),
    "retry": (("task", _is_nonempty), ("attempt", _is_attempt), ("reason", _is_str)),
    "commit": (("task", _is_nonempty), ("commit", _is_nonempty)),
    "merge": (("task", _is_nonempty), ("head", _is_nonempty)),
    "fail": (("task", _is_nonempty), ("reason", _is_str)),
    "stop": (("task", _is_nonempty), ("reason", _is_str), ("by", _one_of("user", "sdd"))),
    "skip": (("task", _is_nonempty), ("reason", _is_str)),
    "supersede": (("task", _is_nonempty), ("round", _matches(_ROUND_RE)), ("reason", _is_str)),
    "hold": (("task", _is_nonempty), ("round", _matches(_ROUND_RE))),
    "task-add": (("round", _matches(_ROUND_RE)),),
    "round-open": (("round", _matches(_ROUND_RE)), ("round_kind", _one_of("checkpoint", "final")),
                   ("title", _is_nonempty)),
    "round-close": (("round", _matches(_ROUND_RE)), ("outcome", _one_of("clean", "fixes", "blocked"))),
    "question": (("question", _matches(_QUESTION_ID_RE)),),
    "answered": (("question", _matches(_QUESTION_ID_RE)), ("source", _one_of(*_SOURCES))),
    "action": (("seq", _is_int), ("outcome", _one_of("applied", "declined"))),
    "run-end": (("outcome", _one_of("clean", "blocked", "stopped")),),
}
_OPTIONAL_REPORT_FIELDS: dict[str, tuple[tuple[str, Callable[[Any], bool]], ...]] = {
    "question": (("task", _is_nonempty),),
    "action": (("reason", _is_str),),
    "run-end": (("next_step", _one_of("merge", "pr", "keep")),),
}


def _validate_report(report: Any, known: set[str] | None) -> None:
    """Validate a report from SDD. ``known`` is the set of task ids, or None to skip membership checks."""
    if not isinstance(report, dict):
        raise RunError("report")
    for assigned in ("n", "at"):
        if assigned in report:
            raise RunError(assigned)
    kind = report.get("kind")
    if not isinstance(kind, str) or kind not in _REPORT_FIELDS:
        raise RunError("kind")
    for name, ok in _REPORT_FIELDS[kind]:
        if name not in report or not ok(report[name]):
            raise RunError(name)
    for name, ok in _OPTIONAL_REPORT_FIELDS.get(kind, ()):
        if name in report and not ok(report[name]):
            raise RunError(name)
    if kind != "task-add" and "task" in report:
        # kinds that do not require task still carry one; a non-string would be unhashable below
        if not isinstance(report["task"], str):
            raise RunError("task")
        if known is not None and report["task"] not in known:
            raise RunError("task")
    if kind == "task-add":
        _validate_task(report.get("task"), "task", known)
        if known is not None and report["task"]["id"] in known:
            raise RunError("task.id")
    elif kind == "round-open":
        _check_id_list(report.get("covers"), "covers", known)
    elif kind == "round-close":
        _validate_findings(report.get("findings"), "findings")


def _validate_question(q: Any, known: set[str]) -> None:
    if not isinstance(q, dict):
        raise RunError("question")
    for key in q:
        if key not in _QUESTION_KEYS:
            raise RunError(str(key))
    if not _matches(_QUESTION_ID_RE)(q.get("id")):
        raise RunError("id")
    if not _is_nonempty(q.get("prompt")):
        raise RunError("prompt")
    if "task" in q and not (isinstance(q["task"], str) and q["task"] in known):
        raise RunError("task")
    if "header" in q and not _is_str(q["header"]):
        raise RunError("header")
    options = q.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 6:
        raise RunError("options")
    values: set[str] = set()
    for i, opt in enumerate(options):
        p = f"options[{i}]"
        if not isinstance(opt, dict):
            raise RunError(p)
        for key in opt:
            if key not in _OPTION_KEYS:
                raise RunError(f"{p}.{key}")
        if not _is_nonempty(opt.get("value")) or opt["value"] in values:
            raise RunError(f"{p}.value")
        values.add(opt["value"])
        if not _is_nonempty(opt.get("label")):
            raise RunError(f"{p}.label")
        if "description" in opt and not _is_str(opt["description"]):
            raise RunError(f"{p}.description")
    for key in ("recommended", "default"):
        if key in q and not (_is_str(q[key]) and q[key] in values):
            raise RunError(key)


def branch_slug(branch: str) -> str:
    """The branch with every run of characters outside ``[A-Za-z0-9._-]`` replaced by ``-``."""
    return _BRANCH_SLUG_RE.sub("-", branch)


# ---- store --------------------------------------------------------------------


class RunStore:
    """One session's SDD run on disk; safe across threads and processes via the shared app lock."""

    def __init__(self, session: os.PathLike, app: AppState | None = None):
        self._session = Path(os.path.abspath(session))
        self._app = app if app is not None else AppState(self._session)
        self._root = self._session / "state"
        self._dir = self._root / "run"

    # ---- raw file helpers ----------------------------------------------------

    def _read_json(self, name: str, default: Any) -> Any:
        try:
            return json.loads((self._dir / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default

    def _write_json(self, name: str, value: Any) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self._dir / name, json.dumps(value, ensure_ascii=False))

    def _read_reports(self) -> list[dict]:
        try:
            raw = (self._dir / "reports.jsonl").read_bytes()
        except FileNotFoundError:
            return []
        out: list[dict] = []
        for chunk in raw.split(b"\n"):
            if not chunk.strip():
                continue
            try:
                item = json.loads(chunk.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(item, dict):
                out.append(item)
        return out

    def _append_report(self, report: dict) -> dict:
        """Number, stamp and append ``report``; the caller holds the app lock."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / "reports.jsonl"
        n = max((r.get("n", 0) for r in self._read_reports() if _is_int(r.get("n"))), default=0) + 1
        entry = {"n": n, "at": time.time(), **report}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        try:
            torn = path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
        except FileNotFoundError:
            torn = False
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(("\n" if torn else "") + line)
            fh.flush()
            os.fsync(fh.fileno())
        return entry

    def _known_tasks(self) -> set[str] | None:
        """Task ids from RUN.json plus accepted fix tasks; None when no run is registered."""
        run = self._read_json("run.json", None)
        if run is None:
            return None
        ids = {t["id"] for t in run.get("tasks", [])}
        for r in self._read_reports():
            if r.get("kind") == "task-add" and isinstance(r.get("task"), dict):
                ids.add(r["task"].get("id"))
        return ids

    # ---- run -----------------------------------------------------------------

    def start(self, run: dict) -> dict:
        """Register the run, or resume it when ``run_id`` matches the stored one.

        A different ``run_id`` deletes ``state/run/`` first. A resume keeps every report; the
        stored task list may only be replaced when it is empty (preflight registration), otherwise
        the ids must match. Also writes the ``<repo>/.quirk/sdd/<branch-slug>.json`` pointer so a
        later session can find this run.
        """
        _validate_run(run)
        with self._app.lock():
            stored = self._read_json("run.json", None)
            resumed = stored is not None and stored.get("run_id") == run["run_id"]
            if resumed:
                old_ids = {t["id"] for t in stored.get("tasks", [])}
                if old_ids and old_ids != {t["id"] for t in run["tasks"]}:
                    raise RunError("tasks")
            elif self._dir.exists():
                shutil.rmtree(self._dir)
            self._write_json("run.json", run)
            sdd = Path(run["repo"]) / ".quirk" / "sdd"
            ensure_self_ignoring(sdd)
            atomic_write(
                sdd / f"{branch_slug(run['branch'])}.json",
                json.dumps({"session": str(self._session), "run_id": run["run_id"]}),
            )
            self._app.bump_rev()
            return {"run": run["run_id"], "resumed": resumed}

    def run(self) -> dict | None:
        """The stored RUN.json, or None when no run is registered."""
        return self._read_json("run.json", None)

    # ---- reports -------------------------------------------------------------

    def report(self, report: dict, *, wait_s: float = 1.0) -> dict:
        """Append an SDD report; returns ``{"n"}``, or ``{"dropped": reason}`` instead of blocking.

        Raises ``RunError`` for invalid input (``"run"`` when no run is registered). Opens
        ``state/app.lock`` on its own descriptor and gives up after ``wait_s``, so it must only be
        called from a process that does not already hold ``AppState.lock()``.
        """
        _validate_report(report, None)
        try:
            fd = os.open(self._root / "app.lock", os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as e:
            return {"dropped": str(e)}
        try:
            deadline = time.monotonic() + wait_s
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        return {"dropped": "lock-busy"}
                    time.sleep(_LOCK_POLL_S)
                except OSError as e:
                    return {"dropped": str(e)}
            try:
                known = self._known_tasks()
                if known is None:
                    raise RunError("run")
                _validate_report(report, known)
                entry = self._append_report(report)
                self._app._tick()
                return {"n": entry["n"]}
            except OSError as e:
                return {"dropped": str(e)}
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def reports(self) -> list[dict]:
        return self._read_reports()

    def last_report_at(self) -> float | None:
        ats = [r["at"] for r in self._read_reports() if isinstance(r.get("at"), (int, float))]
        return max(ats, default=None)

    # ---- questions -----------------------------------------------------------

    def ask(self, question: dict) -> dict:
        """Store ``question`` open and append its ``question`` report.

        ``fallback`` is true when the tab has not checked in within ``TAB_FALLBACK_AFTER_S``, so the
        caller should also post the question to orca ask. Question ids are never reused.
        """
        with self._app.lock():
            known = self._known_tasks()
            if known is None:
                raise RunError("run")
            _validate_question(question, known)
            questions = self._read_json("questions.json", [])
            if any(q["id"] == question["id"] for q in questions):
                raise RunError("id")
            questions.append({**question, "asked_at": time.time(), "state": "open"})
            self._write_json("questions.json", questions)
            report: dict[str, Any] = {"kind": "question", "question": question["id"]}
            if "task" in question:
                report["task"] = question["task"]
            self._append_report(report)
            self._app.bump_rev()
            seen = self.tab_seen_ago()
            return {
                "question": question["id"],
                "tab_seen_ago": seen,
                "fallback": seen is None or seen > TAB_FALLBACK_AFTER_S,
            }

    def questions(self) -> list[dict]:
        return self._read_json("questions.json", [])

    def answer(
        self, qid: str, source: str, pick: str | None = None, text: str | None = None
    ) -> tuple[dict, bool]:
        """Record the first answer to ``qid``; returns ``(Answer, recorded)``.

        ``recorded`` is False when the question was already answered, in which case the winning
        Answer is returned and nothing changes. Exactly one of ``pick`` (an option value) or
        ``text`` must be given.
        """
        if source not in _SOURCES:
            raise RunError("source")
        if (pick is None) == (text is None):
            raise RunError("pick")
        if text is not None and not _is_nonempty(text):
            raise RunError("text")
        with self._app.lock():
            questions = self._read_json("questions.json", [])
            q = next((x for x in questions if x["id"] == qid), None)
            if q is None:
                raise RunError("question")
            label = None
            if pick is not None:
                label = next((o["label"] for o in q["options"] if o["value"] == pick), None)
                if label is None:
                    raise RunError("pick")
            if q["state"] == "answered":
                return q["answer"], False
            answer: dict[str, Any] = {"question": qid, "source": source}
            if pick is not None:
                answer["pick"] = pick
                answer["label"] = label
            else:
                answer["text"] = text
            answer["at"] = time.time()
            q["state"] = "answered"
            q["answer"] = answer
            self._write_json("questions.json", questions)
            self._append_report({"kind": "answered", "question": qid, "source": source})
            self._app.bump_rev()
            return answer, True

    # ---- tab check-ins -------------------------------------------------------

    def touch_tab(self, now: float | None = None) -> None:
        """Record that the tab is alive; writes at most once per ``TAB_TOUCH_INTERVAL_S``."""
        now = time.time() if now is None else now
        with self._app.lock():
            last = self._read_tab_seen()
            if last is not None and 0 <= now - last < TAB_TOUCH_INTERVAL_S:
                return
            self._dir.mkdir(parents=True, exist_ok=True)
            atomic_write(self._dir / "tab-seen", repr(float(now)))

    def _read_tab_seen(self) -> float | None:
        try:
            return float((self._dir / "tab-seen").read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return None

    def tab_seen_ago(self, now: float | None = None) -> float | None:
        """Seconds since the last tab check-in, or None when the tab never checked in."""
        last = self._read_tab_seen()
        if last is None:
            return None
        now = time.time() if now is None else now
        return max(0.0, now - last)

    # ---- git facts -----------------------------------------------------------

    def git_facts(self) -> dict | None:
        """The stored git facts, or None when there are none or they were written for another run."""
        facts = self._read_json("git.json", None)
        if not isinstance(facts, dict):
            return None
        stored = self._read_json("run.json", None)
        if stored is not None and "run_id" in facts and facts["run_id"] != stored.get("run_id"):
            return None
        return facts

    def write_git_facts(self, facts: dict, run_id: str | None = None) -> bool:
        """Replace ``state/run/git.json``; called by the git watcher only when facts changed.

        The facts are stamped with ``run_id`` and written only while that run is still the stored
        one, so a watcher that loaded an old run cannot write over its replacement. Returns whether
        the facts were written.
        """
        if not isinstance(facts, dict):
            raise RunError("facts")
        with self._app.lock():
            stored = self._read_json("run.json", None)
            if run_id is not None and (stored is None or stored.get("run_id") != run_id):
                return False
            self._write_json("git.json", {**facts, "run_id": run_id} if run_id is not None else facts)
            self._app.bump_rev()
            return True
