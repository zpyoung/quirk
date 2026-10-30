#!/usr/bin/env python3
"""Record a scripted web-app flow to WebM and MP4 with the cache's Playwright install.

``record.py --project DIR --url URL --steps STEPS.json [--size 1920x1080] [--fps 30] [--scale 1]``
prints one JSON object ``{"webm", "mp4", "duration_s"}`` and sends diagnostics to stderr. ``webm`` is
null when ``--scale`` is above 1.

``STEPS.json`` is a list of ``{"action": ...}`` objects, run in order after the browser opens ``URL``:
``goto`` (``url``, resolved against ``--url``), ``click`` (``selector`` or ``text``), ``fill``
(``selector``, ``value``), ``wait`` (``ms``, or ``selector`` / ``text`` to wait for) and ``scroll``
(``selector`` to scroll into view, else ``y`` pixels, default 600), ``hover`` (``selector`` or ``text``),
``move`` (``x``, ``y`` in viewport pixels), ``press`` (``key``, a Playwright key name such as ``Tab`` or
``Shift+Tab``) and ``drag`` (``from`` and ``to``, each ``{selector}``, ``{text}`` or ``{x, y}``). Every
step except ``wait`` is followed by a short pause so the recording shows the change; ``ms`` on those
steps sets its length. Step values are embedded in the generated script as JSON data, never as code.

The generated Node script lands in ``<project>/assets/recordings/`` beside the recording. The
browser is headless Chromium with ``recordVideo`` at ``--size`` (viewport and video size equal) and
``fps`` (Playwright 1.64+ encodes VP9 and takes the option). The MP4 is H.264 yuv420p, CRF 18.

A pointer is drawn into the page, and moves only on real mouse events, when ``--scale`` is above 1 or
any step is ``hover``, ``move`` or ``drag``; Playwright's own cursor is off then. In that mode every
pointer step, and the move before a ``click``, glides to the element's bounding-box center.
``--scale 2`` or ``3`` records at that device scale through CDP screencast frames, because
``recordVideo`` renders a 1x page into a corner of a larger canvas. The frames and their concat list
live in ``assets/recordings/.frames-<stamp>/`` until the MP4 is converted, and the MP4's width and
height must equal ``--size`` times ``--scale`` (rounded down to even) or the run exits 1 naming both.

Exit codes: 0 ok; 1 the recording or conversion failed, or the project directory is missing;
2 usage error (bad URL, size, fps, scale or steps, including an unknown action); 3 Node, ffmpeg, ffprobe
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

sys.dont_write_bytecode = True
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

ACTIONS = ("goto", "click", "fill", "wait", "scroll", "hover", "move", "press", "drag")
POINTER_ACTIONS = ("hover", "move", "drag")
SCALES = (1, 2, 3)
INSTALL_PLAYWRIGHT = "python3 skills/making-videos/scripts/doctor.py install --what playwright --yes"
SIZE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
RECORD_TIMEOUT_S = 900
CONVERT_TIMEOUT_S = 900
DEFAULT_PAUSE_MS = 400

NODE_HEAD = """\
"use strict";
const { chromium } = require(%(playwright)s);

const BASE_URL = %(url)s;
const SIZE = %(size)s;
const FPS = %(fps)d;
const SCALE = %(scale)d;
const POINTER = %(pointer)s;
const DEFAULT_PAUSE_MS = %(pause)d;
const GLIDE_MS = 700;
const DRAG_MS = 900;
%(paths)s
const STEPS = %(steps)s;
%(pointer_js)s
async function runStep(page, step) {
  switch (step.action) {
    case "goto":
      await page.goto(new URL(step.url || "", BASE_URL).href, { waitUntil: "load" });
      if (POINTER) {
        await nudge(page);
      }
      break;
    case "click":
      if (POINTER) {
        const at = await pointOf(page, step);
        await glide(page, at.x, at.y, GLIDE_MS);
        await page.mouse.down();
        await page.waitForTimeout(60);
        await page.mouse.up();
      } else {
        await (step.selector ? page.locator(step.selector) : page.getByText(step.text)).first().click();
      }
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
    case "hover": {
      const at = await pointOf(page, step);
      await glide(page, at.x, at.y, GLIDE_MS);
      break;
    }
    case "move":
      await glide(page, step.x, step.y, GLIDE_MS);
      break;
    case "press":
      await page.keyboard.press(step.key);
      break;
    case "drag": {
      const from = await pointOf(page, step.from);
      await glide(page, from.x, from.y, GLIDE_MS);
      await page.mouse.down();
      const to = await pointOf(page, step.to);
      await glide(page, to.x, to.y, DRAG_MS);
      await page.mouse.up();
      break;
    }
    default:
      throw new Error("unknown action " + step.action);
  }
  if (step.action !== "wait") {
    await page.waitForTimeout(step.ms === undefined ? DEFAULT_PAUSE_MS : step.ms);
  }
}
"""

POINTER_JS = """function installPointer() {
  const add = () => {
    const el = document.createElement("div");
    el.id = "mv-pointer";
    el.style.cssText = "position:fixed;left:-40px;top:-40px;width:22px;height:30px;z-index:2147483647;pointer-events:none;";
    el.innerHTML = '<svg viewBox="0 0 22 30" width="22" height="30"><path d="M2 2 L2 24 L8 18.5 L12 28 L16 26 L12 17 L20 17 Z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(el);
    window.addEventListener("mousemove", (e) => {
      el.style.left = e.clientX + "px";
      el.style.top = e.clientY + "px";
    }, true);
  };
  document.documentElement ? add() : addEventListener("DOMContentLoaded", add);
}

let cursor = { x: SIZE.width / 2, y: SIZE.height / 2 };

async function glide(page, x, y, ms) {
  const from = cursor;
  const n = Math.max(1, Math.round(ms / 16));
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    await page.mouse.move(from.x + (x - from.x) * e, from.y + (y - from.y) * e);
    await page.waitForTimeout(16);
  }
  cursor = { x, y };
}

async function nudge(page) {
  await page.mouse.move(cursor.x + 1, cursor.y);
  await page.mouse.move(cursor.x, cursor.y);
}

function locate(page, target) {
  return (target.selector ? page.locator(target.selector) : page.getByText(target.text)).first();
}

async function pointOf(page, target) {
  if (target.selector === undefined && target.text === undefined) {
    return { x: target.x, y: target.y };
  }
  const loc = locate(page, target);
  await loc.waitFor({ state: "visible" });
  await loc.scrollIntoViewIfNeeded();
  const box = await loc.boundingBox();
  if (!box) {
    throw new Error("no bounding box for " + JSON.stringify(target));
  }
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}
"""

VIDEO_TAIL = """
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: SIZE,
    recordVideo: {
      dir: RAW_DIR,
      size: SIZE,
      fps: FPS,%(show_actions)s
    },
  });
  if (POINTER) {
    await context.addInitScript(installPointer);
  }
  const page = await context.newPage();
  const video = page.video();
  try {
    await page.goto(BASE_URL, { waitUntil: "load" });
    if (POINTER) {
      await nudge(page);
    }
    for (const step of STEPS) {
      await runStep(page, step);
    }
    await context.close();
    await video.saveAs(FINAL_PATH);
    await video.delete();
  } finally {
    await browser.close();
  }
  console.log(FINAL_PATH);
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""

SHOW_ACTIONS = """
      showActions: { duration: 500, cursor: "pointer" },"""

SCREENCAST_TAIL = """
(async () => {
  const { mkdirSync, writeFileSync } = require("node:fs");
  const browser = await chromium.launch({
    headless: true,
    args: ["--force-device-scale-factor=" + SCALE, "--window-size=" + SIZE.width + "," + SIZE.height],
  });
  try {
    const context = await browser.newContext({ viewport: null });
    await context.addInitScript(installPointer);
    const page = await context.newPage();
    await page.goto(BASE_URL, { waitUntil: "load" });
    await nudge(page);
    await page.waitForTimeout(600);

    mkdirSync(FRAMES_DIR, { recursive: true });
    const frames = [];
    const cdp = await context.newCDPSession(page);
    cdp.on("Page.screencastFrame", async (frame) => {
      const file = String(frames.length).padStart(5, "0") + ".jpg";
      frames.push({ file, t: frame.metadata.timestamp });
      writeFileSync(FRAMES_DIR + "/" + file, Buffer.from(frame.data, "base64"));
      await cdp.send("Page.screencastFrameAck", { sessionId: frame.sessionId }).catch(() => {});
    });
    await cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: 96,
      maxWidth: SIZE.width * SCALE,
      maxHeight: SIZE.height * SCALE,
      everyNthFrame: 1,
    });
    await page.waitForTimeout(300);
    for (const step of STEPS) {
      await runStep(page, step);
    }
    await page.waitForTimeout(200);
    await cdp.send("Page.stopScreencast");
    const stoppedAt = Date.now() / 1000;

    if (frames.length === 0) {
      throw new Error("the screencast produced no frames");
    }
    const lines = [];
    frames.forEach((frame, i) => {
      const next = i + 1 < frames.length ? frames[i + 1].t : stoppedAt;
      const hold = next - frame.t;
      lines.push("file '" + frame.file + "'", "duration " + (hold > 0 ? hold : 0.2).toFixed(4));
    });
    lines.push("file '" + frames[frames.length - 1].file + "'");
    writeFileSync(LIST_PATH, lines.join("\\n") + "\\n");
    await context.close();
  } finally {
    await browser.close();
  }
  console.log(LIST_PATH);
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""

VIDEO_PATHS = """const RAW_DIR = %(raw_dir)s;
const FINAL_PATH = %(final_path)s;"""

SCREENCAST_PATHS = """const FRAMES_DIR = %(frames_dir)s;
const LIST_PATH = FRAMES_DIR + "/list.txt";"""


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


def _is_endpoint(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if _non_empty_str(value.get("selector")) or _non_empty_str(value.get("text")):
        return True
    return _is_number(value.get("x")) and _is_number(value.get("y"))


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
        elif action == "hover" and not (_non_empty_str(step.get("selector")) or _non_empty_str(step.get("text"))):
            _usage(f"{label}: hover needs a selector or text")
        elif action == "move" and not (_is_number(step.get("x")) and _is_number(step.get("y"))):
            _usage(f"{label}: move needs numeric x and y")
        elif action == "press" and not _non_empty_str(step.get("key")):
            _usage(f"{label}: press needs a non-empty key")
        elif action == "drag" and not (_is_endpoint(step.get("from")) and _is_endpoint(step.get("to"))):
            _usage(f"{label}: drag needs from and to, each a selector, text, or x and y")
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
    return scrubbed_env(
        {
            "NODE_PATH": str(pkg.parent) + (os.pathsep + existing if existing else ""),
            "PLAYWRIGHT_BROWSERS_PATH": str(cache_root() / "ms-playwright"),
        }
    )


def uses_pointer(steps: "list[dict]", scale: int) -> bool:
    """Whether the recording draws its own pointer: scaled, or any step moves the mouse on its own."""
    return scale > 1 or any(step["action"] in POINTER_ACTIONS for step in steps)


def render_script(url: str, size: "tuple[int, int]", fps: int, steps: "list[dict]",
                  pkg: Path, raw_dir: Path, final_path: Path, scale: int = 1,
                  frames_dir: Optional[Path] = None) -> str:
    """The Node script source; every value is embedded as a JSON literal.

    At scale 1 the script records a WebM to ``final_path`` and prints that path. Above 1 it writes
    screencast frames and an ffmpeg concat list into ``frames_dir`` and prints the list's path.
    """
    pointer = uses_pointer(steps, scale)
    values = {
        "playwright": json.dumps(str(pkg)),
        "url": json.dumps(url),
        "size": json.dumps({"width": size[0], "height": size[1]}),
        "fps": fps,
        "scale": scale,
        "pointer": "true" if pointer else "false",
        "pause": DEFAULT_PAUSE_MS,
        "steps": json.dumps(steps, indent=2),
        "pointer_js": "\n" + POINTER_JS if pointer else "",
    }
    if scale > 1:
        values["paths"] = SCREENCAST_PATHS % {"frames_dir": json.dumps(str(frames_dir))}
        return NODE_HEAD % values + SCREENCAST_TAIL
    values["paths"] = VIDEO_PATHS % {"raw_dir": json.dumps(str(raw_dir)), "final_path": json.dumps(str(final_path))}
    return NODE_HEAD % values + VIDEO_TAIL % {"show_actions": "" if pointer else SHOW_ACTIONS}


def _tail(text: str, limit: int = 1500) -> str:
    return text.strip()[-limit:]


def _even(value: int) -> int:
    return value // 2 * 2


def _probe(args: "list[str]", mp4: Path) -> str:
    try:
        proc = run(["ffprobe", "-v", "error", *args, str(mp4)], timeout=60)
    except FileNotFoundError:
        _missing("ffprobe", "brew install ffmpeg")
    except subprocess.TimeoutExpired:
        _fail("ffprobe timed out")
    if proc.returncode != 0 or not proc.stdout.strip():
        _fail(f"ffprobe gave no output (exit {proc.returncode}): {_tail(proc.stderr)}")
    return proc.stdout.strip().splitlines()[-1]


def _convert(source: Path, mp4: Path, fps: int, *, concat: bool = False,
             expected_size: Optional["tuple[int, int]"] = None) -> float:
    """Encode ``source`` (a WebM, or an ffmpeg concat list when ``concat``) to ``mp4``; return its duration.

    With ``expected_size`` the MP4's frame size must match it, otherwise the run exits 1 naming both
    sizes: a recording whose page does not fill the canvas is a failed recording.
    """
    ffmpeg_argv = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *(["-f", "concat"] if concat else []),
        "-i", str(source),
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
        proc_duration = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)], timeout=60)
    except FileNotFoundError:
        _missing("ffprobe", "brew install ffmpeg")
    except subprocess.TimeoutExpired:
        _fail("ffprobe timed out")
    try:
        duration = round(float(proc_duration.stdout.strip().splitlines()[-1]), 3)
    except (ValueError, IndexError):
        _fail(f"ffprobe gave no duration (exit {proc_duration.returncode}): {_tail(proc_duration.stderr)}")
    if expected_size is not None:
        want = f"{expected_size[0]}x{expected_size[1]}"
        got = _probe(["-select_streams", "v:0", "-show_entries", "stream=width,height",
                      "-of", "csv=s=x:p=0"], mp4)
        if got != want:
            _fail(f"the recording is {got} but --size times --scale is {want}")
    return duration


def _cmd_record(args: argparse.Namespace) -> None:
    steps = _load_steps(args.steps)
    size = _parse_size(args.size)
    if not 1 <= args.fps <= 120:
        _usage(f"--fps must be between 1 and 120, got {args.fps}")
    if args.scale not in SCALES:
        _usage(f"--scale must be 1, 2 or 3, got {args.scale}")
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
    frames_dir = rec_dir / f".frames-{stamp}"
    script_path.write_text(
        render_script(args.url, size, args.fps, steps, pkg, rec_dir / f".raw-{stamp}", final_webm,
                      scale=args.scale, frames_dir=frames_dir),
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
        produced = Path(printed[-1].strip()) if printed else None
        if produced is None or not produced.is_file():
            _fail(f"the recording script did not produce a video: {_tail(proc.stdout + proc.stderr)}")
        if args.scale > 1:
            webm = None
            mp4 = rec_dir / f"record-{stamp}.mp4"
            expected = (_even(size[0] * args.scale), _even(size[1] * args.scale))
            duration = _convert(produced, mp4, args.fps, concat=True, expected_size=expected)
            shutil.rmtree(frames_dir, ignore_errors=True)
        else:
            webm = produced
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
    emit({"webm": str(webm) if webm else None, "mp4": str(mp4), "duration_s": duration})


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="record.py", description="Record a scripted web-app flow with Playwright.")
    parser.add_argument("--project", required=True, help="project directory")
    parser.add_argument("--url", required=True, help="page to open first")
    parser.add_argument("--steps", required=True, help="JSON file with the list of steps")
    parser.add_argument("--size", default="1920x1080", help="viewport and video size, WxH")
    parser.add_argument("--fps", type=int, default=30, help="recording and MP4 frame rate")
    parser.add_argument("--scale", type=int, default=1,
                        help="device scale 1, 2 or 3; above 1 the video is size times scale")
    parser.set_defaults(func=_cmd_record)
    return parser


def main(argv: Optional["list[str]"] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
