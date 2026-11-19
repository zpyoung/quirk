"""The real built shell, as an app-mode companion server serves it: token and session injected, no external references.

No browser and no QUIRK_COMPANION_SHELL override, so this exercises the shell.html that ships.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
CLI = SKILL / "scripts" / "companion.py"
SHELL_FILE = SKILL / "companion-app" / "shell.html"

BOOT_PLACEHOLDER = '<script type="application/json" id="quirk-companion-boot">null</script>'
BOOT_SCRIPT = re.compile(r'<script type="application/json" id="quirk-companion-boot">(.*?)</script>', re.DOTALL)


@pytest.fixture
def served(tmp_path: Path):
    session = tmp_path / ".quirk" / "brainstorm" / "shell-served"
    env = {k: v for k, v in os.environ.items() if k != "QUIRK_COMPANION_SHELL"}
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(session), "--app", "--foreground", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        line = proc.stdout.readline()
        assert line, proc.stderr.read()
        info = json.loads(line)
        assert info["type"] == "server-started" and info["mode"] == "app"
        yield session, info
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        for stream in (proc.stdout, proc.stderr):
            if stream:
                stream.close()


def fetch_shell(port: int) -> tuple[int, str, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", "/")
        resp = conn.getresponse()
        return resp.status, resp.getheader("Content-Type") or "", resp.read().decode("utf-8")
    finally:
        conn.close()


def test_served_shell_carries_the_session_token_and_name(served) -> None:
    session, info = served
    status, content_type, html = fetch_shell(info["port"])
    assert status == 200 and content_type.startswith("text/html")
    blocks = BOOT_SCRIPT.findall(html)
    assert len(blocks) == 1, "exactly one boot block"
    assert html.count('id="quirk-companion-boot"') == 1
    boot = json.loads(blocks[0])
    assert boot["token"] == (session / "state" / "token").read_text().strip()
    assert boot["session"] == session.name


def test_served_shell_has_no_external_references(served) -> None:
    _, info = served
    _, _, html = fetch_shell(info["port"])
    assert 'src="http' not in html and 'href="http' not in html
    assert "src='http" not in html and "href='http" not in html


def test_server_injects_at_serve_time_and_never_rewrites_shell_html(served) -> None:
    before = SHELL_FILE.read_bytes()
    _, info = served
    _, _, html = fetch_shell(info["port"])
    assert BOOT_PLACEHOLDER not in html
    text = before.decode("utf-8")
    assert text.count(BOOT_PLACEHOLDER) == 1 and text.count('id="quirk-companion-boot"') == 1
    assert SHELL_FILE.read_bytes() == before
