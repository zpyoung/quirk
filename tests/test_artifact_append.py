from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_unknown_artifact_type_exits_2(initialized_project: Path) -> None:
    result = run_script("artifact_append.py", "bgu", cwd=initialized_project)
    assert result.returncode == 2
    assert "unknown type" in result.stderr.lower()
