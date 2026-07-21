from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS_DIR / "sdd-wave"


def run_wave(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
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


def test_create_requires_an_explicit_baseline_command(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)

    result = run_wave(
        "create",
        "--repo", str(repo),
        "--run-slug", "no-baseline",
        "--task-id", "T3",
        "--base", base,
        "--worktree-dir", str(tmp_path / "worktrees"),
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "--baseline-cmd" in result.stderr
    assert not git(repo, "branch", "--list", "sdd/no-baseline/T3")


def test_create_rejects_an_option_shaped_base_ref(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    injected = tmp_path / "create.out"

    result = run_wave(
        "create",
        "--repo", str(repo),
        "--run-slug", "inject",
        "--task-id", "T0",
        f"--base=--output={injected}",
        "--worktree-dir", str(tmp_path / "worktrees"),
        "--baseline-cmd", "true",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "does not resolve to a commit" in result.stderr
    assert not injected.exists()
    assert not git(repo, "branch", "--list", "sdd/inject/T0")


def test_merge_lane_rejects_diff_option_injection(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    branch = "evil"
    worktree = tmp_path / "evil-worktree"
    git(repo, "worktree", "add", "-b", branch, str(worktree), base)
    (worktree / "protected.txt").write_text("injected change\n")
    git(worktree, "add", "protected.txt")
    git(worktree, "commit", "-m", "protected change")
    candidate = git(worktree, "rev-parse", "HEAD")
    injected_prefix = tmp_path / "diff.out"
    injected_file = Path(f"{injected_prefix}..{branch}")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        f"--base=--output={injected_prefix}",
        "--task-branch", branch,
        "--candidate-sha", candidate,
        "--expected-parent", base,
        "--worktree", str(worktree),
        "--scope-file", "allowed.txt",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert not injected_file.exists()
    assert (repo / "protected.txt").read_text() == "base\n"
    assert git(repo, "rev-parse", "HEAD") == base
    assert worktree.exists()


def test_merge_lane_audits_rename_source_paths(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    branch = "sdd/rename/T1"
    worktree = tmp_path / "rename-worktree"
    git(repo, "worktree", "add", "-b", branch, str(worktree), base)
    git(worktree, "mv", "protected.txt", "allowed-renamed.txt")
    git(worktree, "commit", "-m", "rename protected into scope")
    candidate = git(worktree, "rev-parse", "HEAD")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", branch,
        "--candidate-sha", candidate,
        "--expected-parent", base,
        "--worktree", str(worktree),
        "--scope-file", "allowed-renamed.txt",
        "--never-touch", "protected.txt",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert {"path": "protected.txt", "reason": "never_touch"} in payload["violations"]
    assert (repo / "protected.txt").read_text() == "base\n"
    assert worktree.exists()


def test_merge_lane_blocks_a_task_ref_move_after_audit(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    branch = "sdd/move/T1"
    worktree = tmp_path / "move-worktree"
    git(repo, "worktree", "add", "-b", branch, str(worktree), base)
    (worktree / "allowed.txt").write_text("audited change\n")
    git(worktree, "add", "allowed.txt")
    git(worktree, "commit", "-m", "audited candidate")
    candidate = git(worktree, "rev-parse", "HEAD")
    (worktree / "protected.txt").write_text("unaudited change\n")
    git(worktree, "add", "protected.txt")
    git(worktree, "commit", "-m", "unaudited ref move")
    moved = git(worktree, "rev-parse", "HEAD")
    git(worktree, "reset", "--hard", candidate)

    real_git = shutil.which("git")
    assert real_git is not None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import os, subprocess, sys\n"
        f"real_git = {real_git!r}\n"
        "result = subprocess.run([real_git, *sys.argv[1:]])\n"
        f"if result.returncode == 0 and 'diff' in sys.argv and not os.environ.get('MOVED_ONCE'):\n"
        "    env = dict(os.environ, MOVED_ONCE='1')\n"
        f"    subprocess.run([real_git, '-C', {str(repo)!r}, 'update-ref', "
        f"'refs/heads/{branch}', {moved!r}], check=True, env=env)\n"
        "raise SystemExit(result.returncode)\n"
    )
    wrapper.chmod(wrapper.stat().st_mode | 0o111)
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", branch,
        "--candidate-sha", candidate,
        "--expected-parent", base,
        "--worktree", str(worktree),
        "--scope-file", "allowed.txt",
        "--never-touch", "protected.txt",
        cwd=tmp_path,
        env=env,
    )

    assert result.returncode != 0
    assert json.loads(result.stdout)["stage"] == "task-ref-moved"
    assert git(repo, "rev-parse", "HEAD") == base
    assert (repo / "protected.txt").read_text() == "base\n"
    assert worktree.exists()


def test_merge_lane_rejects_a_different_task_worktree(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    task_a = tmp_path / "task-a-worktree"
    task_b = tmp_path / "task-b-worktree"
    git(repo, "worktree", "add", "-b", "sdd/tasks/a", str(task_a), base)
    git(repo, "worktree", "add", "-b", "sdd/tasks/b", str(task_b), base)
    (task_a / "allowed.txt").write_text("task a\n")
    git(task_a, "add", "allowed.txt")
    git(task_a, "commit", "-m", "task a")
    candidate = git(task_a, "rev-parse", "HEAD")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", "sdd/tasks/a",
        "--candidate-sha", candidate,
        "--expected-parent", base,
        "--worktree", str(task_b),
        "--scope-file", "allowed.txt",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert json.loads(result.stdout)["stage"] == "worktree-validation"
    assert task_a.exists()
    assert task_b.exists()
    assert git(repo, "rev-parse", "HEAD") == base


def test_merge_lane_requires_candidate_and_expected_parent_match(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    branch = "sdd/guards/T1"
    worktree = tmp_path / "guard-worktree"
    git(repo, "worktree", "add", "-b", branch, str(worktree), base)
    (worktree / "allowed.txt").write_text("candidate\n")
    git(worktree, "add", "allowed.txt")
    git(worktree, "commit", "-m", "candidate")
    candidate = git(worktree, "rev-parse", "HEAD")

    wrong_candidate = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", branch,
        "--candidate-sha", base,
        "--expected-parent", base,
        "--worktree", str(worktree),
        "--scope-file", "allowed.txt",
        cwd=tmp_path,
    )
    wrong_parent = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", branch,
        "--candidate-sha", candidate,
        "--expected-parent", candidate,
        "--worktree", str(worktree),
        "--scope-file", "allowed.txt",
        cwd=tmp_path,
    )

    assert json.loads(wrong_candidate.stdout)["stage"] == "candidate-mismatch"
    assert json.loads(wrong_parent.stdout)["stage"] == "expected-parent-mismatch"
    assert wrong_candidate.returncode != 0
    assert wrong_parent.returncode != 0
    assert git(repo, "rev-parse", "HEAD") == base
    assert worktree.exists()


def test_merge_lane_never_touch_wins_and_preserves_branch(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    branch = "sdd/audit/T3"
    retained = tmp_path / "retained-worktree"
    git(repo, "worktree", "add", "-b", branch, str(retained), base)
    (retained / "protected.txt").write_text("changed\n")
    git(retained, "add", "protected.txt")
    git(retained, "commit", "-m", "touch protected")
    candidate = git(retained, "rev-parse", "HEAD")
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps({
        "files": ["protected.txt"],
        "never_touch": ["protected.txt"],
    }))

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", branch,
        "--candidate-sha", candidate,
        "--expected-parent", base,
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
        "--baseline-cmd", "true",
        cwd=tmp_path,
    )
    assert create.returncode == 0, create.stderr
    created = json.loads(create.stdout)
    worktree = Path(created["worktree"])
    (worktree / "allowed.txt").write_text("task change\n")
    git(worktree, "add", "allowed.txt")
    git(worktree, "commit", "-m", "task change")
    candidate = git(worktree, "rev-parse", "HEAD")

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", created["branch"],
        "--candidate-sha", candidate,
        "--expected-parent", base,
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


def test_merge_lane_rejects_an_independent_diff_head(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    retained = tmp_path / "retained-worktree"
    retained.mkdir()

    result = run_wave(
        "merge-lane",
        "--repo", str(repo),
        "--base", base,
        "--task-branch", "main",
        "--candidate-sha", base,
        "--expected-parent", base,
        "--head", "different-ref",
        "--worktree", str(retained),
        "--scope-file", "allowed.txt",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --head" in result.stderr
    assert retained.exists()
