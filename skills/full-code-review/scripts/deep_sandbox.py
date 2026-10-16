#!/usr/bin/env python3
"""Run review reproduction commands in isolated throwaway source copies."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from borrow_review_source import probe_refusal
from jsonio import load_object, write_json

_SHA = re.compile(r"^[0-9a-f]{40}$")
_LABEL = re.compile(r"^[a-zA-Z0-9_-]+$")
_CREDENTIALS = ("GH_TOKEN", "GITHUB_TOKEN", "GLAB_TOKEN", "GITLAB_TOKEN",
                "SSH_AUTH_SOCK", "GIT_ASKPASS")
_ENV_DIRS = {"HOME": "home", "XDG_CONFIG_HOME": "xdg_config",
             "XDG_STATE_HOME": "xdg_state", "XDG_CACHE_HOME": "xdg_cache",
             "TMPDIR": "tmp"}


def evaluate_trust(context: dict, source_access: str = "author-worktree") -> dict:
    """Require author ownership or a trusted same-repository reviewer before prompting for execution."""
    if not isinstance(context, dict) or context.get("seat") not in ("author", "reviewer"):
        raise ValueError("context must have an author or reviewer seat")
    if not isinstance(source_access, str) or not source_access:
        raise ValueError("source access must be a nonempty string")
    if source_access == "diff-only":
        reason = "diff-only source access"
    elif context["seat"] == "reviewer":
        reason = probe_refusal(context)
    else:
        reason = None
    allowed = reason is None
    return {"allowed": allowed, "prompt_required": allowed, "reason": reason}


def probe_capabilities(source_root: str) -> dict:
    """Find a functioning local OS write sandbox, or report environment-only isolation."""
    if sys.platform == "darwin":
        command = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"]
        kind = "sandbox-exec"
    elif sys.platform.startswith("linux"):
        binary = shutil.which("bwrap")
        command = ([binary, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                    "/bin/true"] if binary else None)
        kind = "bwrap"
    else:
        command = None
        kind = "worktree"
    if command:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"sandbox_kind": kind}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"sandbox_kind": "worktree"}


def _git_environment() -> dict:
    env = os.environ.copy()
    for name in list(env):
        if name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
                    "GIT_TEMPLATE_DIR", "GIT_COMMON_DIR", "GIT_INDEX_FILE") or \
                name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            env.pop(name)
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0")
    return env


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=120,
                          env=_git_environment())


def _stub(path: Path) -> None:
    path.write_text("#!/bin/sh\nprintf '%s\\n' 'blocked in deep-mode throwaway copy: "
                    "gh/glab are disabled' >&2\nexit 127\n", encoding="utf-8")
    path.chmod(0o755)


def acquire_copy(source_root: str, head_sha: str, out_manifest: str,
                 label: str = "finder") -> dict:
    """Create a CoW clone or detached worktree at the expected head and an isolated environment."""
    if not isinstance(head_sha, str) or not _SHA.fullmatch(head_sha):
        raise ValueError("head_sha must be a full lowercase 40-character SHA")
    if not isinstance(label, str) or not _LABEL.fullmatch(label):
        raise ValueError("label must contain only letters, digits, underscores, or hyphens")
    if not isinstance(out_manifest, str) or not out_manifest:
        raise ValueError("out_manifest is required")
    if not isinstance(source_root, str) or not os.path.isdir(source_root):
        raise ValueError("source_root must be an existing git directory")
    root = os.path.realpath(source_root)
    resolved = _git("-C", root, "rev-parse", "HEAD")
    if resolved.returncode != 0:
        raise ValueError("source_root must be an existing git directory")
    if resolved.stdout.strip() != head_sha:
        raise ValueError("head_sha mismatch: source HEAD is %s" % resolved.stdout.strip())
    toplevel = _git("-C", root, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0 or os.path.realpath(toplevel.stdout.strip()) != root:
        raise ValueError("source_root must be the git worktree root")
    if os.path.exists(out_manifest):
        raise ValueError("out_manifest already exists")

    copy_dir = os.path.realpath(tempfile.mkdtemp(prefix="deep-copy-%s-" % label))
    env_dir = os.path.realpath(tempfile.mkdtemp(prefix="deep-env-%s-" % label))
    copy_kind = "git-worktree"
    registered = False
    try:
        git_dir = Path(root, ".git")
        if sys.platform == "darwin" and git_dir.is_dir() and not git_dir.is_symlink() and \
                not Path(git_dir, "config").is_symlink():
            clone = subprocess.run(["cp", "-cR", os.path.join(root, "."), copy_dir],
                                   capture_output=True, text=True, timeout=180)
            if clone.returncode == 0:
                hooks = Path(copy_dir, ".git", "hooks")
                if hooks.is_symlink():
                    hooks.unlink()
                elif hooks.exists():
                    shutil.rmtree(hooks)
                for key, value in (("core.hooksPath", "/dev/null"),
                                   ("core.fsmonitor", "false")):
                    configured = _git("config", "--file", str(Path(copy_dir, ".git", "config")),
                                      key, value)
                    if configured.returncode != 0:
                        raise OSError("could not isolate copied git config: %s" % configured.stderr.strip())
                copy_kind = "clonefile"
        if copy_kind == "git-worktree":
            shutil.rmtree(copy_dir)
            added = _git("-C", root, "-c", "core.hooksPath=/dev/null",
                         "-c", "core.fsmonitor=false", "worktree", "add", "--detach",
                         copy_dir, head_sha)
            if added.returncode != 0:
                raise OSError("creating detached worktree failed: %s" %
                              (added.stderr.strip() or added.stdout.strip()))
            registered = True
        for suffix in (*_ENV_DIRS.values(), "bin"):
            Path(env_dir, suffix).mkdir()
        for name in ("gh", "glab"):
            _stub(Path(env_dir, "bin", name))
        manifest = {"schema": 1, "label": label, "source_root": root,
                    "head_sha": head_sha, "copy_dir": copy_dir, "env_dir": env_dir,
                    "copy_kind": copy_kind,
                    "sandbox_kind": probe_capabilities(root)["sandbox_kind"],
                    "released": False}
        write_json(out_manifest, manifest)
        return manifest
    except Exception:
        if registered:
            _git("-C", root, "worktree", "remove", "--force", copy_dir)
        if os.path.isdir(copy_dir):
            shutil.rmtree(copy_dir)
        shutil.rmtree(env_dir)
        raise


def _manifest(manifest_path: str, require_active: bool = True) -> dict:
    manifest = load_object(manifest_path, "deep copy manifest")
    copy_dir, env_dir = manifest.get("copy_dir"), manifest.get("env_dir")
    if manifest.get("schema") != 1 or manifest.get("copy_kind") not in ("clonefile", "git-worktree") \
            or manifest.get("sandbox_kind") not in ("sandbox-exec", "bwrap", "worktree") \
            or not isinstance(copy_dir, str) or not isinstance(env_dir, str) \
            or not os.path.basename(copy_dir).startswith("deep-copy-") \
            or not os.path.basename(env_dir).startswith("deep-env-") \
            or not os.path.isabs(copy_dir) or not os.path.isabs(env_dir) \
            or os.path.realpath(copy_dir) != copy_dir or os.path.realpath(env_dir) != env_dir:
        raise ValueError("invalid deep copy manifest")
    if require_active and (manifest.get("released") or not os.path.isdir(copy_dir)
                           or not os.path.isdir(env_dir)):
        raise ValueError("deep copy has already been released or is missing")
    return manifest


def _seatbelt_profile(copy_dir: str, env_dir: str) -> str:
    def subpath(path: str) -> str:
        return '(subpath "%s")' % path.replace("\\", "\\\\").replace('"', '\\"')
    return ("(version 1)(allow default)(deny file-write*)"
            "(allow file-write* %s %s "
            '(literal "/dev/null") (literal "/dev/zero") '
            '(literal "/dev/random") (literal "/dev/urandom") '
            '(literal "/dev/tty"))') % (subpath(copy_dir), subpath(env_dir))


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def exec_in_copy(manifest_path: str, command: list[str], timeout: int = 120,
                 cwd_rel: str = ".") -> dict:
    """Run one bounded argv command in the copy; report unavailable dependencies without aborting."""
    manifest = _manifest(manifest_path)
    if not isinstance(command, list):
        raise ValueError("command must be a nonempty argv list")
    argv = command[1:] if command and command[0] == "--" else command
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise ValueError("command must be a nonempty argv list")
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")
    if not isinstance(cwd_rel, str) or os.path.isabs(cwd_rel) or ".." in Path(cwd_rel).parts:
        raise ValueError("cwd must be a relative directory inside the copy")
    root = manifest["copy_dir"]
    cwd = os.path.realpath(os.path.join(root, cwd_rel))
    if os.path.commonpath((root, cwd)) != root or not os.path.isdir(cwd):
        raise ValueError("cwd must be an existing directory inside the copy")
    env_dir = manifest["env_dir"]
    env = _git_environment()
    for name in _CREDENTIALS:
        env.pop(name, None)
    env.update({name: str(Path(env_dir, suffix)) for name, suffix in _ENV_DIRS.items()})
    env["PATH"] = str(Path(env_dir, "bin")) + os.pathsep + env.get("PATH", "")
    env.update(GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.hooksPath",
               GIT_CONFIG_VALUE_0="/dev/null", GIT_CONFIG_KEY_1="core.fsmonitor",
               GIT_CONFIG_VALUE_1="false")
    kind = manifest["sandbox_kind"]
    if kind == "sandbox-exec":
        run_command = ["/usr/bin/sandbox-exec", "-p",
                       _seatbelt_profile(root, env_dir), *argv]
    elif kind == "bwrap":
        binary = shutil.which("bwrap")
        if not binary:
            raise ValueError("bwrap is no longer available")
        run_command = [binary, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                       "--bind", root, root, "--bind", env_dir, env_dir,
                       "--chdir", cwd, "--", *argv]
    else:
        run_command = argv
    timed_out = False
    try:
        process = subprocess.run(run_command, cwd=cwd, env=env, timeout=timeout,
                                 capture_output=True, text=True)
        exit_code = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code, timed_out = 124, True
        stdout, stderr = _text(exc.stdout), _text(exc.stderr)
    except FileNotFoundError as exc:
        exit_code, stdout, stderr = 127, "", str(exc)
    except PermissionError as exc:
        exit_code, stdout, stderr = 126, "", str(exc)
    blocked = os.path.basename(argv[0]) in ("gh", "glab") and \
        "blocked in deep-mode throwaway copy" in stderr
    missing = ("ModuleNotFoundError" in stderr or "ImportError" in stderr or
               "command not found" in stderr.lower() or
               (exit_code == 127 and not blocked)) and not timed_out
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr,
            "timed_out": timed_out, "sandbox_kind": kind,
            "environment_unavailable": missing,
            "unavailable_reason": stderr.strip() if missing else None}


def release_copy(manifest_path: str) -> dict:
    """Remove only the copy and environment named in an acquired manifest."""
    manifest = _manifest(manifest_path, require_active=False)
    copy_dir, env_dir = manifest["copy_dir"], manifest["env_dir"]
    if not manifest.get("released"):
        if manifest["copy_kind"] == "git-worktree" and os.path.isdir(copy_dir):
            removed = _git("-C", manifest["source_root"], "worktree", "remove", "--force",
                           copy_dir)
            if removed.returncode != 0:
                raise OSError("removing detached worktree failed: %s" % removed.stderr.strip())
        if os.path.isdir(copy_dir):
            shutil.rmtree(copy_dir)
        if os.path.isdir(env_dir):
            shutil.rmtree(env_dir)
        manifest["released"] = True
        write_json(manifest_path, manifest)
    return {"released": True, "copy_dir": copy_dir}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Serve JSON command results and JSON argument errors on stdout."""
    try:
        parser = _Parser(description="Execute review checks in throwaway source copies")
        subs = parser.add_subparsers(dest="action", required=True, parser_class=_Parser)
        trust = subs.add_parser("check-trust")
        trust.add_argument("--context", required=True)
        trust.add_argument("--source-access", default="author-worktree")
        trust.add_argument("--out")
        acquire = subs.add_parser("acquire")
        acquire.add_argument("--source-root", required=True)
        acquire.add_argument("--head-sha", required=True)
        acquire.add_argument("--label", default="finder")
        acquire.add_argument("--out", required=True)
        execute = subs.add_parser("exec")
        execute.add_argument("--manifest", required=True)
        execute.add_argument("--timeout", type=int, default=120)
        execute.add_argument("--cwd", default=".")
        execute.add_argument("command", nargs=argparse.REMAINDER)
        release = subs.add_parser("release")
        release.add_argument("--manifest", required=True)
        args = parser.parse_args(argv)
        if args.action == "check-trust":
            result = evaluate_trust(load_object(args.context, "context"), args.source_access)
            if args.out:
                write_json(args.out, result)
        elif args.action == "acquire":
            result = acquire_copy(args.source_root, args.head_sha, args.out, args.label)
        elif args.action == "exec":
            result = exec_in_copy(args.manifest, args.command, args.timeout, args.cwd)
        else:
            result = release_copy(args.manifest)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
