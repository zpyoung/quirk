"""Open a worktree in the Orca IDE through its CLI, using only the fixed terminal list, switch and create argv."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

TIMEOUT = 10.0
DETAIL_LIMIT = 200


def orca_command() -> str | None:
    """The resolved Orca executable, or None when it is not on PATH.

    ``ORCA_CLI_COMMAND`` wins; otherwise ``orca-ide`` on Linux, where a bare ``orca`` is a screen reader.
    """
    name = os.environ.get("ORCA_CLI_COMMAND") or ("orca-ide" if sys.platform.startswith("linux") else "orca")
    return shutil.which(name)


class OrcaError(Exception):
    """An Orca call that failed; ``detail`` is one short line fit to show a user."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail[:DETAIL_LIMIT]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _call(exe: str, *args: str) -> dict:
    """Run one Orca CLI call with --json; raises OrcaError on a non-zero exit, bad output or ``ok: false``."""
    try:
        proc = subprocess.run(
            [exe, *args, "--json"], stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT, shell=False
        )
    except subprocess.TimeoutExpired as exc:
        raise OrcaError(f"orca timed out after {int(TIMEOUT)}s") from exc
    except OSError as exc:
        raise OrcaError(f"orca could not run: {exc}") from exc
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    try:
        body = json.loads(out)
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("ok") is False:
        error = body.get("error")
        message = error.get("message") or error.get("code") if isinstance(error, dict) else error
        raise OrcaError(_first_line(str(message or "")) or "orca reported an error")
    if proc.returncode != 0:
        raise OrcaError(_first_line(err) or _first_line(out) or f"orca exited {proc.returncode}")
    if not isinstance(body, dict):
        raise OrcaError("orca printed no JSON")
    return body


def open_worktree(exe: str, worktree: str, title: str) -> str:
    """Focus an existing Orca terminal in ``worktree`` or create one titled ``title``.

    Returns ``"switched"`` or ``"created"``. ``worktree`` must already be vetted as a listed worktree.
    Raises OrcaError when Orca fails.
    """
    selector = f"path:{worktree}"
    listing = _call(exe, "terminal", "list", "--worktree", selector)
    result = listing.get("result")
    terminals = result.get("terminals") if isinstance(result, dict) else None
    handle = terminals[0].get("handle") if terminals and isinstance(terminals[0], dict) else None
    if isinstance(handle, str) and handle:
        _call(exe, "terminal", "switch", "--terminal", handle)
        return "switched"
    _call(exe, "terminal", "create", "--worktree", selector, "--title", title, "--focus")
    return "created"
