#!/usr/bin/env python3
"""Shared markdown-artifact parsing and rendering primitives."""
from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

FIELD_RE = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)
SPLICE_FIELD_LINE_RE = re.compile(r"^-\s+\*\*(.+?)\*\*:.*$", re.MULTILINE)
SCHEMA_VERSION_RE = re.compile(r"<!--\s*schema-version:\s*(\d+)\s*-->")

# filesystems that legitimately reject directory fsync entirely, rather than failing this call
_DIR_FSYNC_UNSUPPORTED_ERRNOS = {errno.EINVAL}
if hasattr(errno, "ENOTSUP"):
    _DIR_FSYNC_UNSUPPORTED_ERRNOS.add(errno.ENOTSUP)

LOCK_DIR_PARTS = (".quirk", "locks")

SCHEMA_VERSION: int = 2


def ensure_lock_dir(project: Path) -> Path:
    """Return the project's lock directory, creating it as self-ignoring if absent.

    The directory carries its own `.gitignore` of `*` rather than an entry in the project's
    root `.gitignore`, so adopting quirk never edits a file the project owns and a project
    initialized before this existed self-heals on its next append. Scoped to `.quirk/locks/`
    because `.quirk/` also holds tracked content.
    """
    lock_dir = project.joinpath(*LOCK_DIR_PARTS)
    lock_dir.mkdir(parents=True, exist_ok=True)
    ignore = lock_dir / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return lock_dir


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _mask_quoted(text: str) -> str:
    """Return text with fenced code and HTML comments blanked, preserving every offset.

    A heading quoted inside a fence is not an entry, and scanning raw text both invents it
    and truncates the block of the entry doing the quoting. Blanking rather than deleting
    keeps `Entry.start` and `Entry.raw` valid against the original file.

    An unterminated fence is left unmasked, deviating from CommonMark: running it to EOF
    would silently hide every entry after a stray backtick, and over-reporting is the safer
    failure for a ledger.
    """
    chars = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "

    for m in _HTML_COMMENT_RE.finditer(text):
        blank(m.start(), m.end())

    pos = 0
    opener: tuple[str, int, int] | None = None
    for line in "".join(chars).splitlines(keepends=True):
        if opener is None:
            m = _FENCE_OPEN_RE.match(line)
            if m is not None:
                opener = (m.group(1)[0], len(m.group(1)), pos)
        else:
            fence_char, fence_len, start = opener
            closer = line.strip()
            if closer and set(closer) == {fence_char} and len(closer) >= fence_len:
                blank(start, pos + len(line))
                opener = None
        pos += len(line)
    return "".join(chars)


def _loose_re(header: str) -> re.Pattern[str]:
    return re.compile(rf"^##\s+{re.escape(header)}-(\d+):", re.MULTILINE)


def _strict_re(header: str) -> re.Pattern[str]:
    return re.compile(rf"^##[ \t]+{re.escape(header)}-(\d+):[ \t]*(\S.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Entry:
    id: int
    header: str
    title: str
    fields: dict[str, str]
    raw: str
    start: int
    end: int


@dataclass(frozen=True)
class MalformedHeading:
    id: int
    header: str
    reason: str
    fields: dict[str, str]


@dataclass(frozen=True)
class ParseResult:
    entries: list[Entry]
    malformed: list[MalformedHeading]


def find_max_id(text: str, header: str) -> int:
    """Return max N from '## HEADER-N:' lines, or 0 if none found."""
    ids = [int(m.group(1)) for m in _loose_re(header).finditer(_mask_quoted(text))]
    return max(ids) if ids else 0


def parse_entries(text: str, header: str) -> ParseResult:
    """Classify every heading claiming HEADER-N into a well-formed Entry or a MalformedHeading.

    Block boundaries come from the loose regex, so any heading that claims an
    ID terminates the preceding block whether or not it is itself well-formed;
    slicing on the strict regex instead would let a malformed heading's block
    run on into its predecessor's and absorb that entry's fields.
    """
    scan = _mask_quoted(text)
    bounds = list(_loose_re(header).finditer(scan))
    strict = _strict_re(header)
    entries: list[Entry] = []
    malformed: list[MalformedHeading] = []
    for i, m in enumerate(bounds):
        end = bounds[i + 1].start() if i + 1 < len(bounds) else len(text)
        block = text[m.start():end]
        masked_block = scan[m.start():end]
        entry_id = int(m.group(1))
        fields = {fm.group(1): fm.group(2).strip() for fm in FIELD_RE.finditer(masked_block)}
        sm = strict.match(masked_block)
        if sm is not None:
            entries.append(Entry(
                id=entry_id, header=header, title=sm.group(2).strip(),
                fields=fields, raw=block, start=m.start(), end=end,
            ))
        else:
            malformed.append(MalformedHeading(id=entry_id, header=header, reason="no title", fields=fields))
    return ParseResult(entries=entries, malformed=malformed)


def render_entry(
    schema: dict, entry_id: int, fields: dict[str, str], *, schema_version: int | None = None
) -> str:
    """Render a markdown entry block for the given schema and fields.

    `schema_version` gates fields listed in `schema["v2_fields"]`: below 2, they are omitted so a
    v1 file never receives a field a v1 reader wouldn't understand. Omitting the parameter (the
    default) preserves the pre-v2 behavior of emitting every populated field.
    """
    title = fields.get("title", "")
    lines = [f"## {schema['header']}-{entry_id}: {title}"]
    suppressed = schema.get("v2_fields", ()) if schema_version is not None and schema_version < 2 else ()
    for key in schema["fields"]:
        if key == "title" or key in suppressed:
            continue
        if fields.get(key):
            label = schema["labels"].get(key, key)
            lines.append(f"- **{label}**: {fields[key]}")
    lines.append("")
    return "\n".join(lines)


_ENTRY_HEADING_RE = re.compile(r"^## ", re.MULTILINE)


def detect_schema_version(text: str) -> int | None:
    """Return the schema-version the file itself declares in its preamble, or None if undeclared.

    Scoped to the text before the first entry heading, found the same masked way `parse_entries`
    finds entry boundaries, so a marker quoted inside an entry's own body — this repo's BUGS.md
    and DEFERRED.md discuss past schema migrations in prose — is never mistaken for the file's
    declaration. The boundary search runs on masked text (fences/comments blanked) but the marker
    search runs on the raw preamble, since the marker is itself an HTML comment that masking would
    blank along with everything else.
    """
    heading = _ENTRY_HEADING_RE.search(_mask_quoted(text))
    preamble = text if heading is None else text[:heading.start()]
    m = SCHEMA_VERSION_RE.search(preamble)
    return int(m.group(1)) if m else None


def hash_probe_spec(spec: str) -> str:
    """Return the first 8 hex characters of sha256(spec) for the `Probe` field's `spec#` fragment."""
    return hashlib.sha256(spec.encode()).hexdigest()[:8]


def hash_file(path: Path) -> str | None:
    """Return the first 8 hex characters of sha256(file bytes), or None if `path` is not a
    readable regular file.
    """
    try:
        # O_NONBLOCK: opening a FIFO for reading otherwise blocks until a writer appears.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except (OSError, ValueError):
        return None
    close_fd = True
    try:
        # checked against this fd's fstat, not a separate stat(path), so the target can't be
        # swapped out between the open and the check
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "rb") as f:
            close_fd = False
            data = f.read()
    except (OSError, ValueError):
        return None
    finally:
        if close_fd:
            os.close(fd)
    return hashlib.sha256(data).hexdigest()[:8]


def atomic_write(path: Path, text: str) -> None:
    """Replace `path`'s contents with `text` via a same-directory temp file and `os.replace`.

    Fsyncs the temp file before the replace and the containing directory after — the first makes
    the new content durable, the second makes the rename itself survive a power cut; neither
    substitutes for the other. Opening the directory is best-effort: platforms that refuse to open
    a directory for reading (Windows) degrade silently rather than raising. Once open, an actual
    fsync failure propagates instead of being swallowed, except on filesystems that reject
    directory fsync outright (EINVAL/ENOTSUP), which degrade the same as a failed open.
    """
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError as e:
        if e.errno not in _DIR_FSYNC_UNSUPPORTED_ERRNOS:
            raise
    finally:
        os.close(dir_fd)


def field_line(label: str, value: str) -> str:
    return f"- **{label}**: {value}"


class DuplicateFieldError(Exception):
    """Raised when an entry's block contains more than one line for the same field label."""


def splice_field(text: str, entry: Entry, label: str, value: str | None) -> str:
    """Replace, insert, or remove `label`'s field line inside `entry`'s block.

    Bounded by `entry.start`/`entry.end`, never by scanning forward for the next `##`, so this is
    safe against both the file's last entry and a fenced heading nested inside the block. Matching
    runs against masked text — the same technique `parse_entries` uses when computing `fields` —
    so a label quoted inside a fenced example is never mistaken for a live duplicate or edited in
    place of the real line.
    """
    scan = _mask_quoted(text)
    block = text[entry.start:entry.end]
    masked_block = scan[entry.start:entry.end]

    label_re = re.compile(rf"^-\s+\*\*{re.escape(label)}\*\*:.*$", re.MULTILINE)
    matches = list(label_re.finditer(masked_block))
    if len(matches) > 1:
        raise DuplicateFieldError(label)

    if matches:
        line_start, line_end = matches[0].start(), matches[0].end()
        if value is None:
            if line_end < len(block) and block[line_end] == "\n":
                new_block = block[:line_start] + block[line_end + 1:]
            else:
                sep_start = line_start - 1
                if sep_start > 0 and block[sep_start - 1] == "\r":
                    sep_start -= 1
                new_block = block[:sep_start] + block[line_end:]
        else:
            new_block = block[:line_start] + field_line(label, value) + block[line_end:]
        return text[:entry.start] + new_block + text[entry.end:]

    if value is None:
        return text

    field_matches = list(SPLICE_FIELD_LINE_RE.finditer(masked_block))
    if field_matches:
        anchor_end = field_matches[-1].end()
    else:
        nl = block.find("\n")
        anchor_end = nl if nl != -1 else len(block)

    new_line = field_line(label, value)
    if anchor_end < len(block) and block[anchor_end] == "\n":
        insert_at = anchor_end + 1
        new_block = block[:insert_at] + new_line + "\n" + block[insert_at:]
    else:
        new_block = block[:anchor_end] + "\n" + new_line

    return text[:entry.start] + new_block + text[entry.end:]


_MILESTONE_HEADING_RE = re.compile(r"^## Milestone: (.+)$")
_ROADMAP_BLANK_RE = re.compile(r"^\s*$")
# [0-9], not \d: \d admits non-ASCII decimal digits that int() would fold onto an ASCII-spelled
# id; 0|[1-9][0-9]* additionally excludes leading zeros, so BUG-007 and BUG-7 stay two spellings
# rather than being silently normalized to one.
_ROADMAP_MEMBER_RE = re.compile(r"^- (BUG|DEFER|TEST)-(0|[1-9][0-9]*)\s*$")
_ROADMAP_DISALLOWED_MEMBER_RE = re.compile(r"^- ([A-Z]+)-(0|[1-9][0-9]*)\s*$")

_ROADMAP_WRITE_BLOCKING_CODES = frozenset({
    "ROADMAP_LINE_MALFORMED",
    "PROPOSAL_IN_ROADMAP",
    "UNKNOWN_HEADER_IN_ROADMAP",
    "DUPLICATE_MEMBERSHIP",
})


@dataclass(frozen=True)
class Milestone:
    name: str
    rank: int
    members: list[str]
    raw_lines: list[str]


@dataclass(frozen=True)
class RoadmapParse:
    milestones: list[Milestone]
    findings: list[tuple[str, str]]
    preamble: str


def _line_body(line: str) -> str:
    """Return `line` without its trailing line terminator, or "" for an empty string."""
    return line.splitlines()[0] if line else ""


def parse_roadmap(text: str) -> RoadmapParse:
    """Parse `ROADMAP.md`'s milestone/member grammar into structured form.

    Total: no input raises. Every line falls into exactly one class (blank, comment, milestone
    heading, member, disallowed member, or malformed); a line under a milestone that matches none
    of the recognized shapes is reported as a `ROADMAP_LINE_MALFORMED` finding rather than failing
    the parse.
    """
    masked = _mask_quoted(text)
    lines = text.splitlines(keepends=True)
    masked_lines = masked.splitlines(keepends=True)

    # matched against masked text so a heading quoted inside the schema's HTML comment (the
    # worked example in its own docstring) is never mistaken for a real milestone
    first_idx = None
    for i, mline in enumerate(masked_lines):
        if _MILESTONE_HEADING_RE.match(_line_body(mline)):
            first_idx = i
            break

    if first_idx is None:
        return RoadmapParse(milestones=[], findings=[], preamble=text)

    preamble = "".join(lines[:first_idx])

    milestones: list[Milestone] = []
    findings: list[tuple[str, str]] = []
    first_milestone_for_id: dict[str, str] = {}
    seen_milestone_names: set[str] = set()

    name: str | None = None
    members: list[str] = []
    raw_lines: list[str] = []

    def close_milestone() -> None:
        if name is not None:
            milestones.append(
                Milestone(name=name, rank=len(milestones), members=members, raw_lines=raw_lines)
            )

    for i in range(first_idx, len(lines)):
        raw_line = lines[i]
        body = _line_body(masked_lines[i])

        heading = _MILESTONE_HEADING_RE.match(body)
        if heading is not None:
            close_milestone()
            name = heading.group(1)
            if name in seen_milestone_names:
                findings.append(("DUPLICATE_MILESTONE_NAME", name))
            seen_milestone_names.add(name)
            members = []
            raw_lines = []
            continue

        if _ROADMAP_BLANK_RE.match(body):
            raw_lines.append(raw_line)
            continue

        # member shape is checked before header identity, so a header outside BUG/DEFER/TEST
        # (e.g. PROPOSAL) still reaches a named finding instead of falling through to "malformed"
        member = _ROADMAP_MEMBER_RE.match(body)
        if member is not None:
            entry_id = f"{member.group(1)}-{member.group(2)}"
            raw_lines.append(raw_line)
            if entry_id in first_milestone_for_id:
                findings.append((
                    "DUPLICATE_MEMBERSHIP",
                    f"{entry_id}: first in '{first_milestone_for_id[entry_id]}', "
                    f"duplicated in '{name}'",
                ))
            else:
                first_milestone_for_id[entry_id] = name
            members.append(entry_id)
            continue

        disallowed = _ROADMAP_DISALLOWED_MEMBER_RE.match(body)
        if disallowed is not None:
            header, num = disallowed.group(1), disallowed.group(2)
            raw_lines.append(raw_line)
            code = "PROPOSAL_IN_ROADMAP" if header == "PROPOSAL" else "UNKNOWN_HEADER_IN_ROADMAP"
            findings.append((code, f"{header}-{num}"))
            continue

        findings.append(("ROADMAP_LINE_MALFORMED", f"{name}: {body}"))

    close_milestone()
    return RoadmapParse(milestones=milestones, findings=findings, preamble=preamble)


def render_roadmap(parse: RoadmapParse) -> str:
    """Reconstruct `ROADMAP.md` text from a parse; byte-for-byte for any input with no findings.

    Milestone bodies come from `raw_lines`, not `members`: a finding-free parse never dropped a
    line, so this is a lossless inverse of `parse_roadmap`. A parse carrying a
    `ROADMAP_LINE_MALFORMED` finding already dropped that line when it was parsed and cannot
    round-trip it back in.
    """
    parts = [parse.preamble]
    for milestone in parse.milestones:
        parts.append(f"## Milestone: {milestone.name}\n")
        parts.extend(milestone.raw_lines)
    return "".join(parts)


def validate_roadmap_for_write(
    parse: RoadmapParse, known_ids: set[str] | None = None
) -> list[tuple[str, str]]:
    """Return the findings that must block `roadmap --write`.

    Blocking regardless of input: malformed lines, disallowed member headers, and duplicate
    membership — a freshly agent-proposed file has no legacy content to be lenient about.
    Dangling references block too, but only once `known_ids` is supplied; `None` means the ledger
    was not checked, not that every id is known. `DUPLICATE_MILESTONE_NAME` never blocks: rank
    comes from document position, never from name, so a name collision can't corrupt a write.
    """
    blocking = [f for f in parse.findings if f[0] in _ROADMAP_WRITE_BLOCKING_CODES]
    if known_ids is not None:
        referenced = {member_id for milestone in parse.milestones for member_id in milestone.members}
        blocking.extend(
            ("DANGLING_ROADMAP_REF", member_id) for member_id in sorted(referenced - known_ids)
        )
    return blocking
