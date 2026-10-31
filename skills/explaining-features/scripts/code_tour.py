#!/usr/bin/env python3
"""Turn a tour.json and the narration clips into a code-tour film, and prove the code on screen is the code at the commit.

Usage: code_tour.py {lines,build,check} --project P

The agent writes ``P/tour.json``: a repo, a commit, a title and scenes. A map scene names 2 to 4 files with
``lit`` node indexes on its lines; a stop scene shows ``rows`` of one file (line numbers, or ``{"skip", "from",
"to"}`` for lines left out) with ``highlight`` line numbers on its lines. Every narration line carries a ``source``.

- ``lines`` writes ``P/assets/lines.json``, one clip per narration line (``l01``, ``l02``, ...) with ``start_s`` 0.
  It validates the tour and never touches git. Prints ``{"lines": N}``.
- ``build`` needs ``P/scenes/index.html`` (``hf.py init``) and ``P/assets/voice/<id>.wav`` for every line. It reads
  the code with ``git show <commit>:<path>``, times the scenes from the measured wav lengths on a 1/30 s grid (0.3 s
  lead, 0.35 s between lines, 0.8 s between scenes, 2.5 s hold), writes the compositions, the index body, the voice
  copies, ``beats.json``, ``sources.md``, ``storyboard.md`` and ``kit/kit.md``, then runs ``check`` on what it wrote.
  The display and mono fonts come from the product's brand (``brief.json`` names the product, ``brands/<product>/
  brand.json`` under ``$QUIRK_STUDIO`` or ``~/Studio`` the families); the colours are the tour's own.
  Prints ``{"scenes", "beats", "film_s", "stops": [{"stop", "rows"}]}``.
- ``check`` compares the compositions with ``tour.json`` and the source at the commit: every stop must be on screen
  with exactly the lines and skip rows ``tour.json`` gives it, and each of its lines must match the source.
  Prints ``{"commit", "checked", "mismatches": [{"scene", "line", "screen", "source", "reason"}]}``.

Code is shown with tabs expanded to 4 spaces, a trailing carriage return dropped and the common leading whitespace
of the stop's rows removed; ``build`` and ``check`` apply the same rule. The tokenizer only wraps runs of text in
spans, so it can colour comments, strings and keywords but never change a character. A line wider than 72 cells (a
wide East Asian character is 2 cells, anything else 1) wraps onto extra rows at the last space that fits, and mid-word
only where a word is longer than a row; the blocks join back to the source line exactly.

Exit 0 ok. Exit 1 a tour that can't ship: a commit that doesn't resolve, a path or line missing at it, a mismatch, a
stop missing or incomplete on screen, a check that saw 0 lines, a brand font the tour can't load, a cut that removes non-whitespace, a stop over MAX_ROWS rows after wrapping (13 with a
label), a film of 90 s or more, a narration line with no source, or a highlight on a line the stop doesn't show.
Exit 2 for a usage error, a bad tour.json or brand font, or a missing input, naming the command that makes it. Exit 3 when git is
missing. One JSON object goes to stdout and diagnostics to stderr; the script never prompts.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import wave
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, NoReturn, Optional, Tuple

EXIT_OK = 0
EXIT_CANT_SHIP = 1
EXIT_BAD_INPUT = 2
EXIT_NO_GIT = 3

FPS = 30
LEAD_S = 0.3
LINE_GAP_S = 0.35
SCENE_GAP_S = 0.8
HOLD_S = 2.5
FILM_LIMIT_S = 90
MAX_ROWS = 14
MAX_ROWS_LABELLED = MAX_ROWS - 1
CHARS_PER_ROW = 72
TAB = "    "

ROW_H = 52
CARD_TOP = 184
CARD_BORDER = 2
CARD_PAD = 14
FIRST_ROW_Y = CARD_TOP + CARD_BORDER + CARD_PAD
BAR_X = 98
BAR_W = 8
LABEL_REGION = [96, 900, 1728, 120]
MAP_TOP = 470
MAP_GAP = 84
MAP_WIDTH = 1728
MAX_LINE_NUMBER = 9999
MAX_PATH = 80
MAX_HEADING = 50
# a row keeps one character spare, because a fallback CJK face measured 1.005 em and a full row spilled onto the next
TITLE_FIT = (MAP_WIDTH // 96 - 1, 3)
LABEL_FIT = (MAP_WIDTH // 48 - 1, 2)
MAX_NODE_NAME = 24
MAX_NODE_FILE = 32

MAKING_VIDEOS = Path(__file__).resolve().parents[2] / "making-videos" / "scripts"

PALETTE = """      --ground: #101114;
      --surface: #16171b;
      --selected: #2c3050;
      --border: #24262c;
      --text: #eceef2;
      --muted: #9aa0ab;
      --accent: #9aa6ff;
      --string: #c6cbe8;"""

ROLES = ("display", "mono")
DEFAULT_FAMILIES = {"display": "Inter", "mono": "JetBrains Mono"}
BUNDLED_FONTS = frozenset((
    "Inter", "Montserrat", "Outfit", "Nunito", "Oswald", "League Gothic", "Archivo Black", "Space Mono", "IBM Plex Mono",
    "JetBrains Mono", "EB Garamond", "Playfair Display", "Source Code Pro", "Noto Sans JP", "Roboto", "Open Sans", "Lato",
    "Poppins",
))
FAMILY_NAME = re.compile(r"[A-Za-z0-9 _-]+")
FONT_FILE_NAME = re.compile(r"[A-Za-z0-9._ -]+")

BASE_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    #root { position: relative; width: 1920px; height: 1080px; background: var(--ground); color: var(--text); font-family: var(--font-display); overflow: hidden; }
    .mono { font-family: var(--font-mono); font-variant-ligatures: none; font-size: 36px; line-height: 1.3; }
    .stop { position: absolute; left: 96px; top: 60px; width: 1100px; color: var(--accent); font-weight: 600; white-space: pre; }
    .commit { position: absolute; right: 96px; top: 60px; width: 500px; text-align: right; color: var(--muted); white-space: pre; }
    .path { position: absolute; left: 96px; top: 110px; width: 1728px; color: var(--text); white-space: pre; }
    .card { position: absolute; left: 96px; top: 184px; width: 1728px; background: var(--surface); border: 2px solid var(--border); border-radius: 14px; padding: 14px 0; }
    .row { position: relative; display: flex; padding: 0 28px; }
    .band { position: absolute; inset: 0; background: var(--selected); border-left: 6px solid var(--accent); opacity: 0; }
    .num { position: relative; flex: 0 0 104px; color: var(--muted); font-family: var(--font-mono); font-size: 36px; line-height: 52px; }
    .txt { position: relative; flex: 1 1 auto; min-width: 0; font-family: var(--font-mono); font-variant-ligatures: none; font-size: 36px; line-height: 52px; }
    .w { display: block; white-space: pre; min-height: 52px; }
    .skip { color: var(--muted); font-style: italic; }
    .k { color: var(--accent); }
    .s { color: var(--string); }
    .c { color: var(--muted); }
    .label { position: absolute; left: 96px; top: 900px; width: 1728px; font-size: 48px; font-weight: 600; line-height: 1.25; color: var(--text); }
"""

MAP_CSS = """
    .title { position: absolute; left: 96px; top: 110px; width: 1728px; font-size: 96px; font-weight: 700; line-height: 1.1; text-wrap: balance; }
    .nodes { position: absolute; left: 96px; top: 470px; width: 1728px; display: flex; align-items: stretch; }
    .node { position: relative; min-height: 300px; background: var(--surface); border: 2px solid var(--border); border-radius: 14px; padding: 36px; }
    .node h3 { font-size: 48px; font-weight: 600; line-height: 1.2; margin-bottom: 24px; }
    .node p { color: var(--muted); overflow-wrap: anywhere; }
    .pip { position: absolute; left: 0; top: 16px; bottom: 16px; width: 8px; background: var(--accent); border-radius: 4px; opacity: 0; }
    .arrow { flex: 0 0 64px; align-self: center; position: relative; height: 4px; margin: 0 10px; background: var(--muted); }
    .arrow::after { content: ""; position: absolute; right: -2px; top: -8px; border-left: 16px solid var(--muted); border-top: 10px solid transparent; border-bottom: 10px solid transparent; }
"""

KIT = """# Scene kit

Tokens (inlined as a `:root` block in every composition; the fonts come from the product's brand, the colours are the tour's own): ground #101114, surface #16171b, selected #2c3050, border #24262c, text #eceef2, muted #9aa0ab, accent #9aa6ff, string #c6cbe8, display {display}, mono {mono}.

Motion roles: highlight move 0.2 s `power2.out`, starting on the frame of its narration line; label enter 0.35 s `power3.out` with a 16 px rise; hard cuts between scenes; no exits, stagger or overshoot.

Components: map node with a lit bar, arrow, stop line, commit line, path line, code card with line numbers, highlight band with an accent bar, skip row that names the skipped lines, bottom label.

Type scale (1920x1080): 96 px title, 48 px labels and node names, 36 px code and metadata. Code is 36 px on 52 px rows with ligatures off, 72 cells to a row (a wide character is 2 cells); longer lines wrap onto extra rows at the last space that fits, or mid-word only where a word is longer than a row. A stop shows at most 14 rows, 13 with a label.
"""


def _fail(code: int, message: str, **extra: Any) -> NoReturn:
    print(f"code_tour.py: {message}", file=sys.stderr)
    print(json.dumps({"error": message, **extra}))
    sys.exit(code)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(f"code_tour.py: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def _cells(text: str) -> int:
    """How many monospace cells ``text`` takes on screen: a wide or fullwidth East Asian character is 2, anything else 1."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pieces(word: str) -> List[str]:
    """The parts of a word a browser can put on different rows: it breaks only between two wide East Asian characters."""
    out = [word[0]]
    for c in word[1:]:
        if _cells(c) == 2 and _cells(out[-1][-1]) == 2:
            out.append(c)
        else:
            out[-1] += c
    return out


def _rows_needed(text: str, per_row: int) -> Optional[int]:
    """The rows ``text`` can take in a box ``per_row`` characters wide, counting every character as the font's widest.

    Wraps greedily at spaces, so the answer bounds any font. ``None`` when a part can't break and is longer than a row,
    because it would run off the frame instead of wrapping.
    """
    rows, used = 1, 0
    for word in re.findall(r"[^ \t\r\n\f]+", text):
        for n, piece in enumerate(_pieces(word)):
            if len(piece) > per_row:
                return None
            gap = 1 if used and n == 0 else 0
            if used + gap + len(piece) > per_row:
                rows, used = rows + 1, len(piece)
            else:
                used += gap + len(piece)
    return rows


# tour.json ---------------------------------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bad(where: str, message: str) -> NoReturn:
    _fail(EXIT_BAD_INPUT, f"tour.json {where}: {message}")


def _text_field(obj: Dict[str, Any], key: str, where: str, limit: Optional[int] = None, required: bool = True, fit: Optional[Tuple[int, int]] = None) -> Optional[str]:
    """The text at ``key``. ``limit`` caps its width in cells; ``fit`` is (characters per row, rows) it must wrap into."""
    value = obj.get(key)
    if value is None and not required:
        return None
    if not _is_text(value):
        _bad(where, f"{key!r} must be non-empty text")
    if limit is not None and _cells(value) > limit:
        _bad(where, f"{key!r} is {_cells(value)} cells wide; the screen has room for {limit}")
    if fit is not None:
        rows = _rows_needed(value, fit[0])
        if rows is None or rows > fit[1]:
            _bad(where, f"{key!r} could take more rows than the screen has ({fit[1]} rows of {fit[0]} characters, counting each as the font's widest); shorten it")
    return value


def _int_list(value: Any, where: str, key: str) -> List[int]:
    if not isinstance(value, list) or not value or not all(_is_int(v) for v in value):
        _bad(where, f"{key!r} must be a non-empty list of whole numbers")
    return value


def _parse_rows(rows: Any, where: str) -> List[Tuple[Any, ...]]:
    """Rows as ``("line", n)`` or ``("skip", note, first, last)``, each starting where the one before ended."""
    if not isinstance(rows, list) or not rows:
        _bad(where, "'rows' must be a non-empty list")
    out: List[Tuple[Any, ...]] = []
    expect: Optional[int] = None
    for item in rows:
        if _is_int(item):
            first = last = item
            row: Tuple[Any, ...] = ("line", item)
        elif isinstance(item, dict) and _is_text(item.get("skip")) and _is_int(item.get("from")) and _is_int(item.get("to")):
            first, last = item["from"], item["to"]
            if first > last:
                _bad(where, f"skip {item['skip']!r} runs from {first} down to {last}")
            row = ("skip", item["skip"], first, last)
        else:
            _bad(where, f"row {item!r} must be a line number or {{\"skip\", \"from\", \"to\"}}")
        if first < 1 or last > MAX_LINE_NUMBER:
            _bad(where, f"line numbers must be between 1 and {MAX_LINE_NUMBER}, not {first}-{last}")
        if expect is not None and first != expect:
            _bad(where, f"row {first} doesn't follow line {expect - 1}; mark the gap with a skip")
        expect = last + 1
        out.append(row)
    if not any(r[0] == "line" for r in out):
        _bad(where, "a stop must show at least one line")
    return out


def _line_numbers(rows: List[Tuple[Any, ...]]) -> List[int]:
    """The line numbers a stop shows as code rows, in order. ``build`` lays them out and ``check`` expects exactly these on screen."""
    return [r[1] for r in rows if r[0] == "line"]


def _skip_span(first: int, last: int) -> str:
    return f"{first}-{last}"


def _structure(tour: Any) -> Dict[str, Any]:
    if not isinstance(tour, dict):
        _bad("", "must be a JSON object")
    repo = tour.get("repo")
    if not _is_text(repo) or not os.path.isabs(repo):
        _bad("", "'repo' must be an absolute path")
    _text_field(tour, "commit", "")
    _text_field(tour, "title", "", fit=TITLE_FIT)
    scenes = tour.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        _bad("", "'scenes' must be a non-empty list")
    stops = 0
    for index, scene in enumerate(scenes, 1):
        where = f"scene s{index}"
        if not isinstance(scene, dict):
            _bad(where, "must be an object")
        _text_field(scene, "label", where, required=False, fit=LABEL_FIT)
        if "map" in scene:
            nodes = scene["map"]
            if not isinstance(nodes, list) or not 2 <= len(nodes) <= 4:
                _bad(where, "'map' must name 2 to 4 files")
            for node in nodes:
                if not isinstance(node, dict):
                    _bad(where, "each map node needs a 'name' and a 'file'")
                _text_field(node, "name", where, MAX_NODE_NAME)
                _text_field(node, "file", where, MAX_NODE_FILE)
            mark = "lit"
        elif "stop" in scene:
            stops += 1
            _text_field(scene, "stop", where)
            _text_field(scene, "path", where, MAX_PATH)
            scene["_rows"] = _parse_rows(scene.get("rows"), where)
            mark = "highlight"
        else:
            _bad(where, "needs 'map' (a map scene) or 'stop' and 'path' (a stop scene)")
        lines = scene.get("lines")
        if not isinstance(lines, list) or not lines or not all(isinstance(l, dict) for l in lines):
            _bad(where, "'lines' must be a non-empty list of narration lines")
        for line in lines:
            _text_field(line, "text", where)
            other = "highlight" if mark == "lit" else "lit"
            if other in line:
                _bad(where, f"a {'map' if mark == 'lit' else 'stop'} scene takes {mark!r}, not {other!r}")
            if mark in line:
                _int_list(line[mark], where, mark)
    for scene in scenes:
        if "stop" in scene:
            heading = f"STOP {stops} OF {stops} · {scene['stop']}"
            if _cells(heading) > MAX_HEADING:
                _bad("scene", f"stop {scene['stop']!r} is too long for the heading; the screen has room for {MAX_HEADING} cells with its STOP n OF N prefix")
    return tour


def _semantics(tour: Dict[str, Any]) -> None:
    """The checks that make a tour unshippable rather than malformed: a line with no source, a highlight off screen."""
    for index, scene in enumerate(tour["scenes"], 1):
        sid = f"s{index}"
        shown = set(_line_numbers(scene.get("_rows", [])))
        for line in scene["lines"]:
            source = line.get("source")
            if not _is_text(source):
                _fail(EXIT_CANT_SHIP, f"scene {sid}: the narration line {line['text']!r} has no source; cite a file and line, a commit or a spec")
            if "map" in scene:
                for node in line.get("lit", []):
                    if not 0 <= node < len(scene["map"]):
                        _fail(EXIT_CANT_SHIP, f"scene {sid}: the line {line['text']!r} lights node {node}, and the map has {len(scene['map'])}")
            else:
                for number in line.get("highlight", []):
                    if number not in shown:
                        _fail(EXIT_CANT_SHIP, f"scene {sid} (stop {scene['stop']!r}): the line {line['text']!r} highlights line {number}, which the stop doesn't show")


def _load_tour(project: Path) -> Dict[str, Any]:
    if not project.is_dir():
        _fail(EXIT_BAD_INPUT, f"{project} is not a folder; pass the film's project folder with --project")
    path = project / "tour.json"
    if not path.is_file():
        _fail(EXIT_BAD_INPUT, f"{path} is missing; write the tour there first")
    try:
        tour = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(EXIT_BAD_INPUT, f"cannot read {path}: {exc}")
    return _structure(tour)


class Narration:
    """One narration line with the scene it belongs to and the highlight or lit nodes it moves."""

    def __init__(self, clip: str, scene: int, last: bool, data: Dict[str, Any], marks: Optional[List[int]]) -> None:
        self.clip = clip
        self.scene = scene
        self.last = last
        self.text = data["text"]
        self.source = data["source"].strip() if isinstance(data.get("source"), str) else ""
        self.marks = marks


def _narration(tour: Dict[str, Any]) -> List[Narration]:
    out: List[Narration] = []
    for index, scene in enumerate(tour["scenes"]):
        key = "lit" if "map" in scene else "highlight"
        for n, data in enumerate(scene["lines"]):
            out.append(Narration(f"l{len(out) + 1:02d}", index, n == len(scene["lines"]) - 1, data, data.get(key)))
    return out


# git ---------------------------------------------------------------------------------------------------------


def _git(repo: str, *args: str) -> "subprocess.CompletedProcess[bytes]":
    # an inherited GIT_DIR from a hook would point git at the wrong repository
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, env=env)
    except OSError as exc:
        _fail(EXIT_NO_GIT, f"cannot run git: {exc}")


def _resolve(repo: str, commit: str) -> str:
    done = _git(repo, "rev-parse", "--verify", "--end-of-options", commit + "^{commit}")
    sha = done.stdout.decode("utf-8", "replace").strip()
    if done.returncode != 0 or not sha:
        detail = done.stderr.decode("utf-8", "replace").strip()
        _fail(EXIT_CANT_SHIP, f"commit {commit!r} does not resolve in {repo}" + (f": {detail}" if detail else ""))
    return sha


def _normalize(line: str) -> str:
    return (line[:-1] if line.endswith("\r") else line).replace("\t", TAB)


class Sources:
    """Source files at one commit, read once each with ``git show`` and normalized the way the screen shows them."""

    def __init__(self, repo: str, sha: str) -> None:
        self.repo = repo
        self.sha = sha
        self.cache: Dict[str, List[str]] = {}

    def lines(self, path: str) -> List[str]:
        if path in self.cache:
            return self.cache[path]
        spec = f"{self.sha}:{path}"
        done = _git(self.repo, "show", spec)
        if done.returncode != 0:
            _fail(EXIT_CANT_SHIP, f"{path} does not exist at commit {self.sha[:8]}", path=path)
        # `git show` on a folder prints a tree listing instead of failing
        if done.stdout.startswith(b"tree " + spec.encode()):
            _fail(EXIT_CANT_SHIP, f"{path} at commit {self.sha[:8]} is a folder, not a file", path=path)
        if b"\0" in done.stdout:
            _fail(EXIT_CANT_SHIP, f"{path} at commit {self.sha[:8]} is a binary file", path=path)
        text = done.stdout.decode("utf-8", "replace")
        parts = text.split("\n")
        if text.endswith("\n"):
            parts.pop()
        self.cache[path] = [_normalize(p) for p in parts]
        return self.cache[path]


# tokenizer ---------------------------------------------------------------------------------------------------

Run = Tuple[Optional[str], str]

_C_WORDS = frozenset(
    "abstract as async await break case catch class const continue declare default defer delete do else enum export "
    "extends false final finally fn for func function if implements import in instanceof interface let mod mut "
    "namespace new null override package private protected pub public readonly return static struct super switch "
    "this throw trait true try undefined var void while with yield".split()
)
_PY_WORDS = frozenset(
    "False None True and as assert async await break class continue def del elif else except finally for from global "
    "if import in is lambda nonlocal not or pass raise return try while with yield".split()
)
_SH_WORDS = frozenset("case do done elif else esac export fi for function if in local return then while".split())
_RB_WORDS = frozenset("begin class def do else elsif end ensure false if module nil rescue return true unless while yield".split())

_PROFILES: Dict[str, Dict[str, Any]] = {
    "c": dict(block=True, line=r"//", backtick=True, triple=False, words=_C_WORDS, at=False),
    "css": dict(block=True, line=None, backtick=False, triple=False, words=frozenset(), at=True),
    "scss": dict(block=True, line=r"//", backtick=False, triple=False, words=frozenset(), at=True),
    "py": dict(block=False, line=r"#", backtick=False, triple=True, words=_PY_WORDS, at=False),
    "sh": dict(block=False, line=r"#", backtick=False, triple=False, words=_SH_WORDS, at=False),
    "rb": dict(block=False, line=r"#", backtick=False, triple=False, words=_RB_WORDS, at=False),
    "data": dict(block=False, line=None, backtick=False, triple=False, words=frozenset(), at=False),
}
_EXTENSIONS = {
    **{e: "c" for e in "ts tsx js jsx mjs cjs java kt kts swift go rs c h cc cpp hpp cs scala dart php".split()},
    "css": "css", "scss": "scss", "less": "scss",
    "py": "py", "sh": "sh", "bash": "sh", "zsh": "sh", "yml": "sh", "yaml": "sh", "toml": "sh", "rb": "rb", "json": "data",
}
_REGEXES: Dict[str, "re.Pattern[str]"] = {}


def _regex(name: str) -> "re.Pattern[str]":
    if name not in _REGEXES:
        p = _PROFILES[name]
        parts = []
        if p["block"]:
            parts.append(r"(?P<c1>/\*.*?(?:\*/|\Z))")
        if p["line"]:
            parts.append(r"(?P<c2>%s[^\n]*)" % p["line"])
        if p["triple"]:
            parts.append(r'(?P<s1>"""(?:\\.|[^\\])*?(?:"""|\Z)|\'\'\'(?:\\.|[^\\])*?(?:\'\'\'|\Z))')
        if p["backtick"]:
            parts.append(r"(?P<s2>`(?:\\.|[^`\\])*(?:`|\Z))")
        parts.append(r'(?P<s3>"(?:\\.|[^"\\\n])*")')
        if name != "data":
            parts.append(r"(?P<s4>'(?:\\.|[^'\\\n])*')")
        if p["at"]:
            parts.append(r"(?P<k1>@[A-Za-z][\w-]*)")
        parts.append(r"(?P<w>[A-Za-z_$][\w$]*)")
        _REGEXES[name] = re.compile("|".join(parts), re.DOTALL)
    return _REGEXES[name]


def _tokenize(text: str, path: str) -> List[Run]:
    """Runs of ``text`` as (kind, piece): kind is ``c`` (comment), ``s`` (string), ``k`` (keyword) or None. The pieces concatenate to ``text``."""
    name = _EXTENSIONS.get(path.rsplit(".", 1)[-1].lower()) if "." in path else None
    if name is None:
        return [(None, text)]
    words = _PROFILES[name]["words"]
    runs: List[Run] = []
    pos = 0

    def add(kind: Optional[str], piece: str) -> None:
        if not piece:
            return
        if runs and runs[-1][0] == kind and kind is None:
            runs[-1] = (None, runs[-1][1] + piece)
        else:
            runs.append((kind, piece))

    for m in _regex(name).finditer(text):
        add(None, text[pos:m.start()])
        group = m.lastgroup or ""
        if group.startswith("c"):
            add("c", m.group())
        elif group.startswith("s"):
            add("s", m.group())
        elif group == "k1" or m.group() in words:
            add("k", m.group())
        else:
            add(None, m.group())
        pos = m.end()
    add(None, text[pos:])
    return runs


def _runs_by_line(lines: List[str], path: str) -> List[List[Run]]:
    per_line: List[List[Run]] = [[]]
    for kind, piece in _tokenize("\n".join(lines), path):
        for i, part in enumerate(piece.split("\n")):
            if i:
                per_line.append([])
            if part:
                per_line[-1].append((kind, part))
    out = []
    for runs, line in zip(per_line, lines):
        # colour must never cost a character, so any disagreement falls back to plain text
        out.append(runs if "".join(p for _, p in runs) == line else ([(None, line)] if line else []))
    return out


def _slice_runs(runs: List[Run], start: int) -> List[Run]:
    out: List[Run] = []
    skipped = 0
    for kind, piece in runs:
        if skipped + len(piece) <= start:
            skipped += len(piece)
            continue
        out.append((kind, piece[max(start - skipped, 0):]))
        skipped = start
    return out


def _break_at(text: str, width: int) -> int:
    """Where to end the first block of ``text``, in characters: after the last space that fits in ``width`` cells, or at the cell limit when a word is too long. Always at least one character."""
    used = 0
    fit = 0
    for char in text:
        used += _cells(char)
        if used > width:
            break
        fit += 1
    else:
        return len(text)
    fit = max(fit, 1)
    indent = len(text) - len(text.lstrip(" "))
    space = text.rfind(" ", indent, fit)
    return space + 1 if space >= 0 else fit


def _chunks(runs: List[Run], width: int = CHARS_PER_ROW) -> List[List[Run]]:
    """Split a row's runs into blocks of at most ``width`` cells that join back to the row exactly."""
    text = "".join(piece for _, piece in runs)
    kinds = [kind for kind, piece in runs for _ in piece]
    chunks: List[List[Run]] = []
    start = 0
    while start < len(text):
        end = start + _break_at(text[start:], width)
        chunk: List[Run] = []
        for i in range(start, end):
            if chunk and chunk[-1][0] == kinds[i]:
                chunk[-1] = (kinds[i], chunk[-1][1] + text[i])
            else:
                chunk.append((kinds[i], text[i]))
        chunks.append(chunk)
        start = end
    return chunks


def _safe(text: str) -> str:
    # hyperframes lint reads a literal slash-star in markup as a CSS comment, in code and prose alike
    return html.escape(text, quote=False).replace("/*", "&#47;*").replace("*/", "*&#47;")


def _runs_html(runs: List[Run]) -> str:
    return "".join(f'<span class="{kind}">{_safe(piece)}</span>' if kind else _safe(piece) for kind, piece in runs)


# stop layout -------------------------------------------------------------------------------------------------


def _leading_spaces(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def _cut_is_blank(source: str, dedent: int) -> bool:
    return not source[:dedent].strip()


class Row:
    def __init__(self, kind: str, number: int, first: int, last: int, note: str, runs: List[Run]) -> None:
        self.kind = kind
        self.number = number
        self.first = first
        self.last = last
        self.note = note
        self.runs = runs
        self.chunks = _chunks(runs) or [[]]
        self.y = 0

    @property
    def height(self) -> int:
        return ROW_H * len(self.chunks)


class Stop:
    def __init__(self, scene_id: str, scene: Dict[str, Any], sources: Sources) -> None:
        self.id = scene_id
        self.name = scene["stop"]
        self.path = scene["path"]
        self.label = scene.get("label")
        lines = sources.lines(self.path)
        numbers = _line_numbers(scene["_rows"])
        for row in scene["_rows"]:
            last = row[1] if row[0] == "line" else row[3]
            if last > len(lines):
                _fail(EXIT_CANT_SHIP, f"{self.path}:{last} does not exist at commit {sources.sha[:8]} (the file has {len(lines)} lines); scene {scene_id}, stop {self.name!r}", path=self.path, line=last)
        text_rows = [lines[n - 1] for n in numbers if lines[n - 1].strip()]
        self.dedent = min((_leading_spaces(t) for t in text_rows), default=0)
        by_line = _runs_by_line(lines, self.path)
        self.rows: List[Row] = []
        for row in scene["_rows"]:
            if row[0] == "line":
                number = row[1]
                self.rows.append(Row("line", number, number, number, "", _slice_runs(by_line[number - 1], self.dedent)))
            else:
                _, note, first, last = row
                span = f"line {first}" if first == last else f"lines {first}–{last}"
                self.rows.append(Row("skip", 0, first, last, note, [(None, f"{note} ({span} skipped)")]))
        y = FIRST_ROW_Y
        for r in self.rows:
            r.y = y
            y += r.height
        self.count = sum(len(r.chunks) for r in self.rows)
        limit = MAX_ROWS_LABELLED if self.label else MAX_ROWS
        if self.count > limit:
            _fail(
                EXIT_CANT_SHIP,
                f"scene {scene_id} (stop {self.name!r}) takes {self.count} rows after wrapping and the limit is {limit}"
                f"{' with a label' if self.label else ''}; pick fewer lines or mark some as skipped",
                stop=self.name, rows=self.count, limit=limit,
            )

    def row(self, number: int) -> Row:
        return next(r for r in self.rows if r.kind == "line" and r.number == number)

    def region(self, number: int) -> List[int]:
        row = self.row(number)
        return [BAR_X, row.y, BAR_W, row.height]


# fonts -------------------------------------------------------------------------------------------------------


def _json_object(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _brand_fonts(project: Path) -> Tuple[str, Path, Dict[str, Any]]:
    """The project's product, its brand folder and the ``fonts`` roles of its ``brand.json``; empty when the brief or brand is missing."""
    product = _json_object(project / "brief.json").get("product")
    if not _is_text(product) or Path(product).name != product:
        return "", Path(), {}
    studio = Path(os.environ.get("QUIRK_STUDIO") or "~/Studio").expanduser()
    brand = studio / "brands" / product
    fonts = _json_object(brand / "brand.json").get("fonts")
    return product, brand, fonts if isinstance(fonts, dict) else {}


def _fonts(project: Path) -> Tuple[Dict[str, str], str, List[Tuple[Path, str]]]:
    """The display and mono families the film uses, the ``@font-face`` rules for any the renderer doesn't bundle, and the font files to copy.

    Families come from the product's brand and fall back to Inter and JetBrains Mono per role. Refuses, before anything
    is written, a family that can't be loaded and a brand with a family the tour doesn't use, because ``verify.py``
    requires every brand family to be injected at render. Each copy is named by role and position, so same-named
    files from different folders never overwrite each other.
    """
    product, brand, fonts = _brand_fonts(project)
    entries = {role: fonts.get(role) if isinstance(fonts.get(role), dict) else {} for role in ROLES}
    used = {role: entries[role]["family"] if _is_text(entries[role].get("family")) else DEFAULT_FAMILIES[role] for role in ROLES}
    for role, family in used.items():
        if not FAMILY_NAME.fullmatch(family):
            _fail(EXIT_BAD_INPUT, f"brand {product!r} font family {family!r} ({role}) must be letters, digits, spaces, hyphens and underscores only, because it is written into CSS")
    unused = sorted({str(f["family"]) for role, f in fonts.items() if role not in ROLES and isinstance(f, dict) and f.get("family")} - set(used.values()))
    if unused:
        _fail(EXIT_CANT_SHIP, f"brand {product!r} has font famil{'y' if len(unused) == 1 else 'ies'} {', '.join(unused)} outside the display and mono roles, so the tour can't use {'it' if len(unused) == 1 else 'them'} and verify would fail the fonts check; move the brand's fonts into display and mono", families=unused)
    rules: List[str] = []
    copies: List[Tuple[Path, str]] = []
    for role in ROLES:
        family = used[role]
        if family in BUNDLED_FONTS:
            continue
        listed = entries[role].get("files")
        names = [f for f in listed if isinstance(f, str)] if isinstance(listed, list) else []
        if not names:
            _fail(EXIT_CANT_SHIP, f"font family {family!r} ({role}) is not bundled with HyperFrames and brand {product!r} lists no file for it; add a static TTF or OTF to {brand} and list it in fonts.{role}.files of brand.json", family=family)
        for position, name in enumerate(names):
            file = (brand / name).resolve()
            if not file.is_relative_to(brand.resolve()):
                _fail(EXIT_BAD_INPUT, f"brand {product!r} font file {name!r} ({family!r}) is outside the brand folder {brand}")
            if not file.is_file():
                _fail(EXIT_CANT_SHIP, f"font family {family!r} ({role}) lists {name!r} but {file} does not exist; copy the font file there or fix fonts.{role}.files in brand.json", family=family)
            if not FONT_FILE_NAME.fullmatch(file.name):
                _fail(EXIT_BAD_INPUT, f"brand {product!r} font file name {file.name!r} ({family!r}) must be letters, digits, dots, spaces, hyphens and underscores only, because it is written into CSS")
            copy = f"{role}-{position}-{file.name}"
            rules.append(f"@font-face {{ font-family: \"{family}\"; src: url('assets/fonts/{copy}'); }}")
            copies.append((file, copy))
    return used, "\n    ".join(rules), copies


def _tokens(used: Dict[str, str], faces: str) -> str:
    """The inline token block every composition and the index carry: any ``@font-face`` rules, then the colours and font roles."""
    root = f':root {{\n{PALETTE}\n      --font-display: "{used["display"]}", sans-serif;\n      --font-mono: "{used["mono"]}", monospace;\n    }}'
    return f"{faces}\n    {root}" if faces else root


# timing ------------------------------------------------------------------------------------------------------


def _ceil(frames: float) -> int:
    return math.ceil(frames - 1e-6)


def _sec(frames: float) -> float:
    return round(frames / FPS, 6)


def _num(seconds: float) -> str:
    text = format(round(seconds, 6), "f").rstrip("0").rstrip(".")
    return text or "0"


class Timing:
    """Frame-aligned starts: every clip start and scene boundary is a whole number of frames."""

    def __init__(self, lengths: List[List[float]]) -> None:
        self.clip_start: List[List[int]] = []
        self.scene_start: List[int] = []
        boundary = 0
        end = 0.0
        for scene in lengths:
            self.scene_start.append(boundary)
            starts: List[int] = []
            t = boundary + round(LEAD_S * FPS)
            for n, length in enumerate(scene):
                if n:
                    t = _ceil(end + LINE_GAP_S * FPS)
                starts.append(t)
                end = t + length * FPS
            self.clip_start.append(starts)
            boundary = _ceil(end + (SCENE_GAP_S - LEAD_S) * FPS)
        self.film = _ceil(end + HOLD_S * FPS)

    def scene_end(self, scene: int) -> int:
        return self.scene_start[scene + 1] if scene + 1 < len(self.scene_start) else self.film


# scenes ------------------------------------------------------------------------------------------------------


def _first_word(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9']+", text)
    return (words[0] if words else (text.split() or [""])[0]).lower()


def _tween(target: str, start: Dict[str, Any], end: Dict[str, Any], duration: float, ease: str, at: float) -> str:
    def obj(d: Dict[str, Any]) -> str:
        return "{ " + ", ".join(f"{k}: {v}" for k, v in d.items()) + " }"
    final = dict(end, duration=duration, ease=f'"{ease}"', immediateRender="false")
    return f'tl.fromTo("#{target}", {obj(start)}, {obj(final)}, {_num(at)});'


def _moves(items: List[int], steps: List[Tuple[Narration, List[int]]], bar_id: Any, dim_id: Any, rel: Any) -> Tuple[List[str], Dict[str, int]]:
    """Tweens that move the highlight, and for each step the item whose change a beat should watch.

    A step that changes nothing gets no tween and no beat, because a detector would find no onset to measure.
    """
    js: List[str] = []
    focus: Dict[str, int] = {}
    current: set = set()
    dimmed = False
    for line, targets in steps:
        on = set(targets)
        at = rel(line)
        flipped = []
        for item in items:
            was, now = item in current, item in on
            if was != now:
                flipped.append(item)
                js.append(_tween(bar_id(item), {"opacity": int(was)}, {"opacity": int(now)}, 0.2, "power2.out", at))
            before = 1 if (not dimmed or was) else 0.72
            after = 1 if now else 0.72
            if before != after:
                js.append(_tween(dim_id(item), {"opacity": before}, {"opacity": after}, 0.2, "power2.out", at))
        newly = [t for t in targets if t not in current]
        if newly:
            focus[line.clip] = newly[0]
        elif flipped:
            focus[line.clip] = flipped[0]
        current, dimmed = on, True
    return js, focus


def _composition(scene_id: str, tokens: str, css: str, body: str, script: str) -> str:
    return f"""<template>
  <style>
    {tokens}
    {BASE_CSS}
    {css}
  </style>
  <div id="root" data-composition-id="{scene_id}" data-width="1920" data-height="1080">
{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {script}
    window.__timelines["{scene_id}"] = tl;
  </script>
</template>
"""


class Built:
    """What the layout and timing produce: file contents to write and the numbers `build` reports."""

    def __init__(self) -> None:
        self.compositions: Dict[str, str] = {}
        self.beats: List[Dict[str, Any]] = []
        self.stops: List[Dict[str, Any]] = []


def _row_html(sid: str, stop: Stop, row: Row) -> str:
    """One card row. Wrapped lines are explicit blocks of at most CHARS_PER_ROW cells, so the row count never depends on the browser."""
    blocks = "".join('<span class="w">' + _runs_html(c) + "</span>" for c in row.chunks if c)
    if row.kind == "skip":
        return f'<div class="row"><div class="num">⋯</div><div class="txt skip" data-skip="{_skip_span(row.first, row.last)}">{blocks}</div></div>'
    n = row.number
    return (
        f'<div class="row" id="{sid}-r{n}"><div class="band" id="{sid}-b{n}"></div><div class="num">{n}</div>'
        f'<div class="txt" id="{sid}-t{n}" data-line="{n}" data-dedent="{stop.dedent}">{blocks}</div></div>'
    )


def _render(tour: Dict[str, Any], lines: List[Narration], stops: Dict[int, Stop], timing: Timing, sha: str, tokens: str) -> Built:
    built = Built()
    scenes = tour["scenes"]
    stop_total = sum(1 for s in scenes if "stop" in s)
    stop_no = 0
    for index, scene in enumerate(scenes):
        sid = f"s{index + 1}"
        mine = [ln for ln in lines if ln.scene == index]
        origin = timing.scene_start[index]
        start_of = {ln.clip: timing.clip_start[index][n] for n, ln in enumerate(mine)}

        def rel(line: Narration, origin: int = origin, start_of: Dict[str, int] = start_of) -> float:
            return (start_of[line.clip] - origin) / FPS

        steps = [(ln, ln.marks) for ln in mine if ln.marks]
        if "map" in scene:
            count = len(scene["map"])
            width = (MAP_WIDTH - (count - 1) * MAP_GAP) // count
            nodes = []
            for i, node in enumerate(scene["map"]):
                nodes.append(
                    f'<div class="node" id="{sid}-n{i}" style="flex: 0 0 {width}px"><div class="pip" id="{sid}-p{i}"></div>'
                    f'<h3>{_safe(node["name"])}</h3><p class="mono">{_safe(node["file"])}</p></div>'
                )
                if i < count - 1:
                    nodes.append('<div class="arrow"></div>')
            js, focus = _moves(list(range(count)), steps, lambda i: f"{sid}-p{i}", lambda i: f"{sid}-n{i}", rel)
            regions = {i: [96 + i * (width + MAP_GAP) + CARD_BORDER, MAP_TOP + CARD_BORDER + 16, BAR_W, 260] for i in range(count)}
            body = (
                f'    <div class="title" id="{sid}-title">{_safe(tour["title"])}</div>\n'
                f'    <div class="nodes">{"".join(nodes)}</div>'
            )
            css = MAP_CSS
        else:
            stop = stops[index]
            stop_no += 1
            built.stops.append({"stop": stop.name, "rows": stop.count})
            rows = [_row_html(sid, stop, r) for r in stop.rows]
            numbers = [r.number for r in stop.rows if r.kind == "line"]
            js, focus = _moves(numbers, steps, lambda n: f"{sid}-b{n}", lambda n: f"{sid}-t{n}", rel)
            regions = {n: stop.region(n) for n in numbers}
            body = (
                f'    <div class="mono stop">{_safe(f"STOP {stop_no} OF {stop_total} · {stop.name}")}</div>\n'
                f'    <div class="mono commit">commit {sha[:8]}</div>\n'
                f'    <div class="mono path">{_safe(stop.path)}</div>\n'
                f'    <div class="card">\n{chr(10).join(rows)}\n    </div>'
            )
            css = ""
        script = list(js)
        scene_start_s = _sec(origin)
        beat_base = {"detector": "changed"}
        for ln in mine:
            if ln.clip in focus:
                expected = _sec(start_of[ln.clip])
                built.beats.append({
                    "id": f"{sid}-{ln.clip}", "word": _first_word(ln.text), "clip": f"assets/voice/{ln.clip}.wav",
                    "clip_start_s": expected, "expected_s": expected, "region": regions[focus[ln.clip]],
                    "baseline_s": round(max(expected - 0.5, scene_start_s + 0.05), 6), **beat_base,
                })
        label = scene.get("label")
        if label:
            last = mine[-1]
            expected = _sec(start_of[last.clip])
            body += f'\n    <div class="label" id="{sid}-label">{_safe(label)}</div>'
            script.insert(0, f'gsap.set("#{sid}-label", {{ opacity: 0 }});')
            script.append(_tween(f"{sid}-label", {"opacity": 0, "y": 16}, {"opacity": 1, "y": 0}, 0.35, "power3.out", rel(last)))
            built.beats.append({
                "id": f"{sid}-label", "word": _first_word(last.text), "clip": f"assets/voice/{last.clip}.wav",
                "clip_start_s": expected, "expected_s": expected, "region": LABEL_REGION,
                "baseline_s": round(max(expected - 0.5, scene_start_s + 0.05), 6), **beat_base,
            })
        built.compositions[sid] = _composition(sid, tokens, css, body, "\n    ".join(script))
    return built


def _index_page(head: str, tour: Dict[str, Any], lines: List[Narration], lengths: Dict[str, float], timing: Timing, tokens: str) -> str:
    hosts = "\n".join(
        f'  <div id="s{i + 1}" class="clip" data-composition-id="s{i + 1}" data-composition-src="compositions/s{i + 1}.html" '
        f'data-start="{_num(_sec(timing.scene_start[i]))}" data-duration="{_num(_sec(timing.scene_end(i) - timing.scene_start[i]))}" '
        f'data-track-index="1" data-width="1920" data-height="1080" style="z-index: 1"></div>'
        for i in range(len(tour["scenes"]))
    )
    audio = "\n".join(
        f'  <audio id="vo-{ln.clip}" class="clip" src="assets/voice/{ln.clip}.wav" '
        f'data-start="{_num(_sec(timing.clip_start[ln.scene][_position(lines, ln)]))}" data-duration="{_num(lengths[ln.clip])}" '
        f'data-track-index="3" data-volume="1"></audio>'
        for ln in lines
    )
    return f"""{head}<body>
<style>
  {tokens}
  html, body {{ margin: 0; background: var(--ground); }}
</style>
<div id="root" data-composition-id="main" data-start="0" data-duration="{_num(_sec(timing.film))}" data-width="1920" data-height="1080">
{hosts}
{audio}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
  window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def _position(lines: List[Narration], line: Narration) -> int:
    return [ln for ln in lines if ln.scene == line.scene].index(line)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _notes(tour: Dict[str, Any], lines: List[Narration], stops: Dict[int, Stop], timing: Timing, sha: str) -> Tuple[str, str]:
    sources = [
        "# Sources",
        "",
        f"All code is read from `{tour['repo']}` at commit `{sha}`.",
        "",
        *[f"- {ln.text}: {ln.source}" for ln in lines],
        "",
    ]
    script, table = [], []
    for i, scene in enumerate(tour["scenes"]):
        mine = [ln for ln in lines if ln.scene == i]
        script.append(f"{i + 1}. " + " ".join(ln.text for ln in mine))
        span = f"{_sec(timing.scene_start[i]):.2f}-{_sec(timing.scene_end(i)):.2f}"
        if "map" in scene:
            shown = "Map: " + ", ".join(n["file"] for n in scene["map"])
            roles = "node bar lights on each line" if any(ln.marks for ln in mine) else "none"
        else:
            stop = stops[i]
            numbers = [r.number for r in stop.rows if r.kind == "line"]
            skipped = sum(1 for r in stop.rows if r.kind == "skip")
            shown = f"`{stop.path}` lines {numbers[0]}-{numbers[-1]}" + (f", {skipped} skipped" if skipped else "")
            roles = "band moves " + ", then ".join(str(ln.marks[0]) for ln in mine if ln.marks) if any(ln.marks for ln in mine) else "none"
        label = f'"{scene["label"]}"' if scene.get("label") else "none"
        cited = "; ".join(ln.source for ln in mine)
        table.append(f"| s{i + 1} | {span} | {_cell(shown)} | {_cell(label)} | {i + 1} | {_cell(cited)} | {_cell(roles)} |")
    board = [
        f"# {tour['title']}",
        "",
        f"- Length: {_sec(timing.film):.1f} s. Aspects: 16:9. Narration: on, {len(lines)} clips (measured).",
        f"- Reader: a technical teammate. A code tour at commit `{sha[:8]}`.",
        "",
        "## Script",
        "",
        *script,
        "",
        "## Scenes",
        "",
        "| Scene | Time (s) | On screen | On-screen text | Narration | Source | Motion roles |",
        "|---|---|---|---|---|---|---|",
        *table,
        "",
        "## Scene kit",
        "",
        "See `kit/kit.md`.",
        "",
        "## Flags",
        "",
        "- No 3D. No cloud service.",
        "- Code comes from `git show`, and `code_tour.py check` compares what is on screen with the commit. It runs at the end of every build.",
        "",
    ]
    return "\n".join(sources), "\n".join(board)


# check -------------------------------------------------------------------------------------------------------


class _CodeRows(HTMLParser):
    """Collects a composition's path row, the text of each numbered code line, each skip row, and the text of any code element with neither marker."""

    def __init__(self) -> None:
        super().__init__()
        self.path: Optional[str] = None
        self.rows: List[Tuple[Any, ...]] = []
        self.skips: List[str] = []
        self.sequence: List[str] = []
        self.loose: List[str] = []
        self.grab: Optional[str] = None
        self.depth = 0
        self.buffer: List[str] = []
        self.meta: Tuple[str, str] = ("", "")

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if self.grab:
            self.depth += 1
        elif "data-line" in a:
            self.grab, self.meta, self.depth, self.buffer = "line", (a["data-line"] or "", a.get("data-dedent") or "0"), 0, []
        elif "data-skip" in a:
            self.skips.append(a["data-skip"] or "")
            self.sequence.append(f"skip {a['data-skip'] or ''}")
        elif "txt" in classes:
            self.grab, self.depth, self.buffer = "loose", 0, []
        elif "path" in classes:
            self.grab, self.depth, self.buffer = "path", 0, []

    def handle_endtag(self, tag: str) -> None:
        if not self.grab:
            return
        if self.depth:
            self.depth -= 1
            return
        text = "".join(self.buffer)
        if self.grab == "path":
            self.path = text
        elif self.grab == "loose":
            self.loose.append(text)
        else:
            self.rows.append((*self.meta, text))
            self.sequence.append(f"line {self.meta[0]}")
        self.grab = None

    def handle_data(self, data: str) -> None:
        if self.grab:
            self.buffer.append(data)


def _normal_row(row: str) -> str:
    kind, _, value = row.partition(" ")
    return f"{kind} {int(value)}" if kind == "line" else row


def _screen(file: Path) -> _CodeRows:
    parser = _CodeRows()
    parser.feed(re.sub(r"<script.*?</script>|<style.*?</style>", "", file.read_text(encoding="utf-8"), flags=re.S))
    return parser


def _compare(project: Path, tour: Dict[str, Any], sha: str) -> Tuple[int, List[Dict[str, Any]]]:
    """How many on-screen code lines were compared with the commit, and each difference from ``tour.json`` and the source.

    Every stop must be on screen with exactly the lines, in order, and skip rows ``tour.json`` gives it. Every other
    composition must show no code at all. A row that lost its marker, a deleted row, a missing composition or code on a
    scene that shows none is a mismatch and never skipped silently.
    """
    sources = Sources(tour["repo"], sha)
    checked = 0
    bad: List[Dict[str, Any]] = []
    folder = project / "scenes" / "compositions"

    def differ(name: str, reason: str, line: Optional[int] = None, screen: Optional[str] = None, source: Optional[str] = None) -> None:
        bad.append({"scene": name, "line": line, "screen": screen, "source": source, "reason": reason})

    stop_files = set()
    for index, scene in enumerate(tour["scenes"], 1):
        if "stop" not in scene:
            continue
        name = f"s{index}.html"
        stop_files.add(name)
        where = f"stop {scene['stop']!r}"
        file = folder / name
        if not file.is_file():
            differ(name, f"{where} has no composition {name}, so none of its code is on screen")
            continue
        parser = _screen(file)
        if not parser.rows:
            differ(name, f"{where} has no numbered code rows on screen")
            continue
        path = scene["path"]
        if parser.path != path:
            differ(name, f"the path row shows {parser.path!r} and tour.json says {path!r}", screen=parser.path, source=path)
        source = sources.lines(path)
        seen: Dict[int, int] = {}
        order: List[int] = []
        for raw_number, raw_dedent, text in parser.rows:
            try:
                number, dedent = int(raw_number), int(raw_dedent)
            except ValueError:
                _fail(EXIT_CANT_SHIP, f"{name}: a code line has an unreadable number or dedent ({raw_number!r}, {raw_dedent!r})")
            checked += 1
            order.append(number)
            seen[number] = seen.get(number, 0) + 1
            if not 1 <= number <= len(source):
                differ(name, f"{path} has no line {number} at commit {sha[:8]}", number, text)
            elif not _cut_is_blank(source[number - 1], dedent):
                differ(name, f"the indentation cut removes non-whitespace ({source[number - 1][:dedent]!r})", number, text, source[number - 1])
            elif source[number - 1][dedent:] != text:
                differ(name, "the text on screen differs from the source", number, text, source[number - 1][dedent:])
        wanted = _line_numbers(scene["_rows"])
        before = len(bad)
        for number in wanted:
            if number not in seen:
                differ(name, f"line {number} is in tour.json for {where} but not on screen", number)
        for number in sorted(seen):
            if number not in wanted:
                differ(name, f"line {number} is on screen but tour.json doesn't show it in {where}", number)
            elif seen[number] > 1:
                differ(name, f"line {number} is on screen {seen[number]} times", number)
        if len(bad) == before and order != wanted:
            differ(name, f"the code rows of {where} are out of order: the screen shows lines {order} and tour.json gives {wanted}")
        rows_clean = len(bad) == before
        for text in parser.loose:
            differ(name, "a code element has neither data-line nor data-skip, so it can't be compared with the commit", screen=text)
        skips = sorted(_skip_span(r[2], r[3]) for r in scene["_rows"] if r[0] == "skip")
        if sorted(parser.skips) != skips:
            differ(name, f"the skip rows on screen ({', '.join(sorted(parser.skips)) or 'none'}) differ from tour.json ({', '.join(skips) or 'none'})")
        elif rows_clean:
            given = [f"line {r[1]}" if r[0] == "line" else f"skip {_skip_span(r[2], r[3])}" for r in scene["_rows"]]
            if [_normal_row(r) for r in parser.sequence] != given:
                differ(name, f"the rows of {where} are out of order: the screen shows {', '.join(parser.sequence)} and tour.json gives {', '.join(given)}")
    for file in sorted(folder.glob("*.html")):
        if file.name in stop_files or not file.is_file():
            continue
        parser = _screen(file)
        if parser.rows or parser.loose or parser.skips:
            differ(file.name, f"{file.name} has code on screen ({len(parser.rows)} numbered rows, {len(parser.loose)} unmarked, {len(parser.skips)} skip rows) but tour.json gives it no stop, so it is code on a scene that shows none")
    return checked, bad


def _report(project: Path, tour: Dict[str, Any], sha: str) -> Dict[str, Any]:
    checked, bad = _compare(project, tour, sha)
    result = {"commit": sha, "checked": checked, "mismatches": bad}
    for m in bad:
        at = "" if m["line"] is None else f" line {m['line']}"
        print(f"code_tour.py: {m['scene']}{at}: {m['reason']}; screen {m['screen']!r}, source {m['source']!r}", file=sys.stderr)
    if checked == 0:
        message = f"checked 0 code lines in {project / 'scenes' / 'compositions'}; a check that saw nothing proves nothing"
        print(f"code_tour.py: {message}", file=sys.stderr)
        print(json.dumps({**result, "error": message}))
        sys.exit(EXIT_CANT_SHIP)
    if bad:
        print(json.dumps({**result, "error": f"{len(bad)} code lines differ from commit {sha[:8]}"}))
        sys.exit(EXIT_CANT_SHIP)
    return result


# commands ----------------------------------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cmd_lines(project: Path) -> None:
    tour = _load_tour(project)
    _semantics(tour)
    lines = _narration(tour)
    _write(project / "assets" / "lines.json", json.dumps([{"id": ln.clip, "text": ln.text, "start_s": 0} for ln in lines], indent=2) + "\n")
    print(json.dumps({"lines": len(lines)}))


def _wav_length(path: Path, clip: str) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError, OSError, ZeroDivisionError) as exc:
        _fail(EXIT_BAD_INPUT, f"cannot read the voice clip {clip} at {path}: {exc}")


def _cmd_build(project: Path) -> None:
    tour = _load_tour(project)
    _semantics(tour)
    lines = _narration(tour)
    used, faces, font_files = _fonts(project)
    tokens = _tokens(used, faces)
    index = project / "scenes" / "index.html"
    if not index.is_file():
        _fail(EXIT_BAD_INPUT, f"{index} is missing; run: python3 {MAKING_VIDEOS / 'hf.py'} --project {project} -- init {project / 'scenes'} --non-interactive")
    page = index.read_text(encoding="utf-8")
    if "<body" not in page or "gsap" not in page.split("<body", 1)[0].lower():
        _fail(EXIT_BAD_INPUT, f"{index} is not the hf.py scaffold (no <body>, or no GSAP in its head); rerun hf.py init")
    voice = project / "assets" / "voice"
    missing = [ln.clip for ln in lines if not (voice / f"{ln.clip}.wav").is_file()]
    if missing:
        _fail(EXIT_BAD_INPUT, f"no voice clip for {', '.join(missing)} in {voice}; run: python3 {MAKING_VIDEOS / 'voice.py'} say --project {project} --lines {project / 'assets' / 'lines.json'}")
    existing = project / "assets" / "lines.json"
    if existing.is_file():
        try:
            have = [(c["id"], c["text"]) for c in json.loads(existing.read_text(encoding="utf-8"))]
        except (OSError, ValueError, KeyError, TypeError):
            have = []
        want = [(ln.clip, ln.text) for ln in lines]
        if have != want:
            stale = next((w[0] for w, h in zip(want + [("", "")], have + [("", "")]) if w != h), "?")
            _fail(EXIT_BAD_INPUT, f"{existing} no longer matches tour.json at {stale}; run: python3 {Path(__file__).resolve()} lines --project {project}, then voice.py say again")
    measured = {ln.clip: _wav_length(voice / f"{ln.clip}.wav", ln.clip) for ln in lines}
    lengths = {clip: round(seconds, 3) for clip, seconds in measured.items()}

    sha = _resolve(tour["repo"], tour["commit"])
    sources = Sources(tour["repo"], sha)
    stops = {i: Stop(f"s{i + 1}", scene, sources) for i, scene in enumerate(tour["scenes"]) if "stop" in scene}
    timing = Timing([[measured[ln.clip] for ln in lines if ln.scene == i] for i in range(len(tour["scenes"]))])
    if timing.film >= FILM_LIMIT_S * FPS:
        _fail(EXIT_CANT_SHIP, f"the film runs {_sec(timing.film):.1f} s and the limit is under {FILM_LIMIT_S} s; cut lines or stops", film_s=_sec(timing.film))

    built = _render(tour, lines, stops, timing, sha, tokens)
    compositions = project / "scenes" / "compositions"
    compositions.mkdir(parents=True, exist_ok=True)
    for old in compositions.glob("s*.html"):
        if re.fullmatch(r"s\d+\.html", old.name) and old.stem not in built.compositions:
            old.unlink()
    for sid, markup in built.compositions.items():
        _write(compositions / f"{sid}.html", markup)
    (project / "scenes" / "assets" / "voice").mkdir(parents=True, exist_ok=True)
    for ln in lines:
        shutil.copyfile(voice / f"{ln.clip}.wav", project / "scenes" / "assets" / "voice" / f"{ln.clip}.wav")
    for source, name in font_files:
        (project / "scenes" / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, project / "scenes" / "assets" / "fonts" / name)
    _write(index, _index_page(page.split("<body", 1)[0], tour, lines, lengths, timing, tokens))
    clips = [{"id": ln.clip, "text": ln.text, "start_s": _sec(timing.clip_start[ln.scene][_position(lines, ln)])} for ln in lines]
    _write(existing, json.dumps(clips, indent=2) + "\n")
    _write(project / "beats.json", json.dumps(built.beats, indent=1) + "\n")
    sources_md, storyboard_md = _notes(tour, lines, stops, timing, sha)
    _write(project / "sources.md", sources_md)
    _write(project / "storyboard.md", storyboard_md)
    _write(project / "kit" / "kit.md", KIT.format(**used))

    _report(project, tour, sha)
    print(json.dumps({"scenes": len(tour["scenes"]), "beats": len(built.beats), "film_s": _sec(timing.film), "stops": built.stops}))


def _cmd_check(project: Path) -> None:
    tour = _load_tour(project)
    compositions = project / "scenes" / "compositions"
    if not any(compositions.glob("*.html")):
        _fail(EXIT_BAD_INPUT, f"no compositions in {compositions}; run: python3 {Path(__file__).resolve()} build --project {project}")
    sha = _resolve(tour["repo"], tour["commit"])
    print(json.dumps(_report(project, tour, sha)))


def main(argv: Optional[List[str]] = None) -> None:
    parser = _Parser(description="Build and check a code-tour film from tour.json.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("lines", "write assets/lines.json"), ("build", "write the scenes, timing and notes, then check"), ("check", "compare the code on screen with the commit")):
        sub = commands.add_parser(name, help=text, description=text)
        sub.add_argument("--project", required=True, help="the film's project folder")
    args = parser.parse_args(argv)
    project = Path(args.project)
    try:
        {"lines": _cmd_lines, "build": _cmd_build, "check": _cmd_check}[args.command](project)
    except OSError as exc:
        _fail(EXIT_BAD_INPUT, f"cannot read or write under {project}: {exc}")


if __name__ == "__main__":
    main()
