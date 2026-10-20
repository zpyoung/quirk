"""stacking-prs stack.sh: read-only stack detection, forge chain building, and the CI-filter scan."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pytest

from .stacking_prs_stubs import read_forge_log, write_forge_stubs

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK = REPO_ROOT / "skills" / "stacking-prs" / "scripts" / "stack.sh"
# STACK_TEST_BASH=/bin/bash runs the suite under macOS's Bash 3.2
BASH = os.environ.get("STACK_TEST_BASH") or shutil.which("bash") or "/bin/bash"

PIPE_TOOLS = (
    "git", "jq", "awk", "sed", "grep", "tr", "sort", "cat", "mktemp", "dirname", "basename",
    "rm", "mv", "head", "tail", "wc", "cut", "uniq", "env", "bash", "ls", "sh", "date", "tee",
)

SUCCESS = [{"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}]
FAILURE = [{"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "FAILURE"}]


class Sandbox:
    """A throwaway repo with a local bare `origin`, a private HOME, and forge stubs."""

    def __init__(self, tmp_path: Path, trunk: str = "main") -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path
        self.trunk = trunk
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        self.origin = tmp_path / "origin.git"
        self.bin = tmp_path / "bin"
        self.log = tmp_path / "forge.log"
        self.counter = 0
        subprocess.run(["git", "init", "-q", "--bare", "-b", trunk, str(self.origin)], check=True)
        self.git("init", "-q", "-b", trunk)
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", str(self.origin))
        self.commit("README", "base\n")
        self.git("push", "-q", "-u", "origin", trunk)

    def env(self) -> Dict[str, str]:
        return {
            **os.environ,
            "HOME": str(self.home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": str(self.root),
        }

    def git(self, *args: str, cwd: Optional[Path] = None) -> str:
        done = subprocess.run(
            ["git", *args], cwd=cwd or self.repo, check=True, capture_output=True, text=True,
            env=self.env(),
        )
        return done.stdout.strip()

    def commit(self, name: str, content: str, message: str = "c") -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def branch(self, name: str, base: str, commits: int = 1, push: bool = True) -> None:
        self.git("checkout", "-q", "-b", name, base)
        for _ in range(commits):
            self.counter += 1
            self.commit(f"f{self.counter}.txt", f"{name}\n{self.counter}\n", f"{name} {self.counter}")
        if push:
            self.git("push", "-q", "-u", "origin", name)

    def chain(self, names: Sequence[str], base: Optional[str] = None, push: bool = True) -> None:
        parent = base or self.trunk
        for name in names:
            self.branch(name, parent, push=push)
            parent = name

    def snapshot(self) -> Dict[str, str]:
        return {
            "repo_refs": self.git("for-each-ref", "--format=%(refname) %(objectname)"),
            "origin_refs": self.git("for-each-ref", "--format=%(refname) %(objectname)", cwd=self.origin),
            "head": self.git("symbolic-ref", "HEAD"),
            "status": self.git("status", "--porcelain=v1", "--untracked-files=all"),
            "fetch_head": str((self.repo / ".git" / "FETCH_HEAD").exists()),
        }

    def restricted_tools(self, without: Sequence[str] = ()) -> Path:
        tools = self.root / "tools"
        tools.mkdir(exist_ok=True)
        for tool in PIPE_TOOLS:
            found = shutil.which(tool)
            if found and tool not in without and not (tools / tool).exists():
                (tools / tool).symlink_to(found)
        return tools

    def run(
        self,
        *args: str,
        fixture: Optional[dict] = None,
        forge: Optional[str] = "github",
        tools: Sequence[str] = ("gh", "glab"),
        restricted: Optional[Sequence[str]] = None,
        cwd: Optional[Path] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        stub_env = write_forge_stubs(self.bin, fixture or {}, self.log, tools)
        env = {**self.env(), **stub_env}
        if restricted is not None:
            env["PATH"] = str(self.bin) + os.pathsep + str(self.restricted_tools(restricted))
        if forge is not None:
            env["STACK_FORGE"] = forge
        env.update(extra_env or {})
        return subprocess.run(
            [BASH, str(STACK), *args], cwd=cwd or self.repo, capture_output=True, text=True, env=env,
        )

    def detect(self, *args: str, **kwargs) -> dict:
        result = self.run(*args, **kwargs)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def forge_calls(self) -> List[List[str]]:
        return read_forge_log(self.log)


def gh_pr(
    number: int, head: str, base: str, *, draft: bool = False, rollup: Optional[list] = None,
    review: str = "", cross: bool = False, author: str = "octocat",
) -> dict:
    return {
        "number": number,
        "url": f"https://github.com/acme/app/pull/{number}",
        "headRefName": head,
        "baseRefName": base,
        "isDraft": draft,
        "state": "OPEN",
        "reviewDecision": review,
        "statusCheckRollup": SUCCESS if rollup is None else rollup,
        "headRefOid": f"{number:040x}",
        "isCrossRepository": cross,
        "author": {"login": author},
    }


def gh_merged(number: int, head: str, base: str = "main") -> dict:
    return {
        "number": number,
        "headRefName": head,
        "baseRefName": base,
        "headRefOid": f"{number:040x}",
        "mergeCommit": {"oid": f"{number + 1000:040x}"},
        "mergedAt": "2026-10-19T10:00:00Z",
    }


def gh_fixture(
    open_prs: Sequence[dict] = (), merged: Sequence[dict] = (), stack_help: int = 1,
    api: Optional[Dict[int, dict]] = None,
) -> dict:
    """GitHub answers. `api` maps a PR number to the `{stdout, exit}` of its `pulls/<n>` call."""
    entries = [
        {"argv": ["pr", "list", "--state", "open"], "stdout": json.dumps(list(open_prs))},
        {"argv": ["pr", "list", "--state", "merged"], "stdout": json.dumps(list(merged))},
        {"argv": ["stack", "--help"], "exit": stack_help},
        {"argv": ["api"], "stdout": ""},
    ]
    for number, answer in (api or {}).items():
        entries.append({"argv": ["api", f"repos/{{owner}}/{{repo}}/pulls/{number}"], **answer})
    return {"gh": entries}


def classic_stack() -> dict:
    return gh_fixture([
        gh_pr(41, "auth-schema", "main", review="APPROVED"),
        gh_pr(42, "auth-api", "auth-schema", draft=True, review="REVIEW_REQUIRED"),
        gh_pr(43, "auth-ui", "auth-api", draft=True, rollup=FAILURE, review="REVIEW_REQUIRED"),
    ])


def gl_mr(
    iid: int, source: str, target: str, *, author: str = "octocat", draft: bool = False,
    merge_sha: Optional[str] = None, squash_sha: Optional[str] = None,
) -> dict:
    return {
        "iid": iid, "source_branch": source, "target_branch": target, "draft": draft,
        "sha": f"{iid:040x}", "author": {"username": author},
        "web_url": f"https://gitlab.com/acme/app/-/merge_requests/{iid}",
        "merge_commit_sha": merge_sha, "squash_commit_sha": squash_sha,
    }


def gl_fixture(
    open_mrs: Sequence[dict] = (), merged: Sequence[dict] = (),
    pipelines: Optional[Dict[int, Optional[str]]] = None, approved: Optional[Dict[int, bool]] = None,
) -> dict:
    entries = [
        {"argv": ["mr", "list", "-F", "json", "--per-page", "100"], "stdout": json.dumps(list(open_mrs))},
        {"argv": ["mr", "list", "-M", "-F", "json", "--per-page", "100"], "stdout": json.dumps(list(merged))},
    ]
    for mr in open_mrs:
        iid = mr["iid"]
        status = (pipelines or {}).get(iid)
        entries.append({
            "argv": ["mr", "view", str(iid), "-F", "json"],
            "stdout": json.dumps({"head_pipeline": None if status is None else {"status": status}}),
        })
        entries.append({
            "argv": ["api", f"projects/:id/merge_requests/{iid}/approvals"],
            "stdout": json.dumps({"approved": (approved or {}).get(iid, False)}),
        })
    return {"glab": entries}


def codes(out: dict) -> List[str]:
    return [w["code"] for w in out["warnings"]]


def warning(out: dict, code: str) -> dict:
    return next(w for w in out["warnings"] if w["code"] == code)


def column(out: dict, key: str) -> list:
    return [layer[key] for layer in out["layers"]]


@pytest.fixture
def sb(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


# ---- usage and preconditions ----------------------------------------------


def test_outside_a_git_repo_exits_1_with_red_error(sb: Sandbox, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = sb.run(cwd=plain, forge="none")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "Error:" in result.stderr


def test_detached_head_exits_1(sb: Sandbox) -> None:
    sb.git("checkout", "-q", "--detach")
    result = sb.run(forge="none")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "detached" in result.stderr.lower()


def test_detached_head_is_fine_when_branch_is_given(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    sb.git("checkout", "-q", "--detach")
    out = sb.detect("--branch", "feature", forge="none")
    assert column(out, "branch") == ["feature"]


def test_missing_jq_exits_1(sb: Sandbox) -> None:
    result = sb.run(forge="none", restricted=("jq",))
    assert result.returncode == 1
    assert result.stdout == ""
    assert "jq" in result.stderr


def test_unknown_option_and_missing_value_exit_1(sb: Sandbox) -> None:
    for args in (("--bogus",), ("--branch",), ("--check-ci",)):
        result = sb.run(*args, forge="none")
        assert result.returncode == 1, args
        assert result.stdout == ""
        assert "Error:" in result.stderr


def test_unknown_branch_and_unknown_trunk_exit_1(sb: Sandbox) -> None:
    for args in (("--branch", "nope"), ("--trunk", "nope")):
        result = sb.run(*args, forge="none")
        assert result.returncode == 1, args
        assert result.stdout == ""


def test_invalid_stack_forge_exits_1(sb: Sandbox) -> None:
    result = sb.run(forge="bitbucket")
    assert result.returncode == 1
    assert "STACK_FORGE" in result.stderr


# ---- trunk and forge resolution -------------------------------------------


def test_trunk_defaults_to_remote_head_then_main_then_master(tmp_path: Path) -> None:
    sb = Sandbox(tmp_path / "a")
    sb.git("branch", "develop")
    sb.git("push", "-q", "origin", "develop")
    sb.git("remote", "set-head", "origin", "develop")
    sb.branch("feature", "develop")
    assert sb.detect(forge="none")["trunk"] == "develop"
    assert sb.detect("--trunk", "main", forge="none")["trunk"] == "main"

    master = Sandbox(tmp_path / "b", trunk="master")
    master.branch("feature", "master")
    assert master.detect(forge="none")["trunk"] == "master"


def test_forge_resolves_from_the_remote_host(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    cases = {
        "git@github.com:acme/app.git": "github",
        "https://github.com/acme/app.git": "github",
        "ssh://git@gitlab.example.com:2222/acme/app.git": "gitlab",
        "https://git.example.org/acme/app": "none",
    }
    for url, expected in cases.items():
        sb.git("remote", "set-url", "origin", url)
        out = sb.detect(forge=None, fixture=gh_fixture() if expected == "github" else gl_fixture())
        assert out["forge"] == expected, url


def test_stack_forge_env_wins_over_the_remote_host(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    sb.git("remote", "set-url", "origin", "https://github.com/acme/app.git")
    assert sb.detect(forge="none")["forge"] == "none"


# ---- SC-1: not in a stack --------------------------------------------------


def test_sc1_branch_with_no_pr_is_not_in_a_stack(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    out = sb.detect(fixture=gh_fixture())
    assert out["in_stack"] is False
    assert out["mode"] == "local"
    assert column(out, "branch") == ["feature"]
    assert out["layers"][0]["state"] == "local"
    assert "forge_unavailable" not in codes(out)


def test_sc1_lone_pr_targeting_trunk_is_not_in_a_stack(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    out = sb.detect(fixture=gh_fixture([gh_pr(7, "feature", "main")]))
    assert out["in_stack"] is False
    assert out["mode"] == "classic"
    assert [layer["number"] for layer in out["layers"]] == [7]


def test_sc1_trunk_itself_has_no_layers(sb: Sandbox) -> None:
    out = sb.detect(forge="none")
    assert out["in_stack"] is False
    assert out["layers"] == []
    assert out["current_branch"] == "main"


# ---- SC-2: a classic GitHub chain -----------------------------------------


def test_sc2_three_layer_classic_chain_bottom_to_top(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    sb.git("checkout", "-q", "auth-api")
    out = sb.detect(fixture=classic_stack())

    assert out["schema"] == 1
    assert (out["forge"], out["mode"], out["trunk"], out["remote"]) == ("github", "classic", "main", "origin")
    assert out["in_stack"] is True
    assert out["current_branch"] == "auth-api"
    assert out["stack_number"] is None
    assert column(out, "position") == [1, 2, 3]
    assert column(out, "branch") == ["auth-schema", "auth-api", "auth-ui"]
    assert column(out, "base") == ["main", "auth-schema", "auth-api"]
    assert column(out, "number") == [41, 42, 43]
    assert column(out, "state") == ["open", "draft", "draft"]
    assert column(out, "ci") == ["pass", "pass", "fail"]
    assert column(out, "review") == ["approved", "review_required", "review_required"]
    assert column(out, "is_current") == [False, True, False]
    assert column(out, "author") == ["octocat"] * 3
    assert out["layers"][0]["url"] == "https://github.com/acme/app/pull/41"
    assert out["layers"][0]["head_sha"] == f"{41:040x}"
    assert out["merged_parents"] == []
    assert out["warnings"] == []


def test_sc2_detection_is_the_same_from_any_layer(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    from_top = sb.detect("--branch", "auth-ui", fixture=classic_stack())
    from_bottom = sb.detect("--branch", "auth-schema", fixture=classic_stack())
    assert column(from_top, "branch") == column(from_bottom, "branch") == ["auth-schema", "auth-api", "auth-ui"]
    assert column(from_top, "is_current") == [False, False, True]


@pytest.mark.parametrize(
    "rollup, expected",
    [
        ([], "none"),
        ([{"conclusion": "SUCCESS"}, {"conclusion": "NEUTRAL"}, {"conclusion": "SKIPPED"}], "pass"),
        ([{"state": "SUCCESS"}], "pass"),
        ([{"conclusion": "SUCCESS"}, {"status": "IN_PROGRESS", "conclusion": ""}], "pending"),
        ([{"conclusion": "SUCCESS"}, {"conclusion": ""}], "pending"),
        ([{"state": "PENDING"}], "pending"),
        ([{"state": "EXPECTED"}], "pending"),
        ([{"status": "QUEUED", "conclusion": None}], "pending"),
        ([{"conclusion": "FAILURE"}, {"conclusion": "SUCCESS"}], "fail"),
        ([{"conclusion": "CANCELLED"}], "fail"),
        ([{"conclusion": "TIMED_OUT"}], "fail"),
        ([{"conclusion": "ACTION_REQUIRED"}], "fail"),
        ([{"state": "ERROR"}], "fail"),
        ([{"state": "FAILURE"}, {"state": "PENDING"}], "fail"),
    ],
)
def test_ci_rollup_mapping(sb: Sandbox, rollup: list, expected: str) -> None:
    sb.branch("feature", "main")
    out = sb.detect(fixture=gh_fixture([gh_pr(7, "feature", "main", rollup=rollup)]))
    assert out["layers"][0]["ci"] == expected


@pytest.mark.parametrize(
    "decision, expected",
    [
        ("APPROVED", "approved"),
        ("CHANGES_REQUESTED", "changes_requested"),
        ("REVIEW_REQUIRED", "review_required"),
        ("", "none"),
        (None, "none"),
    ],
)
def test_review_decision_mapping(sb: Sandbox, decision: Optional[str], expected: str) -> None:
    sb.branch("feature", "main")
    out = sb.detect(fixture=gh_fixture([gh_pr(7, "feature", "main", review=decision)]))
    assert out["layers"][0]["review"] == expected


def test_github_list_calls_use_the_documented_argv(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    sb.detect(fixture=gh_fixture([gh_pr(7, "feature", "main")]))
    calls = sb.forge_calls()
    assert calls[0] == [
        "gh", "pr", "list", "--state", "open", "--limit", "200", "--json",
        "number,url,headRefName,baseRefName,isDraft,state,reviewDecision,statusCheckRollup,"
        "headRefOid,isCrossRepository,author",
    ]
    assert calls[1] == [
        "gh", "pr", "list", "--state", "merged", "--limit", "100", "--json",
        "number,headRefName,baseRefName,headRefOid,mergeCommit,mergedAt",
    ]


def test_behind_parent_counts_against_the_remote_base(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    sb.git("checkout", "-q", "main")
    sb.commit("trunk-moved.txt", "x\n", "trunk moved")
    sb.git("push", "-q", "origin", "main")
    sb.git("checkout", "-q", "auth-schema")
    sb.commit("schema-extra.txt", "x\n", "schema extra")
    sb.git("push", "-q", "origin", "auth-schema")
    sb.git("checkout", "-q", "auth-api")
    out = sb.detect(fixture=gh_fixture([
        gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema"),
    ]))
    assert column(out, "behind_parent") == [1, 1]


def test_behind_parent_falls_back_to_a_local_base_then_null(sb: Sandbox) -> None:
    sb.branch("unpushed-base", "main", push=False)
    sb.branch("top", "unpushed-base")
    sb.git("checkout", "-q", "unpushed-base")
    sb.commit("extra.txt", "x\n", "extra")
    sb.git("checkout", "-q", "top")
    out = sb.detect(fixture=gh_fixture([gh_pr(9, "top", "unpushed-base")]))
    assert out["layers"][0]["behind_parent"] == 1

    orphan = sb.detect(fixture=gh_fixture([gh_pr(9, "top", "ghost")]))
    assert orphan["layers"][0]["behind_parent"] is None


# ---- SC-3: local ancestry --------------------------------------------------


def test_sc3_local_ancestry_ignores_backup_branches(sb: Sandbox) -> None:
    sb.branch("part-a", "main", push=False)
    sb.branch("part-b", "part-a", push=False)
    sb.branch("part-c", "part-b", commits=2, push=False)
    # a backup sitting between part-b and part-c would be picked as part-c's parent if it counted
    sb.git("branch", "backup/part-c_20261020_141500", "part-c~1")
    out = sb.detect(forge="none")

    assert out["mode"] == "local"
    assert out["in_stack"] is True
    assert column(out, "branch") == ["part-a", "part-b", "part-c"]
    assert column(out, "base") == ["main", "part-a", "part-b"]
    assert column(out, "state") == ["local"] * 3
    assert column(out, "ci") == ["unknown"] * 3
    assert column(out, "review") == ["unknown"] * 3
    assert column(out, "number") == [None] * 3
    assert column(out, "url") == [None] * 3
    assert column(out, "author") == [None] * 3
    assert column(out, "head_sha") == [sb.git("rev-parse", b) for b in ("part-a", "part-b", "part-c")]
    assert out["warnings"] == []


def test_sc3_local_walk_goes_down_and_up_from_the_middle(sb: Sandbox) -> None:
    sb.chain(["part-a", "part-b", "part-c"], push=False)
    out = sb.detect("--branch", "part-b", forge="none")
    assert column(out, "branch") == ["part-a", "part-b", "part-c"]
    assert column(out, "is_current") == [False, True, False]


def test_local_walk_up_stops_at_a_fork(sb: Sandbox) -> None:
    sb.branch("part-a", "main", push=False)
    sb.branch("left", "part-a", push=False)
    sb.git("checkout", "-q", "part-a")
    sb.branch("right", "part-a", push=False)
    out = sb.detect("--branch", "part-a", forge="none")
    assert column(out, "branch") == ["part-a"]
    assert warning(out, "branched_stack")["branches"] == ["left", "right"]


def test_local_mode_skips_branches_already_merged_into_trunk(sb: Sandbox) -> None:
    sb.branch("old-work", "main", push=False)
    sb.git("checkout", "-q", "main")
    sb.git("merge", "-q", "--ff-only", "old-work")
    sb.branch("feature", "main", push=False)
    out = sb.detect(forge="none")
    assert column(out, "branch") == ["feature"]
    assert column(out, "base") == ["main"]


# ---- native detection and gh stack -----------------------------------------


def test_native_mode_when_the_pulls_response_has_a_stack_object(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        api={41: {"stdout": '{"number": 9, "prs": [41, 42]}\n'}},
    )
    out = sb.detect(fixture=fixture)
    assert out["mode"] == "native"
    assert out["stack_number"] == 9
    assert ["gh", "api", "repos/{owner}/{repo}/pulls/41", "--jq", ".stack // empty"] in sb.forge_calls()


def test_native_check_targets_the_bottom_layer_only(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    sb.detect(fixture=classic_stack())
    api_calls = [c for c in sb.forge_calls() if c[:2] == ["gh", "api"]]
    assert [c[2] for c in api_calls] == ["repos/{owner}/{repo}/pulls/41"]


@pytest.mark.parametrize("stdout", ["", "null\n"])
def test_absent_or_null_stack_key_means_classic(sb: Sandbox, stdout: str) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        api={41: {"stdout": stdout}},
    )
    out = sb.detect(fixture=fixture)
    assert out["mode"] == "classic"
    assert out["stack_number"] is None
    assert "forge_unavailable" not in codes(out)


def test_failed_native_call_means_classic_plus_a_warning(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        api={41: {"exit": 1, "stderr": "HTTP 500"}},
    )
    out = sb.detect(fixture=fixture)
    assert out["mode"] == "classic"
    assert out["in_stack"] is True
    assert "forge_unavailable" in codes(out)


def test_ghes_never_runs_native_detection(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        stack_help=0, api={41: {"stdout": '{"number": 9}'}},
    )
    out = sb.detect(fixture=fixture, forge="ghes")
    assert out["forge"] == "ghes"
    assert out["mode"] == "classic"
    assert out["native_available"] is False
    assert [c for c in sb.forge_calls() if c[:2] == ["gh", "api"]] == []


def test_gh_stack_installed_and_native_available(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    prs = [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")]

    installed = sb.detect(fixture=gh_fixture(prs, stack_help=0))
    assert (installed["gh_stack_installed"], installed["native_available"]) == (True, True)

    missing = sb.detect(fixture=gh_fixture(prs, stack_help=1))
    assert (missing["gh_stack_installed"], missing["native_available"]) == (False, False)


def test_cross_fork_layer_blocks_native_and_warns(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    prs = [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema", cross=True)]
    out = sb.detect(fixture=gh_fixture(prs, stack_help=0))
    assert out["gh_stack_installed"] is True
    assert out["native_available"] is False
    assert warning(out, "cross_fork")["branches"] == ["auth-api"]


# ---- SC-4: broken chains ---------------------------------------------------


def test_sc4_base_that_is_a_merged_head_is_a_broken_chain(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(42, "auth-api", "auth-schema")], merged=[gh_merged(41, "auth-schema")],
    )
    out = sb.detect(fixture=fixture)
    assert out["in_stack"] is False
    assert warning(out, "broken_chain")["branches"] == ["auth-api"]
    assert out["merged_parents"] == [{
        "branch": "auth-schema",
        "number": 41,
        "head_sha": f"{41:040x}",
        "merge_sha": f"{1041:040x}",
        "child": "auth-api",
    }]


def test_base_that_exists_nowhere_is_a_broken_chain(sb: Sandbox) -> None:
    sb.branch("auth-api", "main")
    out = sb.detect(fixture=gh_fixture([gh_pr(42, "auth-api", "ghost")]))
    assert "broken_chain" in codes(out)
    assert out["merged_parents"] == []


def test_base_that_is_an_existing_branch_without_a_pr_is_not_broken(sb: Sandbox) -> None:
    sb.chain(["develop", "auth-api"])
    out = sb.detect(fixture=gh_fixture([gh_pr(42, "auth-api", "develop")]))
    assert "broken_chain" not in codes(out)


def test_healthy_chain_reports_no_merged_parents_even_with_merged_history(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        merged=[gh_merged(30, "auth-api")],
    )
    out = sb.detect(fixture=fixture)
    assert out["merged_parents"] == []
    assert "broken_chain" not in codes(out)


# ---- branched stacks, deep stacks ------------------------------------------


def test_branched_stack_stops_at_the_fork(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main")
    sb.branch("auth-api", "auth-schema")
    sb.branch("auth-docs", "auth-schema")
    fixture = gh_fixture([
        gh_pr(41, "auth-schema", "main"),
        gh_pr(42, "auth-api", "auth-schema"),
        gh_pr(43, "auth-docs", "auth-schema"),
    ])
    out = sb.detect("--branch", "auth-schema", fixture=fixture)
    assert column(out, "branch") == ["auth-schema"]
    assert warning(out, "branched_stack")["branches"] == ["auth-api", "auth-docs"]


def test_merged_anchor_reads_the_forge_chain_above_the_merged_head(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    fixture = gh_fixture(
        [gh_pr(42, "auth-api", "auth-schema"), gh_pr(43, "auth-ui", "auth-api")],
        merged=[gh_merged(41, "auth-schema")],
    )
    out = sb.detect("--branch", "auth-schema", fixture=fixture)
    assert out["mode"] == "classic"
    assert column(out, "branch") == ["auth-api", "auth-ui"]
    assert column(out, "is_current") == [False, False]
    assert out["in_stack"] is True
    assert out["merged_parents"] == [{
        "branch": "auth-schema",
        "number": 41,
        "head_sha": f"{41:040x}",
        "merge_sha": f"{1041:040x}",
        "child": "auth-api",
    }]


def test_merged_anchor_with_two_open_children_keeps_forge_mode_and_names_each_child(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main")
    sb.branch("auth-api", "auth-schema")
    sb.branch("auth-docs", "auth-schema")
    fixture = gh_fixture(
        [gh_pr(42, "auth-api", "auth-schema"), gh_pr(43, "auth-docs", "auth-schema")],
        merged=[gh_merged(41, "auth-schema")],
    )
    out = sb.detect("--branch", "auth-schema", fixture=fixture)
    assert out["mode"] == "classic"
    assert out["layers"] == []
    assert out["in_stack"] is False
    assert [(m["branch"], m["number"], m["child"]) for m in out["merged_parents"]] == [
        ("auth-schema", 41, "auth-api"),
        ("auth-schema", 41, "auth-docs"),
    ]
    assert warning(out, "branched_stack")["branches"] == ["auth-api", "auth-docs"]
    assert "broken_chain" not in codes(out)


def test_unpublished_bottom_is_layer_one_above_the_open_prs(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main", push=False)
    sb.branch("auth-api", "auth-schema")
    sb.branch("auth-ui", "auth-api")
    fixture = gh_fixture([gh_pr(42, "auth-api", "auth-schema"), gh_pr(43, "auth-ui", "auth-api")])
    out = sb.detect("--branch", "auth-schema", fixture=fixture)
    assert out["mode"] == "classic"
    assert out["in_stack"] is True
    assert column(out, "branch") == ["auth-schema", "auth-api", "auth-ui"]
    assert column(out, "state") == ["local", "open", "open"]
    assert column(out, "number") == [None, 42, 43]
    assert column(out, "base") == ["main", "auth-schema", "auth-api"]
    assert column(out, "is_current") == [True, False, False]
    assert out["merged_parents"] == []
    assert "broken_chain" not in codes(out)
    assert not any("null" in arg for call in sb.forge_calls() for arg in call)


def test_unpublished_bottom_takes_its_base_from_local_ancestry(sb: Sandbox) -> None:
    sb.branch("develop", "main", push=False)
    sb.branch("auth-schema", "develop", push=False)
    sb.branch("auth-api", "auth-schema")
    out = sb.detect("--branch", "auth-schema", fixture=gh_fixture([gh_pr(42, "auth-api", "auth-schema")]))
    assert column(out, "branch") == ["auth-schema", "auth-api"]
    assert out["layers"][0]["base"] == "develop"


def test_trunk_is_never_an_unpublished_bottom(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main")
    out = sb.detect("--branch", "main", fixture=gh_fixture([gh_pr(41, "auth-schema", "main")]))
    assert out["layers"] == []


def test_unpublished_bottom_on_gitlab_skips_glab_calls_for_the_local_layer(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main", push=False)
    sb.branch("auth-api", "auth-schema")
    fixture = gl_fixture([gl_mr(42, "auth-api", "auth-schema")])
    out = sb.detect("--branch", "auth-schema", fixture=fixture, forge="gitlab")
    assert column(out, "state") == ["local", "open"]
    assert not any("null" in arg for call in sb.forge_calls() for arg in call)


def test_fork_below_the_anchor_is_reported_from_a_child_of_the_fork(sb: Sandbox) -> None:
    sb.branch("auth-schema", "main")
    sb.branch("auth-api", "auth-schema")
    sb.branch("auth-docs", "auth-schema")
    fixture = gh_fixture([
        gh_pr(41, "auth-schema", "main"),
        gh_pr(42, "auth-api", "auth-schema"),
        gh_pr(43, "auth-docs", "auth-schema"),
    ])
    out = sb.detect("--branch", "auth-api", fixture=fixture)
    assert column(out, "branch") == ["auth-schema", "auth-api"]
    assert warning(out, "branched_stack")["branches"] == ["auth-api", "auth-docs"]


def _numbered_chain(sb: Sandbox, count: int) -> dict:
    names = [f"layer-{i}" for i in range(1, count + 1)]
    sb.chain(names)
    prs = [gh_pr(i + 1, name, "main" if i == 0 else names[i - 1]) for i, name in enumerate(names)]
    return gh_fixture(prs)


def test_sc5_deep_stack_warns_at_five_layers_not_four(tmp_path: Path) -> None:
    four = Sandbox(tmp_path / "four")
    out4 = four.detect(fixture=_numbered_chain(four, 4))
    assert len(out4["layers"]) == 4
    assert "deep_stack" not in codes(out4)

    five = Sandbox(tmp_path / "five")
    out5 = five.detect(fixture=_numbered_chain(five, 5))
    assert len(out5["layers"]) == 5
    assert "deep_stack" in codes(out5)


# ---- SC-15: GitLab ---------------------------------------------------------


def _gitlab_chain(sb: Sandbox, count: int, authors: Optional[Sequence[str]] = None, **kwargs) -> dict:
    names = [f"layer-{i}" for i in range(1, count + 1)]
    sb.chain(names)
    mrs = [
        gl_mr(i + 1, name, "main" if i == 0 else names[i - 1], author=(authors or ["octocat"] * count)[i])
        for i, name in enumerate(names)
    ]
    return gl_fixture(mrs, **kwargs)


def test_sc15_gitlab_chain_maps_pipeline_and_approval(sb: Sandbox) -> None:
    fixture = _gitlab_chain(
        sb, 4,
        pipelines={1: "success", 2: "running", 3: "failed", 4: None},
        approved={1: True},
    )
    out = sb.detect(fixture=fixture, forge="gitlab")
    assert (out["forge"], out["mode"], out["in_stack"]) == ("gitlab", "classic", True)
    assert column(out, "branch") == ["layer-1", "layer-2", "layer-3", "layer-4"]
    assert column(out, "number") == [1, 2, 3, 4]
    assert column(out, "ci") == ["pass", "pending", "fail", "none"]
    assert column(out, "review") == ["approved", "review_required", "review_required", "review_required"]
    assert column(out, "state") == ["open"] * 4
    assert out["layers"][0]["url"] == "https://gitlab.com/acme/app/-/merge_requests/1"
    assert out["layers"][0]["head_sha"] == f"{1:040x}"
    assert out["warnings"] == []
    calls = sb.forge_calls()
    assert ["glab", "mr", "list", "-F", "json", "--per-page", "100"] in calls
    assert ["glab", "mr", "list", "-M", "-F", "json", "--per-page", "100"] in calls
    assert ["glab", "mr", "view", "1", "-F", "json"] in calls
    assert ["glab", "api", "projects/:id/merge_requests/1/approvals"] in calls
    assert [c for c in calls if c[:2] == ["gh", "api"]] == []


@pytest.mark.parametrize(
    "status, expected",
    [("canceled", "fail"), ("pending", "pending"), ("created", "pending"), (None, "none")],
)
def test_gitlab_pipeline_status_mapping(sb: Sandbox, status: Optional[str], expected: str) -> None:
    sb.branch("feature", "main")
    fixture = gl_fixture([gl_mr(5, "feature", "main")], pipelines={5: status})
    out = sb.detect(fixture=fixture, forge="gitlab")
    assert out["layers"][0]["ci"] == expected


def test_sc15_retarget_cap_at_five_open_mrs_not_four(tmp_path: Path) -> None:
    four = Sandbox(tmp_path / "four")
    out4 = four.detect(fixture=_gitlab_chain(four, 4), forge="gitlab")
    assert "gitlab_retarget_cap" not in codes(out4)

    five = Sandbox(tmp_path / "five")
    out5 = five.detect(fixture=_gitlab_chain(five, 5), forge="gitlab")
    assert codes(out5) == ["deep_stack", "gitlab_retarget_cap"]


def test_sc15_mixed_authors_warn_and_single_author_does_not(tmp_path: Path) -> None:
    mixed = Sandbox(tmp_path / "mixed")
    out = mixed.detect(fixture=_gitlab_chain(mixed, 3, authors=["ann", "ann", "bob"]), forge="gitlab")
    assert codes(out) == ["gitlab_mixed_authors"]

    same = Sandbox(tmp_path / "same")
    out = same.detect(fixture=_gitlab_chain(same, 3), forge="gitlab")
    assert codes(out) == []


def test_gitlab_merged_parent_falls_back_to_the_squash_sha(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = gl_fixture(
        [gl_mr(42, "auth-api", "auth-schema")],
        merged=[gl_mr(41, "auth-schema", "main", squash_sha="e" * 40)],
    )
    out = sb.detect(fixture=fixture, forge="gitlab")
    assert "broken_chain" in codes(out)
    assert out["merged_parents"][0]["merge_sha"] == "e" * 40
    assert out["merged_parents"][0]["head_sha"] == f"{41:040x}"


def test_gitlab_detail_failure_keeps_the_chain_and_warns(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    fixture = gl_fixture([gl_mr(5, "feature", "main")])
    fixture["glab"] = [e for e in fixture["glab"] if e["argv"][:2] != ["mr", "view"]]
    fixture["glab"].append({"argv": ["mr", "view"], "exit": 1})
    out = sb.detect(fixture=fixture, forge="gitlab")
    assert out["layers"][0]["number"] == 5
    assert out["layers"][0]["ci"] == "unknown"
    assert "forge_unavailable" in codes(out)


# ---- SC-10: CI filters -----------------------------------------------------

FLOW = "on:\n  pull_request:\n    branches: [main]\n"
BLOCK = "on:\n  pull_request:\n    branches:\n      - main\n"
BLOCK_FLUSH = "on:\n  pull_request:\n    branches:\n    - 'main'\n"
IGNORE = "on:\n  pull_request:\n    branches-ignore:\n      - auth-schema\n"
GLOB_SKIPS = "on:\n  pull_request:\n    branches: ['release/**', main]\n"
GLOB_MATCHES = "on:\n  pull_request:\n    branches: ['auth-**', main]\n"
TARGET = "on:\n  pull_request_target:\n    branches: [main]  # trunk only\n"
UNREADABLE_SHAPES = {
    "inline-map": "on: { pull_request: { branches: [main] } }\n",
    "scalar": "on:\n  pull_request:\n    branches: main\n",
    "multiline-flow": "on:\n  pull_request:\n    branches: [main,\n      develop]\n",
    "no-filter": "on:\n  pull_request:\n    types: [opened]\n",
    "bare-trigger": "on: pull_request\n",
    "push-only": "on:\n  push:\n    branches: [main]\n",
    "negation": "on:\n  pull_request:\n    branches: ['!main']\n",
}
WORKFLOW = ".github/workflows/test.yml"


def _write_workflow(sb: Sandbox, text: str, name: str = "test.yml") -> None:
    path = sb.repo / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _filtered_detect(sb: Sandbox, **kwargs) -> dict:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    return sb.detect(fixture=classic_stack(), **kwargs)


@pytest.mark.parametrize("workflow", [FLOW, BLOCK, BLOCK_FLUSH, GLOB_SKIPS, TARGET])
def test_sc10_filter_that_skips_every_non_trunk_base(sb: Sandbox, workflow: str) -> None:
    _write_workflow(sb, workflow)
    out = _filtered_detect(sb)
    found = warning(out, "ci_filter")
    assert found["branches"] == ["auth-api", "auth-ui"]
    assert found["files"] == [WORKFLOW]


def test_sc10_branches_ignore_skips_only_the_ignored_base(sb: Sandbox) -> None:
    _write_workflow(sb, IGNORE)
    out = _filtered_detect(sb)
    assert warning(out, "ci_filter")["branches"] == ["auth-api"]


def test_sc10_a_matching_glob_means_no_warning(sb: Sandbox) -> None:
    _write_workflow(sb, GLOB_MATCHES)
    assert "ci_filter" not in codes(_filtered_detect(sb))


@pytest.mark.parametrize("shape", sorted(UNREADABLE_SHAPES))
def test_sc10_a_shape_the_scan_cannot_read_gives_no_warning(sb: Sandbox, shape: str) -> None:
    _write_workflow(sb, UNREADABLE_SHAPES[shape])
    assert "ci_filter" not in codes(_filtered_detect(sb))


def test_sc10_quoted_flow_entry_with_a_comma_is_one_pattern(sb: Sandbox) -> None:
    _write_workflow(sb, "on:\n  pull_request:\n    branches: ['feature,a']\n")
    assert sb.detect("--check-ci", "feature,a", forge=None)["skipped"] == []
    assert sb.detect("--check-ci", "feature", forge=None)["skipped"] == [
        {"base": "feature", "files": [WORKFLOW]}
    ]


@pytest.mark.parametrize("entries", ["'a\\'b", "\"a\\\"b\"", "'a' b", "'a''b'", "a'b"])
def test_sc10_a_quoted_entry_it_cannot_split_safely_gives_no_warning(sb: Sandbox, entries: str) -> None:
    _write_workflow(sb, f"on:\n  pull_request:\n    branches: [{entries}, main]\n")
    assert sb.detect("--check-ci", "auth-schema", forge=None)["skipped"] == []


def test_sc10_block_entry_with_an_escape_is_unreadable_and_gives_no_warning(sb: Sandbox) -> None:
    _write_workflow(sb, 'on:\n  pull_request:\n    branches:\n      - "auth\\u002dschema"\n')
    assert sb.detect("--check-ci", "auth-schema", forge=None)["skipped"] == []


@pytest.mark.parametrize("entry", ["'a''b'", "\"a\\\"b\"", "'a' b", "a'b"])
def test_sc10_a_block_entry_it_cannot_decode_safely_gives_no_warning(sb: Sandbox, entry: str) -> None:
    _write_workflow(sb, f"on:\n  pull_request:\n    branches:\n      - {entry}\n")
    assert sb.detect("--check-ci", "auth-schema", forge=None)["skipped"] == []


@pytest.mark.parametrize("entry", ['"main"', "'main'"])
def test_sc10_a_simple_quoted_block_entry_is_unquoted_before_matching(sb: Sandbox, entry: str) -> None:
    _write_workflow(sb, f"on:\n  pull_request:\n    branches:\n      - {entry}\n")
    assert sb.detect("--check-ci", "auth-schema", "main", forge=None)["skipped"] == [
        {"base": "auth-schema", "files": [WORKFLOW]}
    ]


HEREDOC = (
    "name: Push only\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
    "      - run: |\n          cat <<'EOF'\n          pull_request:\n            branches: [main]\n"
    "          EOF\n"
)


@pytest.mark.parametrize("workflow", [
    HEREDOC,
    "on:\n  push:\n    branches: [main]\njobs:\n  build:\n    steps:\n      - run: |\n"
    "          pull_request:\n            branches: [main]\n",
    "on:\n  push:\n    branches: [main]\n  workflow_dispatch:\n    inputs:\n      note:\n"
    "        description: |\n          pull_request:\n            branches: [main]\n",
    "pull_request:\n  branches: [main]\n",
    "on: pull_request\n",
    "on: [pull_request, push]\n",
    "on:\n  - pull_request\n  - push\n",
])
def test_sc10_pull_request_text_outside_the_on_block_is_never_a_trigger(sb: Sandbox, workflow: str) -> None:
    _write_workflow(sb, workflow)
    assert "ci_filter" not in codes(_filtered_detect(sb))
    assert sb.detect("--check-ci", "auth-schema", forge=None)["skipped"] == []


def test_sc10_a_real_trigger_still_warns_next_to_a_heredoc_decoy(sb: Sandbox) -> None:
    _write_workflow(sb, FLOW + "jobs:\n  build:\n    steps:\n      - run: echo hi\n")
    assert warning(_filtered_detect(sb), "ci_filter")["branches"] == ["auth-api", "auth-ui"]
    assert sb.detect("--check-ci", "auth-schema", forge=None)["skipped"] == [
        {"base": "auth-schema", "files": [WORKFLOW]}
    ]


def test_sc10_files_lists_every_skipping_workflow_sorted(sb: Sandbox) -> None:
    _write_workflow(sb, FLOW, "b.yaml")
    _write_workflow(sb, BLOCK, "a.yml")
    _write_workflow(sb, GLOB_MATCHES, "c.yml")
    out = _filtered_detect(sb)
    assert warning(out, "ci_filter")["files"] == [".github/workflows/a.yml", ".github/workflows/b.yaml"]


def test_sc10_every_trigger_in_a_file_must_skip_the_base(sb: Sandbox) -> None:
    _write_workflow(sb, "on:\n  pull_request:\n    branches: [main]\n  pull_request_target:\n    types: [opened]\n")
    assert "ci_filter" not in codes(_filtered_detect(sb))


def test_sc10_no_warning_for_native_none_gitlab_or_no_workflows(tmp_path: Path) -> None:
    clean = Sandbox(tmp_path / "clean")
    assert "ci_filter" not in codes(_filtered_detect(clean))

    native = Sandbox(tmp_path / "native")
    _write_workflow(native, FLOW)
    native.chain(["auth-schema", "auth-api"])
    fixture = gh_fixture(
        [gh_pr(41, "auth-schema", "main"), gh_pr(42, "auth-api", "auth-schema")],
        api={41: {"stdout": '{"number": 3}'}},
    )
    assert "ci_filter" not in codes(native.detect(fixture=fixture))

    none = Sandbox(tmp_path / "none")
    _write_workflow(none, FLOW)
    none.chain(["auth-schema", "auth-api"], push=False)
    assert "ci_filter" not in codes(none.detect(forge="none"))

    gitlab = Sandbox(tmp_path / "gitlab")
    _write_workflow(gitlab, FLOW)
    assert "ci_filter" not in codes(gitlab.detect(fixture=_gitlab_chain(gitlab, 3), forge="gitlab"))


def test_sc10_check_ci_reports_skipped_planned_bases(sb: Sandbox) -> None:
    _write_workflow(sb, FLOW)
    _write_workflow(sb, IGNORE, "ignore.yml")
    out = sb.detect("--check-ci", "auth-schema", "main", "auth-api", forge=None)
    assert out == {
        "schema": 1,
        "skipped": [
            {"base": "auth-schema", "files": [".github/workflows/ignore.yml", WORKFLOW]},
            {"base": "auth-api", "files": [WORKFLOW]},
        ],
    }
    assert sb.forge_calls() == []


def test_sc10_check_ci_with_no_workflows_or_no_skips_is_empty(sb: Sandbox) -> None:
    assert sb.detect("--check-ci", "auth-schema", forge=None) == {"schema": 1, "skipped": []}
    _write_workflow(sb, GLOB_MATCHES)
    assert sb.detect("--check-ci", "auth-schema", forge=None) == {"schema": 1, "skipped": []}


def test_sc10_check_ci_works_outside_a_plain_branch_context(sb: Sandbox) -> None:
    _write_workflow(sb, FLOW)
    sb.git("checkout", "-q", "--detach")
    out = sb.detect("--check-ci", "auth-schema", forge=None)
    assert out["skipped"] == [{"base": "auth-schema", "files": [WORKFLOW]}]


# ---- SC-12: other worktrees ------------------------------------------------


def test_sc12_layer_checked_out_in_another_worktree(sb: Sandbox, tmp_path: Path) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    sb.git("checkout", "-q", "auth-api")
    other = tmp_path / "wt-ui"
    sb.git("worktree", "add", "-q", str(other), "auth-ui")
    out = sb.detect(fixture=classic_stack())

    worktrees = column(out, "worktree")
    assert worktrees[:2] == [None, None]
    assert Path(worktrees[2]).resolve() == other.resolve()
    assert warning(out, "layer_in_other_worktree")["branches"] == ["auth-ui"]


def test_sc12_the_current_worktree_is_not_reported(sb: Sandbox, tmp_path: Path) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    sb.git("checkout", "-q", "main")
    other = tmp_path / "wt-schema"
    sb.git("worktree", "add", "-q", str(other), "auth-schema")
    out = sb.detect(fixture=classic_stack(), cwd=other)
    assert out["layers"][0]["worktree"] is None
    assert "layer_in_other_worktree" not in codes(out)


# ---- forge unavailable -----------------------------------------------------


def test_failing_list_call_degrades_to_local_with_a_warning(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    fixture = {"gh": [{"argv": ["pr", "list"], "exit": 4, "stderr": "gh auth login"}]}
    result = sb.run(fixture=fixture)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["mode"] == "local"
    assert out["forge"] == "github"
    assert codes(out) == ["forge_unavailable"]
    assert column(out, "branch") == ["auth-schema", "auth-api"]
    assert column(out, "ci") == ["unknown", "unknown"]


def test_unparseable_list_output_degrades_to_local(sb: Sandbox) -> None:
    sb.branch("feature", "main")
    fixture = {"gh": [{"argv": ["pr", "list"], "stdout": "not json"}]}
    out = sb.detect(fixture=fixture)
    assert out["mode"] == "local"
    assert "forge_unavailable" in codes(out)


def test_gh_not_installed_degrades_to_local(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    out = sb.detect(fixture=classic_stack(), tools=("glab",), restricted=())
    assert out["mode"] == "local"
    assert out["gh_stack_installed"] is False
    assert out["native_available"] is False
    assert codes(out) == ["forge_unavailable"]
    assert [c for c in sb.forge_calls() if c[0] == "gh"] == []


def test_glab_not_installed_degrades_to_local(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api"])
    out = sb.detect(fixture=gl_fixture(), forge="gitlab", tools=("gh",), restricted=())
    assert out["mode"] == "local"
    assert codes(out) == ["forge_unavailable"]


# ---- invariants ------------------------------------------------------------

MUTATING_TOKENS = {"merge", "edit", "create", "close", "reopen", "ready", "comment", "review",
                   "delete", "update", "link", "push", "rebase", "-X", "--method", "-f", "--field"}


def test_stack_sh_never_writes(sb: Sandbox, tmp_path: Path) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    sb.git("checkout", "-q", "auth-api")
    sb.git("worktree", "add", "-q", str(tmp_path / "wt-ui"), "auth-ui")
    _write_workflow(sb, FLOW)
    before = sb.snapshot()
    scenarios = [
        dict(fixture=classic_stack()),
        dict(fixture=classic_stack(), forge="ghes"),
        dict(fixture=gl_fixture(), forge="gitlab"),
        dict(forge="none"),
    ]
    for kwargs in scenarios:
        assert sb.run(**kwargs).returncode == 0
        calls = sb.forge_calls()
        assert sb.run("--check-ci", "auth-schema", forge=None).returncode == 0
        assert sb.snapshot() == before
        for call in calls:
            assert MUTATING_TOKENS.isdisjoint(call[1:]), call
            if call[1] == "api":
                assert "-X" not in call and "--method" not in call


def test_output_is_deterministic(sb: Sandbox) -> None:
    sb.chain(["auth-schema", "auth-api", "auth-ui"])
    first = sb.run(fixture=classic_stack()).stdout
    second = sb.run(fixture=classic_stack()).stdout
    assert first == second


def test_stdout_is_a_single_json_document_and_warnings_follow_the_code_order(sb: Sandbox, tmp_path: Path) -> None:
    names = [f"layer-{i}" for i in range(1, 6)]
    sb.chain(names)
    sb.git("checkout", "-q", "layer-1")
    sb.git("worktree", "add", "-q", str(tmp_path / "wt"), "layer-5")
    _write_workflow(sb, FLOW)
    prs = [gh_pr(i + 1, name, "auth-merged" if i == 0 else names[i - 1], cross=(i == 2)) for i, name in enumerate(names)]
    fixture = gh_fixture(
        prs, merged=[gh_merged(40, "auth-merged")], stack_help=0,
        api={1: {"exit": 1, "stderr": "boom"}},
    )
    result = sb.run("--branch", "layer-3", fixture=fixture)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert codes(out) == [
        "forge_unavailable", "broken_chain", "deep_stack", "cross_fork", "ci_filter", "layer_in_other_worktree",
    ]
    assert out["native_available"] is False
