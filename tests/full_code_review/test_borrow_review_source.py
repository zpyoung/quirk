import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts"))
import borrow_review_source as m  # noqa: E402


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


def fixture(tmp_path):
    bare = tmp_path / "origin.git"
    work = tmp_path / "author"
    local = tmp_path / "reviewer"
    run("git", "init", "--bare", str(bare))
    run("git", "clone", str(bare), str(work))
    run("git", "config", "user.email", "test@example.com", cwd=work)
    run("git", "config", "user.name", "Test", cwd=work)
    (work / "value.txt").write_text("base\n")
    run("git", "add", "value.txt", cwd=work)
    run("git", "commit", "-m", "base", cwd=work)
    run("git", "branch", "-M", "main", cwd=work)
    run("git", "push", "origin", "main", cwd=work)
    (work / "value.txt").write_text("change head\n")
    run("git", "commit", "-am", "head", cwd=work)
    head = run("git", "rev-parse", "HEAD", cwd=work).stdout.strip()
    run("git", "push", "origin", "HEAD:refs/merge-requests/7/head", cwd=work)
    run("git", "clone", "--branch", "main", str(bare), str(local))
    remote = "git@gitlab.example:group/project.git"
    run("git", "remote", "set-url", "origin", remote, cwd=local)
    run("git", "config", "url.%s.insteadOf" % bare.resolve().as_uri(), remote, cwd=local)
    project = "group/project"
    context = {
        "seat": "reviewer", "refs": {"base": "b" * 40, "start": "c" * 40, "head": head},
        "change": {"number": 7, "host": "gitlab.example", "project": project, "sha": head},
    }
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(context))
    return local, ctx_path, head


def invoke(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(argv)
    return rc, json.loads(buf.getvalue())


def test_acquire_is_detached_at_mr_head_and_release_is_idempotent(tmp_path):
    local, context, head = fixture(tmp_path)
    before_head = run("git", "rev-parse", "HEAD", cwd=local).stdout
    before_status = run("git", "status", "--porcelain=v1", cwd=local).stdout
    manifest_path = tmp_path / "source.json"
    rc, manifest = invoke(["acquire", "--context", str(context), "--repo", str(local),
                           "--out", str(manifest_path), "--allow-mutation-probe"])
    assert rc == 0 and manifest["kind"] == "worktree"
    assert manifest["mutation_consent"] is True
    borrowed = Path(manifest["path"])
    assert (borrowed / "value.txt").read_text() == "change head\n"
    assert run("git", "rev-parse", "HEAD", cwd=borrowed).stdout.strip() == head
    symbolic = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=borrowed)
    assert symbolic.returncode != 0
    assert run("git", "rev-parse", "HEAD", cwd=local).stdout == before_head
    assert run("git", "status", "--porcelain=v1", cwd=local).stdout == before_status
    rc, result = invoke(["release", "--manifest", str(manifest_path)])
    assert rc == 0 and result["released"] is True and not borrowed.exists()
    rc, result = invoke(["release", "--manifest", str(manifest_path)])
    assert rc == 0 and result["already_absent"] is True


def test_stale_head_aborts_without_touching_caller(tmp_path):
    local, context, _ = fixture(tmp_path)
    value = json.loads(context.read_text())
    value["refs"]["head"] = "d" * 40
    value["change"]["sha"] = "d" * 40
    context.write_text(json.dumps(value))
    before = run("git", "status", "--porcelain=v1", cwd=local).stdout
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(local),
                         "--out", str(tmp_path / "source.json")])
    assert rc == 2 and "head moved" in result["error"]
    assert run("git", "status", "--porcelain=v1", cwd=local).stdout == before


def test_no_matching_clone_requires_explicit_choice_and_diff_only_is_structured(tmp_path):
    _, context, head = fixture(tmp_path)
    out = tmp_path / "source.json"
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(tmp_path),
                         "--out", str(out)])
    assert rc == 2 and "ask before" in result["error"]
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(tmp_path),
                         "--out", str(out), "--diff-only", "--reason", "clone declined"])
    assert rc == 0 and result["kind"] == "diff-only" and result["head_sha"] == head
    assert result["mutation_consent"] is False and result["reason"] == "clone declined"


def test_explicit_temp_clone_path_is_cleaned_completely(tmp_path):
    _, context, head = fixture(tmp_path)
    # The fixture's project string is the source bare path after normalization; recover it
    # from the matching reviewer clone's origin through a fresh local clone in the fake.
    bare = next(tmp_path.glob("origin.git"))
    old_clone = m._clone_project
    def fake_clone(host, project, root):
        repo = Path(root) / "repo"
        run("git", "clone", "--no-checkout", str(bare), str(repo))
        return str(repo.resolve())
    m._clone_project = fake_clone
    try:
        manifest_path = tmp_path / "temp-source.json"
        rc, manifest = invoke(["acquire", "--context", str(context), "--repo", str(tmp_path / "none"),
                               "--out", str(manifest_path), "--allow-temp-clone"])
        assert rc == 0 and manifest["kind"] == "temp-clone"
        cleanup_root = Path(manifest["cleanup_root"])
        assert cleanup_root.exists() and Path(manifest["path"], "value.txt").read_text() == "change head\n"
        assert manifest["head_sha"] == head
        assert run("git", "rev-parse", "--is-shallow-repository", cwd=manifest["repo_root"]).stdout.strip() == "true"
        assert invoke(["release", "--manifest", str(manifest_path)])[0] == 0
        assert not cleanup_root.exists()
    finally:
        m._clone_project = old_clone


def test_same_project_path_on_different_host_is_not_accepted(tmp_path):
    local, context, _ = fixture(tmp_path)
    run("git", "remote", "set-url", "origin", "git@other-gitlab.example:group/project.git", cwd=local)
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(local),
                         "--out", str(tmp_path / "source.json")])
    assert rc == 2 and "no matching local clone" in result["error"]
    assert m._origin_identity("git@gitlab-a.example:group/proj.git") != \
           m._origin_identity("git@gitlab-b.example:group/proj.git")


def test_temp_clone_command_is_shallow_and_host_pinned(tmp_path):
    calls = []
    old = m._run
    def fake_run(cmd, timeout=180, env=None):
        calls.append((cmd, env))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    m._run = fake_run
    try:
        repo = m._clone_project("gitlab.example", "group/project", str(tmp_path))
        cmd, env = calls[0]
        assert "--depth=1" in cmd and "--filter=blob:none" in cmd and "--no-checkout" in cmd
        assert env["GITLAB_HOST"] == "gitlab.example"
        assert repo.endswith("/repo")
    finally:
        m._run = old
