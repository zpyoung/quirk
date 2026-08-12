"""`reconcile`: the git-ancestry promotion algorithm, `--close`, and `--verify`.

docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The reconcile algorithm, §Field rendering
(`Verify`), §Exit codes. Phase 2 only (logic.md:778-785): reconcile always evaluates in the
project's own repo, since `start` is `--here`-only and no `Handoff` field is ever written. The
cross-project fixture (`Handoff.dest:`) is Phase 3 and out of scope here.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

import pm

from .conftest import TEMPLATES_DIR, isolated_git_env, run_pm

NONEXISTENT_SHA = "f" * 40


# --- fixtures and helpers ---------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=isolated_git_env(), check=True,
    )


@pytest.fixture
def pm_git_project(fake_git_repo: Path) -> Path:
    """`fake_git_repo`, additionally scaffolded with v2 ledgers and committed.

    `reconcile`'s target repo (Phase 2: the project dir itself) must be a real git checkout so
    ancestry/fetch/worktree calls have something to run against.
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


def append_defer(project: Path, entry_id: int, title: str = "a deferral", **fields: str) -> None:
    _append_entry(project, "DEFERRED.md", "DEFER", entry_id, title, fields)


def bugs_text(project: Path) -> str:
    return (project / "BUGS.md").read_text()


def status_line(text: str, heading: str) -> str:
    entry_text = text.split(heading, 1)[1]
    return next(line for line in entry_text.splitlines() if "**Status**" in line)


def field_line(text: str, heading: str, label: str) -> str:
    entry_text = text.split(heading, 1)[1]
    return next(line for line in entry_text.splitlines() if f"**{label}**" in line)


def commit_all(repo: Path, message: str = "commit") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def current_branch(repo: Path) -> str:
    return _git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()


def _parse_args(*argv: str) -> argparse.Namespace:
    return pm.build_parser().parse_args(list(argv))


# --- VerifyField: render/parse round trip -----------------------------------


def test_verify_field_round_trips() -> None:
    field = pm.VerifyField(date="2026-08-07", integration_ref="origin/main", probe="pass")
    value = pm.render_verify(field)
    assert value == "2026-08-07 — integration_ref: origin/main — probe: pass"
    parsed = pm.parse_verify(value)
    assert parsed == field
    assert pm.render_verify(parsed) == value


def test_verify_field_rejects_unknown_probe_token() -> None:
    parsed = pm.parse_verify("2026-08-07 — integration_ref: origin/main — probe: bogus")
    assert isinstance(parsed, pm.MalformedField)


def test_verify_field_rejects_missing_segment() -> None:
    parsed = pm.parse_verify("2026-08-07 — integration_ref: origin/main")
    assert isinstance(parsed, pm.MalformedField)


def test_verify_field_rejects_trailing_segment() -> None:
    parsed = pm.parse_verify("2026-08-07 — integration_ref: origin/main — probe: pass — extra")
    assert isinstance(parsed, pm.MalformedField)


# --- closed Status: reason segment (--close) --------------------------------


def test_closed_status_without_reason_round_trips_unchanged() -> None:
    field = pm.StatusField(state="closed", date="2026-08-06", attempt=1, integrated="a" * 40)
    value = pm.render_status(field)
    assert value == f"closed — 2026-08-06 — attempt 1 — integrated: {'a' * 40}"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_closed_status_with_reason_round_trips() -> None:
    field = pm.StatusField(
        state="closed", date="2026-08-06", attempt=1, integrated="a" * 40,
        reason="landed via rebase, worker sha unreachable",
    )
    value = pm.render_status(field)
    assert value.endswith("reason: landed via rebase, worker sha unreachable")
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


# --- condition table: promote / not-yet / cannot-evaluate ------------------


def test_reconcile_promotes_reachable_commit_to_closed(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    line = status_line(text, "## BUG-1:")
    assert line.startswith("- **Status**: closed")
    assert f"integrated: {sha}" in line
    assert "closed" in result.stdout


def test_reconcile_leaves_not_yet_reachable_commit_as_delivered(pm_git_project: Path) -> None:
    base_branch = current_branch(pm_git_project)
    _git(pm_git_project, "checkout", "-q", "-b", "feature")
    (pm_git_project / "feature.txt").write_text("feature work\n")
    commit_all(pm_git_project, "feature work")
    feature_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", base_branch)

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {feature_sha}", Probe="none",
    )

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert status_line(text, "## BUG-1:").startswith("- **Status**: delivered")
    assert "awaiting integration" in result.stdout


def test_reconcile_reports_cannot_evaluate_commit_not_in_repo(pm_git_project: Path) -> None:
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {NONEXISTENT_SHA}", Probe="none",
    )

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "cannot evaluate" in result.stdout
    assert "commit not in destination repo" in result.stdout
    text = bugs_text(pm_git_project)
    assert status_line(text, "## BUG-1:").startswith("- **Status**: delivered")


def test_reconcile_reports_fetch_failed(pm_git_project: Path) -> None:
    _git(pm_git_project, "remote", "add", "origin", "/nonexistent/path/to/nowhere.git")
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "fetch failed" in result.stdout
    text = bugs_text(pm_git_project)
    assert status_line(text, "## BUG-1:").startswith("- **Status**: delivered")


def test_reconcile_reports_integration_ref_unresolvable_distinct_from_unknown_commit(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # regression: the two must not collapse into the same diagnostic (tech.md, exit 128 is not
    # one condition)
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    monkeypatch.setenv("QUIRK_PM_INTEGRATION_REF", "no-such-ref-anywhere")

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "integration ref unresolvable: no-such-ref-anywhere" in result.stdout
    assert "commit not in destination repo" not in result.stdout


def test_evaluate_delivered_reports_destination_repo_missing(tmp_path: Path) -> None:
    outcome, detail = pm._evaluate_delivered(tmp_path / "does-not-exist", "a" * 40, {})
    assert outcome == "cannot_evaluate"
    assert detail == "destination repo missing"


def test_evaluate_delivered_reports_git_error_on_unexpected_merge_base_exit(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    real_run_git = pm._run_git

    def fake_run_git(args: list[str], cwd: Path):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 99, stdout="", stderr="weird failure\n")
        return real_run_git(args, cwd)

    monkeypatch.setattr(pm, "_run_git", fake_run_git)

    outcome, detail = pm._evaluate_delivered(pm_git_project, sha, {})

    assert outcome == "cannot_evaluate"
    assert detail == "git error: weird failure"


def test_reconcile_zero_delivered_entries_exits_0(pm_project: Path) -> None:
    result = run_pm("reconcile", cwd=pm_project)
    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "no delivered entries" in result.stdout


def test_reconcile_aggregate_mix_exits_0(pm_git_project: Path) -> None:
    base_branch = current_branch(pm_git_project)
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()

    # committed on a branch never merged back, so `checkout base_branch` below doesn't touch it
    _git(pm_git_project, "checkout", "-q", "-b", "feature")
    (pm_git_project / "feature.txt").write_text("feature work\n")
    _git(pm_git_project, "add", "feature.txt")
    _git(pm_git_project, "commit", "-q", "-m", "feature work")
    feature_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", base_branch)

    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    append_defer(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {feature_sha}", Probe="none",
    )
    append_defer(
        pm_git_project, 2,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {NONEXISTENT_SHA}", Probe="none",
    )

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "1 closed, 1 awaiting integration, 1 cannot evaluate" in result.stdout


def test_reconcile_missing_ledger_file_exits_3(project_dir: Path) -> None:
    result = run_pm("reconcile", cwd=project_dir)
    assert result.returncode == pm.EXIT_NOT_FOUND


def test_reconcile_missing_project_dir_exits_7(tmp_path: Path) -> None:
    result = run_pm("reconcile", "--project-dir", str(tmp_path / "nope"), cwd=tmp_path)
    assert result.returncode == pm.EXIT_PROJECT_DIR_NOT_FOUND


def test_reconcile_batch_rejects_integrated_without_close(pm_project: Path) -> None:
    result = run_pm("reconcile", "--integrated", "a" * 40, cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT


# --- fetch memoization: once per unique repo per run ------------------------


def test_fetch_memoized_once_per_repo_across_multiple_delivered_entries(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    append_bug(pm_git_project, 2, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    append_defer(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    fetch_calls: list[Path] = []
    real_run_git = pm._run_git

    def spy(args: list[str], cwd: Path):
        if args[:1] == ["fetch"]:
            fetch_calls.append(cwd)
        return real_run_git(args, cwd)

    monkeypatch.setattr(pm, "_run_git", spy)

    evals = pm._reconcile_read_pass(pm_git_project)

    assert len(fetch_calls) == 1
    assert len(evals) == 3
    assert all(ev.outcome == "promote" for ev in evals)


# --- write-back CAS: race between read pass and write-back -----------------


def test_write_back_skips_silently_on_cas_mismatch_race(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    evals = pm._reconcile_read_pass(pm_git_project)
    assert len(evals) == 1
    ev = evals[0]
    assert ev.outcome == "promote"

    # a racing `decide` lands between the read pass and this write-back
    decide_result = run_pm(
        "decide", "BUG-1", "--as", "wontfix", "--reason", "folded into the redesign", cwd=pm_git_project,
    )
    assert decide_result.returncode == pm.EXIT_OK, decide_result.stderr

    result, verify_outcome = pm._reconcile_write_back(pm_git_project, ev, verify=False)

    assert result == "skipped"
    assert verify_outcome is None
    text = bugs_text(pm_git_project)
    line = status_line(text, "## BUG-1:")
    assert "wontfix" in line
    assert "closed" not in line


def test_write_back_skips_silently_when_only_commit_hand_edited(pm_git_project: Path) -> None:
    # a hand-edit that changes only `commit:` at the same attempt/state is exactly the
    # staleness a Probe-based compare would miss — this is why the write-back CAS compares the
    # commit sha specifically, not the standard (id, attempt, state, probe) tuple every other
    # transition uses
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    evals = pm._reconcile_read_pass(pm_git_project)
    ev = evals[0]
    assert ev.outcome == "promote"

    _git(pm_git_project, "commit", "--allow-empty", "-q", "-m", "a second real commit")
    other_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    text = bugs_text(pm_git_project)
    edited = text.replace(sha, other_sha)
    assert edited != text
    (pm_git_project / "BUGS.md").write_text(edited)

    result, verify_outcome = pm._reconcile_write_back(pm_git_project, ev, verify=False)

    assert result == "skipped"
    assert verify_outcome is None
    line = status_line(bugs_text(pm_git_project), "## BUG-1:")
    assert other_sha in line
    assert "closed" not in line


def test_batch_reconcile_exits_0_and_reports_skip_on_cas_mismatch(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # regression: batch reconcile must exit 0 on a per-entry CAS mismatch, never 6
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    real_write_back = pm._reconcile_write_back

    def racing_write_back(project: Path, ev, verify: bool):
        result = run_pm(
            "decide", "BUG-1", "--as", "wontfix", "--reason", "folded into the redesign", cwd=project,
        )
        assert result.returncode == pm.EXIT_OK, result.stderr
        return real_write_back(project, ev, verify)

    monkeypatch.setattr(pm, "_reconcile_write_back", racing_write_back)

    args = _parse_args("reconcile", "--project-dir", str(pm_git_project))
    exit_code = pm.cmd_reconcile(args)

    assert exit_code == pm.EXIT_OK
    text = bugs_text(pm_git_project)
    assert "wontfix" in status_line(text, "## BUG-1:")


# --- --close: the human-ratified path ---------------------------------------


def test_close_records_human_supplied_sha_and_reason(pm_git_project: Path) -> None:
    worker_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "commit", "--allow-empty", "-q", "-m", "rewritten by rebase")
    rewritten_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {worker_sha}", Probe="none",
    )

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", rewritten_sha,
        "--reason", "landed via rebase, worker sha unreachable", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    line = status_line(text, "## BUG-1:")
    assert "- **Status**: closed" in line
    assert f"integrated: {rewritten_sha}" in line
    assert worker_sha not in line
    assert "reason: landed via rebase, worker sha unreachable" in line


def test_close_rejects_integrated_not_ancestor_of_integration_ref(pm_git_project: Path) -> None:
    base_branch = current_branch(pm_git_project)
    _git(pm_git_project, "checkout", "-q", "-b", "feature")
    (pm_git_project / "feature.txt").write_text("feature work\n")
    commit_all(pm_git_project, "feature work")
    feature_sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", base_branch)
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {feature_sha}", Probe="none",
    )
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", feature_sha,
        "--reason", "not actually merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert bugs_text(pm_git_project) == before


def test_close_rejects_integrated_sha_unknown_to_repo(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", NONEXISTENT_SHA,
        "--reason", "bogus", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert bugs_text(pm_git_project) == before


def test_close_rejects_abbreviated_sha(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha[:7],
        "--reason", "abbreviated", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert bugs_text(pm_git_project) == before


def test_close_rejects_bad_reason_free_text(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "bad — reason", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert bugs_text(pm_git_project) == before


def test_close_requires_delivered_state(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1)  # never started: state "open"

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "already merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_CAS_FAILURE, result.stdout


def test_close_cas_race_two_calls_exactly_one_succeeds_other_gets_exit6(pm_git_project: Path) -> None:
    # regression: --close is the *only* reconcile path that returns 6 on a CAS mismatch
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    results: list[subprocess.CompletedProcess] = []

    def runner() -> None:
        results.append(run_pm(
            "reconcile", "--close", "BUG-1", "--integrated", sha,
            "--reason", "verified merged upstream", cwd=pm_git_project,
        ))

    threads = [threading.Thread(target=runner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    codes = sorted(r.returncode for r in results)
    assert codes == [pm.EXIT_OK, pm.EXIT_CAS_FAILURE], [r.stdout + r.stderr for r in results]
    text = bugs_text(pm_git_project)
    assert status_line(text, "## BUG-1:").count("closed") == 1


# --- --verify: probe re-run in a temporary detached worktree ----------------


def test_verify_writes_pass_when_recheck_finds_nothing(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("clean now\n")
    commit_all(pm_git_project, "add clean marker file")
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="grep:PM_RECONCILE_MARKER -- marker.txt — baseline: 1 match (marker.txt) — spec#12345678",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: pass" in verify_line
    assert "integration_ref:" in verify_line
    assert "verify: pass" in result.stdout


def test_verify_writes_fail_when_recheck_still_matches_but_still_promotes(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("PM_RECONCILE_MARKER still here\n")
    commit_all(pm_git_project, "add marker file that still matches")
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="grep:PM_RECONCILE_MARKER -- marker.txt — baseline: 2 matches (marker.txt) — spec#12345678",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    # a failing re-run never un-promotes the entry
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: fail" in verify_line


def test_verify_removes_temporary_worktree_even_when_probe_rerun_raises(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="grep:NOTHING_ANYWHERE_XYZ -- README.md — baseline: 1 match (README.md) — spec#12345678",
    )

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated probe re-run failure")

    monkeypatch.setattr(pm, "run_probe", boom)

    args = _parse_args("reconcile", "--verify", "--project-dir", str(pm_git_project))
    exit_code = pm.cmd_reconcile(args)

    assert exit_code == pm.EXIT_OK
    worktree_list = _git(pm_git_project, "worktree", "list", "--porcelain").stdout
    assert worktree_list.count("worktree ") == 1  # only the main worktree remains
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line
