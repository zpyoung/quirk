#!/usr/bin/env python3
"""Read-only summary of typed-artifact entries grouped by file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from artifact_lib import parse_entries

ARTIFACT_FILES = [
    ("BUGS.md", "BUG"),
    ("DEFERRED.md", "DEFER"),
    ("TEST_BACKLOG.md", "TEST"),
    ("proposals.md", "PROPOSAL"),
]


def render_report(project: Path) -> str:
    lines: list[str] = []
    for filename, header in ARTIFACT_FILES:
        path = project / filename
        if not path.exists():
            lines.append(f"## {filename}: file not found")
            continue
        result = parse_entries(path.read_text(), header)
        entries, malformed = result.entries, result.malformed
        if not entries and not malformed:
            lines.append(f"## {filename}: no entries")
            continue
        lines.append(f"## {filename}: {len(entries) + len(malformed)} entries")
        for e in entries:
            sev = e.fields.get("Severity") or e.fields.get("Priority") or "-"
            lines.append(f"  - {header}-{e.id} [{sev}] {e.title}")
        for m in malformed:
            lines.append(f"  - {header}-{m.id} [malformed heading]: {m.reason}")
    adr_dir = project / "docs" / "adr"
    if adr_dir.exists():
        adrs = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
        lines.append(f"## docs/adr/: {len(adrs)} ADRs")
        for f in adrs:
            lines.append(f"  - {f.name}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize typed-artifact entries.")
    parser.add_argument("--project-dir", default=".")
    args = parser.parse_args(argv)

    project = Path(args.project_dir).resolve()
    print(render_report(project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
