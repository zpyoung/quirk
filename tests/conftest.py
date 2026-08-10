from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"
TEMPLATES_DIR = REPO_ROOT / "templates"
HOOKS_DIR = REPO_ROOT / "hooks"
FILING_SCRIPTS_DIR = REPO_ROOT / "skills" / "filing-requests" / "scripts"


def isolated_git_env() -> dict[str, str]:
    """Environment for a git subprocess call that ignores the machine's global/system config.

    Shared by `fake_git_repo` and any later caller (worktree/fetch/merge-base tests) that runs
    git against its repo — without this, an ambient `core.hooksPath` or `init.templateDir` can
    run hook code the test never asked for, reaching the network or hanging on a machine the
    author never tested against.
    """
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A fresh empty 'project' directory the scripts can mutate."""
    return tmp_path


@pytest.fixture
def initialized_project(project_dir: Path) -> Path:
    """A project pre-populated with empty artifact files (no entries)."""
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        src = TEMPLATES_DIR / name
        if src.exists():
            shutil.copy(src, project_dir / name)
    adr_dir = project_dir / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


@pytest.fixture
def pm_project(initialized_project: Path) -> Path:
    """initialized_project, additionally at schema v2 and given an empty ROADMAP.md."""
    shutil.copy(TEMPLATES_DIR / "ROADMAP.md", initialized_project / "ROADMAP.md")
    return initialized_project


@pytest.fixture
def fake_git_repo(tmp_path: Path) -> Path:
    """A real `git init`-ed repo with one commit, for worktree/reconcile tests — no network."""
    repo = tmp_path / "fake_git_repo"
    repo.mkdir()
    empty_template = tmp_path / "fake_git_repo_template"
    empty_template.mkdir()
    empty_hooks = tmp_path / "fake_git_repo_hooks"
    empty_hooks.mkdir()
    env = isolated_git_env()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env
        )

    # --template neutralizes a global `init.templateDir`; core.hooksPath below neutralizes a
    # global `core.hooksPath` set after init — either would otherwise let hook code run
    git("init", "-q", f"--template={empty_template}")
    git("config", "core.hooksPath", str(empty_hooks))
    # local, not --global: a CI runner has no global git identity or signing config to fall back on
    git("config", "user.email", "quirk-test@example.invalid")
    git("config", "user.name", "Quirk Test")
    git("config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("fake repo for tests\n")
    git("add", "README.md")
    git("commit", "-q", "-m", "initial commit")
    return repo


def run_script(script_name: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a bin/*.py script in a child process; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(BIN_DIR / script_name), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def run_pm(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke bin/pm.py in a child process; mirrors the existing run_script helper."""
    return run_script("pm.py", *args, cwd=cwd)


def load_filing_module(name: str) -> ModuleType:
    """Load a skills/filing-requests/scripts/<name>.py module by path, without touching sys.path."""
    path = FILING_SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"filing_requests_scripts.{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_filing_script(
    script_name: str, *args: str, cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess:
    """Invoke a skills/filing-requests/scripts/<name>.py in a child process."""
    return subprocess.run(
        [sys.executable, str(FILING_SCRIPTS_DIR / script_name), *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
    )
