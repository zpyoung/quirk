#!/usr/bin/env python3
"""Voice-sync analysis for ``verify.py``: when each beat first changes on screen versus its word onset.

Runs only under the skill's venv interpreter (needs numpy); ``verify.py`` is the launcher. Reads one
JSON request on stdin and prints exactly one JSON object on stdout; diagnostics go to stderr.
Exit codes: 0 analysed; 1 bad request or decode failure (``{"error": ...}``); 3 numpy missing.

Request: ``{"mp4", "fps", "width", "height", "beats": [beat + "clip_key"], "audio": {clip_key: item}}``
where ``item`` is ``items[0]`` of ``hyperframes audio --json``. Only a window of about one second
either side of each beat is decoded, at half resolution, so a 3-minute video stays fast.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import scrubbed_env  # noqa: E402

try:
    import numpy as np
except ImportError:
    np = None

EXIT_OK, EXIT_FAILED, EXIT_MISSING_TOOL = 0, 1, 3

DECODE_SCALE = 0.5
CHANGE_LEVEL = 24
SHARE_THRESHOLD = 0.01
COLOR_TOLERANCE = 40
WINDOW_AFTER_S = 1.0
SILENCE_WINDOW_S = 0.05
ONSET_WINDOW_S = 0.08
ONSET_MIN_STRENGTH = 0.15


def parse_color(value: str) -> "tuple[int, int, int]":
    """``#rrggbb`` to an ``(r, g, b)`` tuple."""
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("color must be #rrggbb, got %r" % value)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def scale_region(region, scale: float, width: int, height: int) -> "tuple[int, int, int, int]":
    """Turn ``[x, y, w, h]`` source pixels into a clamped ``(x0, y0, x1, y1)`` box on the decoded frame."""
    x, y, w, h = region
    x0 = min(max(int(x * scale), 0), width - 1)
    y0 = min(max(int(y * scale), 0), height - 1)
    x1 = min(max(int(round((x + w) * scale)), x0 + 1), width)
    y1 = min(max(int(round((y + h) * scale)), y0 + 1), height)
    return x0, y0, x1, y1


def changed_share(base, cur) -> float:
    """Share of pixels whose largest channel difference from ``base`` exceeds 24 levels."""
    diff = np.abs(cur.astype(np.int16) - base.astype(np.int16)).max(axis=2)
    return float((diff > CHANGE_LEVEL).mean())


def color_share(cur, rgb, tolerance: int = COLOR_TOLERANCE) -> float:
    """Share of pixels within ``tolerance`` levels of ``rgb`` on every channel."""
    diff = np.abs(cur.astype(np.int16) - np.array(rgb, dtype=np.int16)).max(axis=2)
    return float((diff <= tolerance).mean())


def visual_onset(frames, box, baseline_index: int, detector: str, rgb=None) -> Optional[int]:
    """Index of the first frame after ``baseline_index`` whose region has changed, or ``None``.

    ``changed`` compares the region to the baseline frame; ``color`` waits for the share of
    pixels near ``rgb`` to grow past the baseline's share by more than 1% of the region.
    """
    x0, y0, x1, y1 = box
    base = frames[baseline_index][y0:y1, x0:x1]
    base_color = color_share(base, rgb) if detector == "color" else 0.0
    for i in range(baseline_index + 1, len(frames)):
        cur = frames[i][y0:y1, x0:x1]
        if detector == "color":
            score = color_share(cur, rgb) - base_color
        else:
            score = changed_share(base, cur)
        if score > SHARE_THRESHOLD:
            return i
    return None


def select_onset(expected: float, item: dict, clip_start: float = 0.0) -> "tuple[float, str, bool]":
    """The word's onset in film time as ``(seconds, via, flagged)``.

    A silence end within 50 ms of ``expected`` wins; else the nearest spectral-flux onset within
    80 ms with strength of at least 0.15; else ``expected`` itself, flagged as unmeasured.
    """
    duration = float(item.get("duration") or 0.0)
    ends = [float(s["end"]) + clip_start for s in item.get("silence") or [] if float(s["end"]) < duration]
    near = [e for e in ends if abs(e - expected) <= SILENCE_WINDOW_S]
    if near:
        return min(near, key=lambda e: abs(e - expected)), "silence", False
    events = (item.get("onsets") or {}).get("events") or []
    onsets = [float(e["t"]) + clip_start for e in events if float(e["strength"]) >= ONSET_MIN_STRENGTH]
    close = [o for o in onsets if abs(o - expected) <= ONSET_WINDOW_S]
    if close:
        return min(close, key=lambda o: abs(o - expected)), "onset", False
    return expected, "expected", True


def decode_window(mp4: str, first_index: int, count: int, fps: float, width: int, height: int):
    """Frames ``first_index`` .. ``first_index + count`` at half size as a list of HxWx3 uint8 arrays."""
    start = max(first_index / fps - 0.25 / fps, 0.0)
    argv = [
        "ffmpeg", "-nostdin", "-v", "error", "-ss", "%.6f" % start, "-i", mp4,
        "-frames:v", str(count), "-vf", "scale=%d:%d" % (width, height),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    proc = subprocess.run(argv, capture_output=True, env=scrubbed_env())
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed decoding frames: %s" % proc.stderr.decode("utf-8", "replace")[-300:])
    raw = np.frombuffer(proc.stdout, np.uint8)
    size = width * height * 3
    return [raw[i * size:(i + 1) * size].reshape(height, width, 3) for i in range(len(raw) // size)]


def analyse(request: dict) -> dict:
    """Measure every beat in ``request``; see the module docstring for the shape."""
    fps = float(request["fps"])
    width = max(int(round(int(request["width"]) * DECODE_SCALE)), 2)
    height = max(int(round(int(request["height"]) * DECODE_SCALE)), 2)
    results = []
    for beat in request["beats"]:
        item = request["audio"][beat["clip_key"]]
        clip_start = float(beat.get("clip_start_s") or 0.0)
        expected = float(beat["expected_s"])
        heard, via, flagged = select_onset(expected, item, clip_start)
        first = max(int(round(float(beat["baseline_s"]) * fps)), 0)
        last = max(int(round((expected + WINDOW_AFTER_S) * fps)), first + 1)
        frames = decode_window(request["mp4"], first, last - first + 1, fps, width, height)
        seen = None
        if frames:
            box = scale_region(beat["region"], DECODE_SCALE, width, height)
            rgb = parse_color(beat["color"]) if beat.get("detector") == "color" else None
            index = visual_onset(frames, box, 0, beat.get("detector") or "changed", rgb)
            if index is not None:
                seen = (first + index) / fps
        offset = None if seen is None else seen - heard
        results.append({
            "id": beat.get("id"),
            "word": beat.get("word"),
            "expected_s": expected,
            "heard_s": round(heard, 4),
            "via": via,
            "flagged": flagged,
            "seen_s": None if seen is None else round(seen, 4),
            "offset_s": offset,
            "offset_frames": None if offset is None else offset * fps,
        })
    return {"fps": fps, "beats": results}


def main() -> int:
    if np is None:
        print(json.dumps({"error": "numpy is not installed in this interpreter; run doctor.py check"}))
        return EXIT_MISSING_TOOL
    try:
        request = json.loads(sys.stdin.read())
        report = analyse(request)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        print("media_worker: %s" % exc, file=sys.stderr)
        print(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}))
        return EXIT_FAILED
    print(json.dumps(report))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
