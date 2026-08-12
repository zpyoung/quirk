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


def test_resolve_integration_ref_returns_none_when_detached_with_no_origin_head(
    pm_git_project: Path,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", "--detach", sha)
    assert pm._resolve_integration_ref(pm_git_project) is None


def test_resolve_integration_ref_env_override_wins_even_when_detached(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", "--detach", sha)
    monkeypatch.setenv("QUIRK_PM_INTEGRATION_REF", "explicit-ref")
    assert pm._resolve_integration_ref(pm_git_project) == "explicit-ref"


def test_reconcile_reports_cannot_evaluate_on_a_detached_checkout_with_no_origin_head(
    pm_git_project: Path,
) -> None:
    # regression: on a detached checkout, `git rev-parse --abbrev-ref HEAD` returns the literal
    # string "HEAD", which resolves as a commit and would let merge-base --is-ancestor succeed
    # against whatever happens to be checked out — a wrong close is worse than an unresolved one
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    _git(pm_git_project, "checkout", "-q", "--detach", sha)
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "cannot evaluate" in result.stdout
    text = bugs_text(pm_git_project)
    line = status_line(text, "## BUG-1:")
    assert line.startswith("- **Status**: delivered")
    assert "closed" not in line


def test_close_refuses_when_the_repo_is_detached_with_no_resolvable_integration_ref(
    pm_git_project: Path,
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    _git(pm_git_project, "checkout", "-q", "--detach", sha)
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "already merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert bugs_text(pm_git_project) == before


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


def test_reconcile_reports_a_ledger_too_large_to_read_instead_of_a_false_all_clear(
    pm_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a ledger reconcile couldn't read is could-not-look, not looked-and-found-nothing — it must
    # never be reported the same way as a genuinely empty backlog
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "10")

    result = run_pm("reconcile", cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "no delivered entries to evaluate" not in result.stdout
    assert "BUGS.md: exceeds 10 bytes, skipping" in result.stdout
    assert "could not be read" in result.stdout


def test_reconcile_reports_a_too_large_ledger_alongside_entries_it_did_evaluate(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a skip on one ledger must not be swallowed just because other ledgers had real work to
    # report — the summary line must not read as a clean, fully-evaluated run
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")
    bugs_size = (pm_git_project / "BUGS.md").stat().st_size

    deferred = pm_git_project / "DEFERRED.md"
    deferred.write_text(deferred.read_text() + "x" * (bugs_size + 100_000))
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(bugs_size + 1000))

    result = run_pm("reconcile", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert "1 closed" in result.stdout
    assert "DEFERRED.md" in result.stdout
    assert "could not be read" in result.stdout


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


# --- batch reconcile: ledger schema guard -----------------------------------


def test_reconcile_batch_refuses_v1_ledger_with_exit8(pm_project: Path) -> None:
    # an unmigrated ledger must refuse, not silently report "no delivered entries" — the same
    # false all-clear `reconcile --close` already avoids via `_prepare_transition`
    append_bug(pm_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {'a' * 40}", Probe="none")
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 1"))
    before = bugs.read_bytes()

    result = run_pm("reconcile", cwd=pm_project)

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH, result.stdout
    assert "no delivered entries" not in result.stdout
    assert bugs.read_bytes() == before


def test_reconcile_batch_refuses_too_new_ledger_with_exit8(pm_project: Path) -> None:
    append_bug(pm_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {'a' * 40}", Probe="none")
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 3"))
    before = bugs.read_bytes()

    result = run_pm("reconcile", cwd=pm_project)

    assert result.returncode == pm.EXIT_SCHEMA_MISMATCH, result.stdout
    assert bugs.read_bytes() == before


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

    evals, _parse_error_lines = pm._reconcile_read_pass(pm_git_project)

    assert len(fetch_calls) == 1
    assert len(evals) == 3
    assert all(ev.outcome == "promote" for ev in evals)


# --- write-back CAS: race between read pass and write-back -----------------


def test_write_back_skips_silently_on_cas_mismatch_race(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    evals, _parse_error_lines = pm._reconcile_read_pass(pm_git_project)
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

    evals, _parse_error_lines = pm._reconcile_read_pass(pm_git_project)
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


def test_close_refuses_on_a_malformed_probe_field(pm_git_project: Path) -> None:
    # --close never reads Probe itself, but the same reasoning as park/decide's malformed-field
    # refusal applies here too: a corrupt sibling field on an entry being declared terminal
    # deserves a diagnostic, not silence
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="not a valid probe at all",
    )
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "already merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert "malformed Probe field" in result.stderr
    assert bugs_text(pm_git_project) == before


def test_close_refuses_exit4_when_malformed_sibling_field_and_state_mismatch_both_hold(
    pm_git_project: Path,
) -> None:
    """4-before-6: an entry both outside --close's allowed states (never started -> open) and
    carrying a malformed Probe must report corrupt-entry, not CAS failure — a fixture where only
    one condition holds can't tell an inverted precedence from an unrelated exit code.
    """
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Probe="not a valid probe at all")  # never started: state "open"
    before = bugs_text(pm_git_project)

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "already merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert bugs_text(pm_git_project) == before


def test_close_refuses_on_a_duplicated_probe_field(pm_git_project: Path) -> None:
    # a second Probe line is invisible to entry.fields (last one wins the dict-collapse) and
    # parses cleanly on its own, so this is a distinct defect from the malformed-field case above
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="none",
    )
    bugs = pm_git_project / "BUGS.md"
    text = bugs.read_text()
    marker = "- **Probe**: none"
    idx = text.index(marker) + len(marker)
    extra_probe = "\n- **Probe**: grep:TODO — baseline: 1 match — spec#12345678"
    bugs.write_text(text[:idx] + extra_probe + text[idx:])
    before = bugs.read_bytes()

    result = run_pm(
        "reconcile", "--close", "BUG-1", "--integrated", sha,
        "--reason", "already merged", cwd=pm_git_project,
    )

    assert result.returncode == pm.EXIT_CORRUPT_ENTRY, result.stdout
    assert "duplicated Probe field" in result.stderr
    assert bugs.read_bytes() == before


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


# --- --verify: an unusable Probe field still records a Verify field ---------


def test_verify_writes_probe_error_when_entry_has_no_probe_field(pm_git_project: Path) -> None:
    # absent Probe = the recorded probe cannot be reconstructed at all, but ancestry alone still
    # promotes; `--verify` was requested, so silently writing no `Verify` field would read as
    # "never verified" rather than "verification was attempted and couldn't run"
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}")

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line
    assert "verify: error" in result.stdout


def test_verify_writes_probe_error_when_probe_field_does_not_reconstruct(pm_git_project: Path) -> None:
    # `grep:` with an empty pattern parses into a well-formed ProbeField (verb/baseline/hashes all
    # match) but `_reconstruct_probe_spec` rejects the empty arg — a different failure mode than
    # an absent or MalformedField Probe, and one the original code didn't guard at all
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="grep: — baseline: 0 matches — spec#12345678",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line


def test_verify_writes_probe_error_for_a_genuinely_malformed_probe_field(pm_git_project: Path) -> None:
    # a third failure mode, distinct from the two above: `Probe` is present but fails
    # `parse_probe` outright (unrecognized verb) rather than being absent or unreconstructable.
    # `_reconcile_read_pass` must filter the resulting MalformedField the same way it filters an
    # absent field — never pass it to `_reconstruct_probe_spec`/`run_probe` as if it had parsed
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="not a valid probe at all",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line


# --- --verify: grep must not treat deleted baseline files as a fix ---------


def test_verify_reports_fail_when_grep_baseline_files_were_deleted_not_fixed(pm_git_project: Path) -> None:
    (pm_git_project / "marker.txt").write_text("PM_DELETED_MARKER still broken\n")
    commit_all(pm_git_project, "add marker file with the symptom")

    # "fixed" by deleting the file outright rather than removing the matched text — the same
    # hazard `grep_baseline_files_missing` exists to catch on the `finish` path
    (pm_git_project / "marker.txt").unlink()
    commit_all(pm_git_project, "delete marker file instead of fixing it")
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe="grep:PM_DELETED_MARKER — baseline: 1 match (marker.txt) — spec#12345678",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    # reachability alone still promotes — a failing re-run never un-promotes the entry
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: fail" in verify_line
    assert "verify: fail" in result.stdout


# --- --verify: absolute grep paths must resolve inside the verify worktree -


def test_verify_rebases_absolute_grep_path_onto_the_verify_worktree(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    readme = pm_git_project / "README.md"
    assert "ABS_PATH_MARKER" not in readme.read_text()

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe=f"grep:ABS_PATH_MARKER -- {readme} — baseline: 0 matches (README.md) — spec#12345678",
    )

    # dirty the *original* checkout only, never committed — the integration ref (and the detached
    # verify worktree checked out from it) never sees this text
    readme.write_text(readme.read_text() + "ABS_PATH_MARKER still here\n")

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    # the committed integration-ref content has zero matches; a verify that (incorrectly) read
    # the dirtied original checkout instead would see one and report `fail`
    assert "probe: pass" in verify_line


def test_verify_reports_error_for_absolute_grep_path_outside_the_repo(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    outside_path = pm_git_project.parent / "outside-the-repo.txt"
    outside_path.write_text("OUTSIDE_MARKER present\n")

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe=(
            f"grep:OUTSIDE_MARKER -- {outside_path} — "
            f"baseline: 1 match ({outside_path}) — spec#12345678"
        ),
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    # reachability alone still promotes even though the probe can't be verified at all
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line


# --- --verify: absolute test: nodeids must resolve inside the verify worktree -


def test_verify_rebases_absolute_test_nodeid_onto_the_verify_worktree(pm_git_project: Path) -> None:
    test_file = pm_git_project / "test_probe_target.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    commit_all(pm_git_project, "add passing probe target test")
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe=f"test:{test_file}::test_ok — baseline: fail — spec#12345678",
    )

    # dirty the *original* checkout only, never committed — a verify that (incorrectly) re-ran
    # the recorded absolute nodeid against this checkout instead of the detached integration-ref
    # worktree would see the failing version and report `fail`
    test_file.write_text("def test_ok():\n    assert False\n")

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: pass" in verify_line


def test_verify_reports_error_for_absolute_test_nodeid_outside_the_repo(pm_git_project: Path) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    outside_path = pm_git_project.parent / "outside-the-repo.py"
    outside_path.write_text("def test_ok():\n    assert True\n")

    append_bug(
        pm_git_project, 1,
        Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}",
        Probe=f"test:{outside_path}::test_ok — baseline: fail — spec#12345678",
    )

    result = run_pm("reconcile", "--verify", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    text = bugs_text(pm_git_project)
    # reachability alone still promotes even though the probe can't be verified at all
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: error" in verify_line


# --- --verify: temporary worktree cleanup never blocks the promotion -------


def test_verify_worktree_cleanup_failure_is_diagnosed_but_does_not_block_promotion(
    pm_git_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    sha = _git(pm_git_project, "rev-parse", "HEAD").stdout.strip()
    append_bug(pm_git_project, 1, Status=f"delivered — 2026-08-05 — attempt 1 — commit: {sha}", Probe="none")

    real_run_git = pm._run_git
    prune_calls: list[list[str]] = []

    def fake_run_git(args: list[str], cwd: Path):
        if args[:2] == ["worktree", "remove"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="simulated remove failure\n")
        if args[:2] == ["worktree", "prune"]:
            # a no-op stand-in for a prune that also fails to clear the stale registration —
            # otherwise a real prune would clean it up and the diagnostic would never fire
            prune_calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return real_run_git(args, cwd)

    monkeypatch.setattr(pm, "_run_git", fake_run_git)

    args = _parse_args("reconcile", "--verify", "--project-dir", str(pm_git_project))
    exit_code = pm.cmd_reconcile(args)

    assert exit_code == pm.EXIT_OK
    assert len(prune_calls) == 1  # bounded: exactly one follow-up, never a retry loop
    text = bugs_text(pm_git_project)
    assert "- **Status**: closed" in status_line(text, "## BUG-1:")
    verify_line = field_line(text, "## BUG-1:", "Verify")
    assert "probe: pass" in verify_line
    stderr = capsys.readouterr().err
    assert "verify worktree" in stderr
