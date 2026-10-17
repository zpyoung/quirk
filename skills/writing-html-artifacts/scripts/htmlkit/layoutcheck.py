"""Layout static check: slot content leaves page geometry to the page shapes and ``q-grid``.

Tier 1 scans the ``<style>`` elements and ``style=""`` attributes inside the ``q-page`` wrapper of
a built page; the head (tokens, base, layout, kit) is never inspected, and a page without the
wrapper yields no findings. Grid is allowed on and inside the page's own custom elements, because
it arranges the element's contents rather than the page; widths, floats and columns are not. Tier 2 scans an app's own ``src/`` stylesheets and ``style={{...}}``
objects in ``.tsx`` files.

Both entry points return ``[{"check": "layout", "detail": ...}]`` and never raise. CSS that cannot
be tokenized is skipped one declaration at a time.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterator, Optional

GRID_HINT = "use q-grid (and q-panel for titled panels)"
WIDTH_HINT = 'page shapes set widths; set "layout" in the header'

THEME_FILES = frozenset({"theme.css", "quirk-tokens.css", "quirk-layout.css"})
_WIDTH_PROPS = frozenset({"width", "min-width", "max-width"})
_PX_PER_UNIT = {"px": 1.0, "pt": 96 / 72, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}
_MAX_PX = 400.0
_MAX_FONT_RELATIVE = 25.0
_LENGTH = re.compile(r"(\d+(?:\.\d*)?|\.\d+)(px|pt|pc|in|cm|mm|rem|em)")
_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)", re.DOTALL)
_DECLARATION = re.compile(r"\s*(-{0,2}[a-zA-Z_][\w-]*)\s*:(.*)", re.DOTALL)
_IMPORTANT = re.compile(r"\s*!\s*important\s*$")
_VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)
_STYLE_OBJECT = re.compile(r"\bstyle\s*=\s*\{\s*\{")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_LIBRARY_PREFIXES = ("q-", "wa-")
_TYPE_SELECTOR = re.compile(r"(?<![\w.#:-])([a-z][a-z0-9]*-[a-z0-9-]*)")
_COMPOUND_END = re.compile(r"[\s>+~]")


def _flag(prop: str, value: str) -> Optional[str]:
    """The reason a declaration is flagged, or None. ``value`` is lowercased and may be empty."""
    if prop == "display" and value in ("grid", "inline-grid"):
        return GRID_HINT
    if (
        prop in ("grid", "grid-area")
        or prop.startswith(("grid-template", "grid-column", "grid-row"))
    ):
        return GRID_HINT
    if prop == "float" and value in ("left", "right", "inline-start", "inline-end"):
        return WIDTH_HINT
    if prop in ("columns", "column-count"):
        return WIDTH_HINT
    if prop in _WIDTH_PROPS and _wide(value):
        return WIDTH_HINT
    return None


def _is_custom_element(tag: str) -> bool:
    return "-" in tag and not tag.startswith(_LIBRARY_PREFIXES)


def _strip_nested(selector: str) -> str:
    """``selector`` with every ``(...)`` and ``[...]`` group blanked, so only top-level parts remain."""
    out, depth = [], 0
    for ch in selector:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
            ch = " "
        out.append(" " if depth else ch)
    return "".join(out)


def _split_selector_list(selectors: str) -> list[str]:
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(selectors):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(selectors[start:i])
            start = i + 1
    parts.append(selectors[start:])
    return parts


def _targets_custom_element(selectors: str) -> bool:
    """True when every selector in the list matches only a custom element or something inside one.

    A selector qualifies when a custom element's compound is its subject, or is followed by a
    descendant or child combinator; a sibling combinator straight after it leaves the element.
    """
    for selector in _split_selector_list(selectors.lower()):
        flat = _strip_nested(selector).strip()
        if not flat:
            return False
        inside = False
        for match in _TYPE_SELECTOR.finditer(flat):
            if not _is_custom_element(match.group(1)):
                continue
            end = _COMPOUND_END.search(flat, match.end())
            rest = flat[end.start():].lstrip() if end else ""
            if not rest or rest[0] not in "+~":
                inside = True
                break
        if not inside:
            return False
    return True


def _wide(value: str) -> bool:
    """True for a plain absolute length at or over the threshold; every other form is exempt."""
    m = _LENGTH.fullmatch(value.strip())
    if m is None:
        return False
    number, unit = float(m.group(1)), m.group(2)
    if unit in ("rem", "em"):
        return number >= _MAX_FONT_RELATIVE
    return number * _PX_PER_UNIT[unit] >= _MAX_PX


def _message(prop: str, value: str, hint: str) -> str:
    shown = f"{prop}: {value}" if value else prop
    return f"`{shown}` is not allowed in slot content; {hint}"


def _declarations(css: str) -> Iterator[tuple[int, str, str, str]]:
    """Yield ``(offset, property, value, selector)`` for each declaration, offset pointing at the property.

    Segments that end at ``{`` are selectors or at-rule preludes and are dropped, so declarations
    inside ``@media`` and ``@container`` blocks come out like top-level ones. ``selector`` is the
    innermost enclosing rule's selector list, or an empty string when there is none.
    """
    css = _COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), css)
    start = depth = i = 0
    quote = ""
    n = len(css)
    segments: list[tuple[int, int, str]] = []
    preludes: list[str] = []
    while i < n:
        ch = css[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote or ch == "\n":
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "{":
            preludes.append(css[start:i].strip())
            start, depth = i + 1, 0
        elif ch == "}" or (ch == ";" and depth == 0):
            segments.append((start, i, _innermost_selector(preludes)))
            if ch == "}" and preludes:
                preludes.pop()
            start, depth = i + 1, 0
        i += 1
    segments.append((start, n, _innermost_selector(preludes)))
    for a, b, selector in segments:
        m = _DECLARATION.match(css, a, b)
        if m is None:
            continue
        value = _IMPORTANT.sub("", m.group(2)).strip().lower()
        yield m.start(1), m.group(1).lower(), value, selector


def _innermost_selector(preludes: list[str]) -> str:
    return next((p for p in reversed(preludes) if not p.startswith("@")), "")


def _css_findings(css: str, *, in_custom_element: bool = False) -> Iterator[tuple[int, str]]:
    """Flagged declarations in ``css``; grid passes when ``in_custom_element`` or its rule targets one."""
    for offset, prop, value, selector in _declarations(css):
        hint = _flag(prop, value)
        if hint is None:
            continue
        if hint == GRID_HINT and (in_custom_element or (selector and _targets_custom_element(selector))):
            continue
        yield offset, _message(prop, value, hint)


class _SlotScanner(HTMLParser):
    """Collects ``(line, message)`` for styles that sit inside an element with class ``q-page``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list[tuple[int, str]] = []
        self._stack: list[tuple[str, bool]] = []
        self._style: Optional[tuple[int, list[str]]] = None

    def _inside(self) -> bool:
        return any(is_page for _, is_page in self._stack)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs)
        if tag not in _VOID:
            self._stack.append((tag, self._is_page(attrs)))
            if tag == "style" and self._style is None:
                line = self.getpos()[0] + (self.get_starttag_text() or "").count("\n")
                self._style = (line, [])

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs)

    @staticmethod
    def _is_page(attrs) -> bool:
        return any(n == "class" and "q-page" in (v or "").split() for n, v in attrs)

    def _open(self, tag, attrs) -> None:
        if not self._inside() and not self._is_page(attrs):
            return
        text = self.get_starttag_text() or ""
        for name, value in attrs:
            if name != "style" or not value:
                continue
            m = re.search(r"\bstyle\s*=", text)
            line = self.getpos()[0] + (text.count("\n", 0, m.start()) if m else 0)
            scoped = _is_custom_element(tag) or any(_is_custom_element(t) for t, _ in self._stack)
            for offset, message in _css_findings(value, in_custom_element=scoped):
                self.findings.append((line + value.count("\n", 0, offset), message))

    def handle_data(self, data):
        if self._style is not None:
            self._style[1].append(data)

    def handle_endtag(self, tag):
        if tag == "style" and self._style is not None:
            self._finish_style()
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def _finish_style(self) -> None:
        line, parts = self._style
        self._style = None
        if not self._inside():
            return
        css = "".join(parts)
        for offset, message in _css_findings(css):
            self.findings.append((line + css.count("\n", 0, offset), message))

    def finish(self) -> None:
        self.close()
        if self._style is not None:
            self._style[1].append(self.rawdata)
            self._finish_style()


def check_html(html: str, *, label: str) -> list[dict]:
    """Layout failures in a built page's slot content, ``<label> line N: <message>`` each.

    Only styles inside the ``q-page`` wrapper are inspected; a page without one has none.
    """
    try:
        scanner = _SlotScanner()
        scanner.feed(html)
        scanner.finish()
        found = scanner.findings
    except Exception:
        return []
    return [{"check": "layout", "detail": f"{label} line {line}: {message}"} for line, message in found]


def _skip_string(text: str, i: int) -> int:
    """Index just past the string literal that opens at ``text[i]``."""
    quote, n = text[i], len(text)
    i += 1
    while i < n and text[i] != quote:
        i += 2 if text[i] == "\\" else 1
    return i + 1


def _object_end(text: str, start: int) -> int:
    """Index of the ``}`` closing the object whose ``{`` is at ``start``, or the text length."""
    depth, i, n = 0, start, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            i = _skip_string(text, i)
            continue
        if ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def _split_entries(text: str, a: int, b: int) -> Iterator[tuple[int, int]]:
    depth, i, start = 0, a, a
    while i < b:
        ch = text[i]
        if ch in "\"'`":
            i = _skip_string(text, i)
            continue
        if ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
        elif ch == "," and depth == 0:
            yield start, i
            start = i + 1
        i += 1
    yield start, b


_ENTRY = re.compile(r"\s*(?:([A-Za-z_$][\w$]*)|\"([^\"]+)\"|'([^']+)')\s*:\s*", re.DOTALL)


def _tsx_findings(text: str) -> Iterator[tuple[int, str]]:
    for opener in _STYLE_OBJECT.finditer(text):
        a = opener.end()
        end = _object_end(text, a - 1)
        for s, e in _split_entries(text, a, end):
            m = _ENTRY.match(text, s, e)
            if m is None:
                continue
            key = next(g for g in m.groups() if g)
            prop = re.sub(r"[A-Z]", lambda c: "-" + c.group().lower(), key)
            raw = text[m.end() : e].strip()
            value = ""
            if raw[:1] in ("'", '"', "`") and raw[-1:] == raw[:1] and len(raw) >= 2 and "${" not in raw:
                value = raw[1:-1].strip().lower()
            elif _NUMBER.fullmatch(raw):
                value = f"{raw}px" if prop in _WIDTH_PROPS else raw
            hint = _flag(prop, value)
            if hint is not None:
                key_at = s + len(text[s:e]) - len(text[s:e].lstrip())
                yield key_at, _message(prop, value, hint)


def check_app_sources(paths: list[Path], *, root: Path) -> list[dict]:
    """Layout failures in an app's ``.css`` and ``.tsx`` sources, ``<path relative to root> line N``.

    The theme, token and layout stylesheets the build ships are skipped. A path that cannot be
    read is one failure, and the scan carries on with the rest.
    """
    out: list[dict] = []
    for path in paths:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix not in (".css", ".tsx") or path.name in THEME_FILES:
            continue
        full = path if path.is_absolute() else Path(root) / path
        try:
            text = full.read_text(encoding="utf-8")
        except (OSError, ValueError):
            out.append({"check": "layout", "detail": f"cannot read {path}"})
            continue
        try:
            rel = full.relative_to(root).as_posix()
        except ValueError:
            rel = full.as_posix()
        try:
            findings = list(_css_findings(text) if suffix == ".css" else _tsx_findings(text))
        except Exception:
            continue
        for offset, message in findings:
            out.append({"check": "layout", "detail": f"{rel} line {text.count(chr(10), 0, offset) + 1}: {message}"})
    return out
