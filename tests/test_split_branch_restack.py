from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.split_branch_fixtures import build_fixture, commit, make_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "restack.sh"


def git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, text=True, capture_output=True
    ).stdout.strip()


def metadata(base_sha: str) -> str:
    return (
        "PR prose\n\n<!-- split-branch:stack -->\nparent: main\n"
        f"base-sha: {base_sha}\nposition: 2/3\n"
        "<!-- /split-branch:stack -->\n"
    )


def fake_forge(
    tmp_path: Path, body: str, provider: str = "gh", *, fail_view: bool = False,
    fail_update: bool = False,
) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    body_file = tmp_path / f"{provider}-body"
    body_file.write_text(body)
    log_file = tmp_path / f"{provider}-log"
    log_file.write_text("")
    executable = bin_dir / provider
    if provider == "gh":
        view, update = "pr view", "pr edit"
        view_output = 'cat "$FAKE_BODY"'
        update_flag = "--body-file"
    else:
        view, update = "mr view", "mr update"
        view_output = (
            "python3 -c 'import json,os; print(json.dumps({\"description\": "
            "open(os.environ[\"FAKE_BODY\"]).read()}))'"
        )
        update_flag = "--description"
    executable.write_text(
        "#!/bin/sh\nset -eu\n"
        ': "${FAKE_BODY:?}" "${FAKE_LOG:?}"\n'
        'printf \'%s\\n\' "$*" >>"$FAKE_LOG"\n'
        f"if [ \"$1 $2\" = '{view}' ]; then\n"
        + ("  exit 19\n" if fail_view else f"  {view_output}\n")
        + f"elif [ \"$1 $2\" = '{update}' ]; then\n"
        + ("  exit 23\n" if fail_update else
           "  shift 2\n  while [ $# -gt 0 ]; do\n"
           f"    if [ \"$1\" = '{update_flag}' ]; then "
           + ("cp \"$2\" \"$FAKE_BODY\"" if provider == "gh" else
              "printf '%s' \"$2\" >\"$FAKE_BODY\"")
           + "; exit 0; fi\n    shift\n  done\n  exit 9\n")
        + "else\n  exit 9\nfi\n"
    )
    executable.chmod(0o755)
    return bin_dir, body_file, log_file


def run_restack(
    repo: Path, bin_dir: Path, body_file: Path, log_file: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        FAKE_BODY=str(body_file),
        FAKE_LOG=str(log_file),
        GIT_CONFIG_NOSYSTEM="1",
    )
    return subprocess.run(
        [str(SCRIPT), *args], cwd=repo, env=env, text=True, capture_output=True
    )


def fixture_forge(tmp_path: Path, body: str, **kwargs):
    return fake_forge(tmp_path, body, **kwargs)


def assert_only_late(repo: Path) -> None:
    assert git(repo, "diff", "--name-only", "main..feature") == "late.txt"
    assert git(repo, "show", "feature:late.txt") == "late feature content"


def test_explicit_base_precedes_conflicting_valid_metadata(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    repo = fixture.path
    recorded = git(repo, "rev-parse", "feature~1")
    wrong_metadata_base = git(repo, "rev-list", "--max-parents=0", "feature")
    new_trunk = git(repo, "rev-parse", "main")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(wrong_metadata_base))

    result = run_restack(repo, bin_dir, body, log, "--branch", "feature", "--onto", "main", "--base-sha", recorded)

    assert result.returncode == 0, result.stderr
    assert_only_late(repo)
    assert f"base-sha: {new_trunk}" in body.read_text()
    assert "position: 2/3" in body.read_text()


def test_metadata_fallback_performs_real_rebase_and_update(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded = git(fixture.path, "rev-parse", "feature~1")
    trunk = git(fixture.path, "rev-parse", "main")
    before = git(fixture.path, "rev-parse", "feature")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(recorded))

    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main")

    assert result.returncode == 0, result.stderr
    assert_only_late(fixture.path)
    assert git(fixture.path, "rev-parse", "feature") != before
    assert git(fixture.path, "rev-parse", "feature^") == trunk
    assert f"base-sha: {trunk}" in body.read_text()
    assert "pr edit" in log.read_text()


@pytest.mark.parametrize("bad_body", ["ordinary body\n", metadata("a" * 40).replace("position: 2/3", "position: bad")])
def test_unavailable_metadata_is_exit_2_and_does_not_move_ref(tmp_path: Path, bad_body: str) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    before = git(fixture.path, "rev-parse", "feature")
    bin_dir, body, log = fixture_forge(tmp_path, bad_body)
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main")
    assert result.returncode == 2
    assert "--base-sha" in result.stderr
    assert git(fixture.path, "rev-parse", "feature") == before
    assert "pr edit" not in log.read_text()


def test_unresolved_explicit_base_is_exit_2(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    before = git(fixture.path, "rev-parse", "feature")
    valid = git(fixture.path, "rev-parse", "feature~1")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(valid))
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main", "--base-sha", "f" * 40)
    assert result.returncode == 2
    assert git(fixture.path, "rev-parse", "feature") == before


def test_body_fetch_failure_without_explicit_base_is_exit_2(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    bin_dir, body, log = fixture_forge(tmp_path, "", fail_view=True)
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main")
    assert result.returncode == 2
    assert "--base-sha" in result.stderr


@pytest.mark.parametrize("args", [
    ("--branch", "missing", "--onto", "main"),
    ("--branch", "feature", "--onto", "missing"),
])
def test_unresolved_child_or_trunk_is_exit_4(tmp_path: Path, args: tuple[str, ...]) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    bin_dir, body, log = fixture_forge(tmp_path, "")
    result = run_restack(fixture.path, bin_dir, body, log, *args)
    assert result.returncode == 4


@pytest.mark.parametrize("args", [
    (), ("--branch", "feature"), ("--onto", "main"),
    ("--wat",), ("--branch",),
])
def test_bad_arguments_are_exit_5(tmp_path: Path, args: tuple[str, ...]) -> None:
    repo = make_repo(tmp_path / "fixture")
    bin_dir, body, log = fixture_forge(tmp_path, "")
    result = run_restack(repo, bin_dir, body, log, *args)
    assert result.returncode == 5


def test_conflicting_rebase_is_aborted_and_leaves_child_unchanged(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "fixture")
    commit(repo, {"shared.txt": "before\n"}, "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "child")
    commit(repo, {"shared.txt": "child\n"}, "child")
    before = git(repo, "rev-parse", "child")
    git(repo, "checkout", "main")
    commit(repo, {"shared.txt": "trunk\n"}, "trunk")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(base))
    result = run_restack(repo, bin_dir, body, log, "--branch", "child", "--onto", "main", "--base-sha", base)
    assert result.returncode == 3
    assert "shared.txt" in result.stderr
    assert git(repo, "rev-parse", "child") == before
    git_dir = Path(git(repo, "rev-parse", "--absolute-git-dir"))
    assert not (git_dir / "rebase-merge").exists()
    assert not (git_dir / "rebase-apply").exists()
    assert "pr edit" not in log.read_text()


def test_non_conflict_rebase_failure_is_operational_exit_6(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded = git(fixture.path, "rev-parse", "feature~1")
    before = git(fixture.path, "rev-parse", "feature")
    (fixture.path / "late.txt").write_text("dirty\n")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(recorded))
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main", "--base-sha", recorded)
    assert result.returncode == 6
    assert "without a content conflict" in result.stderr
    assert git(fixture.path, "rev-parse", "feature") == before


@pytest.mark.parametrize("provider", ["gh", "glab"])
def test_update_failure_rolls_back_child_and_returns_6(tmp_path: Path, provider: str) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded = git(fixture.path, "rev-parse", "feature~1")
    before = git(fixture.path, "rev-parse", "feature")
    args = ["--branch", "feature", "--onto", "main", "--base-sha", recorded]
    if provider == "glab":
        git(fixture.path, "remote", "add", "origin", "git@forge.example:group/project.git")
        git(fixture.path, "config", "remote.origin.splitBranchForge", "gitlab")
    bin_dir, body, log = fixture_forge(
        tmp_path, metadata(recorded), provider=provider, fail_update=True
    )
    result = run_restack(fixture.path, bin_dir, body, log, *args)
    assert result.returncode == 6
    assert "restored" in result.stderr
    assert git(fixture.path, "rev-parse", "feature") == before
    git_dir = Path(git(fixture.path, "rev-parse", "--absolute-git-dir"))
    assert not (git_dir / "rebase-merge").exists()
    assert not (git_dir / "rebase-apply").exists()


def test_explicit_base_does_not_fabricate_missing_metadata(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded = git(fixture.path, "rev-parse", "feature~1")
    before = git(fixture.path, "rev-parse", "feature")
    bin_dir, body, log = fixture_forge(tmp_path, "ordinary body\n")
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main", "--base-sha", recorded)
    assert result.returncode == 6
    assert git(fixture.path, "rev-parse", "feature") == before
    assert "split-branch:stack" not in body.read_text()


@pytest.mark.parametrize("url,configured,slug", [
    ("https://GITLAB.example/group/project.git", False, "group/project"),
    ("git@code.example:group/sub/project.git", True, "group/sub/project"),
])
def test_gitlab_fetch_update_repo_selection(
    tmp_path: Path, url: str, configured: bool, slug: str
) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    recorded = git(fixture.path, "rev-parse", "feature~1")
    git(fixture.path, "remote", "add", "upstream", url)
    if configured:
        git(fixture.path, "config", "remote.upstream.splitBranchForge", "gitlab")
    bin_dir, body, log = fixture_forge(tmp_path, metadata(recorded), provider="glab")
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main", "--remote", "upstream")
    assert result.returncode == 0, result.stderr
    assert_only_late(fixture.path)
    calls = log.read_text()
    assert f"mr view feature --repo {slug} --output json" in calls
    assert f"mr update feature --repo {slug} --description" in calls
    assert f"base-sha: {git(fixture.path, 'rev-parse', 'main')}" in body.read_text()


def test_gitlab_fetch_failure_propagates_as_exit_2(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture", "squash_merged_base")
    git(fixture.path, "remote", "add", "origin", "git@gitlab.example:group/project.git")
    bin_dir, body, log = fixture_forge(tmp_path, "", provider="glab", fail_view=True)
    result = run_restack(fixture.path, bin_dir, body, log, "--branch", "feature", "--onto", "main")
    assert result.returncode == 2
    assert "mr view" in log.read_text()
