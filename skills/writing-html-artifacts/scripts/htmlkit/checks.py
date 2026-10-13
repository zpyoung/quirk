"""Static checks over a built artifact: header, licenses, checksums, external references, size.

The page is tokenized once with ``html.parser``, following HTML raw-text and comment rules, so
text that merely looks like markup inside script, style or comments cannot hide or fake a reference.

Library blocks (``data-quirk-lib``) and shell blocks (``data-quirk-shell``) are verified by hash
instead of scanned, so the vendored libraries and the two shipped scripts can mention URLs and call
``fetch`` without tripping the scan. A block counts as verified only when its opening tag carries
exactly that one attribute; any other attribute (``src`` above all) makes it an ordinary element
that is scanned like the rest of the page. Comments and ``application/json`` script blocks are
data and never load anything. ``fetch(`` and similar calls are looked for only in inline script
bodies and ``on*`` handler attributes, never in prose.

``mode`` is ``offline``, ``connected`` or ``companion``; companion pages follow the offline
rules (``/_quirk/lib/`` paths are not ``http:``, ``https:`` or ``//`` targets, so they pass).
"""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional

from . import SKILL_DIR
from .header import read_header
from .vendor import VendorError, VendorStore, escape_inline, sha256_text

MODES = ("offline", "connected", "companion")
SIZE_FAIL = 10 * 1024 * 1024
SIZE_WARN = 2 * 1024 * 1024

_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.IGNORECASE)
_CSS_URL = re.compile(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)\"'\s]*))\s*\)", re.IGNORECASE)
_CSS_IMPORT = re.compile(
    r"@import\s+(?:url\(\s*)?(?:\"([^\"]*)\"|'([^']*)'|([^)\"'\s;]+))", re.IGNORECASE
)
_CALLS = (
    (re.compile(r"\bfetch\s*\("), "fetch("),
    (re.compile(r"\bXMLHttpRequest\b"), "XMLHttpRequest"),
    (re.compile(r"\bWebSocket\s*\("), "WebSocket("),
    (re.compile(r"\bEventSource\s*\("), "EventSource("),
)
_CSS_STRING_CALL = re.compile(r"(?<![\w-])((?:-webkit-)?image-set|src)\(", re.IGNORECASE)
_LOADING_ATTRS = ("src", "href", "srcset", "imagesrcset", "poster", "action", "data", "background")
_NARROW_ATTRS = (("script", "src"), ("script", "href"), ("link", "href"))
_SRCSET_ATTRS = ("srcset", "imagesrcset")


_RAW_TEXT = frozenset({"script", "style", "textarea", "title", "xmp", "iframe", "noembed", "noframes", "noscript"})
_FOREIGN = frozenset({"svg", "math"})
_JSON_TYPES = ("application/json", "application/ld+json")
_COMMENT_END = re.compile(r"--!?>")
_SCRIPT_ESCAPES = re.compile(r"<!---?>|<!--|-->|<script(?=[\t\n\r\f />])|</script(?=[\t\n\r\f />])", re.IGNORECASE)


def _ends_double_escaped(script_text: str) -> bool:
    """True when ``script_text`` leaves an HTML script in the double-escaped state.

    There a ``</script>`` does not end the element, so the text after it is still script.
    """
    state = 0
    for m in _SCRIPT_ESCAPES.finditer(script_text):
        token = m.group(0).lower()
        if token in ("<!-->", "<!--->") or token == "-->":
            state = 0
        elif token == "<!--":
            state = state or 1
        elif token == "<script":
            state = 2 if state == 1 else state
        elif state == 2:
            state = 1
    return state == 2


@dataclass
class _Page:
    """What the tokenizer found that can load or run something."""

    attrs: list[tuple[str, str, str]] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    handlers: list[str] = field(default_factory=list)
    css: list[str] = field(default_factory=list)
    libs: list[tuple[str, str, str]] = field(default_factory=list)
    shells: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _Capture:
    tag: str
    verified: Optional[tuple[str, str]]
    json_data: bool
    foreign: bool
    parts: list[str] = field(default_factory=list)


class _Scanner(HTMLParser):
    """Tokenizer that mirrors how browsers split markup from raw text and comments.

    The stdlib parser diverges from the HTML spec in ways that would let text hide real
    markup: it enters raw-text mode only for script and style, ends a comment at the next
    ``-->`` whatever follows ``<!--``, and ignores attributes on end tags. Those hooks are
    overridden so the scan is never narrower than what a browser would load.
    """

    CDATA_CONTENT_ELEMENTS = ()
    RCDATA_CONTENT_ELEMENTS = ()

    def __init__(self, page: _Page) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page
        self._foreign = 0
        self._capture: Optional[_Capture] = None

    def set_cdata_mode(self, elem, *, escapable=False):
        self.cdata_elem = elem.lower()
        self.interesting = re.compile(r"</%s(?=[\t\n\r\f />])" % re.escape(self.cdata_elem), re.IGNORECASE)

    def parse_comment(self, i, report=True):
        raw = self.rawdata
        start = i + 4
        if raw.startswith(">", start):
            return start + 1
        if raw.startswith("->", start):
            return start + 2
        match = _COMMENT_END.search(raw, start)
        return match.end() if match else -1

    def parse_marked_section(self, i, report=1):
        end = self.rawdata.find(">", i)
        return end + 1 if end >= 0 else -1

    def parse_endtag(self, i):
        if self.cdata_elem:
            raw = self.rawdata
            body = "".join(self._capture.parts) if self._capture else ""
            if self.cdata_elem == "script" and not self._foreign and _ends_double_escaped(body):
                self.handle_data(raw[i : i + 8])
                return i + 8
            end = raw.find(">", i)
            if end < 0:
                return -1
            self.handle_endtag(self.cdata_elem)
            self.clear_cdata_mode()
            return end + 1
        return super().parse_endtag(i)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, selfclosing=False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, selfclosing=True)

    def handle_data(self, data):
        if self._capture is not None:
            self._capture.parts.append(data)

    def handle_endtag(self, tag):
        if self._capture is not None and tag == self._capture.tag:
            self._close_capture()
        if tag in _FOREIGN and self._foreign:
            self._foreign -= 1

    def _open(self, tag: str, attrs: list, selfclosing: bool) -> None:
        values = [(name, value if value is not None else "") for name, value in attrs]
        lone = attrs[0] if len(attrs) == 1 and attrs[0][1] is not None else None
        verified = None
        if lone is not None and not self._foreign:
            if lone[0] == "data-quirk-lib" and tag in ("script", "style"):
                verified = ("lib", lone[1])
            elif lone[0] == "data-quirk-shell" and tag == "script":
                verified = ("shell", lone[1])
        if verified is None:
            for name, value in values:
                self.page.attrs.append((tag, name, value))
                if name.startswith("on"):
                    self.page.handlers.append(value)
        if tag in _FOREIGN and not selfclosing:
            self._foreign += 1
        if tag in _RAW_TEXT and not (selfclosing and self._foreign):
            declared = next((v.strip().lower() for n, v in values if n == "type"), "")
            self.set_cdata_mode(tag)
            self._capture = _Capture(tag, verified, declared in _JSON_TYPES, bool(self._foreign))

    def _close_capture(self, terminated: bool = True) -> None:
        cap, self._capture = self._capture, None
        text = "".join(cap.parts)
        if cap.tag == "noscript" or cap.foreign:
            nested = _Scanner(self.page)
            nested.feed(text)
            nested.finish()
        if cap.verified and terminated:
            kind, label = cap.verified
            if kind == "lib":
                self.page.libs.append((label, "css" if cap.tag == "style" else "js", text))
            else:
                self.page.shells.append((label, text))
        elif cap.tag == "script" and not cap.json_data:
            self.page.scripts.append(text)
        elif cap.tag == "style":
            self.page.css.append(text)

    def finish(self) -> None:
        """Flush the input; an element left open at EOF still has its body scanned."""
        self.close()
        if self._capture is not None:
            self._capture.parts.append(self.rawdata)
            self._close_capture(terminated=False)


def _scan_page(html: str) -> _Page:
    page = _Page()
    scanner = _Scanner(page)
    scanner.feed(html)
    scanner.finish()
    return page


def default_shells(skill_dir: Optional[Path] = None) -> dict[str, Path]:
    """Shell name to the shipped file its inlined block must match."""
    base = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    return {
        "chrome": base / "theme" / "chrome.js",
        "companion": base / "templates" / "companion" / "companion.js",
    }


def _is_external(url: str) -> bool:
    cleaned = re.sub(r"[\t\r\n]", "", html_lib.unescape(url)).strip().lower()
    return cleaned.startswith(("http:", "https:", "//"))


def _clip(text: str, width: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


def _first(match: "re.Match[str]") -> str:
    return next((g for g in match.groups() if g), "")


def _css_string_targets(css: str) -> Iterable[tuple[str, str]]:
    """Yield ``(function, target)`` for quoted strings inside ``image-set()`` and ``src()``.

    Those functions accept a bare string as an image target, which ``url()`` matching misses.
    A string that is the argument of a nested ``url(`` is left to the ``url()`` scan.
    A call nested in one already scanned is skipped, so the scan stays linear on unclosed calls.
    """
    n = len(css)
    scanned_to = 0
    for call in _CSS_STRING_CALL.finditer(css):
        if call.start() < scanned_to:
            continue
        depth, i = 1, call.end()
        while i < n and depth:
            ch = css[i]
            if ch in "\"'":
                end = i + 1
                while end < n and css[end] != ch:
                    end += 2 if css[end] == "\\" else 1
                if not css[max(0, i - 8) : i].rstrip().lower().endswith("url("):
                    yield call.group(1).lower(), css[i + 1 : end]
                i = end
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        scanned_to = i


def _license_failures(html: str, labels: Iterable[str]) -> list[dict]:
    out = []
    for label in labels:
        name, _, ver = label.rpartition("@")
        if not name or not ver or f"<!-- license: {name} {ver} " not in html:
            out.append({"check": "license", "detail": f"no license comment for {label}"})
    return out


def _lib_checksum_failure(label: str, kind: str, content: str, store: VendorStore) -> Optional[dict]:
    name, _, ver = label.rpartition("@")
    if not name or not ver:
        return {"check": "checksum", "detail": f"library block label {label!r} is not name@version"}
    try:
        lv = store.resolve(name, ver)
    except VendorError as exc:
        return {"check": "checksum", "detail": f"{label}: {exc}"}
    expected = {f.inline_sha256 for f in lv.files if f.inline and f.kind == kind and f.inline_sha256}
    if sha256_text(content) not in expected:
        return {"check": "checksum", "detail": f"library block {label} differs from its recorded inline_sha256"}
    return None


def _shell_checksum_failure(name: str, content: str, shells: dict[str, Path]) -> Optional[dict]:
    path = shells.get(name)
    if path is None:
        return {"check": "checksum", "detail": f"shell block {name!r} is not a known shell"}
    try:
        expected = sha256_text(escape_inline(Path(path).read_text(encoding="utf-8"), "js"))
    except OSError:
        return {"check": "checksum", "detail": f"shell block {name!r}: shipped file {path} cannot be read"}
    if sha256_text(content) != expected:
        return {"check": "checksum", "detail": f"shell block {name!r} differs from {path}"}
    return None


def _reference_failures(page: _Page, mode: str, tier: int) -> list[dict]:
    strict = mode in ("offline", "companion")
    markup_all = strict and tier == 1
    css_any = strict
    found: list[str] = []
    style_attrs: list[str] = []

    for tag, attr_name, value in page.attrs:
        if attr_name == "style":
            style_attrs.append(value)
            continue
        if attr_name == "srcdoc":
            nested = _reference_failures(_scan_page(value), mode, tier)
            found.extend(f"srcdoc: {f['detail']}" for f in nested)
            continue
        local = attr_name.rpartition(":")[2]
        if markup_all:
            if (attr_name not in _LOADING_ATTRS and local != "href") or (tag == "a" and local == "href"):
                continue
        elif (tag, local if local == "href" else attr_name) not in _NARROW_ATTRS:
            continue
        if attr_name in _SRCSET_ATTRS:
            candidates = [c.strip().split(None, 1)[0] for c in value.split(",") if c.strip()]
        else:
            candidates = [value]
        for candidate in candidates:
            if _is_external(candidate):
                found.append(f"<{tag} {attr_name}> loads {_clip(candidate)}")

    for css in page.css + style_attrs:
        for m in _CSS_IMPORT.finditer(css):
            if _is_external(_first(m)):
                found.append(f"@import of {_clip(_first(m))}")
        regions = [css] if css_any else [m.group(0) for m in _FONT_FACE.finditer(css)]
        for region in regions:
            for m in _CSS_URL.finditer(region):
                if _is_external(_first(m)):
                    kind = "CSS url()" if css_any else "font url()"
                    found.append(f"{kind} loads {_clip(_first(m))}")
            for func, target in _css_string_targets(region):
                if _is_external(target):
                    prefix = "CSS" if css_any else "font"
                    found.append(f"{prefix} {func}() loads {_clip(target)}")

    if markup_all:
        for pattern, label in _CALLS:
            if any(pattern.search(code) for code in page.scripts + page.handlers):
                found.append(f"page code calls {label}")

    return [{"check": "external-refs", "detail": detail} for detail in dict.fromkeys(found)]


def run_checks(
    html: str,
    *,
    mode: str,
    tier: int,
    vendor: VendorStore,
    shells: Optional[dict[str, Path]] = None,
) -> dict:
    """Run every static check and return ``{passed, failures, warnings}``.

    Each failure and warning is ``{check, detail}``. ``shells`` maps shell block names to the
    shipped files they must match; it defaults to ``default_shells()``, and a shell is only
    checked when its block is present. Raises ValueError for an unknown ``mode``.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, got {mode!r}")
    shell_map = shells if shells is not None else default_shells()
    failures: list[dict] = []
    warnings: list[dict] = []

    meta = read_header(html)
    if meta is None:
        failures.append({"check": "header", "detail": "header is missing or unparseable"})
    elif "schema" not in meta:
        failures.append({"check": "header", "detail": "header has no schema field"})

    page = _scan_page(html)
    labels: dict[str, None] = {}
    for label, kind, content in page.libs:
        labels[label] = None
        failure = _lib_checksum_failure(label, kind, content, vendor)
        if failure:
            failures.append(failure)
    failures.extend(_license_failures(html, labels))
    for name, content in page.shells:
        failure = _shell_checksum_failure(name, content, shell_map)
        if failure:
            failures.append(failure)
    failures.extend(_reference_failures(page, mode, tier))

    size = len(html.encode("utf-8"))
    if size > SIZE_FAIL:
        failures.append({"check": "size", "detail": f"{size} bytes exceeds the {SIZE_FAIL} byte limit"})
    if size > SIZE_WARN:
        warnings.append({"check": "size", "detail": f"{size} bytes is over {SIZE_WARN}; the file may be slow to open"})

    return {"passed": not failures, "failures": failures, "warnings": warnings}
