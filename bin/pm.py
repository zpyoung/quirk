#!/usr/bin/env python3
"""Subcommand CLI over typed-artifact markdown files: index/next/doctor/status/migrate/roadmap,
plus the Phase-2 lifecycle commands start/finish/park/decide (reconcile is a later task's stub).

The read layer (index/next/doctor/status/roadmap) consumes `Status`, `Blocked by`, and
`ROADMAP.md` membership to compute readiness (`ready`/`eligible`/`unplaced`) and to run
cross-ledger doctor findings (`CYCLE`, `DANGLING`, `BLOCKED_BY_*`, roadmap findings). The
lifecycle commands mutate an entry's `Status`/`Probe` fields under the same compare-and-swap
procedure — acquire the ledger's lock, re-read, compare the expectation tuple captured before any
slow work, splice and write on match, refuse without writing on mismatch. `start` here is
`--here`-only (Phase 2): no `Handoff` field, no worktree, no dispatch.
"""
from __future__ import annotations

import argparse
import codecs
import datetime
import fcntl
import locale
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, IO, Iterable, Iterator

from artifact_lib import (
    DuplicateFieldError,
    Entry,
    MalformedHeading,
    RoadmapParse,
    atomic_write,
    detect_schema_version,
    ensure_lock_dir,
    field_present_but_empty,
    hash_file,
    hash_probe_spec,
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
DEFAULT_MAX_FILE_BYTES = 1_048_576
# Above this, max_bytes + 1 is still a valid Py_ssize_t on every platform, but
# a sys.maxsize-relative bound isn't: CPython accepts a read() size far below
# sys.maxsize on the stack but still fails to actually service it (OverflowError
# or MemoryError) once the size is absurdly large, and where that line falls is
# host-dependent. 1 GiB is comfortably past any real artifact file and
# comfortably short of that failure mode on any real host.
MAX_USABLE_FILE_BYTES = 1_073_741_824

DEFAULT_PROBE_TIMEOUT = 120.0
DEFAULT_TEST_RUNNER = "python3 -m pytest"
DEFAULT_TEST_EXIT_MAP: dict[int, str] = {0: "pass", 1: "fail", 4: "missing", 5: "missing"}


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

    findings.extend(_cross_ledger_doctor_findings(project))

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

    findings.extend(_cross_ledger_doctor_findings(project))

    if not findings:
        lines.append("[quirk:pm] doctor: no findings")
    else:
        for code, detail in findings:
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
    """
    # a lock file's contents are never read or written, only its existence and its flock, so
    # O_NOFOLLOW refuses a symlink planted at this path instead of opening (and O_CREAT|O_RDWR
    # truncating) whatever it points at
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
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

    lock_dir = ensure_lock_dir(project)
    timeout = float(os.environ.get("ARTIFACT_LOCK_TIMEOUT", "5.0"))
    deadline = time.monotonic() + timeout

    held_locks: list[IO[str]] = []
    try:
        # every lock is held before any file is touched, so a timeout partway through never
        # leaves an earlier ledger migrated while a later one wasn't — a fixed order (this list's)
        # is what keeps that safe against deadlock, since two acquirers taking locks in different
        # orders can wait on each other forever
        for filename in LEDGER_FILES:
            lock_file = _acquire_ledger_lock(lock_dir / f"{filename}.lock", deadline)
            if lock_file is None:
                print(
                    f"[quirk:pm] could not acquire lock on {filename}, nothing written",
                    file=sys.stderr,
                )
                return EXIT_LOCK_TIMEOUT
            held_locks.append(lock_file)

        saw_too_new = False
        for filename in LEDGER_FILES:
            outcome, message = _migrate_one_ledger(project, filename)
            print(f"[quirk:pm] {message}")
            saw_too_new = saw_too_new or outcome == "too_new"

        roadmap_path = project / "ROADMAP.md"
        if roadmap_path.exists():
            print("[quirk:pm] ROADMAP.md: already exists")
        else:
            shutil.copy(TEMPLATES_DIR / "ROADMAP.md", roadmap_path)
            print("[quirk:pm] ROADMAP.md: created")
    finally:
        for lock_file in held_locks:
            lock_file.close()

    if saw_too_new:
        return EXIT_SCHEMA_MISMATCH
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
    sys.stdout.write(render_index(project) + render_doctor(project))
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


def is_valid_free_text(value: str) -> bool:
    """Return whether `value` is safe as a lifecycle field's one free-text segment.

    Rejects a newline, a carriage return, or the field delimiter itself — any of these
    would make the delimiter-split grammar ambiguous when the field is parsed back. Shared by
    `start`/`park`/`decide` to validate `--reason`/`--parked` before writing anything.
    """
    return _FREE_TEXT_BAD_RE.search(value) is None


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

    if i >= len(parts) or not _DATE_RE.match(parts[i]):
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
    if i < len(parts):
        m = _FINAL_RE.match(parts[i])
        if m is None:
            return MalformedField(raw=line, reason="final")
        final = m.group(1)
        i += 1

        m = _SKIPPED_RE.match(parts[i]) if verb == "grep" and i < len(parts) else None
        if m is not None:
            skipped_files = _safe_int(m.group(1))
            if skipped_files is None:
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
        skipped_files=skipped_files,
    )


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


def _load_ledger_world(project: Path) -> LedgerWorld:
    entries: dict[str, tuple[Entry, ArtifactSpec]] = {}
    parse_errors: list[str] = []
    malformed_total = 0
    for spec in BACKLOG_FILES:
        path = project / spec.filename
        if not path.exists():
            continue
        fp, skip_reason = _read_and_parse(project, spec)
        if fp is None:
            if skip_reason is not None:
                parse_errors.append(f"[quirk:pm] {spec.filename}: {skip_reason}")
            continue
        malformed_total += len(fp.malformed)
        for e in fp.entries:
            entries[f"{spec.header}-{e.id}"] = (e, spec)
    return LedgerWorld(entries=entries, parse_errors=parse_errors, malformed_total=malformed_total)


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
    merely being started or reported delivered never unblocks its dependents early.
    """
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
    """
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

    Used to explain an empty ready-set: only named, resolvable IDs are counted, since those are
    the ones a human can act on to unblock the most work.
    """
    counts: dict[str, int] = {}
    for _key, (entry, _spec) in world.entries.items():
        if not _is_open(entry):
            continue
        blocked = _blocked_by(entry)
        if blocked.truncated:
            continue
        for token in blocked.tokens:
            if token.kind == "id" and not satisfied(world, token.id):
                counts[token.id] = counts.get(token.id, 0) + 1
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
    """Return every cycle in `edges`, each reported once regardless of which member it is
    discovered from (deduped by rotation).

    Iterative DFS with an explicit frame stack and a recursion-stack color set — never recursive
    — so a large or adversarially deep graph terminates in bounded, linear time instead of
    risking a stack overflow or an accidentally-quadratic reimplementation.
    """
    color: dict[str, int] = {}  # 0 unvisited (default), 1 on stack, 2 done
    found: list[tuple[str, ...]] = []
    seen_rotations: set[tuple[str, ...]] = set()

    def normalize(cycle: list[str]) -> tuple[str, ...]:
        start = min(range(len(cycle)), key=lambda i: cycle[i])
        return tuple(cycle[start:] + cycle[:start])

    for root in sorted(edges):
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
    return found


def _cycle_doctor_findings(world: LedgerWorld) -> list[tuple[str, str]]:
    cycles = _find_cycles(_blocked_by_edges(world))
    return [("CYCLE", " -> ".join((*cyc, cyc[0]))) for cyc in cycles]


def _roadmap_doctor_findings(project: Path, known_ids: set[str]) -> list[tuple[str, str]]:
    roadmap = _read_roadmap(project)
    findings = list(roadmap.findings)
    referenced = {member_id for milestone in roadmap.milestones for member_id in milestone.members}
    findings.extend(("DANGLING_ROADMAP_REF", member_id) for member_id in sorted(referenced - known_ids))
    return findings


def _cross_ledger_doctor_findings(project: Path) -> list[tuple[str, str]]:
    world = _load_ledger_world(project)
    findings = _blocked_by_doctor_findings(world)
    findings.extend(_cycle_doctor_findings(world))
    findings.extend(_roadmap_doctor_findings(project, set(world.entries)))
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
    """The `QUIRK_PM_PROBE_TIMEOUT` bound (seconds) in effect, defaulting to 120."""
    raw = os.environ.get("QUIRK_PM_PROBE_TIMEOUT")
    if raw is None:
        return DEFAULT_PROBE_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT
    return value if value > 0 else DEFAULT_PROBE_TIMEOUT


def _parse_test_exit_map(raw: str) -> dict[int, str] | None:
    """Parse `QUIRK_PM_TEST_EXIT_MAP`'s `code:outcome` list; `None` if any entry is malformed."""
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
        proc = subprocess.run(command, cwd=root, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ProbeResult(outcome="error", detail=f"probe exceeded {timeout}s timeout")
    except OSError as exc:
        return ProbeResult(outcome="error", detail=f"could not run test runner: {exc}")

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
    except re.error as exc:
        return ProbeResult(outcome="error", detail=str(exc))

    if spec.paths:
        bases: list[Path] = []
        for raw in spec.paths:
            candidate = Path(raw)
            candidate = candidate if candidate.is_absolute() else root / candidate
            if not candidate.exists():
                return ProbeResult(outcome="error", detail=f"path not found: {raw}")
            try:
                if candidate.is_dir():
                    with os.scandir(candidate):
                        pass
                else:
                    with open(candidate, "rb"):
                        pass
            except PermissionError:
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
            try:
                text = file_path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                skipped += 1
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
    code that carried the symptom is not a fix.
    """
    return [name for name in baseline_files if not (root / name).exists()]


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
) -> _Prepared | _Refusal:
    """Run every check that precedes the CAS write, in the exit-code table's precedence order:
    not-found (3) -> bad argument (2) -> schema mismatch (8) -> corrupt entry (4) -> CAS (6).

    `validate_args` supplies the command-specific "2" checks (probe syntax, `--reason`, `--by`,
    `--repo`) — they run after the not-found check and before the schema/corrupt checks, per
    tech.md's per-command precedence table, so a not-found ID always outranks a bad argument.
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
    status = _entry_status(entry)
    if isinstance(status, MalformedField):
        return _refuse(
            EXIT_CORRUPT_ENTRY, f"{spec.header}-{entry_id}: malformed Status field ({status.reason})"
        )

    if spec.header == "PROPOSAL":
        return _refuse(
            EXIT_CAS_FAILURE, f"{spec.header}-{entry_id}: PROPOSAL entries are not part of the PM lifecycle"
        )
    if status.state not in allowed_states:
        return _refuse(
            EXIT_CAS_FAILURE,
            f"{spec.header}-{entry_id}: expected state in {sorted(allowed_states)}, found {status.state!r}",
        )

    return _Prepared(spec=spec, entry_id=entry_id, entry=entry, status=status)


def _expectation(prepared: _Prepared) -> tuple[int, int, str, str | None]:
    return (
        prepared.entry_id, prepared.status.attempt, prepared.status.state,
        prepared.entry.fields.get("Probe"),
    )


def _commit_transition(
    project: Path,
    spec: ArtifactSpec,
    entry_id: int,
    expected: tuple[int, int, str, str | None],
    new_status: StatusField,
    new_probe: ProbeField | None,
) -> _Refusal | None:
    """Re-read, re-locate, and compare `expected` under the held lock; splice and write on match.

    The compare and the write happen inside this one lock acquisition — splitting them into a
    read-then-later-write would reopen exactly the race the CAS procedure exists to close.
    """
    path = project / spec.filename
    lock_dir = ensure_lock_dir(project)
    timeout = float(os.environ.get("ARTIFACT_LOCK_TIMEOUT", "5.0"))
    deadline = time.monotonic() + timeout
    lock_file = _acquire_ledger_lock(lock_dir / f"{spec.filename}.lock", deadline)
    if lock_file is None:
        return _refuse(EXIT_LOCK_TIMEOUT, f"could not acquire lock on {spec.filename}, nothing written")
    try:
        with path.open(encoding="utf-8", newline="") as f:
            text = f.read()
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
        # attempt, not just state, closes the stale-transition race: a status-only compare
        # can't tell this in_progress from a different, later attempt at the same state
        current = (entry.id, status.attempt, status.state, entry.fields.get("Probe"))
        if current != expected:
            return _refuse(EXIT_CAS_FAILURE, f"{spec.header}-{entry_id}: CAS mismatch, refusing")

        try:
            new_text = splice_field(text, entry, "Status", render_status(new_status))
            if new_probe is not None:
                reparsed = parse_entries(new_text, spec.header)
                entry2 = next(e for e in reparsed.entries if e.id == entry_id)
                new_text = splice_field(new_text, entry2, "Probe", render_probe(new_probe))
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
    if spec.verb == "test":
        final = result.outcome
        final_file_hash = hash_file(root / spec.nodeid.split("::", 1)[0])
    else:
        final = _grep_summary(result.count or 0)
    return replace(current, final=final, final_spec_hash=final_spec_hash, final_file_hash=final_file_hash)


def cmd_start(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    probe_spec_box: list[ProbeSpec] = []

    def validate_args() -> _Refusal | None:
        if args.repo is not None:
            return _refuse(
                EXIT_BAD_ARGUMENT, "dispatch is not available yet (Phase 2 is --here only); drop --repo"
            )
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
    if not probe_accepts_baseline(probe_spec, baseline):
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: baseline probe outcome "
            f"{baseline.outcome!r} does not discriminate this entry",
            file=sys.stderr,
        )
        return EXIT_PROBE_REFUSED

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
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    probe_raw = prepared.entry.fields.get("Probe")
    current_probe = parse_probe(probe_raw) if probe_raw is not None else ProbeField(verb="none", arg="")
    if isinstance(current_probe, MalformedField):
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: malformed Probe field "
            f"({current_probe.reason})",
            file=sys.stderr,
        )
        return EXIT_CORRUPT_ENTRY
    probe_verb_arg = "none" if current_probe.verb == "none" else f"{current_probe.verb}:{current_probe.arg}"
    probe_spec = parse_probe_spec(probe_verb_arg)
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

    result = run_probe(probe_spec, project)
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
        refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, None)
        if refusal is not None:
            print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
            return refusal.code
        print(
            f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: probe refused "
            f"(refused {new_status.refused})",
            file=sys.stderr,
        )
        return EXIT_PROBE_REFUSED

    commit_sha = _git_head_sha(project)
    if commit_sha is None:
        print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: could not resolve HEAD", file=sys.stderr)
        return EXIT_FINISH_PRECONDITION_FAILED

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


def cmd_park(args: argparse.Namespace) -> int:
    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return EXIT_PROJECT_DIR_NOT_FOUND

    def validate_args() -> _Refusal | None:
        if not is_valid_free_text(args.reason):
            return _refuse(EXIT_BAD_ARGUMENT, "--reason contains a newline, carriage return, or ' — '")
        return None

    prepared = _prepare_transition(
        project, args.id, validate_args=validate_args, allowed_states=frozenset({"in_progress"}),
    )
    if isinstance(prepared, _Refusal):
        print(f"[quirk:pm] {prepared.message}", file=sys.stderr)
        return prepared.code
    expected = _expectation(prepared)

    new_status = StatusField(
        state="open", date=_today(),
        attempt=prepared.status.attempt, refused=prepared.status.refused, parked=args.reason,
    )
    refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, None)
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
        if not is_valid_free_text(args.reason):
            return _refuse(EXIT_BAD_ARGUMENT, "--reason contains a newline, carriage return, or ' — '")
        if args.as_ == "superseded":
            if not args.by:
                return _refuse(EXIT_BAD_ARGUMENT, "--as superseded requires --by")
            if not _ENTRY_ID_ARG_RE.match(args.by):
                return _refuse(EXIT_BAD_ARGUMENT, f"--by {args.by!r} is not a valid entry ID")
        return None

    prepared = _prepare_transition(
        project, args.id, validate_args=validate_args,
        allowed_states=frozenset({"open", "in_progress", "delivered"}),
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

    refusal = _commit_transition(project, prepared.spec, prepared.entry_id, expected, new_status, None)
    if refusal is not None:
        print(f"[quirk:pm] {refusal.message}", file=sys.stderr)
        return refusal.code

    print(f"[quirk:pm] {prepared.spec.header}-{prepared.entry_id}: {args.as_}")
    return EXIT_OK


def cmd_reconcile(args: argparse.Namespace) -> int:
    return _not_implemented("reconcile")


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
    known_ids = set(_load_ledger_world(project).entries)
    findings = validate_roadmap_for_write(parse, known_ids)
    if findings:
        for code, detail in findings:
            print(f"[quirk:pm] {code}: {detail}", file=sys.stderr)
        return EXIT_BAD_ARGUMENT

    lock_dir = ensure_lock_dir(project)
    timeout = float(os.environ.get("ARTIFACT_LOCK_TIMEOUT", "5.0"))
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
    p_start.add_argument("--probe", required=True, metavar="VERB:ARG")
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
    p_park.add_argument("--reason", required=True, metavar="TEXT")
    _add_project_dir(p_park)
    p_park.set_defaults(func=cmd_park)

    p_decide = subparsers.add_parser("decide", help="Decide an entry's fate")
    p_decide.add_argument("id")
    p_decide.add_argument("--as", dest="as_", required=True, choices=["wontfix", "superseded"])
    p_decide.add_argument("--reason", required=True, metavar="TEXT")
    p_decide.add_argument("--by", metavar="ID")
    _add_project_dir(p_decide)
    p_decide.set_defaults(func=cmd_decide)

    p_reconcile = subparsers.add_parser("reconcile", help="Reconcile delivered entries (not yet implemented)")
    p_reconcile.add_argument("--verify", action="store_true")
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
    except Exception as exc:
        print(f"[quirk:pm] unexpected error: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    sys.exit(main())
