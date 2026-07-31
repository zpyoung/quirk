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

import canonical_schema  # noqa: E402
from _common import (  # noqa: E402
    CORE_FIELDS,
    NON_WAIVABLE,
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


# How much a provenance claims. An append that lands weaker content on a stronger destination
# cannot re-label that content -- the canonical form has one provenance slot per field -- so the
# merged field is flagged instead of silently inheriting the destination's stronger claim.
_PROVENANCE_RANK = {"observed": 3, "reported": 2, "inferred": 1, "missing": 0}


def _has_content(entry: dict) -> bool:
    """Whether `entry` already carries a resolved value -- a `missing` field never does."""
    if entry.get("provenance") == "missing":
        return False
    value = entry.get("value")
    return isinstance(value, str) and value.strip() != ""


def _rank(entry: dict) -> int:
    return _PROVENANCE_RANK.get(entry.get("provenance"), 0)


def _can_merge_into(existing: dict, incoming: dict) -> bool:
    """Whether appending `incoming` onto `existing` keeps both provenance claims true.

    A field has exactly one provenance slot and one `source` slot, so an append makes the
    destination's provenance speak for the incoming content too. That is honest only when the
    two claims are *equal*:

    - a weaker incoming (`reported` into `observed`) would assert it was verified, and a
      `missing` one would lose its reason entirely;
    - a stronger incoming (`observed` into `reported`) understates the claim, which is safe on
      its own -- but it strands the incoming's `source`, and `verified_against` cites that
      source, so the drift would produce a document that no longer validates.

    Two locked rules collide here -- the carry-over tables' `append_or_become`, and "every
    carried field keeps the provenance it already had" -- and provenance wins, because it is
    the invariant the renderer enforces rather than a mapping the caller can re-derive.
    """
    return _has_content(incoming) and _rank(incoming) == _rank(existing)


def _merge(existing: dict, incoming: dict, lead_in: str) -> dict:
    merged = dict(existing)
    merged["value"] = f"{existing['value']}\n\n{lead_in}\n{incoming['value']}"
    if incoming.get("needs_confirmation") is True:
        merged["needs_confirmation"] = True
    # two observed claims each cite what verified them, and `verified_against` entries are
    # matched against field sources -- keeping only one would strand the other's citation
    existing_source, incoming_source = existing.get("source"), incoming.get("source")
    if isinstance(incoming_source, str) and incoming_source.strip():
        if not isinstance(existing_source, str) or not existing_source.strip():
            merged["source"] = incoming_source
        elif incoming_source not in existing_source:
            merged["source"] = f"{existing_source}; {incoming_source}"
    return merged


def _retain_beside(mapped: dict, name: str, entry: dict) -> None:
    """Keep `entry` under its own name rather than folding it into a stronger destination."""
    existing = mapped.get(name)
    if existing is None or not _has_content(existing):
        mapped[name] = dict(entry, name=name)
        return
    if _can_merge_into(existing, entry):
        mapped[name] = _merge(existing, dict(entry, name=name), _collision_lead_in(name))
        return
    # its own name is taken by a stronger claim too -- park it rather than drop it, because
    # nothing the user supplied is ever discarded on drift
    suffix = 2
    while f"{name}_{suffix}" in mapped:
        suffix += 1
    mapped[f"{name}_{suffix}"] = dict(entry, name=f"{name}_{suffix}")


def _place(mapped: dict, dest_name: str, entry: dict, lead_in: str, original_name: str) -> None:
    """Put `entry` at `dest_name`, merging rather than overwriting whatever is already there.

    Overwriting is what discards a field: two source entries can land on one destination
    (`environment -> constraints` onto an existing `constraints`, or two entries that simply
    share a name), and "nothing the user supplied is ever discarded on drift" makes the
    already-settled value and the incoming one both survive.
    """
    existing = mapped.get(dest_name)
    if existing is None or not _has_content(existing):
        # nothing settled here yet -- the incoming becomes the destination outright
        mapped[dest_name] = dict(entry, name=dest_name)
        return
    if _can_merge_into(existing, entry):
        mapped[dest_name] = _merge(existing, dict(entry, name=dest_name), lead_in)
        return
    _retain_beside(mapped, original_name, entry)


def _drift_template_fields(template_fields: list, table: list, to: str) -> list:
    """Carry `template.fields` across the same mapping the values took.

    Left behind, the union the emission gate reads still describes the *source* type: the
    destination type's own required fields are never enforced and the source type's are
    reported missing. Rebuilding it here applies the union rule to the new type -- mapped
    entries keep the template's structure and ordering, the destination core is additive,
    and the non-waivable gate overrides both.
    """
    rows = {row["from"]: row for row in table}
    out: dict = {}
    for entry in template_fields:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        row = rows.get(entry["name"])
        dest_name = row["to"] if row is not None else entry["name"]
        required = bool(entry.get("required"))
        if row is not None and row["mode"] == "demote_optional":
            required = False  # dropped from the core; retained as an optional field
        source = entry.get("source") if entry.get("source") in ("template", "core") else "core"

        prev = out.get(dest_name)
        if prev is None:
            out[dest_name] = {"name": dest_name, "required": required, "source": source}
            continue
        # two template entries collapsed onto one destination: a template can add
        # requirements but never subtract them, so requiredness is the union
        prev["required"] = prev["required"] or required
        if source == "template":
            prev["source"] = "template"

    for name in CORE_FIELDS.get(to, []):
        if name not in out:
            out[name] = {"name": name, "required": True, "source": "core"}

    for name in NON_WAIVABLE.get(to, []):
        if name in out:
            out[name]["required"] = True

    return list(out.values())


def apply_drift(doc: dict, to: str) -> dict:
    """Apply the drift carry-over table for `doc["type"]` -> `to` and return a new document.

    Every field the table names is mapped per its row; every field the table doesn't name is
    retained under its original name; nothing is dropped when two of them collide. `doc`
    itself is never mutated.
    """
    table = DRIFT_TABLES[(doc.get("type"), to)]

    source_fields = doc.get("fields")
    if not isinstance(source_fields, list):
        source_fields = []
    # name -> every entry carrying it, not just the last: collapsing to one entry per name
    # silently discards the others, and drift's whole contract is that it discards nothing
    by_name: dict = {}
    for f in source_fields:
        if isinstance(f, dict) and isinstance(f.get("name"), str):
            by_name.setdefault(f["name"], []).append(f)

    mapped: dict = {}
    for row in table:
        for entry in by_name.get(row["from"], []):
            new_entry = dict(entry)
            if row["mode"] == "rename_reopen":
                new_entry["needs_confirmation"] = True
            _place(
                mapped, row["to"], new_entry,
                row.get("lead_in") or _collision_lead_in(row["from"]), row["from"],
            )

    consumed = {row["from"] for row in table}
    for name, entries in by_name.items():
        if name in consumed:
            continue
        for entry in entries:
            _place(mapped, name, entry, _collision_lead_in(name), name)

    new_doc = dict(doc)
    new_doc["type"] = to
    new_doc["fields"] = list(mapped.values())
    # a halt was computed against the *source* type's field set -- carrying it over would block
    # the destination on a field the new type may not even have. Drift is itself the "keep
    # working on it" exit from a halt, so re-deriving is the whole point.
    new_doc.pop("halted", None)

    template = doc.get("template")
    if isinstance(template, dict):
        template_fields = template.get("fields")
        # rebuilt only from a union that already exists -- an absent or empty template.fields
        # means template resolution has not settled yet, and inventing one here would
        # manufacture the very fallback the emission gate exists to refuse
        if isinstance(template_fields, list) and template_fields:
            new_template = dict(template)
            new_template["fields"] = _drift_template_fields(template_fields, table, to)
            new_doc["template"] = new_template
            new_doc["fields"] = _in_union_order(new_doc["fields"], new_template["fields"])

    return new_doc


def _in_union_order(fields: list, union: list) -> list:
    """Reorder carried values to the rebuilt union's order.

    The renderer projects `fields` in document order, and the union is where the template's
    own structure and ordering live -- so leaving the values in carry-table order would emit an
    artifact that ignores the maintainer's section order for no reason other than which row
    happened to fire first. Anything the union doesn't name (a field retained beside a stronger
    destination, say) keeps its relative order and follows behind.
    """
    order = {entry["name"]: i for i, entry in enumerate(union) if isinstance(entry, dict)}
    return sorted(fields, key=lambda f: order.get(f["name"], len(order)))


def _collision_lead_in(name: str) -> str:
    """Lead-in for a merge the tables don't name -- two fields landing on one destination."""
    return f"Also supplied for {name}:"


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

    # Structural validity only -- never --for-emission, since drift routinely fires mid-session
    # before the core fields are resolved. Without this the carry-over silently normalizes a
    # malformed `fields` (an object where an array belongs, say) to empty and reports success,
    # so the user's answers vanish from a document that then looks like a clean drift.
    result = canonical_schema.validate(doc)
    if not result["valid"]:
        print(json.dumps(result, ensure_ascii=False))
        return 3

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
