#!/usr/bin/env python3
"""Narration for the making-videos skill: Kokoro speech, word alignment and SRT captions.

Every subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 ok; 1 the operation failed (the JSON has an ``error`` key); 2 usage error;
3 a required tool or venv is missing (the JSON has ``fix``, the command to run).
``say`` and ``align`` are launchers: the models and their Python dependencies live in the cache
venv, so the work runs in ``voice_worker.py`` under that interpreter. ``captions`` is stdlib only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple, NoReturn, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_USAGE,
    SCRUB_ENV,
    cache_root,
    emit,
    ffmpeg_full_candidates,
    load_brief,
    run,
    studio_root,
    venv_python,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
WORKER = SCRIPTS_DIR / "voice_worker.py"
DOCTOR_FIX = f"python3 {SCRIPTS_DIR / 'doctor.py'} install --what tts --yes"
FFMPEG_FIX = "brew install ffmpeg-full"
FFPROBE_TIMEOUT_S = 60

CLIP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WORKER_TIMEOUT_S = 3600
FFMPEG_TIMEOUT_S = 3600

MAX_LINES = 2
MAX_LINE_CHARS = 42
MAX_CPS = 20.0
MIN_CUE_S = 1.0
PAUSE_BREAK_S = 0.6
MAX_REFLOW_GROUPS = 4
SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _fail(message: str, code: int = EXIT_FAILED, **extra: object) -> NoReturn:
    print(message, file=sys.stderr)
    emit({"error": message, **extra}, code)


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _read_json(path: Path, what: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"{what} not found: {path}")
    except (OSError, UnicodeError) as exc:
        _fail(f"cannot read {what} {path}: {exc}")
    except json.JSONDecodeError as exc:
        _fail(f"{what} {path} is not valid JSON: {exc}")


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _load_lines(path: str, need_text: bool) -> "list[dict]":
    lines = _read_json(Path(path), "lines file")
    if not isinstance(lines, list) or not lines:
        _fail("lines file must be a non-empty JSON list of {id, text, start_s}")
    seen = set()
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            _fail(f"lines[{i}] must be an object")
        clip = line.get("id")
        if not isinstance(clip, str) or not CLIP_ID_RE.match(clip):
            _fail(f"lines[{i}] has an invalid id {clip!r}: use letters, digits, '.', '_' or '-'")
        if clip in seen:
            _fail(f"duplicate clip id {clip!r}")
        seen.add(clip)
        if need_text and not (isinstance(line.get("text"), str) and line["text"].strip()):
            _fail(f"lines[{i}] ({clip}) needs a non-empty text")
        if not _number(line.get("start_s")):
            _fail(f"lines[{i}] ({clip}) needs a numeric start_s")
    return lines


def _require_project(path: str) -> Path:
    project = Path(path)
    if not project.is_dir():
        _fail(f"project folder not found: {project}")
    return project


def _brand(project: Path) -> Optional[dict]:
    try:
        product = load_brief(project).get("product")
    except FileNotFoundError as exc:
        _fail(str(exc))
    except (OSError, ValueError) as exc:
        _fail(f"cannot read brief.json in {project}: {exc}")
    if not isinstance(product, str) or not product:
        return None
    path = studio_root() / "brands" / product / "brand.json"
    if not path.is_file():
        return None
    brand = _read_json(path, "brand")
    if not isinstance(brand, dict):
        _fail(f"brand {path} must be a JSON object")
    return brand


def _valid_pronunciations(raw: object) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        _fail("brand pronunciations must be an object of {word: {from, to}}")
    for word, patch in raw.items():
        if not (
            isinstance(patch, dict)
            and isinstance(patch.get("from"), str)
            and isinstance(patch.get("to"), str)
            and patch["from"]
        ):
            _fail(f"brand pronunciation for {word!r} needs non-empty string 'from' and 'to'")
    return raw


def _child_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in SCRUB_ENV}


def _ffmpeg_binary() -> str:
    override = os.environ.get("QUIRK_FFMPEG")
    if override:
        return override
    full = ffmpeg_full_candidates()
    return str(full[0]) if full else "ffmpeg"


def _ffprobe_binary() -> str:
    override = os.environ.get("QUIRK_FFPROBE")
    if override:
        return override
    sibling = Path(_ffmpeg_binary()).with_name("ffprobe")
    return str(sibling) if sibling.is_file() else "ffprobe"


def _require_venv() -> Path:
    python = venv_python()
    if not python.exists():
        _fail(
            f"the narration venv is not installed: {python}",
            EXIT_MISSING_TOOL,
            missing="tts venv",
            fix=DOCTOR_FIX,
        )
    return python


def _run_worker(args_list: "list[str]", extra_env: Optional[dict] = None) -> dict:
    python = _require_venv()
    env = _child_env()
    env["ORT_DISABLE_TELEMETRY"] = "1"
    env["HF_HOME"] = str(cache_root() / "hf")
    env.update(extra_env or {})
    try:
        proc = run([str(python), str(WORKER), *args_list], env=env, timeout=WORKER_TIMEOUT_S)
    except FileNotFoundError:
        _fail(
            f"cannot execute {python}",
            EXIT_MISSING_TOOL,
            missing="tts venv",
            fix=DOCTOR_FIX,
        )
    except Exception as exc:  # TimeoutExpired and OSError both end the operation
        _fail(f"voice worker did not finish: {type(exc).__name__}: {exc}")
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        _fail(f"voice worker failed (exit {proc.returncode}): {_tail(proc.stderr)}")
    last = [line for line in proc.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(last[-1]) if last else None
    except json.JSONDecodeError:
        result = None
    if not isinstance(result, dict):
        _fail(f"voice worker printed no JSON object: {_tail(proc.stdout)}")
    return result


def _cmd_say(args: argparse.Namespace) -> None:
    _require_venv()
    project = _require_project(args.project)
    lines = _load_lines(args.lines, need_text=True)
    brand = _brand(project)
    voice = args.voice
    if voice is None:
        voice_cfg = (brand or {}).get("voice")
        if not isinstance(voice_cfg, dict) or not voice_cfg.get("id"):
            _fail("no --voice given and the project's brand has no voice.id")
        if voice_cfg.get("engine", "kokoro") != "kokoro":
            _fail(
                f"brand voice engine is {voice_cfg.get('engine')!r}; say.py only makes Kokoro "
                "voices. Make cloud voices with cloud.py."
            )
        voice = voice_cfg["id"]
    pronunciations = _valid_pronunciations((brand or {}).get("pronunciations"))
    out_dir = project / "assets" / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = _run_worker(
        [
            "say",
            "--lines",
            str(Path(args.lines).resolve()),
            "--voice",
            voice,
            "--out-dir",
            str(out_dir),
            "--model-dir",
            str(cache_root() / "models" / "kokoro"),
            "--pronunciations",
            json.dumps(pronunciations, ensure_ascii=False),
        ]
    )
    emit(result)


def _cmd_align(args: argparse.Namespace) -> None:
    _require_venv()
    project = _require_project(args.project)
    wavs = sorted((project / "assets" / "voice").glob("*.wav"))
    if not wavs:
        _fail(f"no clips under {project / 'assets' / 'voice'}; run voice.py say first")
    result = _run_worker(
        ["align", "--model", args.model, "--ffmpeg", _ffmpeg_binary(), "--wavs", *map(str, wavs)]
    )
    emit(result)


class Word(NamedTuple):
    text: str
    start: float
    end: float


class Cue(NamedTuple):
    start: float
    end: float
    lines: "list[str]"


def _wrap(words: "list[Word]") -> Optional["list[str]"]:
    """Lay ``words`` out in at most two balanced lines, or None when they do not fit."""
    texts = [w.text for w in words]
    whole = " ".join(texts)
    if len(whole) <= MAX_LINE_CHARS or len(texts) == 1:
        return [whole]
    best: Optional["list[str]"] = None
    for i in range(1, len(texts)):
        first, second = " ".join(texts[:i]), " ".join(texts[i:])
        if max(len(first), len(second)) <= MAX_LINE_CHARS and (
            best is None or max(len(first), len(second)) < max(map(len, best))
        ):
            best = [first, second]
    return best


def _group(words: "list[Word]") -> "list[list[Word]]":
    groups: "list[list[Word]]" = []
    current: "list[Word]" = []
    for word in words:
        if current and (
            word.start - current[-1].end >= PAUSE_BREAK_S
            or SENTENCE_END.search(current[-1].text)
            or _wrap(current + [word]) is None
        ):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def _chars(words: "list[Word]") -> int:
    return len(" ".join(w.text for w in words))


def _ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def _fast_enough(chars: int, start: float, end: float) -> bool:
    """True when ``chars`` shown from ``start`` to ``end`` stay within the speed limit, to the millisecond."""
    return chars * 1000 <= MAX_CPS * (_ms(end) - _ms(start))


def _fit(words: "list[Word]", next_start: float) -> float:
    """End time for a cue, stretched to the reading-speed and minimum-length floors.

    The end never passes ``next_start``.
    """
    start = words[0].start
    reading = (_ms(start) + math.ceil(_chars(words) * 1000 / MAX_CPS)) / 1000
    wanted = max(words[-1].end, reading, start + MIN_CUE_S)
    return min(wanted, next_start)


def _speed_ok(words: "list[Word]", next_start: float) -> bool:
    return _fast_enough(_chars(words), words[0].start, _fit(words, next_start))


def _chain_ok(parts: "list[list[Word]]", next_start: float) -> bool:
    for j, part in enumerate(parts):
        following = parts[j + 1][0].start if j + 1 < len(parts) else next_start
        if not _speed_ok(part, following):
            return False
    return True


def _worst_ratio(parts: "list[list[Word]]", next_start: float) -> float:
    worst = 0.0
    for j, part in enumerate(parts):
        following = parts[j + 1][0].start if j + 1 < len(parts) else next_start
        span = max(_fit(part, following) - part[0].start, 1e-6)
        worst = max(worst, _chars(part) / span)
    return worst


def _repair(groups: "list[tuple[int, list[Word]]]", i: int) -> "Optional[tuple[int, int, list[list[Word]]]]":
    """Merge group ``i`` with its neighbours in the same clip and re-split at word boundaries.

    Returns ``(first, last, parts)`` replacing ``groups[first:last + 1]`` with cues that all meet
    the speed limit, or None when no regrouping of nearby words can.
    """
    clip = groups[i][0]
    lo = i
    while lo > 0 and groups[lo - 1][0] == clip:
        lo -= 1
    hi = i
    while hi + 1 < len(groups) and groups[hi + 1][0] == clip:
        hi += 1
    for size in range(2, min(MAX_REFLOW_GROUPS, hi - lo + 1) + 1):
        for first in range(i, i - size, -1):
            last = first + size - 1
            if first < lo or last > hi:
                continue
            words = [w for _, g in groups[first : last + 1] for w in g]
            next_start = groups[last + 1][1][0].start if last + 1 < len(groups) else float("inf")
            candidates = [[words]] + [[words[:k], words[k:]] for k in range(1, len(words))]
            best = None
            for parts in candidates:
                if any(_wrap(p) is None for p in parts) or not _chain_ok(parts, next_start):
                    continue
                score = (len(parts), _worst_ratio(parts, next_start))
                if best is None or score < best[0]:
                    best = (score, parts)
            if best is not None:
                return first, last, best[1]
    return None


def _reflow(groups: "list[tuple[int, list[Word]]]") -> "list[tuple[int, list[Word]]]":
    groups = list(groups)
    i = 0
    while i < len(groups):
        next_start = groups[i + 1][1][0].start if i + 1 < len(groups) else float("inf")
        if _speed_ok(groups[i][1], next_start):
            i += 1
            continue
        fix = _repair(groups, i)
        if fix is None:
            i += 1
            continue
        first, last, parts = fix
        groups[first : last + 1] = [(groups[i][0], part) for part in parts]
        i = first + len(parts)
    return groups


def _pieces(text: str, start: float, end: float) -> "list[Word]":
    """``text`` as one Word, or hyphen-broken pieces of at most 42 characters sharing its time span."""
    if len(text) <= MAX_LINE_CHARS:
        return [Word(text, start, end)]
    size = MAX_LINE_CHARS - 1
    chunks = [text[i : i + size] + "-" for i in range(0, len(text) - MAX_LINE_CHARS, size)]
    chunks.append(text[size * len(chunks) :])
    total = sum(len(c) for c in chunks)
    words, cursor = [], start
    for n, chunk in enumerate(chunks):
        stop = end if n == len(chunks) - 1 else cursor + (end - start) * len(chunk) / total
        words.append(Word(chunk, cursor, stop))
        cursor = stop
    return words


def build_cues(clips: "list[tuple[float, list[dict]]]") -> "list[Cue]":
    """Cues for ``(start_s, words)`` clips on the video timeline.

    Each cue holds at most two lines of 42 characters; a longer word is broken with a hyphen. Cues
    are stretched to 20 characters per second and 1.0 s using only the silence before the next
    cue. Cues break at sentence ends, pauses of 0.6 s or more, clip boundaries and the line limits;
    a cue still too fast is regrouped with its neighbours in the same clip. Speech that is faster
    than 20 characters per second even then leaves an over-limit cue, which ``speed_violations``
    reports.
    """
    groups: "list[tuple[int, list[Word]]]" = []
    for index, (offset, raw) in enumerate(clips):
        words: "list[Word]" = []
        for w in raw:
            words.extend(_pieces(str(w["text"]), offset + float(w["start"]), offset + float(w["end"])))
        groups.extend((index, g) for g in _group(words))
    groups.sort(key=lambda g: g[1][0].start)
    groups = _reflow(groups)
    cues: "list[Cue]" = []
    for i, (_, group) in enumerate(groups):
        next_start = groups[i + 1][1][0].start if i + 1 < len(groups) else float("inf")
        end = _fit(group, next_start)
        cues.append(Cue(group[0].start, end, _wrap(group) or [" ".join(w.text for w in group)]))
    return cues


def speed_violations(cues: "list[Cue]") -> "list[dict]":
    """Cues shown faster than 20 characters per second, as ``{cue, start, end, cps}`` (cue is 1-based)."""
    found = []
    for n, cue in enumerate(cues, 1):
        chars = len(" ".join(cue.lines))
        if not _fast_enough(chars, cue.start, cue.end):
            seconds = (_ms(cue.end) - _ms(cue.start)) / 1000
            cps = round(chars / seconds, 2) if seconds > 0 else None
            found.append({"cue": n, "start": round(cue.start, 3), "end": round(cue.end, 3), "cps": cps})
    return found


def _timestamp(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(cues: "list[Cue]") -> str:
    """SubRip text for ``cues``: numbered blocks separated by blank lines."""
    blocks = [
        f"{n}\n{_timestamp(c.start)} --> {_timestamp(c.end)}\n" + "\n".join(c.lines) + "\n"
        for n, c in enumerate(cues, 1)
    ]
    return "\n".join(blocks)


def _filter_path(path: str) -> str:
    return re.sub(r"([\\:',\[\];])", r"\\\1", path)


class CaptionLayout(NamedTuple):
    """Caption placement in pixels of a reference frame of ``width`` x ``height``."""

    width: int
    height: int
    margin_bottom: int
    margin_left: int
    margin_right: int
    font: int
    outline: int


# 9:16 is the conservative envelope from the craft research (bottom 672, left 120, right 192 on
# 1080x1920) that clears TikTok, Reels and Shorts UI. The 1:1 and 16:9 figures are chosen here, not
# sourced: 1:1 keeps the 90% caption width BBC specifies, 16:9 keeps the 5% title-safe margin.
CAPTION_LAYOUTS = {
    "9:16": CaptionLayout(1080, 1920, 672, 120, 192, 48, 4),
    "1:1": CaptionLayout(1080, 1080, 108, 54, 54, 44, 4),
    "16:9": CaptionLayout(1920, 1080, 54, 96, 96, 54, 3),
}
ASPECTS = tuple(CAPTION_LAYOUTS)
ASS_PLAYRES_X = 384
ASS_PLAYRES_Y = 288


def aspect_of(width: int, height: int) -> str:
    """The supported aspect nearest to ``width`` x ``height``, compared on a log scale."""
    ratio = math.log(width / height)
    return min(ASPECTS, key=lambda a: abs(ratio - math.log(CAPTION_LAYOUTS[a].width / CAPTION_LAYOUTS[a].height)))


def caption_style(aspect: str, width: int, height: int) -> str:
    """The libass ``force_style`` string that places captions for ``aspect`` on a ``width`` x ``height`` frame.

    ffmpeg turns an SRT into an ASS script with PlayRes 384x288, and libass reads ``FontSize``,
    ``Outline`` and ``MarginV`` against PlayResY and ``MarginL``/``MarginR`` against PlayResX. The
    filter's ``original_size`` option only corrects pixel aspect and leaves PlayRes alone, so the
    pixel layout is converted here instead: vertical values times 288/height, horizontal margins
    times 384/width. Margins are rounded to whole units, so they land within about 4 px of the
    target on a 1080x1920 frame; font size and outline keep two decimals.
    """
    layout = CAPTION_LAYOUTS[aspect]
    sy = height / layout.height
    sx = width / layout.width
    down_y = ASS_PLAYRES_Y / height
    down_x = ASS_PLAYRES_X / width
    fields = [
        ("FontSize", round(layout.font * sy * down_y, 2)),
        ("Outline", round(layout.outline * sy * down_y, 2)),
        ("Shadow", 0),
        ("BorderStyle", 1),
        ("PrimaryColour", "&H00FFFFFF"),
        ("OutlineColour", "&H00000000"),
        ("Alignment", 2),
        ("MarginV", round(layout.margin_bottom * sy * down_y)),
        ("MarginL", round(layout.margin_left * sx * down_x)),
        ("MarginR", round(layout.margin_right * sx * down_x)),
    ]
    return ",".join(f"{name}={value}" for name, value in fields)


def _probe_size(video: Path) -> Optional["tuple[int, int]"]:
    """Displayed (width, height) of ``video``'s first video stream, or None when ffprobe cannot tell."""
    argv = [
        _ffprobe_binary(), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json", str(video),
    ]
    try:
        proc = run(argv, env=_child_env(), timeout=FFPROBE_TIMEOUT_S)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        stream = json.loads(proc.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        turns = [stream.get("tags", {}).get("rotate")] + [
            d.get("rotation") for d in stream.get("side_data_list", []) if isinstance(d, dict)
        ]
        rotated = any(t is not None and int(float(t)) % 180 == 90 for t in turns)
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (height, width) if rotated else (width, height)


def _resolve_layout(video: Path, srt: Path, aspect: Optional[str]) -> "tuple[str, int, int]":
    """Aspect and pixel size to style captions for; exits 2 when neither the flag nor the file says."""
    size = _probe_size(video)
    if aspect is None:
        if size is None:
            _fail(
                f"cannot tell the aspect of {video} (ffprobe could not read it); pass --aspect 16:9, 9:16 or 1:1",
                EXIT_USAGE,
                srt=str(srt),
            )
        return aspect_of(*size), size[0], size[1]
    if size is None:
        reference = CAPTION_LAYOUTS[aspect]
        print(f"ffprobe could not read {video}; assuming {reference.width}x{reference.height}", file=sys.stderr)
        return aspect, reference.width, reference.height
    seen = aspect_of(*size)
    if seen != aspect:
        _fail(
            f"--aspect {aspect} disagrees with {video}, which is {size[0]}x{size[1]} ({seen})",
            EXIT_USAGE,
            srt=str(srt),
        )
    return aspect, size[0], size[1]


def _burn(srt: Path, video: Path, out: Path, aspect: Optional[str] = None) -> None:
    ffmpeg = _ffmpeg_binary()
    missing = {"missing": "ffmpeg subtitles filter", "fix": FFMPEG_FIX}
    try:
        probe = run([ffmpeg, "-hide_banner", "-filters"], env=_child_env(), timeout=60)
    except FileNotFoundError:
        _fail(f"ffmpeg not found: {ffmpeg}", EXIT_MISSING_TOOL, **missing)
    except Exception as exc:
        _fail(f"cannot probe ffmpeg filters: {type(exc).__name__}: {exc}")
    if not re.search(r"(?m)^\s*\S+\s+subtitles\s", probe.stdout):
        _fail(
            f"{ffmpeg} has no 'subtitles' filter (built without libass)",
            EXIT_MISSING_TOOL,
            srt=str(srt),
            **missing,
        )
    if not video.is_file():
        _fail(f"video to burn into not found: {video}", srt=str(srt))
    aspect, width, height = _resolve_layout(video, srt, aspect)
    style = caption_style(aspect, width, height)
    out.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        ffmpeg, "-y", "-v", "error", "-i", str(video),
        "-vf", f"subtitles={_filter_path(str(srt))}:force_style='{style}'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "copy", "-movflags", "+faststart",
        str(out),
    ]
    try:
        proc = run(argv, env=_child_env(), timeout=FFMPEG_TIMEOUT_S)
    except Exception as exc:
        _fail(f"ffmpeg did not finish: {type(exc).__name__}: {exc}", srt=str(srt))
    if proc.returncode != 0:
        _fail(f"ffmpeg failed (exit {proc.returncode}): {_tail(proc.stderr)}", srt=str(srt))


def _cmd_captions(args: argparse.Namespace) -> None:
    if bool(args.burn) != bool(args.burned):
        _fail("--burn and --burned must be given together", EXIT_USAGE)
    project = _require_project(args.project)
    lines = _load_lines(args.lines, need_text=False)
    clips = []
    for line in lines:
        path = project / "assets" / "voice" / f"{line['id']}.words.json"
        if not path.is_file():
            _fail(f"no word timings for clip {line['id']!r} at {path}; run voice.py align first")
        words = _read_json(path, "word timings")
        if not isinstance(words, list) or not all(
            isinstance(w, dict) and "text" in w and _number(w.get("start")) and _number(w.get("end"))
            for w in words
        ):
            _fail(f"{path} must be a list of {{text, start, end}}")
        clips.append((float(line["start_s"]), words))
    cues = build_cues(clips)
    if not cues:
        _fail("no words in any clip, so there are no captions to write")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_srt(cues), encoding="utf-8")
    slow = speed_violations(cues)
    if slow:
        message = (
            f"{len(slow)} caption cue(s) exceed {MAX_CPS:g} characters per second because the "
            "narration is that fast; slow the narration or shorten the line, then rerun"
        )
        print(message, file=sys.stderr)
        emit({"ok": False, "error": message, "srt": str(out), "cps_violations": slow}, EXIT_FAILED)
    burned = None
    if args.burn:
        _burn(out, Path(args.burn), Path(args.burned), args.aspect)
        burned = str(Path(args.burned))
    emit({"srt": str(out), "burned": burned})


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="voice.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    say = sub.add_parser("say", help="synthesize each line with Kokoro into assets/voice/<id>.wav")
    say.add_argument("--project", required=True, help="project directory")
    say.add_argument("--lines", required=True, help="lines JSON: [{id, text, start_s}]")
    say.add_argument("--voice", help="Kokoro voice id; defaults to the brand's voice.id")
    say.set_defaults(func=_cmd_say)

    align = sub.add_parser("align", help="write <id>.words.json beside every clip in assets/voice")
    align.add_argument("--project", required=True, help="project directory")
    align.add_argument("--model", default="small.en", help="faster-whisper model name")
    align.set_defaults(func=_cmd_align)

    caps = sub.add_parser("captions", help="build an SRT from word timings, optionally burn it in")
    caps.add_argument("--project", required=True, help="project directory")
    caps.add_argument("--lines", required=True, help="lines JSON: [{id, start_s}]")
    caps.add_argument("--out", required=True, help="SRT file to write")
    caps.add_argument("--burn", help="video to burn the captions into")
    caps.add_argument("--burned", help="where to write the captioned video")
    caps.add_argument(
        "--aspect",
        choices=ASPECTS,
        help="caption placement for --burn; default: inferred from the video's size with ffprobe",
    )
    caps.set_defaults(func=_cmd_captions)
    return parser


def main(argv: Optional["list[str]"] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (OSError, UnicodeError) as exc:
        _fail(f"{type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
