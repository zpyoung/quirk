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


def publish(
    repo: Path, plan: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), "--plan", str(plan), "--dry-run", *args],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def find_line(lines: list[str], *parts: str) -> int:
    return next(i for i, line in enumerate(lines) if all(part in line for part in parts))


def assert_create_metadata(
    repo: Path,
    lines: list[str],
    create_indexes: list[int],
    branches: list[str],
) -> None:
    parents = ["main", *branches[:-1]]
    for position, (line_index, parent) in enumerate(
        zip(create_indexes, parents), start=1
    ):
        line = lines[line_index]
        assert line.count("<!-- split-branch:stack -->") == 1
        assert f"parent: {parent}" in line
        assert f"base-sha: {git(repo, 'rev-parse', parent)}" in line
        assert f"position: {position}/3" in line
        assert line.count("<!-- /split-branch:stack -->") == 1


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
    assert_create_metadata(repo, lines, creates, branches)


def test_null_original_pr_omits_comment_and_retarget(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path, original_pr=None)
    result = publish(repo, plan, "--forge", "github")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert not any(" comment " in line for line in lines)
    assert not any(" pr edit " in line for line in lines)


def test_gitlab_complete_order_metadata_ready_and_fork_note(tmp_path: Path) -> None:
    repo, plan, branches = prepare(tmp_path)
    result = publish(repo, plan, "--remote", "upstream", "--forge", "gitlab", "--fork")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()

    pushes = [find_line(lines, "git push -u upstream", branch) for branch in branches]
    force = find_line(lines, "git push --force-with-lease upstream feature/x")
    comment = find_line(lines, "glab mr note 456")
    creates = [
        find_line(
            lines,
            "glab mr create --draft --yes",
            f"--target-branch {parent}",
            f"--source-branch {branch}",
        )
        for branch, parent in zip(branches, ["main", *branches[:-1]])
    ]
    retarget = find_line(
        lines, "glab mr update 456 --yes", f"--target-branch {branches[-1]}"
    )
    ready = find_line(lines, f"glab mr update {branches[0]} --yes --ready")

    assert pushes == sorted(pushes)
    assert max(pushes) < force < comment < min(creates)
    assert creates == sorted(creates)
    assert max(creates) < retarget < ready
    assert sum("glab mr create" in line for line in lines) == 3
    assert sum(" --ready" in line for line in lines) == 1
    assert all(" --yes " in f" {lines[i]} " for i in [*creates, retarget, ready])
    notes = [line for line in lines if line.startswith("NOTE:")]
    assert len(notes) == 1
    assert "fork" in notes[0].lower() and "retarget" in notes[0].lower()
    assert_create_metadata(repo, lines, creates, branches)


def test_gitlab_fork_real_run_prints_but_does_not_execute_retarget(tmp_path: Path) -> None:
    repo, plan, branches = prepare(tmp_path)
    shim_dir = tmp_path / "fork-shims"
    shim_dir.mkdir()
    real_git = subprocess.run(
        ["which", "git"], check=True, text=True, capture_output=True
    ).stdout.strip()
    forge_log = tmp_path / "glab.log"
    (shim_dir / "git").write_text(
        f'''#!/bin/sh
if [ "$1" = push ]; then exit 0; fi
exec "{real_git}" "$@"
'''
    )
    (shim_dir / "git").chmod(0o755)
    (shim_dir / "glab").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{forge_log}"\nexit 0\n'
    )
    (shim_dir / "glab").chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--plan",
            str(plan),
            "--forge",
            "gitlab",
            "--fork",
            "--remote",
            "upstream",
        ],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "NOTE:" in result.stdout
    assert f"glab mr update 456 --yes --target-branch {branches[-1]}" in result.stdout
    executed = forge_log.read_text().splitlines()
    assert not any(line.startswith("mr update 456 ") for line in executed)
    assert f"mr update {branches[0]} --yes --ready" in executed
    assert all(" --yes " in f" {line} " for line in executed if line.startswith("mr create "))


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


def test_dry_run_executes_only_git_reads_and_preserves_git_bytes(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    real_git = subprocess.run(
        ["which", "git"], check=True, text=True, capture_output=True
    ).stdout.strip()
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    git_log = tmp_path / "git.log"
    network_log = tmp_path / "network.log"
    (shim_dir / "git").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{git_log}"\nexec "{real_git}" "$@"\n'
    )
    (shim_dir / "git").chmod(0o755)
    for command in ("gh", "glab"):
        (shim_dir / command).write_text(
            f'#!/bin/sh\necho {command} >> "{network_log}"\nexit 99\n'
        )
        (shim_dir / command).chmod(0o755)

    def git_bytes() -> dict[str, bytes]:
        return {
            str(path.relative_to(repo / ".git")): path.read_bytes()
            for path in (repo / ".git").rglob("*")
            if path.is_file()
        }

    before = git_bytes()
    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}{os.pathsep}{env['PATH']}"
    result = publish(repo, plan, "--forge", "github", env=env)
    assert result.returncode == 0, result.stderr
    assert git_bytes() == before
    assert not network_log.exists()
    calls = git_log.read_text().splitlines()
    assert calls
    assert all(
        call == "config --get remote.pushDefault"
        or call.startswith("show-ref --verify --quiet refs/heads/")
        or call.startswith("rev-parse --verify ")
        for call in calls
    )


def test_unresolved_parent_is_rejected_before_any_publish_output(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    data = json.loads(plan.read_text())
    data["slices"][2]["parent"] = "missing-parent"
    plan.write_text(json.dumps(data))
    result = publish(repo, plan, "--forge", "github")
    assert result.returncode == 5
    assert result.stdout == ""


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


def forge_path(tmp_path: Path, available_cli: str) -> dict[str, str]:
    bin_dir = tmp_path / f"bin-{available_cli}"
    bin_dir.mkdir()
    for command in ("bash", "dirname", "git", "jq"):
        executable = subprocess.run(
            ["which", command], check=True, text=True, capture_output=True
        ).stdout.strip()
        (bin_dir / command).symlink_to(executable)
    cli = bin_dir / available_cli
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    return env


def test_missing_github_cli_exits_seven_when_only_glab_exists(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    result = subprocess.run(
        [str(SCRIPT), "--plan", str(plan), "--forge", "github"],
        cwd=repo,
        env=forge_path(tmp_path, "glab"),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7
    assert "gh" in result.stderr
    assert git(repo, "status", "--porcelain") == ""


def test_missing_gitlab_cli_exits_seven_when_only_gh_exists(tmp_path: Path) -> None:
    repo, plan, _ = prepare(tmp_path)
    result = subprocess.run(
        [str(SCRIPT), "--plan", str(plan), "--forge", "gitlab"],
        cwd=repo,
        env=forge_path(tmp_path, "gh"),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7
    assert "glab" in result.stderr
    assert git(repo, "status", "--porcelain") == ""
