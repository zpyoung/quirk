import contextlib
import io
import json
import subprocess
from pathlib import Path

import pytest

import borrow_review_source as m


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
        "change": {"number": 7, "host": "gitlab.example", "project": project, "sha": head,
                   "is_fork": False, "author_trusted": True},
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


def test_explicit_temp_clone_path_is_cleaned_completely(tmp_path, monkeypatch):
    _, context, head = fixture(tmp_path)
    bare = tmp_path / "origin.git"

    def fake_clone(host, project, root, forge_name="gitlab"):
        repo = Path(root) / "repo"
        run("git", "clone", "--no-checkout", str(bare), str(repo))
        return str(repo.resolve())
    monkeypatch.setattr(m, "_clone_project", fake_clone)
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


def test_same_project_path_on_different_host_is_not_accepted(tmp_path):
    local, context, _ = fixture(tmp_path)
    run("git", "remote", "set-url", "origin", "git@other-gitlab.example:group/project.git", cwd=local)
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(local),
                         "--out", str(tmp_path / "source.json")])
    assert rc == 2 and "no matching local clone" in result["error"]
    assert m._origin_identity("git@gitlab-a.example:group/proj.git") != \
           m._origin_identity("git@gitlab-b.example:group/proj.git")


def test_temp_clone_command_is_shallow_and_host_pinned(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, timeout=180, env=None):
        calls.append((cmd, env))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(m, "_run", fake_run)
    repo = m._clone_project("gitlab.example", "group/project", str(tmp_path))
    cmd, env = calls[0]
    assert "--depth=1" in cmd and "--filter=blob:none" in cmd and "--no-checkout" in cmd
    assert env["GITLAB_HOST"] == "gitlab.example"
    assert repo.endswith("/repo")


@pytest.mark.parametrize("fields, reason", [
    ({"is_fork": True, "author_trusted": True}, "fork"),
    ({"is_fork": False, "author_trusted": None}, "trusted"),
    ({}, "fork"),
])
def test_mutation_probe_is_refused_for_forks_and_untrusted_authors(tmp_path, fields, reason):
    local, context, _ = fixture(tmp_path)
    value = json.loads(context.read_text())
    for key in ("is_fork", "author_trusted"):
        value["change"].pop(key, None)
    value["change"].update(fields)
    context.write_text(json.dumps(value))
    out = tmp_path / "manifest.json"
    rc, manifest = invoke(["acquire", "--context", str(context), "--repo", str(local),
                           "--out", str(out), "--allow-mutation-probe"])
    invoke(["release", "--manifest", str(out)])
    assert rc == 0
    assert manifest["mutation_consent"] is False
    assert reason in manifest["mutation_refused"]


def acquired(tmp_path):
    local, context, _ = fixture(tmp_path)
    out = tmp_path / "source.json"
    rc, manifest = invoke(["acquire", "--context", str(context), "--repo", str(local),
                           "--out", str(out)])
    assert rc == 0
    return local, out, manifest


def rewrite(out, **changes):
    manifest = json.loads(out.read_text())
    manifest.update(changes)
    out.write_text(json.dumps(manifest))


def test_release_refuses_a_worktree_path_without_the_owned_prefix(tmp_path):
    _, out, manifest = acquired(tmp_path)
    victim = tmp_path / "precious"
    victim.mkdir()
    (victim / "keep.txt").write_text("data")
    rewrite(out, path=str(victim))
    rc, result = invoke(["release", "--manifest", str(out)])
    assert rc == 2 and "unrecognized worktree path" in result["error"]
    assert (victim / "keep.txt").exists() and Path(manifest["path"]).exists()


@pytest.mark.parametrize("tamper", ["wrong-token", "missing-marker", "missing-token-field"])
def test_release_refuses_when_the_cleanup_marker_does_not_prove_ownership(tmp_path, tamper):
    _, out, manifest = acquired(tmp_path)
    marker = Path(manifest["cleanup_root"], ".quirk-review-source")
    if tamper == "wrong-token":
        rewrite(out, cleanup_token="0" * 32)
    elif tamper == "missing-marker":
        marker.unlink()
    else:
        value = json.loads(out.read_text())
        del value["cleanup_token"]
        out.write_text(json.dumps(value))
    rc, result = invoke(["release", "--manifest", str(out)])
    assert rc == 2 and "cleanup marker" in result["error"]
    assert Path(manifest["path"]).exists() and Path(manifest["cleanup_root"]).exists()


@pytest.mark.parametrize("schema", [0, 2, None])
def test_release_refuses_an_unsupported_manifest_schema(tmp_path, schema):
    _, out, manifest = acquired(tmp_path)
    rewrite(out, schema=schema)
    rc, result = invoke(["release", "--manifest", str(out)])
    assert rc == 2 and "schema" in result["error"]
    assert Path(manifest["path"]).exists()


def test_release_refuses_a_cleanup_root_that_is_not_the_owned_directory(tmp_path):
    _, out, manifest = acquired(tmp_path)
    victim = tmp_path / "precious"
    victim.mkdir()
    (victim / "keep.txt").write_text("data")
    (victim / ".quirk-review-source").write_text("not-the-token\n")
    rewrite(out, cleanup_root=str(victim))
    rc, _ = invoke(["release", "--manifest", str(out)])
    assert rc == 2 and (victim / "keep.txt").exists()


def test_release_drops_the_private_review_ref(tmp_path):
    local, out, manifest = acquired(tmp_path)
    ref = manifest["review_ref"]
    assert run("git", "rev-parse", "--verify", ref, cwd=local).returncode == 0
    rc, _ = invoke(["release", "--manifest", str(out)])
    assert rc == 0
    missing = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=local, capture_output=True)
    assert missing.returncode != 0
    assert str(manifest["path"]) not in run("git", "worktree", "list", cwd=local).stdout


def test_release_reports_failure_when_the_paths_survive_removal(tmp_path, monkeypatch):
    _, out, manifest = acquired(tmp_path)
    monkeypatch.setattr(m.shutil, "rmtree", lambda *args, **kwargs: None)
    rc, result = invoke(["release", "--manifest", str(out)])
    assert rc == 2 and "released" not in result
    assert manifest["cleanup_root"] in result["error"]


def test_acquire_reports_an_origin_lookup_timeout_as_json_error(tmp_path, monkeypatch):
    local, context, _ = fixture(tmp_path)
    real_run = m._run

    def timing_out_on_config(cmd, timeout=180, env=None):
        if "config" in cmd:
            raise subprocess.TimeoutExpired(cmd, timeout)
        return real_run(cmd, timeout=timeout, env=env)
    monkeypatch.setattr(m, "_run", timing_out_on_config)
    rc, result = invoke(["acquire", "--context", str(context), "--repo", str(local),
                         "--out", str(tmp_path / "source.json")])
    assert rc == 2 and "origin" in result["error"]
