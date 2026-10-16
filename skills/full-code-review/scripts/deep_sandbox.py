#!/usr/bin/env python3
"""Run review reproduction commands in isolated throwaway source copies."""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from borrow_review_source import probe_refusal
from jsonio import load_object, write_json

_SHA = re.compile(r"^[0-9a-f]{40}$")
_LABEL = re.compile(r"^[a-zA-Z0-9_-]+$")
_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM")
_FALLBACK_WARNING = (
    "environment-only isolation: filesystem access and nested absolute gh/glab execution "
    "are not enforced by the OS; only trusted, consented commands may run")
_ENV_DIRS = {"HOME": "home", "XDG_CONFIG_HOME": "xdg_config",
             "XDG_STATE_HOME": "xdg_state", "XDG_CACHE_HOME": "xdg_cache",
             "XDG_DATA_HOME": "xdg_data", "XDG_RUNTIME_DIR": "xdg_runtime",
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
    """Probe OS isolation; explicitly distinguish an environment-only fallback."""
    if sys.platform == "darwin":
        command = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"]
        kind = "sandbox-exec"
    elif sys.platform.startswith("linux"):
        binary = shutil.which("bwrap")
        command = ([binary, "--unshare-pid", "--die-with-parent", "--ro-bind", "/", "/",
                    "--dev", "/dev", "--proc", "/proc", "/bin/true"] if binary else None)
        kind = "bwrap"
    else:
        command, kind = None, "worktree"
    if command:
        try:
            result = _run(command, timeout=10, env=_git_environment())
            if result.returncode == 0:
                return {"sandbox_kind": kind, "os_enforced": True, "isolation_warning": None}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"sandbox_kind": "worktree", "os_enforced": False,
            "isolation_warning": _FALLBACK_WARNING}


def _git_environment() -> dict:
    env = {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}
    env["PATH"] = os.pathsep.join(path for path in env.get("PATH", os.defpath).split(os.pathsep)
                                if os.path.isabs(path))
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               GIT_ATTR_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
               GIT_CONFIG_COUNT="4", GIT_CONFIG_KEY_0="core.hooksPath",
               GIT_CONFIG_VALUE_0="/dev/null", GIT_CONFIG_KEY_1="core.fsmonitor",
               GIT_CONFIG_VALUE_1="false", GIT_CONFIG_KEY_2="core.attributesFile",
               GIT_CONFIG_VALUE_2="/dev/null", GIT_CONFIG_KEY_3="maintenance.auto",
               GIT_CONFIG_VALUE_3="false")
    return env


def _run(command: list[str], timeout: int, **kwargs) -> subprocess.CompletedProcess:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="backslashreplace",
                               start_new_session=True, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(process.pid)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired as exc:
            process.stdout.close()
            process.stderr.close()
            raise subprocess.TimeoutExpired(command, timeout, exc.output, exc.stderr)
        raise subprocess.TimeoutExpired(command, timeout, stdout, stderr)
    finally:
        _kill_group(process.pid)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], timeout=120, env=_git_environment())


def _stub(path: Path) -> None:
    path.write_text("#!/bin/sh\nprintf '%s\\n' 'blocked in deep-mode throwaway copy: "
                    "gh/glab are disabled' >&2\nexit 127\n", encoding="utf-8")
    path.chmod(0o755)


def _checked_git(*args: str) -> subprocess.CompletedProcess:
    result = _git(*args)
    if result.returncode:
        raise OSError("isolated git command failed: %s" % result.stderr.strip())
    return result


def _registry_root() -> Path:
    root = Path(tempfile.gettempdir()).resolve() / ("deep-review-%s" % os.getuid())
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("unsafe deep-copy registry directory")
    return root


def _source_git(root: Path) -> tuple[Path, Path]:
    git_dir = root / ".git"
    if git_dir.is_file():
        pointer = git_dir.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir: "):
            raise ValueError("invalid source git worktree pointer")
        git_dir = (root / pointer[8:]).resolve()
    if not git_dir.is_dir() or not (git_dir / "HEAD").is_file():
        raise ValueError("source_root must be the git worktree root")
    common = git_dir
    if (git_dir / "commondir").is_file():
        common = (git_dir / (git_dir / "commondir").read_text(encoding="utf-8").strip()).resolve()
    if not (common / "objects").is_dir():
        raise ValueError("source repository objects are missing")
    return git_dir, common


def _export_head(root: Path, stage: Path, head_sha: str) -> tuple[Path, bool]:
    git_dir, common = _source_git(root)
    facade = stage / "source.git"
    _checked_git("init", "--bare", "--template=", "-q", str(facade))
    for name in ("HEAD", "packed-refs"):
        origin = git_dir / name if (git_dir / name).exists() else common / name
        if origin.is_file():
            shutil.copyfile(origin, facade / name)
    for origin in (common / "refs", git_dir / "refs"):
        if origin.is_dir():
            shutil.copytree(origin, facade / "refs", dirs_exist_ok=True)
    (facade / "objects" / "info" / "alternates").write_text(
        str((common / "objects").resolve()) + "\n", encoding="utf-8")
    actual = _checked_git("--git-dir=" + str(facade), "rev-parse", "--verify", "HEAD").stdout.strip()
    if actual != head_sha:
        raise ValueError("head_sha mismatch: source HEAD is %s" % actual)
    staged_changes = False
    if (git_dir / "index").is_file():
        shutil.copyfile(git_dir / "index", facade / "index")
        for shared_index in git_dir.glob("sharedindex.*"):
            shutil.copyfile(shared_index, facade / shared_index.name)
        staged = _git("--git-dir=" + str(facade), "--work-tree=" + str(root),
                      "diff-index", "--cached", "--quiet", "--no-ext-diff",
                      "--no-textconv", head_sha, "--")
        if staged.returncode not in (0, 1):
            raise OSError("could not inspect source index without executing filters: %s" %
                          staged.stderr.strip())
        staged_changes = staged.returncode == 1
    bundle = stage / "source.bundle"
    _checked_git("--git-dir=" + str(facade), "bundle", "create", str(bundle), "HEAD")
    return bundle, staged_changes


def _remove_nested_git(root: Path) -> None:
    for directory, dirs, files in os.walk(root, followlinks=False):
        if ".git" in dirs:
            item = Path(directory, ".git")
            if item.is_symlink():
                item.unlink()
            else:
                shutil.rmtree(item)
            dirs.remove(".git")
        if ".git" in files:
            Path(directory, ".git").unlink()


def _snapshot(root: Path, destination: Path) -> str:
    cloned = sys.platform == "darwin"
    for entry in root.iterdir():
        if entry.name == ".git":
            continue
        target = destination / entry.name
        copied = False
        if entry.is_dir() and not entry.is_symlink() and any(
                ".git" in dirs or ".git" in files
                for _, dirs, files in os.walk(entry, followlinks=False)):
            cloned = False
        if cloned:
            result = _run(["/bin/cp", "-cR", str(entry), str(target)], timeout=180,
                          env=_git_environment())
            copied = result.returncode == 0
            if not copied and os.path.lexists(target):
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            cloned = copied
        if not copied:
            if entry.is_symlink():
                target.symlink_to(os.readlink(entry), target_is_directory=entry.is_dir())
            elif entry.is_dir():
                shutil.copytree(entry, target, symlinks=True,
                                ignore=shutil.ignore_patterns(".git"))
            elif entry.is_file():
                shutil.copy2(entry, target)
            else:
                raise ValueError("source snapshot contains a non-file entry: %s" % entry)
    _remove_nested_git(destination)
    return "clonefile" if cloned else "copy"


def _protected_paths() -> tuple[list[str], list[str]]:
    homes = {os.path.expanduser("~"), os.environ.get("HOME", "")}
    credentials = set()
    for home in homes - {""}:
        for suffix in (".ssh", ".aws", ".azure", ".config", ".docker", ".kube", ".gnupg",
                       ".netrc", ".gitconfig", ".git-credentials", ".npmrc", ".pypirc",
                       ".local/share/keyrings", "Library/Keychains",
                       "Library/Application Support/gh", "Library/Application Support/glab"):
            credentials.add(os.path.realpath(os.path.join(home, suffix)))
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "AWS_SHARED_CREDENTIALS_FILE",
                 "AWS_CONFIG_FILE", "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CONFIG_DIR",
                 "DOCKER_CONFIG", "KUBECONFIG", "SSH_AUTH_SOCK"):
        for path in os.environ.get(name, "").split(os.pathsep):
            if os.path.isabs(path):
                credentials.add(os.path.realpath(path))
    executables = set()
    search = os.environ.get("PATH", os.defpath).split(os.pathsep)
    search.extend(("/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/bin"))
    for directory in search:
        if os.path.isabs(directory):
            for name in ("gh", "glab"):
                path = Path(directory, name)
                if path.exists():
                    executables.update((str(path), os.path.realpath(path)))
    return sorted(credentials), sorted(executables)


def acquire_copy(source_root: str, head_sha: str, out_manifest: str,
                 label: str = "finder") -> dict:
    """Snapshot the worktree with independent metadata and record any divergence from HEAD."""
    if not isinstance(head_sha, str) or not _SHA.fullmatch(head_sha):
        raise ValueError("head_sha must be a full lowercase 40-character SHA")
    if not isinstance(label, str) or not _LABEL.fullmatch(label):
        raise ValueError("label must contain only letters, digits, underscores, or hyphens")
    if not isinstance(out_manifest, str) or not out_manifest or os.path.lexists(out_manifest):
        raise ValueError("out_manifest is required and must not already exist")
    if not isinstance(source_root, str) or not os.path.isdir(source_root):
        raise ValueError("source_root must be an existing git directory")
    root = Path(source_root).resolve()
    lease = _registry_root() / ("lease-" + secrets.token_hex(16))
    lease.mkdir(mode=0o700)
    copy, environment = lease / "copy", lease / "environment"
    copy.mkdir()
    environment.mkdir()
    try:
        with tempfile.TemporaryDirectory(prefix="deep-stage-", dir=str(lease)) as stage:
            bundle, staged_changes = _export_head(root, Path(stage), head_sha)
            snapshot_kind = _snapshot(root, copy)
            _checked_git("init", "--template=", "-q", str(copy))
            for key, value in (("core.hooksPath", "/dev/null"), ("core.fsmonitor", "false"),
                               ("core.attributesFile", "/dev/null")):
                _checked_git("-C", str(copy), "config", key, value)
            _checked_git("-C", str(copy), "fetch", "--no-tags", str(bundle), "HEAD")
            _checked_git("-C", str(copy), "update-ref", "--no-deref", "HEAD", head_sha)
            _checked_git("-C", str(copy), "read-tree", head_sha)
        changed = staged_changes or bool(_checked_git(
            "-C", str(copy), "status", "--porcelain", "--untracked-files=normal",
            "--ignored=matching").stdout.strip())
        for suffix in (*_ENV_DIRS.values(), "bin"):
            (environment / suffix).mkdir(mode=0o700)
        for name in ("gh", "glab"):
            _stub(environment / "bin" / name)
        kind = probe_capabilities(str(root))["sandbox_kind"]
        credentials, executables = _protected_paths()
        manifest = {"schema": 2, "lease_id": lease.name, "label": label,
                    "source_root": str(root), "head_sha": head_sha,
                    "copy_dir": str(copy), "env_dir": str(environment),
                    "copy_kind": "independent-copy", "snapshot_kind": snapshot_kind,
                    "source_state": {"kind": "worktree-snapshot", "local_changes": changed,
                                     "index": "rebuilt-from-head"},
                    "credential_paths": credentials, "blocked_executables": executables,
                    "sandbox_kind": kind, "os_enforced": kind != "worktree",
                    "isolation_warning": _FALLBACK_WARNING if kind == "worktree" else None,
                    "released": False}
        write_json(str(lease / "record.json"), manifest)
        write_json(out_manifest, manifest)
        return manifest
    except BaseException:
        shutil.rmtree(lease)
        raise


def _manifest(manifest_path: str, require_active: bool = True) -> dict:
    manifest = load_object(manifest_path, "deep copy manifest")
    lease_id = manifest.get("lease_id")
    if manifest.get("schema") != 2 or not isinstance(lease_id, str) or not re.fullmatch(
            r"lease-[0-9a-f]{32}", lease_id):
        raise ValueError("invalid deep copy manifest")
    lease = _registry_root() / lease_id
    if manifest.get("copy_dir") != str(lease / "copy") or manifest.get("env_dir") != str(
            lease / "environment") or manifest.get("copy_kind") != "independent-copy":
        raise ValueError("invalid deep copy manifest paths")
    if manifest.get("released") is True and not require_active:
        return manifest
    if lease.is_symlink() or not lease.is_dir():
        raise ValueError("deep copy has already been released or is missing")
    record = load_object(str(lease / "record.json"), "deep copy registration")
    if manifest != record:
        raise ValueError("deep copy manifest does not match its acquisition registration")
    for name in ("copy_dir", "env_dir"):
        path = Path(manifest[name])
        if path.is_symlink() or (not path.is_dir() and (require_active or path.exists())):
            raise ValueError("deep copy has already been released or is missing")
    return manifest


def _seatbelt_profile(copy_dir: str, env_dir: str,
                      credential_paths: list[str], blocked_executables: list[str]) -> str:
    def quoted(path: str) -> str:
        return json.dumps(path, ensure_ascii=False)

    writable = " ".join("(subpath %s)" % quoted(path) for path in (copy_dir, env_dir))
    protected = " ".join("(subpath %s)" % quoted(path) for path in credential_paths)
    blocked = " ".join("(literal %s)" % quoted(path) for path in blocked_executables)
    return ("(version 1)(allow default)(deny file-write*)"
            "(allow file-write* %s (literal \"/dev/null\") (literal \"/dev/zero\") "
            "(literal \"/dev/random\") (literal \"/dev/urandom\") (literal \"/dev/tty\"))"
            "(deny file-read* %s %s)(deny process-exec %s "
            "(require-all (regex #\"/(gh|glab)$\") (require-not (subpath %s))))"
            "(deny mach-lookup (global-name \"com.apple.securityd\") "
            "(global-name \"com.apple.secd\"))") % (
                writable, protected, blocked, blocked, quoted(env_dir))


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="backslashreplace") if isinstance(value, bytes) else value


def _bwrap_command(manifest: dict, cwd: str, argv: list[str]) -> list[str]:
    binary = shutil.which("bwrap")
    if not binary:
        raise ValueError("bwrap is no longer available")
    command = [binary, "--unshare-pid", "--die-with-parent", "--ro-bind", "/", "/",
               "--dev", "/dev", "--proc", "/proc",
               "--bind", manifest["copy_dir"], manifest["copy_dir"],
               "--bind", manifest["env_dir"], manifest["env_dir"]]
    masked = []
    for path in sorted(set(manifest["credential_paths"] + manifest["blocked_executables"]),
                       key=lambda item: (len(Path(item).parts), item)):
        if not os.path.exists(path) or any(path == parent or path.startswith(parent + os.sep)
                                           for parent in masked):
            continue
        if os.path.isdir(path):
            command.extend(("--tmpfs", path, "--remount-ro", path))
        else:
            command.extend(("--ro-bind", "/dev/null", path))
        masked.append(path)
    command.extend(("--chdir", cwd, "--", *argv))
    return command


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
    direct_forge = (os.path.basename(argv[0]) in ("gh", "glab")
                    or os.path.realpath(argv[0]) in manifest["blocked_executables"])
    env.update({name: str(Path(env_dir, suffix)) for name, suffix in _ENV_DIRS.items()})
    env["PATH"] = str(Path(env_dir, "bin")) + os.pathsep + env.get("PATH", "")
    if direct_forge:
        argv = [str(Path(env_dir, "bin", "gh"))]
    kind = manifest["sandbox_kind"]
    if kind == "sandbox-exec":
        run_command = ["/usr/bin/sandbox-exec", "-p",
                       _seatbelt_profile(root, env_dir, manifest["credential_paths"],
                                         manifest["blocked_executables"]), *argv]
    elif kind == "bwrap":
        run_command = _bwrap_command(manifest, cwd, argv)
    else:
        run_command = argv
    timed_out = False
    try:
        process = _run(run_command, timeout=timeout, cwd=cwd, env=env)
        exit_code = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code, timed_out = 124, True
        stdout, stderr = _text(exc.stdout), _text(exc.stderr)
    except FileNotFoundError as exc:
        exit_code, stdout, stderr = 127, "", str(exc)
    except PermissionError as exc:
        exit_code, stdout, stderr = 126, "", str(exc)
    blocked = "blocked in deep-mode throwaway copy" in stderr
    infrastructure_failure = (kind != "worktree" and exit_code != 0
                              and stderr.startswith(("sandbox-exec:", "bwrap:")))
    missing = (infrastructure_failure or "ModuleNotFoundError" in stderr or
               "ImportError" in stderr or "command not found" in stderr.lower() or
               (exit_code == 127 and not blocked)) and not timed_out
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr,
            "timed_out": timed_out, "sandbox_kind": kind,
            "os_enforced": manifest["os_enforced"],
            "isolation_warning": manifest["isolation_warning"],
            "environment_unavailable": missing,
            "unavailable_reason": stderr.strip() if missing else None}


def release_copy(manifest_path: str) -> dict:
    """Remove only the copy and environment named in an acquired manifest."""
    manifest = _manifest(manifest_path, require_active=False)
    copy_dir = manifest["copy_dir"]
    if not manifest.get("released"):
        lease = _registry_root() / manifest["lease_id"]
        shutil.rmtree(lease)
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
