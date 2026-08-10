from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

import pm

from .conftest import TEMPLATES_DIR, run_pm

V1_BUGS = """<!-- schema-version: 1 -->
<!-- BUGS.md SCHEMA (append only — do not rewrite existing entries)
Entry format:
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]

Required fields: title, file, description, severity.
-->

# BUGS

Bugs noticed during sessions but not fixed in the current scope.

## BUG-1: legacy sample bug
- **Observed**: 2026-01-01
- **File**: x.py:1
- **Description**: sample description with an em dash — kept verbatim
- **Severity**: high
"""

V1_DEFERRED = """<!-- schema-version: 1 -->
<!-- DEFERRED.md SCHEMA (append only)
Entry format:
## DEFER-[N]: [Task title]
- **Deferred**: [date]
- **Session context**: [what triggered this]
- **Why deferred**: [out of scope / blocked on / requires decision]
- **Estimated effort**: [S/M/L]
- **Priority**: [P1/P2/P3/P4]
- **Proposed owner**: [Claude / name / unassigned]

Required fields: title, why_deferred, priority.
-->

# DEFERRED

Tasks surfaced during sessions but explicitly out of scope for the current work.

## DEFER-1: legacy deferred task
- **Deferred**: 2026-01-01
- **Why deferred**: out of scope
- **Priority**: P2
"""

V1_TEST_BACKLOG = """<!-- schema-version: 1 -->
<!-- TEST_BACKLOG.md SCHEMA (append only)
Entry format:
## TEST-[N]: [Function or behavior to test]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1/P2/P3/P4]

Required fields: file_under_test, reason_skipped.
-->

# TEST BACKLOG

Tests that were skipped, abbreviated, or flagged as needing expansion.

## TEST-1: legacy skipped test
- **File under test**: bin/pm.py
- **Test type**: unit
- **Reason skipped**: complexity
- **Priority**: P3
"""


@pytest.fixture
def legacy_project(project_dir: Path) -> Path:
    """A project whose four ledgers are genuine pre-migration schema-v1 content, no ROADMAP.md.

    `proposals.md` is built from the shipped v2 template with only the version digit rolled
    back, mirroring this repo's own ledger today — `proposals.md` never gained new fields, so
    its v1 and v2 comment text are identical, unlike the other three files' hand-written v1
    text above, which must omit the v2-only fields to be a genuine pre-migration fixture.
    """
    (project_dir / "BUGS.md").write_text(V1_BUGS)
    (project_dir / "DEFERRED.md").write_text(V1_DEFERRED)
    (project_dir / "TEST_BACKLOG.md").write_text(V1_TEST_BACKLOG)
    v2_proposals = (TEMPLATES_DIR / "proposals.md").read_text()
    v1_proposals = v2_proposals.replace("schema-version: 2", "schema-version: 1", 1)
    (project_dir / "proposals.md").write_text(v1_proposals)
    return project_dir


# --- idempotent no-op ----------------------------------------------------


def test_migrate_is_idempotent_on_an_already_v2_project(initialized_project: Path) -> None:
    before = {name: (initialized_project / name).read_bytes() for name in pm.LEDGER_FILES}

    result = run_pm("migrate", cwd=initialized_project)

    assert result.returncode == 0, result.stderr
    for name in pm.LEDGER_FILES:
        assert (initialized_project / name).read_bytes() == before[name]
        assert f"{name}: already v2" in result.stdout


# --- partial-run resume ---------------------------------------------------


def test_migrate_partial_run_resumes_cleanly_after_a_crash(
    legacy_project: Path, monkeypatch
) -> None:
    bugs = legacy_project / "BUGS.md"
    original = bugs.read_bytes()

    def raising_replace(*args, **kwargs):
        raise OSError("simulated crash mid-migration")

    monkeypatch.setattr(os, "replace", raising_replace)
    rc = pm.main(["migrate", "--project-dir", str(legacy_project)])
    assert rc == pm.EXIT_UNEXPECTED_ERROR
    assert bugs.read_bytes() == original
    assert pm.detect_schema_version(bugs.read_text()) == 1

    monkeypatch.undo()
    rc = pm.main(["migrate", "--project-dir", str(legacy_project)])
    assert rc == pm.EXIT_OK
    assert pm.detect_schema_version(bugs.read_text()) == 2


# --- proposals.md version bump only ---------------------------------------


def test_migrate_proposals_only_changes_the_version_marker(legacy_project: Path) -> None:
    result = run_pm("migrate", cwd=legacy_project)
    assert result.returncode == 0, result.stderr

    migrated = (legacy_project / "proposals.md").read_text()
    template = (TEMPLATES_DIR / "proposals.md").read_text()
    assert migrated == template


# --- refusal on a newer schema --------------------------------------------


def test_migrate_refuses_a_schema_version_newer_than_it_understands(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 3"))
    before = bugs.read_bytes()

    result = run_pm("migrate", cwd=initialized_project)

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH
    assert bugs.read_bytes() == before
    assert "BUGS.md" in result.stdout
    assert "DEFERRED.md: already v2" in result.stdout
    assert "TEST_BACKLOG.md: already v2" in result.stdout
    assert "proposals.md: already v2" in result.stdout


# --- TEST_BACKLOG.md gains Logged without touching entries ----------------


def test_migrate_test_backlog_adds_logged_without_touching_existing_entries(
    legacy_project: Path,
) -> None:
    before_body = (legacy_project / "TEST_BACKLOG.md").read_text().split("## TEST-1:", 1)[1]

    result = run_pm("migrate", cwd=legacy_project)
    assert result.returncode == 0, result.stderr

    after_text = (legacy_project / "TEST_BACKLOG.md").read_text()
    after_body = after_text.split("## TEST-1:", 1)[1]
    assert after_body == before_body
    assert "- **Logged**: [date, auto-stamped like Observed/Deferred/Proposed on every other type]" in after_text


# --- ROADMAP.md create-or-skip --------------------------------------------


def test_migrate_creates_roadmap_when_absent(legacy_project: Path) -> None:
    assert not (legacy_project / "ROADMAP.md").exists()

    result = run_pm("migrate", cwd=legacy_project)

    assert result.returncode == 0, result.stderr
    assert (legacy_project / "ROADMAP.md").read_text() == (TEMPLATES_DIR / "ROADMAP.md").read_text()
    assert "ROADMAP.md: created" in result.stdout


def test_migrate_leaves_an_existing_roadmap_alone(legacy_project: Path) -> None:
    custom = "<!-- schema-version: 2 -->\n<!-- ROADMAP.md SCHEMA -->\n\n# ROADMAP\n\n## Milestone: custom\n- BUG-1\n"
    (legacy_project / "ROADMAP.md").write_text(custom)

    result = run_pm("migrate", cwd=legacy_project)

    assert result.returncode == 0, result.stderr
    assert (legacy_project / "ROADMAP.md").read_text() == custom
    assert "ROADMAP.md: already exists" in result.stdout


# --- aggregate precondition failures --------------------------------------


def test_migrate_exits_3_when_a_ledger_file_is_missing_and_attempts_nothing(
    legacy_project: Path,
) -> None:
    (legacy_project / "proposals.md").unlink()
    before = (legacy_project / "BUGS.md").read_bytes()

    result = run_pm("migrate", cwd=legacy_project)

    assert result.returncode == pm.EXIT_NOT_FOUND
    assert "proposals.md" in result.stderr
    assert (legacy_project / "BUGS.md").read_bytes() == before
    assert not (legacy_project / "ROADMAP.md").exists()


def test_migrate_exits_7_when_the_project_dir_is_missing(project_dir: Path) -> None:
    missing = project_dir / "does-not-exist"

    result = run_pm("migrate", "--project-dir", str(missing), cwd=project_dir)

    assert result.returncode == pm.EXIT_PROJECT_DIR_NOT_FOUND


# --- CLI surface: every subcommand registered ------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["start", "BUG-1", "--probe", "pytest:tests/test_x.py"],
        ["finish", "BUG-1"],
        ["park", "BUG-1", "--reason", "waiting on upstream"],
        ["decide", "BUG-1", "--as", "wontfix", "--reason", "not worth it"],
        ["reconcile"],
        ["roadmap", "--show"],
    ],
)
def test_unimplemented_subcommands_exit_two_and_say_so(
    initialized_project: Path, argv: list[str]
) -> None:
    result = run_pm(*argv, cwd=initialized_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert "not implemented" in result.stderr.lower()


def test_all_eleven_subcommands_are_registered() -> None:
    parser = pm.build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    assert set(subparsers_action.choices) == {
        "next", "start", "finish", "park", "decide", "reconcile",
        "roadmap", "status", "index", "doctor", "migrate",
    }


# --- bare flags vs. subcommands: identical output --------------------------


@pytest.mark.parametrize("bare,sub", [("--index", "index"), ("--next", "next"), ("--doctor", "doctor")])
def test_bare_flag_and_subcommand_produce_identical_output(
    initialized_project: Path, bare: str, sub: str
) -> None:
    bare_result = run_pm(bare, cwd=initialized_project)
    sub_result = run_pm(sub, cwd=initialized_project)

    assert bare_result.returncode == 0
    assert sub_result.returncode == 0
    assert bare_result.stdout == sub_result.stdout


# --- status = index + doctor ------------------------------------------------


def test_status_equals_index_output_followed_by_doctor_output(initialized_project: Path) -> None:
    index_result = run_pm("index", cwd=initialized_project)
    doctor_result = run_pm("doctor", cwd=initialized_project)
    status_result = run_pm("status", cwd=initialized_project)

    assert status_result.returncode == 0
    assert status_result.stdout == index_result.stdout + doctor_result.stdout
