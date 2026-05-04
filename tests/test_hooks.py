from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"


def run_hook(name: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_load_tail_suggests_init_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("load_artifact_tail.sh", project_dir)
    assert r.returncode == 0
    assert "/quirk:artifacts:init" in r.stdout


def test_load_tail_emits_tail_when_artifacts_exist(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")
    r = run_hook("load_artifact_tail.sh", initialized_project)
    assert r.returncode == 0
    assert "BUG-1: alpha" in r.stdout


def test_load_tail_silent_when_project_dir_unset(project_dir: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    r = subprocess.run(
        ["bash", str(HOOKS_DIR / "load_artifact_tail.sh")],
        env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert r.stdout == ""


def stdin_for_edit(file_path: Path) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}})


def run_hook_with_stdin(name: str, stdin: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env, input=stdin, capture_output=True, text=True,
    )


def test_lint_tics_warns_on_match(initialized_project: Path) -> None:
    bad = initialized_project / "thing.py"
    bad.write_text("# this is a pre-existing thing — should be flagged\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bad), initialized_project)
    assert r.returncode == 0
    assert "pre-existing" in r.stdout.lower()
    assert "BUGS.md" in r.stdout


def test_lint_tics_silent_on_no_match(initialized_project: Path) -> None:
    ok = initialized_project / "thing.py"
    ok.write_text("# clean code\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(ok), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_on_binary(initialized_project: Path) -> None:
    bin_file = initialized_project / "thing.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bin_file), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_when_no_artifacts(project_dir: Path) -> None:
    f = project_dir / "x.py"
    f.write_text("pre-existing code here\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(f), project_dir)
    assert r.returncode == 0
    assert r.stdout == ""  # no artifacts → don't warn


def test_wrap_session_emits_reminder_when_artifacts_exist(initialized_project: Path) -> None:
    r = run_hook("wrap_session.sh", initialized_project)
    assert r.returncode == 0
    assert "Route any unrouted observations" in r.stdout


def test_wrap_session_silent_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("wrap_session.sh", project_dir)
    assert r.returncode == 0
    assert r.stdout == ""


def test_hooks_json_structure() -> None:
    config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    hooks = config["hooks"]
    assert "SessionStart" in hooks
    assert "PostToolUse" in hooks
    assert "Stop" in hooks

    post = hooks["PostToolUse"][0]
    assert post["matcher"] == "Edit|Write"
    assert "lint_tics.sh" in post["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in post["hooks"][0]["command"]
