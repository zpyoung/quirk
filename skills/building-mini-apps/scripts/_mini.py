"""Shared helpers for new_app.py and add_patterns.py: pattern discovery, step runner, dev check.

Kept in one module so the two scripts install, build and verify an app identically.
"""
from __future__ import annotations

import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = SKILL_ROOT / "gallery" / "src" / "patterns"
REGISTRY_R = SKILL_ROOT / "registry" / "r"
SHADCN = "shadcn@4.22.1"
DEV_TIMEOUT = 30
TAIL_LINES = 20
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def known_patterns() -> list[str]:
    """Pattern slugs that have both a gallery folder and a built registry item."""
    if not PATTERNS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in PATTERNS_DIR.iterdir()
        if p.is_dir() and (REGISTRY_R / f"{p.name}.json").is_file()
    )


def parse_patterns(raw: str | None) -> list[str]:
    """Split a comma list into ordered, de-duplicated slugs; None or empty gives no patterns."""
    slugs: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part and part not in slugs:
            slugs.append(part)
    return slugs


def unknown_patterns(slugs: list[str]) -> list[str]:
    known = set(known_patterns())
    return [s for s in slugs if s not in known]


def usage_error(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def tail(text: str) -> str:
    return "\n".join(text.rstrip().splitlines()[-TAIL_LINES:])


def step_failed(name: str, output: str) -> int:
    print(f"step {name} failed", file=sys.stderr)
    if output.strip():
        print(tail(output), file=sys.stderr)
    return 1


def run_step(name: str, cmd: list[str], cwd: Path) -> int:
    """Run one command with stdin closed; on failure report the step name and output tail."""
    print(f"+ [{name}] {' '.join(cmd)}  (cwd {cwd})", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
        )
    except OSError as exc:
        return step_failed(name, str(exc))
    if proc.returncode != 0:
        return step_failed(name, proc.stdout)
    return 0


def add_step(app: Path, patterns: list[str]) -> int:
    """`shadcn add` of the base plus `patterns` from the local registry; existing files are kept."""
    items = [str(REGISTRY_R / "base.json")] + [str(REGISTRY_R / f"{p}.json") for p in patterns]
    return run_step("add", ["pnpm", "dlx", SHADCN, "add", *items, "-y"], app)


def build_step(app: Path) -> int:
    return run_step("build", ["pnpm", "build"], app)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def dev_step(app: Path) -> int:
    """Start `pnpm dev`, wait for its `Local:` line, then stop the whole process group."""
    cmd = ["pnpm", "dev", "--port", str(free_port()), "--strictPort"]
    print(f"+ [dev] {' '.join(cmd)}  (cwd {app})", flush=True)
    env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0"}
    try:
        proc = subprocess.Popen(
            cmd, cwd=app, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, start_new_session=True,
        )
    except OSError as exc:
        return step_failed("dev", str(exc))

    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(ANSI_RE.sub("", line))
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    seen: list[str] = []
    ready = False
    deadline = time.monotonic() + DEV_TIMEOUT
    try:
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                break
            seen.append(line)
            if "Local:" in line:
                ready = True
                break
    finally:
        stop_group(proc)
    if not ready:
        return step_failed("dev", "".join(seen) or f"no `Local:` line within {DEV_TIMEOUT}s")
    return 0


def stop_group(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue
