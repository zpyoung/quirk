#!/usr/bin/env python3
"""Scaffold a mini app: shadcn Vite app, the base, and any named patterns from the local registry.

Usage:
    new_app.py <target_dir> [--patterns p1,p2,...]

Without --patterns only the base is installed. Steps run in order: init, add, tokens, build, dev.

Exits 0 on success (printing the app path and patterns), 1 when a step fails (naming it and
printing the tail of its output), and 2 on a usage error, checked before any command runs: an
unknown pattern, an existing target, or a missing parent directory.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _mini

TOKENS_IMPORT = '@import "./styles/mini-tokens.css";'
TOP_LEVEL_IMPORT_RE = re.compile(r"^@import\b")


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


def tokens_step(app: Path) -> int:
    """Import mini-tokens.css right after the last top-level @import; a no-op when present."""
    css = app / "src" / "index.css"
    try:
        text = css.read_text(encoding="utf-8")
    except OSError as exc:
        return _mini.step_failed("tokens", str(exc))
    if "styles/mini-tokens.css" in text:
        return 0
    lines = text.splitlines(keepends=True)
    last = max((i for i, line in enumerate(lines) if TOP_LEVEL_IMPORT_RE.match(line)), default=None)
    if last is None:
        return _mini.step_failed("tokens", f"no top-level @import found in {css}")
    if not lines[last].endswith("\n"):
        lines[last] += "\n"
    lines.insert(last + 1, TOKENS_IMPORT + "\n")
    css.write_text("".join(lines), encoding="utf-8")
    print(f"+ [tokens] wired {TOKENS_IMPORT} into {css}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target_dir", help="new app directory; must not exist, its parent must")
    parser.add_argument("--patterns", help="comma-separated pattern slugs; omit for the base alone")
    args = parser.parse_args(argv)

    app = Path(args.target_dir).expanduser().absolute()
    patterns = _mini.parse_patterns(args.patterns)
    unknown = _mini.unknown_patterns(patterns)
    if unknown:
        known = ", ".join(_mini.known_patterns())
        return _mini.usage_error(f"unknown pattern: {', '.join(unknown)} (known: {known})")
    if app.exists():
        return _mini.usage_error(f"target already exists: {app}")
    if not app.parent.is_dir():
        return _mini.usage_error(f"parent directory does not exist: {app.parent}")

    steps = (
        init_step,
        lambda a: _mini.add_step(a, patterns),
        tokens_step,
        _mini.build_step,
        _mini.dev_step,
    )
    for step in steps:
        code = step(app)
        if code:
            return code

    print(f"app: {app}")
    print(f"patterns: {', '.join(patterns) if patterns else 'base only'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
