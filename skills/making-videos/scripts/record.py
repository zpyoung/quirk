#!/usr/bin/env python3
"""Record a scripted web-app flow to WebM and MP4 with the cache's Playwright install.

``record.py --project DIR --url URL --steps STEPS.json [--size 1920x1080] [--fps 30]`` prints one
JSON object ``{"webm", "mp4", "duration_s"}`` and sends diagnostics to stderr.

``STEPS.json`` is a list of ``{"action": ...}`` objects, run in order after the browser opens ``URL``:
``goto`` (``url``, resolved against ``--url``), ``click`` (``selector`` or ``text``), ``fill``
(``selector``, ``value``), ``wait`` (``ms``, or ``selector`` / ``text`` to wait for) and ``scroll``
(``selector`` to scroll into view, else ``y`` pixels, default 600). Every step except ``wait`` is
followed by a short pause so the recording shows the change; ``ms`` on those steps sets its length.
Step values are embedded in the generated script as JSON data, never as code.

The generated Node script lands in ``<project>/assets/recordings/`` beside the recording. The
browser is headless Chromium with ``recordVideo`` at ``--size`` (viewport and video size equal) and
``fps`` (Playwright 1.64+ encodes VP9 and takes the option). The MP4 is H.264 yuv420p, CRF 18.

Exit codes: 0 ok; 1 the recording or conversion failed, or the project directory is missing;
2 usage error (bad URL, size, fps or steps, including an unknown action); 3 Node, ffmpeg, ffprobe
or the pinned Playwright install is missing (the JSON names the fix). Provider keys and Gemini keys
are removed from the child environment. A ``calls.jsonl`` record with provider ``playwright`` and
the URL's host (no query string) is appended once the browser has been launched.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import NoReturn, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_USAGE,
    PLAYWRIGHT_VERSION,
    cache_root,
    emit,
    log_call,
    run,
    scrubbed_env,
)

ACTIONS = ("goto", "click", "fill", "wait", "scroll")
INSTALL_PLAYWRIGHT = "python3 skills/making-videos/scripts/doctor.py install --what playwright --yes"
SIZE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
RECORD_TIMEOUT_S = 900
CONVERT_TIMEOUT_S = 900
DEFAULT_PAUSE_MS = 400

NODE_SCRIPT = """\
"use strict";
const { chromium } = require(%(playwright)s);

const BASE_URL = %(url)s;
const SIZE = %(size)s;
const FPS = %(fps)d;
const RAW_DIR = %(raw_dir)s;
const FINAL_PATH = %(final_path)s;
const DEFAULT_PAUSE_MS = %(pause)d;
const STEPS = %(steps)s;

async function runStep(page, step) {
  switch (step.action) {
    case "goto":
      await page.goto(new URL(step.url || "", BASE_URL).href, { waitUntil: "load" });
      break;
    case "click":
      await (step.selector ? page.locator(step.selector) : page.getByText(step.text)).first().click();
      break;
    case "fill":
      await page.locator(step.selector).first().fill(step.value);
      break;
    case "wait":
      if (step.ms !== undefined) {
        await page.waitForTimeout(step.ms);
      } else if (step.selector) {
        await page.locator(step.selector).first().waitFor();
      } else {
        await page.getByText(step.text).first().waitFor();
      }
      break;
    case "scroll":
      if (step.selector) {
        await page.locator(step.selector).first().scrollIntoViewIfNeeded();
      } else {
        await page.mouse.wheel(0, step.y === undefined ? 600 : step.y);
      }
      break;
    default:
      throw new Error("unknown action " + step.action);
  }
  if (step.action !== "wait") {
    await page.waitForTimeout(step.ms === undefined ? DEFAULT_PAUSE_MS : step.ms);
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: SIZE,
    recordVideo: {
      dir: RAW_DIR,
      size: SIZE,
      fps: FPS,
      showActions: { duration: 500, cursor: "pointer" },
    },
  });
  const page = await context.newPage();
  const video = page.video();
  try {
    await page.goto(BASE_URL, { waitUntil: "load" });
    for (const step of STEPS) {
      await runStep(page, step);
    }
  } finally {
    await context.close();
    await browser.close();
  }
  await video.saveAs(FINAL_PATH);
  await video.delete();
  console.log(FINAL_PATH);
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _usage(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    emit({"error": message}, EXIT_USAGE)


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    emit({"error": message}, EXIT_FAILED)


def _missing(tool: str, fix: str) -> NoReturn:
    message = f"{tool} is required but missing; fix: {fix}"
    print(message, file=sys.stderr)
    emit({"error": message, "missing": tool, "install": fix}, EXIT_MISSING_TOOL)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def validate_steps(raw: object) -> "list[dict]":
    """Return ``raw`` if it is a valid list of steps, else exit 2 naming the first bad step."""
    if not isinstance(raw, list) or not raw:
        _usage("--steps must be a non-empty JSON list of step objects")
    for index, step in enumerate(raw, start=1):
        label = f"step {index}"
        if not isinstance(step, dict):
            _usage(f"{label} must be an object")
        action = step.get("action")
        if action not in ACTIONS:
            _usage(f"{label}: unknown action {action!r}; use one of {', '.join(ACTIONS)}")
        if "ms" in step and not (_is_number(step["ms"]) and step["ms"] >= 0):
            _usage(f"{label}: ms must be a number of at least 0")
        if action == "goto" and "url" in step and not isinstance(step["url"], str):
            _usage(f"{label}: goto url must be a string")
        elif action == "click" and not (_non_empty_str(step.get("selector")) or _non_empty_str(step.get("text"))):
            _usage(f"{label}: click needs a selector or text")
        elif action == "fill":
            if not _non_empty_str(step.get("selector")) or not isinstance(step.get("value"), str):
                _usage(f"{label}: fill needs a selector and a string value")
        elif action == "wait":
            if not ("ms" in step or _non_empty_str(step.get("selector")) or _non_empty_str(step.get("text"))):
                _usage(f"{label}: wait needs ms, a selector or text")
        elif action == "scroll" and "y" in step and not _is_number(step["y"]):
            _usage(f"{label}: scroll y must be a number")
    return raw


def _load_steps(path: str) -> "list[dict]":
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        _usage(f"cannot read --steps {path}: {exc}")
    except (ValueError, UnicodeError) as exc:
        _usage(f"--steps {path} is not valid JSON: {exc}")
    return validate_steps(raw)


def _parse_size(value: str) -> "tuple[int, int]":
    match = SIZE_RE.match(value)
    if not match or int(match.group(1)) < 1 or int(match.group(2)) < 1:
        _usage(f"--size must look like 1920x1080, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def _parse_url(value: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        _usage(f"--url must be an http(s) URL with a host, got {value!r}")
    return parts


def _playwright_dir() -> Path:
    return cache_root() / "node" / "node_modules" / "playwright"


def _check_playwright() -> Path:
    pkg = _playwright_dir()
    try:
        version = json.loads((pkg / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        version = None
    if version != PLAYWRIGHT_VERSION:
        found = f"found {version}" if version else "not installed"
        _missing(f"playwright {PLAYWRIGHT_VERSION} ({found})", INSTALL_PLAYWRIGHT)
    return pkg


def _child_env(pkg: Path) -> dict:
    existing = os.environ.get("NODE_PATH")
    return scrubbed_env({"NODE_PATH": str(pkg.parent) + (os.pathsep + existing if existing else "")})


def render_script(url: str, size: "tuple[int, int]", fps: int, steps: "list[dict]",
                  pkg: Path, raw_dir: Path, final_path: Path) -> str:
    """The Node script source; every value is embedded as a JSON literal."""
    return NODE_SCRIPT % {
        "playwright": json.dumps(str(pkg)),
        "url": json.dumps(url),
        "size": json.dumps({"width": size[0], "height": size[1]}),
        "fps": fps,
        "raw_dir": json.dumps(str(raw_dir)),
        "final_path": json.dumps(str(final_path)),
        "pause": DEFAULT_PAUSE_MS,
        "steps": json.dumps(steps, indent=2),
    }


def _tail(text: str, limit: int = 1500) -> str:
    return text.strip()[-limit:]


def _convert(webm: Path, mp4: Path, fps: int) -> float:
    ffmpeg_argv = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(webm),
        "-vf", f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-movflags", "+faststart", "-an", str(mp4),
    ]
    try:
        proc = run(ffmpeg_argv, timeout=CONVERT_TIMEOUT_S)
    except FileNotFoundError:
        _missing("ffmpeg", "brew install ffmpeg")
    except subprocess.TimeoutExpired:
        _fail("ffmpeg timed out converting the recording")
    if proc.returncode != 0 or not mp4.is_file():
        _fail(f"ffmpeg failed (exit {proc.returncode}): {_tail(proc.stderr)}")
    try:
        probe = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)], timeout=60)
    except FileNotFoundError:
        _missing("ffprobe", "brew install ffmpeg")
    except subprocess.TimeoutExpired:
        _fail("ffprobe timed out")
    try:
        return round(float(probe.stdout.strip().splitlines()[-1]), 3)
    except (ValueError, IndexError):
        _fail(f"ffprobe gave no duration (exit {probe.returncode}): {_tail(probe.stderr)}")


def _cmd_record(args: argparse.Namespace) -> None:
    steps = _load_steps(args.steps)
    size = _parse_size(args.size)
    if not 1 <= args.fps <= 120:
        _usage(f"--fps must be between 1 and 120, got {args.fps}")
    url_parts = _parse_url(args.url)

    project = Path(args.project)
    if not project.is_dir():
        _fail(f"project directory not found: {project}")
    pkg = _check_playwright()
    if shutil.which("node") is None:
        _missing("node", "install Node (for example: brew install node)")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            _missing(tool, "brew install ffmpeg")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    rec_dir = project / "assets" / "recordings"
    rec_dir.mkdir(parents=True, exist_ok=True)
    script_path = rec_dir / f"record-{stamp}.cjs"
    final_webm = rec_dir / f"record-{stamp}.webm"
    script_path.write_text(
        render_script(args.url, size, args.fps, steps, pkg, rec_dir / f".raw-{stamp}", final_webm),
        encoding="utf-8",
    )

    status = 0
    mp4_bytes = 0
    try:
        try:
            proc = run(["node", str(script_path)], env=_child_env(pkg), timeout=RECORD_TIMEOUT_S)
        except FileNotFoundError:
            _missing("node", "install Node (for example: brew install node)")
        except subprocess.TimeoutExpired:
            _fail(f"recording timed out after {RECORD_TIMEOUT_S}s")
        printed = [line for line in proc.stdout.splitlines() if line.strip()]
        if proc.returncode != 0:
            _fail(f"recording failed (exit {proc.returncode}): {_tail(proc.stderr)}")
        webm = Path(printed[-1].strip()) if printed else None
        if webm is None or not webm.is_file():
            _fail(f"the recording script did not produce a video: {_tail(proc.stdout + proc.stderr)}")
        mp4 = webm.with_suffix(".mp4")
        duration = _convert(webm, mp4, args.fps)
        status, mp4_bytes = 200, mp4.stat().st_size
    finally:
        try:
            log_call(project, {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "provider": "playwright",
                "method": "RECORD",
                "host": (url_parts.hostname or "").lower(),
                "path": url_parts.path,
                "status": status,
                "bytes": mp4_bytes,
            })
        except OSError as exc:
            print(f"could not write calls.jsonl: {exc}", file=sys.stderr)
    emit({"webm": str(webm), "mp4": str(mp4), "duration_s": duration})


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="record.py", description="Record a scripted web-app flow with Playwright.")
    parser.add_argument("--project", required=True, help="project directory")
    parser.add_argument("--url", required=True, help="page to open first")
    parser.add_argument("--steps", required=True, help="JSON file with the list of steps")
    parser.add_argument("--size", default="1920x1080", help="viewport and video size, WxH")
    parser.add_argument("--fps", type=int, default=30, help="recording and MP4 frame rate")
    parser.set_defaults(func=_cmd_record)
    return parser


def main(argv: Optional["list[str]"] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
