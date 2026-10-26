#!/usr/bin/env python3
"""Studio bookkeeping for the making-videos skill: studio dirs, projects, versions and brand kits.

Every subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 ok; 1 the operation failed (the JSON has an ``error`` key); 2 usage error.
A version folder is created empty and never deleted, renamed or replaced.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import NoReturn, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_USAGE,
    PROVIDER_KEY_ENV,
    emit,
    project_dir,
    studio_root,
)

MAX_LENGTH_S = 180
NARRATION_THRESHOLD_S = 20
DEFAULT_LENGTH_S = 30
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
PRODUCT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
VERSION_RE = re.compile(r"^v(\d+)$")
PROJECT_SUBDIRS = ("assets", "kit")
BRAND_REQUIRED = ("product", "colors", "fonts", "voice")


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    emit({"error": message}, EXIT_FAILED)


def _read_json_object(path: Path, what: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"{what} not found: {path}")
    except (OSError, UnicodeError) as exc:
        _fail(f"cannot read {what} {path}: {exc}")
    except json.JSONDecodeError as exc:
        _fail(f"{what} {path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        _fail(f"{what} {path} must be a JSON object")
    return data


def _brand_path(product: str) -> Path:
    if not PRODUCT_RE.match(product):
        _fail(f"invalid --product {product!r}: use letters, digits, '.', '_' or '-'")
    return studio_root() / "brands" / product / "brand.json"


def _cmd_init(args: argparse.Namespace) -> int:
    root = studio_root()
    created = []
    for path in (root, root / "videos", root / "brands"):
        if not path.is_dir():
            path.mkdir(parents=True)
            created.append(str(path))
    emit({"studio": str(root), "created": created})


def _build_brief(args: argparse.Namespace, today: str) -> dict:
    given = _read_json_object(Path(args.brief_json), "brief") if args.brief_json else {}
    length_s = given.get("length_s", DEFAULT_LENGTH_S)
    if isinstance(length_s, bool) or not isinstance(length_s, (int, float)) or length_s <= 0:
        _fail("length_s must be a positive number of seconds")
    if length_s > MAX_LENGTH_S:
        _fail(f"length_s {length_s} is over the {MAX_LENGTH_S} second (3-minute) cap")
    cloud_allow = given.get("cloud_allow", [])
    if not isinstance(cloud_allow, list):
        _fail("cloud_allow must be a list of provider names")
    for provider in cloud_allow:
        if provider not in PROVIDER_KEY_ENV:
            known = ", ".join(sorted(PROVIDER_KEY_ENV))
            _fail(f"unknown cloud provider {provider!r} in cloud_allow (known: {known})")
    music = given.get("music") or {}
    return {
        "slug": args.slug,
        "product": args.product,
        "title": given.get("title", args.slug),
        "length_s": length_s,
        "aspects": given.get("aspects", ["16:9"]),
        "narration": given.get("narration", length_s > NARRATION_THRESHOLD_S),
        "cloud_allow": cloud_allow,
        "music": {"source": music.get("source", "none"), "path": music.get("path")},
        "created": today,
    }


def _cmd_project_new(args: argparse.Namespace) -> int:
    if not SLUG_RE.match(args.slug):
        _fail(f"invalid --slug {args.slug!r}: use lowercase letters, digits and '-' only")
    today = datetime.date.today().isoformat()
    brief = _build_brief(args, today)
    project = project_dir(f"{today}-{args.slug}")
    if project.exists():
        _fail(f"project folder already exists: {project}")
    project.mkdir(parents=True)
    subdirs = [project / name for name in PROJECT_SUBDIRS]
    for subdir in subdirs:
        subdir.mkdir()
    brief_path = project / "brief.json"
    brief_path.write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")
    emit({"project": str(project), "brief": str(brief_path), "created": [str(d) for d in subdirs]})


def _cmd_version_new(args: argparse.Namespace) -> int:
    project = Path(args.project)
    if not project.is_dir():
        _fail(f"project folder not found: {project}")
    matches = (VERSION_RE.match(p.name) for p in project.iterdir())
    numbers = [int(m.group(1)) for m in matches if m]
    version = f"v{max(numbers, default=0) + 1}"
    path = project / version
    path.mkdir()
    emit({"version": version, "path": str(path)})


def _cmd_brand_show(args: argparse.Namespace) -> int:
    path = _brand_path(args.product)
    brand = _read_json_object(path, "brand") if path.is_file() else None
    emit({"brand": brand, "path": str(path)})


def _cmd_brand_save(args: argparse.Namespace) -> int:
    path = _brand_path(args.product)
    brand = _read_json_object(Path(args.file), "brand file")
    missing = [key for key in BRAND_REQUIRED if key not in brand]
    if missing:
        _fail(f"brand file is missing required key(s): {', '.join(missing)}")
    if brand["product"] != args.product:
        _fail(f"brand product {brand['product']!r} does not match --product {args.product!r}")
    brand["confirmed"] = bool(args.confirm)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brand, indent=2) + "\n", encoding="utf-8")
    emit({"path": str(path), "confirmed": brand["confirmed"]})


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="studio.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    init = sub.add_parser("init", help="create the studio directories")
    init.set_defaults(func=_cmd_init)

    project = sub.add_parser("project", help="project folders")
    project_sub = project.add_subparsers(dest="action", required=True, parser_class=_Parser)
    new = project_sub.add_parser("new", help="create <YYYY-MM-DD>-<slug> with a brief.json and assets/ and kit/")
    new.add_argument("--slug", required=True)
    new.add_argument("--product", required=True)
    new.add_argument("--brief-json", help="JSON file whose fields override the brief defaults")
    new.set_defaults(func=_cmd_project_new)

    version = sub.add_parser("version", help="render version folders")
    version_sub = version.add_subparsers(dest="action", required=True, parser_class=_Parser)
    vnew = version_sub.add_parser("new", help="create the next empty vN folder")
    vnew.add_argument("--project", required=True, help="project directory")
    vnew.set_defaults(func=_cmd_version_new)

    brand = sub.add_parser("brand", help="brand kits")
    brand_sub = brand.add_subparsers(dest="action", required=True, parser_class=_Parser)
    show = brand_sub.add_parser("show", help="print a product's brand.json or null")
    show.add_argument("--product", required=True)
    show.set_defaults(func=_cmd_brand_show)
    save = brand_sub.add_parser("save", help="validate and store a brand.json")
    save.add_argument("--product", required=True)
    save.add_argument("--file", required=True, help="brand JSON to store")
    save.add_argument("--confirm", action="store_true", help="mark the brand confirmed")
    save.set_defaults(func=_cmd_brand_save)
    return parser


def main(argv: Optional["list[str]"] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, UnicodeError) as exc:
        _fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
