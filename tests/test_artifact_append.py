from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

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


def test_gaps_use_max_plus_one(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    body = bugs.read_text()
    for n in (3, 7, 12):
        body += f"\n## BUG-{n}: x\n- **File**: x.py:1\n- **Description**: y\n- **Severity**: low\n"
    bugs.write_text(body)
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=after gaps",
        "--field", "file=a.py:1",
        "--field", "description=z",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    assert "## BUG-13: after gaps" in bugs.read_text()


def test_schema_version_mismatch_exits_8(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    text = bugs.read_text().replace("schema-version: 1", "schema-version: 99")
    bugs.write_text(text)
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=t", "--field", "file=x:1",
        "--field", "description=d", "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 8
    assert "schema" in result.stderr.lower()


def test_missing_target_file_exits_3(project_dir: Path) -> None:
    # project_dir has no BUGS.md
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=t", "--field", "file=x:1",
        "--field", "description=d", "--field", "severity=low",
        cwd=project_dir,
    )
    assert result.returncode == 3
    assert "BUGS.md not found" in result.stderr
    assert "init" in result.stderr.lower()


@pytest.mark.parametrize(
    "kind, header, target_file, fields",
    [
        ("defer", "DEFER", "DEFERRED.md", [
            ("title", "ship later"),
            ("why_deferred", "out of scope"),
            ("priority", "P3"),
        ]),
        ("test-skip", "TEST", "TEST_BACKLOG.md", [
            ("title", "edge case"),
            ("file_under_test", "auth.ts"),
            ("reason_skipped", "complexity"),
        ]),
        ("proposal", "PROPOSAL", "proposals.md", [
            ("title", "rethink session storage"),
            ("context", "JWT has problems"),
            ("recommendation", "switch to opaque tokens"),
        ]),
    ],
)
def test_all_artifact_types_append(
    initialized_project: Path,
    kind: str, header: str, target_file: str,
    fields: list[tuple[str, str]],
) -> None:
    args = []
    for k, v in fields:
        args += ["--field", f"{k}={v}"]
    result = run_script("artifact_append.py", kind, *args, cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    target = (initialized_project / target_file).read_text()
    assert f"## {header}-1:" in target
    assert f"{header}-1:" in result.stdout


def test_concurrent_appends_do_not_collide_on_id(initialized_project: Path) -> None:
    """Two concurrent runs must produce BUG-1 and BUG-2, not two BUG-1s."""
    results = []

    def runner() -> None:
        r = run_script(
            "artifact_append.py", "bug",
            "--field", "title=concurrent",
            "--field", "file=x:1",
            "--field", "description=d",
            "--field", "severity=low",
            cwd=initialized_project,
        )
        results.append(r)

    threads = [threading.Thread(target=runner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    bugs = (initialized_project / "BUGS.md").read_text()
    assert "## BUG-1: concurrent" in bugs
    assert "## BUG-2: concurrent" in bugs
    assert all(r.returncode == 0 for r in results)


def test_lock_contention_exits_5(initialized_project: Path) -> None:
    """If the lock file is already held, the script gives up after the timeout and exits 5."""
    lock_path = initialized_project / ".BUGS.md.lock"
    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        # Run with a short fake timeout via env var
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.5"}
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "bin" / "artifact_append.py"),
             "bug",
             "--field", "title=t", "--field", "file=x:1",
             "--field", "description=d", "--field", "severity=low"],
            cwd=initialized_project,
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 5
        assert "lock" in r.stderr.lower()
