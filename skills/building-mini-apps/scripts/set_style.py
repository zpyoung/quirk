#!/usr/bin/env python3
"""Switch an existing mini app to another style.

Usage:
    set_style.py <app_dir> <slug> [--force]

Runs style (overwrites src/styles/mini-tokens.css and adds any font packages the style needs;
packages are never removed), tokens (rewires the font lines in src/index.css once), build and
dev, as new_app.py does. Files other than the tokens file are left as the user edited them.

A tokens file that was hand-edited (no style header, or a header whose hash no longer matches) is
not overwritten unless --force is given; --force discards those edits.

Exits 0 on success (printing the app path and style), 1 when a step fails (naming it and printing
the tail of its output), and 2 on a usage error, checked before any command runs: no
components.json in <app_dir>, an unknown style, a missing tokens file, or a hand-edited one
without --force.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _mini
import _styles


def hand_edited(tokens: Path) -> bool:
    """True when the tokens file lacks a generated header or no longer matches its hash."""
    slug, ok = _styles.parse_header(tokens.read_text(encoding="utf-8"))
    return slug is None or not ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app_dir", help="existing mini app (has components.json)")
    parser.add_argument("slug", help=f"style slug: {', '.join(_styles.SLUGS)}")
    parser.add_argument("--force", action="store_true",
                        help="overwrite a hand-edited tokens file, discarding the edits")
    args = parser.parse_args(argv)

    app = Path(args.app_dir).expanduser().absolute()
    tokens = app / _mini.TOKENS_REL
    if not (app / "components.json").is_file():
        return _mini.usage_error(f"not a mini app (no components.json): {app}")
    if args.slug not in _styles.SLUGS:
        return _mini.usage_error(
            f"unknown style: {args.slug} (known: {', '.join(_styles.SLUGS)})"
        )
    if not tokens.is_file():
        return _mini.usage_error(f"missing tokens file: {tokens}")
    try:
        edited = hand_edited(tokens)
    except OSError as exc:
        return _mini.usage_error(f"cannot read {tokens}: {exc}")
    if edited and not args.force:
        return _mini.usage_error(
            f"{tokens} was edited by hand; rerunning with --force discards the edits"
        )

    steps = (
        lambda a: _mini.style_step(a, args.slug),
        lambda a: _mini.tokens_step(a),
        lambda a: _mini.build_step(a),
        lambda a: _mini.dev_step(a),
    )
    for step in steps:
        code = step(app)
        if code:
            return code

    print(f"app: {app}")
    print(f"style: {args.slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
