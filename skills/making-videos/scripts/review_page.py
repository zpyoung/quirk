#!/usr/bin/env python3
"""Build the review page for a making-videos project through the writing-html-artifacts skill.

``review_page.py --project DIR`` writes ``<project>/review.src.html`` (a ``report`` source, kept so
the page can be rebuilt by hand) and builds ``<project>/review.html`` with the sibling skill's
builder. The newest version leads: the agent's verdict, findings generated from ``verify.json``,
the players, the scenes with play buttons, the agent's checklist (``<vN>/review-notes.md``), the
verify results, the frames, the outside calls, then earlier versions with a compare. Every value
read from project files is HTML-escaped, media links are relative to the project, and the page
makes no network request, so it works from ``file://`` while it sits in the project folder.

Prints one JSON object: ``{"page", "source", "checks"}`` on success, ``{"error", ...}`` otherwise.
Exit codes: 0 ok; 1 the builder is missing, failed or its static checks failed (an ``error`` key,
plus ``page``, ``source`` and ``checks`` when the builder got that far); 2 usage error or missing
project.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn, Optional
from urllib.parse import quote

# siblings are imported by bare name, so the script directory must be on sys.path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import EXIT_FAILED, EXIT_USAGE, emit, scrubbed_env  # noqa: E402

LOCAL_PROVIDERS = frozenset({"hyperframes", "playwright"})
BUILDER_TIMEOUT_S = 180


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


# text helpers -----------------------------------------------------------------------------------


def esc(value: Any) -> str:
    """HTML-escape any value; non-strings are JSON-encoded first."""
    if isinstance(value, str):
        text = value
    elif value is None:
        text = ""
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value)
    else:
        text = json.dumps(value)
    return html.escape(text, quote=True)


def rel_url(path: Path, base: Path) -> str:
    """Percent-encoded relative URL of ``path`` under ``base``, escaped for an attribute."""
    return esc(quote(path.relative_to(base).as_posix(), safe="/"))


def _num(value: Any) -> str:
    """A number without trailing zeros (``3.70`` -> ``3.7``); anything else as text."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return "%g" % value


def _fixed(value: Any) -> str:
    """One decimal place for loudness readings, so ``-16.0`` keeps its zero."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "%.1f" % value
    return str(value)


def _plural(count: int, one: str, many: str) -> str:
    return "%d %s" % (count, one if count == 1 else many)


def _join_words(items: "list[str]") -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# markdown ---------------------------------------------------------------------------------------

_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_FENCE = re.compile(r"^\s*```")
_BLOCKQUOTE = re.compile(r"^\s*>")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _inline(text: str) -> str:
    parts = _CODE_SPAN.split(text)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append("<code>%s</code>" % esc(part))
        else:
            out.append(_BOLD.sub(lambda m: "<strong>%s</strong>" % m.group(1), esc(part)))
    return "".join(out)


def _plain(text: str) -> str:
    """Markdown inline markup removed, for labels and captions."""
    return _BOLD.sub(r"\1", _CODE_SPAN.sub(r"\1", text)).strip()


def _split_row(line: str) -> "list[str]":
    """Cells of a Markdown table row; ``\\|`` and pipes inside code spans do not split."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    cells, current, in_code, i = [], [], False, 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail or not text.rstrip().endswith("|"):
        cells.append(tail)
    return cells


def _is_table_start(lines: "list[str]", i: int) -> bool:
    return (
        "|" in lines[i]
        and i + 1 < len(lines)
        and "|" in lines[i + 1]
        and bool(_TABLE_SEPARATOR.match(lines[i + 1]))
    )


def _is_table_row(line: str) -> bool:
    """A pipe line that is not the start of another Markdown block."""
    return "|" in line and not any(
        p.match(line) for p in (_HEADING, _FENCE, _BULLET, _NUMBERED, _BLOCKQUOTE)
    )


def _read_table(lines: "list[str]", i: int) -> "tuple[list[str], list[list[str]], int]":
    """Header cells, body rows and the index after the table that starts at ``lines[i]``.

    A body row is any line containing a pipe after the delimiter row; outer pipes are optional. A
    heading, fence, list item, blockquote or blank line ends the table even if it contains a pipe.
    """
    header = _split_row(lines[i])
    i += 2
    rows = []
    while i < len(lines) and _is_table_row(lines[i]):
        rows.append(_split_row(lines[i]))
        i += 1
    return header, rows, i


def _table_html(header: "list[str]", rows: "list[list[str]]", caption: str) -> str:
    width = len(header)
    head = "".join('<th scope="col">%s</th>' % _inline(c) for c in header)
    body = []
    for row in rows:
        cells = (row + [""] * width)[:width]
        body.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(c) for c in cells))
    return (
        '<div class="q-table-wrap">\n<table>\n<caption>%s</caption>\n<thead><tr>%s</tr></thead>\n'
        "<tbody>\n%s\n</tbody>\n</table>\n</div>" % (esc(caption), head, "\n".join(body))
    )


def render_markdown(text: str, shift: int = 0) -> str:
    """Render a small Markdown subset to HTML; unknown syntax falls back to escaped text.

    Supports headings (moved ``shift`` levels deeper, capped at h6), paragraphs, bullet and numbered
    lists, fenced code, and pipe tables (rendered as real ``<table>`` elements with a caption taken
    from the nearest heading).
    """
    lines = text.splitlines()
    out: "list[str]" = []
    last_heading = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line):
            i += 1
            code = []
            while i < len(lines) and not _FENCE.match(lines[i]):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % esc("\n".join(code)))
            continue
        heading = _HEADING.match(line)
        if heading:
            level = min(6, len(heading.group(1)) + shift)
            last_heading = _plain(heading.group(2))
            out.append("<h%d>%s</h%d>" % (level, _inline(heading.group(2)), level))
            i += 1
            continue
        if _is_table_start(lines, i):
            header, rows, i = _read_table(lines, i)
            out.append(_table_html(header, rows, last_heading or "Table"))
            continue
        for pattern, tag in ((_BULLET, "ul"), (_NUMBERED, "ol")):
            if pattern.match(line):
                items = []
                while i < len(lines) and pattern.match(lines[i]):
                    items.append("<li>%s</li>" % _inline(pattern.match(lines[i]).group(1)))
                    i += 1
                out.append("<%s>\n%s\n</%s>" % (tag, "\n".join(items), tag))
                break
        else:
            if not line.strip():
                i += 1
                continue
            para = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not _FENCE.match(lines[i])
                and not _HEADING.match(lines[i])
                and not _BULLET.match(lines[i])
                and not _NUMBERED.match(lines[i])
                and not _is_table_start(lines, i)
            ):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % _inline(" ".join(para)))
    return "\n".join(out)


def _shift_to_h3(text: str) -> int:
    """Levels to push a Markdown document's headings so its shallowest becomes an h3."""
    levels = [len(m.group(1)) for m in map(_HEADING.match, text.splitlines()) if m]
    return 3 - min(levels) if levels else 0


# reading project files ---------------------------------------------------------------------------


def _read_json(path: Path) -> "tuple[Optional[Any], Optional[str]]":
    """Parsed JSON and None, or None and a short reason the file could not be used."""
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, ValueError) as exc:
        return None, "unreadable (%s)" % type(exc).__name__


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    except OSError:
        return None


def _version_dirs(project: Path) -> "list[Path]":
    found = [p for p in project.iterdir() if p.is_dir() and re.fullmatch(r"v\d+", p.name)]
    return sorted(found, key=lambda p: int(p.name[1:]), reverse=True)


def _read_calls(project: Path) -> "tuple[list[dict], int]":
    path = project / "calls.jsonl"
    if not path.is_file():
        return [], 0
    records, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(rec, dict):
            records.append(rec)
        else:
            bad += 1
    return records, bad


def _what_ran(rec: dict) -> str:
    provider = rec.get("provider")
    if provider == "hyperframes":
        args = rec.get("args")
        parts = [rec.get("subcommand")]
        if isinstance(args, list):
            parts.append(" ".join(str(a) for a in args))
        return " ".join(str(p) for p in parts if p)
    if provider == "playwright":
        return " ".join(str(p) for p in (rec.get("method"), rec.get("host")) if p)
    target = "%s%s" % (rec.get("host") or "", rec.get("path") or "")
    return " ".join(str(p) for p in (rec.get("method"), target) if p)


def _beat_words(project: Path) -> "dict[str, str]":
    """Spoken word per beat id from the project's ``beats*.json`` files."""
    words: "dict[str, str]" = {}
    for path in sorted(project.glob("beats*.json")):
        data, _ = _read_json(path)
        beats = data.get("beats") if isinstance(data, dict) else data
        for beat in beats if isinstance(beats, list) else []:
            if isinstance(beat, dict) and beat.get("id") is not None and beat.get("word"):
                words.setdefault(str(beat["id"]), str(beat["word"]))
    return words


# cuts, runs and verdicts ------------------------------------------------------------------------

_ASPECT = re.compile(r"(?<!\d)(\d{1,2})x(\d{1,2})(?!\d)")


def _aspect(mp4: Path) -> "Optional[tuple[int, int]]":
    match = _ASPECT.search(mp4.stem)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _cut_labels(mp4s: "list[Path]") -> "dict[str, str]":
    """Short name per MP4: its aspect ratio when that is unique among the cuts, else the file name."""
    guesses = {m.name: ("%d:%d" % _aspect(m)) if _aspect(m) else m.name for m in mp4s}
    counts: "dict[str, int]" = {}
    for label in guesses.values():
        counts[label] = counts.get(label, 0) + 1
    return {name: label if counts[label] == 1 else name for name, label in guesses.items()}


CHECK_LABELS = {
    "fonts": "fonts",
    "render_log": "render log",
    "contrast": "contrast",
    "title_safe": "title safe",
    "loudness": "loudness",
    "sync": "sync",
    "blender": "blender",
    "outside_calls": "outside calls",
}


def _check_label(name: Any) -> str:
    return CHECK_LABELS.get(str(name)) or str(name).replace("_", " ")


class Version:
    """Everything the page needs to know about one ``vN`` folder."""

    def __init__(self, project: Path, vdir: Path) -> None:
        self.project = project
        self.dir = vdir
        self.name = vdir.name
        self.mp4s = sorted(vdir.glob("*.mp4"))
        self.srts = sorted(vdir.glob("*.srt"))
        self.labels = _cut_labels(self.mp4s)
        self.verify_problem: Optional[str] = None
        self.verify_flaws: "list[str]" = []
        self.runs: "list[tuple[Optional[str], dict]]" = []
        self._unreadable_runs: "set[str]" = set()
        data, reason = _read_json(vdir / "verify.json")
        if reason == "missing":
            self.verify_problem = "no verify.json"
        elif reason or not isinstance(data, dict):
            self.verify_problem = "verify.json %s" % (reason or "is not an object")
        elif "runs" in data and not isinstance(data["runs"], dict):
            self.verify_problem = "verify.json runs unreadable"
        elif isinstance(data.get("runs"), dict):
            for key, run in sorted(data["runs"].items()):
                if isinstance(run, dict):
                    self.runs.append((key, self._checked_run(key, run)))
                else:
                    self._unreadable_runs.add(key)
                    self.verify_flaws.append("verify.json run for %s unreadable" % key)
        else:
            self.runs = [(self.mp4s[0].name if len(self.mp4s) == 1 else None, self._checked_run(None, data))]
        self.note_verdict, self.note_rest = self._read_note()

    def _checked_run(self, key: Optional[str], run: dict) -> dict:
        """``run`` with a non-list ``checks`` emptied; each malformed part is named in ``verify_flaws``."""
        where = " for %s" % key if key else ""
        checks = run.get("checks")
        if checks is not None and not isinstance(checks, list):
            self.verify_flaws.append("verify.json checks unreadable%s" % where)
            run = dict(run, checks=[])
        for check in run.get("checks") or []:
            measured = check.get("measured") if isinstance(check, dict) and check.get("name") == "sync" else None
            if isinstance(measured, dict) and measured.get("beats") is not None and not isinstance(measured["beats"], list):
                self.verify_flaws.append("verify.json sync beats unreadable%s" % where)
        return run

    def _read_note(self) -> "tuple[Optional[str], Optional[str]]":
        """The first paragraph of ``review-notes.md`` and the rest of it, or ``(None, None)``."""
        text = _read_text(self.dir / "review-notes.md")
        if text is None or not text.strip():
            return None, None
        blocks = re.split(r"\n\s*\n", text.strip(), maxsplit=1)
        first = blocks[0]
        first_line = first.splitlines()[0]
        if any(p.match(first_line) for p in (_BULLET, _NUMBERED, _HEADING, _FENCE)) or _is_table_start([first_line, ""], 0):
            return None, text.strip()
        return " ".join(line.strip() for line in first.splitlines()), blocks[1] if len(blocks) > 1 else ""

    def run_label(self, name: Optional[str]) -> str:
        if name is None:
            return "this version"
        return self.labels.get(name, name)

    def run_for(self, mp4: Path) -> Optional[dict]:
        return next((run for key, run in self.runs if key == mp4.name), None)

    def failing(self, run: dict) -> "list[dict]":
        checks = run.get("checks")
        return [c for c in checks if isinstance(c, dict) and c.get("status") == "fail"] if isinstance(checks, list) else []

    def missing(self, with_verify: bool = True) -> "list[str]":
        """Named gaps in this version: MP4, verify.json, a run per MP4, stills per MP4."""
        gaps = []
        if not self.mp4s:
            gaps.append("no MP4")
        if with_verify:
            gaps.extend(self.verify_gaps())
        gaps.extend(self.still_gaps())
        return gaps

    def verify_gaps(self) -> "list[str]":
        if self.verify_problem:
            return [self.verify_problem]
        keys = {key for key, _ in self.runs}
        if None in keys:
            return list(self.verify_flaws)
        absent = ["no verify run for %s" % m.name for m in self.mp4s if m.name not in keys | self._unreadable_runs]
        return self.verify_flaws + absent

    def still_gaps(self) -> "list[str]":
        return [g.missing for g in self.frame_groups() if g.missing]

    def plain_verdict(self) -> str:
        """One plain sentence or two on what verify found for this version."""
        if self.verify_problem:
            return "There are no usable verify results for %s yet." % self.name
        if not self.runs:
            return "verify.json for %s holds no runs yet." % self.name
        failed = [(key, run) for key, run in self.runs if not run.get("passed")]
        if failed:
            parts = []
            for key, run in failed:
                names = [_check_label(c.get("name")) for c in self.failing(run)]
                parts.append("the %s cut%s" % (self.run_label(key), " (%s)" % ", ".join(names) if names else "")
                             if key else "%s%s" % (self.name, " (%s)" % ", ".join(names) if names else ""))
            text = "Verify failed on %s." % _join_words(parts)
        else:
            many = len(self.runs) > 1
            cuts = "both cuts of" if len(self.runs) == 2 else "all %d cuts of" % len(self.runs)
            text = "Verify passed on %s %s." % (cuts, self.name) if many else "Verify passed on %s." % self.name
            tallies = {self._tally(run) for _, run in self.runs}
            if len(tallies) == 1:
                passed, total, skipped = tallies.pop()
                text += " %s passed %d of %d checks" % ("Each cut" if many else "It", passed, total)
                text += ", and %d %s skipped." % (skipped, "was" if skipped == 1 else "were") if skipped else "."
        gaps = self.verify_gaps()
        if gaps:
            text += " " + "; ".join(g[:1].upper() + g[1:] for g in gaps) + "."
        return text

    @staticmethod
    def _tally(run: dict) -> "tuple[int, int, int]":
        checks = [c for c in run.get("checks") or [] if isinstance(c, dict)]
        return (
            sum(1 for c in checks if c.get("status") == "pass"),
            len(checks),
            sum(1 for c in checks if c.get("status") == "skip"),
        )

    def frame_groups(self) -> "list[FrameGroup]":
        """Stills per MP4 (``frames/<stem>/``), or the flat ``frames/`` of an older verify run."""
        frames = self.dir / "frames"
        flat = sorted(frames.glob("*.png")) if frames.is_dir() else []
        flat = [p for p in flat if p.name != "sheet.png"]
        groups = []
        for mp4 in self.mp4s:
            folder = frames / mp4.stem
            where = "frames/%s/" % mp4.stem
            if folder.is_dir():
                stills = sorted(p for p in folder.glob("*.png") if p.name != "sheet.png")
            elif len(self.mp4s) == 1 and flat:
                stills, where = flat, "frames/"
            else:
                stills = []
            groups.append(FrameGroup(self.labels[mp4.name], stills, "no stills in %s" % where if not stills else None))
        if not self.mp4s and flat:
            groups.append(FrameGroup("All cuts", flat, None))
        elif len(self.mp4s) > 1 and flat and not any(g.stills for g in groups):
            groups = [FrameGroup("All cuts", flat, None)]
        return groups


class FrameGroup:
    """The stills belonging to one cut (or to a flat ``frames/`` folder) and, if none, what is missing."""

    def __init__(self, label: str, stills: "list[Path]", missing: Optional[str]) -> None:
        self.label = label
        self.stills = stills
        self.missing = missing


# scenes -----------------------------------------------------------------------------------------


class Scene:
    """One storyboard row: a label, an optional start time in seconds, and the words spoken or shown."""

    def __init__(self, label: str, start: Optional[str], words: str) -> None:
        self.label = label
        self.start = start
        self.words = words

    @property
    def scene_id(self) -> str:
        first = self.label.split()[0] if self.label.split() else self.label
        return first if re.fullmatch(r"s?\d+", first) else self.label


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _script_items(text: str) -> "list[str]":
    """Items of the numbered list under the storyboard's Script heading."""
    items: "list[str]" = []
    in_script = False
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            if in_script and items:
                break
            in_script = heading.group(2).strip().lower().startswith("script")
            continue
        match = _NUMBERED.match(line)
        if in_script and match:
            items.append(match.group(1).strip())
    return items


def parse_scenes(storyboard: str) -> "Optional[list[Scene]]":
    """Scenes from the first table whose first header starts with Scene and that has a Time column.

    Returns None when no table qualifies. Words come from the Script list when it has one item per
    row, else the Narration column, else the first column whose header contains "text".
    """
    lines = storyboard.splitlines()
    i = 0
    while i < len(lines):
        if not _is_table_start(lines, i):
            i += 1
            continue
        header, rows, i = _read_table(lines, i)
        heads = [h.strip().lower() for h in header]
        time_col = next((n for n, h in enumerate(heads) if h.startswith("time")), None)
        if not heads or not heads[0].startswith("scene") or time_col is None or not rows:
            continue
        script = _script_items(storyboard)
        narration = next((n for n, h in enumerate(heads) if h.startswith("narration")), None)
        text_col = next((n for n, h in enumerate(heads) if "text" in h), None)
        scenes = []
        for n, row in enumerate(rows):
            row = row + [""] * (len(heads) - len(row))
            found = _NUMBER.search(row[time_col])
            if len(script) == len(rows):
                words = script[n]
            elif narration is not None:
                words = row[narration]
            elif text_col is not None:
                words = row[text_col]
            else:
                words = ""
            scenes.append(Scene(_plain(row[0]).lower(), found.group(0) if found else None, words))
        return scenes
    return None


def scene_at(scenes: "list[Scene]", seconds: float) -> Optional[Scene]:
    """The last scene that starts at or before ``seconds``."""
    current = None
    for scene in scenes:
        if scene.start is not None and float(scene.start) <= seconds:
            current = scene
    return current


# verify check wording ---------------------------------------------------------------------------


def _generic(value: Any) -> str:
    """Short plain rendering of a measured or threshold value, never raw JSON."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return _num(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(_generic(v) if not isinstance(v, (dict, list)) else "(%s)" % _plural(len(v), "item", "items")
                         for v in value)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                text = "(%s)" % _plural(len(item), "item", "items")
            else:
                text = _generic(item)
            parts.append("%s: %s" % (str(key).replace("_", " "), text))
        return ", ".join(parts)
    return str(value)


def _range(value: Any) -> str:
    return "%s to %s" % (_num(value[0]), _num(value[1])) if isinstance(value, list) and len(value) == 2 else ""


def _measured_fonts(m: Any) -> str:
    if isinstance(m, dict) and "injected" in m:
        n = m["injected"]
        return "%s injected at render, %s unresolved" % (
            _plural(n, "font family", "font families") if isinstance(n, int) else "%s font families" % n,
            _num(m.get("unresolved", 0)),
        )
    return ""


def _threshold_fonts(t: Any) -> str:
    if isinstance(t, dict) and "injected_min" in t:
        none = " and none unresolved" if t.get("unresolved") == 0 else ""
        return "At least %s brand fonts%s" % (_num(t["injected_min"]), none)
    return ""


def _measured_render_log(m: Any) -> str:
    if isinstance(m, dict) and "known_bad" in m:
        bad, other = m.get("known_bad") or 0, m.get("other") or 0
        if not bad and not other:
            return "No warning or error lines"
        return "%s, %s" % (_plural(bad, "known-bad line", "known-bad lines"), _plural(other, "other line", "other lines"))
    return ""


def _measured_contrast(m: Any) -> str:
    if isinstance(m, dict) and "failing" in m:
        text = _plural(m["failing"], "failing text element", "failing text elements") if isinstance(m["failing"], int) else ""
        ratio = m.get("worst_ratio")
        return text + (", worst ratio %s:1" % _num(ratio) if ratio is not None and text else "")
    return ""


def _measured_title_safe(m: Any) -> str:
    if isinstance(m, dict) and "collisions" in m and isinstance(m["collisions"], int):
        bands = m.get("bands_checked")
        where = " across %s" % _plural(len(bands), "edge band", "edge bands") if isinstance(bands, list) else ""
        return _plural(m["collisions"], "collision", "collisions") + where
    return ""


def _measured_loudness(m: Any) -> str:
    if isinstance(m, dict) and "lufs" in m:
        return "%s LUFS, true peak %s dBTP" % (_fixed(m["lufs"]), _fixed(m.get("true_peak_dbtp")))
    return ""


def _threshold_loudness(t: Any) -> str:
    if isinstance(t, dict) and _range(t.get("lufs")):
        peak = t.get("true_peak_dbtp_max")
        return "%s LUFS%s" % (_range(t["lufs"]), ", peak at most %s dBTP" % _num(peak) if peak is not None else "")
    return ""


def _measured_sync(m: Any) -> str:
    if isinstance(m, dict) and "worst_frames" in m:
        return "Worst beat %s frames off" % _num(m["worst_frames"])
    return ""


def _threshold_sync(t: Any) -> str:
    if isinstance(t, dict) and "offset_frames_max" in t:
        return "Every beat within %s" % _plural(1, "frame", "frames") if t["offset_frames_max"] == 1 else \
            "Every beat within %s frames" % _num(t["offset_frames_max"])
    return ""


def _measured_blender(m: Any) -> str:
    if isinstance(m, dict) and "guards" in m:
        return "%s clean, %s mirrored text" % (
            _plural(m["guards"], "guard file", "guard files") if isinstance(m["guards"], int) else "guard files",
            _num(m.get("mirrored_frames", 0)),
        )
    return ""


def _threshold_outside_calls(t: Any) -> str:
    if isinstance(t, dict) and isinstance(t.get("cloud_allow"), list):
        allowed = t["cloud_allow"]
        return "Local tools and: %s" % ", ".join(str(a) for a in allowed) if allowed else "Local tools only"
    return ""


MEASURED = {
    "fonts": _measured_fonts,
    "render_log": _measured_render_log,
    "contrast": _measured_contrast,
    "title_safe": _measured_title_safe,
    "loudness": _measured_loudness,
    "sync": _measured_sync,
    "blender": _measured_blender,
}

THRESHOLD = {
    "fonts": _threshold_fonts,
    "contrast": lambda t: "WCAG AA for all text" if isinstance(t, dict) and "failing" in t else "",
    "render_log": lambda t: "No known-bad lines" if isinstance(t, dict) and "known_bad" in t else "",
    "title_safe": lambda t: "No text in the outer 5% of any edge" if isinstance(t, dict) and "collisions" in t else "",
    "loudness": _threshold_loudness,
    "sync": _threshold_sync,
    "blender": lambda t: "No default scene and no mirrored text" if isinstance(t, dict) and "default_scene" in t else "",
    "outside_calls": _threshold_outside_calls,
}

STATUS_WORDS = {"pass": "Pass", "fail": "Fail", "skip": "Skipped"}


def measured_text(check: dict) -> str:
    """Plain-words measured value of one check; falls back to the generic rendering, then ``detail``."""
    name = str(check.get("name"))
    text = ""
    if name != "outside_calls":
        text = MEASURED.get(name, lambda _m: "")(check.get("measured"))
    text = text or _generic(check.get("measured")) or str(check.get("detail") or "")
    detail = str(check.get("detail") or "")
    if check.get("status") == "fail" and detail and detail != text:
        text = "%s. %s" % (text, detail) if text else detail
    return text


def threshold_text(check: dict) -> str:
    """Plain-words bar of one check, falling back to the generic rendering."""
    name = str(check.get("name"))
    return THRESHOLD.get(name, lambda _t: "")(check.get("threshold")) or _generic(check.get("threshold"))


# page pieces ------------------------------------------------------------------------------------


def _section(ident: str, heading: str, body: str) -> str:
    return '<section aria-labelledby="%s-h">\n<h2 id="%s-h">%s</h2>\n%s\n</section>' % (ident, ident, esc(heading), body)


def _missing_line(gaps: "list[str]") -> str:
    if not gaps:
        return ""
    return '<p class="missing"><strong>Missing:</strong> %s.</p>' % esc("; ".join(gaps))


def _tilde(path: Path) -> str:
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home):] if home != "/" and text.startswith(home + "/") else text


def _meta(project: Path, brief: Any) -> str:
    facts = []
    if isinstance(brief, dict):
        if brief.get("product"):
            facts.append(esc(brief["product"]))
        if brief.get("length_s") is not None:
            facts.append(esc("%s s" % _num(brief["length_s"])))
        aspects = brief.get("aspects")
        if isinstance(aspects, list) and aspects:
            facts.append(esc("aspects " + _join_words([str(a) for a in aspects])))
        if "narration" in brief:
            facts.append("narration " + ("on" if brief.get("narration") else "off"))
        if brief.get("created"):
            facts.append(esc("created %s" % brief["created"]))
    facts.append("project <code>%s</code>" % esc(_tilde(project)))
    return '<p class="q-meta">%s.</p>' % ", ".join(facts)


def _player(project: Path, version: Version, mp4: Path, index: Optional[int]) -> str:
    label = version.labels[mp4.name]
    aspect = _aspect(mp4)
    tall = bool(aspect) and aspect[0] <= aspect[1]
    span = "1" if tall else "3"
    srt = next((s for s in version.srts if s.stem == mp4.stem), None)
    link = ', captions as a sidecar file: <a href="%s">%s</a>' % (rel_url(srt, project), esc(srt.name)) if srt else ""
    ident = ' id="cut-%d" data-cut="%s"' % (index, esc(label)) if index is not None else ""
    return (
        '<figure data-span="%s" class="cut">\n  <video%s%s controls preload="metadata" playsinline src="%s" '
        'aria-label="%s"></video>\n  <figcaption>%s%s</figcaption>\n</figure>'
        % (span, ident, ' class="tall"' if tall else "", rel_url(mp4, project), esc("%s cut, %s" % (label, mp4.name)),
           esc(label), link)
    )


def _players(project: Path, version: Version, numbered: bool) -> str:
    figures = [_player(project, version, mp4, n if numbered else None) for n, mp4 in enumerate(version.mp4s)]
    extra = [s for s in version.srts if not any(s.stem == m.stem for m in version.mp4s)]
    tail = ""
    if extra:
        tail = "\n<p>Captions: %s</p>" % ", ".join('<a href="%s">%s</a>' % (rel_url(s, project), esc(s.name)) for s in extra)
    return "<q-grid>\n%s\n</q-grid>%s" % ("\n".join(figures), tail) if figures else ""


def _verdict_html(version: Version) -> str:
    if version.note_verdict:
        return _inline(version.note_verdict)
    return esc(version.plain_verdict())


def _summary(version: Version) -> str:
    parts = []
    for key, run in version.runs:
        if run.get("stop"):
            names = [_check_label(c.get("name")) for c in version.failing(run)]
            where = "the %s cut" % version.run_label(key) if key else version.name
            parts.append(
                '<p class="q-lede">%s</p>'
                % esc("Stopped after 3 failed verify attempts on %s.%s" % (
                    where, " Failing checks: %s." % ", ".join(names) if names else ""))
            )
    parts.append('<p class="q-lede">%s</p>' % _verdict_html(version))
    return "\n".join(parts)


# findings ---------------------------------------------------------------------------------------


def _beat_label(words: "dict[str, str]", beat: dict) -> str:
    label = words.get(str(beat.get("id")), str(beat.get("id")))
    return label + (" (no onset)" if beat.get("via") == "expected" else "")


def _run_beats(run: dict) -> "list[dict]":
    for check in run.get("checks") or []:
        if isinstance(check, dict) and check.get("name") == "sync" and isinstance(check.get("measured"), dict):
            beats = check["measured"].get("beats")
            return [b for b in beats if isinstance(b, dict)] if isinstance(beats, list) else []
    return []


def _find_check(run: dict, name: str) -> Optional[dict]:
    return next((c for c in run.get("checks") or [] if isinstance(c, dict) and c.get("name") == name), None)


def _cuts_phrase(count: int) -> str:
    return "" if count == 1 else " in both cuts" if count == 2 else " in all %d cuts" % count


def _loudness_finding(version: Version) -> Optional[str]:
    rows = []
    for key, run in version.runs:
        check = _find_check(run, "loudness")
        if check and isinstance(check.get("measured"), dict) and "lufs" in check["measured"]:
            rows.append((key, check))
    if not rows:
        return None
    readings = {(c["measured"]["lufs"], c["measured"].get("true_peak_dbtp")) for _, c in rows}
    failed = any(c.get("status") == "fail" for _, c in rows)
    bar = threshold_text(rows[0][1])
    if len(readings) == 1:
        text = "Loudness is %s%s: %s." % ("off target" if failed else "on target", _cuts_phrase(len(rows)), measured_text(rows[0][1]))
    else:
        text = "Loudness is %s: %s." % (
            "off target" if failed else "on target",
            "; ".join("%s %s" % (version.run_label(k), measured_text(c)) for k, c in rows),
        )
    return text + (" The bar is %s." % bar if bar else "")


def _sync_finding(version: Version, words: "dict[str, str]") -> Optional[str]:
    per_run = [(key, _run_beats(run), _find_check(run, "sync")) for key, run in version.runs]
    per_run = [(k, b, c) for k, b, c in per_run if b and c]
    if not per_run:
        return None
    scored = [(abs(beat["offset_frames"]), key, beat) for key, beats, _ in per_run for beat in beats
              if isinstance(beat.get("offset_frames"), (int, float))]
    failed = any(c.get("status") == "fail" for _, _, c in per_run)
    count = max(len(b) for _, b, _ in per_run)
    limit = (per_run[0][2].get("threshold") or {}).get("offset_frames_max", 1) if isinstance(per_run[0][2].get("threshold"), dict) else 1
    if scored:
        worst = max(scored, key=lambda row: row[0])
        word = words.get(str(worst[2].get("id")), str(worst[2].get("id")))
    else:
        worst, word = (0, None, {}), ""
    if failed:
        text = "Sync is off: the worst beat, on \"%s\", is %s frames from its spoken word." % (word, _num(worst[0]))
    else:
        text = "All %d sync beats land within %s frames of their spoken word." % (count, _num(max(worst[0], 0)) if worst[0] else _num(limit))
    expected = []
    for _, beats, _ in per_run:
        for beat in beats:
            if beat.get("via") == "expected":
                label = words.get(str(beat.get("id")), str(beat.get("id")))
                if label not in expected:
                    expected.append(label)
    if expected:
        quoted = _join_words(['"%s"' % e for e in expected])
        text += " The beat%s on %s had no clear audio onset, so verify used the expected time there." % (
            "" if len(expected) == 1 else "s", quoted)
    return text


def _local_call_failed(rec: dict) -> bool:
    """hyperframes logs a process exit code (0 is ok); playwright logs an HTTP-style status (2xx is ok)."""
    status = rec.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        return False
    if rec.get("provider") == "playwright":
        return not 200 <= status < 300
    return status != 0


def _calls_finding(project: Path, brief: Any) -> str:
    records, bad = _read_calls(project)
    if not records:
        return "No outside calls were logged." if not bad else "No readable calls were logged."
    allowed = set(brief.get("cloud_allow") or []) if isinstance(brief, dict) else set()
    local = [r for r in records if r.get("provider") in LOCAL_PROVIDERS]
    remote = [r for r in records if r.get("provider") not in LOCAL_PROVIDERS]
    if not remote:
        names = _join_words(sorted({str(r.get("provider")) for r in local}))
        text = "Nothing left the machine. There were %d logged calls, every one to local tools (%s)." % (len(records), names)
    else:
        by_provider: "dict[str, int]" = {}
        for r in remote:
            key = str(r.get("provider"))
            by_provider[key] = by_provider.get(key, 0) + 1
        text = "There were %d logged calls, %d of them to outside services: %s." % (
            len(records), len(remote), ", ".join("%s (%d)" % (p, n) for p, n in sorted(by_provider.items())))
        blocked = sorted(p for p in by_provider if p not in allowed)
        if blocked:
            text += " Not allowed by the brief: %s." % ", ".join(blocked)
    odd = [r for r in local if _local_call_failed(r)]
    text += " %s failed." % _plural(len(odd), "local call", "local calls") if odd else ""
    return text


def _attempt_findings(version: Version) -> "list[str]":
    lines = []
    for key, run in version.runs:
        attempts = run.get("attempts")
        who = "the %s cut" % version.run_label(key) if key else version.name
        if isinstance(attempts, list) and attempts:
            steps = ", ".join(
                "attempt %s %s" % (a.get("n", n + 1), "passed" if a.get("passed") else "failed")
                for n, a in enumerate(a for a in attempts if isinstance(a, dict))
            )
            lines.append("Verify history for %s: %s." % (who, steps))
        elif run.get("attempt") is not None:
            lines.append("Verify history for %s: attempt %s %s." % (who, run["attempt"], "passed" if run.get("passed") else "failed"))
    return lines


def render_findings(project: Path, version: Version, brief: Any) -> str:
    bullets: "list[str]" = []
    for key, run in version.runs:
        for check in version.failing(run):
            where = "the %s cut" % version.run_label(key) if key else version.name
            bullets.append("%s failed %s: %s" % (where[:1].upper() + where[1:], _check_label(check.get("name")), measured_text(check)))
    if version.runs:
        words = _beat_words(project)
        for line in (_loudness_finding(version), _sync_finding(version, words)):
            if line:
                bullets.append(line)
    else:
        bullets.append(version.plain_verdict())
    bullets.append(_calls_finding(project, brief))
    bullets.extend(_attempt_findings(version))
    return "<ul>\n%s\n</ul>" % "\n".join("  <li>%s</li>" % esc(b) for b in bullets)


# scenes section --------------------------------------------------------------------------------


def render_scenes(storyboard: Optional[str], scenes: "Optional[list[Scene]]", version: Version) -> str:
    if storyboard is None:
        return '<p class="missing"><strong>Missing:</strong> storyboard.md.</p>'
    if scenes is None:
        shift = _shift_to_h3(storyboard)
        return "<p>storyboard.md has no scene table with a Time column, so it is shown as written.</p>\n%s" % render_markdown(storyboard, shift)
    pick = ""
    if len(version.mp4s) >= 2:
        radios = "\n  ".join(
            '<label><input type="radio" name="cut" value="cut-%d"%s> the %s cut</label>'
            % (n, " checked" if n == 0 else "", esc(version.labels[m.name]))
            for n, m in enumerate(version.mp4s)
        )
        pick = '<fieldset class="pick">\n  <legend>Play buttons start</legend>\n  %s\n</fieldset>\n' % radios
    has_words = any(s.words for s in scenes)
    rows = []
    for scene in scenes:
        start = '<span class="start">%s s</span>' % esc(scene.start) if scene.start is not None else ""
        button = ""
        if scene.start is not None:
            button = '<button type="button" class="seek" data-seek="%s">Play %s from %s s</button>' % (
                esc(scene.start), esc(scene.scene_id), esc(scene.start))
        words = _inline(scene.words)
        cell = words + ("<br>" if words and button else "") + button
        rows.append('<tr><th scope="row">%s%s</th>%s</tr>' % (
            esc(scene.label), start, "<td>%s</td>" % cell if has_words or button else "<td></td>"))
    intro = (
        "<p>Start times come from storyboard.md. A play button jumps to the start of its scene.</p>\n"
        if any(s.start is not None for s in scenes) else ""
    )
    status = '<p id="seek-status" class="q-meta" aria-live="polite"></p>\n' if intro else ""
    return (
        '%s%s<div class="q-table-wrap">\n  <table>\n    <caption>The %d scenes, with start times on the film timeline%s</caption>\n'
        '    <thead><tr><th scope="col">Scene and start</th><th scope="col">%s</th></tr></thead>\n'
        "    <tbody>\n      %s\n    </tbody>\n  </table>\n</div>\n%s"
        % (intro, pick, len(scenes), " and the words with each" if has_words else "",
           "Script and play" if has_words else "Play", "\n      ".join(rows), status)
    )


# verify results ---------------------------------------------------------------------------------


def _chart(version: Version, words: "dict[str, str]") -> str:
    series = [(version.run_label(key), _run_beats(run), run) for key, run in version.runs]
    series = [(label, beats, run) for label, beats, run in series if beats][:8]
    if not series:
        return ""
    order: "list[str]" = []
    labels: "dict[str, str]" = {}
    for _, beats, _ in series:
        for beat in beats:
            bid = str(beat.get("id"))
            if bid not in labels:
                order.append(bid)
                labels[bid] = _beat_label(words, beat)
            elif beat.get("via") == "expected":
                labels[bid] = _beat_label(words, beat)

    def offsets(beats: "list[dict]") -> "dict[str, Any]":
        return {str(b.get("id")): b.get("offset_frames") for b in beats}

    first = offsets(series[0][1])
    agree = all(offsets(b) == first for _, b, _ in series[1:])
    shown = series[:1] if agree else series
    values = [v for _, beats, _ in shown for v in offsets(beats).values() if isinstance(v, (int, float))]
    limit = 1
    check = _find_check(series[0][2], "sync")
    if check and isinstance(check.get("threshold"), dict) and isinstance(check["threshold"].get("offset_frames_max"), (int, float)):
        limit = check["threshold"]["offset_frames_max"]
    bound = max([limit] + [abs(v) for v in values])
    bound = bound if bound == int(bound) else float(int(bound) + 1)
    names = ["Offset (frames)"] if agree else [label for label, _, _ in shown]
    head = "".join("<th>%s</th>" % esc(n) for n in ["Beat word"] + names)
    body = []
    for bid in order:
        cells = "".join(
            "<td>%s</td>" % ("" if offsets(beats).get(bid) is None else esc(_num(offsets(beats)[bid]))) for _, beats, _ in shown
        )
        body.append("<tr><td>%s</td>%s</tr>" % (esc(labels[bid]), cells))
    worst = max([abs(v) for v in values] or [0])
    expected = sorted({labels[b] for _, beats, _ in series for b in [str(x.get("id")) for x in beats if x.get("via") == "expected"]})
    summary = "%s beats %s the %s-frame bar; the largest offset is %s frames.%s" % (
        len(order), "stay inside" if worst <= limit else "go past", _num(limit), _num(worst),
        " Beats marked (no onset) use the expected time, not a measurement." if expected else "")
    options = {
        "plugins": {"legend": {"display": not agree}},
        "scales": {"x": {"min": -bound, "max": bound,
                         "title": {"display": True, "text": "Frames from the spoken word, bar is +/-%s" % _num(limit)}}},
    }
    note = (
        "Every cut measured the same offsets." if agree and len(series) > 1
        else "" if agree else "The cuts measured different offsets, so each has its own series."
    )
    return (
        '<h3 id="sync-h">How close each beat landed</h3>\n'
        "<p>A beat is an on-screen change timed to a spoken word. A positive offset means the picture changed after the word started. %s</p>\n"
        '<q-chart type="bar" horizontal summary="%s" x="Beat word">\n  <table>\n    <thead><tr>%s</tr></thead>\n    <tbody>\n      %s\n    </tbody>\n  </table>\n'
        "  <script type=\"application/json\">%s</script>\n</q-chart>"
        % (esc(note), esc(summary), head, "\n      ".join(body), json.dumps(options).replace("<", "\\u003c"))
    )


def render_results(version: Version, project: Path) -> str:
    if not version.runs:
        return _missing_line(version.verify_gaps()) or "<p>No verify results yet.</p>"
    names: "list[str]" = []
    for _, run in version.runs:
        for check in run.get("checks") or []:
            if isinstance(check, dict) and str(check.get("name")) not in names:
                names.append(str(check.get("name")))
    if not names:
        return "\n".join(part for part in (_missing_line(version.verify_gaps()), "<p>verify.json lists no checks.</p>") if part)
    labels = [version.run_label(key) if key else "Result" for key, _ in version.runs]
    cols = "".join('<th scope="col">%s</th>' % esc(label) for label in labels)
    rows = []
    for name in names:
        cells, measured, bars = [], [], []
        for (key, run), label in zip(version.runs, labels):
            check = _find_check(run, name)
            if not check:
                cells.append('<td class="skip">No result</td>')
                continue
            status = str(check.get("status"))
            cells.append('<td class="%s">%s</td>' % (re.sub(r"[^a-z]", "", status.lower()) or "skip", esc(STATUS_WORDS.get(status, status.capitalize() or "Unknown"))))
            measured.append((label, measured_text(check)))
            bars.append((label, threshold_text(check)))
        rows.append("<tr><th scope=\"row\">%s</th>%s<td>%s</td><td>%s</td></tr>" % (
            esc(_check_label(name).capitalize()), "".join(cells), _by_cut(measured, len(version.runs)), _by_cut(bars, len(version.runs))))
    table = (
        '<div class="q-table-wrap">\n  <table>\n    <caption>The checks verify ran on each rendered MP4</caption>\n'
        '    <thead><tr><th scope="col">Check</th>%s<th scope="col">Measured</th><th scope="col">Bar</th></tr></thead>\n'
        "    <tbody>\n      %s\n    </tbody>\n  </table>\n</div>" % (cols, "\n      ".join(rows))
    )
    gaps = _missing_line(version.verify_gaps())
    return "\n".join(part for part in (gaps, table, _chart(version, _beat_words(project))) if part)


def _by_cut(pairs: "list[tuple[str, str]]", cuts: int) -> str:
    """One text when every cut agrees, else one line per cut."""
    texts = [t for _, t in pairs]
    if not texts:
        return ""
    if len(set(texts)) == 1:
        return esc(texts[0])
    return "<br>".join("%s: %s" % (esc(label), esc(text)) for label, text in pairs)


# frames -----------------------------------------------------------------------------------------

_STILL_TIME = re.compile(r"-(\d+(?:\.\d+)?)s$")


def _still_figure(project: Path, still: Path, scenes: "Optional[list[Scene]]", cut: str) -> str:
    match = _STILL_TIME.search(still.stem)
    if match:
        seconds = float(match.group(1))
        scene = scene_at(scenes, seconds) if scenes else None
        caption = "%s, %s s" % (scene.label, _num(seconds)) if scene else "%s s" % _num(seconds)
        alt = "%s frame%s at %s s" % (cut, " of scene %s" % scene.label if scene else "", _num(seconds))
    else:
        caption = still.name
        alt = "%s frame %s" % (cut, still.name)
    return '<figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>' % (
        rel_url(still, project), esc(alt), esc(caption))


def render_frames(project: Path, version: Version, scenes: "Optional[list[Scene]]") -> str:
    groups = version.frame_groups()
    if not groups:
        return "<p class=\"missing\"><strong>Missing:</strong> no stills.</p>"

    def body(group: FrameGroup) -> str:
        if not group.stills:
            return _missing_line([group.missing or "no stills"])
        figures = "\n      ".join(_still_figure(project, s, scenes, group.label) for s in group.stills)
        return "<q-grid>\n      %s\n    </q-grid>" % figures

    intro = "<p>Verify decoded these stills from the finished MP4s.</p>\n"
    if len(version.mp4s) >= 2 and len(groups) >= 2:
        panels = "\n".join("  <section>\n    <h3>%s frames</h3>\n    %s\n  </section>" % (esc(g.label), body(g)) for g in groups)
        return '%s<q-tabs label="Frames by cut">\n%s\n</q-tabs>' % (intro, panels)
    return intro + "\n".join(body(g) for g in groups)


# outside calls ----------------------------------------------------------------------------------


def render_calls(project: Path, brief: Any) -> str:
    records, bad = _read_calls(project)
    allowed = set(brief.get("cloud_allow") or []) if isinstance(brief, dict) else set()
    note = ""
    if bad:
        note = '<p class="missing"><strong>Note:</strong> %s in calls.jsonl.</p>\n' % _plural(bad, "unreadable line", "unreadable lines")
    if not records:
        return note + "<p>No outside calls were logged.</p>"
    stamps = sorted(str(r["ts"]) for r in records if r.get("ts"))
    span = " from %s to %s" % (stamps[0], stamps[-1]) if stamps else ""
    intro = "<p>%s</p>" % esc("%d calls logged%s. Cloud services allowed by the brief: %s." % (
        len(records), span, ", ".join(sorted(str(a) for a in allowed)) or "none"))
    groups: "dict[tuple[str, str], int]" = {}
    for rec in records:
        key = (str(rec.get("provider") or "unknown"), str(rec.get("subcommand") or rec.get("host") or "none"))
        groups[key] = groups.get(key, 0) + 1
    counts = "".join(
        '<tr><td>%s</td><td>%s</td><td class="num">%d</td></tr>' % (esc(p), esc(k), n) for (p, k), n in sorted(groups.items())
    )
    parts = [
        note + intro,
        '<div class="q-table-wrap">\n  <table>\n    <caption>Logged calls counted by provider and subcommand or host</caption>\n'
        '    <thead><tr><th scope="col">Provider</th><th scope="col">Subcommand or host</th><th scope="col" class="num">Calls</th></tr></thead>\n'
        "    <tbody>%s</tbody>\n  </table>\n</div>" % counts,
    ]
    remote = [r for r in records if r.get("provider") not in LOCAL_PROVIDERS]
    if remote:
        rows = []
        for rec in remote:
            flagged = rec.get("provider") not in allowed
            rows.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class=\"num\">%s</td><td class=\"%s\">%s</td></tr>" % (
                    esc(rec.get("ts")), esc(rec.get("provider") or "unknown"), esc(_what_ran(rec)), esc(rec.get("status")),
                    esc(rec.get("bytes")), "bad" if flagged else "", "not allowed" if flagged else "allowed")
            )
        parts.append(
            "<h3>Cloud and outside calls</h3>\n"
            '<div class="q-table-wrap">\n  <table>\n    <caption>Every call to a provider that is not a local tool</caption>\n'
            '    <thead><tr><th scope="col">Time</th><th scope="col">Provider</th><th scope="col">What ran</th>'
            '<th scope="col">Status</th><th scope="col" class="num">Bytes</th><th scope="col">Allowed</th></tr></thead>\n'
            "    <tbody>\n      %s\n    </tbody>\n  </table>\n</div>" % "\n      ".join(rows)
        )
    return "\n".join(parts)


# earlier versions and compare -------------------------------------------------------------------


def render_compare(project: Path, versions: "list[Version]") -> str:
    options = [(v, m) for v in versions for m in v.mp4s]
    if not options:
        return "<p>No version has an MP4 to compare yet.</p>"
    first = 0
    other = next((n for n, (v, _) in enumerate(options) if v.name != options[0][0].name), 1 if len(options) > 1 else 0)

    def pane(which: str, selected: int) -> str:
        opts = "".join(
            '<option value="%s"%s>%s</option>' % (rel_url(m, project), " selected" if n == selected else "", esc("%s / %s" % (v.name, m.name)))
            for n, (v, m) in enumerate(options)
        )
        src = rel_url(options[selected][1], project)
        return (
            '<div class="pane">\n  <label>%s cut <select data-target="cmp-%s">%s</select></label>\n'
            '  <video id="cmp-%s" controls preload="metadata" playsinline src="%s"></video>\n</div>'
            % (which.upper(), which, opts, which, src)
        )

    return "<h3>Compare two cuts</h3>\n<q-grid>\n%s\n%s\n</q-grid>" % (pane("a", first), pane("b", other))


def render_earlier(project: Path, older: "list[Version]", all_versions: "list[Version]") -> str:
    parts = []
    for v in older:
        gaps = _missing_line(v.missing())
        notes = (v.dir / "review-notes.md")
        notes_link = ' <a href="%s">The agent\'s notes for %s</a>.' % (rel_url(notes, project), esc(v.name)) if notes.is_file() else ""
        verify_link = (
            '<a href="%s">Raw verify results for %s</a>.' % (rel_url(v.dir / "verify.json", project), esc(v.name))
            if (v.dir / "verify.json").is_file() else ""
        )
        parts.append("\n".join(p for p in (
            '<h3 id="%s-h">%s</h3>' % (esc(v.name), esc(v.name)),
            "<p>%s</p>" % _verdict_html(v),
            _players(project, v, False),
            gaps,
            "<p>%s%s</p>" % (verify_link, notes_link) if verify_link or notes_link else "",
        ) if p))
    parts.append(render_compare(project, all_versions))
    return "\n".join(parts)


# files and method -------------------------------------------------------------------------------


def render_files(project: Path, version: Optional[Version], all_versions: "list[Version]") -> str:
    items: "list[tuple[Path, str]]" = []
    for name, label in (("brief.json", "The brief"), ("storyboard.md", "The storyboard"), ("sources.md", "Sources")):
        if (project / name).is_file():
            items.append((project / name, "%s (%s)" % (label, name)))
    for path in sorted(project.glob("beats*.json")):
        items.append((path, "Sync beats (%s)" % path.name))
    if (project / "calls.jsonl").is_file():
        items.append((project / "calls.jsonl", "The outside-calls log (calls.jsonl)"))
    for v in all_versions[:1]:
        for path, label in ((v.dir / "verify.json", "Raw verify results for %s" % v.name), (v.dir / "review-notes.md", "The agent's notes for %s" % v.name)):
            if path.is_file():
                items.append((path, "%s (%s/%s)" % (label, v.name, path.name)))
        for path in sorted(v.dir.glob("*.log")):
            items.append((path, "Render log (%s/%s)" % (v.name, path.name)))
    if not items:
        return "<p>No project files to list yet.</p>"
    return "<ul>\n%s\n</ul>" % "\n".join('  <li><a href="%s">%s</a></li>' % (rel_url(p, project), esc(t)) for p, t in items)


def render_method(project: Path, version: Optional[Version], brief_ok: bool, story_ok: bool) -> str:
    used = ["verify.json"] if version and version.runs else []
    has_note = bool(version and (version.note_verdict is not None or version.note_rest))
    used += [n for n, ok in (("review-notes.md", has_note),
                              ("calls.jsonl", (project / "calls.jsonl").is_file()),
                              ("the beats files", bool(list(project.glob("beats*.json")))),
                              ("storyboard.md", story_ok), ("brief.json", brief_ok)) if ok]
    sources = _join_words(["<code>%s</code>" % esc(u) if u.endswith((".json", ".md", ".jsonl")) else esc(u) for u in used]) or "the project files"
    return (
        "<p>This page was generated from %s. The findings and the verify results are read from verify.json; "
        "the checklist is the agent's own frame review. The frames are verify's own stills, and the contact sheet it also writes is not shown. "
        "Links are relative to the project folder, so keep this page there for the videos and images to load. "
        "The source is <code>review.src.html</code>, built with the writing-html-artifacts skill.</p>" % sources
    )


# page -------------------------------------------------------------------------------------------

CSS = """<style>
.cut { margin: 0; }
.cut video { display: block; width: 100%; height: auto; background: var(--q-color-text); border-radius: var(--q-radius-sm); }
.cut video.tall { max-height: 80vh; width: auto; max-inline-size: 100%; }
.pane video { display: block; width: 100%; max-height: 70vh; background: var(--q-color-text); border-radius: var(--q-radius-sm); }
.pane label { display: block; margin-bottom: var(--q-space-2); }
.pick { border: 1px solid var(--q-color-border); border-radius: var(--q-radius-md); padding: var(--q-space-2) var(--q-space-4); display: flex; flex-wrap: wrap; gap: var(--q-space-2) var(--q-space-6); }
.pick label { display: inline-flex; align-items: center; gap: var(--q-space-2); min-height: 44px; }
.missing { border: 1px solid var(--q-color-warn); border-radius: var(--q-radius-md); padding: var(--q-space-2) var(--q-space-4); }
td.pass { color: var(--q-color-good); font-weight: 600; }
td.fail, td.bad { color: var(--q-color-critical); font-weight: 600; }
td.skip { color: var(--q-color-text-muted); }
.seek { min-height: 44px; margin: var(--q-space-2) 0 0; }
.start { display: block; font-weight: 400; font-size: var(--q-size-small); color: var(--q-color-text-muted); font-variant-numeric: tabular-nums; }
figure img { display: block; width: 100%; height: auto; border: 1px solid var(--q-color-border); border-radius: var(--q-radius-sm); }
figcaption { font-size: var(--q-size-small); color: var(--q-color-text-muted); }
</style>"""

SEEK_JS = """<script>
window.addEventListener("load", function () {
  var status = document.getElementById("seek-status");
  function chosen() {
    var radio = document.querySelector('input[name="cut"]:checked');
    return radio ? radio.value : "cut-0";
  }
  document.querySelectorAll("button.seek").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var pick = chosen();
      var t = parseFloat(btn.dataset.seek);
      document.querySelectorAll("video[data-cut]").forEach(function (v) {
        if (v.id === pick) { v.currentTime = t; v.play().catch(function () {}); } else { v.pause(); }
      });
      var player = document.getElementById(pick);
      if (!player) { return; }
      player.scrollIntoView({block: "nearest"});
      status.textContent = player.dataset.cut + " cut playing from " + t + " s.";
    });
  });
});
</script>"""

COMPARE_JS = """<script>
window.addEventListener("load", function () {
  document.querySelectorAll("select[data-target]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var v = document.getElementById(sel.getAttribute("data-target"));
      v.src = sel.value;
      v.load();
    });
  });
});
</script>"""


def _header_line(header: dict) -> str:
    """The source header as one HTML comment line; ``<``, ``>`` and ``&`` cannot close the comment."""
    text = json.dumps(header, ensure_ascii=False)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    text = text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "<!-- quirk-src %s -->" % text


def build_source(project: Path) -> str:
    """The ``report`` source for the project's review page."""
    brief, brief_reason = _read_json(project / "brief.json")
    storyboard = _read_text(project / "storyboard.md")
    scenes = parse_scenes(storyboard) if storyboard else None
    versions = [Version(project, d) for d in _version_dirs(project)]
    newest = versions[0] if versions else None

    base = brief.get("title") if isinstance(brief, dict) and brief.get("title") else "Video review"
    title = "%s, %s review" % (base, newest.name) if newest else "%s, no versions yet" % base

    interactions = []
    has_scene_buttons = bool(scenes) and any(s.start is not None for s in scenes)
    if newest and newest.mp4s:
        interactions.append("play each cut in its own player")
    if has_scene_buttons:
        interactions.append("jump to a scene from the scene table")
        if newest and len(newest.mp4s) >= 2:
            interactions.append("choose which cut a scene jump plays")
    if newest and len(newest.mp4s) >= 2 and len(newest.frame_groups()) >= 2:
        interactions.append("switch the frames between cuts")
    comparing = len(versions) >= 2 and any(v.mp4s for v in versions)
    if comparing:
        interactions.append("compare two cuts from any version side by side")

    out = [
        _header_line({"template": "report", "title": title, "layout": "explainer", "mode": "offline", "interactions": interactions}),
        "<!-- slot: summary -->",
    ]
    if newest is None:
        out.append('<p class="q-lede">There is no version folder in this project yet, so there is nothing to review.</p>')
    else:
        out.append(_summary(newest))
    out.append("<!-- slot: main -->")
    out.append(_meta(project, brief))
    gaps = []
    if brief_reason:
        gaps.append("brief.json %s" % ("is missing" if brief_reason == "missing" else brief_reason))
    if storyboard is None:
        gaps.append("storyboard.md is missing")
    if newest is None:
        gaps.append("no versions (vN folders)")
    out.append(_missing_line(gaps))

    if newest:
        out.append(_section("findings", "Findings", render_findings(project, newest, brief)))
        watch = _players(project, newest, True) or _missing_line(["no MP4"])
        out.append(_section("watch", "Watch", watch))
        out.append(_section("scenes", "Scenes", render_scenes(storyboard, scenes, newest)))
        if newest.note_verdict is not None or newest.note_rest:
            rest = newest.note_rest or ""
            check = render_markdown(rest, 2) if rest.strip() else "<p>Nothing beyond the checks.</p>"
            check = '<p>This is the agent\'s own look at the frames. Source: <a href="%s">%s/review-notes.md</a>.</p>\n%s' % (
                rel_url(newest.dir / "review-notes.md", project), esc(newest.name), check)
        else:
            check = "<p>The agent's frame review for %s isn't written yet.</p>" % esc(newest.name)
        out.append(_section("look", "What I would check before signing off", check))
        out.append(_section("checks", "Verify results", render_results(newest, project)))
        out.append(_section("frames", "Frames", render_frames(project, newest, scenes)))
    out.append(_section("calls", "Outside calls", render_calls(project, brief)))
    if len(versions) >= 2:
        out.append(_section("earlier", "Earlier versions", render_earlier(project, versions[1:], versions)))
    out.append(_section("files", "Files", render_files(project, newest, versions)))
    out.append(_section("method", "How this page was built", render_method(project, newest, brief_reason is None, storyboard is not None)))
    out.append(CSS)
    if has_scene_buttons:
        out.append(SEEK_JS)
    if comparing:
        out.append(COMPARE_JS)
    return "\n".join(part for part in out if part) + "\n"


# building ---------------------------------------------------------------------------------------


def run_builder(project: Path, source: Path, page: Path) -> "tuple[int, Optional[dict], str]":
    """Run the sibling builder; returns its exit code, its JSON object (or None) and a stderr tail."""
    skills = Path(__file__).resolve().parents[2]
    builder = skills / "writing-html-artifacts" / "scripts" / "quirk_html.py"
    if not builder.is_file():
        return -1, None, "the writing-html-artifacts builder is missing: %s" % builder
    cmd = [sys.executable, str(builder), "build", str(source), "--out", str(page), "--project-dir", str(project)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=BUILDER_TIMEOUT_S, env=scrubbed_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, None, "could not run %s: %s" % (builder.name, type(exc).__name__)
    try:
        data = json.loads(proc.stdout.strip())
    except ValueError:
        data = None
    return proc.returncode, data if isinstance(data, dict) else None, proc.stderr.strip()[-300:]


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = _Parser(description="Build review.html for a making-videos project.")
    parser.add_argument("--project", required=True, help="project folder")
    args = parser.parse_args(argv)
    project = Path(args.project).expanduser()
    if not project.is_dir():
        emit({"error": "project directory not found: %s" % project}, EXIT_USAGE)
    source, page = project / "review.src.html", project / "review.html"
    try:
        source.write_text(build_source(project), encoding="utf-8")
    except OSError as exc:
        emit({"error": "%s: %s" % (type(exc).__name__, exc)}, EXIT_FAILED)

    code, data, stderr = run_builder(project, source, page)
    base = {"source": str(source)}
    if code == -1:
        emit(dict(base, error=stderr), EXIT_FAILED)
    if data is None:
        emit(dict(base, error="the html builder printed no JSON (exit %d): %s" % (code, stderr)), EXIT_FAILED)
    if code == 2:
        emit(dict(base, error="the html builder rejected the source: %s" % data.get("error", stderr)), EXIT_FAILED)
    checks = data.get("checks")
    if code == 1:
        found = []
        for failure in (checks or {}).get("failures", []):
            if isinstance(failure, dict):
                found.append(": ".join(str(failure[k]) for k in ("check", "detail") if failure.get(k)))
            else:
                found.append(str(failure))
        emit(dict(base, error="static checks failed: %s" % ("; ".join(found) or "see checks"), page=str(page), checks=checks), EXIT_FAILED)
    if code != 0 or not isinstance(checks, dict):
        emit(dict(base, error="the html builder exited %d without a checks report: %s" % (code, stderr)), EXIT_FAILED)
    emit({"page": str(page), "source": str(source), "checks": checks})


if __name__ == "__main__":
    sys.exit(main())
