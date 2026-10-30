#!/usr/bin/env python3
"""List the processes still running from an explainer folder, so a run can check that it stopped everything it started.

Usage: leftovers.py --explainer DIR

Prints one JSON object, ``{"yours": [{"pid", "command"}], "check_by_hand": [{"pid", "command"}]}``:

- ``yours``: the process's ``HOME`` is DIR or a folder under it. Staging runs everything with such a
  ``HOME``, so these are the run's own survivors and are safe to stop by PID.
- ``check_by_hand``: only the process's working directory is DIR or under it. It may be the user's own shell
  or editor, so the caller names it and never stops it.

A process in both groups is listed in ``yours`` only. A process whose environment can't be read (another
user's, or a protected system binary) is never ``yours``. An open file alone never lists a process, and
neither does this script or any process it started or runs under. Nothing is ever stopped.

Exit 0 when the scan ran, whatever it found. Exit 2 for a usage error or a DIR that is not a folder. Exit 3
when ``ps`` or ``lsof`` is missing or fails, which means the check did not run. Diagnostics go to stderr; the
script never prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_TOOL_FAILED = 3

PS_ENV_LINE = re.compile(r"^\s*(\d+)\s+(\d+)\s(.*)$", re.DOTALL)
PS_COMMAND_LINE = re.compile(r"^\s*(\d+)\s(.*)$", re.DOTALL)
NEXT_ENV_VAR = re.compile(r"\s[A-Za-z_][A-Za-z0-9_]*=")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(f"leftovers.py: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def _fail(code: int, message: str) -> NoReturn:
    print(f"leftovers.py: {message}", file=sys.stderr)
    sys.exit(code)


def _run(argv: list[str], ok_codes: tuple[int, ...] = (0,)) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, errors="replace")
    except OSError as exc:
        _fail(EXIT_TOOL_FAILED, f"cannot run {argv[0]}: {exc}")
    if done.returncode not in ok_codes or (done.returncode != 0 and done.stderr.strip()):
        detail = done.stderr.strip() or f"exit {done.returncode}"
        _fail(EXIT_TOOL_FAILED, f"{argv[0]} failed: {detail}")
    return done.stdout


def _is_under(path: str, base: Path) -> bool:
    """True when ``path`` is ``base`` or inside it, comparing whole path parts so a sibling sharing a prefix is not."""
    try:
        Path(os.path.realpath(path)).relative_to(base)
    except ValueError:
        return False
    return True


def _home_is_under(env_line: str, bases: set[Path], literal_dirs: set[str]) -> bool:
    """Whether the ``HOME`` that ``ps -e`` appended after the command line is under the folder.

    ``ps`` joins the environment with spaces, so a value containing spaces can't be cut out by splitting. The
    known folder is matched as a literal prefix first, then the value is cut at the next ``NAME=``.
    """
    marker = env_line.rfind(" HOME=")
    if marker < 0:
        return False
    rest = env_line[marker + len(" HOME="):]
    for literal in literal_dirs:
        if rest.startswith(literal):
            after = rest[len(literal):]
            if after == "" or after[0] == "/" or NEXT_ENV_VAR.match(after):
                return True
    value = NEXT_ENV_VAR.split(rest, maxsplit=1)[0]
    return any(_is_under(value, base) for base in bases)


def _processes_with_environment() -> dict[int, tuple[int, str]]:
    table: dict[int, tuple[int, str]] = {}
    # `-axeww` leaves the environment out on macOS; `-A -E` prints it after the command
    for line in _run(["ps", "-A", "-E", "-ww", "-o", "pid=,ppid=,command="]).splitlines():
        match = PS_ENV_LINE.match(line)
        if match:
            table[int(match.group(1))] = (int(match.group(2)), " " + match.group(3))
    return table


def _commands() -> dict[int, str]:
    commands: dict[int, str] = {}
    for line in _run(["ps", "-A", "-ww", "-o", "pid=,command="]).splitlines():
        match = PS_COMMAND_LINE.match(line)
        if match:
            commands[int(match.group(1))] = match.group(2).strip()
    return commands


def _working_directories() -> dict[int, str]:
    """Each process's working directory, from the cwd descriptor only, so an open file never counts."""
    cwds: dict[int, str] = {}
    pid = None
    for line in _run(["lsof", "-w", "-n", "-P", "-a", "-d", "cwd", "-F", "pn"], ok_codes=(0, 1)).splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            cwds[pid] = line[1:]
    return cwds


def _excluded(table: dict[int, tuple[int, str]]) -> set[int]:
    """This script, every process above it, and every process it started (its own ``ps`` and ``lsof``)."""
    me = os.getpid()
    skip = {me, os.getppid()}
    pid = me
    while pid in table and table[pid][0] not in skip and table[pid][0] > 1:
        pid = table[pid][0]
        skip.add(pid)
    below = {me}
    grew = True
    while grew:
        grew = False
        for child, (parent, _) in table.items():
            if parent in below and child not in below:
                below.add(child)
                grew = True
    return skip | below


def main() -> int:
    parser = _Parser(description="List processes still running from an explainer folder.")
    parser.add_argument("--explainer", required=True, metavar="DIR")
    args = parser.parse_args()

    folder = Path(args.explainer)
    if not folder.is_dir():
        _fail(EXIT_BAD_INPUT, f"{args.explainer} is not a folder")
    absolute = os.path.abspath(args.explainer)
    resolved = os.path.realpath(args.explainer)
    bases = {Path(absolute), Path(resolved)}
    literal_dirs = {absolute.rstrip("/"), resolved.rstrip("/")}

    # lsof runs first so its own process, which has the folder as its working directory, is gone before ps lists
    cwds = _working_directories()
    table = _processes_with_environment()
    commands = _commands()
    skip = _excluded(table)

    yours: list[int] = []
    for pid, (_, env_line) in table.items():
        if pid not in skip and _home_is_under(env_line, bases, literal_dirs):
            yours.append(pid)
    by_hand = [
        pid
        for pid, cwd in cwds.items()
        if pid in table and pid not in skip and pid not in yours and any(_is_under(cwd, base) for base in bases)
    ]

    def entry(pid: int) -> dict[str, object]:
        return {"pid": pid, "command": commands.get(pid, table.get(pid, (0, ""))[1].strip())}

    print(json.dumps({"yours": [entry(p) for p in sorted(yours)], "check_by_hand": [entry(p) for p in sorted(by_hand)]}))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
