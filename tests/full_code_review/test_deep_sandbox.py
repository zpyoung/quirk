import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import deep_sandbox as m


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def repository(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    (repo / "data.txt").write_text("head\n", encoding="utf-8")
    (repo / "nested").mkdir()
    (repo / "nested" / "value.txt").write_text("nested\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "head")
    return repo, git(repo, "rev-parse", "HEAD")


def invoke(*args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = m.main(list(args))
    return code, json.loads(output.getvalue())


@pytest.mark.parametrize("seat, fork, trusted, access, allowed, reason", [
    ("author", None, None, "author-worktree", True, None),
    ("reviewer", False, True, "reviewer-worktree", True, None),
    ("reviewer", True, True, "reviewer-worktree", False, "fork"),
    ("reviewer", None, True, "reviewer-worktree", False, "fork"),
    ("reviewer", False, False, "reviewer-worktree", False, "trusted"),
    ("reviewer", False, None, "reviewer-worktree", False, "trusted"),
    ("author", None, None, "diff-only", False, "diff-only"),
])
def test_trust_requires_trusted_source_and_prompts_only_when_allowed(
        seat, fork, trusted, access, allowed, reason):
    decision = m.evaluate_trust({"seat": seat, "change": {
        "is_fork": fork, "author_trusted": trusted}}, access)
    assert decision == {"allowed": allowed, "prompt_required": allowed,
                        "reason": None if allowed else decision["reason"]}
    if reason:
        assert reason in decision["reason"]


def test_check_trust_cli_writes_decision(tmp_path):
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"seat": "author", "change": {}}), encoding="utf-8")
    out = tmp_path / "trust.json"
    code, decision = invoke("check-trust", "--context", str(context), "--out", str(out))
    assert code == 0
    assert decision == {"allowed": True, "prompt_required": True, "reason": None}
    assert json.loads(out.read_text(encoding="utf-8")) == decision


def test_probe_capabilities_runs_exact_platform_probes(tmp_path, monkeypatch):
    calls = []
    real_run = subprocess.run

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    monkeypatch.setattr(m.sys, "platform", "darwin")
    assert m.probe_capabilities(str(tmp_path))["sandbox_kind"] == "sandbox-exec"
    assert calls == [["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)",
                      "/usr/bin/true"]]
    calls.clear()
    monkeypatch.setattr(m.sys, "platform", "linux")
    monkeypatch.setattr(m.shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else None)
    assert m.probe_capabilities(str(tmp_path))["sandbox_kind"] == "bwrap"
    assert calls == [["/usr/bin/bwrap", "--ro-bind", "/", "/", "--dev", "/dev",
                      "--proc", "/proc", "/bin/true"]]
    monkeypatch.setattr(m.subprocess, "run", real_run)


def test_failed_probe_falls_back_to_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr(m.sys, "platform", "linux")
    monkeypatch.setattr(m.shutil, "which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 1))
    assert m.probe_capabilities(str(tmp_path))["sandbox_kind"] == "worktree"


def test_worktree_lifecycle_isolates_hooks_environment_and_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(m.sys, "platform", "linux")
    repo, sha = repository(tmp_path)
    hook_marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "post-checkout"
    hook.write_text("#!/bin/sh\nprintf ran > '" + str(hook_marker) + "'\n", encoding="utf-8")
    hook.chmod(0o755)
    before_config = (repo / ".git" / "config").read_bytes()
    before_status = git(repo, "status", "--porcelain")
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("GIT_ASKPASS", "/private/askpass")
    manifest_path = tmp_path / "copy.json"
    code, manifest = invoke("acquire", "--source-root", str(repo), "--head-sha", sha,
                            "--out", str(manifest_path))
    assert code == 0 and json.loads(manifest_path.read_text()) == manifest
    assert manifest["copy_kind"] == "git-worktree"
    copy_dir, env_dir = Path(manifest["copy_dir"]), Path(manifest["env_dir"])
    try:
        assert str(copy_dir) == os.path.realpath(copy_dir)
        assert str(env_dir) == os.path.realpath(env_dir)
        assert copy_dir != repo and (copy_dir / "data.txt").read_text() == "head\n"
        assert git(copy_dir, "rev-parse", "HEAD") == sha
        assert not hook_marker.exists()
        cmd = [sys.executable, "-c", "import json,os; print(json.dumps({k:os.environ.get(k) "
               "for k in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME',"
               "'TMPDIR','GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM','GIT_TERMINAL_PROMPT',"
               "'GH_TOKEN','GIT_ASKPASS','PATH')}))"]
        code, result = invoke("exec", "--manifest", str(manifest_path), "--cwd", "nested",
                              "--", *cmd)
        assert code == 0 and result["exit_code"] == 0
        values = json.loads(result["stdout"])
        for name, path in (("HOME", "home"), ("XDG_CONFIG_HOME", "xdg_config"),
                           ("XDG_STATE_HOME", "xdg_state"), ("XDG_CACHE_HOME", "xdg_cache"),
                           ("TMPDIR", "tmp")):
            assert values[name] == str(env_dir / path)
            assert (env_dir / path).is_dir()
        assert values["GH_TOKEN"] is None and values["GIT_ASKPASS"] is None
        assert values["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert values["GIT_CONFIG_NOSYSTEM"] == "1"
        assert values["GIT_TERMINAL_PROMPT"] == "0"
        assert values["PATH"].split(os.pathsep)[0] == str(env_dir / "bin")
        code, hooks = invoke("exec", "--manifest", str(manifest_path), "--",
                             "git", "config", "--get", "core.hooksPath")
        assert code == 0 and hooks["stdout"].strip() == "/dev/null"
        code, checkout = invoke("exec", "--manifest", str(manifest_path), "--",
                                "git", "switch", "--detach", "HEAD")
        assert code == 0 and checkout["exit_code"] == 0 and not hook_marker.exists()
        for executable in ("gh", "glab"):
            code, blocked = invoke("exec", "--manifest", str(manifest_path), "--", executable)
            assert code == 0 and blocked["exit_code"] == 127
            assert "blocked in deep-mode throwaway copy" in blocked["stderr"]
            assert blocked["environment_unavailable"] is False
        code, missing = invoke("exec", "--manifest", str(manifest_path), "--",
                               sys.executable, "-c", "import nonexistent_deep_dependency")
        assert code == 0 and missing["environment_unavailable"] is True
        assert "ModuleNotFoundError" in missing["unavailable_reason"]
        code, not_found = invoke("exec", "--manifest", str(manifest_path), "--",
                                 "nonexistent-deep-executable")
        assert code == 0 and not_found["exit_code"] == 127
        assert not_found["environment_unavailable"] is True
        assert not_found["unavailable_reason"]
        assert (repo / ".git" / "config").read_bytes() == before_config
        assert git(repo, "status", "--porcelain") == before_status
        assert not hook_marker.exists()
    finally:
        code, released = invoke("release", "--manifest", str(manifest_path))
        assert code == 0 and released == {"released": True, "copy_dir": str(copy_dir)}
        assert not copy_dir.exists() and not env_dir.exists()



@pytest.mark.parametrize("clone_supported", [True, False])
def test_mac_clone_attempt_and_fallback_leave_source_git_config_untouched(
        tmp_path, monkeypatch, clone_supported):
    repo, sha = repository(tmp_path)
    hook = repo / ".git" / "hooks" / "post-checkout"
    hook.write_text("#!/bin/sh\nexit 44\n", encoding="utf-8")
    hook.chmod(0o755)
    original_config = (repo / ".git" / "config").read_bytes()
    monkeypatch.setattr(m.sys, "platform", "darwin")
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    real_run = subprocess.run
    cp_calls = []

    def clone_or_fail(args, **kwargs):
        if args[0] == "cp":
            cp_calls.append(args)
            if not clone_supported:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="clone not supported")
            shutil.copytree(args[2], args[3], dirs_exist_ok=True, symlinks=True)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return real_run(args, **kwargs)

    monkeypatch.setattr(m.subprocess, "run", clone_or_fail)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    copy = Path(manifest["copy_dir"])
    try:
        assert cp_calls == [["cp", "-cR", os.path.join(str(repo), "."), str(copy)]]
        assert manifest["copy_kind"] == ("clonefile" if clone_supported else "git-worktree")
        assert (copy / "data.txt").read_text() == "head\n"
        if clone_supported:
            assert not (copy / ".git" / "hooks").exists()
            assert git(copy, "config", "--file", str(copy / ".git" / "config"),
                       "--get", "core.hooksPath") == "/dev/null"
            assert git(copy, "config", "--file", str(copy / ".git" / "config"),
                       "--get", "core.fsmonitor") == "false"
        assert (repo / ".git" / "config").read_bytes() == original_config
        assert hook.exists()
    finally:
        m.release_copy(str(out))
        assert not copy.exists() and not Path(manifest["env_dir"]).exists()


def test_kernel_sandbox_denies_outside_writes_when_available(tmp_path):
    kind = m.probe_capabilities(str(tmp_path))["sandbox_kind"]
    if kind == "worktree":
        pytest.skip("no functioning OS write sandbox on this machine")
    repo, sha = repository(tmp_path)
    outside = tmp_path / "outside.txt"
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        assert manifest["sandbox_kind"] == kind
        for target, expected in ((outside, 1), (Path(manifest["copy_dir"]) / "inside.txt", 0),
                                 (Path(manifest["env_dir"]) / "inside.txt", 0)):
            result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                    "from pathlib import Path; Path(%r).write_text('check')"
                                    % str(target)])
            assert (result["exit_code"] == 0) == (expected == 0)
            assert target.exists() == (expected == 0)
    finally:
        m.release_copy(str(out))

def test_exec_rejects_symlink_and_parent_directory_traversal(tmp_path, monkeypatch):
    repo, sha = repository(tmp_path)
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    copy = Path(manifest["copy_dir"])
    (copy / "outside").symlink_to(tmp_path, target_is_directory=True)
    try:
        for cwd in ("..", "nested/../", "outside", str(tmp_path)):
            code, error = invoke("exec", "--manifest", str(out), "--cwd", cwd,
                                 "--", sys.executable, "-c", "print('bad')")
            assert code == 2 and "error" in error
    finally:
        m.release_copy(str(out))


def test_invalid_head_and_missing_manifest_are_json_errors(tmp_path):
    repo, sha = repository(tmp_path)
    output = tmp_path / "copy.json"
    for invalid_sha in ("not-a-sha", "a" * 40):
        code, result = invoke("acquire", "--source-root", str(repo), "--head-sha", invalid_sha,
                              "--out", str(output))
        assert code == 2 and "error" in result and not output.exists()
    for args in (("release", "--manifest", str(output)),
                 ("exec", "--manifest", str(output), "--", "true"),
                 ("exec", "--manifest", str(output), "--"),
                 ("acquire", "--source-root", str(repo))):
        code, result = invoke(*args)
        assert code == 2 and "error" in result


def test_exec_timeout_returns_structured_result(tmp_path, monkeypatch):
    repo, sha = repository(tmp_path)
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    manifest_path = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(manifest_path))
    try:
        result = m.exec_in_copy(str(manifest_path),
                                [sys.executable, "-c", "import time; time.sleep(3)"], timeout=1)
        assert result["timed_out"] is True and result["exit_code"] != 0
        assert result["environment_unavailable"] is False
    finally:
        m.release_copy(str(manifest_path))


def test_sandbox_exec_profile_limits_writes_to_copy_and_env(tmp_path, monkeypatch):
    repo, sha = repository(tmp_path)
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    manifest["sandbox_kind"] = "sandbox-exec"
    out.write_text(json.dumps(manifest), encoding="utf-8")
    observed = []

    def fake_run(args, **kwargs):
        observed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    try:
        result = m.exec_in_copy(str(out), ["/bin/echo", "ok"])
        assert result["stdout"] == "ok"
        cmd = observed[0]
        assert cmd[:2] == ["/usr/bin/sandbox-exec", "-p"]
        profile = cmd[2]
        assert "(deny file-write*)" in profile
        for path in (manifest["copy_dir"], manifest["env_dir"]):
            assert '(subpath "' + path + '")' in profile
        assert '(literal "/dev/null")' in profile
        assert cmd[3:] == ["/bin/echo", "ok"]
    finally:
        monkeypatch.undo()
        m.release_copy(str(out))


def test_bwrap_mounts_only_copy_and_env_writable(tmp_path, monkeypatch):
    repo, sha = repository(tmp_path)
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})
    monkeypatch.setattr(m.shutil, "which", lambda name: "/usr/bin/bwrap")
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    manifest["sandbox_kind"] = "bwrap"
    out.write_text(json.dumps(manifest), encoding="utf-8")
    observed = []

    def fake_run(args, **kwargs):
        observed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    try:
        assert m.exec_in_copy(str(out), ["/bin/echo", "ok"])["exit_code"] == 0
        cmd = observed[0]
        assert "--ro-bind" in cmd and "--dev" in cmd and "--proc" in cmd
        for path in (manifest["copy_dir"], manifest["env_dir"]):
            assert ["--bind", path, path] == cmd[cmd.index(path) - 1:cmd.index(path) + 2]
    finally:
        monkeypatch.undo()
        m.release_copy(str(out))
