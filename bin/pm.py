#!/usr/bin/env python3
"""Read-only view over typed-artifact markdown files: --index, --next, --doctor.

Phase 1: no Status field, no Blocked by, no ROADMAP.md exist yet anywhere in
the schema, so every well-formed entry is open, nothing is blocked, and every
open entry is unplaced. Lifecycle counts (in_progress/delivered/closed) and
roadmap-derived findings are Phase-2+ and never appear here.
"""
from __future__ import annotations

import argparse
import codecs
import locale
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from artifact_lib import Entry, MalformedHeading, parse_entries

SEVERITY_URGENCY = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_URGENCY = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}

NEXT_TOP_N = 5
DEFAULT_MAX_FILE_BYTES = 1_048_576
# Above this, max_bytes + 1 is still a valid Py_ssize_t on every platform, but
# a sys.maxsize-relative bound isn't: CPython accepts a read() size far below
# sys.maxsize on the stack but still fails to actually service it (OverflowError
# or MemoryError) once the size is absurdly large, and where that line falls is
# host-dependent. 1 GiB is comfortably past any real artifact file and
# comfortably short of that failure mode on any real host.
MAX_USABLE_FILE_BYTES = 1_073_741_824


@dataclass(frozen=True)
class ArtifactSpec:
    filename: str
    header: str
    label: str
    urgency_field: str | None
    urgency_table: dict[str, int] | None
    date_field: str | None


BACKLOG_FILES: list[ArtifactSpec] = [
    ArtifactSpec("BUGS.md", "BUG", "BUGS", "Severity", SEVERITY_URGENCY, "Observed"),
    ArtifactSpec("DEFERRED.md", "DEFER", "DEFERRED", "Priority", PRIORITY_URGENCY, "Deferred"),
    # TEST entries carry no date field until the schema-v2 migration adds one.
    ArtifactSpec("TEST_BACKLOG.md", "TEST", "TEST", "Priority", PRIORITY_URGENCY, None),
]
PROPOSALS = ArtifactSpec("proposals.md", "PROPOSAL", "PROPOSALS", None, None, "Proposed")
ALL_SPECS = [*BACKLOG_FILES, PROPOSALS]

NOT_INITIALIZED_MESSAGE = (
    "[quirk:pm] No artifact files found. Run /quirk:artifacts:init to scaffold.\n"
)


@dataclass(frozen=True)
class FileParse:
    spec: ArtifactSpec
    entries: list[Entry]
    malformed: list[MalformedHeading]


def _any_artifact_file_exists(project: Path) -> bool:
    return any((project / spec.filename).exists() for spec in ALL_SPECS)


def _max_file_bytes() -> int:
    raw = os.environ.get("QUIRK_PM_MAX_FILE_BYTES")
    if raw is None:
        return DEFAULT_MAX_FILE_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_FILE_BYTES
    if value <= 0:
        return DEFAULT_MAX_FILE_BYTES
    if value > MAX_USABLE_FILE_BYTES:
        return DEFAULT_MAX_FILE_BYTES
    return value


def _read_and_parse(project: Path, spec: ArtifactSpec) -> tuple[FileParse | None, str | None]:
    """Return (FileParse, None) on success, else (None, skip-reason).

    A read/parse failure or an oversize file is reported as a caller-visible
    skip reason rather than raised, so one bad file never takes down the
    whole read layer. The file is opened once and read up to max_bytes + 1
    bytes in a single call, so pm.py — which runs on every SessionStart —
    never loads more than that bound into memory, even if the file grows
    between a caller's existence check and this read.
    """
    path = project / spec.filename
    max_bytes = _max_file_bytes()
    try:
        # O_NONBLOCK, not path.open: opening a FIFO for reading otherwise blocks
        # until a writer appears, which would hang the SessionStart hook that
        # runs this. The type is then checked against this same fd's fstat, not
        # a separate stat(path) call, so nothing can swap the target in between.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None, "parse error, skipping"
    close_fd = True
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None, "not a regular file, skipping"
        # a regular file ignores O_NONBLOCK on read, so this reads normally
        with os.fdopen(fd, "rb") as f:
            close_fd = False  # fdopen owns fd now; its context manager closes it
            data = f.read(max_bytes + 1)
    except OSError:
        return None, "parse error, skipping"
    finally:
        if close_fd:
            os.close(fd)
    if len(data) > max_bytes:
        return None, f"exceeds {max_bytes} bytes, skipping"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        platform_encoding = locale.getpreferredencoding(False)
        try:
            platform_is_utf8 = codecs.lookup(platform_encoding).name == codecs.lookup("utf-8").name
        except LookupError:
            platform_is_utf8 = False
        if platform_is_utf8:
            # the strict utf-8 decode above already spoke for the platform
            # encoding in this case; retrying it would just fail the same way.
            return None, "parse error, skipping"
        # artifact_append.py writes with the platform default encoding, not
        # explicit utf-8; a file quirk itself wrote must not be dropped over
        # that. On a non-utf-8 host this is still a genuine guess: bytes invalid
        # under utf-8 but valid under the platform encoding are indistinguishable
        # from bytes actually written in some third encoding that also happens
        # to decode cleanly here. No reader can resolve that from the bytes
        # alone, so this fallback stays best-effort.
        try:
            text = data.decode(platform_encoding)
        except (UnicodeDecodeError, LookupError):
            return None, "parse error, skipping"
    try:
        result = parse_entries(text, spec.header)
    except Exception:
        return None, "parse error, skipping"
    return FileParse(spec, result.entries, result.malformed), None


def _urgency(spec: ArtifactSpec, fields: dict[str, str]) -> int:
    if spec.urgency_field is None or spec.urgency_table is None:
        return 2
    raw = (fields.get(spec.urgency_field) or "").strip().lower()
    return spec.urgency_table.get(raw, 2)


def _age_sort_key(spec: ArtifactSpec, fields: dict[str, str]) -> str:
    # missing date sorts oldest; "" precedes every ISO date string lexically
    if spec.date_field is None:
        return ""
    return fields.get(spec.date_field) or ""


def _display_age(spec: ArtifactSpec, fields: dict[str, str]) -> str:
    if spec.date_field is None:
        return "no date"
    return fields.get(spec.date_field) or "no date"


def _doctor_findings(fp: FileParse) -> list[tuple[str, str]]:
    spec = fp.spec
    findings: list[tuple[str, str]] = []
    for m in fp.malformed:
        findings.append((
            "MALFORMED_HEADING",
            f"{spec.header}-{m.id} in {spec.filename} — heading claims an ID with no title",
        ))
    seen: set[int] = set()
    dup_seen: set[int] = set()
    dup_ids: list[int] = []
    for claimed_id in (*(e.id for e in fp.entries), *(m.id for m in fp.malformed)):
        if claimed_id in seen and claimed_id not in dup_seen:
            dup_ids.append(claimed_id)
            dup_seen.add(claimed_id)
        seen.add(claimed_id)
    for eid in dup_ids:
        findings.append((
            "DUPLICATE_ID",
            f"{spec.header}-{eid} in {spec.filename} — two headings claim the same ID",
        ))
    return findings


# --- --index -----------------------------------------------------------


def render_index(project: Path) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE

    parse_error_lines: list[str] = []
    counts_segments: list[str] = []
    ready = 0
    malformed_total = 0
    findings: list[tuple[str, str]] = []

    for spec in BACKLOG_FILES:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                parse_error_lines.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            continue
        open_count = len(fp.entries)
        total = open_count + len(fp.malformed)
        counts_segments.append(f"{spec.label} {open_count}/{total} open")
        ready += open_count
        malformed_total += len(fp.malformed)
        findings.extend(_doctor_findings(fp))

    if (project / PROPOSALS.filename).exists():
        proposals_fp, proposals_skip_reason = _read_and_parse(project, PROPOSALS)
        if proposals_fp is None:
            if proposals_skip_reason is not None:
                parse_error_lines.append(f"[quirk:pm] {PROPOSALS.filename}: {proposals_skip_reason}")
        else:
            findings.extend(_doctor_findings(proposals_fp))

    unplaced_total = ready + malformed_total
    counts_line = "[quirk:pm] " + " · ".join(counts_segments)
    if counts_segments:
        counts_line += " · "
    counts_line += f"{unplaced_total} unplaced ({ready} ready, 0 blocked, {malformed_total} malformed)"

    lines = [counts_line, *parse_error_lines]
    if findings:
        lines.append(f"[quirk:pm] doctor: {len(findings)} findings — run `pm.py --doctor` for details")
    return "\n".join(lines) + "\n"


# --- --next --------------------------------------------------------------


def render_next(project: Path) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE

    parse_error_lines: list[str] = []
    candidates: list[tuple[int, str, int, str, Entry, ArtifactSpec]] = []
    ready = 0
    malformed_total = 0

    for spec in BACKLOG_FILES:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                parse_error_lines.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            continue
        ready += len(fp.entries)
        malformed_total += len(fp.malformed)
        for e in fp.entries:
            candidates.append((_urgency(spec, e.fields), _age_sort_key(spec, e.fields), e.id, spec.header, e, spec))

    candidates.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    top = candidates[:NEXT_TOP_N]

    lines = list(parse_error_lines)
    if top:
        lines.append(f"[quirk:pm] next candidates ({len(top)} of {len(candidates)} ready):")
        for urgency, _age, eid, header, e, spec in top:
            rank_label = e.fields.get(spec.urgency_field) or "unranked"
            lines.append(f"  - {header}-{eid} [{rank_label}] {e.title} — {_display_age(spec, e.fields)}")
    else:
        lines.append("[quirk:pm] no ready candidates")

    unplaced_total = ready + malformed_total
    lines.append(f"[quirk:pm] {unplaced_total} unplaced ({ready} ready, 0 blocked, {malformed_total} malformed)")
    return "\n".join(lines) + "\n"


# --- --doctor --------------------------------------------------------------


def render_doctor(project: Path) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE

    lines: list[str] = []
    findings: list[tuple[str, str]] = []
    for spec in ALL_SPECS:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                lines.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            continue
        findings.extend(_doctor_findings(fp))

    if not findings:
        lines.append("[quirk:pm] doctor: no findings")
    else:
        for code, detail in findings:
            lines.append(f"[quirk:pm] {code}: {detail}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only view of typed-artifact entries.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--index", action="store_true", help="Bounded summary of backlog state")
    group.add_argument("--next", action="store_true", help="Top-5 shortlist of ready work")
    group.add_argument("--doctor", action="store_true", help="Structural findings across artifact files")
    parser.add_argument("--project-dir", default=".", help="Project root containing artifact files")
    args = parser.parse_args(argv)

    project = Path(args.project_dir).resolve()
    if args.index:
        sys.stdout.write(render_index(project))
    elif args.next:
        sys.stdout.write(render_next(project))
    elif args.doctor:
        sys.stdout.write(render_doctor(project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
