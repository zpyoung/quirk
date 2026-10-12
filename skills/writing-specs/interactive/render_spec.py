#!/usr/bin/env python3
"""Render and fold interactive logic-spec review data (Python 3.9+, stdlib only)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import webbrowser
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PAYLOAD_PLACEHOLDER = '<script type="application/json" id="quirk-logic-spec-payload">null</script>'
PAYLOAD_OPEN = '<script type="application/json" id="quirk-logic-spec-payload">'
PAYLOAD_CLOSE = "</script>"
EXPORT_KIND = "quirk-logic-spec-decisions"
RENDER_OUTPUT_FIELDS = {"reviewReason", "ruling", "rulingNote", "acceptance"}
RENDER_OUTPUT_FIELDS_V2 = RENDER_OUTPUT_FIELDS | {
    "dropReason",
    "reopened",
    "reapprovedHash",
    "originalText",
    "rejectReason",
    "researchRequest",
    "originalCertainty",
    # a reviewer's bookmark, not content, so toggling it must never look like a changed item
    "flagged",
    # marks a comment as handled without touching the scenario, so it must not reset decisions either
    "answeredComment",
}
SCOPE_CONDITIONS = ("no-code", "under-10", "under-30")
PLACEMENTS = ("in", "conditional", "out")
RULINGS = ("build-on", "verify-first", "wrong")
CERTAINTIES = ("confirmed", "assumed", "unverified")
SCENARIO_CHOICES = ("spec", "custom")
CONSTRAINT_KINDS = ("placement", "verification", "naming", "non-goal", "other")
CONSTRAINT_RULINGS = ("approved", "rewritten", "rejected")
CONSTRAINT_STATE_RULINGS = ("approve", "rewrite", "reject")
DISPUTE_KINDS = ("derivation", "scenario")
REQUIREMENT_GROUPS = ("min", "i3", "i2", "i1")
STAGE1_ITEM_KINDS = ("behaviors", "scenarios", "constraints", "assumptions", "blindSpots")
EXIT6_MESSAGE = (
    "read-only v1 spec: page review, check-export, reapprove, and fold are refused; "
    "amend logic.json and re-render"
)
UNSAFE_OBJECT_IDS = frozenset(
    (
        "__proto__",
        "constructor",
        "prototype",
        "hasOwnProperty",
        "isPrototypeOf",
        "propertyIsEnumerable",
        "toLocaleString",
        "toString",
        "valueOf",
        "__defineGetter__",
        "__defineSetter__",
        "__lookupGetter__",
        "__lookupSetter__",
    )
)
COMPARISON_KIND = "quirk-approach-comparison"
COMPARE_EXPORT_KIND = "quirk-approach-comparison-challenges"
UNSIGNED_COMPARISON_WARNING = "comparison.json ignored: stage 3 waits for stage-2 sign-off"
COMPARE_EXPORT_REFUSAL = "stage-3 exports carry challenges, not decisions; use check-export or challenges"
# size label -> (low, high) points; shared by validation and the app's effort display
POINT_MAP: Dict[str, Tuple[int, int]] = {
    "S": (2, 2),
    "S-M": (2, 3),
    "M": (3, 3),
    "M-L": (3, 5),
    "L": (5, 5),
    "L-XL": (5, 8),
    "XL": (8, 8),
}
SCORE_STATUSES = ("met", "met with workaround", "very hard", "not met")
SLICE_BANDS = ("v1", "fast-follow", "optional")
FLOW_KINDS = ("new", "changed", "reused")
MESSAGE_KINDS = ("call", "return", "async", "focal")
TABLE_STATUSES = ("new", "changed", "existing")
COLUMN_CHIPS = ("PK", "FK", "UQ")
REF_KINDS = ("fk", "json")
DEPLOY_STATUSES = ("stated", "implied", "not-stated")
HISTORY_OUTCOMES = ("revised", "held")
FINDING_TYPES = ("disputes", "same score, different design")
CONFIDENCE_LEVELS = ("low", "medium", "high")
COMPARE_TAB_KEYS = ("overview", "approaches", "effort", "blast", "tradeoffs")
SEQUENCE_MAX_PARTICIPANTS = 5
SEQUENCE_MAX_MESSAGES = 12
SCHEMA_MAX_TABLES = 5
SCHEMA_MAX_REFS = 6


class Validator:
    """Small schema validator that reports every actionable JSON-pointer error."""

    def __init__(self) -> None:
        self.errors: List[Tuple[str, str]] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append((path or "/", message))

    def field(self, value: Any, key: str, path: str) -> Any:
        if not isinstance(value, dict):
            return None
        if key not in value:
            self.error(pointer(path, key), "required key is missing")
            return None
        return value[key]

    def object(self, value: Any, path: str) -> Optional[dict]:
        if not isinstance(value, dict):
            self.error(path or "/", "expected an object")
            return None
        return value

    def array(self, value: Any, path: str) -> Optional[list]:
        if not isinstance(value, list):
            self.error(path or "/", "expected an array")
            return None
        return value

    def string(self, value: Any, path: str, nonempty: bool = False) -> bool:
        if not isinstance(value, str):
            self.error(path or "/", "expected a string")
            return False
        if nonempty and not value.strip():
            self.error(path or "/", "must not be empty")
            return False
        return True

    def identifier(self, value: Any, path: str) -> bool:
        if not self.string(value, path, nonempty=True):
            return False
        if value in UNSAFE_OBJECT_IDS:
            self.error(path or "/", "reserved JavaScript object property is not a safe id")
            return False
        return True

    def boolean(self, value: Any, path: str) -> bool:
        if type(value) is not bool:
            self.error(path or "/", "expected a boolean")
            return False
        return True

    def enum(self, value: Any, choices: Sequence[str], path: str) -> bool:
        if not isinstance(value, str) or value not in choices:
            self.error(path or "/", "expected one of: " + ", ".join(choices))
            return False
        return True

    def string_array(self, value: Any, path: str, nonempty_items: bool = False) -> Optional[list]:
        result = self.array(value, path)
        if result is None:
            return None
        for index, item in enumerate(result):
            self.string(item, pointer(path, index), nonempty=nonempty_items)
        return result

    def iso_datetime(self, value: Any, path: str) -> bool:
        if not self.string(value, path, nonempty=True):
            return False
        try:
            parse_iso_datetime(value)
        except (TypeError, ValueError, OverflowError):
            self.error(path or "/", "expected an ISO 8601 date-time")
            return False
        return True

    def exact_version(self, value: Any, path: str, allowed: Sequence[int] = (1,)) -> bool:
        if type(value) is not int or value not in allowed:
            choices = " or ".join(str(item) for item in sorted(allowed))
            self.error(path or "/", "expected schema version " + choices)
            return False
        return True


def pointer(path: str, part: Any) -> str:
    escaped = str(part).replace("~", "~0").replace("/", "~1")
    return (path if path else "") + "/" + escaped


def parse_iso_datetime(value: str) -> datetime:
    if "T" not in value and "t" not in value:
        raise ValueError("date-time separator is missing")
    # fromisoformat accepted trailing Z only in newer Python releases.
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render_id(logic: dict) -> str:
    try:
        return sha256(canonical_json(logic).encode("utf-8")).hexdigest()[:12]
    except RecursionError:
        raise ValueError("logic.json is too deeply nested to render")


def item_hashes(logic: dict) -> Dict[str, str]:
    is_v2 = logic.get("schemaVersion") == 2
    fields = RENDER_OUTPUT_FIELDS_V2 if is_v2 else RENDER_OUTPUT_FIELDS
    keys = (
        ("requirements", "assumptions", "blindSpots", "scenarios", "behaviors", "constraints")
        if is_v2
        else ("requirements", "assumptions", "blindSpots", "scenarios")
    )
    hashes: Dict[str, str] = {}
    for key in keys:
        for item in logic.get(key, []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            clean = {name: value for name, value in item.items() if name not in fields}
            hashes[item["id"]] = sha256(canonical_json(clean).encode("utf-8")).hexdigest()
    return hashes


def stage1_item_hashes(logic: dict) -> Dict[str, str]:
    """The stage-1Pin subset of item_hashes: behaviors, scenarios, constraints, assumptions, blindSpots."""
    stage1_ids = {
        item["id"]
        for kind in STAGE1_ITEM_KINDS
        for item in logic.get(kind, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    return {ident: value for ident, value in item_hashes(logic).items() if ident in stage1_ids}


def _required(v: Validator, obj: dict, key: str, path: str) -> Any:
    return v.field(obj, key, path)


def _string_field(v: Validator, obj: dict, key: str, path: str, nonempty: bool = False) -> Any:
    value = _required(v, obj, key, path)
    if key in obj:
        v.string(value, pointer(path, key), nonempty=nonempty)
    return value


def _id_field(v: Validator, obj: dict, key: str, path: str) -> Any:
    value = _required(v, obj, key, path)
    if key in obj:
        v.identifier(value, pointer(path, key))
    return value


def _string_list_field(v: Validator, obj: dict, key: str, path: str) -> Any:
    value = _required(v, obj, key, path)
    if key in obj:
        v.string_array(value, pointer(path, key), nonempty_items=True)
    return value


def _record_ids(v: Validator, objects: Iterable[Any], path: str, ids: Dict[str, str]) -> None:
    for index, raw in enumerate(objects):
        if not isinstance(raw, dict):
            continue
        ident = raw.get("id")
        if not isinstance(ident, str) or not ident:
            continue
        ident_path = pointer(pointer(path, index), "id")
        previous = ids.get(ident)
        if previous is not None:
            v.error(ident_path, "duplicate id; first used at " + previous)
        else:
            ids[ident] = ident_path


def validate_logic(logic: Any) -> List[Tuple[str, str]]:
    v = Validator()
    root = v.object(logic, "")
    if root is None:
        return v.errors

    version = _required(v, root, "schemaVersion", "")
    if "schemaVersion" in root:
        v.exact_version(version, "/schemaVersion")
    _string_field(v, root, "title", "", nonempty=True)
    _string_field(v, root, "status", "")

    amendments = _required(v, root, "amendments", "")
    amendments_path = "/amendments"
    if "amendments" in root:
        rows = v.array(amendments, amendments_path)
        if rows is not None:
            for index, row in enumerate(rows):
                path = pointer(amendments_path, index)
                item = v.object(row, path)
                if item is None:
                    continue
                day = _string_field(v, item, "date", path, nonempty=True)
                if "date" in item and isinstance(day, str):
                    try:
                        if date.fromisoformat(day).isoformat() != day:
                            raise ValueError
                    except ValueError:
                        v.error(pointer(path, "date"), 'expected a date in "YYYY-MM-DD" format')
                _string_field(v, item, "text", path)

    sections = _required(v, root, "sections", "")
    if "sections" in root:
        section_obj = v.object(sections, "/sections")
        if section_obj is not None:
            for key in ("purpose", "conceptualModel", "dataFlow"):
                _string_field(v, section_obj, key, "/sections")
            for key, fields in (
                ("decisionsLocked", ("area", "decision")),
                ("industryInsights", ("finding", "sources")),
                ("deferredIdeas", ("text", "techSpec")),
                ("glossary", ("term", "definition")),
            ):
                raw = _required(v, section_obj, key, "/sections")
                if key not in section_obj:
                    continue
                values = v.array(raw, pointer("/sections", key))
                if values is None:
                    continue
                for index, value in enumerate(values):
                    path = pointer(pointer("/sections", key), index)
                    item = v.object(value, path)
                    if item is None:
                        continue
                    for field in fields:
                        field_value = _required(v, item, field, path)
                        if field not in item:
                            continue
                        if field == "sources":
                            v.string_array(field_value, pointer(path, field))
                        elif field == "techSpec":
                            v.boolean(field_value, pointer(path, field))
                        else:
                            v.string(field_value, pointer(path, field))
            non_goals = _required(v, section_obj, "scopeNonGoals", "/sections")
            if "scopeNonGoals" in section_obj:
                v.string_array(non_goals, "/sections/scopeNonGoals")

    requirement_rows = _required(v, root, "requirements", "")
    requirements: List[Any] = []
    if "requirements" in root:
        rows = v.array(requirement_rows, "/requirements")
        if rows is not None:
            requirements = rows
            for index, raw in enumerate(rows):
                path = pointer("/requirements", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("area", "text", "summary", "detail"):
                    _string_field(v, item, key, path)
                if "scope" in item:
                    v.enum(item["scope"], ("in", "out"), pointer(path, "scope"))
                else:
                    _required(v, item, "scope", path)
                if "group" in item:
                    v.enum(item["group"], ("min", "i3", "i2", "i1"), pointer(path, "group"))
                else:
                    _required(v, item, "group", path)
                if "provenance" in item:
                    v.enum(item["provenance"], ("you-chose", "you-recommended", "claude"), pointer(path, "provenance"))
                else:
                    _required(v, item, "provenance", path)
                if item.get("provenance") == "claude" and "rationale" not in item:
                    v.error(pointer(path, "rationale"), "required when provenance is claude")
                elif "rationale" in item:
                    v.string(item["rationale"], pointer(path, "rationale"))
                if item.get("provenance") in ("you-chose", "you-recommended") and "question" not in item:
                    v.error(pointer(path, "question"), "required unless provenance is claude")
                elif "question" in item:
                    v.string(item["question"], pointer(path, "question"))
                if "certainty" in item:
                    certainty = item["certainty"]
                    if certainty is not None:
                        v.enum(certainty, CERTAINTIES, pointer(path, "certainty"))
                else:
                    _required(v, item, "certainty", path)
                _string_list_field(v, item, "dependsOn", path)
                if "condition" in item:
                    v.enum(item["condition"], SCOPE_CONDITIONS, pointer(path, "condition"))
                    if item.get("scope") != "in":
                        v.error(pointer(path, "condition"), 'only valid when scope is "in"')
                if "reviewReason" in item:
                    v.string(item["reviewReason"], pointer(path, "reviewReason"))

    assumptions = _required(v, root, "assumptions", "")
    assumption_rows: List[Any] = []
    if "assumptions" in root:
        rows = v.array(assumptions, "/assumptions")
        if rows is not None:
            assumption_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/assumptions", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("claim", "basis", "ifWrong", "meaning", "check", "checkCost"):
                    _string_field(v, item, key, path)
                if "certainty" in item:
                    v.enum(item["certainty"], CERTAINTIES, pointer(path, "certainty"))
                else:
                    _required(v, item, "certainty", path)
                _string_list_field(v, item, "affects", path)
                if "ruling" in item:
                    v.enum(item["ruling"], RULINGS, pointer(path, "ruling"))
                if "rulingNote" in item:
                    v.string(item["rulingNote"], pointer(path, "rulingNote"))

    blind_spots = _required(v, root, "blindSpots", "")
    blind_rows: List[Any] = []
    if "blindSpots" in root:
        rows = v.array(blind_spots, "/blindSpots")
        if rows is not None:
            blind_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/blindSpots", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("title", "detail"):
                    _string_field(v, item, key, path)
                _string_list_field(v, item, "sources", path)
                if "resolvedBy" in item:
                    _id_field(v, item, "resolvedBy", path)
                if "acceptance" in item:
                    v.string(item["acceptance"], pointer(path, "acceptance"))

    scenarios = _required(v, root, "scenarios", "")
    scenario_rows: List[Any] = []
    if "scenarios" in root:
        rows = v.array(scenarios, "/scenarios")
        if rows is not None:
            scenario_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/scenarios", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("given", "when", "then", "explanation"):
                    _string_field(v, item, key, path)
                alternatives = _required(v, item, "alternatives", path)
                if "alternatives" in item:
                    v.string_array(alternatives, pointer(path, "alternatives"))
                _string_list_field(v, item, "refs", path)
                if "requestId" in item:
                    _id_field(v, item, "requestId", path)

    conflicts = _required(v, root, "conflicts", "")
    conflict_rows: List[Any] = []
    if "conflicts" in root:
        rows = v.array(conflicts, "/conflicts")
        if rows is not None:
            conflict_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/conflicts", index)
                pair = v.array(raw, path)
                if pair is None:
                    continue
                if len(pair) != 2:
                    v.error(path, "expected a pair of requirement ids")
                for part_index, ident in enumerate(pair):
                    v.string(ident, pointer(path, part_index), nonempty=True)
                if len(pair) == 2 and pair[0] == pair[1]:
                    v.error(path, "conflict must name two distinct requirements")

    research = _required(v, root, "research", "")
    research_rows: List[Any] = []
    if "research" in root:
        rows = v.array(research, "/research")
        if rows is not None:
            research_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/research", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "requestId", path)
                _id_field(v, item, "blindSpotId", path)
                for key in ("summary", "detail"):
                    _string_field(v, item, key, path)
                value = _required(v, item, "answeredAt", path)
                if "answeredAt" in item:
                    v.iso_datetime(value, pointer(path, "answeredAt"))

    ids: Dict[str, str] = {}
    req_ids: set = set()
    blind_ids: set = set()
    state_ids: set = set()
    entry_ids: set = set()
    _record_ids(v, requirements, "/requirements", ids)
    _record_ids(v, assumption_rows, "/assumptions", ids)
    _record_ids(v, blind_rows, "/blindSpots", ids)
    _record_ids(v, scenario_rows, "/scenarios", ids)
    req_ids.update(item.get("id") for item in requirements if isinstance(item, dict) and isinstance(item.get("id"), str))
    blind_ids.update(item.get("id") for item in blind_rows if isinstance(item, dict) and isinstance(item.get("id"), str))
    for index, item in enumerate(research_rows):
        if isinstance(item, dict):
            ident = item.get("requestId")
            if isinstance(ident, str) and ident:
                id_path = pointer(pointer("/research", index), "requestId")
                if ident in ids:
                    v.error(id_path, "duplicate id; first used at " + ids[ident])
                else:
                    ids[ident] = id_path

    views = root.get("views")
    if "views" in root:
        view_obj = v.object(views, "/views")
        if view_obj is not None:
            if "stateMachine" in view_obj:
                machine = v.object(view_obj["stateMachine"], "/views/stateMachine")
                if machine is not None:
                    states_raw = _required(v, machine, "states", "/views/stateMachine")
                    states: List[Any] = []
                    if "states" in machine:
                        values = v.array(states_raw, "/views/stateMachine/states")
                        if values is not None:
                            states = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/states", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _string_field(v, item, "label", path)
                                _string_field(v, item, "detail", path)
                                if "focal" in item:
                                    v.boolean(item["focal"], pointer(path, "focal"))
                    entries: List[Any] = []
                    if "entries" in machine:
                        values = v.array(machine["entries"], "/views/stateMachine/entries")
                        if values is not None:
                            entries = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/entries", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _string_field(v, item, "label", path)
                    transitions_raw = _required(v, machine, "transitions", "/views/stateMachine")
                    transitions: List[Any] = []
                    if "transitions" in machine:
                        values = v.array(transitions_raw, "/views/stateMachine/transitions")
                        if values is not None:
                            transitions = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/transitions", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _id_field(v, item, "from", path)
                                _id_field(v, item, "to", path)
                                _string_field(v, item, "short", path)
                                _string_field(v, item, "event", path)
                                _string_list_field(v, item, "reqs", path)
                                if "blindSpot" in item:
                                    _id_field(v, item, "blindSpot", path)
                    _record_ids(v, states, "/views/stateMachine/states", ids)
                    _record_ids(v, entries, "/views/stateMachine/entries", ids)
                    _record_ids(v, transitions, "/views/stateMachine/transitions", ids)
                    state_ids.update(item.get("id") for item in states if isinstance(item, dict) and isinstance(item.get("id"), str))
                    entry_ids.update(item.get("id") for item in entries if isinstance(item, dict) and isinstance(item.get("id"), str))
            if "storyMap" in view_obj:
                story = v.object(view_obj["storyMap"], "/views/storyMap")
                if story is not None:
                    journey_raw = _required(v, story, "journey", "/views/storyMap")
                    if "journey" in story:
                        journey = v.array(journey_raw, "/views/storyMap/journey")
                        if journey is not None:
                            for index, raw in enumerate(journey):
                                path = pointer("/views/storyMap/journey", index)
                                item = v.object(raw, path)
                                if item is not None:
                                    _string_field(v, item, "area", path)
                                    _string_field(v, item, "label", path)
                    cross = _required(v, story, "crossCutting", "/views/storyMap")
                    if "crossCutting" in story:
                        v.string_array(cross, "/views/storyMap/crossCutting")

    if "signoff" in root:
        signoff = v.object(root["signoff"], "/signoff")
        if signoff is not None:
            signed_at = _required(v, signoff, "signedAt", "/signoff")
            if "signedAt" in signoff:
                v.iso_datetime(signed_at, "/signoff/signedAt")
            _string_field(v, signoff, "renderId", "/signoff", nonempty=True)

    for index, raw in enumerate(requirements):
        if isinstance(raw, dict):
            for j, ident in enumerate(raw.get("dependsOn", []) if isinstance(raw.get("dependsOn"), list) else []):
                if isinstance(ident, str) and ident not in req_ids:
                    v.error(pointer(pointer(pointer("/requirements", index), "dependsOn"), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(assumption_rows):
        if isinstance(raw, dict):
            for j, ident in enumerate(raw.get("affects", []) if isinstance(raw.get("affects"), list) else []):
                if isinstance(ident, str) and ident not in req_ids:
                    v.error(pointer(pointer(pointer("/assumptions", index), "affects"), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(blind_rows):
        if isinstance(raw, dict):
            for key in ("sources", "resolvedBy"):
                refs = raw.get(key, []) if key == "sources" else ([raw[key]] if key in raw else [])
                for j, ident in enumerate(refs if isinstance(refs, list) else []):
                    if isinstance(ident, str) and ident not in req_ids:
                        ref_path = pointer(pointer("/blindSpots", index), key)
                        v.error(pointer(ref_path, j) if key == "sources" else ref_path, "unknown requirement id: " + ident)
    for index, raw in enumerate(scenario_rows):
        if isinstance(raw, dict):
            for j, ident in enumerate(raw.get("refs", []) if isinstance(raw.get("refs"), list) else []):
                if isinstance(ident, str) and ident not in req_ids:
                    v.error(pointer(pointer(pointer("/scenarios", index), "refs"), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(conflict_rows):
        if isinstance(raw, list) and len(raw) == 2:
            for j, ident in enumerate(raw):
                if isinstance(ident, str) and ident not in req_ids:
                    v.error(pointer(pointer("/conflicts", index), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(research_rows):
        if isinstance(raw, dict):
            ident = raw.get("blindSpotId")
            if isinstance(ident, str) and ident not in blind_ids:
                v.error(pointer(pointer("/research", index), "blindSpotId"), "unknown blind spot id: " + ident)
    if "views" in root and isinstance(root.get("views"), dict):
        machine = root["views"].get("stateMachine")
        if isinstance(machine, dict):
            states = machine.get("states", []) if isinstance(machine.get("states"), list) else []
            entries = machine.get("entries", []) if isinstance(machine.get("entries"), list) else []
            transitions = machine.get("transitions", []) if isinstance(machine.get("transitions"), list) else []
            valid_from = state_ids | entry_ids
            for index, raw in enumerate(transitions):
                if not isinstance(raw, dict):
                    continue
                for key, valid in (("from", valid_from), ("to", state_ids)):
                    ident = raw.get(key)
                    if isinstance(ident, str) and ident not in valid:
                        v.error(pointer(pointer("/views/stateMachine/transitions", index), key), "unknown state or entry id: " + ident)
                for j, ident in enumerate(raw.get("reqs", []) if isinstance(raw.get("reqs"), list) else []):
                    if isinstance(ident, str) and ident not in req_ids:
                        v.error(pointer(pointer(pointer("/views/stateMachine/transitions", index), "reqs"), j), "unknown requirement id: " + ident)
                ident = raw.get("blindSpot")
                if isinstance(ident, str) and ident not in blind_ids:
                    v.error(pointer(pointer("/views/stateMachine/transitions", index), "blindSpot"), "unknown blind spot id: " + ident)

    return v.errors


def _validate_provenance(v: Validator, item: dict, path: str) -> None:
    """Shared provenance/rationale/question rule for v2 scenarios and constraints."""
    if "provenance" in item:
        v.enum(item["provenance"], ("you-chose", "you-recommended", "claude"), pointer(path, "provenance"))
    else:
        _required(v, item, "provenance", path)
    if item.get("provenance") == "claude" and "rationale" not in item:
        v.error(pointer(path, "rationale"), "required when provenance is claude")
    elif "rationale" in item:
        v.string(item["rationale"], pointer(path, "rationale"))
    if item.get("provenance") in ("you-chose", "you-recommended") and "question" not in item:
        v.error(pointer(path, "question"), "required unless provenance is claude")
    elif "question" in item:
        v.string(item["question"], pointer(path, "question"))


CUSTOM_COLUMN_TYPES = ("text", "markdown", "items", "status", "quote")
STATUS_COLORS = ("green", "yellow", "orange", "red", "blue", "default")


def _required_array(v: Validator, obj: dict, key: str, path: str) -> Optional[list]:
    raw = _required(v, obj, key, path)
    return v.array(raw, pointer(path, key)) if key in obj else None


def _validate_custom_views(v: Validator, raw: Any, item_ids: set) -> None:
    """Each custom view is a task-specific table: typed columns, and rows whose cells match their column's type."""
    views = v.array(raw, "/views/custom") or []
    _record_ids(v, views, "/views/custom", {})
    for view_index, view_raw in enumerate(views):
        base = pointer("/views/custom", view_index)
        view = v.object(view_raw, base)
        if view is None:
            continue
        _id_field(v, view, "id", base)
        _string_field(v, view, "title", base, nonempty=True)
        if "intro" in view:
            v.string(view["intro"], pointer(base, "intro"))
        columns: Dict[str, str] = {}
        column_rows = _required_array(v, view, "columns", base)
        for index, column_raw in enumerate(column_rows or []):
            path = pointer(pointer(base, "columns"), index)
            column = v.object(column_raw, path)
            if column is None:
                continue
            key = _id_field(v, column, "key", path)
            _string_field(v, column, "label", path, nonempty=True)
            kind = _required(v, column, "type", path)
            if "type" in column:
                v.enum(kind, CUSTOM_COLUMN_TYPES, pointer(path, "type"))
            if isinstance(key, str) and key:
                if key in columns:
                    v.error(pointer(path, "key"), "duplicate column key: " + key)
                columns[key] = kind if isinstance(kind, str) else ""
            if "statuses" in column:
                statuses = v.object(column["statuses"], pointer(path, "statuses"))
                for value, color in (statuses or {}).items():
                    v.enum(color, STATUS_COLORS, pointer(pointer(path, "statuses"), value))
        for index, column_raw in enumerate(column_rows or []):
            if not isinstance(column_raw, dict):
                continue
            path = pointer(pointer(base, "columns"), index)
            target = column_raw.get("checkedAgainst")
            if column_raw.get("type") == "quote":
                if target is None:
                    v.error(pointer(path, "checkedAgainst"), "required for a quote column")
                elif not isinstance(target, str) or columns.get(target) != "items":
                    v.error(pointer(path, "checkedAgainst"), "must name an items column in this view")
            elif target is not None:
                v.error(pointer(path, "checkedAgainst"), "only allowed on a quote column")
        row_rows = _required_array(v, view, "rows", base) or []
        _record_ids(v, row_rows, pointer(base, "rows"), {})
        for index, row_raw in enumerate(row_rows):
            path = pointer(pointer(base, "rows"), index)
            row = v.object(row_raw, path)
            if row is None:
                continue
            _string_field(v, row, "id", path, nonempty=True)
            cells_raw = _required(v, row, "cells", path)
            cells = v.object(cells_raw, pointer(path, "cells")) if "cells" in row else None
            for key, cell in (cells or {}).items():
                cell_path = pointer(pointer(path, "cells"), key)
                if key not in columns:
                    v.error(cell_path, "unknown column key: " + key)
                    continue
                if columns[key] == "items":
                    ids = v.array(cell, cell_path)
                    for j, item in enumerate(ids or []):
                        if v.string(item, pointer(cell_path, j), nonempty=True) and item not in item_ids:
                            v.error(pointer(cell_path, j), "unknown logic item id: " + item)
                elif isinstance(cell, dict):
                    _string_field(v, cell, "text", cell_path)
                    if "certainty" in cell:
                        v.enum(cell["certainty"], CERTAINTIES, pointer(cell_path, "certainty"))
                else:
                    v.string(cell, cell_path)


def _quotable_text(root: dict, ident: str) -> Optional[str]:
    """Mirrors the page's quotable text for an item id."""
    fields = {
        "scenarios": lambda item: [item["given"], item["when"], item["then"], *item["alternatives"]],
        "requirements": lambda item: [item["text"], item["summary"], item["detail"]],
        "constraints": lambda item: [item["text"]],
        "behaviors": lambda item: [item["rule"], item.get("detail", "")],
        "assumptions": lambda item: [item["claim"], item["basis"], item["meaning"]],
        "blindSpots": lambda item: [item["title"], item["detail"]],
    }
    for kind, pick in fields.items():
        for item in root.get(kind, []):
            if item.get("id") == ident:
                return "\n".join(pick(item))
    return None


def quote_pattern(text: str) -> "re.Pattern[str]":
    """`<...>` in a quote is a placeholder matching any text; the page applies the same rule."""
    return re.compile(".+?".join(re.escape(part) for part in re.split(r"<[^>]+>", text)))


def custom_view_quote_warnings(root: dict) -> List[str]:
    """One warning per quote cell whose checked items word it differently; drift is a review finding, not an error."""
    warnings: List[str] = []
    for view in root.get("views", {}).get("custom", []):
        for column in view["columns"]:
            if column["type"] != "quote":
                continue
            for row in view["rows"]:
                cell = row["cells"].get(column["key"])
                text = cell["text"] if isinstance(cell, dict) else cell
                if not text:
                    continue
                pattern = quote_pattern(text)
                drift = [
                    ident
                    for ident in row["cells"].get(column["checkedAgainst"], [])
                    if (source := _quotable_text(root, ident)) is not None and not pattern.search(source)
                ]
                if drift:
                    warnings.append(
                        "warning: custom view " + view["id"] + " row " + row["id"] + ": worded differently in " + ", ".join(drift)
                    )
    return warnings


def validate_logic_v2(logic: dict) -> Tuple[List[Tuple[str, str]], List[str]]:
    v = Validator()
    root = logic
    warnings: List[str] = []

    _string_field(v, root, "title", "", nonempty=True)

    stage: Optional[int] = None
    if "stage" not in root:
        v.error("/stage", "required key is missing")
    elif type(root["stage"]) is not int or root["stage"] not in (1, 2):
        v.error("/stage", "expected 1 or 2")
    else:
        stage = root["stage"]

    status = _string_field(v, root, "status", "")
    if stage is not None and "status" in root and isinstance(status, str):
        if stage == 1 and status != "Draft":
            v.error("/status", 'expected "Draft" in stage 1')
        elif stage == 2 and status != "Stage 1 approved" and not status.startswith("Approved"):
            v.error("/status", 'expected "Stage 1 approved" or a status starting with "Approved" in stage 2')

    amendments = _required(v, root, "amendments", "")
    if "amendments" in root:
        rows = v.array(amendments, "/amendments")
        if rows is not None:
            for index, row in enumerate(rows):
                path = pointer("/amendments", index)
                item = v.object(row, path)
                if item is None:
                    continue
                day = _string_field(v, item, "date", path, nonempty=True)
                if "date" in item and isinstance(day, str):
                    try:
                        if date.fromisoformat(day).isoformat() != day:
                            raise ValueError
                    except ValueError:
                        v.error(pointer(path, "date"), 'expected a date in "YYYY-MM-DD" format')
                _string_field(v, item, "text", path)

    sections = _required(v, root, "sections", "")
    if "sections" in root:
        section_obj = v.object(sections, "/sections")
        if section_obj is not None:
            for key in ("purpose", "conceptualModel", "dataFlow"):
                _string_field(v, section_obj, key, "/sections")
            for key, fields in (
                ("decisionsLocked", ("area", "decision")),
                ("industryInsights", ("finding", "sources")),
                ("deferredIdeas", ("text", "techSpec")),
                ("glossary", ("term", "definition")),
            ):
                raw = _required(v, section_obj, key, "/sections")
                if key not in section_obj:
                    continue
                values = v.array(raw, pointer("/sections", key))
                if values is None:
                    continue
                for index, value in enumerate(values):
                    path = pointer(pointer("/sections", key), index)
                    item = v.object(value, path)
                    if item is None:
                        continue
                    for field in fields:
                        field_value = _required(v, item, field, path)
                        if field not in item:
                            continue
                        if field == "sources":
                            v.string_array(field_value, pointer(path, field))
                        elif field == "techSpec":
                            v.boolean(field_value, pointer(path, field))
                        else:
                            v.string(field_value, pointer(path, field))
            non_goals = _required(v, section_obj, "scopeNonGoals", "/sections")
            if "scopeNonGoals" in section_obj:
                v.string_array(non_goals, "/sections/scopeNonGoals")

    behavior_rows: List[Any] = []
    behaviors = _required(v, root, "behaviors", "")
    if "behaviors" in root:
        rows = v.array(behaviors, "/behaviors")
        if rows is not None:
            behavior_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/behaviors", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                _string_field(v, item, "rule", path, nonempty=True)
                if "detail" in item:
                    v.string(item["detail"], pointer(path, "detail"))

    constraint_rows: List[Any] = []
    constraints = _required(v, root, "constraints", "")
    if "constraints" in root:
        rows = v.array(constraints, "/constraints")
        if rows is not None:
            constraint_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/constraints", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                _string_field(v, item, "area", path)
                if "kind" in item:
                    v.enum(item["kind"], CONSTRAINT_KINDS, pointer(path, "kind"))
                else:
                    _required(v, item, "kind", path)
                _string_field(v, item, "text", path, nonempty=True)
                _validate_provenance(v, item, path)
                if "requestId" in item:
                    _id_field(v, item, "requestId", path)
                if "ruling" in item:
                    v.enum(item["ruling"], CONSTRAINT_RULINGS, pointer(path, "ruling"))
                if "originalText" in item:
                    v.string(item["originalText"], pointer(path, "originalText"))
                if "rejectReason" in item:
                    v.string(item["rejectReason"], pointer(path, "rejectReason"))

    scenario_rows: List[Any] = []
    scenarios = _required(v, root, "scenarios", "")
    if "scenarios" in root:
        rows = v.array(scenarios, "/scenarios")
        if rows is not None:
            scenario_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/scenarios", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                _id_field(v, item, "behavior", path)
                for key in ("given", "when", "then", "explanation"):
                    _string_field(v, item, key, path)
                alternatives = _required(v, item, "alternatives", path)
                if "alternatives" in item:
                    v.string_array(alternatives, pointer(path, "alternatives"))
                _validate_provenance(v, item, path)
                if "requestId" in item:
                    _id_field(v, item, "requestId", path)
                if "dropReason" in item:
                    v.string(item["dropReason"], pointer(path, "dropReason"))
                if "reopened" in item:
                    reopened_path = pointer(path, "reopened")
                    reopened = v.object(item["reopened"], reopened_path)
                    if reopened is not None:
                        _id_field(v, reopened, "requirementId", reopened_path)
                        _string_field(v, reopened, "reason", reopened_path)
                        if "raisedAt" in reopened:
                            v.iso_datetime(reopened["raisedAt"], pointer(reopened_path, "raisedAt"))
                        else:
                            _required(v, reopened, "raisedAt", reopened_path)
                if "reapprovedHash" in item:
                    v.string(item["reapprovedHash"], pointer(path, "reapprovedHash"), nonempty=True)
                if "flagged" in item and item["flagged"] is not True:
                    v.error(pointer(path, "flagged"), "must be true when present")
                if "answeredComment" in item:
                    v.string(item["answeredComment"], pointer(path, "answeredComment"), nonempty=True)
                if "reopened" in item and "reapprovedHash" in item:
                    v.error(pointer(path, "reapprovedHash"), "reopened and reapprovedHash cannot both be present")

    assumption_rows: List[Any] = []
    assumptions = _required(v, root, "assumptions", "")
    if "assumptions" in root:
        rows = v.array(assumptions, "/assumptions")
        if rows is not None:
            assumption_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/assumptions", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("claim", "basis", "ifWrong", "meaning", "check", "checkCost"):
                    _string_field(v, item, key, path)
                if "certainty" in item:
                    v.enum(item["certainty"], CERTAINTIES, pointer(path, "certainty"))
                else:
                    _required(v, item, "certainty", path)
                _string_list_field(v, item, "affects", path)
                if "ruling" in item:
                    v.enum(item["ruling"], RULINGS, pointer(path, "ruling"))
                if "rulingNote" in item:
                    v.string(item["rulingNote"], pointer(path, "rulingNote"))
                if "originalCertainty" in item:
                    v.enum(item["originalCertainty"], CERTAINTIES, pointer(path, "originalCertainty"))

    blind_rows: List[Any] = []
    blind_spots = _required(v, root, "blindSpots", "")
    if "blindSpots" in root:
        rows = v.array(blind_spots, "/blindSpots")
        if rows is not None:
            blind_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/blindSpots", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("title", "detail"):
                    _string_field(v, item, key, path)
                _string_list_field(v, item, "sources", path)
                if "resolvedBy" in item:
                    _id_field(v, item, "resolvedBy", path)
                if "acceptance" in item:
                    v.string(item["acceptance"], pointer(path, "acceptance"))
                if "researchRequest" in item:
                    request_path = pointer(path, "researchRequest")
                    request = v.object(item["researchRequest"], request_path)
                    if request is not None:
                        _id_field(v, request, "id", request_path)
                        _string_field(v, request, "question", request_path)
                        asked = _required(v, request, "requestedAt", request_path)
                        if "requestedAt" in request:
                            v.iso_datetime(asked, pointer(request_path, "requestedAt"))

    research_rows: List[Any] = []
    research = _required(v, root, "research", "")
    if "research" in root:
        rows = v.array(research, "/research")
        if rows is not None:
            research_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/research", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "requestId", path)
                _id_field(v, item, "blindSpotId", path)
                for key in ("summary", "detail"):
                    _string_field(v, item, key, path)
                value = _required(v, item, "answeredAt", path)
                if "answeredAt" in item:
                    v.iso_datetime(value, pointer(path, "answeredAt"))

    requirement_rows: List[Any] = []
    requirements = _required(v, root, "requirements", "")
    if "requirements" in root:
        rows = v.array(requirements, "/requirements")
        if rows is not None:
            requirement_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/requirements", index)
                item = v.object(raw, path)
                if item is None:
                    continue
                _id_field(v, item, "id", path)
                for key in ("area", "text", "summary", "detail"):
                    _string_field(v, item, key, path)
                if "scope" in item:
                    v.enum(item["scope"], ("in", "out"), pointer(path, "scope"))
                else:
                    _required(v, item, "scope", path)
                if "group" in item:
                    v.enum(item["group"], REQUIREMENT_GROUPS, pointer(path, "group"))
                else:
                    _required(v, item, "group", path)
                if "certainty" in item:
                    certainty = item["certainty"]
                    if certainty is not None:
                        v.enum(certainty, CERTAINTIES, pointer(path, "certainty"))
                else:
                    _required(v, item, "certainty", path)
                _string_list_field(v, item, "dependsOn", path)
                _string_list_field(v, item, "derivedFrom", path)
                if "condition" in item:
                    v.enum(item["condition"], SCOPE_CONDITIONS, pointer(path, "condition"))
                    if item.get("scope") != "in":
                        v.error(pointer(path, "condition"), 'only valid when scope is "in"')
                if "reviewReason" in item:
                    v.string(item["reviewReason"], pointer(path, "reviewReason"))

    conflict_rows: List[Any] = []
    conflicts = _required(v, root, "conflicts", "")
    if "conflicts" in root:
        rows = v.array(conflicts, "/conflicts")
        if rows is not None:
            conflict_rows = rows
            for index, raw in enumerate(rows):
                path = pointer("/conflicts", index)
                pair = v.array(raw, path)
                if pair is None:
                    continue
                if len(pair) != 2:
                    v.error(path, "expected a pair of requirement ids")
                for part_index, ident in enumerate(pair):
                    v.string(ident, pointer(path, part_index), nonempty=True)
                if len(pair) == 2 and pair[0] == pair[1]:
                    v.error(path, "conflict must name two distinct requirements")

    ids: Dict[str, str] = {}
    _record_ids(v, behavior_rows, "/behaviors", ids)
    _record_ids(v, scenario_rows, "/scenarios", ids)
    _record_ids(v, constraint_rows, "/constraints", ids)
    _record_ids(v, requirement_rows, "/requirements", ids)
    _record_ids(v, assumption_rows, "/assumptions", ids)
    _record_ids(v, blind_rows, "/blindSpots", ids)

    behavior_ids = {item["id"] for item in behavior_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    scenario_ids = {item["id"] for item in scenario_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    constraint_ids = {item["id"] for item in constraint_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    requirement_ids = {item["id"] for item in requirement_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    requirement_by_id = {item["id"]: item for item in requirement_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    blind_ids = {item["id"] for item in blind_rows if isinstance(item, dict) and isinstance(item.get("id"), str)}
    scenario_or_constraint_ids = scenario_ids | constraint_ids

    scenarios_by_behavior: Dict[str, List[Tuple[int, dict]]] = {}
    for index, raw in enumerate(scenario_rows):
        if not isinstance(raw, dict):
            continue
        behavior_id = raw.get("behavior")
        if isinstance(behavior_id, str):
            if behavior_id not in behavior_ids:
                v.error(pointer(pointer("/scenarios", index), "behavior"), "unknown behavior id: " + behavior_id)
            else:
                scenarios_by_behavior.setdefault(behavior_id, []).append((index, raw))

    for behavior_index, behavior in enumerate(behavior_rows):
        if not isinstance(behavior, dict) or not isinstance(behavior.get("id"), str):
            continue
        rows = scenarios_by_behavior.get(behavior["id"], [])
        if not rows:
            v.error(pointer("/behaviors", behavior_index), "behavior has no scenarios")

    for index, raw in enumerate(assumption_rows):
        if not isinstance(raw, dict):
            continue
        for j, ident in enumerate(raw.get("affects", []) if isinstance(raw.get("affects"), list) else []):
            if isinstance(ident, str) and ident not in scenario_or_constraint_ids:
                v.error(
                    pointer(pointer(pointer("/assumptions", index), "affects"), j),
                    "unknown scenario or constraint id: " + ident,
                )
    for index, raw in enumerate(blind_rows):
        if not isinstance(raw, dict):
            continue
        for j, ident in enumerate(raw.get("sources", []) if isinstance(raw.get("sources"), list) else []):
            if isinstance(ident, str) and ident not in scenario_or_constraint_ids:
                v.error(
                    pointer(pointer(pointer("/blindSpots", index), "sources"), j),
                    "unknown scenario or constraint id: " + ident,
                )
        if "resolvedBy" in raw:
            ident = raw["resolvedBy"]
            if isinstance(ident, str) and ident not in scenario_or_constraint_ids:
                v.error(
                    pointer(pointer("/blindSpots", index), "resolvedBy"),
                    "unknown scenario or constraint id: " + ident,
                )

    for index, raw in enumerate(scenario_rows):
        if not isinstance(raw, dict):
            continue
        reopened = raw.get("reopened")
        if isinstance(reopened, dict):
            ident = reopened.get("requirementId")
            if isinstance(ident, str):
                path = pointer(pointer(pointer("/scenarios", index), "reopened"), "requirementId")
                requirement = requirement_by_id.get(ident)
                if requirement is None:
                    v.error(path, "unknown requirement id: " + ident)
                else:
                    derived_from = requirement.get("derivedFrom", [])
                    scenario_id = raw.get("id")
                    if not isinstance(derived_from, list) or scenario_id not in derived_from:
                        v.error(path, "requirement " + ident + " does not derive from this scenario")

    for index, raw in enumerate(requirement_rows):
        if not isinstance(raw, dict):
            continue
        for j, ident in enumerate(raw.get("dependsOn", []) if isinstance(raw.get("dependsOn"), list) else []):
            if isinstance(ident, str) and ident not in requirement_ids:
                v.error(pointer(pointer(pointer("/requirements", index), "dependsOn"), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(conflict_rows):
        if isinstance(raw, list) and len(raw) == 2:
            for j, ident in enumerate(raw):
                if isinstance(ident, str) and ident not in requirement_ids:
                    v.error(pointer(pointer("/conflicts", index), j), "unknown requirement id: " + ident)
    for index, raw in enumerate(research_rows):
        if isinstance(raw, dict):
            ident = raw.get("blindSpotId")
            if isinstance(ident, str) and ident not in blind_ids:
                v.error(pointer(pointer("/research", index), "blindSpotId"), "unknown blind spot id: " + ident)

    if "views" in root:
        view_obj = v.object(root["views"], "/views")
        if view_obj is not None:
            if "stateMachine" in view_obj:
                machine = v.object(view_obj["stateMachine"], "/views/stateMachine")
                if machine is not None:
                    states_raw = _required(v, machine, "states", "/views/stateMachine")
                    states: List[Any] = []
                    if "states" in machine:
                        values = v.array(states_raw, "/views/stateMachine/states")
                        if values is not None:
                            states = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/states", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _string_field(v, item, "label", path)
                                _string_field(v, item, "detail", path)
                                if "focal" in item:
                                    v.boolean(item["focal"], pointer(path, "focal"))
                    entries: List[Any] = []
                    if "entries" in machine:
                        values = v.array(machine["entries"], "/views/stateMachine/entries")
                        if values is not None:
                            entries = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/entries", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _string_field(v, item, "label", path)
                    transitions_raw = _required(v, machine, "transitions", "/views/stateMachine")
                    transitions: List[Any] = []
                    if "transitions" in machine:
                        values = v.array(transitions_raw, "/views/stateMachine/transitions")
                        if values is not None:
                            transitions = values
                            for index, raw in enumerate(values):
                                path = pointer("/views/stateMachine/transitions", index)
                                item = v.object(raw, path)
                                if item is None:
                                    continue
                                _id_field(v, item, "id", path)
                                _id_field(v, item, "from", path)
                                _id_field(v, item, "to", path)
                                _string_field(v, item, "short", path)
                                _string_field(v, item, "event", path)
                                _string_list_field(v, item, "reqs", path)
                                if "blindSpot" in item:
                                    _id_field(v, item, "blindSpot", path)
                    view_ids: Dict[str, str] = {}
                    _record_ids(v, states, "/views/stateMachine/states", view_ids)
                    _record_ids(v, entries, "/views/stateMachine/entries", view_ids)
                    _record_ids(v, transitions, "/views/stateMachine/transitions", view_ids)
                    state_ids = {item["id"] for item in states if isinstance(item, dict) and isinstance(item.get("id"), str)}
                    entry_ids = {item["id"] for item in entries if isinstance(item, dict) and isinstance(item.get("id"), str)}
                    valid_from = state_ids | entry_ids
                    for index, raw in enumerate(transitions):
                        if not isinstance(raw, dict):
                            continue
                        for key, valid in (("from", valid_from), ("to", state_ids)):
                            ident = raw.get(key)
                            if isinstance(ident, str) and ident not in valid:
                                v.error(pointer(pointer("/views/stateMachine/transitions", index), key), "unknown state or entry id: " + ident)
                        for j, ident in enumerate(raw.get("reqs", []) if isinstance(raw.get("reqs"), list) else []):
                            if isinstance(ident, str) and ident not in requirement_ids:
                                v.error(
                                    pointer(pointer(pointer("/views/stateMachine/transitions", index), "reqs"), j),
                                    "unknown requirement id: " + ident,
                                )
                        if "blindSpot" in raw:
                            ident = raw.get("blindSpot")
                            if isinstance(ident, str) and ident not in blind_ids:
                                v.error(
                                    pointer(pointer("/views/stateMachine/transitions", index), "blindSpot"),
                                    "unknown blind spot id: " + ident,
                                )
            if "storyMap" in view_obj:
                story = v.object(view_obj["storyMap"], "/views/storyMap")
                if story is not None:
                    journey_raw = _required(v, story, "journey", "/views/storyMap")
                    if "journey" in story:
                        journey = v.array(journey_raw, "/views/storyMap/journey")
                        if journey is not None:
                            for index, raw in enumerate(journey):
                                path = pointer("/views/storyMap/journey", index)
                                item = v.object(raw, path)
                                if item is not None:
                                    _string_field(v, item, "area", path)
                                    _string_field(v, item, "label", path)
                    cross = _required(v, story, "crossCutting", "/views/storyMap")
                    if "crossCutting" in story:
                        v.string_array(cross, "/views/storyMap/crossCutting")
            if "custom" in view_obj:
                _validate_custom_views(v, view_obj["custom"], set(ids))

    if "stage1Pin" in root:
        pin = v.object(root["stage1Pin"], "/stage1Pin")
        if pin is not None:
            if "signedAt" in pin:
                v.iso_datetime(pin["signedAt"], "/stage1Pin/signedAt")
            else:
                _required(v, pin, "signedAt", "/stage1Pin")
            _string_field(v, pin, "renderId", "/stage1Pin", nonempty=True)
            hashes = _required(v, pin, "itemHashes", "/stage1Pin")
            if "itemHashes" in pin:
                v.object(hashes, "/stage1Pin/itemHashes")

    if "signoff" in root:
        signoff = v.object(root["signoff"], "/signoff")
        if signoff is not None:
            if "signedAt" in signoff:
                v.iso_datetime(signoff["signedAt"], "/signoff/signedAt")
            else:
                _required(v, signoff, "signedAt", "/signoff")
            _string_field(v, signoff, "renderId", "/signoff", nonempty=True)

    if stage == 1:
        if root.get("requirements"):
            v.error("/requirements", "must be empty in stage 1")
        if root.get("conflicts"):
            v.error("/conflicts", "must be empty in stage 1")
        if root.get("views"):
            v.error("/views", "must be absent in stage 1")
        if root.get("stage1Pin"):
            v.error("/stage1Pin", "must be absent in stage 1")
        if root.get("signoff"):
            v.error("/signoff", "must be absent in stage 1")
        for index, raw in enumerate(scenario_rows):
            if not isinstance(raw, dict):
                continue
            for field in ("dropReason", "reopened", "reapprovedHash", "flagged"):
                if field in raw:
                    v.error(pointer(pointer("/scenarios", index), field), "must be absent in stage 1")
        for index, raw in enumerate(constraint_rows):
            if not isinstance(raw, dict):
                continue
            for field in ("ruling", "originalText", "rejectReason"):
                if field in raw:
                    v.error(pointer(pointer("/constraints", index), field), "must be absent in stage 1")
        for index, raw in enumerate(assumption_rows):
            if not isinstance(raw, dict):
                continue
            for field in ("ruling", "rulingNote", "originalCertainty"):
                if field in raw:
                    v.error(pointer(pointer("/assumptions", index), field), "must be absent in stage 1")
        for index, raw in enumerate(blind_rows):
            if not isinstance(raw, dict):
                continue
            for field in ("acceptance", "researchRequest"):
                if field in raw:
                    v.error(pointer(pointer("/blindSpots", index), field), "must be absent in stage 1")

    elif stage == 2:
        if not root.get("stage1Pin"):
            v.error("/stage1Pin", "required in stage 2")
        for index, raw in enumerate(scenario_rows):
            if isinstance(raw, dict) and "answeredComment" in raw:
                v.error(pointer(pointer("/scenarios", index), "answeredComment"), "must be absent in stage 2")
        for index, raw in enumerate(constraint_rows):
            if isinstance(raw, dict) and "ruling" not in raw:
                v.error(pointer(pointer("/constraints", index), "ruling"), "required in stage 2")

        approved_scenario_ids = {
            item["id"]
            for item in scenario_rows
            if isinstance(item, dict) and isinstance(item.get("id"), str) and "dropReason" not in item
        }
        derivable_constraint_ids = {
            item["id"]
            for item in constraint_rows
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("ruling") in ("approved", "rewritten")
        }
        for index, raw in enumerate(requirement_rows):
            if not isinstance(raw, dict):
                continue
            path = pointer(pointer("/requirements", index), "derivedFrom")
            derived_from = raw.get("derivedFrom")
            if not isinstance(derived_from, list) or not derived_from:
                v.error(path, "must not be empty")
                continue
            for j, ident in enumerate(derived_from):
                if isinstance(ident, str) and ident not in approved_scenario_ids and ident not in derivable_constraint_ids:
                    v.error(pointer(path, j), "must name an approved scenario or an approved/rewritten constraint")

        if not v.errors:
            _validate_stage1_lock(v, root)

    if not v.errors:
        warnings.extend(custom_view_quote_warnings(root))
    return v.errors, warnings


def _validate_stage1_lock(v: Validator, root: dict) -> None:
    pin = root.get("stage1Pin")
    if not isinstance(pin, dict):
        return
    pinned_hashes = pin.get("itemHashes")
    if not isinstance(pinned_hashes, dict):
        return
    current_hashes = stage1_item_hashes(root)
    scenario_by_id: Dict[str, dict] = {}
    scenario_path_by_id: Dict[str, str] = {}
    for index, item in enumerate(root.get("scenarios", [])):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            scenario_by_id[item["id"]] = item
            scenario_path_by_id[item["id"]] = pointer("/scenarios", index)
    pinned_ids = set(pinned_hashes.keys())
    current_ids = set(current_hashes.keys())
    for ident in sorted((pinned_ids - current_ids) | (current_ids - pinned_ids)):
        v.error(pointer("/stage1Pin/itemHashes", ident), "stage-1 item changed after sign-off")
    for ident in sorted(pinned_ids & current_ids):
        scenario = scenario_by_id.get(ident)
        # check reapprovedHash against the live hash regardless of the pin, so a stale value can't slip through fold
        if scenario is not None and "reapprovedHash" in scenario:
            if scenario["reapprovedHash"] != current_hashes[ident]:
                v.error(pointer(scenario_path_by_id[ident], "reapprovedHash"), "reapprovedHash does not match the item's current hash")
            continue
        if current_hashes[ident] == pinned_hashes[ident]:
            continue
        if scenario is not None and "reopened" in scenario:
            continue
        v.error(pointer("/stage1Pin/itemHashes", ident), "stage-1 item changed after sign-off")


def validate_logic_dispatch(logic: Any) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Validate logic.json against the schema for its declared schemaVersion."""
    v = Validator()
    root = v.object(logic, "")
    if root is None:
        return v.errors, []
    version = root.get("schemaVersion")
    if not v.exact_version(version, "/schemaVersion", (1, 2)):
        return v.errors, []
    if version == 1:
        return validate_logic(logic), []
    return validate_logic_v2(logic)


def validate_export_shape(export: Any) -> List[Tuple[str, str]]:
    v = Validator()
    root = v.object(export, "")
    if root is None:
        return v.errors
    kind = _required(v, root, "kind", "")
    if "kind" in root and kind != EXPORT_KIND:
        v.error("/kind", 'expected "' + EXPORT_KIND + '"')
    version = _required(v, root, "schemaVersion", "")
    if "schemaVersion" in root:
        v.exact_version(version, "/schemaVersion", (2,))
    stage = _required(v, root, "stage", "")
    if "stage" in root and (type(stage) is not int or stage not in (1, 2)):
        v.error("/stage", "expected 1 or 2")
    root_stage = stage if (type(stage) is int and stage in (1, 2)) else None
    for key in ("slug", "renderId"):
        _string_field(v, root, key, "", nonempty=True)
    exported_at = _required(v, root, "exportedAt", "")
    if "exportedAt" in root:
        v.iso_datetime(exported_at, "/exportedAt")
    if "signed" in root:
        v.boolean(root["signed"], "/signed")
    else:
        _required(v, root, "signed", "")
    seen = _required(v, root, "seen", "")
    if "seen" in root:
        seen_obj = v.object(seen, "/seen")
        if seen_obj is not None:
            for key, value in seen_obj.items():
                v.string(value, pointer("/seen", key), nonempty=True)

    state_raw = _required(v, root, "state", "")
    state = v.object(state_raw, "/state") if "state" in root else None
    if state is not None:
        if "stage" in state:
            if type(state["stage"]) is not int or state["stage"] not in (1, 2):
                v.error("/state/stage", "expected 1 or 2")
            elif root_stage is not None and state["stage"] != root_stage:
                v.error("/state/stage", "must equal the export's stage")
        else:
            _required(v, state, "stage", "/state")

        outcomes = _required(v, state, "scenarioOutcomes", "/state")
        if "scenarioOutcomes" in state:
            mapping = v.object(outcomes, "/state/scenarioOutcomes")
            if mapping is not None:
                for ident, value in mapping.items():
                    path = pointer("/state/scenarioOutcomes", ident)
                    outcome = v.object(value, path)
                    if outcome is not None:
                        choice = _required(v, outcome, "choice", path)
                        if "choice" in outcome:
                            if choice in SCENARIO_CHOICES or (
                                isinstance(choice, str) and re.fullmatch(r"alt-\d+", choice)
                            ):
                                pass
                            else:
                                v.error(pointer(path, "choice"), 'expected "spec", "custom", or "alt-<n>"')
                        custom = _string_field(v, outcome, "custom", path)
                        if choice == "custom" and isinstance(custom, str) and not custom.strip():
                            v.error(pointer(path, "custom"), "custom scenario outcome must not be blank")

        approved = _required(v, state, "scenarioApproved", "/state")
        if "scenarioApproved" in state:
            mapping = v.object(approved, "/state/scenarioApproved")
            if mapping is not None:
                for ident, value in mapping.items():
                    v.boolean(value, pointer("/state/scenarioApproved", ident))

        drops = _required(v, state, "scenarioDrops", "/state")
        if "scenarioDrops" in state:
            mapping = v.object(drops, "/state/scenarioDrops")
            if mapping is not None:
                for ident, value in mapping.items():
                    v.string(value, pointer("/state/scenarioDrops", ident))

        # optional: exports from pages built before update feedback, comments, or flags existed omit them
        for key in ("scenarioUpdates", "scenarioComments"):
            if key in state:
                mapping = v.object(state[key], pointer("/state", key))
                if mapping is not None:
                    for ident, value in mapping.items():
                        v.string(value, pointer(pointer("/state", key), ident))
        if "scenarioFlags" in state:
            mapping = v.object(state["scenarioFlags"], "/state/scenarioFlags")
            if mapping is not None:
                for ident, value in mapping.items():
                    v.boolean(value, pointer("/state/scenarioFlags", ident))

        requests = _required(v, state, "scenarioRequests", "/state")
        if "scenarioRequests" in state:
            rows = v.array(requests, "/state/scenarioRequests")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/state/scenarioRequests", index)
                    request = v.object(value, path)
                    if request is not None:
                        _id_field(v, request, "id", path)
                        _id_field(v, request, "behavior", path)
                        _string_field(v, request, "text", path)
                        asked = _required(v, request, "requestedAt", path)
                        if "requestedAt" in request:
                            v.iso_datetime(asked, pointer(path, "requestedAt"))

        rulings = _required(v, state, "constraintRulings", "/state")
        if "constraintRulings" in state:
            mapping = v.object(rulings, "/state/constraintRulings")
            if mapping is not None:
                for ident, value in mapping.items():
                    path = pointer("/state/constraintRulings", ident)
                    ruling = v.object(value, path)
                    if ruling is not None:
                        if "ruling" in ruling:
                            v.enum(ruling["ruling"], CONSTRAINT_STATE_RULINGS, pointer(path, "ruling"))
                        else:
                            _required(v, ruling, "ruling", path)
                        _string_field(v, ruling, "text", path)
                        _string_field(v, ruling, "reason", path)

        assumptions_state = _required(v, state, "assumptions", "/state")
        if "assumptions" in state:
            mapping = v.object(assumptions_state, "/state/assumptions")
            if mapping is not None:
                for ident, value in mapping.items():
                    path = pointer("/state/assumptions", ident)
                    decision = v.object(value, path)
                    if decision is not None:
                        if "ruling" in decision:
                            v.enum(decision["ruling"], RULINGS, pointer(path, "ruling"))
                        _string_field(v, decision, "note", path)
                        if "certainty" in decision:
                            v.enum(decision["certainty"], CERTAINTIES, pointer(path, "certainty"))

        blind_state = _required(v, state, "blindSpots", "/state")
        if "blindSpots" in state:
            mapping = v.object(blind_state, "/state/blindSpots")
            if mapping is not None:
                for ident, value in mapping.items():
                    path = pointer("/state/blindSpots", ident)
                    decision = v.object(value, path)
                    if decision is not None:
                        if "accepted" in decision:
                            v.boolean(decision["accepted"], pointer(path, "accepted"))
                        else:
                            _required(v, decision, "accepted", path)
                        _string_field(v, decision, "note", path)

        research_requests = _required(v, state, "researchRequests", "/state")
        if "researchRequests" in state:
            rows = v.array(research_requests, "/state/researchRequests")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/state/researchRequests", index)
                    request = v.object(value, path)
                    if request is not None:
                        _id_field(v, request, "id", path)
                        _id_field(v, request, "blindSpotId", path)
                        _string_field(v, request, "question", path)
                        asked = _required(v, request, "requestedAt", path)
                        if "requestedAt" in request:
                            v.iso_datetime(asked, pointer(path, "requestedAt"))

        placements = _required(v, state, "placements", "/state")
        if "placements" in state:
            mapping = v.object(placements, "/state/placements")
            if mapping is not None:
                for ident, value in mapping.items():
                    v.enum(value, PLACEMENTS, pointer("/state/placements", ident))

        conditions = _required(v, state, "conditions", "/state")
        if "conditions" in state:
            mapping = v.object(conditions, "/state/conditions")
            if mapping is not None:
                for ident, value in mapping.items():
                    v.enum(value, SCOPE_CONDITIONS, pointer("/state/conditions", ident))

        for key in ("moveReasons", "notes"):
            raw = _required(v, state, key, "/state")
            if key in state:
                mapping = v.object(raw, pointer("/state", key))
                if mapping is not None:
                    for ident, value in mapping.items():
                        v.string(value, pointer(pointer("/state", key), ident))

        disputes = _required(v, state, "disputes", "/state")
        if "disputes" in state:
            mapping = v.object(disputes, "/state/disputes")
            if mapping is not None:
                for ident, value in mapping.items():
                    path = pointer("/state/disputes", ident)
                    dispute = v.object(value, path)
                    if dispute is not None:
                        kind_value = _required(v, dispute, "kind", path)
                        if "kind" in dispute:
                            v.enum(kind_value, DISPUTE_KINDS, pointer(path, "kind"))
                        target = _required(v, dispute, "target", path)
                        if "target" in dispute:
                            if target is not None:
                                v.string(target, pointer(path, "target"), nonempty=True)
                            if kind_value == "scenario" and target is None:
                                v.error(pointer(path, "target"), "required when kind is scenario")
                            if kind_value == "derivation" and target is not None:
                                v.error(pointer(path, "target"), "must be null when kind is derivation")
                        _string_field(v, dispute, "reason", path, nonempty=True)

        if "verdict" in state:
            v.enum(state["verdict"], ("approve", "send-back"), "/state/verdict")
        _string_field(v, state, "verdictNote", "/state")
        if "signedAt" in state:
            v.iso_datetime(state["signedAt"], "/state/signedAt")
        updated = _required(v, state, "updatedAt", "/state")
        if "updatedAt" in state:
            v.iso_datetime(updated, "/state/updatedAt")

        state_stage = state.get("stage") if type(state.get("stage")) is int else None
        if state_stage == 1:
            inapplicable = ("placements", "conditions", "moveReasons", "notes", "disputes")
        elif state_stage == 2:
            inapplicable = (
                "scenarioOutcomes",
                "scenarioDrops",
                "scenarioUpdates",
                "scenarioComments",
                "constraintRulings",
                "assumptions",
                "blindSpots",
                "scenarioRequests",
                "researchRequests",
            )
        else:
            inapplicable = ()
        for key in inapplicable:
            value = state.get(key)
            if isinstance(value, (dict, list)) and value:
                v.error(pointer("/state", key), "must be empty in stage " + str(state_stage))

    record_raw = _required(v, root, "record", "")
    record = v.object(record_raw, "/record") if "record" in root else None
    if record is not None:
        if "stage" in record:
            if type(record["stage"]) is not int or record["stage"] not in (1, 2):
                v.error("/record/stage", "expected 1 or 2")
            elif root_stage is not None and record["stage"] != root_stage:
                v.error("/record/stage", "must equal the export's stage")
        else:
            _required(v, record, "stage", "/record")
        verdict = _required(v, record, "verdict", "/record")
        if "verdict" in record and verdict is not None:
            v.enum(verdict, ("approve", "send-back"), "/record/verdict")
        _string_field(v, record, "verdictNote", "/record")
        signed_at = _required(v, record, "signedAt", "/record")
        if "signedAt" in record and signed_at is not None:
            v.iso_datetime(signed_at, "/record/signedAt")

        scenarios = _required(v, record, "scenarios", "/record")
        if "scenarios" in record:
            rows = v.array(scenarios, "/record/scenarios")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/scenarios", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "id", path)
                        v.boolean(_required(v, item, "approved", path), pointer(path, "approved"))
                        dropped = _required(v, item, "dropped", path)
                        if "dropped" in item and dropped is not None:
                            v.string(dropped, pointer(path, "dropped"))
                        if item.get("update") is not None:
                            v.string(item["update"], pointer(path, "update"))
                        if item.get("comment") is not None:
                            v.string(item["comment"], pointer(path, "comment"))
                        if "flagged" in item:
                            v.boolean(item["flagged"], pointer(path, "flagged"))
                        _string_field(v, item, "then", path)
                        v.boolean(_required(v, item, "changesSpec", path), pointer(path, "changesSpec"))

        constraints = _required(v, record, "constraints", "/record")
        if "constraints" in record:
            rows = v.array(constraints, "/record/constraints")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/constraints", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "id", path)
                        ruling = _required(v, item, "ruling", path)
                        if "ruling" in item and ruling is not None:
                            v.enum(ruling, CONSTRAINT_STATE_RULINGS, pointer(path, "ruling"))
                        _string_field(v, item, "text", path)
                        _string_field(v, item, "reason", path)

        assumptions_rec = _required(v, record, "assumptions", "/record")
        if "assumptions" in record:
            rows = v.array(assumptions_rec, "/record/assumptions")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/assumptions", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "id", path)
                        ruling = _required(v, item, "ruling", path)
                        if "ruling" in item and ruling is not None:
                            v.enum(ruling, RULINGS, pointer(path, "ruling"))
                        _string_field(v, item, "note", path)
                        if item.get("certainty") is not None:
                            v.enum(item["certainty"], CERTAINTIES, pointer(path, "certainty"))

        blind_rec = _required(v, record, "blindSpots", "/record")
        if "blindSpots" in record:
            rows = v.array(blind_rec, "/record/blindSpots")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/blindSpots", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "id", path)
                        v.boolean(_required(v, item, "accepted", path), pointer(path, "accepted"))
                        _string_field(v, item, "note", path)

        placements_rec = _required(v, record, "placements", "/record")
        if "placements" in record:
            rows = v.array(placements_rec, "/record/placements")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/placements", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "id", path)
                        v.enum(_required(v, item, "from", path), PLACEMENTS, pointer(path, "from"))
                        v.enum(_required(v, item, "to", path), PLACEMENTS, pointer(path, "to"))
                        condition = _required(v, item, "condition", path)
                        if "condition" in item and condition is not None:
                            v.enum(condition, SCOPE_CONDITIONS, pointer(path, "condition"))
                        _string_field(v, item, "reason", path)

        disputes_rec = _required(v, record, "disputes", "/record")
        if "disputes" in record:
            rows = v.array(disputes_rec, "/record/disputes")
            if rows is not None:
                for index, value in enumerate(rows):
                    path = pointer("/record/disputes", index)
                    item = v.object(value, path)
                    if item is not None:
                        _id_field(v, item, "requirementId", path)
                        kind_value = _required(v, item, "kind", path)
                        if "kind" in item:
                            v.enum(kind_value, DISPUTE_KINDS, pointer(path, "kind"))
                        target = _required(v, item, "target", path)
                        if "target" in item:
                            if target is not None:
                                v.string(target, pointer(path, "target"), nonempty=True)
                            if kind_value == "scenario" and target is None:
                                v.error(pointer(path, "target"), "required when kind is scenario")
                            if kind_value == "derivation" and target is not None:
                                v.error(pointer(path, "target"), "must be null when kind is derivation")
                        _string_field(v, item, "reason", path, nonempty=True)

        for key, request_kind in (("scenarioRequests", "scenario"), ("researchRequests", "research")):
            raw = _required(v, record, key, "/record")
            if key not in record:
                continue
            rows = v.array(raw, pointer("/record", key))
            if rows is None:
                continue
            for index, value in enumerate(rows):
                path = pointer(pointer("/record", key), index)
                request = v.object(value, path)
                if request is not None:
                    _id_field(v, request, "id", path)
                    if request_kind == "scenario":
                        _id_field(v, request, "behavior", path)
                        _string_field(v, request, "text", path)
                    else:
                        _id_field(v, request, "blindSpotId", path)
                        _string_field(v, request, "question", path)
                    asked = _required(v, request, "requestedAt", path)
                    if "requestedAt" in request:
                        v.iso_datetime(asked, pointer(path, "requestedAt"))

        warnings = _required(v, record, "openWarnings", "/record")
        if "openWarnings" in record:
            v.string_array(warnings, "/record/openWarnings")

    if root.get("signed") is True and isinstance(state, dict):
        if "signedAt" not in state:
            v.error("/state/signedAt", "required for a signed export")
        if state.get("verdict") != "approve":
            v.error("/state/verdict", 'signed export must have verdict "approve"')
    return v.errors


def logic_reference_errors(export: dict, logic: dict) -> List[Tuple[str, str]]:
    """Cross-reference an export's ids against the v2 logic's item and requirement maps."""
    errors: List[Tuple[str, str]] = []
    behavior_ids = {item["id"] for item in logic["behaviors"]}
    scenario_ids = {item["id"] for item in logic["scenarios"]}
    scenario_by_id = {item["id"]: item for item in logic["scenarios"]}
    constraint_ids = {item["id"] for item in logic["constraints"]}
    assumption_ids = {item["id"] for item in logic["assumptions"]}
    blind_ids = {item["id"] for item in logic["blindSpots"]}
    requirement_ids = {item["id"] for item in logic["requirements"]}
    requirement_by_id = {item["id"]: item for item in logic["requirements"]}
    item_ids = behavior_ids | scenario_ids | constraint_ids | assumption_ids | blind_ids | requirement_ids

    state = export["state"]
    updates = state.get("scenarioUpdates", {})
    for key in ("scenarioUpdates", "scenarioComments", "scenarioFlags"):
        for ident in state.get(key, {}):
            if ident not in scenario_ids:
                errors.append((pointer(pointer("/state", key), ident), "unknown scenario id: " + ident))
    for key, known, label in (
        ("scenarioApproved", scenario_ids, "scenario"),
        ("scenarioDrops", scenario_ids, "scenario"),
        ("constraintRulings", constraint_ids, "constraint"),
        ("assumptions", assumption_ids, "assumption"),
        ("blindSpots", blind_ids, "blind spot"),
    ):
        for ident in state[key]:
            if ident not in known:
                errors.append((pointer(pointer("/state", key), ident), "unknown " + label + " id: " + ident))
    for ident, approved in state["scenarioApproved"].items():
        if approved and state["scenarioDrops"].get(ident, "").strip():
            errors.append(
                (
                    pointer(pointer("/state", "scenarioDrops"), ident),
                    "scenario cannot be both approved and dropped: " + ident,
                )
            )
        if approved and updates.get(ident, "").strip():
            errors.append(
                (
                    pointer(pointer("/state", "scenarioUpdates"), ident),
                    "scenario cannot be both approved and awaiting an update: " + ident,
                )
            )
    if state.get("stage") == 2:
        reopened_ids = {item["id"] for item in logic["scenarios"] if "reopened" in item}
        for ident in state["scenarioApproved"]:
            if ident in scenario_ids and ident not in reopened_ids:
                errors.append(
                    (pointer(pointer("/state", "scenarioApproved"), ident), "scenario is not reopened: " + ident)
                )
    for key in ("placements", "conditions", "moveReasons"):
        for ident in state[key]:
            if ident not in requirement_ids:
                errors.append((pointer(pointer("/state", key), ident), "unknown requirement id: " + ident))
    for ident in state["notes"]:
        if ident not in item_ids:
            errors.append((pointer(pointer("/state", "notes"), ident), "unknown logic item id: " + ident))
    for ident, outcome in state["scenarioOutcomes"].items():
        if ident not in scenario_ids:
            errors.append((pointer(pointer("/state", "scenarioOutcomes"), ident), "unknown scenario id: " + ident))
            continue
        choice = outcome["choice"]
        if choice.startswith("alt-"):
            digits = choice[4:].lstrip("0") or "0"
            max_index = len(scenario_by_id[ident]["alternatives"]) - 1
            max_digits = str(max_index)
            out_of_range = max_index < 0 or len(digits) > len(max_digits)
            if not out_of_range and len(digits) == len(max_digits):
                out_of_range = digits > max_digits
            if out_of_range:
                errors.append(
                    (
                        pointer(pointer(pointer("/state", "scenarioOutcomes"), ident), "choice"),
                        "alternative index is out of range for scenario " + ident,
                    )
                )
    for index, request in enumerate(state["scenarioRequests"]):
        if request["behavior"] not in behavior_ids:
            errors.append(
                (
                    pointer(pointer(pointer("/state", "scenarioRequests"), index), "behavior"),
                    "unknown behavior id: " + request["behavior"],
                )
            )
    for index, request in enumerate(state["researchRequests"]):
        if request["blindSpotId"] not in blind_ids:
            errors.append(
                (
                    pointer(pointer(pointer("/state", "researchRequests"), index), "blindSpotId"),
                    "unknown blind spot id: " + request["blindSpotId"],
                )
            )
    for ident, dispute in state["disputes"].items():
        if ident not in requirement_ids:
            errors.append((pointer(pointer("/state", "disputes"), ident), "unknown requirement id: " + ident))
            continue
        if dispute["kind"] == "scenario":
            derived_from = requirement_by_id[ident].get("derivedFrom", [])
            target = dispute.get("target")
            if target not in derived_from or target not in scenario_ids:
                errors.append(
                    (
                        pointer(pointer(pointer("/state", "disputes"), ident), "target"),
                        "target must be a scenario id in the requirement's derivedFrom",
                    )
                )
    for ident in export["seen"]:
        if ident not in item_ids:
            errors.append((pointer("/seen", ident), "unknown logic item id: " + ident))

    record = export["record"]
    for key, known, label in (
        ("scenarios", scenario_ids, "scenario"),
        ("constraints", constraint_ids, "constraint"),
        ("assumptions", assumption_ids, "assumption"),
        ("blindSpots", blind_ids, "blind spot"),
    ):
        for index, item in enumerate(record[key]):
            if item["id"] not in known:
                errors.append(
                    (pointer(pointer(pointer("/record", key), index), "id"), "unknown " + label + " id: " + item["id"])
                )
    for index, item in enumerate(record["placements"]):
        if item["id"] not in requirement_ids:
            errors.append(
                (pointer(pointer(pointer("/record", "placements"), index), "id"), "unknown requirement id: " + item["id"])
            )
    for index, dispute in enumerate(record["disputes"]):
        ident = dispute["requirementId"]
        if ident not in requirement_ids:
            errors.append(
                (
                    pointer(pointer(pointer("/record", "disputes"), index), "requirementId"),
                    "unknown requirement id: " + ident,
                )
            )
            continue
        if dispute["kind"] == "scenario":
            derived_from = requirement_by_id[ident].get("derivedFrom", [])
            target = dispute.get("target")
            if target not in derived_from or target not in scenario_ids:
                errors.append(
                    (
                        pointer(pointer(pointer("/record", "disputes"), index), "target"),
                        "target must be a scenario id in the requirement's derivedFrom",
                    )
                )
    for key in ("scenarioRequests", "researchRequests"):
        for index, request in enumerate(record[key]):
            if key == "scenarioRequests" and request["behavior"] not in behavior_ids:
                errors.append(
                    (
                        pointer(pointer(pointer("/record", key), index), "behavior"),
                        "unknown behavior id: " + request["behavior"],
                    )
                )
            if key == "researchRequests" and request["blindSpotId"] not in blind_ids:
                errors.append(
                    (
                        pointer(pointer(pointer("/record", key), index), "blindSpotId"),
                        "unknown blind spot id: " + request["blindSpotId"],
                    )
                )
    return errors


def _reject_json_constant(constant: str) -> Any:
    raise ValueError("non-standard numeric constant: " + constant)


JSON_MAX_DEPTH = 200


def _json_depth_exceeded(value: Any, limit: int = JSON_MAX_DEPTH) -> Optional[str]:
    """Return the pointer where value's nesting exceeds limit, or None. Walks an explicit stack rather than
    recursing, so the check itself cannot fall over on the same input it is meant to reject."""
    stack: List[Tuple[Any, str, int]] = [(value, "", 0)]
    while stack:
        current, path, depth = stack.pop()
        if depth > limit:
            return path or "/"
        if isinstance(current, dict):
            for key, item in current.items():
                stack.append((item, pointer(path, key), depth + 1))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                stack.append((item, pointer(path, index), depth + 1))
    return None


def load_json(path: Path, label: str) -> Tuple[Optional[Any], List[Tuple[str, str]]]:
    try:
        with path.open("r", encoding="utf-8") as source:
            value = json.load(source, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        return None, [("/", "invalid JSON in " + label + " at line " + str(exc.lineno) + ", column " + str(exc.colno) + ": " + exc.msg)]
    except UnicodeError as exc:
        return None, [("/", "invalid UTF-8 in " + label + ": " + str(exc))]
    except OSError as exc:
        return None, [("/", "cannot read " + label + ": " + str(exc))]
    except RecursionError:
        return None, [("/", "invalid JSON in " + label + ": input is too deeply nested")]
    except ValueError as exc:
        return None, [("/", "invalid JSON in " + label + ": " + str(exc))]
    too_deep = _json_depth_exceeded(value)
    if too_deep is not None:
        return None, [(too_deep, "invalid JSON in " + label + ": input is too deeply nested")]
    return value, []


def emit_errors(errors: Iterable[Tuple[str, str]]) -> None:
    for path, message in errors:
        print(path + ": " + message, file=sys.stderr)


def load_logic(spec_dir: Path) -> Tuple[Optional[dict], Optional[str]]:
    path = spec_dir / "logic.json"
    value, errors = load_json(path, str(path))
    if errors:
        emit_errors(errors)
        return None, None
    validation, warnings = validate_logic_dispatch(value)
    if validation:
        emit_errors(validation)
        return None, None
    for warning in warnings:
        print(warning, file=sys.stderr)
    try:
        return value, render_id(value)
    except UnicodeError as exc:
        print("/: logic.json contains invalid Unicode: " + str(exc), file=sys.stderr)
        return None, None
    except ValueError as exc:
        print("/: " + str(exc), file=sys.stderr)
        return None, None


SCORE_TARGET_FIELDS = ("status", "qualifier", "wording", "note", "citations", "requirementHash")
SLICE_TARGET_FIELDS = ("name", "size", "band", "lines")


def spec_is_signed_stage2(logic: dict) -> bool:
    """True when logic.json is a v2 spec whose stage-2 sign-off has been folded in."""
    return (
        logic.get("schemaVersion") == 2
        and logic.get("stage") == 2
        and str(logic.get("status", "")).startswith("Approved")
        and "signoff" in logic
    )


def comparison_id(comparison: dict) -> str:
    try:
        return sha256(canonical_json(comparison).encode("utf-8")).hexdigest()[:12]
    except RecursionError:
        raise ValueError("comparison.json is too deeply nested to render")


def target_hash(obj: dict, kind: str) -> str:
    """Hash of the content a reviewer argues with, so checks and history never invalidate a draft."""
    if kind == "score":
        fields = SCORE_TARGET_FIELDS
    elif kind == "slice":
        fields = SLICE_TARGET_FIELDS
    else:
        raise ValueError("unknown target kind: " + str(kind))
    hashed = {name: obj[name] for name in fields if name in obj}
    return sha256(canonical_json(hashed).encode("utf-8")).hexdigest()[:12]


def _is_int(value: Any) -> bool:
    return type(value) is int


def _optional_string(v: Validator, obj: dict, key: str, path: str) -> None:
    if key in obj:
        v.string(obj[key], pointer(path, key))


def _required_string_array(v: Validator, obj: dict, key: str, path: str) -> None:
    if key in obj:
        v.string_array(obj[key], pointer(path, key))
    else:
        v.error(pointer(path, key), "required key is missing")


def _validate_read_at(v: Validator, value: Any, path: str) -> None:
    if not v.string(value, path, nonempty=True):
        return
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        v.error(path, "expected a YYYY-MM-DD date")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        v.error(path, "expected a real calendar date")


def _validate_slices(v: Validator, raw: Any, path: str) -> None:
    slices = v.array(raw, path)
    if slices is None:
        return
    seen: Dict[str, str] = {}
    for index, slice_raw in enumerate(slices):
        base = pointer(path, index)
        item = v.object(slice_raw, base)
        if item is None:
            continue
        ident = _required(v, item, "id", base)
        if "id" in item and v.string(ident, pointer(base, "id"), nonempty=True):
            if ident in seen:
                v.error(pointer(base, "id"), "duplicate slice id; first used at " + seen[ident])
            else:
                seen[ident] = pointer(base, "id")
        for key in ("name", "area", "risk"):
            _string_field(v, item, key, base, nonempty=True)
        size = _required(v, item, "size", base)
        if "size" in item:
            v.enum(size, tuple(POINT_MAP), pointer(base, "size"))
        band = _required(v, item, "band", base)
        if "band" in item:
            v.enum(band, SLICE_BANDS, pointer(base, "band"))
        _optional_string(v, item, "riskHeadline", base)
        if "lines" in item:
            lines_path = pointer(base, "lines")
            lines = v.object(item["lines"], lines_path)
            for repo, span in (lines or {}).items():
                span_path = pointer(lines_path, repo)
                if not isinstance(span, list) or len(span) != 2 or not all(_is_int(n) and n >= 0 for n in span):
                    v.error(span_path, "expected [lo, hi] with non-negative integers")
                elif span[0] > span[1]:
                    v.error(span_path, "lo must not exceed hi")


def _validate_flow(v: Validator, approach: dict, path: str, flow_stages: Optional[list]) -> None:
    flow = v.array(approach["flow"], pointer(path, "flow"))
    if flow is None:
        return
    allowed = set(flow_stages) if isinstance(flow_stages, list) else set()
    cells: Dict[Tuple[str, str], str] = {}
    for index, box_raw in enumerate(flow):
        base = pointer(pointer(path, "flow"), index)
        box = v.object(box_raw, base)
        if box is None:
            continue
        stage = _required(v, box, "stage", base)
        lane = _required(v, box, "lane", base)
        for key in ("stage", "lane"):
            if key in box:
                v.string(box[key], pointer(base, key), nonempty=True)
        _string_field(v, box, "text", base)
        kind = _required(v, box, "kind", base)
        if "kind" in box:
            v.enum(kind, FLOW_KINDS, pointer(base, "kind"))
        if "focal" in box:
            v.boolean(box["focal"], pointer(base, "focal"))
        if isinstance(stage, str) and stage:
            if stage not in allowed:
                v.error(pointer(base, "stage"), "stage is not listed in flowStages: " + stage)
            if isinstance(lane, str) and lane:
                previous = cells.get((lane, stage))
                if previous is not None:
                    v.error(base, "second box in lane " + lane + " at stage " + stage + "; first at " + previous)
                else:
                    cells[(lane, stage)] = base


def _validate_sequence(v: Validator, raw: Any, path: str) -> None:
    sequence = v.object(raw, path)
    if sequence is None:
        return
    participants_raw = _required(v, sequence, "participants", path)
    participants: List[str] = []
    if "participants" in sequence:
        listed = v.string_array(participants_raw, pointer(path, "participants"), nonempty_items=True)
        participants = [name for name in (listed or []) if isinstance(name, str)]
        if listed is not None and len(listed) > SEQUENCE_MAX_PARTICIPANTS:
            v.error(pointer(path, "participants"), "at most " + str(SEQUENCE_MAX_PARTICIPANTS) + " participants")
    messages_raw = _required(v, sequence, "messages", path)
    if "messages" not in sequence:
        return
    messages = v.array(messages_raw, pointer(path, "messages"))
    if messages is None:
        return
    if len(messages) > SEQUENCE_MAX_MESSAGES:
        v.error(pointer(path, "messages"), "at most " + str(SEQUENCE_MAX_MESSAGES) + " messages")
    for index, message_raw in enumerate(messages):
        base = pointer(pointer(path, "messages"), index)
        message = v.object(message_raw, base)
        if message is None:
            continue
        for key in ("from", "to"):
            name = _required(v, message, key, base)
            if key in message and v.string(name, pointer(base, key), nonempty=True) and name not in participants:
                v.error(pointer(base, key), "unknown participant: " + name)
        _string_field(v, message, "label", base)
        kind = _required(v, message, "kind", base)
        if "kind" in message:
            v.enum(kind, MESSAGE_KINDS, pointer(base, "kind"))


def _validate_schema_diagram(v: Validator, raw: Any, path: str) -> None:
    diagram = v.object(raw, path)
    if diagram is None:
        return
    columns_by_table: Dict[str, set] = {}
    tables_raw = _required(v, diagram, "tables", path)
    if "tables" in diagram:
        tables = v.array(tables_raw, pointer(path, "tables"))
        if tables is not None and len(tables) > SCHEMA_MAX_TABLES:
            v.error(pointer(path, "tables"), "at most " + str(SCHEMA_MAX_TABLES) + " tables")
        for index, table_raw in enumerate(tables or []):
            base = pointer(pointer(path, "tables"), index)
            table = v.object(table_raw, base)
            if table is None:
                continue
            name = _required(v, table, "name", base)
            names: set = set()
            if "name" in table and v.string(name, pointer(base, "name"), nonempty=True):
                if name in columns_by_table:
                    v.error(pointer(base, "name"), "duplicate table name: " + name)
                columns_by_table.setdefault(name, names)
                names = columns_by_table[name]
            status = _required(v, table, "status", base)
            if "status" in table:
                v.enum(status, TABLE_STATUSES, pointer(base, "status"))
            columns = _required_array(v, table, "columns", base)
            for col_index, column_raw in enumerate(columns or []):
                col_path = pointer(pointer(base, "columns"), col_index)
                column = v.object(column_raw, col_path)
                if column is None:
                    continue
                col_name = _string_field(v, column, "name", col_path, nonempty=True)
                if isinstance(col_name, str):
                    names.add(col_name)
                _string_field(v, column, "type", col_path)
                chip = column.get("chip")
                if "chip" in column and chip is not None:
                    v.enum(chip, COLUMN_CHIPS, pointer(col_path, "chip"))
                if "highlight" in column:
                    v.boolean(column["highlight"], pointer(col_path, "highlight"))
            _optional_string(v, table, "moreColumns", base)
    refs_raw = _required(v, diagram, "refs", path)
    if "refs" not in diagram:
        return
    refs = v.array(refs_raw, pointer(path, "refs"))
    if refs is None:
        return
    if len(refs) > SCHEMA_MAX_REFS:
        v.error(pointer(path, "refs"), "at most " + str(SCHEMA_MAX_REFS) + " refs (fk and json together)")
    for index, ref_raw in enumerate(refs):
        base = pointer(pointer(path, "refs"), index)
        ref = v.object(ref_raw, base)
        if ref is None:
            continue
        for key in ("from", "to"):
            end = _required(v, ref, key, base)
            if key not in ref:
                continue
            end_path = pointer(base, key)
            if not isinstance(end, list) or len(end) != 2 or not all(isinstance(part, str) for part in end):
                v.error(end_path, "expected [table, column]")
            elif end[0] not in columns_by_table:
                v.error(end_path, "unknown table: " + end[0])
            elif end[1] not in columns_by_table[end[0]]:
                v.error(end_path, "unknown column: " + end[0] + "." + end[1])
        kind = _required(v, ref, "kind", base)
        if "kind" in ref:
            v.enum(kind, REF_KINDS, pointer(base, "kind"))


def _validate_approach(v: Validator, raw: Any, path: str, flow_stages: Optional[list], example_stages: Optional[list]) -> None:
    approach = v.object(raw, path)
    if approach is None:
        return
    for key in ("title", "overview", "revision", "schemaChange"):
        _string_field(v, approach, key, path, nonempty=True)
    anchors = _required_array(v, approach, "anchors", path)
    for index, anchor_raw in enumerate(anchors or []):
        base = pointer(pointer(path, "anchors"), index)
        anchor = v.object(anchor_raw, base)
        if anchor is not None:
            _string_field(v, anchor, "repo", base, nonempty=True)
            _string_field(v, anchor, "commit", base, nonempty=True)
    if "readAt" in approach:
        _validate_read_at(v, approach["readAt"], pointer(path, "readAt"))
    else:
        v.error(pointer(path, "readAt"), "required key is missing")
    _optional_string(v, approach, "specMarkdown", path)
    repos = _required_array(v, approach, "repos", path)
    seen_repos: set = set()
    for index, repo_raw in enumerate(repos or []):
        base = pointer(pointer(path, "repos"), index)
        repo = v.object(repo_raw, base)
        if repo is None:
            continue
        _string_field(v, repo, "name", base, nonempty=True)
        repo_name = repo.get("name")
        if isinstance(repo_name, str):
            if repo_name in seen_repos:
                v.error(pointer(base, "name"), f'duplicate repo name "{repo_name}"')
            seen_repos.add(repo_name)
        files = _required(v, repo, "files", base)
        if "files" in repo and (not _is_int(files) or files < 0):
            v.error(pointer(base, "files"), "expected a non-negative integer")
    _required_string_array(v, approach, "hotPaths", path)
    deploy_raw = _required(v, approach, "deploy", path)
    deploy = v.object(deploy_raw, pointer(path, "deploy")) if "deploy" in approach else None
    if deploy is not None:
        status = _required(v, deploy, "status", pointer(path, "deploy"))
        if "status" in deploy:
            v.enum(status, DEPLOY_STATUSES, pointer(pointer(path, "deploy"), "status"))
        _required_string_array(v, deploy, "steps", pointer(path, "deploy"))
    if "criticalPath" not in approach:
        v.error(pointer(path, "criticalPath"), "required key is missing")
    elif approach["criticalPath"] is not None:
        v.string(approach["criticalPath"], pointer(path, "criticalPath"))
    if "slices" in approach:
        _validate_slices(v, approach["slices"], pointer(path, "slices"))
    else:
        v.error(pointer(path, "slices"), "required key is missing")
    if "flow" in approach:
        _validate_flow(v, approach, path, flow_stages)
    if "sequence" in approach:
        _validate_sequence(v, approach["sequence"], pointer(path, "sequence"))
    if "schema" in approach:
        _validate_schema_diagram(v, approach["schema"], pointer(path, "schema"))
    if "exampleTrace" in approach:
        trace = v.string_array(approach["exampleTrace"], pointer(path, "exampleTrace"))
        if trace is not None and (example_stages is None or len(trace) != len(example_stages)):
            expected = "example.stages" if example_stages is None else str(len(example_stages)) + " entries (one per example.stages)"
            v.error(pointer(path, "exampleTrace"), "must have " + expected)
    for key in ("restsOn", "effortGaps"):
        if key in approach:
            v.string_array(approach[key], pointer(path, key))
    if "undo" in approach:
        undo_path = pointer(path, "undo")
        undo = v.object(approach["undo"], undo_path)
        for key in ("flagOff", "hardToReverse", "cheapestNext"):
            if undo is not None:
                _string_field(v, undo, key, undo_path)


def _validate_scores(v: Validator, root: dict, logic: dict, approach_ids: List[str], warnings: List[str]) -> None:
    requirements = {
        item["id"]: item
        for item in logic.get("requirements", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    hashes = item_hashes(logic)
    if "scores" not in root:
        v.error("/scores", "required key is missing")
        return
    scores = v.object(root["scores"], "/scores")
    if scores is None:
        return
    for requirement_id in scores:
        if requirement_id not in requirements:
            v.error(pointer("/scores", requirement_id), "unknown requirement id: " + requirement_id)
    for requirement_id, requirement in requirements.items():
        if requirement.get("scope") != "out" and requirement_id not in scores:
            v.error(pointer("/scores", requirement_id), "in-scope requirement has no scores")
    for requirement_id, per_approach_raw in scores.items():
        req_path = pointer("/scores", requirement_id)
        per_approach = v.object(per_approach_raw, req_path)
        if per_approach is None:
            continue
        for approach_id in per_approach:
            if approach_id not in approach_ids:
                v.error(pointer(req_path, approach_id), "unknown approach id: " + approach_id)
        requirement = requirements.get(requirement_id)
        if requirement is None or requirement.get("scope") == "out":
            continue
        for approach_id in approach_ids:
            if approach_id not in per_approach:
                v.error(pointer(req_path, approach_id), "missing score for approach " + approach_id)
    for requirement_id, per_approach_raw in scores.items():
        if not isinstance(per_approach_raw, dict):
            continue
        for approach_id, score_raw in per_approach_raw.items():
            path = pointer(pointer("/scores", requirement_id), approach_id)
            score = v.object(score_raw, path)
            if score is None:
                continue
            status = _required(v, score, "status", path)
            if "status" in score:
                v.enum(status, SCORE_STATUSES, pointer(path, "status"))
            _optional_string(v, score, "qualifier", path)
            for key in ("wording", "note", "requirementHash", "requirementText"):
                _string_field(v, score, key, path)
            _required_string_array(v, score, "citations", path)
            _optional_string(v, score, "check", path)
            if "history" in score:
                _validate_history(v, score["history"], pointer(path, "history"))
            current = hashes.get(requirement_id)
            claimed = score.get("requirementHash")
            if current is not None and isinstance(claimed, str) and claimed != current:
                warnings.append("warning: " + path + ": scored against older requirement text")


def _validate_history(v: Validator, raw: Any, path: str) -> None:
    for index, entry_raw in enumerate(v.array(raw, path) or []):
        base = pointer(path, index)
        entry = v.object(entry_raw, base)
        if entry is None:
            continue
        previous = _required(v, entry, "previous", base)
        if "previous" in entry:
            previous_path = pointer(base, "previous")
            previous_obj = v.object(previous, previous_path)
            if previous_obj is not None:
                prior_status = _required(v, previous_obj, "status", previous_path)
                if "status" in previous_obj:
                    v.enum(prior_status, SCORE_STATUSES, pointer(previous_path, "status"))
                _optional_string(v, previous_obj, "qualifier", previous_path)
        _string_field(v, entry, "challenge", base)
        _string_field(v, entry, "reply", base)
        outcome = _required(v, entry, "outcome", base)
        if "outcome" in entry:
            v.enum(outcome, HISTORY_OUTCOMES, pointer(base, "outcome"))


def _approach_id_map(v: Validator, raw: Any, path: str, approach_ids: List[str]) -> None:
    mapping = v.object(raw, path)
    for key, value in (mapping or {}).items():
        if key not in approach_ids:
            v.error(pointer(path, key), "unknown approach id: " + key)
        v.string(value, pointer(path, key))


def _validate_findings(v: Validator, root: dict, requirement_ids: set, approach_ids: List[str]) -> None:
    for index, finding_raw in enumerate(v.array(root["findings"], "/findings") or []):
        base = pointer("/findings", index)
        finding = v.object(finding_raw, base)
        if finding is None:
            continue
        requirement = _required(v, finding, "requirementId", base)
        if "requirementId" in finding and v.string(requirement, pointer(base, "requirementId"), nonempty=True):
            if requirement not in requirement_ids:
                v.error(pointer(base, "requirementId"), "unknown requirement id: " + requirement)
        approaches = _required(v, finding, "approaches", base)
        if "approaches" in finding and approaches != "all":
            listed = v.array(approaches, pointer(base, "approaches"))
            for item_index, ident in enumerate(listed or []):
                item_path = pointer(pointer(base, "approaches"), item_index)
                if v.string(ident, item_path, nonempty=True) and ident not in approach_ids:
                    v.error(item_path, "unknown approach id: " + ident)
        kind = _required(v, finding, "type", base)
        if "type" in finding:
            v.enum(kind, FINDING_TYPES, pointer(base, "type"))
        _string_field(v, finding, "text", base)
        _string_field(v, finding, "citation", base, nonempty=True)


def _validate_guidance(v: Validator, raw: Any, requirement_ids: set, approach_ids: List[str]) -> None:
    guidance = v.object(raw, "/guidance")
    if guidance is None:
        return
    _string_field(v, guidance, "intro", "/guidance")
    steps = _required_array(v, guidance, "steps", "/guidance")
    for index, step_raw in enumerate(steps or []):
        base = pointer("/guidance/steps", index)
        step = v.object(step_raw, base)
        if step is None:
            continue
        _string_field(v, step, "title", base)
        _string_field(v, step, "body", base)
        tab = _required(v, step, "tab", base)
        if "tab" in step:
            v.enum(tab, COMPARE_TAB_KEYS, pointer(base, "tab"))
    if "questions" in guidance:
        v.string_array(guidance["questions"], "/guidance/questions")
    else:
        v.error("/guidance/questions", "required key is missing")
    recommendation_raw = _required(v, guidance, "recommendation", "/guidance")
    if "recommendation" in guidance:
        rec_path = "/guidance/recommendation"
        rec = v.object(recommendation_raw, rec_path)
        if rec is not None:
            approach = _required(v, rec, "approachId", rec_path)
            if "approachId" in rec and v.string(approach, pointer(rec_path, "approachId"), nonempty=True):
                if approach not in approach_ids:
                    v.error(pointer(rec_path, "approachId"), "unknown approach id: " + approach)
            _string_field(v, rec, "headline", rec_path)
            confidence = _required(v, rec, "confidence", rec_path)
            if "confidence" in rec:
                v.enum(confidence, CONFIDENCE_LEVELS, pointer(rec_path, "confidence"))
            _string_field(v, rec, "confidenceReason", rec_path)
            for key in ("why", "costs", "changeMyMind"):
                _required_string_array(v, rec, key, rec_path)
    suggested = _required_array(v, guidance, "suggestedChallenges", "/guidance")
    for index, entry_raw in enumerate(suggested or []):
        base = pointer("/guidance/suggestedChallenges", index)
        entry = v.object(entry_raw, base)
        if entry is None:
            continue
        for key, known in (("requirementId", requirement_ids), ("approachId", set(approach_ids))):
            ident = _required(v, entry, key, base)
            if key in entry and v.string(ident, pointer(base, key), nonempty=True) and ident not in known:
                v.error(pointer(base, key), "unknown " + ("requirement" if key == "requirementId" else "approach") + " id: " + ident)
        _string_field(v, entry, "note", base)
        want = _required(v, entry, "want", base)
        if "want" in entry:
            v.enum(want, SCORE_STATUSES, pointer(base, "want"))
    _optional_string(v, guidance, "changeNote", "/guidance")


def validate_comparison(comparison: Any, logic: dict) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Errors and warnings for comparison.json against its signed logic.json; errors block the render."""
    v = Validator()
    warnings: List[str] = []
    root = v.object(comparison, "")
    if root is None:
        return v.errors, warnings
    kind = _required(v, root, "kind", "")
    if "kind" in root and kind != COMPARISON_KIND:
        v.error("/kind", 'expected "' + COMPARISON_KIND + '"')
    if "schemaVersion" in root:
        v.exact_version(root["schemaVersion"], "/schemaVersion", (1,))
    else:
        v.error("/schemaVersion", "required key is missing")
    built = _required(v, root, "builtAgainst", "")
    if "builtAgainst" in root:
        built_obj = v.object(built, "/builtAgainst")
        if built_obj is not None:
            signoff_id = _string_field(v, built_obj, "signoffRenderId", "/builtAgainst", nonempty=True)
            expected = (logic.get("signoff") or {}).get("renderId") if isinstance(logic.get("signoff"), dict) else None
            if isinstance(signoff_id, str) and expected is not None and signoff_id != expected:
                warnings.append("warning: /builtAgainst/signoffRenderId differs from logic.signoff.renderId")

    flow_stages: Optional[list] = None
    if "flowStages" in root:
        listed = v.string_array(root["flowStages"], "/flowStages", nonempty_items=True)
        if listed is not None:
            flow_stages = listed
            if not 3 <= len(listed) <= 8:
                v.error("/flowStages", "expected 3 to 8 stages")
    example_stages: Optional[list] = None
    if "example" in root:
        example = v.object(root["example"], "/example")
        if example is not None:
            _string_field(v, example, "scenario", "/example")
            stages = _required(v, example, "stages", "/example")
            if "stages" in example:
                example_stages = v.string_array(stages, "/example/stages")

    approach_ids: List[str] = []
    approaches_raw = _required(v, root, "approaches", "")
    if "approaches" in root:
        approaches = v.array(approaches_raw, "/approaches")
        if approaches is not None:
            if not 2 <= len(approaches) <= 5:
                v.error("/approaches", "expected 2 to 5 approaches, found " + str(len(approaches)))
            seen: Dict[str, str] = {}
            for index, raw in enumerate(approaches):
                path = pointer("/approaches", index)
                if isinstance(raw, dict) and "id" in raw:
                    ident = raw["id"]
                    id_path = pointer(path, "id")
                    if not isinstance(ident, str) or not re.fullmatch(r"[A-Z]", ident):
                        v.error(id_path, "expected a single uppercase letter A-Z")
                    elif ident in seen:
                        v.error(id_path, "duplicate approach id; first used at " + seen[ident])
                    else:
                        seen[ident] = id_path
                        approach_ids.append(ident)
                elif isinstance(raw, dict):
                    v.error(pointer(path, "id"), "required key is missing")
                _validate_approach(v, raw, path, flow_stages, example_stages)
            for index, raw in enumerate(approaches):
                if isinstance(raw, dict) and "rivalClaims" in raw:
                    claims_path = pointer(pointer("/approaches", index), "rivalClaims")
                    claims = v.object(raw["rivalClaims"], claims_path)
                    for other, items in (claims or {}).items():
                        if other not in approach_ids:
                            v.error(pointer(claims_path, other), "unknown approach id: " + other)
                        elif other == raw.get("id"):
                            v.error(pointer(claims_path, other), "an approach cannot rival itself")
                        v.string_array(items, pointer(claims_path, other))

    requirement_ids = {
        item["id"]
        for item in logic.get("requirements", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    _validate_scores(v, root, logic, approach_ids, warnings)
    if "findings" in root:
        _validate_findings(v, root, requirement_ids, approach_ids)
    for index, pairing_raw in enumerate(v.array(root["pairings"], "/pairings") or [] if "pairings" in root else []):
        base = pointer("/pairings", index)
        pairing = v.object(pairing_raw, base)
        if pairing is None:
            continue
        _string_field(v, pairing, "name", base, nonempty=True)
        _string_field(v, pairing, "text", base)
        items = _required(v, pairing, "items", base)
        if "items" in pairing:
            _approach_id_map(v, items, pointer(base, "items"), approach_ids)
    for index, choice_raw in enumerate(v.array(root["choices"], "/choices") or [] if "choices" in root else []):
        base = pointer("/choices", index)
        choice = v.object(choice_raw, base)
        if choice is None:
            continue
        _string_field(v, choice, "question", base, nonempty=True)
        answers = _required(v, choice, "answers", base)
        if "answers" in choice:
            _approach_id_map(v, answers, pointer(base, "answers"), approach_ids)
    if "keyDifferences" in root:
        v.string_array(root["keyDifferences"], "/keyDifferences")
    if "guidance" in root:
        _validate_guidance(v, root["guidance"], requirement_ids, approach_ids)
    return v.errors, warnings


def load_comparison(spec_dir: Path, logic: dict) -> Tuple[Optional[dict], Optional[str], int]:
    """Load comparison.json beside logic.json. Status 0 means loaded or absent; 1 means invalid."""
    if logic.get("schemaVersion") != 2:
        return None, None, 0
    path = spec_dir / "comparison.json"
    if not path.exists():
        return None, None, 0
    if not spec_is_signed_stage2(logic):
        print(UNSIGNED_COMPARISON_WARNING, file=sys.stderr)
        return None, None, 0
    value, errors = load_json(path, str(path))
    warnings: List[str] = []
    if not errors:
        errors, warnings = validate_comparison(value, logic)
    if errors:
        emit_errors(errors)
        return None, None, 1
    for warning in warnings:
        print(warning, file=sys.stderr)
    try:
        return value, comparison_id(value), 0
    except UnicodeError as exc:
        print("/: comparison.json contains invalid Unicode: " + str(exc), file=sys.stderr)
        return None, None, 1
    except ValueError as exc:
        print("/: " + str(exc), file=sys.stderr)
        return None, None, 1


def _export_kind(export_path: Path) -> Optional[str]:
    """The export's "kind" alone, so callers can route before full shape validation; None when unreadable."""
    value, errors = load_json(export_path, str(export_path))
    if errors or not isinstance(value, dict):
        return None
    kind = value.get("kind")
    return kind if isinstance(kind, str) else None


def validate_compare_export_shape(export: Any) -> List[Tuple[str, str]]:
    v = Validator()
    root = v.object(export, "")
    if root is None:
        return v.errors
    kind = _required(v, root, "kind", "")
    if "kind" in root and kind != COMPARE_EXPORT_KIND:
        v.error("/kind", 'expected "' + COMPARE_EXPORT_KIND + '"')
    if "schemaVersion" in root:
        v.exact_version(root["schemaVersion"], "/schemaVersion", (1,))
    else:
        v.error("/schemaVersion", "required key is missing")
    for key in ("slug", "renderId", "comparisonId"):
        _string_field(v, root, key, "", nonempty=True)
    exported_at = _required(v, root, "exportedAt", "")
    if "exportedAt" in root:
        v.iso_datetime(exported_at, "/exportedAt")
    challenges_raw = _required(v, root, "challenges", "")
    if "challenges" in root:
        seen: Dict[str, str] = {}
        for index, raw in enumerate(v.array(challenges_raw, "/challenges") or []):
            base = pointer("/challenges", index)
            challenge = v.object(raw, base)
            if challenge is None:
                continue
            ident = _required(v, challenge, "id", base)
            if "id" in challenge and v.string(ident, pointer(base, "id"), nonempty=True):
                if ident in seen:
                    v.error(pointer(base, "id"), "duplicate challenge id; first used at " + seen[ident])
                else:
                    seen[ident] = pointer(base, "id")
            target_type = _validate_challenge_target(v, challenge, base)
            _string_field(v, challenge, "note", base, nonempty=True)
            want = _required(v, challenge, "want", base)
            if "want" in challenge and target_type is not None:
                choices = SCORE_STATUSES if target_type == "score" else tuple(POINT_MAP)
                v.enum(want, choices, pointer(base, "want"))
            elif "want" in challenge:
                v.string(want, pointer(base, "want"), nonempty=True)
            _string_field(v, challenge, "targetHash", base, nonempty=True)
    stars = _required(v, root, "stars", "")
    if "stars" in root:
        v.string_array(stars, "/stars", nonempty_items=True)
    revisions = _required(v, root, "approachRevisions", "")
    if "approachRevisions" in root:
        revisions_obj = v.object(revisions, "/approachRevisions")
        for key, value in (revisions_obj or {}).items():
            v.string(value, pointer("/approachRevisions", key))
    return v.errors


def _validate_challenge_target(v: Validator, challenge: dict, base: str) -> Optional[str]:
    target_path = pointer(base, "target")
    target = v.object(challenge["target"], target_path) if "target" in challenge else None
    if "target" not in challenge:
        v.error(target_path, "required key is missing")
    if target is None:
        return None
    target_type = _required(v, target, "type", target_path)
    if "type" not in target or not v.enum(target_type, ("score", "slice"), pointer(target_path, "type")):
        return None
    keys = ("requirementId", "approachId") if target_type == "score" else ("approachId", "sliceId")
    for key in keys:
        _string_field(v, target, key, target_path, nonempty=True)
    return target_type


def _resolve_challenge_target(comparison: dict, target: dict) -> Optional[Tuple[str, dict]]:
    """The score or slice a challenge aims at, with its target kind, or None when it no longer exists."""
    approach_id = target["approachId"]
    if target["type"] == "score":
        score = comparison.get("scores", {}).get(target["requirementId"], {}).get(approach_id)
        return ("score", score) if isinstance(score, dict) else None
    for approach in comparison.get("approaches", []):
        if approach.get("id") == approach_id:
            for item in approach.get("slices", []):
                if item.get("id") == target["sliceId"]:
                    return "slice", item
    return None


def _check_compare_export(spec_dir: Path, export_path: Path) -> Tuple[Optional[dict], Optional[dict], Optional[dict], int]:
    """Shared validation for stage-3 check-export and challenges: (export, comparison, logic, exit code)."""
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return None, None, None, 1
    comparison, current_comparison_id, status = load_comparison(spec_dir, logic)
    if status:
        return None, None, None, 1
    value, errors = load_export_file(export_path)
    if not errors:
        errors = validate_compare_export_shape(value)
    if errors:
        emit_errors(errors)
        return None, None, None, 1
    if value.get("slug") != spec_dir.name:
        print("export belongs to a different spec", file=sys.stderr)
        return None, None, None, 3
    if comparison is None or value.get("comparisonId") != current_comparison_id:
        print("comparison changed since this export", file=sys.stderr)
        return None, None, None, 3
    unresolved = [
        (pointer(pointer("/challenges", index), "target"), "target does not resolve to a score or slice in comparison.json")
        for index, challenge in enumerate(value["challenges"])
        if _resolve_challenge_target(comparison, challenge["target"]) is None
    ]
    if unresolved:
        emit_errors(unresolved)
        return None, None, None, 1
    return value, comparison, logic, 0


def command_check_compare_export(spec_dir: Path, export_path: Path) -> int:
    export, _, _, code = _check_compare_export(spec_dir, export_path)
    if export is None:
        return code
    print("stage-3: " + str(len(export["challenges"])) + " challenges, " + str(len(export["stars"])) + " stars")
    return 0


def command_challenges(spec_dir: Path, export_path: Path, as_json: bool) -> int:
    """Print a stage-3 export's challenges grouped by approach, ready to route to each proponent."""
    export, comparison, logic, code = _check_compare_export(spec_dir, export_path)
    if export is None or comparison is None or logic is None:
        return code
    requirement_text = {
        item["id"]: item.get("text", "")
        for item in logic.get("requirements", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    groups: Dict[str, List[dict]] = {}
    for challenge in export["challenges"]:
        target = challenge["target"]
        kind, current = _resolve_challenge_target(comparison, target) or ("", {})
        entry: Dict[str, Any] = {"id": challenge["id"], "type": target["type"]}
        if kind == "score":
            entry["requirementId"] = target["requirementId"]
            entry["requirementText"] = requirement_text.get(target["requirementId"], "")
            entry["current"] = current.get("status")
            if current.get("qualifier"):
                entry["currentQualifier"] = current["qualifier"]
        else:
            entry["sliceId"] = target["sliceId"]
            entry["sliceName"] = current.get("name", "")
            entry["current"] = current.get("size")
        entry["note"] = challenge["note"]
        entry["want"] = challenge["want"]
        entry["targetChanged"] = target_hash(current, kind) != challenge["targetHash"]
        groups.setdefault(target["approachId"], []).append(entry)
    ordered = {
        approach["id"]: groups[approach["id"]]
        for approach in comparison.get("approaches", [])
        if approach.get("id") in groups
    }
    if as_json:
        print(json.dumps({**ordered, "stars": export["stars"]}, ensure_ascii=False, indent=2))
        return 0
    for approach_id, entries in ordered.items():
        print("Approach " + approach_id)
        for entry in entries:
            if entry["type"] == "score":
                print("  [" + entry["id"] + "] " + entry["requirementId"] + ": " + entry["requirementText"])
            else:
                print("  [" + entry["id"] + "] slice " + entry["sliceId"] + ": " + entry["sliceName"])
            current = str(entry["current"]) + (" (" + entry["currentQualifier"] + ")" if entry.get("currentQualifier") else "")
            print("    current: " + current)
            print("    reviewer note: " + entry["note"])
            print("    wants: " + entry["want"])
            if entry["targetChanged"]:
                print("    target changed")
        print()
    print("Stars: " + (", ".join(export["stars"]) if export["stars"] else "none"))
    return 0


def logic_placement(requirement: dict) -> str:
    if requirement["scope"] == "out":
        return "out"
    return "conditional" if "condition" in requirement else "in"


def effective_placement(state: dict, requirement: dict) -> str:
    return state["placements"].get(requirement["id"], logic_placement(requirement))


def effective_condition(state: dict, requirement: dict) -> Optional[str]:
    if effective_placement(state, requirement) != "conditional":
        return None
    return state["conditions"].get(requirement["id"], requirement.get("condition"))


def placement_changed(state: dict, requirement: dict) -> bool:
    original = logic_placement(requirement)
    final = effective_placement(state, requirement)
    if final != original:
        return True
    return final == "conditional" and effective_condition(state, requirement) != requirement.get("condition")


def render_markdown(logic: dict) -> str:
    lines: List[str] = [
        "<!-- generated from logic.json by render_spec.py — do not edit -->",
        "",
        "# " + logic["title"],
        "",
        "## Status & amendments",
        "",
        "**Status:** " + logic["status"],
        "",
        "**Amendments:**",
    ]
    amendments = logic["amendments"]
    if amendments:
        lines.extend("- " + item["date"] + " — " + item["text"] for item in amendments)
    else:
        lines.append("none")
    sections = logic["sections"]
    for heading, key in (("Purpose", "purpose"), ("Conceptual model", "conceptualModel"), ("Data flow", "dataFlow")):
        lines.extend(["", "## " + heading, "", sections[key]])

    lines.extend(["", "## Behavior & scenarios", ""])
    for index, scenario in enumerate(logic["scenarios"], 1):
        lines.append(str(index) + ". **" + scenario["id"] + "**")
        lines.append("   - **Given** " + scenario["given"])
        lines.append("   - **When** " + scenario["when"])
        lines.append("   - **Then** " + scenario["then"])
        if scenario["alternatives"]:
            lines.append("   - **Alternatives** " + "; ".join(scenario["alternatives"]))
        lines.append("   - " + scenario["explanation"])
        if scenario["refs"]:
            lines.append("   - **Requirements** " + ", ".join(scenario["refs"]))
        if "requestId" in scenario:
            lines.append("   - **Request** " + scenario["requestId"])
        lines.append("")

    lines.extend(["## Requirements", ""])
    requirements = logic["requirements"]
    groups = (
        ("In scope", [r for r in requirements if r["scope"] == "in" and "condition" not in r], False),
        ("Conditionally in scope", [r for r in requirements if r["scope"] == "in" and "condition" in r], True),
        ("Out of scope", [r for r in requirements if r["scope"] == "out"], False),
    )
    for heading, rows, conditional in groups:
        lines.extend(["### " + heading, ""])
        header = "| ID | Area | Requirement | Summary | Detail | Group | Provenance |"
        if conditional:
            header = "| ID | Area | Condition | Requirement | Summary | Detail | Group | Provenance |"
        lines.extend([header, "|" + "---|" * (8 if conditional else 7)])
        for item in rows:
            cells = [item["id"], item["area"]]
            if conditional:
                cells.append(item["condition"])
            cells.extend((item["text"], item["summary"], item["detail"], item["group"], item["provenance"]))
            lines.append("| " + " | ".join(markdown_cell(cell) for cell in cells) + " |")
        if not rows:
            lines.append("| _None_ |" + " |" * (7 if conditional else 6))
        lines.append("")

    lines.extend(["## Assumptions & blind spots", "", "### Assumptions", ""])
    for item in logic["assumptions"]:
        lines.append("- **" + item["id"] + " — " + item["claim"] + "** (" + item["certainty"] + ")")
        lines.append("  - Basis: " + item["basis"])
        lines.append("  - If wrong: " + item["ifWrong"])
        lines.append("  - Affects: " + (", ".join(item["affects"]) or "none"))
        lines.append("  - Meaning: " + item["meaning"])
        lines.append("  - Check: " + item["check"] + " (cost: " + item["checkCost"] + ")")
        if "ruling" in item:
            lines.append("  - Reviewer ruling: " + item["ruling"] + (" — " + item["rulingNote"] if item.get("rulingNote") else ""))
    if not logic["assumptions"]:
        lines.append("None.")
    lines.extend(["", "### Blind spots", ""])
    research_by_spot: Dict[str, List[dict]] = {}
    for finding in logic["research"]:
        research_by_spot.setdefault(finding["blindSpotId"], []).append(finding)
    for item in logic["blindSpots"]:
        lines.append("- **" + item["id"] + " — " + item["title"] + "**")
        lines.append("  - " + item["detail"])
        lines.append("  - Sources: " + (", ".join(item["sources"]) or "none"))
        if "resolvedBy" in item:
            lines.append("  - Resolved by: " + item["resolvedBy"])
        if "acceptance" in item:
            lines.append("  - Reviewer acceptance: " + item["acceptance"])
        for finding in research_by_spot.get(item["id"], []):
            lines.append("  - **Research finding (" + finding["answeredAt"] + ")** " + finding["summary"] + " — " + finding["detail"])
    if not logic["blindSpots"]:
        lines.append("None.")

    lines.extend(["", "## Decisions Locked", ""])
    decisions_by_area: Dict[str, List[str]] = {}
    for item in sections["decisionsLocked"]:
        decisions_by_area.setdefault(item["area"], []).append(item["decision"])
    for area, decisions in decisions_by_area.items():
        lines.append("### " + area)
        lines.append("")
        lines.extend("- " + decision for decision in decisions)
        lines.append("")
    if not decisions_by_area:
        lines.append("None.")

    lines.extend(["", "## Industry Insights", ""])
    for item in sections["industryInsights"]:
        suffix = " — " + ", ".join(item["sources"]) if item["sources"] else ""
        lines.append("- " + item["finding"] + suffix)
    if not sections["industryInsights"]:
        lines.append("None.")

    lines.extend(["", "## Scope & non-goals", ""])
    lines.extend("- " + item for item in sections["scopeNonGoals"])
    if not sections["scopeNonGoals"]:
        lines.append("None.")

    lines.extend(["", "## Deferred Ideas", ""])
    for item in sections["deferredIdeas"]:
        prefix = "[tech-spec] " if item["techSpec"] else ""
        lines.append("- " + prefix + item["text"])
    if not sections["deferredIdeas"]:
        lines.append("None.")

    lines.extend(["", "## Glossary", "", "| Term | Definition |", "|---|---|"])
    for item in sections["glossary"]:
        lines.append("| " + markdown_cell(item["term"]) + " | " + markdown_cell(item["definition"]) + " |")
    if not sections["glossary"]:
        lines.append("| _None_ | |")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown_v2(logic: dict) -> str:
    lines: List[str] = [
        "<!-- generated from logic.json by render_spec.py — do not edit -->",
        "",
        "# " + logic["title"],
        "",
        "## Status & amendments",
        "",
        "**Status:** " + logic["status"],
        "",
        "**Amendments:**",
    ]
    amendments = logic["amendments"]
    if amendments:
        lines.extend("- " + item["date"] + " — " + item["text"] for item in amendments)
    else:
        lines.append("none")
    sections = logic["sections"]
    for heading, key in (("Purpose", "purpose"), ("Conceptual model", "conceptualModel"), ("Data flow", "dataFlow")):
        lines.extend(["", "## " + heading, "", sections[key]])

    lines.extend(["", "## Behavior & scenarios", ""])
    scenarios_by_behavior: Dict[str, List[dict]] = {}
    for scenario in logic["scenarios"]:
        scenarios_by_behavior.setdefault(scenario["behavior"], []).append(scenario)
    for behavior in logic["behaviors"]:
        lines.append("### " + behavior["rule"])
        lines.append("")
        if behavior.get("detail"):
            lines.append(behavior["detail"])
            lines.append("")
        for index, scenario in enumerate(scenarios_by_behavior.get(behavior["id"], []), 1):
            lines.append(str(index) + ". **" + scenario["id"] + "**")
            lines.append("   - **Given** " + scenario["given"])
            lines.append("   - **When** " + scenario["when"])
            lines.append("   - **Then** " + scenario["then"])
            if scenario["alternatives"]:
                lines.append("   - **Alternatives** " + "; ".join(scenario["alternatives"]))
            lines.append("   - " + scenario["explanation"])
            if scenario.get("dropReason"):
                lines.append("   - **Dropped:** " + scenario["dropReason"])
            if scenario.get("flagged"):
                lines.append("   - **Flagged for deeper review**")
            lines.append("")

    lines.extend(["## Constraints", "", "| ID | Kind | Text | Ruling |", "|---|---|---|---|"])
    for item in logic["constraints"]:
        ruling = item.get("ruling", "pending")
        lines.append("| " + " | ".join(markdown_cell(cell) for cell in (item["id"], item["kind"], item["text"], ruling)) + " |")
    if not logic["constraints"]:
        lines.append("| _None_ | | | |")

    lines.extend(["", "## Requirements", ""])
    if logic["stage"] == 1:
        lines.append("Derived after stage 1 is signed.")
    else:
        requirements = logic["requirements"]
        groups = (
            ("In scope", [r for r in requirements if r["scope"] == "in" and "condition" not in r], False),
            ("Conditionally in scope", [r for r in requirements if r["scope"] == "in" and "condition" in r], True),
            ("Out of scope", [r for r in requirements if r["scope"] == "out"], False),
        )
        for heading, rows, conditional in groups:
            lines.extend(["### " + heading, ""])
            header = "| ID | Area | Requirement | Summary | Detail | Group | Derived from |"
            if conditional:
                header = "| ID | Area | Condition | Requirement | Summary | Detail | Group | Derived from |"
            lines.extend([header, "|" + "---|" * (8 if conditional else 7)])
            for item in rows:
                cells = [item["id"], item["area"]]
                if conditional:
                    cells.append(item["condition"])
                cells.extend((item["text"], item["summary"], item["detail"], item["group"], ", ".join(item["derivedFrom"])))
                lines.append("| " + " | ".join(markdown_cell(cell) for cell in cells) + " |")
            if not rows:
                lines.append("| _None_ |" + " |" * (7 if conditional else 6))
            lines.append("")

    lines.extend(["## Assumptions & blind spots", "", "### Assumptions", ""])
    for item in logic["assumptions"]:
        certainty = item["certainty"]
        if "originalCertainty" in item:
            certainty += ", set by the reviewer; Claude said " + item["originalCertainty"]
        lines.append("- **" + item["id"] + " — " + item["claim"] + "** (" + certainty + ")")
        lines.append("  - Basis: " + item["basis"])
        lines.append("  - If wrong: " + item["ifWrong"])
        lines.append("  - Affects: " + (", ".join(item["affects"]) or "none"))
        lines.append("  - Meaning: " + item["meaning"])
        lines.append("  - Check: " + item["check"] + " (cost: " + item["checkCost"] + ")")
        if "ruling" in item:
            lines.append("  - Reviewer ruling: " + item["ruling"] + (" — " + item["rulingNote"] if item.get("rulingNote") else ""))
    if not logic["assumptions"]:
        lines.append("None.")
    lines.extend(["", "### Blind spots", ""])
    research_by_spot: Dict[str, List[dict]] = {}
    for finding in logic["research"]:
        research_by_spot.setdefault(finding["blindSpotId"], []).append(finding)
    for item in logic["blindSpots"]:
        lines.append("- **" + item["id"] + " — " + item["title"] + "**")
        lines.append("  - " + item["detail"])
        lines.append("  - Sources: " + (", ".join(item["sources"]) or "none"))
        if "resolvedBy" in item:
            lines.append("  - Resolved by: " + item["resolvedBy"])
        if "acceptance" in item:
            lines.append("  - Reviewer acceptance: " + item["acceptance"])
        if "researchRequest" in item:
            question = item["researchRequest"]["question"].strip() or "a general deeper look"
            lines.append("  - Research requested at sign-off: " + question)
        for finding in research_by_spot.get(item["id"], []):
            lines.append("  - **Research finding (" + finding["answeredAt"] + ")** " + finding["summary"] + " — " + finding["detail"])
    if not logic["blindSpots"]:
        lines.append("None.")

    lines.extend(["", "## Decisions Locked", ""])
    decisions_by_area: Dict[str, List[str]] = {}
    for item in sections["decisionsLocked"]:
        decisions_by_area.setdefault(item["area"], []).append(item["decision"])
    for area, decisions in decisions_by_area.items():
        lines.append("### " + area)
        lines.append("")
        lines.extend("- " + decision for decision in decisions)
        lines.append("")
    if not decisions_by_area:
        lines.append("None.")

    lines.extend(["", "## Industry Insights", ""])
    for item in sections["industryInsights"]:
        suffix = " — " + ", ".join(item["sources"]) if item["sources"] else ""
        lines.append("- " + item["finding"] + suffix)
    if not sections["industryInsights"]:
        lines.append("None.")

    lines.extend(["", "## Scope & non-goals", ""])
    lines.extend("- " + item for item in sections["scopeNonGoals"])
    dropped = [scenario for scenario in logic["scenarios"] if scenario.get("dropReason")]
    for scenario in dropped:
        lines.append("- Dropped scenario " + scenario["id"] + ": " + scenario["dropReason"])
    rejected = [item for item in logic["constraints"] if item.get("ruling") == "rejected"]
    for item in rejected:
        lines.append("- Rejected constraint " + item["id"] + ": " + item.get("rejectReason", ""))
    if not sections["scopeNonGoals"] and not dropped and not rejected:
        lines.append("None.")

    lines.extend(["", "## Deferred Ideas", ""])
    for item in sections["deferredIdeas"]:
        prefix = "[tech-spec] " if item["techSpec"] else ""
        lines.append("- " + prefix + item["text"])
    if not sections["deferredIdeas"]:
        lines.append("None.")

    lines.extend(["", "## Glossary", "", "| Term | Definition |", "|---|---|"])
    for item in sections["glossary"]:
        lines.append("| " + markdown_cell(item["term"]) + " | " + markdown_cell(item["definition"]) + " |")
    if not sections["glossary"]:
        lines.append("| _None_ | |")
    return "\n".join(lines).rstrip() + "\n"


def markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def gitignore_contents(spec_dir: Path) -> str:
    path = spec_dir / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    additions = [entry for entry in ("review.html", "*-decisions-*.json") if entry not in lines]
    if additions:
        if existing and not existing.endswith(("\n", "\r")):
            existing += "\n"
        existing += "\n".join(additions) + "\n"
    return existing


def write_files_atomically(files: Dict[Path, str]) -> None:
    for path in files:
        if path.is_dir():
            raise OSError("output path is a directory: " + str(path))

    current_umask = os.umask(0)
    os.umask(current_umask)
    default_mode = 0o666 & ~current_umask
    staged: Dict[Path, Path] = {}
    try:
        for path, content in files.items():
            descriptor, temporary_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
            temporary = Path(temporary_name)
            staged[path] = temporary
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else default_mode
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                target.write(content)
            os.chmod(temporary, mode)
        for path in files:
            os.replace(staged[path], path)
    finally:
        for temporary in staged.values():
            try:
                temporary.unlink()
            except OSError:
                pass


def prepare_render_files(
    spec_dir: Path,
    logic: dict,
    current_render_id: str,
    prior: Any = None,
    comparison: Optional[dict] = None,
    comparison_id: Optional[str] = None,
) -> Tuple[str, str]:
    template_path = Path(__file__).resolve().with_name("review-template.html")
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("cannot read review template: " + str(exc))
    if template.count(PAYLOAD_PLACEHOLDER) != 1:
        raise ValueError("review template must contain exactly one payload placeholder")
    markdown = render_markdown_v2(logic) if logic.get("schemaVersion") == 2 else render_markdown(logic)
    try:
        payload = {
            "spec": logic,
            "slug": spec_dir.name,
            "renderId": current_render_id,
            "itemHashes": item_hashes(logic),
            "logicMarkdown": markdown,
            "priorDecisions": prior,
        }
        if comparison is not None and comparison_id is not None:
            payload["comparison"] = comparison
            payload["comparisonId"] = comparison_id
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except RecursionError:
        raise ValueError("logic.json is too deeply nested to render")
    serialized = serialized.replace("<", "\\u003c")
    html = template.replace(PAYLOAD_PLACEHOLDER, PAYLOAD_OPEN + serialized + PAYLOAD_CLOSE)
    return html, markdown


def render_files(
    spec_dir: Path,
    logic: dict,
    current_render_id: str,
    prior: Any = None,
    open_page: bool = False,
    comparison: Optional[dict] = None,
    comparison_id: Optional[str] = None,
) -> None:
    if logic.get("schemaVersion") == 1:
        # v1 specs are read-only: no page review, so no review.html is written.
        markdown = render_markdown(logic)
        outputs = {
            spec_dir / "logic.md": markdown,
            spec_dir / ".gitignore": gitignore_contents(spec_dir),
        }
        write_files_atomically(outputs)
        print(current_render_id)
        return
    html, markdown = prepare_render_files(spec_dir, logic, current_render_id, prior, comparison, comparison_id)
    outputs = {
        spec_dir / "review.html": html,
        spec_dir / "logic.md": markdown,
        spec_dir / ".gitignore": gitignore_contents(spec_dir),
    }
    write_files_atomically(outputs)
    print(current_render_id)
    if open_page:
        webbrowser.open((spec_dir / "review.html").resolve().as_uri())


def export_is_stale(export: dict, spec_dir: Path, current_render_id: str) -> bool:
    return export.get("slug") != spec_dir.name or export.get("renderId") != current_render_id


def load_export_file(path: Path) -> Tuple[Optional[Any], List[Tuple[str, str]]]:
    return load_json(path, str(path))


def command_validate(spec_dir: Path) -> int:
    logic, _ = load_logic(spec_dir)
    if logic is None:
        return 1
    _, _, status = load_comparison(spec_dir, logic)
    return 1 if status else 0


def command_render(spec_dir: Path, prior_path: Optional[Path], open_page: bool) -> int:
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return 1
    if logic.get("schemaVersion") == 1:
        if prior_path is not None or open_page:
            print(EXIT6_MESSAGE, file=sys.stderr)
            return 6
        try:
            render_files(spec_dir, logic, current_id)
        except (OSError, ValueError) as exc:
            print("/: " + str(exc), file=sys.stderr)
            return 1
        return 0

    comparison, loaded_comparison_id, comparison_status = load_comparison(spec_dir, logic)
    if comparison_status:
        return 1

    prior = None
    if prior_path is not None:
        prior, errors = load_json(prior_path, str(prior_path))
        if errors:
            emit_errors(errors)
            return 1
        shape_errors = validate_export_shape(prior)
        if shape_errors:
            emit_errors(shape_errors)
            return 1
        if prior.get("slug") != spec_dir.name:
            print("prior export belongs to a different spec", file=sys.stderr)
            return 3
        for warning in unmatched_answered_comments(logic, prior):
            print(warning, file=sys.stderr)
    try:
        render_files(spec_dir, logic, current_id, prior, open_page, comparison, loaded_comparison_id)
    except (OSError, ValueError) as exc:
        print("/: " + str(exc), file=sys.stderr)
        return 1
    return 0


def unmatched_answered_comments(logic: dict, prior: dict) -> List[str]:
    """Warn about each answeredComment the page will not match, since that comment then stays on the page as unanswered."""
    comments = prior.get("state", {}).get("scenarioComments", {})
    warnings = []
    for scenario in logic.get("scenarios", []):
        answered = scenario.get("answeredComment")
        if answered is None:
            continue
        if comments.get(scenario["id"], "").strip() != answered.strip():
            warnings.append(
                "warning: " + scenario["id"] + " answeredComment does not match the reviewer's comment in the prior export, so the page keeps that comment"
            )
    return warnings


def _read_export_and_validate(export_path: Path) -> Tuple[Optional[dict], int]:
    value, errors = load_export_file(export_path)
    if errors:
        emit_errors(errors)
        return None, 1
    errors = validate_export_shape(value)
    if errors:
        emit_errors(errors)
        return None, 1
    return value, 0


def command_check_export(spec_dir: Path, export_path: Path) -> int:
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return 1
    if logic.get("schemaVersion") == 1:
        print(EXIT6_MESSAGE, file=sys.stderr)
        return 6
    if _export_kind(export_path) == COMPARE_EXPORT_KIND:
        return command_check_compare_export(spec_dir, export_path)
    export, code = _read_export_and_validate(export_path)
    if code or export is None:
        return code
    print("signed" if export["signed"] else "unsigned")
    if export_is_stale(export, spec_dir, current_id) or export.get("stage") != logic["stage"]:
        return 3
    errors = logic_reference_errors(export, logic)
    if errors:
        emit_errors(errors)
        return 1
    return 0


def discover_export(
    spec_dir: Path, downloads: Path, current_render_id: str, required_stage: Optional[int] = None
) -> Optional[Path]:
    """Return the newest export for this spec across both folders, preferring the current render."""
    candidates: List[Tuple[bool, datetime, Path]] = []
    for directory in (spec_dir, downloads):
        try:
            if not directory.is_dir():
                continue
            # os.scandir raises on an unreadable directory; Path.glob swallows it instead
            with os.scandir(directory) as entries:
                names = [entry.name for entry in entries if entry.name.endswith(".json")]
            paths = sorted(directory / name for name in names)
        except OSError as exc:
            raise OSError(str(directory) + ": " + str(exc)) from exc
        for path in paths:
            value, errors = load_export_file(path)
            # unrelated or broken JSON is common in Downloads, so it is skipped silently
            if errors or not isinstance(value, dict):
                continue
            if value.get("kind") != EXPORT_KIND or value.get("slug") != spec_dir.name:
                continue
            if required_stage is not None and (value.get("schemaVersion") != 2 or value.get("stage") != required_stage):
                continue
            if validate_export_shape(value):
                continue
            exported_at = value.get("exportedAt")
            if not isinstance(exported_at, str):
                print(str(path) + ": skipping export without a valid exportedAt", file=sys.stderr)
                continue
            try:
                stamp = parse_iso_datetime(exported_at)
            except (TypeError, ValueError, OverflowError):
                print(str(path) + ": skipping export with invalid exportedAt", file=sys.stderr)
                continue
            candidates.append((value.get("renderId") == current_render_id, stamp, path.resolve()))
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[:2])[2]


def command_find_export(spec_dir: Path, downloads: Path) -> int:
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return 1
    if logic.get("schemaVersion") == 1:
        print(EXIT6_MESSAGE, file=sys.stderr)
        return 6
    try:
        found = discover_export(spec_dir, downloads, current_id, required_stage=logic["stage"])
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if found is None:
        print("no matching decision export found", file=sys.stderr)
        return 5
    print(str(move_beside_review(found, spec_dir)))
    return 0


def move_beside_review(export_path: Path, spec_dir: Path) -> Path:
    """Move an export found elsewhere into the spec folder, next to review.html, and return where it now lives.

    Never overwrites: a name already taken in the spec folder, or a failed move, leaves the export where it was.
    """
    destination = spec_dir.resolve() / export_path.name
    if export_path.parent == destination.parent or destination.exists():
        return export_path
    try:
        shutil.move(str(export_path), str(destination))
    except OSError as exc:
        print(str(export_path) + ": could not move beside review.html: " + str(exc), file=sys.stderr)
        return export_path
    return destination


def derived_requirement_status(requirement: dict, scenario_by_id: Dict[str, dict]) -> str:
    """withdrawn / flagged / active, computed from whether derivedFrom scenarios were reopened.

    Never stored; the Python and TS renderers must compute this identically.
    """
    derived_from = requirement.get("derivedFrom", [])
    if not derived_from:
        return "active"
    reopened = [ident in scenario_by_id and "reopened" in scenario_by_id[ident] for ident in derived_from]
    if all(reopened):
        return "withdrawn"
    if any(reopened):
        return "flagged"
    return "active"


def stage1_active_blind_spots(logic: dict, state: dict) -> List[dict]:
    """Active unless resolvedBy names a scenario approved-and-undropped, or a constraint ruled approve/rewrite, in state."""
    scenario_ids = {item["id"] for item in logic["scenarios"]}
    active = []
    for blind_spot in logic["blindSpots"]:
        resolved_by = blind_spot.get("resolvedBy")
        resolved = False
        if resolved_by in scenario_ids:
            resolved = bool(state["scenarioApproved"].get(resolved_by)) and not state["scenarioDrops"].get(
                resolved_by, ""
            ).strip()
        elif resolved_by is not None:
            resolved = state["constraintRulings"].get(resolved_by, {}).get("ruling") in ("approve", "rewrite")
        if not resolved:
            active.append(blind_spot)
    return active


def researched_blind_spot_ids(logic: dict, state: dict) -> set:
    """Blind spots the reviewer asked Claude to research; like a verify-first ruling, asking settles them for sign-off."""
    return {request["blindSpotId"] for request in state["researchRequests"]} | {
        finding["blindSpotId"] for finding in logic["research"]
    }


def stage1_gate_failures(logic: dict, state: dict) -> List[Tuple[str, str]]:
    failures: List[Tuple[str, str]] = []

    unresolved = []
    awaiting_update = []
    for scenario in logic["scenarios"]:
        ident = scenario["id"]
        if state["scenarioApproved"].get(ident, False):
            continue
        if state["scenarioDrops"].get(ident, "").strip():
            continue
        if state.get("scenarioUpdates", {}).get(ident, "").strip():
            awaiting_update.append(ident)
        else:
            unresolved.append(ident)
    scenario_request_ids = {scenario.get("requestId") for scenario in logic["scenarios"] if scenario.get("requestId")}
    pending_requests = [request for request in state["scenarioRequests"] if request["id"] not in scenario_request_ids]
    if unresolved or awaiting_update or pending_requests:
        detail = []
        if unresolved:
            detail.append("not resolved: " + ", ".join(unresolved))
        if awaiting_update:
            detail.append("update requested: " + ", ".join(awaiting_update))
        if pending_requests:
            detail.append("pending scenario requests: " + ", ".join(request["id"] for request in pending_requests))
        failures.append(("scenarios", "; ".join(detail)))

    missing_constraints = []
    for constraint in logic["constraints"]:
        ruling = state["constraintRulings"].get(constraint["id"])
        if not ruling:
            missing_constraints.append(constraint["id"])
            continue
        if ruling["ruling"] == "rewrite" and not ruling.get("text", "").strip():
            missing_constraints.append(constraint["id"] + " (rewrite needs text)")
        if ruling["ruling"] == "reject" and not ruling.get("reason", "").strip():
            missing_constraints.append(constraint["id"] + " (reject needs a reason)")
    if missing_constraints:
        failures.append(("constraints", "constraints need a ruling: " + ", ".join(missing_constraints)))

    missing_assumptions = []
    for assumption in logic["assumptions"]:
        decision = state["assumptions"].get(assumption["id"], {})
        ruling = decision.get("ruling")
        if ruling not in RULINGS or (ruling != "build-on" and not decision.get("note", "").strip()):
            missing_assumptions.append(assumption["id"])
    if missing_assumptions:
        failures.append(
            ("assumptions", "assumptions need a ruling and a note unless build-on: " + ", ".join(missing_assumptions))
        )

    missing_blind = []
    researched = researched_blind_spot_ids(logic, state)
    for blind_spot in stage1_active_blind_spots(logic, state):
        if blind_spot["id"] in researched:
            continue
        decision = state["blindSpots"].get(blind_spot["id"], {})
        if not decision.get("accepted") or not decision.get("note", "").strip():
            missing_blind.append(blind_spot["id"])
    if missing_blind:
        failures.append(
            (
                "blind-spots",
                "active blind spots need acceptance in the reviewer's words or a research request: "
                + ", ".join(missing_blind),
            )
        )

    return failures


def stage2_scope_warnings(logic: dict, state: dict, scenario_by_id: Dict[str, dict]) -> List[str]:
    """Same as v1's scope warnings, but withdrawn requirements neither warn nor are warned about."""
    non_withdrawn = [
        item for item in logic["requirements"] if derived_requirement_status(item, scenario_by_id) != "withdrawn"
    ]
    placements = {item["id"]: effective_placement(state, item) for item in non_withdrawn}
    warnings: List[str] = []
    for requirement in non_withdrawn:
        if placements[requirement["id"]] == "out":
            continue
        for dependency in requirement["dependsOn"]:
            if dependency in placements and placements[dependency] == "out":
                warnings.append(requirement["id"] + " depends on " + dependency + ", which is out of scope.")
    for left, right in logic["conflicts"]:
        if left in placements and right in placements and placements[left] != "out" and placements[right] != "out":
            warnings.append(left + " and " + right + " contradict each other; only one can be in scope.")
    return warnings


def stage2_gate_failures(logic: dict, state: dict) -> List[Tuple[str, str]]:
    failures: List[Tuple[str, str]] = []
    scenario_by_id = {item["id"]: item for item in logic["scenarios"]}

    approved_scenarios = {item["id"] for item in logic["scenarios"] if "dropReason" not in item}
    approved_constraints = {
        item["id"] for item in logic["constraints"] if item.get("ruling") in ("approved", "rewritten")
    }
    approved_items = approved_scenarios | approved_constraints
    derived = set()
    for requirement in logic["requirements"]:
        if derived_requirement_status(requirement, scenario_by_id) == "withdrawn":
            continue
        derived.update(requirement.get("derivedFrom", []))
    missing_derivation = sorted(approved_items - derived)
    if missing_derivation:
        failures.append(("derivation", "approved items missing a derived requirement: " + ", ".join(missing_derivation)))

    missing_reasons = []
    for requirement in logic["requirements"]:
        if derived_requirement_status(requirement, scenario_by_id) == "withdrawn":
            continue
        final = effective_placement(state, requirement)
        if placement_changed(state, requirement) and not state["moveReasons"].get(requirement["id"], "").strip():
            missing_reasons.append(requirement["id"])
        if final == "conditional" and effective_condition(state, requirement) is None:
            missing_reasons.append(requirement["id"] + " (conditional placement needs a condition)")
    if missing_reasons:
        failures.append(
            (
                "move-reasons",
                "scope changes need a reason; conditional placements need a condition: " + ", ".join(missing_reasons),
            )
        )

    warnings = stage2_scope_warnings(logic, state, scenario_by_id)
    if warnings:
        failures.append(("scope-warnings", "resolve scope warnings: " + " ".join(warnings)))

    if state["disputes"] or any("reopened" in scenario for scenario in logic["scenarios"]):
        failures.append(("disputes", "unresolved disputes or reopened scenarios remain"))

    return failures


def stage1_fold(logic: dict, export: dict) -> None:
    """Apply stage-1 decisions in place and advance the spec to stage 2. Does not write signoff."""
    state = export["state"]
    for scenario in logic["scenarios"]:
        ident = scenario["id"]
        outcome = state["scenarioOutcomes"].get(ident)
        if outcome and outcome["choice"] != "spec":
            if outcome["choice"] == "custom":
                scenario["then"] = outcome["custom"]
            else:
                scenario["then"] = scenario["alternatives"][int(outcome["choice"][4:])]
        drop_reason = state["scenarioDrops"].get(ident, "")
        if drop_reason.strip():
            scenario["dropReason"] = drop_reason
        if state.get("scenarioFlags", {}).get(ident):
            scenario["flagged"] = True
        scenario.pop("answeredComment", None)

    for constraint in logic["constraints"]:
        ruling = state["constraintRulings"].get(constraint["id"])
        if not ruling:
            continue
        if ruling["ruling"] == "approve":
            constraint["ruling"] = "approved"
        elif ruling["ruling"] == "rewrite":
            constraint["ruling"] = "rewritten"
            constraint["originalText"] = constraint["text"]
            constraint["text"] = ruling["text"]
        elif ruling["ruling"] == "reject":
            constraint["ruling"] = "rejected"
            constraint["rejectReason"] = ruling["reason"]

    for assumption in logic["assumptions"]:
        decision = state["assumptions"][assumption["id"]]
        assumption["ruling"] = decision["ruling"]
        assumption["rulingNote"] = decision["note"]
        certainty = decision.get("certainty")
        if certainty and certainty != assumption["certainty"]:
            assumption["originalCertainty"] = assumption["certainty"]
            assumption["certainty"] = certainty

    answered_request_ids = {finding["requestId"] for finding in logic["research"]}
    for blind_spot in stage1_active_blind_spots(logic, state):
        decision = state["blindSpots"].get(blind_spot["id"], {})
        if decision.get("accepted") and decision.get("note", "").strip():
            blind_spot["acceptance"] = decision["note"]
        pending = [
            request
            for request in state["researchRequests"]
            if request["blindSpotId"] == blind_spot["id"] and request["id"] not in answered_request_ids
        ]
        if pending:
            request = pending[-1]
            blind_spot["researchRequest"] = {
                "id": request["id"],
                "question": request["question"],
                "requestedAt": request["requestedAt"],
            }

    logic["stage"] = 2
    logic["status"] = "Stage 1 approved"
    logic["stage1Pin"] = {
        "signedAt": state["signedAt"],
        "renderId": export["renderId"],
        "itemHashes": stage1_item_hashes(logic),
    }


def final_fold(logic: dict, export: dict, tech_spec_requested: bool) -> None:
    state = export["state"]
    for requirement in logic["requirements"]:
        ident = requirement["id"]
        final = effective_placement(state, requirement)
        changed = placement_changed(state, requirement)
        if final == "out":
            requirement["scope"] = "out"
            requirement.pop("condition", None)
        else:
            requirement["scope"] = "in"
            if final == "conditional":
                condition = effective_condition(state, requirement)
                if condition is not None:
                    requirement["condition"] = condition
            else:
                requirement.pop("condition", None)
        if changed:
            reason = state["moveReasons"].get(ident, "")
            if reason:
                requirement["reviewReason"] = reason
            else:
                requirement.pop("reviewReason", None)

    for scenario in logic["scenarios"]:
        flagged = state.get("scenarioFlags", {}).get(scenario["id"])
        if flagged is True:
            scenario["flagged"] = True
        elif flagged is False:
            scenario.pop("flagged", None)
        reapproved_hash = scenario.get("reapprovedHash")
        if reapproved_hash:
            logic["stage1Pin"]["itemHashes"][scenario["id"]] = reapproved_hash
            del scenario["reapprovedHash"]

    logic["signoff"] = {"signedAt": state["signedAt"], "renderId": export["renderId"]}
    logic["status"] = "Approved — Tech spec: requested" if tech_spec_requested else "Approved"


def _fold_write_outputs(spec_dir: Path, logic: dict) -> Optional[str]:
    """Render and write the folded logic.json plus its outputs atomically. Returns the new renderId, or None on write failure (already reported to stderr)."""
    try:
        folded_id = render_id(logic)
        html, markdown = prepare_render_files(spec_dir, logic, folded_id)
        outputs = {
            spec_dir / "review.html": html,
            spec_dir / "logic.md": markdown,
            spec_dir / ".gitignore": gitignore_contents(spec_dir),
            spec_dir / "logic.json": json.dumps(logic, ensure_ascii=False, indent=2) + "\n",
        }
        # logic.json is installed last so a failed write never pairs an approved source with stale outputs
        write_files_atomically(outputs)
        return folded_id
    except (OSError, ValueError) as exc:
        print("/: " + str(exc), file=sys.stderr)
        return None


def command_fold(spec_dir: Path, export_path: Path, tech_spec_requested: bool) -> int:
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return 1
    if logic.get("schemaVersion") == 1:
        print(EXIT6_MESSAGE, file=sys.stderr)
        return 6
    if _export_kind(export_path) == COMPARE_EXPORT_KIND:
        print(COMPARE_EXPORT_REFUSAL, file=sys.stderr)
        return 2
    stage = logic["stage"]
    if stage == 1 and tech_spec_requested:
        print("pass --tech-spec-requested at the final fold", file=sys.stderr)
        return 2

    export, code = _read_export_and_validate(export_path)
    if code or export is None:
        return code
    if export_is_stale(export, spec_dir, current_id) or export.get("stage") != stage:
        print("export is stale or belongs to a different spec", file=sys.stderr)
        return 3
    errors = logic_reference_errors(export, logic)
    if errors:
        emit_errors(errors)
        return 1
    if not export["signed"]:
        print("export is unsigned", file=sys.stderr)
        return 4
    failures = stage1_gate_failures(logic, export["state"]) if stage == 1 else stage2_gate_failures(logic, export["state"])
    if failures:
        for gate, message in failures:
            print("gate " + gate + ": " + message, file=sys.stderr)
        return 4

    if stage == 1:
        stage1_fold(logic, export)
    else:
        final_fold(logic, export, tech_spec_requested)
        post_fold_errors, _ = validate_logic_dispatch(logic)
        if post_fold_errors:
            emit_errors(post_fold_errors)
            return 1

    folded_id = _fold_write_outputs(spec_dir, logic)
    if folded_id is None:
        return 1
    print(folded_id)
    return 0


def command_reapprove(spec_dir: Path, export_path: Path) -> int:
    logic, current_id = load_logic(spec_dir)
    if logic is None or current_id is None:
        return 1
    if logic.get("schemaVersion") == 1:
        print(EXIT6_MESSAGE, file=sys.stderr)
        return 6
    if _export_kind(export_path) == COMPARE_EXPORT_KIND:
        print(COMPARE_EXPORT_REFUSAL, file=sys.stderr)
        return 2
    if logic["stage"] != 2:
        print("reapprove is only valid in stage 2", file=sys.stderr)
        return 2

    export, code = _read_export_and_validate(export_path)
    if code or export is None:
        return code
    if export_is_stale(export, spec_dir, current_id) or export.get("stage") != 2:
        print("export is stale or belongs to a different spec", file=sys.stderr)
        return 3
    errors = logic_reference_errors(export, logic)
    if errors:
        emit_errors(errors)
        return 1

    state = export["state"]
    current_hashes = item_hashes(logic)
    reapproved_ids: List[str] = []
    for scenario in logic["scenarios"]:
        ident = scenario["id"]
        if "reopened" not in scenario:
            continue
        if not state["scenarioApproved"].get(ident):
            continue
        current_hash = current_hashes.get(ident)
        if export["seen"].get(ident) != current_hash:
            continue
        del scenario["reopened"]
        scenario["reapprovedHash"] = current_hash
        reapproved_ids.append(ident)

    if not reapproved_ids:
        print("nothing to re-approve", file=sys.stderr)
        return 4

    new_id = _fold_write_outputs(spec_dir, logic)
    if new_id is None:
        return 1
    for ident in reapproved_ids:
        print(ident)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate, render, and fold interactive logic specs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate logic.json")
    validate.add_argument("spec_dir", type=Path)
    render = subparsers.add_parser("render", help="render review.html and logic.md")
    render.add_argument("spec_dir", type=Path)
    render.add_argument("--prior", type=Path)
    render.add_argument("--open", action="store_true")
    find_export = subparsers.add_parser("find-export", help="find the latest decision export")
    find_export.add_argument("spec_dir", type=Path)
    find_export.add_argument("--downloads", type=Path)
    check = subparsers.add_parser("check-export", help="validate and check export freshness")
    check.add_argument("spec_dir", type=Path)
    check.add_argument("export", type=Path)
    fold = subparsers.add_parser("fold", help="apply a signed decision export")
    fold.add_argument("spec_dir", type=Path)
    fold.add_argument("export", type=Path)
    fold.add_argument("--tech-spec-requested", action="store_true")
    reapprove = subparsers.add_parser("reapprove", help="reapprove a reopened scenario against a stage-2 export")
    reapprove.add_argument("spec_dir", type=Path)
    reapprove.add_argument("export", type=Path)
    challenges = subparsers.add_parser("challenges", help="print stage-3 challenges grouped by approach")
    challenges.add_argument("spec_dir", type=Path)
    challenges.add_argument("export", type=Path)
    challenges.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    # the slug is the folder's basename, so "." or "sub/.." must resolve to a real name
    spec_dir = Path(os.path.abspath(args.spec_dir.expanduser()))
    if args.command == "validate":
        return command_validate(spec_dir)
    if args.command == "render":
        return command_render(spec_dir, args.prior.expanduser() if args.prior else None, args.open)
    if args.command == "find-export":
        downloads = args.downloads.expanduser() if args.downloads else Path.home() / "Downloads"
        return command_find_export(spec_dir, downloads)
    if args.command == "check-export":
        return command_check_export(spec_dir, args.export.expanduser())
    if args.command == "fold":
        return command_fold(spec_dir, args.export.expanduser(), args.tech_spec_requested)
    if args.command == "reapprove":
        return command_reapprove(spec_dir, args.export.expanduser())
    if args.command == "challenges":
        return command_challenges(spec_dir, args.export.expanduser(), args.as_json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
