#!/usr/bin/env python3
"""Decide what an explainer does with a film, from the making-videos ``verify.json`` for it.

Usage: verify_outcome.py --verify FILE [--mp4 NAME]

Prints one JSON object, ``{"outcome", "failed", "detail"}``, where ``outcome`` is one of:

- ``ship``: the run passed; the film goes in.
- ``ship_disclosed``: only ``sync`` or ``loudness`` failed; the film goes in and the page lists the failure.
- ``omit``: a check a viewer would notice failed, an unknown check failed, or the run failed with no failed
  check named; the film stays out and the page says why.
- ``halt``: ``outside_calls`` failed, on any attempt. The call has already happened, so the run stops.
- ``retry``: the run failed and its stop flag is false; fix the cause and verify again.

The first matching rule decides, in the order ship, halt, retry, omit, ship_disclosed. ``halt`` outranks
``retry`` so a cloud call nobody named is never fixed and re-run.

Exit 0 when an outcome was produced. Exit 2 for an unreadable or malformed file, a run that is not in it, or
several runs with no ``--mp4``. Diagnostics go to stderr; the script never prompts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NoReturn, Optional

EXIT_OK = 0
EXIT_BAD_INPUT = 2

POLISH_CHECKS = ("sync", "loudness")
HALT_CHECK = "outside_calls"


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(f"verify_outcome.py: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def _bad_input(message: str) -> NoReturn:
    print(f"verify_outcome.py: {message}", file=sys.stderr)
    sys.exit(EXIT_BAD_INPUT)


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _bad_input(f"cannot read {path}: {exc}")
    if not isinstance(data, dict):
        _bad_input(f"{path} must hold a JSON object")
    return data


def _select_run(data: dict[str, Any], mp4: Optional[str]) -> tuple[str, dict[str, Any]]:
    """The one run to judge: ``runs`` keyed by MP4 filename, or a flat file that is itself one run."""
    runs = data.get("runs")
    if isinstance(runs, dict):
        runs = {name: run for name, run in runs.items() if isinstance(run, dict)}
    elif isinstance(data.get("checks"), list):
        runs = {mp4 or "(the only run)": data}
    else:
        runs = {}
    if mp4 is not None:
        wanted = Path(mp4).name
        if wanted not in runs:
            _bad_input(f"no run for {wanted} in the file; it has: {', '.join(runs) or 'no runs'}")
        return wanted, runs[wanted]
    if not runs:
        _bad_input("the file has no runs")
    if len(runs) > 1:
        _bad_input(f"several runs ({', '.join(runs)}); pass --mp4")
    (name, run), = runs.items()
    return name, run


def _failed_names(checks: Any) -> list[str]:
    if not isinstance(checks, list):
        return []
    names: list[str] = []
    for item in checks:
        if isinstance(item, dict) and item.get("status") == "fail" and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def _halted_on_any_attempt(run: dict[str, Any]) -> bool:
    if HALT_CHECK in _failed_names(run.get("checks")):
        return True
    attempts = run.get("attempts")
    if not isinstance(attempts, list):
        return False
    return any(isinstance(a, dict) and HALT_CHECK in _failed_names(a.get("checks")) for a in attempts)


def decide(name: str, run: dict[str, Any]) -> dict[str, Any]:
    """Apply the five rules to one run and return the JSON payload."""
    passed = run.get("passed")
    if not isinstance(passed, bool):
        _bad_input(f"{name}: 'passed' must be true or false")
    failed = _failed_names(run.get("checks"))
    if passed:
        return {"outcome": "ship", "failed": [], "detail": f"{name} passed verify; the film goes in."}
    if _halted_on_any_attempt(run):
        if HALT_CHECK not in failed:
            failed.append(HALT_CHECK)
        return {
            "outcome": "halt",
            "failed": failed,
            "detail": f"{name} made a call the brief did not name; stop the run and tell the user.",
        }
    stop = run.get("stop")
    if not isinstance(stop, bool):
        _bad_input(f"{name}: a failed run needs a boolean 'stop' flag")
    if not stop:
        return {
            "outcome": "retry",
            "failed": failed,
            "detail": f"{name} failed and has attempts left; fix the cause and verify again.",
        }
    if not failed or any(n not in POLISH_CHECKS for n in failed):
        reason = ", ".join(failed) if failed else "no failed check was named"
        return {
            "outcome": "omit",
            "failed": failed,
            "detail": f"{name} stopped after its last attempt ({reason}); leave the film out and say why on the page.",
        }
    return {
        "outcome": "ship_disclosed",
        "failed": failed,
        "detail": f"{name} stopped on {', '.join(failed)} only; the film goes in and the page lists the failure.",
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = _Parser(prog="verify_outcome.py", description="Sort a verify.json run into ship, ship_disclosed, omit, halt or retry.")
    parser.add_argument("--verify", required=True, help="the verify.json written by making-videos")
    parser.add_argument("--mp4", help="the render whose run to judge; needed when the file holds several")
    args = parser.parse_args(argv)
    name, run = _select_run(_load(Path(args.verify)), args.mp4)
    print(json.dumps(decide(name, run)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
