"""Forge-neutral types for the review scripts.

The adapters in this package own every forge call: reads, posting, staging, publishing and
the reviewer's completion verdict. Scripts work on these shapes and on the `Forge`
protocol, and build an adapter with `make_forge`.

Two things stay outside the adapters. `post_reviewer_review` still picks the transport it
injects by forge name, and it reads draft and thread dicts with `forge.gitlab.draft_summary`
and `discussion_resolved`; both adapters return those shapes, so the helpers are neutral
in practice. `review_memory.fetch_discussions` passes a GET-only transport when it builds
a GitLab adapter.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit
from typing import List, Optional, Protocol

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ForgeError(RuntimeError):
    """A forge call or a forge response failed.

    `code` is one of: auth, not_found, conflict, validation, transient, unknown.
    It subclasses RuntimeError so callers that historically caught RuntimeError keep working.
    """

    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.code = code


def default_run(cmd, input_text=None, timeout=120, env=None):
    """Run a command, mapping launch failures and timeouts to a non-zero CompletedProcess."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, input=input_text,
                              timeout=timeout, shell=False, env=env)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def positive_int(value, label):
    """Return `value` as a positive int, or raise ForgeError naming `label`."""
    if isinstance(value, bool):
        raise ForgeError("%s must be a positive integer" % label, "validation")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ForgeError("%s must be a positive integer" % label, "validation")
    if number <= 0:
        raise ForgeError("%s must be a positive integer" % label, "validation")
    return number


def valid_sha(value, label):
    """Return `value` if it is a full lowercase SHA, else raise ForgeError naming `label`."""
    if not isinstance(value, str) or not SHA_RE.match(value):
        raise ForgeError("%s must be a full lowercase SHA" % label, "validation")
    return value


FORGE_NAMES = ("github", "gitlab", "none")
_KNOWN_HOSTS = {"github.com": "github", "gitlab.com": "gitlab"}
_AUTH_PROBES = {"github": ["gh", "auth", "status", "--hostname"],
                "gitlab": ["glab", "auth", "status", "--hostname"]}


def parse_origin(url):
    """Return (host, project) for an HTTP(S), SSH, or scp-style git remote.

    A filesystem remote has no host. The host is part of the identity because two
    forge instances can hold the same owner/repository path. An HTTP(S) port stays in
    the host (two instances can share a name and differ by port); an SSH port is dropped
    because it is not the port of the web host.
    """
    value = str(url or "").strip()
    host = None
    project = ""
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value):
        parsed = urlsplit(value)
        host = parsed.hostname.lower() if parsed.hostname else None
        try:
            port = parsed.port
        except ValueError:
            port = None
        if host and port and parsed.scheme.lower() in ("http", "https"):
            host = "%s:%d" % (host, port)
        project = parsed.path.lstrip("/")
    else:
        match = re.match(r"^(?:[^@/:]+@)?([^/:]+):(.+)$", value)
        if match:
            host = match.group(1).lower()
            project = match.group(2)
        else:
            project = value
    project = re.sub(r"\.git$", "", project).strip("/")
    return host, project


@dataclass
class ForgeChoice:
    name: str
    host: Optional[str]
    project: Optional[str]
    reason: str


def _probe_run(cmd, timeout=20):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _authenticated(run, forge_name, host):
    try:
        return run(_AUTH_PROBES[forge_name] + [host], timeout=20).returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def detect_forge(origin_url, override=None, run=None):
    """Choose github, gitlab, or none for a remote URL.

    `override` (from --forge) wins. github.com and gitlab.com are recognized directly;
    any other host is classified by which of `gh` / `glab` is authenticated for it, and
    an ambiguous or unauthenticated host yields "none" with a reason naming --forge.
    """
    if override is not None and override not in FORGE_NAMES:
        raise ValueError("--forge must be one of %s" % ", ".join(FORGE_NAMES))
    run = run or _probe_run
    host, project = parse_origin(origin_url) if str(origin_url or "").strip() else (None, None)
    project = project or None
    if override is not None:
        return ForgeChoice(override, host, project, "selected with --forge %s" % override)
    if not str(origin_url or "").strip():
        return ForgeChoice("none", None, None, "no origin remote is configured")
    if not host:
        return ForgeChoice("none", None, project, "origin is a filesystem remote with no forge host")
    if host in _KNOWN_HOSTS:
        return ForgeChoice(_KNOWN_HOSTS[host], host, project, "recognized host %s" % host)
    authed = [name for name in ("github", "gitlab") if _authenticated(run, name, host)]
    if len(authed) == 1:
        return ForgeChoice(authed[0], host, project,
                           "%s CLI is authenticated for %s" % ("gh" if authed[0] == "github" else "glab", host))
    if authed:
        reason = "both gh and glab are authenticated for %s; pass --forge github or --forge gitlab" % host
    else:
        reason = "neither gh nor glab is authenticated for %s; authenticate one or pass --forge" % host
    return ForgeChoice("none", host, project, reason)


def change_label(forge_name, number):
    """Human label for a change request: "PR #12" on GitHub, "MR !12" on GitLab."""
    return ("PR #%s" if forge_name == "github" else "MR !%s") % number


def note_url(forge_name, host, project, number, note_id):
    """Web URL of one posted note, for when the forge response did not include one."""
    if forge_name == "github":
        return "https://%s/%s/pull/%s#discussion_r%s" % (host, project, number, note_id)
    return "https://%s/%s/-/merge_requests/%s#note_%s" % (host, project, number, note_id)


def make_forge(name, host, project, run=None, api_call=None):
    """Return the adapter for `name` bound to host/project, or None for "none".

    `run` replaces the command runner and `api_call` the whole API transport (tests inject both).
    """
    if name == "none":
        return None
    if not host or not project:
        raise ForgeError("%s needs a host and project; pass --host and -R" % name, "validation")
    if name == "gitlab":
        from forge.gitlab import GitLabForge
        return GitLabForge(host, project, run=run, api_call=api_call)
    if name == "github":
        from forge.github import GitHubForge
        return GitHubForge(host, project, run=run, api_call=api_call)
    raise ValueError("unknown forge %r" % name)


class Forge(Protocol):
    """What the review scripts need from a code forge.

    Shapes are plain dicts so both adapters can return what the scripts already consume:

    change_records(number) -> {
        "number": int, "title": str, "description": str, "web_url": str,
        "author": str (username), "source_branch": str,
        "refs": {"base": sha|None, "start": sha|None, "head": sha|None},
        "records": [per-file change dicts: old_path, new_path, diff, new_file, deleted_file,
                    renamed_file, a_mode, b_mode, binary?, too_large?, collapsed?,
                    a_blob_id?, b_blob_id?],
        "reported_count": int | "N+" | None, "overflow": bool | None }
        Raises ForgeError(message) on any failure.
    change_details(number) -> {"number", "open": bool, "state", "author_id", "author_username",
        "source_branch", "target_branch", "sha", "base_sha", "start_sha", "web_url"} | None
    current_user() -> {"id", "username"} | None
    find_change_for_branch(branch) -> int | None
    list_threads(number) -> [{"id", "resolved"?, "web_url"?, "position"?,
        "notes": [{"id", "body", "author": {"id", "username"}, "web_url"?, "position"?,
                   "resolved"?}]}]   (raises ForgeError on incomplete pagination)

    The reviewer flow also needs the write side:

    inline_target(refs, old_path, new_path, line, diff_text, side) -> position | None
        None when the forge could not anchor `line` on the diff.
    complete(number, action, head_sha, body) -> dict
        action is "approve", "request-changes" or "comment-only"; `body` is the
        request-changes message on forges that take one.
    identity, live_change, changed_paths, pending, stage_notes, live_staged_ids, publish,
    post_inline, post_overview and cleanup_commands carry the staging and publishing steps.
    """

    name: str
    host: str
    project: str

    def change_label(self, number: int) -> str: ...
    def note_url(self, number: int, note_id) -> str: ...
    def change_records(self, number: int) -> dict: ...
    def change_details(self, number: int) -> Optional[dict]: ...
    def current_user(self) -> Optional[dict]: ...
    def find_change_for_branch(self, branch: str) -> Optional[int]: ...
    def head_refspec(self, number: int) -> str: ...
    def clone_command(self, dest: str) -> tuple: ...
    def list_threads(self, number: int, api_call=None) -> List[dict]: ...
    def inline_target(self, refs: dict, old_path: str, new_path: str, line: int,
                      diff_text: str, side: str = "new") -> Optional[dict]: ...
    def complete(self, number: int, action: str, head_sha: str, body: str) -> dict: ...
    def identity(self) -> dict: ...
    def live_change(self, number: int) -> tuple: ...
    def changed_paths(self, old_head: str, new_head: str) -> set: ...
    def pending(self, number: int, username: str) -> List[dict]: ...
    def stage_notes(self, number: int, notes: list, head_sha: str, record, username: str) -> None: ...
    def live_staged_ids(self, number: int, username: str) -> set: ...
    def publish(self, number: int, state: dict) -> None: ...
    def post_inline(self, number: int, body: str, position: dict, head_sha: str) -> dict: ...
    def post_overview(self, number: int, body: str) -> dict: ...
    def cleanup_commands(self, state: dict) -> List[str]: ...
