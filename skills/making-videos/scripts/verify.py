#!/usr/bin/env python3
"""Strict verify for one rendered version of a making-videos project; writes ``<vN>/verify.json``.

Each check reads the source that can see it: the project's HTML and the render log (fonts),
HyperFrames ``check --json`` output (contrast, title-safe), the MP4 (loudness, voice sync, frames),
``guard.json`` files (Blender) and ``calls.jsonl`` (outside calls).

Prints exactly one JSON object to stdout; diagnostics go to stderr.
Exit codes: 0 every check passed or was skipped; 1 a check failed, or the MP4 is missing
(``{"error": "missing_render"}``); 2 usage error (missing project, version or flag, ambiguous MP4,
unreadable input); 3 ffmpeg or ffprobe is missing.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, Optional

# sibling modules are imported by bare name when this file is run by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_OK,
    EXIT_USAGE,
    emit,
    load_brief,
    studio_root,
    venv_python,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
HF_PY = SCRIPTS_DIR / "hf.py"
WORKER_PY = SCRIPTS_DIR / "media_worker.py"

MAX_ATTEMPTS = 3
LUFS_RANGE = (-17.0, -15.0)
TRUE_PEAK_MAX = -1.0
SHEET_COLUMNS, SHEET_ROWS = 4, 3
SHEET_TILE_WIDTH = 480
DEFAULT_STILLS = 6
LOCAL_PROVIDERS = frozenset({"hyperframes", "playwright"})
SKIPPED_DIRS = frozenset({"node_modules", ".hyperframes"})

BANDS = {
    "top": "x0=0;y0=0;x1=1;y1=.05;severity=error",
    "bottom": "x0=0;y0=.95;x1=1;y1=1;severity=error",
    "left": "x0=0;y0=0;x1=.05;y1=1;severity=error",
    "right": "x0=.95;y0=0;x1=1;y1=1;severity=error",
}
CAPTION_ZONE_CODE = "caption_zone_collision"
CONTRAST_CODE = "contrast_aa_failure"

_COMMENTS = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)
_FONT_USE = re.compile(r"var\(\s*(--font-[A-Za-z0-9_-]*)")
_FONT_DEF = re.compile(r"(--font-[A-Za-z0-9_-]*)\s*:")
_STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
_STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_LINK_TAG = re.compile(r"<link\b[^>]*>", re.I)
_REL_STYLESHEET = re.compile(r"""\brel\s*=\s*["']?[^"'>]*\bstylesheet\b""", re.I)
_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
_INJECTED = re.compile(r"Injected deterministic @font-face rules for (\d+) requested font famil", re.I)
_RATIO = re.compile(r"Contrast is ([0-9.]+):1")
_LOUDNESS_I = re.compile(r"^\s*I:\s+(-?[0-9.]+|-inf)\s+LUFS", re.M)
_LOUDNESS_TP = re.compile(r"^\s*Peak:\s+(-?[0-9.]+|-inf)\s+dBFS", re.M)


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print("%s: error: %s" % (self.prog, message), file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def usage_error(message: str) -> NoReturn:
    print("verify.py: %s" % message, file=sys.stderr)
    emit({"error": message}, EXIT_USAGE)


def make_check(name: str, status: str, measured, threshold, detail: str) -> dict:
    return {"name": name, "status": status, "measured": measured, "threshold": threshold, "detail": detail}


def read_json_file(path: Path):
    """Parse a JSON file that may be preceded by log lines (``hf.py`` output captured with 2>&1)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    decoder = json.JSONDecoder()
    for match in re.finditer(r"^[\[{]", text, re.M):
        try:
            return decoder.raw_decode(text[match.start():])[0]
        except ValueError:
            continue
    raise ValueError("no JSON document found")


def rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def hf_command(project: Path, *hf_args: str) -> str:
    return " ".join(shlex.quote(a) for a in ["python3", str(HF_PY), "--project", str(project), "--", *hf_args])


# fonts ------------------------------------------------------------------------------------------

def _html_files(root: Path) -> "list[Path]":
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.html") if not SKIPPED_DIRS.intersection(p.relative_to(root).parts))


def _inline_definitions(text: str) -> "set[str]":
    chunks = _STYLE_BLOCK.findall(text)
    chunks += [a or b for a, b in _STYLE_ATTR.findall(text)]
    return {name for chunk in chunks for name in _FONT_DEF.findall(chunk)}


def scan_fonts(project: Path) -> "list[str]":
    """Problems with font tokens in the scene HTML: unresolved ``var(--font-*)`` and linked token sheets."""
    scenes = project / "scenes"
    files = _html_files(scenes)
    roots = [p for p in (scenes / "index.html", project / "index.html") if p.is_file()]
    root_defs: "set[str]" = set()
    for root in roots:
        root_defs |= _inline_definitions(_COMMENTS.sub("", root.read_text(encoding="utf-8", errors="replace")))
    problems = []
    for path in files:
        text = _COMMENTS.sub("", path.read_text(encoding="utf-8", errors="replace"))
        defined = _inline_definitions(text) | root_defs
        missing = sorted(set(_FONT_USE.findall(text)) - defined)
        for name in missing:
            problems.append("%s uses var(%s) but no inline <style> or style= defines it" % (rel(path, project), name))
        for tag in _LINK_TAG.findall(text):
            if not _REL_STYLESHEET.search(tag):
                continue
            href = _HREF.search(tag)
            if not href:
                continue
            target = href.group(1).split("#")[0].split("?")[0]
            if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", target, re.I):
                continue
            for base in (path.parent, scenes):
                css = base / target
                if css.is_file():
                    names = sorted(set(_FONT_DEF.findall(_COMMENTS.sub("", css.read_text(encoding="utf-8", errors="replace")))))
                    if names:
                        problems.append(
                            "%s links stylesheet %s which defines %s; inline the :root tokens instead"
                            % (rel(path, project), rel(css, project), ", ".join(names))
                        )
                    break
    return problems


def brand_family_count(project: Path, brief: dict) -> "tuple[int, bool]":
    """Number of font families in the brand and whether brand.json was found."""
    product = brief.get("product")
    path = studio_root() / "brands" / str(product) / "brand.json"
    try:
        fonts = json.loads(path.read_text(encoding="utf-8")).get("fonts") or {}
    except (OSError, ValueError, AttributeError):
        return 1, False
    families = {f.get("family") for f in fonts.values() if isinstance(f, dict) and f.get("family")}
    return (len(families) or len(fonts) or 1), True


def check_fonts(project: Path, brief: dict, render_log: Path, version: str) -> dict:
    problems = scan_fonts(project)
    required, _ = brand_family_count(project, brief)
    injected = 0
    if not render_log.is_file():
        render_cmd = hf_command(
            project, "render", "--quality", "delivery", "--workers", "2", "--output",
            str(project / version / "<slug>-16x9.mp4"), str(project / "scenes"),
        )
        problems.append(
            "render log %s not found; produce it with: %s > %s 2>&1"
            % (render_log, render_cmd, shlex.quote(str(project / version / "render.log")))
        )
    else:
        counts = [int(n) for n in _INJECTED.findall(render_log.read_text(encoding="utf-8", errors="replace"))]
        injected = max(counts) if counts else 0
        if not counts:
            problems.append(
                "%s has no 'Injected deterministic @font-face rules' line, so the MP4 may use fallback fonts"
                % render_log
            )
        elif injected < required:
            problems.append(
                "render log injected %d font famil%s but the brand has %d"
                % (injected, "y" if injected == 1 else "ies", required)
            )
    unresolved = sum(1 for p in problems if "var(" in p or "links stylesheet" in p)
    return make_check(
        "fonts", "fail" if problems else "pass",
        {"injected": injected, "required": required, "unresolved": unresolved},
        {"injected_min": required, "unresolved": 0},
        "; ".join(problems) if problems else "tokens inlined and %d font famil%s injected at render" % (
            injected, "y" if injected == 1 else "ies"),
    )


# contrast and title-safe -----------------------------------------------------------------------

def parse_check_args(values: "list[str]") -> "list[tuple[Optional[str], Path, object]]":
    """``[BAND=]FILE`` arguments to ``(band, path, document)``; exits 2 on a name or file that cannot be used."""
    parsed = []
    for value in values:
        band: Optional[str] = None
        file_part = value
        head, sep, tail = value.partition("=")
        if sep and head in BANDS:
            band, file_part = head, tail
        path = Path(file_part)
        try:
            doc = read_json_file(path)
        except (OSError, ValueError) as exc:
            usage_error("cannot read --check-json %s: %s" % (path, exc))
        parsed.append((band, path, doc))
    return parsed


def _findings(doc) -> "list[dict]":
    out = []
    if isinstance(doc, dict):
        for section in doc.values():
            if isinstance(section, dict) and isinstance(section.get("findings"), list):
                out.extend(f for f in section["findings"] if isinstance(f, dict))
    return out


def _finding_ratio(finding: dict) -> Optional[float]:
    ratio = finding.get("ratio")
    if isinstance(ratio, (int, float)):
        return float(ratio)
    match = _RATIO.search(str(finding.get("message") or ""))
    return float(match.group(1)) if match else None


def check_contrast(project: Path, version: str, docs: "list[tuple[Optional[str], Path, object]]") -> dict:
    if not docs:
        cmd = hf_command(project, "check", "--json", str(project / "scenes"))
        return make_check(
            "contrast", "fail", None, {"failing": 0},
            "no check JSON passed; run `%s > %s` and pass it with --check-json"
            % (cmd, shlex.quote(str(project / version / "check.json"))),
        )
    seen = set()
    failing = []
    for _, _, doc in docs:
        for finding in _findings(doc):
            if finding.get("code") != CONTRAST_CODE:
                continue
            key = (finding.get("sourceFile"), finding.get("selector"), finding.get("text"), finding.get("requiredRatio"))
            if key not in seen:
                seen.add(key)
                failing.append(finding)
    ratios = [r for r in (_finding_ratio(f) for f in failing) if r is not None]
    measured = {"failing": len(failing), "worst_ratio": min(ratios) if ratios else None}
    detail = "all text meets WCAG AA"
    if failing:
        samples = ", ".join(
            "%r (%s)" % (f.get("text"), ("%.2f:1" % _finding_ratio(f)) if _finding_ratio(f) else "ratio unknown")
            for f in failing[:5]
        )
        detail = "%d text element(s) fail WCAG AA: %s" % (len(failing), samples)
    return make_check("contrast", "fail" if failing else "pass", measured, {"failing": 0}, detail)


def check_title_safe(project: Path, version: str, docs: "list[tuple[Optional[str], Path, object]]") -> dict:
    band_cmds = [
        "%s > %s"
        % (
            hf_command(project, "check", "--json", "--caption-zone", BANDS[band], str(project / "scenes")),
            shlex.quote(str(project / version / ("check-%s.json" % band))),
        )
        for band in BANDS
    ]
    how = "run each, then pass them as --check-json top=FILE bottom=FILE left=FILE right=FILE: " + " ; ".join(band_cmds)
    if not docs:
        return make_check("title_safe", "fail", None, {"collisions": 0}, "no check JSON passed; " + how)
    collisions = []
    covered = set()
    for band, _, doc in docs:
        if band:
            covered.add(band)
        for finding in _findings(doc):
            if finding.get("code") == CAPTION_ZONE_CODE:
                collisions.append((band, finding))
    if collisions:
        texts = ", ".join(
            "%r%s" % (f.get("text"), (" in %s band" % b) if b else "") for b, f in collisions[:5]
        )
        return make_check(
            "title_safe", "fail", {"collisions": len(collisions)}, {"collisions": 0},
            "text inside the outer 5%% of the frame: %s" % texts,
        )
    missing = [b for b in BANDS if b not in covered]
    if missing:
        return make_check(
            "title_safe", "fail", {"collisions": 0, "bands_checked": sorted(covered)}, {"bands": list(BANDS)},
            "band runs missing for %s; %s" % (", ".join(missing), how),
        )
    return make_check(
        "title_safe", "pass", {"collisions": 0, "bands_checked": sorted(covered)}, {"collisions": 0},
        "no text in the outer 5% of any edge",
    )


# blender and outside calls ---------------------------------------------------------------------

def check_blender(project: Path) -> dict:
    guards = sorted(p for p in project.rglob("guard.json") if not SKIPPED_DIRS.intersection(p.relative_to(project).parts))
    if not guards:
        return make_check("blender", "skip", None, None, "no guard.json under the project, so no 3D clip")
    default_scene = 0
    mirrored = 0
    problems = []
    for path in guards:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            problems.append("%s unreadable: %s" % (rel(path, project), exc))
            continue
        if data.get("default_scene"):
            default_scene += 1
            problems.append("%s reports the default scene" % rel(path, project))
        frames = data.get("mirrored_frames") or []
        if frames:
            mirrored += len(frames)
            problems.append("%s has %d mirrored text frame(s)" % (rel(path, project), len(frames)))
    return make_check(
        "blender", "fail" if problems else "pass",
        {"guards": len(guards), "default_scene": default_scene, "mirrored_frames": mirrored},
        {"default_scene": 0, "mirrored_frames": 0},
        "; ".join(problems) if problems else "%d guard file(s) clean" % len(guards),
    )


def check_outside_calls(project: Path, brief: dict) -> dict:
    allowed = set(brief.get("cloud_allow") or []) | LOCAL_PROVIDERS
    offenders: "dict[str, int]" = {}
    path = project / "calls.jsonl"
    total = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                provider = json.loads(line).get("provider")
            except (ValueError, AttributeError):
                continue
            total += 1
            if provider not in allowed:
                offenders[str(provider)] = offenders.get(str(provider), 0) + 1
    detail = "%d logged call(s), all to allowed providers" % total
    if offenders:
        detail = "calls to providers the brief does not allow: %s" % ", ".join(
            "%s (%d)" % (p, n) for p, n in sorted(offenders.items())
        )
    return make_check(
        "outside_calls", "fail" if offenders else "pass", offenders, {"cloud_allow": sorted(brief.get("cloud_allow") or [])},
        detail,
    )


# media ------------------------------------------------------------------------------------------

def probe_video(mp4: Path) -> dict:
    """fps, size and duration of the first video stream; raises ``RuntimeError`` when ffprobe cannot read it."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=avg_frame_rate,r_frame_rate,width,height,duration", "-show_entries", "format=duration",
         "-of", "json", str(mp4)],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(proc.stdout or "{}")
        stream = data["streams"][0]
        fps = 0.0
        for key in ("avg_frame_rate", "r_frame_rate"):
            num, _, den = str(stream.get(key) or "0/1").partition("/")
            if float(den or 1) and float(num) / float(den or 1) > 0:
                fps = float(num) / float(den or 1)
                break
        duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
        if fps <= 0 or duration <= 0:
            raise ValueError("no frame rate or duration")
        return {"fps": fps, "width": int(stream["width"]), "height": int(stream["height"]), "duration": duration}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("ffprobe could not read %s: %s %s" % (mp4, exc, proc.stderr.strip()[-200:]))


def parse_ebur128(stderr: str) -> "tuple[Optional[float], Optional[float]]":
    """Integrated loudness (LUFS) and true peak (dBTP) from the ebur128 Summary, or ``None`` when absent."""
    summary = stderr.rsplit("Summary:", 1)[-1] if "Summary:" in stderr else ""

    def number(match) -> Optional[float]:
        if not match or match.group(1) == "-inf":
            return None
        return float(match.group(1))

    return number(_LOUDNESS_I.search(summary)), number(_LOUDNESS_TP.search(summary))


def check_loudness(mp4: Path, narrated: bool) -> dict:
    threshold = {"lufs": list(LUFS_RANGE), "true_peak_dbtp_max": TRUE_PEAK_MAX}
    if not narrated:
        return make_check("loudness", "skip", None, threshold, "silent video (brief.narration is false)")
    proc = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    lufs, peak = parse_ebur128(proc.stderr)
    if lufs is None or peak is None:
        return make_check("loudness", "fail", None, threshold, "ffmpeg ebur128 reported no loudness; the MP4 may have no audio")
    ok = LUFS_RANGE[0] <= lufs <= LUFS_RANGE[1] and peak <= TRUE_PEAK_MAX
    detail = "integrated %.1f LUFS, true peak %.1f dBTP" % (lufs, peak)
    if not ok:
        detail += "; target is -17 to -15 LUFS with true peak at or below -1.0 dBTP"
    return make_check("loudness", "pass" if ok else "fail", {"lufs": lufs, "true_peak_dbtp": peak}, threshold, detail)


def load_beats(path: Path) -> "list[dict]":
    try:
        beats = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        usage_error("cannot read beats file %s: %s" % (path, exc))
    if not isinstance(beats, list) or not all(isinstance(b, dict) for b in beats):
        usage_error("beats file %s must be a JSON list of beat objects" % path)
    for i, beat in enumerate(beats):
        for key in ("id", "clip", "expected_s", "region", "baseline_s"):
            if key not in beat:
                usage_error("beats file %s: beat %d is missing %r" % (path, i, key))
        if beat.get("detector") == "color" and not beat.get("color"):
            usage_error("beats file %s: beat %r uses the color detector but has no color" % (path, beat["id"]))
    return beats


def parse_audio_args(values: "list[str]") -> "dict[str, Path]":
    mapping = {}
    for value in values:
        clip, sep, file_part = value.rpartition("=")
        if not sep or not clip or not file_part:
            usage_error("--audio-json expects CLIP=FILE, got %r" % value)
        mapping[clip] = Path(file_part)
    return mapping


def _audio_item(doc) -> dict:
    items = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise ValueError("no items[0] in the audio JSON")
    return items[0]


def collect_audio(project: Path, beats: "list[dict]", supplied: "dict[str, Path]") -> "tuple[dict, Optional[str], bool]":
    """Per-clip ``hyperframes audio`` items. Returns ``(items, error, tool_missing)``."""
    items: "dict[str, dict]" = {}
    for clip in dict.fromkeys(b["clip"] for b in beats):
        given = supplied.get(clip) or next((p for k, p in supplied.items() if Path(k).name == Path(clip).name), None)
        try:
            if given is not None:
                items[clip] = _audio_item(read_json_file(given))
                continue
            clip_path = Path(clip) if Path(clip).is_absolute() else project / clip
            proc = subprocess.run(
                [sys.executable, str(HF_PY), "--project", str(project), "--", "audio", str(clip_path),
                 "--only", "loudness,onsets,silence,envelope", "--hop-ms", "10", "--json"],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode == EXIT_MISSING_TOOL:
                return items, "hf.py reported a missing tool: %s" % (proc.stdout.strip() or proc.stderr.strip())[:200], True
            if proc.returncode != 0:
                return items, "hyperframes audio failed for %s (exit %d): %s" % (clip, proc.returncode, proc.stderr.strip()[-200:]), False
            tmp = proc.stdout
            decoder = json.JSONDecoder()
            start = re.search(r"^\{", tmp, re.M)
            if not start:
                return items, "hyperframes audio printed no JSON for %s" % clip, False
            items[clip] = _audio_item(decoder.raw_decode(tmp[start.start():])[0])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return items, "audio analysis for %s failed: %s" % (clip, exc), False
    return items, None, False


def check_sync(project: Path, mp4: Path, info: dict, beats: Optional["list[dict]"], supplied: "dict[str, Path]") -> dict:
    threshold = {"offset_frames_max": 1}
    if not beats:
        return make_check("sync", "skip", None, threshold, "no beats.json, so there are no timed beats to measure")
    py = venv_python()
    if not py.is_file():
        return make_check(
            "sync", "skip", None, threshold,
            "venv python not found at %s; run `python3 %s check --need narration` to see the fix"
            % (py, SCRIPTS_DIR / "doctor.py"),
        )
    items, error, tool_missing = collect_audio(project, beats, supplied)
    if error:
        return make_check("sync", "skip" if tool_missing else "fail", None, threshold, error)
    request = {
        "mp4": str(mp4), "fps": info["fps"], "width": info["width"], "height": info["height"],
        "audio": items, "beats": [dict(b, clip_key=b["clip"]) for b in beats],
    }
    try:
        proc = subprocess.run([str(py), str(WORKER_PY)], input=json.dumps(request), capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return make_check("sync", "fail", None, threshold, "media_worker did not run: %s" % exc)
    try:
        report = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return make_check("sync", "fail", None, threshold, "media_worker printed no JSON: %s" % proc.stderr.strip()[-200:])
    if proc.returncode == EXIT_MISSING_TOOL:
        return make_check("sync", "skip", None, threshold, "media_worker needs numpy in the venv: %s" % report.get("error"))
    if proc.returncode != 0 or "beats" not in report:
        return make_check("sync", "fail", None, threshold, "media_worker failed: %s" % report.get("error", proc.stderr.strip()[-200:]))
    rows = report["beats"]
    problems = []
    flagged = []
    worst = 0.0
    for row in rows:
        if row.get("flagged"):
            flagged.append(str(row.get("id")))
        if row.get("offset_s") is None:
            problems.append("%s: no change seen in its region after the baseline" % row.get("id"))
            continue
        worst = max(worst, abs(row["offset_frames"]))
        if abs(row["offset_s"]) > 1.0 / info["fps"] + 1e-6:
            problems.append("%s: picture %+0.0f ms from the word (%+.1f frames)" % (
                row.get("id"), row["offset_s"] * 1000, row["offset_frames"]))
    detail = "; ".join(problems) if problems else "%d beat(s) within one frame" % len(rows)
    if flagged:
        detail += "; flagged (no audio onset near the expected time, expected time used): %s" % ", ".join(flagged)
    measured = {
        "worst_frames": worst,
        "beats": [{k: r.get(k) for k in ("id", "via", "offset_frames")} for r in rows],
    }
    return make_check("sync", "fail" if problems else "pass", measured, threshold, detail)


# frames -----------------------------------------------------------------------------------------

def _grab(mp4: Path, at: float, out: Path) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "%.3f" % at, "-i", str(mp4), "-frames:v", "1", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError("ffmpeg could not grab a frame at %.3f s: %s" % (at, proc.stderr.strip()[-200:]))


def extract_frames(mp4: Path, vdir: Path, info: dict, at: "Optional[list[float]]") -> dict:
    """Contact sheet and stills decoded from the MP4 into ``<vN>/frames/``."""
    frames = vdir / "frames"
    frames.mkdir(exist_ok=True)
    last = max(info["duration"] - 1.0 / info["fps"], 0.0)

    def clamp(t: float) -> float:
        return min(max(t, 0.0), last)

    tiles = SHEET_COLUMNS * SHEET_ROWS
    work = frames / ".sheet-tmp"
    work.mkdir(exist_ok=True)
    try:
        for i in range(tiles):
            _grab(mp4, clamp((i + 0.5) * info["duration"] / tiles), work / ("s%02d.png" % i))
        sheet = frames / "sheet.png"
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", "1", "-i", str(work / "s%02d.png"),
             "-vf", "scale=%d:-1,tile=%dx%d" % (SHEET_TILE_WIDTH, SHEET_COLUMNS, SHEET_ROWS),
             "-frames:v", "1", str(sheet)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not sheet.is_file():
            raise RuntimeError("ffmpeg could not tile the contact sheet: %s" % proc.stderr.strip()[-200:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    times = at if at else [(i + 0.5) * info["duration"] / DEFAULT_STILLS for i in range(DEFAULT_STILLS)]
    stills = []
    for n, t in enumerate(times, start=1):
        out = frames / ("still-%02d-%.2fs.png" % (n, clamp(t)))
        _grab(mp4, clamp(t), out)
        stills.append(str(out))
    return {"sheet": str(sheet), "stills": stills}


# attempts and main -----------------------------------------------------------------------------

def read_attempts(path: Path) -> "list[dict]":
    try:
        attempts = json.loads(path.read_text(encoding="utf-8")).get("attempts")
    except (OSError, ValueError, AttributeError):
        return []
    return [a for a in attempts if isinstance(a, dict)] if isinstance(attempts, list) else []


def parse_at(text: str) -> "list[float]":
    try:
        return [float(part) for part in text.split(",") if part.strip()]
    except ValueError:
        usage_error("--at expects comma-separated seconds, got %r" % text)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="verify.py", description="Strict verify for one rendered version.")
    parser.add_argument("--project", required=True, help="project directory")
    parser.add_argument("--version", required=True, help="version folder name, such as v1")
    parser.add_argument("--mp4", help="the render to check (default: the only *.mp4 in the version folder)")
    parser.add_argument("--beats", help="beats.json (default: <project>/beats.json when present)")
    parser.add_argument("--check-json", action="append", default=[], metavar="[BAND=]FILE",
                        help="hf.py check --json output; BAND is top|bottom|left|right for a --caption-zone run")
    parser.add_argument("--render-log", help="render log (default: <project>/<version>/render.log)")
    parser.add_argument("--audio-json", action="append", default=[], metavar="CLIP=FILE",
                        help="precomputed hyperframes audio --json for a beat clip; skips running it")
    parser.add_argument("--at", help="comma-separated seconds for stills (default: six evenly spaced)")
    return parser


def main(argv: Optional["list[str]"] = None) -> int:
    args = build_parser().parse_args(argv)
    project = Path(args.project)
    if not project.is_dir():
        usage_error("project directory not found: %s" % project)
    vdir = project / args.version
    if not vdir.is_dir():
        usage_error("version folder not found: %s" % vdir)
    try:
        brief = load_brief(project)
    except (OSError, ValueError) as exc:
        usage_error("cannot read brief.json: %s" % exc)

    if args.mp4:
        mp4 = Path(args.mp4)
        if not mp4.is_file():
            emit({"error": "missing_render", "detail": "no such file: %s" % mp4}, EXIT_FAILED)
    else:
        found = sorted(vdir.glob("*.mp4"))
        if not found:
            emit({"error": "missing_render", "detail": "no *.mp4 in %s; render the version first" % vdir}, EXIT_FAILED)
        if len(found) > 1:
            usage_error("several MP4s in %s (%s); pass --mp4" % (vdir, ", ".join(p.name for p in found)))
        mp4 = found[0]

    check_docs = parse_check_args(args.check_json)
    supplied = parse_audio_args(args.audio_json)
    beats_path = Path(args.beats) if args.beats else project / "beats.json"
    beats = load_beats(beats_path) if args.beats or beats_path.is_file() else None
    at = parse_at(args.at) if args.at else None

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            emit({"error": "%s is not installed; run `brew install ffmpeg`" % tool}, EXIT_MISSING_TOOL)

    try:
        info = probe_video(mp4)
        render_log = Path(args.render_log) if args.render_log else vdir / "render.log"
        checks = [
            check_fonts(project, brief, render_log, args.version),
            check_contrast(project, args.version, check_docs),
            check_title_safe(project, args.version, check_docs),
            check_loudness(mp4, bool(brief.get("narration"))),
            check_sync(project, mp4, info, beats, supplied),
            check_blender(project),
            check_outside_calls(project, brief),
        ]
        frames = extract_frames(mp4, vdir, info, at)
    except RuntimeError as exc:
        print("verify.py: %s" % exc, file=sys.stderr)
        emit({"error": str(exc)}, EXIT_FAILED)

    passed = all(c["status"] != "fail" for c in checks)
    verify_json = vdir / "verify.json"
    attempts = read_attempts(verify_json)
    attempts.append({
        "n": len(attempts) + 1,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "passed": passed,
    })
    attempt = len(attempts)
    result = {
        "version": args.version,
        "attempt": attempt,
        "passed": passed,
        "stop": attempt >= MAX_ATTEMPTS and not passed,
        "checks": checks,
        "frames": frames,
    }
    verify_json.write_text(json.dumps(dict(result, attempts=attempts), indent=2) + "\n", encoding="utf-8")
    emit(result, EXIT_OK if passed else EXIT_FAILED)


if __name__ == "__main__":
    sys.exit(main())
