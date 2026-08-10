"""The CAS transition mechanism and the four Phase-2 lifecycle commands.

docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The CAS transition mechanism, §Exit codes.
Phase 2 is `--here` only (logic.md:778-785): `start` writes no `Handoff`, creates no worktree,
launches nothing; `finish` compares the worktree root against the project's own repo.
"""
from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import pm

from .conftest import TEMPLATES_DIR, isolated_git_env, run_pm

SHA = "a" * 40


# --- fixtures --------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=isolated_git_env(), check=True,
    )


@pytest.fixture
def pm_git_project(fake_git_repo: Path) -> Path:
    """`fake_git_repo`, additionally scaffolded with v2 ledgers and committed.

    `finish`'s worktree-root precondition needs the project directory to itself be a git
    checkout, so lifecycle tests that exercise `finish` need this instead of `pm_project`.
    """
    for name in pm.LEDGER_FILES:
        shutil.copy(TEMPLATES_DIR / name, fake_git_repo / name)
    shutil.copy(TEMPLATES_DIR / "ROADMAP.md", fake_git_repo / "ROADMAP.md")
    (fake_git_repo / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    _git(fake_git_repo, "add", "-A")
    _git(fake_git_repo, "commit", "-q", "-m", "seed ledger")
    return fake_git_repo


def _append_entry(project: Path, filename: str, header: str, entry_id: int, title: str, fields: dict[str, str]) -> None:
    path = project / filename
    lines = [f"\n## {header}-{entry_id}: {title}"]
    for label, value in fields.items():
        lines.append(f"- **{label}**: {value}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def append_bug(project: Path, entry_id: int, title: str = "a bug", **fields: str) -> None:
    _append_entry(project, "BUGS.md", "BUG", entry_id, title, fields)


def append_proposal(project: Path, entry_id: int, title: str = "a proposal", **fields: str) -> None:
    _append_entry(project, "proposals.md", "PROPOSAL", entry_id, title, fields)


def bugs_text(project: Path) -> str:
    return (project / "BUGS.md").read_text()


def status_line(text: str, heading: str) -> str:
    """The `Status` line inside the entry whose heading starts with `heading` (e.g. `"## BUG-1:"`)

    — never the schema comment's own worked example, which also contains the literal substring
    `**Status**` and would otherwise be matched by a whole-file scan.
    """
    entry_text = text.split(heading, 1)[1]
    return next(line for line in entry_text.splitlines() if "**Status**" in line)


def commit_all(repo: Path, message: str = "commit") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


# --- transition table: start ------------------------------------------------


def test_start_from_never_started_open_writes_in_progress_attempt_1(pm_project: Path) -> None:
    append_bug(pm_project, 1)

    result = run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_project)
    assert "- **Status**: in_progress" in text
    assert "attempt 1" in text
    assert "- **Probe**: none" in text


def test_start_from_parked_open_increments_attempt_preserves_refused_clears_parked(pm_project: Path) -> None:
    append_bug(
        pm_project, 1,
        Status="open — 2026-08-07 — attempt 3 — refused 2 — parked: waiting on design",
    )

    result = run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_project)
    assert "in_progress" in text
    assert "attempt 4" in text
    assert "refused 2" in text
    assert "parked:" not in text


def test_start_refuses_when_already_in_progress(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_start_probe_already_green_refuses_exit9_and_writes_nothing(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm(
        "start", "BUG-1", "--probe", "grep:NO_SUCH_PATTERN_ANYWHERE_XYZ", "--here", cwd=pm_project,
    )

    assert result.returncode == pm.EXIT_PROBE_REFUSED, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_start_refuses_a_proposal_id(pm_project: Path) -> None:
    append_proposal(pm_project, 1, context="x", recommendation="y")
    before = (pm_project / "proposals.md").read_bytes()

    result = run_pm("start", "PROPOSAL-1", "--probe", "none", "--here", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "proposals.md").read_bytes() == before


def test_start_repo_flag_refuses_with_exit_2_in_phase_2(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("start", "BUG-1", "--probe", "none", "--repo", "some-repo", cwd=pm_project)

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


# --- transition table: finish -----------------------------------------------


def test_finish_delivers_on_clean_tree_and_passing_probe(pm_git_project: Path) -> None:
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1")
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: delivered" in text
    assert f"commit: {_git(pm_git_project, 'rev-parse', 'HEAD').stdout.strip()}" in text


def test_finish_refuses_when_probe_still_fails_and_increments_refused(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("PM_LIFECYCLE_MARKER\n")
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1 and marker")
    run_pm("start", "BUG-1", "--probe", "grep:PM_LIFECYCLE_MARKER", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_PROBE_REFUSED, result.stdout
    text = bugs_text(pm_git_project)
    assert "- **Status**: in_progress" in text
    assert "refused 1" in text
    assert "commit:" not in text


def test_finish_refuses_on_dirty_working_tree(pm_git_project: Path) -> None:
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1")
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")
    (pm_git_project / "uncommitted.txt").write_text("dirty\n")
    before = (pm_git_project / "BUGS.md").read_bytes()

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_FINISH_PRECONDITION_FAILED, result.stdout
    assert (pm_git_project / "BUGS.md").read_bytes() == before


def test_finish_refuses_when_project_dir_is_not_a_git_worktree(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("finish", "BUG-1", cwd=pm_project)

    assert result.returncode == pm.EXIT_FINISH_PRECONDITION_FAILED, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_finish_refuses_a_proposal_id(pm_git_project: Path) -> None:
    append_proposal(pm_git_project, 1, context="x", recommendation="y")
    commit_all(pm_git_project, "add proposal")
    before = (pm_git_project / "proposals.md").read_bytes()

    result = run_pm("finish", "PROPOSAL-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_git_project / "proposals.md").read_bytes() == before


# --- transition table: park --------------------------------------------------


def test_park_returns_to_open_keeping_attempt_and_refused(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    result = run_pm("park", "BUG-1", "--reason", "waiting on design", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_project)
    assert "- **Status**: open" in text
    assert "attempt 1" in text
    assert "parked: waiting on design" in text


def test_park_refuses_when_not_in_progress(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("park", "BUG-1", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_park_rejects_a_reason_containing_the_delimiter(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("park", "BUG-1", "--reason", "bad — reason", cwd=pm_project)

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_park_refuses_a_proposal_id(pm_project: Path) -> None:
    append_proposal(pm_project, 1, context="x", recommendation="y")
    before = (pm_project / "proposals.md").read_bytes()

    result = run_pm("park", "PROPOSAL-1", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "proposals.md").read_bytes() == before


# --- transition table: decide ------------------------------------------------


def test_decide_wontfix_from_never_started_open_omits_attempt(pm_project: Path) -> None:
    append_bug(pm_project, 1)

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "not worth it", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    line = status_line(bugs_text(pm_project), "## BUG-1:")
    assert line.startswith("- **Status**: wontfix")
    assert "attempt" not in line
    assert "reason: not worth it" in line


def test_decide_wontfix_from_in_progress(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "not worth it", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_project)
    assert "- **Status**: wontfix — " in text
    assert "attempt 1" in text


def test_decide_wontfix_from_delivered(pm_project: Path) -> None:
    append_bug(pm_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {SHA}")

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "supersede plans", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "- **Status**: wontfix" in bugs_text(pm_project)


def test_decide_superseded_requires_by(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("decide", "BUG-1", "--as", "superseded", "--reason", "folded in", cwd=pm_project)

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_decide_superseded_with_by_succeeds(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    append_bug(pm_project, 2, title="the replacement")

    result = run_pm(
        "decide", "BUG-1", "--as", "superseded", "--reason", "folded into BUG-2", "--by", "BUG-2",
        cwd=pm_project,
    )

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_project)
    assert "- **Status**: superseded" in text
    assert "by: BUG-2" in text
    assert "reason: folded into BUG-2" in text


def test_decide_refuses_from_a_terminal_state(pm_project: Path) -> None:
    append_bug(pm_project, 1, Status="wontfix — 2026-08-05 — reason: already decided")
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "again", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_decide_refuses_a_proposal_id(pm_project: Path) -> None:
    append_proposal(pm_project, 1, context="x", recommendation="y")
    before = (pm_project / "proposals.md").read_bytes()

    result = run_pm("decide", "PROPOSAL-1", "--as", "wontfix", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout
    assert (pm_project / "proposals.md").read_bytes() == before


# --- regression row 1: the stale-finish interleaving ------------------------
#
# This is the test the whole CAS mechanism exists for: a status-only compare passes this exact
# sequence, writing attempt 1's evidence onto attempt 2's entry.


def test_regression_row1_stale_finish_interleaving_refuses_and_preserves_attempt_2(
    pm_git_project: Path,
) -> None:
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1")
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1 attempt 1")

    spec = next(s for s in pm.ALL_SPECS if s.header == "BUG")
    prepared = pm._prepare_transition(
        pm_git_project, "BUG-1", validate_args=lambda: None, allowed_states=frozenset({"in_progress"}),
    )
    assert isinstance(prepared, pm._Prepared)
    stale_expected = pm._expectation(prepared)
    stale_head_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()

    run_pm("park", "BUG-1", "--reason", "out of budget", cwd=pm_git_project)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1 attempt 2")

    stale_new_status = pm.StatusField(
        state="delivered", date=pm._today(), attempt=1, refused=0, commit=stale_head_sha,
    )
    refusal = pm._commit_transition(
        pm_git_project, spec, prepared.entry_id, stale_expected, stale_new_status, None,
    )

    assert refusal is not None
    assert refusal.code == pm.EXIT_CAS_FAILURE

    text = bugs_text(pm_git_project)
    assert "- **Status**: in_progress" in text
    assert "attempt 2" in text
    assert "commit:" not in text
    assert stale_head_sha not in text


# --- regression row 2: park keeps its counters ------------------------------


def test_regression_row2_park_preserves_attempt_and_refused_across_restart(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("PM_LIFECYCLE_MARKER\n")
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1 and marker")
    run_pm("start", "BUG-1", "--probe", "grep:PM_LIFECYCLE_MARKER", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    run_pm("finish", "BUG-1", cwd=pm_git_project)
    # finish's own refusal write lands in the same checkout it just checked for cleanliness —
    # committing it (as a real worker would, alongside their next attempt) keeps the tree clean
    # for the next finish call
    commit_all(pm_git_project, "record refusal 1")
    run_pm("finish", "BUG-1", cwd=pm_git_project)
    commit_all(pm_git_project, "record refusal 2")

    result = run_pm("park", "BUG-1", "--reason", "out of budget", cwd=pm_git_project)
    assert result.returncode == pm.EXIT_OK, result.stderr
    line = status_line(bugs_text(pm_git_project), "## BUG-1:")
    assert "attempt 1" in line
    assert "refused 2" in line
    assert "parked: out of budget" in line

    result = run_pm("start", "BUG-1", "--probe", "grep:PM_LIFECYCLE_MARKER", "--here", cwd=pm_git_project)
    assert result.returncode == pm.EXIT_OK, result.stderr
    line = status_line(bugs_text(pm_git_project), "## BUG-1:")
    assert "attempt 2" in line
    assert "refused 2" in line
    assert "parked:" not in line


# --- CAS race: two `finish` calls, exactly one wins -------------------------
#
# Mirrors tests/test_artifact_append.py::test_concurrent_appends_do_not_collide_on_id's
# threading pattern.


def test_cas_race_two_finish_calls_exactly_one_succeeds(pm_git_project: Path) -> None:
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1")
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    results: list[subprocess.CompletedProcess] = []

    def runner() -> None:
        results.append(run_pm("finish", "BUG-1", cwd=pm_git_project))

    threads = [threading.Thread(target=runner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    codes = sorted(r.returncode for r in results)
    assert codes == [pm.EXIT_OK, pm.EXIT_CAS_FAILURE]
    assert "- **Status**: delivered" in bugs_text(pm_git_project)


# --- crash mid-transition: atomic_write leaves the file untouched ----------


def test_crash_mid_transition_leaves_ledger_byte_identical(pm_project: Path, monkeypatch) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)
    bugs = pm_project / "BUGS.md"
    before = bugs.read_bytes()

    def raising_replace(*args, **kwargs):
        raise OSError("simulated crash mid-transition")

    monkeypatch.setattr(os, "replace", raising_replace)

    rc = pm.main(["park", "BUG-1", "--reason", "x", "--project-dir", str(pm_project)])

    assert rc == pm.EXIT_UNEXPECTED_ERROR
    assert bugs.read_bytes() == before


# --- MalformedField status: exit 4, never written over ----------------------


def test_malformed_status_refuses_exit4_and_leaves_the_ledger_untouched(pm_project: Path) -> None:
    append_bug(pm_project, 1, Status="bogus_state — 2026-08-05")
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("park", "BUG-1", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_malformed_heading_claiming_the_id_refuses_exit4(pm_project: Path) -> None:
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1:\n- **Description**: no title\n")
    before = bugs.read_bytes()

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert bugs.read_bytes() == before


def test_duplicate_entry_id_refuses_exit4(pm_project: Path) -> None:
    append_bug(pm_project, 1, title="first")
    append_bug(pm_project, 1, title="second")
    before = (pm_project / "BUGS.md").read_bytes()

    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert (pm_project / "BUGS.md").read_bytes() == before


def test_duplicated_status_line_refuses_exit4_via_splice_field(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    bugs = pm_project / "BUGS.md"
    text = bugs.read_text()
    marker = "\n## BUG-1: a bug"
    idx = text.index(marker) + len(marker)
    dup_line = "\n- **Status**: in_progress — 2026-08-05 — attempt 1"
    bugs.write_text(text[:idx] + dup_line + dup_line + text[idx:])
    before = bugs.read_bytes()

    result = run_pm("park", "BUG-1", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert bugs.read_bytes() == before


# --- v1 ledger: exit 8 ------------------------------------------------------


def test_v1_ledger_refuses_write_with_exit8(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 1"))
    before = bugs.read_bytes()

    result = run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH, result.stdout
    assert bugs.read_bytes() == before


# --- exit-code precedence: one fixture per command's chain -----------------


def test_precedence_start_not_found_beats_bad_probe_argument(pm_project: Path) -> None:
    result = run_pm("start", "BUG-999", "--probe", "not-a-real-verb", "--here", cwd=pm_project)
    assert result.returncode == pm.EXIT_NOT_FOUND, result.stdout


def test_precedence_finish_precondition_beats_probe_refusal(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("PM_LIFECYCLE_MARKER\n")
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1 and marker")
    run_pm("start", "BUG-1", "--probe", "grep:PM_LIFECYCLE_MARKER", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")
    # dirty tree AND a still-failing probe both hold; 10 must win over 9
    (pm_git_project / "uncommitted.txt").write_text("dirty\n")

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_FINISH_PRECONDITION_FAILED, result.stdout


def test_precedence_park_schema_mismatch_beats_corrupt_entry(pm_project: Path) -> None:
    append_bug(pm_project, 1, title="first")
    append_bug(pm_project, 1, title="second")
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 1"))
    before = bugs.read_bytes()

    result = run_pm("park", "BUG-1", "--reason", "x", cwd=pm_project)

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH, result.stdout
    assert bugs.read_bytes() == before


def test_precedence_decide_not_found_beats_bad_reason(pm_project: Path) -> None:
    result = run_pm("decide", "BUG-999", "--as", "wontfix", "--reason", "bad — reason", cwd=pm_project)
    assert result.returncode == pm.EXIT_NOT_FOUND, result.stdout


# --- lock timeout: exit 5 means nothing was written -------------------------


def test_lock_timeout_on_park_writes_nothing(pm_project: Path) -> None:
    append_bug(pm_project, 1)
    run_pm("start", "BUG-1", "--probe", "none", "--here", cwd=pm_project)
    before = (pm_project / "BUGS.md").read_bytes()

    lock_path = pm_project / ".quirk" / "locks" / "BUGS.md.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.3"}
        result = subprocess.run(
            [sys.executable, str(pm.REPO_ROOT / "bin" / "pm.py"), "park", "BUG-1", "--reason", "x"],
            cwd=pm_project, capture_output=True, text=True, env=env,
        )

    assert result.returncode == pm.EXIT_LOCK_TIMEOUT, result.stderr
    assert (pm_project / "BUGS.md").read_bytes() == before


# --- project dir missing: exit 7 --------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["start", "BUG-1", "--probe", "none", "--here"],
        ["finish", "BUG-1"],
        ["park", "BUG-1", "--reason", "x"],
        ["decide", "BUG-1", "--as", "wontfix", "--reason", "x"],
    ],
)
def test_project_dir_missing_exits_7(project_dir: Path, argv: list[str]) -> None:
    missing = project_dir / "does-not-exist"
    result = run_pm(*argv, "--project-dir", str(missing), cwd=project_dir)
    assert result.returncode == pm.EXIT_PROJECT_DIR_NOT_FOUND, result.stdout


# --- not found: exit 3 ------------------------------------------------------


def test_entry_not_found_exits_3(pm_project: Path) -> None:
    result = run_pm("finish", "BUG-1", cwd=pm_project)
    assert result.returncode == pm.EXIT_NOT_FOUND, result.stdout


def test_ledger_file_missing_exits_3(pm_project: Path) -> None:
    (pm_project / "BUGS.md").unlink()
    result = run_pm("decide", "BUG-1", "--as", "wontfix", "--reason", "x", cwd=pm_project)
    assert result.returncode == pm.EXIT_NOT_FOUND, result.stdout
