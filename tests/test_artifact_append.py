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


def test_empty_optional_field_is_omitted(initialized_project: Path) -> None:
    """A user-supplied optional field with empty value should not render as a bare label."""
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=clean entry",
        "--field", "file=x:1",
        "--field", "description=test",
        "--field", "severity=low",
        "--field", "proposed_fix=",  # explicit empty
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    bugs = (initialized_project / "BUGS.md").read_text()
    # Extract just the BUG-1 entry (after the schema comment).
    parts = bugs.split("## BUG-1: clean entry")
    assert len(parts) == 2, "Entry not found"
    entry = parts[1]
    # The proposed_fix label must NOT appear in the rendered entry.
    assert "**Proposed fix**:" not in entry
    # But required fields must be there.
    assert "**File**: x:1" in entry
    assert "**Description**: test" in entry
    assert "**Severity**: low" in entry


def test_sequential_id_increment(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-6: prior\n- **File**: x.py:1\n- **Description**: y\n- **Severity**: low\n")
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=new bug",
        "--field", "file=a.py:1",
        "--field", "description=z",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    assert "## BUG-7: new bug" in bugs.read_text()
    assert "BUG-7: new bug" in result.stdout
