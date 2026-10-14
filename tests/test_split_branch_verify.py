from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests.split_branch_fixtures import build_fixture

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "verify.sh"


def worktree_count(repo: Path) -> int:
    output = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sum(line.startswith("worktree ") for line in output.splitlines())


def run_verify(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def verdict(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.stdout.count("\n") == 1, result.stdout
    return json.loads(result.stdout)


def test_success_uses_isolated_worktree_and_removes_default_temp_root(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    capture = tmp_path / "command-cwd"
    temp_parent = tmp_path / "temporary-roots"
    temp_parent.mkdir()
    env = os.environ.copy()
    env.update({"TMPDIR": str(temp_parent), "VERIFY_CAPTURE": str(capture)})
    before = worktree_count(fixture.path)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        'pwd > "$VERIFY_CAPTURE"; echo build-output',
        "--test-cmd",
        "touch isolated-artifact; echo test-output",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert verdict(result) == {
        "branch": fixture.branch,
        "build": 0,
        "test": 0,
        "ok": True,
    }
    assert "build-output" in result.stderr
    assert "test-output" in result.stderr
    command_cwd = Path(capture.read_text().strip())
    assert command_cwd != fixture.path
    assert not command_cwd.exists()
    assert not (fixture.path / "isolated-artifact").exists()
    assert list(temp_parent.iterdir()) == []
    assert worktree_count(fixture.path) == before


def test_build_failure_reports_status_and_cleans_worktree(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    root = tmp_path / "verification"
    before = worktree_count(fixture.path)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "echo failed-build; exit 17",
        "--worktree-root",
        str(root),
    )

    assert result.returncode == 1
    data = verdict(result)
    assert data["build"] == 17
    assert data["ok"] is False
    assert "failed-build" in result.stderr
    assert not (root / fixture.branch).exists()
    assert worktree_count(fixture.path) == before


def test_test_failure_exits_two_and_cleans_worktree(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    root = tmp_path / "verification"
    before = worktree_count(fixture.path)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "true",
        "--test-cmd",
        "exit 23",
        "--worktree-root",
        str(root),
    )

    assert result.returncode == 2
    assert verdict(result) == {
        "branch": fixture.branch,
        "build": 0,
        "test": 23,
        "ok": False,
    }
    assert not (root / fixture.branch).exists()
    assert worktree_count(fixture.path) == before


def test_locked_worktree_is_unlocked_and_removed(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    root = tmp_path / "verification"
    before = worktree_count(fixture.path)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "git worktree lock .",
        "--worktree-root",
        str(root),
    )

    assert result.returncode == 0, result.stderr
    assert verdict(result)["ok"] is True
    assert not (root / fixture.branch).exists()
    assert worktree_count(fixture.path) == before


def test_keep_on_failure_retains_worktree_and_reports_path(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    root = tmp_path / "verification"
    kept_path = root / fixture.branch
    before = worktree_count(fixture.path)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "false",
        "--worktree-root",
        str(root),
        "--keep-on-failure",
    )

    assert result.returncode == 1
    assert kept_path.is_dir()
    assert str(kept_path) in result.stderr
    assert worktree_count(fixture.path) == before + 1

    subprocess.run(
        ["git", "worktree", "remove", "--force", str(kept_path)],
        cwd=fixture.path,
        check=True,
    )
    assert worktree_count(fixture.path) == before


def test_ref_is_sanitised_for_worktree_path(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    subprocess.run(
        ["git", "branch", "slice/one", fixture.head], cwd=fixture.path, check=True
    )
    root = tmp_path / "verification"

    result = run_verify(
        fixture.path,
        "--branch",
        "slice/one",
        "--build-cmd",
        "test \"$PWD\" = \"$EXPECTED_PATH\"",
        "--worktree-root",
        str(root),
        env={**os.environ, "EXPECTED_PATH": str(root / "slice-one")},
    )

    assert result.returncode == 0, result.stderr
    assert not (root / "slice-one").exists()


def test_bad_arguments_and_worktree_creation_failure_have_documented_codes(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    before = worktree_count(fixture.path)
    bad_args = run_verify(fixture.path, "--branch", fixture.branch)
    assert bad_args.returncode == 5
    assert bad_args.stdout == ""

    root = tmp_path / "verification"
    occupied = root / fixture.branch
    occupied.mkdir(parents=True)
    (occupied / "blocker").write_text("not an empty directory\n")
    creation_failure = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "true",
        "--worktree-root",
        str(root),
    )
    assert creation_failure.returncode == 4
    assert creation_failure.stdout == ""
    assert worktree_count(fixture.path) == before


def test_root_canonicalization_failure_exits_four(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    root = tmp_path / "changed-to-file"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_mkdir = bin_dir / "mkdir"
    fake_mkdir.write_text(
        "#!/usr/bin/env bash\n"
        'command /bin/mkdir "$@" || exit $?\n'
        'command /bin/rmdir "${@: -1}" || exit $?\n'
        'printf blocker > "${@: -1}"\n'
    )
    fake_mkdir.chmod(0o755)

    result = run_verify(
        fixture.path,
        "--branch",
        fixture.branch,
        "--build-cmd",
        "true",
        "--worktree-root",
        str(root),
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    assert result.returncode == 4
    assert result.stdout == ""
    assert "could not canonicalize worktree root" in result.stderr
