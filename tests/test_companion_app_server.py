"""Tests for the companion server's app mode: the new subcommands, the app HTTP routes and restart.

Servers run as foreground subprocesses on 127.0.0.1 port 0 and are always stopped in teardown. The
shell is a tiny fixture written into the test's tmp dir and selected with QUIRK_COMPANION_SHELL.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
CLI = SKILL / "scripts" / "companion.py"

BOOT_PLACEHOLDER = '<script type="application/json" id="quirk-companion-boot">null</script>'
SHELL = f"<!doctype html><html><body><div id=root></div>{BOOT_PLACEHOLDER}</body></html>"
TOKEN_HEADER = "X-Quirk-Token"

QUESTIONS = {
    "v": 1,
    "kind": "questions",
    "stage": "questions",
    "title": "Scope",
    "questions": [
        {
            "id": "q1",
            "type": "single",
            "prompt": "Which storage?",
            "options": [{"id": "sql", "label": "SQL"}, {"id": "files", "label": "Files"}],
        },
        {"id": "q2", "type": "text", "prompt": "Anything else?"},
    ],
}
APPROACHES = {
    "v": 1,
    "kind": "approaches",
    "stage": "approaches",
    "title": "Approaches",
    "approaches": [
        {"id": "one", "title": "One", "summary_md": "first", "recommended": True},
        {"id": "two", "title": "Two", "summary_md": "second", "recommended": False},
    ],
}
DESIGN = {
    "v": 1,
    "kind": "design-section",
    "stage": "design",
    "title": "Design",
    "index": 1,
    "total": 2,
    "sections": [{"id": "s1", "title": "Data", "body_md": "text"}],
}
SPEC_MD = {
    "v": 1,
    "kind": "spec-review",
    "stage": "spec",
    "title": "Spec",
    "format": "markdown",
    "spec_path": "spec.md",
    "sections": [{"id": "s1", "title": "Goal", "body_md": "text"}],
}
SPEC_INTERACTIVE = {"v": 1, "kind": "spec-review", "stage": "spec", "title": "Spec", "format": "interactive"}
EDIT_CARD = {
    "v": 1,
    "kind": "edit-card",
    "stage": "design",
    "title": "Edit",
    "decision_id": "storage",
    "from": "SQL",
    "to": "Files",
    "invalidates": [],
    "origin": "rail",
}
HAND_OFF = {
    "v": 1,
    "kind": "hand-off",
    "stage": "hand-off",
    "title": "Next",
    "choices": [
        {"id": "plan", "label": "Plan", "description": "write a plan", "recommended": True},
        {"id": "stop", "label": "Stop", "description": "stop here", "recommended": False},
    ],
}
DONE = {"v": 1, "kind": "done", "stage": "hand-off", "title": "Done", "message_md": "bye"}
DECISION = {"id": "storage", "stage": "questions", "area": "Data", "label": "Storage", "value": "SQL", "status": "confirmed"}


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

    def __init__(self, session: Path, proc: subprocess.Popen, info: dict, root: Path) -> None:
        self.session = session
        self.proc = proc
        self.info = info
        self.root = root
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

    def step(self, spec: dict) -> dict:
        path = self.root / f"step-{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return self.cli("step", self.session, path)

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

    def event(
        self,
        type_: str,
        payload: dict,
        nonce: Optional[str] = None,
        client_id: Optional[str] = None,
        step: object = None,
        **kw,
    ):
        body: dict = {"client_id": client_id or uuid.uuid4().hex, "type": type_, "payload": payload}
        if nonce is not None:
            body["nonce"] = nonce
        if step is not None:
            body["step"] = step
        return self.post("/_quirk/app/event", body, **kw)

    def snapshot(self) -> dict:
        status, data, _ = self.request("GET", "/_quirk/app/snapshot")
        assert status == 200
        return json.loads(data)

    def next(self, *extra: object, expect: Optional[int] = 0) -> dict:
        return self.cli("next", self.session, "--timeout", "3", *extra, expect=expect)


def start_app(root: Path, session: Path, *extra: str, shell: Optional[str] = SHELL) -> App:
    root.mkdir(parents=True, exist_ok=True)
    if shell is not None:
        (root / "shell.html").write_text(shell, encoding="utf-8")
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
    return App(session, proc, info, root)


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


@pytest.fixture
def session(tmp_path: Path) -> Path:
    return tmp_path / ".quirk" / "brainstorm" / "s1"


@pytest.fixture
def app(tmp_path: Path, session: Path):
    srv = start_app(tmp_path / "root", session)
    try:
        yield srv
    finally:
        stop_app(srv)


# ---- start, mode marker and token -------------------------------------------------------------


def test_start_app_records_mode_in_server_info_and_mode_file(app: App) -> None:
    assert app.info["mode"] == "app"
    assert json.loads((app.state / "server-info").read_text()) == app.info
    assert json.loads((app.state / "mode.json").read_text()) == {"mode": "app"}


def test_screen_mode_server_info_has_no_mode_key(tmp_path: Path) -> None:
    session = tmp_path / "scr"
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(session), "--foreground", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        info = json.loads(proc.stdout.readline())
        assert "mode" not in info
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        proc.stdout.close()
        proc.stderr.close()


def test_token_file_is_0600_and_stable_across_restart(tmp_path: Path, session: Path) -> None:
    first = start_app(tmp_path / "root", session)
    try:
        token = first.token
        assert (first.state / "token").stat().st_mode & 0o777 == 0o600
        assert len(token) >= 24
    finally:
        stop_app(first)
    second = start_app(tmp_path / "root", session)
    try:
        assert second.token == token
        assert (second.state / "token").stat().st_mode & 0o777 == 0o600
    finally:
        stop_app(second)


def test_restart_reuses_state_and_the_same_port_when_free(tmp_path: Path, session: Path) -> None:
    first = start_app(tmp_path / "root", session)
    try:
        step = first.step(QUESTIONS)
        port = first.port
    finally:
        stop_app(first)
    second = start_app(tmp_path / "root", session)
    try:
        assert second.port == port
        snap = second.snapshot()
        assert snap["step"]["id"] == step["step"] and snap["step"]["nonce"] == step["nonce"]
    finally:
        stop_app(second)


def test_restart_falls_back_when_the_previous_port_is_taken(tmp_path: Path, session: Path) -> None:
    import socket

    first = start_app(tmp_path / "root", session)
    port = first.port
    stop_app(first)
    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        second = start_app(tmp_path / "root", session)
        try:
            assert second.port != port
            assert second.info["url"] == f"http://127.0.0.1:{second.port}/"
        finally:
            stop_app(second)
    finally:
        blocker.close()


def test_background_start_app_returns_mode_and_stop_works(tmp_path: Path, session: Path) -> None:
    rc, info, err = run("start", session, "--app")
    try:
        assert rc == 0 and info["mode"] == "app", (info, err)
    finally:
        run("stop", session)
    rc, stopped, _ = run("stop", session)
    assert rc == 0 and stopped == {"stopped": False}


# ---- mode mismatch ------------------------------------------------------------------------------


def test_app_subcommands_on_a_screen_session_exit_2(tmp_path: Path) -> None:
    session = tmp_path / "screen-session"
    (session / "state").mkdir(parents=True)
    step = tmp_path / "s.json"
    step.write_text(json.dumps(QUESTIONS))
    decisions = tmp_path / "d.json"
    decisions.write_text("[]")
    review = tmp_path / "r.html"
    review.write_text("<p>r</p>")
    for args in (
        ("step", session, step),
        ("status", session, "--text", "hi"),
        ("decide", session, decisions),
        ("review", session, review),
        ("next", session, "--timeout", "0.2"),
        ("snapshot", session),
    ):
        rc, out, _ = run(*args)
        assert rc == 2 and out == {"error": "session is not in app mode"}, args


def test_screen_subcommands_on_an_app_session_exit_2(app: App, tmp_path: Path) -> None:
    screen = tmp_path / "screen.json"
    screen.write_text("{}")
    for args in (("show", app.session, screen), ("wait", app.session, "--timeout", "0.2"), ("events", app.session)):
        rc, out, _ = run(*args)
        assert rc == 2 and out == {"error": "session is in app mode"}, args


def test_start_without_app_on_an_app_session_exits_2(app: App) -> None:
    stop_app(app)
    rc, out, _ = run("start", app.session)
    assert rc == 2 and "app mode" in out["error"]


def test_start_without_app_on_a_live_app_server_exits_2(app: App) -> None:
    rc, out, _ = run("start", app.session)
    assert rc == 2 and "error" in out


def test_start_app_on_a_live_screen_server_exits_2(tmp_path: Path) -> None:
    session = tmp_path / "live-screen"
    rc, info, _ = run("start", session)
    try:
        assert rc == 0 and "mode" not in info
        rc, out, _ = run("start", session, "--app")
        assert rc == 2 and "error" in out
        assert not (session / "state" / "mode.json").exists()
    finally:
        run("stop", session)


def test_start_app_on_a_stopped_screen_session_exits_2_and_writes_nothing(tmp_path: Path) -> None:
    session = tmp_path / "stopped-screen"
    assert run("start", session)[0] == 0
    spec = tmp_path / "screen.json"
    spec.write_text(json.dumps({"title": "Layout", "question": "Which?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}))
    rc, shown, _ = run("show", session, spec, "--project-dir", tmp_path)
    assert rc == 0, shown
    assert run("stop", session)[0] == 0
    rc, out, _ = run("start", session, "--app")
    assert rc == 2 and out == {"error": "session is a screen-mode session"}
    assert not (session / "state" / "mode.json").exists()
    assert not (session / "state" / "token").exists()
    assert not (session / "state" / "steps").exists()
    rc, _, _ = run("start", session, "--app", "--foreground")
    assert rc == 2


def test_restarting_an_existing_app_session_still_works(tmp_path: Path, session: Path) -> None:
    first = start_app(tmp_path / "root", session)
    stop_app(first)
    second = start_app(tmp_path / "root", session)
    stop_app(second)


def test_stop_works_on_an_app_session(session: Path) -> None:
    assert run("start", session, "--app")[0] == 0
    rc, out, _ = run("stop", session)
    assert rc == 0 and out == {"stopped": True}


# ---- step ---------------------------------------------------------------------------------------


def test_step_prints_id_nonce_and_url_and_makes_the_step_current(app: App) -> None:
    out = app.step(QUESTIONS)
    assert re.fullmatch(r"0001-questions", out["step"]) and out["nonce"] and out["url"] == app.info["url"]
    current = json.loads((app.state / "current.json").read_text())
    assert current["screen"] == out["step"] and current["nonce"] == out["nonce"] and current["mode"] == "app"
    assert (app.state / "steps" / f"{out['step']}.json").exists()
    assert app.step(APPROACHES)["step"] == "0002-approaches"


def test_step_works_without_a_running_server_and_url_is_null(app: App) -> None:
    stop_app(app)
    out = app.step(QUESTIONS)
    assert out["url"] is None and out["step"] == "0001-questions"


def test_an_invalid_step_exits_2_with_field_and_changes_nothing(app: App) -> None:
    good = app.step(QUESTIONS)
    bad = {**QUESTIONS, "questions": [{"id": "q1", "type": "single", "prompt": "p", "options": []}]}
    path = app.root / "bad.json"
    path.write_text(json.dumps(bad))
    out = app.cli("step", app.session, path, expect=2)
    assert out["field"] == "questions[0].options" and out["error"]
    assert json.loads((app.state / "current.json").read_text())["screen"] == good["step"]
    assert [p.name for p in (app.state / "steps").glob("*.json")] == [f"{good['step']}.json"]


def test_step_with_unreadable_or_non_json_file_exits_2(app: App) -> None:
    out = app.cli("step", app.session, app.root / "missing.json", expect=2)
    assert out["error"]
    path = app.root / "garbage.json"
    path.write_text("{nope")
    assert app.cli("step", app.session, path, expect=2)["error"]


# ---- status -------------------------------------------------------------------------------------


def test_status_sets_and_clears(app: App) -> None:
    out = app.cli("status", app.session, "--text", "Thinking", "--stage", "design", "--progress", "2/5", "--interruptible")
    assert out["status"]["text"] == "Thinking" and out["status"]["stage"] == "design"
    assert out["status"]["progress"] == "2/5" and out["status"]["interruptible"] is True
    assert app.snapshot()["status"]["text"] == "Thinking"
    assert app.cli("status", app.session, "--clear") == {"status": None}
    assert app.snapshot()["status"] is None


def test_status_errors_exit_2(app: App) -> None:
    for args in (
        ("--text", "x", "--progress", "two of five"),
        ("--text", "x", "--progress", "2/"),
        ("--text", "x", "--stage", "nonsense"),
        (),
        ("--clear", "--interruptible"),
    ):
        out = app.cli("status", app.session, *args, expect=2)
        assert out["error"], args


# ---- decide -------------------------------------------------------------------------------------


def test_decide_replaces_the_whole_list(app: App) -> None:
    path = app.root / "d.json"
    path.write_text(json.dumps([DECISION, {**DECISION, "id": "other"}]))
    assert app.cli("decide", app.session, path) == {"decisions": 2}
    path.write_text(json.dumps([DECISION]))
    assert app.cli("decide", app.session, path) == {"decisions": 1}
    assert [d["id"] for d in app.snapshot()["decisions"]] == ["storage"]


def test_decide_errors_keep_the_previous_list(app: App) -> None:
    path = app.root / "d.json"
    path.write_text(json.dumps([DECISION]))
    app.cli("decide", app.session, path)
    path.write_text("[{broken")
    assert app.cli("decide", app.session, path, expect=2)["error"]
    path.write_text(json.dumps({"not": "a list"}))
    assert app.cli("decide", app.session, path, expect=2)["error"]
    path.write_text(json.dumps([{**DECISION, "status": "bogus"}]))
    out = app.cli("decide", app.session, path, expect=2)
    assert out["field"] == "[0].status"
    assert app.cli("decide", app.session, app.root / "missing.json", expect=2)["error"]
    assert [d["id"] for d in app.snapshot()["decisions"]] == ["storage"]


# ---- review -------------------------------------------------------------------------------------


def make_review(app: App, text: str = "<html><body>review &lt; page</body></html>") -> Path:
    spec_dir = app.root / "specs"
    spec_dir.mkdir(exist_ok=True)
    path = spec_dir / "review.html"
    path.write_text(text, encoding="utf-8")
    assert app.cli("review", app.session, path) == {"review_url": "/_quirk/review"}
    return path


def test_review_get_is_404_then_serves_the_file_verbatim(app: App) -> None:
    assert app.request("GET", "/_quirk/review")[0] == 404
    path = make_review(app)
    status, body, resp = app.request("GET", "/_quirk/review?x=1")
    assert status == 200 and body == path.read_bytes()
    assert resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert app.snapshot()["review_registered"] is True


def test_review_with_a_missing_file_exits_2(app: App) -> None:
    assert app.cli("review", app.session, app.root / "nope.html", expect=2)["error"]
    assert app.cli("review", app.session, app.root, expect=2)["error"]


EXPORT = {"kind": "quirk-logic-spec-decisions", "slug": "my-spec", "stage": "draft", "signed": False, "items": [{"é": 1}]}


def test_review_export_requires_the_token(app: App) -> None:
    make_review(app)
    assert app.post("/_quirk/review/export", EXPORT, token=None)[0] == 403
    assert app.post("/_quirk/review/export", EXPORT, token="wrong")[0] == 403


def test_review_export_rejects_bad_kind_slug_and_shape(app: App) -> None:
    make_review(app)
    for body in (
        {**EXPORT, "kind": "other"},
        {k: v for k, v in EXPORT.items() if k != "kind"},
        {**EXPORT, "slug": "../evil"},
        {**EXPORT, "slug": "Upper"},
        {**EXPORT, "slug": ""},
        {k: v for k, v in EXPORT.items() if k != "slug"},
        {**EXPORT, "slug": "a" * 82},
        [1, 2],
        b"not json",
    ):
        assert app.post("/_quirk/review/export", body)[0] == 400, body


def test_review_export_over_2_mib_is_413(app: App) -> None:
    make_review(app)
    big = json.dumps({**EXPORT, "pad": "x" * (2 * 1024 * 1024)}).encode()
    assert app.post("/_quirk/review/export", big)[0] == 413


def test_review_export_without_a_registered_review_is_404(app: App) -> None:
    assert app.post("/_quirk/review/export", EXPORT)[0] == 404


@pytest.mark.parametrize(
    ("kind", "infix"),
    [("quirk-logic-spec-decisions", "decisions"), ("quirk-approach-comparison-challenges", "challenges")],
)
def test_review_export_writes_beside_review_html_and_emits_an_event(app: App, kind: str, infix: str) -> None:
    review = make_review(app)
    body = {**EXPORT, "kind": kind}
    status, data = app.post("/_quirk/review/export", body)
    assert status == 200
    path = Path(json.loads(data)["path"])
    assert path.parent == review.parent.resolve() or path.parent == review.parent
    assert re.fullmatch(rf"my-spec-{infix}-\d{{8}}T\d{{6}}Z\.json", path.name), path.name
    assert json.loads(path.read_text(encoding="utf-8")) == body
    assert path.read_text(encoding="utf-8") == json.dumps(body, indent=2, ensure_ascii=False)
    out = app.next()
    event = out["events"][0]
    assert event["type"] == "review-export"
    assert event["payload"] == {"path": str(path), "kind": kind, "stage": "draft", "signed": False}
    status2, data2 = app.post("/_quirk/review/export", body)
    assert status2 == 200 and Path(json.loads(data2)["path"]) != path


# ---- GET / and state ----------------------------------------------------------------------------


def test_get_root_injects_the_boot_json_into_the_shell(app: App, session: Path) -> None:
    status, body, resp = app.request("GET", "/")
    assert status == 200 and resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert resp.getheader("Cache-Control") == "no-store"
    page = body.decode()
    assert BOOT_PLACEHOLDER not in page
    match = re.search(r'id="quirk-companion-boot">(.*?)</script>', page)
    assert json.loads(match.group(1)) == {"token": app.token, "session": session.name}


def test_boot_json_escapes_angle_brackets(tmp_path: Path) -> None:
    session = tmp_path / "s<b>x"
    srv = start_app(tmp_path / "root", session)
    try:
        _, body, _ = srv.request("GET", "/")
        raw = re.search(r'id="quirk-companion-boot">(.*?)</script>', body.decode()).group(1)
        assert "<" not in raw and "\\u003c" in raw
        assert json.loads(raw)["session"] == "s<b>x"
    finally:
        stop_app(srv)


@pytest.mark.parametrize(
    "shell",
    [None, "<html>no placeholder</html>", f"{BOOT_PLACEHOLDER}{BOOT_PLACEHOLDER}"],
    ids=["missing", "no-placeholder", "two-placeholders"],
)
def test_get_root_without_a_usable_shell_is_500(tmp_path: Path, session: Path, shell: Optional[str]) -> None:
    srv = start_app(tmp_path / "root", session, shell=shell)
    try:
        status, body, _ = srv.request("GET", "/")
        assert status == 500 and json.loads(body) == {"error": "companion shell not built"}
    finally:
        stop_app(srv)


def test_state_route_keeps_screen_and_nonce_and_adds_mode(app: App) -> None:
    status, body, _ = app.request("GET", "/_quirk/state")
    assert status == 200 and json.loads(body) == {"screen": None, "nonce": None, "mode": "app"}
    step = app.step(QUESTIONS)
    _, body, _ = app.request("GET", "/_quirk/state")
    assert json.loads(body) == {"screen": step["step"], "nonce": step["nonce"], "mode": "app"}


def test_lib_route_still_serves_whitelisted_files_in_app_mode(app: App) -> None:
    assert app.request("GET", "/_quirk/lib/nope/1/x.js")[0] == 404
    libs = json.loads((SKILL / "vendor" / "libraries.json").read_text())["libraries"]["mermaid"]
    version = libs["current"]
    path = libs["versions"][version]["files"][0]["path"]
    assert app.request("GET", f"/_quirk/lib/mermaid/{version}/{path}")[0] == 200


# ---- guard and token ----------------------------------------------------------------------------


def test_foreign_origin_and_host_get_403_on_every_app_route(app: App) -> None:
    app.step(QUESTIONS)
    token = {TOKEN_HEADER: app.token}
    body = json.dumps({"client_id": "c1", "type": "continue", "payload": {}}).encode()
    for method, path in (
        ("GET", "/"),
        ("GET", "/_quirk/app/snapshot"),
        ("GET", "/_quirk/review"),
        ("POST", "/_quirk/app/event"),
        ("POST", "/_quirk/review/export"),
    ):
        for extra in ({"Origin": "http://evil.example"}, {"Host": "evil.example"}):
            status, _, _ = app.request(method, path, body if method == "POST" else None, {**token, **extra})
            assert status == 403, (method, path, extra)
    assert app.cli("next", app.session, "--timeout", "0.3", expect=1)["status"] == "timeout"


def test_app_event_without_or_with_a_wrong_token_is_403(app: App) -> None:
    app.step(QUESTIONS)
    payload = {"client_id": "c1", "type": "continue", "payload": {}}
    assert app.post("/_quirk/app/event", payload, token=None)[0] == 403
    status, data = app.post("/_quirk/app/event", payload, token="wrong")
    assert status == 403 and json.loads(data) == {"error": "bad token"}
    assert app.cli("next", app.session, "--timeout", "0.3", expect=1)["status"] == "timeout"


def test_screen_mode_event_route_is_not_served_in_app_mode(app: App) -> None:
    app.step(QUESTIONS)
    assert app.post("/_quirk/event", {"type": "proceed"})[0] == 404


# ---- event route --------------------------------------------------------------------------------


def test_a_valid_submit_is_accepted_and_visible_via_next(app: App) -> None:
    step = app.step(QUESTIONS)
    payload = {"answers": {"q1": {"selected": ["sql"]}, "q2": {"text": "hi", "other": "o", "skipped": True}}, "comment": "ok"}
    status, data = app.event("submit", payload, nonce=step["nonce"], client_id="c-1")
    assert (status, data) == (204, b"")
    out = app.next()
    (event,) = out["events"]
    assert event["type"] == "submit" and event["step"] == step["step"] and event["client_id"] == "c-1"
    assert event["payload"] == payload and out["cursor"] == event["seq"]
    assert app.snapshot()["step_state"] == "submitted"


def test_a_stale_nonce_submit_gets_409_and_writes_nothing(app: App) -> None:
    old = app.step(QUESTIONS)
    app.step(APPROACHES)
    status, data = app.event("submit", {"answers": {}}, nonce=old["nonce"])
    assert status == 409 and json.loads(data) == {"superseded": True}
    status, _ = app.event("submit", {"pick": "one"}, nonce=None)
    assert status == 409
    assert app.cli("next", app.session, "--timeout", "0.3", expect=1)["status"] == "timeout"


def test_submit_with_no_current_step_is_409(app: App) -> None:
    assert app.event("submit", {"pick": "one"}, nonce="x")[0] == 409


@pytest.mark.parametrize(
    ("spec", "payload"),
    [
        (QUESTIONS, {"answers": {"nope": {"text": "x"}}}),
        (QUESTIONS, {"answers": {"q1": {"selected": ["bogus"]}}}),
        (QUESTIONS, {"answers": {"q2": {"selected": ["sql"]}}}),
        (QUESTIONS, {"answers": {"q1": {"selected": "sql"}}}),
        (QUESTIONS, {"answers": {"q1": {"surprise": 1}}}),
        (QUESTIONS, {"answers": {"q1": {"skipped": False}}}),
        (QUESTIONS, {"answers": ["q1"]}),
        (QUESTIONS, {"pick": "sql"}),
        (QUESTIONS, {"answers": {}, "comment": "x" * 4001}),
        (QUESTIONS, {"answers": {}, "comment": 5}),
        (APPROACHES, {"pick": "three"}),
        (APPROACHES, {}),
        (APPROACHES, {"pick": ["one"]}),
        (DESIGN, {"verdict": "maybe"}),
        (DESIGN, {"verdict": "sign-off"}),
        (SPEC_MD, {"verdict": "looks-right"}),
        (HAND_OFF, {"pick": "one"}),
        (DONE, {}),
        (EDIT_CARD, {"decision": "confirm"}),
        (SPEC_INTERACTIVE, {"verdict": "sign-off"}),
    ],
)
def test_submit_payloads_are_validated_against_the_step(app: App, spec: dict, payload: dict) -> None:
    step = app.step(spec)
    status, data = app.event("submit", payload, nonce=step["nonce"])
    assert status == 400, data
    assert json.loads(data)["error"]
    assert app.cli("next", app.session, "--timeout", "0.3", expect=1)["status"] == "timeout"


@pytest.mark.parametrize(
    ("spec", "payload"),
    [
        (APPROACHES, {"pick": "two", "comment": "because"}),
        (DESIGN, {"verdict": "looks-right"}),
        (DESIGN, {"verdict": "needs-changes", "comment": "x" * 4000}),
        (SPEC_MD, {"verdict": "sign-off"}),
        (SPEC_MD, {"verdict": "changes"}),
        (HAND_OFF, {"pick": "plan"}),
    ],
)
def test_valid_submits_for_each_kind_are_accepted(app: App, spec: dict, payload: dict) -> None:
    step = app.step(spec)
    assert app.event("submit", payload, nonce=step["nonce"])[0] == 204


def test_duplicate_client_id_returns_200_duplicate_and_writes_nothing(app: App) -> None:
    step = app.step(APPROACHES)
    assert app.event("submit", {"pick": "one"}, nonce=step["nonce"], client_id="dup")[0] == 204
    status, data = app.event("submit", {"pick": "one"}, nonce=step["nonce"], client_id="dup")
    assert status == 200 and json.loads(data) == {"duplicate": True}
    assert len(app.next(expect=0)["events"]) == 1
    # a retry still dedupes after the step moved on
    app.step(DESIGN)
    status, data = app.event("submit", {"pick": "one"}, nonce=step["nonce"], client_id="dup")
    assert status == 200 and json.loads(data) == {"duplicate": True}


def test_malformed_event_bodies_get_400(app: App) -> None:
    step = app.step(APPROACHES)
    nonce = step["nonce"]
    good = {"client_id": "c", "type": "continue", "payload": {}, "nonce": nonce}
    for body in (
        b"not json",
        b"[]",
        {**good, "client_id": ""},
        {**good, "client_id": "x" * 101},
        {**good, "client_id": 5},
        {k: v for k, v in good.items() if k != "client_id"},
        {**good, "payload": "nope"},
        {**good, "type": "bogus"},
        {**good, "type": "review-export"},
    ):
        status, _ = app.post("/_quirk/app/event", body)
        assert status == 400, body
    status, data = app.post("/_quirk/app/event", {**good, "type": "bogus"})
    assert json.loads(data) == {"error": "unsupported event type"}
    assert app.post("/_quirk/app/event", {**good, "client_id": "x" * 100})[0] == 204


def test_event_body_over_64_kib_gets_400(app: App) -> None:
    app.step(APPROACHES)
    body = json.dumps({"client_id": "c", "type": "continue", "payload": {"pad": "x" * 70000}}).encode()
    assert app.post("/_quirk/app/event", body)[0] == 400


def test_continue_and_edit_request_need_only_the_token(app: App) -> None:
    old = app.step(APPROACHES)
    path = app.root / "d.json"
    path.write_text(json.dumps([DECISION]))
    app.cli("decide", app.session, path)
    app.step(DESIGN)
    assert app.event("continue", {}, nonce=old["nonce"])[0] == 204
    assert app.event("edit-request", {"decision_id": "storage", "to": "Files", "note": "n"})[0] == 204
    assert app.event("edit-request", {"decision_id": "missing"})[0] == 400
    assert app.event("edit-request", {})[0] == 400
    assert app.event("edit-request", {"decision_id": "storage", "to": 3})[0] == 400
    assert app.event("continue", {"extra": 1})[0] == 400
    types = [e["type"] for e in app.next()["events"]]
    assert types == ["continue", "edit-request"]


def test_edit_decision_needs_an_edit_card_step_and_a_fresh_nonce(app: App) -> None:
    approaches = app.step(APPROACHES)
    assert app.event("edit-decision", {"decision": "confirm"}, nonce=approaches["nonce"])[0] == 400
    card = app.step(EDIT_CARD)
    assert app.event("edit-decision", {"decision": "confirm"}, nonce=approaches["nonce"])[0] == 409
    assert app.event("edit-decision", {"decision": "maybe"}, nonce=card["nonce"])[0] == 400
    assert app.event("edit-decision", {"decision": "cancel"}, nonce=card["nonce"])[0] == 204
    (event,) = app.next()["events"]
    assert event["type"] == "edit-decision" and event["step"] == card["step"]


def test_drafts_are_saved_in_the_snapshot_and_never_returned_by_next(app: App) -> None:
    step = app.step(QUESTIONS)
    sid = step["step"]
    draft = {"answers": {"q1": {"selected": ["files"]}}, "comment": "wip"}
    assert app.event("draft", draft, step=sid)[0] == 204
    assert app.event("draft", {**draft, "comment": "wip2"}, step=sid)[0] == 204
    assert json.loads((app.state / "drafts" / f"{sid}.json").read_text())["comment"] == "wip2"
    assert app.snapshot()["draft"]["comment"] == "wip2"
    assert not (app.state / "app-events").exists() or (app.state / "app-events").read_text() == ""
    assert app.cli("next", app.session, "--timeout", "0.3", expect=1)["status"] == "timeout"


def test_draft_with_no_current_step_gets_400(app: App) -> None:
    assert app.event("draft", {"answers": {}}, step="anything")[0] == 400
    assert app.event("draft", {"answers": {}})[0] == 400


def test_draft_without_a_step_gets_400_and_saves_nothing(app: App) -> None:
    step = app.step(QUESTIONS)
    assert app.event("draft", {"answers": {}, "comment": "x"})[0] == 400
    for bad in ("", 5, ["x"], {"id": "x"}, True):
        assert app.event("draft", {"comment": "x"}, step=bad)[0] == 400, bad
    assert not (app.state / "drafts" / f"{step['step']}.json").exists()


def test_draft_for_a_superseded_step_gets_409_and_saves_nothing(app: App) -> None:
    old = app.step(QUESTIONS)
    new = app.step(APPROACHES)
    status, data = app.event("draft", {"answers": {}, "comment": "late"}, step=old["step"])
    assert status == 409 and json.loads(data) == {"superseded": True}
    assert not (app.state / "drafts" / f"{old['step']}.json").exists()
    assert not (app.state / "drafts" / f"{new['step']}.json").exists()
    assert app.snapshot().get("draft") in (None, {})
    assert app.event("draft", {"answers": {}, "comment": "now"}, step=new["step"])[0] == 204
    assert app.snapshot()["draft"]["comment"] == "now"


def test_draft_accepts_a_pick_and_returns_it_in_the_snapshot(app: App) -> None:
    step = app.step(APPROACHES)
    draft = {"answers": {}, "comment": "c", "pick": "two"}
    assert app.event("draft", draft, step=step["step"])[0] == 204
    assert app.snapshot()["draft"] == draft
    for bad in (["two"], {"id": "two"}, 2, None):
        assert app.event("draft", {"pick": bad}, step=step["step"])[0] == 400, bad
    assert app.event("draft", {"surprise": 1}, step=step["step"])[0] == 400
    assert app.snapshot()["draft"] == draft


def test_continue_is_accepted_before_any_step_exists(app: App) -> None:
    assert app.event("continue", {})[0] == 204
    assert app.event("continue", {"extra": 1})[0] == 400
    assert app.post("/_quirk/app/event", {"client_id": "c", "type": "continue", "payload": {}}, token="wrong")[0] == 403
    (event,) = app.next()["events"]
    assert event["type"] == "continue" and event["step"] is None


def test_continue_before_any_step_dedupes_on_client_id(app: App) -> None:
    assert app.event("continue", {}, client_id="same")[0] == 204
    status, data = app.event("continue", {}, client_id="same")
    assert status == 200 and json.loads(data) == {"duplicate": True}
    assert len(app.next()["events"]) == 1


def test_other_events_still_need_a_current_step(app: App) -> None:
    assert app.event("edit-request", {"decision_id": "storage"})[0] == 400
    assert app.event("edit-decision", {"decision": "cancel"}, nonce="x")[0] == 409


WRONG_TYPES = (["x"], {"a": 1}, 5, True)


def test_wrong_typed_fields_get_400_instead_of_crashing_the_handler(app: App) -> None:
    path = app.root / "d.json"
    path.write_text(json.dumps([DECISION]))
    app.cli("decide", app.session, path)
    card = app.step(EDIT_CARD)
    make_review(app)
    for bad in WRONG_TYPES:
        assert app.event("edit-request", {"decision_id": bad})[0] == 400, bad
        assert app.event("edit-request", {"decision_id": "storage", "to": bad})[0] == 400, bad
        assert app.event("edit-request", {"decision_id": "storage", "note": bad})[0] == 400, bad
        assert app.event("edit-decision", {"decision": bad}, nonce=card["nonce"])[0] == 400, bad
        assert app.event("draft", {"pick": bad}, step=card["step"])[0] == 400, bad
        if not isinstance(bad, dict):
            assert app.event("draft", {"answers": bad}, step=card["step"])[0] == 400, bad
        assert app.event("draft", {"comment": bad}, step=card["step"])[0] == 400, bad
        assert app.event("draft", {}, step=bad)[0] == 400, bad
        assert app.post("/_quirk/app/event", {"client_id": "c", "type": bad, "payload": {}})[0] == 400, bad
        assert app.post("/_quirk/app/event", {"client_id": "c", "type": "continue", "payload": bad})[0] == 400, bad
        assert app.post("/_quirk/app/event", {"client_id": "c", "type": "submit", "payload": {}, "nonce": bad})[0] == 409, bad
        assert app.post("/_quirk/review/export", {**EXPORT, "kind": bad})[0] == 400, bad
        assert app.post("/_quirk/review/export", {**EXPORT, "slug": bad})[0] == 400, bad
    assert app.event("edit-request", {"decision_id": "storage"})[0] == 204


def test_wrong_typed_submit_fields_get_400_instead_of_crashing_the_handler(app: App) -> None:
    for spec, field in ((APPROACHES, "pick"), (HAND_OFF, "pick"), (DESIGN, "verdict")):
        step = app.step(spec)
        for bad in WRONG_TYPES:
            assert app.event("submit", {field: bad}, nonce=step["nonce"])[0] == 400, (spec["kind"], bad)
    step = app.step(QUESTIONS)
    for bad in WRONG_TYPES:
        assert app.event("submit", {"answers": {"q1": {"selected": bad}}}, nonce=step["nonce"])[0] == 400, bad
        assert app.event("submit", {"answers": {"q1": {"selected": [bad]}}}, nonce=step["nonce"])[0] == 400, bad
        assert app.event("submit", {"answers": {"q1": bad}}, nonce=step["nonce"])[0] == 400, bad
    assert app.event("submit", {"answers": {"q1": {"selected": ["sql"]}}}, nonce=step["nonce"])[0] == 204


# ---- snapshot -----------------------------------------------------------------------------------


def test_snapshot_route_returns_200_on_a_new_rev_and_204_when_unchanged(app: App) -> None:
    snap = app.snapshot()
    rev = snap["rev"]
    assert snap["mode"] == "app" and app.request("GET", f"/_quirk/app/snapshot?rev={rev}")[0] == 204
    status, body, _ = app.request("GET", f"/_quirk/app/snapshot?rev={rev + 1}")
    assert status == 200 and json.loads(body)["rev"] == rev
    assert app.request("GET", "/_quirk/app/snapshot?rev=abc")[0] == 200
    app.cli("status", app.session, "--text", "working")
    status, body, _ = app.request("GET", f"/_quirk/app/snapshot?rev={rev}")
    assert status == 200 and json.loads(body)["rev"] > rev
    status, body, resp = app.request("GET", f"/_quirk/app/snapshot?rev={json.loads(body)['rev']}")
    assert status == 204 and body == b""


def test_snapshot_subcommand_matches_the_http_route(app: App) -> None:
    app.step(QUESTIONS)
    assert app.cli("snapshot", app.session) == app.snapshot()


# ---- next ---------------------------------------------------------------------------------------


def test_next_returns_events_after_a_cursor_and_a_timeout_rerun_loses_nothing(app: App) -> None:
    step = app.step(APPROACHES)
    timed_out = app.cli("next", app.session, "--timeout", "0.4", expect=1)
    assert timed_out == {"status": "timeout", "cursor": 0}
    app.event("continue", {}, client_id="a")
    first = app.next()
    assert [e["client_id"] for e in first["events"]] == ["a"]
    cursor = first["cursor"]
    assert app.cli("next", app.session, "--after", cursor, "--timeout", "0.4", expect=1) == {"status": "timeout", "cursor": cursor}
    app.event("submit", {"pick": "one"}, nonce=step["nonce"], client_id="b")
    second = app.next("--after", cursor)
    assert [e["client_id"] for e in second["events"]] == ["b"] and second["cursor"] > cursor
    assert [e["client_id"] for e in app.next("--after", 0)["events"]] == ["a", "b"]
    assert all(e["seq"] > 0 for e in second["events"]) and "timestamp" in second["events"][0]


def test_next_waits_for_an_event_posted_while_it_blocks(app: App) -> None:
    app.step(APPROACHES)
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "next", str(app.session), "--timeout", "20"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        import time

        time.sleep(0.8)
        assert app.event("continue", {}, client_id="late")[0] == 204
        out, _ = proc.communicate(timeout=15)
        assert proc.returncode == 0 and json.loads(out)["events"][0]["client_id"] == "late"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_next_without_a_server_exits_2_no_server(app: App) -> None:
    stop_app(app)
    rc, out, _ = run("next", app.session, "--timeout", "0.3")
    assert rc == 2 and out == {"status": "no-server"}
