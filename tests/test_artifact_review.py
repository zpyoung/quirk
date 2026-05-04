from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_review_empty_project_reports_no_entries(initialized_project: Path) -> None:
    result = run_script("artifact_review.py", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md" in out
    assert "no entries" in out.lower()


def test_review_lists_populated_entries(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + (
        "\n## BUG-1: alpha\n- **File**: a:1\n- **Description**: x\n- **Severity**: high\n"
        "\n## BUG-2: beta\n- **File**: b:1\n- **Description**: y\n- **Severity**: low\n"
    ))
    defers = initialized_project / "DEFERRED.md"
    defers.write_text(defers.read_text() + (
        "\n## DEFER-1: refactor\n- **Why deferred**: out of scope\n- **Priority**: P2\n"
    ))
    result = run_script("artifact_review.py", cwd=initialized_project)
    assert result.returncode == 0
    out = result.stdout
    assert "BUGS.md: 2 entries" in out
    assert "BUG-1 [high] alpha" in out
    assert "BUG-2 [low] beta" in out
    assert "DEFERRED.md: 1 entries" in out
    assert "DEFER-1 [P2] refactor" in out
