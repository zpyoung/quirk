#!/usr/bin/env python3
"""Durable, read-only cross-run memory for combined merge-request reviews.

The module deliberately contains no renderer or posting dependencies.  It stores
reviewer's own decisions locally and uses GitLab discussions only as a read-only
source of live publication state.
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
import tempfile
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from forge import gitlab as _gitlab

SCHEMA_VERSION = 1
_RETENTION_SECONDS = 90 * 24 * 60 * 60
_FP_RE = re.compile(r"^[0-9a-f]{64}$")
_MARKER_RE = re.compile(r"<!--\s*sakura-review:\s*fp=([0-9a-f]{64})\s*-->", re.I)
_BLOCK_START_RE = re.compile(r"\A\s*<!--\s*sakura-review:v1\b")
_BLOCK_FP_RE = re.compile(
    r"\A\s*<!--\s*sakura-review:v1[ \t]*\r?\n(?:(?!-->).*\n)*?fp:[ \t]*([0-9a-f]{64})[ \t]*\r?\n")


# ---------------------------------------------------------------------------
# Stable identity and filesystem primitives
# ---------------------------------------------------------------------------

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
    raw = origin.strip()
    match = re.match(r"^(?:[^@]+@)?([^:/]+):(.+)$", raw)
    if match and "://" not in raw:
        host, project = match.groups()
        return "%s/%s" % (_normalize_host(host), _normalize_project(project))
    parsed = urllib.parse.urlparse(raw if "://" in raw else "https://" + raw)
    host = _normalize_host(parsed.netloc or parsed.path.split("/", 1)[0])
    path = parsed.path if parsed.netloc else parsed.path.split("/", 1)[1] if "/" in parsed.path else ""
    project = _normalize_project(path)
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
    return Path(root) / "sakura" / "review-memory"


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


def _atomic_write(path: Path, value: Any) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".memory-", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _target_identity(context: dict, repo: str) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    change_ctx = context.get("change") if isinstance(context.get("change"), dict) else {}
    # A prepared MR is authoritative even when the mode was branch/local.
    if change_ctx.get("number") is not None:
        host = _normalize_host(change_ctx.get("host") or context.get("host"))
        project = _normalize_project(change_ctx.get("project") or context.get("project"))
        if not host or not project or not str(change_ctx["number"]).isdigit() or int(change_ctx["number"]) < 1:
            raise ValueError("MR memory requires host, project and positive IID")
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


def _diff_sections(diff: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in (diff or "").splitlines():
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            current = match.group(2) if match else None
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
        return None, ["memory ledger unreadable; continuing with a clean snapshot"]
    if not isinstance(data, dict):
        return None, ["memory ledger is not an object; continuing with a clean snapshot"]
    version = data.get("schemaVersion", 0)
    if type(version) is not int or version < 0:
        return None, ["memory ledger has an invalid schema version; refusing overwrite"]
    if version > SCHEMA_VERSION:
        return None, ["memory ledger uses an unsupported future schema; continuing with a clean snapshot"]
    if version == 0:
        data["schemaVersion"] = SCHEMA_VERSION
        warnings.append("migrated legacy memory ledger")
    snapshot = data.get("snapshot")
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("identity"), dict)
            or not isinstance(snapshot.get("findings"), list)
            or any(not isinstance(item, dict) for item in snapshot["findings"])
            or type(snapshot.get("started_at")) not in (int, float)
            or not isinstance(snapshot.get("file_hashes"), dict)):
        return None, ["memory ledger has an invalid snapshot; refusing overwrite"]
    for finding in snapshot["findings"]:
        fp = finding.get("fingerprint")
        if (not isinstance(fp, str) or not _FP_RE.fullmatch(fp)
                or any(not isinstance(finding.get(field), str) for field in ("dimension", "file", "note"))
                or finding.get("disposition") not in ("fix", "later", "detail", "ignore", "none")
                or finding.get("seat") not in ("author", "reviewer")
                or ("receipt" in finding and not isinstance(finding["receipt"], dict))):
            return None, ["memory ledger has an invalid finding; refusing overwrite"]
    return data, warnings


def _prune(directory: Path, now: float) -> None:
    cutoff = now - _RETENTION_SECONDS
    for path in directory.glob("*.json"):
        try:
            data, _ = _read_record(path)
            if data is None:
                continue
            touched = float(data.get("updated_at", data["snapshot"]["started_at"]))
            if touched < cutoff:
                path.unlink()
        except (OSError, ValueError, TypeError):
            continue


# ---------------------------------------------------------------------------
# GitLab discussions (GET-only)
# ---------------------------------------------------------------------------

def _default_api(host: str, method: str, endpoint: str, payload: Any = None):
    if method.upper() != "GET":
        raise ValueError("review memory only permits GET discussion requests")
    return _gitlab.get_json(host, endpoint)


def fetch_discussions(host: str, project: str, number: Any, api: Callable | None = None) -> list[dict]:
    """Fetch every discussion page using GET, rejecting incomplete pagination."""
    if not host or not project or not str(number).isdigit() or int(number) < 1:
        raise ValueError("host, project and positive change number are required")
    return _gitlab.fetch_discussions(api or _default_api, host, _normalize_project(project), number)

# ---------------------------------------------------------------------------

def load_snapshot(context: dict, repo: str = ".", dimensions=(), guidance=(), fresh: bool = False) -> dict:
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
                                            change_ctx.get("project") or context.get("project"), change_ctx["number"])
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
    old = new = None
    for line in lines:
        if line.startswith("--- "):
            old = line[4:].split("\t", 1)[0].strip()
            old = old[2:] if old.startswith("a/") else old
        elif line.startswith("+++ "):
            new = line[4:].split("\t", 1)[0].strip()
            new = new[2:] if new.startswith("b/") else new
        if old and new:
            break
    return old, new


def _anchor(diff: str, file: str, line: Any, side: str = "new") -> str | None:
    wanted = _line_number(line)
    if wanted is None:
        return None
    lines = (diff or "").splitlines()
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
    found = None
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
            matched = ((side == "old" and old_no == wanted and prefix in (" ", "-")) or
                       (side != "old" and new_no == wanted and prefix in (" ", "+")))
            if matched:
                if found is not None:
                    return None
                found = content
            if prefix in (" ", "-"):
                old_no += 1
            if prefix in (" ", "+"):
                new_no += 1
    return found


def _norm_anchor(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fingerprint(dimension: str, file: str, text: str) -> tuple[str, str]:
    anchor_hash = hashlib.sha256(_norm_anchor(text).encode("utf-8")).hexdigest()
    fingerprint = hashlib.sha256((dimension + "\0" + file + "\0" + anchor_hash).encode("utf-8")).hexdigest()
    return fingerprint, anchor_hash


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

    A body that begins with a `sakura-review:v1` block carries only that block's `fp:` line
    (none for overview blocks, whose list values are not fingerprints); legacy markers anywhere
    else in such a body are ignored because the rest of it embeds untrusted report text. A body
    without a leading v1 block carries the legacy one-line markers found anywhere in it, and a
    v1 block quoted later does not count. Line endings may be LF or CRLF. Result is deduplicated
    in first-seen order. Never raises: non-str input yields [].

    Callers must still check the note's author; markers are copyable text.
    """
    if not isinstance(body, str):
        return []
    if _BLOCK_START_RE.match(body):
        block = _BLOCK_FP_RE.match(body)
        return [block.group(1)] if block else []
    return list(dict.fromkeys(match.group(1).lower() for match in _MARKER_RE.finditer(body)))


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
            return "https://%s/%s/-/merge_requests/%s#note_%s" % (
                _normalize_host(host), _normalize_project(project), change_ctx["number"], note["id"])
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

def reconcile(report: dict, context: dict, snapshot: dict) -> dict:
    validate_snapshot(snapshot, context)
    _validate_report_binding(report, snapshot)
    enriched = copy.deepcopy(report)
    warnings = list(snapshot.get("warnings") or [])
    prior = snapshot.get("findings") or []
    seat = snapshot["seat"]
    available = snapshot.get("discussions_available", False)
    discussions = snapshot.get("discussions", []) if available else []
    change_context = context.get("change") or {}
    if discussions and not (change_context.get("current_username") or change_context.get("current_user_id") is not None):
        warnings.append("Posting identity unknown; MR markers are treated as human context.")
    current_counts, prior_by_fp = {}, {}
    for item in prior:
        if item.get("fingerprint"):
            prior_by_fp.setdefault(item["fingerprint"], []).append(item)
    for finding in enriched["findings"]:
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
        fp, anchor_hash = _fingerprint(dimension, finding["file"], text) if text and _norm_anchor(text) else (None, None)
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
        thread, human = _discussion_details(discussions, fp, finding, context)
        memory["thread"], memory["human_context"] = thread, human
        previous = matches[0] if fp and len(matches) == 1 else None
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
            # The decision is usable offline; MR delivery still requires a live GET.
            memory["state"] = "carried"
        elif fp and not previous:
            for candidate in prior:
                if (candidate.get("file") != finding["file"]
                        or candidate.get("dimension") != memory["dimension"]
                        or not candidate.get("fingerprint")):
                    continue
                score = difflib.SequenceMatcher(None, _prior_text(candidate).lower(),
                                               _prior_text(finding).lower()).ratio()
                if score < 0.55:
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


# ---------------------------------------------------------------------------
# Decisions and receipts
# ---------------------------------------------------------------------------
def _report_digest(report: dict) -> str:
    return hashlib.sha256(_canonical_json(report).encode("utf-8")).hexdigest()


def _safe_record(item: dict) -> dict:
    allowed = ("fingerprint", "dimension", "anchor_hash", "severity", "file", "line", "title", "body_md",
               "recommendation_md", "disposition", "note", "seat", "receipt", "state", "thread")
    result = {key: copy.deepcopy(item[key]) for key in allowed if key in item}
    return result


def commit_report(report: dict, decisions: dict | None = None, receipts: dict | None = None) -> dict:
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
                return {"saved": False, "warnings": warnings + ["refusing destructive ledger overwrite"]}
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
                          "snapshot": new_snapshot, "updated_at": time.time()}
            _atomic_write(ledger_path, new_record)
            _prune(directory, time.time())
    except OSError as exc:
        return {"saved": False, "warnings": warnings + ["could not persist review memory: %s" % exc]}
    return {"saved": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value
def check_plan(report: dict, context: dict, snapshot: dict) -> dict:
    """Build the author-delivery suppression plan without changing any input."""
    identity_warnings = validate_snapshot(snapshot, context, ".")
    refreshed = copy.deepcopy(snapshot)
    change_ctx = context.get("change") if isinstance(context.get("change"), dict) else {}
    warnings = list(identity_warnings)
    if change_ctx.get("number") is not None:
        try:
            refreshed["discussions"] = fetch_discussions(change_ctx.get("host") or context.get("host"),
                                                         change_ctx.get("project") or context.get("project"), change_ctx["number"])
        except Exception as exc:
            raise RuntimeError("discussion cross-check unavailable: %s" % exc) from exc
        refreshed["discussions_available"] = True
    enriched = reconcile(report, context, refreshed)
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


def main(argv=None) -> int:
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
    rec.add_argument("--context", required=True)
    rec.add_argument("--snapshot", required=True)
    rec.add_argument("--out", required=True)
    chk = sub.add_parser("check")
    chk.add_argument("--report", required=True)
    chk.add_argument("--context", required=True)
    chk.add_argument("--snapshot")
    chk.add_argument("--out", required=True)
    save = sub.add_parser("save")
    save.add_argument("--report", required=True)
    save.add_argument("--decisions")
    save.add_argument("--receipts")
    args = parser.parse_args(argv)
    try:
        if args.command == "load":
            result = load_snapshot(_load_json(args.context), args.repo, args.dimension, args.guidance, args.fresh)
            _atomic_write(Path(args.out), result)
        elif args.command == "reconcile":
            result = reconcile(_load_json(args.report), _load_json(args.context), _load_json(args.snapshot))
            _atomic_write(Path(args.out), result)
        elif args.command == "check":
            report = _load_json(args.report)
            context = _load_json(args.context)
            snapshot = (_load_json(args.snapshot) if args.snapshot else
                        ((report.get("memory") or {}).get("snapshot")))
            if not isinstance(snapshot, dict):
                raise ValueError("check requires --snapshot or report.memory.snapshot")
            result = check_plan(report, context, snapshot)
            _atomic_write(Path(args.out), result)
        else:
            if not args.decisions and not args.receipts:
                raise ValueError("save requires --decisions or --receipts")
            decisions = _load_json(args.decisions) if args.decisions else None
            receipts = _load_json(args.receipts) if args.receipts else None
            result = commit_report(_load_json(args.report), decisions, receipts)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
