"""Page shapes: the registry of layout names, the generated section nav and region placement.

Every tier-1 page has one of seven shapes. The build emits the same regions (summary, nav, main,
aside) in each shape's own DOM order and ``theme/layout.css`` places them, so tab order, phones
and print all follow the document. ``validate_layout`` guards the names, ``build_nav`` derives the
section nav from the page's headings, and ``render_regions`` assembles the region wrapper.
"""
from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from typing import Optional

LAYOUTS: tuple[str, ...] = ("report", "explainer", "longform", "tool", "comparison", "dashboard", "reference")
DEFAULT_LAYOUT = "report"
NAV_MODES = ("auto", "on", "off")
NAV_MIN_H2 = 5

_NAV_EXCLUDED = ("q-panel", "q-compare", "q-tabs", "q-board")
_NAV_LABEL = {"reference": "Sections"}
_ID_ATTR = re.compile(r"""\bid\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.I)
_NON_SLUG = re.compile(r"[^a-z0-9]+")

SUMMARY_PLACEMENT = {
    "report": "the answer or findings under the h1",
    "explainer": "the answer or findings under the h1",
    "longform": "the answer or findings under the h1",
    "comparison": "the recommendation line above the table",
    "tool": "the live result beside the inputs",
    "dashboard": "the headline metric, top-left",
    "reference": "a one-line purpose under the h1",
}


def _source_error(message: str) -> Exception:
    from .assemble import SourceError

    return SourceError(message)


def validate_layout(value: object, *, origin: str = "header field 'layout'") -> str:
    """Return ``value`` when it names a shape; raises SourceError listing all seven names otherwise.

    ``origin`` names where the value came from (the source header, ``screen.json``, ``quirk-app.json``
    or the ``--layout`` flag) so the error points the author at the place to fix.
    """
    if isinstance(value, str) and value in LAYOUTS:
        return value
    raise _source_error(f"{origin} must be one of {', '.join(LAYOUTS)}, got {value!r}")


def summary_hint(layout: str) -> str:
    """Where the summary slot's content goes on ``layout``, for the missing-summary error."""
    return SUMMARY_PLACEMENT.get(layout, SUMMARY_PLACEMENT[DEFAULT_LAYOUT])


def collect_ids(*texts: str) -> set[str]:
    """Every ``id`` attribute value found in the given HTML texts."""
    found: set[str] = set()
    for text in texts:
        for match in _ID_ATTR.finditer(text):
            found.add(next(g for g in match.groups() if g is not None))
    return found


class _Heading:
    __slots__ = ("level", "start", "tag_len", "id", "text", "counted")

    def __init__(self, level: int, start: int, tag_len: int, existing: Optional[str], counted: bool) -> None:
        self.level = level
        self.start = start
        self.tag_len = tag_len
        self.id = existing
        self.text = ""
        self.counted = counted


class _HeadingScan(HTMLParser):
    """Collect h2/h3 headings with their source offsets, skipping those inside the excluded elements."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self._lines = [0]
        for line in text.split("\n"):
            self._lines.append(self._lines[-1] + len(line) + 1)
        self._excluded = 0
        self._open: Optional[_Heading] = None
        self.headings: list[_Heading] = []
        self.ids: set[str] = set()

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._lines[line - 1] + col

    def handle_starttag(self, tag: str, attrs: list) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)
        if tag in _NAV_EXCLUDED:
            self._excluded += 1
        if tag in ("h2", "h3"):
            existing = next((v for n, v in attrs if n == "id" and v), None)
            heading = _Heading(int(tag[1]), self._offset(), 1 + len(tag), existing, self._excluded == 0)
            self.headings.append(heading)
            self._open = heading

    def handle_endtag(self, tag: str) -> None:
        if tag in _NAV_EXCLUDED and self._excluded:
            self._excluded -= 1
        if tag in ("h2", "h3"):
            self._open = None

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._open.text += data


def _slug(text: str) -> str:
    return _NON_SLUG.sub("-", text.lower()).strip("-") or "section"


def _unique(base: str, taken: set[str]) -> str:
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        candidate = f"{base}-{n}"
    taken.add(candidate)
    return candidate


def _list(items: list[tuple[_Heading, list[_Heading]]], *, css_class: Optional[str]) -> str:
    def link(heading: _Heading) -> str:
        label = html_lib.escape(" ".join(heading.text.split()))
        return f'<a href="#{html_lib.escape(heading.id or "", quote=True)}">{label}</a>'

    rows = []
    for heading, children in items:
        nested = ""
        if children:
            nested = "<ol>" + "".join(f"<li>{link(c)}</li>" for c in children) + "</ol>"
        rows.append(f"<li>{link(heading)}{nested}</li>")
    attr = f' class="{css_class}"' if css_class else ""
    return f"<ol{attr}>" + "".join(rows) + "</ol>"


def build_nav(main_html: str, *, layout: str, nav: str, reserved_ids: set[str]) -> tuple[Optional[str], str]:
    """Build the section nav for ``main_html``; returns ``(nav_html or None, main_html)``.

    ``main_html`` comes back unchanged unless a nav is built, in which case every counted h2 and h3
    without an ``id`` gains one derived from its text and made unique against ``reserved_ids`` and
    the ids already in the page. Headings inside q-panel, q-compare, q-tabs and q-board are not
    counted or listed. The nav appears when ``nav`` is ``on``, or ``auto`` on ``reference`` or at
    five or more h2s. Raises SourceError for ``off`` on ``reference``, for ``on`` with no h2, and for ``auto`` on
    ``reference`` with no h2 or h3.
    """
    if nav not in NAV_MODES:
        raise ValueError(f"nav must be one of {', '.join(NAV_MODES)}, got {nav!r}")
    if nav == "off" and layout == "reference":
        raise _source_error("nav 'off' is not allowed on the reference shape: reference always has its section nav")
    scan = _HeadingScan(main_html)
    scan.feed(main_html)
    scan.close()
    counted = [h for h in scan.headings if h.counted]
    h2_count = sum(1 for h in counted if h.level == 2)
    if nav == "on" and h2_count == 0:
        raise _source_error("nav needs at least one h2 in main (nav is set to 'on')")
    if nav == "auto" and layout == "reference" and not counted:
        raise _source_error("a reference page needs h2 sections for its section nav: add h2 headings to main")
    if not (nav == "on" or (nav == "auto" and (layout == "reference" or h2_count >= NAV_MIN_H2))):
        return None, main_html

    taken = set(reserved_ids) | scan.ids
    insertions: list[tuple[int, str]] = []
    for heading in counted:
        if heading.id is None:
            heading.id = _unique(_slug(heading.text), taken)
            insertions.append((heading.start + heading.tag_len, f' id="{heading.id}"'))
    page = main_html
    for position, text in sorted(insertions, reverse=True):
        page = page[:position] + text + page[position:]

    items: list[tuple[_Heading, list[_Heading]]] = []
    for heading in counted:
        if heading.level == 2 or not items:
            items.append((heading, []))
        else:
            items[-1][1].append(heading)
    label = _NAV_LABEL.get(layout, "On this page")
    markup = (
        f'<nav class="q-nav" aria-label="{label}">'
        f'<details class="q-nav-menu"><summary>{label}</summary>{_list(items, css_class=None)}</details>'
        f'{_list(items, css_class="q-nav-rail")}'
        "</nav>"
    )
    return markup, page


def render_regions(layout: str, *, summary: str, main: str, aside: str, nav: Optional[str], legacy: bool) -> str:
    """Wrap the regions in ``<div class="q-page" data-layout=...>`` in the shape's DOM order.

    ``main`` is wrapped in ``<main id="main">`` unless ``legacy`` is set, because a legacy skeleton
    already provides it. An empty ``summary`` is omitted; only the legacy-summary path allows that.
    Raises ValueError for a layout outside ``LAYOUTS``.
    """
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {', '.join(LAYOUTS)}, got {layout!r}")
    summary_html = f'<section class="q-summary" aria-label="Summary">\n{summary}\n</section>' if summary else ""
    main_html = main if legacy else f'<main id="main">\n{main}\n</main>'
    if layout == "tool":
        order = [nav, main_html, summary_html]
    elif layout == "report":
        order = [summary_html, nav, main_html, aside]
    else:
        order = [summary_html, nav, main_html]
    body = "\n".join(part for part in order if part)
    return f'<div class="q-page" data-layout="{layout}">\n{body}\n</div>'
