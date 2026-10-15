#!/usr/bin/env python3
"""Small, safe Markdown renderer for the combined-review report."""

import html
import itertools

import highlight
import re


_ESCAPABLE = "\\`*_[]()|"
_ABSOLUTE_DEST = re.compile(r"^(?:https?|mailto):[^\s]*$", re.IGNORECASE)
_RELATIVE_DEST = re.compile(r"^(?!//)(?!\\)[^\s:]*(?:[/?#][^\s]*)?$")
_CONTROL_DEST = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")
_FENCE = re.compile(r"^```\s*(?P<info>[^\s`]+)?\s*$")
_UL_ITEM = re.compile(r"^[-*] (.*)$")
_OL_ITEM = re.compile(r"^\d+\. (.*)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _text(tokens, value):
    if not value:
        return
    if tokens and tokens[-1][0] == "TEXT":
        tokens[-1] = ("TEXT", tokens[-1][1] + value)
    else:
        tokens.append(("TEXT", value))


def _backtick_run(text, pos):
    end = pos
    while end < len(text) and text[end] == "`":
        end += 1
    return end - pos


def _star_run(text, pos):
    end = pos
    while end < len(text) and text[end] == "*":
        end += 1
    return end - pos


def _find_code_close(text, pos, width):
    needle = "`" * width
    while True:
        found = text.find(needle, pos)
        if found < 0:
            return -1
        if _backtick_run(text, found) == width:
            return found
        pos = found + _backtick_run(text, found)


def _valid_destination(dest):
    if _CONTROL_DEST.search(dest):
        return None
    stripped = dest.strip()
    if "\\" in stripped:
        return None
    if _ABSOLUTE_DEST.match(stripped) or _RELATIVE_DEST.match(stripped):
        return stripped
    return None


def _link_parts(text, pos):
    if pos >= len(text) or text[pos] != "[":
        return None
    i = pos + 1
    depth = 0
    label_end = None
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in _ESCAPABLE:
            i += 2
            continue
        if ch == "`":
            width = _backtick_run(text, i)
            close = _find_code_close(text, i + width, width)
            i = close + width if close >= 0 else i + width
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            if depth:
                depth -= 1
            else:
                label_end = i
                break
        i += 1
    if label_end is None or label_end + 1 >= len(text) or text[label_end + 1] != "(":
        return None
    i = label_end + 2
    dest_start = i
    parens = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            parens += 1
        elif ch == ")":
            if not parens:
                return text[pos + 1:label_end], text[dest_start:i], i + 1
            parens -= 1
        i += 1
    return None


def _at_close(text, pos, closing):
    if closing == "**":
        return text.startswith("**", pos)
    if closing == "*":
        return text.startswith("*", pos) and _star_run(text, pos) % 2 == 1
    return False


def _tokenize(text, pos=0, closing=None):
    tokens = []
    while pos < len(text):
        if closing and _at_close(text, pos, closing):
            return tokens, pos + len(closing), True

        ch = text[pos]
        if ch == "\\" and pos + 1 < len(text) and text[pos + 1] in _ESCAPABLE:
            _text(tokens, text[pos + 1])
            pos += 2
            continue

        if ch == "`":
            width = _backtick_run(text, pos)
            close = _find_code_close(text, pos + width, width)
            if close >= 0:
                tokens.append(("CODE", text[pos + width:close]))
                pos = close + width
            else:
                _text(tokens, text[pos:pos + width])
                pos += width
            continue

        if ch == "!" and pos + 1 < len(text) and text[pos + 1] == "[":
            image = _link_parts(text, pos + 1)
            if image:
                _text(tokens, text[pos:image[2]])
                pos = image[2]
                continue

        if ch == "[":
            link = _link_parts(text, pos)
            if link:
                label, raw_dest, end = link
                dest = _valid_destination(raw_dest)
                if dest is not None:
                    tokens.append(("LINK", tokenize_inline(label), dest))
                else:
                    _text(tokens, text[pos:end])
                pos = end
                continue

        if text.startswith("**", pos):
            children, end, closed = _tokenize(text, pos + 2, "**")
            if closed:
                tokens.append(("STRONG", children))
                pos = end
            else:
                _text(tokens, "**")
                pos += 2
            continue

        if ch == "*" and not text.startswith("**", pos):
            children, end, closed = _tokenize(text, pos + 1, "*")
            if closed:
                tokens.append(("EM", children))
                pos = end
            else:
                _text(tokens, "*")
                pos += 1
            continue

        start = pos
        while pos < len(text):
            if closing and _at_close(text, pos, closing):
                break
            if text[pos] in "\\`[*" or (text[pos] == "!" and pos + 1 < len(text) and text[pos + 1] == "["):
                break
            pos += 1
        if pos == start:
            _text(tokens, text[pos])
            pos += 1
        else:
            _text(tokens, text[start:pos])

    return tokens, pos, False


def tokenize_inline(text):
    """Tokenize one logical line into a nested, inert inline token tree."""
    tokens, _, _ = _tokenize("" if text is None else str(text))
    return tokens


def _emit(tokens):
    out = []
    for token in tokens:
        kind = token[0]
        if kind == "TEXT":
            out.append(html.escape(token[1], quote=True))
        elif kind == "CODE":
            out.append("<code>%s</code>" % html.escape(token[1], quote=True))
        elif kind == "LINK":
            out.append('<a href="%s" rel="noopener noreferrer">%s</a>' % (
                html.escape(token[2], quote=True), _emit(token[1])))
        elif kind == "STRONG":
            out.append("<strong>%s</strong>" % _emit(token[1]))
        elif kind == "EM":
            out.append("<em>%s</em>" % _emit(token[1]))
    return "".join(out)


def render_inline(text):
    """Render one logical line with safe inline Markdown and no block wrapper."""
    value = "" if text is None else str(text)
    try:
        return _emit(tokenize_inline(value))
    except Exception:
        return html.escape(value, quote=True)


def _has_unescaped_pipe(line):
    escaped = False
    for ch in line:
        if ch == "\\":
            escaped = not escaped
            continue
        if ch == "|" and not escaped:
            return True
        escaped = False
    return False


def _split_row(line):
    cells = []
    buf = []
    slash_run = 0
    for ch in line:
        if ch == "\\":
            buf.append(ch)
            slash_run += 1
            continue
        if ch == "|" and slash_run % 2 == 0:
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        slash_run = 0
    cells.append("".join(buf))
    stripped = line.strip()
    if stripped.startswith("|") and cells and not cells[0].strip():
        cells.pop(0)
    if stripped.endswith("|") and cells and not cells[-1].strip():
        cells.pop()
    return [cell.strip() for cell in cells]


def _separator(line):
    if not _has_unescaped_pipe(line):
        return None
    cells = _split_row(line)
    if not cells or any(not re.match(r"^:?-+:?$", cell) for cell in cells):
        return None
    align = []
    for cell in cells:
        if cell.startswith(":") and cell.endswith(":"):
            align.append("center")
        elif cell.endswith(":"):
            align.append("right")
        else:
            align.append(None)
    return align


def _is_table(lines, pos):
    return (pos + 1 < len(lines) and _has_unescaped_pipe(lines[pos]) and
            _separator(lines[pos + 1]) is not None)


def _kind(lines, pos):
    line = lines[pos]
    if not line.strip():
        return "blank"
    if _FENCE.match(line):
        return "fence"
    if _UL_ITEM.match(line):
        return "ul"
    if _OL_ITEM.match(line):
        return "ol"
    if _is_table(lines, pos):
        return "table"
    if line.startswith(">"):
        return "quote"
    return "paragraph"


def _render_list(lines, pos, ordered):
    matcher = _OL_ITEM if ordered else _UL_ITEM
    items = []
    while pos < len(lines):
        match = matcher.match(lines[pos])
        if not match:
            break
        parts = [match.group(1)]
        pos += 1
        while pos < len(lines) and re.match(r"^\s{2,}\S", lines[pos]):
            parts.append(re.sub(r"^\s{2,}", "", lines[pos]))
            pos += 1
        items.append(" ".join(parts))
    tag = "ol" if ordered else "ul"
    body = "".join("<li>%s</li>" % render_inline(item) for item in items)
    return "<%s>%s</%s>" % (tag, body, tag), pos


def _cell(tag, value, alignment):
    style = ' style="text-align:%s"' % alignment if alignment else ""
    return "<%s%s>%s</%s>" % (tag, style, render_inline(value), tag)


def _render_table(lines, pos):
    headers = _split_row(lines[pos])
    align = _separator(lines[pos + 1])
    width = len(headers)
    align = (align + [None] * width)[:width]
    pos += 2
    rows = []
    while pos < len(lines) and lines[pos].strip() and _has_unescaped_pipe(lines[pos]):
        if _kind(lines, pos) in ("fence", "ul", "ol", "quote"):
            break
        row = _split_row(lines[pos])
        row = (row + [""] * width)[:width]
        rows.append(row)
        pos += 1
    head = "".join(_cell("th", value, align[i]) for i, value in enumerate(headers))
    body = "".join("<tr>%s</tr>" % "".join(
        _cell("td", value, align[i]) for i, value in enumerate(row)) for row in rows)
    table = "<table><thead><tr>%s</tr></thead>" % head
    if rows:
        table += "<tbody>%s</tbody>" % body
    table += "</table>"
    return '<div class="table-wrap">%s</div>' % table, pos


def _diff_rows(source):
    """Pair a unified diff into side-by-side rows.

    Returns ``(path, rows, changed)``. A row is ``("hunk", header)`` or
    ``("line", old, new)`` where each side is ``None`` or ``(number, kind, text)``
    and ``kind`` is ``ctx``, ``del``, or ``ins``. Numbers are ``None`` until a
    parseable ``@@`` header supplies them.
    """
    lines = source.split("\n")
    path = None
    rows = []
    changed = False
    old_no = new_no = None
    dels, inss = [], []

    def flush():
        for left, right in itertools.zip_longest(dels, inss):
            rows.append(("line", left, right))
        del dels[:], inss[:]

    pos = 0
    while pos < len(lines):
        line = lines[pos]
        # a removed line can itself start with "--", so only a ---/+++ pair is a file header
        if line.startswith("--- ") and pos + 1 < len(lines) and lines[pos + 1].startswith("+++ "):
            flush()
            target = lines[pos + 1][4:].strip()
            path = target[2:] if target.startswith("b/") else target
            pos += 2
            continue
        if line.startswith(("diff ", "index ")) or line.startswith("\\ "):
            pos += 1
            continue
        if line.startswith("@@"):
            flush()
            match = _HUNK.match(line)
            old_no, new_no = (int(match.group(1)), int(match.group(2))) if match else (None, None)
            rows.append(("hunk", line))
        elif line.startswith("-"):
            if inss:
                flush()
            dels.append((old_no, "del", line[1:]))
            old_no = old_no + 1 if old_no is not None else None
            changed = True
        elif line.startswith("+"):
            inss.append((new_no, "ins", line[1:]))
            new_no = new_no + 1 if new_no is not None else None
            changed = True
        else:
            flush()
            text = line[1:] if line.startswith(" ") else line
            rows.append(("line", (old_no, "ctx", text), (new_no, "ctx", text)))
            old_no = old_no + 1 if old_no is not None else None
            new_no = new_no + 1 if new_no is not None else None
        pos += 1
    flush()
    while rows and rows[-1] == ("line", (None, "ctx", ""), (None, "ctx", "")):
        rows.pop()
    return path, rows, changed


def _highlight_sides(rows, language):
    """Colour each hunk's old and new side as one source, keyed by row cell."""
    coloured = {}
    hunk = []
    for index, row in enumerate(rows + [("hunk", "")]):
        if row[0] != "hunk":
            hunk.append(index)
            continue
        for column in (1, 2):
            cells = [i for i in hunk if rows[i][column] is not None]
            lines = highlight.highlight_lines([rows[i][column][2] for i in cells], language)
            coloured.update(((i, column), line) for i, line in zip(cells, lines))
        hunk = []
    return coloured


def _diff_cells(value, code):
    if value is None:
        return '<td class="sbs-ln"></td><td class="sbs-code sbs-empty"></td>'
    number, kind, _ = value
    if kind == "del":
        code = "<del>%s</del>" % code
    elif kind == "ins":
        code = "<ins>%s</ins>" % code
    return '<td class="sbs-ln">%s</td><td class="sbs-code sbs-%s">%s</td>' % (
        "" if number is None else number, kind, code)


def render_side_by_side(source):
    """Render a unified diff as a current-vs-suggested table, or None if nothing changes."""
    path, rows, changed = _diff_rows(source)
    if not changed:
        return None
    coloured = _highlight_sides(rows, highlight.language_for_path(path))
    label = "Current and suggested code" + (" for %s" % path if path else "")
    body = []
    for index, row in enumerate(rows):
        if row[0] == "hunk":
            body.append('<tr class="sbs-hunk"><td colspan="4">%s</td></tr>' %
                        html.escape(row[1], quote=True))
        else:
            body.append("<tr>%s%s</tr>" % (_diff_cells(row[1], coloured.get((index, 1))),
                                           _diff_cells(row[2], coloured.get((index, 2)))))
    head = ('<div class="sbs-path">%s</div>' % html.escape(path, quote=True)) if path else ""
    return ('<div class="sbs-wrap">%s<table class="sbs" aria-label="%s">'
            '<colgroup><col class="sbs-col-ln"><col><col class="sbs-col-ln"><col></colgroup>'
            '<thead><tr><th scope="col" colspan="2">Current</th>'
            '<th scope="col" colspan="2">Suggested</th></tr></thead>'
            '<tbody>%s</tbody></table></div>' %
            (head, html.escape(label, quote=True), "".join(body)))


def split_blocks(text):
    """Split Markdown into block tokens without allowing paragraphs to swallow blocks."""
    if text is None or text == "":
        return []
    lines = str(text).splitlines()
    blocks = []
    pos = 0
    while pos < len(lines):
        kind = _kind(lines, pos)
        if kind == "blank":
            pos += 1
            continue
        if kind == "fence":
            language = _FENCE.match(lines[pos]).group("info")
            pos += 1
            content = []
            while pos < len(lines) and not _FENCE.match(lines[pos]):
                content.append(lines[pos])
                pos += 1
            if pos < len(lines):
                pos += 1
            source = "\n".join(content)
            name = highlight.supported(language)
            if name == "diff":
                table = render_side_by_side(source)
                if table:
                    blocks.append(("HTML", table))
                    continue
            attr = ' class="lang-%s"' % name if name else ""
            blocks.append(("HTML", '<pre class="snippet"><code%s>%s</code></pre>' %
                           (attr, highlight.highlight(source, language))))
            continue
        if kind in ("ul", "ol"):
            rendered, pos = _render_list(lines, pos, kind == "ol")
            blocks.append(("HTML", rendered))
            continue
        if kind == "table":
            rendered, pos = _render_table(lines, pos)
            blocks.append(("HTML", rendered))
            continue
        if kind == "quote":
            quoted = []
            while pos < len(lines) and lines[pos].startswith(">"):
                value = lines[pos][1:]
                if value.startswith(" "):
                    value = value[1:]
                quoted.append(value)
                pos += 1
            blocks.append(("HTML", "<blockquote>%s</blockquote>" % render_markdown("\n".join(quoted))))
            continue
        paragraph = []
        while pos < len(lines) and _kind(lines, pos) == "paragraph":
            paragraph.append(lines[pos].strip())
            pos += 1
        blocks.append(("HTML", "<p>%s</p>" % render_inline(" ".join(paragraph))))
    return blocks


def render_markdown(text):
    """Render supported block Markdown safely; None and empty input render empty."""
    value = "" if text is None else str(text)
    try:
        return "\n".join(block[1] for block in split_blocks(value))
    except Exception:
        return "<p>%s</p>" % html.escape(value, quote=True) if value else ""
