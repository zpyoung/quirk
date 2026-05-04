#!/usr/bin/env python3
"""Scaffold typed-artifact files into the current project."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

ROOT_TEMPLATES = ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]
ADR_TEMPLATE = TEMPLATES_DIR / "adr" / "0000-record-architecture-decisions.md"
SNIPPET_TEMPLATE = TEMPLATES_DIR / "claude_md_snippet.md"
SNIPPET_MARKER = "<!-- quirk-typed-artifacts:trigger -->"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold typed-artifact files.")
    parser.add_argument("--force", action="store_true",
                        help="Backup and overwrite existing artifacts")
    parser.add_argument("--no-claude-md", action="store_true",
                        help="Do not write/append to CLAUDE.md")
    parser.add_argument("--project-dir", default=".",
                        help="Project root to scaffold into")
    args = parser.parse_args(argv)

    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return 7

    created: list[str] = []
    skipped: list[str] = []

    for name in ROOT_TEMPLATES:
        src = TEMPLATES_DIR / name
        dst = project / name
        if dst.exists() and not args.force:
            skipped.append(name)
            continue
        if dst.exists() and args.force:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy(dst, dst.with_suffix(dst.suffix + f".bak.{stamp}"))
        shutil.copy(src, dst)
        created.append(name)

    adr_dir = project / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr_dst = adr_dir / "0000-record-architecture-decisions.md"
    if not adr_dst.exists() or args.force:
        if adr_dst.exists() and args.force:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy(adr_dst, adr_dst.with_suffix(adr_dst.suffix + f".bak.{stamp}"))
        shutil.copy(ADR_TEMPLATE, adr_dst)
        created.append("docs/adr/0000-record-architecture-decisions.md")
    else:
        skipped.append("docs/adr/0000-record-architecture-decisions.md")

    if not args.no_claude_md:
        claude_md = project / "CLAUDE.md"
        snippet = SNIPPET_TEMPLATE.read_text()
        existing = claude_md.read_text() if claude_md.exists() else ""
        if SNIPPET_MARKER in existing:
            skipped.append("CLAUDE.md (snippet already present)")
        else:
            joiner = "\n\n" if existing and not existing.endswith("\n") else ""
            new_text = existing + joiner + snippet if existing else snippet
            claude_md.write_text(new_text)
            created.append("CLAUDE.md (snippet appended)" if existing else "CLAUDE.md")

    print(f"Created: {', '.join(created) if created else '(none)'}")
    if skipped:
        print(f"Skipped: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
