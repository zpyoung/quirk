from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_unknown_artifact_type_exits_2(initialized_project: Path) -> None:
    result = run_script("artifact_append.py", "bgu", cwd=initialized_project)
    assert result.returncode == 2
    assert "unknown type" in result.stderr.lower()


def test_missing_required_field_exits_2(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=auth fails",
        "--field", "file=login.ts:42",
        # missing: description, severity
        cwd=initialized_project,
    )
    assert result.returncode == 2
    assert "missing required field" in result.stderr.lower()


def test_unknown_field_exits_2(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "nonsense=oops",
        cwd=initialized_project,
    )
    assert result.returncode == 2
    assert "unknown field" in result.stderr.lower()


def test_append_bug_1_to_empty_file(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=auth fails on safari",
        "--field", "file=login.ts:42",
        "--field", "description=safari rejects the cookie",
        "--field", "severity=high",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    bugs = (initialized_project / "BUGS.md").read_text()
    assert "## BUG-1: auth fails on safari" in bugs
    assert "**File**: login.ts:42" in bugs
    assert "**Severity**: high" in bugs
    assert "BUG-1: auth fails on safari" in result.stdout
