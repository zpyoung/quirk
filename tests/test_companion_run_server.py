"""Tests for the companion server's run view: the run subcommands, the run HTTP routes and the idle rule.

Servers run as foreground subprocesses on 127.0.0.1 port 0 and are always stopped in teardown. The
shell is a tiny fixture selected with QUIRK_COMPANION_SHELL, and repos are real temp git repos.
"""
from __future__ import annotations

import http.client
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
CLI = SKILL / "scripts" / "companion.py"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit.appstate import AppState  # noqa: E402

BOOT_PLACEHOLDER = '<script type="application/json" id="quirk-companion-boot">null</script>'
SHELL = f"<!doctype html><html><body><div id=root></div>{BOOT_PLACEHOLDER}</body></html>"
TOKEN_HEADER = "X-Quirk-Token"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def run(*args: object, env: Optional[dict] = None, timeout: float = 60) -> tuple[int, dict, str]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )
    out = proc.stdout.strip()
    assert out.count("\n") == 0, f"stdout must be one JSON object: {proc.stdout!r}"
    return proc.returncode, json.loads(out), proc.stderr


class App:
    """A foreground app-mode companion server and the helpers the tests drive it with."""

    def __init__(self, session: Path, proc: subprocess.Popen, info: dict, root: Path, repo: Optional["Repo"]) -> None:
        self.session = session
        self.proc = proc
        self.info = info
        self.root = root
        self.repo = repo
        self.port = info["port"]

    @property
    def state(self) -> Path:
        return self.session / "state"

    @property
    def token(self) -> str:
        return (self.state / "token").read_text().strip()

    def cli(self, *args: object, expect: Optional[int] = 0) -> dict:
        rc, out, err = run(*args, env={"QUIRK_COMPANION_SHELL": str(self.root / "shell.html")})
        if expect is not None:
            assert rc == expect, (rc, out, err)
        return out

    def json_file(self, payload: object) -> Path:
        path = self.root / f"in-{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def run_start(self, doc: dict, expect: Optional[int] = 0) -> dict:
        return self.cli("run-start", self.session, self.json_file(doc), expect=expect)

    def report(self, payload: dict, expect: Optional[int] = 0) -> dict:
        return self.cli("report", self.session, json.dumps(payload), expect=expect)

    def ask(self, question: dict, expect: Optional[int] = 0) -> dict:
        return self.cli("ask", self.session, self.json_file(question), expect=expect)

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read(), resp
        finally:
            conn.close()

    def post(self, path: str, payload: dict | bytes, token: Optional[str] = "", headers: dict | None = None):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        if token is not None:
            hdrs[TOKEN_HEADER] = token or self.token
        status, data, _ = self.request("POST", path, body, hdrs)
        return status, data

    def event(self, type_: str, payload: object, client_id: Optional[str] = None, **kw):
        body: dict = {"client_id": client_id or uuid.uuid4().hex, "type": type_, "payload": payload}
        status, data = self.post("/_quirk/app/event", body, **kw)
        return status, (json.loads(data) if data else None)

    def snapshot(self, token: Optional[str] = "") -> dict:
        """The snapshot; sent with the session token (as the tab does) unless ``token`` is None."""
        headers = {} if token is None else {TOKEN_HEADER: token or self.token}
        status, data, _ = self.request("GET", "/_quirk/app/snapshot", headers=headers)
        assert status == 200
        return json.loads(data)

    def get_json(self, path: str) -> tuple[int, object]:
        status, data, _ = self.request("GET", path)
        return status, (json.loads(data) if status == 200 else None)

    def next(self, *extra: object, expect: Optional[int] = 0) -> dict:
        return self.cli("next", self.session, "--timeout", "3", *extra, expect=expect)

    def statuses(self) -> dict[str, str]:
        return {t["id"]: t["status"] for t in self.snapshot()["run"]["tasks"]}


def start_app(root: Path, session: Path, *extra: str, repo: Optional["Repo"] = None) -> App:
    root.mkdir(parents=True, exist_ok=True)
    (root / "shell.html").write_text(SHELL, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(session), "--app", "--foreground", "--port", "0", *extra],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "QUIRK_COMPANION_SHELL": str(root / "shell.html")},
    )
    line = proc.stdout.readline()
    assert line, proc.stderr.read()
    info = json.loads(line)
    assert info["type"] == "server-started"
    return App(session, proc, info, root, repo)


def stop_app(app: App) -> None:
    if app.proc.poll() is None:
        app.proc.send_signal(signal.SIGTERM)
        try:
            app.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            app.proc.kill()
            app.proc.wait()
    for stream in (app.proc.stdout, app.proc.stderr):
        if stream:
            stream.close()


def wait_for(predicate: Callable[[], object], timeout: float = 10.0, interval: float = 0.1) -> object:
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(interval)


def g(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


class Repo:
    """A real repo with a ``feat`` branch; ``task_branch`` forks and commits a task branch."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir(parents=True)
        g(path, "init", "-q", "-b", "main")
        (path / "README.md").write_text("hello\n")
        g(path, "add", "-A")
        g(path, "commit", "-q", "-m", "init")
        self.base = g(path, "rev-parse", "HEAD")
        g(path, "branch", "feat")

    def task_branch(self, tid: str, name: str, text: str) -> None:
        g(self.path, "checkout", "-q", "-b", f"sdd/r1/{tid}", "feat")
        (self.path / name).write_text(text)
        g(self.path, "add", "-A")
        g(self.path, "commit", "-q", "-m", f"{tid} work")
        g(self.path, "checkout", "-q", "main")


def tk(tid: str, deps: tuple[str, ...] = ()) -> dict:
    return {"id": tid, "title": f"Task {tid}", "deps": list(deps), "order_after": []}


def run_doc(repo: Repo, *tasks: dict, run_id: str = "r1") -> dict:
    return {
        "v": 1,
        "run_id": run_id,
        "repo": str(repo.path),
        "branch": "feat",
        "branch_pattern": "sdd/{run}/{task}",
        "base": repo.base,
        "tasks": list(tasks),
    }


def question(qid: str = "q-1", **extra: object) -> dict:
    return {
        "id": qid,
        "prompt": "Pick one",
        "options": [{"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"}],
        **extra,
    }


def dispatch(tid: str, attempt: int = 1) -> dict:
    return {"kind": "dispatch", "task": tid, "attempt": attempt, "branch": f"sdd/r1/{tid}",
            "worktree": f"/wt/{tid}", "base": "abc1234"}


def offline_session(session: Path) -> None:
    """An app-mode session with no server, as SDD's preflight sees it before ``start``."""
    session.mkdir(parents=True)
    AppState(session).init()
    (session / "state" / "mode.json").write_text(json.dumps({"mode": "app"}), encoding="utf-8")


@pytest.fixture
def session(tmp_path: Path) -> Path:
    return tmp_path / ".quirk" / "sdd" / "s1"


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "repo")


@pytest.fixture
def app(tmp_path: Path, session: Path, repo: Repo):
    srv = start_app(tmp_path / "root", session, repo=repo)
    try:
        yield srv
    finally:
        stop_app(srv)


@pytest.fixture
def mixed(app: App, repo: Repo) -> App:
    """T1 running, T2 passed, T3 failed."""
    app.run_start(run_doc(repo, tk("T1"), tk("T2"), tk("T3")))
    app.report(dispatch("T1"))
    app.report(dispatch("T2"))
    app.report({"kind": "commit", "task": "T2", "commit": "c" * 40})
    app.report(dispatch("T3"))
    app.report({"kind": "fail", "task": "T3", "reason": "tests red"})
    assert app.statuses() == {"T1": "running", "T2": "passed", "T3": "failed"}
    return app


# ---- run-start ---------------------------------------------------------------------------------


def test_run_start_preflight_then_plan_resumes_the_run(app: App, repo: Repo) -> None:
    first = app.run_start(run_doc(repo))
    assert first == {"run": "r1", "resumed": False, "url": app.info["url"]}
    app.report({"kind": "status", "text": "preflight"})
    second = app.run_start(run_doc(repo, tk("T1"), tk("T2", ("T1",))))
    assert second == {"run": "r1", "resumed": True, "url": app.info["url"]}
    run_view = app.snapshot()["run"]
    assert [t["id"] for t in run_view["tasks"]] == ["T1", "T2"]
    assert run_view["status_text"] == "preflight"


def test_run_start_with_a_new_run_id_resets_the_run(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.report({"kind": "status", "text": "old"})
    out = app.run_start(run_doc(repo, tk("T9"), run_id="r2"))
    assert out["resumed"] is False
    run_view = app.snapshot()["run"]
    assert run_view["run_id"] == "r2"
    assert run_view.get("status_text") is None
    assert [t["id"] for t in run_view["tasks"]] == ["T9"]
    assert app.report({"kind": "status", "text": "new"}) == {"n": 1}


def test_run_start_url_is_null_without_a_server(tmp_path: Path, session: Path, repo: Repo) -> None:
    offline_session(session)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run_doc(repo, tk("T1"))))
    rc, out, _ = run("run-start", session, path)
    assert (rc, out) == (0, {"run": "r1", "resumed": False, "url": None})


def test_run_start_rejects_an_invalid_run_with_its_field(app: App, repo: Repo) -> None:
    doc = run_doc(repo, tk("T1"))
    doc["tasks"][0]["deps"] = ["nope"]
    out = app.run_start(doc, expect=2)
    assert out["field"] == "tasks[0].deps"


def test_run_start_makes_an_sdd_session_parent_self_ignoring(app: App) -> None:
    assert (app.session.parent / ".gitignore").read_text() == "*\n"


# ---- report ------------------------------------------------------------------------------------


def test_report_returns_its_number(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    assert app.report({"kind": "status", "text": "one"}) == {"n": 1}
    assert app.report(dispatch("T1")) == {"n": 2}


def test_report_reads_a_file(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    path = app.json_file({"kind": "status", "text": "from a file"})
    assert app.cli("report", app.session, "--file", path) == {"n": 1}


def test_report_invalid_exits_2_with_the_field(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    assert app.report({"kind": "dispatch", "task": "T9", "attempt": 1, "branch": "b", "worktree": "/w",
                       "base": "x"}, expect=2)["field"] == "task"
    assert app.report({"kind": "nonsense"}, expect=2)["field"] == "kind"
    assert app.report({"kind": "status"}, expect=2)["field"] == "text"


def test_report_needs_exactly_one_input(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    path = app.json_file({"kind": "status", "text": "x"})
    assert "error" in app.cli("report", app.session, expect=2)
    assert "error" in app.cli("report", app.session, "{}", "--file", path, expect=2)
    assert "error" in app.cli("report", app.session, "not json", expect=2)


def test_report_without_a_run_exits_2(app: App) -> None:
    out = app.report({"kind": "status", "text": "x"}, expect=2)
    assert out["error"] == "no run"


@pytest.mark.parametrize(
    "args",
    [
        ("run-start", "RUN"),
        ("report", '{"kind": "status", "text": "x"}'),
        ("ask", "RUN"),
        ("await", "q-1"),
        ("answer", "q-1", "--source", "sdd", "--pick", "a"),
    ],
)
def test_run_commands_refuse_a_session_that_is_not_in_app_mode(tmp_path: Path, args: tuple) -> None:
    session = tmp_path / "screen"
    (session / "state").mkdir(parents=True)
    argv = [str(tmp_path / "x.json") if a == "RUN" else a for a in args]
    rc, out, _ = run(argv[0], session, *argv[1:])
    assert (rc, out) == (2, {"error": "session is not in app mode"})


# ---- ask, await, answer ------------------------------------------------------------------------


def test_ask_falls_back_until_the_tab_checks_in(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    first = app.ask(question("q-1", task="T1"))
    assert first["question"] == "q-1" and first["tab_seen_ago"] is None and first["fallback"] is True
    app.snapshot()
    second = app.ask(question("q-2"))
    assert second["fallback"] is False
    assert 0 <= second["tab_seen_ago"] < 5


def test_ask_rejects_a_bad_question(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    assert app.ask({"id": "q-1", "prompt": "p", "options": []}, expect=2)["field"] == "options"
    app.ask(question("q-1"))
    assert app.ask(question("q-1"), expect=2)["field"] == "id"


def test_answer_first_by_cli_then_tab_gets_409(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    won = app.cli("answer", app.session, "q-1", "--source", "orca", "--pick", "a")
    assert won["answered"]["source"] == "orca" and won["answered"]["label"] == "Alpha"
    status, body = app.event("run-answer", {"question": "q-1", "pick": "b"})
    assert status == 409
    assert body["answered"]["source"] == "orca" and body["answered"]["pick"] == "a"
    late = app.cli("answer", app.session, "q-1", "--source", "sdd", "--pick", "b", expect=1)
    assert late["already"] is True and late["answered"]["source"] == "orca"


def test_answer_first_by_tab_then_cli_is_already(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    status, body = app.event("run-answer", {"question": "q-1", "pick": "b"})
    assert (status, body) == (204, None)
    late = app.cli("answer", app.session, "q-1", "--source", "orca", "--pick", "a", expect=1)
    assert late["already"] is True
    assert late["answered"]["source"] == "tab" and late["answered"]["pick"] == "b"
    delivered = app.next()["events"]
    assert [(e["type"], e["step"], e["payload"]) for e in delivered] == [
        ("run-answer", None, {"question": "q-1", "pick": "b", "run_id": "r1"})
    ]


def test_answer_accepts_free_text_from_the_tab(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    assert app.event("run-answer", {"question": "q-1", "text": "something else"})[0] == 204
    answer = app.snapshot()["run"]["questions"][0]["answer"]
    assert answer["source"] == "tab" and answer["text"] == "something else"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "nope", "pick": "a"},
        {"question": "q-1", "pick": "zzz"},
        {"question": "q-1", "pick": "a", "text": "both"},
        {"question": "q-1"},
        {"question": "q-1", "pick": 5},
        {"question": "q-1", "text": ""},
        {"question": ["q-1"], "pick": "a"},
        {"pick": "a"},
    ],
)
def test_run_answer_rejects_a_bad_payload_with_400(app: App, repo: Repo, payload: dict) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    status, body = app.event("run-answer", payload)
    assert status == 400 and "error" in body
    assert app.snapshot()["run"]["questions"][0]["state"] == "open"
    assert app.event("run-answer", {"question": "q-1", "pick": "a"})[0] == 204


def test_run_events_without_a_run_are_400(app: App) -> None:
    for type_, payload in (
        ("run-answer", {"question": "q-1", "pick": "a"}),
        ("run-stop", {"task": "T1"}),
        ("run-retry", {"task": "T1"}),
    ):
        assert app.event(type_, payload) == (400, {"error": "no run"})


def test_await_returns_an_answer_already_given(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    app.cli("answer", app.session, "q-1", "--source", "sdd", "--text", "go")
    out = app.cli("await", app.session, "q-1", "--timeout", "5")
    assert out["answered"]["source"] == "sdd" and out["answered"]["text"] == "go"


def test_await_wakes_when_the_tab_answers(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    waiter = subprocess.Popen(
        [sys.executable, str(CLI), "await", str(app.session), "q-1", "--timeout", "10"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.5)
        assert app.event("run-answer", {"question": "q-1", "pick": "b"})[0] == 204
        out, _ = waiter.communicate(timeout=10)
    finally:
        if waiter.poll() is None:
            waiter.kill()
            waiter.communicate()
    assert waiter.returncode == 0
    assert json.loads(out)["answered"]["source"] == "tab"


def test_await_reports_tab_quiet_when_no_tab_polls(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    started = time.monotonic()
    out = app.cli("await", app.session, "q-1", "--quiet-after", "0.5", "--timeout", "30", expect=1)
    assert out == {"status": "tab-quiet"}
    assert time.monotonic() - started < 10


def test_await_does_not_go_quiet_while_the_tab_polls_or_when_disabled(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    app.snapshot()
    out = app.cli("await", app.session, "q-1", "--quiet-after", "60", "--timeout", "1", expect=1)
    assert out == {"status": "timeout"}
    out = app.cli("await", app.session, "q-1", "--quiet-after", "0", "--timeout", "1", expect=1)
    assert out == {"status": "timeout"}


def test_await_of_an_unknown_question_exits_2(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    assert app.cli("await", app.session, "nope", "--timeout", "1", expect=2)["field"] == "question"


def test_await_reports_no_server_after_stop(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    stop_app(app)
    assert app.cli("await", app.session, "q-1", "--timeout", "5", expect=2) == {"status": "no-server"}


# ---- run-stop and run-retry --------------------------------------------------------------------


def test_run_stop_requires_the_token(mixed: App) -> None:
    status, _ = mixed.event("run-stop", {"task": "T1"}, token=None)
    assert status == 403
    status, _ = mixed.event("run-stop", {"task": "T1"}, token="wrong")
    assert status == 403
    assert mixed.next("--after", "0", expect=1)["status"] == "timeout"


def test_run_stop_is_refused_for_a_passed_task(mixed: App) -> None:
    assert mixed.event("run-stop", {"task": "T2"}) == (409, {"refused": "passed"})
    assert mixed.event("run-retry", {"task": "T2"}) == (409, {"refused": "passed"})


def test_run_stop_is_accepted_once_then_duplicate_and_reaches_next(mixed: App) -> None:
    status, body = mixed.event("run-stop", {"task": "T1"}, client_id="c1")
    assert (status, body) == (204, None)
    assert mixed.event("run-stop", {"task": "T1"}, client_id="c2") == (200, {"duplicate": True})
    assert mixed.event("run-stop", {"task": "T1"}, client_id="c1") == (200, {"duplicate": True})
    events = mixed.next()["events"]
    assert [(e["type"], e["step"], e["payload"], e["client_id"]) for e in events] == [
        ("run-stop", None, {"task": "T1", "run_id": "r1"}, "c1")
    ]
    task = next(t for t in mixed.snapshot()["run"]["tasks"] if t["id"] == "T1")
    assert task["pending_action"] == "stop"


def test_an_old_runs_pending_action_does_not_block_a_new_run(mixed: App, repo: Repo) -> None:
    assert mixed.event("run-stop", {"task": "T1"}, client_id="old")[0] == 204
    mixed.run_start(run_doc(repo, tk("T1"), tk("T2"), tk("T3"), run_id="r2"))
    mixed.report(dispatch("T1"))
    task = next(t for t in mixed.snapshot()["run"]["tasks"] if t["id"] == "T1")
    assert task["status"] == "running" and "pending_action" not in task
    assert mixed.event("run-stop", {"task": "T1"}, client_id="new")[0] == 204
    events = mixed.next("--after", "0")["events"]
    assert [(e["client_id"], e["payload"]["run_id"]) for e in events] == [("old", "r1"), ("new", "r2")]
    task = next(t for t in mixed.snapshot()["run"]["tasks"] if t["id"] == "T1")
    assert task["pending_action"] == "stop"


def test_run_stop_is_accepted_on_a_failed_task(mixed: App) -> None:
    assert mixed.event("run-stop", {"task": "T3"})[0] == 204


def test_run_retry_is_only_for_a_failed_task(mixed: App) -> None:
    assert mixed.event("run-retry", {"task": "T1"}) == (409, {"refused": "running"})
    assert mixed.event("run-retry", {"task": "T3"}, client_id="r1")[0] == 204
    assert mixed.event("run-retry", {"task": "T3"}, client_id="r2") == (200, {"duplicate": True})
    task = next(t for t in mixed.snapshot()["run"]["tasks"] if t["id"] == "T3")
    assert task["pending_action"] == "retry"


@pytest.mark.parametrize("payload", [{}, {"task": ["T1"]}, {"task": 3}, {"task": ""}, {"task": "NOPE"}])
@pytest.mark.parametrize("type_", ["run-stop", "run-retry"])
def test_run_stop_and_retry_reject_a_bad_payload_with_400(mixed: App, type_: str, payload: dict) -> None:
    status, body = mixed.event(type_, payload)
    assert status == 400 and "error" in body
    assert mixed.snapshot()["run"] is not None


# ---- snapshot ----------------------------------------------------------------------------------


def test_snapshot_run_is_null_without_a_run_and_set_with_one(app: App, repo: Repo) -> None:
    assert app.snapshot()["run"] is None
    assert app.cli("snapshot", app.session)["run"] is None
    app.run_start(run_doc(repo, tk("T1")))
    snap = app.snapshot()
    assert snap["run"]["run_id"] == "r1"
    assert app.cli("snapshot", app.session)["run"]["run_id"] == "r1"


def test_snapshot_survives_an_unreadable_run(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    (app.state / "run" / "run.json").write_text("{not json", encoding="utf-8")
    assert app.snapshot()["run"] is None
    assert app.cli("snapshot", app.session)["run"] is None


def test_snapshot_204_on_an_unchanged_rev_survives_reports_and_tab_polls(
    tmp_path: Path, session: Path, repo: Repo
) -> None:
    offline_session(session)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run_doc(repo, tk("T1"))))
    run("run-start", session, path)
    srv = start_app(tmp_path / "root", session, repo=repo)
    try:
        # the watcher's first poll writes git.json and moves rev once; wait it out
        wait_for(lambda: (srv.state / "run" / "git.json").exists())
        rev = srv.snapshot()["rev"]
        for _ in range(3):
            assert srv.request("GET", f"/_quirk/app/snapshot?rev={rev}")[0] == 204
        srv.report({"kind": "status", "text": "gate 1"})
        status, data, _ = srv.request("GET", f"/_quirk/app/snapshot?rev={rev}")
        assert status == 200
        body = json.loads(data)
        assert body["rev"] > rev and body["run"]["status_text"] == "gate 1"
        assert srv.request("GET", f"/_quirk/app/snapshot?rev={body['rev']}")[0] == 204
    finally:
        stop_app(srv)


def test_snapshot_get_counts_as_a_tab_check_in_even_on_204(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    rev = app.snapshot()["rev"]
    assert (app.state / "run" / "tab-seen").exists()
    (app.state / "run" / "tab-seen").unlink()
    headers = {TOKEN_HEADER: app.token}
    assert app.request("GET", f"/_quirk/app/snapshot?rev={rev}", headers=headers)[0] in (200, 204)
    assert (app.state / "run" / "tab-seen").exists()


def test_a_snapshot_get_without_the_token_does_not_count_as_a_tab_check_in(app: App, repo: Repo) -> None:
    app.run_start(run_doc(repo, tk("T1")))
    app.ask(question("q-1"))
    assert app.snapshot(token=None)["run"] is not None
    assert not (app.state / "run" / "tab-seen").exists()
    app.snapshot(token="wrong")
    assert not (app.state / "run" / "tab-seen").exists()
    app.snapshot()
    assert (app.state / "run" / "tab-seen").exists()
    out = app.cli("await", app.session, "q-1", "--quiet-after", "60", "--timeout", "1", expect=1)
    assert out == {"status": "timeout"}


# ---- diff route --------------------------------------------------------------------------------


def test_diff_returns_a_committed_task(app: App, repo: Repo) -> None:
    repo.task_branch("T1", "a.txt", "alpha\n")
    app.run_start(run_doc(repo, tk("T1"), tk("T2")))
    status, body = app.get_json("/_quirk/run/diff?task=T1")
    assert status == 200
    assert body["task"] == "T1" and body["source"] == "commit" and body["truncated"] is False
    assert [f["path"] for f in body["files"]] == ["a.txt"]
    assert body["files"][0]["status"] == "added" and "+alpha" in body["files"][0]["patch"]


def test_diff_is_404_for_an_unknown_task_a_branchless_task_or_no_run(app: App, repo: Repo) -> None:
    assert app.get_json("/_quirk/run/diff?task=T1")[0] == 404
    repo.task_branch("T1", "a.txt", "alpha\n")
    app.run_start(run_doc(repo, tk("T1"), tk("T2")))
    assert app.get_json("/_quirk/run/diff?task=NOPE")[0] == 404
    assert app.get_json("/_quirk/run/diff?task=T2")[0] == 404
    assert app.get_json("/_quirk/run/diff")[0] == 404


def test_diff_keeps_the_host_guard(app: App, repo: Repo) -> None:
    repo.task_branch("T1", "a.txt", "alpha\n")
    app.run_start(run_doc(repo, tk("T1")))
    status, _, _ = app.request("GET", "/_quirk/run/diff?task=T1", headers={"Host": "evil.test"})
    assert status == 403


def test_diff_route_does_not_exist_in_screen_mode(tmp_path: Path) -> None:
    session = tmp_path / "scr"
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(session), "--foreground", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        info = json.loads(proc.stdout.readline())
        conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=10)
        conn.request("GET", "/_quirk/run/diff?task=T1")
        assert conn.getresponse().status == 404
        conn.close()
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        proc.stdout.close()
        proc.stderr.close()


# ---- watcher and idle --------------------------------------------------------------------------


def test_the_server_watches_git_into_the_run_view(tmp_path: Path, session: Path, repo: Repo) -> None:
    repo.task_branch("T1", "a.txt", "alpha\n")
    offline_session(session)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run_doc(repo, tk("T1"), tk("T2"))))
    run("run-start", session, path)
    srv = start_app(tmp_path / "root", session, repo=repo)
    try:
        wait_for(lambda: (srv.state / "run" / "git.json").exists())
        facts = json.loads((srv.state / "run" / "git.json").read_text())
        assert facts["tasks"]["T1"]["commits"] == 1 and "T2" not in facts["tasks"]
        task = next(t for t in srv.snapshot()["run"]["tasks"] if t["id"] == "T1")
        assert task["status"] == "passed" and task["files"] == 1
    finally:
        stop_app(srv)


def test_a_server_with_no_run_stops_when_idle(tmp_path: Path, session: Path) -> None:
    srv = start_app(tmp_path / "root", session, "--idle-minutes", "0.01")
    try:
        assert srv.proc.wait(timeout=10) == 0
        assert json.loads((srv.state / "server-stopped").read_text())["reason"] == "idle"
    finally:
        stop_app(srv)


def test_a_registered_run_keeps_the_server_up_past_the_idle_limit(tmp_path: Path, session: Path, repo: Repo) -> None:
    offline_session(session)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run_doc(repo, tk("T1"))))
    run("run-start", session, path)
    srv = start_app(tmp_path / "root", session, "--idle-minutes", "0.01", repo=repo)
    try:
        deadline = time.monotonic() + 2.0
        n = 0
        while time.monotonic() < deadline:
            n += 1
            srv.report({"kind": "status", "text": f"step {n}"})
            assert srv.proc.poll() is None
            time.sleep(0.2)
        assert n >= 3
        srv.report({"kind": "run-end", "outcome": "clean"})
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            assert srv.proc.poll() is None
            time.sleep(0.1)
    finally:
        stop_app(srv)
