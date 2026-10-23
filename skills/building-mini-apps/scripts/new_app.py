#!/usr/bin/env python3
"""Scaffold a mini app: shadcn Vite app, the base, and any named patterns from the local registry.

Usage:
    new_app.py <target_dir> [--patterns p1,p2,...] [--style <slug>]

Without --patterns only the base is installed. --style picks the look (default neutral-house; one
of the seven in styles/). Steps run in order: init, add, style, tokens, build, dev.

Exits 0 on success (printing the app path, patterns and style), 1 when a step fails (naming it and
printing the tail of its output), and 2 on a usage error, checked before any command runs: an
unknown pattern or style, an existing target, or a missing parent directory.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import _mini
import _styles


def in_git_work_tree(directory: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--is-inside-work-tree"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
    except OSError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def init_step(app: Path) -> int:
    cmd = [
        "pnpm", "dlx", _mini.SHADCN, "init", "-t", "vite", "-n", app.name,
        "-b", "radix", "-p", "nova", "-y", "--no-monorepo",
    ]
    code = _mini.run_step("init", cmd, app.parent)
    if code == 0 and (app / ".git").exists() and in_git_work_tree(app.parent):
        shutil.rmtree(app / ".git", ignore_errors=True)
    return code


tokens_step = _mini.tokens_step


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target_dir", help="new app directory; must not exist, its parent must")
    parser.add_argument("--patterns", help="comma-separated pattern slugs; omit for the base alone")
    parser.add_argument("--style", default=_styles.DEFAULT_SLUG,
                        help=f"style slug (default {_styles.DEFAULT_SLUG})")
    args = parser.parse_args(argv)

    app = Path(args.target_dir).expanduser().absolute()
    patterns = _mini.parse_patterns(args.patterns)
    unknown = _mini.unknown_patterns(patterns)
    if unknown:
        known = ", ".join(_mini.known_patterns())
        return _mini.usage_error(f"unknown pattern: {', '.join(unknown)} (known: {known})")
    if args.style not in _styles.SLUGS:
        return _mini.usage_error(
            f"unknown style: {args.style} (known: {', '.join(_styles.SLUGS)})"
        )
    if app.exists():
        return _mini.usage_error(f"target already exists: {app}")
    if not app.parent.is_dir():
        return _mini.usage_error(f"parent directory does not exist: {app.parent}")

    steps = (
        init_step,
        lambda a: _mini.add_step(a, patterns),
        lambda a: _mini.style_step(a, args.style),
        lambda a: _mini.tokens_step(a),
        _mini.build_step,
        _mini.dev_step,
    )
    for step in steps:
        code = step(app)
        if code:
            return code

    print(f"app: {app}")
    print(f"patterns: {', '.join(patterns) if patterns else 'base only'}")
    print(f"style: {args.style}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
