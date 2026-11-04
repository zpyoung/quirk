#!/usr/bin/env python3
"""Live companion for the writing-html-artifacts skill: a local page that asks one question at a time.

``start`` runs a small HTTP server for a session directory, ``show`` builds a screen from a
``screen.json`` and makes it the current one, ``wait`` blocks until the user clicks Proceed on
the current screen, ``events`` reads what the user did and ``stop`` ends the server. Every
subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.

Exit codes: 0 success; 1 for ``show`` when a static check fails and for the ``wait`` timeout;
2 for usage errors, a malformed screen, a missing session, no live server (``wait``), a
server that never came up (``start``) or a filesystem failure. Anything that is not a failed
check or a timeout is reported as ``{"error": ...}``, except ``wait``'s
``{"status": "no-server"}``.

The server binds 127.0.0.1 by default and trusts nothing from the page except a per-screen
nonce. It never touches the network beyond its own socket.

``start --app`` runs the same server in app mode: it serves a prebuilt React shell and a
snapshot/event API over the on-disk state in ``htmlkit.appstate``, and the agent drives it with
``step``, ``status``, ``decide``, ``review``, ``mock``, ``mock-export``, ``say``, ``reply``, ``next`` and ``snapshot``. A session is in app mode
exactly when ``state/mode.json`` says so; the screen subcommands refuse an app session and the
app subcommands refuse a screen session, both with exit 2.
"""
from __future__ import annotations

import argparse
import datetime
import html as html_lib
import http.client
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NoReturn, Optional, Sequence
from urllib.parse import parse_qs, unquote, urlsplit

# the skill directory holds htmlkit and is not on sys.path when this file is run by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from htmlkit import SKILL_DIR, assemble, mocks, resolve  # noqa: E402
from htmlkit.appstate import AppState, AppStateError  # noqa: E402
from htmlkit.fsutil import atomic_write, ensure_self_ignoring  # noqa: E402
from htmlkit.header import read_header, render_header  # noqa: E402
from htmlkit.layouts import validate_layout  # noqa: E402
from htmlkit.steps import StepError, validate_step  # noqa: E402
from htmlkit.vendor import VendorError, VendorStore, shell_block  # noqa: E402

EXIT_OK, EXIT_NOT_OK, EXIT_USAGE = 0, 1, 2

MAX_BODY = 64 * 1024
DRAIN_LIMIT = 1024 * 1024
START_TIMEOUT = 10.0
STOP_TIMEOUT = 5.0
POLL_SECONDS = 0.2
DEFAULT_HOST = "127.0.0.1"
WILDCARD_HOSTS = ("0.0.0.0", "::", "")
LOOPBACK_NAMES = ("127.0.0.1", "::1", "localhost")
PROBE_TIMEOUT = 3.0
REQUEST_TIMEOUT = 10.0
OPTION_ID = re.compile(r"[a-z0-9-]{1,40}")
SLOT_LINE = re.compile(r"^<!-- slot:", re.M)
SCREEN_KEYS = {"title", "question", "select", "options", "content", "diagram", "layout"}
EVENT_TYPES = ("click", "proceed")

APP_EVENT_TYPES = ("submit", "continue", "chat", "comment", "edit-request", "edit-decision", "draft")
MAX_EXPORT_BODY = 2 * 1024 * 1024
EXPORT_DRAIN_LIMIT = 8 * 1024 * 1024
MAX_CLIENT_ID = 100
MAX_COMMENT = 4000
BLOCK_ID = re.compile(r"[A-Za-z0-9:/_.-]{1,200}")
TOKEN_HEADER = "X-Quirk-Token"
SHELL_ENV = "QUIRK_COMPANION_SHELL"
SHELL_PLACEHOLDER = '<script type="application/json" id="quirk-companion-boot">null</script>'
REVIEW_KINDS = {
    "quirk-logic-spec-decisions": "decisions",
    "quirk-approach-comparison-challenges": "challenges",
}
REVIEW_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,80}")
VERDICTS = {
    "mock-review": ("looks-right", "needs-changes", "skip"),
    "design-section": ("looks-right", "needs-changes"),
    "spec-review": ("sign-off", "changes"),
}
ANSWER_KEYS = {"selected", "other", "text", "skipped"}
MOCK_VERSION = re.compile(r"[1-9][0-9]{0,3}")
MOCK_ID_LIST_MAX = 200
MOCK_ID = re.compile(r"[a-z0-9-]{1,40}")

WAITING_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>Waiting</title></head><body>"
    "<p>Waiting for the first question. This page reloads by itself.</p>"
    "<script>setInterval(function () {"
    'fetch("/_quirk/state", {cache: "no-store"}).then(function (r) { return r.json(); })'
    ".then(function (s) { if (s && s.nonce) { location.reload(); } }).catch(function () {});"
    "}, 2000);</script></body></html>"
)

MERMAID_INIT = """(function () {
  "use strict";
  var pre = document.querySelector("pre.mermaid");
  if (!pre || typeof mermaid === "undefined") { return; }
  var source = pre.textContent;
  var drawn = null;
  var queue = Promise.resolve();
  function isDark() {
    var mode = document.documentElement.getAttribute("data-theme");
    if (mode === "dark" || mode === "light") { return mode === "dark"; }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function draw(dark) {
    if (dark === drawn) { return; }
    drawn = dark;
    queue = queue.then(function () {
      pre.removeAttribute("data-processed");
      pre.textContent = source;
      mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "default" });
      return mermaid.run({ nodes: [pre] });
    }).catch(function () {});
  }
  draw(isDark());
  document.addEventListener("quirk-theme", function (event) {
    draw(event.detail.effective === "dark");
  });
})();"""


class ScreenError(Exception):
    """The screen, the session or a build input is unusable; the author must change it."""


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        _emit({"error": message})
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def _emit(payload: dict) -> None:
    print(json.dumps(payload), flush=True)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    _emit({"error": message})
    return EXIT_USAGE


def _state_dir(session: Path) -> Path:
    return session / "state"


def _read_json(path: Path) -> Optional[object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _is_app_session(session: Path) -> bool:
    """Whether ``state/mode.json`` marks the session as app mode."""
    data = _read_json(_state_dir(session) / "mode.json")
    return isinstance(data, dict) and data.get("mode") == "app"


def _is_screen_session(session: Path) -> bool:
    """Whether the session has screen-mode artifacts and no app-mode marker.

    A screen-mode session cannot become an app session: its ``current.json`` names a screen, not a step.
    """
    if _is_app_session(session):
        return False
    state = _state_dir(session)
    current = _read_json(state / "current.json")
    if isinstance(current, dict) and current.get("mode") != "app":
        return True
    return (state / "events").exists() or any((session / "screens").glob("*.html"))


def _previous_port(state: Path) -> Optional[int]:
    """The port recorded by the session's last server, read before ``server-info`` is cleared."""
    info = _read_json(state / "server-info")
    port = info.get("port") if isinstance(info, dict) else None
    return port if isinstance(port, int) and not isinstance(port, bool) and 0 < port < 65536 else None


def _prepare_session(session: Path) -> None:
    """Create the session's directories; a ``.quirk/brainstorm`` parent becomes self-ignoring."""
    parent = session.parent
    if parent.name == "brainstorm" and parent.parent.name == ".quirk":
        ensure_self_ignoring(parent)
    (session / "screens").mkdir(parents=True, exist_ok=True)
    _state_dir(session).mkdir(parents=True, exist_ok=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _probe_target(info: dict) -> Optional[tuple[str, int]]:
    host = info.get("host")
    port = info.get("port")
    if not isinstance(host, str) or not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
        return None
    if host in WILDCARD_HOSTS:
        host = "::1" if host == "::" else "127.0.0.1"
    return host, port


def _answers_as_companion(info: dict) -> bool:
    """Whether the recorded host and port answer ``GET /_quirk/state`` the way a companion does.

    A pid can outlive its server and be reused by an unrelated process; only the companion's
    own socket answers with a JSON object carrying ``screen`` and ``nonce``.
    """
    target = _probe_target(info)
    if target is None:
        return False
    host, port = target
    conn = http.client.HTTPConnection(host, port, timeout=PROBE_TIMEOUT)
    try:
        conn.request("GET", "/_quirk/state")
        resp = conn.getresponse()
        body = json.loads(resp.read(MAX_BODY))
        return resp.status == 200 and isinstance(body, dict) and "screen" in body and "nonce" in body
    except (OSError, http.client.HTTPException, ValueError):
        return False
    finally:
        conn.close()


def live_server_info(session: Path) -> Optional[dict]:
    """The session's ``server-info`` when its companion is alive, else None.

    Dead means: no parseable ``server-info`` with an integer pid, a ``server-stopped`` file, or a
    pid that no longer exists; a session whose pid is gone and has no ``server-stopped`` file
    gets one with reason ``stale``. A live pid whose recorded port does not answer as the
    companion yields None for this call only: the pid may be reused or the probe may have been
    transient, so nothing is recorded and the pid is never signalled.
    """
    state = _state_dir(session)
    if (state / "server-stopped").exists():
        return None
    info = _read_json(state / "server-info")
    pid = info.get("pid") if isinstance(info, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    if _pid_alive(pid):
        return info if _answers_as_companion(info) else None
    try:
        if not (state / "server-stopped").exists():
            _write_stopped(state, "stale")
    except OSError:
        pass
    return None


def _read_events(session: Path) -> list[dict]:
    try:
        text = (_state_dir(session) / "events").read_text(encoding="utf-8")
    except OSError:
        return []
    records = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _normalized_ip(text: str) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(text.split("%", 1)[0]))
    except ValueError:
        return None


def _parse_authority(text: str) -> Optional[tuple[str, Optional[str]]]:
    """Split ``HOST``, ``HOST:PORT``, ``[v6]`` or ``[v6]:PORT`` into lowercase name and optional port.

    A bare IPv6 literal such as ``::1`` is a host with no port. Returns None for an empty name,
    a malformed bracket, or a port that is not 1-65535.
    """
    if text.startswith("["):
        name, sep, rest = text[1:].partition("]")
        if not sep or (rest and not rest.startswith(":")):
            return None
        port: Optional[str] = rest[1:] if rest else None
    elif text.count(":") == 1:
        name, _, port = text.partition(":")
    else:
        name, port = text, None
    if not name or not re.fullmatch(r"[A-Za-z0-9._:%-]+", name):
        return None
    if port is not None and not (port.isascii() and port.isdigit() and 0 < int(port) < 65536):
        return None
    return name.lower(), port


def _same_host(a: str, b: str) -> bool:
    ip_a, ip_b = _normalized_ip(a), _normalized_ip(b)
    return a == b if ip_a is None or ip_b is None else ip_a == ip_b


def _allow_host(value: str) -> str:
    """argparse type for ``--allow-host``: a valid ``HOST`` or ``HOST:PORT``, lowercased."""
    parsed = _parse_authority(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"expected HOST or HOST:PORT, got {value!r}")
    return value.lower()


def _own_addresses() -> frozenset:
    """Loopback addresses plus every address this machine's hostname resolves to."""
    found = {_normalized_ip(name) for name in LOOPBACK_NAMES}
    hostname = socket.gethostname()
    try:
        found.update(_normalized_ip(addr) for addr in socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    try:
        found.update(_normalized_ip(info[4][0]) for info in socket.getaddrinfo(hostname, None))
    except OSError:
        pass
    found.discard(None)
    return frozenset(found)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, host: str, port: int, session: Path, allowed_hosts: Sequence[str] = (), app: bool = False
    ) -> None:
        self.address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
        self.session = session
        self.app = app
        self.app_state = AppState(session) if app else None
        self.token = self.app_state.token() if self.app_state else ""
        self.bound_host = host
        self.allowed_hosts = [parsed for parsed in map(_parse_authority, allowed_hosts) if parsed is not None]
        self.event_lock = threading.Lock()
        self.last_request = time.monotonic()
        self.own_addresses = _own_addresses() if host in WILDCARD_HOSTS else frozenset()
        super().__init__((host, port), _Handler)
        self.bound_port = self.server_address[1]

    def expected_host(self) -> str:
        host = f"[{self.bound_host}]" if ":" in self.bound_host else self.bound_host
        return f"{host}:{self.bound_port}"

    def host_allowed(self, header: Optional[str]) -> bool:
        """Whether a request's Host names this server.

        Accepted: the bound host and port; on a wildcard bind, loopback or an own interface
        address on the bound port; or an ``--allow-host`` entry (a bare host allows any port,
        ``HOST:PORT`` that exact pair). Any other name, including a rebinding page's, is refused.
        """
        if header is None:
            return False
        if self.bound_host not in WILDCARD_HOSTS and header == self.expected_host():
            return True
        parsed = _parse_authority(header)
        if parsed is None or (":" in parsed[0] and not header.startswith("[")):
            return False
        name, port = parsed
        if self.bound_host in WILDCARD_HOSTS and port == str(self.bound_port):
            if name == "localhost" or _normalized_ip(name) in self.own_addresses:
                return True
        return any(
            _same_host(name, allowed_name) and (allowed_port is None or allowed_port == port)
            for allowed_name, allowed_port in self.allowed_hosts
        )

    def current(self) -> Optional[dict]:
        data = _read_json(_state_dir(self.session) / "current.json")
        if isinstance(data, dict) and isinstance(data.get("screen"), str) and isinstance(data.get("nonce"), str):
            return data
        return None

    def idle_seconds(self) -> float:
        idle = time.monotonic() - self.last_request
        try:
            shown = time.time() - (_state_dir(self.session) / "current.json").stat().st_mtime
        except OSError:
            return idle
        return min(idle, shown)


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    server_version = "quirk-companion"
    timeout = REQUEST_TIMEOUT

    def log_message(self, format: str, *args: object) -> None:
        return

    def _reply(self, status: int, body: bytes = b"", content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if status != 204 and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        self._reply(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _guard(self) -> bool:
        """Count the request as activity and refuse a foreign Host or Origin with 403."""
        self.server.last_request = time.monotonic()
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not self.server.host_allowed(host) or (origin is not None and origin != f"http://{host}"):
            self._reply(403, b"forbidden\n")
            return False
        return True

    def do_GET(self) -> None:
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path == "/":
            if self.server.app:
                self._serve_shell()
            else:
                self._serve_screen()
        elif path == "/_quirk/state":
            current = self.server.current() or {}
            state = {"screen": current.get("screen"), "nonce": current.get("nonce")}
            self._json(200, {**state, "mode": "app"} if self.server.app else state)
        elif self.server.app and path == "/_quirk/app/snapshot":
            self._serve_snapshot()
        elif self.server.app and path == "/_quirk/review":
            self._serve_review()
        elif self.server.app and path.startswith("/_quirk/mock/"):
            self._serve_mock(path[len("/_quirk/mock/") :])
        elif path.startswith("/_quirk/lib/"):
            self._serve_library(path[len("/_quirk/lib/") :])
        else:
            self._reply(404, b"not found\n")

    def do_POST(self) -> None:
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if self.server.app and path == "/_quirk/app/event":
            self._accept_app_event()
        elif self.server.app and path == "/_quirk/review/export":
            self._accept_review_export()
        elif not self.server.app and path == "/_quirk/event":
            self._accept_event()
        else:
            self._reply(404, b"not found\n")

    def _serve_screen(self) -> None:
        current = self.server.current()
        page: Optional[bytes] = None
        if current is not None:
            name = current["screen"]
            if re.fullmatch(r"[A-Za-z0-9._-]+", name):
                try:
                    page = (self.server.session / "screens" / f"{name}.html").read_bytes()
                except OSError:
                    page = None
        self._reply(200, page if page is not None else WAITING_PAGE.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_shell(self) -> None:
        """The prebuilt app shell with the session token written into its boot element."""
        override = os.environ.get(SHELL_ENV)
        shell = Path(override) if override else Path(__file__).resolve().parent.parent / "companion-app" / "shell.html"
        try:
            text = shell.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            text = ""
        if text.count(SHELL_PLACEHOLDER) != 1:
            self._json(500, {"error": "companion shell not built"})
            return
        boot = json.dumps(
            {"token": self.server.token, "session": self.server.session.resolve().name}, separators=(",", ":")
        ).replace("<", "\\u003c")
        page = text.replace(SHELL_PLACEHOLDER, SHELL_PLACEHOLDER.replace("null", boot))
        self._reply(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_snapshot(self) -> None:
        snapshot = self.server.app_state.snapshot()
        wanted = parse_qs(urlsplit(self.path).query).get("rev", [""])[0]
        if wanted.isascii() and wanted.isdigit() and int(wanted) == snapshot["rev"]:
            self._reply(204)
        else:
            self._json(200, snapshot)

    def _serve_review(self) -> None:
        path = self.server.app_state.review_path()
        try:
            page = path.read_bytes() if path is not None else None
        except OSError:
            page = None
        if page is None:
            self._reply(404, b"not found\n")
        else:
            self._reply(200, page, "text/html; charset=utf-8")

    def _serve_mock(self, rest: str) -> None:
        """A registered mock version inside the harness page; needs the session token in ``?t=``."""
        given = parse_qs(urlsplit(self.path).query).get("t", [""])[0]
        if not secrets.compare_digest(given.encode("utf-8"), self.server.token.encode("utf-8")):
            self._json(403, {"error": "bad token"})
            return
        app_state = self.server.app_state
        mock = app_state.get_mock(int(rest)) if MOCK_VERSION.fullmatch(rest) else None
        if mock is None:
            self._reply(404, b"not found\n")
            return
        index = app_state.mocks_index()
        boot = mocks.make_boot(
            mode="app", version=mock["version"], latest=index["latest"], versions=index["versions"],
            screens=mock["screens"], changed=mock["changed"], mock_html=mock["html"], revision=mock["revision"],
            token=self.server.token,
        )
        try:
            page = mocks.fill_template(*mocks.load_template(), boot)
        except mocks.MockError:
            self._json(500, {"error": "mock harness missing"})
            return
        self._reply(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_library(self, rest: str) -> None:
        parts = [unquote(p) for p in rest.split("/")]
        if len(parts) < 3:
            self._reply(404, b"not found\n")
            return
        name, version, rel = parts[0], parts[1], "/".join(parts[2:])
        path = _library_file(name, version, rel)
        if path is None:
            self._reply(404, b"not found\n")
            return
        kind = {".js": "text/javascript", ".css": "text/css"}.get(path.suffix) or (
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        try:
            self._reply(200, path.read_bytes(), kind)
        except OSError:
            self._reply(404, b"not found\n")

    def _drain(self, length: int, limit: int = DRAIN_LIMIT) -> None:
        remaining = min(length, limit)
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    def _accept_event(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            self._json(400, {"error": "a Content-Length is required"})
            return
        if length > MAX_BODY:
            self._drain(length)
            self.close_connection = True
            self._json(400, {"error": f"body is over {MAX_BODY} bytes"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except OSError:
            self.close_connection = True
            return
        except (ValueError, RecursionError):
            self._json(400, {"error": "body is not valid JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return
        current = self.server.current()
        if current is None or payload.get("nonce") != current["nonce"]:
            self._json(409, {"superseded": True})
            return
        problem = _event_problem(payload)
        if problem:
            self._json(400, {"error": problem})
            return
        record = {
            "type": payload["type"],
            "screen": current["screen"],
            "nonce": current["nonce"],
            "choice": payload.get("choice"),
            "text": payload.get("text", ""),
            "selected": payload.get("selected", []),
            "note": payload.get("note"),
            "timestamp": time.time(),
        }
        with self.server.event_lock:
            latest = self.server.current()
            if latest is None or latest["nonce"] != current["nonce"]:
                self._json(409, {"superseded": True})
                return
            with open(_state_dir(self.server.session) / "events", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        self._reply(204)

    def _check_token(self) -> bool:
        """Refuse an app POST that lacks the session token; the unread body is drained first."""
        given = self.headers.get(TOKEN_HEADER, "")
        if secrets.compare_digest(given.encode("utf-8"), self.server.token.encode("utf-8")):
            return True
        try:
            self._drain(int(self.headers.get("Content-Length", "0")))
        except ValueError:
            pass
        self.close_connection = True
        self._json(403, {"error": "bad token"})
        return False

    def _read_object(self, limit: int, over_status: int, drain_limit: int = DRAIN_LIMIT) -> Optional[dict]:
        """The request body as a JSON object, or None after replying with the matching error."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            self._json(400, {"error": "a Content-Length is required"})
            return None
        if length > limit:
            self._drain(length, drain_limit)
            self.close_connection = True
            self._json(over_status, {"error": f"body is over {limit} bytes"})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except OSError:
            self.close_connection = True
            return None
        except (ValueError, RecursionError):
            self._json(400, {"error": "body is not valid JSON"})
            return None
        if not isinstance(payload, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return None
        return payload

    def _accept_app_event(self) -> None:
        if not self._check_token():
            return
        body = self._read_object(MAX_BODY, 400)
        if body is None:
            return
        client_id = body.get("client_id")
        if not isinstance(client_id, str) or not 0 < len(client_id) <= MAX_CLIENT_ID:
            self._json(400, {"error": f"client_id must be a string of 1 to {MAX_CLIENT_ID} characters"})
            return
        kind = body.get("type")
        if not isinstance(kind, str) or kind not in APP_EVENT_TYPES:
            self._json(400, {"error": "unsupported event type"})
            return
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            self._json(400, {"error": "payload must be an object"})
            return
        app = self.server.app_state
        try:
            with app.lock():
                status, reply = self._record_app_event(app, kind, client_id, body.get("nonce"), body.get("step"), payload)
        except AppStateError as exc:
            status, reply = 400, {"error": str(exc), "field": exc.field}
        if reply is None:
            self._reply(status)
        else:
            self._json(status, reply)

    def _record_app_event(
        self, app: AppState, kind: str, client_id: str, nonce: object, draft_step: object, payload: dict
    ) -> tuple[int, Optional[dict]]:
        """Validate one app event against the current step and store it; runs under the state lock.

        ``draft_step`` is the step id a draft belongs to; a draft for any step but the current one is
        superseded and saves nothing. A ``continue`` is recorded even before the first step exists.
        """
        current = self.server.current()
        if kind == "draft" and not (isinstance(draft_step, str) and draft_step):
            return 400, {"error": "a draft must name its step"}
        if kind != "draft" and any(e.get("client_id") == client_id for e in app.events_after(0)):
            return 200, {"duplicate": True}
        if kind in ("chat", "comment"):
            return self._record_conversation(app, kind, client_id, payload, current)
        needs_nonce = kind in ("submit", "edit-decision")
        if needs_nonce and (current is None or nonce != current["nonce"]):
            return 409, {"superseded": True}
        if current is None:
            if kind == "continue" and not payload:
                if app.append_event(kind, payload, client_id, step=None) is None:
                    return 200, {"duplicate": True}
                return 204, None
            return 400, {"error": "no step is current"}
        if kind == "draft" and draft_step != current["screen"]:
            return 409, {"superseded": True}
        step = _read_json(_state_dir(self.server.session) / "steps" / f"{current['screen']}.json")
        if not isinstance(step, dict):
            return 400, {"error": "the current step is unreadable"}
        problem = _app_event_problem(kind, step, payload, app)
        if problem:
            return 400, {"error": problem}
        if kind == "draft":
            app.save_draft(current["screen"], payload)
            return 204, None
        if app.append_event(kind, payload, client_id, step=current["screen"]) is None:
            return 200, {"duplicate": True}
        return 204, None

    def _record_conversation(
        self, app: AppState, kind: str, client_id: str, payload: dict, current: Optional[dict]
    ) -> tuple[int, Optional[dict]]:
        """Store a ``chat`` or ``comment`` event; runs under the state lock, after the duplicate check.

        Both stay valid across steps, so neither needs the step nonce. A comment's stored payload always
        carries the thread id the server resolved, so the agent can reply to it.
        """
        problem = _conversation_problem(kind, payload, app)
        if problem:
            return 400, {"error": problem}
        step_id = current["screen"] if current else None
        if kind == "chat":
            seq = app.append_event(kind, payload, client_id, step=step_id)
            if seq is None:
                return 200, {"duplicate": True}
            app.append_chat("user", payload["text"], event_seq=seq)
            return 204, None
        thread_id = app.add_comment(payload["block_id"], step_id, payload["text"], payload.get("thread_id"))
        stored = {"block_id": payload["block_id"], "text": payload["text"], "thread_id": thread_id}
        if app.append_event(kind, stored, client_id, step=step_id) is None:
            return 200, {"duplicate": True}
        return 204, None

    def _accept_review_export(self) -> None:
        if not self._check_token():
            return
        body = self._read_object(MAX_EXPORT_BODY, 413, EXPORT_DRAIN_LIMIT)
        if body is None:
            return
        kind, slug = body.get("kind"), body.get("slug")
        if not isinstance(kind, str) or kind not in REVIEW_KINDS:
            self._json(400, {"error": f"kind must be one of {', '.join(REVIEW_KINDS)}"})
            return
        if not isinstance(slug, str) or not REVIEW_SLUG.fullmatch(slug):
            self._json(400, {"error": "slug must match [a-z0-9][a-z0-9-]{0,80}"})
            return
        app = self.server.app_state
        review = app.review_path()
        if review is None:
            self._json(404, {"error": "no review is registered"})
            return
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            with app.lock():
                target = review.parent / f"{slug}-{REVIEW_KINDS[kind]}-{stamp}.json"
                copy = 2
                while target.exists():
                    target = review.parent / f"{slug}-{REVIEW_KINDS[kind]}-{stamp}-{copy}.json"
                    copy += 1
                atomic_write(target, json.dumps(body, indent=2, ensure_ascii=False))
                app.append_event(
                    "review-export",
                    {"path": str(target), "kind": kind, "stage": body.get("stage"), "signed": body.get("signed")},
                    client_id=f"review-export-{uuid.uuid4().hex}",
                    step=(self.server.current() or {}).get("screen"),
                )
        except OSError as exc:
            self._json(500, {"error": f"cannot write the export: {exc}"})
            return
        self._json(200, {"path": str(target)})


def _app_event_problem(kind: str, step: dict, payload: dict, app: AppState) -> Optional[str]:
    """Why ``payload`` is not a valid ``kind`` event for ``step``, or None."""
    if kind == "draft":
        if set(payload) - {"answers", "comment", "pick"}:
            return "a draft carries only answers, comment and pick"
        if "answers" in payload and not isinstance(payload["answers"], dict):
            return "answers must be an object"
        if "pick" in payload and not isinstance(payload["pick"], str):
            return "pick must be a string"
        return _comment_problem(payload)
    if kind == "continue":
        return None if not payload else "continue takes an empty payload"
    if kind == "edit-request":
        extra = set(payload) - {"decision_id", "to", "note"}
        if extra:
            return f"unknown payload field(s): {', '.join(sorted(extra))}"
        decision_id = payload.get("decision_id")
        if not isinstance(decision_id, str) or decision_id not in {d.get("id") for d in app.snapshot()["decisions"]}:
            return "decision_id must name an existing decision"
        for key in ("to", "note"):
            if key in payload and not (isinstance(payload[key], str) and len(payload[key]) <= MAX_COMMENT):
                return f"{key} must be a string of at most {MAX_COMMENT} characters"
        return None
    if kind == "edit-decision":
        if step.get("kind") != "edit-card":
            return "edit-decision is only valid on an edit-card step"
        if set(payload) != {"decision"} or not isinstance(payload["decision"], str) or payload["decision"] not in ("confirm", "cancel"):
            return "payload must be {decision: confirm|cancel}"
        return None
    return _submit_problem(step, payload)


def _conversation_problem(kind: str, payload: dict, app: AppState) -> Optional[str]:
    """Why ``payload`` is not a valid ``chat`` or ``comment`` event, or None; every field is type-checked first."""
    allowed = {"text"} if kind == "chat" else {"block_id", "text", "thread_id"}
    extra = set(payload) - allowed
    if extra:
        return f"unknown payload field(s): {', '.join(sorted(extra))}"
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_COMMENT:
        return f"text must be a non-empty string of at most {MAX_COMMENT} characters"
    if kind == "chat":
        return None
    block_id = payload.get("block_id")
    if not isinstance(block_id, str) or not BLOCK_ID.fullmatch(block_id):
        return "block_id must be 1 to 200 characters of A-Z a-z 0-9 : / _ . -"
    if "thread_id" in payload:
        thread_id = payload["thread_id"]
        if not isinstance(thread_id, str) or thread_id not in {t.get("id") for t in app.snapshot()["threads"]}:
            return "thread_id must name an existing thread"
    return None


def _comment_problem(payload: dict) -> Optional[str]:
    comment = payload.get("comment")
    if "comment" in payload and not (isinstance(comment, str) and len(comment) <= MAX_COMMENT):
        return f"comment must be a string of at most {MAX_COMMENT} characters"
    return None


def _submit_problem(step: dict, payload: dict) -> Optional[str]:
    """Why ``payload`` is not a valid ``submit`` for ``step``'s kind, or None."""
    kind = step.get("kind")
    if kind in ("done", "edit-card"):
        return f"a {kind} step takes no submit"
    if kind == "spec-review" and step.get("format") == "interactive":
        return "an interactive spec review is exported with review-export, not submit"
    field = {"questions": "answers", "approaches": "pick", "hand-off": "pick"}.get(kind, "verdict")
    extra = set(payload) - {field, "comment"} - ({"visited", "marks"} if kind == "mock-review" else set())
    if extra:
        return f"unknown payload field(s): {', '.join(sorted(extra))}"
    problem = _comment_problem(payload)
    if problem:
        return problem
    if kind == "mock-review":
        for key in ("visited", "marks"):
            if key in payload and not _mock_ids_ok(payload[key]):
                return f"{key} must be a list of at most {MOCK_ID_LIST_MAX} screen ids matching [a-z0-9-]{{1,40}}"
    value = payload.get(field)
    if kind == "questions":
        return _answers_problem(step, value)
    if kind == "approaches":
        allowed = [a.get("id") for a in step.get("approaches", [])]
    elif kind == "hand-off":
        allowed = [c.get("id") for c in step.get("choices", [])]
    else:
        allowed = list(VERDICTS.get(kind, ()))
    if not isinstance(value, str) or value not in allowed:
        return f"{field} must be one of {', '.join(map(str, allowed))}"
    return None


def _mock_ids_ok(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= MOCK_ID_LIST_MAX
        and all(isinstance(v, str) and MOCK_ID.fullmatch(v) for v in value)
    )


def _answers_problem(step: dict, answers: object) -> Optional[str]:
    if not isinstance(answers, dict):
        return "answers must be an object"
    questions = {q.get("id"): q for q in step.get("questions", [])}
    for qid, answer in answers.items():
        if qid not in questions:
            return f"answers.{qid}: not a question of this step"
        if not isinstance(answer, dict):
            return f"answers.{qid} must be an object"
        extra = set(answer) - ANSWER_KEYS
        if extra:
            return f"answers.{qid}: unknown field(s): {', '.join(sorted(extra))}"
        options = {o.get("id") for o in questions[qid].get("options", [])}
        selected = answer.get("selected", [])
        if not isinstance(selected, list) or not all(isinstance(o, str) and o in options for o in selected):
            return f"answers.{qid}.selected must list option ids of that question"
        for key in ("other", "text"):
            if key in answer and not isinstance(answer[key], str):
                return f"answers.{qid}.{key} must be a string"
        if "skipped" in answer and answer["skipped"] is not True:
            return f"answers.{qid}.skipped must be true"
    return None


def _event_problem(payload: dict) -> Optional[str]:
    if payload.get("type") not in EVENT_TYPES:
        return f"type must be one of {', '.join(EVENT_TYPES)}"
    if not (payload.get("choice") is None or isinstance(payload.get("choice"), str)):
        return "choice must be a string or null"
    if not isinstance(payload.get("text", ""), str):
        return "text must be a string"
    selected = payload.get("selected", [])
    if not isinstance(selected, list) or not all(isinstance(s, str) for s in selected):
        return "selected must be a list of strings"
    if not (payload.get("note") is None or isinstance(payload.get("note"), str)):
        return "note must be a string or null"
    return None


def _library_file(name: str, version: str, rel: str) -> Optional[Path]:
    """The vendored file for ``/_quirk/lib/<name>/<version>/<rel>``, only when ``libraries.json`` lists it."""
    registry = _read_json(SKILL_DIR / "vendor" / "libraries.json")
    try:
        files = registry["libraries"][name]["versions"][version]["files"]
    except (KeyError, TypeError):
        return None
    if not any(isinstance(f, dict) and f.get("path") == rel for f in files):
        return None
    root = (SKILL_DIR / "vendor" / name / version).resolve()
    path = (root / rel).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def _write_stopped(state: Path, reason: str) -> None:
    atomic_write(state / "server-stopped", json.dumps({"reason": reason, "at": time.time()}))


def _reuse_live_server(existing: dict, host: Optional[str], allowed_hosts: Sequence[str]) -> int:
    """Emit a live server's info, or refuse when explicit host flags contradict its settings.

    Flags left at their defaults (no ``--host``, no ``--allow-host``) always reuse.
    """
    differs = (host is not None and host != existing.get("host")) or (
        bool(allowed_hosts) and set(allowed_hosts) != set(existing.get("allowed_hosts") or [])
    )
    if differs:
        return _fail("a companion server is already running for this session with different host settings; run stop first, then start again")
    _emit(existing)
    return EXIT_OK


def _mode_conflict(session: Path, app: bool, existing: Optional[dict]) -> Optional[int]:
    """Exit code 2 (after reporting) when ``start`` asks for a mode the session is not in."""
    if existing is not None:
        running = existing.get("mode", "screen")
        if (running == "app") != app:
            return _fail(
                f"a companion server is already running for this session in {running} mode; run stop first, then start again"
            )
    elif not app and _is_app_session(session):
        return _fail("session is in app mode; start it with --app")
    elif app and _is_screen_session(session):
        return _fail("session is a screen-mode session")
    return None


def _bind(host: str, ports: Sequence[int], session: Path, allowed_hosts: Sequence[str], app: bool) -> _Server:
    """A server on the first of ``ports`` that binds; raises the last OSError when none does."""
    error: Optional[OSError] = None
    for port in ports:
        try:
            return _Server(host, port, session, allowed_hosts, app)
        except OSError as exc:
            error = exc
    assert error is not None
    raise error


def _serve(
    session: Path,
    host: Optional[str],
    port: int,
    idle_minutes: float,
    allowed_hosts: Sequence[str] = (),
    app: bool = False,
    prefer_port: Optional[int] = None,
) -> int:
    """Run the server in this process until it is stopped, idle or signalled."""
    existing = live_server_info(session)
    conflict = _mode_conflict(session, app, existing)
    if conflict is not None:
        return conflict
    if existing is not None:
        return _reuse_live_server(existing, host, allowed_hosts)
    host = DEFAULT_HOST if host is None else host
    _prepare_session(session)
    state = _state_dir(session)
    if app:
        if prefer_port is None:
            prefer_port = _previous_port(state)
        AppState(session).init()
        atomic_write(state / "mode.json", json.dumps({"mode": "app"}))
    for stale in ("server-stopped", "server-info"):
        (state / stale).unlink(missing_ok=True)
    ports = [prefer_port, port] if prefer_port and prefer_port != port else [port]
    try:
        httpd = _bind(host, ports, session, allowed_hosts, app)
    except OSError as exc:
        return _fail(f"cannot listen on {host}:{port}: {exc}")
    shown_host = "127.0.0.1" if host in WILDCARD_HOSTS else (f"[{host}]" if ":" in host else host)
    info = {
        "type": "server-started",
        "pid": os.getpid(),
        "port": httpd.bound_port,
        "host": host,
        "allowed_hosts": list(allowed_hosts),
        "url": f"http://{shown_host}:{httpd.bound_port}/",
        "screen_dir": str(session / "screens"),
        "state_dir": str(state),
    }
    if app:
        info["mode"] = "app"
    stop = threading.Event()
    reason = {"value": "signal"}

    def on_signal(signum: int, _frame: object) -> None:
        reason["value"] = "stop" if signum == signal.SIGTERM else "signal"
        stop.set()

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, on_signal)
    atomic_write(state / "server-info", json.dumps(info))
    _emit(info)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    limit = idle_minutes * 60
    while not stop.wait(0.1):
        if httpd.idle_seconds() >= limit:
            reason["value"] = "idle"
            break
    httpd.shutdown()
    httpd.server_close()
    _write_stopped(state, reason["value"])
    return EXIT_OK


def _cmd_start(args: argparse.Namespace) -> int:
    session = Path(args.session)
    if args.foreground:
        return _serve(session, args.host, args.port, args.idle_minutes, args.allow_host, args.app, args.prefer_port)
    existing = live_server_info(session)
    conflict = _mode_conflict(session, args.app, existing)
    if conflict is not None:
        return conflict
    if existing is not None:
        return _reuse_live_server(existing, args.host, args.allow_host)
    _prepare_session(session)
    state = _state_dir(session)
    prefer_port = _previous_port(state) if args.app else None
    if args.app:
        AppState(session).init()
        atomic_write(state / "mode.json", json.dumps({"mode": "app"}))
    for stale in ("server-stopped", "server-info"):
        (state / stale).unlink(missing_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "start",
        str(session),
        "--foreground",
        "--host",
        DEFAULT_HOST if args.host is None else args.host,
        "--port",
        str(args.port),
        "--idle-minutes",
        str(args.idle_minutes),
    ]
    for entry in args.allow_host:
        command += ["--allow-host", entry]
    if args.app:
        command.append("--app")
        if prefer_port:
            command += ["--prefer-port", str(prefer_port)]
    with open(state / "server.log", "ab") as log:
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        info = _read_json(state / "server-info")
        if isinstance(info, dict) and info.get("pid") == child.pid:
            _emit(info)
            return EXIT_OK
        if child.poll() is not None:
            return _fail(f"the companion server exited with code {child.returncode}; see {state / 'server.log'}")
        time.sleep(0.05)
    return _fail(f"the companion server wrote no server-info within {START_TIMEOUT:.0f}s; see {state / 'server.log'}")


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-")
    return slug or "screen"


def _next_screen_number(screens: Path) -> int:
    numbers = [int(m.group(1)) for p in screens.glob("*.html") if (m := re.match(r"(\d{4,})-", p.name))]
    return max(numbers, default=0) + 1


def _given(spec: dict, key: str) -> Optional[str]:
    """``spec[key]`` when it is a string with visible content, else None."""
    value = spec.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _text(spec: dict, key: str, required: bool) -> Optional[str]:
    """A required non-empty string, or an optional one where None, "" and whitespace mean absent."""
    value = spec.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ScreenError(f"{key!r} must be a non-empty string")
    return _given(spec, key)


def load_screen(path: Path) -> dict:
    """Read and validate a ``screen.json``; raises ScreenError describing the first problem."""
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ScreenError(f"cannot read screen {path}: {exc}") from exc
    except (ValueError, RecursionError) as exc:
        raise ScreenError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise ScreenError("screen.json must be a JSON object")
    unknown = sorted(set(spec) - SCREEN_KEYS)
    if unknown:
        raise ScreenError(f"unknown screen field(s): {', '.join(unknown)}")
    _text(spec, "title", True)
    _text(spec, "question", True)
    _text(spec, "content", False)
    _text(spec, "diagram", False)
    if spec.get("layout") is not None:
        try:
            validate_layout(spec["layout"], origin="screen.json key 'layout'")
        except assemble.SourceError as exc:
            raise ScreenError(str(exc)) from exc
    if spec.get("select", "single") not in ("single", "multi"):
        raise ScreenError("'select' must be single or multi")
    items = spec.get("options")
    if not isinstance(items, list) or not 2 <= len(items) <= 4:
        raise ScreenError("'options' must be a list of 2 to 4 options")
    seen: set[str] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ScreenError(f"options[{i}] must be an object")
        ident = item.get("id")
        if not isinstance(ident, str) or not OPTION_ID.fullmatch(ident):
            raise ScreenError(f"options[{i}].id must match [a-z0-9-]{{1,40}}")
        if ident in seen:
            raise ScreenError(f"option id {ident!r} is used twice")
        seen.add(ident)
        _text(item, "label", True)
        for key in ("description", "html"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ScreenError(f"options[{i}].{key} must be a string")
    for fragment in [spec.get("content") or ""] + [o.get("html") or "" for o in items]:
        if SLOT_LINE.search(fragment):
            raise ScreenError("content and option html may not contain a line starting with '<!-- slot:'")
    return spec


def _option_cards(spec: dict, nonce: str) -> str:
    multi = spec.get("select", "single") == "multi"
    attr = html_lib.escape
    cards = []
    for i, option in enumerate(spec["options"]):
        state = 'aria-pressed="false"' if multi else f'role="radio" aria-checked="false" tabindex="{0 if i == 0 else -1}"'
        parts = [f'<span class="q-option-label">{attr(option["label"])}</span>']
        if _given(option, "description"):
            parts.append(f'<span class="q-option-desc">{attr(option["description"])}</span>')
        if _given(option, "html"):
            parts.append(f'<span class="q-option-mockup">{option["html"]}</span>')
        cards.append(
            f'<button type="button" class="q-option" {state} '
            f'data-option-id="{attr(option["id"])}" data-label="{attr(option["label"])}">\n'
            + "\n".join(parts)
            + "\n</button>"
        )
    role = "group" if multi else "radiogroup"
    return (
        f'<div class="q-options" role="{role}" aria-labelledby="q-question" '
        f'data-quirk-nonce="{attr(nonce)}" data-select="{"multi" if multi else "single"}">\n'
        + "\n".join(cards)
        + "\n</div>"
    )


def _mermaid_version() -> str:
    store = VendorStore([SKILL_DIR / "vendor" / "libraries.json"])
    try:
        return store.resolve("mermaid", None).version
    except VendorError as exc:
        raise ScreenError(str(exc)) from exc


def _source_text(spec: dict, nonce: str) -> str:
    content = _given(spec, "content") or ""
    if _given(spec, "diagram"):
        figure = f'<figure class="q-diagram"><pre class="mermaid">{html_lib.escape(spec["diagram"])}</pre></figure>'
        content = f"{content}\n{figure}" if content else figure
    meta = {"template": "companion", "title": spec["title"], "mode": "offline"}
    if spec.get("layout") is not None:
        meta["layout"] = spec["layout"]
    header = json.dumps(meta)
    slots = {
        "question": f'<h2 id="q-question">{html_lib.escape(spec["question"])}</h2>',
        "options": _option_cards(spec, nonce),
        "content": content,
    }
    body = "\n".join(f"<!-- slot: {name} -->\n{text}" for name, text in slots.items())
    return f"<!-- quirk-src {header} -->\n{body}\n"


def _finish_page(page: str, spec: dict) -> str:
    """Mark the built page as companion mode and add the scripts the skeleton cannot carry.

    ``assemble`` builds offline pages; the companion header, the companion shell block and the
    served Mermaid script are added here, and ``check_artifact`` then verifies the result in
    companion mode from that header.
    """
    first, header_line, rest = page.split("\n", 2)
    meta = read_header(page)
    if meta is None:
        raise ScreenError("the built screen has no header")
    meta["mode"] = "companion"
    extra = [shell_block("companion", SKILL_DIR / "templates" / "companion" / "companion.js").text]
    if _given(spec, "diagram"):
        extra.append(f'<script src="/_quirk/lib/mermaid/{_mermaid_version()}/mermaid.min.js"></script>')
        extra.append(f"<script>\n{MERMAID_INIT}\n</script>")
    page = f"{first}\n{render_header(meta)}\n{rest}"
    end = page.rfind("</body>")
    if end < 0:
        raise ScreenError("the companion skeleton has no </body>")
    return page[:end] + "\n".join(extra) + "\n" + page[end:]


def _build_screen(spec: dict, nonce: str, project_dir: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="quirk-companion-") as tmp:
        source = Path(tmp) / "screen.src.html"
        source.write_text(_source_text(spec, nonce), encoding="utf-8")
        built = Path(tmp) / "screen.html"
        try:
            assemble.build_tier1(
                source,
                out=built,
                upgrade=False,
                project_dir=project_dir,
                user_dir=resolve.default_user_dir(),
            )
        except assemble.BuildError as exc:
            raise ScreenError(str(exc)) from exc
        return _finish_page(built.read_text(encoding="utf-8"), spec)


def _cmd_show(args: argparse.Namespace) -> int:
    session = Path(args.session)
    if _is_app_session(session):
        return _fail("session is in app mode")
    state = _state_dir(session)
    if not state.is_dir() or not (session / "screens").is_dir():
        return _fail(f"{session} is not a companion session; run start first")
    try:
        spec = load_screen(Path(args.screen))
        project_dir = Path(args.project_dir) if args.project_dir else resolve.default_project_dir()
        nonce = secrets.token_urlsafe(16)
        page = _build_screen(spec, nonce, project_dir)
        screens = session / "screens"
        screen_id = f"{_next_screen_number(screens):04d}-{_slugify(spec['title'])}"
        path = screens / f"{screen_id}.html"
        atomic_write(path, page)
        checks = assemble.check_artifact(path, project_dir=project_dir, user_dir=resolve.default_user_dir())
    except (ScreenError, assemble.BuildError) as exc:
        return _fail(str(exc))
    if checks["passed"]:
        atomic_write(state / "current.json", json.dumps({"screen": screen_id, "nonce": nonce, "shown_at": time.time()}))
    info = _read_json(state / "server-info")
    url = info.get("url") if isinstance(info, dict) else None
    _emit({"screen": screen_id, "nonce": nonce, "url": url, "checks": checks})
    return EXIT_OK if checks["passed"] else EXIT_NOT_OK


def _cmd_wait(args: argparse.Namespace) -> int:
    session = Path(args.session)
    if _is_app_session(session):
        return _fail("session is in app mode")
    deadline = time.monotonic() + args.timeout
    current: Optional[dict] = None
    while True:
        if live_server_info(session) is None:
            _emit({"status": "no-server"})
            print("no live companion server for this session; run start", file=sys.stderr)
            return EXIT_USAGE
        if current is None:
            data = _read_json(_state_dir(session) / "current.json")
            current = data if isinstance(data, dict) and isinstance(data.get("shown_at"), (int, float)) else None
        if current is not None:
            clicks = []
            for event in _read_events(session):
                if event.get("screen") != current.get("screen") or not isinstance(event.get("timestamp"), (int, float)):
                    continue
                if event["timestamp"] < current["shown_at"]:
                    continue
                if event.get("type") == "proceed":
                    _emit({"proceed": event, "clicks": clicks})
                    return EXIT_OK
                if event.get("type") == "click":
                    clicks.append(event)
        if time.monotonic() >= deadline:
            screen = current.get("screen") if current else None
            _emit({"status": "timeout", "screen": screen})
            print("timed out waiting for Proceed; re-run wait, no click is lost", file=sys.stderr)
            return EXIT_NOT_OK
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))


def _cmd_events(args: argparse.Namespace) -> int:
    if _is_app_session(Path(args.session)):
        return _fail("session is in app mode")
    events = _read_events(Path(args.session))
    if args.screen:
        events = [e for e in events if e.get("screen") == args.screen]
    _emit({"events": events})
    return EXIT_OK


def _app_session(args: argparse.Namespace) -> Optional[AppState]:
    """The session's AppState, or None after reporting that the session is not in app mode."""
    session = Path(args.session)
    if not _is_app_session(session):
        _fail("session is not in app mode")
        return None
    return AppState(session)


def _field_error(exc: Exception, field: str) -> int:
    print(str(exc), file=sys.stderr)
    _emit({"error": str(exc), "field": field})
    return EXIT_USAGE


def _read_input(path: str) -> object:
    """The JSON in ``path``; raises ScreenError when it cannot be read or parsed."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ScreenError(f"cannot read {path}: {exc}") from exc
    except (ValueError, RecursionError) as exc:
        raise ScreenError(f"{path} is not valid JSON: {exc}") from exc


def _cmd_step(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    try:
        step = validate_step(_read_input(args.step))
    except ScreenError as exc:
        return _fail(str(exc))
    except StepError as exc:
        return _field_error(exc, exc.field)
    if step["kind"] == "mock-review" and step["version"] not in app.mocks_index()["versions"]:
        return _field_error(ValueError(f"mock version {step['version']} is not registered"), "version")
    written = app.write_step(step)
    info = live_server_info(Path(args.session))
    _emit({**written, "url": info.get("url") if info else None})
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    if args.clear:
        app.clear_status()
        _emit({"status": None})
        return EXIT_OK
    if args.text is None:
        return _fail("--text is required unless --clear is given")
    try:
        status = app.set_status(args.text, args.stage, args.progress, args.interruptible)
    except AppStateError as exc:
        return _field_error(exc, exc.field)
    _emit({"status": status})
    return EXIT_OK


def _cmd_decide(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    try:
        decisions = _read_input(args.decisions)
        if not isinstance(decisions, list):
            raise ScreenError("the decisions file must contain a JSON list")
        app.set_decisions(decisions)
    except ScreenError as exc:
        return _fail(str(exc))
    except AppStateError as exc:
        return _field_error(exc, exc.field)
    _emit({"decisions": len(decisions)})
    return EXIT_OK


def _cmd_review(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    path = Path(args.review_html)
    try:
        with open(path, "rb") as fh:
            fh.read(1)
    except OSError as exc:
        return _fail(f"cannot read {path}: {exc}")
    app.set_review(path)
    _emit({"review_url": "/_quirk/review"})
    return EXIT_OK


def _cmd_mock(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    try:
        with open(args.mock_html, "rb") as fh:
            raw = fh.read(mocks.MAX_MOCK_BYTES + 1)
    except OSError as exc:
        return _fail(f"cannot read {args.mock_html}: {exc}")
    if len(raw) > mocks.MAX_MOCK_BYTES:
        return _fail(f"{args.mock_html} is over {mocks.MAX_MOCK_BYTES // (1024 * 1024)} MiB")
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(f"{args.mock_html} is not UTF-8")
    try:
        screens = mocks.validate_screens(_read_input(args.screens))
        changed = mocks.validate_changed(_read_input(args.changed)) if args.changed else []
        app.register_mock(args.version, html, screens, changed)
    except ScreenError as exc:
        return _fail(str(exc))
    except (mocks.MockError, AppStateError) as exc:
        return _field_error(exc, exc.field)
    _emit({"version": args.version, "mock_url": f"/_quirk/mock/{args.version}"})
    return EXIT_OK


def _cmd_mock_export(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    mock = app.get_mock(args.version)
    if mock is None:
        return _field_error(ValueError(f"mock version {args.version} is not registered"), "version")
    boot = mocks.make_boot(
        mode="offline", version=args.version, latest=args.version, versions=[args.version],
        screens=mock["screens"], changed=mock["changed"], mock_html=mock["html"], revision=mock["revision"],
    )
    try:
        page = mocks.fill_template(*mocks.load_template(), boot)
    except mocks.MockError as exc:
        return _fail(str(exc))
    review = mocks.build_review(args.version, app.snapshot()["threads"], mocks.now_iso())
    out = Path(os.path.abspath(args.out))
    contents = {
        "mock.html": page,
        "screens.md": mocks.screens_markdown(mock["screens"], args.version),
        "review.json": json.dumps(review, ensure_ascii=False, indent=2) + "\n",
    }
    try:
        out.mkdir(parents=True, exist_ok=True)
        for name, text in contents.items():
            atomic_write(out / name, text)
    except OSError as exc:
        return _fail(f"cannot write {out}: {exc}")
    _emit({"files": [str(out / name) for name in contents]})
    return EXIT_OK


def _cmd_say(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    if (args.text is None) == (args.file is None):
        return _fail("give exactly one of --text and --file")
    text = args.text
    if args.file is not None:
        try:
            text = Path(args.file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return _fail(f"cannot read {args.file}: {exc}")
    try:
        if not text.strip():
            raise AppStateError("text", "text must not be empty")
        seq = app.append_chat(args.sender, text)
    except AppStateError as exc:
        return _field_error(exc, exc.field)
    _emit({"chat": seq})
    return EXIT_OK


def _cmd_reply(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    try:
        if not args.text.strip():
            raise AppStateError("text", "text must not be empty")
        app.reply(args.thread_id, args.text, args.resolve)
    except AppStateError as exc:
        return _field_error(exc, exc.field)
    _emit({"thread": args.thread_id})
    return EXIT_OK


def _cmd_next(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    session = Path(args.session)
    deadline = time.monotonic() + args.timeout
    while True:
        if live_server_info(session) is None:
            _emit({"status": "no-server"})
            print("no live companion server for this session; run start --app", file=sys.stderr)
            return EXIT_USAGE
        events = app.events_after(args.after)
        if events:
            app.mark_delivered([e["seq"] for e in events])
            _emit({"events": events, "cursor": max(e["seq"] for e in events)})
            return EXIT_OK
        if time.monotonic() >= deadline:
            _emit({"status": "timeout", "cursor": args.after})
            print("timed out waiting for an event; re-run next with the same --after, nothing is lost", file=sys.stderr)
            return EXIT_NOT_OK
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))


def _cmd_snapshot(args: argparse.Namespace) -> int:
    app = _app_session(args)
    if app is None:
        return EXIT_USAGE
    _emit(app.snapshot())
    return EXIT_OK


def _cmd_stop(args: argparse.Namespace) -> int:
    session = Path(args.session)
    info = live_server_info(session)
    if info is None:
        _emit({"stopped": False})
        return EXIT_OK
    try:
        os.kill(info["pid"], signal.SIGTERM)
    except OSError as exc:
        print(f"could not signal pid {info['pid']}: {exc}", file=sys.stderr)
        _emit({"stopped": False})
        return EXIT_OK
    deadline = time.monotonic() + STOP_TIMEOUT
    while time.monotonic() < deadline and _pid_alive(info["pid"]):
        time.sleep(0.05)
    _emit({"stopped": not _pid_alive(info["pid"])})
    return EXIT_OK


def _port(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid port: {value!r}") from None
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError("must be between 0 and 65535")
    return number


def _positive(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="companion.py", description="Live companion for brainstorming screens.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    start = sub.add_parser("start", help="start the session's server, or reuse a live one")
    start.add_argument("session")
    start.add_argument("--host", default=None)
    start.add_argument("--allow-host", type=_allow_host, action="append", default=[], metavar="HOST[:PORT]")
    start.add_argument("--port", type=_port, default=0)
    start.add_argument("--idle-minutes", type=_positive, default=30.0)
    start.add_argument("--foreground", action="store_true")
    start.add_argument("--app", action="store_true", help="serve the app-mode shell and API")
    start.add_argument("--prefer-port", type=_port, default=None, help=argparse.SUPPRESS)
    start.set_defaults(func=_cmd_start)

    show = sub.add_parser("show", help="build a screen and make it current")
    show.add_argument("session")
    show.add_argument("screen")
    show.add_argument("--project-dir")
    show.set_defaults(func=_cmd_show)

    wait = sub.add_parser("wait", help="block until Proceed is clicked on the current screen")
    wait.add_argument("session")
    wait.add_argument("--timeout", type=float, default=110.0)
    wait.set_defaults(func=_cmd_wait)

    events = sub.add_parser("events", help="print the recorded events")
    events.add_argument("session")
    events.add_argument("--screen")
    events.set_defaults(func=_cmd_events)

    step = sub.add_parser("step", help="app mode: make a step current")
    step.add_argument("session")
    step.add_argument("step", metavar="STEP.json")
    step.set_defaults(func=_cmd_step)

    status = sub.add_parser("status", help="app mode: set or clear the status line")
    status.add_argument("session")
    status.add_argument("--text")
    status.add_argument("--stage")
    status.add_argument("--progress", metavar="N/M")
    mark = status.add_mutually_exclusive_group()
    mark.add_argument("--interruptible", action="store_true")
    mark.add_argument("--clear", action="store_true")
    status.set_defaults(func=_cmd_status)

    decide = sub.add_parser("decide", help="app mode: replace the decisions list")
    decide.add_argument("session")
    decide.add_argument("decisions", metavar="DECISIONS.json")
    decide.set_defaults(func=_cmd_decide)

    review = sub.add_parser("review", help="app mode: register the interactive review page")
    review.add_argument("session")
    review.add_argument("review_html", metavar="REVIEW_HTML")
    review.set_defaults(func=_cmd_review)

    mock = sub.add_parser("mock", help="app mode: register a mock version for the UX review")
    mock.add_argument("session")
    mock.add_argument("mock_html", metavar="MOCK_HTML")
    mock.add_argument("--version", type=int, required=True, metavar="N")
    mock.add_argument("--screens", required=True, metavar="SCREENS_JSON")
    mock.add_argument("--changed", metavar="CHANGED_JSON")
    mock.set_defaults(func=_cmd_mock)

    mock_export = sub.add_parser("mock-export", help="app mode: write a mock version as an offline folder")
    mock_export.add_argument("session")
    mock_export.add_argument("--version", type=int, required=True, metavar="N")
    mock_export.add_argument("--out", required=True, metavar="DIR")
    mock_export.set_defaults(func=_cmd_mock_export)

    say = sub.add_parser("say", help="app mode: add a chat message")
    say.add_argument("session")
    say.add_argument("--text")
    say.add_argument("--file")
    say.add_argument("--from", dest="sender", choices=("agent", "user"), default="agent")
    say.set_defaults(func=_cmd_say)

    reply = sub.add_parser("reply", help="app mode: reply inside a comment thread")
    reply.add_argument("session")
    reply.add_argument("thread_id", metavar="THREAD_ID")
    reply.add_argument("--text", required=True)
    reply.add_argument("--resolve", choices=("addressed", "not-addressed"))
    reply.set_defaults(func=_cmd_reply)

    nxt = sub.add_parser("next", help="app mode: block until user events arrive")
    nxt.add_argument("session")
    nxt.add_argument("--after", type=int, default=0, metavar="SEQ")
    nxt.add_argument("--timeout", type=float, default=110.0)
    nxt.set_defaults(func=_cmd_next)

    snapshot = sub.add_parser("snapshot", help="app mode: print the snapshot the tab receives")
    snapshot.add_argument("session")
    snapshot.set_defaults(func=_cmd_snapshot)

    stop = sub.add_parser("stop", help="stop the session's server")
    stop.add_argument("session")
    stop.set_defaults(func=_cmd_stop)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Run one subcommand; a filesystem or encoding failure is reported as ``{"error": ...}``, exit 2."""
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, UnicodeError, OverflowError, ValueError) as exc:
        return _fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
