#!/usr/bin/env python3
"""Add pattern blocks to an existing mini app.

Usage:
    add_patterns.py <app_dir> --patterns p1,p2,...

Runs add (the base plus the patterns; files that already exist are skipped, never overwritten),
build and dev, as new_app.py does.

Exits 0 on success (printing what was added), 1 when a step fails (naming it and printing the
tail of its output), and 2 on a usage error, checked before any command runs: no components.json
in <app_dir>, or an unknown pattern.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _mini


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app_dir", help="existing mini app (has components.json)")
    parser.add_argument("--patterns", required=True, help="comma-separated pattern slugs")
    args = parser.parse_args(argv)

    app = Path(args.app_dir).expanduser().absolute()
    patterns = _mini.parse_patterns(args.patterns)
    if not (app / "components.json").is_file():
        return _mini.usage_error(f"not a mini app (no components.json): {app}")
    if not patterns:
        return _mini.usage_error("--patterns needs at least one pattern")
    unknown = _mini.unknown_patterns(patterns)
    if unknown:
        known = ", ".join(_mini.known_patterns())
        return _mini.usage_error(f"unknown pattern: {', '.join(unknown)} (known: {known})")

    for step in (lambda a: _mini.add_step(a, patterns), _mini.build_step, _mini.dev_step):
        code = step(app)
        if code:
            return code

    print(f"app: {app}")
    print(f"added: {', '.join(patterns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
