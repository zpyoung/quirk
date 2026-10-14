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
_NUMBER = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
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

    __slots__ = ("tag", "attrs", "line", "parent", "children", "content")

    def __init__(self, tag: str, attrs: dict[str, str], line: int, parent: Optional["_Node"]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.parent = parent
        self.children: list[_Node] = []
        self.content: list[Any] = []  # text strings and child nodes in source order


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
        if node.tag in _FOREIGN:
            self._foreign += 1

    def _pop(self) -> None:
        node = self.stack.pop()
        self._open[node.tag] -= 1
        if node.tag in _FOREIGN:
            self._foreign -= 1

    def _close_nearest(self, targets: frozenset, stoppers: frozenset) -> bool:
        """Close the nearest open element in ``targets`` unless a stopper comes first."""
        for index in range(len(self.stack) - 1, 0, -1):
            tag = self.stack[index].tag
            if tag in targets:
                while len(self.stack) > index:
                    self._pop()
                return True
            if tag in stoppers:
                return False
        return False

    def _imply_end(self, tag: str) -> None:
        top = self.stack[-1].tag
        if tag == "li" and self._open["li"]:
            self._close_nearest(frozenset({"li"}), _ITEM_STOPPERS)
        elif tag in ("dd", "dt") and (self._open["dd"] or self._open["dt"]):
            self._close_nearest(frozenset({"dd", "dt"}), _ITEM_STOPPERS)
        elif tag in ("td", "th") and (self._open["td"] or self._open["th"]):
            self._close_nearest(frozenset({"td", "th"}), _TABLE_STOPPERS | {"tr"})
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
        if tag in _CLOSES_P and self._open["p"]:
            self._close_nearest(frozenset({"p"}), _BUTTON_SCOPE)

    def _start(self, tag: str, attrs: list, self_closing: bool) -> None:
        self._imply_end(tag)
        values: dict[str, str] = {}
        for name, value in attrs:
            values.setdefault(name, value if value is not None else "")
        parent = self.stack[-1]
        node = _Node(tag, values, self.getpos()[0], parent)
        parent.children.append(node)
        parent.content.append(node)
        self.nodes.append(node)
        if tag in _VOID or (self_closing and self._foreign):
            return
        self._push(node)


def _descendants(node: _Node) -> Iterator[_Node]:
    """Every element below ``node`` in document order, without recursion."""
    pending = list(reversed(node.children))
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.children))


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


def _first(node: _Node, tag: str) -> Optional[_Node]:
    return next((d for d in _descendants(node) if d.tag == tag), None)


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
    try:
        builder.feed(text)
        builder.close()
    except Exception:  # noqa: BLE001 - a parser fault must not hide the failures found so far
        pass
    found: list[tuple[int, int, str]] = []

    def report(line: int, message: str) -> None:
        found.append((line, len(found), message))

    for node in builder.nodes:
        if not _KIT_NAME.match(node.tag):
            continue
        element = catalog.elements.get(node.tag)
        if element is None:
            report(node.line, f"unknown element <{node.tag}>")
            continue
        _check_element(node, element, report)
    found.sort()
    return [{"check": "kit", "detail": f"{label} line {line}: {message}"} for line, _, message in found]


def _check_element(node: _Node, element: Element, report: Report) -> None:
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
        below = list(_descendants(node))
        for group in element.requires:
            if not any(_selector_matches(selector, node, below) for selector in group):
                names = ", ".join(s[1:] if s.startswith("@") else s for s in group)
                report(node.line, f"<{tag}> needs one of: {names}")
    if element.parent is not None:
        ancestor = node.parent
        while ancestor is not None and ancestor.tag != element.parent:
            ancestor = ancestor.parent
        if ancestor is None:
            report(node.line, f"<{tag}> must be inside <{element.parent}>")
    for rule in element.rules:
        _RULES[rule](node, report)


def _selector_matches(selector: str, node: _Node, below: list[_Node]) -> bool:
    own = _ATTR_SELECTOR.match(selector)
    if own:
        return own.group(1) in node.attrs
    parsed = _NODE_SELECTOR.match(selector)
    if parsed is None:
        return False
    want_tag, want_attr, want_value = parsed.groups()
    for descendant in below:
        if want_tag is not None and descendant.tag != want_tag:
            continue
        if want_attr is not None:
            if want_attr not in descendant.attrs:
                continue
            if want_value is not None and descendant.attrs[want_attr] != want_value:
                continue
        return True
    return False


def _rule_max_series(node: _Node, report: Report) -> None:
    table = _first(node, "table")
    if table is None:
        return
    y = node.attrs.get("y")
    if y is not None:
        series = len([part for part in y.split(",") if part.strip()])
    else:
        rows = [d for d in _descendants(table) if d.tag == "tr"]
        header = next((r for r in rows if _inside(r, "thead", table)), rows[0] if rows else None)
        if header is None:
            return
        cells = [c for c in header.children if c.tag == "th"]
        if not cells:
            return
        series = max(len(cells) - 1, 0)
    if series > MAX_SERIES:
        report(node.line, f"<{node.tag}> has {series} series; the limit is {MAX_SERIES}")


def _inside(node: _Node, tag: str, stop: _Node) -> bool:
    ancestor = node.parent
    while ancestor is not None and ancestor is not stop:
        if ancestor.tag == tag:
            return True
        ancestor = ancestor.parent
    return False


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


def _rule_diff_notes(node: _Node, report: Report) -> None:
    pre = _first(node, "pre")
    if pre is None:
        return
    files = parse_diff(_text(pre))
    for note in (d for d in _descendants(node) if d.tag == "q-diff-note"):
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


def _rule_heading_sections(node: _Node, report: Report) -> None:
    sections = [c for c in node.children if c.tag == "section"]
    for index, section in enumerate(sections, 1):
        first = section.children[0] if section.children else None
        if first is None or first.tag not in _HEADINGS:
            report(section.line, f"<{node.tag}> section {index} does not start with a heading")


def _rule_timeline_items(node: _Node, report: Report) -> None:
    ol = _first(node, "ol")
    if ol is None:
        return
    items = [c for c in ol.children if c.tag == "li"]
    for index, item in enumerate(items, 1):
        if not any(d.tag == "time" and "datetime" in d.attrs for d in _descendants(item)):
            report(item.line, f"<{node.tag}> item {index} has no <time datetime>")
        tone = item.attrs.get("data-tone")
        if tone is not None and tone not in TONES:
            report(item.line, f'<{node.tag}> item {index} data-tone="{tone}" is not one of {", ".join(TONES)}')


_RULES: dict[str, Callable[[_Node, Report], None]] = {
    "max-series": _rule_max_series,
    "diff-notes": _rule_diff_notes,
    "heading-sections": _rule_heading_sections,
    "board-columns": _rule_heading_sections,
    "timeline-items": _rule_timeline_items,
}
assert set(_RULES) == KNOWN_RULES


# -- JSX -------------------------------------------------------------------------------------------

_JSX_TAG = re.compile(r"<(q-[a-z]+(?:-[a-z]+)*)(?=[\s/>])")
_JSX_ATTR = re.compile(r"[A-Za-z_$][\w$:.-]*")
_JSX_LITERAL = re.compile(r"""^(?:"([^"\\\n]*)"|'([^'\\\n]*)')$""")


def _skip_braces(text: str, start: int) -> int:
    """Index just past the ``}`` that closes the ``{`` at ``start`` (``len(text)`` if unterminated).

    Strings, template literals with ``${}`` nesting and comments are skipped, so a brace or ``>``
    inside one does not end the expression.
    """
    n = len(text)
    stack = ["{"]
    i = start + 1
    while i < n and stack:
        c = text[i]
        if stack[-1] == "`":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
            elif c == "$" and text.startswith("${", i):
                stack.append("{")
                i += 1
            i += 1
            continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif c == "`":
            stack.append("`")
            i += 1
        elif c == "{":
            stack.append("{")
            i += 1
        elif c == "}":
            stack.pop()
            i += 1
        elif c == "/" and text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end + 1
        elif c == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            i += 1
    return min(i, n)


def _jsx_attributes(text: str, pos: int) -> tuple[dict[str, Optional[str]], bool]:
    """Read the attributes of the JSX tag whose name ends at ``pos``.

    Returns the attribute names mapped to their literal string value, or ``None`` for an expression
    or a valueless attribute, and whether a ``{...spread}`` could be supplying more.
    """
    attrs: dict[str, Optional[str]] = {}
    spread = False
    n = len(text)
    i = pos
    while i < n:
        c = text[i]
        if c == ">":
            break
        if c.isspace() or c == "/":
            i += 1
        elif c == "{":
            spread = True
            i = _skip_braces(text, i)
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
                    end = _skip_braces(text, j)
                    literal = _JSX_LITERAL.match(text[j + 1 : end - 1].strip())
                    value = (literal.group(1) if literal.group(1) is not None else literal.group(2)) if literal else None
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
    """
    failures: list[dict] = []
    for label, text in files:
        starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
        for match in _JSX_TAG.finditer(text):
            tag = match.group(1)
            line = bisect.bisect_right(starts, match.start())

            def fail(message: str) -> None:
                failures.append({"check": "kit", "detail": f"{label} line {line}: {message}"})

            element = catalog.elements.get(tag)
            if element is None:
                fail(f"unknown element <{tag}>")
                continue
            attrs, spread = _jsx_attributes(text, match.end())
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
