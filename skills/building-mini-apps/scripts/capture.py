#!/usr/bin/env python3
"""Capture helpers for analyzing an app: preflight checks, video search, and frame extraction.

Usage:
    capture.py preflight
    capture.py search <app> [--query TEXT] [--limit N]
    capture.py video <app> <source_id> <url> [--threshold FLOAT]

`video` downloads at 720p or lower into references/media/<app>/_video/<source_id>/, extracts
frames into references/media/<app>/ named <source_id>-t<SSSS>.png (whole-second timestamp),
prints each frame's path relative to the skill root, and always deletes its own
_video/<source_id>/ before exiting (and _video/ itself once nothing else is in it). Runs for
different source IDs can overlap safely. Frames left over from an earlier run of the same
source ID are replaced; other sources' frames and scratch, and anything outside
references/media/<app>/, are never touched.

Tools resolve from CAPTURE_YTDLP (else PATH, else ~/.local/bin/yt-dlp), CAPTURE_FFMPEG (else
PATH) and CAPTURE_PLAYWRIGHT (else PATH). An override that points at nothing is a failure
rather than a reason to fall back.

Exits 0 on success, 1 on a named failure, and 2 on a usage error: bad arguments, a source_id
that is not S<number>, or an app name that is not lowercase letters, digits and hyphens.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

SKILL_ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = SKILL_ROOT / "references" / "media"

APP_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SOURCE_ID_RE = re.compile(r"^S[0-9]+$")
PTS_TIME_RE = re.compile(r"pts_time:\s*(-?[0-9.]+(?:e[-+]?[0-9]+)?)")

DEFAULT_LIMIT = 8
DEFAULT_THRESHOLD = 0.3
MIN_SCENE_FRAMES = 5
SEARCH_FORMAT = "%(id)s|%(title)s|%(channel)s|%(upload_date)s|%(duration)s"
VIDEO_FORMAT = "bv*[height<=720][ext=mp4]/b[height<=720]"
TAIL_LINES = 15

# env override, executable name, fallback locations tried after PATH
TOOLS = {
    "yt-dlp": ("CAPTURE_YTDLP", [Path.home() / ".local" / "bin" / "yt-dlp"]),
    "ffmpeg": ("CAPTURE_FFMPEG", []),
    "playwright-cli": ("CAPTURE_PLAYWRIGHT", []),
}


class CaptureError(Exception):
    """A named failure; main() prints the message and exits 1."""


def resolve_tool(name: str) -> Optional[str]:
    """Absolute path of a tool, or None. A set but unusable override is not replaced by PATH."""
    env_name, fallbacks = TOOLS[name]
    override = os.environ.get(env_name)
    if override:
        return shutil.which(override)
    found = shutil.which(name)
    if found:
        return found
    for candidate in fallbacks:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def require_tool(name: str) -> str:
    found = resolve_tool(name)
    if found is None:
        env_name = TOOLS[name][0]
        override = os.environ.get(env_name)
        detail = f"{env_name}={override} is not an executable" if override else "not found"
        raise CaptureError(f"{name}: {detail}")
    return found


def tail(text: str) -> str:
    return "\n".join(text.rstrip().splitlines()[-TAIL_LINES:])


def run(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            list(cmd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except OSError as exc:
        raise CaptureError(f"{Path(cmd[0]).name}: could not run: {exc}") from exc


def check_git() -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(SKILL_ROOT), "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
    except OSError:
        return False, "git is not installed"
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    return False, (
        f"{SKILL_ROOT} is not inside a git work tree; run this skill from a quirk checkout, "
        "not an installed plugin copy"
    )


def check_references_writable() -> Tuple[bool, str]:
    references = SKILL_ROOT / "references"
    if references.is_dir() and os.access(references, os.W_OK):
        return True, str(references)
    return False, f"{references} is missing or not writable"


def check_tool(name: str) -> Tuple[bool, str]:
    found = resolve_tool(name)
    if found:
        return True, found
    env_name = TOOLS[name][0]
    override = os.environ.get(env_name)
    if override:
        return False, f"{env_name}={override} is not an executable"
    return False, f"not on PATH (override with {env_name})"


def cmd_preflight(_args: argparse.Namespace) -> int:
    checks: List[Tuple[str, Callable[[], Tuple[bool, str]]]] = [
        ("git", check_git),
        ("references", check_references_writable),
        *[(name, lambda n=name: check_tool(n)) for name in TOOLS],
    ]
    failed = False
    for label, check in checks:
        ok, detail = check()
        print(f"{'ok  ' if ok else 'FAIL'} {label}: {detail}")
        failed = failed or not ok
    return 1 if failed else 0


def cmd_search(args: argparse.Namespace) -> int:
    ytdlp = require_tool("yt-dlp")
    query = args.query or f"{args.app} app walkthrough {datetime.date.today().year}"
    proc = run([ytdlp, f"ytsearch{args.limit}:{query}", "--flat-playlist", "--print", SEARCH_FORMAT])
    if proc.returncode != 0:
        raise CaptureError(f"yt-dlp search failed (exit {proc.returncode}):\n{tail(proc.stderr)}")
    sys.stdout.write(proc.stdout)
    return 0


def make_scratch(video_dir: Path) -> None:
    """Create a run's scratch folder; retries because a sibling run may rmdir the shared parent."""
    for attempt in range(5):
        try:
            video_dir.mkdir(parents=True)
            return
        except FileNotFoundError:
            if attempt == 4:
                raise


def remove_scratch(video_dir: Path) -> None:
    """Delete only this run's scratch folder, then the shared parent if it is now empty."""
    shutil.rmtree(video_dir, ignore_errors=True)
    try:
        video_dir.parent.rmdir()
    except OSError:
        pass


def download(ytdlp: str, url: str, source_id: str, video_dir: Path) -> Path:
    make_scratch(video_dir)
    proc = run([ytdlp, "-f", VIDEO_FORMAT, "-o", str(video_dir / f"{source_id}.%(ext)s"), url])
    if proc.returncode != 0:
        raise CaptureError(f"download failed (yt-dlp exit {proc.returncode}):\n{tail(proc.stderr)}")
    videos = sorted(video_dir.glob(f"{source_id}.*"))
    if not videos:
        raise CaptureError("download failed: yt-dlp produced no file")
    return videos[0]


def extract(ffmpeg: str, video: Path, vf: str, out_dir: Path) -> List[Tuple[float, Path]]:
    """Run one ffmpeg pass; returns (pts_time, file) in output order."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()
    proc = run([
        ffmpeg, "-hide_banner", "-nostdin", "-i", str(video), "-vf", vf,
        "-fps_mode", "vfr", str(out_dir / "%04d.png"),
    ])
    if proc.returncode != 0:
        raise CaptureError(f"ffmpeg extraction failed (exit {proc.returncode}):\n{tail(proc.stderr)}")
    times = [float(m.group(1)) for line in proc.stderr.splitlines()
             if "showinfo" in line and (m := PTS_TIME_RE.search(line))]
    files = sorted(out_dir.glob("*.png"), key=lambda path: int(path.stem))
    if len(times) != len(files):
        raise CaptureError(
            f"ffmpeg extraction failed: {len(files)} frames but {len(times)} showinfo timestamps"
        )
    return list(zip(times, files))


def frame_name(source_id: str, seconds: int) -> str:
    return f"{source_id}-t{seconds:04d}.png"


def publish_frames(
    frames: List[Tuple[float, Path]], source_id: str, media: Path
) -> List[Path]:
    """Move frames into media/, one per whole second, replacing this source's earlier frames."""
    chosen = {}
    for pts, path in frames:
        chosen.setdefault(max(int(pts), 0), path)
    for stale in media.glob(f"{source_id}-t[0-9][0-9][0-9][0-9].png"):
        stale.unlink()
    published = []
    for seconds in sorted(chosen):
        dest = media / frame_name(source_id, seconds)
        shutil.move(str(chosen[seconds]), str(dest))
        published.append(dest)
    return published


def cmd_video(args: argparse.Namespace) -> int:
    ytdlp = require_tool("yt-dlp")
    ffmpeg = require_tool("ffmpeg")
    media = MEDIA_DIR / args.app
    video_dir = media / "_video" / args.source_id
    media.mkdir(parents=True, exist_ok=True)
    try:
        if video_dir.exists():
            shutil.rmtree(video_dir)
        video = download(ytdlp, args.url, args.source_id, video_dir)
        out_dir = video_dir / "frames"
        scene_vf = f"select='gt(scene,{args.threshold})',showinfo,scale=1280:-1"
        frames = extract(ffmpeg, video, scene_vf, out_dir)
        if len(frames) < MIN_SCENE_FRAMES:
            frames = extract(ffmpeg, video, "fps=1,showinfo,scale=1280:-1", out_dir)
        if not frames:
            raise CaptureError("no frames extracted from the video")
        published = publish_frames(frames, args.source_id, media)
    finally:
        remove_scratch(video_dir)
    for path in published:
        print(path.relative_to(SKILL_ROOT).as_posix())
    return 0


def app_name(value: str) -> str:
    if not APP_RE.match(value):
        raise argparse.ArgumentTypeError(f"app must match {APP_RE.pattern}: {value!r}")
    return value


def source_id(value: str) -> str:
    if not SOURCE_ID_RE.match(value):
        raise argparse.ArgumentTypeError(f"source_id must match {SOURCE_ID_RE.pattern}: {value!r}")
    return value


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def unit_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if not 0 < number < 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1, exclusive")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="check git, writable references/ and the three tools")

    search = sub.add_parser("search", help="flat-playlist video search through yt-dlp")
    search.add_argument("app", type=app_name)
    search.add_argument("--query", help="default: '<app> app walkthrough <current year>'")
    search.add_argument("--limit", type=positive_int, default=DEFAULT_LIMIT)

    video = sub.add_parser("video", help="download one video and extract frames from it")
    video.add_argument("app", type=app_name)
    video.add_argument("source_id", type=source_id, help="S<number>, as in the study note's Sources")
    video.add_argument("url")
    video.add_argument("--threshold", type=unit_float, default=DEFAULT_THRESHOLD,
                       help="scene-change threshold, default 0.3; lower it for more frames")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"preflight": cmd_preflight, "search": cmd_search, "video": cmd_video}
    try:
        return handlers[args.command](args)
    except CaptureError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
