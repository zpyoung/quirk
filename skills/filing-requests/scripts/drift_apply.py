#!/usr/bin/env python3
"""Apply the bug<->feature drift carry-over tables to a filing-requests canonical document.

Invoked directly by filename, like the other filing-requests scripts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# loaded both as `python3 .../drift_apply.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling import to _common work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _common import (  # noqa: E402
    SchemaVersionError,
    check_schema_version,
    read_json_arg,
)

# tech.md -> Drift carry-over, verbatim. Applied top to bottom with identity mappings first,
# so a later append lands on an already-settled destination rather than racing it.
BUG_TO_FEATURE = [
    {"from": "current_behavior", "to": "current_behavior", "mode": "identity"},
    {
        "from": "steps_to_reproduce", "to": "current_behavior", "mode": "append_or_become",
        "lead_in": "Steps to reproduce (from the original bug report):",
    },
    {"from": "expected_behavior", "to": "acceptance_criteria", "mode": "rename_reopen"},
    {"from": "environment", "to": "constraints", "mode": "identity_rename"},
]

FEATURE_TO_BUG = [
    {"from": "current_behavior", "to": "current_behavior", "mode": "identity"},
    {
        "from": "problem", "to": "current_behavior", "mode": "append_or_become",
        "lead_in": "Problem statement (from the original feature request):",
    },
    {"from": "acceptance_criteria", "to": "expected_behavior", "mode": "identity_rename"},
    {"from": "who_benefits", "to": "affected_users", "mode": "demote_optional"},
]

DRIFT_TABLES = {
    ("bug", "feature"): BUG_TO_FEATURE,
    ("feature", "bug"): FEATURE_TO_BUG,
}


def _has_content(entry: dict) -> bool:
    """Whether `entry` already carries a resolved value -- a `missing` field never does."""
    if entry.get("provenance") == "missing":
        return False
    value = entry.get("value")
    return isinstance(value, str) and value.strip() != ""


def apply_drift(doc: dict, to: str) -> dict:
    """Apply the drift carry-over table for `doc["type"]` -> `to` and return a new document.

    Every field the table names is mapped per its row; every field the table doesn't name is
    retained under its original name. `doc` itself is never mutated.
    """
    table = DRIFT_TABLES[(doc.get("type"), to)]

    source_fields = doc.get("fields")
    if not isinstance(source_fields, list):
        source_fields = []
    by_name = {
        f["name"]: f for f in source_fields
        if isinstance(f, dict) and isinstance(f.get("name"), str)
    }

    mapped: dict = {}
    consumed = set()
    for row in table:
        consumed.add(row["from"])
        entry = by_name.get(row["from"])
        if entry is None:
            continue

        dest_name = row["to"]
        mode = row["mode"]

        if mode == "append_or_become":
            existing = mapped.get(dest_name)
            if existing is not None and _has_content(existing):
                incoming = entry.get("value") or entry.get("reason") or ""
                merged = dict(existing)
                merged["value"] = f"{existing['value']}\n\n{row['lead_in']}\n{incoming}"
                mapped[dest_name] = merged
            else:
                new_entry = dict(entry)
                new_entry["name"] = dest_name
                mapped[dest_name] = new_entry
            continue

        new_entry = dict(entry)
        new_entry["name"] = dest_name
        if mode == "rename_reopen":
            new_entry["needs_confirmation"] = True
        mapped[dest_name] = new_entry

    for name, entry in by_name.items():
        if name not in consumed:
            mapped.setdefault(name, dict(entry))

    new_doc = dict(doc)
    new_doc["type"] = to
    new_doc["fields"] = list(mapped.values())
    return new_doc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply the bug<->feature drift carry-over tables to a canonical document.",
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--to", required=True, choices=("bug", "feature", "code-change"))
    parser.add_argument("--output")
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

    current_type = doc.get("type") if isinstance(doc, dict) else None

    if args.to == current_type:
        print(f"already this type ({args.to!r}); nothing to drift", file=sys.stderr)
        return 2

    if args.to == "code-change":
        print("drift to code-change is not defined; start a fresh session.", file=sys.stderr)
        return 2

    if (current_type, args.to) not in DRIFT_TABLES:
        print(
            f"drift from {current_type!r} to {args.to!r} is not defined; start a fresh session.",
            file=sys.stderr,
        )
        return 2

    new_doc = apply_drift(doc, args.to)

    if args.output:
        Path(args.output).write_text(json.dumps(new_doc, ensure_ascii=False), encoding="utf-8")
    else:
        print(json.dumps(new_doc, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
