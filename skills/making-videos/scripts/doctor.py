#!/usr/bin/env python3
"""Toolchain check and opt-in installer for the making-videos skill.

``check [--need narration,3d,record,captions]`` reports one entry per tool as
``{"ok", "tools": [{"name", "ok", "version", "fix"}]}``; it exits 0 even when a tool is missing
because the JSON carries the verdict. ``install --what tts|playwright --yes`` builds the skill's
private Kokoro venv (and downloads the two model files) or its Playwright install (package and Chromium, under ``<cache>/ms-playwright``) under the cache;
it refuses without ``--yes`` because the SKILL.md flow asks the user first. Node, pnpm, ffmpeg,
Blender and Chrome are never installed; each one's ``fix`` is the command or download to run.

Every command prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 ok; 1 an install step failed; 2 usage error (unknown need, install without
``--yes``); 3 a tool needed to install is missing (``uv`` or ``pnpm``).
Overrides, all for tests and unusual installs: ``QUIRK_VIDEO_CACHE`` (cache root),
``QUIRK_PLATFORM`` (replaces ``sys.platform``), ``QUIRK_FFMPEG`` (the only ffmpeg checked for the
``subtitles`` filter, needed only by ``captions``), ``QUIRK_BLENDER`` (the only Blender checked), ``QUIRK_KOKORO_BASE_URL``
(where the Kokoro model files are downloaded from).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import NoReturn, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_USAGE,
    PLAYWRIGHT_VERSION,
    SCRUB_ENV,
    cache_root,
    emit,
    run,
    ssl_context,
    venv_python,
)

NEEDS = ("narration", "3d", "record", "captions")
MIN_NODE_MAJOR = 22
MIN_BLENDER = (4, 2)
NARRATION_PYTHONS = ("3.11", "3.12")
VENV_MODULES = ("kokoro_onnx", "soundfile", "faster_whisper", "numpy")
KOKORO_PIP_PACKAGES = ("kokoro-onnx==0.6.1", "soundfile", "faster-whisper", "numpy")
KOKORO_MODEL_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
KOKORO_BASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
BLENDER_APP = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_DOWNLOAD = "download Blender 4.2 or newer from https://www.blender.org/download/"
INSTALL_TTS_FIX = "doctor.py install --what tts --yes"
INSTALL_PLAYWRIGHT_FIX = "doctor.py install --what playwright --yes"
PROBE_TIMEOUT_S = 30
INSTALL_TIMEOUT_S = 1800
STDERR_TAIL_LINES = 15

_VENV_PROBE = (
    "import sys\n"
    "print('%d.%d.%d' % sys.version_info[:3])\n"
    "missing = []\n"
    f"for name in {VENV_MODULES!r}:\n"
    "    try:\n"
    "        __import__(name)\n"
    "    except Exception:\n"
    "        missing.append(name)\n"
    "print(','.join(missing))\n"
)


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _env(extra: Optional[dict] = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in SCRUB_ENV}
    env["ORT_DISABLE_TELEMETRY"] = "1"
    if extra:
        env.update(extra)
    return env


def browsers_path() -> Path:
    """Where Playwright's browsers live: inside the skill cache, never the user-global one."""
    return cache_root() / "ms-playwright"


def _entry(name: str, ok: bool, version: str = "", fix: str = "", **extra: object) -> dict:
    entry = {"name": name, "ok": ok, "version": version, "fix": "" if ok else fix}
    entry.update(extra)
    return entry


def _probe(argv: "list[str]") -> "Optional[subprocess.CompletedProcess[str]]":
    """Run ``argv``; None when the executable is missing or times out."""
    try:
        return run(argv, env=_env(), timeout=PROBE_TIMEOUT_S)
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None


def _first_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0].strip() if lines else ""


def _version_in(text: str) -> str:
    match = re.search(r"version\s+(\S+)", text)
    return match.group(1) if match else _first_line(text)


def _platform() -> str:
    return os.environ.get("QUIRK_PLATFORM") or sys.platform


def check_platform() -> "list[dict]":
    plat = _platform()
    if plat == "darwin":
        return []
    return [
        _entry(
            "platform",
            False,
            plat,
            "unsupported platform; making-videos runs on macOS only",
        )
    ]


def check_node() -> dict:
    fix = "brew install node (Node 22 or newer is required)"
    proc = _probe(["node", "--version"])
    if proc is None or proc.returncode != 0:
        return _entry("node", False, "", fix)
    version = _first_line(proc.stdout).lstrip("v")
    match = re.match(r"(\d+)", version)
    return _entry("node", bool(match) and int(match.group(1)) >= MIN_NODE_MAJOR, version, fix)


def check_pnpm() -> dict:
    proc = _probe(["pnpm", "--version"])
    ok = proc is not None and proc.returncode == 0
    return _entry("pnpm", ok, _first_line(proc.stdout) if ok else "", "brew install pnpm")


def check_ffmpeg_tool(name: str) -> dict:
    proc = _probe([name, "-version"])
    ok = proc is not None and proc.returncode == 0
    return _entry(name, ok, _version_in(proc.stdout) if ok else "", "brew install ffmpeg-full")


def _has_subtitles_filter(binary: str) -> bool:
    proc = _probe([binary, "-hide_banner", "-filters"])
    if proc is None or proc.returncode != 0:
        return False
    return any(re.match(r"^\s*\S+\s+subtitles\s", line) for line in proc.stdout.splitlines())


def check_ffmpeg_subtitles() -> dict:
    override = os.environ.get("QUIRK_FFMPEG")
    if override:
        candidates = [override]
    else:
        candidates = [c for c in (shutil.which("ffmpeg"), FFMPEG_FULL) if c]
    for binary in candidates:
        if _has_subtitles_filter(binary):
            return _entry("ffmpeg_subtitles", True, "present", path=binary)
    return _entry("ffmpeg_subtitles", False, "", "brew install ffmpeg-full")


def check_narration() -> "list[dict]":
    python = venv_python()
    venv_entry: dict
    if not python.is_file():
        venv_entry = _entry("narration_venv", False, "", INSTALL_TTS_FIX)
    else:
        proc = _probe([str(python), "-c", _VENV_PROBE])
        lines = proc.stdout.splitlines() if proc is not None and proc.returncode == 0 else []
        if len(lines) < 1:
            venv_entry = _entry("narration_venv", False, "unusable", INSTALL_TTS_FIX)
        else:
            version = lines[0].strip()
            missing = [m for m in (lines[1].strip().split(",") if len(lines) > 1 else []) if m]
            right_python = ".".join(version.split(".")[:2]) in NARRATION_PYTHONS
            detail = version + (f"; missing {', '.join(missing)}" if missing else "")
            if not right_python:
                detail += "; Python 3.11 or 3.12 is required"
            venv_entry = _entry(
                "narration_venv", right_python and not missing, detail, INSTALL_TTS_FIX
            )
    model_dir = cache_root() / "models" / "kokoro"
    absent = [f for f in KOKORO_MODEL_FILES if not (model_dir / f).is_file()]
    models_entry = _entry(
        "kokoro_models",
        not absent,
        str(model_dir) if not absent else f"missing {', '.join(absent)}",
        INSTALL_TTS_FIX,
    )
    return [venv_entry, models_entry]


def _find_blender() -> Optional[str]:
    override = os.environ.get("QUIRK_BLENDER")
    if override:
        return override if Path(override).is_file() else None
    found = shutil.which("blender")
    if found:
        return found
    return BLENDER_APP if Path(BLENDER_APP).is_file() else None


def check_blender() -> dict:
    binary = _find_blender()
    if binary is None:
        return _entry("blender", False, "", BLENDER_DOWNLOAD)
    proc = _probe([binary, "--version"])
    match = re.search(r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", proc.stdout) if proc else None
    if not match:
        return _entry("blender", False, "unknown", BLENDER_DOWNLOAD, path=binary)
    major, minor = int(match.group(1)), int(match.group(2))
    version = ".".join(g for g in match.groups() if g is not None)
    return _entry("blender", (major, minor) >= MIN_BLENDER, version, BLENDER_DOWNLOAD, path=binary)


def check_playwright() -> "list[dict]":
    package = cache_root() / "node" / "node_modules" / "playwright" / "package.json"
    version = ""
    try:
        version = str(json.loads(package.read_text(encoding="utf-8")).get("version", ""))
    except (OSError, ValueError, AttributeError):
        pass
    package_entry = _entry("playwright", version == PLAYWRIGHT_VERSION, version, INSTALL_PLAYWRIGHT_FIX)
    root = browsers_path()
    builds = sorted(p.name for p in root.glob("chromium*-*") if p.is_dir()) if root.is_dir() else []
    browser_entry = _entry(
        "playwright_chromium",
        bool(builds),
        builds[0] if builds else f"no chromium under {root}",
        INSTALL_PLAYWRIGHT_FIX,
    )
    return [package_entry, browser_entry]


def cmd_check(args: argparse.Namespace) -> int:
    needs = [n.strip() for n in args.need.split(",") if n.strip()] if args.need else []
    unknown = [n for n in needs if n not in NEEDS]
    if unknown:
        emit({"error": f"unknown need: {', '.join(unknown)}; choose from {', '.join(NEEDS)}"}, EXIT_USAGE)

    tools = check_platform()
    tools += [
        check_node(),
        check_pnpm(),
        check_ffmpeg_tool("ffmpeg"),
        check_ffmpeg_tool("ffprobe"),
    ]
    if "captions" in needs:
        tools.append(check_ffmpeg_subtitles())
    if "narration" in needs:
        tools += check_narration()
    if "3d" in needs:
        tools.append(check_blender())
    if "record" in needs:
        tools += check_playwright()
    emit({"ok": all(t["ok"] for t in tools), "tools": tools})


def _command_failed(argv: "list[str]", detail: str, stderr: str = "") -> NoReturn:
    command = " ".join(argv)
    tail = "\n".join(stderr.strip().splitlines()[-STDERR_TAIL_LINES:])
    print(f"failed: {command}\n{tail}", file=sys.stderr)
    payload = {"error": f"{detail}: {command}", "command": command}
    if tail:
        payload["stderr_tail"] = tail
    emit(payload, EXIT_FAILED)


def _run_step(argv: "list[str]", extra_env: Optional[dict] = None) -> None:
    try:
        proc = run(argv, env=_env(extra_env), timeout=INSTALL_TIMEOUT_S)
    except FileNotFoundError:
        emit({"error": f"{argv[0]} is not installed", "tool": argv[0]}, EXIT_MISSING_TOOL)
    except subprocess.TimeoutExpired:
        _command_failed(argv, "timed out")
    if proc.returncode != 0:
        _command_failed(argv, f"exit {proc.returncode}", proc.stderr)


def _download(url: str, dest: Path) -> None:
    """Stream ``url`` to a temp file beside ``dest`` and rename it on success."""
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60, context=ssl_context()) as resp, open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh, 1024 * 1024)
        os.replace(tmp, dest)
    except (OSError, ValueError) as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        print(f"download failed: {url}: {exc}", file=sys.stderr)
        emit(
            {
                "error": f"could not download {dest.name}: {exc}",
                "url": url,
                "path": str(dest),
            },
            EXIT_FAILED,
        )


def install_tts() -> dict:
    if shutil.which("uv", path=os.environ.get("PATH")) is None:
        emit({"error": "uv is not installed", "tool": "uv", "fix": "brew install uv"}, EXIT_MISSING_TOOL)
    venv = cache_root() / "venv"
    cache_root().mkdir(parents=True, exist_ok=True)
    _run_step(["uv", "venv", "--python", "3.12", str(venv)])
    _run_step(["uv", "pip", "install", "--python", str(venv_python()), *KOKORO_PIP_PACKAGES])

    base = (os.environ.get("QUIRK_KOKORO_BASE_URL") or KOKORO_BASE_URL).rstrip("/") + "/"
    model_dir = cache_root() / "models" / "kokoro"
    model_dir.mkdir(parents=True, exist_ok=True)
    installed = ["venv", *KOKORO_PIP_PACKAGES]
    for name in KOKORO_MODEL_FILES:
        dest = model_dir / name
        if not dest.is_file() or dest.stat().st_size == 0:
            _download(base + name, dest)
        installed.append(str(dest))
    return {"installed": installed, "path": str(venv)}


def install_playwright() -> dict:
    if shutil.which("pnpm", path=os.environ.get("PATH")) is None:
        emit({"error": "pnpm is not installed", "tool": "pnpm", "fix": "brew install pnpm"}, EXIT_MISSING_TOOL)
    node_dir = cache_root() / "node"
    node_dir.mkdir(parents=True, exist_ok=True)
    manifest = node_dir / "package.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({"name": "quirk-video-node", "private": True}) + "\n")
    _run_step(["pnpm", "add", "--dir", str(node_dir), f"playwright@{PLAYWRIGHT_VERSION}"])
    _run_step(
        ["pnpm", "--dir", str(node_dir), "exec", "playwright", "install", "chromium"],
        {"PLAYWRIGHT_BROWSERS_PATH": str(browsers_path())},
    )
    return {
        "installed": [f"playwright@{PLAYWRIGHT_VERSION}", "chromium"],
        "path": str(node_dir),
        "browsers": str(browsers_path()),
    }


def cmd_install(args: argparse.Namespace) -> int:
    if not args.yes:
        emit(
            {"error": f"install {args.what} needs the user's agreement first; ask, then rerun with --yes"},
            EXIT_USAGE,
        )
    result = install_tts() if args.what == "tts" else install_playwright()
    emit(result)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="doctor.py", description="Check and install the making-videos toolchain.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = sub.add_parser("check", help="report which tools are present")
    check.add_argument("--need", default="", help="comma list of: " + ", ".join(NEEDS))
    check.set_defaults(func=cmd_check)
    install = sub.add_parser("install", help="install the Kokoro venv or Playwright into the cache")
    install.add_argument("--what", required=True, choices=("tts", "playwright"))
    install.add_argument("--yes", action="store_true", help="the user agreed to the install")
    install.set_defaults(func=cmd_install)
    return parser


def main(argv: Optional["list[str]"] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
