"""The component kit's catalog and its inclusion scan.

The catalog (``vendor/kit/<version>/catalog.json``) is the one description of the kit's elements:
their attributes, the HTML they wrap and the rules a page must satisfy. ``load_catalog`` reads and
validates it for one kit version, resolving the kit through the ``VendorStore`` like any other
library. ``needs`` tells the builder whether a source uses the kit, and whether that use pulls in
Chart.js.

``check_html`` validates the q-* markup of a page or source file against the catalog and
``check_jsx`` does the narrower attribute-level check for tier-2 sources. Both report failures as
``{"check": "kit", "detail": "<label> line <n>: <message>"}``; the message phrases are stable
because tests match them.
"""
from __future__ import annotations

import bisect
import html as html_lib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterator, Optional
from .vendor import VendorError, VendorStore

KIT_TAG = re.compile(r"<q-[a-z]", re.IGNORECASE)
CHART_TAG = re.compile(r"<q-chart[\s/>]", re.IGNORECASE)
CODE_TAG = re.compile(r"<q-(?:code|diff)[\s/>]", re.IGNORECASE)
FLOW_TAG = re.compile(r"<q-flow[\s/>]", re.IGNORECASE)
SCHEMA_TAG = re.compile(r"<q-schema[\s/>]", re.IGNORECASE)

KNOWN_RULES = frozenset(
    {"max-series", "diff-notes", "heading-sections", "board-columns", "timeline-items", "compare-recommended", "flow-data", "schema-data"}
)
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


def needs_highlight(text: str) -> bool:
    """Report whether ``text`` uses ``<q-code>`` or ``<q-diff>``, which highlight with highlight.js.

    The scan is textual, like ``needs``.
    """
    return bool(CODE_TAG.search(text))



def needs_flow(text: str) -> bool:
    """Report whether ``text`` uses ``<q-flow>`` or ``<q-schema>``, which lay out and zoom with the flow bundle.

    The scan is textual, like ``needs``.
    """
    return bool(FLOW_TAG.search(text) or SCHEMA_TAG.search(text))

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


# -- the check -------------------------------------------------------------------------------------

MAX_SERIES = 8
TONES = ("neutral", "success", "warning", "danger")
_VOID = frozenset(
    "area base basefont bgsound br col embed frame hr img input keygen link meta param source track wbr".split()
)
_HEADINGS = frozenset({"h2", "h3", "h4", "h5", "h6"})
_ANY_HEADING = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_FOREIGN = frozenset({"svg", "math"})
_KIT_NAME = re.compile(r"q-[a-z]")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_DIGITS = re.compile(r"[0-9]+")
_HUNK = re.compile(r"^@@ -[0-9]{1,9}(?:,([0-9]{1,9}))? \+([0-9]{1,9})(?:,([0-9]{1,9}))? @@")
_ATTR_SELECTOR = re.compile(r"^@([a-z-]+)$")
_NODE_SELECTOR = re.compile(r"^([a-z][a-z0-9]*)?(?:\[([a-z-]+)(?:=([a-z-]+))?\])?$")

# HTML's "special" elements, which stop an implied-end-tag search for li, dd and dt
_SPECIAL = frozenset(
    (
        "address applet area article aside base basefont bgsound blockquote body br button caption center col "
        "colgroup dd details dir div dl dt embed fieldset figcaption figure footer form frame frameset h1 h2 h3 "
        "h4 h5 h6 head header hgroup hr html iframe img input keygen li link listing main marquee menu meta nav "
        "noembed noframes noscript object ol p param plaintext pre script search section select source style "
        "summary table tbody td template textarea tfoot th thead title tr track ul wbr xmp svg math"
    ).split()
)
_ITEM_STOPPERS = _SPECIAL - {"address", "div", "p"}
_TABLE_STOPPERS = frozenset({"table", "template", "html", "body"})
_CELL_STOPPERS = _TABLE_STOPPERS | {"tr"}
_STOPPER_SETS = (_ITEM_STOPPERS, _CELL_STOPPERS, _TABLE_STOPPERS)
_IMPLIED_END_TARGETS = frozenset(
    "li dd dt td th tr thead tbody tfoot caption colgroup".split()
)
_BUTTON_SCOPE = frozenset("applet caption html table td th marquee object template button svg math".split())
_CLOSES_P = frozenset(
    (
        "address article aside blockquote center details dialog dir div dl fieldset figcaption figure footer form "
        "h1 h2 h3 h4 h5 h6 header hgroup hr li dd dt listing main menu nav ol p plaintext pre search section "
        "summary table ul xmp"
    ).split()
)


class _Node:
    """One element of the tolerant tree: its attributes, source line and children."""

    __slots__ = ("tag", "attrs", "line", "parent", "children", "content", "self_closed", "order", "end")

    def __init__(self, tag: str, attrs: dict[str, str], line: int, parent: Optional["_Node"]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.parent = parent
        self.children: list[_Node] = []
        self.content: list[Any] = []  # text strings and child nodes in source order
        self.self_closed = False
        # document-order position, and the position just past the last descendant
        self.order = 0
        self.end = 0


class _TreeBuilder(HTMLParser):
    """Builds a tolerant element tree and records each element's start line.

    The stdlib parser builds no tree and keeps ``script`` and ``style`` bodies as raw text, which is
    what the kit check needs. This class adds HTML's implied end tags for the elements authors leave
    open, ignores void elements and a stray end tag, and lets an end tag close any unclosed
    descendants. Markup it cannot make sense of yields a smaller tree, never an exception.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, 0, None)
        self.stack: list[_Node] = [self.root]
        self.nodes: list[_Node] = []
        self._open = Counter()
        self._foreign = 0
        self._p_marks: list[int] = []
        self._scope_marks: list[int] = []
        # stack positions of the open elements an implied end can close, and of each stopper set
        self._target_marks: dict[str, list[int]] = {tag: [] for tag in _IMPLIED_END_TARGETS}
        self._stopper_marks: dict[frozenset, list[int]] = {stoppers: [] for stoppers in _STOPPER_SETS}

    def parse_html_declaration(self, i):
        # the stdlib's marked-section parser raises on `<![foo ]]>`, which would end the check early
        if self.rawdata.startswith("<![", i):
            return self.parse_bogus_comment(i)
        return super().parse_html_declaration(i)

    def finish(self) -> None:
        """Close what is still open at the end of the input, so every node has its ``end``."""
        for node in self.stack[1:]:
            node.end = len(self.nodes)

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        if self._open[tag] <= 0:
            return
        while self.stack[-1].tag != tag:
            self._pop()
        self._pop()

    def handle_data(self, data):
        self.stack[-1].content.append(data)

    def _push(self, node: _Node) -> None:
        self.stack.append(node)
        self._open[node.tag] += 1
        if node.tag == "p":
            self._p_marks.append(len(self.stack) - 1)
        if node.tag in _BUTTON_SCOPE:
            self._scope_marks.append(len(self.stack) - 1)
        if node.tag in _FOREIGN:
            self._foreign += 1
        if node.tag in _IMPLIED_END_TARGETS:
            self._target_marks[node.tag].append(len(self.stack) - 1)
        for stoppers, marks in self._stopper_marks.items():
            if node.tag in stoppers:
                marks.append(len(self.stack) - 1)

    def _pop(self) -> None:
        node = self.stack.pop()
        node.end = len(self.nodes)
        self._open[node.tag] -= 1
        if node.tag == "p":
            self._p_marks.pop()
        if node.tag in _BUTTON_SCOPE:
            self._scope_marks.pop()
        if node.tag in _FOREIGN:
            self._foreign -= 1
        if node.tag in _IMPLIED_END_TARGETS:
            self._target_marks[node.tag].pop()
        for stoppers, marks in self._stopper_marks.items():
            if node.tag in stoppers:
                marks.pop()

    def _close_nearest(self, targets: frozenset, stoppers: frozenset) -> bool:
        """Close the nearest open element in ``targets`` unless a stopper comes first.

        Both positions come from the marks kept on push and pop, so the stack is never rescanned.
        An element in both sets counts as the target.
        """
        nearest = max((marks[-1] for tag in targets if (marks := self._target_marks[tag])), default=0)
        blocking = self._stopper_marks[stoppers]
        if nearest == 0 or (blocking and blocking[-1] > nearest):
            return False
        while len(self.stack) > nearest:
            self._pop()
        return True

    def _imply_end(self, tag: str) -> None:
        top = self.stack[-1].tag
        if tag == "li" and self._open["li"]:
            self._close_nearest(frozenset({"li"}), _ITEM_STOPPERS)
        elif tag in ("dd", "dt") and (self._open["dd"] or self._open["dt"]):
            self._close_nearest(frozenset({"dd", "dt"}), _ITEM_STOPPERS)
        elif tag in ("td", "th") and (self._open["td"] or self._open["th"]):
            self._close_nearest(frozenset({"td", "th"}), _CELL_STOPPERS)
        elif tag == "tr":
            while self._close_nearest(frozenset({"tr", "td", "th"}), _TABLE_STOPPERS):
                pass
        elif tag in ("thead", "tbody", "tfoot"):
            while self._close_nearest(
                frozenset({"thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup"}), _TABLE_STOPPERS
            ):
                pass
        elif tag in ("option", "optgroup"):
            if top == "option":
                self._pop()
            if tag == "optgroup" and self.stack[-1].tag == "optgroup":
                self._pop()
        elif tag in _ANY_HEADING and top in _ANY_HEADING:
            self._pop()
        if tag in _CLOSES_P and self._p_marks:
            index = self._p_marks[-1]
            if not self._scope_marks or self._scope_marks[-1] < index:
                while len(self.stack) > index:
                    self._pop()

    def _start(self, tag: str, attrs: list, self_closing: bool) -> None:
        self._imply_end(tag)
        values: dict[str, str] = {}
        for name, value in attrs:
            values.setdefault(name, value if value is not None else "")
        parent = self.stack[-1]
        node = _Node(tag, values, self.getpos()[0], parent)
        node.order = len(self.nodes)
        node.end = node.order + 1
        parent.children.append(node)
        parent.content.append(node)
        self.nodes.append(node)
        node.self_closed = self_closing and tag not in _VOID
        if tag in _VOID or (self_closing and self._foreign):
            return
        self._push(node)


_TIME_DATETIME = "time[datetime]"


class _Index:
    """Per-tag lookups over the finished tree, so a rule's subtree queries never walk the subtree.

    A node's descendants are exactly the nodes whose document order falls in ``(order, end)``, so
    each query is a bisect, however deeply the page nests.
    """

    def __init__(self, nodes: list[_Node]) -> None:
        self._nodes: dict[str, list[_Node]] = {}
        self._orders: dict[str, list[int]] = {}
        self._reach: dict[str, list[int]] = {}
        self._diffs: dict[int, dict[str, set[int]]] = {}
        for node in nodes:
            self._add(node.tag, node)
            if node.tag == "time" and "datetime" in node.attrs:
                self._add(_TIME_DATETIME, node)

    def _add(self, key: str, node: _Node) -> None:
        self._nodes.setdefault(key, []).append(node)
        self._orders.setdefault(key, []).append(node.order)

    def within(self, node: _Node, key: str, skip: Optional[str] = None) -> Iterator[_Node]:
        """Descendants of ``node`` under ``key`` in document order, leaving out those below a ``skip`` element."""
        found, orders = self._nodes.get(key), self._orders.get(key)
        if not found or orders is None:
            return
        skipped, skipped_orders = self._nodes.get(skip or ""), self._orders.get(skip or "")
        pos = node.order + 1
        while True:
            i = bisect.bisect_left(orders, pos)
            if i >= len(found) or orders[i] >= node.end:
                return
            candidate = found[i]
            if skipped and skipped_orders is not None:
                j = bisect.bisect_left(skipped_orders, pos)
                if j < len(skipped) and skipped_orders[j] < candidate.order:
                    pos = skipped[j].end
                    continue
            yield candidate
            pos = candidate.order + 1

    def first(self, node: _Node, key: str, skip: Optional[str] = None) -> Optional[_Node]:
        return next(self.within(node, key, skip), None)

    def nodes_of(self, key: str) -> list[_Node]:
        """Every element indexed under ``key`` in document order; the empty list when there is none."""
        return list(self._nodes.get(key, ()))

    def diff_files(self, pre: _Node) -> dict[str, set[int]]:
        """``parse_diff`` of a ``pre``, computed once however many elements read it."""
        files = self._diffs.get(id(pre))
        if files is None:
            files = self._diffs[id(pre)] = parse_diff(_text(pre))
        return files

    def encloses(self, node: _Node, key: str) -> bool:
        """Whether some ancestor of ``node`` has the tag ``key``."""
        orders = self._orders.get(key)
        if not orders:
            return False
        reach = self._reach.get(key)
        if reach is None:
            reach = []
            furthest = 0
            for candidate in self._nodes[key]:
                furthest = max(furthest, candidate.end)
                reach.append(furthest)
            self._reach[key] = reach
        i = bisect.bisect_left(orders, node.order)
        return i > 0 and reach[i - 1] > node.order


def _text(node: _Node) -> str:
    parts: list[str] = []
    pending: list[Any] = list(reversed(node.content))
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            parts.append(item)
        else:
            pending.extend(reversed(item.content))
    return "".join(parts)


def _positive_integer(value: str) -> Optional[int]:
    """The value as an int, or ``None`` when it is not a positive integer or is absurdly long."""
    if not _DIGITS.fullmatch(value) or not value.strip("0") or len(value) > 18:
        return None
    return int(value)


def _kind_problem(attribute: Attribute, value: str) -> Optional[str]:
    """Why ``value`` does not fit the attribute's kind, as the end of a failure message."""
    kind = attribute.kind
    if kind == "enum":
        if attribute.values is not None and value not in attribute.values:
            return f"is not one of {', '.join(attribute.values)}"
    elif kind == "integer":
        if not _DIGITS.fullmatch(value) or not value.strip("0"):
            return "is not a positive integer"
    elif kind == "ident":
        if not _IDENT.fullmatch(value):
            return "is not an identifier"
    elif kind == "number-list":
        parts = [p.strip() for p in value.split(",")]
        if len(parts) < 2 or not all(_NUMBER.fullmatch(p) and math.isfinite(float(p)) for p in parts):
            return "is not a number list"
    return None


Report = Callable[[int, str], None]


def check_html(text: str, catalog: Catalog, *, label: str) -> list[dict]:
    """Validate the q-* elements of ``text`` and return one failure per problem, in source order.

    ``text`` is a built page or a tier-1 source file. ``script`` and ``style`` bodies are raw text
    and never validated, ``template`` content is ordinary markup, and a malformed document yields
    whatever checks its recoverable structure allows.
    """
    builder = _TreeBuilder()
    stopped_at: Optional[int] = None
    try:
        builder.feed(text)
        builder.close()
    except Exception:  # noqa: BLE001 - kept as a failure below, so a parser fault never reads as a pass
        stopped_at = builder.getpos()[0]
    builder.finish()
    found: list[tuple[int, int, str]] = []

    def report(line: int, message: str) -> None:
        found.append((line, len(found), message))

    index = _Index(builder.nodes)
    selectors = _below_selectors(catalog)
    below = _below_masks(builder.nodes, selectors) if selectors else {}
    for node in builder.nodes:
        if not _KIT_NAME.match(node.tag):
            continue
        element = catalog.elements.get(node.tag)
        if element is None:
            report(node.line, f"unknown element <{node.tag}>")
            continue
        if node.self_closed:
            report(node.line, f"<{node.tag}> cannot be self-closed; write <{node.tag} …></{node.tag}>")
        _check_element(node, element, report, selectors, below.get(id(node), 0), index)
    if stopped_at is not None:
        report(stopped_at, "could not parse the markup after this line; the kit check stopped here")
    found.sort()
    return [{"check": "kit", "detail": f"{label} line {line}: {message}"} for line, _, message in found]


def _check_element(
    node: _Node, element: Element, report: Report, selectors: list[str], below: int, index: _Index
) -> None:
    tag = node.tag
    for attribute in element.attributes:
        if attribute.name not in node.attrs:
            if attribute.required:
                report(node.line, f"<{tag}> needs attribute {attribute.name}")
            continue
        value = node.attrs[attribute.name]
        problem = _kind_problem(attribute, value)
        if problem:
            report(node.line, f'<{tag}> {attribute.name}="{value}" {problem}')
    if element.requires:
        for group in element.requires:
            if not any(_selector_matches(selector, node, selectors, below) for selector in group):
                names = ", ".join(s[1:] if s.startswith("@") else s for s in group)
                report(node.line, f"<{tag}> needs one of: {names}")
    if element.parent is not None and not index.encloses(node, element.parent):
        report(node.line, f"<{tag}> must be inside <{element.parent}>")
    for rule in element.rules:
        _RULES[rule](node, report, index)


def _selector_matches(selector: str, node: _Node, selectors: list[str], below: int) -> bool:
    """Whether ``node`` (for ``@attr``) or an element below it satisfies ``selector``.

    ``below`` is the bit mask ``_below_masks`` computed for ``node``, indexed by ``selectors``.
    """
    own = _ATTR_SELECTOR.match(selector)
    if own:
        return own.group(1) in node.attrs
    return selector in selectors and bool(below >> selectors.index(selector) & 1)


def _below_selectors(catalog: Catalog) -> list[str]:
    """The distinct descendant selectors the catalog's ``requires`` groups use, in first-use order."""
    found: dict[str, None] = {}
    for element in catalog.elements.values():
        for group in element.requires:
            for selector in group:
                if not _ATTR_SELECTOR.match(selector) and _NODE_SELECTOR.match(selector):
                    found[selector] = None
    return list(found)


def _node_matches(selector: str, node: _Node) -> bool:
    want_tag, want_attr, want_value = _NODE_SELECTOR.match(selector).groups()
    if want_tag is not None and node.tag != want_tag:
        return False
    if want_attr is not None:
        if want_attr not in node.attrs:
            return False
        if want_value is not None and node.attrs[want_attr] != want_value:
            return False
    return True


def _below_masks(nodes: list[_Node], selectors: list[str]) -> dict[int, int]:
    """For each element, a bit mask of the ``selectors`` some element below it satisfies.

    One reverse pass over document order (a child always follows its parent), so the work is
    linear in the page however deeply q-* elements nest.
    """
    masks: dict[int, int] = {}
    for node in reversed(nodes):
        parent = node.parent
        if parent is None:
            continue
        own = 0
        for bit, selector in enumerate(selectors):
            if _node_matches(selector, node):
                own |= 1 << bit
        masks[id(parent)] = masks.get(id(parent), 0) | own | masks.get(id(node), 0)
    return masks


def _header_row(table: _Node, index: _Index) -> Optional[_Node]:
    """The first row inside a ``thead`` of ``table``, else its first row."""
    for thead in index.within(table, "thead"):
        row = index.first(thead, "tr")
        if row is not None:
            return row
    return index.first(table, "tr")


def _rule_max_series(node: _Node, report: Report, index: _Index) -> None:
    table = index.first(node, "table", skip=node.tag)
    if table is None:
        return
    y = node.attrs.get("y")
    if y is not None:
        series = len([part for part in y.split(",") if part.strip()])
    else:
        header = _header_row(table, index)
        if header is None:
            return
        cells = [c for c in header.children if c.tag == "th"]
        if not cells:
            return
        series = max(len(cells) - 1, 0)
    if series > MAX_SERIES:
        report(node.line, f"<{node.tag}> has {series} series; the limit is {MAX_SERIES}")


def _diff_path(raw: str) -> Optional[str]:
    path = raw.split("\t", 1)[0].strip()
    if path == "/dev/null":
        return None
    return path[2:] if path.startswith("b/") else path


def parse_diff(text: str) -> dict[str, set[int]]:
    """Map each file named by a ``+++ `` header to the new-side line numbers its hunks cover.

    Context and ``+`` lines count, ``-`` lines do not. Hunk sizes are used only to tell a real
    ``--- ``/``+++ `` header pair from a removed or added line that happens to look like one, so a
    hand-written diff with wrong counts still parses.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    files: dict[str, set[int]] = {}
    current: Optional[set[int]] = None
    new_no: Optional[int] = None
    old_left = new_left = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            hunk_follows = i + 2 < len(lines) and lines[i + 2].startswith("@@")
            if not (old_left > 0 or new_left > 0) or hunk_follows:
                path = _diff_path(lines[i + 1][4:])
                current = files.setdefault(path, set()) if path is not None else None
                new_no, old_left, new_left = None, 0, 0
                i += 2
                continue
        hunk = _HUNK.match(line)
        if hunk:
            new_no = int(hunk.group(2))
            old_left = int(hunk.group(1)) if hunk.group(1) is not None else 1
            new_left = int(hunk.group(3)) if hunk.group(3) is not None else 1
        elif new_no is not None:
            if line.startswith("+"):
                if current is not None:
                    current.add(new_no)
                new_no += 1
                new_left -= 1
            elif line.startswith("-"):
                old_left -= 1
            elif line.startswith(" ") or (line == "" and old_left > 0 and new_left > 0):
                if current is not None:
                    current.add(new_no)
                new_no += 1
                old_left -= 1
                new_left -= 1
            elif not line.startswith("\\"):
                new_no, old_left, new_left = None, 0, 0
        elif line.startswith("diff "):
            new_no, old_left, new_left = None, 0, 0
        i += 1
    return files


def _rule_diff_notes(node: _Node, report: Report, index: _Index) -> None:
    pre = index.first(node, "pre", skip=node.tag)
    if pre is None:
        return
    files = index.diff_files(pre)
    for note in index.within(node, "q-diff-note", skip=node.tag):
        file = note.attrs.get("file")
        if file is None:
            continue
        if file not in files:
            report(note.line, f'<q-diff-note> file="{file}" is not in its diff')
            continue
        raw = note.attrs.get("line")
        if raw is None or not _DIGITS.fullmatch(raw) or not raw.strip("0"):
            continue
        number = _positive_integer(raw)
        if number is None or number not in files[file]:
            report(note.line, f"<q-diff-note> line {raw.lstrip('0')} is not a new-side line of {file}")


def _rule_heading_sections(node: _Node, report: Report, index: _Index) -> None:
    sections = [c for c in node.children if c.tag == "section"]
    for index, section in enumerate(sections, 1):
        first = section.children[0] if section.children else None
        if first is None or first.tag not in _HEADINGS:
            report(section.line, f"<{node.tag}> section {index} does not start with a heading")


def _rule_timeline_items(node: _Node, report: Report, index: _Index) -> None:
    ol = index.first(node, "ol", skip=node.tag)
    if ol is None:
        return
    items = [c for c in ol.children if c.tag == "li"]
    for number, item in enumerate(items, 1):
        if index.first(item, _TIME_DATETIME) is None:
            report(item.line, f"<{node.tag}> item {number} has no <time datetime>")
        tone = item.attrs.get("data-tone")
        if tone is not None and tone not in TONES:
            report(item.line, f'<{node.tag}> item {number} data-tone="{tone}" is not one of {", ".join(TONES)}')


def _rule_compare_recommended(node: _Node, report: Report, index: _Index) -> None:
    table = next((c for c in node.children if c.tag == "table"), None)
    if table is None:
        if index.first(node, "table", skip=node.tag) is not None:
            report(node.line, f"<{node.tag}> needs its <table> as a direct child, not wrapped in another element")
        return
    raw = node.attrs.get("recommended")
    if raw is None or not _DIGITS.fullmatch(raw):
        return
    header = _header_row(table, index)
    if header is None:
        return
    options = len([c for c in header.children if c.tag in ("th", "td")]) - 1
    if options < 1:
        report(node.line, f"<{node.tag}> table has no option columns; the header row needs a cell for each option after the criteria column")
        return
    number = _positive_integer(raw)
    if number is None or number > options:
        report(node.line, f'<{node.tag}> recommended="{raw}" must be between 1 and {options} (the option columns)')


_FLOW_MAX_KINDS = 8
_FLOW_WARN_NODES = 60
_FLOW_MAX_NODES = 200
_FLOW_WARN_EDGE_LABEL = 30
_FLOW_WARN_DECISION_LABEL = 24
_FLOW_MIN_TRACE_STEPS = 2
_FLOW_WARN_TRACE_STEPS = 30
_FLOW_WARN_VALUE_LINES = 40
_FLOW_MAX_VALUE_LINES = 400
_FLOW_WARN_NOTE_CHARS = 120
_FLOW_SHAPES = ("box", "decision", "subprocess")
_FLOW_COORD_KEYS = frozenset({"x", "y", "position", "positions"})
_FLOW_DETAIL_TAGS = frozenset(
    "p ul ol li code pre a em strong b i br span kbd samp sub sup dl dt dd".split()
)
_FLOW_FORBIDDEN_RAW = re.compile(
    r"<\s*/?\s*(?:script|style|form|input|button|select|textarea|img|iframe|object|embed|svg|math|table|video|audio|link|meta|base)\b",
    re.IGNORECASE,
)


def _is_safe_flow_href(href: str) -> bool:
    cleaned = re.sub(r"[\s\x00-\x1f]+", "", html_lib.unescape(href)).lower()
    if not cleaned:
        return False
    if cleaned.startswith(("#", "/", "./", "../")):
        return not cleaned.startswith("//")
    if cleaned.startswith(("http:", "https:", "mailto:")):
        return True
    scheme_sep = cleaned.find(":")
    slash_sep = cleaned.find("/")
    return scheme_sep < 0 or (0 <= slash_sep < scheme_sep)


def _check_and_sanitize_flow_detail(detail: str) -> Optional[str]:
    """Return sanitized HTML when ``detail`` uses only allowed prose/list/code/link markup, else ``None``."""
    if _FLOW_FORBIDDEN_RAW.search(detail):
        return None
    builder = _TreeBuilder()
    try:
        builder.feed(detail)
        builder.close()
    except Exception:  # noqa: BLE001
        return None
    builder.finish()
    for n in builder.nodes:
        if n.tag not in _FLOW_DETAIL_TAGS:
            return None
        for attr_name, attr_val in n.attrs.items():
            name = attr_name.lower()
            if name.startswith("on") or name in ("src", "srcset", "action", "formaction", "data", "background", "poster", "style"):
                return None
            if name == "href":
                if n.tag != "a" or not _is_safe_flow_href(attr_val):
                    return None

    def render_clean(cur: _Node) -> str:
        parts: list[str] = []
        for item in cur.content:
            if isinstance(item, str):
                parts.append(html_lib.escape(item))
            elif isinstance(item, _Node) and item.tag in _FLOW_DETAIL_TAGS:
                if item.tag == "br":
                    parts.append("<br>")
                elif item.tag == "a" and "href" in item.attrs and _is_safe_flow_href(item.attrs["href"]):
                    href = html_lib.escape(item.attrs["href"], quote=True)
                    parts.append(f'<a href="{href}">{render_clean(item)}</a>')
                else:
                    parts.append(f"<{item.tag}>{render_clean(item)}</{item.tag}>")
        return "".join(parts)

    return render_clean(builder.root)


def _flow_forward_cycles(node_ids: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    """Strongly connected components of 2+ nodes over the forward edges.

    Nodes in each component follow ``node_ids`` order, and components are ordered by their first node.
    """
    successors: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        if not e["loop"]:
            successors[e["from"]].append(e["to"])
    position = {nid: i for i, nid in enumerate(node_ids)}
    number: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    for root in node_ids:
        if root in number:
            continue
        number[root] = lowlink[root] = len(number)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(successors[root]))]
        while work:
            current, targets = work[-1]
            advanced = False
            for target in targets:
                if target not in number:
                    number[target] = lowlink[target] = len(number)
                    stack.append(target)
                    on_stack.add(target)
                    work.append((target, iter(successors[target])))
                    advanced = True
                    break
                if target in on_stack:
                    lowlink[current] = min(lowlink[current], number[target])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[current])
            if lowlink[current] == number[current]:
                members: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    members.append(member)
                    if member == current:
                        break
                if len(members) > 1:
                    components.append(sorted(members, key=position.__getitem__))
    components.sort(key=lambda c: position[c[0]])
    return components


def _flow_value_lines(value: Any) -> Optional[int]:
    """Line count of ``value`` pretty-printed with 2-space indent, or ``None`` when it isn't strict JSON.

    A string or key holding an unpaired surrogate counts as not JSON: it can't be written as UTF-8.
    """
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
        text.encode("utf-8")
    except (ValueError, RecursionError):
        return None
    return text.count("\n") + 1


def _validate_flow_traces(
    data: dict[str, Any],
    line: int,
    node_map: dict[str, dict[str, Any]],
    clean_edges: list[dict[str, Any]],
    fail: Callable[[int, str], None],
    report_warn: Report,
) -> list[dict[str, Any]]:
    """Check ``data["traces"]`` and return the cleaned traces; every failure goes through ``fail``."""
    raw_traces = data.get("traces", [])
    if not isinstance(raw_traces, list):
        fail(line, "<q-flow> traces must be a list")
        return []

    clean_traces: list[dict[str, Any]] = []
    seen_trace_ids: set[str] = set()
    dup_trace_ids: set[str] = set()
    for trace in raw_traces:
        if not isinstance(trace, dict):
            fail(line, "<q-flow> each trace needs an id and a label")
            continue
        tid = trace.get("id")
        tlabel = trace.get("label")
        header_ok = _is_text(tid) and _is_text(tlabel)
        if not header_ok:
            fail(line, "<q-flow> each trace needs an id and a label")
            t = "?"
        else:
            t = tid
            if tid in seen_trace_ids:
                if tid not in dup_trace_ids:
                    fail(line, f'<q-flow> has duplicate trace id "{tid}"')
                    dup_trace_ids.add(tid)
            else:
                seen_trace_ids.add(tid)

        raw_steps = trace.get("steps")
        if not isinstance(raw_steps, list) or len(raw_steps) < _FLOW_MIN_TRACE_STEPS:
            fail(line, f'<q-flow> trace "{t}" needs at least 2 steps')
        if not isinstance(raw_steps, list):
            continue
        if len(raw_steps) > _FLOW_WARN_TRACE_STEPS:
            report_warn(
                line,
                f'<q-flow> trace "{t}" has {len(raw_steps)} steps: traces over 30 steps are hard to follow; split it',
            )

        clean_steps: list[dict[str, Any]] = []
        prev_node: Optional[str] = None
        for n, step in enumerate(raw_steps, start=1):
            where = f'<q-flow> trace "{t}" step {n}'
            if not isinstance(step, dict):
                fail(line, f"{where} needs a node and a value")
                prev_node = None
                continue
            snode = step.get("node")
            has_value = "value" in step
            if not isinstance(snode, str) or not has_value:
                fail(line, f"{where} needs a node and a value")
            known = isinstance(snode, str) and snode in node_map
            if isinstance(snode, str) and not known:
                fail(line, f'{where} points at unknown node "{snode}"')
            note = step.get("note")
            if "note" in step and not isinstance(note, str):
                fail(line, f"{where} note must be a string")

            via = step.get("via")
            has_via = "via" in step
            edge_index: Optional[int] = None
            if has_via and n == 1:
                fail(line, f"{where} has no incoming edge; remove via")
            elif n > 1 and known and prev_node is not None:
                candidates = [i for i, e in enumerate(clean_edges) if e["from"] == prev_node and e["to"] == snode]
                if has_via:
                    named = next(
                        (i for i, e in enumerate(clean_edges) if isinstance(via, str) and e["ref"] == via), None
                    )
                    if named is None:
                        fail(line, f'{where} names unknown edge "{via}"')
                    elif named not in candidates:
                        fail(line, f'{where}: edge "{via}" doesn\'t run from "{prev_node}" to "{snode}"')
                    else:
                        edge_index = named
                elif not candidates:
                    fail(line, f'{where}: no edge from "{prev_node}" to "{snode}"')
                elif len(candidates) > 1:
                    fail(
                        line,
                        f'{where}: {len(candidates)} edges run from "{prev_node}" to "{snode}"; name one with via',
                    )
                else:
                    edge_index = candidates[0]

            if has_value:
                lines = _flow_value_lines(step["value"])
                if lines is None:
                    fail(line, f"{where} has a value that isn't JSON")
                elif lines > _FLOW_MAX_VALUE_LINES:
                    fail(line, f"{where} value is {lines} lines; at most 400")
                elif lines > _FLOW_WARN_VALUE_LINES:
                    report_warn(
                        line,
                        f"{where} value is {lines} lines: values over 40 lines are hard to scan; "
                        "keep the fields the reader needs",
                    )
            if isinstance(note, str) and len(note) > _FLOW_WARN_NOTE_CHARS:
                report_warn(
                    line,
                    f"{where} note is {len(note)} characters: notes over 120 characters crowd the panel",
                )

            clean_steps.append(
                {
                    "node": snode,
                    "value": step.get("value"),
                    "note": note if isinstance(note, str) else None,
                    "via": via if isinstance(via, str) else None,
                    "edge": edge_index,
                }
            )
            prev_node = snode if known else None

        if header_ok:
            clean_traces.append({"id": t, "label": tlabel, "steps": clean_steps})
    return clean_traces


_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _flow_has_unwritable_text(data: dict[str, Any]) -> bool:
    """True when a string or object key in the graph data holds an unpaired surrogate.

    Trace step values are skipped: they have their own "isn't JSON" rule. The walk is iterative so
    deeply nested data can't raise RecursionError.
    """
    stack: list[tuple[Any, str]] = [(data, "root")]
    while stack:
        obj, where = stack.pop()
        if isinstance(obj, str):
            if _LONE_SURROGATE.search(obj):
                return True
        elif isinstance(obj, dict):
            for key, val in obj.items():
                if _LONE_SURROGATE.search(key):
                    return True
                if where == "step" and key == "value":
                    continue
                child = "other"
                if where == "root" and key == "traces":
                    child = "traces"
                elif where == "trace" and key == "steps":
                    child = "steps"
                stack.append((val, child))
        elif isinstance(obj, list):
            child = {"traces": "trace", "steps": "step"}.get(where, "other")
            stack.extend((item, child) for item in obj)
    return False


def _validate_flow_node(
    node: _Node,
    report_fail: Report,
    report_warn: Report,
    *,
    page_flow_ids: Optional[frozenset[str]] = None,
) -> Optional[dict[str, Any]]:
    scripts = [c for c in node.children if c.tag == "script"]
    if not scripts:
        return None
    json_script = next(
        (s for s in scripts if s.attrs.get("type", "").strip().lower() == "application/json"),
        None,
    )
    if json_script is None:
        report_fail(node.line, '<q-flow> needs a <script type="application/json"> child holding a JSON object')
        return None
    raw_json = _text(json_script)
    try:
        data = json.loads(raw_json)
    except (ValueError, RecursionError):
        if _FLOW_FORBIDDEN_RAW.search(raw_json):
            report_fail(node.line, "<q-flow> detail may hold only paragraphs, lists, code and links")
        else:
            report_fail(node.line, '<q-flow> needs a <script type="application/json"> child holding a JSON object')
        return None
    if not isinstance(data, dict):
        report_fail(node.line, '<q-flow> needs a <script type="application/json"> child holding a JSON object')
        return None

    before_fails: list[int] = []

    def fail(line: int, msg: str) -> None:
        before_fails.append(1)
        report_fail(line, msg)

    if _flow_has_unwritable_text(data):
        fail(node.line, "<q-flow> graph data holds text that can't be written as UTF-8")

    if _FLOW_COORD_KEYS & set(data):
        fail(node.line, "<q-flow> positions are laid out automatically; remove coordinates")

    kinds = data.get("kinds", {})
    if not isinstance(kinds, dict):
        fail(node.line, "<q-flow> kinds must be a JSON object")
        kinds = {}
    else:
        if len(kinds) > _FLOW_MAX_KINDS:
            fail(node.line, f"<q-flow> declares {len(kinds)} kinds; at most eight kinds, one per chart color")
        for k, v in kinds.items():
            if not _is_text(k) or isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= _FLOW_MAX_KINDS):
                fail(node.line, f'<q-flow> kind "{k}" color must be an integer from 1 to 8')

    raw_groups = data.get("groups", [])
    if not isinstance(raw_groups, list):
        fail(node.line, "<q-flow> groups must be a list")
        raw_groups = []

    seen_ids: set[str] = set()
    dup_reported: set[str] = set()
    group_map: dict[str, dict[str, Any]] = {}
    clean_groups: list[dict[str, Any]] = []
    for g in raw_groups:
        if not isinstance(g, dict):
            fail(node.line, "<q-flow> each group must be an object")
            continue
        if _FLOW_COORD_KEYS & set(g):
            fail(node.line, "<q-flow> positions are laid out automatically; remove coordinates")
        gid = g.get("id")
        glabel = g.get("label")
        if not _is_text(gid) or not _is_text(glabel):
            fail(node.line, "<q-flow> each group needs an id and a label")
            continue
        if gid in seen_ids:
            if gid not in dup_reported:
                fail(node.line, f'<q-flow> has duplicate id "{gid}"')
                dup_reported.add(gid)
            continue
        seen_ids.add(gid)
        parent = g.get("parent")
        entry = {"id": gid, "label": glabel, "parent": parent if isinstance(parent, str) and parent else None}
        group_map[gid] = entry
        clean_groups.append(entry)

    cycle_reported = False
    for gid, g in group_map.items():
        parent = g["parent"]
        if parent is not None:
            if parent not in group_map:
                fail(node.line, f'<q-flow> group "{gid}" points at unknown group "{parent}"')
            elif not cycle_reported:
                visited = {gid}
                cur: Optional[str] = parent
                while cur is not None and cur in group_map:
                    if cur in visited:
                        fail(node.line, f'<q-flow> group nesting loops at "{gid}"')
                        cycle_reported = True
                        break
                    visited.add(cur)
                    cur = group_map[cur]["parent"]

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        fail(node.line, "<q-flow> needs a non-empty nodes list")
        raw_nodes = []
    else:
        if len(raw_nodes) > _FLOW_MAX_NODES:
            fail(
                node.line,
                f"<q-flow> has {len(raw_nodes)} nodes (more than 200 nodes); split into groups or several graphs",
            )
        elif len(raw_nodes) > _FLOW_WARN_NODES:
            report_warn(
                node.line,
                f"<q-flow> has {len(raw_nodes)} nodes: large graphs read poorly, split into groups or several graphs",
            )

    is_lanes = node.attrs.get("groups", "panels").strip().lower() == "lanes"
    top_groups = [g for g in clean_groups if g["parent"] is None]
    lane_reported = False
    if is_lanes and not top_groups and raw_nodes:
        fail(node.line, "<q-flow> in lane mode every node belongs to a lane")
        lane_reported = True

    node_map: dict[str, dict[str, Any]] = {}
    clean_nodes: list[dict[str, Any]] = []
    for n in raw_nodes:
        if not isinstance(n, dict):
            fail(node.line, "<q-flow> each node must be an object")
            continue
        if _FLOW_COORD_KEYS & set(n):
            fail(node.line, "<q-flow> positions are laid out automatically; remove coordinates")
        nid = n.get("id")
        nlabel = n.get("label")
        if not _is_text(nid) or not _is_text(nlabel):
            fail(node.line, "<q-flow> each node needs an id and a label")
            continue
        if nid in seen_ids:
            if nid not in dup_reported:
                fail(node.line, f'<q-flow> has duplicate id "{nid}"')
                dup_reported.add(nid)
        else:
            seen_ids.add(nid)
        nkind = n.get("kind")
        if nkind is not None and (not isinstance(nkind, str) or nkind not in kinds):
            fail(node.line, f'<q-flow> node "{nid}" has undeclared kind "{nkind}"')
        ngroup = n.get("group")
        if ngroup is not None and (not isinstance(ngroup, str) or ngroup not in group_map):
            fail(node.line, f'<q-flow> node "{nid}" points at unknown group "{ngroup}"')
        if is_lanes and not lane_reported and (not isinstance(ngroup, str) or ngroup not in group_map):
            fail(node.line, f'<q-flow> node "{nid}" is outside every lane: in lane mode every node belongs to a lane')
            lane_reported = True
        ndetail = n.get("detail")
        clean_detail: Optional[str] = None
        if ndetail is not None:
            if not isinstance(ndetail, str):
                fail(node.line, f'<q-flow> node "{nid}" detail may hold only paragraphs, lists, code and links')
            else:
                clean_detail = _check_and_sanitize_flow_detail(ndetail)
                if clean_detail is None:
                    fail(node.line, f'<q-flow> node "{nid}" detail may hold only paragraphs, lists, code and links')
        nshape = n.get("shape")
        if nshape is not None and nshape not in _FLOW_SHAPES:
            fail(node.line, f'<q-flow> node "{nid}" has unknown shape "{nshape}"; use box, decision or subprocess')
        nflow = n.get("flow")
        if nflow is not None:
            if nshape != "subprocess":
                fail(node.line, f'<q-flow> node "{nid}" names a flow, but only a subprocess can name a flow')
            elif not _is_text(nflow):
                fail(node.line, f'<q-flow> node "{nid}" flow must be the id of another q-flow')
            elif page_flow_ids is not None and nflow not in page_flow_ids:
                fail(node.line, f'<q-flow> flow "{nflow}" names no q-flow on this page')
        entry = {
            "id": nid,
            "label": nlabel,
            "kind": nkind if isinstance(nkind, str) else None,
            "group": ngroup if isinstance(ngroup, str) else None,
            "detail_html": clean_detail,
            "shape": nshape if nshape in _FLOW_SHAPES else "box",
            "flow": nflow if nshape == "subprocess" and _is_text(nflow) else None,
        }
        node_map[nid] = entry
        clean_nodes.append(entry)

    raw_edges = data.get("edges", [])
    if not isinstance(raw_edges, list):
        fail(node.line, "<q-flow> edges must be a list")
        raw_edges = []

    clean_edges: list[dict[str, Any]] = []
    seen_edge_ids: set[str] = set()
    dup_edge_ids: set[str] = set()
    for e in raw_edges:
        if not isinstance(e, dict):
            fail(node.line, "<q-flow> each edge must be an object")
            continue
        if _FLOW_COORD_KEYS & set(e):
            fail(node.line, "<q-flow> positions are laid out automatically; remove coordinates")
        efrom = e.get("from")
        eto = e.get("to")
        if not isinstance(efrom, str) or efrom not in node_map:
            fail(node.line, f'<q-flow> edge points at unknown node "{efrom}"')
        if not isinstance(eto, str) or eto not in node_map:
            fail(node.line, f'<q-flow> edge points at unknown node "{eto}"')
        elabel = e.get("label")
        if elabel is not None:
            if not isinstance(elabel, str):
                fail(node.line, "<q-flow> edge label must be a string")
            elif len(elabel) > _FLOW_WARN_EDGE_LABEL:
                report_warn(
                    node.line,
                    f'<q-flow> edge label "{elabel}" is {len(elabel)} characters: edge labels over 30 characters crowd the layout',
                )
        easync = e.get("async")
        if easync is not None and not isinstance(easync, bool):
            fail(node.line, "<q-flow> edge async must be true or false")
        eloop = e.get("loop")
        if eloop is not None and not isinstance(eloop, bool):
            fail(node.line, "<q-flow> edge loop must be true or false")
        eref: Optional[str] = None
        if "id" in e:
            eid = e["id"]
            if not _is_text(eid):
                fail(node.line, "<q-flow> edge id must be a non-empty string")
            else:
                eref = eid
                if eid in seen_edge_ids:
                    if eid not in dup_edge_ids:
                        fail(node.line, f'<q-flow> has duplicate edge id "{eid}"')
                        dup_edge_ids.add(eid)
                else:
                    seen_edge_ids.add(eid)
        if isinstance(efrom, str) and isinstance(eto, str) and efrom in node_map and eto in node_map:
            clean_edges.append(
                {
                    "from": efrom,
                    "to": eto,
                    "label": elabel.strip() if isinstance(elabel, str) and elabel.strip() else None,
                    "async": easync is True,
                    "loop": eloop is True or efrom == eto,
                    "ref": eref,
                }
            )

    for decision in (n for n in clean_nodes if n["shape"] == "decision"):
        did = decision["id"]
        exits = [e for e in clean_edges if e["from"] == did]
        if len(exits) < 2:
            fail(node.line, f'<q-flow> decision "{did}" needs at least 2 exits')
        if any(e["label"] is None for e in exits):
            fail(node.line, f'<q-flow> every exit of decision "{did}" needs a label')
        if len(decision["label"]) > _FLOW_WARN_DECISION_LABEL:
            report_warn(
                node.line,
                f'<q-flow> decision "{did}" label is {len(decision["label"])} characters: '
                "decision labels over 24 characters overflow the diamond",
            )
        labels = [e["label"] for e in exits if e["label"] is not None]
        for label in dict.fromkeys(labels):
            if labels.count(label) > 1:
                report_warn(node.line, f'<q-flow> decision "{did}" has two exits labelled "{label}"')

    for cycle in _flow_forward_cycles(list(node_map), clean_edges):
        through = ", ".join(f'"{nid}"' for nid in cycle)
        report_warn(node.line, f"<q-flow> has a cycle with no loop edge through {through}: mark the return edge with loop: true")

    clean_traces = _validate_flow_traces(data, node.line, node_map, clean_edges, fail, report_warn)

    if before_fails:
        return None
    return {
        "groups": clean_groups,
        "group_map": group_map,
        "nodes": clean_nodes,
        "node_map": node_map,
        "edges": clean_edges,
        "traces": clean_traces,
    }


def _rule_flow_data(node: _Node, report: Report, index: _Index) -> None:
    own_id = node.attrs.get("id")
    page_flow_ids = frozenset(
        flow_id for other in index.nodes_of("q-flow") if (flow_id := other.attrs.get("id")) and flow_id != own_id
    )
    _validate_flow_node(node, report, lambda _line, _msg: None, page_flow_ids=page_flow_ids)


_SCHEMA_MAX_ENTITIES = 80
_SCHEMA_WARN_ENTITIES = 30
_SCHEMA_WARN_ROWS = 40
_SCHEMA_NOTATIONS = ("er", "class")
_SCHEMA_KEYS = ("PK", "FK", "UK")
_SCHEMA_CARDS = ("zero-or-one", "one", "zero-or-many", "one-or-many")
_SCHEMA_VISIBILITIES = ("public", "private", "protected", "package")
_SCHEMA_STEREOTYPES = ("interface", "abstract", "enum")
_SCHEMA_REL_TYPES = ("inherits", "implements", "composition", "aggregation", "association", "dependency")
_SCHEMA_MULTIPLICITY = re.compile(r"(\*|[0-9]+|[0-9]+\.\.([0-9]+|\*))")


def _schema_shown(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _schema_multiplicity_ok(value: Any) -> bool:
    """True for UML's short multiplicity form: ``*``, ``n`` or ``n..m`` / ``n..*`` with n <= m."""
    if not isinstance(value, str) or not _SCHEMA_MULTIPLICITY.fullmatch(value):
        return False
    if ".." not in value:
        return True
    low, high = value.split("..")
    if high == "*":
        return True
    low, high = low.lstrip("0") or "0", high.lstrip("0") or "0"
    return (len(low), low) <= (len(high), high)


def _validate_schema_node(node: _Node, report_fail: Report, report_warn: Report) -> Optional[dict[str, Any]]:
    """Validate one ``<q-schema>`` and return its cleaned data, or ``None`` when it cannot be used.

    Failures and warnings go to the two callbacks as they are found. An unknown ``notation`` is left
    to the catalog's enum check, so nothing further is validated or reported here.
    """
    notation = node.attrs.get("notation", "er")
    if notation not in _SCHEMA_NOTATIONS:
        return None
    scripts = [c for c in node.children if c.tag == "script"]
    if not scripts:
        return None
    json_script = next(
        (s for s in scripts if s.attrs.get("type", "").strip().lower() == "application/json"),
        None,
    )
    if json_script is None:
        report_fail(node.line, '<q-schema> needs a <script type="application/json"> child holding a JSON object')
        return None
    raw_json = _text(json_script)
    try:
        data = json.loads(raw_json)
    except (ValueError, RecursionError):
        if _FLOW_FORBIDDEN_RAW.search(raw_json):
            report_fail(node.line, "<q-schema> detail may hold only paragraphs, lists, code and links")
        else:
            report_fail(node.line, '<q-schema> needs a <script type="application/json"> child holding a JSON object')
        return None
    if not isinstance(data, dict):
        report_fail(node.line, '<q-schema> needs a <script type="application/json"> child holding a JSON object')
        return None

    is_class = notation == "class"
    noun = "class" if is_class else "entity"
    failed: list[int] = []
    once: set[str] = set()

    def fail(msg: str) -> None:
        failed.append(1)
        report_fail(node.line, f"<q-schema> {msg}")

    def fail_once(msg: str) -> None:
        if msg not in once:
            once.add(msg)
            fail(msg)

    def warn(msg: str) -> None:
        report_warn(node.line, f"<q-schema> {msg}")

    def no_coords(obj: dict[str, Any]) -> None:
        if _FLOW_COORD_KEYS & set(obj):
            fail_once("positions are not allowed; the element lays the model out")

    no_coords(data)

    kinds = data.get("kinds", {})
    if not isinstance(kinds, dict):
        fail("kinds must be a JSON object")
        kinds = {}
    else:
        if len(kinds) > _FLOW_MAX_KINDS:
            fail("at most eight kinds, one per chart color")
        for k, v in kinds.items():
            if not _is_text(k) or isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= _FLOW_MAX_KINDS):
                fail(f'kind "{k}" color must be an integer from 1 to 8')

    raw_groups = data.get("groups", [])
    if not isinstance(raw_groups, list):
        fail("groups must be a list")
        raw_groups = []

    seen_ids: set[str] = set()
    group_map: dict[str, dict[str, Any]] = {}
    clean_groups: list[dict[str, Any]] = []
    for g in raw_groups:
        if not isinstance(g, dict):
            fail("each group must be an object")
            continue
        no_coords(g)
        gid = g.get("id")
        glabel = g.get("label")
        if not _is_text(gid) or not _is_text(glabel):
            fail("each group needs an id and a label")
            continue
        if gid in seen_ids:
            fail_once(f'has duplicate id "{gid}"')
            continue
        seen_ids.add(gid)
        parent = g.get("parent")
        entry = {"id": gid, "label": glabel, "parent": parent if isinstance(parent, str) and parent else None}
        group_map[gid] = entry
        clean_groups.append(entry)

    cycle_reported = False
    for gid, g in group_map.items():
        parent = g["parent"]
        if parent is None:
            continue
        if parent not in group_map:
            fail(f'group "{gid}" points at unknown group "{parent}"')
        elif not cycle_reported:
            visited = {gid}
            cur: Optional[str] = parent
            while cur is not None and cur in group_map:
                if cur in visited:
                    fail("group nesting loops")
                    cycle_reported = True
                    break
                visited.add(cur)
                cur = group_map[cur]["parent"]

    raw_entities = data.get("entities")
    plural = "classes" if is_class else "entities"
    if not isinstance(raw_entities, list) or not raw_entities:
        fail("needs a non-empty entities list")
        raw_entities = []
    elif len(raw_entities) > _SCHEMA_MAX_ENTITIES:
        fail(f"more than {_SCHEMA_MAX_ENTITIES} {plural}")
    elif len(raw_entities) > _SCHEMA_WARN_ENTITIES:
        if is_class:
            warn("large diagrams read poorly, split them into groups or several diagrams")
        else:
            warn("large models read poorly, split them into groups or several models")

    def clean_flag(obj: dict[str, Any], key: str, owner: str) -> bool:
        value = obj.get(key)
        if value is not None and not isinstance(value, bool):
            fail(f'{key} of "{owner}" must be true or false')
        return value is True

    def clean_note(obj: dict[str, Any], owner: str) -> Optional[str]:
        note = obj.get("note")
        if note is None:
            return None
        if not _is_text(note):
            fail(f'note of "{owner}" must be non-blank text')
            return None
        return note

    def clean_visibility(obj: dict[str, Any]) -> Optional[str]:
        value = obj.get("visibility")
        if value is None:
            return None
        if not isinstance(value, str) or value not in _SCHEMA_VISIBILITIES:
            fail(f'unknown visibility "{_schema_shown(value)}"; use public, private, protected or package')
            return None
        return value

    def clean_er_field(eid: str, f: Any) -> Optional[dict[str, Any]]:
        if not isinstance(f, dict):
            fail(f'each field of "{eid}" must be an object')
            return None
        no_coords(f)
        name, ftype = f.get("name"), f.get("type")
        if not _is_text(name) or not _is_text(ftype):
            fail(f'each field of "{eid}" needs a name and a type')
            return None
        raw_key = f.get("key")
        keys: list[str] = []
        if raw_key is not None:
            for k in raw_key if isinstance(raw_key, list) else [raw_key]:
                if not isinstance(k, str) or k not in _SCHEMA_KEYS:
                    fail(f'unknown key "{_schema_shown(k)}"; use PK, FK or UK')
                elif k not in keys:
                    keys.append(k)
        owner = f"{eid}.{name}"
        return {
            "name": name,
            "type": ftype,
            "keys": keys,
            "nullable": clean_flag(f, "nullable", owner),
            "note": clean_note(f, owner),
        }

    def clean_class_field(eid: str, f: Any) -> Optional[dict[str, Any]]:
        if not isinstance(f, dict):
            fail(f'each attribute of "{eid}" must be an object')
            return None
        no_coords(f)
        name, ftype = f.get("name"), f.get("type")
        if not _is_text(name) or (ftype is not None and not _is_text(ftype)):
            fail(f'each attribute of "{eid}" needs a name, and a type when it has one')
            return None
        if "key" in f:
            fail_once("keys and cardinality belong to data models; this is a class diagram")
        owner = f"{eid}.{name}"
        return {
            "name": name,
            "type": ftype,
            "visibility": clean_visibility(f),
            "static": clean_flag(f, "static", owner),
            "note": clean_note(f, owner),
        }

    def clean_method(eid: str, m: Any) -> Optional[dict[str, Any]]:
        if not isinstance(m, dict):
            fail(f'each method of "{eid}" must be an object')
            return None
        no_coords(m)
        signature = m.get("signature")
        if not _is_text(signature):
            fail(f'each method of "{eid}" needs a signature')
            return None
        owner = f"{eid}.{signature}"
        return {
            "signature": signature,
            "visibility": clean_visibility(m),
            "static": clean_flag(m, "static", owner),
            "abstract": clean_flag(m, "abstract", owner),
            "note": clean_note(m, owner),
        }

    entity_map: dict[str, dict[str, Any]] = {}
    clean_entities: list[dict[str, Any]] = []
    for e in raw_entities:
        if not isinstance(e, dict):
            fail(f"each {noun} must be an object")
            continue
        no_coords(e)
        eid = e.get("id")
        elabel = e.get("label")
        if not _is_text(eid) or not _is_text(elabel):
            fail(f"each {noun} needs an id and a label")
            continue
        if not is_class and "." in eid:
            fail_once(f"entity ids may not contain '.': \"{eid}\"")
        if eid in seen_ids:
            fail_once(f'duplicate {noun} id "{eid}"' if eid in entity_map else f'has duplicate id "{eid}"')
            continue
        seen_ids.add(eid)
        ekind = e.get("kind")
        if ekind is not None and (not isinstance(ekind, str) or ekind not in kinds):
            fail(f'undeclared kind "{_schema_shown(ekind)}"')
        egroup = e.get("group")
        if egroup is not None and (not isinstance(egroup, str) or egroup not in group_map):
            fail(f'unknown group "{_schema_shown(egroup)}"')
        edetail = e.get("detail")
        clean_detail: Optional[str] = None
        if edetail is not None:
            clean_detail = _check_and_sanitize_flow_detail(edetail) if isinstance(edetail, str) else None
            if clean_detail is None:
                fail("detail may hold only paragraphs, lists, code and links")
        stereotype = e.get("stereotype")
        if is_class:
            if stereotype is not None and (not isinstance(stereotype, str) or stereotype not in _SCHEMA_STEREOTYPES):
                fail(f'unknown stereotype "{_schema_shown(stereotype)}"; use interface, abstract or enum')
                stereotype = None
        else:
            if "stereotype" in e or "methods" in e:
                fail_once('methods, stereotypes and relationship types belong to class diagrams; add notation="class"')
            stereotype = None

        raw_fields = e.get("fields")
        fields: list[dict[str, Any]] = []
        methods: list[dict[str, Any]] = []
        member_count = 0
        duplicate_member = False
        if "fields" not in e and is_class:
            raw_fields = []
        if not isinstance(raw_fields, list) or (not is_class and not raw_fields):
            fail(f'{noun} "{eid}" needs a non-empty fields list' if not is_class else f'"{eid}" fields must be a list')
        else:
            member_count += len(raw_fields)
            seen_names: set[str] = set()
            for f in raw_fields:
                cleaned = clean_class_field(eid, f) if is_class else clean_er_field(eid, f)
                if cleaned is None:
                    continue
                if cleaned["name"] in seen_names:
                    if is_class:
                        duplicate_member = True
                    else:
                        fail_once(f'duplicate field "{cleaned["name"]}" in "{eid}"')
                    continue
                seen_names.add(cleaned["name"])
                fields.append(cleaned)
        if is_class:
            raw_methods = e.get("methods", [])
            if not isinstance(raw_methods, list):
                fail(f'"{eid}" methods must be a list')
            else:
                member_count += len(raw_methods)
                seen_signatures: set[str] = set()
                for m in raw_methods:
                    cleaned = clean_method(eid, m)
                    if cleaned is None:
                        continue
                    if cleaned["signature"] in seen_signatures:
                        duplicate_member = True
                        continue
                    seen_signatures.add(cleaned["signature"])
                    methods.append(cleaned)
            if duplicate_member:
                fail_once(f'duplicate member in "{eid}"')
        if member_count > _SCHEMA_WARN_ROWS:
            warn(f'"{eid}" has more than {_SCHEMA_WARN_ROWS} {"members" if is_class else "fields"}')

        entry = {
            "id": eid,
            "label": elabel,
            "kind": ekind if isinstance(ekind, str) else None,
            "group": egroup if isinstance(egroup, str) else None,
            "stereotype": stereotype if isinstance(stereotype, str) else None,
            "detail_html": clean_detail,
            "fields": fields,
            "methods": methods,
        }
        entity_map[eid] = entry
        clean_entities.append(entry)

    raw_rels = data.get("relationships", [])
    if not isinstance(raw_rels, list):
        fail("relationships must be a list")
        raw_rels = []

    def clean_label(r: dict[str, Any]) -> Optional[str]:
        label = r.get("label")
        if label is None:
            return None
        if not isinstance(label, str):
            fail("relationship label must be a string")
            return None
        if not label.strip():
            fail("relationship label must not be blank")
            return None
        return label.strip()

    def er_end(r: dict[str, Any], side: str) -> Optional[tuple[str, str]]:
        raw = r.get(side)
        entity_id, _, field_name = raw.partition(".") if isinstance(raw, str) else ("", "", "")
        if not entity_id or not field_name:
            fail("relationship ends are written entity.field")
            return None
        if entity_id not in entity_map:
            fail(f'relationship names unknown entity "{entity_id}"')
            return None
        if not any(f["name"] == field_name for f in entity_map[entity_id]["fields"]):
            fail(f'relationship names unknown field "{raw}"')
            return None
        return entity_id, field_name

    def class_end(r: dict[str, Any], side: str) -> Optional[str]:
        raw = r.get(side)
        if isinstance(raw, str) and raw in entity_map:
            return raw
        if isinstance(raw, str) and "." in raw:
            fail("class relationships join classes, not members")
        else:
            fail(f'relationship names unknown class "{_schema_shown(raw)}"')
        return None

    clean_rels: list[dict[str, Any]] = []
    for r in raw_rels:
        if not isinstance(r, dict):
            fail("each relationship must be an object")
            continue
        no_coords(r)
        label = clean_label(r)
        if is_class:
            src, dst = class_end(r, "from"), class_end(r, "to")
            rtype = r.get("type")
            if rtype is None:
                fail("relationship needs a type; use inherits, implements, composition, aggregation, association or dependency")
            elif not isinstance(rtype, str) or rtype not in _SCHEMA_REL_TYPES:
                fail(
                    f'unknown relationship type "{_schema_shown(rtype)}"; '
                    "use inherits, implements, composition, aggregation, association or dependency"
                )
                rtype = None
            if "from_card" in r or "to_card" in r:
                fail_once("keys and cardinality belong to data models; this is a class diagram")
            mults: dict[str, Optional[str]] = {}
            for side in ("from_mult", "to_mult"):
                value = r.get(side)
                mults[side] = None
                if value is None:
                    continue
                if _schema_multiplicity_ok(value):
                    mults[side] = value
                else:
                    fail(f'unknown multiplicity "{_schema_shown(value)}"; use 1, 0..1, *, 0..*, 1..* or n..m')
            directed = r.get("directed")
            if directed is not None:
                if not isinstance(directed, bool):
                    fail("directed must be true or false")
                elif rtype is not None and rtype != "association":
                    fail("directed is only valid on an association")
            if src is not None and dst is not None and isinstance(rtype, str):
                clean_rels.append(
                    {
                        "from_entity": src,
                        "to_entity": dst,
                        "type": rtype,
                        "from_mult": mults["from_mult"],
                        "to_mult": mults["to_mult"],
                        "label": label,
                        "directed": directed is True,
                    }
                )
        else:
            if "type" in r:
                fail_once('methods, stereotypes and relationship types belong to class diagrams; add notation="class"')
            src_end, dst_end = er_end(r, "from"), er_end(r, "to")
            cards: dict[str, Optional[str]] = {}
            for side in ("from_card", "to_card"):
                value = r.get(side)
                cards[side] = None
                if value is None:
                    fail(f"relationship needs {side}")
                elif not isinstance(value, str) or value not in _SCHEMA_CARDS:
                    fail(
                        f'unknown cardinality "{_schema_shown(value)}"; '
                        "use zero-or-one, one, zero-or-many or one-or-many"
                    )
                else:
                    cards[side] = value
            if src_end is not None and dst_end is not None and cards["from_card"] and cards["to_card"]:
                clean_rels.append(
                    {
                        "from_entity": src_end[0],
                        "from_field": src_end[1],
                        "to_entity": dst_end[0],
                        "to_field": dst_end[1],
                        "from_card": cards["from_card"],
                        "to_card": cards["to_card"],
                        "label": label,
                    }
                )

    if is_class:
        edges = [(r["from_entity"], r["to_entity"]) for r in clean_rels if r["type"] in ("inherits", "implements")]
        incoming = {eid: 0 for eid in entity_map}
        onward: dict[str, list[str]] = {eid: [] for eid in entity_map}
        for src, dst in edges:
            incoming[dst] += 1
            onward[src].append(dst)
        ready = [eid for eid, n in incoming.items() if n == 0]
        settled = 0
        while ready:
            current = ready.pop()
            settled += 1
            for nxt in onward[current]:
                incoming[nxt] -= 1
                if incoming[nxt] == 0:
                    ready.append(nxt)
        if settled < len(entity_map):
            fail("inheritance loops")
        for r in clean_rels:
            target = entity_map[r["to_entity"]]
            if r["type"] == "implements" and target["stereotype"] != "interface":
                message = f'"{target["id"]}" is implemented but isn\'t an interface'
            elif r["type"] == "inherits" and target["stereotype"] == "interface":
                message = f'"{target["id"]}" is an interface; use implements'
            else:
                continue
            if message not in once:
                once.add(message)
                warn(message)
    else:
        used = {(r["from_entity"], r["from_field"]) for r in clean_rels} | {
            (r["to_entity"], r["to_field"]) for r in clean_rels
        }
        for entry in clean_entities:
            for f in entry["fields"]:
                if "FK" in f["keys"] and (entry["id"], f["name"]) not in used:
                    warn(f'FK field "{entry["id"]}.{f["name"]}" has no relationship')
        for r in clean_rels:
            source = next(f for f in entity_map[r["from_entity"]]["fields"] if f["name"] == r["from_field"])
            if "FK" not in source["keys"]:
                message = f'relationship starts at "{r["from_entity"]}.{r["from_field"]}", which isn\'t marked FK'
                if message not in once:
                    once.add(message)
                    warn(message)

    if failed:
        return None
    return {
        "notation": notation,
        "kinds": kinds,
        "groups": clean_groups,
        "group_map": group_map,
        "entities": clean_entities,
        "entity_map": entity_map,
        "relationships": clean_rels,
    }


def _rule_schema_data(node: _Node, report: Report, index: _Index) -> None:
    _validate_schema_node(node, report, lambda _line, _msg: None)


def check_html_warnings(text: str, catalog: Catalog, *, label: str) -> list[dict]:
    """Return non-fatal kit warnings for ``text`` (such as large ``q-flow`` graphs or long edge labels)."""
    if not (FLOW_TAG.search(text) or SCHEMA_TAG.search(text)):
        return []
    builder = _TreeBuilder()
    try:
        builder.feed(text)
        builder.close()
    except Exception:  # noqa: BLE001
        pass
    builder.finish()
    found: list[tuple[int, int, str]] = []

    def report_warn(line: int, message: str) -> None:
        found.append((line, len(found), message))

    for node in builder.nodes:
        if node.tag == "q-flow" and "q-flow" in catalog.elements:
            _validate_flow_node(node, lambda _line, _msg: None, report_warn)
        elif node.tag == "q-schema" and "q-schema" in catalog.elements:
            _validate_schema_node(node, lambda _line, _msg: None, report_warn)
    found.sort()
    return [{"check": "kit", "detail": f"{label} line {line}: {message}"} for line, _, message in found]


def _render_flow_fallback_html(parsed: dict[str, Any]) -> str:
    groups = parsed["groups"]
    nodes = parsed["nodes"]
    node_map = parsed["node_map"]
    edges = parsed["edges"]

    out_by_node: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        out_by_node.setdefault(e["from"], []).append(e)

    def render_node(n: dict[str, Any]) -> str:
        nid = html_lib.escape(n["id"], quote=True)
        label = html_lib.escape(n["label"])
        shape = n.get("shape", "box")
        title_meta = [html_lib.escape(m) for m in (shape if shape != "box" else None, n["kind"]) if m]
        kind_str = f" ({', '.join(title_meta)})" if title_meta else ""
        lead = ""
        if shape == "subprocess" and n.get("flow"):
            flow = n["flow"]
            lead = (
                f': <a href="#{html_lib.escape(flow, quote=True)}">'
                f"opens the &quot;{html_lib.escape(flow)}&quot; graph</a>"
            )
        detail_str = f'<div data-q-flow-list-detail>{n["detail_html"]}</div>' if n["detail_html"] else ""
        outs = out_by_node.get(n["id"], [])
        edge_str = ""
        if shape == "decision":
            exits = []
            for e in outs:
                tlabel = html_lib.escape(node_map[e["to"]]["label"])
                arrow = "\u21a9" if e.get("loop") else "\u2192"
                exits.append(f"{html_lib.escape(e['label'] or '')} {arrow} {tlabel}{' (async)' if e['async'] else ''}")
            lead = f": {', '.join(exits)}"
        elif outs:
            items = []
            for e in outs:
                if e.get("loop"):
                    target = "itself" if e["from"] == e["to"] else html_lib.escape(node_map[e["to"]]["label"])
                    text = f"\u21a9 returns to {target}"
                    if e["label"]:
                        text += f": {html_lib.escape(e['label'])}"
                    if e["async"]:
                        text += " (async)"
                    items.append(f"<li>{text}</li>")
                else:
                    tlabel = html_lib.escape(node_map[e["to"]]["label"])
                    meta = []
                    if e["label"]:
                        meta.append(html_lib.escape(e["label"]))
                    if e["async"]:
                        meta.append("async")
                    suffix = f" ({', '.join(meta)})" if meta else ""
                    items.append(f"<li>\u2192 {tlabel}{suffix}</li>")
            edge_str = f"<ul>{''.join(items)}</ul>"
        return f'<li data-q-flow-list-node="{nid}"><strong>{label}</strong>{kind_str}{lead}{detail_str}{edge_str}</li>'

    def render_trace(trace: dict[str, Any]) -> str:
        items = []
        for n, step in enumerate(trace["steps"], start=1):
            edge = edges[step["edge"]] if step["edge"] is not None else None
            via_part = ""
            if edge is not None and (step["via"] is not None or edge["loop"]):
                if edge["label"]:
                    via_part = f", via &quot;{html_lib.escape(edge['label'])}&quot;"
                elif step["via"] is not None:
                    via_part = f", via &quot;{html_lib.escape(step['via'])}&quot;"
                else:
                    via_part = ", around the loop"
            note_part = f": {html_lib.escape(step['note'])}" if step["note"] else ""
            pretty = json.dumps(step["value"], indent=2, ensure_ascii=False, allow_nan=False)
            items.append(
                f'<li data-q-flow-list-step="{n}">{html_lib.escape(node_map[step["node"]]["label"])}'
                f"{via_part}{note_part}<pre><code>{html_lib.escape(pretty)}</code></pre></li>"
            )
        return (
            f'<div data-q-flow-list-trace="{html_lib.escape(trace["id"], quote=True)}">'
            f"<p><strong>Trace: {html_lib.escape(trace['label'])}</strong></p><ol>{''.join(items)}</ol></div>"
        )

    def render_group(g: dict[str, Any]) -> str:
        gid = html_lib.escape(g["id"], quote=True)
        glabel = html_lib.escape(g["label"])
        children_items = [render_group(cg) for cg in groups if cg["parent"] == g["id"]]
        children_items.extend(render_node(n) for n in nodes if n["group"] == g["id"])
        sub = f"<ul>{''.join(children_items)}</ul>" if children_items else ""
        return f'<li data-q-flow-list-group="{gid}"><strong>{glabel}</strong>{sub}</li>'

    top_items = [render_group(g) for g in groups if g["parent"] is None]
    top_items.extend(render_node(n) for n in nodes if n["group"] is None)
    list_html = f"<ul>{''.join(top_items)}</ul>"
    list_html += "".join(render_trace(t) for t in parsed.get("traces", []))
    return (
        '<div class="q-flow-stage" data-q-kit data-q-flow-stage>'
        '<p class="q-flow-notice" data-q-flow-notice>JavaScript is off, so this graph is shown as a list below.</p>'
        "</div>"
        '<details class="q-flow-list" data-q-kit data-q-flow-list open>'
        "<summary>Graph as a list</summary>"
        f"<div data-q-flow-list-body>{list_html}</div>"
        "</details>"
    )


_FLOW_BLOCK = re.compile(r"(<q-flow\b[^>]*>.*?</q-flow\s*>)", re.IGNORECASE | re.DOTALL)
_FLOW_CLOSER = re.compile(r"</q-flow\s*>\Z", re.IGNORECASE)


def inject_flow_fallbacks(html: str) -> str:
    """Insert the static notice and ``<details open>`` text list into valid ``<q-flow>`` elements in ``html``."""
    if not FLOW_TAG.search(html):
        return html

    def replace_block(match: "re.Match[str]") -> str:
        block = match.group(1)
        if "data-q-flow-list" in block:
            return block
        builder = _TreeBuilder()
        try:
            builder.feed(block)
            builder.close()
        except Exception:  # noqa: BLE001
            return block
        builder.finish()
        qflow = next((n for n in builder.nodes if n.tag == "q-flow"), None)
        if qflow is None or qflow.self_closed or "summary" not in qflow.attrs:
            return block
        parsed = _validate_flow_node(qflow, lambda _l, _m: None, lambda _l, _m: None)
        if parsed is None:
            return block
        fallback = _render_flow_fallback_html(parsed)
        return _FLOW_CLOSER.sub(lambda m: fallback + m.group(0), block, count=1)

    return _FLOW_BLOCK.sub(replace_block, html)


_SCHEMA_CARD_WORDS = {
    "zero-or-one": "zero or one",
    "one": "one",
    "zero-or-many": "zero or many",
    "one-or-many": "one or many",
}
_SCHEMA_VERBS = {
    "inherits": "inherits from",
    "implements": "implements",
    "composition": "is composed of",
    "aggregation": "aggregates",
    "association": "is associated with",
    "dependency": "depends on",
}


def _schema_plural(label: str) -> str:
    """The English plural of ``label`` as written: consonant+y to ies, s/x/z/ch/sh add es, else add s."""
    lowered = label.lower()
    if len(label) >= 2 and lowered.endswith("y") and label[-2].isalpha() and lowered[-2] not in "aeiou":
        return label[:-1] + "ies"
    if lowered.endswith(("s", "x", "z", "ch", "sh")):
        return label + "es"
    return label + "s"


def _schema_member_line(member: dict[str, Any], *, is_method: bool) -> str:
    """The text of one class attribute or method, with visibility, static and abstract in words."""
    if is_method:
        body = member["signature"]
    else:
        body = f'{member["name"]}: {member["type"]}' if member["type"] else member["name"]
    parts = [member["visibility"], "static" if member["static"] else None, "abstract" if member.get("abstract") else None, body]
    line = " ".join(p for p in parts if p)
    return f'{line} ({member["note"]})' if member["note"] else line


def _schema_field_line(field: dict[str, Any]) -> str:
    """The text of one data model field: name, type, keys, nullability and note."""
    line = f'{field["name"]}: {field["type"]}'
    for key in field["keys"]:
        line += f", {key}"
    if field["nullable"]:
        line += ", can be empty"
    return f'{line} ({field["note"]})' if field["note"] else line


def _schema_relationship_sentence(parsed: dict[str, Any], rel: dict[str, Any]) -> str:
    """One relationship as a sentence, from the entity labels as written."""
    entities = parsed["entity_map"]
    source = entities[rel["from_entity"]]["label"]
    target = entities[rel["to_entity"]]["label"]
    if parsed["notation"] == "class":
        sentence = f'{source} {_SCHEMA_VERBS[rel["type"]]}'
        if rel["type"] not in ("inherits", "implements") and rel["to_mult"]:
            sentence += f' {rel["to_mult"]}'
        sentence += f" {target}"
        extras = []
        if rel["from_mult"]:
            extras.append(f'{rel["from_mult"]} {source} per {target}')
        if rel["label"]:
            extras.append(rel["label"])
        return f'{sentence} ({"; ".join(extras)})' if extras else sentence

    def form(card: str, label: str) -> str:
        many = card.endswith("many")
        return f'{_SCHEMA_CARD_WORDS[card]} {_schema_plural(label) if many else label}'

    verb = rel["label"] or "has"
    return (
        f"Each {target} {verb} {form(rel['from_card'], source)}, and each {source} has {form(rel['to_card'], target)} "
        f"({rel['from_entity']}.{rel['from_field']} → {rel['to_entity']}.{rel['to_field']})"
    )


def _render_schema_fallback_html(parsed: dict[str, Any]) -> str:
    groups = parsed["groups"]
    entities = parsed["entities"]
    is_class = parsed["notation"] == "class"
    noun = "class diagram" if is_class else "data model"

    def render_entity(entity: dict[str, Any]) -> str:
        eid = html_lib.escape(entity["id"], quote=True)
        meta = [html_lib.escape(m) for m in (entity["kind"], entity["stereotype"]) if m]
        meta_str = f" ({', '.join(meta)})" if meta else ""
        detail_str = f'<div data-q-flow-list-detail>{entity["detail_html"]}</div>' if entity["detail_html"] else ""
        if is_class:
            lines = [_schema_member_line(f, is_method=False) for f in entity["fields"]]
            lines += [_schema_member_line(m, is_method=True) for m in entity["methods"]]
        else:
            lines = [_schema_field_line(f) for f in entity["fields"]]
        rows = f"<ul>{''.join(f'<li>{html_lib.escape(line)}</li>' for line in lines)}</ul>" if lines else ""
        label = html_lib.escape(entity["label"])
        return f'<li data-q-schema-list-entity="{eid}"><strong>{label}</strong>{meta_str}{detail_str}{rows}</li>'

    subgroups: dict[Optional[str], list[dict[str, Any]]] = {}
    for g in groups:
        subgroups.setdefault(g["parent"], []).append(g)
    members: dict[Optional[str], list[dict[str, Any]]] = {}
    for e in entities:
        members.setdefault(e["group"], []).append(e)

    def render_top_level_groups() -> list[str]:
        """The group ``<li>`` items, walked with an explicit stack so nesting depth is not bounded by recursion."""
        top: list[str] = []
        stack: list[tuple[Optional[dict[str, Any]], Any, list[str]]] = [(None, iter(subgroups.get(None, [])), top)]
        while True:
            group, pending, items = stack[-1]
            child = next(pending, None)
            if child is not None:
                stack.append((child, iter(subgroups.get(child["id"], [])), []))
                continue
            if group is None:
                return top
            stack.pop()
            items.extend(render_entity(e) for e in members.get(group["id"], []))
            gid = html_lib.escape(group["id"], quote=True)
            glabel = html_lib.escape(group["label"])
            sub = f"<ul>{''.join(items)}</ul>" if items else ""
            stack[-1][2].append(f'<li data-q-flow-list-group="{gid}"><strong>{glabel}</strong>{sub}</li>')

    top_items = render_top_level_groups()
    top_items.extend(render_entity(e) for e in members.get(None, []))
    body = f"<ul>{''.join(top_items)}</ul>"
    if parsed["relationships"]:
        sentences = "".join(
            f"<li>{html_lib.escape(_schema_relationship_sentence(parsed, r))}</li>" for r in parsed["relationships"]
        )
        body += f"<p>Relationships</p><ul data-q-schema-list-rels>{sentences}</ul>"
    title = "Class diagram as a list" if is_class else "Data model as a list"
    return (
        '<div class="q-flow-stage" data-q-kit data-q-flow-stage>'
        f'<p class="q-flow-notice" data-q-flow-notice>JavaScript is off, so this {noun} is shown as a list below.</p>'
        "</div>"
        '<details class="q-flow-list" data-q-kit data-q-flow-list open>'
        f"<summary>{title}</summary>"
        f"<div data-q-flow-list-body>{body}</div>"
        "</details>"
    )


_SCHEMA_OPENER = re.compile(r"<q-schema\b[^>]*>", re.IGNORECASE)
_SCHEMA_CLOSER = re.compile(r"</q-schema\s*>\Z", re.IGNORECASE)
_SCHEMA_SCAN = re.compile(r"<script\b[^>]*>|</q-schema\s*>", re.IGNORECASE)
_SCRIPT_END = re.compile(r"</script\b", re.IGNORECASE)


def _schema_blocks(html: str) -> list[tuple[int, int]]:
    """Spans of each ``<q-schema>`` element, ending at the first closing tag that is not inside a ``<script>``.

    A browser ends a script only at ``</script``, so the text ``</q-schema>`` inside the JSON is data.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        opener = _SCHEMA_OPENER.search(html, pos)
        if opener is None:
            return spans
        cursor = opener.end()
        end = None
        while True:
            hit = _SCHEMA_SCAN.search(html, cursor)
            if hit is None:
                break
            if hit.group(0)[1] == "/":
                end = hit.end()
                break
            script_end = _SCRIPT_END.search(html, hit.end())
            if script_end is None:
                break
            cursor = script_end.end()
        if end is None:
            pos = opener.end()
            continue
        spans.append((opener.start(), end))
        pos = end


def inject_schema_fallbacks(html: str) -> str:
    """Insert the static notice and ``<details open>`` text list into valid ``<q-schema>`` elements in ``html``."""
    if not SCHEMA_TAG.search(html):
        return html

    def fill_block(block: str) -> str:
        builder = _TreeBuilder()
        try:
            builder.feed(block)
            builder.close()
        except Exception:  # noqa: BLE001
            return block
        builder.finish()
        if any("data-q-flow-list" in n.attrs for n in builder.nodes):
            return block
        qschema = next((n for n in builder.nodes if n.tag == "q-schema"), None)
        if qschema is None or qschema.self_closed or "summary" not in qschema.attrs:
            return block
        parsed = _validate_schema_node(qschema, lambda _l, _m: None, lambda _l, _m: None)
        if parsed is None:
            return block
        fallback = _render_schema_fallback_html(parsed)
        return _SCHEMA_CLOSER.sub(lambda m: fallback + m.group(0), block, count=1)

    out: list[str] = []
    last = 0
    for start, end in _schema_blocks(html):
        out.append(html[last:start])
        out.append(fill_block(html[start:end]))
        last = end
    out.append(html[last:])
    return "".join(out)


_RULES: dict[str, Callable[[_Node, Report, _Index], None]] = {
    "max-series": _rule_max_series,
    "diff-notes": _rule_diff_notes,
    "heading-sections": _rule_heading_sections,
    "board-columns": _rule_heading_sections,
    "timeline-items": _rule_timeline_items,
    "compare-recommended": _rule_compare_recommended,
    "flow-data": _rule_flow_data,
    "schema-data": _rule_schema_data,
}
assert set(_RULES) == KNOWN_RULES


# -- JSX -------------------------------------------------------------------------------------------

_JSX_TAG = re.compile(r"<(q-[a-z]+(?:-[a-z]+)*)(?=[\s/>])")
_JSX_ATTR = re.compile(r"[A-Za-z_$][\w$:.-]*")
_JSX_LITERAL = re.compile(r"""^(?:"([^"\\\n]*)"|'([^'\\\n]*)')$""")
_COMMENT_OPEN = re.compile(r"^[ \t]*(?=//|/\*)|\{\s*(?=/\*)", re.MULTILINE)
_EXPRESSION_CLOSE = re.compile(r"\s*\}")


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    """``text`` with each span overwritten by spaces, newlines kept, so offsets and lines hold."""
    out: list[str] = []
    last = 0
    for start, end in spans:
        out.append(text[last:start])
        out.append(re.sub(r"[^\n]", " ", text[start:end]))
        last = end
    out.append(text[last:])
    return "".join(out)


def _html_comment_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        start = text.find("<!--", pos)
        if start < 0:
            return spans
        end = text.find("-->", start + 4)
        if end < 0:
            return spans
        spans.append((start, end + 3))
        pos = end + 3


def _js_comment_spans(text: str) -> list[tuple[int, int]]:
    """Spans of the comments that are unambiguously comments, each ending at its own terminator.

    A ``//`` or ``/*`` counts only as the first text on its line, and a ``/* */`` also as the whole
    content of a ``{ }`` container. Mid-line occurrences may be string or JSX text and are left
    for the tag scan, as is a ``/*`` that never closes.
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    pos = 0
    close = -1  # first "*/" at or after some earlier start; -2 once none is left
    while True:
        opened = _COMMENT_OPEN.search(text, pos)
        if opened is None:
            return spans
        start = opened.end()
        if text.startswith("//", start):
            end = text.find("\n", start)
            end = n if end < 0 else end
        else:
            if close == -2:
                pos = start + 2
                continue
            if close < start + 2:
                close = text.find("*/", start + 2)
                if close < 0:
                    close = -2
                    pos = start + 2
                    continue
            end = close + 2
            if text[opened.start()] == "{" and _EXPRESSION_CLOSE.match(text, end) is None:
                pos = start + 2
                continue
        spans.append((start, end))
        pos = end


def _blank_comments(text: str, html: bool = False) -> str:
    """``text`` with its unambiguous comments blanked; ``html`` also blanks ``<!-- -->`` comments."""
    if html:
        text = _blank(text, _html_comment_spans(text))
    return _blank(text, _js_comment_spans(text))


class _Braces:
    """Where each ``{`` of one source closes, found lazily and never scanned twice.

    A scan records every brace it opens in code mode with its end, so a later query for one of
    those, or for a brace nested in it, is a lookup. Unterminated braces are recorded too, so
    thousands of unclosed ``{`` cost one pass over the source instead of one each. Strings,
    template literals with ``${}`` nesting and comments are skipped, so a brace or ``>`` inside one
    does not end an expression.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self._ends: dict[int, int] = {}

    def end(self, start: int) -> Optional[int]:
        """Index just past the ``}`` that closes the ``{`` at ``start``, or ``None`` if unterminated."""
        known = self._ends.get(start)
        if known is None:
            self._scan(start)
            known = self._ends[start]
        return known if known >= 0 else None

    def _scan(self, start: int) -> None:
        text, ends = self._text, self._ends
        n = len(text)
        stack: list[tuple[str, int]] = [("{", start)]
        i = start + 1
        while i < n and stack:
            c = text[i]
            if stack[-1][0] == "`":
                if c == "\\":
                    i += 2
                    continue
                if c == "`":
                    stack.pop()
                elif c == "$" and text.startswith("${", i):
                    stack.append(("{", i + 1))
                    i += 1
                i += 1
                continue
            if c in "'\"":
                j = i + 1
                while j < n and text[j] != c and text[j] != "\n":
                    j += 2 if text[j] == "\\" else 1
                i = j + 1
            elif c == "`":
                stack.append(("`", i))
                i += 1
            elif c == "{":
                known = ends.get(i)
                if known is None:
                    stack.append(("{", i))
                    i += 1
                elif known < 0:
                    break
                else:
                    i = known
            elif c == "}":
                ends[stack.pop()[1]] = i + 1
                i += 1
            elif c == "/" and text.startswith("//", i):
                end = text.find("\n", i)
                i = n if end < 0 else end + 1
            elif c == "/" and text.startswith("/*", i):
                end = text.find("*/", i + 2)
                i = n if end < 0 else end + 2
            else:
                i += 1
        for kind, opened in stack:
            if kind == "{":
                ends[opened] = -1


def _jsx_attributes(
    text: str, pos: int, braces: _Braces, limit: int
) -> tuple[dict[str, Optional[str]], bool]:
    """Read the attributes of the JSX tag whose name ends at ``pos``.

    Returns the attribute names mapped to their literal string value, or ``None`` for an expression
    or a valueless attribute, and whether a ``{...spread}`` could be supplying more. An unterminated
    ``{`` ends at ``limit`` (the next q-* tag), so the scan never runs on to the end of the source.
    """
    attrs: dict[str, Optional[str]] = {}
    spread = False
    n = len(text)
    i = pos
    while i < n:
        c = text[i]
        if c == ">" or c == "<":
            break
        if c.isspace() or c == "/":
            i += 1
        elif c == "{":
            spread = True
            end = braces.end(i)
            i = max(limit, i + 1) if end is None else end
        else:
            m = _JSX_ATTR.match(text, i)
            if m is None:
                i += 1
                continue
            name = m.group(0)
            i = m.end()
            j = i
            while j < n and text[j].isspace():
                j += 1
            value: Optional[str] = None
            if j < n and text[j] == "=":
                j += 1
                while j < n and text[j].isspace():
                    j += 1
                if j < n and text[j] in "'\"":
                    end = text.find(text[j], j + 1)
                    if end < 0:
                        attrs.setdefault(name, None)
                        break
                    value = text[j + 1 : end]
                    i = end + 1
                elif j < n and text[j] == "{":
                    end = braces.end(j)
                    if end is None:
                        i = max(limit, j + 1)
                    else:
                        literal = _JSX_LITERAL.match(text[j + 1 : end - 1].strip())
                        value = (
                            (literal.group(1) if literal.group(1) is not None else literal.group(2)) if literal else None
                        )
                        i = end
                else:
                    i = j
            attrs.setdefault(name, value)
    return attrs, spread


def check_jsx(files: list[tuple[str, str]], catalog: Catalog) -> list[dict]:
    """Check the q-* tags of tier-2 sources, given as ``(label, text)`` pairs.

    Validates tag names, that each required attribute is present in any form (``{expr}`` and spreads
    included) and literal string values against the enum, integer, ident and number-list kinds.
    Children aren't statically known in JSX, so ``requires``, ``rules`` and ``parent`` are skipped.

    Only comments that are unambiguously comments are ignored (see ``_js_comment_spans``, plus
    ``<!-- -->`` in a ``.html`` file); q-* text inside strings or mid-line comments is still checked.
    """
    failures: list[dict] = []
    for label, source in files:
        starts = [0] + [i + 1 for i, ch in enumerate(source) if ch == "\n"]
        text = _blank_comments(source, html=label.endswith(".html"))
        braces = _Braces(text)
        matches = list(_JSX_TAG.finditer(text))
        for k, match in enumerate(matches):
            tag = match.group(1)
            line = bisect.bisect_right(starts, match.start())
            limit = matches[k + 1].start() if k + 1 < len(matches) else len(text)

            def fail(message: str) -> None:
                failures.append({"check": "kit", "detail": f"{label} line {line}: {message}"})

            element = catalog.elements.get(tag)
            if element is None:
                fail(f"unknown element <{tag}>")
                continue
            attrs, spread = _jsx_attributes(text, match.end(), braces, limit)
            for attribute in element.attributes:
                if attribute.name not in attrs:
                    if attribute.required and not spread:
                        fail(f"<{tag}> needs attribute {attribute.name}")
                    continue
                value = attrs[attribute.name]
                problem = _kind_problem(attribute, value) if value is not None else None
                if problem:
                    fail(f'<{tag}> {attribute.name}="{value}" {problem}')
    return failures
