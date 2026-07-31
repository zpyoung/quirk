"""YAML parsing for filing-requests: PyYAML when importable, a bounded subset otherwise.

No CLI surface. `parse_yaml(text, path)` is the one entry point every caller uses; the tier
is resolved once at import time (`YAML_TIER`) so no caller has to know which one served it.
`parse(text, path)` is the bounded subset itself (Tier 2), exposed directly so it can be
tested without a PyYAML install on the machine shadowing it.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

YAML_TIER = "pyyaml" if _yaml is not None else "mini"


class TemplateParseError(Exception):
    """Raised by either parsing tier on input it cannot handle -- the one failure mode
    both `parse_yaml` and `parse` share, naming the file and line that caused it.
    """

    def __init__(self, message: str, path: str, line: int):
        self.message = message
        self.path = path
        self.line = line
        super().__init__(f"{path}:{line}: {message}")


def parse_yaml(text: str, path: str = "<string>") -> Any:
    """Parse `text` as YAML, preferring PyYAML and falling back to `parse` (below)."""
    if YAML_TIER == "pyyaml":
        try:
            return _yaml.safe_load(text)
        except _yaml.YAMLError as exc:
            line = 1
            mark = getattr(exc, "problem_mark", None)
            if mark is not None:
                line = mark.line + 1
            reason = str(exc).splitlines()[0] if str(exc) else "invalid YAML"
            raise TemplateParseError(reason, path, line) from exc
        except RecursionError as exc:
            # a deeply nested template is one bad file, not a reason to abort discovery for
            # the rest of the repo -- both tiers surface it as the same per-file failure
            raise TemplateParseError("nesting is too deep to parse", path, 1) from exc
    return parse(text, path)


# ---- Tier 2: the bounded subset -----------------------------------------------------
#
# Supported: block mappings (nested via indentation), block sequences (including
# `- key: value` list items), plain/single/double-quoted scalars, booleans, `|`/`>`
# block scalars, `#` comments, and flow sequences whose items are all scalars
# (`[a, "b", c]`, including the empty `[]`). Not supported: flow mappings, flow
# sequences containing a nested collection, anchors/aliases, multi-document
# separators, tags, merge keys -- each raises TemplateParseError.

_BLOCK_SCALAR_INDICATORS = ("|", ">", "|-", "|+", ">-", ">+")
_BOOL_TRUE = ("true", "True", "TRUE")
_BOOL_FALSE = ("false", "False", "FALSE")
_NULL = ("null", "Null", "NULL", "~")

# Nesting is bounded so a pathological template fails as this module's own per-file error
# rather than as a RecursionError escaping into the caller's discovery loop. Real issue
# templates nest three or four levels; 64 is far past anything legitimate.
_MAX_DEPTH = 64


def parse(text: str, path: str = "<string>") -> Any:
    """Parse `text` against the bounded YAML subset described above.

    Raises TemplateParseError naming `path` and the offending line for anything outside
    that subset.
    """
    cur = _Cursor(text.splitlines())
    try:
        node = _parse_node(cur, 0, path, 0)
    except RecursionError as exc:  # pragma: no cover - _MAX_DEPTH fires first
        raise TemplateParseError("nesting is too deep to parse", path, 1) from exc
    leftover = cur.peek_logical()
    if leftover is not None:
        j, _indent, content = leftover
        raise TemplateParseError(f"unexpected content: {content!r}", path, j + 1)
    return node


class _Cursor:
    """A one-directional walk over `raw` lines that skips blank and comment-only ones."""

    def __init__(self, raw: List[str]):
        self.raw = raw
        self.n = len(raw)
        self.i = 0

    def peek_logical(self) -> Optional[Tuple[int, int, str]]:
        """Return (line_index, indent, content) of the next real line, without consuming it."""
        j = self.i
        while j < self.n:
            stripped = _strip_comment(self.raw[j])
            if stripped.strip() == "":
                j += 1
                continue
            indent = len(stripped) - len(stripped.lstrip(" "))
            return (j, indent, stripped.strip())
        return None

    def advance_to(self, j: int) -> None:
        self.i = j + 1


def _strip_comment(line: str) -> str:
    """Cut `line` at the first unquoted `#` preceded by whitespace or the line start."""
    in_single = in_double = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if in_single:
            if ch == "'":
                if i + 1 < n and line[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
        i += 1
    return line


def _find_colon(content: str) -> Optional[int]:
    """Find the first unquoted `:` that separates a mapping key from its value."""
    in_single = in_double = False
    i, n = 0, len(content)
    while i < n:
        ch = content[i]
        if in_single:
            if ch == "'":
                if i + 1 < n and content[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch == ":" and (i + 1 == n or content[i + 1] == " "):
            return i
        i += 1
    return None


def _reject_doc_markers(content: str, path: str, lineno: int) -> None:
    if content in ("---", "..."):
        raise TemplateParseError("multi-document separators are not supported", path, lineno)
    if content.startswith("%"):
        raise TemplateParseError("YAML directives are not supported", path, lineno)


def _check_depth(depth: int, path: str, lineno: int) -> None:
    if depth > _MAX_DEPTH:
        raise TemplateParseError(
            f"nesting deeper than {_MAX_DEPTH} levels is not supported", path, lineno
        )


def _parse_node(cur: _Cursor, min_indent: int, path: str, depth: int) -> Any:
    peek = cur.peek_logical()
    if peek is None:
        return None
    j, indent, content = peek
    if indent < min_indent:
        return None
    _check_depth(depth, path, j + 1)
    _reject_doc_markers(content, path, j + 1)
    if content[0] == "{":
        raise TemplateParseError(f"flow mappings are not supported: {content!r}", path, j + 1)
    if content[0] == "[":
        cur.advance_to(j)
        return _parse_flow_sequence(content, path, j + 1)
    if content == "-" or content.startswith("- "):
        return _parse_sequence(cur, indent, path, depth)
    if _find_colon(content) is not None:
        return _parse_mapping(cur, indent, path, depth)
    cur.advance_to(j)
    return _parse_scalar(content, path, j + 1)


def _split_key(content: str, path: str, lineno: int) -> Tuple[str, str]:
    idx = _find_colon(content)
    if idx is None:
        raise TemplateParseError(f"expected 'key: value', got {content!r}", path, lineno)
    key = content[:idx].strip()
    if key == "<<":
        raise TemplateParseError("merge keys are not supported", path, lineno)
    if key == "":
        raise TemplateParseError(f"expected 'key: value', got {content!r}", path, lineno)
    return key, content[idx + 1 :].strip()


def _consume_value(
    cur: _Cursor, key_indent: int, value_part: str, path: str, lineno: int, depth: int
) -> Any:
    """Given the text after a mapping key's `:`, return its value, consuming any nested
    lines it owns (a block scalar body, or a mapping/sequence indented under an empty value).
    """
    if value_part == "":
        nxt = cur.peek_logical()
        if nxt is not None and nxt[1] > key_indent:
            return _parse_node(cur, nxt[1], path, depth + 1)
        return None
    if value_part in _BLOCK_SCALAR_INDICATORS:
        return _parse_block_scalar(cur, value_part, key_indent, path, lineno)
    return _parse_scalar(value_part, path, lineno)


def _parse_mapping(cur: _Cursor, indent: int, path: str, depth: int) -> dict:
    result: dict = {}
    while True:
        peek = cur.peek_logical()
        if peek is None:
            break
        j, cur_indent, content = peek
        if cur_indent != indent:
            break
        if content == "-" or content.startswith("- "):
            raise TemplateParseError("expected a mapping key, found a sequence item", path, j + 1)
        _reject_doc_markers(content, path, j + 1)
        key, value_part = _split_key(content, path, j + 1)
        cur.advance_to(j)
        result[key] = _consume_value(cur, indent, value_part, path, j + 1, depth)
    return result


def _parse_sequence(cur: _Cursor, indent: int, path: str, depth: int) -> list:
    items: list = []
    while True:
        peek = cur.peek_logical()
        if peek is None:
            break
        j, cur_indent, content = peek
        if cur_indent != indent:
            break
        if not (content == "-" or content.startswith("- ")):
            break
        cur.advance_to(j)
        after_dash = content[1:]
        rest = after_dash.lstrip(" ")
        if rest == "":
            nxt = cur.peek_logical()
            if nxt is not None and nxt[1] > indent:
                items.append(_parse_node(cur, nxt[1], path, depth + 1))
            else:
                items.append(None)
            continue
        item_col = indent + 1 + (len(after_dash) - len(rest))
        if rest in _BLOCK_SCALAR_INDICATORS:
            items.append(_parse_block_scalar(cur, rest, indent, path, j + 1))
            continue
        if rest[0] == "{":
            raise TemplateParseError(f"flow mappings are not supported: {rest!r}", path, j + 1)
        if rest[0] == "[":
            items.append(_parse_flow_sequence(rest, path, j + 1))
            continue
        if _find_colon(rest) is None:
            items.append(_parse_scalar(rest, path, j + 1))
            continue
        _check_depth(depth, path, j + 1)
        key, value_part = _split_key(rest, path, j + 1)
        mapping = {key: _consume_value(cur, item_col, value_part, path, j + 1, depth + 1)}
        while True:
            sibling = cur.peek_logical()
            if sibling is None:
                break
            j2, indent2, content2 = sibling
            if indent2 != item_col:
                break
            if content2 == "-" or content2.startswith("- "):
                raise TemplateParseError(
                    "expected a mapping key, found a sequence item", path, j2 + 1
                )
            _reject_doc_markers(content2, path, j2 + 1)
            key2, value_part2 = _split_key(content2, path, j2 + 1)
            cur.advance_to(j2)
            mapping[key2] = _consume_value(cur, item_col, value_part2, path, j2 + 1, depth + 1)
        items.append(mapping)
    return items


def _parse_block_scalar(cur: _Cursor, indicator: str, indent: int, path: str, lineno: int) -> str:
    style = indicator[0]
    lines: List[str] = []
    block_indent: Optional[int] = None
    while cur.i < cur.n:
        raw = cur.raw[cur.i]
        if raw.strip() == "":
            lines.append("")
            cur.i += 1
            continue
        line_indent = len(raw) - len(raw.lstrip(" "))
        if block_indent is None:
            if line_indent <= indent:
                break
            block_indent = line_indent
        elif line_indent < block_indent:
            break
        lines.append(raw[block_indent:])
        cur.i += 1
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ""
    body = "\n".join(lines) if style == "|" else _fold(lines)
    return body + "\n"


def _fold(lines: List[str]) -> str:
    out: List[str] = []
    blank_run = 0
    started = False
    for line in lines:
        if line == "":
            blank_run += 1
            continue
        if started:
            out.append("\n" * blank_run if blank_run else " ")
        out.append(line)
        started = True
        blank_run = 0
    return "".join(out)


def _parse_flow_sequence(content: str, path: str, lineno: int) -> list:
    """Parse a bracketed flow sequence of scalar items -- `[a, "b", c]`, including the
    empty `[]` -- tolerating surrounding whitespace and a trailing comma. Raises
    TemplateParseError if an item is itself a collection (`[[a], b]`, `[{k: v}]`).
    """
    if not content.endswith("]"):
        raise TemplateParseError(f"unterminated flow sequence: {content!r}", path, lineno)
    inner = content[1:-1].strip()
    if inner == "":
        return []
    raw_items = _split_flow_items(inner)
    if raw_items and raw_items[-1].strip() == "":
        raw_items.pop()
    items = []
    for raw_item in raw_items:
        item = raw_item.strip()
        if item == "" or item[0] in "{[":
            raise TemplateParseError(
                f"flow sequences may only contain scalar items: {content!r}", path, lineno
            )
        items.append(_parse_scalar(item, path, lineno))
    return items


def _split_flow_items(inner: str) -> List[str]:
    """Split a flow sequence's inner text on top-level commas, honoring quotes and
    nested brackets so a rejected nested collection stays intact as one item.
    """
    items: List[str] = []
    depth = 0
    in_single = in_double = False
    start = 0
    i, n = 0, len(inner)
    while i < n:
        ch = inner[i]
        if in_single:
            if ch == "'":
                if i + 1 < n and inner[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(inner[start:i])
            start = i + 1
        i += 1
    items.append(inner[start:])
    return items


def _parse_scalar(raw: str, path: str, lineno: int) -> Any:
    raw = raw.strip()
    first = raw[0]
    if first == '"':
        return _parse_double_quoted(raw, path, lineno)
    if first == "'":
        return _parse_single_quoted(raw, path, lineno)
    if first == "{":
        raise TemplateParseError(f"flow mappings are not supported: {raw!r}", path, lineno)
    if first == "[":
        return _parse_flow_sequence(raw, path, lineno)
    if first in "&*":
        raise TemplateParseError(f"anchors and aliases are not supported: {raw!r}", path, lineno)
    if first == "!":
        raise TemplateParseError(f"tags are not supported: {raw!r}", path, lineno)
    if raw in ("---", "..."):
        raise TemplateParseError("multi-document separators are not supported", path, lineno)
    if raw in _BOOL_TRUE:
        return True
    if raw in _BOOL_FALSE:
        return False
    if raw in _NULL:
        return None
    return raw


# The full YAML double-quoted escape table. A shorter table that silently drops the backslash
# from anything it doesn't know makes this tier disagree with PyYAML about the *content* of a
# template ID or field name -- the one thing the two tiers must never do.
_DOUBLE_ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v",
    "f": "\f", "r": "\r", "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\",
    "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029",
}
# escape -> number of hex digits that follow it
_DOUBLE_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def _parse_double_quoted(raw: str, path: str, lineno: int) -> str:
    if len(raw) < 2 or raw[-1] != '"':
        raise TemplateParseError(f"unterminated double-quoted scalar: {raw!r}", path, lineno)
    body = raw[1:-1]
    out: List[str] = []
    i, n = 0, len(body)
    while i < n:
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            raise TemplateParseError(
                f"trailing backslash in double-quoted scalar: {raw!r}", path, lineno
            )
        esc = body[i + 1]
        width = _DOUBLE_HEX_ESCAPES.get(esc)
        if width is not None:
            digits = body[i + 2 : i + 2 + width]
            if len(digits) != width or any(c not in "0123456789abcdefABCDEF" for c in digits):
                raise TemplateParseError(
                    rf"expected {width} hex digits after \{esc} in {raw!r}", path, lineno
                )
            out.append(chr(int(digits, 16)))
            i += 2 + width
            continue
        if esc not in _DOUBLE_ESCAPES:
            raise TemplateParseError(
                rf"unknown escape \{esc} in double-quoted scalar: {raw!r}", path, lineno
            )
        out.append(_DOUBLE_ESCAPES[esc])
        i += 2
    return "".join(out)


def _parse_single_quoted(raw: str, path: str, lineno: int) -> str:
    if len(raw) < 2 or raw[-1] != "'":
        raise TemplateParseError(f"unterminated single-quoted scalar: {raw!r}", path, lineno)
    return raw[1:-1].replace("''", "'")
