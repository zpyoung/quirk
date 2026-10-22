#!/usr/bin/env python3
"""The one way making-videos runs HyperFrames: ``hf.py [--project DIR] -- <hyperframes args...>``.

Runs ``pnpm dlx hyperframes@<HYPERFRAMES_VERSION> <args>`` with telemetry and skill installs
switched off and every cloud credential removed from the child's environment. Unlike the other
scripts it does not print one JSON object on success: the child's stdout and stderr pass through
unchanged and the exit code is the child's. The wrapper itself reports problems as one JSON
object on stdout.

``snapshot`` always runs with ``--describe false`` (injected when absent); ``--describe true`` is
refused because describing sends frames to Gemini. With ``--project`` each run appends a
``calls.jsonl`` record. ``~/.hyperframes/config.json`` is never read or written.

Exit codes: the child's; 1 the project directory is missing; 2 usage error or refused
``--describe``; 3 pnpm is not installed.
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_MISSING_TOOL,
    EXIT_USAGE,
    HYPERFRAMES_VERSION,
    SCRUB_ENV,
    emit,
    log_call,
)

FORCED_ENV = {
    "HYPERFRAMES_NO_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "HYPERFRAMES_SKIP_SKILLS": "1",
}


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def child_env(base: Optional[dict] = None) -> dict:
    """``base`` (default ``os.environ``) with telemetry off and every SCRUB_ENV variable removed."""
    env = dict(os.environ if base is None else base)
    env.update(FORCED_ENV)
    for name in SCRUB_ENV:
        env.pop(name, None)
    return env


def subcommand_of(args: "list[str]") -> str:
    """The first argument that is not a flag, or an empty string."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return ""


def apply_describe_policy(args: "list[str]") -> "list[str]":
    """Return ``args`` with describing forced off for ``snapshot``; exits 2 on ``--describe true``."""
    if subcommand_of(args) != "snapshot":
        return args
    for i, arg in enumerate(args):
        if arg == "--describe" or arg.startswith("--describe="):
            if arg == "--describe":
                value = args[i + 1] if i + 1 < len(args) else ""
            else:
                value = arg.split("=", 1)[1]
            if value.lower() != "false":
                emit(
                    {
                        "error": "snapshot --describe is refused: describing sends frames to Gemini; "
                        "use --describe false"
                    },
                    EXIT_USAGE,
                )
            return args
    return args + ["--describe", "false"]


def main(argv: Optional["list[str]"] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        split = argv.index("--")
        own, hf_args = argv[:split], argv[split + 1 :]
    else:
        own, hf_args = argv, []

    parser = _Parser(prog="hf.py", description="Run HyperFrames through the pinned, scrubbed wrapper.")
    parser.add_argument("--project", help="project directory; appends a calls.jsonl record")
    ns = parser.parse_args(own)
    if not hf_args:
        parser.error("usage: hf.py [--project DIR] -- <hyperframes args...>")

    project = Path(ns.project) if ns.project else None
    if project is not None and not project.is_dir():
        emit({"error": f"project directory not found: {project}"}, EXIT_FAILED)

    hf_args = apply_describe_policy(hf_args)

    env = child_env()
    pnpm = shutil.which("pnpm", path=env.get("PATH"))
    if pnpm is None:
        emit(
            {"error": "pnpm is not installed; run `doctor.py check` for the fix"},
            EXIT_MISSING_TOOL,
        )

    cmd = [pnpm, "dlx", f"hyperframes@{HYPERFRAMES_VERSION}", *hf_args]
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        code = subprocess.run(cmd, env=env).returncode
    except FileNotFoundError:
        emit({"error": "pnpm is not installed; run `doctor.py check` for the fix"}, EXIT_MISSING_TOOL)

    if project is not None:
        log_call(
            project,
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "provider": "hyperframes",
                "subcommand": subcommand_of(hf_args),
                "args": hf_args,
                "status": code,
            },
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
