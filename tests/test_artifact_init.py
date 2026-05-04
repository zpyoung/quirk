from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_init_empty_project_creates_all_artifacts(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        assert (project_dir / name).exists(), f"missing {name}"
    assert (project_dir / "docs" / "adr" / "0000-record-architecture-decisions.md").exists()
    assert "Created" in result.stdout
