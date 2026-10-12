#!/usr/bin/env python3
"""Re-capture the playwright-cli golden cases against the web fixture.

Run `python3 capture.py` with playwright-cli on PATH. Each case lands next to this file as
`<case>.json` in the golden driver-output schema (argv, returncode, stdout, stderr, files).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "skills" / "using-apps-like-a-user" / "scripts"))

from _web import VIEWPORT_JS, VISIBILITY_JS  # noqa: E402

SESSION = "golden"
SERVER = ROOT / "tests" / "fixtures" / "using-apps-like-a-user" / "web" / "server.py"


def run(run_dir: Path, case: str, args: list, session: bool = True) -> str:
    before = {p for p in run_dir.rglob("*") if p.is_file()}
    argv = ["playwright-cli"] + ([f"-s={SESSION}"] if session else []) + args
    proc = subprocess.run(argv, cwd=str(run_dir), capture_output=True, text=True, timeout=120)
    files = {}
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file() and p not in before):
        rel = str(path.relative_to(run_dir))
        try:
            files[rel] = path.read_text()
        except UnicodeDecodeError:
            files[rel] = None
    record = {
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "files": files,
    }
    (HERE / f"{case}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{case}: rc={proc.returncode}")
    return proc.stdout


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, str(SERVER), "--port", "0"], stdout=subprocess.PIPE, text=True
    )
    run_dir = Path(tempfile.mkdtemp(prefix="likeuser-golden-"))
    try:
        port = int(server.stdout.readline().split()[1])
        url = f"http://127.0.0.1:{port}/"
        run(run_dir, "version", ["--version"], session=False)
        run(run_dir, "open", ["open", url])
        snapshot_stdout = run(run_dir, "snapshot", ["snapshot"])
        run(run_dir, "click", ["click", "e4"])
        run(run_dir, "snapshot_after_click", ["snapshot"])
        run(run_dir, "click_right", ["click", "e4", "right"])
        run(run_dir, "dblclick", ["dblclick", "e4"])
        run(run_dir, "click_stale_ref", ["click", "e999"])
        run(run_dir, "fill", ["fill", "e10", "hello"])
        run(run_dir, "type", ["type", " world"])
        run(run_dir, "snapshot_after_type", ["snapshot"])
        run(run_dir, "press", ["press", "Tab"])
        run(run_dir, "hotkey", ["press", "Meta+s"])
        run(run_dir, "hover", ["hover", "e4"])
        run(run_dir, "mousemove", ["mousemove", "10", "10"])
        run(run_dir, "mousedown", ["mousedown"])
        run(run_dir, "mouseup", ["mouseup"])
        run(run_dir, "mousewheel", ["mousewheel", "0", "720"])
        run(run_dir, "select_error", ["select", "e10", "x"])
        theme = re.search(r'combobox "Theme" \[ref=(e\d+)\]', snapshot_stdout).group(1)
        run(run_dir, "select", ["select", theme, "Dark"])
        run(run_dir, "click_save_avatar", ["click", "e12"])
        run(run_dir, "console", ["console", "error"])
        run(run_dir, "requests", ["requests", "--static"])
        run(run_dir, "eval_visibility_hidden", ["eval", VISIBILITY_JS, "e8"])
        run(run_dir, "eval_visibility_visible", ["eval", VISIBILITY_JS, "e4"])
        run(run_dir, "eval_viewport", ["eval", VIEWPORT_JS])
        run(run_dir, "screenshot", ["screenshot", "--filename=shot.png"])
        run(run_dir, "state_save", ["state-save", "state.json"])
        run(run_dir, "close", ["close"])
        run(run_dir, "snapshot_session_closed", ["snapshot"])
    finally:
        subprocess.run(["playwright-cli", f"-s={SESSION}", "close"], cwd=str(run_dir),
                       capture_output=True, text=True)
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(run_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
