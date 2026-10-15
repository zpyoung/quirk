#!/usr/bin/env python3
"""Resolve a diff (forge-first, git-fallback) and write a shared context file.

Sources: --change <number>, --branch <name>, or --local. The forge (GitHub or GitLab,
chosen by forge.detect_forge) is preferred whenever a change request exists because
it returns the canonical diff against the live target branch plus authoritative
base/start/head refs, so a stale or rebase-pending local branch still reviews
cleanly. git is the fallback.

Pure helpers (parsing, batching, host/project resolution) are unit-testable; the
subprocess wrappers are mock-testable.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

from forge import ForgeError, detect_forge, make_forge

DEFAULT_MAX_CHARS = 240000  # ~60k tokens
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# repo diff config can substitute the patch, so pin canonical flags
_GIT_DIFF_GLOBAL_FLAGS = ["-c", "core.quotepath=false", "--literal-pathspecs"]
_GIT_DIFF_FLAGS = [
    "--no-ext-diff", "--no-textconv", "--no-color",
    "--src-prefix=a/", "--dst-prefix=b/", "--ignore-submodules=all",
    "--diff-algorithm=myers",
]

# Content lines are prefixed, so metadata must be line-anchored.
_BINARY_FILES_RE = re.compile(r'Binary files .+ and .+ differ')

# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

def _decode_git_path(field):
    """Decode one raw or C-quoted path field emitted by git."""
    if not field.startswith('"'):
        return field
    if len(field) < 2 or not field.endswith('"'):
        return None
    data = bytearray()
    i = 1
    escapes = {"\\": 0x5c, '"': 0x22, "t": 0x09, "n": 0x0a, "r": 0x0d}
    while i < len(field) - 1:
        char = field[i]
        if char != "\\":
            data.extend(char.encode("utf-8", "surrogateescape"))
            i += 1
            continue
        i += 1
        if i >= len(field) - 1:
            return None
        char = field[i]
        if char in escapes:
            data.append(escapes[char])
            i += 1
        elif char in "01234567":
            match = re.match(r"[0-7]{1,3}", field[i:len(field) - 1])
            data.append(int(match.group(0), 8))
            i += len(match.group(0))
        else:
            data.extend(char.encode("utf-8", "surrogateescape"))
            i += 1
    return data.decode("utf-8", "surrogateescape")


def _quoted_field_end(text, start=0):
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
        elif text[i] == '"':
            return i + 1
        else:
            i += 1
    return None


def _diff_git_fields(line):
    prefix = "diff --git "
    if not line.startswith(prefix):
        return None
    payload = line[len(prefix):]
    if payload.startswith('"'):
        end = _quoted_field_end(payload)
        if end is None or end >= len(payload) or not payload[end].isspace():
            return None
        first, second = payload[:end], payload[end:].lstrip()
        if second.startswith('"') and _quoted_field_end(second) != len(second):
            return None
        return _decode_git_path(first), _decode_git_path(second)

    candidates = []
    for marker in (" b/", ' "b/'):
        start = 0
        while True:
            pos = payload.find(marker, start)
            if pos < 0:
                break
            first, second = payload[:pos], payload[pos + 1:]
            decoded = (_decode_git_path(first), _decode_git_path(second))
            if decoded[0] and decoded[1] and decoded[0].startswith("a/") and decoded[1].startswith("b/"):
                candidates.append(decoded)
            start = pos + 1
    if not candidates:
        return None
    for first, second in candidates:
        if first[2:] == second[2:]:
            return first, second
    return candidates[0]


def _strip_ab(p):
    p = p.strip()
    if p.startswith('"'):
        end = _quoted_field_end(p)
        p = _decode_git_path(p[:end]) if end is not None else None
    else:
        p = p.split("\t", 1)[0].rstrip()
    if p and (p.startswith("a/") or p.startswith("b/")):
        return p[2:]
    return p


def _path_from_diff_git(line):
    fields = _diff_git_fields(line)
    return _strip_ab(fields[1]) if fields else None


def _quote_git_path(path):
    """Render a path using git's C-quoting rules when delimiters require it."""
    data = path.encode("utf-8", "surrogateescape")
    if all(0x21 <= byte <= 0x7e and byte not in (0x22, 0x5c) for byte in data):
        return path
    escaped = []
    named = {0x09: r"\t", 0x0a: r"\n", 0x0d: r"\r", 0x22: r'\"', 0x5c: r"\\"}
    for byte in data:
        if byte in named:
            escaped.append(named[byte])
        elif 0x20 <= byte <= 0x7e:
            escaped.append(chr(byte))
        else:
            escaped.append("\\%03o" % byte)
    return '"%s"' % "".join(escaped)


def parse_unified_diff(text):
    """Split a unified diff into per-file entries with hunk header lines."""
    files, cur, in_hunk = [], None, False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            if cur:
                files.append(cur)
            cur = {"header": line, "file": _path_from_diff_git(line), "hunks": []}
            in_hunk = False
        elif line.startswith("@@") and cur is not None:
            cur["hunks"].append(line)
            in_hunk = True
        elif line.startswith("+++ ") and cur is not None and not in_hunk:
            fp = _strip_ab(line[4:])
            if fp and fp != "/dev/null":
                cur["file"] = fp
    if cur:
        files.append(cur)
    return files


def _deduplicate(items):
    return list(dict.fromkeys(item for item in items if item))


def changed_files_from_diff(text):
    return _deduplicate(f["file"] for f in parse_unified_diff(text) if f.get("file"))


def count_changed_lines(text):
    """Count additions and deletions within unified-diff hunks."""
    n, in_hunk = 0, False
    for line in (text or "").splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            # File markers precede the first hunk; their prefixes are valid hunk content.
            in_hunk = True
        elif in_hunk and line.startswith(("+", "-")):
            n += 1
    return n


def split_diff_by_file(text):
    """Return {file: diff_text}, preserving repeated sections for each path."""
    out, cur_file, buf, in_hunk = {}, None, [], False

    def flush():
        if cur_file is not None:
            section = "\n".join(buf)
            if cur_file in out:
                out[cur_file] += "\n" + section
            else:
                out[cur_file] = section

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush()
            buf = [line]
            cur_file = _path_from_diff_git(line)
            in_hunk = False
        else:
            buf.append(line)
            if line.startswith("@@"):
                in_hunk = True
            elif line.startswith("+++ ") and not in_hunk:
                path = _strip_ab(line[4:])
                if path and path != "/dev/null":
                    cur_file = path
    flush()
    return out


def batch_files(file_diffs, max_chars):
    """Greedily pack {file: diff} into batches under max_chars. A single file
    larger than the budget gets its own batch (never silently dropped)."""
    batches, cur = [], {"files": [], "parts": [], "size": 0}
    for f, d in file_diffs.items():
        dl = len(d)
        if cur["files"] and cur["size"] + dl > max_chars:
            batches.append(cur)
            cur = {"files": [], "parts": [], "size": 0}
        cur["files"].append(f)
        cur["parts"].append(d)
        cur["size"] += dl
    if cur["files"]:
        batches.append(cur)
    return [{"files": b["files"], "diff": "\n".join(b["parts"])} for b in batches]


def reconstruct_diff_from_changes(changes):
    """Build a unified diff from GitLab MR changes with textual content."""
    parts = []
    for c in changes:
        if not (c.get("diff") or "").strip():
            continue
        old, new = c.get("old_path"), c.get("new_path")
        old_field, new_field = _quote_git_path("a/%s" % old), _quote_git_path("b/%s" % new)
        parts.append("diff --git %s %s" % (old_field, new_field))
        old_mode, new_mode = c.get("a_mode"), c.get("b_mode")
        if c.get("new_file") and new_mode not in (None, "", "0", 0):
            parts.append("new file mode %s" % new_mode)
        if c.get("deleted_file") and old_mode not in (None, "", "0", 0):
            parts.append("deleted file mode %s" % old_mode)
        if (not c.get("new_file") and not c.get("deleted_file") and
                old_mode not in (None, "", "0", 0) and
                new_mode not in (None, "", "0", 0) and old_mode != new_mode):
            parts.append("old mode %s" % old_mode)
            parts.append("new mode %s" % new_mode)
        if c.get("renamed_file"):
            parts.append("rename from %s" % old)
            parts.append("rename to %s" % new)
        old_marker = "/dev/null" if c.get("new_file") else _quote_git_path("a/%s" % old)
        new_marker = "/dev/null" if c.get("deleted_file") else _quote_git_path("b/%s" % new)
        parts.append("--- %s" % old_marker)
        parts.append("+++ %s" % new_marker)
        parts.append(c.get("diff").rstrip("\n"))
    return ("\n".join(parts) + "\n") if parts else ""


def _is_binary_change(change):
    return any(change.get(k) for k in ("binary", "binary_file", "is_binary"))


def _same_blob(change):
    """Return whether GitLab positively identifies identical content blobs."""
    pairs = (
        ("a_blob_id", "b_blob_id"),
        ("old_blob_id", "new_blob_id"),
    )
    for old_key, new_key in pairs:
        old, new = change.get(old_key), change.get(new_key)
        if old and new:
            return old == new
    return False


def _can_be_metadata_only(change):
    old_mode, new_mode = change.get("a_mode"), change.get("b_mode")
    return bool(change.get("renamed_file") or _same_blob(change) or
                (old_mode not in (None, "", "0", 0) and
                 new_mode not in (None, "", "0", 0) and old_mode != new_mode))


def _section_has_binary_metadata(section):
    in_hunk = False
    for line in section.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk and (line == "GIT binary patch" or
                              _BINARY_FILES_RE.fullmatch(line)):
            return True
    return False


def not_text_reviewable_from_diff(text):
    """Return paths whose git sections identify binary content."""
    return [path for path, section in split_diff_by_file(text).items()
            if _section_has_binary_metadata(section)]


def is_test_file(path):
    """Classify common test-file conventions across supported ecosystems."""
    normalized = path.replace("\\", "/").strip("/")
    parts = normalized.split("/") if normalized else []
    lower_parts = [part.lower() for part in parts]
    name = parts[-1] if parts else ""
    lower = name.lower()

    if any(part in ("tests", "__tests__") for part in lower_parts[:-1]):
        return True
    if any(lower_parts[i:i + 2] == ["src", "test"]
           for i in range(max(0, len(lower_parts) - 1))):
        return True
    if any(part == "spec" for part in lower_parts[:-1]):
        return True
    if lower == "conftest.py":
        return True
    if lower.endswith(".py") and (lower.startswith("test_") or lower.endswith("_test.py")):
        return True
    if re.search(r'\.(test|spec)\..+$', lower):
        return True
    if lower.endswith("_test.go") or lower.endswith("_spec.rb"):
        return True
    if re.search(r'Test\.[^.]+$', name):
        return True
    return False


def is_source_file(path):
    """Return whether a changed path is production source for coverage gating."""
    normalized = path.replace("\\", "/").strip("/")
    parts = normalized.lower().split("/") if normalized else []
    name = parts[-1] if parts else ""
    if any(part in ("doc", "docs", "documentation") for part in parts[:-1]):
        return False
    if any(name.endswith(ext) for ext in (
            ".md", ".markdown", ".mdown", ".mkd", ".rst",
            ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg")):
        return False
    if (name.endswith(".lock") or name in ("go.sum", "yarn.lock") or
            re.search(r"(?:^|[-_.])lock(?:[-_.]|$)", name)):
        return False
    return True


def classify_files(paths):
    """Return deduplicated test paths and production source paths."""
    paths = _deduplicate(paths)
    tests = [path for path in paths if is_test_file(path)]
    test_set = set(tests)
    return tests, [path for path in paths
                   if path not in test_set and is_source_file(path)]


def _reported_change_count(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value, False
    if isinstance(value, str):
        match = re.fullmatch(r'\s*(\d+)(\+)?\s*', value)
        if match:
            return int(match.group(1)), bool(match.group(2))
    return None, False


def resolve_scope_intent(title=None, branch=None):
    """Compose an intent hint without judging the change description."""
    title = (title or "").strip()
    branch = (branch or "").strip()
    if title and branch:
        return {"guess": "%s (%s)" % (title, branch),
                "basis": "change.title + source_branch"}
    if title:
        return {"guess": title, "basis": "change.title"}
    if branch:
        return {"guess": branch, "basis": "source_branch"}
    return {"guess": "", "basis": "none"}


# --------------------------------------------------------------------------- #
# Subprocess wrappers (mock-testable)
# --------------------------------------------------------------------------- #

def _run(cmd, timeout=90):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="surrogateescape", timeout=timeout)


def _late_run(cmd, timeout=90, **_ignored):
    # resolve _run at call time so a test's replacement module attribute is used
    return _run(cmd, timeout=timeout)


def _git_diff_command(cwd):
    return (["git", "-C", cwd] + _GIT_DIFF_GLOBAL_FLAGS + ["diff"] +
            _GIT_DIFF_FLAGS)


def _git_diff_path(base, head, path, cwd=".", old_path=None):
    """Return a file diff, empty text on proven no delta, or None on failure."""
    if not base or not head or not path:
        return None
    paths = _deduplicate([old_path, path])
    cmd = (_git_diff_command(cwd) + ["--find-renames=50%",
           "%s..%s" % (base, head), "--"] + paths)
    try:
        r = _run(cmd, timeout=120)
        if r.returncode == 0:
            return r.stdout
    except Exception:
        return None

    missing = []
    for sha in (base, head):
        try:
            r = _run(["git", "-C", cwd, "cat-file", "-e", "%s^{commit}" % sha], timeout=30)
            if r.returncode != 0:
                missing.append(sha)
        except Exception:
            missing.append(sha)
    if not missing:
        return None

    for sha in missing:
        try:
            r = _run(["git", "-C", cwd, "fetch", "origin", sha], timeout=120)
            if r.returncode != 0:
                return None
        except Exception:
            return None
    try:
        r = _run(cmd, timeout=120)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _git_diff_range(base, head, cwd=".", context_lines=None):
    """Return a complete range diff, including empty success, or None."""
    if not base or not head:
        return None
    option = [] if context_lines is None else ["-U%d" % context_lines]
    cmd = (_git_diff_command(cwd) + ["--find-renames=50%"] + option +
           ["%s..%s" % (base, head)])
    try:
        r = _run(cmd, timeout=120)
        if r.returncode == 0:
            return r.stdout
    except Exception:
        return None

    for sha in (base, head):
        try:
            r = _run(["git", "-C", cwd, "fetch", "origin", sha], timeout=120)
            if r.returncode != 0:
                return None
        except Exception:
            return None
    try:
        r = _run(cmd, timeout=120)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _git_changed_files_range(base, head, cwd="."):
    """Return the exact NUL-delimited range file list, or None on failure."""
    if not base or not head:
        return None
    try:
        cmd = (_git_diff_command(cwd) + ["--find-renames=50%", "--name-only", "-z",
               "%s..%s" % (base, head)])
        r = _run(cmd, timeout=120)
        return _deduplicate(r.stdout.split("\0")) if r.returncode == 0 else None
    except Exception:
        return None


def _prepare_gitlab_changes(changes, refs, cwd="."):
    """Return reconstructed text, changed, unavailable, and non-text paths."""
    parts, changed_files, unavailable, not_text = [], [], [], []
    for change in changes:
        path = change.get("new_path") or change.get("old_path")
        if path:
            changed_files.append(path)
        content_truncated = any(change.get(flag) is True
                                for flag in ("collapsed", "too_large"))
        if _is_binary_change(change):
            rendered = reconstruct_diff_from_changes([change])
            if path:
                not_text.append(path)
        elif (change.get("diff") or "").strip() and not content_truncated:
            rendered = reconstruct_diff_from_changes([change])
        else:
            old_path = change.get("old_path") if change.get("renamed_file") else None
            if old_path:
                recovered = _git_diff_path(refs.get("base"), refs.get("head"), path, cwd,
                                           old_path=old_path)
            else:
                recovered = _git_diff_path(refs.get("base"), refs.get("head"), path, cwd)
            rendered = recovered or ""
            if (recovered is None or
                    (recovered == "" and not _can_be_metadata_only(change))):
                if path and not _same_blob(change):
                    unavailable.append(path)
        if rendered:
            parts.append(rendered.rstrip("\n"))
    diff_text = "\n".join(parts)
    return ((diff_text + "\n" if diff_text else ""), _deduplicate(changed_files),
            _deduplicate(unavailable), _deduplicate(not_text))


def get_origin_url(cwd="."):
    try:
        r = _run(["git", "-C", cwd, "remote", "get-url", "origin"], timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def detect_target_branch(cwd="."):
    try:
        r = _run(["git", "-C", cwd, "symbolic-ref", "refs/remotes/origin/HEAD"], timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().rsplit("/", 1)[-1]
    except Exception:
        pass
    return "main"


def detect_current_branch(cwd="."):
    """Return the current branch name, or None when detached or unavailable."""
    try:
        r = _run(["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"], timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None

def change_diff(forge, number, cwd=".", metadata=None):
    """Return (diff_text, refs, change) from the forge, or None on any failure.

    `metadata`, when supplied, receives complete file-availability information
    and details of any full-list recovery.
    """
    try:
        data = forge.change_records(number)
    except ForgeError as exc:
        if metadata is not None:
            metadata["error"] = str(exc)
        return None
    refs = dict(data["refs"])
    changes = data["records"]
    reported_count, count_is_lower_bound = _reported_change_count(data.get("reported_count"))
    # Compare counts because GitLab's overflow flag is not reliable for every truncation.
    count_mismatch = (reported_count is None or count_is_lower_bound or
                      reported_count != len(changes))
    list_truncated = data.get("overflow") is True or count_mismatch

    if list_truncated:
        recovered = _git_diff_range(refs.get("base"), refs.get("head"), cwd)
        recovered_files = (_git_changed_files_range(refs.get("base"), refs.get("head"), cwd)
                           if recovered is not None else None)
        if (recovered is None or recovered_files is None or
                (recovered_files is not None and len(recovered_files) < len(changes)) or
                (reported_count is not None and not count_is_lower_bound and
                 len(recovered_files) != reported_count) or
                (count_is_lower_bound and len(recovered_files) < reported_count)):
            if metadata is not None:
                metadata["error"] = "forge file list was truncated and git recovery failed"
            return None
        diff_text = recovered
        changed_files = recovered_files
        unavailable = []
        not_text = not_text_reviewable_from_diff(diff_text)
        recovery = {
            "api_file_count": len(changes),
            "reported_changes_count": data.get("reported_count"),
            "overflow": data.get("overflow"),
            "recovered_file_count": len(changed_files),
            "recovered_from": "git",
        }
    else:
        diff_text, changed_files, unavailable, not_text = _prepare_gitlab_changes(
            changes, refs, cwd)
        recovery = None

    if diff_text and (not refs.get("base") or not refs.get("head")):
        if metadata is not None:
            metadata["error"] = "forge returned a diff without usable refs"
        return None
    if metadata is not None:
        # inline notes on these files are lost or rejected, so delivery routes them to the overview
        metadata["unanchorable_files"] = _deduplicate([
            c.get("new_path") or c.get("old_path") for c in changes
            if c.get("collapsed") is True or c.get("too_large") is True])
        metadata["changed_files"] = changed_files
        metadata["diff_unavailable"] = unavailable
        metadata["not_text_reviewable"] = not_text
        metadata["file_list_recovery"] = recovery
    change = {
        "number": data.get("number") or number,
        "title": data.get("title") or "",
        "description": data.get("description") or "",
        "web_url": data.get("web_url") or "",
        "author": data.get("author") or "",
        "source_branch": data.get("source_branch") or "",
    }
    return diff_text, refs, change


def change_details(forge, number):
    """Return the change identity needed for seat detection and reviewer delivery."""
    return forge.change_details(number)


def current_user(forge):
    """Return the authenticated forge identity, or None when it cannot be read."""
    return forge.current_user()


def commit_authors(forge, number):
    """Return [{username, email}] for the change's commits, or None when unresolvable."""
    return forge.commit_authors(number)


def _is_viewer(commit, viewer):
    username = (commit.get("username") or "").casefold()
    email = (commit.get("email") or "").casefold()
    if username and username == str(viewer.get("username") or "").casefold():
        return True
    return bool(email) and email in {e.casefold() for e in viewer.get("emails") or [] if e}


def mixed_authorship(seat, viewer, commits):
    """Whether someone besides the change author also committed, from the viewer's side.

    True when the viewer authored the change and another identity has commits on it, or
    the viewer did not author it but has commits on it. None when commits are unknown.
    """
    if commits is None:
        return None
    mine = sum(1 for commit in commits if _is_viewer(commit, viewer))
    if seat == "author":
        return mine < len(commits)
    return mine > 0


def detect_seat(author_username, current_username, author_id=None, current_id=None):
    """Classify a change request as author or reviewer without a user-configurable override."""
    if author_id is not None and current_id is not None:
        return "author" if str(author_id) == str(current_id) else "reviewer"
    if not author_username or not current_username:
        return None
    return "author" if author_username.casefold() == current_username.casefold() else "reviewer"


def find_change_for_branch(forge, branch):
    return forge.find_change_for_branch(branch)


def git_diff_branch(branch, target, context_lines, cwd=".", metadata=None):
    """Return a remote-target merge-base diff, empty on success or None."""
    try:
        source_ref = "refs/remotes/origin/%s" % branch
        target_ref = "refs/remotes/origin/%s" % target
        for name, remote_ref in ((branch, source_ref), (target, target_ref)):
            refspec = "+refs/heads/%s:%s" % (name, remote_ref)
            fetched = _run(["git", "-C", cwd, "fetch", "origin", refspec], timeout=120)
            if fetched.returncode != 0:
                return None
        head_result = _run(["git", "-C", cwd, "rev-parse", "--verify",
                            "%s^{commit}" % source_ref], timeout=30)
        target_result = _run(["git", "-C", cwd, "rev-parse", "--verify",
                              "%s^{commit}" % target_ref], timeout=30)
        if (head_result.returncode != 0 or not head_result.stdout.strip() or
                target_result.returncode != 0 or not target_result.stdout.strip()):
            return None
        head = head_result.stdout.strip()
        base_result = _run(["git", "-C", cwd, "merge-base",
                            target_ref, head], timeout=30)
        if base_result.returncode != 0 or not base_result.stdout.strip():
            return None
        base = base_result.stdout.strip()
    except Exception:
        return None
    diff_text = _git_diff_range(base, head, cwd, context_lines)
    changed_files = (_git_changed_files_range(base, head, cwd)
                     if diff_text is not None else None)
    if changed_files is None:
        return None
    if metadata is not None:
        metadata["refs"] = {"base": base, "start": base, "head": head}
        metadata["changed_files"] = changed_files
    return diff_text


def _untracked_diff(path, cwd):
    try:
        r = _run(_git_diff_command(cwd) +
                 ["--no-index", "--", "/dev/null", path], timeout=60)
        return r.stdout if r.returncode in (0, 1) else None
    except Exception:
        return None


def git_diff_local(context_lines, cwd=".", metadata=None, excluded_path=None):
    """Return staged, unstaged, and untracked diffs, or None on failure."""
    try:
        diff_cmd = _git_diff_command(cwd) + ["--find-renames=50%"]
        unstaged = _run(diff_cmd + ["-U%d" % context_lines], timeout=60)
        staged = _run(diff_cmd + ["--staged", "-U%d" % context_lines], timeout=60)
        unstaged_names = _run(diff_cmd + ["--name-only", "-z"], timeout=60)
        staged_names = _run(diff_cmd + ["--staged", "--name-only", "-z"], timeout=60)
        untracked_result = _run(["git", "-C", cwd, "ls-files", "--others",
                                 "--exclude-standard", "-z"], timeout=60)
        if any(r.returncode != 0 for r in (
                unstaged, staged, unstaged_names, staged_names, untracked_result)):
            return None
    except Exception:
        return None

    excluded_real_path = os.path.realpath(excluded_path) if excluded_path else None
    untracked = [
        path for path in untracked_result.stdout.split("\0")
        if path and os.path.realpath(os.path.join(cwd, path)) != excluded_real_path
    ]
    changed_files = _deduplicate(
        unstaged_names.stdout.split("\0") + staged_names.stdout.split("\0") + untracked)
    parts = [unstaged.stdout or "", staged.stdout or ""]
    for path in untracked:
        rendered = _untracked_diff(path, cwd)
        if rendered is None:
            return None
        parts.append(rendered)
    try:
        head_result = _run(["git", "-C", cwd, "rev-parse", "--verify", "HEAD^{commit}"],
                           timeout=30)
    except Exception:
        return None
    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    diff_text = "".join(parts)
    if diff_text and not head:
        return None
    if metadata is not None:
        metadata["untracked_files"] = untracked
        metadata["changed_files"] = changed_files
        metadata["refs"] = {"base": head, "start": head, "head": head}
    return diff_text


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _fail(out, mode, message, paths=None, seat=None):
    try:
        os.unlink(out)
    except FileNotFoundError:
        pass
    detail = {"code": "diff_source_failed", "message": message}
    if paths:
        detail["paths"] = paths
    error = {"status": "error", "mode": mode, "error": detail}
    if seat:
        error["seat"] = seat
    print(json.dumps(error, indent=2), file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resolve a diff (forge-first) into a shared context file.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--change", metavar="NUMBER")
    g.add_argument("--branch")
    g.add_argument("--local", action="store_true")
    ap.add_argument("--target-branch")
    ap.add_argument("--forge", choices=("github", "gitlab", "none"))
    ap.add_argument("--seat", choices=("author", "reviewer"))
    ap.add_argument("--host")
    ap.add_argument("-R", "--project")
    ap.add_argument("--context-lines", type=int, default=3)
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    origin = get_origin_url(args.cwd)
    # local review never needs the forge, so skip probing CLIs for it
    choice = detect_forge(origin, "none" if args.local else args.forge)
    host = args.host or choice.host
    project = args.project or choice.project
    target = args.target_branch or detect_target_branch(args.cwd)

    source = mode = None
    refs = {"base": None, "start": None, "head": None}
    diff_text, fallback_reason, change = None, None, None
    source_branch = args.branch if args.branch else None
    number = None
    forge_metadata = {}
    local_metadata = {}
    forge = None
    forge_error = None
    if choice.name != "none" and not args.local:
        try:
            forge = make_forge(choice.name, host, project, run=_late_run)
        except ForgeError as exc:
            forge_error = str(exc)
    elif choice.name == "none":
        forge_error = "no supported forge: %s" % choice.reason

    if args.change:
        mode = "change"
        number = args.change
        if forge is None:
            return _fail(args.out, mode, forge_error or "no forge available for a change request")
        res = change_diff(forge, number, args.cwd, forge_metadata)
        if not res:
            return _fail(args.out, mode, forge_metadata.get("error", "forge change diff failed"))
        diff_text, refs, change = res
        source_branch = change.get("source_branch") or source_branch
        source = forge.name
    elif args.branch:
        mode = "branch"
        number = find_change_for_branch(forge, args.branch) if forge is not None else None
        res = change_diff(forge, number, args.cwd, forge_metadata) if number else None
        if res:
            diff_text, refs, change = res
            source_branch = change.get("source_branch") or source_branch
            source = forge.name
        else:
            source = "git"
            number = None
            fallback_reason = ("no change request found for branch or the forge diff failed; used git diff"
                               if forge is not None else "%s; used git diff" % forge_error)
            diff_text = git_diff_branch(args.branch, target, args.context_lines,
                                        args.cwd, local_metadata)
            if diff_text is None:
                return _fail(args.out, mode, "forge and branch git diff both failed")
            refs = local_metadata.get("refs", refs)
    else:
        mode, source = "local", "git"
        source_branch = detect_current_branch(args.cwd)
        output_path = os.path.realpath(args.out)
        diff_text = git_diff_local(args.context_lines, args.cwd, local_metadata,
                                   excluded_path=output_path)
        if diff_text is None:
            return _fail(args.out, mode, "local git diff failed")
        refs = local_metadata.get("refs", refs)

    if diff_text and (not refs.get("base") or not refs.get("head")):
        return _fail(args.out, mode, "diff source did not provide usable refs")

    seat = "author"
    if source != "git" and number:
        label = forge.change_label(number)
        details = change_details(forge, number)
        viewer = current_user(forge) if details else None
        identity_error = None
        if not details:
            identity_error = "could not resolve %s metadata for seat detection" % label
        elif any(not isinstance(refs.get(key), str) or not SHA_RE.match(refs[key])
                 for key in ("base", "start", "head")):
            identity_error = "the forge returned incomplete or malformed diff refs"
        elif details.get("open") is not True:
            identity_error = "%s is not open" % label
        elif str(details.get("number")) != str(number):
            identity_error = "%s metadata came back for a different change" % label
        elif mode == "branch" and details.get("source_branch") != args.branch:
            identity_error = "discovered change source branch does not match the requested branch"
        elif details.get("sha") != refs.get("head"):
            identity_error = "%s head moved while the review context was being prepared; rerun" % label
        elif details.get("base_sha") != refs.get("base") or details.get("start_sha") != refs.get("start"):
            identity_error = "%s base/start diff refs changed while the review context was being prepared; rerun" % label
        elif not viewer:
            identity_error = "could not resolve the authenticated forge user for seat detection"
        detected = None if identity_error else detect_seat(
            details.get("author_username"), viewer.get("username"),
            details.get("author_id"), viewer.get("id"),
        )
        if not detected and not identity_error:
            identity_error = "change author identity is incomplete; seat detection is unsafe"
        if identity_error:
            return _fail(args.out, mode, identity_error, seat="unknown")
        mixed = mixed_authorship(detected, viewer, commit_authors(forge, number))
        seat_source = "detected"
        if mixed:
            if not args.seat:
                return _fail(args.out, mode,
                             "%s has commits from both you and another author; rerun with "
                             "--seat author or --seat reviewer" % label, seat="ambiguous")
            detected, seat_source = args.seat, "chosen"
        elif args.seat:
            return _fail(args.out, mode, "--seat is only accepted when authorship is mixed")
        seat = detected
        change = dict(change or {})
        change.update({
            "number": int(number) if str(number).isdigit() else number,
            "label": label,
            "host": host, "project": project,
            "state": details.get("state"),
            "author_id": details.get("author_id"),
            "author_username": details.get("author_username"),
            "target_branch": details.get("target_branch"),
            "sha": details.get("sha"),
            "base_sha": details.get("base_sha"),
            "start_sha": details.get("start_sha"),
            "current_user_id": viewer.get("id"),
            "current_username": viewer.get("username"),
            "seat": seat,
            "seat_source": seat_source,
            "mixed_authorship": mixed,
            "is_fork": bool(details.get("is_fork")),
            "author_trusted": True if details.get("author_id") == viewer.get("id") and details.get("author_id") is not None
                              else details.get("author_trusted"),
        })
        if details.get("target_branch"):
            target = details["target_branch"]

    if "changed_files" in forge_metadata:
        files = forge_metadata["changed_files"]
    elif "changed_files" in local_metadata:
        files = local_metadata["changed_files"]
    else:
        files = changed_files_from_diff(diff_text)
    files = _deduplicate(files + local_metadata.get("untracked_files", []))
    diff_unavailable = forge_metadata.get("diff_unavailable", [])
    not_text_reviewable = _deduplicate(
        forge_metadata.get("not_text_reviewable", []) +
        not_text_reviewable_from_diff(diff_text))
    parsed_paths = set(split_diff_by_file(diff_text))
    accounted_paths = parsed_paths | set(diff_unavailable) | set(not_text_reviewable)
    unaccounted_paths = [path for path in files if path not in accounted_paths]
    if unaccounted_paths:
        return _fail(args.out, mode,
                     "diff manifest paths have no parseable or classified content",
                     unaccounted_paths)
    test_files, source_files = classify_files(files)
    untracked_files = local_metadata.get("untracked_files", [])
    batched = len(diff_text) > args.max_chars
    batches = batch_files(split_diff_by_file(diff_text), args.max_chars) if batched else []
    scope_intent = resolve_scope_intent(
        title=change.get("title") if change else None,
        branch=source_branch,
    )

    context = {
        "schema": 1,
        "forge": choice.name,
        "seat": seat,
        "source": source, "mode": mode, "host": host, "project": project,
        "source_branch": source_branch, "refs": refs, "target_branch": target,
        "changed_files": files, "test_files": test_files, "source_files": source_files,
        "diff_unavailable": diff_unavailable,
        "not_text_reviewable": not_text_reviewable,
        "untracked_files": untracked_files,
        "file_list_recovery": forge_metadata.get("file_list_recovery"),
        "unanchorable_files": forge_metadata.get("unanchorable_files", []),
        "diff": diff_text, "batched": batched,
        "change": change, "has_description": bool(change and change.get("description", "").strip()),
        "scope_intent": scope_intent,
        "size": {"files": len(files), "lines": count_changed_lines(diff_text)},
    }
    if batched:
        context["batches"] = batches
    with open(args.out, "w") as fh:
        json.dump(context, fh, indent=2)

    meta = {
        "forge": choice.name,
        "seat": seat,
        "source": source, "mode": mode, "host": host, "project": project,
        "source_branch": source_branch, "refs": refs, "changed_files": files,
        "test_files": test_files, "source_files": source_files,
        "diff_unavailable": diff_unavailable,
        "not_text_reviewable": not_text_reviewable,
        "untracked_files": untracked_files,
        "file_list_recovery": context["file_list_recovery"],
        "batched": batched, "has_description": context["has_description"],
        "scope_intent": scope_intent,
        "size": context["size"],
        "num_batches": len(batches) if batched else (1 if diff_text else 0),
        "out": os.path.abspath(args.out),
    }
    if fallback_reason:
        meta["fallback_reason"] = fallback_reason
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
