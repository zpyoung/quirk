#!/usr/bin/env python3
"""Subcommand CLI over typed-artifact markdown files: index/next/doctor/status/migrate,
plus stubs for the Phase-3 lifecycle commands (start/finish/park/decide/reconcile/roadmap).

The read layer (index/next/doctor/status) predates the lifecycle schema: no Status field,
no Blocked by, no ROADMAP.md membership feed into it, so every well-formed entry is open,
nothing is blocked, and every open entry is unplaced. Lifecycle counts
(in_progress/delivered/closed) and roadmap-derived findings are added by a later task.
"""
from __future__ import annotations

import argparse
import codecs
import fcntl
import locale
import os
import re
import shutil
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from artifact_lib import (
    Entry,
    MalformedHeading,
    atomic_write,
    detect_schema_version,
    ensure_lock_dir,
    parse_entries,
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
    # artifact_append.py writes these files with the platform default encoding,
    # not explicit utf-8 (fenced there). Bytes valid under both codecs must
    # decode as the writer actually wrote them, not as whichever codec is
    # tried first, so the platform codec goes first whenever it differs from
    # utf-8 — this couples the reader to that locale-dependent write.
    platform_encoding = locale.getpreferredencoding(False)
    try:
        platform_is_utf8 = codecs.lookup(platform_encoding).name == codecs.lookup("utf-8").name
    except LookupError:
        platform_is_utf8 = False
    if platform_is_utf8:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return None, "parse error, skipping"
    else:
        try:
            text = data.decode(platform_encoding)
        except (UnicodeDecodeError, LookupError):
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
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
    lock_file = open(lock_path, "w")
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


# --- not-yet-implemented lifecycle commands -----------------------------


def _not_implemented(name: str) -> int:
    print(f"pm.py {name}: not implemented yet", file=sys.stderr)
    return EXIT_BAD_ARGUMENT


def cmd_start(args: argparse.Namespace) -> int:
    return _not_implemented("start")


def cmd_finish(args: argparse.Namespace) -> int:
    return _not_implemented("finish")


def cmd_park(args: argparse.Namespace) -> int:
    return _not_implemented("park")


def cmd_decide(args: argparse.Namespace) -> int:
    return _not_implemented("decide")


def cmd_reconcile(args: argparse.Namespace) -> int:
    return _not_implemented("reconcile")


def cmd_roadmap(args: argparse.Namespace) -> int:
    return _not_implemented("roadmap")


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

    p_start = subparsers.add_parser("start", help="Start work on an entry (not yet implemented)")
    p_start.add_argument("id")
    p_start.add_argument("--probe", required=True, metavar="VERB:ARG")
    p_start.add_argument("--repo", metavar="SEL")
    p_start.add_argument("--here", action="store_true")
    _add_project_dir(p_start)
    p_start.set_defaults(func=cmd_start)

    p_finish = subparsers.add_parser("finish", help="Finish work on an entry (not yet implemented)")
    p_finish.add_argument("id")
    _add_project_dir(p_finish)
    p_finish.set_defaults(func=cmd_finish)

    p_park = subparsers.add_parser("park", help="Park an in-progress entry (not yet implemented)")
    p_park.add_argument("id")
    p_park.add_argument("--reason", required=True, metavar="TEXT")
    _add_project_dir(p_park)
    p_park.set_defaults(func=cmd_park)

    p_decide = subparsers.add_parser("decide", help="Decide an entry's fate (not yet implemented)")
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
