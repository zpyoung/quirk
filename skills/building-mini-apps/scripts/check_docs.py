#!/usr/bin/env python3
"""Check study notes, pattern and style references and blueprints, and vet staged observation bullets.

Usage:
    check_docs.py study <app>
    check_docs.py pattern <pattern>
    check_docs.py blueprint <app>
    check_docs.py style <style>
    check_docs.py observations <app> <bullets_file> [--frames]

Names come from the files on disk (references/apps, references/patterns, references/blueprints,
references/styles) and must match [a-z0-9][a-z0-9-]*. `observations` never edits a file; every
non-blank line must be a '- S<n>, ...' bullet or an 'Unseen: <text>' line (the capture brief's
note on what the source can't show; not checked for source IDs or frames). With --frames it also
requires each cited references/media/<app>/<file>.png to exist.

Exits 0 when the document is complete, 1 when it is missing or incomplete (each problem is
printed), and 2 on a usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


SKILL_ROOT = Path(__file__).resolve().parent.parent

FOLDERS = {"study": "apps", "pattern": "patterns", "blueprint": "blueprints", "style": "styles"}
REQUIRED: Dict[str, Tuple[str, ...]] = {
    "study": ("Sources", "Observations", "Unseen", "Patterns fed"),
    "pattern": ("When to use", "Anatomy", "Interaction", "Borrow / Leave out", "Block API", "Sources"),
    "blueprint": ("Core jobs", "Screens", "Coverage", "Composition",
                  "Proposed patterns", "Proposed revisions"),
    "style": ("Character", "When it fits", "Studied from", "Leaves out"),
}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
JOB_STATES = ("proposed", "confirmed", "covered")
MARKS = ("matched", "approximated", "left out")

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|(?!\s*-)(.+)\|\s*$", re.MULTILINE)
JOB_ID_RE = re.compile(r"^J[0-9]+$")
ROW_START_RE = re.compile(r"^(J[0-9]+\b|Screen:)")
FRAME_NAME_RE = re.compile(r"[A-Z][0-9]+-[A-Za-z0-9_-]+\.png")
SOURCE_ID_RE = re.compile(r"\bS[0-9]+\b")
BULLET_RE = re.compile(r"^- (S[0-9]+), ")
UNSEEN_RE = re.compile(r"^Unseen:\s*\S")
FRAME_PATH_RE = re.compile(r"references/media/[A-Za-z0-9_./-]+?\.png")


def sections(text: str) -> List[Tuple[str, str]]:
    """Split a markdown document into (level-2 heading, body) pairs, in document order."""
    matches = list(HEADING_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[m.end():end].strip()))
    return out


def path_for(kind: str, name: str) -> Path:
    return SKILL_ROOT / "references" / FOLDERS[kind] / f"{name}.md"


def table_rows(body: str, header: Tuple[str, ...]) -> Tuple[List[List[str]], List[str]]:
    """Return (data rows as cell lists, problems) for the first table in a section body.

    The first row must be the expected header; it is dropped from the data rows.
    """
    rows = [[c.strip() for c in r.split("|")] for r in TABLE_ROW_RE.findall(body)]
    if not rows or [c.lower() for c in rows[0]] != [h.lower() for h in header]:
        return [], [f"table header must be '{' | '.join(header)}'"]
    problems = []
    data = []
    for row in rows[1:]:
        if len(row) != len(header):
            problems.append(f"table row has {len(row)} cells, expected {len(header)}: {row[0] if row else ''}")
        else:
            data.append(row)
    return data, problems


def source_ids(study_text: str) -> Set[str]:
    """IDs listed in the first column of the study note's '## Sources' table."""
    body = dict(sections(study_text)).get("Sources", "")
    ids = set()
    for row in TABLE_ROW_RE.findall(body):
        first = row.split("|")[0].strip()
        if SOURCE_ID_RE.fullmatch(first):
            ids.add(first)
    return ids


def check_blueprint(bodies: Dict[str, str], study_text: str) -> List[str]:
    """Problems in a blueprint's Core jobs and Coverage tables, resolved against its study note."""
    problems: List[str] = []
    jobs: Dict[str, str] = {}
    if bodies.get("Core jobs"):
        data, issues = table_rows(bodies["Core jobs"], ("ID", "Job", "State"))
        problems += [f"'## Core jobs': {i}" for i in issues]
        if not issues and not data:
            problems.append("'## Core jobs' needs at least one job row")
        for job_id, _, state in data:
            if not JOB_ID_RE.match(job_id):
                problems.append(f"'## Core jobs': bad job ID {job_id!r}, expected J<number>")
            elif job_id in jobs:
                problems.append(f"'## Core jobs': duplicate job ID {job_id}")
            else:
                jobs[job_id] = state
            if state not in JOB_STATES:
                problems.append(f"'## Core jobs': {job_id} has bad State {state!r}, "
                                f"expected one of {', '.join(JOB_STATES)}")
    coverage_rows: List[str] = []
    if bodies.get("Coverage"):
        data, issues = table_rows(bodies["Coverage"], ("Row", "Mark", "Pattern", "Evidence"))
        problems += [f"'## Coverage': {i}" for i in issues]
        observations = dict(sections(study_text)).get("Observations", "")
        known_sources = source_ids(study_text)
        for row, mark, _, evidence in data:
            coverage_rows.append(row)
            if not ROW_START_RE.match(row):
                problems.append(f"'## Coverage': row {row!r} must start with a job ID or 'Screen:'")
            if mark not in MARKS:
                problems.append(f"'## Coverage': row {row!r} has bad Mark {mark!r}, "
                                f"expected one of {', '.join(MARKS)}")
            frames = FRAME_NAME_RE.findall(evidence)
            sources = SOURCE_ID_RE.findall(FRAME_NAME_RE.sub(" ", evidence))
            unseen = re.search(r"\bunseen\b", evidence) is not None
            for frame in frames:
                if frame not in observations:
                    problems.append(f"'## Coverage': row {row!r} cites frame {frame} "
                                    "that is not in the study note's Observations")
            for source in sources:
                if source not in known_sources:
                    problems.append(f"'## Coverage': row {row!r} cites {source}, "
                                    "which is not in the study note's Sources")
            if unseen and mark != "left out":
                problems.append(f"'## Coverage': row {row!r} uses 'unseen' but Mark is {mark!r}; "
                                "only 'left out' rows may")
            if not (frames or sources or unseen):
                problems.append(f"'## Coverage': row {row!r} has no citation in Evidence")
    for job_id, state in jobs.items():
        if state in ("confirmed", "covered") and not any(
                re.match(re.escape(job_id) + r"\b", r) for r in coverage_rows):
            problems.append(f"job {job_id} is {state} but has no coverage row")
    return problems


def check(kind: str, name: str) -> List[str]:
    """Return the problems found in one document; an empty list means it passes."""
    required = REQUIRED[kind]
    path = path_for(kind, name)
    if not path.is_file():
        return [f"missing file {path}"]
    study_text = ""
    if kind == "blueprint":
        study = path_for("study", name)
        if not study.is_file():
            return [f"no study note for {name}"]
        study_text = study.read_text()
    found = sections(path.read_text())
    titles = [t for t, _ in found]
    problems = []
    for title in required:
        if title not in titles:
            problems.append(f"missing section '## {title}'")
    present = [t for t in titles if t in required]
    if not problems and present != list(required):
        problems.append(f"sections out of order: {present}")
    bodies = dict(found)
    for title in required:
        if title in bodies and not bodies[title]:
            problems.append(f"section '## {title}' is empty")
    if kind == "study" and "Sources" in bodies:
        rows = TABLE_ROW_RE.findall(bodies["Sources"])
        if len(rows) - 1 < 2:
            problems.append("'## Sources' needs a table with at least 2 source rows")
    if kind == "blueprint":
        problems += check_blueprint(bodies, study_text)
    return problems


def check_observations(name: str, bullets: Path, frames: bool) -> List[str]:
    """Return one 'line N: reason' problem per failing line of a staged bullets file."""
    study = path_for("study", name)
    if not study.is_file():
        return [f"missing file {study}"]
    if not bullets.is_file():
        return [f"missing file {bullets}"]
    known = source_ids(study.read_text())
    problems = []
    for number, line in enumerate(bullets.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        if UNSEEN_RE.match(line):
            continue
        match = BULLET_RE.match(line)
        if not match:
            problems.append(f"line {number}: not a bullet of the form '- S<n>, ...'")
            continue
        if match.group(1) not in known:
            problems.append(f"line {number}: source {match.group(1)} is not in the study note's Sources")
        if frames:
            for rel in FRAME_PATH_RE.findall(line):
                if ".." in rel.split("/") or not (SKILL_ROOT / rel).is_file():
                    problems.append(f"line {number}: frame {rel} does not exist")
    return problems


def main(argv: List[str]) -> int:
    kind = argv[0] if argv else ""
    frames = False
    args = list(argv[1:])
    if kind == "observations" and "--frames" in args:
        frames = True
        args.remove("--frames")
    wanted = {"study": 1, "pattern": 1, "blueprint": 1, "style": 1, "observations": 2}.get(kind)
    if wanted is None or len(args) != wanted or any(a.startswith("--") for a in args):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not NAME_RE.match(args[0]):
        print(f"invalid name {args[0]!r}: must match [a-z0-9][a-z0-9-]*", file=sys.stderr)
        return 2
    if kind == "observations":
        problems = check_observations(args[0], Path(args[1]), frames)
    else:
        problems = check(kind, args[0])
    for p in problems:
        print(f"{kind} {args[0]}: {p}")
    if not problems:
        print(f"{kind} {args[0]}: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
