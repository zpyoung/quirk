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
                          text=True, check=True, env=m._git_environment()).stdout.strip()


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


def fallback(monkeypatch):
    monkeypatch.setattr(m, "probe_capabilities", lambda root: {"sandbox_kind": "worktree"})


def test_failed_probe_reports_environment_only_limitation(tmp_path, monkeypatch):
    monkeypatch.setattr(m.sys, "platform", "unsupported")
    capability = m.probe_capabilities(str(tmp_path))
    assert capability["sandbox_kind"] == "worktree"
    assert capability["os_enforced"] is False
    assert "not enforced" in capability["isolation_warning"]


def test_copy_has_private_git_metadata_and_sanitized_environment(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    original_config = (repo / ".git" / "config").read_bytes()
    for name in ("GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "CUSTOM_SECRET",
                 "SSH_AUTH_SOCK", "PYTHONPATH", "LD_PRELOAD", "GIT_CONFIG_PARAMETERS"):
        monkeypatch.setenv(name, "caller-secret")
    out = tmp_path / "copy.json"
    code, manifest = invoke("acquire", "--source-root", str(repo), "--head-sha", sha,
                            "--out", str(out))
    assert code == 0
    copy = Path(manifest["copy_dir"])
    env_dir = Path(manifest["env_dir"])
    try:
        assert manifest["copy_kind"] == "independent-copy"
        assert manifest["source_state"]["local_changes"] is False
        assert (copy / ".git").is_dir()
        assert not (copy / ".git" / "objects" / "info" / "alternates").exists()
        assert git(copy, "rev-parse", "HEAD") == sha
        assert git(copy, "rev-parse", "--git-common-dir") == ".git"
        result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                "import json,os;print(json.dumps(dict(os.environ)))"],
                                cwd_rel="nested")
        values = json.loads(result["stdout"])
        assert result["exit_code"] == 0
        for name in ("GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "CUSTOM_SECRET",
                     "SSH_AUTH_SOCK", "PYTHONPATH", "LD_PRELOAD", "GIT_CONFIG_PARAMETERS"):
            assert name not in values
        for name, suffix in m._ENV_DIRS.items():
            assert values[name] == str(env_dir / suffix)
        assert values["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert values["GIT_CONFIG_NOSYSTEM"] == "1"
        assert values["PATH"].split(os.pathsep)[0] == str(env_dir / "bin")
        assert result["os_enforced"] is False and result["isolation_warning"]
        git(copy, "config", "caller.proof", "isolated")
        git(copy, "update-ref", "refs/heads/private-copy", sha)
        assert (repo / ".git" / "config").read_bytes() == original_config
        assert not (repo / ".git" / "refs" / "heads" / "private-copy").exists()
        for command in (["gh"], ["glab"], ["/some/absolute/gh"]):
            blocked = m.exec_in_copy(str(out), command)
            assert blocked["exit_code"] == 127
            assert blocked["environment_unavailable"] is False
            assert "blocked in deep-mode" in blocked["stderr"]
    finally:
        released = m.release_copy(str(out))
        assert released == {"released": True, "copy_dir": str(copy)}
        assert not copy.exists() and not env_dir.exists()
        assert m.release_copy(str(out)) == released


def test_acquire_never_runs_source_fsmonitor_filters_hooks_or_config_includes(
        tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    marker = tmp_path / "executed"
    program = tmp_path / "unsafe"
    program.write_text("#!/bin/sh\nprintf ran >> '%s'\ncat\n" % marker, encoding="utf-8")
    program.chmod(0o755)
    included = tmp_path / "included.config"
    included.write_text("[core]\n\tfsmonitor = %s\n[filter \"unsafe\"]\n"
                        "\tclean = %s\n\tsmudge = %s\n\trequired = true\n"
                        % (program, program, program), encoding="utf-8")
    git(repo, "config", "include.path", str(included))
    git(repo, "config", "core.hooksPath", str(tmp_path / "hooks"))
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "post-checkout").write_text(program.read_text(), encoding="utf-8")
    (hooks / "post-checkout").chmod(0o755)
    (repo / ".gitattributes").write_text("*.txt filter=unsafe\n", encoding="utf-8")
    (repo / "data.txt").write_text("local\n", encoding="utf-8")
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        copy = Path(manifest["copy_dir"])
        assert not marker.exists()
        assert (copy / "data.txt").read_text() == "local\n"
        assert str(included) not in (copy / ".git" / "config").read_text()
        assert str(program) not in (copy / ".git" / "config").read_text()
        result = m.exec_in_copy(str(out), ["git", "status", "--porcelain"])
        assert result["exit_code"] == 0 and not marker.exists()
        result = m.exec_in_copy(str(out), ["git", "switch", "--detach", "HEAD"])
        assert result["exit_code"] == 0 and not marker.exists()
    finally:
        m.release_copy(str(out))


def test_snapshot_reports_local_changes_without_claiming_exact_head_tree(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    (repo / "data.txt").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "data.txt")
    (repo / "data.txt").write_text("unstaged\n", encoding="utf-8")
    (repo / "new.txt").write_text("untracked\n", encoding="utf-8")
    (repo / "nested" / "value.txt").unlink()
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        copy = Path(manifest["copy_dir"])
        assert git(copy, "rev-parse", "HEAD") == sha
        assert git(copy, "show", "HEAD:data.txt") == "head"
        assert (copy / "data.txt").read_text() == "unstaged\n"
        assert (copy / "new.txt").read_text() == "untracked\n"
        assert not (copy / "nested" / "value.txt").exists()
        assert manifest["source_state"] == {
            "kind": "worktree-snapshot", "local_changes": True,
            "index": "rebuilt-from-head"}
    finally:
        m.release_copy(str(out))


def test_staged_changes_are_reported_even_when_worktree_matches_head(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    (repo / "data.txt").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "data.txt")
    (repo / "data.txt").write_text("head\n", encoding="utf-8")
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        assert manifest["source_state"]["local_changes"] is True
        assert manifest["source_state"]["index"] == "rebuilt-from-head"
        assert Path(manifest["copy_dir"], "data.txt").read_text() == "head\n"
    finally:
        m.release_copy(str(out))


def test_linked_source_worktree_does_not_keep_caller_git_pointers(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "--detach", str(linked), sha)
    (linked / "data.txt").write_text("linked local\n", encoding="utf-8")
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(linked), sha, str(out))
    try:
        copy = Path(manifest["copy_dir"])
        assert (copy / ".git").is_dir()
        assert not (copy / ".git" / "commondir").exists()
        assert not (copy / ".git" / "objects" / "info" / "alternates").exists()
        assert (copy / "data.txt").read_text() == "linked local\n"
        assert git(copy, "rev-parse", "HEAD") == sha
    finally:
        m.release_copy(str(out))


@pytest.mark.parametrize("clone_supported", [True, False])
def test_clonefile_snapshot_or_fallback_excludes_source_git_metadata(
        tmp_path, monkeypatch, clone_supported):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    original_config = (repo / ".git" / "config").read_bytes()
    monkeypatch.setattr(m.sys, "platform", "darwin")
    real_run = m._run
    clone_attempts = []

    def copy_or_fail(command, timeout, **kwargs):
        if command[0] == "/bin/cp":
            source, destination = Path(command[2]), Path(command[3])
            clone_attempts.append(source.name)
            if not clone_supported:
                return subprocess.CompletedProcess(command, 1, "", "clone unavailable")
            if source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
            else:
                shutil.copy2(source, destination)
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, timeout, **kwargs)

    monkeypatch.setattr(m, "_run", copy_or_fail)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        assert clone_attempts and ".git" not in clone_attempts
        assert manifest["snapshot_kind"] == ("clonefile" if clone_supported else "copy")
        assert Path(manifest["copy_dir"], "data.txt").read_text() == "head\n"
        assert (repo / ".git" / "config").read_bytes() == original_config
        assert not Path(manifest["copy_dir"], ".git", "objects", "info", "alternates").exists()
    finally:
        m.release_copy(str(out))


def test_kernel_sandbox_denies_outside_writes_credentials_and_absolute_forge_exec(
        tmp_path, monkeypatch):
    kind = m.probe_capabilities(str(tmp_path))["sandbox_kind"]
    if kind == "worktree":
        pytest.skip("no functioning OS sandbox on this machine")
    repo, sha = repository(tmp_path)
    credentials = tmp_path / "caller-home" / ".aws" / "credentials"
    credentials.parent.mkdir(parents=True)
    credentials.write_text("caller-secret", encoding="utf-8")
    forge_dir = tmp_path / "forge-bin"
    forge_dir.mkdir()
    forge = forge_dir / "gh"
    forge.write_text("#!/bin/sh\nprintf 'should not execute'\n", encoding="utf-8")
    forge.chmod(0o755)
    monkeypatch.setenv("HOME", str(credentials.parent.parent))
    monkeypatch.setenv("PATH", str(forge_dir) + os.pathsep + os.environ["PATH"])
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        assert manifest["sandbox_kind"] == kind
        outside = tmp_path / "outside"
        result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                "from pathlib import Path;Path(%r).write_text('bad')" % str(outside)])
        assert result["exit_code"] != 0 and not outside.exists()
        result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                "from pathlib import Path;print(Path(%r).read_text())"
                                % str(credentials)])
        assert result["exit_code"] != 0 and "caller-secret" not in result["stdout"]
        result = m.exec_in_copy(str(out), ["/bin/sh", "-c", str(forge)])
        assert result["exit_code"] != 0
        assert "should not execute" not in result["stdout"]
        inside = Path(manifest["copy_dir"]) / "inside"
        result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                "from pathlib import Path;Path(%r).write_text('ok')" % str(inside)])
        assert result["exit_code"] == 0 and inside.read_text() == "ok"
    finally:
        m.release_copy(str(out))


def test_kernel_sandbox_hides_unlisted_home_files_and_credential_sockets(
        tmp_path, monkeypatch):
    import socket
    import tempfile

    kind = m.probe_capabilities(str(tmp_path))["sandbox_kind"]
    if kind == "worktree":
        pytest.skip("no functioning OS sandbox on this machine")
    repo, sha = repository(tmp_path)
    home = tmp_path / "caller-home"
    home.mkdir()
    for name in (".zshrc", ".claude.json", ".zsh_history"):
        (home / name).write_text("caller-secret", encoding="utf-8")
    socket_dir = Path(tempfile.mkdtemp(prefix="agent"))
    agent, other = str(socket_dir / "agent.sock"), str(socket_dir / "other.sock")
    servers = []
    for path in (agent, other):
        server = socket.socket(socket.AF_UNIX)
        server.bind(path)
        server.listen(4)
        servers.append(server)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SSH_AUTH_SOCK", agent)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    connect = ("import socket;s=socket.socket(socket.AF_UNIX)\n"
               "try:\n s.connect(%r);print('connected')\nexcept OSError:\n print('denied')")
    try:
        for name in (".zshrc", ".claude.json", ".zsh_history"):
            result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                    "from pathlib import Path;print(Path(%r).read_text())"
                                    % str(home / name)])
            assert result["exit_code"] != 0 and "caller-secret" not in result["stdout"]
        denied = m.exec_in_copy(str(out), [sys.executable, "-c", connect % agent])
        assert denied["stdout"].strip() == "denied"
        reachable = m.exec_in_copy(str(out), [sys.executable, "-c", connect % other])
        assert reachable["stdout"].strip() == "connected"
        assert manifest["home_dirs"] == [str(home.resolve())]
    finally:
        for server in servers:
            server.close()
        shutil.rmtree(socket_dir, ignore_errors=True)
        m.release_copy(str(out))


def test_timeout_kills_descendants_instead_of_only_the_parent(tmp_path, monkeypatch):
    import time

    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    marker = Path(manifest["copy_dir"]) / "child-survived"
    child = "import time,pathlib;time.sleep(1.2);pathlib.Path(%r).write_text('bad')" % str(marker)
    parent = ("import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',%r]);"
              "print('started',flush=True);time.sleep(10)" % child)
    try:
        started = time.monotonic()
        result = m.exec_in_copy(str(out), [sys.executable, "-c", parent], timeout=1)
        assert time.monotonic() - started < 4
        assert result["timed_out"] is True and result["exit_code"] == 124
        assert "started" in result["stdout"]
        assert result["environment_unavailable"] is False
        time.sleep(3)
        assert not marker.exists()
    finally:
        m.release_copy(str(out))


def test_background_child_holding_pipes_does_not_mask_a_clean_exit(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(out))
    try:
        result = m.exec_in_copy(
            str(out), ["sh", "-c", "sleep 30 & echo done; exit 0"], timeout=1)
        assert result["timed_out"] is False and result["exit_code"] == 0
        assert "done" in result["stdout"]
    finally:
        m.release_copy(str(out))


def test_process_that_closes_its_pipes_and_hangs_is_reported_as_timed_out(
        tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(out))
    try:
        result = m.exec_in_copy(
            str(out), ["sh", "-c", "exec >&- 2>&-; sleep 30"], timeout=1)
        assert result["timed_out"] is True and result["exit_code"] == 124
    finally:
        m.release_copy(str(out))


def test_protected_paths_treat_sandbox_denied_stat_as_absent(tmp_path, monkeypatch):
    forge_dir = tmp_path / "bin"
    forge_dir.mkdir()
    (forge_dir / "gh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(forge_dir))

    def denied(self, *args, **kwargs):
        raise PermissionError(1, "Operation not permitted", str(self))

    monkeypatch.setattr(Path, "exists", denied)
    _, executables = m._protected_paths()
    assert str(forge_dir / "gh") in executables


def test_exec_bounds_captured_output_and_reports_what_was_dropped(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(out))
    try:
        result = m.exec_in_copy(str(out), [
            sys.executable, "-c",
            "import sys;sys.stdout.write('a'*3000000);sys.stderr.write('tail-marker')"])
        assert result["exit_code"] == 0
        assert result["output_truncated"] is True
        assert result["bytes_dropped"] > 2000000
        assert len(result["stdout"]) < m._HEAD_BYTES + m._TAIL_BYTES + 100
        assert result["stdout"].startswith("aaa") and result["stdout"].endswith("aaa")
        assert "bytes omitted" in result["stdout"]
        assert result["stderr"] == "tail-marker"
        small = m.exec_in_copy(str(out), [sys.executable, "-c", "print('ok')"])
        assert small["output_truncated"] is False and small["bytes_dropped"] == 0
    finally:
        m.release_copy(str(out))


def test_runaway_output_kills_the_process_before_the_timeout(tmp_path, monkeypatch):
    import time

    fallback(monkeypatch)
    monkeypatch.setattr(m, "_RUNAWAY_BYTES", 2 * 1024 * 1024)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(out))
    try:
        started = time.monotonic()
        result = m.exec_in_copy(str(out), [
            sys.executable, "-c", "import sys\nwhile True: sys.stdout.write('y'*65536)"],
            timeout=60)
        assert time.monotonic() - started < 20
        assert result["timed_out"] is False and result["output_truncated"] is True
        assert result["exit_code"] != 0
        assert len(result["stdout"]) < m._HEAD_BYTES + m._TAIL_BYTES + 100
    finally:
        m.release_copy(str(out))


def test_exec_retains_binary_output_as_printable_evidence(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    manifest = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(manifest))
    try:
        result = m.exec_in_copy(str(manifest), [
            sys.executable, "-c", "import os;os.write(1, bytes([255]));os.write(2, bytes([254]))",
        ])
        assert result["exit_code"] == 0
        assert result["stdout"] == "\\xff"
        assert result["stderr"] == "\\xfe"
        assert result["environment_unavailable"] is False
    finally:
        m.release_copy(str(manifest))


def test_cleanup_rejects_forged_manifest_paths_even_with_expected_basenames(
        tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    arbitrary = tmp_path / "deep-copy-user-data"
    arbitrary.mkdir()
    protected = arbitrary / "important"
    protected.write_text("keep", encoding="utf-8")
    try:
        forged = dict(manifest, copy_dir=str(arbitrary))
        forged_path = tmp_path / "forged.json"
        forged_path.write_text(json.dumps(forged), encoding="utf-8")
        code, error = invoke("release", "--manifest", str(forged_path))
        assert code == 2 and "error" in error
        assert protected.read_text() == "keep"
        code, error = invoke("exec", "--manifest", str(forged_path), "--", "/usr/bin/true")
        assert code == 2 and "error" in error
    finally:
        m.release_copy(str(out))


def test_release_cleans_remaining_environment_when_copy_was_removed(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    shutil.rmtree(manifest["copy_dir"])
    shutil.rmtree(repo)
    assert m.release_copy(str(out))["released"] is True
    assert not Path(manifest["env_dir"]).exists()


def test_exec_rejects_symlink_and_parent_directory_traversal(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    (Path(manifest["copy_dir"]) / "outside").symlink_to(tmp_path, target_is_directory=True)
    try:
        for cwd in ("..", "nested/../", "outside", str(tmp_path)):
            code, error = invoke("exec", "--manifest", str(out), "--cwd", cwd,
                                 "--", sys.executable, "-c", "print('bad')")
            assert code == 2 and "error" in error
        result = m.exec_in_copy(str(out), [sys.executable, "-c",
                                "import nonexistent_deep_dependency"])
        assert result["environment_unavailable"] is True
        assert "ModuleNotFoundError" in result["unavailable_reason"]
        assert m.exec_in_copy(str(out), ["nonexistent-deep-executable"])["exit_code"] == 127
    finally:
        m.release_copy(str(out))


def test_reviewed_code_failures_are_not_reported_as_missing_environment(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "a.py").write_text("import b\n", encoding="utf-8")
    (repo / "b.py").write_text("import a\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "modules")
    sha = git(repo, "rev-parse", "HEAD")
    out = tmp_path / "copy.json"
    m.acquire_copy(str(repo), sha, str(out))
    try:
        for argv in ([sys.executable, "-c", "from a import missing_name"],
                     [sys.executable, "-c", "import pkg.not_there"],
                     [sys.executable, "-c", "import sys;sys.stderr.write('ImportError\\n')"],
                     ["/bin/sh", "-c", "echo 'x: command not found' >&2; exit 127"]):
            result = m.exec_in_copy(str(out), argv)
            assert result["stderr"]
            assert result["environment_unavailable"] is False, argv
            assert result["unavailable_reason"] is None
    finally:
        m.release_copy(str(out))


def test_gitignored_artifacts_do_not_mark_snapshot_as_local_changes(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore")
    sha = git(repo, "rev-parse", "HEAD")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    try:
        assert manifest["source_state"]["local_changes"] is False
    finally:
        m.release_copy(str(out))


def test_release_removes_read_only_and_unreadable_directories(tmp_path, monkeypatch):
    fallback(monkeypatch)
    repo, sha = repository(tmp_path)
    out = tmp_path / "copy.json"
    manifest = m.acquire_copy(str(repo), sha, str(out))
    script = ("import os;os.makedirs('../environment/home/mod/sub');"
              "open('../environment/home/mod/sub/f','w').write('x');"
              "os.makedirs('../environment/home/closed/inner');"
              "os.chmod('../environment/home/mod/sub',0o555);"
              "os.chmod('../environment/home/mod',0o555);"
              "os.chmod('../environment/home/closed/inner',0);"
              "os.chmod('../environment/home/closed',0)")
    result = m.exec_in_copy(str(out), [sys.executable, "-c", script])
    assert result["exit_code"] == 0, result["stderr"]
    released = m.release_copy(str(out))
    assert released["released"] is True
    assert not Path(manifest["env_dir"]).exists()


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
