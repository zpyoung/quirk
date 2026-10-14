"""The component kit's catalog and its inclusion scan.

The catalog (``vendor/kit/<version>/catalog.json``) is the one description of the kit's elements:
their attributes, the HTML they wrap and the rules a page must satisfy. ``load_catalog`` reads and
validates it for one kit version, resolving the kit through the ``VendorStore`` like any other
library. ``needs`` tells the builder whether a source uses the kit, and whether that use pulls in
Chart.js.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .vendor import VendorError, VendorStore

KIT_TAG = re.compile(r"<q-[a-z]", re.IGNORECASE)
CHART_TAG = re.compile(r"<q-chart[\s/>]", re.IGNORECASE)

KNOWN_RULES = frozenset({"max-series", "diff-notes", "heading-sections", "board-columns", "timeline-items"})
ATTRIBUTE_KINDS = ("text", "enum", "boolean", "number-list", "integer", "ident")

_TAG = re.compile(r"^q-[a-z]+(-[a-z]+)*\Z")
_ATTRIBUTE_NAME = re.compile(r"^[a-z][a-z0-9-]*\Z")
_SELECTOR = re.compile(r"^(@[a-z-]+|[a-z][a-z0-9]*(\[[a-z-]+(=[a-z-]+)?\])?|\[[a-z-]+(=[a-z-]+)?\])\Z")


class KitError(Exception):
    """The kit catalog cannot be found, read or validated; the message names every problem."""


@dataclass(frozen=True)
class Attribute:
    name: str
    required: bool
    kind: str
    description: str
    values: Optional[tuple[str, ...]] = None
    default: Optional[str] = None


@dataclass(frozen=True)
class Element:
    tag: str
    use_when: str
    parent: Optional[str]
    interactive: bool
    attributes: tuple[Attribute, ...]
    requires: tuple[tuple[str, ...], ...]
    rules: tuple[str, ...]
    children: str
    example: str


@dataclass(frozen=True)
class Catalog:
    """A validated catalog. ``elements`` maps tag to ``Element`` in catalog order."""

    kit_version: str
    global_attributes: tuple[str, ...]
    elements: dict[str, Element]


def needs(text: str) -> tuple[bool, bool]:
    """Report whether ``text`` uses the kit and whether it uses ``<q-chart>``, as ``(kit, chartjs)``.

    The scan is deliberately textual: a q-* tag inside a script string or a template still pulls the
    kit in, and ``&lt;q-chart`` (escaped, so not markup) does not.
    """
    return bool(KIT_TAG.search(text)), bool(CHART_TAG.search(text))


def load_catalog(store: VendorStore, version: Optional[str]) -> Catalog:
    """Load and validate the catalog of kit ``version`` (``None`` means the registry's current).

    Raises ``KitError`` when the kit is not registered at that version, the catalog is missing or
    not valid JSON, or any part of it breaks the schema; schema problems are reported together.
    """
    try:
        lv = store.resolve("kit", version)
    except VendorError as exc:
        raise KitError(str(exc)) from exc
    path = lv.root / "catalog.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KitError(f"kit@{lv.version}: catalog.json is missing") from None
    except (OSError, ValueError, RecursionError) as exc:
        raise KitError(f"kit@{lv.version}: catalog.json cannot be read: {exc}") from exc
    problems: list[str] = []
    catalog = _build(data, lv.version, lv.root.name, problems)
    if problems or catalog is None:
        raise KitError(f"kit@{lv.version} catalog.json: " + "; ".join(problems))
    return catalog


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _build(data: Any, version: str, dirname: str, problems: list[str]) -> Optional[Catalog]:
    if not isinstance(data, dict):
        problems.append("must be a JSON object")
        return None
    if data.get("schema") != 1 or isinstance(data.get("schema"), bool):
        problems.append(f"schema must be 1, got {data.get('schema')!r}")
    kit_version = data.get("kit_version")
    if kit_version != dirname or kit_version != version:
        problems.append(f"kit_version {kit_version!r} must equal its directory name {dirname!r}")
    globals_ = data.get("global_attributes")
    if not isinstance(globals_, list) or not all(_is_text(g) for g in globals_):
        problems.append("global_attributes must be a list of attribute names")
        globals_ = []
    raw_elements = data.get("elements")
    if not isinstance(raw_elements, list) or not raw_elements:
        problems.append("elements must be a non-empty list")
        raw_elements = []

    tags = [e.get("tag") for e in raw_elements if isinstance(e, dict)]
    elements: dict[str, Element] = {}
    for index, raw in enumerate(raw_elements):
        element = _element(raw, index, tags, problems)
        if element is not None and element.tag not in elements:
            elements[element.tag] = element
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if tag in seen:
            problems.append(f"duplicate element tag {tag!r}")
        seen.add(tag)
    for tag, element in elements.items():
        if element.parent is not None and element.parent not in elements:
            problems.append(f"{tag}: parent {element.parent!r} is not an element of this catalog")
    return Catalog(kit_version=str(kit_version), global_attributes=tuple(globals_), elements=elements)


def _element(raw: Any, index: int, tags: list[Any], problems: list[str]) -> Optional[Element]:
    if not isinstance(raw, dict):
        problems.append(f"elements[{index}] must be an object")
        return None
    tag = raw.get("tag")
    if not isinstance(tag, str) or not _TAG.match(tag):
        problems.append(f"elements[{index}]: tag {tag!r} must match ^q-[a-z]+(-[a-z]+)*$")
        return None
    mark = len(problems)
    where = tag

    use_when = raw.get("use_when")
    if not isinstance(use_when, str) or not use_when.startswith("Use when"):
        problems.append(f"{where}: use_when must be a line starting 'Use when'")
    parent = raw.get("parent")
    if parent is not None and (not isinstance(parent, str) or not _TAG.match(parent)):
        problems.append(f"{where}: parent must be null or an element tag, got {parent!r}")
        parent = None
    if not isinstance(raw.get("interactive"), bool):
        problems.append(f"{where}: interactive must be true or false")
    for key in ("children", "example"):
        if not _is_text(raw.get(key)):
            problems.append(f"{where}: {key} must be a non-empty string")

    attributes = _attributes(raw.get("attributes"), where, problems)
    requires = _requires(raw.get("requires"), where, problems)
    rules = raw.get("rules")
    if not isinstance(rules, list) or not all(isinstance(r, str) for r in rules):
        problems.append(f"{where}: rules must be a list of rule names")
        rules = []
    else:
        for rule in rules:
            if rule not in KNOWN_RULES:
                problems.append(f"{where}: unknown rule {rule!r} (known: {', '.join(sorted(KNOWN_RULES))})")
    if len(problems) > mark:
        return None
    return Element(
        tag=tag,
        use_when=use_when,
        parent=parent,
        interactive=raw["interactive"],
        attributes=attributes,
        requires=requires,
        rules=tuple(rules),
        children=raw["children"],
        example=raw["example"],
    )


def _attributes(raw: Any, where: str, problems: list[str]) -> tuple[Attribute, ...]:
    if not isinstance(raw, list):
        problems.append(f"{where}: attributes must be a list")
        return ()
    attributes: list[Attribute] = []
    names: set[str] = set()
    for i, a in enumerate(raw):
        label = f"{where}: attributes[{i}]"
        if not isinstance(a, dict):
            problems.append(f"{label} must be an object")
            continue
        name = a.get("name")
        if not isinstance(name, str) or not _ATTRIBUTE_NAME.match(name):
            problems.append(f"{label}: name {name!r} must match ^[a-z][a-z0-9-]*$")
            continue
        label = f"{where}: attribute {name}"
        if name in names:
            problems.append(f"{label} is declared twice")
        names.add(name)
        if not isinstance(a.get("required"), bool):
            problems.append(f"{label}: required must be true or false")
        kind = a.get("kind")
        if kind not in ATTRIBUTE_KINDS:
            problems.append(f"{label}: kind {kind!r} must be one of {', '.join(ATTRIBUTE_KINDS)}")
        values = a.get("values")
        if kind == "enum":
            if not isinstance(values, list) or not values or not all(_is_text(v) for v in values):
                problems.append(f"{label}: an enum needs a non-empty list of values")
                values = None
        elif values is not None:
            problems.append(f"{label}: values are only for the enum kind")
            values = None
        default = a.get("default")
        if default is not None:
            if not isinstance(default, str):
                problems.append(f"{label}: default must be a string")
            elif values is not None and default not in values:
                problems.append(f"{label}: default {default!r} is not one of its values")
        if not _is_text(a.get("description")):
            problems.append(f"{label}: description must be a non-empty string")
        if isinstance(kind, str) and isinstance(a.get("required"), bool) and _is_text(a.get("description")):
            attributes.append(
                Attribute(
                    name=name,
                    required=a["required"],
                    kind=kind,
                    description=a["description"],
                    values=tuple(values) if values is not None else None,
                    default=default if isinstance(default, str) else None,
                )
            )
    return tuple(attributes)


def _requires(raw: Any, where: str, problems: list[str]) -> tuple[tuple[str, ...], ...]:
    if not isinstance(raw, list):
        problems.append(f"{where}: requires must be a list of selector lists")
        return ()
    groups: list[tuple[str, ...]] = []
    for i, group in enumerate(raw):
        if not isinstance(group, list) or not group:
            problems.append(f"{where}: requires[{i}] must be a non-empty list of selectors")
            continue
        for selector in group:
            if not isinstance(selector, str) or not _SELECTOR.match(selector):
                problems.append(f"{where}: requires[{i}] selector {selector!r} is outside the selector grammar")
        groups.append(tuple(s for s in group if isinstance(s, str)))
    return tuple(groups)
