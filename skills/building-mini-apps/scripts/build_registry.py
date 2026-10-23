#!/usr/bin/env python3
"""Assemble the local shadcn registry for building-mini-apps and keep it fresh.

Without flags: writes registry/registry.json from the base manifest plus every
gallery/src/patterns/*/registry-item.json, then runs `shadcn build` into
registry/r/. With --check: no writes and no network; exits 1 naming each item
whose built registry/r/<item>.json is missing or differs from its sources.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
GALLERY = SKILL_ROOT / "gallery"
REGISTRY = SKILL_ROOT / "registry"
BASE_MANIFEST = REGISTRY / "base.registry-item.json"
PATTERNS_DIR = GALLERY / "src" / "patterns"
SHADCN = "shadcn@4.22.1"
ITEM_SCHEMA = "https://ui.shadcn.com/schema/registry-item.json"
REGISTRY_SCHEMA = "https://ui.shadcn.com/schema/registry.json"
HOMEPAGE = "https://github.com/zpyoung/quirk/tree/main/skills/building-mini-apps"
COMPARED_KEYS = ("name", "type", "title", "description", "dependencies", "registryDependencies")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pattern_item(manifest: Path) -> dict:
    """Pattern item with `files` derived from the folder's .ts/.tsx sources."""
    folder = manifest.parent
    item = load_json(manifest)
    if item.get("name") != folder.name:
        raise ValueError(f"{manifest}: name {item.get('name')!r} must equal folder {folder.name!r}")
    sources = sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix in (".ts", ".tsx")
    )
    files = []
    for source in sources:
        rel = source.relative_to(GALLERY).as_posix()
        files.append({"path": rel, "type": "registry:file", "target": rel})
    return {"$schema": ITEM_SCHEMA, **item, "type": "registry:block", "files": files}


def collect_items() -> list[dict]:
    items = [load_json(BASE_MANIFEST)]
    if PATTERNS_DIR.is_dir():
        for manifest in sorted(PATTERNS_DIR.glob("*/registry-item.json")):
            items.append(pattern_item(manifest))
    return items


def expected_built(item: dict) -> dict:
    """What `shadcn build` should emit for `item`, read from the current sources."""
    built = {key: item[key] for key in COMPARED_KEYS if key in item}
    built["files"] = [
        {
            "path": f["path"],
            "type": f["type"],
            "target": f.get("target"),
            "content": (GALLERY / f["path"]).read_text(encoding="utf-8"),
        }
        for f in item["files"]
    ]
    return built


def actual_built(path: Path) -> dict:
    data = load_json(path)
    built = {key: data[key] for key in COMPARED_KEYS if key in data}
    built["files"] = [
        {k: f.get(k) for k in ("path", "type", "target", "content")} for f in data.get("files", [])
    ]
    return built


def stale_reason(item: dict) -> str | None:
    built_path = REGISTRY / "r" / f"{item['name']}.json"
    if not built_path.is_file():
        return f"missing {built_path.relative_to(SKILL_ROOT)}"
    try:
        expected = expected_built(item)
    except OSError as exc:
        return f"source unreadable: {exc}"
    actual = actual_built(built_path)
    if expected == actual:
        return None
    if expected["files"] != actual["files"]:
        built_by_path = {f["path"]: f for f in actual["files"]}
        differing = [
            f["path"] for f in expected["files"] if built_by_path.get(f["path"]) != f
        ]
        extra = [p for p in built_by_path if p not in {f["path"] for f in expected["files"]}]
        return "files differ: " + ", ".join(differing + extra)
    keys = [k for k in expected if expected[k] != actual.get(k)]
    return "metadata differs: " + ", ".join(keys)


def check() -> int:
    stale = []
    for item in collect_items():
        reason = stale_reason(item)
        if reason:
            stale.append((item["name"], reason))
    for name, reason in stale:
        print(f"stale: {name} ({reason})", file=sys.stderr)
    if stale:
        print("run: python3 skills/building-mini-apps/scripts/build_registry.py", file=sys.stderr)
        return 1
    print("registry is fresh")
    return 0


def build() -> int:
    items = collect_items()
    registry = {
        "$schema": REGISTRY_SCHEMA,
        "name": "mini-apps",
        "homepage": HOMEPAGE,
        "items": items,
    }
    REGISTRY.mkdir(parents=True, exist_ok=True)
    (REGISTRY / "registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    cmd = ["pnpm", "dlx", SHADCN, "build", "../registry/registry.json", "--output", "../registry/r"]
    print("+ " + " ".join(cmd) + "  (cwd gallery/)")
    return subprocess.run(cmd, cwd=GALLERY, stdin=subprocess.DEVNULL).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="no writes, no network; exit 1 naming each stale or missing built item",
    )
    args = parser.parse_args(argv)
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
