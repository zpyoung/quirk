#!/usr/bin/env python3
"""Shared helpers for the making-videos scripts: paths, JSON output, subprocess and call logging.

Every script prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 ok; 1 the operation or check failed (the JSON has an ``error`` key or explains);
2 usage error; 3 a required tool or venv is missing (the JSON names it and the install command).
``QUIRK_STUDIO`` (default ``~/Studio``) and ``QUIRK_VIDEO_CACHE`` (default ``~/.cache/quirk-video``)
override the two roots so tests never touch the home directory.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, Optional

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_MISSING_TOOL = 0, 1, 2, 3

HYPERFRAMES_VERSION = "0.8.185"
PLAYWRIGHT_VERSION = "1.64.1"

PROVIDER_KEY_ENV = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "pexels": "PEXELS_API_KEY",
    "pixabay": "PIXABAY_API_KEY",
    "freesound": "FREESOUND_API_KEY",
}

SCRUB_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY") + tuple(PROVIDER_KEY_ENV.values())


def studio_root() -> Path:
    """The studio directory: ``$QUIRK_STUDIO`` or ``~/Studio``."""
    return Path(os.environ.get("QUIRK_STUDIO") or "~/Studio").expanduser()


def cache_root() -> Path:
    """The tool cache directory: ``$QUIRK_VIDEO_CACHE`` or ``~/.cache/quirk-video``."""
    return Path(os.environ.get("QUIRK_VIDEO_CACHE") or "~/.cache/quirk-video").expanduser()


def venv_python() -> Path:
    """The interpreter of the skill's private venv; it may not exist yet."""
    return cache_root() / "venv" / "bin" / "python"


def project_dir(name: str) -> Path:
    """The project folder for a dated name such as ``2026-10-22-launch``."""
    return studio_root() / "videos" / name


def emit(obj: dict, code: int = 0) -> NoReturn:
    """Print ``obj`` as the one JSON object on stdout, then exit with ``code``."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()
    raise SystemExit(code)


def run(
    argv: "list[str]",
    env: Optional[dict] = None,
    timeout: Optional[float] = None,
) -> "subprocess.CompletedProcess[str]":
    """Run ``argv`` capturing text output; never raises on a non-zero exit.

    Raises ``subprocess.TimeoutExpired`` on timeout and ``FileNotFoundError`` when
    ``argv[0]`` is missing, so callers can map them to exit 1 and exit 3.
    """
    return subprocess.run(
        argv,
        env=env,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def log_call(project: Path, record: dict) -> None:
    """Append ``record`` as one line of ``<project>/calls.jsonl``.

    Raises ``FileNotFoundError`` when the project directory does not exist; it never creates one.
    """
    if not Path(project).is_dir():
        raise FileNotFoundError(f"project directory not found: {project}")
    with open(Path(project) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def load_brief(project: Path) -> dict:
    """Read ``<project>/brief.json``; raises ``FileNotFoundError`` when it is missing."""
    path = Path(project) / "brief.json"
    if not path.is_file():
        raise FileNotFoundError(f"brief.json not found in {project}")
    return json.loads(path.read_text(encoding="utf-8"))
