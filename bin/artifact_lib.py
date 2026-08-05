#!/usr/bin/env python3
"""Shared markdown-artifact parsing and rendering primitives."""
from __future__ import annotations

import re
from dataclasses import dataclass

FIELD_RE = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)
SCHEMA_VERSION_RE = re.compile(r"<!--\s*schema-version:\s*(\d+)\s*-->")


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
    ids = [int(m.group(1)) for m in _loose_re(header).finditer(text)]
    return max(ids) if ids else 0


def parse_entries(text: str, header: str) -> ParseResult:
    """Classify every heading claiming HEADER-N into a well-formed Entry or a MalformedHeading.

    Block boundaries come from the loose regex, so any heading that claims an
    ID terminates the preceding block whether or not it is itself well-formed;
    slicing on the strict regex instead would let a malformed heading's block
    run on into its predecessor's and absorb that entry's fields.
    """
    bounds = list(_loose_re(header).finditer(text))
    strict = _strict_re(header)
    entries: list[Entry] = []
    malformed: list[MalformedHeading] = []
    for i, m in enumerate(bounds):
        end = bounds[i + 1].start() if i + 1 < len(bounds) else len(text)
        block = text[m.start():end]
        entry_id = int(m.group(1))
        fields = {fm.group(1): fm.group(2).strip() for fm in FIELD_RE.finditer(block)}
        sm = strict.match(block)
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
