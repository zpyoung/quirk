#!/usr/bin/env python3
"""Compile the style sources in styles/*.json into the CSS and lists the gallery and apps use.

Usage:
    build_styles.py [--check | --check-file <css>]

Without flags: validates every source, runs the contrast gate, then writes styles/dist/<slug>.css,
gallery/src/styles/mini-tokens.css (the neutral-house app CSS), gallery/src/styles/gallery-styles.css
and gallery/src/gallery/style-list.json. With --check: no writes; exits 1 naming each output that
is stale or missing, and on any validation or contrast failure. With --check-file: runs the
contrast gate on a hand-edited app tokens file and exits 1 on a failure or a missing token.

Exits 0 on success, 1 on a validation, contrast or freshness failure, and 2 on a usage error: a
missing styles/ directory, a source whose slug is not a known style, or a bad flag.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import _mini
import _styles

SKILL_ROOT = _mini.SKILL_ROOT
REBUILD_COMMAND = "python3 skills/building-mini-apps/scripts/build_styles.py"


class _UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise ValueError(message)


def outputs(root: Path, styles: Dict[str, _styles.Style]) -> Dict[Path, str]:
    """Every generated file under `root`, mapped to the text it should contain."""
    files: Dict[Path, str] = {}
    for slug, style in styles.items():
        files[root / "styles" / "dist" / f"{slug}.css"] = _styles.render_app_css(style)
    files[root / "gallery" / "src" / "styles" / "mini-tokens.css"] = _styles.render_app_css(
        styles[_styles.DEFAULT_SLUG]
    )
    files[root / "gallery" / "src" / "styles" / "gallery-styles.css"] = _styles.render_gallery_css(styles)
    listing = [{"slug": slug, "name": style["name"]} for slug, style in styles.items()]
    files[root / "gallery" / "src" / "gallery" / "style-list.json"] = (
        json.dumps(listing, indent=2, ensure_ascii=False) + "\n"
    )
    return files


def load_all(styles_dir: Path) -> "tuple[Dict[str, _styles.Style], List[str]]":
    """Load every source; returns the valid styles and one message per problem."""
    loaded: Dict[str, _styles.Style] = {}
    problems: List[str] = []
    for path in _styles.source_paths(styles_dir):
        try:
            loaded[path.stem] = _styles.load_style(path)
        except _styles.StyleError as exc:
            problems.append(str(exc))
    for slug, style in list(loaded.items()):
        problems += [str(f) for f in _styles.contrast_failures(style)]
    ordered = {slug: loaded[slug] for slug in _styles.SLUGS if slug in loaded}
    return ordered, problems


def check_file(path: Path) -> int:
    if not path.is_file():
        return _mini.usage_error(f"not a file: {path}")
    text = path.read_text(encoding="utf-8")
    header_slug, _ = _styles.parse_header(text)
    try:
        failures = _styles.tokens_failures(text, str(path), header_slug or path.stem)
    except _styles.StyleError as exc:
        print(exc, file=sys.stderr)
        return 1
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return 1
    print(f"{path}: passes AA")
    return 0


def main(argv: Optional[List[str]] = None, skill_root: Optional[Path] = None) -> int:
    root = SKILL_ROOT if skill_root is None else Path(skill_root)
    parser = _UsageParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="no writes; exit 1 naming each stale output or failing style")
    group.add_argument("--check-file", metavar="CSS",
                       help="run the contrast gate on an app tokens file")
    try:
        args = parser.parse_args(argv)
    except ValueError as exc:
        return _mini.usage_error(str(exc))

    if args.check_file:
        return check_file(Path(args.check_file))

    styles_dir = root / "styles"
    if not styles_dir.is_dir():
        return _mini.usage_error(f"missing styles directory: {styles_dir}")
    unknown = _styles.unknown_sources(styles_dir)
    if unknown:
        names = ", ".join(p.name for p in unknown)
        return _mini.usage_error(f"unknown style source: {names} (known: {', '.join(_styles.SLUGS)})")

    styles, problems = load_all(styles_dir)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if _styles.DEFAULT_SLUG not in styles:
        return _mini.usage_error(f"missing styles/{_styles.DEFAULT_SLUG}.json")

    files = outputs(root, styles)
    if args.check:
        stale = [
            p for p, text in files.items()
            if not p.is_file() or p.read_bytes() != text.encode("utf-8")
        ]
        for path in stale:
            print(f"stale: {path.relative_to(root).as_posix()}", file=sys.stderr)
        if stale:
            print(f"run: {REBUILD_COMMAND}", file=sys.stderr)
            return 1
        print("styles are fresh")
        return 0

    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    print(f"styles built: {len(styles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
