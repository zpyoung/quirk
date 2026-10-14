"""Runs the Node/Playwright browser verification (`scripts/verify/verify.mjs`) on an HTML file.

Guarantees a `VerifyResult` dict for every call: when Node, the dependency install or the browser
is unavailable, or the file does not exist (`missing-file`), the result has
`status: "not-browser-verified"` and a `reason`, never an exception. When the verifier itself
crashes or times out on an existing file the result has `status: "failed"` with reason
`verify-crashed` or `verify-timeout`, so a page that hangs or breaks the verifier is not mistaken
for a missing browser.
The report is also written to `<out_dir>/report.json` so `report_is_stale` can later tell whether
verification ran on the file as it is now. Never downloads a browser and never opens the network
beyond the one-time `pnpm install` of `playwright-core`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent.parent / "verify"
INSTALL_TIMEOUT_S = 300
VERIFY_TIMEOUT_S = 180


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_out_dir(file: Path) -> Path:
    """`<file stem>.verify/` beside the file."""
    return file.parent / f"{file.stem}.verify"


def _no_report(
    file: Path, out_dir: Path, reason: str, detail: str = "", status: str = "not-browser-verified", no_js: bool = False
) -> dict:
    try:
        file_sha256 = _sha256(file)
    except OSError:
        file_sha256 = None
    result: dict = {
        "status": status,
        "file_sha256": file_sha256,
        "browser": None,
        "checks": {},
        "screenshots": [],
        "requests": [],
        "reason": reason,
        "no_js": no_js,
    }
    if detail:
        result["detail"] = detail
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    except OSError:
        # the report is a convenience for report_is_stale; the result is still returned without it
        pass
    return result


def _install_command() -> list[str] | None:
    if shutil.which("pnpm"):
        return ["pnpm", "install", "--frozen-lockfile"]
    if shutil.which("corepack"):
        return ["corepack", "pnpm", "install", "--frozen-lockfile"]
    return None


def _ensure_installed() -> str | None:
    """Installs the Node dependency when absent; returns an error detail on failure, else None."""
    if (VERIFY_DIR / "node_modules").is_dir():
        return None
    command = _install_command()
    if command is None:
        return "neither pnpm nor corepack is available"
    env = {**os.environ, "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"}
    try:
        proc = subprocess.run(
            command,
            cwd=VERIFY_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout).strip()[-500:]
    return None


def run_verify(file: Path, out_dir: Path | None = None, mode: str = "offline", no_js: bool = False) -> dict:
    """Verifies `file` in a real browser and returns the `VerifyResult`.

    `mode` is "offline" (any non-local request fails the network check) or "connected" (requests
    are listed but do not fail it). `no_js` loads the page with JavaScript disabled and adds the
    `fallback` check; the result's `no_js` key records which mode ran.
    """
    if mode not in ("offline", "connected"):
        raise ValueError(f"mode must be 'offline' or 'connected', got {mode!r}")
    file = Path(file).resolve()
    out_dir = Path(out_dir) if out_dir is not None else default_out_dir(file)

    if not file.is_file():
        return _no_report(file, out_dir, "missing-file", no_js=no_js)
    node = shutil.which("node")
    if node is None:
        return _no_report(file, out_dir, "no-node", no_js=no_js)
    error = _ensure_installed()
    if error is not None:
        return _no_report(file, out_dir, "install-failed", error, no_js=no_js)

    report = out_dir / "report.json"
    report.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [node, str(VERIFY_DIR / "verify.mjs"), str(file), str(out_dir), mode, *(["--no-js"] if no_js else [])],
            capture_output=True,
            text=True,
            timeout=VERIFY_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return _no_report(file, out_dir, "verify-timeout", status="failed", no_js=no_js)

    try:
        result = json.loads(report.read_text())
    except (OSError, ValueError):
        return _no_report(file, out_dir, "verify-crashed", proc.stderr.strip()[-500:], status="failed", no_js=no_js)
    result["no_js"] = no_js
    if result.get("status") == "not-browser-verified":
        result["reason"] = "no-browser"
        report.write_text(json.dumps(result, indent=2) + "\n")
    return result


def report_is_stale(file: Path, report: Path) -> bool:
    """True when `report` is missing, unreadable, or was produced for different file contents."""
    try:
        recorded = json.loads(Path(report).read_text()).get("file_sha256")
        return recorded != _sha256(Path(file))
    except (OSError, ValueError, AttributeError):
        return True
