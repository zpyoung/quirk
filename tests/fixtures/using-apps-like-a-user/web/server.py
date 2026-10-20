#!/usr/bin/env python3
"""Web fixture for using-apps-like-a-user: a page with planted UI bugs and a state endpoint.

Run as `python3 server.py --port N`; port 0 picks a free port and the first stdout line is
`PORT <n>`. `/hits` returns the fixture state: per-control hit counters, the text field's
content, and `saved_path` (always null for the web fixture).
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
USERNAME = "tester"
PASSWORD = "fixture-pass"
COUNTERS = ("working", "dead", "hidden", "verify", "delete", "save")
STATIC = {"/": "index.html", "/index.html": "index.html"}
BEACONS = ("working", "dead", "hidden", "delete")

_lock = threading.Lock()
_state = {"hits": {name: 0 for name in COUNTERS}, "text": "", "saved_path": None}


def snapshot() -> dict:
    """Return a copy of the fixture state in the shared fixture-state schema."""
    with _lock:
        return {
            "hits": dict(_state["hits"]),
            "text": _state["text"],
            "saved_path": _state["saved_path"],
        }


def _bump(name: str) -> None:
    with _lock:
        _state["hits"][name] += 1


class Handler(BaseHTTPRequestHandler):
    server_version = "LikeUserFixture/1"

    def log_message(self, fmt, *args):
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            body = (HERE / STATIC[path]).read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
        elif path == "/hits":
            self._json(200, snapshot())
        elif path == "/verify":
            _bump("verify")
            page = b"<!doctype html><title>Verified</title><h1>Verified</h1>"
            self._send(200, page, "text/html; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        body = self._read_body()
        if path.startswith("/api/hit/") and path[len("/api/hit/"):] in BEACONS:
            _bump(path[len("/api/hit/"):])
            self._send(204, b"", "text/plain")
        elif path == "/api/avatar":
            _bump("save")
            self._json(500, {"error": "avatar store unavailable"})
        elif path == "/api/text":
            try:
                text = json.loads(body or b"{}").get("text", "")
            except ValueError:
                text = ""
            with _lock:
                _state["text"] = str(text)
            self._send(204, b"", "text/plain")
        elif path == "/api/login":
            try:
                creds = json.loads(body or b"{}")
            except ValueError:
                creds = {}
            ok = creds.get("username") == USERNAME and creds.get("password") == PASSWORD
            self._json(200 if ok else 401, {"ok": ok})
        else:
            self._send(404, b"not found", "text/plain")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    sys.stdout.write("PORT %d\n" % httpd.server_address[1])
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
