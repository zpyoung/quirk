#!/usr/bin/env python3
"""Headless Blender renderer for the making-videos skill.

Runs the author's scene script and the in-Blender guard (``bl_guard.py``) against a ``.blend``,
renders the frame range to a PNG sequence and encodes it with ffmpeg. Prints exactly one JSON object
to stdout and sends diagnostics to stderr.
Exit codes: 0 ok; 1 the render or a guard check failed (the JSON has an ``error`` key); 2 usage error;
3 Blender or ffmpeg is missing (the JSON names it and the install command).
The Blender binary is ``$QUIRK_BLENDER``, else ``blender`` on PATH, else the macOS app bundle.
``$QUIRK_VIDEO_FPS`` (default 30) sets the encode frame rate unless ``--fps`` is given.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bl_guard import parse_frames  # noqa: E402
from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_USAGE,
    SCRUB_ENV,
    cache_root,
    emit,
    run,
    studio_root,
)

MAC_APP_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_INSTALL = "Install Blender from https://www.blender.org/download/ or set QUIRK_BLENDER to the binary"
FFMPEG_INSTALL = "Install ffmpeg (macOS: brew install ffmpeg)"
GUARD_PY = Path(__file__).resolve().parent / "bl_guard.py"
DEFAULT_FPS = 30.0
TAIL_CHARS = 2000
VERSION_DIR = re.compile(r"v\d+")


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def find_blender(env: "dict[str, str]") -> Optional[str]:
    """The Blender binary: ``QUIRK_BLENDER``, else ``blender`` on PATH, else the macOS app; None if absent.

    An explicit ``QUIRK_BLENDER`` that does not exist is not silently replaced by a fallback.
    """
    explicit = env.get("QUIRK_BLENDER")
    if explicit:
        return explicit if os.path.isfile(explicit) and os.access(explicit, os.X_OK) else None
    found = shutil.which("blender", path=env.get("PATH", ""))
    if found:
        return found
    if os.path.isfile(MAC_APP_BLENDER) and os.access(MAC_APP_BLENDER, os.X_OK):
        return MAC_APP_BLENDER
    return None


def chunk_ranges(first: int, last: int, chunk: Optional[int]) -> "list[tuple[int, int]]":
    """Split ``first..last`` into inclusive ranges of at most ``chunk`` frames (one range when None)."""
    if not chunk:
        return [(first, last)]
    return [(a, min(a + chunk - 1, last)) for a in range(first, last + 1, chunk)]


def blender_argv(blender: str, blend: Path, script: Path, out: Path, frames: "tuple[int, int]", alpha: bool) -> "list[str]":
    """The Blender command line: file first, exit code on, author script then guard, args after ``--``."""
    argv = [
        blender,
        "-b",
        str(blend),
        "--python-exit-code",
        "1",
        "--python",
        str(script),
        "--python",
        str(GUARD_PY),
        "--",
        "--out",
        str(out),
        "--frames",
        f"{frames[0]}-{frames[1]}",
    ]
    if alpha:
        argv.append("--alpha")
    return argv


def merge_guards(guards: "list[dict]") -> dict:
    """Combine per-chunk ``guard.json`` objects into one covering the whole render."""
    merged = {
        "default_scene": any(g.get("default_scene") for g in guards),
        "view_transform": guards[0].get("view_transform", ""),
        "text_objects": [],
        "mirrored_frames": sorted({f for g in guards for f in g.get("mirrored_frames", [])}),
        "edge_on_frames": sorted({f for g in guards for f in g.get("edge_on_frames", [])}),
        "frames_rendered": sum(int(g.get("frames_rendered", 0)) for g in guards),
    }
    for g in guards:
        for name in g.get("text_objects", []):
            if name not in merged["text_objects"]:
                merged["text_objects"].append(name)
    return merged


def guard_warnings(guard: dict) -> "list[str]":
    """Non-fatal findings from a merged guard: edge-on text and a non-Standard view transform."""
    warnings = []
    if guard["edge_on_frames"]:
        warnings.append(f"text is nearly edge-on to the camera on frames {guard['edge_on_frames']}")
    if guard["view_transform"] != "Standard":
        warnings.append(
            f"view transform is {guard['view_transform']}; it shifts brand colours, "
            "use Standard with emission shaders for exact hex"
        )
    return warnings


def _tail(text: str) -> str:
    return text.strip()[-TAIL_CHARS:]


def _fail(message: str, **extra: object) -> NoReturn:
    print(message, file=sys.stderr)
    emit({"error": message, **extra}, EXIT_FAILED)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def out_dir_refusal(out: Path) -> Optional[str]:
    """Why ``out`` (already resolved) may not receive frames, or None when it is allowed.

    Frames go only under the studio or the tool cache, never into a version folder
    (``<studio>/videos/<project>/v<N>``) because versions are never rewritten.
    """
    if not (_is_within(out, studio_root()) or _is_within(out, cache_root())):
        return f"--out must be inside the studio ({studio_root()}) or the cache ({cache_root()}): {out}"
    if _is_within(out, studio_root()):
        parts = out.relative_to(studio_root().resolve()).parts
        if len(parts) >= 3 and parts[0] == "videos" and VERSION_DIR.fullmatch(parts[2]):
            return f"--out is inside the version folder {parts[2]}, which is never rewritten: {out}"
    return None


def _encode(out: Path, first: int, count: int, fps: float, alpha: bool, env: dict) -> Path:
    clip = out / ("clip.mov" if alpha else "clip.mp4")
    codec = (
        ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
        if alpha
        else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "14", "-movflags", "+faststart"]
    )
    argv = [
        "ffmpeg", "-y", "-framerate", f"{fps:g}", "-start_number", str(first),
        "-i", str(out / "f_%04d.png"), "-frames:v", str(count), *codec, str(clip),
    ]  # fmt: skip
    try:
        proc = run(argv, env=env)
    except FileNotFoundError:
        emit({"error": "ffmpeg not found", "missing": "ffmpeg", "install": FFMPEG_INSTALL}, EXIT_MISSING_TOOL)
    if proc.returncode != 0:
        _fail(f"ffmpeg exited {proc.returncode}: {_tail(proc.stderr)}")
    return clip


def main(argv: "Optional[list[str]]" = None) -> NoReturn:
    """Render, check and encode; always ends by emitting one JSON object."""
    parser = _Parser(prog="blender_render.py", description=__doc__.splitlines()[0])
    parser.add_argument("--blend", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--chunk", type=int)
    parser.add_argument("--alpha", action="store_true")
    parser.add_argument("--fps", type=float)
    args = parser.parse_args(argv)

    try:
        first, last = parse_frames(args.frames)
    except ValueError as exc:
        parser.error(str(exc))
    if args.chunk is not None and args.chunk < 1:
        parser.error("--chunk must be a positive number of frames")
    fps = args.fps if args.fps is not None else float(os.environ.get("QUIRK_VIDEO_FPS") or DEFAULT_FPS)
    if fps <= 0:
        parser.error("fps must be positive")

    blend, script, out = Path(args.blend).resolve(), Path(args.script).resolve(), Path(args.out).resolve()
    refusal = out_dir_refusal(out)
    if refusal:
        _fail(refusal)
    if not blend.is_file():
        _fail(f"blend file not found: {blend}")
    if not script.is_file():
        _fail(f"scene script not found: {script}")

    child_env = {k: v for k, v in os.environ.items() if k not in SCRUB_ENV}
    blender = find_blender(child_env)
    if blender is None:
        emit({"error": "Blender not found", "missing": "blender", "install": BLENDER_INSTALL}, EXIT_MISSING_TOOL)

    out.mkdir(parents=True, exist_ok=True)
    for stale in range(first, last + 1):
        (out / f"f_{stale:04d}.png").unlink(missing_ok=True)

    guards = []
    for a, b in chunk_ranges(first, last, args.chunk):
        guard_file = out / "guard.json"
        guard_file.unlink(missing_ok=True)
        try:
            proc = run(blender_argv(blender, blend, script, out, (a, b), args.alpha), env=child_env)
        except FileNotFoundError:
            emit({"error": "Blender not found", "missing": "blender", "install": BLENDER_INSTALL}, EXIT_MISSING_TOOL)
        if proc.returncode != 0:
            _fail(f"blender exited {proc.returncode} on frames {a}-{b}: {_tail(proc.stderr or proc.stdout)}")
        if not guard_file.is_file():
            _fail(f"guard.json was not written for frames {a}-{b}; bl_guard.py did not run to completion")
        try:
            guards.append(json.loads(guard_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            _fail(f"guard.json is not valid JSON: {exc}")
        if guards[-1].get("default_scene") or guards[-1].get("mirrored_frames"):
            break

    guard = merge_guards(guards)
    (out / "guard.json").write_text(json.dumps(guard), encoding="utf-8")
    warnings = guard_warnings(guard)
    if guard["default_scene"]:
        _fail(
            "the scene is Blender's default scene (a lone Cube): the author script did not build anything",
            guard=guard, warnings=warnings,
        )  # fmt: skip
    if guard["mirrored_frames"]:
        _fail(
            f"text faces away from the camera (mirrored) on frames {guard['mirrored_frames']}",
            guard=guard, warnings=warnings,
        )  # fmt: skip

    missing = [f"f_{n:04d}.png" for n in range(first, last + 1) if not (out / f"f_{n:04d}.png").is_file()]
    if missing:
        _fail(f"{len(missing)} rendered frame(s) missing, first {missing[0]}", guard=guard, warnings=warnings)

    clip = _encode(out, first, last - first + 1, fps, args.alpha, child_env)
    emit({
        "frames": last - first + 1,
        "out": str(out),
        "clip": str(clip),
        "guard": guard,
        "warnings": warnings,
    })  # fmt: skip


if __name__ == "__main__":
    main()
