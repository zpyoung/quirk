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
    ATTRIBUTION_LINE,
    DISCLOSURE_FOOTER,
    HEADLESS_BANNER,
    HEDGE_PREFIX,
    SchemaVersionError,
    check_schema_version,
    read_json_arg,
    slugify,
)

# The four fixed wordings live in _common.py (tech.md -> markdown_render.py). They are
# re-exported here because this is the module that renders them, and tests assert them
# through the renderer they belong to.
__all__ = [
    "ATTRIBUTION_LINE", "DISCLOSURE_FOOTER", "HEADLESS_BANNER", "HEDGE_PREFIX", "render", "main",
]

# a slug that survives slugify() unchanged is the only thing that reaches a filename --
# the artifact path is built by joining, so an unsanitized slug is a path-traversal write.
FALLBACK_SLUG = "untitled"


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


class SlugError(ValueError):
    """Raised when an explicit --slug carries nothing a filename can be built from."""


def _artifact_relative_path(doc: dict, slug_override: str | None) -> Path:
    """Compute `docs/quirk/requests/YYYY-MM-DD-<slug>.md`, always a single new filename.

    `--slug` is user input that lands in a path, so it goes through the same `slugify` the
    title does -- separators and `..` segments cannot survive it. An override that slugifies
    to nothing is a usage error rather than a silent write to a different filename; a *title*
    that slugifies to nothing falls back, since the user never chose the filename there.
    """
    if slug_override is not None:
        slug = slugify(slug_override)
        if slug == "":
            raise SlugError(f"--slug {slug_override!r} contains no usable characters")
    else:
        slug = slugify(doc["title"]) or FALLBACK_SLUG
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
        try:
            rel_path = _artifact_relative_path(doc, args.slug)
        except SlugError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        root = Path(args.write).resolve()
        full_path = root / rel_path
        # belt and braces: the slug is already sanitized, so this can only fire if that
        # ever regresses -- and the failure it would catch is an overwrite outside the root.
        if root not in full_path.resolve().parents:
            print(f"refusing to write outside {args.write}: {rel_path}", file=sys.stderr)
            return 2
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
