#!/usr/bin/env python3
"""Live companion for the writing-html-artifacts skill: a local page that asks one question at a time.

``start`` runs a small HTTP server for a session directory, ``show`` builds a screen from a
``screen.json`` and makes it the current one, ``wait`` blocks until the user clicks Proceed on
the current screen, ``events`` reads what the user did and ``stop`` ends the server. Every
subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.

Exit codes: 0 success; 1 for ``show`` when a static check fails and for the ``wait`` timeout;
2 for usage errors, a malformed screen, a missing session, no live server (``wait``) or a
server that never came up (``start``). Anything that is not a failed check or a timeout is
reported as ``{"error": ...}``, except ``wait``'s ``{"status": "no-server"}``.

The server binds 127.0.0.1 by default and trusts nothing from the page except a per-screen
nonce. It never touches the network beyond its own socket.
"""
from __future__ import annotations

import argparse
import html as html_lib
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NoReturn, Optional
from urllib.parse import unquote, urlsplit

# the skill directory holds htmlkit and is not on sys.path when this file is run by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from htmlkit import SKILL_DIR, assemble, resolve  # noqa: E402
from htmlkit.fsutil import atomic_write, ensure_self_ignoring  # noqa: E402
from htmlkit.header import read_header, render_header  # noqa: E402
from htmlkit.vendor import VendorError, VendorStore, shell_block  # noqa: E402

EXIT_OK, EXIT_NOT_OK, EXIT_USAGE = 0, 1, 2

MAX_BODY = 64 * 1024
DRAIN_LIMIT = 1024 * 1024
START_TIMEOUT = 10.0
STOP_TIMEOUT = 5.0
POLL_SECONDS = 0.2
WILDCARD_HOSTS = ("0.0.0.0", "::", "")
OPTION_ID = re.compile(r"[a-z0-9-]{1,40}")
SLOT_LINE = re.compile(r"^<!-- slot:", re.M)
SCREEN_KEYS = {"title", "question", "select", "options", "content", "diagram"}
EVENT_TYPES = ("click", "proceed")

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


def _prepare_session(session: Path) -> None:
    """Create the session's directories; a ``.quirk/brainstorm`` parent becomes self-ignoring."""
    parent = session.parent
    if parent.name == "brainstorm" and parent.parent.name == ".quirk":
        ensure_self_ignoring(parent)
    (session / "screens").mkdir(parents=True, exist_ok=True)
    _state_dir(session).mkdir(parents=True, exist_ok=True)


def live_server_info(session: Path) -> Optional[dict]:
    """The session's ``server-info`` when its server is alive, else None.

    Dead means: no parseable ``server-info`` with an integer pid, a ``server-stopped`` file, or
    a pid that no longer exists.
    """
    state = _state_dir(session)
    if (state / "server-stopped").exists():
        return None
    info = _read_json(state / "server-info")
    pid = info.get("pid") if isinstance(info, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    except OSError:
        return None
    return info


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


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host: str, port: int, session: Path) -> None:
        self.address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
        self.session = session
        self.bound_host = host
        self.event_lock = threading.Lock()
        self.last_request = time.monotonic()
        super().__init__((host, port), _Handler)
        self.bound_port = self.server_address[1]

    def expected_host(self) -> str:
        host = f"[{self.bound_host}]" if ":" in self.bound_host else self.bound_host
        return f"{host}:{self.bound_port}"

    def host_allowed(self, header: Optional[str]) -> bool:
        if header is None:
            return False
        if self.bound_host in WILDCARD_HOSTS:
            return header.endswith(f":{self.bound_port}")
        return header == self.expected_host()

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
        own_origin = f"http://{host}" if host else None
        if not self.server.host_allowed(host) or (origin is not None and origin != own_origin):
            self._reply(403, b"forbidden\n")
            return False
        return True

    def do_GET(self) -> None:
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._serve_screen()
        elif path == "/_quirk/state":
            current = self.server.current() or {}
            self._json(200, {"screen": current.get("screen"), "nonce": current.get("nonce")})
        elif path.startswith("/_quirk/lib/"):
            self._serve_library(path[len("/_quirk/lib/") :])
        else:
            self._reply(404, b"not found\n")

    def do_POST(self) -> None:
        if not self._guard():
            return
        if urlsplit(self.path).path != "/_quirk/event":
            self._reply(404, b"not found\n")
            return
        self._accept_event()

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

    def _drain(self, length: int) -> None:
        remaining = min(length, DRAIN_LIMIT)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

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


def _serve(session: Path, host: str, port: int, idle_minutes: float) -> int:
    """Run the server in this process until it is stopped, idle or signalled."""
    existing = live_server_info(session)
    if existing is not None:
        _emit(existing)
        return EXIT_OK
    _prepare_session(session)
    state = _state_dir(session)
    for stale in ("server-stopped", "server-info"):
        (state / stale).unlink(missing_ok=True)
    try:
        httpd = _Server(host, port, session)
    except OSError as exc:
        return _fail(f"cannot listen on {host}:{port}: {exc}")
    shown_host = "127.0.0.1" if host in WILDCARD_HOSTS else (f"[{host}]" if ":" in host else host)
    info = {
        "type": "server-started",
        "pid": os.getpid(),
        "port": httpd.bound_port,
        "host": host,
        "url": f"http://{shown_host}:{httpd.bound_port}/",
        "screen_dir": str(session / "screens"),
        "state_dir": str(state),
    }
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
        return _serve(session, args.host, args.port, args.idle_minutes)
    existing = live_server_info(session)
    if existing is not None:
        _emit(existing)
        return EXIT_OK
    _prepare_session(session)
    state = _state_dir(session)
    for stale in ("server-stopped", "server-info"):
        (state / stale).unlink(missing_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "start",
        str(session),
        "--foreground",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--idle-minutes",
        str(args.idle_minutes),
    ]
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


def _text(spec: dict, key: str, required: bool) -> Optional[str]:
    value = spec.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ScreenError(f"{key!r} must be a non-empty string")
    return value


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
        if option.get("description"):
            parts.append(f'<span class="q-option-desc">{attr(option["description"])}</span>')
        if option.get("html"):
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
    content = spec.get("content") or ""
    if spec.get("diagram"):
        figure = f'<figure class="q-diagram"><pre class="mermaid">{html_lib.escape(spec["diagram"])}</pre></figure>'
        content = f"{content}\n{figure}" if content else figure
    header = json.dumps({"template": "companion", "title": spec["title"], "mode": "offline"})
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
    if spec.get("diagram"):
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
    events = _read_events(Path(args.session))
    if args.screen:
        events = [e for e in events if e.get("screen") == args.screen]
    _emit({"events": events})
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
    while time.monotonic() < deadline and live_server_info(session) is not None:
        time.sleep(0.05)
    _emit({"stopped": live_server_info(session) is None})
    return EXIT_OK


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
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=0)
    start.add_argument("--idle-minutes", type=_positive, default=30.0)
    start.add_argument("--foreground", action="store_true")
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

    stop = sub.add_parser("stop", help="stop the session's server")
    stop.add_argument("session")
    stop.set_defaults(func=_cmd_stop)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
