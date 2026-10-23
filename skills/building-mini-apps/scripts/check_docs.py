#!/usr/bin/env python3
"""Check that a study note or pattern reference has every required section, in order.

Usage:
    check_docs.py study <app>
    check_docs.py pattern <pattern>

Exits 0 when the document is complete, 1 when it is missing or incomplete (each problem is
printed), and 2 on a usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SKILL_ROOT = Path(__file__).resolve().parent.parent

APPS = ("linear", "things", "raycast", "craft", "obsidian",
        "tableplus", "fantastical", "notion", "granola", "figma",
        "home-assistant", "pagerduty", "incident-io")
PATTERNS = ("list-peek", "expand-in-place", "action-palette", "doc-collections", "workspace-panes",
            "staged-table-edit", "mini-full", "view-switcher", "assisted-notes", "inspector",
            "command-center")

KINDS: Dict[str, Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = {
    "study": ("apps", APPS, ("Sources", "Observations", "Unseen", "Patterns fed")),
    "pattern": ("patterns", PATTERNS, ("When to use", "Anatomy", "Interaction",
                                       "Borrow / Leave out", "Block API", "Sources")),
}

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|(?!\s*-)(.+)\|\s*$", re.MULTILINE)


def sections(text: str) -> List[Tuple[str, str]]:
    """Split a markdown document into (level-2 heading, body) pairs, in document order."""
    matches = list(HEADING_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[m.end():end].strip()))
    return out


def check(kind: str, name: str) -> List[str]:
    """Return the problems found in one document; an empty list means it passes."""
    folder, allowed, required = KINDS[kind]
    if name not in allowed:
        return [f"unknown {kind} name {name!r}; expected one of {', '.join(allowed)}"]
    path = SKILL_ROOT / "references" / folder / f"{name}.md"
    if not path.is_file():
        return [f"missing file {path}"]
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
    return problems


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0] not in KINDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    problems = check(argv[0], argv[1])
    for p in problems:
        print(f"{argv[0]} {argv[1]}: {p}")
    if not problems:
        print(f"{argv[0]} {argv[1]}: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
