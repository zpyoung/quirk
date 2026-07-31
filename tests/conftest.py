from __future__ import annotations

import importlib.util
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


def run_script(script_name: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a bin/*.py script in a child process; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(BIN_DIR / script_name), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


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
