#!/usr/bin/env python3
"""Shared markdown-artifact parsing and rendering primitives."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FIELD_RE = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)
SCHEMA_VERSION_RE = re.compile(r"<!--\s*schema-version:\s*(\d+)\s*-->")

LOCK_DIR_PARTS = (".quirk", "locks")


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
                fields=fields, raw=block, start=m.start(),
            ))
        else:
            malformed.append(MalformedHeading(id=entry_id, header=header, reason="no title", fields=fields))
    return ParseResult(entries=entries, malformed=malformed)


def render_entry(schema: dict, entry_id: int, fields: dict[str, str]) -> str:
    """Render a markdown entry block for the given schema and fields."""
    title = fields.get("title", "")
    lines = [f"## {schema['header']}-{entry_id}: {title}"]
    for key in schema["fields"]:
        if key == "title":
            continue
        if fields.get(key):
            label = schema["labels"].get(key, key)
            lines.append(f"- **{label}**: {fields[key]}")
    lines.append("")
    return "\n".join(lines)


def detect_schema_version(text: str) -> int | None:
    m = SCHEMA_VERSION_RE.search(text)
    return int(m.group(1)) if m else None
