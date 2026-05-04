from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_review_empty_project_reports_no_entries(initialized_project: Path) -> None:
    result = run_script("artifact_review.py", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md" in out
    assert "no entries" in out.lower()
