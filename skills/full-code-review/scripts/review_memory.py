#!/usr/bin/env python3
"""Durable, read-only cross-run memory for full code reviews of changes and branches.

The module deliberately contains no renderer or posting dependencies.  It stores
the reviewer's own decisions locally and uses GitHub or GitLab discussions only as a
read-only source of live publication state.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from forge import gitlab as _gitlab
from forge import make_forge, note_url as _note_url, parse_origin
from jsonio import load_object, write_json

SCHEMA_VERSION = 1
# bumped when the fingerprint inputs change; older ledgers are rekeyed on read
FINGERPRINT_SCHEME = 2
_RETENTION_SECONDS = 90 * 24 * 60 * 60
_FP_RE = re.compile(r"^[0-9a-f]{64}$")
_BLOCK_START_RE = re.compile(r"\A\s*<!--\s*quirk-review:v1\b")
_BLOCK_FP_RE = re.compile(
    r"\A\s*<!--\s*quirk-review:v1[ \t]*\r?\n(?:(?!-->).*\n)*?fp:[ \t]*([0-9a-f]{64})[ \t]*\r?\n")


def _normalize_project(project: Any) -> str:
    value = str(project or "").strip().strip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value.strip("/")


def _normalize_host(host: Any) -> str:
    value = str(host or "").strip().strip("/")
    if "://" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlparse(value)
    netloc = (parsed.netloc or parsed.path).strip().strip("/").lower()
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    return netloc


def _origin_identity(origin: Any) -> str | None:
    """Normalize HTTPS/SSH/SCP origins to ``host/project``."""
    if not origin or not isinstance(origin, str):
        return None
    host, project = parse_origin(origin)
    return "%s/%s" % (host, project) if host and project else None


def _git(*args: str, repo: str = ".") -> str | None:
    try:
        result = subprocess.run(["git", "-C", repo, *args], text=True,
                                capture_output=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def _repo_identity(repo: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    origin = _git("config", "--get", "remote.origin.url", repo=repo)
    normalized = _origin_identity(origin)
    if normalized:
        return normalized, warnings
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", repo=repo)
    if common:
        return "git-common-dir:" + os.path.realpath(common), ["origin remote unavailable; memory is scoped to this git common-dir"]
    return "repo:" + os.path.realpath(repo), ["origin remote unavailable; memory is scoped to this repository"]


def _state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(root) / "quirk" / "review-memory"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@contextmanager
def _locked(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".lock"
    with open(lock_path, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _target_identity(context: dict, repo: str) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    change_ctx = context.get("change") if isinstance(context.get("change"), dict) else {}
    # A prepared change request is authoritative even when the mode was branch/local.
    if change_ctx.get("number") is not None:
        host = _normalize_host(change_ctx.get("host") or context.get("host"))
        project = _normalize_project(change_ctx.get("project") or context.get("project"))
        if not host or not project or not str(change_ctx["number"]).isdigit() or int(change_ctx["number"]) < 1:
            raise ValueError("change memory requires host, project and a positive number")
        identity = {"repo": "%s/%s" % (host, project), "target": "change", "number": str(change_ctx["number"])}
    else:
        repository, repo_warnings = _repo_identity(repo)
        warnings.extend(repo_warnings)
        mode = context.get("mode")
        branch = context.get("source_branch")
        if not branch and mode in ("branch", "local"):
            branch = _git("branch", "--show-current", repo=repo)
        branch = str(branch or "(detached)")
        identity = {"repo": repository, "target": "branch" if mode == "branch" else "local", "branch": branch}
    return identity, warnings


def _target_key(identity: dict) -> str:
    return hashlib.sha256(_canonical_json(identity).encode()).hexdigest()


def _guidance_hash(paths: Any) -> str:
    digests = []
    for filename in sorted(str(p) for p in (paths or [])):
        try:
            with open(filename, "rb") as fh:
                content = fh.read()
            digests.append(hashlib.sha256(content).hexdigest())
        except OSError:
            digests.append("<unavailable>")
    return hashlib.sha256(_canonical_json(sorted(digests)).encode()).hexdigest()


def _diff_lines(diff: str) -> list[str]:
    """Split on newlines only; str.splitlines also breaks on form feed, NEL and U+2028."""
    lines = (diff or "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _decode_git_path(field: str) -> str | None:
    """Decode one raw or C-quoted path field as git emits it; None when malformed."""
    if not field.startswith('"'):
        return field
    if len(field) < 2 or not field.endswith('"'):
        return None
    data = bytearray()
    escapes = {"\\": 0x5c, '"': 0x22, "t": 0x09, "n": 0x0a, "r": 0x0d}
    i, end = 1, len(field) - 1
    while i < end:
        char = field[i]
        i += 1
        if char != "\\":
            data.extend(char.encode("utf-8", "surrogateescape"))
            continue
        if i >= end:
            return None
        char = field[i]
        if char in escapes:
            data.append(escapes[char])
            i += 1
        elif char in "01234567":
            octal = re.match(r"[0-7]{1,3}", field[i:end]).group(0)
            data.append(int(octal, 8) & 0xff)
            i += len(octal)
        else:
            data.extend(char.encode("utf-8", "surrogateescape"))
            i += 1
    return data.decode("utf-8", "surrogateescape")


def _quoted_field_end(text: str) -> int | None:
    i = 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
        elif text[i] == '"':
            return i + 1
        else:
            i += 1
    return None


def _strip_prefix(path: str | None, prefix: str) -> str | None:
    return path[2:] if path and path.startswith(prefix) else path


def _header_path(text: str, prefix: str) -> str | None:
    """Decode a ---/+++ path field, dropping git's a/ or b/ prefix and any timestamp."""
    text = text.strip()
    if text.startswith('"'):
        end = _quoted_field_end(text)
        decoded = _decode_git_path(text[:end]) if end is not None else None
    else:
        decoded = text.split("\t", 1)[0].rstrip()
    return _strip_prefix(decoded, prefix)


def _diff_git_paths(line: str) -> tuple[str, str] | None:
    """The (old, new) paths of a `diff --git` line with prefixes removed, or None."""
    payload = line[len("diff --git "):]
    if payload.startswith('"'):
        end = _quoted_field_end(payload)
        if end is None or end >= len(payload) or not payload[end].isspace():
            return None
        first, second = payload[:end], payload[end:].lstrip()
        if second.startswith('"') and _quoted_field_end(second) != len(second):
            return None
        pairs = [(first, second)]
    else:
        pairs = []
        for marker in (" b/", ' "b/'):
            pos = payload.find(marker)
            while pos >= 0:
                pairs.append((payload[:pos], payload[pos + 1:]))
                pos = payload.find(marker, pos + 1)
    decoded = [(_decode_git_path(a), _decode_git_path(b)) for a, b in pairs]
    decoded = [(a, b) for a, b in decoded if a and b and a.startswith("a/") and b.startswith("b/")]
    if not decoded:
        return None
    old, new = next(((a, b) for a, b in decoded if a[2:] == b[2:]), decoded[0])
    return old[2:], new[2:]


def _diff_sections(diff: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in _diff_lines(diff):
        if line.startswith("diff --git "):
            paths = _diff_git_paths(line)
            current = paths[1] if paths else None
            if current:
                sections.setdefault(current, []).append(line)
        elif current:
            sections[current].append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def _file_hashes(context: dict) -> dict[str, str]:
    return {path: hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()
            for path, text in _diff_sections(context.get("diff") or "").items()}


def _read_record(path: Path) -> tuple[dict | None, list[str]]:
    warnings: list[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None, warnings
    except (OSError, ValueError):
        return None, ["memory ledger %s unreadable; continuing with a clean snapshot" % path]
    if not isinstance(data, dict):
        return None, ["memory ledger %s is not an object; continuing with a clean snapshot" % path]
    version = data.get("schemaVersion", 0)
    if type(version) is not int or version < 0:
        return None, ["memory ledger %s has an invalid schema version; refusing overwrite" % path]
    if version > SCHEMA_VERSION:
        return None, ["memory ledger %s uses an unsupported future schema; continuing with a clean snapshot" % path]
    if version == 0:
        data["schemaVersion"] = SCHEMA_VERSION
        warnings.append("migrated legacy memory ledger")
    snapshot = data.get("snapshot")
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("identity"), dict)
            or not isinstance(snapshot.get("findings"), list)
            or any(not isinstance(item, dict) for item in snapshot["findings"])
            or type(snapshot.get("started_at")) not in (int, float)
            or not isinstance(snapshot.get("file_hashes"), dict)):
        return None, ["memory ledger %s has an invalid snapshot; refusing overwrite" % path]
    for finding in snapshot["findings"]:
        fp = finding.get("fingerprint")
        if (not isinstance(fp, str) or not _FP_RE.fullmatch(fp)
                or any(not isinstance(finding.get(field), str) for field in ("dimension", "file", "note"))
                or finding.get("disposition") not in ("fix", "later", "detail", "ignore", "none")
                or finding.get("seat") not in ("author", "reviewer")
                or ("receipt" in finding and not isinstance(finding["receipt"], dict))):
            return None, ["memory ledger %s has an invalid finding; refusing overwrite" % path]
    if data.get("fingerprintScheme", 1) != FINGERPRINT_SCHEME:
        data["fingerprintScheme"] = FINGERPRINT_SCHEME
        warnings.append("migrated memory ledger to fingerprint scheme %d" % FINGERPRINT_SCHEME)
        warnings.extend(_rekey_findings(snapshot))
    return data, warnings


def _rekey_findings(snapshot: dict) -> list[str]:
    """Recompute stored fingerprints under the current scheme from each entry's anchor hash.

    Entries without a usable anchor hash keep their old fingerprint, which no longer matches
    any current finding. Entries that collapse onto one fingerprint are dropped because the
    ledger cannot tell them apart. Threads posted under the old fingerprints stay unmatched,
    so findings already published may be offered for posting again once.
    """
    groups: dict[str, list[dict]] = {}
    for finding in snapshot["findings"]:
        anchor_hash = finding.get("anchor_hash")
        if isinstance(anchor_hash, str) and _FP_RE.fullmatch(anchor_hash):
            finding["fingerprint"] = _fingerprint_of(finding["file"], anchor_hash)
        groups.setdefault(finding["fingerprint"], []).append(finding)
    snapshot["findings"] = [group[0] for group in groups.values() if len(group) == 1]
    dropped = sum(len(group) for group in groups.values() if len(group) > 1)
    return ["dropped %d prior finding(s) whose fingerprints became ambiguous" % dropped] if dropped else []


def _prune(directory: Path, now: float) -> None:
    cutoff = now - _RETENTION_SECONDS
    for path in directory.glob("*.json"):
        try:
            data, _ = _read_record(path)
            if data is None:
                touched = path.stat().st_mtime
            else:
                touched = float(data.get("updated_at", data["snapshot"]["started_at"]))
            if touched < cutoff:
                path.unlink()
        except (OSError, ValueError, TypeError):
            continue


def _default_api(host: str, method: str, endpoint: str, payload: Any = None):
    if method.upper() != "GET":
        raise ValueError("review memory only permits GET discussion requests")
    return _gitlab.get_json(host, endpoint)


def fetch_discussions(host: str, project: str, number: Any, api: Callable | None = None,
                      forge: str = "gitlab") -> list[dict]:
    """Fetch every review thread as a discussion dict, rejecting incomplete pagination.

    Read-only: GitLab access is restricted to GET requests.
    """
    if not host or not project or not str(number).isdigit() or int(number) < 1:
        raise ValueError("host, project and positive change number are required")
    adapter = make_forge(forge, host, _normalize_project(project))
    if adapter is None:
        raise ValueError("no forge adapter for %r" % forge)
    return adapter.list_threads(int(number), api_call=api or (_default_api if forge == "gitlab" else None))


def load_snapshot(context: dict, repo: str = ".", dimensions=(), guidance=(), fresh: bool = False) -> dict:
    """Load the prior ledger for this review target and start a new run generation.

    Prior decisions carry over only while the target identity, base SHA, review
    dimensions and guidance are unchanged, or never when `fresh` is set; otherwise the
    snapshot records why they were discarded. Live discussions are fetched for change
    requests. An unreadable ledger or failed fetch becomes a warning rather than an error.
    """
    identity, warnings = _target_identity(context, repo)
    key = _target_key(identity)
    directory = _state_dir()
    path = directory / (key + ".json")
    refs = context.get("refs") if isinstance(context.get("refs"), dict) else {}
    base_sha, head_sha = refs.get("base"), refs.get("head")
    dims = sorted({str(item) for item in (dimensions or [])})
    guidance_hash = _guidance_hash(guidance)
    hashes = _file_hashes(context)
    old = None
    try:
        with _locked(directory):
            old, read_warnings = _read_record(path)
            warnings.extend(read_warnings)
    except OSError as exc:
        warnings.append("memory ledger unavailable: %s" % exc)
    old_snapshot = old.get("snapshot") if old else None
    reason = None
    if fresh:
        reason = "fresh requested"
    elif old_snapshot:
        if old_snapshot.get("identity") != identity:
            reason = "target identity changed"
        elif old_snapshot.get("base_sha") != base_sha:
            reason = "base SHA changed"
        elif old_snapshot.get("dimensions", []) != dims:
            reason = "review dimensions changed"
        elif old_snapshot.get("guidance_hash") != guidance_hash:
            reason = "review guidance changed"
    prior = [] if reason else list(old_snapshot.get("findings", [])) if old_snapshot else []
    discussions: list[dict] = []
    available = True
    change_ctx = context.get("change") if isinstance(context.get("change"), dict) else {}
    if change_ctx.get("number") is not None:
        try:
            discussions = fetch_discussions(change_ctx.get("host") or context.get("host"),
                                            change_ctx.get("project") or context.get("project"), change_ctx["number"], forge=context.get("forge", "gitlab"))
        except Exception as exc:
            available = False
            warnings.append("discussion cross-check unavailable: %s" % exc)
    unavailable = set(context.get("diff_unavailable") or []) | set(context.get("not_text_reviewable") or [])
    unchanged = [] if reason or not old_snapshot else sorted(
        path_name for path_name, digest in hashes.items()
        if old_snapshot.get("file_hashes", {}).get(path_name) == digest and path_name not in unavailable)
    snapshot = {
        "schemaVersion": SCHEMA_VERSION, "target_key": key, "identity": identity,
        "seat": context.get("seat", "author"), "base_sha": base_sha, "head_sha": head_sha,
        "previous_head_sha": old_snapshot.get("head_sha") if old_snapshot and not reason else None,
        "dimensions": dims, "guidance_hash": guidance_hash, "started_at": time.time(),
        "findings": prior, "discussions": discussions, "discussions_available": available,
        "warnings": list(warnings), "invalidation_reason": reason,
        "file_hashes": hashes, "unchanged_files": unchanged,
    }
    return snapshot


def validate_snapshot(snapshot: dict, context: dict, repo: str = ".") -> list[str]:
    """Validate persisted target, generation and current diff binding."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("identity"), dict):
        raise ValueError("snapshot has no identity")
    if type(snapshot.get("schemaVersion")) is not int or snapshot["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported snapshot schema")
    identity, warnings = _target_identity(context, repo)
    if snapshot["identity"] != identity or snapshot.get("target_key") != _target_key(identity):
        raise ValueError("memory snapshot identity does not match review context")
    if not isinstance(snapshot.get("target_key"), str) or not _FP_RE.match(snapshot["target_key"]):
        raise ValueError("memory snapshot target key is invalid")
    refs = context.get("refs") if isinstance(context.get("refs"), dict) else {}
    if snapshot.get("base_sha") != refs.get("base") or snapshot.get("head_sha") != refs.get("head"):
        raise ValueError("memory snapshot diff refs do not match review context")
    if snapshot.get("seat", "author") != context.get("seat", "author"):
        raise ValueError("memory snapshot seat does not match review context")
    return warnings


def _derive_title(issue: Any) -> str:
    value = "" if issue is None else str(issue)
    value = re.split(r"(?<=[.;:])\s+", value.strip(), maxsplit=1)[0]
    value = re.sub(r"\s+", " ", value).rstrip(".;:")
    if not value:
        return "Untitled finding"
    if len(value) > 80:
        cut = value.rfind(" ", 0, 77)
        if cut < 1:
            cut = 77
        value = value[:cut].rstrip() + "…"
    return value


def _line_number(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def _paths_from_header(lines: list[str]) -> tuple[str | None, str | None]:
    """The (old, new) paths a diff section names, decoded; ---/+++ and renames win over the git line."""
    old = new = None
    if lines and lines[0].startswith("diff --git "):
        old, new = _diff_git_paths(lines[0]) or (None, None)
    for line in lines[1:]:
        if line.startswith("@@"):
            break
        if line.startswith("--- "):
            old = _header_path(line[4:], "a/") or old
        elif line.startswith("+++ "):
            new = _header_path(line[4:], "b/") or new
        elif line.startswith("rename from "):
            old = _decode_git_path(line[len("rename from "):]) or old
        elif line.startswith("rename to "):
            new = _decode_git_path(line[len("rename to "):]) or new
    return old, new


def _line_span(value: Any) -> tuple[int, int] | None:
    numbers = [int(item) for item in re.findall(r"\d+", str(value or ""))]
    if not numbers:
        return None
    last = numbers[1] if len(numbers) > 1 and numbers[1] >= numbers[0] else numbers[0]
    return numbers[0], last


def _anchor(diff: str, file: str, line: Any, side: str = "new") -> str | None:
    """Text of the first nonblank diff line inside the finding's line range, or None.

    A range that opens on blank lines anchors on its first nonblank line. None means that
    line is ambiguous in the diff or the range has no nonblank line the diff shows.
    """
    span = _line_span(line)
    if span is None:
        return None
    first, last = span
    lines = _diff_lines(diff)
    section: list[str] = []
    sections: list[list[str]] = []
    for text in lines:
        if text.startswith("diff --git "):
            if section:
                sections.append(section)
            section = [text]
        elif section:
            section.append(text)
    if section:
        sections.append(section)
    candidates: dict[int, list[str]] = {}
    for section in sections:
        old_path, new_path = _paths_from_header(section)
        if file not in (old_path, new_path):
            continue
        old_no = new_no = None
        for text in section:
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", text)
            if match:
                old_no, new_no = int(match.group(1)), int(match.group(3))
                continue
            if old_no is None or not text:
                continue
            prefix, content = text[0], text[1:]
            if prefix == "\\":
                continue
            number = old_no if side == "old" else new_no
            if first <= number <= last and prefix in ((" ", "-") if side == "old" else (" ", "+")):
                candidates.setdefault(number, []).append(content)
            if prefix in (" ", "-"):
                old_no += 1
            if prefix in (" ", "+"):
                new_no += 1
    for number in sorted(candidates):
        if any(_norm_anchor(content) for content in candidates[number]):
            return candidates[number][0] if len(candidates[number]) == 1 else None
    return None


def _norm_anchor(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fingerprint_of(file: str, anchor_hash: str) -> str:
    return hashlib.sha256((file + "\0" + anchor_hash).encode("utf-8", "surrogateescape")).hexdigest()


def _fingerprint(file: str, text: str) -> tuple[str, str]:
    """Identity of a finding's diff anchor: stable across lens tags, which vary per run."""
    anchor_hash = hashlib.sha256(_norm_anchor(text).encode("utf-8", "surrogateescape")).hexdigest()
    return _fingerprint_of(file, anchor_hash), anchor_hash


def _note_author(note: dict) -> tuple[str, str]:
    """Return a note's (username, user_id) across both GitLab note shapes."""
    author = note.get("author")
    if isinstance(author, dict):
        return str(author.get("username") or ""), str(author.get("id") or "")
    return str(note.get("author_username") or ""), str(note.get("author_id") or "")


def note_is_from(note: dict, username: Any, user_id: Any) -> bool:
    """Whether a GitLab note was written by the given authenticated identity.

    Establishes that a marked note really is one of our own published findings:
    markers are copyable text, so a fingerprint match alone proves nothing.
    Returns False whenever no identity was supplied to compare against.
    """
    author, author_id = _note_author(note)
    if user_id is not None and author_id:
        return str(user_id) == author_id
    if username and author:
        return str(username).casefold() == author.casefold()
    return False


def _is_posting_identity(note: dict, context: dict) -> bool:
    change_ctx = context.get("change") or {}
    return note_is_from(note, change_ctx.get("current_username"), change_ctx.get("current_user_id"))


def marker_fingerprints(body: Any) -> list[str]:
    """Return the lowercase finding fingerprints a posted note body carries.

    Only a body that begins with a `quirk-review:v1` block carries a fingerprint: that block's
    `fp:` line (none for overview blocks, whose list values are not fingerprints). A block quoted
    later in a body does not count, because the rest of a body embeds untrusted report text.
    Line endings may be LF or CRLF. Never raises: non-str input yields [].

    Callers must still check the note's author; markers are copyable text.
    """
    if not isinstance(body, str):
        return []
    if _BLOCK_START_RE.match(body):
        block = _BLOCK_FP_RE.match(body)
        return [block.group(1)] if block else []
    return []


def _discussion_details(discussions: list[dict], fp: str | None, finding: dict, context: dict) -> tuple[dict | None, list[dict]]:
    marker_matches: list[dict] = []
    human: list[dict] = []
    file = str(finding.get("file", ""))
    wanted = _line_number(finding.get("line"))
    change_ctx = context.get("change") or {}
    host = change_ctx.get("host") or context.get("host")
    project = change_ctx.get("project") or context.get("project")

    def note_url(note, discussion):
        explicit = note.get("web_url") or discussion.get("web_url")
        if explicit:
            return explicit
        if host and project and change_ctx.get("number") and note.get("id") is not None:
            return _note_url(context.get("forge", "gitlab"), _normalize_host(host),
                             _normalize_project(project), change_ctx["number"], note["id"])
        return None
    for discussion in discussions or []:
        notes = discussion.get("notes")
        if not isinstance(notes, list):
            notes = []
        # markers are copyable, so only the posting identity's notes prove we posted
        marked = any(marker_fingerprints(str(note.get("body") or note.get("note") or ""))
                     and _is_posting_identity(note, context)
                     for note in notes if isinstance(note, dict))
        found = None
        replies = []
        for index, note in enumerate(notes):
            if not isinstance(note, dict):
                continue
            body = str(note.get("body") or note.get("note") or "")
            if fp and fp.lower() in marker_fingerprints(body) and _is_posting_identity(note, context):
                found = note
                root_author = _note_author(note)[0]
                for reply in notes[index + 1:]:
                    if not isinstance(reply, dict):
                        continue
                    author = _note_author(reply)[0]
                    if reply.get("system") or (root_author and author == root_author):
                        continue
                    replies.append({"author": author or "", "body": str(reply.get("body") or reply.get("note") or "")})
                break
        if found is not None:
            thread = {"discussion_id": discussion.get("id"), "note_id": found.get("id"),
                      "url": note_url(found, discussion),
                      "resolved": bool(discussion.get("resolved") or found.get("resolved")),
                      "replies": replies}
            marker_matches.append(thread)
            continue
        if marked:
            continue
        # Unmarked positioned comments are context only.
        position = discussion.get("position") or (notes[0].get("position") if notes and isinstance(notes[0], dict) else {})
        if isinstance(position, dict) and position.get("new_path", position.get("old_path")) == file:
            pos_line = position.get("new_line") if position.get("new_line") is not None else position.get("old_line")
            if wanted is not None and _line_number(pos_line) == wanted:
                root = notes[0] if notes and isinstance(notes[0], dict) else {}
                note_id, discussion_id = root.get("id"), discussion.get("id")
                # render rejects an entry without usable ids, so drop the one record, not the report
                if (not isinstance(note_id, int) or isinstance(note_id, bool)
                        or not isinstance(discussion_id, str) or not discussion_id):
                    continue
                author = _note_author(root)[0]
                human.append({"discussion_id": discussion_id, "note_id": note_id,
                              "author": author or "", "url": note_url(root, discussion),
                              "body": str(root.get("body") or root.get("note") or ""),
                              "resolved": bool(discussion.get("resolved") or root.get("resolved")),
                              "own": _is_posting_identity(root, context)})
    if marker_matches:
        # Multiple live markers are ambiguous; an open one is the conservative
        # suppression choice while retaining the first thread context.
        open_threads = [item for item in marker_matches if not item.get("resolved")]
        return (open_threads[0] if open_threads else marker_matches[0]), human
    return None, human


def _validate_report_binding(report: dict, snapshot: dict) -> None:
    meta = report.get("meta")
    identity = snapshot.get("identity")
    if not isinstance(meta, dict) or not isinstance(identity, dict):
        raise ValueError("report and memory snapshot require target identity")
    target = identity.get("target")
    if meta.get("target") != target:
        raise ValueError("report target does not match memory snapshot")
    if target == "change" and str(meta.get("number")) != str(identity.get("number")):
        raise ValueError("report change number does not match memory snapshot")
    if target == "branch" and meta.get("branch") != identity.get("branch"):
        raise ValueError("report branch does not match memory snapshot")
    if meta.get("project") is not None and identity.get("repo", "").split("/", 1)[-1] != _normalize_project(meta["project"]):
        raise ValueError("report project does not match memory snapshot")
    if meta.get("head_sha") is not None and meta["head_sha"] != snapshot.get("head_sha"):
        raise ValueError("report head does not match memory snapshot")
    if meta.get("seat", "author") != snapshot.get("seat"):
        raise ValueError("report seat does not match memory snapshot")



def _prior_text(prior: dict) -> str:
    return "\n".join(str(prior.get(key) or "") for key in ("title", "body_md"))


_SAME_FINDING_THRESHOLD = 0.55


def _same_finding(prior: dict, finding: dict) -> bool:
    """Whether an exact fingerprint match is plausibly the same finding, not another one on a repeated line."""
    prior_text = _prior_text(prior).strip()
    if not prior_text:
        return True
    return difflib.SequenceMatcher(None, prior_text.lower(),
                                   _prior_text(finding).strip().lower()).ratio() >= _SAME_FINDING_THRESHOLD


def reconcile(report: dict, context: dict, snapshot: dict, repo: str = ".") -> dict:
    """Return a copy of `report` with each finding's `memory` block filled in.

    Matches findings to the snapshot's prior decisions and live threads by diff-anchor
    fingerprint, and lists previously posted findings that no longer appear. `repo` must be
    the reviewed repository so branch and local identities resolve against it. Raises
    ValueError when the snapshot or report does not bind to `context`, or when a
    finding's `anchor_side` is not "new" or "old". Does not modify its inputs.
    """
    validate_snapshot(snapshot, context, repo)
    _validate_report_binding(report, snapshot)
    enriched = copy.deepcopy(report)
    warnings = list(snapshot.get("warnings") or [])
    prior = snapshot.get("findings") or []
    seat = snapshot["seat"]
    available = snapshot.get("discussions_available", False)
    discussions = snapshot.get("discussions", []) if available else []
    change_context = context.get("change") or {}
    if discussions and not (change_context.get("current_username") or change_context.get("current_user_id") is not None):
        warnings.append("Posting identity unknown; posted markers are treated as human context.")
    current_counts, prior_by_fp = {}, {}
    for item in prior:
        if item.get("fingerprint"):
            prior_by_fp.setdefault(item["fingerprint"], []).append(item)
    for finding in enriched["findings"]:
        if finding.get("anchor_side", "new") not in ("new", "old"):
            raise ValueError("finding anchor_side must be new or old")
        dimensions = finding.get("dimensions") or []
        dimension = finding.get("dimension") or (sorted(dimensions)[0] if dimensions else "unknown")
        finding["file"] = str(finding["file"]).strip()
        finding["line"] = str(finding["line"]).strip()
        if finding.get("title") is None:
            finding["title"] = _derive_title(finding.get("issue", finding.get("body_md")))
        if finding.get("body_md") is None and finding.get("issue") is not None:
            finding["body_md"] = str(finding["issue"])
        if finding.get("recommendation_md") is None and finding.get("recommendation") is not None:
            finding["recommendation_md"] = str(finding["recommendation"])
        text = _anchor(context.get("diff", ""), finding["file"], finding["line"],
                       finding.get("anchor_side", "new"))
        fp, anchor_hash = _fingerprint(finding["file"], text) if text and _norm_anchor(text) else (None, None)
        if fp:
            current_counts[fp] = current_counts.get(fp, 0) + 1
        else:
            warnings.append("No unique nonblank diff anchor for %s:%s; treating as new." %
                            (finding["file"], finding["line"]))
        finding["memory"] = {
            "fingerprint": fp, "dimension": dimension, "anchor_hash": anchor_hash,
            "state": "new", "match": None, "disposition": "none", "note": "",
            "suppress_post": False, "thread": None, "candidates": [], "human_context": [],
        }

    matched_prior = set()
    for finding in enriched["findings"]:
        memory = finding["memory"]
        fp = memory["fingerprint"]
        matches = prior_by_fp.get(fp, [])
        ambiguous = fp and (current_counts[fp] > 1 or len(matches) > 1)
        if ambiguous:
            warnings.append("Ambiguous fingerprint at %s:%s; treating as new without a posting marker." %
                            (finding["file"], finding["line"]))
            matched_prior.add(fp)
            memory["fingerprint"] = fp = None
        previous = matches[0] if fp and len(matches) == 1 else None
        diverged = previous is not None and not _same_finding(previous, finding)
        if diverged:
            warnings.append("Fingerprint at %s:%s matches a prior finding with different text; treating as new." %
                            (finding["file"], finding["line"]))
            previous = None
        thread, human = _discussion_details(discussions, None if diverged else fp, finding, context)
        memory["thread"], memory["human_context"] = thread, human
        if previous:
            matched_prior.add(fp)
            memory["match"] = "exact"
            if previous.get("seat") == seat:
                memory["disposition"] = previous.get("disposition", "none")
                memory["note"] = previous.get("note", "")
                if memory["disposition"] != "none":
                    memory["state"] = "restored-decision"
        if thread:
            memory["match"] = "exact"
            memory["suppress_post"] = True
            if thread["resolved"]:
                memory["state"], memory["disposition"] = "re-found-after-resolution", "none"
            else:
                memory["state"] = "answered" if thread["replies"] else "carried"
        elif previous and (previous.get("receipt") or {}).get("published") and not available:
            # The decision is usable offline; forge delivery still requires a live GET.
            memory["state"] = "carried"
        elif fp and not previous:
            for candidate in prior:
                if candidate.get("file") != finding["file"] or not candidate.get("fingerprint"):
                    continue
                score = difflib.SequenceMatcher(None, _prior_text(candidate).lower(),
                                               _prior_text(finding).lower()).ratio()
                if score < _SAME_FINDING_THRESHOLD:
                    continue
                candidate_thread, _ = _discussion_details(
                    discussions, candidate["fingerprint"], candidate, context)
                memory["candidates"].append({
                    "fingerprint": candidate["fingerprint"], "title": candidate.get("title", ""),
                    "body_md": candidate.get("body_md", ""), "similarity": round(score, 3),
                    "thread": candidate_thread,
                })
                matched_prior.add(candidate["fingerprint"])
            memory["candidates"].sort(key=lambda item: (-item["similarity"], item["fingerprint"]))
            if memory["candidates"]:
                memory["match"] = "candidate"
                resolved = next((item["thread"] for item in memory["candidates"]
                                 if item["thread"] and item["thread"]["resolved"]), None)
                if resolved:
                    memory["state"], memory["thread"] = "possible-regression", resolved

    unavailable = set(context.get("diff_unavailable") or []) | set(context.get("not_text_reviewable") or [])
    completed = set((report.get("run") or {}).get("dimensions_run") or [])
    current_fps = set(current_counts)
    appears_fixed = []
    for previous in prior:
        fp = previous.get("fingerprint")
        if (not fp or fp in current_fps or fp in matched_prior
                or previous.get("dimension") not in completed or previous.get("file") in unavailable):
            continue
        thread, _ = _discussion_details(discussions, fp, previous, context)
        if not thread and not (previous.get("receipt") or {}).get("published"):
            continue
        value = _safe_record(previous)
        value["thread"] = thread
        appears_fixed.append(value)
    enriched["memory"] = {"snapshot": copy.deepcopy(snapshot),
                          "appears_fixed": appears_fixed, "warnings": warnings}
    return enriched


def _report_digest(report: dict) -> str:
    return hashlib.sha256(_canonical_json(report).encode("utf-8", "surrogateescape")).hexdigest()


def _safe_record(item: dict) -> dict:
    allowed = ("fingerprint", "dimension", "anchor_hash", "severity", "file", "line", "title", "body_md",
               "recommendation_md", "disposition", "note", "seat", "receipt", "state", "thread")
    result = {key: copy.deepcopy(item[key]) for key in allowed if key in item}
    return result


def commit_report(report: dict, decisions: dict | None = None, receipts: dict | None = None) -> dict:
    """Persist triage decisions and publication receipts to the durable ledger.

    `decisions` must be bound to this exact report and seat; `receipts` may stand alone and
    only record confirmed publications. Returns `{"saved": bool, "warnings": [...]}`:
    `saved` is False, not an exception, when the report carries no memory snapshot, a newer
    run already wrote the ledger, the existing ledger is unreadable, or the write fails.
    Raises ValueError for malformed or mismatched decisions, receipts and snapshots.
    """
    memory = report.get("memory") if isinstance(report, dict) else None
    if not isinstance(memory, dict) or not isinstance(memory.get("snapshot"), dict):
        return {"saved": False, "warnings": ["report has no memory snapshot; nothing saved"]}
    snapshot = memory["snapshot"]
    _validate_report_binding(report, snapshot)
    key = snapshot.get("target_key")
    if (type(snapshot.get("schemaVersion")) is not int or snapshot["schemaVersion"] != SCHEMA_VERSION or not isinstance(key, str)
            or not _FP_RE.fullmatch(key) or key != _target_key(snapshot["identity"])):
        raise ValueError("memory snapshot has an invalid schema or target key")
    started = snapshot.get("started_at")
    if type(started) not in (int, float) or not 0 < started < float("inf"):
        raise ValueError("memory snapshot has an invalid generation")
    seat = snapshot["seat"]
    ranked = sorted(report["findings"], key=lambda item: {"Must fix": 0, "Should fix": 1, "Nit": 2}[item["severity"]])
    by_id = {"F%d" % rank: item for rank, item in enumerate(ranked, 1)}
    rows = {}
    if decisions is not None:
        if (decisions.get("schema") != 1 or decisions.get("seat") != seat
                or decisions.get("report_sha256") != _report_digest(report)):
            raise ValueError("decisions are not bound to this exact report and seat")
        for row in decisions.get("decisions", []):
            if (not isinstance(row, dict) or row.get("id") not in by_id
                    or row["id"] in rows or row.get("slot") not in ("fix", "later", "detail", "ignore", "none")
                    or not isinstance(row.get("note", ""), str)):
                raise ValueError("invalid or duplicate finding decision")
            rows[row["id"]] = row
        if set(rows) != set(by_id):
            raise ValueError("decision finding ID set does not match report")
    elif receipts is None:
        raise ValueError("receipt-only save requires receipts")
    receipts = {} if receipts is None else receipts
    if not isinstance(receipts, dict):
        raise ValueError("receipts must be an object")
    for finding_id, receipt in receipts.items():
        if finding_id not in by_id or not isinstance(receipt, dict) or receipt.get("published") is not True:
            raise ValueError("receipt requires a known finding and confirmed publication")
    counts = {}
    for finding in ranked:
        fp = (finding.get("memory") or {}).get("fingerprint")
        if fp:
            if not isinstance(fp, str) or not _FP_RE.fullmatch(fp):
                raise ValueError("invalid finding fingerprint")
            counts[fp] = counts.get(fp, 0) + 1
    directory = _state_dir()
    ledger_path = directory / (key + ".json")
    warnings = []
    try:
        with _locked(directory):
            record, read_warnings = _read_record(ledger_path)
            warnings.extend(read_warnings)
            if record is None and ledger_path.exists():
                return {"saved": False, "warnings": warnings + [
                    "refusing destructive ledger overwrite; fix or delete %s to resume saving" % ledger_path]}
            stored = (record or {}).get("snapshot", {})
            if stored.get("started_at", 0) > started:
                return {"saved": False, "warnings": ["stale review run refused; newer memory exists"]}
            same_run = stored.get("started_at") == started
            clear = snapshot.get("invalidation_reason") and not same_run
            merged = {} if clear else {item["fingerprint"]: copy.deepcopy(item)
                                      for item in stored.get("findings", []) if item.get("fingerprint")}
            for finding_id, finding in by_id.items():
                fm = finding.get("memory") or {}
                fp = fm.get("fingerprint")
                if not fp or counts[fp] != 1:
                    continue
                previous = merged.get(fp, {})
                entry = _safe_record({**finding, **fm, "seat": seat})
                if "receipt" in previous:
                    entry["receipt"] = copy.deepcopy(previous["receipt"])
                if decisions is None and previous:
                    for field in ("disposition", "note", "seat"):
                        if field in previous:
                            entry[field] = previous[field]
                elif finding_id in rows:
                    entry["disposition"] = rows[finding_id]["slot"]
                    entry["note"] = rows[finding_id].get("note", "")
                if finding_id in receipts:
                    entry["receipt"] = {field: copy.deepcopy(value) for field, value in receipts[finding_id].items()
                                        if field in ("published", "discussion_id", "note_id", "url", "head_sha")}
                merged[fp] = entry
            new_snapshot = copy.deepcopy(snapshot)
            new_snapshot["findings"] = list(merged.values())
            # The ledger does not need a second copy of live discussion history.
            new_snapshot["discussions"] = []
            new_record = {**(record or {}), "schemaVersion": SCHEMA_VERSION,
                          "fingerprintScheme": FINGERPRINT_SCHEME, "snapshot": new_snapshot, "updated_at": time.time()}
            write_json(ledger_path, new_record)
            _prune(directory, time.time())
    except OSError as exc:
        return {"saved": False, "warnings": warnings + ["could not persist review memory: %s" % exc]}
    return {"saved": True, "warnings": warnings}


def _load_json(path: str, label: str = "JSON input") -> dict:
    return load_object(path, label)


def check_plan(report: dict, context: dict, snapshot: dict, repo: str = ".") -> dict:
    """Build the author-delivery suppression plan without changing any input."""
    identity_warnings = validate_snapshot(snapshot, context, repo)
    refreshed = copy.deepcopy(snapshot)
    change_ctx = context.get("change") if isinstance(context.get("change"), dict) else {}
    warnings = list(identity_warnings)
    if change_ctx.get("number") is not None:
        try:
            refreshed["discussions"] = fetch_discussions(change_ctx.get("host") or context.get("host"),
                                                         change_ctx.get("project") or context.get("project"), change_ctx["number"], forge=context.get("forge", "gitlab"))
        except Exception as exc:
            raise RuntimeError("discussion cross-check unavailable: %s" % exc) from exc
        refreshed["discussions_available"] = True
    enriched = reconcile(report, context, refreshed, repo)
    findings = enriched.get("findings") if isinstance(enriched.get("findings"), list) else []
    severity_order = {"Must fix": 0, "Should fix": 1, "Nit": 2}
    ranked = sorted(enumerate(findings), key=lambda pair: severity_order.get(pair[1].get("severity"), 99))
    rank_ids = {index: "F%d" % (position + 1) for position, (index, _) in enumerate(ranked)}
    planned = []
    for index, finding in enumerate(findings):
        memory = finding.get("memory") if isinstance(finding.get("memory"), dict) else {}
        planned.append({
            "id": rank_ids[index],
            "fingerprint": memory.get("fingerprint"),
            "suppress_post": bool(memory.get("suppress_post")),
            "state": memory.get("state", "new"),
            "thread": copy.deepcopy(memory.get("thread")),
        })
    return {"findings": planned, "warnings": warnings + list(enriched.get("memory", {}).get("warnings") or [])}


_KEPT = ("fix", "later", "detail")


def compute_stats(records: list[dict]) -> dict:
    """Per-lens keep/dismiss counts across ledger records, noisiest lens first.

    Kept is Will fix / Fix later / Needs detail (Blocking / Non-blocking / Question in
    reviewer seat); dismissed is Ignore (Drop); undecided is none. Both seats share slots.
    """
    lenses: dict[str, dict] = {}
    for record in records:
        for finding in record["snapshot"]["findings"]:
            row = lenses.setdefault(finding["dimension"], {"id": finding["dimension"], "kept": 0,
                                                           "dismissed": 0, "undecided": 0})
            disposition = finding.get("disposition")
            row["kept" if disposition in _KEPT else "dismissed" if disposition == "ignore" else "undecided"] += 1
    for row in lenses.values():
        decided = row["kept"] + row["dismissed"]
        row["dismiss_rate"] = round(row["dismissed"] / decided, 3) if decided else 0.0
    ordered = sorted(lenses.values(), key=lambda r: (-r["dismiss_rate"], r["id"]))
    return {"lenses": ordered, "records": len(records)}


def stats(repo: str | None = None) -> dict:
    """Read every ledger record (or only `repo`'s) and return compute_stats plus warnings."""
    directory = _state_dir()
    wanted = _repo_identity(repo)[0] if repo else None
    records, warnings = [], []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        data, record_warnings = _read_record(path)
        if data is None:
            warnings.append("%s skipped: %s" % (path.name, "; ".join(record_warnings) or "unreadable"))
            continue
        if wanted is None or data["snapshot"]["identity"].get("repo") == wanted:
            records.append(data)
    result = compute_stats(records)
    result["warnings"] = warnings
    return result


def main(argv=None) -> int:
    """CLI entry point; every subcommand prints its JSON result to stdout.

    Exit 0 on success, 2 on invalid input or an error. `save` exits 1 when nothing was
    persisted (`saved` is false), still printing the result so callers can read the reason.
    """
    parser = argparse.ArgumentParser(description="Load, reconcile and save review memory")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("load")
    load.add_argument("--context", required=True)
    load.add_argument("--repo", default=".")
    load.add_argument("--dimension", action="append", default=[])
    load.add_argument("--guidance", action="append", default=[])
    load.add_argument("--fresh", action="store_true")
    load.add_argument("--out", required=True)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--report", required=True)
    rec.add_argument("--repo", default=".")
    rec.add_argument("--context", required=True)
    rec.add_argument("--snapshot", required=True)
    rec.add_argument("--out", required=True)
    chk = sub.add_parser("check")
    chk.add_argument("--report", required=True)
    chk.add_argument("--repo", default=".")
    chk.add_argument("--context", required=True)
    chk.add_argument("--snapshot")
    chk.add_argument("--out", required=True)
    save = sub.add_parser("save")
    save.add_argument("--report", required=True)
    save.add_argument("--decisions")
    save.add_argument("--receipts")
    st = sub.add_parser("stats")
    scope = st.add_mutually_exclusive_group()
    scope.add_argument("--repo")
    scope.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "stats":
            print(json.dumps(stats(None if args.all else (args.repo or ".")), indent=2, sort_keys=True))
            return 0
        if args.command == "load":
            result = load_snapshot(_load_json(args.context, "--context"), args.repo, args.dimension, args.guidance, args.fresh)
            write_json(Path(args.out), result)
        elif args.command == "reconcile":
            result = reconcile(_load_json(args.report, "--report"), _load_json(args.context, "--context"),
                         _load_json(args.snapshot, "--snapshot"), args.repo)
            write_json(Path(args.out), result)
        elif args.command == "check":
            report = _load_json(args.report, "--report")
            context = _load_json(args.context, "--context")
            snapshot = (_load_json(args.snapshot, "--snapshot") if args.snapshot else
                        ((report.get("memory") or {}).get("snapshot")))
            if not isinstance(snapshot, dict):
                raise ValueError("check requires --snapshot or report.memory.snapshot")
            result = check_plan(report, context, snapshot, args.repo)
            write_json(Path(args.out), result)
        else:
            if not args.decisions and not args.receipts:
                raise ValueError("save requires --decisions or --receipts")
            decisions = _load_json(args.decisions, "--decisions") if args.decisions else None
            receipts = _load_json(args.receipts, "--receipts") if args.receipts else None
            result = commit_report(_load_json(args.report, "--report"), decisions, receipts)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if args.command == "save" and not result["saved"] else 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
