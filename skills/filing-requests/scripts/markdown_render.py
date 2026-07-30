#!/usr/bin/env python3
"""Render a filing-requests canonical JSON document into artifact markdown.

Invoked directly by filename; there is no separate console-script entry point.
Rendering is a pure function of the document -- no model in the loop, and no
call to secret_scan.py (that sequencing belongs to the caller).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# loaded both as `python3 .../markdown_render.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling imports work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import canonical_schema  # noqa: E402
from _common import (  # noqa: E402
    SchemaVersionError,
    check_schema_version,
    read_json_arg,
    slugify,
)

# Fixed wording, asserted verbatim in tests -- a change here is a deliberate
# edit with a failing test behind it, not drift.
HEDGE_PREFIX = "Inferred, not directly confirmed — "
ATTRIBUTION_LINE = "*Proposed by the reporter, included as an open suggestion rather than a directive.*"
HEADLESS_BANNER = "> **Headless run: no human confirmed this artifact.**"
DISCLOSURE_FOOTER = "*This report was drafted with AI assistance.*"


def _humanize_field_name(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("_"))


def _render_field(field: dict) -> str:
    provenance = field["provenance"]
    if provenance == "missing":
        body = field["reason"]
    elif provenance == "inferred":
        body = f"{HEDGE_PREFIX}{field['value']}"
    else:  # observed, reported
        body = field["value"]
    return f"## {_humanize_field_name(field['name'])}\n\n{body}"


def render(doc: dict) -> str:
    """Render a canonical filing-requests document to artifact markdown.

    Assumes the caller has already confirmed
    `canonical_schema.validate(doc, for_emission=True)["valid"]` is True --
    this function performs no validation of its own.
    """
    parts = []

    if doc.get("headless"):
        parts.append(HEADLESS_BANNER)

    parts.append(f"# {doc['title']}")

    for field in doc.get("fields", []):
        parts.append(_render_field(field))

    proposed_solution = doc.get("proposed_solution")
    if proposed_solution is not None:
        parts.append(f"## Proposed approach\n\n{ATTRIBUTION_LINE}\n\n{proposed_solution['value']}")

    verified_against = doc.get("verified_against") or []
    if verified_against:
        lines = "\n".join(f"- {entry}" for entry in verified_against)
        parts.append(f"## Verified against\n\n{lines}")

    if doc.get("disclosure_required"):
        parts.append(DISCLOSURE_FOOTER)

    return "\n\n".join(parts) + "\n"


def _today_str() -> str:
    return date.today().isoformat()


def _artifact_relative_path(doc: dict, slug_override: str | None) -> Path:
    slug = slug_override if slug_override else slugify(doc["title"])
    return Path("docs") / "quirk" / "requests" / f"{_today_str()}-{slug}.md"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a filing-requests canonical document to markdown.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--write")
    parser.add_argument("--slug")
    args = parser.parse_args(argv)

    try:
        doc = read_json_arg(args.input)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        check_schema_version(doc)
    except SchemaVersionError as exc:
        print(str(exc), file=sys.stderr)
        return 8

    result = canonical_schema.validate(doc, for_emission=True)
    if not result["valid"]:
        print(json.dumps(result, ensure_ascii=False))
        return 3

    text = render(doc)

    if args.write:
        rel_path = _artifact_relative_path(doc, args.slug)
        full_path = Path(args.write) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(text, encoding="utf-8")
        print(str(rel_path))
    elif args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
