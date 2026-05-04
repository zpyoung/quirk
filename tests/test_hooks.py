from __future__ import annotations

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
