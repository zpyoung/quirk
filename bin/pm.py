#!/usr/bin/env python3
"""Subcommand CLI over typed-artifact markdown files: index/next/doctor/status/migrate/roadmap,
plus the Phase-2 lifecycle commands start/finish/park/decide/reconcile.

The read layer (index/next/doctor/status/roadmap) consumes `Status`, `Blocked by`, and
`ROADMAP.md` membership to compute readiness (`ready`/`eligible`/`unplaced`) and to run
cross-ledger doctor findings (`CYCLE`, `DANGLING`, `BLOCKED_BY_*`, roadmap findings). The
lifecycle commands mutate an entry's `Status`/`Probe` fields under the same compare-and-swap
procedure — acquire the ledger's lock, re-read, compare the expectation tuple captured before any
slow work, splice and write on match, refuse without writing on mismatch. `start` here is
`--here`-only (Phase 2): no `Handoff` field, no worktree, no dispatch; `reconcile` likewise
evaluates ancestry in the project's own repo rather than a `Handoff.dest:`.
"""
from __future__ import annotations

import argparse
import codecs
import datetime
import fcntl
import locale
import math
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, IO, Iterable, Iterator

from artifact_lib import (
    DuplicateFieldError,
    Entry,
    MalformedHeading,
    RoadmapParse,
    SymlinkedLedgerError,
    _preamble_member_findings,
    atomic_write,
    detect_schema_version,
    duplicate_field_labels,
    ensure_lock_dir,
    field_present_but_empty,
    hash_file,
    hash_probe_spec,
    mask_quoted,
    parse_entries,
    parse_roadmap,
    render_roadmap,
    splice_field,
    validate_roadmap_for_write,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

# bin/artifact_append.py's scheme (2/3/5/8), extended per docs/quirk/specs/2026-08-04-pm-agent/
# tech.md's Exit codes table. Shared here so every later pm.py subcommand reuses one table
# instead of re-deriving its own numbering.
EXIT_OK = 0
EXIT_UNEXPECTED_ERROR = 1
EXIT_BAD_ARGUMENT = 2
EXIT_NOT_FOUND = 3
EXIT_CORRUPT_ENTRY = 4
EXIT_LOCK_TIMEOUT = 5
EXIT_CAS_FAILURE = 6
EXIT_PROJECT_DIR_NOT_FOUND = 7
EXIT_SCHEMA_MISMATCH = 8
EXIT_PROBE_REFUSED = 9
EXIT_FINISH_PRECONDITION_FAILED = 10
EXIT_ADAPTER_FAILURE = 11

SEVERITY_URGENCY = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_URGENCY = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}

NEXT_TOP_N = 5
INDEX_IN_PROGRESS_CAP = 10
INDEX_DELIVERED_CAP = 5
INDEX_TITLE_TRUNCATE = 60
DEFAULT_MAX_FILE_BYTES = 1_048_576
# Above this, max_bytes + 1 is still a valid Py_ssize_t on every platform, but
# a sys.maxsize-relative bound isn't: CPython accepts a read() size far below
# sys.maxsize on the stack but still fails to actually service it (OverflowError
# or MemoryError) once the size is absurdly large, and where that line falls is
# host-dependent. 1 GiB is comfortably past any real artifact file and
# comfortably short of that failure mode on any real host.
MAX_USABLE_FILE_BYTES = 1_073_741_824

DEFAULT_LOCK_TIMEOUT = 5.0
DEFAULT_PROBE_TIMEOUT = 120.0
# bounds the post-timeout drain: a descendant that left the process group (its own setsid, or a
# daemon) and still holds the runner's stdout/stderr pipe open keeps communicate() blocked on EOF
# past the group kill, so this second wait can't be unbounded either
PROBE_KILL_DRAIN_TIMEOUT = 5.0
DEFAULT_TEST_RUNNER = "python3 -m pytest"
DEFAULT_TEST_EXIT_MAP: dict[int, str] = {0: "pass", 1: "fail", 4: "missing", 5: "missing"}
_PROBE_OUTCOMES = frozenset({"pass", "fail", "missing", "error"})

DEFAULT_STALL_DAYS = 7
DEFAULT_UNDETERMINED_AFTER_DAYS = 14


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
    ArtifactSpec("TEST_BACKLOG.md", "TEST", "TEST", "Priority", PRIORITY_URGENCY, "Logged"),
]
PROPOSALS = ArtifactSpec("proposals.md", "PROPOSAL", "PROPOSALS", None, None, "Proposed")
ALL_SPECS = [*BACKLOG_FILES, PROPOSALS]
LEDGER_FILES: list[str] = [spec.filename for spec in ALL_SPECS]

NOT_INITIALIZED_MESSAGE = (
    "[quirk:pm] No artifact files found. Run /quirk:artifacts:init to scaffold.\n"
)


@dataclass(frozen=True)
class FileParse:
    spec: ArtifactSpec
    entries: list[Entry]
    malformed: list[MalformedHeading]
    text: str


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


def _lock_timeout() -> float:
    """The `ARTIFACT_LOCK_TIMEOUT` bound (seconds) in effect, mirroring `_max_file_bytes()`'s
    validation shape: a non-numeric, non-finite, or non-positive value falls back to the default
    rather than being honored — `inf` would make a contended lock's caller wait forever, and a
    bare `float()` on a non-numeric value would raise `ValueError` out of the command.
    """
    raw = os.environ.get("ARTIFACT_LOCK_TIMEOUT")
    if raw is None:
        return DEFAULT_LOCK_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_LOCK_TIMEOUT
    return value


def _read_file_safely(path: Path, max_bytes: int) -> tuple[bytes | None, str | None]:
    """Return (bytes, None) on success, else (None, skip-reason).

    A read failure or an oversize file is reported as a caller-visible skip reason rather than
    raised, so one bad file never takes down the whole read layer. The file is opened once and
    read up to max_bytes + 1 bytes in a single call, so a caller that runs on every SessionStart
    never loads more than that bound into memory, even if the file grows between a caller's
    existence check and this read.
    """
    try:
        # O_NONBLOCK, not path.open: opening a FIFO for reading otherwise blocks
        # until a writer appears, which would hang the SessionStart hook that
        # runs this. The type is then checked against this same fd's fstat, not
        # a separate stat(path) call, so nothing can swap the target in between.
        # O_NONBLOCK doesn't exist on Windows, which also has no POSIX FIFOs to
        # block on, so 0 (a no-op flag) is the correct fallback there.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
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
    return data, None


def _decode_platform_text(data: bytes) -> str | None:
    """Return `data` decoded to text, or `None` if it decodes under neither candidate encoding.

    artifact_append.py writes these files with the platform default encoding, not explicit
    utf-8 (fenced there). Bytes valid under both codecs must decode as the writer actually wrote
    them, not as whichever codec is tried first, so the platform codec goes first whenever it
    differs from utf-8 — this couples the reader to that locale-dependent write.
    """
    platform_encoding = locale.getpreferredencoding(False)
    try:
        platform_is_utf8 = codecs.lookup(platform_encoding).name == codecs.lookup("utf-8").name
    except LookupError:
        platform_is_utf8 = False
    if platform_is_utf8:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        return data.decode(platform_encoding)
    except (UnicodeDecodeError, LookupError):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None


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
    data, skip_reason = _read_file_safely(path, max_bytes)
    if data is None:
        return None, skip_reason
    text = _decode_platform_text(data)
    if text is None:
        return None, "parse error, skipping"
    try:
        result = parse_entries(text, spec.header)
    except Exception:
        return None, "parse error, skipping"
    return FileParse(spec, result.entries, result.malformed, text), None


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


# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §Doctor findings catalog. Codes this module
# surfaces but that aren't catalog rows (BLOCKED_BY_TRUNCATED, UNKNOWN_HEADER_IN_ROADMAP,
# ROADMAP_UNREADABLE — forwarded from artifact_lib) fall back to "warning" below, the same tier
# as the DANGLING-adjacent findings they stand in for.
SEVERITY_ORDER = ("warning", "notice", "informational")

FINDING_SEVERITY: dict[str, str] = {
    "DANGLING": "warning",
    "BLOCKED_BY_PROPOSAL": "warning",
    "CYCLE": "warning",
    "DUPLICATE_ID": "warning",
    "MALFORMED_HEADING": "warning",
    "DANGLING_ROADMAP_REF": "warning",
    "MEMBER_OUTSIDE_MILESTONE": "warning",
    "PROPOSAL_IN_ROADMAP": "warning",
    "ROADMAP_LINE_MALFORMED": "warning",
    "MALFORMED_LIFECYCLE_FIELD": "warning",
    "DUPLICATE_LIFECYCLE_FIELD": "warning",
    "POST_MERGE_PROBE_REGRESSION": "warning",
    "DUPLICATE_MEMBERSHIP": "notice",
    "DUPLICATE_MILESTONE_NAME": "notice",
    "BLOCKED_BY_DUPLICATE": "notice",
    "PROBE_SPEC_CHANGED": "notice",
    "PROBE_FILE_CHANGED": "notice",
    "STALLED": "informational",
    "AWAITING_INTEGRATION": "informational",
    "UNDETERMINED": "informational",
    "UNVERIFIED_DELIVERY": "informational",
}


def _finding_severity(code: str) -> str:
    return FINDING_SEVERITY.get(code, "warning")


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


def _index_counts_segments(
    project: Path, world: LedgerWorld, parse_error_lines: list[str]
) -> list[str]:
    """Return one `"{label} N open (M blocked)"` segment per readable, present backlog file.

    A missing file contributes no segment, matching Phase 1's behavior. A file that failed to
    parse likewise contributes none — its parse-error line (already in `parse_error_lines`, from
    the same `ALL_SPECS` pass `--doctor` uses) is what reports it instead, so the two never
    disagree about which files are readable.
    """
    by_file: dict[str, list[tuple[str, Entry]]] = {spec.filename: [] for spec in BACKLOG_FILES}
    for key, (entry, spec) in world.entries.items():
        by_file[spec.filename].append((key, entry))

    segments: list[str] = []
    for spec in BACKLOG_FILES:
        if not (project / spec.filename).exists():
            continue
        if any(line.startswith(f"[quirk:pm] {spec.filename}:") for line in parse_error_lines):
            continue
        open_count = blocked_count = 0
        for key, entry in by_file[spec.filename]:
            if not _is_open(entry):
                continue
            open_count += 1
            if not ready(world, key):
                blocked_count += 1
        segment = f"{spec.label} {open_count} open"
        if blocked_count:
            segment += f" ({blocked_count} blocked)"
        segments.append(segment)
    return segments


def _index_closed_evidence(world: LedgerWorld) -> tuple[int, int, int]:
    """Return `(total closed, probed, unverified/none)` — the same `Probe.verb == "none"` split
    `UNVERIFIED_DELIVERY` draws in the doctor catalog, so the two surfaces never disagree about
    which closures carry independent evidence.
    """
    total = probed = unverified = 0
    for _key, (entry, _spec) in world.entries.items():
        status = _entry_status(entry)
        if not isinstance(status, StatusField) or status.state != "closed":
            continue
        total += 1
        probe = _entry_probe(entry)
        if isinstance(probe, ProbeField) and probe.verb == "none":
            unverified += 1
        else:
            probed += 1
    return total, probed, unverified


def _index_lifecycle_section(
    world: LedgerWorld, today: str, *, state: str, verb: str, header: str, cap: int
) -> list[str]:
    """Render a bounded, ID-based `state` section (`in_progress` / `delivered`), oldest first so
    a cap trims the freshest — least actionable — entries rather than the ones most worth seeing.

    Omitted entirely when `state` has no matching entries, per the read layer's contract that a
    zero-entry section renders nothing rather than a count of zero.
    """
    candidates: list[tuple[str, Entry, StatusField]] = []
    for key, (entry, _spec) in world.entries.items():
        status = _entry_status(entry)
        if isinstance(status, StatusField) and status.state == state:
            candidates.append((key, entry, status))
    if not candidates:
        return []

    def sort_key(item: tuple[str, Entry, StatusField]) -> tuple[int, str, int]:
        key, _entry, status = item
        age = _days_since(today, status.date)
        return (-(age if age is not None else -1), *_entry_sort_key(key))

    candidates.sort(key=sort_key)
    shown = candidates[:cap]

    lines = [f"[quirk:pm] {header} ({len(shown)} shown / {len(candidates)} total):"]
    for key, entry, status in shown:
        title = entry.title[:INDEX_TITLE_TRUNCATE]
        age = _days_since(today, status.date)
        age_part = f" ({age}d ago)" if age is not None else ""
        row = f"  - {key} {title} — {verb} {status.date}{age_part}"
        if state == "in_progress":
            # reuses doctor's own threshold check so --index and --doctor can never disagree
            # about which in_progress entries are stalled
            if any(code == "STALLED" for code, _detail in _status_age_findings(key, status, today)):
                row += " — STALLED"
        lines.append(row)

    remaining = len(candidates) - len(shown)
    if remaining > 0:
        lines.append(f"  …and {remaining} more")
    return lines


def render_index(project: Path, *, today: str | None = None) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE
    if today is None:
        today = _today()

    world = _load_ledger_world(project)
    roadmap = _read_roadmap(project)
    ranks = _milestone_ranks(roadmap)
    findings, parse_error_lines = _collect_all_findings(project, today)

    ready_count, blocked_count, malformed_count = _unplaced_counts(world, ranks)
    unplaced_total = ready_count + blocked_count + malformed_count
    counts_segments = _index_counts_segments(project, world, parse_error_lines)
    counts_segments.append(
        f"{unplaced_total} unplaced ({ready_count} ready, {blocked_count} blocked, {malformed_count} malformed)"
    )
    lines = ["[quirk:pm] " + " · ".join(counts_segments), *parse_error_lines]

    lines.extend(_index_lifecycle_section(
        world, today, state="in_progress", verb="started",
        header="in_progress", cap=INDEX_IN_PROGRESS_CAP,
    ))
    lines.extend(_index_lifecycle_section(
        world, today, state="delivered", verb="delivered",
        header="delivered, awaiting integration", cap=INDEX_DELIVERED_CAP,
    ))

    closed_total, closed_probed, closed_unverified = _index_closed_evidence(world)
    if closed_total:
        lines.append(
            f"[quirk:pm] closed {closed_total} total ({closed_probed} probed, {closed_unverified} unverified/none)"
        )

    if findings:
        lines.append(f"[quirk:pm] doctor: {len(findings)} findings — run /quirk:pm:status for details")
    return "\n".join(lines) + "\n"


# --- --next --------------------------------------------------------------


def render_next(project: Path) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE

    world = _load_ledger_world(project)
    roadmap = _read_roadmap(project)
    ranks = _milestone_ranks(roadmap)

    ready_keys: list[str] = []
    candidates: list[tuple[int, int, str, int, str, Entry, ArtifactSpec]] = []
    for key, (entry, spec) in world.entries.items():
        if not (_is_open(entry) and ready(world, key)):
            continue
        ready_keys.append(key)
        if not eligible(world, ranks, key):
            continue
        rank = ranks.get(key, -1)
        urgency = _urgency(spec, entry.fields)
        age = _age_sort_key(spec, entry.fields)
        candidates.append((rank, urgency, age, entry.id, spec.header, entry, spec))
    candidates.sort(key=lambda c: (c[0], c[1], c[2], c[3], c[4]))
    top = candidates[:NEXT_TOP_N]

    lines = list(world.parse_errors)
    if top:
        lines.append(f"[quirk:pm] next candidates ({len(top)} of {len(candidates)} eligible):")
        for _rank, _urgency_val, _age, eid, header, e, spec in top:
            rank_label = e.fields.get(spec.urgency_field) or "unranked"
            lines.append(f"  - {header}-{eid} [{rank_label}] {e.title} — {_display_age(spec, e.fields)}")
    elif ready_keys:
        # the shortlist can be empty with ready work still on the board: medium/low-urgency
        # entries in no milestone are ready but not eligible, so this must not say "no ready
        # candidates" — that would contradict the "N ready" count printed two lines down
        lines.append(
            f"[quirk:pm] {len(ready_keys)} ready but not eligible: sitting in no milestone at "
            "medium/low urgency — place them on the roadmap to make them visible"
        )
    else:
        lines.append("[quirk:pm] no ready candidates")
        culprits = _blocking_culprits(world)
        if culprits:
            named = ", ".join(f"{blocker_id} (blocks {count})" for blocker_id, count in culprits)
            lines.append(f"[quirk:pm] blocked by: {named}")

    ready_count, blocked_count, malformed_count = _unplaced_counts(world, ranks)
    unplaced_total = ready_count + blocked_count + malformed_count
    lines.append(
        f"[quirk:pm] {unplaced_total} unplaced "
        f"({ready_count} ready, {blocked_count} blocked, {malformed_count} malformed)"
    )
    return "\n".join(lines) + "\n"


# --- --doctor --------------------------------------------------------------


def _collect_all_findings(project: Path, today: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return `(findings, parse_error_lines)` exactly as `render_doctor` computes them.

    Factored out so `--index`'s finding count and per-entry `STALLED` check can share this one
    computation with `--doctor` instead of a second, independently-drifting implementation of
    the same catalog.
    """
    parse_error_lines: list[str] = []
    findings: list[tuple[str, str]] = []
    for spec in ALL_SPECS:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                parse_error_lines.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            continue
        findings.extend(_doctor_findings(fp))
        if spec.header != "PROPOSAL":
            findings.extend(_lifecycle_doctor_findings(fp, today))

    findings.extend(_cross_ledger_doctor_findings(project))
    return findings, parse_error_lines


def render_doctor(project: Path, *, today: str | None = None) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE
    if today is None:
        today = _today()

    findings, lines = _collect_all_findings(project, today)

    if not findings:
        lines.append("[quirk:pm] doctor: no findings")
    else:
        grouped: dict[str, list[tuple[str, str]]] = {severity: [] for severity in SEVERITY_ORDER}
        for code, detail in findings:
            grouped[_finding_severity(code)].append((code, detail))
        for severity in SEVERITY_ORDER:
            for code, detail in grouped[severity]:
                lines.append(f"[quirk:pm] {code}: {detail}")
    return "\n".join(lines) + "\n"


# --- migrate -----------------------------------------------------------

# matches an optional legacy `<!-- schema-version: N -->` line followed by the mandatory
# `<!-- ... SCHEMA ... -->` comment, both anchored to the file's first byte — every ledger
# this plugin ships (templates and every fixture) puts the schema comment first. Line
# terminators are matched as `\r\n` or `\n` (never a bare `\n`), since the ledger being
# migrated is now read with its original bytes intact and may be CRLF.
_LEGACY_PREAMBLE_RE = re.compile(
    r"\A(?:<!--\s*schema-version:\s*\d+\s*-->(?:\r\n|\n))?(<!--.*?-->(?:\r\n|\n)?)", re.DOTALL
)


def _v2_schema_block(filename: str) -> str:
    """Return `templates/{filename}`'s leading version marker + schema-comment block.

    Sourced from the template rather than duplicated as a string literal, so the template
    stays the single definition of the v2 comment text and a future edit to it can't drift
    out of sync with what `migrate` writes.
    """
    template_text = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    m = _LEGACY_PREAMBLE_RE.match(template_text)
    if m is None:
        raise RuntimeError(f"templates/{filename} has no leading schema-comment block")
    return template_text[:m.end()]


def _migrate_ledger_text(text: str, filename: str) -> str:
    """Return `text` with its schema-comment block replaced by the v2 one, entries untouched."""
    v2_block = _v2_schema_block(filename)
    m = _LEGACY_PREAMBLE_RE.match(text)
    if m is None:
        return v2_block + text
    return v2_block + text[m.end():]


def _acquire_ledger_lock(lock_path: Path, deadline: float) -> IO[str] | None:
    """Open `lock_path` and block (polling) for its exclusive flock until acquired or `deadline`.

    Returns the open, locked file object, or `None` on timeout. Closing the returned object is
    what releases the flock, so on timeout the caller owes nothing back for this call — the file
    opened here is already closed before `None` is returned.

    Raises `SymlinkedLedgerError` — the same refusal `atomic_write` raises for a symlinked ledger
    — when `lock_path` is itself a symlink, so `main()`'s existing handler for that reports it as
    a deliberate refusal (exit 2) rather than letting the `OSError` `O_NOFOLLOW` raises reach the
    catch-all and blame pm.py for the user's setup.
    """
    # a lock file's contents are never read or written, only its existence and its flock, so
    # O_NOFOLLOW refuses a symlink planted at this path instead of opening (and O_CREAT|O_RDWR
    # truncating) whatever it points at
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        if lock_path.is_symlink():
            raise SymlinkedLedgerError(f"refusing to use a symlinked lock file: {lock_path}") from exc
        raise
    lock_file = os.fdopen(fd, "r+")
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_file
        except BlockingIOError:
            if time.monotonic() > deadline:
                lock_file.close()
                return None
            time.sleep(0.05)


def _migrate_one_ledger(project: Path, filename: str) -> tuple[str, str]:
    """Migrate one ledger file to schema v2. Caller must already hold `filename`'s lock.

    Returns `(outcome, message)`; `outcome` is one of `"already_v2"` / `"migrated"` / `"too_new"`,
    folded by the caller into `migrate`'s per-file report and aggregate exit code. Any exception
    propagates to the caller uncaught, so an unexpected failure aborts the run rather than being
    silently absorbed per-file.

    Reads and writes with `newline=""`: `migrate`'s contract is that it touches no entry body,
    and universal-newline translation on read would silently rewrite every CRLF line ending in
    the file to LF, which is exactly such a touch. The encoding is pinned to match
    `atomic_write`'s for the same reason — reading in the host locale and writing utf-8
    transcodes every non-ASCII byte on a host where those differ.
    """
    target = project / filename
    with target.open(encoding="utf-8", newline="") as f:
        text = f.read()
    version = detect_schema_version(text)
    if version == 2:
        return "already_v2", f"{filename}: already v2"
    if version is not None and version > 2:
        return (
            "too_new",
            f"{filename}: schema v{version} file, plugin understands v2. Upgrade quirk.",
        )

    atomic_write(target, _migrate_ledger_text(text, filename))
    return "migrated", f"{filename}: migrated to v2"


def _migrate_preflight_too_new(project: Path) -> str | None:
    """Read-only, pre-lock scan of every ledger for a schema version this plugin can't migrate.

    `cmd_migrate` needs this answer before it acquires any lock: discovering a too-new file only
    after lock contention would let an unrelated timeout (5) mask what tech.md's exit-code
    precedence (7 -> 3 -> 8 -> 5) says must be an unconditional 8. Not a substitute for the
    lock-held check `_migrate_one_ledger` still does on every file — a file can change between
    this scan and that one.
    """
    for filename in LEDGER_FILES:
        path = project / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as f:
            version = detect_schema_version(f.read())
        if version is not None and version > 2:
            return f"{filename}: schema v{version} file, plugin understands v2. Upgrade quirk."
    return None


def cmd_migrate(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    missing = [name for name in LEDGER_FILES if not (project / name).exists()]
    if missing:
        print(
            f"{', '.join(missing)} not found in {project}. Run /quirk:artifacts:init first.",
            file=sys.stderr,
        )
        return EXIT_NOT_FOUND

    too_new_message = _migrate_preflight_too_new(project)
    if too_new_message is not None:
        print(f"[quirk:pm] {too_new_message}", file=sys.stderr)
        return EXIT_SCHEMA_MISMATCH

    lock_dir = ensure_lock_dir(project)
    timeout = _lock_timeout()
    deadline = time.monotonic() + timeout

    held_locks: list[IO[str]] = []
    try:
        # every lock is held before any file is touched, so a timeout partway through never
        # leaves an earlier ledger migrated while a later one wasn't — a fixed order (this
        # list's, with ROADMAP.md's lock taken last) is what keeps that safe against deadlock,
        # since two acquirers taking locks in different orders can wait on each other forever
        for filename in (*LEDGER_FILES, "ROADMAP.md"):
            lock_file = _acquire_ledger_lock(lock_dir / f"{filename}.lock", deadline)
            if lock_file is None:
                print(
                    f"[quirk:pm] could not acquire lock on {filename}, nothing written",
                    file=sys.stderr,
                )
                return EXIT_LOCK_TIMEOUT
            held_locks.append(lock_file)

        # re-run under lock, over every ledger, before any of them is written: a file can become
        # too new in the window between the read-only preflight above and the lock actually
        # being held, and the all-or-nothing property every lock is acquired up front for must
        # hold here too — discovering the problem mid-write-loop, after an earlier ledger has
        # already been migrated, is the same partial-migration failure the preflight exists to
        # prevent, just moved one step later
        too_new_message = _migrate_preflight_too_new(project)
        if too_new_message is not None:
            print(f"[quirk:pm] {too_new_message}", file=sys.stderr)
            return EXIT_SCHEMA_MISMATCH

        for filename in LEDGER_FILES:
            _outcome, message = _migrate_one_ledger(project, filename)
            print(f"[quirk:pm] {message}")

        roadmap_path = project / "ROADMAP.md"
        if roadmap_path.exists():
            print("[quirk:pm] ROADMAP.md: already exists")
        else:
            template_text = (TEMPLATES_DIR / "ROADMAP.md").read_text(encoding="utf-8")
            atomic_write(roadmap_path, template_text)
            print("[quirk:pm] ROADMAP.md: created")
    finally:
        for lock_file in held_locks:
            lock_file.close()

    return EXIT_OK


# --- read-command handlers ---------------------------------------------


def cmd_index(args: argparse.Namespace) -> int:
    sys.stdout.write(render_index(Path(args.project_dir).resolve()))
    return EXIT_OK


def cmd_next(args: argparse.Namespace) -> int:
    sys.stdout.write(render_next(Path(args.project_dir).resolve()))
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    sys.stdout.write(render_doctor(Path(args.project_dir).resolve()))
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    # one shared `today` for both halves, so a midnight rollover between the two calls can
    # never make the index's finding count disagree with the doctor findings printed under it
    today = _today()
    sys.stdout.write(render_index(project, today=today) + render_doctor(project, today=today))
    return EXIT_OK


# --- lifecycle field grammar: Status, Probe -----------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §Field rendering. `Handoff` is Phase 3
# (logic.md:778-785 locks Phase 2's `start` to `--here`, which never writes it) and is not
# implemented here.

DELIM = " — "  # space, em dash, space: the one delimiter every lifecycle field splits on
_FREE_TEXT_BAD_RE = re.compile(r"[\r\n]| — ")

_STATE_RE = re.compile(r"^(open|in_progress|delivered|closed|wontfix|superseded)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ATTEMPT_RE = re.compile(r"^attempt (\d+)$")
_REFUSED_RE = re.compile(r"^refused (\d+)$")
_COMMIT_RE = re.compile(r"^commit: ([0-9a-f]{40})$")
_INTEGRATED_RE = re.compile(r"^integrated: ([0-9a-f]{40})$")
_BY_RE = re.compile(r"^by: ([A-Z]+-\d+)$")
_REASON_RE = re.compile(r"^reason: (.+)$")
_PARKED_RE = re.compile(r"^parked: (.+)$")

_PROBE_VERB_RE = re.compile(r"^(test|grep|none):?(.*)$")
_BASELINE_RE = re.compile(r"^baseline: (.+)$")
_FINAL_RE = re.compile(r"^final: (.+)$")
_HASHES_RE = re.compile(r"^spec#([0-9a-f]{8})(?: file#([0-9a-f]{8}))?$")
_SKIPPED_RE = re.compile(r"^skipped (\d+) unreadable$")
_GREP_BASELINE_FILES_RE = re.compile(r"^(.*) \((.*)\)$")

# in_progress/delivered/closed/open can only be reached by way of a start, so a missing
# attempt segment there is corruption, not a never-started entry; wontfix/superseded are the
# only states `decide` can reach directly from a never-started `open`.
_STATUS_ATTEMPT_REQUIRED = frozenset({"open", "in_progress", "delivered", "closed"})


def _valid_lifecycle_date(value: str) -> bool:
    """Whether `value` is a real calendar date shaped `YYYY-MM-DD`.

    `_DATE_RE` alone only checks digit shape and accepts a nonexistent date like `2026-02-30`;
    checking it here — inside `parse_status`/`parse_verify` themselves — is what rejects that
    date at every lifecycle state, not just the two states `_status_age_findings` happens to
    age-check.
    """
    if not _DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _safe_int(digits: str) -> int | None:
    """Convert a regex-captured decimal digit string to `int`, or `None` if it is too long to
    convert — CPython caps integer string conversion length, and `parse_status`/`parse_probe`
    are contracted to be total, so an oversized numeric segment must fail like any other
    malformed one, not raise.
    """
    try:
        return int(digits)
    except ValueError:
        return None


def _free_text_violation(value: str) -> str | None:
    """Return why `value` is unsafe as a lifecycle field's one free-text segment, or `None` if
    it's safe.

    Rejects a newline, a carriage return, or the field delimiter itself — any of these would
    make the delimiter-split grammar ambiguous when the field is parsed back. Also rejects
    anything `mask_quoted` blanks — an HTML comment or a fenced code span — reusing that same
    masking rather than hand-listing the triggering characters: `parse_entries` runs every field
    value through it before a `--probe`/`--reason` value is ever read back, so a value the mask
    changes would round-trip as something other than what was written (e.g. `grep:<!-- x -->`
    is stored as `grep:` padded with spaces).
    """
    if _FREE_TEXT_BAD_RE.search(value) is not None:
        return "a newline, carriage return, or ' — '"
    if mask_quoted(value) != value:
        return "an HTML comment or fenced code span (blanked when the ledger is parsed back)"
    return None


def is_valid_free_text(value: str) -> bool:
    """Return whether `value` is safe as a lifecycle field's one free-text segment.

    Shared by `start`/`park`/`decide` to validate `--probe`/`--reason`/`--parked` before
    writing anything.
    """
    return _free_text_violation(value) is None


@dataclass(frozen=True)
class StatusField:
    state: str
    date: str
    attempt: int = 0
    refused: int = 0
    commit: str | None = None
    integrated: str | None = None
    by: str | None = None
    reason: str | None = None
    parked: str | None = None


@dataclass(frozen=True)
class ProbeField:
    verb: str
    arg: str
    baseline: str | None = None
    baseline_files: list[str] = field(default_factory=list)
    final: str | None = None
    spec_hash: str | None = None
    file_hash: str | None = None
    final_spec_hash: str | None = None
    final_file_hash: str | None = None
    skipped_files: int = 0
    final_skipped_files: int = 0


@dataclass(frozen=True)
class MalformedField:
    raw: str
    reason: str


def render_status(status: StatusField) -> str:
    """Render a `StatusField` to its `Status` field value (the text after `- **Status**: `).

    `parse_status` is its exact inverse for any `StatusField` a real transition produces.
    """
    segments = [status.state, status.date]
    if status.attempt > 0:
        segments.append(f"attempt {status.attempt}")
    if status.refused > 0:
        segments.append(f"refused {status.refused}")
    if status.state == "delivered":
        segments.append(f"commit: {status.commit}")
    elif status.state == "closed":
        segments.append(f"integrated: {status.integrated}")
        # only `reconcile --close` supplies a reason; automatic promotion never does, so this
        # stays absent for the ordinary case the schema table shows
        if status.reason is not None:
            segments.append(f"reason: {status.reason}")
    elif status.state == "superseded":
        segments.append(f"by: {status.by}")
        segments.append(f"reason: {status.reason}")
    elif status.state == "wontfix":
        segments.append(f"reason: {status.reason}")
    elif status.state == "open" and status.parked is not None:
        segments.append(f"parked: {status.parked}")
    return DELIM.join(segments)


def parse_status(line: str) -> StatusField | MalformedField:
    """Parse a `Status` field's value into a `StatusField`, total over all input.

    Matches segments left to right against their anchored patterns; a segment that fails to
    match — including one missing where the state requires it — yields `MalformedField` naming
    that segment, never a partially filled `StatusField` and never a coercion to `open`: an
    unparseable line is unknown state, and a transition command must refuse to write over it.
    """
    parts = line.split(DELIM)

    if not parts or not _STATE_RE.match(parts[0]):
        return MalformedField(raw=line, reason="state")
    state = parts[0]
    i = 1

    if i >= len(parts) or not _valid_lifecycle_date(parts[i]):
        return MalformedField(raw=line, reason="date")
    date = parts[i]
    i += 1

    attempt = 0
    m = _ATTEMPT_RE.match(parts[i]) if i < len(parts) else None
    if m is not None:
        attempt = _safe_int(m.group(1))
        if attempt is None:
            return MalformedField(raw=line, reason="attempt")
        i += 1
    elif state in _STATUS_ATTEMPT_REQUIRED:
        return MalformedField(raw=line, reason="attempt")

    refused = 0
    m = _REFUSED_RE.match(parts[i]) if i < len(parts) else None
    if m is not None:
        refused = _safe_int(m.group(1))
        if refused is None:
            return MalformedField(raw=line, reason="refused")
        i += 1

    commit = integrated = by = reason = parked = None

    if state == "delivered":
        m = _COMMIT_RE.match(parts[i]) if i < len(parts) else None
        if m is None:
            return MalformedField(raw=line, reason="commit")
        commit = m.group(1)
        i += 1
    elif state == "closed":
        m = _INTEGRATED_RE.match(parts[i]) if i < len(parts) else None
        if m is None:
            return MalformedField(raw=line, reason="integrated")
        integrated = m.group(1)
        i += 1
        if i < len(parts):
            m = _REASON_RE.match(DELIM.join(parts[i:]))
            if m is None:
                return MalformedField(raw=line, reason="reason")
            reason = m.group(1)
            i = len(parts)
    elif state == "superseded":
        m = _BY_RE.match(parts[i]) if i < len(parts) else None
        if m is None:
            return MalformedField(raw=line, reason="by")
        by = m.group(1)
        i += 1
        if i >= len(parts):
            return MalformedField(raw=line, reason="reason")
        m = _REASON_RE.match(DELIM.join(parts[i:]))
        if m is None:
            return MalformedField(raw=line, reason="reason")
        reason = m.group(1)
        i = len(parts)
    elif state == "wontfix":
        if i >= len(parts):
            return MalformedField(raw=line, reason="reason")
        m = _REASON_RE.match(DELIM.join(parts[i:]))
        if m is None:
            return MalformedField(raw=line, reason="reason")
        reason = m.group(1)
        i = len(parts)
    elif state == "open" and i < len(parts):
        m = _PARKED_RE.match(DELIM.join(parts[i:]))
        if m is None:
            return MalformedField(raw=line, reason="parked")
        parked = m.group(1)
        i = len(parts)

    if i != len(parts):
        return MalformedField(raw=line, reason="trailing segment")

    return StatusField(
        state=state, date=date, attempt=attempt, refused=refused,
        commit=commit, integrated=integrated, by=by, reason=reason, parked=parked,
    )


def _render_probe_hashes(spec_hash: str | None, file_hash: str | None) -> str:
    if file_hash is not None:
        return f"spec#{spec_hash} file#{file_hash}"
    return f"spec#{spec_hash}"


def render_probe(probe: ProbeField) -> str:
    """Render a `ProbeField` to its `Probe` field value (the text after `- **Probe**: `).

    `parse_probe` is its exact inverse. Baseline and final each carry their own hash pair —
    `spec_hash`/`file_hash` for the baseline occurrence, `final_spec_hash`/`final_file_hash` for
    the `final:` occurrence — so a hand-edit of the `Probe:` line between `start` and `finish`
    changes only the pair that actually changed, instead of forcing both occurrences to agree by
    construction.
    """
    if probe.verb == "none":
        return "none"

    segments = [f"{probe.verb}:{probe.arg}" if probe.arg else probe.verb]

    if probe.verb == "grep" and probe.baseline_files:
        baseline_text = f"{probe.baseline} ({', '.join(probe.baseline_files)})"
    else:
        baseline_text = probe.baseline
    segments.append(f"baseline: {baseline_text}")

    if probe.verb == "grep" and probe.skipped_files > 0:
        segments.append(f"skipped {probe.skipped_files} unreadable")

    segments.append(_render_probe_hashes(probe.spec_hash, probe.file_hash))

    if probe.final is not None:
        segments.append(f"final: {probe.final}")
        if probe.verb == "grep" and probe.final_skipped_files > 0:
            segments.append(f"skipped {probe.final_skipped_files} unreadable")
        segments.append(_render_probe_hashes(probe.final_spec_hash, probe.final_file_hash))

    return DELIM.join(segments)


def parse_probe(line: str) -> ProbeField | MalformedField:
    """Parse a `Probe` field's value into a `ProbeField`, total over all input.

    Matches segments left to right against their anchored patterns, exactly as `parse_status`
    does; a segment that fails to match yields `MalformedField` naming that segment, never a
    partial `ProbeField`.
    """
    parts = line.split(DELIM)

    m = _PROBE_VERB_RE.match(parts[0]) if parts else None
    if m is None:
        return MalformedField(raw=line, reason="verb")
    verb, arg = m.group(1), m.group(2)
    i = 1

    if verb == "none":
        if i != len(parts):
            return MalformedField(raw=line, reason="trailing segment")
        return ProbeField(verb=verb, arg=arg)

    m = _BASELINE_RE.match(parts[i]) if i < len(parts) else None
    if m is None:
        return MalformedField(raw=line, reason="baseline")
    baseline_raw = m.group(1)
    i += 1

    baseline = baseline_raw
    baseline_files: list[str] = []
    if verb == "grep":
        fm = _GREP_BASELINE_FILES_RE.match(baseline_raw)
        if fm is not None:
            baseline = fm.group(1)
            baseline_files = fm.group(2).split(", ") if fm.group(2) else []

    skipped_files = 0
    m = _SKIPPED_RE.match(parts[i]) if verb == "grep" and i < len(parts) else None
    if m is not None:
        skipped_files = _safe_int(m.group(1))
        if skipped_files is None:
            return MalformedField(raw=line, reason="skipped")
        i += 1

    m = _HASHES_RE.match(parts[i]) if i < len(parts) else None
    if m is None:
        return MalformedField(raw=line, reason="hashes")
    spec_hash, file_hash = m.group(1), m.group(2)
    if verb == "grep" and file_hash is not None:
        return MalformedField(raw=line, reason="hashes")
    i += 1

    final = None
    final_spec_hash = final_file_hash = None
    final_skipped_files = 0
    if i < len(parts):
        m = _FINAL_RE.match(parts[i])
        if m is None:
            return MalformedField(raw=line, reason="final")
        final = m.group(1)
        i += 1

        m = _SKIPPED_RE.match(parts[i]) if verb == "grep" and i < len(parts) else None
        if m is not None:
            final_skipped_files = _safe_int(m.group(1))
            if final_skipped_files is None:
                return MalformedField(raw=line, reason="skipped")
            i += 1

        m = _HASHES_RE.match(parts[i]) if i < len(parts) else None
        if m is None:
            return MalformedField(raw=line, reason="hashes")
        final_spec_hash, final_file_hash = m.group(1), m.group(2)
        if verb == "grep" and final_file_hash is not None:
            return MalformedField(raw=line, reason="hashes")
        i += 1

    if i != len(parts):
        return MalformedField(raw=line, reason="trailing segment")

    return ProbeField(
        verb=verb, arg=arg, baseline=baseline, baseline_files=baseline_files,
        final=final, spec_hash=spec_hash, file_hash=file_hash,
        final_spec_hash=final_spec_hash, final_file_hash=final_file_hash,
        skipped_files=skipped_files, final_skipped_files=final_skipped_files,
    )


@dataclass(frozen=True)
class VerifyField:
    date: str
    integration_ref: str
    probe: str  # "pass" | "fail" | "missing" | "error"


_VERIFY_INTEGRATION_REF_RE = re.compile(r"^integration_ref: (\S+)$")
_VERIFY_PROBE_RE = re.compile(r"^probe: (pass|fail|missing|error)$")


def render_verify(verify: VerifyField) -> str:
    """Render a `VerifyField` to its `Verify` field value (the text after `- **Verify**: `).

    `parse_verify` is its exact inverse.
    """
    return DELIM.join([
        verify.date, f"integration_ref: {verify.integration_ref}", f"probe: {verify.probe}",
    ])


def parse_verify(line: str) -> VerifyField | MalformedField:
    """Parse a `Verify` field's value into a `VerifyField`, total over all input.

    Matches segments left to right against their anchored patterns, exactly as `parse_status`/
    `parse_probe` do; a segment that fails to match yields `MalformedField` naming that segment.
    """
    parts = line.split(DELIM)

    if not parts or not _valid_lifecycle_date(parts[0]):
        return MalformedField(raw=line, reason="date")
    date = parts[0]

    if len(parts) < 2:
        return MalformedField(raw=line, reason="integration_ref")
    m = _VERIFY_INTEGRATION_REF_RE.match(parts[1])
    if m is None:
        return MalformedField(raw=line, reason="integration_ref")
    integration_ref = m.group(1)

    if len(parts) < 3:
        return MalformedField(raw=line, reason="probe")
    m = _VERIFY_PROBE_RE.match(parts[2])
    if m is None:
        return MalformedField(raw=line, reason="probe")
    probe = m.group(1)

    if len(parts) != 3:
        return MalformedField(raw=line, reason="trailing segment")

    return VerifyField(date=date, integration_ref=integration_ref, probe=probe)


# --- doctor: lifecycle findings ------------------------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §Doctor findings catalog, §The reconcile
# algorithm. `doctor` never touches git or runs a probe (tech.md:1489-1491), so every finding
# here is derived from the entry's own fields on disk — which is why `AWAITING_INTEGRATION` and
# `UNDETERMINED` are an age-based guess standing in for the ancestry check only `reconcile` can
# make.

_LIFECYCLE_FIELD_LABELS = ("Status", "Probe", "Verify")


def _positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _stall_days() -> int:
    return _positive_int_env("QUIRK_PM_STALL_DAYS", DEFAULT_STALL_DAYS)


def _undetermined_after_days() -> int:
    return _positive_int_env("QUIRK_PM_UNDETERMINED_AFTER_DAYS", DEFAULT_UNDETERMINED_AFTER_DAYS)


def _days_since(today: str, date: str) -> int | None:
    """Whole days from `date` to `today`, or `None` if either fails to parse as a real calendar
    date — `_DATE_RE` only checks digit shape, not that e.g. day 30 exists in February.
    """
    try:
        t = datetime.date.fromisoformat(today)
        d = datetime.date.fromisoformat(date)
    except ValueError:
        return None
    return (t - d).days


def _malformed_lifecycle_finding(key: str, label: str, reason: str) -> tuple[str, str]:
    return ("MALFORMED_LIFECYCLE_FIELD", f"{key}: {label} field does not parse ({reason})")


def _entry_probe(entry: Entry) -> ProbeField | MalformedField | None:
    raw = entry.fields.get("Probe")
    if raw is None:
        # mirrors `_entry_status`: a value-less field line never reaches `entry.fields`, so it's
        # indistinguishable here from the field never having been written at all
        if field_present_but_empty(entry, "Probe"):
            return MalformedField(raw="", reason="empty")
        return None
    return parse_probe(raw)


def _entry_verify(entry: Entry) -> VerifyField | MalformedField | None:
    raw = entry.fields.get("Verify")
    if raw is None:
        if field_present_but_empty(entry, "Verify"):
            return MalformedField(raw="", reason="empty")
        return None
    return parse_verify(raw)


def _duplicate_lifecycle_field_labels(masked_text: str, entry: Entry) -> list[str]:
    """Labels among `Status`/`Probe`/`Verify` with more than one live field line in `entry`.

    `masked_text` is the file's full text already run through `artifact_lib.mask_quoted`, so a
    label quoted inside a fenced example is never mistaken for a live duplicate — and so a caller
    checking every entry in the file can mask once and pass the same text into every call here,
    rather than each call re-masking the whole file.
    """
    return duplicate_field_labels(masked_text, entry, _LIFECYCLE_FIELD_LABELS)


def _status_age_findings(key: str, status: StatusField, today: str) -> list[tuple[str, str]]:
    if status.state not in ("in_progress", "delivered"):
        return []
    age = _days_since(today, status.date)
    if age is None:
        return [_malformed_lifecycle_finding(key, "Status", "date")]
    if status.state == "in_progress":
        if age > _stall_days():
            return [("STALLED", f"{key}: in_progress since {status.date} ({age}d ago)")]
        return []
    if age >= _undetermined_after_days():
        return [(
            "UNDETERMINED",
            f"{key}: not reachable after {age} days — rebase/squash or not yet merged; "
            "a human must resolve",
        )]
    return [("AWAITING_INTEGRATION", f"{key}: {age} days")]


def _lifecycle_doctor_findings(fp: FileParse, today: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    masked_text = mask_quoted(fp.text)
    for entry in fp.entries:
        key = f"{fp.spec.header}-{entry.id}"

        for label in _duplicate_lifecycle_field_labels(masked_text, entry):
            findings.append(("DUPLICATE_LIFECYCLE_FIELD", f"{key}: more than one {label} field line"))

        status = _entry_status(entry)
        if isinstance(status, MalformedField):
            findings.append(_malformed_lifecycle_finding(key, "Status", status.reason))
            status = None
        else:
            findings.extend(_status_age_findings(key, status, today))

        probe = _entry_probe(entry)
        if isinstance(probe, MalformedField):
            findings.append(_malformed_lifecycle_finding(key, "Probe", probe.reason))
            probe = None

        verify = _entry_verify(entry)
        if isinstance(verify, MalformedField):
            findings.append(_malformed_lifecycle_finding(key, "Verify", verify.reason))
            verify = None

        delivered_or_closed = status is not None and status.state in ("delivered", "closed")
        if delivered_or_closed and probe is not None and probe.verb == "none":
            findings.append(("UNVERIFIED_DELIVERY", f"{key}: delivered via probe none"))

        if probe is not None and probe.final is not None:
            if probe.final_spec_hash != probe.spec_hash:
                findings.append(("PROBE_SPEC_CHANGED", f"{key}: spec hash changed between start and finish"))
            if probe.final_file_hash != probe.file_hash:
                findings.append(("PROBE_FILE_CHANGED", f"{key}: file hash changed between start and finish"))

        if verify is not None and verify.probe != "pass":
            findings.append((
                "POST_MERGE_PROBE_REGRESSION",
                f"{key}: verify probe outcome is {verify.probe!r}, not pass",
            ))

    return findings


# --- Blocked by: lexical rules -------------------------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §`Blocked by` lexical rules;
# docs/quirk/specs/2026-08-04-pm-agent/logic.md, §Job 1 — roadmap and what's next.

# [0-9], not \d: \d admits non-ASCII decimal digits that int() would fold onto the same
# ASCII-spelled id; 0|[1-9][0-9]* also excludes leading zeros, so BUG-007 and BUG-7 stay two
# spellings rather than being silently normalized to one.
_BLOCKED_BY_ID_RE = re.compile(r"^(BUG|DEFER|TEST)-(0|[1-9][0-9]*)$")
_BLOCKED_BY_ANY_HEADER_RE = re.compile(r"^([A-Z]+)-(0|[1-9][0-9]*)$")

_SATISFIED_STATES = frozenset({"closed", "wontfix", "superseded"})


@dataclass(frozen=True)
class BlockedByToken:
    raw: str
    kind: str  # "id" | "proposal" | "malformed"
    id: str | None = None


@dataclass(frozen=True)
class BlockedByField:
    tokens: tuple[BlockedByToken, ...]
    truncated: bool
    duplicate_ids: tuple[str, ...]
    empty: bool = False


def parse_blocked_by(value: str) -> BlockedByField:
    """Parse a `Blocked by` field's value into its tokens, total over all input.

    A value whose last non-space character is a comma means `FIELD_RE`'s line-anchored match
    silently dropped a wrapped continuation line — `truncated` records that so the caller can
    fail closed on it, since the dropped text could have named anything.
    """
    stripped = value.strip()
    if not stripped:
        return BlockedByField(tokens=(), truncated=False, duplicate_ids=())

    truncated = stripped.endswith(",")
    body = stripped[:-1].strip() if truncated else stripped

    tokens: list[BlockedByToken] = []
    seen: set[str] = set()
    dup_ids: list[str] = []
    if body:
        for raw in re.split(r"\s*,\s*", body):
            m = _BLOCKED_BY_ID_RE.fullmatch(raw)
            if m is not None:
                entry_id = f"{m.group(1)}-{m.group(2)}"
                if entry_id in seen and entry_id not in dup_ids:
                    dup_ids.append(entry_id)
                seen.add(entry_id)
                tokens.append(BlockedByToken(raw=raw, kind="id", id=entry_id))
                continue
            header_m = _BLOCKED_BY_ANY_HEADER_RE.fullmatch(raw)
            if header_m is not None and header_m.group(1) == "PROPOSAL":
                tokens.append(BlockedByToken(raw=raw, kind="proposal"))
                continue
            tokens.append(BlockedByToken(raw=raw, kind="malformed"))

    return BlockedByField(tokens=tuple(tokens), truncated=truncated, duplicate_ids=tuple(dup_ids))


# --- readiness -------------------------------------------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/logic.md, §Job 1 — roadmap and what's next.


@dataclass(frozen=True)
class LedgerWorld:
    """Every well-formed BUG/DEFER/TEST entry in the project, keyed `"HEADER-N"`.

    Built fresh on every call — nothing here is cached across invocations, matching the design's
    "every finding is computed fresh from the files on disk" observability contract.
    """
    entries: dict[str, tuple[Entry, ArtifactSpec]]
    parse_errors: list[str]
    malformed_total: int
    ambiguous_ids: frozenset[str]
    skipped_headers: frozenset[str]


def _load_ledger_world(project: Path) -> LedgerWorld:
    entries: dict[str, tuple[Entry, ArtifactSpec]] = {}
    ambiguous_ids: set[str] = set()
    parse_errors: list[str] = []
    malformed_total = 0
    skipped_headers: set[str] = set()
    for spec in BACKLOG_FILES:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                parse_errors.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            skipped_headers.add(spec.header)
            continue
        malformed_total += len(fp.malformed)
        for e in fp.entries:
            key = f"{spec.header}-{e.id}"
            if key in entries:
                ambiguous_ids.add(key)
            entries[key] = (e, spec)
    return LedgerWorld(
        entries=entries, parse_errors=parse_errors, malformed_total=malformed_total,
        ambiguous_ids=frozenset(ambiguous_ids), skipped_headers=frozenset(skipped_headers),
    )


def _read_roadmap(project: Path) -> RoadmapParse:
    """Return `project`'s parsed `ROADMAP.md`.

    A missing file is the ordinary starting state, not an error — every entry then sorts at
    milestone rank -1, exactly as if `ROADMAP.md` existed with no milestones in it. A file that
    exists but cannot be read, is oversized, or fails to decode is not that state and must not
    collapse into it silently — instead of falling back to an empty roadmap unremarked, it
    carries a `ROADMAP_UNREADABLE` finding so the corruption is visible to `--doctor`/`--index`.
    """
    path = project / "ROADMAP.md"
    if not path.exists():
        return RoadmapParse(milestones=[], findings=[], preamble="")
    # reuses the ledger files' guarded reader: --index/--next run on every SessionStart, and an
    # unbounded, blocking read here would hang on a FIFO or exhaust memory on an oversized file
    data, skip_reason = _read_file_safely(path, _max_file_bytes())
    if data is None:
        return RoadmapParse(milestones=[], findings=[("ROADMAP_UNREADABLE", skip_reason)], preamble="")
    text = _decode_platform_text(data)
    if text is None:
        return RoadmapParse(
            milestones=[], findings=[("ROADMAP_UNREADABLE", "parse error, skipping")], preamble=""
        )
    return parse_roadmap(text)


def _milestone_ranks(roadmap: RoadmapParse) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for milestone in roadmap.milestones:
        for member_id in milestone.members:
            ranks.setdefault(member_id, milestone.rank)
    return ranks


def _entry_status(entry: Entry) -> StatusField | MalformedField:
    raw = entry.fields.get("Status")
    if raw is None:
        # a value-less `Status` line is corruption (someone deleted the value but not the
        # label), not the ordinary never-started state, so it must not silently default to open
        if field_present_but_empty(entry, "Status"):
            return MalformedField(raw="", reason="empty")
        return StatusField(state="open", date="")
    return parse_status(raw)


def _is_open(entry: Entry) -> bool:
    status = _entry_status(entry)
    return isinstance(status, StatusField) and status.state == "open"


def _blocked_by(entry: Entry) -> BlockedByField:
    raw = entry.fields.get("Blocked by")
    if not raw:
        # a value-less field line never reaches `entry.fields` at all, so it and a field that
        # was simply never written are otherwise indistinguishable here; a hand-edit that
        # truncated the field is far likelier than a deliberate "nothing blocks this", so this
        # fails closed the same direction as a truncated or malformed value, not open
        if field_present_but_empty(entry, "Blocked by"):
            return BlockedByField(tokens=(), truncated=False, duplicate_ids=(), empty=True)
        return BlockedByField(tokens=(), truncated=False, duplicate_ids=())
    return parse_blocked_by(raw)


def satisfied(world: LedgerWorld, key: str) -> bool:
    """Return whether `key` (e.g. `"BUG-3"`) is a satisfied blocker: it resolves to a known
    entry whose status is `closed`, `wontfix`, or `superseded`.

    Only those three terminal states satisfy — `in_progress`/`delivered` do not, so a blocker
    merely being started or reported delivered never unblocks its dependents early. An id claimed
    by more than one live entry (`DUPLICATE_ID`) never satisfies either, regardless of what any
    one of those entries says — resolving the ambiguity to "whichever parsed last" would let a
    still-open duplicate's dependents unblock on a different, closed one's say-so.
    """
    if key in world.ambiguous_ids:
        return False
    target = world.entries.get(key)
    if target is None:
        return False
    entry, _spec = target
    status = _entry_status(entry)
    return isinstance(status, StatusField) and status.state in _SATISFIED_STATES


def ready(world: LedgerWorld, key: str) -> bool:
    """Return whether the entry named `key` is open and every one of its blockers is satisfied.

    Uses only `key`'s direct blockers — a satisfied blocker's own blockers never matter, so this
    stays O(1) per entry with no graph walk. A truncated `Blocked by` value fails closed: the
    dropped continuation could have named anything, so it blocks rather than being read as
    satisfied by what little survived the parse.

    An id claimed by more than one live entry (`DUPLICATE_ID`) is never ready either, the same
    way it never satisfies a dependent in `satisfied()` — resolving the ambiguity to whichever
    heading `_load_ledger_world` happened to keep last would let a still-ambiguous entry be
    reported ready and recommended by `next`.
    """
    if key in world.ambiguous_ids:
        return False
    target = world.entries.get(key)
    if target is None:
        return False
    entry, _spec = target
    if not _is_open(entry):
        return False
    blocked = _blocked_by(entry)
    if blocked.truncated or blocked.empty:
        return False
    for token in blocked.tokens:
        if token.kind != "id" or not satisfied(world, token.id):
            return False
    return True


def eligible(world: LedgerWorld, ranks: dict[str, int], key: str) -> bool:
    entry, spec = world.entries[key]
    if not ready(world, key):
        return False
    return key in ranks or _urgency(spec, entry.fields) <= 1


def _entry_sort_key(key: str) -> tuple[str, int]:
    header, _, num = key.partition("-")
    return (header, int(num))


def _unplaced_counts(world: LedgerWorld, ranks: dict[str, int]) -> tuple[int, int, int]:
    """Return (ready, blocked, malformed) among open entries in no milestone.

    Restricting the count to ready entries would leave blocked, unroadmapped, medium-urgency
    work counted nowhere; malformed headings are counted regardless of milestone membership,
    since a malformed heading has no readable ID to check membership against.
    """
    ready_count = blocked_count = 0
    for key, (entry, _spec) in world.entries.items():
        if key in ranks:
            continue
        if not _is_open(entry):
            continue
        if ready(world, key):
            ready_count += 1
        else:
            blocked_count += 1
    return ready_count, blocked_count, world.malformed_total


def _blocking_culprits(world: LedgerWorld) -> list[tuple[str, int]]:
    """Return `(blocker_id, how_many_open_entries_it_blocks)`, most-blocking first.

    Used to explain an empty ready-set: only named, resolvable IDs are counted — an id-shaped
    token that names no known entry is `DANGLING`, not a blocker a human can act on — and each
    blocked entry counts once per blocker regardless of how many times that blocker's id is
    repeated in its own `Blocked by` field (`BLOCKED_BY_DUPLICATE` already reports that repeat).
    """
    counts: dict[str, int] = {}
    for _key, (entry, _spec) in world.entries.items():
        if not _is_open(entry):
            continue
        blocked = _blocked_by(entry)
        if blocked.truncated:
            continue
        culprits = {
            token.id for token in blocked.tokens
            if token.kind == "id" and token.id in world.entries and not satisfied(world, token.id)
        }
        for blocker_id in culprits:
            counts[blocker_id] = counts.get(blocker_id, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


# --- doctor: cross-ledger findings ------------------------------------------


def _blocked_by_doctor_findings(world: LedgerWorld) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for key in sorted(world.entries, key=_entry_sort_key):
        entry, _spec = world.entries[key]
        blocked = _blocked_by(entry)
        if blocked.truncated:
            findings.append((
                "BLOCKED_BY_TRUNCATED",
                f"{key}: Blocked by value ends with a trailing comma — a wrapped continuation "
                "may have been dropped",
            ))
        if blocked.empty:
            findings.append(("DANGLING", f"{key}: Blocked by field is present but empty"))
        for token in blocked.tokens:
            if token.kind == "malformed":
                findings.append(("DANGLING", f"{key}: malformed token {token.raw!r}"))
            elif token.kind == "proposal":
                findings.append(("BLOCKED_BY_PROPOSAL", f"{key}: references {token.raw}"))
            elif token.id not in world.entries:
                # a ledger `doctor` skipped (oversize, parse error) is could-not-look, not
                # looked-and-found-nothing — a reference into that ledger's id space must not
                # assert the id doesn't exist when the truth is the file was never read
                header, _, _num = token.id.partition("-")
                if header not in world.skipped_headers:
                    findings.append(("DANGLING", f"{key}: references unknown {token.id}"))
        for dup_id in blocked.duplicate_ids:
            findings.append(("BLOCKED_BY_DUPLICATE", f"{key}: {dup_id} listed more than once"))
    return findings


def _blocked_by_edges(world: LedgerWorld) -> dict[str, list[str]]:
    return {
        key: [t.id for t in _blocked_by(entry).tokens if t.kind == "id"]
        for key, (entry, _spec) in world.entries.items()
    }


def _find_cycles(edges: dict[str, list[str]]) -> list[tuple[str, ...]]:
    """Return cycles in `edges` sufficient to name every node that participates in at least one,
    each reported once regardless of which member it is discovered from (deduped by rotation).

    Iterative DFS with an explicit frame stack and a recursion-stack color set — never recursive
    — so a large or adversarially deep graph terminates in bounded, linear time instead of
    risking a stack overflow or an accidentally-quadratic reimplementation.

    A single DFS pass retires (colors 2) a node once every edge leaving it has been explored, and
    never revisits it — the standard shape for detecting *that* a graph has a cycle, but not for
    naming every node that sits on one: two cycles sharing a node can have the pass finish that
    node while walking the first, so the edge into it from the second is seen already-retired and
    silently dropped, leaving the second cycle's other members in no reported path at all. A node
    restarted as its own fresh root stays on the stack for the whole of its own traversal, so
    retrying from any node the first pass left uncovered is guaranteed to surface a cycle through
    it if one exists; `covered` tracks that and the restarts stop once it can't grow.
    """
    found: list[tuple[str, ...]] = []
    seen_rotations: set[tuple[str, ...]] = set()
    covered: set[str] = set()

    def normalize(cycle: list[str]) -> tuple[str, ...]:
        start = min(range(len(cycle)), key=lambda i: cycle[i])
        return tuple(cycle[start:] + cycle[:start])

    def run(roots: Iterable[str]) -> None:
        color: dict[str, int] = {}  # 0 unvisited (default), 1 on stack, 2 done
        for root in roots:
            if color.get(root, 0) != 0:
                continue
            path = [root]
            color[root] = 1
            # node -> its index in `path` while on the stack, so a back edge locates the cycle's
            # start in O(1) instead of a path.index() scan that is O(path length) per back edge
            pos_in_path: dict[str, int] = {root: 0}
            frames = [(root, 0)]
            while frames:
                node, idx = frames[-1]
                neighbors = edges.get(node, [])
                if idx < len(neighbors):
                    frames[-1] = (node, idx + 1)
                    nxt = neighbors[idx]
                    state = color.get(nxt, 0)
                    if state == 1:
                        cyc = normalize(path[pos_in_path[nxt]:])
                        covered.update(cyc)
                        if cyc not in seen_rotations:
                            seen_rotations.add(cyc)
                            found.append(cyc)
                    elif state == 0:
                        color[nxt] = 1
                        path.append(nxt)
                        pos_in_path[nxt] = len(path) - 1
                        frames.append((nxt, 0))
                else:
                    color[node] = 2
                    path.pop()
                    del pos_in_path[node]
                    frames.pop()

    run(sorted(edges))
    for node in sorted(set(edges) - covered):
        if node not in covered:
            run([node])
    return found


def _cycle_doctor_findings(world: LedgerWorld) -> list[tuple[str, str]]:
    cycles = _find_cycles(_blocked_by_edges(world))
    return [("CYCLE", " -> ".join((*cyc, cyc[0]))) for cyc in cycles]


def _roadmap_doctor_findings(
    project: Path, known_ids: set[str], skipped_headers: frozenset[str]
) -> list[tuple[str, str]]:
    roadmap = _read_roadmap(project)
    findings = list(roadmap.findings)
    findings.extend(_preamble_member_findings(roadmap.preamble))
    referenced = {member_id for milestone in roadmap.milestones for member_id in milestone.members}
    for member_id in sorted(referenced - known_ids):
        # a ledger `doctor` skipped (oversize, parse error) is could-not-look, not
        # looked-and-found-nothing — a reference into that ledger's id space must not assert
        # the id doesn't exist when the truth is the file was never read, the same reasoning
        # `_blocked_by_doctor_findings` applies to `Blocked by`
        header, _, _num = member_id.partition("-")
        if header not in skipped_headers:
            findings.append(("DANGLING_ROADMAP_REF", member_id))
    return findings


def _cross_ledger_doctor_findings(project: Path) -> list[tuple[str, str]]:
    world = _load_ledger_world(project)
    findings = _blocked_by_doctor_findings(world)
    findings.extend(_cycle_doctor_findings(world))
    findings.extend(_roadmap_doctor_findings(project, set(world.entries), world.skipped_headers))
    return findings


# --- roadmap ---------------------------------------------------------------


def render_roadmap_show(project: Path) -> str:
    if not _any_artifact_file_exists(project):
        return NOT_INITIALIZED_MESSAGE

    roadmap = _read_roadmap(project)
    world = _load_ledger_world(project)
    ranks = _milestone_ranks(roadmap)

    lines: list[str] = []
    if roadmap.milestones:
        for milestone in roadmap.milestones:
            lines.append(f"[quirk:pm] Milestone: {milestone.name}")
            for member_id in milestone.members:
                lines.append(f"  - {member_id}")
    else:
        lines.append("[quirk:pm] no milestones")

    ready_keys = sorted((key for key in world.entries if ready(world, key)), key=_entry_sort_key)
    if ready_keys:
        lines.append(f"[quirk:pm] {len(ready_keys)} ready: {', '.join(ready_keys)}")
    else:
        lines.append("[quirk:pm] 0 ready")

    ready_count, blocked_count, malformed_count = _unplaced_counts(world, ranks)
    unplaced_total = ready_count + blocked_count + malformed_count
    lines.append(
        f"[quirk:pm] {unplaced_total} unplaced "
        f"({ready_count} ready, {blocked_count} blocked, {malformed_count} malformed)"
    )
    return "\n".join(lines) + "\n"


# --- The probe execution contract ----------------------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The probe execution contract.
# Runs a `--probe VERB:ARG` spec and reports what happened; never prints, never exits, never
# raises on an ordinary probe outcome. `start`/`finish` (a later task) call this engine rather
# than reaching into it.


@dataclass(frozen=True)
class ProbeSpec:
    """A parsed `--probe VERB:ARG` argument, ready for `run_probe`.

    `arg` is the exact text after `verb:` — `f"{verb}:{arg}"` (or just `"none"`) reconstructs
    the original value byte-for-byte, which is what `ProbeField.arg` stores and what gets hashed
    for `spec#`.
    """
    verb: str
    arg: str
    nodeid: str | None = None
    pattern: str | None = None
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbeArgError:
    """`parse_probe_spec` could not make sense of a `--probe` value."""
    detail: str


@dataclass(frozen=True)
class ProbeResult:
    """What running a `ProbeSpec` observed.

    `outcome` is `pass`/`fail`/`missing`/`error` for `test:`, `ok`/`error` for `grep:`, and
    `none` for `none`. `test:` additionally reaches `config_error` when `QUIRK_PM_TEST_RUNNER`
    is set to something other than the default without a matching `QUIRK_PM_TEST_EXIT_MAP` —
    distinct from `error` because it is a refusal to guess, not an observed probe outcome.
    """
    outcome: str
    count: int | None = None
    files: tuple[str, ...] = ()
    skipped_files: int = 0
    detail: str | None = None


def parse_probe_spec(value: str) -> ProbeSpec | ProbeArgError:
    """Parse a `--probe VERB:ARG` command-line value into a `ProbeSpec`, total over its input.

    `grep:`'s argument splits on the first standalone ` -- ` token only: everything before is
    the pattern, verbatim; everything after is `shlex.split()` into `paths`. No ` -- ` means the
    whole remainder is the pattern and `paths` stays empty (`run_probe` defaults that to the
    worktree root).
    """
    if value == "none":
        return ProbeSpec(verb="none", arg="")

    if value.startswith("test:"):
        nodeid = value[len("test:"):]
        if not nodeid:
            return ProbeArgError("test: probe requires a nodeid")
        return ProbeSpec(verb="test", arg=nodeid, nodeid=nodeid)

    if value.startswith("grep:"):
        rest = value[len("grep:"):]
        pattern, sep, paths_text = rest.partition(" -- ")
        if not pattern:
            return ProbeArgError("grep: probe requires a pattern")
        paths: tuple[str, ...] = ()
        if sep:
            try:
                paths = tuple(shlex.split(paths_text))
            except ValueError as exc:
                return ProbeArgError(f"grep: probe paths are not valid shell syntax: {exc}")
        return ProbeSpec(verb="grep", arg=rest, pattern=pattern, paths=paths)

    return ProbeArgError(f"unrecognized probe verb in {value!r} (expected test:, grep:, or none)")


def _probe_timeout() -> float:
    """The `QUIRK_PM_PROBE_TIMEOUT` bound (seconds) in effect, defaulting to 120.

    A value that isn't a finite positive number (`inf`, `nan`, zero, negative) falls back to the
    default with a message on stderr rather than being honored: `subprocess` raises rather than
    bounding anything given an infinite timeout, so accepting one would silently strip the bound
    every later probe execution depends on.
    """
    raw = os.environ.get("QUIRK_PM_PROBE_TIMEOUT")
    if raw is None:
        return DEFAULT_PROBE_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT
    if math.isfinite(value) and value > 0:
        return value
    print(
        f"[quirk:pm] QUIRK_PM_PROBE_TIMEOUT={raw!r} is not a finite positive number, "
        f"using the default ({DEFAULT_PROBE_TIMEOUT}s)",
        file=sys.stderr,
    )
    return DEFAULT_PROBE_TIMEOUT


def _parse_test_exit_map(raw: str) -> dict[int, str] | None:
    """Parse `QUIRK_PM_TEST_EXIT_MAP`'s `code:outcome` list; `None` if any entry is malformed or
    names an outcome outside `_PROBE_OUTCOMES` — everything downstream (`Verify`'s mapping,
    `UNVERIFIED_DELIVERY`, `probe_accepts_final`) assumes that exact four-token vocabulary.
    """
    mapping: dict[int, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        code_text, sep, outcome = item.partition(":")
        if not sep or not outcome:
            return None
        try:
            code = int(code_text)
        except ValueError:
            return None
        if outcome not in _PROBE_OUTCOMES:
            return None
        mapping[code] = outcome
    return mapping if mapping else None


def _test_exit_map() -> tuple[dict[int, str] | None, str | None]:
    """The pytest-exit-code -> outcome mapping in effect, or `(None, reason)` if none applies.

    `QUIRK_PM_TEST_EXIT_MAP`, when set, always governs. Otherwise the default (pytest's own
    codes) applies only while `QUIRK_PM_TEST_RUNNER` is still the default — reusing pytest's
    codes for an arbitrary configured runner would silently misread whatever that runner's exit
    statuses actually mean.
    """
    raw = os.environ.get("QUIRK_PM_TEST_EXIT_MAP")
    if raw is not None:
        parsed = _parse_test_exit_map(raw)
        if parsed is None:
            return None, f"QUIRK_PM_TEST_EXIT_MAP is malformed: {raw!r}"
        return parsed, None

    runner = os.environ.get("QUIRK_PM_TEST_RUNNER", DEFAULT_TEST_RUNNER)
    if runner != DEFAULT_TEST_RUNNER:
        return None, "QUIRK_PM_TEST_RUNNER is set without QUIRK_PM_TEST_EXIT_MAP"
    return DEFAULT_TEST_EXIT_MAP, None


def _kill_probe_group(proc: subprocess.Popen) -> None:
    """Best-effort SIGKILL to `proc`'s own process group — a group that's already gone (the
    process exited normally, or an earlier call already killed it) is not an error.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_test_probe(spec: ProbeSpec, root: Path, timeout: float) -> ProbeResult:
    exit_map, error = _test_exit_map()
    if exit_map is None:
        return ProbeResult(outcome="config_error", detail=error)

    runner = os.environ.get("QUIRK_PM_TEST_RUNNER", DEFAULT_TEST_RUNNER)
    try:
        command = [*shlex.split(runner), spec.nodeid]
    except ValueError as exc:
        return ProbeResult(
            outcome="config_error", detail=f"QUIRK_PM_TEST_RUNNER is malformed: {exc}"
        )

    try:
        # start_new_session: the runner becomes its own process group leader (pgid == its pid),
        # separate from pm.py's — so a timeout can signal that whole group without touching the
        # group pm.py itself runs in. stdout/stderr are never read (only the exit code is), so
        # DEVNULL discards them at the OS level rather than having communicate() accumulate an
        # unbounded amount of a noisy runner's output in memory.
        proc = subprocess.Popen(
            command, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return ProbeResult(outcome="error", detail=f"could not run test runner: {exc}")

    try:
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # a runner that spawns its own children (a server, a worker pool, ...) leaves them in
            # the same group by default, so the group — not just the runner's own pid — is what
            # must be signaled for the timeout to actually bound the work
            _kill_probe_group(proc)
            try:
                proc.communicate(timeout=PROBE_KILL_DRAIN_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.wait()
            return ProbeResult(outcome="error", detail=f"probe exceeded {timeout}s timeout")
    finally:
        # however the probe was abandoned — timeout (already handled above), KeyboardInterrupt,
        # or any other exception — the runner's isolated group must not outlive this call
        _kill_probe_group(proc)

    outcome = exit_map.get(proc.returncode, "error")
    detail = None if outcome != "error" else f"unmapped exit code {proc.returncode}"
    return ProbeResult(outcome=outcome, detail=detail)


def _display_grep_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _grep_walk_targets(base: Path, allowed_roots: list[Path]) -> Iterator[Path]:
    if base.is_file():
        yield base
        return
    # followlinks=False: a symlinked directory is left unvisited rather than recursed into,
    # which is what keeps a self-referential symlink from walking forever
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            file_path = Path(dirpath) / name
            if file_path.is_symlink():
                real = Path(os.path.realpath(file_path))
                if not any(real.is_relative_to(allowed) for allowed in allowed_roots):
                    continue
            yield file_path


def _run_grep_probe(spec: ProbeSpec, root: Path, timeout: float) -> ProbeResult:
    try:
        regex = re.compile(spec.pattern)
    except (re.error, RecursionError, OverflowError) as exc:
        return ProbeResult(outcome="error", detail=str(exc))

    if spec.paths:
        bases: list[Path] = []
        for raw in spec.paths:
            candidate = Path(raw)
            candidate = candidate if candidate.is_absolute() else root / candidate
            if not candidate.exists():
                return ProbeResult(outcome="error", detail=f"path not found: {raw}")
            is_dir = candidate.is_dir()
            # checked before the open below: a FIFO passes `exists()` but blocks on open until a
            # writer appears, which would stall before `started` is even set — `is_file`, not
            # `exists`, for the same reason `grep_baseline_files_missing` uses it
            if not is_dir and not candidate.is_file():
                return ProbeResult(outcome="error", detail=f"not a file or directory: {raw}")
            try:
                if is_dir:
                    with os.scandir(candidate):
                        pass
                else:
                    with open(candidate, "rb"):
                        pass
            except OSError:
                # validation (exists/is_dir/is_file above) and this open are separate stat calls,
                # so a path that disappears (or a directory replaced by something scandir can't
                # read) in between must resolve here rather than raise past run_probe's contract
                return ProbeResult(outcome="error", detail=f"path not readable: {raw}")
            bases.append(candidate.resolve())
    else:
        bases = [root.resolve()]

    started = time.monotonic()
    count = 0
    skipped = 0
    matched_files: set[str] = set()

    for base in bases:
        for file_path in _grep_walk_targets(base, bases):
            # per file, not per line: bounds the check's own cost while still guaranteeing
            # termination on a tree too large to finish scanning inside the timeout
            if time.monotonic() - started > timeout:
                return ProbeResult(
                    outcome="error", detail="scan exceeded timeout", skipped_files=skipped,
                )
            data, _skip_reason = _read_file_safely(file_path, MAX_USABLE_FILE_BYTES)
            if data is None:
                skipped += 1
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue

            file_hit = False
            for line in text.splitlines():
                if regex.search(line):
                    count += 1
                    file_hit = True
            if file_hit:
                matched_files.add(_display_grep_path(root, file_path))

    return ProbeResult(
        outcome="ok", count=count, files=tuple(sorted(matched_files)), skipped_files=skipped,
    )


def run_probe(spec: ProbeSpec, root: Path, *, timeout: float | None = None) -> ProbeResult:
    """Execute `spec` against worktree `root` and report what happened.

    Never raises on an ordinary probe outcome or a misconfigured runner — a failed probe is
    data. `none` is never actually executed: this returns its fixed result without touching the
    filesystem or spawning anything.
    """
    if timeout is None:
        timeout = _probe_timeout()

    if spec.verb == "none":
        return ProbeResult(outcome="none")
    if spec.verb == "test":
        return _run_test_probe(spec, root, timeout)
    if spec.verb == "grep":
        return _run_grep_probe(spec, root, timeout)
    raise ValueError(f"unknown probe verb {spec.verb!r}")


def probe_accepts_baseline(spec: ProbeSpec, result: ProbeResult) -> bool:
    """Whether `result` is a `start`-acceptable baseline for `spec`.

    `none` has no baseline to judge, so it always accepts. `grep:` needs at least one match —
    `baseline_count == 0` means the pattern doesn't discriminate this entry.
    """
    if spec.verb == "none":
        return True
    if spec.verb == "test":
        # only a genuinely failing test is evidence; missing/error/timeout would make a typo'd
        # nodeid or broken config indistinguishable from a real red baseline
        return result.outcome == "fail"
    if spec.verb == "grep":
        return result.outcome == "ok" and (result.count or 0) > 0
    raise ValueError(f"unknown probe verb {spec.verb!r}")


def probe_accepts_final(spec: ProbeSpec, result: ProbeResult) -> bool:
    """Whether `result` is a `finish`-acceptable outcome for `spec`.

    For `grep:` this covers only the count half of the rule — see `grep_baseline_files_missing`
    for the "did the baseline's files survive" half, which `finish` must check first.
    """
    if spec.verb == "none":
        return True
    if spec.verb == "test":
        return result.outcome == "pass"
    if spec.verb == "grep":
        return result.outcome == "ok" and result.count == 0
    raise ValueError(f"unknown probe verb {spec.verb!r}")


def grep_baseline_files_missing(root: Path, baseline_files: Iterable[str]) -> list[str]:
    """Baseline files (as recorded by `start`, relative to `root`) that no longer exist.

    `finish` must refuse if this is non-empty regardless of the new scan's count: deleting the
    code that carried the symptom is not a fix, and replacing it with a directory of the same
    name is the same deletion wearing a hat — `is_file` catches both, `exists` only the first.
    """
    return [name for name in baseline_files if not (root / name).is_file()]


def _reconstruct_probe_spec(probe: ProbeField) -> ProbeSpec | ProbeArgError:
    """Reconstruct the `ProbeSpec` `run_probe` needs from a parsed `ProbeField` — re-parses the
    same `verb:arg` text a recorded `Probe:` line encodes, the way `--probe` originally was.
    Shared by `finish` (re-running the recorded probe against `HEAD`) and `reconcile --verify`
    (re-running it against the integration ref).
    """
    verb_arg = "none" if probe.verb == "none" else f"{probe.verb}:{probe.arg}"
    return parse_probe_spec(verb_arg)


# --- lifecycle commands: start, finish, park, decide ----------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The CAS transition mechanism, §Exit codes
# (per-command precedence). Phase 2 is --here only (logic.md:778-785): no `Handoff` field, no
# worktree, no dispatch — `start`'s sequence is baseline probe -> write ledger, and `finish`
# compares the worktree root against the project's own repo.


def _not_implemented(name: str) -> int:
    print(f"pm.py {name}: not implemented yet", file=sys.stderr)
    return EXIT_BAD_ARGUMENT


@dataclass(frozen=True)
class _Refusal:
    code: int
    message: str


def _refuse(code: int, message: str) -> _Refusal:
    return _Refusal(code, message)


@dataclass(frozen=True)
class _Prepared:
    spec: ArtifactSpec
    entry_id: int
    entry: Entry
    status: StatusField


_ENTRY_ID_ARG_RE = re.compile(r"^([A-Z]+)-(0|[1-9][0-9]*)$")


def _today() -> str:
    return datetime.date.today().isoformat()


def _resolve_ledger(project: Path, id_str: str) -> tuple[ArtifactSpec, int, Path] | _Refusal:
    m = _ENTRY_ID_ARG_RE.match(id_str)
    spec = None
    if m is not None:
        spec = next((s for s in ALL_SPECS if s.header == m.group(1)), None)
    if m is None or spec is None:
        return _refuse(EXIT_NOT_FOUND, f"{id_str}: no such entry")
    path = project / spec.filename
    if not path.exists():
        return _refuse(EXIT_NOT_FOUND, f"{spec.filename} not found in {project}")
    return spec, int(m.group(2)), path


def _prepare_transition(
    project: Path,
    id_str: str,
    *,
    validate_args: Callable[[], _Refusal | None],
    allowed_states: frozenset[str],
    sibling_fields: tuple[str, ...] = (),
) -> _Prepared | _Refusal:
    """Run every check that precedes the CAS write, in the exit-code table's precedence order:
    not-found (3) -> bad argument (2) -> schema mismatch (8) -> corrupt entry (4) -> CAS (6).

    `validate_args` supplies the command-specific "2" checks (probe syntax, `--reason`, `--by`,
    `--repo`) — they run after the not-found check and before the schema/corrupt checks, per
    tech.md's per-command precedence table, so a not-found ID always outranks a bad argument.

    The corrupt-entry (4) step is itself several checks in sequence: heading ambiguity (duplicate
    ID, missing title), which applies to any file, then a PROPOSAL guard (6) ahead of the `Status`
    parse — proposals.md has its own `Status` vocabulary, so parsing it as a PM lifecycle field
    would report a false "malformed" finding instead of the true "not part of the lifecycle" one —
    then, when `sibling_fields` is non-empty, `_sibling_field_refusal`'s malformed/duplicated
    check over those fields. All of it precedes the state comparison (6): `park`/`decide`/
    `reconcile --close` are about to declare the entry terminal, and `finish` is about to read and
    execute its `Probe`, so a corrupt entry must be reported as corrupt even when its state also
    happens to mismatch — a fixture where only one condition holds can't tell that precedence
    apart from an unrelated exit code. `start` leaves `sibling_fields` empty: it always supplies a
    fresh `Probe`, so refusing on an old corrupt one would strand an entry nothing could repair.
    """
    resolved = _resolve_ledger(project, id_str)
    if isinstance(resolved, _Refusal):
        return resolved
    spec, entry_id, path = resolved

    with path.open(encoding="utf-8", newline="") as f:
        text = f.read()
    parse = parse_entries(text, spec.header)
    matches = [e for e in parse.entries if e.id == entry_id]
    malformed = [m for m in parse.malformed if m.id == entry_id]
    if not matches and not malformed:
        return _refuse(EXIT_NOT_FOUND, f"{spec.header}-{entry_id}: not found in {spec.filename}")

    arg_error = validate_args()
    if arg_error is not None:
        return arg_error

    if detect_schema_version(text) != 2:
        return _refuse(
            EXIT_SCHEMA_MISMATCH, f"{spec.filename} is not on schema v2. Run /quirk:pm:migrate first."
        )

    if len(matches) + len(malformed) > 1:
        return _refuse(EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: duplicate ID in {spec.filename}")
    if malformed:
        return _refuse(EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: malformed heading, no title")
    entry = matches[0]

    # ahead of the Status parse below: proposals.md's own `Status` vocabulary (proposed/accepted/
    # rejected/superseded) is legitimately unparseable as a PM lifecycle Status, and reporting
    # that as a malformed field would tell the user something false about their file
    if spec.header == "PROPOSAL":
        return _refuse(
            EXIT_CAS_FAILURE, f"{spec.header}-{entry_id}: PROPOSAL entries are not part of the PM lifecycle"
        )

    status = _entry_status(entry)
    if isinstance(status, MalformedField):
        return _refuse(
            EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: malformed Status field ({status.reason})"
        )
    try:
        splice_field(text, entry, "Status", render_status(status))
    except DuplicateFieldError:
        return _refuse(EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: duplicated field line, refusing")

    prepared = _Prepared(spec=spec, entry_id=entry_id, entry=entry, status=status)

    if sibling_fields:
        sibling_refusal = _sibling_field_refusal(prepared, mask_quoted(text), sibling_fields)
        if sibling_refusal is not None:
            return sibling_refusal

    if status.state not in allowed_states:
        return _refuse(
            EXIT_CAS_FAILURE,
            f"{spec.header}-{entry_id}: expected state in {sorted(allowed_states)}, found {status.state!r}",
        )

    return prepared


def _expectation(prepared: _Prepared) -> tuple[int, int, str, str | None]:
    return (
        prepared.entry_id, prepared.status.attempt, prepared.status.state,
        prepared.entry.fields.get("Probe"),
    )


def _sibling_field_refusal(
    prepared: _Prepared, masked_text: str, labels: tuple[str, ...]
) -> _Refusal | None:
    """Refuse (`EXIT_CORRUPT_ENTRY`) if any of `prepared.entry`'s fields named in `labels` —
    `Probe` and/or `Verify` — is malformed or duplicated.

    `park`/`decide`/`reconcile --close`/batch `reconcile` transition `Status` without ever
    reading `Verify` themselves (and without reading `Probe` either, apart from `finish`), but
    leaving a corrupt sibling field in place on an entry they're about to declare terminal — with
    no diagnostic at the moment its fate is decided — is the same corruption a malformed `Status`
    already refuses on in `_prepare_transition`. Duplication is the same class of corruption as
    malformed, just invisible to it: `artifact_lib`'s parse dict-collapses a repeated label, so a
    second `Probe`/`Verify` line parses cleanly as whichever one wins the collapse and would
    otherwise be left in place by a transition that doesn't rewrite that field. `start` is exempt
    from both: it always supplies a fresh `Probe`, so refusing on an old corrupt one would strand
    an entry nothing could repair. `finish` checks only `Probe`, since it neither reads nor writes
    `Verify`.
    """
    for label in duplicate_field_labels(masked_text, prepared.entry, labels):
        return _refuse(
            EXIT_CORRUPT_ENTRY,
            f"{prepared.spec.header}-{prepared.entry_id}: duplicated {label} field line, refusing",
        )
    if "Probe" in labels:
        probe = _entry_probe(prepared.entry)
        if isinstance(probe, MalformedField):
            return _refuse(
                EXIT_CORRUPT_ENTRY, f"{prepared.spec.header}-{prepared.entry_id}: malformed Probe field ({probe.reason})"
            )
    if "Verify" in labels:
        verify = _entry_verify(prepared.entry)
        if isinstance(verify, MalformedField):
            return _refuse(
                EXIT_CORRUPT_ENTRY,
                f"{prepared.spec.header}-{prepared.entry_id}: malformed Verify field ({verify.reason})",
            )
    return None


def _commit_transition(
    project: Path,
    spec: ArtifactSpec,
    entry_id: int,
    expected: tuple[int, int, str, str | None],
    new_status: StatusField,
    new_probe: ProbeField | None,
    *,
    extra: Callable[[Entry, StatusField], str | None] | None = None,
    new_verify: VerifyField | None = None,
    sibling_fields: tuple[str, ...] = (),
) -> _Refusal | None:
    """Re-read, re-locate, and compare `expected` under the held lock; splice and write on match.

    The compare and the write happen inside this one lock acquisition — splitting them into a
    read-then-later-write would reopen exactly the race the CAS procedure exists to close.

    `extra` overrides the tuple's fourth element (default: the raw `Probe` field, matching every
    lifecycle command's compare); `reconcile`'s write-back passes the recorded commit sha
    instead, since a hand-edit that only changes `commit:` at the same attempt/state is exactly
    the staleness a Probe-only compare would miss. `new_verify`, when given, splices a `Verify`
    field alongside `Status`/`Probe` under the same lock — reconcile's `--verify` write.

    Re-checks the schema version on the text read under the lock, the same guard
    `_prepare_transition` applies before the lock is even taken: that earlier check is a
    preflight, not a substitute for this one — a ledger `migrate` upgrades in the window between
    the two must not be written by a transition that validated a different version of the file.
    `sibling_fields`, when non-empty, re-runs `_sibling_field_refusal` over those fields against
    this same locked re-read for the identical reason: `park`/`decide`/`reconcile --close`/batch
    `reconcile` only ever splice `Status` (plus, for batch `reconcile --verify`, `Verify`), so
    nothing else here would ever notice a `Probe`/`Verify` a concurrent hand-edit corrupted
    between the preflight and this write — the CAS compare above only covers whichever field
    `expected`'s fourth element happens to track.
    """
    path = project / spec.filename
    lock_dir = ensure_lock_dir(project)
    timeout = _lock_timeout()
    deadline = time.monotonic() + timeout
    lock_file = _acquire_ledger_lock(lock_dir / f"{spec.filename}.lock", deadline)
    if lock_file is None:
        return _refuse(EXIT_LOCK_TIMEOUT, f"could not acquire lock on {spec.filename}, nothing written")
    try:
        with path.open(encoding="utf-8", newline="") as f:
            text = f.read()
        if detect_schema_version(text) != 2:
            return _refuse(
                EXIT_SCHEMA_MISMATCH, f"{spec.filename} is not on schema v2. Run /quirk:pm:migrate first."
            )
        parse = parse_entries(text, spec.header)
        matches = [e for e in parse.entries if e.id == entry_id]
        malformed = [m for m in parse.malformed if m.id == entry_id]
        if len(matches) != 1 or malformed:
            return _refuse(EXIT_CAS_FAILURE, f"{spec.header}-{entry_id}: entry changed, refusing")
        entry = matches[0]
        status = _entry_status(entry)
        if isinstance(status, MalformedField):
            return _refuse(
                EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: malformed Status field ({status.reason})"
            )
        if sibling_fields:
            sibling_refusal = _sibling_field_refusal(
                _Prepared(spec=spec, entry_id=entry_id, entry=entry, status=status),
                mask_quoted(text), sibling_fields,
            )
            if sibling_refusal is not None:
                return sibling_refusal
        # attempt, not just state, closes the stale-transition race: a status-only compare
        # can't tell this in_progress from a different, later attempt at the same state
        extra_value = entry.fields.get("Probe") if extra is None else extra(entry, status)
        current = (entry.id, status.attempt, status.state, extra_value)
        if current != expected:
            return _refuse(EXIT_CAS_FAILURE, f"{spec.header}-{entry_id}: CAS mismatch, refusing")

        try:
            new_text = splice_field(text, entry, "Status", render_status(new_status))
            if new_probe is not None:
                reparsed = parse_entries(new_text, spec.header)
                entry2 = next(e for e in reparsed.entries if e.id == entry_id)
                new_text = splice_field(new_text, entry2, "Probe", render_probe(new_probe))
            if new_verify is not None:
                reparsed = parse_entries(new_text, spec.header)
                entry3 = next(e for e in reparsed.entries if e.id == entry_id)
                new_text = splice_field(new_text, entry3, "Verify", render_verify(new_verify))
        except DuplicateFieldError:
            return _refuse(EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: duplicated field line, refusing")

        atomic_write(path, new_text)
        return None
    finally:
        lock_file.close()


# --- git plumbing for `finish`'s preconditions -----------------------------


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_show_toplevel(cwd: Path) -> str | None:
    proc = _run_git(["rev-parse", "--show-toplevel"], cwd)
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _git_dirty_paths(cwd: Path) -> list[str] | None:
    proc = _run_git(["status", "--porcelain"], cwd)
    if proc is None or proc.returncode != 0:
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _git_head_sha(cwd: Path) -> str | None:
    proc = _run_git(["rev-parse", "HEAD"], cwd)
    if proc is None or proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None


# --- git plumbing for `reconcile` -------------------------------------------
#
# docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The reconcile algorithm.


def _repo_missing(repo: Path) -> bool:
    return not repo.exists() or not repo.is_dir()


def _resolve_integration_ref(repo: Path) -> str | None:
    """The ref `reconcile` measures ancestry against for `repo` this run (logic.md:205-207), or
    `None` when no such ref can be resolved.

    `QUIRK_PM_INTEGRATION_REF` always wins when set. Otherwise the repo's default branch via
    `refs/remotes/origin/HEAD`; repos made by `git init` plus `git remote add` carry no such
    symref, so this falls back to the currently checked-out branch — but only a real one.
    `git rev-parse --abbrev-ref HEAD` returns the literal string `"HEAD"` on a detached checkout
    and would look like a resolved branch name to a caller that only checks whether the result
    verifies as a commit, since "HEAD" always does; `symbolic-ref` instead fails outright when
    `HEAD` is detached, which is what lets this report `None` instead of a false ref name a wrong
    close could be measured against.
    """
    override = os.environ.get("QUIRK_PM_INTEGRATION_REF")
    if override:
        return override
    proc = _run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo)
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    proc = _run_git(["symbolic-ref", "-q", "--short", "HEAD"], repo)
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return None


_DETACHED_HEAD_DETAIL = (
    "cannot resolve integration ref: detached HEAD, no origin/HEAD, and "
    "QUIRK_PM_INTEGRATION_REF is not set"
)


def _stderr_excerpt(proc: subprocess.CompletedProcess) -> str:
    first_line = (proc.stderr or "").strip().splitlines()
    return first_line[0] if first_line else f"exit {proc.returncode}"


@dataclass(frozen=True)
class _RepoState:
    """Per-repo git facts computed at most once per `reconcile` run — the fetch/integration-ref
    memoization tech.md requires ("fetch once per repo, not once per entry").
    """
    fetch_ok: bool
    integration_ref: str | None
    integration_ref_ok: bool


def _repo_state(repo: Path, cache: dict[Path, _RepoState]) -> _RepoState:
    cached = cache.get(repo)
    if cached is not None:
        return cached
    fetch_proc = _run_git(["fetch"], repo)
    fetch_ok = fetch_proc is not None and fetch_proc.returncode == 0
    integration_ref = _resolve_integration_ref(repo)
    integration_ref_ok = False
    if fetch_ok and integration_ref is not None:
        verify_proc = _run_git(["rev-parse", "--verify", f"{integration_ref}^{{commit}}"], repo)
        integration_ref_ok = verify_proc is not None and verify_proc.returncode == 0
    state = _RepoState(fetch_ok=fetch_ok, integration_ref=integration_ref, integration_ref_ok=integration_ref_ok)
    cache[repo] = state
    return state


def _target_repo(project: Path, entry: Entry) -> Path:
    """The repository `reconcile` evaluates `entry`'s ancestry in.

    Phase 2: always the project's own repo — `start` is `--here`-only (logic.md:778-785), so no
    `Handoff` field is ever written and there is no `dest:` to read. Phase 3 substitutes a
    `Handoff.dest:` lookup here instead.
    """
    return project


def _evaluate_delivered(repo: Path, sha: str, cache: dict[Path, _RepoState]) -> tuple[str, str | None]:
    """The condition table from tech.md's reconcile algorithm, evaluated for one `delivered`
    entry's recorded `commit:` sha against `repo`. Returns `(outcome, detail)`; `outcome` is one
    of `"promote"` / `"not_yet"` / `"cannot_evaluate"`, never promoting on an ambiguous signal.
    """
    if _repo_missing(repo):
        return "cannot_evaluate", "destination repo missing"
    state = _repo_state(repo, cache)
    if not state.fetch_ok:
        return "cannot_evaluate", "fetch failed"
    cat_proc = _run_git(["cat-file", "-e", f"{sha}^{{commit}}"], repo)
    if cat_proc is None or cat_proc.returncode != 0:
        return "cannot_evaluate", "commit not in destination repo"
    if state.integration_ref is None:
        return "cannot_evaluate", _DETACHED_HEAD_DETAIL
    if not state.integration_ref_ok:
        return "cannot_evaluate", f"integration ref unresolvable: {state.integration_ref}"
    anc_proc = _run_git(["merge-base", "--is-ancestor", sha, state.integration_ref], repo)
    if anc_proc is None:
        return "cannot_evaluate", "git error: could not run git"
    if anc_proc.returncode == 0:
        return "promote", None
    if anc_proc.returncode == 1:
        return "not_yet", None
    return "cannot_evaluate", f"git error: {_stderr_excerpt(anc_proc)}"


def _verify_probe_outcome(spec: ProbeSpec, result: ProbeResult, baseline_files_missing: bool = False) -> str:
    """Map a probe re-run's `ProbeResult` onto the pass/fail/missing/error vocabulary `Verify`
    shares with `Probe`'s `final:` (tech.md's `Verify` schema) — `grep:`'s own outcome vocabulary
    (`ok`/`error` plus a count) has no `missing` case, but `Verify` needs one uniform scale
    regardless of which verb the entry recorded.

    `baseline_files_missing` mirrors `finish`'s `grep_baseline_files_missing` check: a zero-match
    re-run is not evidence of a fix if the files the baseline matched are gone rather than fixed,
    so that case is reported as `fail`, the same as a re-run that still matches.
    """
    if spec.verb == "none":
        return "pass"
    if spec.verb == "test":
        return result.outcome if result.outcome in _PROBE_OUTCOMES else "error"
    if spec.verb == "grep":
        if result.outcome == "error":
            return "error"
        if baseline_files_missing:
            return "fail"
        return "pass" if (result.count or 0) == 0 else "fail"
    raise ValueError(f"unknown probe verb {spec.verb!r}")


def _rebase_verify_paths(spec: ProbeSpec, repo: Path, tmpdir: Path) -> ProbeSpec | None:
    """Rewrite `spec`'s absolute path(s) — `grep:`'s `paths`, `test:`'s nodeid file part — from
    `repo` onto `tmpdir`.

    `run_probe` keeps an absolute path as-is rather than resolving it under `root`, so without
    this a probe recorded with an absolute target would silently re-scan the original checkout
    instead of the detached `--verify` worktree it's supposed to measure — true of a `test:`
    nodeid's file part exactly as it is of a `grep:` path. `None` when a path lies outside `repo`
    entirely — there is nothing under `tmpdir` for it to correspond to, and the caller reports
    `error` rather than guessing.
    """
    repo_resolved = repo.resolve()

    def rebase_one(raw: str) -> str | None:
        candidate = Path(raw)
        if not candidate.is_absolute():
            return raw
        try:
            rel = candidate.resolve().relative_to(repo_resolved)
        except ValueError:
            return None
        return str(tmpdir / rel)

    if spec.verb == "grep" and spec.paths:
        rebased: list[str] = []
        for raw in spec.paths:
            new_raw = rebase_one(raw)
            if new_raw is None:
                return None
            rebased.append(new_raw)
        return replace(spec, paths=tuple(rebased))

    if spec.verb == "test" and spec.nodeid:
        file_part, sep, rest = spec.nodeid.partition("::")
        new_file_part = rebase_one(file_part)
        if new_file_part is None:
            return None
        new_nodeid = f"{new_file_part}{sep}{rest}"
        return replace(spec, nodeid=new_nodeid, arg=new_nodeid)

    return spec


def _worktree_still_registered(repo: Path, tmpdir: Path) -> bool:
    proc = _run_git(["worktree", "list", "--porcelain"], repo)
    if proc is None or proc.returncode != 0:
        return True  # can't confirm cleanup succeeded, so don't report it clean
    target = tmpdir.resolve()
    for line in proc.stdout.splitlines():
        if line.startswith("worktree ") and Path(line[len("worktree "):]).resolve() == target:
            return True
    return False


def _cleanup_verify_worktree(repo: Path, tmpdir: Path) -> None:
    """Best-effort removal of a temporary `--verify` worktree.

    A failed `worktree remove` gets one bounded follow-up (`worktree prune`, run after the
    directory is gone so git can actually recognize the worktree as stale) rather than a retry
    loop. Any remainder — directory or git's own registration — is only ever reported on stderr;
    it never un-promotes the entry or changes reconcile's exit code (tech.md: "a failing re-run
    does not un-promote the entry" applies equally to cleanup, which isn't part of the outcome).
    """
    remove_proc = _run_git(["worktree", "remove", str(tmpdir), "--force"], repo)
    removed = remove_proc is not None and remove_proc.returncode == 0
    shutil.rmtree(tmpdir, ignore_errors=True)
    if removed:
        return
    # the bounded follow-up: one prune attempt, only on the failure path, never a retry loop
    _run_git(["worktree", "prune"], repo)
    if tmpdir.exists() or _worktree_still_registered(repo, tmpdir):
        print(
            f"[quirk:pm] could not fully clean up temporary verify worktree {tmpdir} "
            "— run `git worktree prune` manually",
            file=sys.stderr,
        )


def _run_verify(
    repo: Path, integration_ref: str, probe_spec: ProbeSpec, probe_field: ProbeField,
) -> VerifyField:
    """Re-run `probe_spec` in a detached worktree at `integration_ref`, reporting the outcome as
    a `VerifyField`. The worktree is always removed, even when `worktree add` itself fails or
    the probe re-run raises — a failing or erroring re-run never blocks the promotion this
    accompanies, only its own field (tech.md: "a failing re-run does not un-promote the entry").
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="quirk-pm-verify-"))
    outcome = "error"
    try:
        add_proc = _run_git(["worktree", "add", "--detach", str(tmpdir), integration_ref], repo)
        if add_proc is not None and add_proc.returncode == 0:
            rebased_spec = _rebase_verify_paths(probe_spec, repo, tmpdir)
            if rebased_spec is not None:
                try:
                    result = run_probe(rebased_spec, tmpdir)
                    baseline_files_missing = rebased_spec.verb == "grep" and bool(
                        grep_baseline_files_missing(tmpdir, probe_field.baseline_files)
                    )
                    outcome = _verify_probe_outcome(rebased_spec, result, baseline_files_missing)
                except Exception:
                    outcome = "error"
    finally:
        _cleanup_verify_worktree(repo, tmpdir)
    return VerifyField(date=_today(), integration_ref=integration_ref, probe=outcome)


# --- Probe field construction for start/finish -----------------------------


def _grep_summary(count: int, nfiles: int | None = None) -> str:
    word = "match" if count == 1 else "matches"
    if nfiles is None:
        return f"{count} {word}"
    file_word = "file" if nfiles == 1 else "files"
    return f"{count} {word} in {nfiles} {file_word}"


def _probe_field_from_baseline(spec: ProbeSpec, result: ProbeResult, root: Path) -> ProbeField:
    if spec.verb == "none":
        return ProbeField(verb="none", arg="")
    raw = f"{spec.verb}:{spec.arg}"
    spec_hash = hash_probe_spec(raw)
    file_hash = None
    baseline_files: list[str] = []
    skipped_files = 0
    if spec.verb == "test":
        baseline = result.outcome
        file_hash = hash_file(root / spec.nodeid.split("::", 1)[0])
    else:
        baseline = _grep_summary(result.count or 0, len(result.files))
        baseline_files = list(result.files)
        skipped_files = result.skipped_files
    return ProbeField(
        verb=spec.verb, arg=spec.arg, baseline=baseline, baseline_files=baseline_files,
        spec_hash=spec_hash, file_hash=file_hash, skipped_files=skipped_files,
    )


def _probe_field_with_final(current: ProbeField, spec: ProbeSpec, result: ProbeResult, root: Path) -> ProbeField:
    if spec.verb == "none":
        return current
    raw = f"{spec.verb}:{spec.arg}"
    final_spec_hash = hash_probe_spec(raw)
    final_file_hash = None
    final_skipped_files = 0
    if spec.verb == "test":
        final = result.outcome
        final_file_hash = hash_file(root / spec.nodeid.split("::", 1)[0])
    else:
        final = _grep_summary(result.count or 0)
        final_skipped_files = result.skipped_files
    return replace(
        current, final=final, final_spec_hash=final_spec_hash, final_file_hash=final_file_hash,
        final_skipped_files=final_skipped_files,
    )


def _grep_baseline_files_unsafe(files: Iterable[str]) -> list[str]:
    """Matched filenames that would not round-trip through the `Probe` field's `baseline (f1,
    f2, ...)` grammar.

    `render_probe` joins them on `", "` inside a `(...)` group appended to `baseline`, and
    `_GREP_BASELINE_FILES_RE` recovers that group by scanning the rendered segment for its
    outermost `" ("` / `")"` — not by position, so any of those literal sequences appearing
    inside a name, not just between names, can move the boundary it finds. `", "` or `DELIM`
    inside a name corrupts the join/split the same way; an embedded newline breaks the field's
    single-line grammar outright.
    """
    return [
        name for name in files
        if "\r" in name or "\n" in name or ", " in name or DELIM in name
        or "(" in name or ")" in name
    ]


def _config_error_refusal(prepared: _Prepared, result: ProbeResult) -> _Refusal | None:
    if result.outcome != "config_error":
        return None
    # a misconfigured runner is a refusal to guess, not an observed outcome — must not be
    # collapsed into an ordinary probe refusal
    return _refuse(EXIT_BAD_ARGUMENT, f"{prepared.spec.header}-{prepared.entry_id}: {result.detail}")


def cmd_start(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    probe_spec_box: list[ProbeSpec] = []

    def validate_args() -> _Refusal | None:
        if args.probe is None:
            return _refuse(EXIT_BAD_ARGUMENT, "--probe is required")
        if args.repo is not None:
            return _refuse(
                EXIT_BAD_ARGUMENT, "dispatch is not available yet (Phase 2 is --here only); drop --repo"
            )
        violation = _free_text_violation(args.probe)
        if violation is not None:
            return _refuse(EXIT_BAD_ARGUMENT, f"--probe contains {violation}")
        parsed = parse_probe_spec(args.probe)
        if isinstance(parsed, ProbeArgError):
            return _refuse(EXIT_BAD_ARGUMENT, parsed.detail)
        probe_spec_box.append(parsed)
        return None

    prepared = _prepare_transition(
        project, args.id, validate_args=validate_args, allowed_states=frozenset({"open"}),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    probe_spec = probe_spec_box[0]
    expected = _expectation(prepared)

    baseline = run_probe(probe_spec, project)
    config_refusal = _config_error_refusal(prepared, baseline)
    if config_refusal is not None:
        print(f"[quirk:pm] {config_refusal.message}", file=sys.stderr)
        return config_refusal.code
    if not probe_accepts_baseline(probe_spec, baseline):
        detail_suffix = f" ({baseline.detail})" if baseline.detail else ""
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: baseline probe outcome "
            f"{baseline.outcome!r} does not discriminate this entry{detail_suffix}",
            file=sys.stderr,
        )
        return EXIT_PROBE_REFUSED

    if probe_spec.verb == "grep":
        unsafe = _grep_baseline_files_unsafe(baseline.files)
        if unsafe:
            print(
                f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: matched filename "
                f"{unsafe[0]!r} cannot be recorded in the Probe field (contains ', ', ' — ', "
                "'(', ')', or a newline)",
                file=sys.stderr,
            )
            return EXIT_BAD_ARGUMENT

    new_status = StatusField(
        state="in_progress", date=_today(),
        attempt=prepared.status.attempt + 1, refused=prepared.status.refused,
    )
    new_probe = _probe_field_from_baseline(probe_spec, baseline, project)

    refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, new_probe)
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: started (attempt {new_status.attempt})")
    return EXIT_OK


def cmd_finish(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    prepared = _prepare_transition(
        project, args.id, validate_args=lambda: None, allowed_states=frozenset({"in_progress"}),
        sibling_fields=("Probe",),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    probe_raw = prepared.entry.fields.get("Probe")
    if probe_raw is None:
        # in_progress is only reached by way of start, which always writes a Probe field — an
        # absent one is corruption, never the deliberate `--probe none` choice
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: in_progress entry has no Probe field",
            file=sys.stderr,
        )
        return EXIT_CORRUPT_ENTRY
    current_probe = parse_probe(probe_raw)
    if isinstance(current_probe, MalformedField):
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: malformed Probe field "
            f"({current_probe.reason})",
            file=sys.stderr,
        )
        return EXIT_CORRUPT_ENTRY
    probe_spec = _reconstruct_probe_spec(current_probe)
    if isinstance(probe_spec, ProbeArgError):
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: recorded Probe is unusable "
            f"({probe_spec.detail})",
            file=sys.stderr,
        )
        return EXIT_CORRUPT_ENTRY

    # preconditions checked before the probe: it's the expensive step, and a dirty tree
    # invalidates it anyway
    toplevel = _git_show_toplevel(project)
    # --show-toplevel, not --git-common-dir: the common dir is identical across every worktree
    # of a repository, so it identifies only the repo, never this specific checkout
    if toplevel is None or Path(toplevel).resolve() != project:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: worktree root does not "
            "match the project directory",
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED

    dirty = _git_dirty_paths(project)
    if dirty is None:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: could not read working tree status",
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED
    if dirty:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: working tree is dirty: " + ", ".join(dirty),
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED

    # captured before the probe runs, so the delivered path below can require it hasn't moved —
    # a probe that writes tracked files must not let a stale sha describe what was measured
    head_before = _git_head_sha(project)
    if head_before is None:
        print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: could not resolve HEAD", file=sys.stderr)
        return EXIT_FINISH_PRECONDITION_FAILED

    result = run_probe(probe_spec, project)
    config_refusal = _config_error_refusal(prepared, result)
    if config_refusal is not None:
        print(f"[quirk:pm] {config_refusal.message}", file=sys.stderr)
        return config_refusal.code

    # re-checked after the probe, before either outcome below is committed: a probe that writes
    # tracked files leaves the tree dirty (or HEAD moved) at the moment of delivery, and a
    # refusal is recorded evidence just as much as a delivered commit is — both must describe
    # what was actually measured, not a tree the probe has since changed out from under it
    dirty_after = _git_dirty_paths(project)
    if dirty_after is None:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: could not read working tree status",
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED
    if dirty_after:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: probe left the working tree "
            "dirty: " + ", ".join(dirty_after),
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED

    commit_sha = _git_head_sha(project)
    if commit_sha is None:
        print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: could not resolve HEAD", file=sys.stderr)
        return EXIT_FINISH_PRECONDITION_FAILED
    if commit_sha != head_before:
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: HEAD moved during the probe "
            f"({head_before} -> {commit_sha})",
            file=sys.stderr,
        )
        return EXIT_FINISH_PRECONDITION_FAILED

    missing_files = (
        grep_baseline_files_missing(project, current_probe.baseline_files)
        if probe_spec.verb == "grep" else []
    )
    accepted = probe_accepts_final(probe_spec, result) and not missing_files

    if not accepted:
        new_status = StatusField(
            state="in_progress", date=_today(),
            attempt=prepared.status.attempt, refused=prepared.status.refused + 1,
        )
        # a refused finish still writes the outcome it observed — the Probe line must never be
        # left untouched just because the transition itself didn't go through
        new_probe = _probe_field_with_final(current_probe, probe_spec, result, project)
        refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, new_probe)
        if refusal is not None:
            print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
            return refusal.code
        # named so commands/pm/finish.md can relay which outcome was recorded on exit 9 — the
        # difference between a genuinely failing probe and a broken one (missing/error) — without
        # needing to re-read the ledger for it
        outcome_label = (
            f"missing baseline files: {', '.join(missing_files)}" if missing_files else result.outcome
        )
        detail_suffix = f" ({result.detail})" if result.detail else ""
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: probe refused "
            f"(refused {new_status.refused}) — outcome {outcome_label}{detail_suffix}",
            file=sys.stderr,
        )
        return EXIT_PROBE_REFUSED

    new_status = StatusField(
        state="delivered", date=_today(),
        attempt=prepared.status.attempt, refused=prepared.status.refused, commit=commit_sha,
    )
    new_probe = _probe_field_with_final(current_probe, probe_spec, result, project)

    refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, new_probe)
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: delivered ({commit_sha})")
    return EXIT_OK


def _validate_reason(reason: str | None) -> _Refusal | None:
    """`--reason`'s value for `park`/`decide`: required, non-empty once stripped, and safe as a
    lifecycle field's free-text segment.
    """
    if reason is None:
        return _refuse(EXIT_BAD_ARGUMENT, "--reason is required")
    if not reason.strip():
        return _refuse(EXIT_BAD_ARGUMENT, "--reason must not be empty or whitespace-only")
    violation = _free_text_violation(reason)
    if violation is not None:
        return _refuse(EXIT_BAD_ARGUMENT, f"--reason contains {violation}")
    return None


def cmd_park(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    def validate_args() -> _Refusal | None:
        return _validate_reason(args.reason)

    prepared = _prepare_transition(
        project, args.id, validate_args=validate_args, allowed_states=frozenset({"in_progress"}),
        sibling_fields=("Probe", "Verify"),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    new_status = StatusField(
        state="open", date=_today(),
        attempt=prepared.status.attempt, refused=prepared.status.refused, parked=args.reason,
    )
    refusal = _commit_transition(
        project, prepared.spec, prepared.entry_id, expected, new_status, None,
        sibling_fields=("Probe", "Verify"),
    )
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: parked")
    return EXIT_OK


def cmd_decide(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    def validate_args() -> _Refusal | None:
        if args.as_ is None:
            return _refuse(EXIT_BAD_ARGUMENT, "--as is required")
        reason_error = _validate_reason(args.reason)
        if reason_error is not None:
            return reason_error
        if args.as_ == "superseded":
            if not args.by:
                return _refuse(EXIT_BAD_ARGUMENT, "--as superseded requires --by")
            if not _ENTRY_ID_ARG_RE.match(args.by):
                return _refuse(EXIT_BAD_ARGUMENT, f"--by {args.by!r} is not a valid entry ID")
        return None

    prepared = _prepare_transition(
        project, args.id, validate_args=validate_args,
        allowed_states=frozenset({"open", "in_progress", "delivered"}),
        sibling_fields=("Probe", "Verify"),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    if args.as_ == "wontfix":
        new_status = StatusField(
            state="wontfix", date=_today(),
            attempt=prepared.status.attempt, refused=prepared.status.refused, reason=args.reason,
        )
    else:
        new_status = StatusField(
            state="superseded", date=_today(),
            attempt=prepared.status.attempt, refused=prepared.status.refused,
            by=args.by, reason=args.reason,
        )

    refusal = _commit_transition(
        project, prepared.spec, prepared.entry_id, expected, new_status, None,
        sibling_fields=("Probe", "Verify"),
    )
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: {args.as_}")
    return EXIT_OK


@dataclass(frozen=True)
class _ReconcileEval:
    """One `delivered` entry's outcome from reconcile's lock-free read pass."""
    spec: ArtifactSpec
    entry_id: int
    status: StatusField
    repo: Path
    outcome: str  # "promote" | "not_yet" | "cannot_evaluate"
    detail: str | None = None
    integration_ref: str | None = None  # set only when outcome == "promote"
    probe_field: ProbeField | None = None  # set only when outcome == "promote" and Probe parses


def _reconcile_schema_refusal(project: Path) -> _Refusal | None:
    """The same v2 guard `_prepare_transition` applies per-entry (:1761), applied here to every
    ledger batch `reconcile` reads before its read pass. Without this, an unmigrated (v1) or
    too-new (v3+) ledger's entries still parse — the schema marker is metadata `parse_entries`
    never looks at — so the read pass would silently evaluate them (or find none) instead of
    refusing, exactly the false all-clear `reconcile --close` already avoids via
    `_prepare_transition`.
    """
    for spec in BACKLOG_FILES:
        path = project / spec.filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as f:
            text = f.read()
        if detect_schema_version(text) != 2:
            return _refuse(
                EXIT_SCHEMA_MISMATCH, f"{spec.filename} is not on schema v2. Run /quirk:pm:migrate first."
            )
    return None


def _reconcile_read_pass(project: Path) -> tuple[list[_ReconcileEval], list[str]]:
    """Lock-free evaluation of every `delivered` entry's ancestry (tech.md's read pass): read
    once, strict parse, no lock held. Only the caller's later write-back, per promotable entry,
    takes a lock, briefly.

    Returns `(evals, parse_error_lines)` — `parse_error_lines` mirrors `LedgerWorld.parse_errors`
    verbatim, so a ledger too large or malformed to read is reported to the caller rather than
    silently contributing zero entries indistinguishable from a ledger with none to report.
    """
    world = _load_ledger_world(project)
    repo_cache: dict[Path, _RepoState] = {}
    evals: list[_ReconcileEval] = []
    for entry, spec in world.entries.values():
        status = _entry_status(entry)
        if not isinstance(status, StatusField) or status.state != "delivered":
            continue
        repo = _target_repo(project, entry)
        outcome, detail = _evaluate_delivered(repo, status.commit, repo_cache)
        integration_ref = None
        probe_field = None
        if outcome == "promote":
            integration_ref = repo_cache[repo].integration_ref
            probe_raw = entry.fields.get("Probe")
            parsed_probe = parse_probe(probe_raw) if probe_raw is not None else None
            probe_field = parsed_probe if isinstance(parsed_probe, ProbeField) else None
        evals.append(_ReconcileEval(
            spec=spec, entry_id=entry.id, status=status, repo=repo,
            outcome=outcome, detail=detail, integration_ref=integration_ref, probe_field=probe_field,
        ))
    return evals, world.parse_errors


def _reconcile_write_back(project: Path, ev: _ReconcileEval, verify: bool) -> tuple[str, str | None]:
    """Attempt the CAS-guarded write-back for one promotable entry.

    Returns `(result, verify_outcome)`: `result` is `"closed"`, `"lock timeout"`, `"corrupt"` (a
    malformed or duplicated `Probe`/`Verify` field — the entry is left `delivered` for the next
    run to re-evaluate once the field is repaired), or `"skipped"` (a CAS mismatch — the entry
    moved since the read pass, silently left for the next run per tech.md). `--verify`'s probe
    re-run happens here, still lock-free, before the lock this function's own write takes.

    Ancestry alone is what makes an entry `closed` — an absent or unreconstructable `Probe` field
    never blocks that promotion. A genuinely malformed or duplicated one does: `park`/`decide`/
    `reconcile --close` all refuse to make an entry terminal over a corrupt sibling field, and
    silently promoting straight past that same corruption here would be the one lifecycle
    transition that doesn't. But when `--verify` was requested, skipping the re-run silently
    would leave no `Verify` field at all, which reads as "never verified" — a different, false
    claim from "verification was attempted and couldn't run." So an unusable probe still records
    a `Verify` field, just with `probe: error` instead of a real outcome.
    """
    verify_field = None
    if verify:
        parsed_spec = _reconstruct_probe_spec(ev.probe_field) if ev.probe_field is not None else None
        if isinstance(parsed_spec, ProbeSpec):
            verify_field = _run_verify(ev.repo, ev.integration_ref, parsed_spec, ev.probe_field)
        else:
            verify_field = VerifyField(date=_today(), integration_ref=ev.integration_ref, probe="error")

    new_status = StatusField(
        state="closed", date=_today(),
        attempt=ev.status.attempt, refused=ev.status.refused, integrated=ev.status.commit,
    )
    expected = (ev.entry_id, ev.status.attempt, ev.status.state, ev.status.commit)
    refusal = _commit_transition(
        project, ev.spec, ev.entry_id, expected, new_status, None,
        extra=lambda entry, status: status.commit, new_verify=verify_field,
        sibling_fields=("Probe", "Verify"),
    )
    if refusal is None:
        return "closed", (verify_field.probe if verify_field is not None else None)
    if refusal.code == EXIT_LOCK_TIMEOUT:
        return "lock timeout", None
    if refusal.code == EXIT_CORRUPT_ENTRY:
        return "corrupt", None
    return "skipped", None


_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _cmd_reconcile_close(args: argparse.Namespace, project: Path) -> int:
    """`reconcile --close`: the human-ratified promotion path (tech.md's "The human-ratified
    close path"). CAS-guarded like every other write, via the same `_expectation`/
    `_commit_transition` machinery `start`/`finish`/`park`/`decide` use — this is the one
    reconcile mode that returns exit 6 on a mismatch, since it targets a single human-named
    entry rather than a batch the next run re-evaluates.
    """
    def validate_args() -> _Refusal | None:
        if not args.integrated:
            return _refuse(EXIT_BAD_ARGUMENT, "--integrated is required with --close")
        if not _FULL_SHA_RE.match(args.integrated):
            return _refuse(EXIT_BAD_ARGUMENT, "--integrated must be a full 40-character commit sha")
        reason_error = _validate_reason(args.reason)
        if reason_error is not None:
            return reason_error
        # Phase 2: reconcile always evaluates in the project's own repo (logic.md:778-785 — no
        # `Handoff.dest:` is ever written). The entry itself isn't parsed yet at this point, so
        # this can't route through `_target_repo` the way the batch read pass does, but in
        # Phase 2 the answer is the same constant either way.
        repo = project
        if _repo_missing(repo):
            return _refuse(EXIT_BAD_ARGUMENT, "--integrated cannot be verified: destination repo missing")
        fetch_proc = _run_git(["fetch"], repo)
        if fetch_proc is None or fetch_proc.returncode != 0:
            return _refuse(EXIT_BAD_ARGUMENT, "--integrated cannot be verified: fetch failed")
        cat_proc = _run_git(["cat-file", "-e", f"{args.integrated}^{{commit}}"], repo)
        if cat_proc is None or cat_proc.returncode != 0:
            return _refuse(
                EXIT_BAD_ARGUMENT, f"--integrated {args.integrated} is not a known commit in {repo}"
            )
        integration_ref = _resolve_integration_ref(repo)
        if integration_ref is None:
            return _refuse(EXIT_BAD_ARGUMENT, _DETACHED_HEAD_DETAIL)
        ref_proc = _run_git(["rev-parse", "--verify", f"{integration_ref}^{{commit}}"], repo)
        if ref_proc is None or ref_proc.returncode != 0:
            return _refuse(EXIT_BAD_ARGUMENT, f"integration ref unresolvable: {integration_ref}")
        anc_proc = _run_git(["merge-base", "--is-ancestor", args.integrated, integration_ref], repo)
        if anc_proc is None or anc_proc.returncode != 0:
            return _refuse(
                EXIT_BAD_ARGUMENT,
                f"--integrated {args.integrated} is not an ancestor of {integration_ref}",
            )
        return None

    prepared = _prepare_transition(
        project, args.close, validate_args=validate_args, allowed_states=frozenset({"delivered"}),
        sibling_fields=("Probe", "Verify"),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    new_status = StatusField(
        state="closed", date=_today(),
        attempt=prepared.status.attempt, refused=prepared.status.refused,
        integrated=args.integrated, reason=args.reason,
    )
    refusal = _commit_transition(
        project, prepared.spec, prepared.entry_id, expected, new_status, None,
        sibling_fields=("Probe", "Verify"),
    )
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: closed ({args.integrated})")
    return EXIT_OK


def cmd_reconcile(args: argparse.Namespace) -> int:
    """Promote `delivered` entries to `closed` by git ancestry (batch), or ratify one entry via
    `--close`. Batch `reconcile` never returns 6 — a CAS mismatch on write-back is a per-entry
    skip reported in the output, since the underlying git facts don't change and the next run
    re-evaluates correctly (tech.md's aggregate-outcomes rule).
    """
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    if args.close is not None:
        return _cmd_reconcile_close(args, project)

    if args.integrated is not None or args.reason is not None:
        print("[quirk:pm] --integrated/--reason require --close", file=sys.stderr)
        return EXIT_BAD_ARGUMENT

    missing = [s.filename for s in BACKLOG_FILES if not (project / s.filename).exists()]
    if missing:
        print(
            f"{', '.join(missing)} not found in {project}. Run /quirk:artifacts:init first.",
            file=sys.stderr,
        )
        return EXIT_NOT_FOUND

    schema_refusal = _reconcile_schema_refusal(project)
    if schema_refusal is not None:
        print(f"[quirk:pm] {schema_refusal.message}", file=sys.stderr)
        return schema_refusal.code

    evals, parse_error_lines = _reconcile_read_pass(project)
    # a skipped ledger is could-not-look, not looked-and-found-nothing — surfaced the same way
    # the read layer already reports it, so this never reads as a second, silently different
    # kind of "clean"
    for line in parse_error_lines:
        print(line)
    if not evals:
        if parse_error_lines:
            print(
                "[quirk:pm] reconcile: no delivered entries evaluated — "
                f"{len(parse_error_lines)} ledger(s) could not be read, see above"
            )
        else:
            print("[quirk:pm] reconcile: no delivered entries to evaluate")
        return EXIT_OK

    promoted = not_yet = cannot_evaluate = skipped = 0
    # exit 5 means "nothing was written" (tech.md's aggregate-outcomes rule) — a lock timeout on
    # one entry never overrides a promotion another entry already committed this run
    lock_timeout_seen = False
    for ev in evals:
        label = f"{ev.spec.header}-{ev.entry_id}"
        if ev.outcome == "not_yet":
            not_yet += 1
            print(f"[quirk:pm] {label}: awaiting integration")
            continue
        if ev.outcome == "cannot_evaluate":
            cannot_evaluate += 1
            print(f"[quirk:pm] {label}: cannot evaluate ({ev.detail})")
            continue

        result, verify_outcome = _reconcile_write_back(project, ev, args.verify)
        if result == "closed":
            promoted += 1
            suffix = f" — verify: {verify_outcome}" if verify_outcome is not None else ""
            print(f"[quirk:pm] {label}: closed ({ev.status.commit}){suffix}")
        elif result == "lock timeout":
            lock_timeout_seen = True
            skipped += 1
            print(f"[quirk:pm] {label}: skipped (lock timeout, retry next run)")
        elif result == "corrupt":
            skipped += 1
            print(f"[quirk:pm] {label}: skipped (malformed or duplicated Probe/Verify field, repair and re-run)")
        else:
            skipped += 1
            print(f"[quirk:pm] {label}: skipped (entry changed since read pass)")

    summary = (
        f"[quirk:pm] reconcile: {promoted} closed, {not_yet} awaiting integration, "
        f"{cannot_evaluate} cannot evaluate, {skipped} skipped (of {len(evals)} delivered)"
    )
    if parse_error_lines:
        summary += f" — {len(parse_error_lines)} ledger(s) could not be read, see above"
    print(summary)
    if lock_timeout_seen and promoted == 0:
        return EXIT_LOCK_TIMEOUT
    return EXIT_OK


def cmd_roadmap(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()

    if args.show:
        sys.stdout.write(render_roadmap_show(project))
        return EXIT_OK

    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    write_path = Path(args.write)
    try:
        text = write_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[quirk:pm] cannot read {args.write}: {exc}", file=sys.stderr)
        return EXIT_NOT_FOUND
    except UnicodeDecodeError as exc:
        print(f"[quirk:pm] cannot read {args.write}: not valid utf-8 ({exc})", file=sys.stderr)
        return EXIT_BAD_ARGUMENT

    parse = parse_roadmap(text)
    world = _load_ledger_world(project)
    # surfaced regardless of outcome below: a skipped ledger makes this validation partial, and
    # that must be visible whether the write proceeds on it or is refused for an unrelated reason
    for line in world.parse_errors:
        print(line)
    findings = validate_roadmap_for_write(parse, set(world.entries), skipped_headers=world.skipped_headers)
    if findings:
        for code, detail in findings:
            print(f"[quirk:pm] {code}: {detail}", file=sys.stderr)
        return EXIT_BAD_ARGUMENT

    lock_dir = ensure_lock_dir(project)
    timeout = _lock_timeout()
    deadline = time.monotonic() + timeout
    lock_file = _acquire_ledger_lock(lock_dir / "ROADMAP.md.lock", deadline)
    if lock_file is None:
        print("[quirk:pm] could not acquire lock on ROADMAP.md, nothing written", file=sys.stderr)
        return EXIT_LOCK_TIMEOUT
    try:
        atomic_write(project / "ROADMAP.md", render_roadmap(parse))
    finally:
        lock_file.close()

    print(f"[quirk:pm] ROADMAP.md written from {args.write}")
    return EXIT_OK


# --- CLI dispatch --------------------------------------------------------


def _add_project_dir(parser: argparse.ArgumentParser, *, top_level: bool = False) -> None:
    # a subparser reparses into its own fresh namespace and then copies every one of its keys
    # onto the outer namespace (argparse._SubParsersAction.__call__), so a real default here would
    # always clobber a --project-dir the top-level parser already captured before the subcommand;
    # SUPPRESS keeps that key out of the subparser's namespace unless the flag actually follows it
    default = "." if top_level else argparse.SUPPRESS
    parser.add_argument("--project-dir", default=default, help="Project root containing artifact files")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="pm.py — typed-artifact lifecycle manager.")
    # --index/--next/--doctor predate the subcommand surface: hooks/load_artifact_tail.sh
    # (a later task's file) still invokes `pm.py --next`, and tests/test_pm_index_doctor.py
    # pins all three bare flags, so they stay live as top-level options rather than being
    # retired in favor of the equivalent subcommands.
    parser.add_argument("--index", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--next", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--doctor", action="store_true", help=argparse.SUPPRESS)
    _add_project_dir(parser, top_level=True)

    subparsers = parser.add_subparsers(dest="command")

    p_next = subparsers.add_parser("next", help="Top-5 shortlist of ready work")
    _add_project_dir(p_next)
    p_next.set_defaults(func=cmd_next)

    p_start = subparsers.add_parser("start", help="Start work on an entry (--here only)")
    p_start.add_argument("id")
    p_start.add_argument("--probe", metavar="VERB:ARG")
    p_start.add_argument("--repo", metavar="SEL")
    p_start.add_argument("--here", action="store_true")
    _add_project_dir(p_start)
    p_start.set_defaults(func=cmd_start)

    p_finish = subparsers.add_parser("finish", help="Finish work on an entry")
    p_finish.add_argument("id")
    _add_project_dir(p_finish)
    p_finish.set_defaults(func=cmd_finish)

    p_park = subparsers.add_parser("park", help="Park an in-progress entry")
    p_park.add_argument("id")
    p_park.add_argument("--reason", metavar="TEXT")
    _add_project_dir(p_park)
    p_park.set_defaults(func=cmd_park)

    p_decide = subparsers.add_parser("decide", help="Decide an entry's fate")
    p_decide.add_argument("id")
    p_decide.add_argument("--as", dest="as_", choices=["wontfix", "superseded"])
    p_decide.add_argument("--reason", metavar="TEXT")
    p_decide.add_argument("--by", metavar="ID")
    _add_project_dir(p_decide)
    p_decide.set_defaults(func=cmd_decide)

    p_reconcile = subparsers.add_parser("reconcile", help="Promote delivered entries reachable from the integration ref")
    p_reconcile.add_argument("--verify", action="store_true")
    p_reconcile.add_argument("--close", metavar="ID")
    p_reconcile.add_argument("--integrated", metavar="SHA")
    p_reconcile.add_argument("--reason", metavar="TEXT")
    _add_project_dir(p_reconcile)
    p_reconcile.set_defaults(func=cmd_reconcile)

    p_roadmap = subparsers.add_parser("roadmap", help="Show or write ROADMAP.md (not yet implemented)")
    roadmap_group = p_roadmap.add_mutually_exclusive_group(required=True)
    roadmap_group.add_argument("--show", action="store_true")
    roadmap_group.add_argument("--write", metavar="PATH")
    _add_project_dir(p_roadmap)
    p_roadmap.set_defaults(func=cmd_roadmap)

    p_status = subparsers.add_parser("status", help="Index output followed by doctor output")
    _add_project_dir(p_status)
    p_status.set_defaults(func=cmd_status)

    p_index = subparsers.add_parser("index", help="Bounded summary of backlog state")
    _add_project_dir(p_index)
    p_index.set_defaults(func=cmd_index)

    p_doctor = subparsers.add_parser("doctor", help="Structural findings across artifact files")
    _add_project_dir(p_doctor)
    p_doctor.set_defaults(func=cmd_doctor)

    p_migrate = subparsers.add_parser("migrate", help="Migrate ledger files to schema v2")
    _add_project_dir(p_migrate)
    p_migrate.set_defaults(func=cmd_migrate)

    return parser


def _dispatch(argv: list[str] | None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # checked ahead of subparser dispatch — see build_parser's --index/--next/--doctor comment
    if args.index:
        return cmd_index(args)
    if args.next:
        return cmd_next(args)
    if args.doctor:
        return cmd_doctor(args)

    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_BAD_ARGUMENT
    return args.func(args)


def main(argv: list[str] | None = None) -> int:
    try:
        return _dispatch(argv)
    except SymlinkedLedgerError as exc:
        # a deliberate, named refusal must not reach the catch-all below: exit 1 is documented as
        # the safety net for an uncaught exception, so reporting this there would both blame
        # pm.py for the user's setup and leave a wrapper unable to tell the two apart
        print(f"[quirk:pm] {exc} — replace it with a regular file and retry", file=sys.stderr)
        return EXIT_BAD_ARGUMENT
    except Exception as exc:
        print(f"[quirk:pm] unexpected error: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    sys.exit(main())
