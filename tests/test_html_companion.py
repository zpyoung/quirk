"""Tests for the live companion server, its CLI and the companion template.

Servers run as subprocesses on 127.0.0.1 port 0 and are always stopped in teardown. No test
reaches beyond the loopback interface.
"""
from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

import companion  # noqa: E402
from htmlkit import assemble, resolve  # noqa: E402

CLI = SKILL / "scripts" / "companion.py"
EXAMPLE = SKILL / "templates" / "companion" / "example.screen.json"
MERMAID_VERSION = json.loads((SKILL / "vendor" / "libraries.json").read_text())["libraries"]["mermaid"]["current"]

SCREEN = {
    "title": "Layout",
    "question": "Which layout fits the dashboard?",
    "select": "multi",
    "options": [
        {"id": "two-col", "label": "Two column", "description": "Filters left, results right"},
        {"id": "stacked", "label": "Stacked", "description": "Filters above results", "html": "<div>mockup</div>"},
    ],
    "content": "<p>Context for the question.</p>",
}


def screen_with(**changes: object) -> dict:
    return {**SCREEN, **changes}


def options(n: int) -> list[dict]:
    return [{"id": f"opt-{i}", "label": f"Option {i}"} for i in range(n)]


def run(*args: object, cwd: Optional[Path] = None, timeout: float = 60) -> tuple[int, dict, str]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
    )
    out = proc.stdout.strip()
    assert out.count("\n") == 0, f"stdout must be one JSON object: {proc.stdout!r}"
    return proc.returncode, json.loads(out), proc.stderr


class Server:
    """A foreground companion server on port 0 and the helpers the tests drive it with."""

    def __init__(self, session: Path, proc: subprocess.Popen, info: dict) -> None:
        self.session = session
        self.proc = proc
        self.info = info
        self.port = info["port"]

    @property
    def state(self) -> Path:
        return self.session / "state"

    def show(self, spec: dict, name: str = "screen.json", expect: int = 0) -> dict:
        path = self.session.parent / name
        path.write_text(json.dumps(spec), encoding="utf-8")
        rc, out, err = run("show", self.session, path, "--project-dir", self.session.parent)
        assert rc == expect, (rc, out, err)
        return out

    def request(
        self, method: str, path: str, body: bytes | None = None, headers: dict | None = None
    ) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def post(self, payload: dict | bytes, headers: dict | None = None) -> tuple[int, bytes]:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return self.request("POST", "/_quirk/event", body, {"Content-Type": "application/json", **(headers or {})})

    def event(self, nonce: str, type_: str = "click", **fields: object) -> tuple[int, bytes]:
        payload = {"nonce": nonce, "type": type_, "choice": None, "text": "", "selected": [], "note": None}
        payload.update(fields)
        return self.post(payload)

    def events(self) -> list[dict]:
        path = self.state / "events"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def current(self) -> dict:
        return json.loads((self.state / "current.json").read_text(encoding="utf-8"))


def start_foreground(session: Path, *extra: str) -> Server:
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(session), "--foreground", "--port", "0", *extra],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    line = proc.stdout.readline()
    assert line, proc.stderr.read()
    info = json.loads(line)
    assert info["type"] == "server-started"
    return Server(session, proc, info)


def stop_server(server: Server) -> None:
    if server.proc.poll() is None:
        server.proc.send_signal(signal.SIGTERM)
        try:
            server.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.proc.kill()
            server.proc.wait()
    for stream in (server.proc.stdout, server.proc.stderr):
        if stream:
            stream.close()


@pytest.fixture
def session(tmp_path: Path) -> Path:
    return tmp_path / ".quirk" / "brainstorm" / "s1"


@pytest.fixture
def server(session: Path):
    srv = start_foreground(session)
    try:
        yield srv
    finally:
        stop_server(srv)


def test_start_reports_server_info_and_creates_state(server: Server, session: Path) -> None:
    info = server.info
    assert info["host"] == "127.0.0.1" and info["port"] > 0
    assert info["url"] == f"http://127.0.0.1:{info['port']}/"
    assert info["pid"] == server.proc.pid
    assert Path(info["screen_dir"]) == session / "screens" and Path(info["state_dir"]) == session / "state"
    assert json.loads((session / "state" / "server-info").read_text()) == info
    assert (session.parent / ".gitignore").read_text() == "*\n"


def test_show_then_click_with_right_nonce_is_recorded(server: Server) -> None:
    shown = server.show(SCREEN)
    assert shown["screen"].endswith("-layout") and shown["screen"].startswith("0001-")
    assert shown["checks"]["passed"] is True and shown["url"] == server.info["url"]
    assert server.current()["nonce"] == shown["nonce"] and server.current()["screen"] == shown["screen"]
    status, _ = server.event(shown["nonce"], "click", choice="two-col", text="Two column", selected=["two-col"])
    assert status == 204
    [event] = server.events()
    assert event["type"] == "click" and event["screen"] == shown["screen"] and event["nonce"] == shown["nonce"]
    assert event["choice"] == "two-col" and event["selected"] == ["two-col"] and event["note"] is None
    assert isinstance(event["timestamp"], float)
    rc, out, _ = run("events", server.session)
    assert rc == 0 and out["events"] == [event]
    rc, out, _ = run("events", server.session, "--screen", "9999-none")
    assert rc == 0 and out == {"events": []}


def test_wrong_nonce_gets_409(server: Server) -> None:
    server.show(SCREEN)
    status, body = server.event("not-the-nonce")
    assert status == 409 and json.loads(body) == {"superseded": True}
    assert server.events() == []


def test_foreign_origin_and_host_get_403(server: Server) -> None:
    nonce = server.show(SCREEN)["nonce"]
    payload = {"nonce": nonce, "type": "click", "choice": None, "text": "", "selected": [], "note": None}
    assert server.post(payload, {"Origin": "http://evil.example"})[0] == 403
    assert server.post(payload, {"Origin": "null"})[0] == 403
    assert server.post(payload, {"Host": "evil.example"})[0] == 403
    assert server.request("GET", "/", headers={"Host": "evil.example"})[0] == 403
    assert server.events() == []
    own = f"http://127.0.0.1:{server.port}"
    assert server.post(payload, {"Origin": own})[0] == 204


@pytest.mark.parametrize(
    "path",
    [
        "/_quirk/lib/mermaid/%s/../../../libraries.json" % MERMAID_VERSION,
        "/_quirk/lib/mermaid/%s/%%2e%%2e/%%2e%%2e/libraries.json" % MERMAID_VERSION,
        "/_quirk/lib/../libraries.json",
        "/_quirk/lib/mermaid/%s/LICENSE.not-listed" % MERMAID_VERSION,
        "/_quirk/lib/mermaid/0.0.0/mermaid.min.js",
        "/_quirk/lib/nope/1/x.js",
    ],
)
def test_lib_traversal_and_unknown_files_get_404(server: Server, path: str) -> None:
    assert server.request("GET", path)[0] == 404


def test_lib_serves_a_file_named_in_libraries_json(server: Server) -> None:
    status, body = server.request("GET", f"/_quirk/lib/mermaid/{MERMAID_VERSION}/mermaid.min.js")
    assert status == 200
    assert body == (SKILL / "vendor" / "mermaid" / MERMAID_VERSION / "mermaid.min.js").read_bytes()


def test_wait_returns_proceed_with_clicks(server: Server) -> None:
    nonce = server.show(SCREEN)["nonce"]
    screen = server.current()["screen"]
    server.event(nonce, "click", choice="two-col", text="Two column", selected=["two-col"])
    server.event(nonce, "click", choice="stacked", text="Stacked", selected=["two-col", "stacked"])
    server.event(nonce, "proceed", text="Proceed", selected=["two-col", "stacked"], note="both please")
    rc, out, _ = run("wait", server.session, "--timeout", 5)
    assert rc == 0
    assert out["proceed"]["type"] == "proceed" and out["proceed"]["note"] == "both please"
    assert [c["choice"] for c in out["clicks"]] == ["two-col", "stacked"]
    assert all(c["screen"] == screen for c in out["clicks"])


def test_wait_times_out_then_a_rerun_finds_a_later_proceed(server: Server) -> None:
    nonce = server.show(SCREEN)["nonce"]
    screen = server.current()["screen"]
    start = time.monotonic()
    rc, out, err = run("wait", server.session, "--timeout", 0.5)
    assert rc == 1 and out == {"status": "timeout", "screen": screen}
    assert time.monotonic() - start < 20 and "wait" in err
    server.event(nonce, "proceed", text="Proceed", selected=["stacked"])
    rc, out, _ = run("wait", server.session, "--timeout", 5)
    assert rc == 0 and out["proceed"]["selected"] == ["stacked"] and out["clicks"] == []


def test_wait_ignores_proceed_from_an_earlier_screen(server: Server) -> None:
    first = server.show(SCREEN)["nonce"]
    server.event(first, "proceed", text="Proceed", selected=["two-col"])
    server.show(screen_with(title="Next"))
    rc, out, _ = run("wait", server.session, "--timeout", 0.5)
    assert rc == 1 and out["status"] == "timeout"


def test_wait_without_a_server_exits_2(tmp_path: Path) -> None:
    session = tmp_path / "none"
    (session / "state").mkdir(parents=True)
    rc, out, _ = run("wait", session, "--timeout", 1)
    assert rc == 2 and out == {"status": "no-server"}
    rc, out, _ = run("wait", tmp_path / "missing", "--timeout", 1)
    assert rc == 2 and out == {"status": "no-server"}
    (session / "state" / "server-info").write_text("not json")
    assert run("wait", session, "--timeout", 1)[0] == 2
    (session / "state" / "server-info").write_text(json.dumps({"pid": 2**22 + 12345}))
    assert run("wait", session, "--timeout", 1)[0] == 2


def test_wait_exits_2_once_the_server_has_stopped(session: Path) -> None:
    srv = start_foreground(session)
    try:
        srv.show(SCREEN)
    finally:
        stop_server(srv)
    rc, out, _ = run("wait", session, "--timeout", 1)
    assert rc == 2 and out == {"status": "no-server"}
    assert json.loads((session / "state" / "server-stopped").read_text())["reason"] == "stop"


def test_a_new_screen_makes_the_old_nonce_stale(server: Server) -> None:
    first = server.show(SCREEN)
    second = server.show(screen_with(title="Second one"))
    assert first["screen"] != second["screen"] and first["nonce"] != second["nonce"]
    assert second["screen"].startswith("0002-")
    status, body = server.event(first["nonce"])
    assert status == 409 and json.loads(body) == {"superseded": True}
    assert server.event(second["nonce"])[0] == 204
    status, body = server.request("GET", "/_quirk/state")
    assert status == 200 and json.loads(body) == {"screen": second["screen"], "nonce": second["nonce"]}


def test_idle_shutdown_writes_server_stopped(session: Path) -> None:
    srv = start_foreground(session, "--idle-minutes", "0.02")
    try:
        assert srv.proc.wait(timeout=20) == 0
    finally:
        stop_server(srv)
    stopped = json.loads((session / "state" / "server-stopped").read_text())
    assert stopped["reason"] == "idle" and isinstance(stopped["at"], float)


def test_show_activity_keeps_an_idle_server_alive(session: Path) -> None:
    srv = start_foreground(session, "--idle-minutes", "0.03")
    try:
        deadline = time.monotonic() + 4.5
        while time.monotonic() < deadline:
            srv.show(SCREEN)
            time.sleep(0.4)
        assert srv.proc.poll() is None
    finally:
        stop_server(srv)


@pytest.mark.parametrize("count", [0, 1, 5])
def test_show_rejects_the_wrong_number_of_options(server: Server, count: int) -> None:
    out = server.show(screen_with(options=options(count)), expect=2)
    assert "options" in out["error"]
    assert not (server.session / "state" / "current.json").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"options": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]},
        {"options": [{"id": "Bad Id", "label": "A"}, {"id": "b", "label": "B"}]},
        {"options": [{"id": "a"}, {"id": "b", "label": "B"}]},
        {"select": "some"},
        {"question": ""},
        {"title": 5},
        {"diagram": 5},
        {"content": ["x"]},
        {"extra": 1},
        {"content": "<!-- slot: main -->\nx"},
    ],
)
def test_show_rejects_malformed_screens(server: Server, changes: dict) -> None:
    out = server.show(screen_with(**changes), expect=2)
    assert "error" in out


def test_show_rejects_unreadable_or_non_object_json_and_missing_session(server: Server, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    rc, out, _ = run("show", server.session, bad, "--project-dir", tmp_path)
    assert rc == 2 and "error" in out
    bad.write_text("[]")
    assert run("show", server.session, bad, "--project-dir", tmp_path)[0] == 2
    rc, out, _ = run("show", server.session, tmp_path / "absent.json", "--project-dir", tmp_path)
    assert rc == 2 and "error" in out
    good = tmp_path / "good.json"
    good.write_text(json.dumps(SCREEN))
    rc, out, _ = run("show", tmp_path / "no-session", good, "--project-dir", tmp_path)
    assert rc == 2 and "error" in out


def test_a_failed_static_check_writes_the_screen_but_does_not_make_it_current(server: Server) -> None:
    good = server.show(SCREEN)
    bad = server.show(screen_with(title="Remote", content='<img src="https://cdn.example.com/x.png" alt="">'), expect=1)
    assert bad["checks"]["passed"] is False
    assert any(f["check"] == "external-refs" for f in bad["checks"]["failures"])
    assert (server.session / "screens" / f"{bad['screen']}.html").is_file()
    assert server.current()["nonce"] == good["nonce"]
    assert server.event(good["nonce"])[0] == 204
    assert server.event(bad["nonce"])[0] == 409


def test_get_root_serves_the_newest_screen(server: Server) -> None:
    status, body = server.request("GET", "/")
    assert status == 200 and b"/_quirk/state" in body and b"Which layout" not in body
    first = server.show(SCREEN)
    second = server.show(screen_with(title="Newer", question="Which one is newer?"))
    status, body = server.request("GET", "/")
    page = body.decode("utf-8")
    assert status == 200 and "Which one is newer?" in page and second["nonce"] in page
    assert "Which layout" not in page and first["nonce"] not in page


def test_screen_page_has_accessible_cards_and_the_shell(server: Server) -> None:
    shown = server.show(SCREEN)
    page = (server.session / "screens" / f"{shown['screen']}.html").read_text(encoding="utf-8")
    assert 'aria-pressed="false"' in page and 'data-option-id="two-col"' in page
    assert 'data-quirk-shell="companion"' in page and 'data-quirk-shell="chrome"' in page
    assert "<div>mockup</div>" in page and "Filters left, results right" in page
    assert page.count(shown["nonce"]) == 1
    assert '"mode": "companion"' in page.split("\n", 2)[1]
    single = server.show(screen_with(select="single", title="Single"))
    page = (server.session / "screens" / f"{single['screen']}.html").read_text(encoding="utf-8")
    assert 'role="radiogroup"' in page and 'role="radio"' in page and "aria-pressed" not in page.split("<body")[1].split("<script")[0]


def test_diagram_screen_loads_the_served_mermaid_and_passes_checks(server: Server) -> None:
    shown = server.show(screen_with(title="Flow", diagram="flowchart LR\n  A --> B"))
    page = (server.session / "screens" / f"{shown['screen']}.html").read_text(encoding="utf-8")
    assert f"/_quirk/lib/mermaid/{MERMAID_VERSION}/mermaid.min.js" in page
    assert "A --&gt; B" in page and "mermaid.min.js\"></script>" in page
    assert len(page) < 200_000
    assert shown["checks"]["passed"] is True
    plain = server.show(SCREEN)
    assert "/_quirk/lib/mermaid/" not in (server.session / "screens" / f"{plain['screen']}.html").read_text()


def test_the_example_screen_shows_and_passes_checks(server: Server) -> None:
    spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    out = server.show(spec)
    assert out["checks"]["passed"] is True


def test_built_screens_pass_the_check_command_in_companion_mode(server: Server, tmp_path: Path) -> None:
    shown = server.show(SCREEN)
    path = server.session / "screens" / f"{shown['screen']}.html"
    result = assemble.check_artifact(path, project_dir=tmp_path, user_dir=tmp_path / "u")
    assert result["passed"] is True
    path.write_text(path.read_text().replace("var nonce", "var other"), encoding="utf-8")
    assert assemble.check_artifact(path, project_dir=tmp_path, user_dir=tmp_path / "u")["passed"] is False


def test_companion_template_is_a_valid_builtin() -> None:
    roots = resolve.template_roots(SKILL, Path("/nonexistent-project"), Path("/nonexistent-user"))
    templates, warnings = resolve.list_templates(roots, skill_dir=SKILL)
    row = next(t for t in templates if t.name == "companion")
    assert row.level == "builtin" and row.tier == 1 and not warnings
    assert list(row.slots) == ["question", "options", "content"] and row.libraries == ["simple-css"]


def test_event_body_limits_and_validation(server: Server) -> None:
    nonce = server.show(SCREEN)["nonce"]
    assert server.post(b"{not json")[0] == 400
    assert server.post(b"[]")[0] == 400
    assert server.post({"nonce": nonce, "type": "hover"})[0] == 400
    assert server.post({"nonce": nonce, "type": "click", "selected": "x"})[0] == 400
    big = json.dumps({"nonce": nonce, "type": "click", "note": "x" * 70_000}).encode()
    assert server.post(big)[0] == 400
    assert server.request("POST", "/_quirk/event", None, {"Content-Type": "application/json"})[0] == 400
    assert server.request("POST", "/nope", b"{}")[0] == 404
    assert server.request("GET", "/nope")[0] == 404
    assert server.events() == []


def test_detached_start_is_idempotent_and_stop_stops_it(tmp_path: Path) -> None:
    session = tmp_path / ".quirk" / "brainstorm" / "d1"
    rc, info, _ = run("start", session, "--idle-minutes", "5")
    try:
        assert rc == 0 and info["type"] == "server-started"
        assert set(info) == {"type", "pid", "port", "host", "allowed_hosts", "url", "screen_dir", "state_dir"}
        os.kill(info["pid"], 0)
        assert (session / "state" / "server.log").exists()
        rc2, again, _ = run("start", session)
        assert rc2 == 0 and again == info
        conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=10)
        conn.request("GET", "/_quirk/state")
        assert conn.getresponse().status == 200
        conn.close()
    finally:
        rc3, stopped, _ = run("stop", session)
    assert rc3 == 0 and stopped == {"stopped": True}
    assert json.loads((session / "state" / "server-stopped").read_text())["reason"] == "stop"
    rc4, stopped, _ = run("stop", session)
    assert rc4 == 0 and stopped == {"stopped": False}
    rc5, restarted, _ = run("start", session)
    try:
        assert rc5 == 0 and restarted["pid"] != info["pid"]
        assert not (session / "state" / "server-stopped").exists()
    finally:
        run("stop", session)


def test_stop_without_a_session_reports_false(tmp_path: Path) -> None:
    rc, out, _ = run("stop", tmp_path / "nothing")
    assert rc == 0 and out == {"stopped": False}


def test_usage_errors_are_one_json_object(tmp_path: Path) -> None:
    proc = subprocess.run([sys.executable, str(CLI), "bogus"], capture_output=True, text=True)
    assert proc.returncode == 2 and "error" in json.loads(proc.stdout)


def test_session_path_that_cannot_be_created_is_a_json_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    rc, out, _ = run("start", blocker / "s1")
    assert rc == 2 and "error" in out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_show_that_cannot_write_the_screen_is_a_json_error(server: Server) -> None:
    screens = server.session / "screens"
    screens.chmod(0o500)
    try:
        out = server.show(SCREEN, expect=2)
    finally:
        screens.chmod(0o700)
    assert "error" in out


@pytest.mark.parametrize("port", ["70000", "-1", "abc"])
def test_out_of_range_port_is_a_json_usage_error(tmp_path: Path, port: str) -> None:
    rc, out, _ = run("start", tmp_path / "s", "--foreground", f"--port={port}")
    assert rc == 2 and "error" in out


def test_empty_optional_strings_are_treated_as_absent(server: Server) -> None:
    spec = screen_with(
        content="",
        diagram="   ",
        options=[
            {"id": "a", "label": "A", "description": "", "html": "  "},
            {"id": "b", "label": "B", "description": "  ", "html": ""},
        ],
    )
    shown = server.show(spec)
    assert shown["checks"]["passed"] is True
    page = (server.session / "screens" / f"{shown['screen']}.html").read_text(encoding="utf-8")
    assert '<span class="q-option-desc"' not in page and '<span class="q-option-mockup"' not in page
    assert '<pre class="mermaid"' not in page and "/_quirk/lib/mermaid" not in page


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _NotACompanion(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"hello"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def bystander():
    proc = subprocess.Popen(["sleep", "60"])
    try:
        yield proc
    finally:
        proc.kill()
        proc.wait()


def _record_server(session: Path, pid: int, port: int) -> None:
    state = session / "state"
    state.mkdir(parents=True)
    (session / "screens").mkdir()
    info = {"type": "server-started", "pid": pid, "port": port, "host": "127.0.0.1"}
    (state / "server-info").write_text(json.dumps(info))


@pytest.mark.parametrize("listener", [False, True])
def test_a_reused_pid_is_never_signalled(session: Path, bystander: subprocess.Popen, listener: bool) -> None:
    httpd = None
    if listener:
        httpd = HTTPServer(("127.0.0.1", 0), _NotACompanion)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    else:
        port = _free_port()
    try:
        _record_server(session, bystander.pid, port)
        rc, out, _ = run("stop", session)
        assert rc == 0 and out == {"stopped": False}
        assert bystander.poll() is None
        assert not (session / "state" / "server-stopped").exists()
        rc, out, _ = run("wait", session, "--timeout", 1)
        assert rc == 2 and out == {"status": "no-server"}
        assert not (session / "state" / "server-stopped").exists()
        assert bystander.poll() is None
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()


def test_start_replaces_a_stale_session_whose_pid_was_reused(session: Path, bystander: subprocess.Popen) -> None:
    _record_server(session, bystander.pid, _free_port())
    rc, info, _ = run("start", session, "--idle-minutes", "5")
    try:
        assert rc == 0 and info["pid"] != bystander.pid
    finally:
        run("stop", session)
    assert bystander.poll() is None


def test_wildcard_bind_accepts_only_loopback_and_own_host_values(session: Path) -> None:
    srv = start_foreground(session, "--host", "0.0.0.0")
    try:
        assert srv.info["host"] == "0.0.0.0"
        port = srv.port
        assert srv.request("GET", "/_quirk/state")[0] == 200
        assert srv.request("GET", "/_quirk/state", headers={"Host": f"localhost:{port}"})[0] == 200
        assert srv.request("GET", "/_quirk/state", headers={"Host": f"127.0.0.1:{port}"})[0] == 200
        for host in (f"evil.example:{port}", f"127.0.0.1:{port + 1}", "127.0.0.1", f"[::1:{port}", f"8.8.8.8:{port}"):
            assert srv.request("GET", "/_quirk/state", headers={"Host": host})[0] == 403, host
        rebound = {"Host": f"evil.example:{port}", "Origin": f"http://evil.example:{port}"}
        assert srv.request("GET", "/_quirk/state", headers=rebound)[0] == 403
        assert srv.post({"nonce": "x", "type": "click"}, rebound)[0] == 403
    finally:
        stop_server(srv)


def test_a_dead_pid_is_recorded_as_stale(session: Path) -> None:
    gone = subprocess.Popen(["sleep", "60"])
    gone.kill()
    gone.wait()
    _record_server(session, gone.pid, _free_port())
    rc, out, _ = run("wait", session, "--timeout", 1)
    assert rc == 2 and out == {"status": "no-server"}
    assert json.loads((session / "state" / "server-stopped").read_text())["reason"] == "stale"


def test_a_failed_probe_on_a_live_pid_leaves_the_server_unmarked(session: Path, monkeypatch) -> None:
    _record_server(session, os.getpid(), _free_port())
    assert companion.live_server_info(session) is None
    assert not (session / "state" / "server-stopped").exists()
    monkeypatch.setattr(companion, "_answers_as_companion", lambda info: True)
    assert companion.live_server_info(session) is not None


def test_parse_authority_handles_names_ports_and_bracketed_v6() -> None:
    assert companion._parse_authority("LocalHost:80") == ("localhost", "80")
    assert companion._parse_authority("[::1]:80") == ("::1", "80")
    assert companion._parse_authority("[::1]") == ("::1", None)
    assert companion._parse_authority("nohost") == ("nohost", None)
    assert companion._parse_authority("::1") == ("::1", None)
    for bad in ("", "[::1", "[::1]x", "host:", "host:0", "host:70000", "host:ab", ":80", "a b"):
        assert companion._parse_authority(bad) is None, bad


def test_allow_host_admits_named_hosts_and_ports_on_a_wildcard_bind(session: Path) -> None:
    srv = start_foreground(session, "--host", "0.0.0.0", "--allow-host", "Devbox.Example.com", "--allow-host", "localhost:8080")
    try:
        assert srv.info["allowed_hosts"] == ["devbox.example.com", "localhost:8080"]
        port = srv.port

        def status(host: str, origin: str | None = None) -> int:
            headers = {"Host": host, **({"Origin": origin} if origin else {})}
            return srv.request("GET", "/_quirk/state", headers=headers)[0]

        assert status(f"devbox.example.com:{port}") == 200
        assert status("devbox.example.com:9999") == 200
        assert status("DEVBOX.example.com") == 200
        assert status("localhost:8080") == 200
        assert status("localhost:8081") == 403
        assert status("evil.example:8080") == 403
        assert status("devbox.example.com.evil:80") == 403
        assert status("devbox.example.com:9999", "http://devbox.example.com:9999") == 200
        assert status("devbox.example.com:9999", "http://evil.example") == 403
    finally:
        stop_server(srv)


def test_allow_host_with_a_port_pins_that_pair_on_a_loopback_bind(session: Path) -> None:
    srv = start_foreground(session, "--allow-host", "localhost:8080")
    try:
        assert srv.request("GET", "/_quirk/state", headers={"Host": "localhost:8080"})[0] == 200
        assert srv.request("GET", "/_quirk/state", headers={"Host": f"localhost:{srv.port}"})[0] == 403
        assert srv.request("GET", "/_quirk/state")[0] == 200
    finally:
        stop_server(srv)


def test_detached_start_passes_allow_host_through(tmp_path: Path) -> None:
    session = tmp_path / "s"
    rc, info, err = run("start", session, "--allow-host", "box.example:8080", "--idle-minutes", "5")
    try:
        assert rc == 0, err
        assert info["allowed_hosts"] == ["box.example:8080"]
        conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=10)
        conn.request("GET", "/_quirk/state", headers={"Host": "box.example:8080"})
        assert conn.getresponse().status == 200
        conn.close()
    finally:
        run("stop", session)


@pytest.mark.parametrize("value", ["", "a b", "host:0", "host:99999", "[::1"])
def test_malformed_allow_host_is_a_json_usage_error(tmp_path: Path, value: str) -> None:
    rc, out, _ = run("start", tmp_path / "s", "--allow-host", value)
    assert rc == 2 and "error" in out


def test_a_stalled_client_is_disconnected_within_the_handler_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(companion._Handler, "timeout", 0.5)
    httpd = companion._Server("127.0.0.1", 0, tmp_path)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        with socket.create_connection(("127.0.0.1", httpd.bound_port), timeout=5) as sock:
            host = f"127.0.0.1:{httpd.bound_port}"
            sock.sendall(
                f"POST /_quirk/event HTTP/1.1\r\nHost: {host}\r\nContent-Length: 100\r\n\r\n{{\"a\"".encode()
            )
            started = time.monotonic()
            assert sock.recv(1024) == b""
            assert time.monotonic() - started < 4
    finally:
        httpd.shutdown()
        httpd.server_close()
