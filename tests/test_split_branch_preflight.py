from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.split_branch_fixtures import build_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "preflight.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def run(repo: Path, *args: str, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if path_prefix is not None:
        env = dict(os.environ)
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [str(PREFLIGHT), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
    )


def fake_date(tmp_path: Path, stamp: str) -> Path:
    """A directory holding a `date` shim that always prints `stamp`."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    shim = bindir / "date"
    shim.write_text(f"#!/bin/sh\necho {stamp}\n")
    shim.chmod(0o755)
    return bindir


def clean_feature_repo(tmp_path: Path):
    """A fixture repo with the feature branch checked out and a clean work tree."""
    fixture = build_fixture(tmp_path, "simple")
    git(fixture.path, "checkout", fixture.branch)
    assert git(fixture.path, "status", "--porcelain") == ""
    return fixture


def test_creates_backup_ref_pointing_at_branch_tip(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    result = run(fixture.path, "--base", "main")
    assert result.returncode == 0, result.stderr
    backup_ref = result.stdout.strip()

    # The one load-bearing property: the backup is restorable to the exact tip.
    assert backup_ref.startswith(f"backup/{fixture.branch}_")
    backup_sha = git(fixture.path, "rev-parse", f"refs/heads/{backup_ref}")
    tip_sha = git(fixture.path, "rev-parse", f"{fixture.branch}^{{commit}}")
    assert backup_sha == tip_sha

    # Stdout carries only the ref name; nothing leaks onto it.
    assert result.stdout.strip() == backup_ref
    # A backup ref is the only change — the work tree is untouched.
    assert git(fixture.path, "status", "--porcelain") == ""


def test_backup_survives_a_rewrite_of_the_branch(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    original_tip = git(fixture.path, "rev-parse", "HEAD")
    backup_ref = run(fixture.path, "--base", "main").stdout.strip()

    # Simulate a split going wrong: hard-reset the branch back to base.
    git(fixture.path, "reset", "--hard", "main")
    assert git(fixture.path, "rev-parse", "HEAD") != original_tip

    # The documented recovery restores the exact pre-split tip.
    git(fixture.path, "reset", "--hard", backup_ref)
    assert git(fixture.path, "rev-parse", "HEAD") == original_tip


def test_dirty_work_tree_is_rejected_without_creating_a_backup(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    tracked = next(p for p in fixture.path.iterdir() if p.is_file() and p.suffix)
    tracked.write_text(tracked.read_text() + "\ndirty\n")

    result = run(fixture.path, "--base", "main")
    assert result.returncode == 2
    assert git(fixture.path, "branch", "--list", "backup/*") == ""


def test_staged_changes_are_rejected(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    tracked = next(p for p in fixture.path.iterdir() if p.is_file() and p.suffix)
    tracked.write_text(tracked.read_text() + "\nstaged\n")
    git(fixture.path, "add", "-A")

    result = run(fixture.path, "--base", "main")
    assert result.returncode == 2


def test_untracked_files_do_not_block(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    (fixture.path / "prompt.md").write_text("scratch\n")

    result = run(fixture.path, "--base", "main")
    assert result.returncode == 0, result.stderr


def test_on_base_branch_is_rejected(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    git(fixture.path, "checkout", "main")
    result = run(fixture.path, "--base", "main")
    assert result.returncode == 3


def test_detached_head_is_rejected(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    git(fixture.path, "checkout", "--detach")
    result = run(fixture.path, "--base", "main")
    assert result.returncode == 3


def test_unresolvable_base_errors(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    result = run(fixture.path, "--base", "does-not-exist")
    assert result.returncode == 4


def test_missing_base_argument_is_bad_arguments(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    result = run(fixture.path)
    assert result.returncode == 5


def test_explicit_branch_backs_up_the_named_branch(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    git(fixture.path, "checkout", "main")  # stand somewhere else
    result = run(fixture.path, "--base", "main", "--branch", fixture.branch)
    assert result.returncode == 0, result.stderr
    backup_ref = result.stdout.strip()
    backup_sha = git(fixture.path, "rev-parse", f"refs/heads/{backup_ref}")
    assert backup_sha == git(fixture.path, "rev-parse", f"{fixture.branch}^{{commit}}")


def test_unknown_argument_is_bad_arguments(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    result = run(fixture.path, "--base", "main", "--frobnicate")
    assert result.returncode == 5


def test_detached_head_with_explicit_branch_is_still_rejected(tmp_path: Path) -> None:
    # A detached HEAD has no branch to protect; --branch must not bypass that.
    fixture = clean_feature_repo(tmp_path)
    git(fixture.path, "checkout", "--detach")
    result = run(fixture.path, "--base", "main", "--branch", fixture.branch)
    assert result.returncode == 3
    assert git(fixture.path, "branch", "--list", "backup/*") == ""


def test_base_as_remote_tracking_ref_counts_as_the_base(tmp_path: Path) -> None:
    # On local main, `--base origin/main` still means "on the base" and must be refused.
    fixture = clean_feature_repo(tmp_path)
    git(fixture.path, "checkout", "main")
    main_sha = git(fixture.path, "rev-parse", "main")
    git(fixture.path, "update-ref", "refs/remotes/origin/main", main_sha)
    result = run(fixture.path, "--base", "origin/main")
    assert result.returncode == 3


def test_base_as_fully_qualified_ref_counts_as_the_base(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    result = run(fixture.path, "--base", "main", "--branch", "refs/heads/main")
    assert result.returncode == 3


def test_same_second_reruns_create_distinct_restorable_backups(tmp_path: Path) -> None:
    fixture = clean_feature_repo(tmp_path)
    bindir = fake_date(tmp_path, "20990101T000000Z")
    tip = git(fixture.path, "rev-parse", f"{fixture.branch}^{{commit}}")

    first = run(fixture.path, "--base", "main", path_prefix=bindir)
    second = run(fixture.path, "--base", "main", path_prefix=bindir)
    assert first.returncode == 0 and second.returncode == 0, (first.stderr, second.stderr)

    ref_a, ref_b = first.stdout.strip(), second.stdout.strip()
    assert ref_a != ref_b, "same-second rerun must not reuse or clobber the first backup"
    assert git(fixture.path, "rev-parse", ref_a) == tip
    assert git(fixture.path, "rev-parse", ref_b) == tip


def test_shadowing_tag_does_not_make_restore_ambiguous(tmp_path: Path) -> None:
    # A tag sharing the generated name would win Git's DWIM resolution, so a
    # `git reset --hard <printed>` would restore the tag's commit, not the tip.
    fixture = clean_feature_repo(tmp_path)
    bindir = fake_date(tmp_path, "20990101T000000Z")
    tip = git(fixture.path, "rev-parse", f"{fixture.branch}^{{commit}}")
    collision = f"backup/{fixture.branch}_20990101T000000Z"
    git(fixture.path, "tag", collision, "main")  # tag at base, a different commit

    result = run(fixture.path, "--base", "main", path_prefix=bindir)
    assert result.returncode == 0, result.stderr
    printed = result.stdout.strip()

    # Whatever name is printed, it must resolve — via DWIM — to the tip.
    assert git(fixture.path, "rev-parse", printed) == tip
    git(fixture.path, "reset", "--hard", printed)
    assert git(fixture.path, "rev-parse", "HEAD") == tip


def test_not_a_git_repo_errors(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = subprocess.run(
        [str(PREFLIGHT), "--base", "main"],
        cwd=str(plain),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
