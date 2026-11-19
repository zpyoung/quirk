#!/usr/bin/env python3
"""Optional template for videos that walk through source code: ``code_walkthrough.py timeline|build --project DIR``.

A JSON spec (default ``<project>/kit/walkthrough.json``) lists the scenes, the narration lines each one
covers and, per scene, one of five layouts: ``cards``, ``files``, ``panels``, ``code`` or ``custom``.

- ``timeline`` places every narration line from its measured clip length, writes ``start_s`` back into
  ``assets/lines.json`` and the scene times into ``kit/timeline.json``. Run it after ``voice.py say`` and
  before ``voice.py align`` and ``voice.py captions``.
- ``build`` writes ``scenes/compositions/<id>.html``, ``scenes/index.html`` and ``<project>/beats.json``
  from the confirmed brand, with every cue timed one frame before its measured word start. It copies the
  voice clips, brand font files and logo into ``scenes/assets/``. ``scenes/`` must exist (``hf.py -- init``).

Prints one JSON object. Exit codes: 0 ok; 1 a project input is missing or malformed, or the spec names a line, word,
source, token or file that does not exist; 2 usage error.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import wave
from pathlib import Path
from typing import NoReturn, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import EXIT_FAILED, EXIT_USAGE, emit, load_brief, studio_root  # noqa: E402

FRAME = 1 / 30
ROW_H = 44
CODE_PAD = 12
WRAP = 80
MIN_TAIL = 10
SCENE_TYPES = ("cards", "files", "panels", "code", "custom")
CUE_RE = re.compile(r"\{\{cue:([^}]+)\}\}")
ROLE_TOKENS = {
    "ground": ("ground", "bg-subtle", "bg", "background"),
    "ink": ("ink", "fg", "text", "foreground"),
    "muted": ("muted", "fg-secondary", "secondary", "text-muted"),
    "rule": ("rule", "border", "line"),
    "focus": ("focus", "primary", "accent"),
    "ring": ("ring", "accent", "highlight", "primary"),
    "good": ("good", "success", "positive"),
    "bad": ("bad", "destructive", "danger", "error"),
}
ROLE_FALLBACK = {"good": "#0b7a5a", "bad": "#c62b1a"}
WEIGHTS = (("thin", 100), ("extralight", 200), ("light", 300), ("book", 400), ("regular", 400),
           ("medium", 500), ("semibold", 600), ("bold", 700), ("extrabold", 800), ("black", 900))
DEFAULT_FAMILIES = {"display": "Inter", "body": "Inter", "mono": "JetBrains Mono"}
GENERIC = {"display": "sans-serif", "body": "sans-serif", "mono": "monospace"}


class SpecError(Exception):
    """The spec or a project input names something that does not exist."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _read_json(path: Path, what: str):
    if not path.is_file():
        raise SpecError(f"{what} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SpecError(f"{what} is not valid JSON: {path}: {exc}") from exc


def wav_seconds(path: Path) -> float:
    if not path.is_file():
        raise SpecError(f"voice clip not found: {path}; run voice.py say first")
    with wave.open(str(path)) as clip:
        return clip.getnframes() / clip.getframerate()


class Project:
    """The spec, brief, brand, narration lines and word timings of one video project."""

    def __init__(self, root: Path, spec_path: Optional[Path]):
        self.root = root
        self.spec_path = spec_path or root / "kit" / "walkthrough.json"
        self.spec = _read_json(self.spec_path, "spec")
        self.brief = load_brief(root)
        self.brand_dir = studio_root() / "brands" / str(self.brief.get("product"))
        self.brand = _read_json(self.brand_dir / "brand.json", "brand.json")
        self.lines_path = root / "assets" / "lines.json"
        self.lines = {line["id"]: line for line in _read_json(self.lines_path, "assets/lines.json")}
        scenes = self.spec.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise SpecError("spec.scenes must be a non-empty list")
        seen = set()
        for scene in scenes:
            sid = scene.get("id")
            if not isinstance(sid, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", sid):
                raise SpecError(f"scene id {sid!r} must be lowercase letters, digits and '-', starting with a letter")
            if sid in seen:
                raise SpecError(f"scene id {sid!r} is used twice")
            seen.add(sid)
            if scene.get("type") not in SCENE_TYPES:
                raise SpecError(f"scene {sid}: type must be one of {', '.join(SCENE_TYPES)}")
            for lid in scene.get("lines") or []:
                if lid not in self.lines:
                    raise SpecError(f"scene {sid}: line {lid!r} is not in assets/lines.json")
        placed = [lid for scene in scenes for lid in scene.get("lines") or []]
        missing = [lid for lid in self.lines if lid not in placed]
        if missing:
            raise SpecError(f"lines not placed in any scene: {', '.join(missing)}")
        if len(placed) != len(set(placed)):
            raise SpecError("a narration line is placed in more than one scene")

    def voice(self, lid: str) -> Path:
        return self.root / "assets" / "voice" / f"{lid}.wav"


def timeline(project: Project) -> dict:
    """Place each line after the previous one and size each scene to its lines; write lines.json and timeline.json."""
    spec = project.spec
    lead = float(spec.get("lead_s", 0.3))
    gap = float(spec.get("gap_s", 0.4))
    scene_gap = float(spec.get("scene_gap_s", 0.6))
    end_hold = float(spec.get("end_hold_s", 3.0))
    t = 0.0
    scenes = []
    for k, scene in enumerate(spec["scenes"]):
        ids = scene.get("lines") or []
        start = round(t, 2)
        cur = start + lead
        for n, lid in enumerate(ids):
            if n:
                cur += gap
            project.lines[lid]["start_s"] = round(cur, 2)
            cur += wav_seconds(project.voice(lid))
        if not ids:
            cur = start + float(scene.get("duration_s", 3.0))
        last = k == len(spec["scenes"]) - 1
        end = cur + (end_hold if last else scene_gap)
        scenes.append({"id": scene["id"], "start": start, "dur": round(end - start, 2), "lines": ids})
        t = round(end, 2)
    project.lines_path.write_text(json.dumps(list(project.lines.values()), indent=1) + "\n", encoding="utf-8")
    doc = {"total": round(t, 2), "scenes": scenes}
    (project.root / "kit").mkdir(exist_ok=True)
    (project.root / "kit" / "timeline.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return doc


def _hex(value: str) -> "tuple[int, int, int]":
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(a: str, b: str, amount: float) -> str:
    """``a`` mixed into ``b`` by ``amount`` (0 gives ``b``)."""
    ra, rb = _hex(a), _hex(b)
    return "#%02x%02x%02x" % tuple(round(x * amount + y * (1 - amount)) for x, y in zip(ra, rb))


def role_colors(project: Project) -> "dict[str, str]":
    """Hex value per template role, from the spec's ``colors`` map or the first brand token that matches."""
    tokens = {str(k).lower(): str(v) for k, v in (project.brand.get("colors") or {}).items()}
    chosen = project.spec.get("colors") or {}
    out = {}
    for role, candidates in ROLE_TOKENS.items():
        name = chosen.get(role)
        if name is not None:
            if name.lower() not in tokens:
                raise SpecError(f"spec.colors.{role} names token {name!r}, which brand.json does not have")
            out[role] = tokens[name.lower()]
            continue
        hit = next((tokens[c] for c in candidates if c in tokens), None)
        if hit is None and role in ROLE_FALLBACK:
            hit = ROLE_FALLBACK[role]
        if hit is None and role == "ring":
            hit = out.get("focus")
        if hit is None:
            raise SpecError(
                f"no brand token for role {role}; set spec.colors.{role} to one of: {', '.join(sorted(tokens))}")
        out[role] = hit
    out["band"] = _mix(out["ring"], "#ffffff", 0.35)
    out["str"] = _mix(out["good"], "#000000", 0.85)
    return out


def _weight(filename: str) -> int:
    stem = re.sub(r"[^a-z]", "", Path(filename).stem.lower())
    for word, weight in sorted(WEIGHTS, key=lambda w: -len(w[0])):
        if stem.endswith(word):
            return weight
    return 400


def brand_fonts(project: Project) -> "tuple[dict[str, str], list[tuple[str, Path, int]]]":
    """Family per role (display, body, mono) and the brand font files to embed as (family, path, weight)."""
    fonts = project.brand.get("fonts") or {}
    families, files = {}, []
    for role, font in fonts.items():
        if not isinstance(font, dict) or not font.get("family"):
            continue
        families[role] = str(font["family"])
        for rel in font.get("files") or []:
            path = project.brand_dir / rel
            if path.is_file():
                files.append((str(font["family"]), path, _weight(path.name)))
    body = families.get("body") or families.get("text")
    for role, fallback in DEFAULT_FAMILIES.items():
        if role not in families:
            families[role] = fallback if role == "mono" or not body else body
    return families, files


def root_css(colors: "dict[str, str]", families: "dict[str, str]", files) -> str:
    faces = "".join(
        f'@font-face {{ font-family: "{fam}"; src: url(\'assets/fonts/{path.name}\'); font-weight: {weight}; }}\n'
        for fam, path, weight in files)
    tokens = "".join(f"  --{role}: {value};\n" for role, value in colors.items())
    fonts = "".join(f'  --font-{role}: "{families[role]}", {GENERIC[role]};\n' for role in ("display", "body", "mono"))
    return f"{faces}:root {{\n{tokens}{fonts}}}\n"


KIT_CSS = """
#root { width: 1920px; height: 1080px; position: relative; overflow: hidden; color: var(--ink); font-family: var(--font-body); }
.k-eyebrow { position: absolute; left: 120px; top: 64px; font-family: var(--font-mono); font-size: 30px; line-height: 40px; color: var(--muted); white-space: nowrap; }
.k-head { position: absolute; left: 120px; top: 108px; max-width: 860px; font-family: var(--font-display); font-weight: 500; font-size: 64px; line-height: 76px; letter-spacing: -0.01em; white-space: nowrap; }
.k-chips { position: absolute; left: 1000px; top: 116px; width: 800px; height: 56px; }
.k-chipw { position: absolute; right: 0; top: 0; white-space: nowrap; }
.k-chip { display: inline-block; font-family: var(--font-body); font-weight: 600; font-size: 30px; line-height: 40px; padding: 8px 22px; border-radius: 999px; background: var(--ink); color: var(--ground); }
.k-code { position: absolute; left: 120px; width: 1680px; border: 2px solid var(--rule); border-radius: 16px; background: #ffffff; overflow: hidden; }
.k-scroll { position: absolute; left: 0; top: 0; width: 100%; }
.k-mask { position: absolute; left: 0; width: 100%; height: 12px; background: #ffffff; }
.k-band { position: absolute; left: 0; top: 12px; width: 100%; height: 44px; background: var(--band); border-left: 8px solid var(--focus); transform-origin: 0 0; }
.k-row { position: absolute; left: 0; height: 44px; width: 100%; white-space: pre; font-family: var(--font-mono); font-size: 30px; line-height: 44px; color: var(--ink); }
.k-no { display: inline-block; width: 96px; padding-right: 20px; text-align: right; color: var(--muted); }
.k-tx { display: inline-block; padding-left: 4px; }
.t-kw { color: var(--focus); }
.t-str { color: var(--str); }
.t-com { color: var(--muted); }
.t-num { color: var(--bad); }
.t-fn { font-weight: 700; }
.t-gap { color: var(--muted); }
.k-card { position: absolute; border: 2px solid var(--rule); border-radius: 16px; background: #ffffff; padding: 28px 32px; }
.k-card-eye { font-family: var(--font-mono); font-size: 28px; line-height: 36px; color: var(--muted); }
.k-card-title { font-family: var(--font-display); font-weight: 500; font-size: 44px; line-height: 52px; margin-top: 12px; }
.k-ring { position: absolute; border: 6px solid var(--ring); border-radius: 18px; box-shadow: 0 0 0 4px var(--ink); }
.k-arrow { position: absolute; height: 6px; background: var(--ink); transform-origin: 0 50%; }
.k-sub { position: absolute; left: 120px; font-family: var(--font-body); font-size: 44px; line-height: 56px; color: var(--muted); max-width: 1680px; }
.k-mono { font-family: var(--font-mono); font-size: 30px; line-height: 44px; white-space: pre; }
.k-tag { display: inline-block; font-family: var(--font-body); font-weight: 600; font-size: 28px; line-height: 36px; padding: 6px 18px; border-radius: 999px; color: #ffffff; background: var(--ink); }
.k-hl { position: absolute; background: var(--band); border-left: 8px solid var(--focus); }
"""
ENTER = 'duration: 0.4, ease: "expo.out"'


TOKEN_RE = re.compile(
    r'(?P<str>[rbfu]?"(?:[^"\\]|\\.)*"|[rbfu]?\'(?:[^\'\\]|\\.)*\')'
    r"|(?P<com>#.*)"
    r"|(?P<kw>\b(?:def|class|return|if|elif|not|is|in|or|and|for|while|raise|try|except|finally|from|import|"
    r"else|lambda|continue|break|pass|yield|await|async|None|True|False|as|with)\b)"
    r"|(?P<num>\b\d+\b)"
)


def char_classes(text: str, force: Optional[str] = None) -> "list[str]":
    if force:
        return [force] * len(text)
    classes = [""] * len(text)
    for m in TOKEN_RE.finditer(text):
        for i in range(m.start(), m.end()):
            classes[i] = m.lastgroup or ""
    m = re.match(r"\s*(?:async\s+)?(?:def|class) (\w+)", text)
    if m:
        for i in range(m.start(1), m.end(1)):
            classes[i] = "fn"
    return classes


def wrap_points(text: str, width: int = WRAP) -> "tuple[list[tuple[int, int]], int]":
    """Row slices of ``text`` broken at spaces like an editor's soft wrap, and the line's indent."""
    indent = len(text) - len(text.lstrip(" "))
    rows, start, first = [], 0, True
    while True:
        limit = width if first else max(MIN_TAIL, width - indent - 4)
        if len(text) - start <= limit:
            rows.append((start, len(text)))
            return rows, indent
        cut = text.rfind(" ", start, start + limit)
        if cut <= start + 10:
            cut = start + limit
        rows.append((start, cut))
        start = cut + 1 if text[cut:cut + 1] == " " else cut
        first = False


def _spans(text: str, classes: "list[str]", a: int, b: int) -> str:
    out, cur, buf = [], None, ""
    for i in range(a, b):
        if classes[i] != cur and buf:
            out.append((cur, buf))
            buf = ""
        cur = classes[i]
        buf += text[i]
    if buf:
        out.append((cur, buf))
    return "".join(f'<span class="t-{c}">{html.escape(s)}</span>' if c else html.escape(s) for c, s in out)


def expand_excerpt(excerpt) -> list:
    """Excerpt items as line numbers, ``"..."`` gaps and ``{"line": n, "as": "str"}``; ``[a, b]`` expands to a..b."""
    out = []
    for item in excerpt:
        if isinstance(item, list) and len(item) == 2:
            out.extend(range(int(item[0]), int(item[1]) + 1))
        else:
            out.append(item)
    return out


def code_rows(src_lines: "list[str]", excerpt, source: str):
    """Row HTML, each source line's (first row, last row), and the rows that start a line or a gap."""
    rows, where, starts = [], {}, set()
    for item in expand_excerpt(excerpt):
        if item == "...":
            starts.add(len(rows))
            rows.append('<span class="k-no"> </span><span class="k-tx t-gap">    …</span>')
            continue
        force = None
        if isinstance(item, dict):
            item, force = item.get("line"), item.get("as")
        if not isinstance(item, (int, str)) or not str(item).isdigit():
            raise SpecError(f"source {source}: excerpt item {item!r} is not a line number, [a, b] range or \"...\"")
        n = int(item)
        if not 1 <= n <= len(src_lines):
            raise SpecError(f"source {source}: line {n} is outside 1..{len(src_lines)}")
        text = src_lines[n - 1].rstrip("\n")
        classes = char_classes(text, force)
        cuts, indent = wrap_points(text)
        first = len(rows)
        starts.add(first)
        for k, (a, b) in enumerate(cuts):
            pad = "" if k == 0 else " " * min(indent + 4, WRAP - MIN_TAIL)
            no = str(n) if k == 0 else " "
            rows.append(f'<span class="k-no">{no}</span><span class="k-tx">{pad}{_spans(text, classes, a, b)}</span>')
        where[n] = (first, len(rows) - 1)
    return rows, where, starts


def snap_scroll(top: int, r0: int, r1: int, visible: int, starts: "set[int]") -> int:
    """``top`` moved onto the start of a line, so the window never opens on a soft-wrapped tail row.

    Snapping down may scroll past the last row, leaving blank rows at the bottom of the panel.
    """
    if top in starts:
        return top
    up = max((s for s in starts if s <= top), default=0)
    if r1 - up < visible:
        return up
    return min((s for s in starts if top < s <= r0), default=top)


class Builder:
    """Turns a placed project (spec, brand, timeline and word timings) into HyperFrames scenes.

    Construction reads every input and raises ``SpecError`` when one is missing or stale, so a
    builder that exists has everything ``build`` needs.
    """

    def __init__(self, project: Project):
        self.p = project
        self.timeline = _read_json(project.root / "kit" / "timeline.json", "kit/timeline.json (run timeline first)")
        self.start = {s["id"]: s["start"] for s in self.timeline["scenes"]}
        self.dur = {s["id"]: s["dur"] for s in self.timeline["scenes"]}
        missing = [s["id"] for s in project.spec["scenes"] if s["id"] not in self.start]
        if missing:
            raise SpecError(f"kit/timeline.json has no scene {', '.join(missing)}; run timeline again")
        self.words = {}
        for lid in project.lines:
            path = project.root / "assets" / "voice" / f"{lid}.words.json"
            self.words[lid] = _read_json(path, f"word timings for line {lid} (run voice.py align)")
        self.shift = {str(k): float(v) for k, v in (project.spec.get("sync_shift") or {}).items()}
        self.colors = role_colors(project)
        self.families, self.font_files = brand_fonts(project)
        self.css = root_css(self.colors, self.families, self.font_files)
        self.sources = {}
        for key, rel in (project.spec.get("sources") or {}).items():
            path = project.root / rel
            if not path.is_file():
                raise SpecError(f"source {key}: {path} not found")
            self.sources[key] = path.read_text(encoding="utf-8").split("\n")
        self.beats = []

    def film(self, cue: str) -> float:
        """Film time of a cue ``line:word`` or ``line:word#n`` (the nth word starting with ``word``)."""
        m = re.fullmatch(r"([A-Za-z0-9_.-]+):([^#]+)(?:#(\d+))?", str(cue).strip())
        if not m:
            raise SpecError(f"cue {cue!r} must look like line:word or line:word#n")
        lid, word, nth = m.group(1), m.group(2), int(m.group(3) or 0)
        if lid not in self.words:
            raise SpecError(f"cue {cue!r}: no line {lid!r}")
        key = re.sub(r"[^a-z0-9]", "", word.lower())
        hits = [w for w in self.words[lid] if re.sub(r"[^a-z0-9]", "", str(w["text"]).lower()).startswith(key)]
        if len(hits) <= nth:
            heard = " ".join(str(w["text"]).strip() for w in self.words[lid])
            raise SpecError(f"cue {cue!r}: line {lid} has no word {nth + 1} starting with {word!r}; heard: {heard}")
        return round(float(self.p.lines[lid]["start_s"]) + float(hits[nth]["start"]), 3)

    def local(self, sid: str, cue: str) -> float:
        """Scene-local tween start for a cue: one frame before the word, plus any measured sync_shift."""
        return round(self.film(cue) - self.start[sid] - FRAME + self.shift.get(str(cue), 0.0), 3)

    def fill(self, sid: str, text: str) -> str:
        return CUE_RE.sub(lambda m: str(self.local(sid, m.group(1))), text)

    def beat(self, bid: str, cue: str, region, sid: str, baseline_local: float) -> None:
        lid, word = str(cue).split(":", 1)
        self.beats.append({
            "id": bid, "word": word.split("#")[0], "clip": f"assets/voice/{lid}.wav",
            "clip_start_s": self.p.lines[lid]["start_s"], "expected_s": self.film(cue),
            "region": [int(v) for v in region], "baseline_s": round(self.start[sid] + baseline_local, 3),
            "detector": "changed", "color": None,
        })

    def composition(self, sid: str, markup: str, js: "list[str]", extra_css: str = "") -> str:
        script = "\n    ".join(js)
        return f"""<template>
  <style>
{self.css}{KIT_CSS}{extra_css}
  </style>
  <div id="root" data-composition-id="{sid}" data-width="1920" data-height="1080">
{markup}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {script}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""

    def header(self, sid: str, scene: dict) -> "tuple[str, list[str]]":
        markup, js = "", []
        if scene.get("eyebrow"):
            markup += f'<div class="k-eyebrow" id="{sid}-eye">{html.escape(scene["eyebrow"])}</div>'
            js.append(f'tl.fromTo("#{sid}-eye", {{ opacity: 0.3 }}, {{ opacity: 1, {ENTER} }}, 0);')
        if scene.get("heading"):
            markup += f'<div class="k-head" id="{sid}-head">{html.escape(scene["heading"])}</div>'
            js.append(f'tl.fromTo("#{sid}-head", {{ opacity: 0.3, y: 16 }}, {{ opacity: 1, y: 0, {ENTER} }}, 0);')
        chip_markup, chip_js = self.chips(sid, scene.get("chips") or [])
        return markup + chip_markup, js + chip_js

    def chips(self, sid: str, items: list) -> "tuple[str, list[str]]":
        """Chips swap in place; each exits just before the next enters, so two never show at once."""
        if not items:
            return "", []
        timed = [(self.local(sid, c["at"]), c["text"]) for c in items]
        markup = "".join(
            f'<div class="k-chipw" id="{sid}-c{k}"><span class="k-chip">{html.escape(text)}</span></div>'
            for k, (_, text) in enumerate(timed))
        js = []
        for k, (t, _) in enumerate(timed):
            js.append(f'gsap.set("#{sid}-c{k}", {{ opacity: 0, y: 12 }});')
            js.append(f'tl.fromTo("#{sid}-c{k}", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "expo.out" }}, {t});')
            if k + 1 < len(timed):
                out = round(timed[k + 1][0] - 0.22, 3)
                js.append(f'tl.fromTo("#{sid}-c{k}", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.2, ease: "power2.in", immediateRender: false }}, {out});')
        return f'<div class="k-chips">{markup}</div>', js

    def sub(self, sid: str, sub: Optional[dict], top: int) -> "tuple[str, list[str]]":
        if not sub:
            return "", []
        at = self.local(sid, sub["at"]) if sub.get("at") else 0.4
        markup = f'<div class="k-sub" id="{sid}-sub" style="top:{int(sub.get("top", top))}px">{html.escape(sub["text"])}</div>'
        return markup, [f'gsap.set("#{sid}-sub", {{ opacity: 0, y: 24 }});',
                        f'tl.fromTo("#{sid}-sub", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, {ENTER} }}, {at});']

    def scene_cards(self, sid: str, scene: dict) -> str:
        cards = scene.get("cards") or []
        if not 1 <= len(cards) <= 3:
            raise SpecError(f"scene {sid}: cards needs 1 to 3 cards")
        top = int(scene.get("top", 430))
        xs = [120, 710, 1300]
        markup, js = self.header(sid, scene)
        for k, card in enumerate(cards):
            x = xs[k]
            markup += (f'<div class="k-card" id="{sid}-card{k}" style="left:{x}px;top:{top}px;width:500px;height:240px">'
                       f'<div class="k-card-eye">{html.escape(card.get("eye", ""))}</div>'
                       f'<div class="k-card-title">{html.escape(card.get("title", ""))}</div></div>'
                       f'<div class="k-ring" id="{sid}-ring{k}" style="left:{x - 10}px;top:{top - 10}px;width:520px;height:260px"></div>')
            js.append(f'gsap.set("#{sid}-ring{k}", {{ opacity: 0 }});')
            at = self.local(sid, card["enter"]) if card.get("enter") else round(0.1 + 0.06 * k, 3)
            if k and scene.get("arrows", True):
                markup += f'<div class="k-arrow" id="{sid}-ar{k}" style="left:{x - 90}px;top:{top + 117}px;width:90px"></div>'
                js.append(f'gsap.set("#{sid}-ar{k}", {{ scaleX: 0 }});')
                js.append(f'tl.fromTo("#{sid}-ar{k}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.3, ease: "expo.out" }}, {at});')
            start_opacity = 0.3 if not card.get("enter") else 0
            js.append(f'gsap.set("#{sid}-card{k}", {{ opacity: {start_opacity}, y: 24 }});')
            js.append(f'tl.fromTo("#{sid}-card{k}", {{ opacity: {start_opacity}, y: 24 }}, {{ opacity: 1, y: 0, {ENTER} }}, {at});')
            if card.get("enter") and at >= 0.9:
                self.beat(f"{sid}-card{k}", card["enter"], [x + 50, top + 50, 400, 140], sid, at - 0.5)
            if card.get("ring"):
                rt = self.local(sid, card["ring"])
                js.append(f'tl.fromTo("#{sid}-ring{k}", {{ opacity: 0, scale: 1.06 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "expo.out" }}, {rt});')
                if rt - 0.5 >= max(at + 0.45, 0.5):
                    self.beat(f"{sid}-ring{k}", card["ring"], [x - 10, top, 30, 240], sid, rt - 0.5)
        sub_markup, sub_js = self.sub(sid, scene.get("sub"), top + 350)
        markup += sub_markup
        js += sub_js
        end = scene.get("end_card")
        if end:
            logo = self.logo_tag()
            at = round(self.local(sid, end["at"]) + float(end.get("delay", 0)), 3) if end.get("at") else 0.4
            markup += (f'<div id="{sid}-end" style="position:absolute;left:120px;top:{int(end.get("top", top + 430))}px;'
                       f'display:flex;align-items:center;gap:40px">{logo}'
                       f'<span class="k-eyebrow" style="position:static;color:var(--ink)">{html.escape(end.get("text", ""))}</span></div>')
            js += [f'gsap.set("#{sid}-end", {{ opacity: 0, y: 24 }});',
                   f'tl.fromTo("#{sid}-end", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, {ENTER} }}, {at});']
        css = (f"\n[id^={sid}-card] .k-card-title {{ font-size: {int(scene['card_title_px'])}px; line-height: {int(scene['card_title_px']) + 8}px; }}"
               if scene.get("card_title_px") else "")
        return self.composition(sid, markup, js, css)

    def scene_files(self, sid: str, scene: dict) -> str:
        files = scene.get("files") or []
        if not 1 <= len(files) <= 6:
            raise SpecError(f"scene {sid}: files needs 1 to 6 rows")
        markup, js = self.header(sid, scene)
        js.append(f'gsap.set("[id^={sid}-hl]", {{ opacity: 0 }});')
        for k, row in enumerate(files):
            y = 240 + k * 112
            tag = f'<span class="k-tag" style="margin-left:20px">{html.escape(row["tag"])}</span>' if row.get("tag") else ""
            markup += (
                f'<div class="k-hl" id="{sid}-hl{k}" style="left:120px;top:{y}px;width:1680px;height:88px;border-radius:8px"></div>'
                f'<div id="{sid}-r{k}" style="position:absolute;left:120px;top:{y}px;width:1680px;height:88px;border-bottom:2px solid var(--rule);display:flex;align-items:center;padding:0 28px">'
                f'<span class="k-mono" style="flex:1">{html.escape(row["path"])}</span>'
                f'<span class="k-mono" style="color:var(--str);font-weight:700">{html.escape(row.get("add", ""))}</span>'
                f'<span class="k-mono" style="color:var(--bad);font-weight:700;margin-left:16px;min-width:40px">{html.escape(row.get("remove", ""))}</span>{tag}</div>')
            if row.get("highlight"):
                t = self.local(sid, row["highlight"])
                js.append(f'tl.fromTo("#{sid}-hl{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "expo.out" }}, {t});')
                if t >= 1.1:
                    self.beat(f"{sid}-row{k}", row["highlight"], [128, y + 10, 60, 60], sid, t - 0.6)
        js.append(f'tl.fromTo("[id^={sid}-r]", {{ opacity: 0.3, y: 16 }}, {{ opacity: 1, y: 0, {ENTER}, stagger: 0.06 }}, 0.1);')
        return self.composition(sid, markup, js)

    def scene_panels(self, sid: str, scene: dict) -> str:
        panels = scene.get("panels") or []
        if not 1 <= len(panels) <= 2:
            raise SpecError(f"scene {sid}: panels needs 1 or 2 panels")
        top, height = int(scene.get("top", 240)), int(scene.get("height", 600))
        width = 1680 if len(panels) == 1 else 820
        markup, js = self.header(sid, scene)
        for k, panel in enumerate(panels):
            pid, x = f"{sid}-p{k}", 120 + k * 860
            body_top = 90
            inner = f'<div class="k-card-eye" style="position:absolute;left:32px;top:28px">{html.escape(panel.get("eye", ""))}</div>'
            if panel.get("title"):
                inner += (f'<div style="position:absolute;left:32px;top:76px;font-family:var(--font-display);font-weight:500;'
                          f'font-size:80px;line-height:96px">{html.escape(panel["title"])}</div>')
                body_top = 196
            mono = panel.get("mono", True)
            step = 64 if mono else 52
            rows_html = ""
            for r, row in enumerate(panel.get("rows") or []):
                y = body_top + r * step
                if isinstance(row, list):
                    rows_html += (f'<div style="position:absolute;left:32px;top:{y}px;display:flex;align-items:baseline">'
                                  f'<span style="width:210px;font-family:var(--font-body);font-size:30px;line-height:44px;color:var(--muted)">{html.escape(str(row[0]))}</span>'
                                  f'<span class="k-mono">{html.escape(str(row[1]))}</span></div>')
                elif mono:
                    rows_html += f'<div class="k-mono" style="position:absolute;left:40px;top:{y}px">{html.escape(str(row))}</div>'
                else:
                    rows_html += (f'<div style="position:absolute;left:32px;top:{y}px;font-family:var(--font-body);font-size:36px;'
                                  f'line-height:52px">· {html.escape(str(row))}</div>')
            steps = panel.get("steps") or []
            if steps:
                first = int(steps[0]["row"])
                inner += (f'<div class="k-hl" id="{pid}-band" style="left:0;top:{body_top + first * step - 10}px;'
                          f'width:100%;height:{step}px"></div>')
                js.append(f'gsap.set("#{pid}-band", {{ opacity: 0 }});')
                prev = first
                for n, st in enumerate(steps):
                    t = self.local(sid, st["at"])
                    if n == 0:
                        js.append(f'tl.fromTo("#{pid}-band", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "expo.out" }}, {t});')
                    else:
                        js.append(f'tl.fromTo("#{pid}-band", {{ y: {(prev - first) * step} }}, {{ y: {(int(st["row"]) - first) * step}, '
                                  f'duration: 0.35, ease: "expo.out", immediateRender: false }}, {t});')
                    prev = int(st["row"])
            markup += (f'<div class="k-card" id="{pid}" style="left:{x}px;top:{top}px;width:{width}px;height:{height}px;padding:0">'
                       f'{inner}{rows_html}</div>')
            at = self.local(sid, panel["enter"]) if panel.get("enter") else round(0.1 + 0.06 * k, 3)
            start_opacity = 0 if panel.get("enter") else 0.3
            js.append(f'gsap.set("#{pid}", {{ opacity: {start_opacity}, y: 24 }});')
            js.append(f'tl.fromTo("#{pid}", {{ opacity: {start_opacity}, y: 24 }}, {{ opacity: 1, y: 0, {ENTER} }}, {at});')
            if panel.get("enter") and at >= 0.9:
                self.beat(f"{pid}", panel["enter"], [x + 40, top + 50, min(width - 80, 500), 200], sid, at - 0.5)
        sub_markup, sub_js = self.sub(sid, scene.get("sub"), top + height + 40)
        footer = ""
        if scene.get("footer"):
            footer = (f'<div class="k-mono" id="{sid}-fx" style="position:absolute;left:120px;top:{top + height + 40}px;'
                      f'font-size:28px;color:var(--muted)">{html.escape(scene["footer"])}</div>')
            js.append(f'tl.fromTo("#{sid}-fx", {{ opacity: 0.3 }}, {{ opacity: 1, {ENTER} }}, 0.6);')
        return self.composition(sid, markup + sub_markup + footer, js + sub_js)

    def scene_code(self, sid: str, scene: dict) -> str:
        source = str(scene.get("source"))
        if source not in self.sources:
            raise SpecError(f"scene {sid}: source {source!r} is not in spec.sources")
        rows, where, starts = code_rows(self.sources[source], scene.get("excerpt") or [], source)
        top = int(scene.get("top", 220))
        visible = int(scene.get("visible", min(17, len(rows))))
        height = visible * ROW_H + 2 * CODE_PAD
        js: "list[str]" = []
        band = None
        scroll, scrolled, scrolls = 0, False, []
        for b in scene.get("bands") or []:
            a, z = int(b["lines"][0]), int(b["lines"][-1])
            if a not in where or z not in where:
                raise SpecError(f"scene {sid}: band lines {a}-{z} are not both in the excerpt")
            t = self.local(sid, b["at"])
            r0, r1 = where[a][0], where[z][1]
            count = r1 - r0 + 1
            new = scroll
            if r1 > scroll + visible - 1:
                new = min(r0, r1 - visible + 1)
            if r0 < scroll:
                new = r0
            new = max(0, min(new, len(rows) - visible))
            new = snap_scroll(new, r0, r1, visible, starts)
            moved = new != scroll
            if moved:
                ts = round(max(0, t - 0.3), 3)
                imm = ", immediateRender: false" if scrolled else ""
                js.append(f'tl.fromTo("#{sid}-scroll", {{ y: {-scroll * ROW_H} }}, {{ y: {-new * ROW_H}, duration: 0.5, ease: "power2.inOut"{imm} }}, {ts});')
                scrolls.append((ts, scroll, new))
                scrolled, scroll = True, new
            if band is None:
                js.insert(0, f'gsap.set("#{sid}-band", {{ opacity: 0, y: {r0 * ROW_H}, scaleY: {count} }});')
                js.append(f'tl.fromTo("#{sid}-band", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "expo.out" }}, {t});')
                if not moved and t >= 1.1:
                    y = top + CODE_PAD + (r0 - scroll) * ROW_H
                    self.beat(f"{sid}-band", b["at"], [130, y + 4, 100, min(count, 3) * ROW_H - 8], sid, t - 0.6)
            else:
                js.append(f'tl.fromTo("#{sid}-band", {{ y: {band[0] * ROW_H}, scaleY: {band[1]} }}, '
                          f'{{ y: {r0 * ROW_H}, scaleY: {count}, duration: 0.35, ease: "expo.out", immediateRender: false }}, {t});')
            band = (r0, count)
        # rows outside the panel window stay hidden so the layout audit only sees what a viewer sees
        sel = lambda idx: ", ".join(f"#{sid}-row{i}" for i in sorted(idx))  # noqa: E731
        hidden = set(range(visible, len(rows)))
        if hidden:
            js.append(f'gsap.set("{sel(hidden)}", {{ visibility: "hidden" }});')
        for ts, a, b in scrolls:
            old, new = set(range(a, min(a + visible, len(rows)))), set(range(b, min(b + visible, len(rows))))
            if new - old:
                js.append(f'tl.set("{sel(new - old)}", {{ visibility: "visible" }}, {ts});')
            if old - new:
                js.append(f'tl.set("{sel(old - new)}", {{ visibility: "hidden" }}, {round(ts + 0.5, 3)});')
        row_html = "".join(f'<div class="k-row" id="{sid}-row{i}" style="top:{CODE_PAD + i * ROW_H}px">{r}</div>'
                           for i, r in enumerate(rows))
        panel = (f'<div class="k-code" id="{sid}-code" style="top:{top}px;height:{height}px">'
                 f'<div class="k-scroll" id="{sid}-scroll"><div class="k-band" id="{sid}-band"></div>{row_html}</div>'
                 f'<div class="k-mask" style="top:0"></div><div class="k-mask" style="bottom:0"></div></div>')
        head_markup, head_js = self.header(sid, scene)
        js = head_js + [f'tl.fromTo("#{sid}-code", {{ opacity: 0.3, y: 24 }}, {{ opacity: 1, y: 0, {ENTER} }}, 0.1);'] + js
        extra_html = self.fill(sid, scene.get("extra_html", ""))
        extra_js = [self.fill(sid, line) for line in scene.get("extra_js") or []]
        return self.composition(sid, head_markup + panel + extra_html, js + extra_js)

    def scene_custom(self, sid: str, scene: dict) -> str:
        path = self.p.root / str(scene.get("file", ""))
        if not scene.get("file") or not path.is_file():
            raise SpecError(f"scene {sid}: custom file {path} not found")
        text = path.read_text(encoding="utf-8").replace("{{kit_css}}", self.css + KIT_CSS)
        return self.fill(sid, text)

    def logo_tag(self) -> str:
        logo = self.p.brand.get("logo")
        if not logo or not (self.p.brand_dir / logo).is_file():
            return ""
        return f'<img src="assets/{Path(logo).name}" alt="{html.escape(str(self.p.brief.get("product", "")))}" style="height:74px">'

    def build(self) -> dict:
        """Write every composition, ``scenes/index.html``, the copied assets and ``beats.json``; return a summary.

        Raises ``SpecError`` when ``scenes/`` is not a HyperFrames project or a scene names something missing.
        """
        scenes_dir = self.p.root / "scenes"
        if not (scenes_dir / "index.html").is_file():
            raise SpecError(f"{scenes_dir} is not a HyperFrames project; run hf.py --project DIR -- init {scenes_dir} --non-interactive")
        comp_dir = scenes_dir / "compositions"
        comp_dir.mkdir(exist_ok=True)
        written = []
        for scene in self.p.spec["scenes"]:
            sid = scene["id"]
            page = getattr(self, f"scene_{scene['type']}")(sid, scene)
            (comp_dir / f"{sid}.html").write_text(page, encoding="utf-8")
            written.append(f"compositions/{sid}.html")
        assets = scenes_dir / "assets"
        (assets / "fonts").mkdir(parents=True, exist_ok=True)
        (assets / "voice").mkdir(parents=True, exist_ok=True)
        for _, path, _ in self.font_files:
            shutil.copy(path, assets / "fonts" / path.name)
        logo = self.p.brand.get("logo")
        if logo and (self.p.brand_dir / logo).is_file():
            shutil.copy(self.p.brand_dir / logo, assets / Path(logo).name)
        audio = []
        for lid, line in self.p.lines.items():
            shutil.copy(self.p.voice(lid), assets / "voice" / f"{lid}.wav")
            audio.append(f'  <audio id="vo-{lid}" class="clip" src="assets/voice/{lid}.wav" data-start="{line["start_s"]}" '
                         f'data-duration="{round(wav_seconds(self.p.voice(lid)), 3)}" data-track-index="3" data-volume="1"></audio>')
        hosts = "\n".join(
            f'  <div id="{s["id"]}" class="clip" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" '
            f'data-start="{s["start"]}" data-duration="{s["dur"]}" data-track-index="1" data-width="1920" data-height="1080" style="z-index: 1"></div>'
            for s in self.timeline["scenes"])
        total = self.timeline["total"]
        (scenes_dir / "index.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{self.css}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: var(--ground); font-family: var(--font-body); }}
#root {{ width: 100%; height: 100%; position: relative; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1920" data-height="1080">
{hosts}
{chr(10).join(audio)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
  window.__timelines["main"] = tl;
</script>
</body>
</html>
""", encoding="utf-8")
        (self.p.root / "beats.json").write_text(json.dumps(self.beats, indent=1) + "\n", encoding="utf-8")
        return {"scenes": [s["id"] for s in self.p.spec["scenes"]], "compositions": written,
                "beats": len(self.beats), "duration": total}


def main(argv: Optional["list[str]"] = None) -> int:
    parser = _Parser(prog="code_walkthrough.py", description="Build a code-walkthrough video from a JSON spec.")
    parser.add_argument("command", choices=("timeline", "build"))
    parser.add_argument("--project", required=True, help="video project folder")
    parser.add_argument("--spec", help="spec file (default <project>/kit/walkthrough.json)")
    ns = parser.parse_args(argv)
    root = Path(ns.project).expanduser()
    if not root.is_dir():
        emit({"error": f"project directory not found: {root}"}, EXIT_FAILED)
    try:
        project = Project(root, Path(ns.spec).expanduser() if ns.spec else None)
        if ns.command == "timeline":
            emit(timeline(project))
        emit(Builder(project).build())
    except (SpecError, FileNotFoundError) as exc:
        emit({"error": str(exc)}, EXIT_FAILED)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError, EOFError, wave.Error, OSError) as exc:
        emit({"error": f"malformed spec or project input: {type(exc).__name__}: {exc}"}, EXIT_FAILED)
    return 0


if __name__ == "__main__":
    sys.exit(main())
