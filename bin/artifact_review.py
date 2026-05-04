#!/usr/bin/env python3
"""Read-only summary of typed-artifact entries grouped by file."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ARTIFACT_FILES = [
    ("BUGS.md", "BUG"),
    ("DEFERRED.md", "DEFER"),
    ("TEST_BACKLOG.md", "TEST"),
    ("proposals.md", "PROPOSAL"),
]


def parse_entries(text: str, header: str) -> list[dict]:
    """Return list of {id, title, fields} dicts parsed from artifact text."""
    entry_re = re.compile(rf"^##\s+{re.escape(header)}-(\d+):\s*(.+)$", re.MULTILINE)
    field_re = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)

    matches = list(entry_re.finditer(text))
    entries = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        fields = {fm.group(1): fm.group(2).strip() for fm in field_re.finditer(block)}
        entries.append({"id": int(m.group(1)), "title": m.group(2).strip(), "fields": fields})
    return entries


def render_report(project: Path) -> str:
    lines: list[str] = []
    for filename, header in ARTIFACT_FILES:
        path = project / filename
        if not path.exists():
            lines.append(f"## {filename}: file not found")
            continue
        entries = parse_entries(path.read_text(), header)
        if not entries:
            lines.append(f"## {filename}: no entries")
            continue
        lines.append(f"## {filename}: {len(entries)} entries")
        for e in entries:
            sev = e["fields"].get("Severity") or e["fields"].get("Priority") or "-"
            lines.append(f"  - {header}-{e['id']} [{sev}] {e['title']}")
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
