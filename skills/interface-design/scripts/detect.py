#!/usr/bin/env python3
"""Regex detector for the UI rules in references/checklist.md that a regex can see.

It proposes candidates; the reviewing agent confirms each one in context before
reporting it. Covers CSS, SCSS, JSX and TSX (Tailwind class strings included).
Reads files only; --changed-since shells out to git with an argument list.

    python3 detect.py [--format text|json] [--changed-since GIT_REF] [--list-rules] PATH [PATH ...]

Exit codes: 0 no findings, 1 findings, 2 usage error, unreadable path or git failure.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

SCANNED_SUFFIXES = (".css", ".scss", ".jsx", ".tsx")
SKIPPED_DIRS = frozenset({"node_modules", ".git", "dist", "build", ".next"})
SCAN_SPAN_LIMIT = 20000

Hit = Tuple[int, str]


class Decl(NamedTuple):
    prop: str
    value: str
    offset: int
    value_offset: int


class Block:
    """A CSS rule body; `decls` holds only the declarations written directly in it."""

    def __init__(self, selector: str) -> None:
        self.selector = selector
        self.decls: List[Decl] = []


class Token(NamedTuple):
    offset: int
    variants: Tuple[str, ...]
    base: str


class ClassString(NamedTuple):
    offset: int
    text: str


class Attr(NamedTuple):
    name: str
    offset: int
    value: str


class Tag(NamedTuple):
    name: str
    start: int
    end: int
    attrs: Tuple[Attr, ...]
    self_closing: bool
    jsx_like: bool

    def attr_names(self) -> Set[str]:
        return {attr.name for attr in self.attrs}

    def find(self, name: str) -> Optional[Attr]:
        for attr in self.attrs:
            if attr.name.lower() == name.lower():
                return attr
        return None


class Rule(NamedTuple):
    id: str
    severity: str
    title: str
    check: Callable[[str], List[Hit]]
    file_level: bool = False


class Finding(NamedTuple):
    path: str
    line: int
    rule: str
    severity: str
    message: str


class GitError(Exception):
    pass


# ---------------------------------------------------------------------------
# Source preparation


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(?m)^[ \t]*//[^\n]*")


def _blank(match: "re.Match[str]") -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_comments(text: str) -> str:
    """Blank out comments in place so offsets and line numbers stay valid."""
    return _LINE_COMMENT.sub(_blank, _BLOCK_COMMENT.sub(_blank, text))


_QUOTES = "\"'`"


def _walk(text: str, i: int, brackets: Optional[Tuple[str, str]]) -> Optional[int]:
    """Index just past the string at text[i] (brackets None) or the bracket pair opening at text[i].

    Iterative with an explicit stack so nested `${}` templates cannot exhaust the interpreter
    stack. None means unbalanced (bracket mode only); string mode then returns len(text).
    """
    n = len(text)
    stop = n if brackets is None else min(n, i + SCAN_SPAN_LIMIT)
    # frames: a one-char str is a string frame (its quote); a list is a code frame [open, close, depth]
    stack: List[object] = [text[i]] if brackets is None else [[brackets[0], brackets[1], 0]]
    j = i + 1 if brackets is None else i
    while j < stop:
        frame = stack[-1]
        ch = text[j]
        if isinstance(frame, str):
            if ch == "\\":
                j += 2
            elif ch == frame:
                stack.pop()
                j += 1
                if not stack:
                    return j
            elif frame == "`" and text.startswith("${", j):
                stack.append(["{", "}", 1])
                j += 2
            elif ch == "\n" and frame != "`":
                stack.pop()
                if not stack:
                    return j
            else:
                j += 1
        else:
            if ch in _QUOTES:
                stack.append(ch)
            elif ch == frame[0]:
                frame[2] += 1
            elif ch == frame[1]:
                frame[2] -= 1
                if frame[2] == 0:
                    stack.pop()
                    if not stack:
                        return j + 1
            j += 1
    return n if brackets is None else None


def _skip_string(text: str, i: int) -> int:
    """Index just past the string literal opening at text[i]."""
    end = _walk(text, i, None)
    return len(text) if end is None else end


def _match_close(text: str, i: int, open_ch: str, close_ch: str) -> Optional[int]:
    """Index just past the bracket matching text[i], skipping strings; None if unbalanced."""
    return _walk(text, i, (open_ch, close_ch))


MAX_TEMPLATE_DEPTH = 32


def _literals(text: str, start: int, end: int, out: List[ClassString]) -> None:
    """Collect string literals in text[start:end]; template `${}` parts are blanked and scanned too.

    Templates nested deeper than MAX_TEMPLATE_DEPTH are blanked but not scanned.
    """
    pending = [(start, end, 0)]
    while pending:
        lo, hi, depth = pending.pop()
        j = lo
        while j < hi:
            ch = text[j]
            if ch not in _QUOTES:
                j += 1
                continue
            stop = _skip_string(text, j)
            closed = stop - 1 > j and text[stop - 1] == ch
            body_end = stop - 1 if closed else stop
            body = list(text[j + 1 : body_end])
            if ch == "`":
                k = j + 1
                while k < body_end:
                    if text.startswith("${", k):
                        close = _match_close(text, k + 1, "{", "}")
                        if close is None:
                            break
                        if depth < MAX_TEMPLATE_DEPTH:
                            pending.append((k + 2, close - 1, depth + 1))
                        for m in range(k, min(close, body_end)):
                            body[m - (j + 1)] = " "
                        k = close
                    else:
                        k += 2 if text[k] == "\\" else 1
            out.append(ClassString(j + 1, "".join(body)))
            j = stop


_CLASS_ATTR = re.compile(r"(?<![\w$.-])(?:className|class)\s*=\s*")
_CLASS_CALL = re.compile(r"(?<![\w$.])(?:cn|clsx|cva|twMerge)\s*\(")


def class_strings(text: str) -> List[ClassString]:
    found: List[ClassString] = []
    for match in _CLASS_ATTR.finditer(text):
        i = match.end()
        if i >= len(text):
            continue
        if text[i] in "\"'`":
            _literals(text, i, _skip_string(text, i), found)
        elif text[i] == "{":
            end = _match_close(text, i, "{", "}")
            if end is not None:
                _literals(text, i + 1, end - 1, found)
    for match in _CLASS_CALL.finditer(text):
        i = match.end() - 1
        end = _match_close(text, i, "(", ")")
        if end is not None:
            _literals(text, i + 1, end - 1, found)
    unique: Dict[int, ClassString] = {}
    for item in found:
        unique.setdefault(item.offset, item)
    return [unique[offset] for offset in sorted(unique)]


def split_variants(raw: str) -> Tuple[Tuple[str, ...], str]:
    """Split `md:hover:bg-red-500` into (('md', 'hover'), 'bg-red-500'), ignoring colons inside [...]."""
    parts: List[str] = []
    depth = 0
    start = 0
    for k, ch in enumerate(raw):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            parts.append(raw[start:k])
            start = k + 1
    return tuple(parts), raw[start:].strip("!")


def tokenize(item: ClassString) -> List[Token]:
    tokens = []
    for match in re.finditer(r"\S+", item.text):
        variants, base = split_variants(match.group())
        tokens.append(Token(item.offset + match.start(), variants, base))
    return tokens


_PROP = re.compile(r"([@A-Za-z_-][\w-]*)\s*:\s*(.*)\Z", re.S)


def _add_decls(segment: str, base: int, block: Block, sink: List[Decl]) -> None:
    pos = 0
    for part in segment.split(";"):
        start = base + pos
        pos += len(part) + 1
        stripped = part.lstrip(" \t\r\n`")
        if not stripped:
            continue
        offset = start + (len(part) - len(stripped))
        if stripped.startswith("@apply") and stripped[6:7].isspace():
            value = stripped[6:].strip()
            decl = Decl("@apply", value, offset, offset + stripped.find(value, 6))
        else:
            match = _PROP.match(stripped)
            if not match:
                continue
            value = match.group(2).strip()
            decl = Decl(match.group(1).lower(), value, offset, offset + match.start(2))
        block.decls.append(decl)
        sink.append(decl)


def parse_css(text: str) -> Tuple[List[Block], List[Decl]]:
    """Lenient CSS/SCSS block parser; on JS/TSX text it just yields few or odd blocks."""
    blocks: List[Block] = []
    decls: List[Decl] = []
    stack: List[Block] = []
    buffer_start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "#" and text.startswith("#{", i):
            end = _match_close(text, i + 1, "{", "}")
            i = n if end is None else end
            continue
        if ch == "{":
            prelude = text[buffer_start:i]
            cut = prelude.rfind(";")
            if cut >= 0 and stack:
                _add_decls(prelude[: cut + 1], buffer_start, stack[-1], decls)
            block = Block(prelude[cut + 1 :].strip())
            blocks.append(block)
            stack.append(block)
            buffer_start = i + 1
        elif ch == "}":
            if stack:
                _add_decls(text[buffer_start:i], buffer_start, stack[-1], decls)
                stack.pop()
            buffer_start = i + 1
        i += 1
    return blocks, decls


_TAG_OPEN = re.compile(r"<([A-Za-z][\w.:-]*)(?=[\s/>])")
_ATTR_NAME = re.compile(r"[^\s=/>{}\"'`]+")
_BARE_VALUE = re.compile(r"[^\s>]+")


def _parse_tag(text: str, match: "re.Match[str]") -> Optional[Tag]:
    n = len(text)
    i = match.end()
    stop = min(n, i + SCAN_SPAN_LIMIT)
    attrs: List[Attr] = []
    start = match.start()
    prev = text[start - 1] if start else ""
    jsx_like = not (prev and (prev.isalnum() or prev in "_$])"))
    while i < stop:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == ">":
            return Tag(match.group(1), start, i + 1, tuple(attrs), False, jsx_like)
        elif text.startswith("/>", i):
            return Tag(match.group(1), start, i + 2, tuple(attrs), True, jsx_like)
        elif ch == "/":
            i += 1
        elif ch == "{":
            end = _match_close(text, i, "{", "}")
            if end is None:
                return None
            i = end
        else:
            name = _ATTR_NAME.match(text, i)
            if not name:
                return None
            offset = i
            i = name.end()
            j = i
            while j < n and text[j].isspace():
                j += 1
            value = ""
            if j < n and text[j] == "=":
                j += 1
                while j < n and text[j].isspace():
                    j += 1
                if j >= n:
                    return None
                if text[j] in "\"'`":
                    i = _skip_string(text, j)
                elif text[j] == "{":
                    end = _match_close(text, j, "{", "}")
                    if end is None:
                        return None
                    i = end
                else:
                    bare = _BARE_VALUE.match(text, j)
                    i = bare.end() if bare else j + 1
                value = text[j:i]
            attrs.append(Attr(name.group(), offset, value))
    return None


_STRING_CONTEXT = re.compile(r"(?:[=(,:?\[{&|!+;]|=>|\b(?:return|typeof|in|of|case))\s*\Z")
_PLAIN_QUOTE = re.compile(r"[\"']")


def _plain_string_spans(text: str) -> List[Tuple[int, int]]:
    """(start, end) of single-line '...' and "..." literals written in code position.

    A quote only opens a literal after an operator or bracket, so an apostrophe in JSX text
    ("don't") never swallows the tags that follow it.
    """
    spans: List[Tuple[int, int]] = []
    pos = 0
    while True:
        match = _PLAIN_QUOTE.search(text, pos)
        if match is None:
            return spans
        i = match.start()
        if not _STRING_CONTEXT.search(text, max(0, i - 16), i):
            pos = i + 1
            continue
        quote = text[i]
        j = i + 1
        while j < len(text) and text[j] != quote and text[j] != "\n":
            j += 2 if text[j] == "\\" else 1
        if j < len(text) and text[j] == quote:
            spans.append((i, j + 1))
            pos = j + 1
        else:
            pos = i + 1


class Analysis:
    """Everything the rules need about one file, computed once."""

    def __init__(self, raw: str) -> None:
        self.text = strip_comments(raw)
        self._line_starts = [0] + [m.end() for m in re.finditer("\n", self.text)]
        self.blocks, self.decls = parse_css(self.text)
        items = class_strings(self.text)
        for decl in self.decls:
            if decl.prop == "@apply":
                items.append(ClassString(decl.value_offset, decl.value))
        self.classes: List[Tuple[ClassString, List[Token]]] = [(item, tokenize(item)) for item in items]
        spans = _plain_string_spans(self.text)
        starts = [span[0] for span in spans]

        def in_string(offset: int) -> bool:
            k = bisect.bisect_right(starts, offset) - 1
            return k >= 0 and offset < spans[k][1]

        self.tags = [
            tag
            for tag in (
                _parse_tag(self.text, m) for m in _TAG_OPEN.finditer(self.text) if not in_string(m.start())
            )
            if tag is not None
        ]

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self._line_starts, offset)

    def tokens(self) -> Iterable[Tuple[List[Token], Token]]:
        for _, toks in self.classes:
            for tok in toks:
                yield toks, tok


@lru_cache(maxsize=8)
def analyze(text: str) -> Analysis:
    return Analysis(text)


# ---------------------------------------------------------------------------
# Value helpers


def _clean_value(value: str) -> str:
    return re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.I).strip()


def _first_word(value: str) -> str:
    words = _clean_value(value).lower().split()
    return words[0] if words else ""


def _split_top_level(value: str, sep: str = ",") -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for k, ch in enumerate(value):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == sep and depth == 0:
            parts.append(value[start:k])
            start = k + 1
    parts.append(value[start:])
    return [part.strip() for part in parts if part.strip()]


_LENGTH = re.compile(r"(-?\d*\.?\d+)(px|rem|em)?")


def _px(token: str) -> Optional[float]:
    """Length token in px (rem/em count 16px); bare numbers only when zero."""
    match = _LENGTH.fullmatch(token)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2)
    if unit is None:
        return 0.0 if number == 0 else None
    return number * 16 if unit in ("rem", "em") else number


_SHADOW_TOKEN = re.compile(r"[^\s(),]+(?:\([^)]*\))?|\([^)]*\)")


class Shadow(NamedTuple):
    x: float
    y: float
    blur: float
    color: Optional[str]


def _shadow_layers(value: str) -> List[Shadow]:
    layers = []
    for layer in _split_top_level(value):
        lengths: List[float] = []
        color: Optional[str] = None
        for token in _SHADOW_TOKEN.findall(layer):
            low = token.lower()
            if low == "inset":
                continue
            px = _px(low)
            if px is not None:
                lengths.append(px)
            elif color is None:
                color = low
        if len(lengths) >= 2:
            layers.append(Shadow(lengths[0], lengths[1], lengths[2] if len(lengths) > 2 else 0.0, color))
    return layers


def _channel(raw: str) -> Optional[float]:
    try:
        return float(re.sub(r"(%|deg)$", "", raw))
    except ValueError:
        return None


def _is_chromatic(color: Optional[str]) -> bool:
    """True when color is an rgb/hsl/hex value that is not grey (named colors and var() are not judged)."""
    if not color:
        return False
    if color.startswith("#"):
        digits = color[1:]
        if not re.fullmatch(r"[0-9a-f]+", digits) or len(digits) not in (3, 4, 6, 8):
            return False
        step = 1 if len(digits) in (3, 4) else 2
        channels = {digits[k : k + step] * (2 // step) for k in range(0, 3 * step, step)}
        return len(channels) > 1
    match = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", color)
    if not match:
        return False
    parts = [p for p in re.split(r"[\s,/]+", match.group(2).strip()) if p]
    if len(parts) < 3:
        return False
    values = [_channel(p) for p in parts[:3]]
    if match.group(1).startswith("rgb"):
        return None not in values and len(set(values)) > 1
    return values[1] is not None and values[1] != 0


def _line_of_token(a: Analysis, tok: Token) -> int:
    return a.line(tok.offset)


# ---------------------------------------------------------------------------
# Rule checks. Each takes one file's text and returns (line, message) pairs.


def _check_focus_outline_removed(text: str) -> List[Hit]:
    a = analyze(text)
    hits: List[Hit] = []
    if not any(":focus-visible" in block.selector.lower() for block in a.blocks):
        for decl in a.decls:
            if decl.prop == "outline" and _first_word(decl.value) in ("none", "0", "0px"):
                hits.append((a.line(decl.offset), "outline removed with no :focus-visible rule in this file: add a visible focus style"))
    for _, toks in a.classes:
        if any("focus-visible" in tok.variants for tok in toks):
            continue
        for tok in toks:
            if tok.base == "outline-none":
                hits.append((a.line(tok.offset), "outline-none with no focus-visible: class in the same string: add a visible focus style"))
    return hits


def _check_click_on_div(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for tag in a.tags:
        if tag.name in ("div", "span"):
            click = tag.find("onClick")
            if click is not None and tag.find("role") is None:
                hits.append((a.line(click.offset), f"<{tag.name}> with onClick and no role: use a <button> or <a>, or add role, tabIndex and key handling"))
    return hits


_ZOOM = re.compile(r"user-scalable\s*=\s*[\"']?no\b|maximum-scale\s*=\s*[\"']?1(?:\.0+)?(?![\d.])", re.I)


def _check_zoom_disabled(text: str) -> List[Hit]:
    a = analyze(text)
    return [(a.line(m.start()), "pinch zoom disabled: remove user-scalable=no and maximum-scale=1") for m in _ZOOM.finditer(a.text)]


def _check_img_no_alt(text: str) -> List[Hit]:
    a = analyze(text)
    return [
        (a.line(tag.start), "<img> has no alt attribute: describe the image, or use alt=\"\" when it is decorative")
        for tag in a.tags
        if tag.name == "img" and tag.find("alt") is None
    ]


def _check_positive_tabindex(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for tag in a.tags:
        attr = tag.find("tabindex")
        if attr is None:
            continue
        match = re.match(r"=?\s*\{?\s*[\"']?(-?\d+)", attr.value)
        if match and int(match.group(1)) > 0:
            hits.append((a.line(attr.offset), "positive tabIndex breaks the natural focus order: use 0 or -1"))
    return hits


def _check_placeholder_as_label(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for tag in a.tags:
        if tag.name not in ("input", "textarea"):
            continue
        placeholder = tag.find("placeholder")
        if placeholder is None:
            continue
        if any(tag.find(name) is not None for name in ("aria-label", "aria-labelledby", "id")):
            continue
        hits.append((a.line(placeholder.offset), f"<{tag.name}> labelled only by its placeholder: add a <label>, aria-label or aria-labelledby"))
    return hits


_ON_PASTE = re.compile(r"\bonPaste\s*=")


def _check_paste_blocked(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for match in _ON_PASTE.finditer(a.text):
        i = match.end()
        while i < len(a.text) and a.text[i].isspace():
            i += 1
        if i >= len(a.text) or a.text[i] not in "{\"'`":
            continue
        end = _match_close(a.text, i, "{", "}") if a.text[i] == "{" else _skip_string(a.text, i)
        if end is not None and "preventDefault" in a.text[i:end]:
            hits.append((a.line(match.start()), "onPaste handler calls preventDefault: let people paste"))
    return hits


def _check_autofocus(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for tag in a.tags:
        attr = tag.find("autofocus")
        if attr is not None:
            hits.append((a.line(attr.offset), "autoFocus moves focus without being asked: keep it only where the screen has one obvious first input"))
    return hits


def _check_transition_all(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        if decl.prop not in ("transition", "transition-property"):
            continue
        for layer in _split_top_level(_clean_value(decl.value)):
            if "all" in layer.lower().split():
                hits.append((a.line(decl.offset), f"{decl.prop}: all animates every property: list the properties that change"))
                break
    for _, tok in a.tokens():
        if tok.base == "transition-all":
            hits.append((a.line(tok.offset), "transition-all animates every property: use transition-colors, transition-opacity or transition-transform"))
    return hits


_LAYOUT_PROP = re.compile(
    r"(?<![\w-])(?:(?:min-|max-)?(?:width|height)|top|left|right|bottom|margin(?:-[a-z]+)*|padding(?:-[a-z]+)*)(?![\w-])",
    re.I,
)
_LAYOUT_MESSAGE = "animating a layout property reflows the page: animate transform or opacity instead"


def _check_layout_property(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        if decl.prop in ("transition", "transition-property", "animation", "animation-name") and _LAYOUT_PROP.search(decl.value):
            hits.append((a.line(decl.offset), _LAYOUT_MESSAGE))
    for _, tok in a.tokens():
        if tok.base.startswith("transition-[") and tok.base.endswith("]"):
            if _LAYOUT_PROP.search(tok.base[len("transition-[") : -1].replace("_", " ").replace(",", " ")):
                hits.append((a.line(tok.offset), _LAYOUT_MESSAGE))
    return hits


_MOTION_START = re.compile(r"@(?:-\w+-)?keyframes\b|(?<![\w-])animation\s*:", re.I)


def _check_no_reduced_motion(text: str) -> List[Hit]:
    a = analyze(text)
    match = _MOTION_START.search(a.text)
    if match and "prefers-reduced-motion" not in a.text.lower():
        return [(a.line(match.start()), "animation with no prefers-reduced-motion handling: add a reduce override")]
    return []


_FONT_SIZE = re.compile(r"(\d*\.?\d+)(px|rem|em)")
_TEXT_PX = re.compile(r"text-\[(\d*\.?\d+)px\]")


def _check_tiny_text(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        if decl.prop != "font-size":
            continue
        match = _FONT_SIZE.fullmatch(_clean_value(decl.value).lower())
        if not match:
            continue
        size = float(match.group(1))
        limit = 12.0 if match.group(2) == "px" else 0.75
        if 0 < size < limit:
            hits.append((a.line(decl.offset), f"font-size {_clean_value(decl.value)} is under 12px: raise it to at least 12px"))
    for _, tok in a.tokens():
        match = _TEXT_PX.fullmatch(tok.base)
        if match and 0 < float(match.group(1)) < 12:
            hits.append((a.line(tok.offset), f"{tok.base} is under 12px: raise it to at least 12px"))
    return hits


def _check_justified(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        if decl.prop == "text-align" and _first_word(decl.value) == "justify":
            hits.append((a.line(decl.offset), "justified text opens uneven word gaps: align left"))
    for _, tok in a.tokens():
        if tok.base == "text-justify":
            hits.append((a.line(tok.offset), "justified text opens uneven word gaps: align left"))
    return hits


_ELLIPSIS_STRING = re.compile(r"""(?<![\w$])(?P<q>["'`])(?:\\.|(?!(?P=q))[^\\\n])*?\.\.\.(?P=q)""")
_DOTS_MESSAGE = "three dots in user-facing text: use the ellipsis character …"
_VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)
_FRAGMENT_OPEN = re.compile(r"<>")
_CLOSING_TAG = re.compile(r"</[\w.:-]*\s*>")


def _jsx_text_dots(a: Analysis, start: int, by_start: Dict[int, Tag]) -> Optional[List[int]]:
    """Lines of `...` in the text children of the JSX element whose content begins at `start`.

    Expressions in `{}` are skipped and nested elements followed; the walk ends at the matching
    close tag. None when the element never closes, so JS after it is not mistaken for text.
    """
    text = a.text
    stop = min(len(text), start + SCAN_SPAN_LIMIT)
    found: List[int] = []
    depth = 1
    pos = start
    while pos < stop:
        ch = text[pos]
        if ch == "{":
            end = _match_close(text, pos, "{", "}")
            if end is None:
                return None
            pos = end
        elif ch == "<":
            child = by_start.get(pos)
            closing = _CLOSING_TAG.match(text, pos)
            if child is not None:
                pos = child.end
                if not (child.self_closing or child.name in _VOID_ELEMENTS):
                    depth += 1
            elif closing is not None:
                pos = closing.end()
                depth -= 1
                if depth == 0:
                    return found
            elif text.startswith("<>", pos):
                pos += 2
                depth += 1
            else:
                return None
        elif text.startswith("...", pos):
            found.append(a.line(pos))
            pos += 3
        else:
            pos += 1
    return None


def _check_three_dots(text: str) -> List[Hit]:
    a = analyze(text)
    lines: Set[int] = set()
    for match in _ELLIPSIS_STRING.finditer(a.text):
        lines.add(a.line(match.end() - 4))
    by_start = {tag.start: tag for tag in a.tags}
    roots = [
        tag.end
        for tag in a.tags
        if tag.jsx_like and not tag.self_closing and tag.name not in _VOID_ELEMENTS
    ]
    roots += [m.end() for m in _FRAGMENT_OPEN.finditer(a.text)]
    for root in roots:
        lines.update(_jsx_text_dots(a, root, by_start) or [])
    return [(line, _DOTS_MESSAGE) for line in sorted(lines)]


_Z_ARBITRARY = re.compile(r"z-\[(\d+)\]")


def _check_z_index(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        value = _clean_value(decl.value)
        if decl.prop == "z-index" and re.fullmatch(r"\d+", value) and int(value) >= 999:
            hits.append((a.line(decl.offset), f"z-index {value}: use a named layer scale instead of escalating"))
    for _, tok in a.tokens():
        match = _Z_ARBITRARY.fullmatch(tok.base)
        if match and int(match.group(1)) >= 999:
            hits.append((a.line(tok.offset), f"{tok.base}: use a named layer scale instead of escalating"))
    return hits


def _check_gradient_text(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for block in a.blocks:
        clips = [d for d in block.decls if d.prop in ("background-clip", "-webkit-background-clip") and _first_word(d.value) == "text"]
        gradient = any(d.prop in ("background", "background-image") and "gradient(" in d.value.lower() for d in block.decls)
        if clips and gradient:
            hits.append((a.line(clips[0].offset), "gradient-filled text: use a solid text color"))
    for _, toks in a.classes:
        clip = next((t for t in toks if t.base == "bg-clip-text"), None)
        if clip is not None and any(re.match(r"bg-(?:gradient|linear)-", t.base) for t in toks):
            hits.append((a.line(clip.offset), "gradient-filled text: use a solid text color"))
    return hits


def _arbitrary_shadow(base: str) -> Optional[str]:
    if base.startswith("shadow-[") and base.endswith("]"):
        return base[len("shadow-[") : -1].replace("_", " ")
    return None


def _shadow_values(a: Analysis) -> Iterable[Tuple[int, List[Shadow]]]:
    for decl in a.decls:
        if decl.prop == "box-shadow":
            yield a.line(decl.offset), _shadow_layers(_clean_value(decl.value))
    for _, tok in a.tokens():
        value = _arbitrary_shadow(tok.base)
        if value is not None:
            yield a.line(tok.offset), _shadow_layers(value)


def _check_hard_offset_shadow(text: str) -> List[Hit]:
    a = analyze(text)
    return [
        (line, "hard offset shadow: use a soft elevation shadow or a border")
        for line, layers in _shadow_values(a)
        if any(s.x != 0 and s.y != 0 and s.blur == 0 for s in layers)
    ]


def _check_glow_shadow(text: str) -> List[Hit]:
    a = analyze(text)
    return [
        (line, "colored glow shadow: use a neutral elevation shadow")
        for line, layers in _shadow_values(a)
        if any(s.x == 0 and s.y == 0 and s.blur >= 16 and _is_chromatic(s.color) for s in layers)
    ]


_STRIPE_MESSAGE = "colored side stripe on a rounded block: justify or change"
_BORDER_L_SCALE = re.compile(r"border-l-([2-8])")
_BORDER_L_ARBITRARY = re.compile(r"border-l-\[(\d+(?:\.\d+)?)px\]")


def _check_side_stripe(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for block in a.blocks:
        if not any(d.prop == "border-radius" for d in block.decls):
            continue
        for decl in block.decls:
            if decl.prop != "border-left":
                continue
            words = _clean_value(decl.value).lower().split()
            widths = [_px(w) for w in words if w.endswith("px")]
            if "solid" in words and any(w is not None and 2 <= w <= 8 for w in widths):
                hits.append((a.line(decl.offset), _STRIPE_MESSAGE))
    for _, toks in a.classes:
        if not any(t.base.startswith("rounded") for t in toks):
            continue
        for tok in toks:
            scale = _BORDER_L_SCALE.fullmatch(tok.base)
            arbitrary = _BORDER_L_ARBITRARY.fullmatch(tok.base)
            if scale or (arbitrary and 2 <= float(arbitrary.group(1)) <= 8):
                hits.append((a.line(tok.offset), _STRIPE_MESSAGE))
    return hits


OVERUSED_FONTS = ("inter", "geist", "roboto", "arial")
_FONT_ARBITRARY = re.compile(r"font-\[(.+)\]")


def _first_family(value: str) -> str:
    families = _split_top_level(value)
    return families[0].strip().strip("\"'").strip().lower() if families else ""


def _check_overused_font(text: str) -> List[Hit]:
    a = analyze(text)
    hits = []
    for decl in a.decls:
        if decl.prop == "font-family":
            family = _first_family(_clean_value(decl.value))
            if family in OVERUSED_FONTS:
                hits.append((a.line(decl.offset), f"{family.title()} as the first font family: justify or change"))
    for _, tok in a.tokens():
        match = _FONT_ARBITRARY.fullmatch(tok.base)
        if match:
            content = match.group(1)
            if content.startswith("family-name:"):
                content = content[len("family-name:") :]
            family = _first_family(content.replace("_", " "))
            if family in OVERUSED_FONTS:
                hits.append((a.line(tok.offset), f"{family.title()} as the first font family: justify or change"))
    return hits


RULES: Sequence[Rule] = (
    Rule("focus-outline-removed", "P0", "Focus outline removed without a replacement", _check_focus_outline_removed),
    Rule("a11y-click-on-div", "P0", "Click handler on a div or span without a role", _check_click_on_div),
    Rule("a11y-zoom-disabled", "P0", "Pinch zoom disabled", _check_zoom_disabled),
    Rule("a11y-img-no-alt", "P1", "Image without alt text", _check_img_no_alt),
    Rule("a11y-positive-tabindex", "P1", "Positive tabindex", _check_positive_tabindex),
    Rule("forms-placeholder-as-label", "P1", "Placeholder used as the only label", _check_placeholder_as_label),
    Rule("forms-paste-blocked", "P1", "Paste blocked on an input", _check_paste_blocked),
    Rule("a11y-autofocus", "P2", "Autofocus attribute", _check_autofocus),
    Rule("motion-transition-all", "P2", "transition: all", _check_transition_all),
    Rule("motion-layout-property", "P2", "Transition or animation on a layout property", _check_layout_property),
    Rule("motion-no-reduced-motion", "P2", "Animation without prefers-reduced-motion handling", _check_no_reduced_motion, file_level=True),
    Rule("type-tiny-text", "P2", "Font size below 12px", _check_tiny_text),
    Rule("type-justified", "P3", "Justified text", _check_justified),
    Rule("content-three-dots", "P3", "Three dots instead of the ellipsis character", _check_three_dots),
    Rule("layout-z-index-escalation", "P3", "z-index of 999 or more", _check_z_index),
    Rule("slop-gradient-text", "P3", "Gradient-filled text", _check_gradient_text),
    Rule("slop-hard-offset-shadow", "P3", "Hard offset shadow", _check_hard_offset_shadow),
    Rule("slop-glow-shadow", "P3", "Colored glow shadow", _check_glow_shadow),
    Rule("intent-side-stripe", "P3", "Colored side stripe on a rounded block (check intent)", _check_side_stripe),
    Rule("intent-overused-font", "P3", "Inter, Geist, Roboto or Arial as the first family (check intent)", _check_overused_font),
)


# ---------------------------------------------------------------------------
# Scanning


def scan_text(text: str) -> List[Tuple[Rule, int, str]]:
    """Run every rule over one file's text; one result per rule and line, sorted by line then rule id."""
    results: Dict[Tuple[str, int], Tuple[Rule, int, str]] = {}
    for rule in RULES:
        for line, message in rule.check(text):
            results.setdefault((rule.id, line), (rule, line, message))
    return sorted(results.values(), key=lambda item: (item[1], item[0].id))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def scan_file(path: Path) -> List[Tuple[str, int, str]]:
    """(rule id, line, message) triples for one file."""
    return [(rule.id, line, message) for rule, line, message in scan_text(_read(Path(path)))]


def _raise(error: OSError) -> None:
    raise error


def collect_files(paths: Sequence[str]) -> List[Path]:
    """Expand PATH arguments into scannable files; raises OSError for a path that is missing or unreadable."""
    files: List[Path] = []
    seen: Set[str] = set()

    def add(candidate: Path) -> None:
        key = os.path.realpath(candidate)
        if candidate.suffix.lower() in SCANNED_SUFFIXES and key not in seen:
            seen.add(key)
            files.append(candidate)

    for raw in paths:
        root = Path(raw)
        if root.is_dir():
            for current, dirs, names in os.walk(root, onerror=_raise):
                dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
                for name in sorted(names):
                    add(Path(current) / name)
        elif root.is_file():
            add(root)
        else:
            raise OSError(f"{raw}: no such file or directory")
    return files


def display_path(path: Path) -> str:
    """Relative to the current directory when under it, else absolute."""
    cwd = Path(os.getcwd())
    for candidate, base in ((Path(os.path.abspath(path)), cwd), (path.resolve(), cwd.resolve())):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    return os.path.abspath(path)


# ---------------------------------------------------------------------------
# Git


def _git(args: Sequence[str], cwd: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc


def verify_ref(ref: str) -> None:
    if ref.startswith("-"):
        raise GitError(f"invalid git ref: {ref}")
    inside = _git(["rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0:
        raise GitError("--changed-since needs a git repository: run from inside the repo")
    found = _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if found.returncode != 0:
        raise GitError(f"unknown git ref: {ref}")


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)


def changed_lines(path: Path, ref: str) -> Optional[Set[int]]:
    """Lines added or modified since ref; None means the whole file counts (untracked)."""
    directory = os.path.dirname(os.path.abspath(path))
    name = os.path.basename(path)
    tracked = _git(["ls-files", "--error-unmatch", "--", name], cwd=directory)
    if tracked.returncode == 1:
        return None
    if tracked.returncode != 0:
        raise GitError(f"{path}: not inside a git repository")
    diff = _git(["diff", "-U0", "--no-color", "--no-ext-diff", ref, "--", name], cwd=directory)
    if diff.returncode != 0:
        raise GitError(f"git diff failed for {path}: {diff.stderr.strip()}")
    lines: Set[int] = set()
    for match in _HUNK.finditer(diff.stdout):
        start = int(match.group(1))
        count = 1 if match.group(2) is None else int(match.group(2))
        lines.update(range(start, start + count))
    return lines


# ---------------------------------------------------------------------------
# CLI


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detect.py",
        description="Flag regex-checkable UI rule candidates in CSS, SCSS, JSX and TSX files.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--changed-since", metavar="GIT_REF", help="keep only findings on lines added or modified since GIT_REF")
    parser.add_argument("--list-rules", action="store_true", help="print every rule id, severity and title, then exit")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    return parser


def run(paths: Sequence[str], changed_since: Optional[str]) -> Tuple[List[Finding], int]:
    files = collect_files(paths)
    if changed_since is not None:
        verify_ref(changed_since)
    findings: List[Finding] = []
    for path in files:
        results = scan_text(_read(path))
        changed = changed_lines(path, changed_since) if changed_since is not None else None
        shown = display_path(path)
        for rule, line, message in results:
            if changed is not None:
                keep = bool(changed) if rule.file_level else line in changed
                if not keep:
                    continue
            findings.append(Finding(shown, line, rule.id, rule.severity, message))
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    return findings, len(files)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        for rule in RULES:
            print(f"{rule.id}  {rule.severity}  {rule.title}")
        return 0
    if not args.paths:
        parser.error("at least one PATH is required")
    try:
        findings, scanned = run(args.paths, args.changed_since)
    except (OSError, GitError) as exc:
        print(f"detect.py: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        payload = {
            "findings": [
                {"path": f.path, "line": f.line, "rule": f.rule, "severity": f.severity, "message": f.message}
                for f in findings
            ],
            "scanned": scanned,
        }
        print(json.dumps(payload, indent=2))
    else:
        for f in findings:
            print(f"{f.path}:{f.line}  {f.rule}  {f.severity}  {f.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
