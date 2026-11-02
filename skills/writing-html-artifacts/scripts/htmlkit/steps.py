"""Validator for the step contract the agent sends to the companion in app mode.

``validate_step`` is the single gate a step passes before it can become current: it rejects
anything outside the ``v: 1`` contract and returns a normalized deep copy the server can render
without re-checking. Pure stdlib, no I/O.
"""
from __future__ import annotations

import copy
import re
from typing import Callable, Optional

STEP_KINDS = ("questions", "approaches", "design-section", "spec-review", "edit-card", "hand-off", "done")
STAGES = ("context", "gray-areas", "questions", "approaches", "design", "spec", "hand-off")

ID_PATTERN = re.compile(r"[a-z0-9-]{1,40}")
QUESTION_TYPES = ("single", "multi", "text")
ORIGINS = ("rail", "chat")
SPEC_FORMATS = ("markdown", "interactive")

COMMON_KEYS = {"v", "kind", "stage", "title", "intro_md", "intro_html", "changed"}
KIND_KEYS = {
    "questions": {"questions"},
    "approaches": {"approaches"},
    "design-section": {"index", "total", "sections"},
    "spec-review": {"format", "spec_path", "sections"},
    "edit-card": {"decision_id", "from", "to", "invalidates", "origin"},
    "hand-off": {"choices"},
    "done": {"message_md"},
}


class StepError(ValueError):
    """A step that breaks the contract; ``field`` is the path of the offending key ("" for the root)."""

    def __init__(self, message: str, field: str = ""):
        super().__init__(message)
        self.field = field


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _fail(path: str, message: str) -> StepError:
    return StepError(f"{path or 'step'}: {message}", field=path)


def _check_keys(obj: dict, allowed: set, path: str) -> None:
    for key in obj:
        if key not in allowed:
            raise _fail(_join(path, str(key)), "unknown field")


def _object(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise _fail(path, "must be an object")
    return value


def _list(value: object, path: str, lo: int = 0, hi: Optional[int] = None) -> list:
    if not isinstance(value, list):
        raise _fail(path, "must be a list")
    if len(value) < lo or (hi is not None and len(value) > hi):
        if hi is None:
            want = f"at least {lo}"
        elif hi == lo:
            want = str(lo)
        else:
            want = f"{lo} to {hi}"
        raise _fail(path, f"must have {want} item(s), got {len(value)}")
    return value


def _required(obj: dict, key: str, path: str) -> object:
    if key not in obj:
        raise _fail(_join(path, key), "is required")
    return obj[key]


def _string(obj: dict, key: str, path: str) -> str:
    value = _required(obj, key, path)
    if not isinstance(value, str) or not value.strip():
        raise _fail(_join(path, key), "must be a non-empty string")
    return value


def _optional_string(obj: dict, key: str, path: str, out: dict) -> None:
    """Copy an optional string into ``out``; ``""`` and a missing key both mean absent."""
    if key not in obj:
        return
    value = obj[key]
    if not isinstance(value, str):
        raise _fail(_join(path, key), "must be a string")
    if value != "":
        out[key] = value


def _id(obj: dict, key: str, path: str) -> str:
    value = _required(obj, key, path)
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise _fail(_join(path, key), "must match [a-z0-9-]{1,40}")
    return value


def _bool(obj: dict, key: str, path: str) -> bool:
    value = _required(obj, key, path)
    if not isinstance(value, bool):
        raise _fail(_join(path, key), "must be true or false")
    return value


def _int(obj: dict, key: str, path: str) -> int:
    value = _required(obj, key, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(_join(path, key), "must be an integer")
    return value


def _items(raw: dict, key: str, path: str, build: Callable[[dict, str], dict], lo: int, hi: Optional[int]) -> list:
    """Validate a list of objects with ``build``, enforcing length and per-list id uniqueness."""
    base = _join(path, key)
    items = _list(_required(raw, key, path), base, lo, hi)
    out, seen = [], set()
    for i, item in enumerate(items):
        item_path = f"{base}[{i}]"
        built = build(_object(item, item_path), item_path)
        if "id" in built:
            if built["id"] in seen:
                raise _fail(f"{item_path}.id", f"id {built['id']!r} is used twice")
            seen.add(built["id"])
        out.append(built)
    return out


def _option(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "label", "description", "preview_html"}, path)
    out = {"id": _id(raw, "id", path), "label": _string(raw, "label", path)}
    for key in ("description", "preview_html"):
        _optional_string(raw, key, path, out)
    return out


def _question(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "type", "prompt", "header", "recommended", "options", "content_html", "diagram"}, path)
    out = {"id": _id(raw, "id", path)}
    qtype = _required(raw, "type", path)
    if qtype not in QUESTION_TYPES:
        raise _fail(_join(path, "type"), f"must be one of {', '.join(QUESTION_TYPES)}")
    out["type"] = qtype
    out["prompt"] = _string(raw, "prompt", path)
    for key in ("header", "content_html", "diagram"):
        _optional_string(raw, key, path, out)
    if qtype == "text":
        for key in ("options", "recommended"):
            if key in raw:
                raise _fail(_join(path, key), "text questions take no options or recommendation")
        return out
    out["options"] = _items(raw, "options", path, _option, 2, 4)
    recommended = raw.get("recommended")
    if recommended is not None and recommended != "":
        if not isinstance(recommended, str) or recommended not in {o["id"] for o in out["options"]}:
            raise _fail(_join(path, "recommended"), "must be the id of one of the question's options")
        out["recommended"] = recommended
    return out


def _source(raw: dict, path: str) -> dict:
    _check_keys(raw, {"title", "url"}, path)
    out = {"title": _string(raw, "title", path), "url": _string(raw, "url", path)}
    if not out["url"].startswith(("http://", "https://")):
        raise _fail(_join(path, "url"), "must start with http:// or https://")
    return out


def _string_list(raw: dict, key: str, path: str) -> list:
    base = _join(path, key)
    items = _list(raw.get(key, []), base)
    for i, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise _fail(f"{base}[{i}]", "must be a non-empty string")
    return list(items)


def _approach(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "title", "summary_md", "recommended", "pros", "cons", "sources", "content_html"}, path)
    out = {
        "id": _id(raw, "id", path),
        "title": _string(raw, "title", path),
        "summary_md": _string(raw, "summary_md", path),
        "recommended": _bool(raw, "recommended", path),
        "pros": _string_list(raw, "pros", path),
        "cons": _string_list(raw, "cons", path),
    }
    sources = _list(raw.get("sources", []), _join(path, "sources"))
    out["sources"] = [_source(_object(s, f"{path}.sources[{j}]"), f"{path}.sources[{j}]") for j, s in enumerate(sources)]
    _optional_string(raw, "content_html", path, out)
    return out


def _exactly_one_recommended(items: list, path: str, noun: str) -> None:
    count = sum(1 for item in items if item["recommended"])
    if count != 1:
        raise _fail(path, f"exactly one {noun} must be recommended, got {count}")


def _design_section(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "title", "body_md", "body_html", "diagram"}, path)
    out = {"id": _id(raw, "id", path), "title": _string(raw, "title", path)}
    for key in ("body_md", "body_html", "diagram"):
        _optional_string(raw, key, path, out)
    if "body_md" not in out and "body_html" not in out:
        raise _fail(path, "needs body_md or body_html")
    return out


def _spec_section(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "title", "body_md"}, path)
    return {"id": _id(raw, "id", path), "title": _string(raw, "title", path), "body_md": _string(raw, "body_md", path)}


def _invalidated(raw: dict, path: str) -> dict:
    _check_keys(raw, {"label", "step_id"}, path)
    out = {"label": _string(raw, "label", path)}
    _optional_string(raw, "step_id", path, out)
    return out


def _choice(raw: dict, path: str) -> dict:
    _check_keys(raw, {"id", "label", "description", "recommended"}, path)
    return {
        "id": _id(raw, "id", path),
        "label": _string(raw, "label", path),
        "description": _string(raw, "description", path),
        "recommended": _bool(raw, "recommended", path),
    }


def _questions(raw: dict) -> dict:
    return {"questions": _items(raw, "questions", "", _question, 1, 4)}


def _approaches(raw: dict) -> dict:
    out = {"approaches": _items(raw, "approaches", "", _approach, 2, 3)}
    _exactly_one_recommended(out["approaches"], "approaches", "approach")
    return out


def _design_section_step(raw: dict) -> dict:
    index = _int(raw, "index", "")
    if index < 1:
        raise _fail("index", "must be at least 1")
    total = _int(raw, "total", "")
    if total < index:
        raise _fail("total", "must be at least index")
    return {"index": index, "total": total, "sections": _items(raw, "sections", "", _design_section, 1, 3)}


def _spec_review(raw: dict) -> dict:
    fmt = _required(raw, "format", "")
    if fmt not in SPEC_FORMATS:
        raise _fail("format", f"must be one of {', '.join(SPEC_FORMATS)}")
    if fmt == "interactive":
        for key in ("spec_path", "sections"):
            if key in raw:
                raise _fail(key, "interactive reviews carry neither spec_path nor sections")
        return {"format": fmt}
    return {
        "format": fmt,
        "spec_path": _string(raw, "spec_path", ""),
        "sections": _items(raw, "sections", "", _spec_section, 1, None),
    }


def _edit_card(raw: dict) -> dict:
    origin = _required(raw, "origin", "")
    if origin not in ORIGINS:
        raise _fail("origin", f"must be one of {', '.join(ORIGINS)}")
    return {
        "decision_id": _id(raw, "decision_id", ""),
        "from": _string(raw, "from", ""),
        "to": _string(raw, "to", ""),
        "invalidates": _items(raw, "invalidates", "", _invalidated, 0, None),
        "origin": origin,
    }


def _hand_off(raw: dict) -> dict:
    out = {"choices": _items(raw, "choices", "", _choice, 2, 3)}
    _exactly_one_recommended(out["choices"], "choices", "choice")
    return out


def _done(raw: dict) -> dict:
    return {"message_md": _string(raw, "message_md", "")}


def _changed(raw: object) -> dict:
    obj = _object(raw, "changed")
    _check_keys(obj, {"summary", "blocks"}, "changed")
    blocks = _list(_required(obj, "blocks", "changed"), "changed.blocks")
    for i, block in enumerate(blocks):
        if not isinstance(block, str) or not block.strip():
            raise _fail(f"changed.blocks[{i}]", "must be a non-empty string")
    return {"summary": _string(obj, "summary", "changed"), "blocks": list(blocks)}


KIND_BUILDERS = {
    "questions": _questions,
    "approaches": _approaches,
    "design-section": _design_section_step,
    "spec-review": _spec_review,
    "edit-card": _edit_card,
    "hand-off": _hand_off,
    "done": _done,
}


def validate_step(raw: object) -> dict:
    """Check ``raw`` against the ``v: 1`` step contract and return a normalized deep copy.

    Raises ``StepError`` naming the first offending field path. Never mutates ``raw``; optional
    strings equal to ``""`` are dropped and the optional lists the contract defaults are filled in.
    """
    if not isinstance(raw, dict):
        raise _fail("", "step must be a JSON object")
    raw = copy.deepcopy(raw)
    version = raw.get("v")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise _fail("v", "must be the integer 1")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in STEP_KINDS:
        raise _fail("kind", f"must be one of {', '.join(STEP_KINDS)}")
    _check_keys(raw, COMMON_KEYS | KIND_KEYS[kind], "")
    stage = raw.get("stage")
    if not isinstance(stage, str) or stage not in STAGES:
        raise _fail("stage", f"must be one of {', '.join(STAGES)}")
    out = {"v": 1, "kind": kind, "stage": stage, "title": _string(raw, "title", "")}
    for key in ("intro_md", "intro_html"):
        _optional_string(raw, key, "", out)
    if "changed" in raw:
        out["changed"] = _changed(raw["changed"])
    out.update(KIND_BUILDERS[kind](raw))
    return out
