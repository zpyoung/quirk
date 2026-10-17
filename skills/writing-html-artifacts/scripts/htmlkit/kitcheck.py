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

KNOWN_RULES = frozenset(
    {"max-series", "diff-notes", "heading-sections", "board-columns", "timeline-items", "compare-recommended", "flow-data"}
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
    """Report whether ``text`` uses ``<q-flow>``, which lays out and zooms with the flow bundle.

    The scan is textual, like ``needs``.
    """
    return bool(FLOW_TAG.search(text))

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


def _validate_flow_node(
    node: _Node, report_fail: Report, report_warn: Report
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
        entry = {
            "id": nid,
            "label": nlabel,
            "kind": nkind if isinstance(nkind, str) else None,
            "group": ngroup if isinstance(ngroup, str) else None,
            "detail_html": clean_detail,
        }
        node_map[nid] = entry
        clean_nodes.append(entry)

    raw_edges = data.get("edges", [])
    if not isinstance(raw_edges, list):
        fail(node.line, "<q-flow> edges must be a list")
        raw_edges = []

    clean_edges: list[dict[str, Any]] = []
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
        if isinstance(efrom, str) and isinstance(eto, str) and efrom in node_map and eto in node_map:
            clean_edges.append(
                {
                    "from": efrom,
                    "to": eto,
                    "label": elabel.strip() if isinstance(elabel, str) and elabel.strip() else None,
                    "async": easync is True,
                }
            )

    if before_fails:
        return None
    return {
        "groups": clean_groups,
        "group_map": group_map,
        "nodes": clean_nodes,
        "node_map": node_map,
        "edges": clean_edges,
    }


def _rule_flow_data(node: _Node, report: Report, index: _Index) -> None:
    _validate_flow_node(node, report, lambda _line, _msg: None)


def check_html_warnings(text: str, catalog: Catalog, *, label: str) -> list[dict]:
    """Return non-fatal kit warnings for ``text`` (such as large ``q-flow`` graphs or long edge labels)."""
    if not FLOW_TAG.search(text):
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
        kind_str = f" ({html_lib.escape(n['kind'])})" if n["kind"] else ""
        detail_str = f'<div data-q-flow-list-detail>{n["detail_html"]}</div>' if n["detail_html"] else ""
        outs = out_by_node.get(n["id"], [])
        edge_str = ""
        if outs:
            items = []
            for e in outs:
                tlabel = html_lib.escape(node_map[e["to"]]["label"])
                meta = []
                if e["label"]:
                    meta.append(html_lib.escape(e["label"]))
                if e["async"]:
                    meta.append("async")
                suffix = f" ({', '.join(meta)})" if meta else ""
                items.append(f"<li>\u2192 {tlabel}{suffix}</li>")
            edge_str = f"<ul>{''.join(items)}</ul>"
        return f'<li data-q-flow-list-node="{nid}"><strong>{label}</strong>{kind_str}{detail_str}{edge_str}</li>'

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


_RULES: dict[str, Callable[[_Node, Report, _Index], None]] = {
    "max-series": _rule_max_series,
    "diff-notes": _rule_diff_notes,
    "heading-sections": _rule_heading_sections,
    "board-columns": _rule_heading_sections,
    "timeline-items": _rule_timeline_items,
    "compare-recommended": _rule_compare_recommended,
    "flow-data": _rule_flow_data,
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
