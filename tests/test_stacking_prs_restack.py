"""stacking-prs restack.sh: replay one stack layer onto a new base, push with lease, retarget."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from .stacking_prs_stubs import read_forge_log, write_forge_stubs

REPO_ROOT = Path(__file__).resolve().parents[1]
RESTACK = REPO_ROOT / "skills" / "stacking-prs" / "scripts" / "restack.sh"
# RESTACK_TEST_BASH=/bin/bash runs the suite under macOS's Bash 3.2
BASH = os.environ.get("RESTACK_TEST_BASH") or shutil.which("bash") or "/bin/bash"

BACKUP_RE = re.compile(r"^backup/[A-Za-z0-9_./-]+_\d{8}_\d{6}$")


class Sandbox:
    """A throwaway repo with a local bare `origin`, a private HOME, and forge stubs."""

    def __init__(self, tmp_path: Path) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        self.origin = tmp_path / "origin.git"
        self.bin = tmp_path / "bin"
        self.log = tmp_path / "forge.log"
        self.counter = 0
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", str(self.origin))
        self.commit("shared.txt", "base\n", "base")
        self.git("push", "-q", "-u", "origin", "main")

    def env(self) -> Dict[str, str]:
        return {
            **os.environ,
            "HOME": str(self.home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": str(self.root),
        }

    def git(self, *args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
        done = subprocess.run(
            ["git", *args], cwd=cwd or self.repo, check=check, capture_output=True, text=True,
            env=self.env(),
        )
        return done.stdout.strip()

    def commit(self, name: str, content: str, message: str, cwd: Optional[Path] = None) -> None:
        path = (cwd or self.repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "-m", message, cwd=cwd)

    def layer(self, name: str, base: str, commits: int = 1, push: bool = True) -> str:
        """Create `name` off `base` with own commits touching their own files; returns its tip."""
        self.git("checkout", "-q", "-b", name, base)
        for index in range(commits):
            self.counter += 1
            self.commit(f"{name}-{index}.txt", f"{name}\n{index}\n", f"{name} commit {index}")
        if push:
            self.git("push", "-q", "-u", "origin", name)
        return self.git("rev-parse", name)

    def squash_merge(self, branch: str) -> None:
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--squash", branch)
        self.git("commit", "-q", "-m", f"squash {branch}")
        self.git("push", "-q", "origin", "main")
        self.git("fetch", "-q", "origin")

    def merge_commit(self, branch: str) -> None:
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", f"merge {branch}", branch)
        self.git("push", "-q", "origin", "main")
        self.git("fetch", "-q", "origin")

    def rev(self, ref: str, cwd: Optional[Path] = None) -> str:
        return self.git("rev-parse", ref, cwd=cwd)

    def own_commits(self, base: str, branch: str) -> List[str]:
        out = self.git("log", "--format=%s", "--reverse", f"{base}..{branch}")
        return out.splitlines()

    def branches(self) -> List[str]:
        return self.git("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()

    def run(
        self,
        *args: str,
        fixture: Optional[Dict[str, List[dict]]] = None,
        forge: Optional[str] = None,
        tools=("gh", "glab"),
        path_only: Optional[str] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        stub_env = write_forge_stubs(self.bin, fixture or {}, self.log, tools)
        env = {**self.env(), **stub_env}
        if path_only is not None:
            env["PATH"] = path_only
        if forge is not None:
            env["STACK_FORGE"] = forge
        env.update(extra_env or {})
        return subprocess.run(
            [BASH, str(RESTACK), *args], cwd=self.repo, capture_output=True, text=True, env=env,
        )

    def forge_calls(self) -> List[List[str]]:
        return read_forge_log(self.log)


def gh_fixture(number: int, base: str, url: str = "https://example.test/pull/42") -> Dict[str, List[dict]]:
    return {
        "gh": [
            {"argv": ["pr", "view", str(number), "--json", "baseRefName"], "stdout": base + "\n"},
            {"argv": ["pr", "view", str(number), "--json", "url"], "stdout": url + "\n"},
            {"argv": ["pr", "edit", str(number)], "stdout": ""},
        ]
    }


def load(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout)


def squash_scenario(sb: Sandbox):
    parent_tip = sb.layer("auth-schema", "main", commits=2)
    child_tip = sb.layer("auth-api", "auth-schema", commits=2)
    sb.squash_merge("auth-schema")
    sb.git("checkout", "-q", "main")
    return parent_tip, child_tip


def test_squash_merged_parent_replays_only_own_commits_pushes_and_retargets(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)

    result = sb.run(
        "--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
        "--forge", "github", fixture=gh_fixture(42, "auth-schema"),
    )

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["success"] is True
    assert out["branch"] == "auth-api"
    assert out["onto"] == "main"
    assert out["onto_ref"] == "origin/main"
    assert out["old_tip"] == parent_tip
    assert out["old_head"] == child_tip
    assert out["new_head"] == sb.rev("auth-api")
    assert out["commits_replayed"] == 2
    assert out["pushed"] is True
    assert out["retargeted"] is True
    assert out["pr_url"] == "https://example.test/pull/42"
    assert out["conflicted_files"] == []
    assert sb.own_commits("origin/main", "auth-api") == ["auth-api commit 0", "auth-api commit 1"]
    assert sb.rev("origin/main") == sb.git("rev-parse", "auth-api~2")
    assert sb.rev("auth-api", cwd=sb.origin) == out["new_head"]
    assert ["gh", "pr", "edit", "42", "--base", "main"] in sb.forge_calls()
    assert not any(call[1:3] == ["pr", "merge"] for call in sb.forge_calls())


def test_stdout_is_only_the_json_document(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)
    assert result.returncode == 0, result.stderr
    json.loads(result.stdout)
    assert result.stdout.strip().startswith("{") and result.stdout.strip().endswith("}")


def test_merge_commit_parent_replays_only_own_commits(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip = sb.layer("auth-schema", "main", commits=2)
    sb.layer("auth-api", "auth-schema", commits=1)
    sb.merge_commit("auth-schema")
    sb.git("checkout", "-q", "main")

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["commits_replayed"] == 1
    assert out["pushed"] is True
    assert out["retargeted"] is False
    assert sb.own_commits("origin/main", "auth-api") == ["auth-api commit 0"]
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/main", "auth-api"], cwd=sb.repo, env=sb.env(),
    )
    assert is_ancestor.returncode == 0


def test_middle_layer_chaining_uses_the_parents_old_head(tmp_path):
    sb = Sandbox(tmp_path)
    schema_tip = sb.layer("auth-schema", "main", commits=1)
    sb.layer("auth-api", "auth-schema", commits=2)
    sb.layer("auth-ui", "auth-api", commits=1)
    sb.squash_merge("auth-schema")
    sb.git("checkout", "-q", "main")

    first = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", schema_tip)
    assert first.returncode == 0, first.stderr
    api = load(first)

    second = sb.run("--branch", "auth-ui", "--onto", "auth-api", "--old-tip", api["old_head"])

    assert second.returncode == 0, second.stderr
    ui = load(second)
    assert ui["onto_ref"] == "origin/auth-api"
    assert ui["commits_replayed"] == 1
    assert sb.own_commits("auth-api", "auth-ui") == ["auth-ui commit 0"]
    assert sb.rev("auth-api") == api["new_head"]
    assert sb.rev("auth-ui", cwd=sb.origin) == ui["new_head"]


def test_onto_ref_falls_back_to_local_branch_without_remote_tracking_ref(tmp_path):
    sb = Sandbox(tmp_path)
    tip = sb.layer("auth-schema", "main", commits=1, push=False)
    sb.layer("auth-api", "auth-schema", commits=1, push=False)
    sb.git("checkout", "-q", "main")
    sb.commit("trunk.txt", "t\n", "trunk moved")
    sb.git("checkout", "-q", "auth-api")
    sb.git("branch", "-q", "-f", "auth-schema", "main")

    result = sb.run("--branch", "auth-api", "--onto", "auth-schema", "--old-tip", tip, "--no-push")

    assert result.returncode == 0, result.stderr
    assert load(result)["onto_ref"] == "auth-schema"


def test_explicit_onto_ref_is_used(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    # an unpushed local commit makes refs/heads/main differ from the default origin/main
    sb.commit("local-parent.txt", "local parent\n", "local parent change")
    onto_tip = sb.rev("main")
    assert onto_tip != sb.rev("origin/main")
    result = sb.run(
        "--branch", "auth-api", "--onto", "main", "--onto-ref", "refs/heads/main",
        "--old-tip", parent_tip, "--no-push",
    )
    assert result.returncode == 0, result.stderr
    assert load(result)["onto_ref"] == "refs/heads/main"
    assert sb.rev("auth-api~2") == onto_tip
    assert sb.own_commits("main", "auth-api") == ["auth-api commit 0", "auth-api commit 1"]


def test_backup_branch_name_format_and_contents(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)

    assert result.returncode == 0, result.stderr
    backup = load(result)["backup_branch"]
    assert BACKUP_RE.match(backup), backup
    assert backup.startswith("backup/auth-api_")
    assert sb.rev(backup) == child_tip
    assert backup not in sb.git("for-each-ref", "--format=%(refname:short)", cwd=sb.origin).splitlines()
    assert "backup" not in sb.git("ls-remote", "--heads", "origin")


def test_conflict_exits_2_restores_branch_and_lists_files(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip = sb.layer("auth-schema", "main", commits=1)
    sb.git("checkout", "-q", "-b", "auth-api", "auth-schema")
    sb.commit("shared.txt", "child edit\n", "child touches shared")
    sb.git("push", "-q", "-u", "origin", "auth-api")
    child_tip = sb.rev("auth-api")
    sb.git("checkout", "-q", "main")
    sb.commit("shared.txt", "trunk edit\n", "trunk touches shared")
    sb.git("push", "-q", "origin", "main")
    sb.git("fetch", "-q", "origin")
    origin_before = sb.rev("auth-api", cwd=sb.origin)

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)

    assert result.returncode == 2, result.stderr
    out = load(result)
    assert out["success"] is False
    assert out["conflicted_files"] == ["shared.txt"]
    assert sb.rev("auth-api") == child_tip
    assert sb.git("symbolic-ref", "HEAD") == "refs/heads/main"
    assert not (sb.repo / ".git" / "rebase-merge").exists()
    assert not (sb.repo / ".git" / "rebase-apply").exists()
    assert sb.git("status", "--porcelain") == ""
    assert sb.rev("auth-api", cwd=sb.origin) == origin_before
    assert BACKUP_RE.match(out["backup_branch"])


def test_branch_checked_out_in_another_worktree_exits_3(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)
    other = tmp_path / "other-wt"
    sb.git("worktree", "add", "-q", str(other), "auth-api")
    branches_before = sb.branches()

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    "--forge", "github", fixture=gh_fixture(42, "auth-schema"))

    assert result.returncode == 3, result.stderr
    out = load(result)
    assert out["success"] is False
    assert "other-wt" in out["message"]
    assert sb.rev("auth-api") == child_tip
    assert sb.branches() == branches_before
    assert sb.forge_calls() == []
    assert sb.rev("auth-api", cwd=sb.origin) == child_tip


def test_branch_checked_out_in_this_worktree_is_allowed(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    sb.git("checkout", "-q", "auth-api")
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--no-push")
    assert result.returncode == 0, result.stderr


# background_fetch: a fetch after the teammate's push refreshes the lease, so only --force-if-includes rejects
@pytest.mark.parametrize("background_fetch", [False, True])
def test_lease_rejection_after_remote_moved_exits_4_keeping_rebase_and_backup(tmp_path, background_fetch):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)
    second = tmp_path / "second"
    sb.git("clone", "-q", str(sb.origin), str(second))
    sb.git("config", "user.email", "o@example.com", cwd=second)
    sb.git("config", "user.name", "o", cwd=second)
    sb.git("config", "commit.gpgsign", "false", cwd=second)
    sb.git("checkout", "-q", "auth-api", cwd=second)
    sb.commit("teammate.txt", "hi\n", "teammate commit", cwd=second)
    sb.git("push", "-q", "origin", "auth-api", cwd=second)
    teammate = sb.rev("auth-api", cwd=second)
    if background_fetch:
        sb.git("fetch", "-q", "origin")

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    "--forge", "github", fixture=gh_fixture(42, "auth-schema"))

    assert result.returncode == 4, result.stderr
    out = load(result)
    assert out["success"] is False
    assert out["pushed"] is False
    assert out["new_head"] == sb.rev("auth-api") != child_tip
    assert sb.rev(out["backup_branch"]) == child_tip
    assert sb.rev("auth-api", cwd=sb.origin) == teammate
    assert not any(call[1:3] == ["pr", "edit"] for call in sb.forge_calls())


def test_retarget_failure_after_push_exits_5_with_the_pr_url(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    fixture = gh_fixture(42, "auth-schema")
    fixture["gh"].insert(0, {"argv": ["pr", "edit", "42"], "exit": 1, "stderr": "boom"})

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    "--forge", "github", fixture=fixture)

    assert result.returncode == 5, result.stderr
    out = load(result)
    assert out["success"] is False
    assert out["pushed"] is True
    assert out["retargeted"] is False
    assert out["pr_url"] == "https://example.test/pull/42"
    assert sb.rev("auth-api", cwd=sb.origin) == out["new_head"]
    assert "Error:" in result.stderr


def test_retarget_skipped_when_pr_already_targets_onto(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    "--forge", "github", fixture=gh_fixture(42, "main"))

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["retargeted"] is False
    assert out["pushed"] is True
    assert not any(call[1:3] == ["pr", "edit"] for call in sb.forge_calls())


def test_update_refs_config_cannot_move_other_branches_or_the_backup(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)
    sb.git("config", "rebase.updateRefs", "true")
    mid = sb.rev("auth-api~1")
    sb.git("branch", "mid-marker", mid)

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--no-push")

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["new_head"] != child_tip
    assert sb.rev("mid-marker") == mid
    assert sb.rev(out["backup_branch"]) == child_tip


@pytest.mark.parametrize("operation", ["rebase", "merge", "cherry-pick", "revert", "bisect"])
def test_operation_in_progress_exits_1_and_leaves_it_alone(tmp_path, operation):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)
    marker = {
        "rebase": "rebase-merge",
        "merge": "MERGE_HEAD",
        "cherry-pick": "CHERRY_PICK_HEAD",
        "revert": "REVERT_HEAD",
        "bisect": "BISECT_LOG",
    }[operation]
    sb.git("checkout", "-q", "-b", "other", "main")
    sb.commit("other.txt", "one\n", "other one")
    sb.commit("other.txt", "two\n", "other two")
    if operation == "rebase":
        edit_env = {**sb.env(), "GIT_SEQUENCE_EDITOR": "sed -i.bak 's/^pick/edit/'"}
        subprocess.run(
            ["git", "rebase", "-i", "main"], cwd=sb.repo, check=True, capture_output=True, env=edit_env,
        )
    elif operation == "merge":
        sb.git("merge", "-q", "--no-commit", "--no-ff", "auth-api")
    elif operation == "cherry-pick":
        (sb.repo / ".git" / "CHERRY_PICK_HEAD").write_text(sb.rev("other") + "\n")
    elif operation == "revert":
        (sb.repo / ".git" / "REVERT_HEAD").write_text(sb.rev("other") + "\n")
    else:
        sb.git("bisect", "start")
    marker_path = sb.repo / sb.git("rev-parse", "--git-path", marker)
    assert marker_path.exists()
    branches_before = sb.branches()
    head_before = sb.rev("HEAD")

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)

    assert result.returncode == 1, result.stderr
    out = load(result)
    assert out["success"] is False
    assert operation in out["message"]
    assert sb.branches() == branches_before
    assert sb.rev("auth-api") == child_tip
    assert sb.rev("HEAD") == head_before
    assert marker_path.exists()


def test_dirty_tree_exits_1_before_any_change(tmp_path):
    for staged in (False, True):
        sb = Sandbox(tmp_path / ("staged" if staged else "unstaged"))
        parent_tip, child_tip = squash_scenario(sb)
        sb.git("checkout", "-q", "main")
        (sb.repo / "shared.txt").write_text("dirty\n")
        if staged:
            sb.git("add", "shared.txt")
        branches_before = sb.branches()

        result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip)

        assert result.returncode == 1
        out = load(result)
        assert out["success"] is False
        assert "Error:" in result.stderr
        assert sb.branches() == branches_before
        assert sb.rev("auth-api") == child_tip


def test_no_push_rebases_locally_and_leaves_remote_alone(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--no-push")

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["pushed"] is False
    assert out["new_head"] == sb.rev("auth-api") != child_tip
    assert sb.rev("auth-api", cwd=sb.origin) == child_tip


def test_gitlab_retarget_command_shape(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    fixture = {"glab": [
        {"argv": ["mr", "view", "7", "-F", "json"],
         "stdout": json.dumps({"target_branch": "auth-schema", "web_url": "https://gl.test/mr/7"})},
        {"argv": ["mr", "update", "7"], "stdout": ""},
    ]}

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "7",
                    "--forge", "gitlab", fixture=fixture)

    assert result.returncode == 0, result.stderr
    out = load(result)
    assert out["retargeted"] is True
    assert out["pr_url"] == "https://gl.test/mr/7"
    assert ["glab", "mr", "update", "7", "--target-branch", "main"] in sb.forge_calls()
    assert not any(call[0] == "gh" for call in sb.forge_calls())


def test_forge_defaults_to_stack_forge_env(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    fixture = {"glab": [
        {"argv": ["mr", "view", "7", "-F", "json"], "stdout": json.dumps({"target_branch": "auth-schema"})},
        {"argv": ["mr", "update", "7"], "stdout": ""},
    ]}
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "7",
                    fixture=fixture, forge="gitlab")
    assert result.returncode == 0, result.stderr
    assert ["glab", "mr", "update", "7", "--target-branch", "main"] in sb.forge_calls()


def test_forge_defaults_to_remote_host(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    sb.git("remote", "set-url", "origin", "https://github.com/acme/repo.git")
    sb.git("remote", "set-url", "--push", "origin", str(sb.origin))
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    fixture=gh_fixture(42, "auth-schema"))
    assert result.returncode == 0, result.stderr
    assert ["gh", "pr", "edit", "42", "--base", "main"] in sb.forge_calls()


def test_pr_with_unresolved_forge_exits_1_before_the_backup(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, child_tip = squash_scenario(sb)
    branches_before = sb.branches()

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42")

    assert result.returncode == 1
    assert load(result)["success"] is False
    assert sb.branches() == branches_before
    assert sb.rev("auth-api") == child_tip


def test_pr_with_missing_forge_cli_exits_1_before_the_backup(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool in ("git", "jq", "date", "mktemp", "rm", "cat", "sed", "tr", "dirname", "basename", "env",
                 "grep", "awk", "head", "tail", "wc", "cut", "sort", "uniq"):
        found = shutil.which(tool)
        if found:
            (tools / tool).symlink_to(found)
    branches_before = sb.branches()

    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "42",
                    "--forge", "github", tools=(), path_only=str(tools))

    assert result.returncode == 1, result.stderr
    assert "gh" in load(result)["message"]
    assert sb.branches() == branches_before


def test_old_tip_that_is_not_an_ancestor_exits_1(tmp_path):
    sb = Sandbox(tmp_path)
    squash_scenario(sb)
    unrelated = sb.rev("main")
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", unrelated)
    assert result.returncode == 1
    assert "ancestor" in load(result)["message"]


def test_missing_branch_unresolvable_onto_ref_and_missing_args_exit_1(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    cases = [
        ("--branch", "nope", "--onto", "main", "--old-tip", parent_tip),
        ("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--onto-ref", "nope/ref"),
        ("--branch", "auth-api", "--onto", "nonexistent", "--old-tip", parent_tip),
        ("--branch", "auth-api", "--onto", "main"),
        ("--bogus",),
    ]
    for args in cases:
        result = sb.run(*args)
        assert result.returncode == 1, (args, result.stderr)
        assert load(result)["success"] is False
        assert "Error:" in result.stderr


def test_gitlab_retarget_is_bound_to_the_remote_project(tmp_path):
    sb = Sandbox(tmp_path)
    parent_tip, _ = squash_scenario(sb)
    url = "https://gitlab.example.com/acme/app.git"
    sb.git("remote", "set-url", "origin", url)
    fixture = {"glab": [
        {"argv": ["mr", "view", "5", "-F", "json"], "stdout": json.dumps({"target_branch": "auth-schema"})},
        {"argv": ["mr", "update", "5"], "stdout": ""},
    ]}
    result = sb.run("--branch", "auth-api", "--onto", "main", "--old-tip", parent_tip, "--pr", "5",
                    "--forge", "gitlab", "--no-push", fixture=fixture)
    assert result.returncode == 0, result.stderr
    calls = [c for c in sb.forge_calls() if c[0] == "glab"]
    assert calls and all(c[-2:] == ["-R", url] for c in calls)
