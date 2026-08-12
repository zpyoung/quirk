from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import pm

from .conftest import BIN_DIR, TEMPLATES_DIR, run_pm

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
    assert "BUGS.md" in result.stderr
    # the too-new schema is discovered in a read-only preflight before any lock is taken or any
    # file touched, so no other ledger's per-file report ever runs
    assert not (initialized_project / "ROADMAP.md").exists()


def test_migrate_too_new_ledger_outranks_lock_contention_on_another_file(
    initialized_project: Path,
) -> None:
    """tech.md's exit-code precedence (7 -> 3 -> 8 -> 5): a too-new schema must be discovered
    before any lock is even attempted, so contention on an unrelated ledger's lock can never mask
    it behind a 5.
    """
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 3"))

    lock_path = initialized_project / ".quirk" / "locks" / "DEFERRED.md.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.3"}
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "pm.py"), "migrate", "--project-dir", str(initialized_project)],
            capture_output=True,
            text=True,
            env=env,
        )

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH


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


# --- CRLF ledgers round-trip byte-for-byte -----------------------------------


def test_migrate_ledger_text_preserves_crlf_in_the_entry_body() -> None:
    raw = (
        b"<!-- schema-version: 1 -->\r\n"
        b"<!-- old SCHEMA -->\r\n"
        b"\r\n# BUGS\r\n\r\n"
        b"## BUG-1: title\r\n"
        b"- **Description**: body\r\n"
    )
    text = raw.decode()  # only \n and \r\n present, so a plain decode leaves both intact
    out = pm._migrate_ledger_text(text, "BUGS.md")

    before = raw.split(b"## BUG-1:", 1)[1]
    after = out.encode().split(b"## BUG-1:", 1)[1]
    assert after == before


def test_migrate_preserves_crlf_line_endings_through_the_full_command(
    legacy_project: Path,
) -> None:
    """`migrate`'s contract is that it touches no entry body — universal-newline translation on
    read would silently flatten every CRLF in the file to LF, which is exactly such a touch.
    """
    raw = (
        b"<!-- schema-version: 1 -->\r\n"
        b"<!-- old SCHEMA -->\r\n"
        b"\r\n# BUGS\r\n\r\n"
        b"## BUG-1: title\r\n"
        b"- **Description**: body\r\n"
    )
    bugs = legacy_project / "BUGS.md"
    bugs.write_bytes(raw)

    result = run_pm("migrate", cwd=legacy_project)
    assert result.returncode == 0, result.stderr

    before_body = raw.split(b"## BUG-1:", 1)[1]
    after_body = bugs.read_bytes().split(b"## BUG-1:", 1)[1]
    assert after_body == before_body
    assert pm.detect_schema_version(bugs.read_text()) == 2


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


def test_migrate_roadmap_creation_survives_a_crash_and_resumes_cleanly(
    initialized_project: Path, monkeypatch
) -> None:
    """A crash while creating `ROADMAP.md` must never leave a truncated file behind —
    `atomic_write`'s same-directory-temp-plus-rename means the file either doesn't exist or is
    the real template, never a partial copy a later `migrate` would then skip as "already
    exists" forever."""
    def raising_replace(*args, **kwargs):
        raise OSError("simulated crash mid-roadmap-write")

    monkeypatch.setattr(os, "replace", raising_replace)
    rc = pm.main(["migrate", "--project-dir", str(initialized_project)])
    assert rc == pm.EXIT_UNEXPECTED_ERROR
    assert not (initialized_project / "ROADMAP.md").exists()
    assert not list(initialized_project.glob(".ROADMAP.md.*.tmp"))

    monkeypatch.undo()
    rc = pm.main(["migrate", "--project-dir", str(initialized_project)])
    assert rc == pm.EXIT_OK
    assert (initialized_project / "ROADMAP.md").read_text() == (TEMPLATES_DIR / "ROADMAP.md").read_text()


def test_migrate_takes_the_roadmap_lock_before_writing_it(initialized_project: Path) -> None:
    """`migrate`'s `ROADMAP.md` creation must be serialized under `.quirk/locks/ROADMAP.md.lock`,
    the same lock `roadmap --write` takes — an externally held lock must block `migrate` exactly
    as an externally held ledger lock already does, instead of writing straight past it."""
    lock_path = initialized_project / ".quirk" / "locks" / "ROADMAP.md.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.3"}
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "pm.py"), "migrate", "--project-dir", str(initialized_project)],
            capture_output=True,
            text=True,
            env=env,
        )

    assert result.returncode == pm.EXIT_LOCK_TIMEOUT
    assert not (initialized_project / "ROADMAP.md").exists()


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


# --- lock timeout: exit 5 means nothing was written -------------------------


def test_migrate_lock_timeout_on_a_later_ledger_writes_nothing_at_all(
    legacy_project: Path,
) -> None:
    """A timeout acquiring any one ledger's lock must not leave earlier ledgers already
    migrated — exit 5's contract is that migrate wrote nothing, not that it wrote some.
    """
    before = {name: (legacy_project / name).read_bytes() for name in pm.LEDGER_FILES}
    lock_path = legacy_project / ".quirk" / "locks" / "TEST_BACKLOG.md.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.3"}
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "pm.py"), "migrate", "--project-dir", str(legacy_project)],
            capture_output=True,
            text=True,
            env=env,
        )

    assert result.returncode == pm.EXIT_LOCK_TIMEOUT
    assert "lock" in result.stderr.lower()
    for name in pm.LEDGER_FILES:
        assert (legacy_project / name).read_bytes() == before[name], name
    assert not (legacy_project / "ROADMAP.md").exists()


# --- ARTIFACT_LOCK_TIMEOUT: validated, not honored verbatim -----------------


@pytest.mark.parametrize("raw", ["inf", "-inf", "nan", "0", "-1", "not-a-number", ""])
def test_lock_timeout_rejects_bad_values_and_falls_back_to_the_default(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFACT_LOCK_TIMEOUT", raw)
    assert pm._lock_timeout() == pm.DEFAULT_LOCK_TIMEOUT


def test_lock_timeout_honors_a_valid_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_LOCK_TIMEOUT", "0.3")
    assert pm._lock_timeout() == 0.3


def test_migrate_survives_a_non_numeric_lock_timeout_env_value(legacy_project: Path) -> None:
    """A non-numeric `ARTIFACT_LOCK_TIMEOUT` must not raise `ValueError` out of the command —
    proves the validated helper is actually wired into `migrate`'s call site, not just defined."""
    env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "banana"}
    result = subprocess.run(
        [sys.executable, str(BIN_DIR / "pm.py"), "migrate", "--project-dir", str(legacy_project)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "Traceback" not in result.stderr


# --- CLI surface: every subcommand registered ------------------------------


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


# --- --project-dir: same effect before or after the subcommand --------------


def _make_populated_project(root: Path) -> Path:
    root.mkdir()
    for name in pm.LEDGER_FILES:
        shutil.copy(TEMPLATES_DIR / name, root / name)
    return root


@pytest.mark.parametrize(
    "argv",
    [["--project-dir", "{target}", "migrate"], ["migrate", "--project-dir", "{target}"]],
    ids=["before-subcommand", "after-subcommand"],
)
def test_project_dir_reaches_migrate_regardless_of_position(
    project_dir: Path, argv: list[str]
) -> None:
    """A `--project-dir` naming a path that doesn't exist must be the path `migrate` checks,
    not silently discarded in favor of the current directory (which does exist) — see the
    subparser-default-clobbers-the-outer-namespace mechanism the fix addresses.
    """
    missing = project_dir / "does-not-exist"
    resolved_argv = [a.format(target=str(missing)) for a in argv]

    result = run_pm(*resolved_argv, cwd=project_dir)

    assert result.returncode == pm.EXIT_PROJECT_DIR_NOT_FOUND


@pytest.mark.parametrize(
    "argv",
    [["--project-dir", "{target}", "--index"], ["--index", "--project-dir", "{target}"]],
    ids=["before-flag", "after-flag"],
)
def test_project_dir_reaches_bare_index_flag_regardless_of_position(
    tmp_path: Path, argv: list[str]
) -> None:
    target = _make_populated_project(tmp_path / "target")
    empty_cwd = tmp_path / "empty"
    empty_cwd.mkdir()
    resolved_argv = [a.format(target=str(target)) for a in argv]

    result = run_pm(*resolved_argv, cwd=empty_cwd)

    assert result.returncode == 0
    assert result.stdout == pm.render_index(target)



def _latin1_env() -> dict[str, str] | None:
    """An env whose preferred encoding is latin-1, or None if this host cannot produce one."""
    env = dict(os.environ)
    env.update(LC_ALL="en_US.ISO8859-1", LANG="en_US.ISO8859-1", PYTHONUTF8="0")
    probe = subprocess.run(
        [sys.executable, "-c", "import locale; print(locale.getpreferredencoding(False))"],
        env=env, capture_output=True, text=True,
    )
    return env if "8859" in probe.stdout else None


def test_migrate_preserves_non_ascii_entry_bodies(pm_project: Path) -> None:
    """migrate's read encoding must match atomic_write's, or non-ASCII bodies transcode.

    Forced to a latin-1 locale because the defect is invisible on a utf-8 host: there the two
    encodings agree and the assertion holds whether or not the read is pinned.
    """
    env = _latin1_env()
    if env is None:
        pytest.skip("host cannot produce a non-utf-8 preferred encoding")

    bugs = pm_project / "BUGS.md"
    text = bugs.read_text(encoding="utf-8").replace("schema-version: 2", "schema-version: 1")
    entry = "\n## BUG-1: em\u2014dash and \u00fcnicode\n- **Description**: na\u00efve caf\u00e9\n"
    bugs.write_text(text + entry, encoding="utf-8")
    before = bugs.read_bytes().split(b"## BUG-1:", 1)[1]

    result = subprocess.run(
        [sys.executable, str(BIN_DIR / "pm.py"), "migrate"],
        cwd=pm_project, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert bugs.read_bytes().split(b"## BUG-1:", 1)[1] == before
