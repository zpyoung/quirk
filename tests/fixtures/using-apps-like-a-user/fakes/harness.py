"""Test harness for driving likeuser.py against fake playwright-cli, orca, and desktop.

A `Sandbox` owns one temp directory holding the state root, lock file, fake desktop JSON, fake
binaries, and scenario files, and runs `likeuser.py` as a subprocess under the `LIKEUSER_*`
overrides that point at them. Nothing here touches the real desktop, clipboard, or lock.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
REPO = FIXTURES.parents[2]
GOLDEN = FIXTURES / "golden"
PNG_DIR = FIXTURES / "png"
SCRIPT = REPO / "skills" / "using-apps-like-a-user" / "scripts" / "likeuser.py"

FIXTURE_BUNDLE = "dev.quirk.uala.fixture"
USER_APP = "com.example.userapp"

NATIVE_TREE = (
    "App=dev.quirk.uala.fixture (pid 30794)\n"
    "Window: \"UALA Fixture\", App: UALA Fixture.\n\n"
    "0 standard window UALA Fixture\n"
    "\t1 text Status: idle\n"
    "\t2 button Working button\n"
    "\t3 button Dead button\n"
    "\t4 button Delete project\n"
    "\t5 text field (settable) Notes\n"
    "\t6 button Save…\n"
    "\t7 close button\n\n"
    "The focused UI element is 0 standard window UALA Fixture."
)
NATIVE_WORKING_TREE = NATIVE_TREE.replace("Status: idle", "Status: working clicked 1 time(s)")
NATIVE_SHEET_TREE = NATIVE_TREE.replace(
    "\t7 close button", "\t7 sheet Save\n\t\t8 button Cancel\n\t\t9 button Save\n\t10 close button")


def golden_yaml(name: str = "snapshot") -> str:
    """Return the yaml block of a golden playwright snapshot."""
    stdout = json.loads((GOLDEN / "playwright" / f"{name}.json").read_text())["stdout"]
    return re.search(r"```yaml\n(.*?)\n```", stdout, re.DOTALL).group(1)


def web_page(yaml: Optional[str] = None, url: str = "http://127.0.0.1:64361/",
             title: str = "Like-a-User Fixture", **extra) -> dict:
    """A scenario page; the yaml defaults to the golden fixture snapshot."""
    page = {"url": url, "title": title, "yaml": yaml or golden_yaml()}
    page.update(extra)
    return page


def home_pages() -> Dict[str, dict]:
    """The golden fixture page before and after a click on the working counter button."""
    return {
        "home": web_page(golden_yaml("snapshot")),
        "counted": web_page(golden_yaml("snapshot_after_click")),
    }


def wrapper(path: Path, python_script: Path, env: Optional[Dict[str, str]] = None) -> Path:
    """Write an executable shell wrapper that runs a fake Python script."""
    exports = "".join(f"export {k}='{v}'\n" for k, v in (env or {}).items())
    path.write_text(f"#!/bin/sh\n{exports}exec '{sys.executable}' '{python_script}' \"$@\"\n")
    path.chmod(0o755)
    return path


class Result:
    """The outcome of one likeuser.py invocation."""

    def __init__(self, proc: subprocess.CompletedProcess) -> None:
        self.code = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        assert len(lines) == 1, f"stdout must be exactly one JSON line: {proc.stdout!r}\n{proc.stderr}"
        self.out = json.loads(lines[0])

    def __getitem__(self, key):
        return self.out[key]

    def get(self, key, default=None):
        return self.out.get(key, default)

    @property
    def status(self) -> str:
        return self.out["status"]


class Sandbox:
    """One isolated environment for likeuser.py runs."""

    def __init__(self, tmp_path: Path, extra_env: Optional[Dict[str, str]] = None) -> None:
        self.tmp = Path(tmp_path)
        self.state_root = self.tmp / "state"
        self.lock_path = self.tmp / "lock" / "desktop.lock"
        self.desktop_path = self.tmp / "desktop.json"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.cwd = self.tmp / "cwd"
        self.cwd.mkdir()
        self.command_log = self.tmp / "commands.jsonl"
        self.pw_scenario = self.tmp / "pw.json"
        self.orca_scenario = self.tmp / "orca.json"
        self.extra_env = dict(extra_env or {})
        self.set_desktop()
        wrapper(self.bin / "playwright-cli", HERE / "fake_playwright.py",
                {"FAKE_PW_SCENARIO": str(self.pw_scenario)})
        wrapper(self.bin / "orca", HERE / "fake_orca.py",
                {"FAKE_ORCA_SCENARIO": str(self.orca_scenario)})
        for name in ("open", "osascript"):
            wrapper(self.bin / name, HERE / "fake_command.py",
                    {"FAKE_COMMAND_LOG": str(self.command_log), "FAKE_COMMAND_NAME": name})

    def set_desktop(self, **changes) -> dict:
        state = {
            "cursor": [100.0, 200.0], "frontmost": USER_APP, "clipboard_change_count": 3,
            "clipboard_text_only": True, "clipboard_text": "users clipboard", "scale": 2.0,
            "permissions": {"accessibility": True, "screen_recording": True},
        }
        if self.desktop_path.exists():
            state = json.loads(self.desktop_path.read_text())
        state.update(changes)
        self.desktop_path.write_text(json.dumps(state))
        return state

    def desktop(self) -> dict:
        return json.loads(self.desktop_path.read_text())

    def web_scenario(self, pages: Optional[Dict[str, dict]] = None, start: str = "home",
                     **extra) -> None:
        scenario = {"golden_dir": str(GOLDEN / "playwright"), "pages": pages or home_pages(),
                    "start": start}
        scenario.update(extra)
        self.pw_scenario.write_text(json.dumps(scenario))

    def native_scenario(self, pages: Optional[Dict[str, dict]] = None, start: str = "idle",
                        **extra) -> None:
        scenario = {
            "golden_dir": str(GOLDEN / "orca"), "bundle": FIXTURE_BUNDLE, "window_id": 83666,
            "scale": 2, "running": True, "screenshot_dir": str(self.tmp / "orca-shots"),
            "open_log": str(self.command_log), "start": start,
            "pages": pages or {
                "idle": {"tree": NATIVE_TREE, "title": "UALA Fixture"},
                "working": {"tree": NATIVE_WORKING_TREE, "title": "UALA Fixture"},
            },
        }
        scenario.update(extra)
        self.orca_scenario.write_text(json.dumps(scenario))

    def env(self, **overrides) -> Dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LIKEUSER_", "FAKE_"))}
        env.update({
            "PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}",
            "LIKEUSER_STATE_ROOT": str(self.state_root),
            "LIKEUSER_LOCK_PATH": str(self.lock_path),
            "LIKEUSER_FAKE_DESKTOP": str(self.desktop_path),
            "LIKEUSER_PLAYWRIGHT_BIN": str(self.bin / "playwright-cli"),
            "LIKEUSER_ORCA_BIN": str(self.bin / "orca"),
            "LIKEUSER_NATIVE_BIN": str(self.tmp / "no-native-driver"),
        })
        env.update(self.extra_env)
        env.update(overrides)
        return {k: v for k, v in env.items() if v is not None}

    def run(self, *args: str, stdin: Optional[str] = None, **env_overrides) -> Result:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args], input=stdin or "", capture_output=True,
            text=True, cwd=str(self.cwd), env=self.env(**env_overrides), timeout=120)
        return Result(proc)

    def raw(self, *args: str, stdin: Optional[str] = None, **env_overrides):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], input=stdin or "", capture_output=True,
            text=True, cwd=str(self.cwd), env=self.env(**env_overrides), timeout=120)

    def begin(self, surface: str = "web", target: Optional[str] = None, owner: str = "yours",
              attended: bool = True, *extra: str, **env_overrides) -> Result:
        target = target or {"web": "http://127.0.0.1:64361/", "native": FIXTURE_BUNDLE,
                            "electron": "fixture-electron"}[surface]
        args = ["begin", "--target", target, "--surface", surface, "--owner", owner,
                "--attended" if attended else "--unattended"]
        if surface == "native" and "--allow-foreground" not in extra:
            args.append("--allow-foreground")
        return self.run(*args, *extra, **env_overrides)

    def run_dir(self, run_id: str) -> Path:
        return self.state_root / "runs" / run_id

    def run_json(self, run_id: str) -> dict:
        return json.loads((self.run_dir(run_id) / "run.json").read_text())

    def write_run_json(self, run_id: str, data: dict) -> None:
        (self.run_dir(run_id) / "run.json").write_text(json.dumps(data))

    def events(self, run_id: str) -> List[dict]:
        path = self.run_dir(run_id) / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def run_files_text(self, run_id: str) -> str:
        parts = []
        for name in ("events.jsonl", "run.json", "report.json", "report.md"):
            path = self.run_dir(run_id) / name
            if path.exists():
                parts.append(path.read_text())
        return "\n".join(parts)

    def pw_calls(self) -> List[dict]:
        return self._calls(self.pw_scenario)

    def orca_calls(self) -> List[dict]:
        return self._calls(self.orca_scenario)

    @staticmethod
    def _calls(scenario: Path) -> List[dict]:
        path = Path(str(scenario) + ".calls.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def pw_argvs(self, command: Optional[str] = None) -> List[List[str]]:
        argvs = [c["argv"] for c in self.pw_calls()]
        return [a for a in argvs if command is None or (a and a[0] == command)]

    def orca_commands(self, sub: str) -> List[dict]:
        return [c for c in self.orca_calls() if len(c["argv"]) > 1 and c["argv"][1] == sub]

    def command_calls(self, tool: str) -> List[dict]:
        if not self.command_log.exists():
            return []
        rows = [json.loads(line) for line in self.command_log.read_text().splitlines()]
        return [r for r in rows if r["tool"] == tool]

    def kill_launched(self) -> None:
        for path in self.state_root.glob("runs/*/run.json"):
            try:
                launched = json.loads(path.read_text()).get("launched", [])
            except (OSError, ValueError):
                continue
            for entry in launched:
                kind, _, ident = entry["id"].partition(":")
                if kind == "pid":
                    try:
                        os.killpg(int(ident), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
