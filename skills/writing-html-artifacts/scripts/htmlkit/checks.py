"""Static checks over a built artifact: header, licenses, checksums, external references, size.

Library blocks (``data-quirk-lib``) and shell blocks (``data-quirk-shell``) are cut out before
the reference scan and verified by hash instead, so the vendored libraries and the two shipped
scripts can mention URLs and call ``fetch`` without tripping the scan. The scan also skips HTML
comments and ``application/json`` script blocks, which are data and never load anything.

``mode`` is ``offline``, ``connected`` or ``companion``; companion pages follow the offline
rules (``/_quirk/lib/`` paths are not ``http:``, ``https:`` or ``//`` targets, so they pass).
"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from typing import Iterable, Optional

from . import SKILL_DIR
from .header import read_header
from .vendor import VendorError, VendorStore, escape_inline, sha256_text

MODES = ("offline", "connected", "companion")
SIZE_FAIL = 10 * 1024 * 1024
SIZE_WARN = 2 * 1024 * 1024

_LIB_BLOCK = re.compile(
    r'<(script|style)\b[^>]*?\bdata-quirk-lib="([^"]*)"[^>]*>(.*?)</\1\s*>', re.IGNORECASE | re.DOTALL
)
_SHELL_BLOCK = re.compile(
    r'<script\b[^>]*?\bdata-quirk-shell="([^"]*)"[^>]*>(.*?)</script\s*>', re.IGNORECASE | re.DOTALL
)
_JSON_BLOCK = re.compile(
    r'<script\b[^>]*\btype\s*=\s*["\']?application/(?:ld\+)?json["\']?[^>]*>.*?</script\s*>',
    re.IGNORECASE | re.DOTALL,
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG = re.compile(r'<([a-zA-Z][a-zA-Z0-9:-]*)((?:"[^"]*"|\'[^\']*\'|[^\'">])*)>')
_ATTR = re.compile(r'([^\s"\'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'=<>`]+)))?')
_STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.IGNORECASE | re.DOTALL)
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
_LOADING_ATTRS = ("src", "href", "srcset", "poster", "action", "data")
_NARROW_ATTRS = (("script", "src"), ("link", "href"))


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


def _css_contexts(scan: str, style_attrs: list[str]) -> list[str]:
    return [m.group(1) for m in _STYLE_BLOCK.finditer(scan)] + style_attrs


def _reference_failures(scan: str, mode: str, tier: int) -> list[dict]:
    strict = mode in ("offline", "companion")
    markup_all = strict and tier == 1
    css_any = strict
    found: list[str] = []
    style_attrs: list[str] = []

    for tag_match in _TAG.finditer(scan):
        tag = tag_match.group(1).lower()
        for attr in _ATTR.finditer(tag_match.group(2)):
            attr_name = attr.group(1).lower()
            value = html_lib.unescape(attr.group(2) or attr.group(3) or attr.group(4) or "")
            if attr_name == "style":
                style_attrs.append(value)
                continue
            if markup_all:
                if attr_name not in _LOADING_ATTRS or (tag == "a" and attr_name == "href"):
                    continue
            elif (tag, attr_name) not in _NARROW_ATTRS:
                continue
            if attr_name == "srcset":
                candidates = [c.strip().split(None, 1)[0] for c in value.split(",") if c.strip()]
            else:
                candidates = [value]
            for candidate in candidates:
                if _is_external(candidate):
                    found.append(f"<{tag} {attr_name}> loads {_clip(candidate)}")

    for css in _css_contexts(scan, style_attrs):
        for m in _CSS_IMPORT.finditer(css):
            if _is_external(_first(m)):
                found.append(f"@import of {_clip(_first(m))}")
        regions = [css] if css_any else [m.group(0) for m in _FONT_FACE.finditer(css)]
        for region in regions:
            for m in _CSS_URL.finditer(region):
                if _is_external(_first(m)):
                    kind = "CSS url()" if css_any else "font url()"
                    found.append(f"{kind} loads {_clip(_first(m))}")

    if markup_all:
        for pattern, label in _CALLS:
            if pattern.search(scan):
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

    labels: dict[str, None] = {}
    for m in _LIB_BLOCK.finditer(html):
        label, kind = m.group(2), "css" if m.group(1).lower() == "style" else "js"
        labels[label] = None
        failure = _lib_checksum_failure(label, kind, m.group(3), vendor)
        if failure:
            failures.append(failure)
    failures.extend(_license_failures(html, labels))
    for m in _SHELL_BLOCK.finditer(html):
        failure = _shell_checksum_failure(m.group(1), m.group(2), shell_map)
        if failure:
            failures.append(failure)

    scan = _LIB_BLOCK.sub(" ", html)
    scan = _SHELL_BLOCK.sub(" ", scan)
    scan = _COMMENT.sub(" ", scan)
    scan = _JSON_BLOCK.sub(" ", scan)
    failures.extend(_reference_failures(scan, mode, tier))

    size = len(html.encode("utf-8"))
    if size > SIZE_FAIL:
        failures.append({"check": "size", "detail": f"{size} bytes exceeds the {SIZE_FAIL} byte limit"})
    if size > SIZE_WARN:
        warnings.append({"check": "size", "detail": f"{size} bytes is over {SIZE_WARN}; the file may be slow to open"})

    return {"passed": not failures, "failures": failures, "warnings": warnings}
