#!/usr/bin/env python3
"""Fit a film under a byte budget so it can be inlined in one HTML page.

Usage: fit_video.py --in MP4 --budget-bytes N --out MP4

Prints one JSON object, ``{"out", "bytes", "reencoded", "video_kbps"}``. When the input already fits it is
copied and ``video_kbps`` is null; otherwise the film is re-encoded as H.264 yuv420p with AAC at 96 kbps
(audio is dropped only when the input has none) at the highest video bitrate that fits.

Video never goes below FLOOR_KBPS: under it text in the film stops being readable. The floor limits the bitrate
tried, not the safety-adjusted estimate, so a budget that holds the floor is tried at the floor and accepted if
that encode fits. Otherwise the script fails and names the budget and the floor, and the caller frees bytes
elsewhere (smaller screenshots, a shorter film).

The encode goes to a unique temporary file next to ``--out`` and is renamed over it on success, so ``--in`` is
never touched whatever it is named.

Exit 0 ok; 1 cannot fit above FLOOR_KBPS or the encode failed; 2 usage or an unreadable input; 3 ffmpeg or
ffprobe missing (needed only when a re-encode is). Diagnostics go to stderr; the script never prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn, Optional

FLOOR_KBPS = 300
AUDIO_KBPS = 96
SAFETY = 0.96
MAX_ENCODES = 3

EXIT_OK = 0
EXIT_CANNOT_FIT = 1
EXIT_USAGE = 2
EXIT_NO_FFMPEG = 3


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(f"fit_video.py: {message}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def _die(message: str, code: int) -> NoReturn:
    print(f"fit_video.py: {message}", file=sys.stderr)
    sys.exit(code)


def _require_ffmpeg() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        _die(f"{' and '.join(missing)} not found; run `brew install ffmpeg`", EXIT_NO_FFMPEG)


def _probe(path: Path) -> tuple[float, bool]:
    """Duration in seconds and whether the file has an audio stream."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        info = json.loads(proc.stdout)
        duration = float(info["format"]["duration"])
        streams = {s.get("codec_type") for s in info.get("streams", [])}
    except (ValueError, KeyError, TypeError):
        _die(f"{path} is not a readable video", EXIT_USAGE)
    if proc.returncode != 0 or duration <= 0 or "video" not in streams:
        _die(f"{path} is not a readable video", EXIT_USAGE)
    return duration, "audio" in streams


def _video_kbps(budget: int, duration: float, has_audio: bool, safety: float = SAFETY) -> int:
    total_kbps = budget * 8 * safety / duration / 1000
    return int(total_kbps - (AUDIO_KBPS if has_audio else 0))


def _encode(src: Path, part: Path, kbps: int, has_audio: bool) -> None:
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-i", str(src),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
        "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k",
        "-movflags", "+faststart",
    ]
    cmd += ["-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k"] if has_audio else ["-an"]
    cmd += ["-f", "mp4", str(part)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _die(f"ffmpeg failed: {proc.stderr.strip()[-400:]}", EXIT_CANNOT_FIT)


def _cannot_fit(budget: int, kbps: int) -> NoReturn:
    _die(
        f"cannot fit the film in {budget} bytes: that leaves {max(kbps, 0)} kbps for video, "
        f"below the {FLOOR_KBPS} kbps floor",
        EXIT_CANNOT_FIT,
    )


def _floor_too_big(budget: int, size: int) -> NoReturn:
    _die(
        f"cannot fit the film in {budget} bytes: an encode at the {FLOOR_KBPS} kbps floor came to {size} bytes",
        EXIT_CANNOT_FIT,
    )


def _temp_beside(out: Path) -> Path:
    """A new empty file in ``out``'s folder that nothing else is named, with the mode a plain copy would get."""
    fd, name = tempfile.mkstemp(dir=out.parent, prefix=f".{out.stem}-", suffix=".mp4")
    os.close(fd)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(name, 0o666 & ~umask)
    return Path(name)


def fit(src: Path, budget: int, out: Path) -> dict[str, object]:
    """Copy or re-encode ``src`` to ``out`` so it is at most ``budget`` bytes; the result is the JSON payload."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.stat().st_size <= budget:
        shutil.copyfile(src, out)
        return {"out": str(out), "bytes": out.stat().st_size, "reencoded": False, "video_kbps": None}

    _require_ffmpeg()
    duration, has_audio = _probe(src)
    unpadded_kbps = _video_kbps(budget, duration, has_audio, safety=1.0)
    if unpadded_kbps < FLOOR_KBPS:
        _cannot_fit(budget, unpadded_kbps)
    kbps = _video_kbps(budget, duration, has_audio)
    part = _temp_beside(out)
    try:
        encodes = 0
        while True:
            # the floor is always tried before giving up, so a budget that can hold it is never rejected untried
            kbps = FLOOR_KBPS if encodes >= MAX_ENCODES else max(kbps, FLOOR_KBPS)
            _encode(src, part, kbps, has_audio)
            encodes += 1
            size = part.stat().st_size
            if size <= budget:
                part.replace(out)
                return {"out": str(out), "bytes": size, "reencoded": True, "video_kbps": kbps}
            if kbps == FLOOR_KBPS:
                _floor_too_big(budget, size)
            # rate control overshot: scale the target by how far off it landed, with a little extra room
            kbps = int(kbps * budget / size * 0.97)
    finally:
        part.unlink(missing_ok=True)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _Parser(prog="fit_video.py", description="Fit an MP4 under a byte budget.")
    parser.add_argument("--in", dest="src", required=True, help="the MP4 to fit")
    parser.add_argument("--budget-bytes", required=True, help="the most bytes the MP4 may take")
    parser.add_argument("--out", required=True, help="where to write the fitted MP4")
    args = parser.parse_args(argv)
    try:
        budget = int(args.budget_bytes)
    except ValueError:
        _die(f"--budget-bytes must be a whole number, got {args.budget_bytes!r}", EXIT_USAGE)
    if budget <= 0:
        _die("--budget-bytes must be above 0", EXIT_USAGE)
    src, out = Path(args.src), Path(args.out)
    if not src.is_file():
        _die(f"input not found: {src}", EXIT_USAGE)
    if src.resolve() == out.resolve():
        _die("--out must differ from --in", EXIT_USAGE)
    print(json.dumps(fit(src, budget, out)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
