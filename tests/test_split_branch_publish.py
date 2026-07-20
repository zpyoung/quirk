from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests.split_branch_fixtures import make_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "publish.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


def prepare(tmp_path: Path, original_pr: int | None = 456) -> tuple[Path, Path, list[str]]:
    repo = make_repo(tmp_path)
    branches = ["feature/x-prep", "feature/x-mvp", "feature/x-polish"]
    parent = "main"
    for branch in branches:
        git(repo, "branch", branch, parent)
        parent = branch
    git(repo, "branch", "feature/x", branches[-1])

    plan = {
        "base": "main",
        "original_branch": "feature/x",
        "original_pr": original_pr,
        "slices": [
            {
                "branch": branch,
                "parent": "main" if index == 0 else branches[index - 1],
                "title": f"Slice {index + 1}",
                "body": f"Body {index + 1}",
                "position": index + 1,
            }
            for index, branch in enumerate(branches)
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    return repo, plan_path, branches


def publish(repo: Path, plan: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), "--plan", str(plan), "--dry-run", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def find_line(lines: list[str], *parts: str) -> int:
    return next(i for i, line in enumerate(lines) if all(part in line for part in parts))


def test_github_dry_run_has_exact_publish_order_and_metadata(tmp_path: Path) -> None:
    repo, plan, branches = prepare(tmp_path)
    result = publish(repo, plan, "--remote", "upstream", "--forge", "github")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()

    pushes = [find_line(lines, "git push -u upstream", branch) for branch in branches]
    force = find_line(lines, "git push --force-with-lease upstream feature/x")
    comment = find_line(lines, "gh pr comment 456")
    creates = [
        find_line(lines, "gh pr create --draft", f"--base {parent}", f"--head {branch}")
        for branch, parent in zip(branches, ["main", *branches[:-1]])
    ]
    retarget = find_line(lines, "gh pr edit 456", f"--base {branches[-1]}")
    ready = find_line(lines, "gh pr ready", branches[0])

    assert pushes == sorted(pushes)
    assert max(pushes) < force < comment < min(creates)
    assert creates == sorted(creates)
    assert max(creates) < retarget < ready
    assert len(lines) == 10
    assert sum("git push -u" in line for line in lines) == 3
    assert sum("gh pr create --draft" in line for line in lines) == 3
    assert sum("gh pr ready" in line for line in lines) == 1
    assert not any(line.startswith("git push") and " origin " in line for line in lines)
    assert not any("git push --force " in line for line in lines)

    base_sha = git(repo, "rev-parse", "main")
    first_create = lines[creates[0]]
    assert "<!-- split-branch:stack -->" in first_create
    assert "parent: main" in first_create
    assert f"base-sha: {base_sha}" in first_create
    assert "position: 1/3" in first_create


def test_null_original_pr_omits_comment_and_retarget(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path, original_pr=None)
    result = publish(repo, plan, "--forge", "github")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert not any(" comment " in line for line in lines)
    assert not any(" pr edit " in line for line in lines)


def test_gitlab_uses_target_branches_and_fork_note(tmp_path: Path) -> None:
    repo, plan, branches = prepare(tmp_path)
    result = publish(repo, plan, "--remote", "upstream", "--forge", "gitlab", "--fork")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    creates = [line for line in lines if "glab mr create --draft" in line]
    assert len(creates) == 3
    for line, parent in zip(creates, ["main", *branches[:-1]]):
        assert f"--target-branch {parent}" in line
    notes = [line for line in lines if line.startswith("NOTE:")]
    assert len(notes) == 1
    assert "fork" in notes[0].lower() and "retarget" in notes[0].lower()
    assert any("glab mr update 456" in line and branches[-1] in line for line in lines)


def test_no_force_push_skips_rewrite_and_retarget_with_one_note(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    result = publish(repo, plan, "--forge", "github", "--no-force-push")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert not any("--force-with-lease" in line for line in lines)
    assert not any("gh pr edit 456" in line for line in lines)
    assert not any("gh pr comment 456" in line for line in lines)
    assert sum(line.startswith("NOTE:") for line in lines) == 1
    assert sum("git push -u" in line for line in lines) == 3
    assert sum("gh pr create --draft" in line for line in lines) == 3


def test_remote_defaults_to_push_default_then_origin(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    git(repo, "config", "remote.pushDefault", "company")
    configured = publish(repo, plan, "--forge", "github")
    assert configured.returncode == 0
    assert "git push -u company" in configured.stdout

    git(repo, "config", "--unset", "remote.pushDefault")
    fallback = publish(repo, plan, "--forge", "github")
    assert fallback.returncode == 0
    assert "git push -u origin" in fallback.stdout


def test_missing_slice_and_malformed_arguments_have_contract_exit_codes(tmp_path: Path) -> None:
    repo, plan, branches = prepare(tmp_path)
    git(repo, "branch", "-D", branches[1])
    missing = publish(repo, plan, "--forge", "github")
    assert missing.returncode == 3

    malformed_plan = tmp_path / "malformed.json"
    malformed_plan.write_text('{"base": "main"}')
    malformed = publish(repo, malformed_plan, "--forge", "github")
    assert malformed.returncode == 5

    bad_arg = subprocess.run(
        [str(SCRIPT), "--wat"], cwd=repo, text=True, capture_output=True, check=False
    )
    assert bad_arg.returncode == 5


def test_missing_forge_cli_exits_seven_before_writes(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("bash", "dirname", "git", "jq"):
        executable = subprocess.run(
            ["which", command], check=True, text=True, capture_output=True
        ).stdout.strip()
        (bin_dir / command).symlink_to(executable)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    result = subprocess.run(
        [str(SCRIPT), "--plan", str(plan), "--forge", "github"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7
    assert git(repo, "status", "--porcelain") == ""
