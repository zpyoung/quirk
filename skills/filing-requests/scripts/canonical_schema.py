#!/usr/bin/env python3
"""Validate a filing-requests canonical JSON document against the schema in tech.md.

Invoked directly by filename; there is no separate console-script entry point.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# loaded both as `python3 .../canonical_schema.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling import to _common work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _common import (  # noqa: E402
    CORE_FIELDS,
    NON_WAIVABLE,
    SchemaVersionError,
    check_schema_version,
    read_json_arg,
)

_TARGET_KINDS = ("github", "gitlab", "jira")
_TRI_STATE = ("yes", "no", "unknown")
_VISIBILITY = ("public", "private", "unknown")
_PROVENANCES = ("observed", "reported", "inferred", "missing")
_TYPES = ("bug", "feature", "code-change")
_DEPTHS = ("none", "read", "run")

_EMISSION_REQUIRED_ROOT_KEYS = (
    "schema_version", "type", "headless", "depth", "title", "target",
    "template", "fields", "verified_against", "disclosure_required",
)


def _validate_target(target) -> list:
    if not isinstance(target, dict):
        return [{"path": "target", "message": "target must be an object"}]
    errors = []
    kind = target.get("kind")
    if kind not in _TARGET_KINDS:
        errors.append({"path": "target.kind", "message": f"unknown kind {kind!r}"})
    if kind == "github" and not isinstance(target.get("repo"), str):
        errors.append({"path": "target.repo", "message": "repo is required when kind == 'github'"})
    if not isinstance(target.get("writable"), bool):
        errors.append({"path": "target.writable", "message": "writable is required and must be a boolean"})
    if target.get("third_party") not in _TRI_STATE:
        errors.append({"path": "target.third_party", "message": "third_party must be 'yes', 'no', or 'unknown'"})
    if target.get("visibility") not in _VISIBILITY:
        errors.append({"path": "target.visibility", "message": "visibility must be 'public', 'private', or 'unknown'"})
    return errors


def _validate_template(template) -> list:
    if not isinstance(template, dict):
        return [{"path": "template", "message": "template must be an object"}]
    errors = []
    if not isinstance(template.get("applied"), bool):
        errors.append({"path": "template.applied", "message": "applied is required and must be a boolean"})
    if "path" not in template:
        errors.append({"path": "template.path", "message": "path is required (string or null)"})
    elif template["path"] is not None and not isinstance(template["path"], str):
        errors.append({"path": "template.path", "message": "path must be a string or null"})
    return errors


def _validate_proposed_solution(proposed_solution) -> list:
    if not isinstance(proposed_solution, dict):
        return [{"path": "proposed_solution", "message": "proposed_solution must be an object"}]
    errors = []
    if not isinstance(proposed_solution.get("value"), str):
        errors.append({"path": "proposed_solution.value", "message": "value is required and must be a string"})
    if proposed_solution.get("attributed_to") != "reporter":
        errors.append({"path": "proposed_solution.attributed_to", "message": "attributed_to must be 'reporter'"})
    return errors


def _validate_halted(halted) -> list:
    if not isinstance(halted, dict):
        return [{"path": "halted", "message": "halted must be an object"}]
    errors = []
    if not isinstance(halted.get("field"), str):
        errors.append({"path": "halted.field", "message": "field is required and must be a string"})
    if not isinstance(halted.get("reason"), str):
        errors.append({"path": "halted.reason", "message": "reason is required and must be a string"})
    return errors


def _validate_field(field, index: int) -> list:
    path = f"fields[{index}]"
    if not isinstance(field, dict):
        return [{"path": path, "message": "field entry must be an object"}]

    errors = []
    if not isinstance(field.get("name"), str):
        errors.append({"path": f"{path}.name", "message": "name is required and must be a string"})

    provenance = field.get("provenance")
    if provenance not in _PROVENANCES:
        errors.append({"path": f"{path}.provenance", "message": f"unknown provenance {provenance!r}"})
        return errors  # sibling-key rules below all depend on a recognized provenance

    has_value = "value" in field
    if provenance in ("observed", "reported", "inferred") and not has_value:
        errors.append({"path": f"{path}.value", "message": f"value is required when provenance == '{provenance}'"})
    elif provenance == "missing" and has_value:
        errors.append({"path": f"{path}.value", "message": "value is forbidden when provenance == 'missing'"})

    has_source = "source" in field
    if provenance == "observed" and not has_source:
        errors.append({"path": f"{path}.source", "message": "source is required when provenance == 'observed'"})
    elif provenance != "observed" and has_source:
        errors.append({"path": f"{path}.source", "message": "source is only legal when provenance == 'observed'"})

    has_reason = "reason" in field
    if provenance == "missing" and not has_reason:
        errors.append({"path": f"{path}.reason", "message": "reason is required when provenance == 'missing'"})
    elif provenance != "missing" and has_reason:
        errors.append({"path": f"{path}.reason", "message": "reason is only legal when provenance == 'missing'"})

    if "polarity" in field:
        if field["polarity"] != "negative":
            errors.append({"path": f"{path}.polarity", "message": "polarity must be 'negative' when present"})
        if provenance != "observed":
            errors.append({
                "path": f"{path}.polarity", "message": "polarity is only legal when provenance == 'observed'",
            })

    if "needs_confirmation" in field and not isinstance(field["needs_confirmation"], bool):
        errors.append({"path": f"{path}.needs_confirmation", "message": "needs_confirmation must be a boolean"})

    return errors


def _validate_verified_against(verified_against, fields) -> list:
    errors = []
    sources = [
        f.get("source") for f in fields
        if isinstance(f, dict) and f.get("provenance") == "observed" and isinstance(f.get("source"), str)
    ]
    for i, entry in enumerate(verified_against):
        path = f"verified_against[{i}]"
        if not isinstance(entry, str):
            errors.append({"path": path, "message": "verified_against entries must be strings"})
            continue
        if not any(entry == source or entry in source for source in sources):
            errors.append({"path": path, "message": f"{entry!r} does not match any observed field's source"})
    return errors


def _check_emission_readiness(doc: dict):
    """Return (errors, halted) for the --for-emission core-field-resolution check."""
    errors = []
    halted = None

    for key in _EMISSION_REQUIRED_ROOT_KEYS:
        if key not in doc:
            errors.append({"path": key, "message": "required for emission"})

    doc_type = doc.get("type")
    non_waivable = set(NON_WAIVABLE.get(doc_type, []))
    fields_by_name = {
        f["name"]: f for f in doc.get("fields", []) if isinstance(f, dict) and isinstance(f.get("name"), str)
    }

    for field_name in CORE_FIELDS.get(doc_type, []):
        entry = fields_by_name.get(field_name)
        provenance = entry.get("provenance") if entry else None
        if field_name in non_waivable:
            if halted is not None:
                continue  # report only the first unresolved non-waivable field
            if entry is None or provenance not in ("observed", "reported", "inferred") or "value" not in entry:
                reason = entry.get("reason") if entry and provenance == "missing" else (
                    "no value has been established for this field"
                )
                halted = {"field": field_name, "reason": reason}
        else:
            resolved = entry is not None and (
                (provenance in ("observed", "reported") and "value" in entry)
                or (provenance == "missing" and "reason" in entry)
            )
            if not resolved:
                errors.append({"path": f"fields.{field_name}", "message": "core field is not resolved for emission"})

    return errors, halted


def validate(doc, for_emission: bool = False) -> dict:
    """Validate a canonical document against the filing-requests schema.

    Returns {"valid": bool, "errors": [{"path": str, "message": str}], "halted": None | {...}}.
    """
    if not isinstance(doc, dict):
        return {"valid": False, "errors": [{"path": "", "message": "document must be a JSON object"}], "halted": None}

    errors = []

    if not isinstance(doc.get("schema_version"), int):
        errors.append({"path": "schema_version", "message": "schema_version is required and must be an integer"})

    if "type" in doc and doc["type"] not in _TYPES:
        errors.append({"path": "type", "message": f"unknown type {doc['type']!r}"})

    if "headless" in doc and not isinstance(doc["headless"], bool):
        errors.append({"path": "headless", "message": "headless must be a boolean"})

    if "depth" in doc and doc["depth"] not in _DEPTHS:
        errors.append({"path": "depth", "message": f"unknown depth {doc['depth']!r}"})

    if "title" in doc and not isinstance(doc["title"], str):
        errors.append({"path": "title", "message": "title must be a string"})

    if "target" in doc:
        errors.extend(_validate_target(doc["target"]))

    if "template" in doc:
        errors.extend(_validate_template(doc["template"]))

    fields = doc.get("fields")
    if fields is not None:
        if not isinstance(fields, list):
            errors.append({"path": "fields", "message": "fields must be an array"})
            fields = []
        else:
            for i, field in enumerate(fields):
                errors.extend(_validate_field(field, i))

    if "proposed_solution" in doc:
        errors.extend(_validate_proposed_solution(doc["proposed_solution"]))

    verified_against = doc.get("verified_against")
    if verified_against is not None:
        if not isinstance(verified_against, list):
            errors.append({"path": "verified_against", "message": "verified_against must be an array"})
        else:
            errors.extend(_validate_verified_against(verified_against, fields or []))

    if "disclosure_required" in doc and not isinstance(doc["disclosure_required"], bool):
        errors.append({"path": "disclosure_required", "message": "disclosure_required must be a boolean"})

    if doc.get("halted") is not None:
        errors.extend(_validate_halted(doc["halted"]))

    halted = None
    if for_emission:
        emission_errors, halted = _check_emission_readiness(doc)
        errors.extend(emission_errors)

    return {"valid": len(errors) == 0 and halted is None, "errors": errors, "halted": halted}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a filing-requests canonical JSON document.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--for-emission", action="store_true")
    args = parser.parse_args(argv)

    try:
        doc = read_json_arg(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        check_schema_version(doc)
    except SchemaVersionError as exc:
        print(str(exc), file=sys.stderr)
        return 8

    result = validate(doc, for_emission=args.for_emission)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 3


if __name__ == "__main__":
    sys.exit(main())
