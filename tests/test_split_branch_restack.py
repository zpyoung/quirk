from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.split_branch_fixtures import build_fixture, commit, make_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "restack.sh"


def git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, text=True, capture_output=True
    ).stdout.strip()


def metadata(base_sha: str) -> str:
    return (
        "PR prose\n\n"
        "<!-- split-branch:stack -->\n"
        "parent: main\n"
        f"base-sha: {base_sha}\n"
        "position: 2/3\n"
        "<!-- /split-branch:stack -->\n"
    )


def fake_gh(tmp_path: Path, body: str) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    body_file = tmp_path / "pr-body"
    body_file.write_text(body)
    log_file = tmp_path / "gh-log"
    log_file.write_text("")
    executable = bin_dir / "gh"
    executable.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        ': "${FAKE_GH_BODY:?}" "${FAKE_GH_LOG:?}"\n'
        "printf '%s\\n' \"$*\" >>\"$FAKE_GH_LOG\"\n"
        "if [ \"$1 $2\" = 'pr view' ]; then\n"
        "  cat \"$FAKE_GH_BODY\"\n"
        "elif [ \"$1 $2\" = 'pr edit' ]; then\n"
        "  shift 2\n"
        "  while [ $# -gt 0 ]; do\n"
        "    if [ \"$1\" = '--body-file' ]; then cp \"$2\" \"$FAKE_GH_BODY\"; exit 0; fi\n"
        "    shift\n"
        "  done\n"
        "  exit 9\n"
        "else\n"
        "  exit 9\n"
        "fi\n"
    )
    executable.chmod(0o755)
    return bin_dir, body_file


def run_restack(
    repo: Path, bin_dir: Path, body_file: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        FAKE_GH_BODY=str(body_file),
        FAKE_GH_LOG=str(body_file.parent / "gh-log"),
        GIT_CONFIG_NOSYSTEM="1",
    )
    return subprocess.run(
        [str(SCRIPT), *args], cwd=repo, env=env, text=True, capture_output=True
    )


def test_restack_after_squash_keeps_only_unmerged_change_and_updates_metadata(
    tmp_path: Path,
) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    repo = fixture.path
    # The child was created on the tip of the lower (early-content) slice.
    recorded_base = git(repo, "rev-parse", f"{fixture.branch}~1")
    new_trunk_sha = git(repo, "rev-parse", "main")
    bin_dir, body_file = fake_gh(tmp_path, metadata(recorded_base))

    result = run_restack(
        repo,
        bin_dir,
        body_file,
        "--branch",
        fixture.branch,
        "--onto",
        "main",
        "--base-sha",
        recorded_base,
    )

    assert result.returncode == 0, result.stderr
    assert git(repo, "diff", "--name-only", "main..feature") == "late.txt"
    assert git(repo, "show", "feature:late.txt") == "late feature content"
    assert "early.txt" not in git(repo, "diff", "--name-only", "main..feature")
    updated = body_file.read_text()
    assert f"base-sha: {new_trunk_sha}" in updated
    assert "position: 2/3" in updated
    assert updated.count("<!-- split-branch:stack -->") == 1


def test_missing_metadata_requires_explicit_base_without_moving_ref(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    before = git(fixture.path, "rev-parse", fixture.branch)
    bin_dir, body_file = fake_gh(tmp_path, "ordinary PR body\n")

    result = run_restack(
        fixture.path,
        bin_dir,
        body_file,
        "--branch",
        fixture.branch,
        "--onto",
        "main",
    )

    assert result.returncode == 2
    assert "--base-sha" in result.stderr
    assert git(fixture.path, "rev-parse", fixture.branch) == before
    assert "pr edit" not in (tmp_path / "gh-log").read_text()


def test_malformed_metadata_requires_explicit_base_without_moving_ref(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    before = git(fixture.path, "rev-parse", fixture.branch)
    malformed = metadata("a" * 40).replace("position: 2/3\n", "position: bad\n")
    bin_dir, body_file = fake_gh(tmp_path, malformed)

    result = run_restack(
        fixture.path,
        bin_dir,
        body_file,
        "--branch",
        fixture.branch,
        "--onto",
        "main",
    )

    assert result.returncode == 2
    assert "--base-sha" in result.stderr
    assert git(fixture.path, "rev-parse", fixture.branch) == before


def test_metadata_base_is_used_when_explicit_base_is_omitted_in_dry_run(
    tmp_path: Path,
) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded_base = git(fixture.path, "rev-parse", f"{fixture.branch}~1")
    before = git(fixture.path, "rev-parse", fixture.branch)
    bin_dir, body_file = fake_gh(tmp_path, metadata(recorded_base))

    result = run_restack(
        fixture.path,
        bin_dir,
        body_file,
        "--branch",
        fixture.branch,
        "--onto",
        "main",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"git rebase --onto main {recorded_base} feature"
    assert git(fixture.path, "rev-parse", fixture.branch) == before


def test_conflicting_rebase_is_aborted_and_leaves_child_unchanged(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "fixture")
    commit(repo, {"shared.txt": "before\n"}, "shared base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "child")
    commit(repo, {"shared.txt": "from child\n"}, "child edit")
    child_before = git(repo, "rev-parse", "child")
    git(repo, "checkout", "main")
    commit(repo, {"shared.txt": "from trunk\n"}, "trunk edit")
    bin_dir, body_file = fake_gh(tmp_path, metadata(base))

    result = run_restack(
        repo,
        bin_dir,
        body_file,
        "--branch",
        "child",
        "--onto",
        "main",
        "--base-sha",
        base,
    )

    assert result.returncode == 3
    assert "shared.txt" in result.stderr
    assert git(repo, "rev-parse", "child") == child_before
    git_dir = Path(git(repo, "rev-parse", "--git-dir"))
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    assert not (git_dir / "rebase-merge").exists()
    assert not (git_dir / "rebase-apply").exists()
    assert "pr edit" not in (tmp_path / "gh-log").read_text()
