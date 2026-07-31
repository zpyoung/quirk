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

_REDACT_THRESHOLD = 8


def _redact(value) -> str:
    """Redact a document-derived value before it appears in an error message.

    Mirrors secret_scan.py's own redaction shape (first 4 + last 4 chars, ellipsis between)
    so an error message can never be used to exfiltrate what the secret scanner exists to catch.
    """
    text = str(value)
    if len(text) <= _REDACT_THRESHOLD:
        return text
    return f"{text[:4]}…{text[-4:]}"


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_valid_repo(repo) -> bool:
    if not isinstance(repo, str):
        return False
    parts = repo.split("/")
    return len(parts) == 2 and all(parts)


def _validate_target(target) -> list:
    if not isinstance(target, dict):
        return [{"path": "target", "message": "target must be an object"}]
    errors = []
    kind = target.get("kind")
    if kind not in _TARGET_KINDS:
        errors.append({"path": "target.kind", "message": f"unknown kind {_redact(kind)!r}"})
    if kind == "github" and not _is_valid_repo(target.get("repo")):
        errors.append({
            "path": "target.repo",
            "message": "repo is required and must be exactly two non-empty 'owner/repo' segments when kind == 'github'",
        })
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
    if "fields" in template:
        errors.extend(_validate_template_fields(template["fields"]))
    return errors


def _validate_template_fields(fields) -> list:
    if not isinstance(fields, list):
        return [{"path": "template.fields", "message": "template.fields must be an array"}]
    errors = []
    for i, entry in enumerate(fields):
        path = f"template.fields[{i}]"
        if not isinstance(entry, dict):
            errors.append({"path": path, "message": "template field entry must be an object"})
            continue
        if not isinstance(entry.get("name"), str):
            errors.append({"path": f"{path}.name", "message": "name is required and must be a string"})
        if not isinstance(entry.get("required"), bool):
            errors.append({"path": f"{path}.required", "message": "required is required and must be a boolean"})
        if entry.get("source") not in ("template", "core"):
            errors.append({"path": f"{path}.source", "message": "source must be 'template' or 'core'"})
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
        errors.append({"path": f"{path}.provenance", "message": f"unknown provenance {_redact(provenance)!r}"})
        return errors  # sibling-key rules below all depend on a recognized provenance

    if provenance in ("observed", "reported", "inferred"):
        if not _is_nonempty_str(field.get("value")):
            errors.append({
                "path": f"{path}.value",
                "message": f"value is required and must be a non-empty string when provenance == '{provenance}'",
            })
    elif "value" in field:
        errors.append({"path": f"{path}.value", "message": "value is forbidden when provenance == 'missing'"})

    if provenance == "observed":
        if not _is_nonempty_str(field.get("source")):
            errors.append({
                "path": f"{path}.source",
                "message": "source is required and must be a non-empty string when provenance == 'observed'",
            })
    elif "source" in field:
        errors.append({"path": f"{path}.source", "message": "source is only legal when provenance == 'observed'"})

    if provenance == "missing":
        if not _is_nonempty_str(field.get("reason")):
            errors.append({
                "path": f"{path}.reason",
                "message": "reason is required and must be a non-empty string when provenance == 'missing'",
            })
    elif "reason" in field:
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
            errors.append({
                "path": path,
                "message": f"{_redact(entry)!r} does not match any observed field's source",
            })
    return errors


def _resolves_non_waivable(entry) -> bool:
    """Whether `entry` satisfies the non-waivable gate -- stricter than ordinary core resolution.

    Only `observed`/`reported` with a real value counts; `inferred`, `missing`, and a value still
    carrying `needs_confirmation: true` all fail the gate.
    """
    if entry is None or entry.get("needs_confirmation") is True:
        return False
    if entry.get("provenance") not in ("observed", "reported"):
        return False
    return _is_nonempty_str(entry.get("value"))


def _non_waivable_halt_reason(entry) -> str:
    if entry is not None and entry.get("needs_confirmation") is True:
        return "value needs user confirmation before it can be treated as resolved"
    if entry is not None and entry.get("provenance") == "missing":
        reason = entry.get("reason")
        if _is_nonempty_str(reason):
            return reason
    if entry is not None and entry.get("provenance") == "inferred":
        return "an inferred value is not sufficient for a non-waivable field"
    return "no value has been established for this field"


def _stored_halt_reason(doc: dict, field_name: str):
    """The reason a *stored* halt gave for this field, if it named the same one.

    `halted` is derived state -- the gate's own output, which `SKILL.md` writes back when the
    user takes the "save the partial canonical form" exit. So it is recomputed from the fields
    every time rather than trusted: honoring a stored halt unconditionally would leave a resumed
    session blocked forever once the user actually resolved the field it named, with no
    documented way to clear it. What the stored copy is still good for is its *wording* -- the
    session wrote that sentence and showed it to the user -- so it carries over whenever the
    recomputed halt lands on the same field.
    """
    stored = doc.get("halted")
    if not isinstance(stored, dict) or stored.get("field") != field_name:
        return None
    reason = stored.get("reason")
    return reason if isinstance(reason, str) and reason.strip() else None


def _check_emission_readiness(doc: dict, fields: list):
    """Return (errors, halted) for the --for-emission core-field-resolution check.

    `fields` is the caller's already-normalized `doc["fields"]` (an array, possibly empty) --
    `validate()` has already reduced any structurally invalid value to `[]` before this runs.
    """
    errors = []
    halted = None

    for key in _EMISSION_REQUIRED_ROOT_KEYS:
        if key not in doc:
            errors.append({"path": key, "message": "required for emission"})

    # logic.md: "A headless feature request halts with the same non-waivable message rather than
    # emitting a hollow artifact." An unattended process cannot know who benefits or what "done"
    # means, so the type is refused outright rather than field-by-field.
    if halted is None and doc.get("headless") is True and doc.get("type") == "feature":
        halted = {
            "field": "problem",
            "reason": "a headless run cannot establish a feature request's non-waivable fields: "
                      "no human is in session to state the problem or the acceptance criteria",
        }

    # The "verified against" line is assembled from `observed` sources, not written freehand.
    # An observed claim with nothing naming what was checked is an unbacked assertion.
    observed_present = any(
        isinstance(f, dict) and f.get("provenance") == "observed" for f in fields
    )
    if observed_present and not doc.get("verified_against"):
        errors.append({
            "path": "verified_against",
            "message": "at least one field is 'observed'; verified_against must name what was checked",
        })

    template = doc.get("template")
    template_fields = template.get("fields") if isinstance(template, dict) else None
    if not isinstance(template_fields, list) or not template_fields:
        # the union of required fields lives on the document, not the per-type table -- an
        # absent or empty template.fields is a structural error, never a fallback to CORE_FIELDS
        errors.append({
            "path": "template.fields",
            "message": "template.fields is required and non-empty for emission",
        })
        return errors, halted

    doc_type = doc.get("type")
    non_waivable = set(NON_WAIVABLE.get(doc_type, []))
    fields_by_name = {
        f["name"]: f for f in fields if isinstance(f, dict) and isinstance(f.get("name"), str)
    }
    required_names = [
        entry["name"] for entry in template_fields
        if isinstance(entry, dict) and entry.get("required") is True and isinstance(entry.get("name"), str)
    ]

    for field_name in required_names:
        entry = fields_by_name.get(field_name)
        if field_name in non_waivable:
            if halted is not None:
                continue  # report only the first unresolved non-waivable field
            if not _resolves_non_waivable(entry):
                halted = {
                    "field": field_name,
                    "reason": _stored_halt_reason(doc, field_name) or _non_waivable_halt_reason(entry),
                }
        else:
            provenance = entry.get("provenance") if entry else None
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

    schema_version = doc.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        errors.append({"path": "schema_version", "message": "schema_version is required and must be an integer"})

    if "type" in doc and doc["type"] not in _TYPES:
        errors.append({"path": "type", "message": f"unknown type {_redact(doc['type'])!r}"})

    if "headless" in doc and not isinstance(doc["headless"], bool):
        errors.append({"path": "headless", "message": "headless must be a boolean"})

    if "depth" in doc and doc["depth"] not in _DEPTHS:
        errors.append({"path": "depth", "message": f"unknown depth {_redact(doc['depth'])!r}"})

    if "title" in doc and not isinstance(doc["title"], str):
        errors.append({"path": "title", "message": "title must be a string"})

    if "target" in doc:
        errors.extend(_validate_target(doc["target"]))

    if "template" in doc:
        errors.extend(_validate_template(doc["template"]))

    fields = doc.get("fields")
    if "fields" in doc:
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

    if "disclosure_required" in doc:
        if not isinstance(doc["disclosure_required"], bool):
            errors.append({"path": "disclosure_required", "message": "disclosure_required must be a boolean"})
        else:
            target = doc.get("target")
            if isinstance(target, dict):
                visibility = target.get("visibility")
                third_party = target.get("third_party")
                # only derivable once target's own axes are well-formed -- _validate_target
                # already flags a malformed target, so this doesn't pile a confusing second
                # error on top of that one
                if visibility in _VISIBILITY and third_party in _TRI_STATE:
                    expected = (visibility != "private") or (third_party != "no")
                    if doc["disclosure_required"] != expected:
                        errors.append({
                            "path": "disclosure_required",
                            "message": (
                                "disclosure_required must be derived from target: "
                                "(visibility != 'private') or (third_party != 'no')"
                            ),
                        })

    if doc.get("halted") is not None:
        errors.extend(_validate_halted(doc["halted"]))

    halted = None
    if for_emission:
        emission_errors, halted = _check_emission_readiness(doc, fields or [])
        errors.extend(emission_errors)

    return {"valid": len(errors) == 0 and halted is None, "errors": errors, "halted": halted}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a filing-requests canonical JSON document.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--for-emission", action="store_true")
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

    result = validate(doc, for_emission=args.for_emission)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 3


if __name__ == "__main__":
    sys.exit(main())
