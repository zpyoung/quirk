from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS_DIR / "sdd-wave"


def run_wave(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "SDD Test")
    git(repo, "config", "user.email", "sdd@example.test")
    (repo / "allowed.txt").write_text("base\n")
    (repo / "protected.txt").write_text("base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo, git(repo, "rev-parse", "HEAD")


def test_create_adds_parent_safe_worktree_and_runs_baseline(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    worktrees = tmp_path / "worktrees"

    result = run_wave(
        "create",
        "--repo", str(repo),
        "--run-slug", "run-17",
        "--task-id", "T1",
        "--base", base,
        "--worktree-dir", str(worktrees),
        "--baseline-cmd", "test -f allowed.txt",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    worktree = Path(payload["worktree"])
    assert payload["status"] == "pass"
    assert payload["branch"] == "sdd/run-17/T1"
    assert worktree.parent == worktrees
    assert worktree.is_dir()
    assert git(worktree, "branch", "--show-current") == "sdd/run-17/T1"


def test_create_reports_baseline_failure(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)

    result = run_wave(
        "create",
        "--repo", str(repo),
        "--run-slug", "baseline",
        "--task-id", "T2",
        "--base", base,
        "--worktree-dir", str(tmp_path / "worktrees"),
        "--baseline-cmd", "printf baseline-error >&2; exit 9",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert payload["stage"] == "baseline"
    assert payload["exit_code"] == 9
    assert "baseline-error" in payload["stderr"]
    assert Path(payload["worktree"]).exists()


def test_merge_lane_never_touch_wins_and_preserves_branch(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    git(repo, "switch", "-c", "sdd/audit/T3")
    (repo / "protected.txt").write_text("changed\n")
    git(repo, "add", "protected.txt")
    git(repo, "commit", "-m", "touch protected")
    git(repo, "switch", "main")
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps({
        "files": ["protected.txt"],
        "never_touch": ["protected.txt"],
    }))
    retained = tmp_path / "retained-worktree"
    retained.mkdir()

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", "sdd/audit/T3",
        "--worktree", str(retained),
        "--scope-json", str(scope),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        {"path": "protected.txt", "reason": "never_touch"}
    ]
    assert git(repo, "branch", "--show-current") == "main"
    assert (repo / "protected.txt").read_text() == "base\n"
    assert retained.exists()


def test_merge_lane_merges_only_after_scope_pass_and_tears_down(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    create = run_wave(
        "create",
        "--repo", str(repo),
        "--run-slug", "merge",
        "--task-id", "T4",
        "--base", base,
        "--worktree-dir", str(tmp_path / "worktrees"),
        cwd=tmp_path,
    )
    assert create.returncode == 0, create.stderr
    created = json.loads(create.stdout)
    worktree = Path(created["worktree"])
    (worktree / "allowed.txt").write_text("task change\n")
    git(worktree, "add", "allowed.txt")
    git(worktree, "commit", "-m", "task change")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", created["branch"],
        "--worktree", str(worktree),
        "--scope-file", "allowed.txt",
        "--never-touch", "protected.txt",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["violations"] == []
    assert (repo / "allowed.txt").read_text() == "task change\n"
    assert len(git(repo, "log", "-1", "--pretty=%P").split()) == 2
    assert not worktree.exists()
