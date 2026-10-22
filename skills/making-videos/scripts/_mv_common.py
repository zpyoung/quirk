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
import ssl
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


CA_BUNDLE_FALLBACKS = (
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
)


def _default_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def ssl_context() -> ssl.SSLContext:
    """A certificate-verifying TLS context that works on Pythons with no CA bundle of their own.

    Resolution order: ``SSL_CERT_FILE`` / ``SSL_CERT_DIR`` when set to something that exists; the
    interpreter's default context when it has CA certificates loaded; else the first existing
    bundle among ``CA_BUNDLE_FALLBACKS`` (macOS ``/etc/ssl/cert.pem``, Homebrew OpenSSL). When none
    exists the default context is returned as is. Verification is never disabled.
    ``QUIRK_CA_FALLBACKS`` (an ``os.pathsep`` list of files) replaces the fallback list so tests can
    point it at a temporary bundle.
    """
    cafile = os.environ.get("SSL_CERT_FILE") or ""
    capath = os.environ.get("SSL_CERT_DIR") or ""
    use_file = bool(cafile) and Path(cafile).is_file()
    use_dir = bool(capath) and Path(capath).is_dir()
    if use_file or use_dir:
        return ssl.create_default_context(
            cafile=cafile if use_file else None, capath=capath if use_dir else None
        )
    ctx = _default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) > 0:
        return ctx
    override = os.environ.get("QUIRK_CA_FALLBACKS")
    fallbacks = tuple(p for p in override.split(os.pathsep) if p) if override is not None else CA_BUNDLE_FALLBACKS
    for candidate in fallbacks:
        if Path(candidate).is_file():
            return ssl.create_default_context(cafile=candidate)
    return ctx


FFMPEG_FULL_PATHS = (
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
    "/usr/local/opt/ffmpeg-full/bin/ffmpeg",
)
BREW_PREFIX_TIMEOUT_S = 15


def ffmpeg_full_candidates() -> "list[Path]":
    """Existing ``ffmpeg-full`` binaries, in preference order; empty when none is installed.

    Order: the Apple Silicon and Intel Homebrew prefixes (``FFMPEG_FULL_PATHS``), then
    ``$(brew --prefix ffmpeg-full)/bin/ffmpeg`` when ``brew`` is on PATH. The brew call (one
    subprocess, scrubbed env, short timeout, any failure ignored) only runs when neither fixed
    path exists. ``QUIRK_FFMPEG_FULL_PATHS`` (an ``os.pathsep`` list, empty allowed) replaces the
    two fixed paths so tests do not see the machine's real Homebrew install. An explicit
    ``QUIRK_FFMPEG`` is the caller's concern and always outranks this list.
    """
    override = os.environ.get("QUIRK_FFMPEG_FULL_PATHS")
    fixed = tuple(p for p in override.split(os.pathsep) if p) if override is not None else FFMPEG_FULL_PATHS
    found = [Path(p) for p in fixed if Path(p).is_file()]
    if found:
        return found
    try:
        proc = run(["brew", "--prefix", "ffmpeg-full"], timeout=BREW_PREFIX_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return []
    prefix = proc.stdout.strip() if proc.returncode == 0 else ""
    if not prefix:
        return []
    candidate = Path(prefix) / "bin" / "ffmpeg"
    return [candidate] if candidate.is_file() else []


def emit(obj: dict, code: int = 0) -> NoReturn:
    """Print ``obj`` as the one JSON object on stdout, then exit with ``code``."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()
    raise SystemExit(code)


def scrubbed_env(extra: Optional[dict] = None) -> dict:
    """A copy of ``os.environ`` plus ``extra`` with every ``SCRUB_ENV`` variable removed.

    Every child process the skill launches gets this environment, so no Gemini or provider key
    reaches a tool that has no use for it.
    """
    env = dict(os.environ)
    if extra:
        env.update(extra)
    for name in SCRUB_ENV:
        env.pop(name, None)
    return env


def run(
    argv: "list[str]",
    env: Optional[dict] = None,
    timeout: Optional[float] = None,
) -> "subprocess.CompletedProcess[str]":
    """Run ``argv`` capturing text output; never raises on a non-zero exit.

    The child never sees a ``SCRUB_ENV`` variable: ``env`` defaults to the current environment and
    any ``SCRUB_ENV`` key is dropped from it either way.

    Raises ``subprocess.TimeoutExpired`` on timeout and ``FileNotFoundError`` when
    ``argv[0]`` is missing, so callers can map them to exit 1 and exit 3.
    """
    return subprocess.run(
        argv,
        env=scrubbed_env() if env is None else {k: v for k, v in env.items() if k not in SCRUB_ENV},
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
