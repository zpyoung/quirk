#!/usr/bin/env python3
"""Acquire and release an isolated source tree for reviewer-seat change-request reviews.

The current checkout is never switched or reset. Reviewer source is fetched into a
private ref and exposed through a detached worktree. When no matching local clone
exists, callers must explicitly choose either --allow-temp-clone or --diff-only.
"""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from forge import make_forge, parse_origin
from jsonio import load_object, write_json

SCHEMA = 1
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _run(cmd, timeout=180, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _emit(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def _error(message, **extra):
    value = {"error": str(message)}
    value.update(extra)
    _emit(value)
    return 2


def _load(path):
    return load_object(path, "context")


_write = write_json


def _origin_identity(url):
    """Return (host, project) for HTTP/SSH/scp remotes; a filesystem remote has no host."""
    return parse_origin(url)


def _project_from_origin(url):
    """Compatibility helper used by older tests/callers."""
    return _origin_identity(url)[1]


def _git_root(path):
    try:
        result = _run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], timeout=20)
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return os.path.realpath(result.stdout.strip())


def _origin_host_project(repo_root):
    # Read the configured URL, not `remote get-url`, which expands url.*.insteadOf
    # and can hide the GitLab host identity behind a local mirror/rewrite.
    result = _run(["git", "-C", repo_root, "config", "--get", "remote.origin.url"], timeout=20)
    return _origin_identity(result.stdout) if result.returncode == 0 else (None, "")


def _validate_context(context):
    if context.get("seat") != "reviewer":
        raise ValueError("borrowed source is only valid for a detected reviewer seat")
    change = context.get("change")
    refs = context.get("refs")
    if not isinstance(change, dict) or not isinstance(refs, dict):
        raise ValueError("context is missing change or refs")
    project = change.get("project")
    host = change.get("host")
    number = change.get("number")
    head = refs.get("head")
    if not isinstance(project, str) or not project.strip():
        raise ValueError("context change.project is required")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("context change.host is required")
    if not str(number).isdigit() or int(number) <= 0:
        raise ValueError("context change.number must be a positive integer")
    if not isinstance(head, str) or not SHA_RE.match(head):
        raise ValueError("context refs.head must be a full lowercase SHA")
    if change.get("sha") and change.get("sha") != head:
        raise ValueError("change sha does not match refs.head")
    return host, project, int(number), head


def _make_root(prefix):
    root = tempfile.mkdtemp(prefix=prefix)
    token = secrets.token_hex(16)
    Path(root, ".quirk-review-source").write_text(token + "\n", encoding="utf-8")
    return root, token


def _clone_project(host, project, root, forge_name="gitlab"):
    repo = os.path.join(root, "repo")
    cmd, env = make_forge(forge_name, host, project).clone_command(repo)
    result = _run(cmd, timeout=300, env=env)
    if result.returncode != 0:
        raise RuntimeError("temporary clone failed: %s" % (result.stderr.strip() or result.stdout.strip()))
    return os.path.realpath(repo)


def _add_worktree(repo_root, number, expected_head, worktree, shallow, refspec):
    review_ref = "refs/quirk-review/%s/head" % number
    fetch_cmd = ["git", "-C", repo_root, "fetch", "--no-tags"]
    if shallow:
        fetch_cmd.append("--depth=1")
    fetch_cmd += ["origin", "+%s:%s" % (refspec, review_ref)]
    fetch = _run(fetch_cmd, timeout=300)
    if fetch.returncode != 0:
        raise RuntimeError("fetching the change head failed: %s" % (fetch.stderr.strip() or fetch.stdout.strip()))
    resolved = _run(["git", "-C", repo_root, "rev-parse", review_ref], timeout=20)
    actual = resolved.stdout.strip() if resolved.returncode == 0 else ""
    if actual != expected_head:
        raise RuntimeError("change head moved before the worktree was borrowed (expected %s, found %s)" %
                           (expected_head, actual or "unknown"))
    os.rmdir(worktree)
    added = _run(["git", "-C", repo_root, "worktree", "add", "--detach", worktree, expected_head],
                 timeout=180)
    if added.returncode != 0:
        raise RuntimeError("creating the detached worktree failed: %s" %
                           (added.stderr.strip() or added.stdout.strip()))
    checked = _run(["git", "-C", worktree, "rev-parse", "HEAD"], timeout=20)
    if checked.returncode != 0 or checked.stdout.strip() != expected_head:
        _run(["git", "-C", repo_root, "worktree", "remove", "--force", worktree], timeout=60)
        raise RuntimeError("borrowed worktree did not resolve to the expected change head")
    symbolic = _run(["git", "-C", worktree, "symbolic-ref", "-q", "HEAD"], timeout=20)
    if symbolic.returncode == 0:
        _run(["git", "-C", repo_root, "worktree", "remove", "--force", worktree], timeout=60)
        raise RuntimeError("borrowed worktree is not detached")
    return review_ref


def probe_refusal(context):
    """Why the mutation probe may not run on this change, or None when it may.

    The probe executes the change's code, so it never runs on a fork or on an author the
    forge does not mark as trusted.
    """
    change = context.get("change") if isinstance(context.get("change"), dict) else {}
    if change.get("is_fork") is not False:
        return "the change comes from a fork (or its origin is unknown)"
    if change.get("author_trusted") is not True:
        return "the change author is not a trusted member of the repository"
    return None


def acquire(args):
    try:
        context = _load(args.context)
        host, project, number, head = _validate_context(context)
    except Exception as exc:
        return _error(exc)
    forge_name = context.get("forge", "gitlab")
    refusal = probe_refusal(context) if args.allow_mutation_probe else None
    mutation_consent = bool(args.allow_mutation_probe) and refusal is None

    if args.diff_only:
        manifest = {
            "schema": SCHEMA, "kind": "diff-only", "path": None,
            "head_sha": head, "host": host, "project": project, "number": number,
            "reason": args.reason or "A matching local source tree was unavailable and the temporary clone was declined.",
            "mutation_consent": False,
        }
        _write(args.out, manifest)
        _emit(manifest)
        return 0

    repo_root = _git_root(args.repo)
    temp_root = None
    token = None
    if repo_root:
        try:
            origin_host, origin_project = _origin_host_project(repo_root)
        except (OSError, subprocess.SubprocessError) as exc:
            return _error("could not read the origin remote of %s: %s" % (repo_root, exc))
        if origin_host != host.lower() or origin_project != project:
            repo_root = None
    if repo_root is None:
        if not args.allow_temp_clone:
            return _error("no matching local clone; ask before using --allow-temp-clone, or choose --diff-only")
        try:
            temp_root, token = _make_root("quirk-review-clone-")
            repo_root = _clone_project(host, project, temp_root, forge_name=forge_name)
        except Exception as exc:
            if temp_root:
                shutil.rmtree(temp_root, ignore_errors=True)
            return _error(exc)

    is_temp_clone = temp_root is not None
    worktree = tempfile.mkdtemp(prefix="quirk-review-worktree-", dir=temp_root)
    if temp_root is None:
        cleanup_root, token = _make_root("quirk-review-cleanup-")
    else:
        cleanup_root = temp_root
    manifest = {
        "schema": SCHEMA,
        "kind": "temp-clone" if is_temp_clone else "worktree",
        "path": os.path.realpath(worktree),
        "repo_root": repo_root,
        "head_sha": head,
        "review_ref": "refs/quirk-review/%s/head" % number,
        "host": host,
        "project": project,
        "number": number,
        "cleanup_root": cleanup_root,
        "cleanup_token": token,
        "mutation_consent": mutation_consent,
        "acquisition": "creating",
    }
    if refusal:
        manifest["mutation_refused"] = refusal
    # Persist cleanup coordinates before git owns the worktree path. An interrupted
    # acquisition can still be released safely with this manifest.
    _write(args.out, manifest)
    try:
        review_ref = _add_worktree(repo_root, number, head, worktree, shallow=is_temp_clone,
                                   refspec=make_forge(forge_name, host, project).head_refspec(number))
    except Exception as exc:
        shutil.rmtree(worktree, ignore_errors=True)
        shutil.rmtree(cleanup_root, ignore_errors=True)
        manifest["acquisition"] = "failed"
        manifest["error"] = str(exc)
        _write(args.out, manifest)
        return _error(exc, head_sha=head)

    manifest["review_ref"] = review_ref
    manifest["acquisition"] = "ready"
    _write(args.out, manifest)
    _emit(manifest)
    return 0


def _safe_marker(manifest):
    root = manifest.get("cleanup_root")
    token = manifest.get("cleanup_token")
    if not isinstance(root, str) or not isinstance(token, str):
        return False
    marker = Path(root, ".quirk-review-source")
    try:
        return marker.read_text(encoding="utf-8").strip() == token
    except OSError:
        return False


def _drop_review_ref(manifest):
    """Delete the private review ref and prune the worktree record from the borrowed clone."""
    repo_root = manifest.get("repo_root")
    review_ref = manifest.get("review_ref")
    if not isinstance(repo_root, str) or not os.path.isdir(repo_root):
        return
    _run(["git", "-C", repo_root, "worktree", "prune"], timeout=60)
    if isinstance(review_ref, str) and review_ref.startswith("refs/quirk-review/"):
        _run(["git", "-C", repo_root, "update-ref", "-d", review_ref], timeout=60)


def release(args):
    """Remove a borrowed source tree, its private review ref and its cleanup root.

    Refuses to delete anything the manifest does not prove this script created: the schema,
    the worktree basename prefix and the cleanup-marker token must all match. Reports
    `released` only once the paths are actually gone; otherwise exits 2 naming what is left.
    """
    try:
        manifest = _load(args.manifest)
    except Exception as exc:
        return _error(exc)
    if manifest.get("schema") != SCHEMA:
        return _error("unsupported source manifest schema")
    if manifest.get("kind") == "diff-only":
        _emit({"released": True, "kind": "diff-only", "already_absent": True})
        return 0
    path = manifest.get("path")
    repo_root = manifest.get("repo_root")
    if not isinstance(path, str) or not os.path.basename(path).startswith("quirk-review-worktree-"):
        return _error("refusing to remove an unrecognized worktree path")
    cleanup_root = manifest.get("cleanup_root")
    already_absent = not os.path.exists(path)
    if (already_absent and isinstance(cleanup_root, str) and not os.path.exists(cleanup_root) and
            os.path.basename(cleanup_root).startswith(("quirk-review-cleanup-", "quirk-review-clone-"))):
        _drop_review_ref(manifest)
        _emit({"released": True, "kind": manifest.get("kind"), "already_absent": True})
        return 0
    if not _safe_marker(manifest):
        return _error("cleanup marker is missing or does not match the manifest")
    if not already_absent and isinstance(repo_root, str):
        removed = _run(["git", "-C", repo_root, "worktree", "remove", "--force", path], timeout=120)
        if removed.returncode != 0 and os.path.exists(path):
            return _error("worktree cleanup failed: %s" % (removed.stderr.strip() or removed.stdout.strip()))
    cleanup_root = manifest["cleanup_root"]
    shutil.rmtree(cleanup_root, ignore_errors=True)
    if manifest.get("kind") != "temp-clone" and os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
    remaining = [item for item in (cleanup_root, path) if os.path.exists(item)]
    if remaining:
        return _error("cleanup incomplete; still present: %s" % ", ".join(remaining))
    _drop_review_ref(manifest)
    _emit({"released": True, "kind": manifest.get("kind"), "already_absent": already_absent})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Borrow a change-head source tree without touching the caller checkout.")
    sub = parser.add_subparsers(dest="command", required=True)
    acq = sub.add_parser("acquire")
    acq.add_argument("--context", required=True)
    acq.add_argument("--repo", default=".")
    acq.add_argument("--out", required=True)
    choice = acq.add_mutually_exclusive_group()
    choice.add_argument("--allow-temp-clone", action="store_true")
    choice.add_argument("--diff-only", action="store_true")
    acq.add_argument("--reason")
    acq.add_argument("--allow-mutation-probe", action="store_true",
                     help="record per-run human consent for the mutation probe")
    rel = sub.add_parser("release")
    rel.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    return acquire(args) if args.command == "acquire" else release(args)


if __name__ == "__main__":
    sys.exit(main())
