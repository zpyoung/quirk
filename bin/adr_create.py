#!/usr/bin/env python3
"""Create a new ADR file in docs/adr/."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ADR_TEMPLATE = """# {nnnn}. {title}

- **Status:** {status}
- **Date:** {today}

## Context

[neutral, pre-decision facts]

## Decision

[the decision]

## Consequences

[positive / negative / neutral]
"""


def kebab(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return s


def find_max_nnnn(adr_dir: Path) -> int:
    pattern = re.compile(r"^(\d{4})-")
    nums = []
    for f in adr_dir.glob("*.md"):
        m = pattern.match(f.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new ADR file.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--status", default="proposed")
    parser.add_argument("--project-dir", default=".")
    args = parser.parse_args(argv)

    slug = kebab(args.title)
    if not slug:
        print("Title produced empty kebab; provide letters/digits.", file=sys.stderr)
        return 2

    adr_dir = Path(args.project_dir).resolve() / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(3):
        nnnn = f"{find_max_nnnn(adr_dir) + 1 + attempt:04d}"
        target = adr_dir / f"{nnnn}-{slug}.md"
        if not target.exists():
            target.write_text(ADR_TEMPLATE.format(
                nnnn=nnnn, title=args.title, status=args.status,
                today=date.today().isoformat(),
            ))
            print(f"ADR-{nnnn}: {args.title}")
            return 0
    print("Could not allocate ADR number after 3 retries.", file=sys.stderr)
    return 5


if __name__ == "__main__":
    sys.exit(main())
