#!/usr/bin/env python3
"""Cut a quirk release for one merged PR: stamp a CalVer version and prepend a CHANGELOG entry.

Run by .github/workflows/release.yml. Reads the merged PR from the GitHub event
JSON at $GITHUB_EVENT_PATH, writes the four release files in --root, and prints
the new version. Committing and pushing are left to the caller.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

PYPROJECT = "pyproject.toml"
PLUGIN_JSON = ".claude-plugin/plugin.json"
MARKETPLACE_JSON = ".claude-plugin/marketplace.json"
CHANGELOG = "CHANGELOG.md"

_PYPROJECT_VERSION = re.compile(r'^version = "([^"]+)"', re.M)
_JSON_VERSION = re.compile(r'"version": "([^"]+)"')


class ReleaseError(Exception):
    """A release file is missing the version field it must contain exactly once."""


def today() -> date:
    return date.today()


def next_version(current: str, today: date) -> str:
    """Return the unpadded YYYY.M.D version for today, adding a micro on same-day re-releases."""
    cal = f"{today.year}.{today.month}.{today.day}"
    parts = current.split(".")
    if parts[:3] != cal.split("."):
        return cal
    micro = int(parts[3]) + 1 if len(parts) > 3 else 1
    return f"{cal}.{micro}"


def read_version(root: Path) -> str:
    """Return the current version from pyproject.toml, the same-day source of truth."""
    match = _PYPROJECT_VERSION.search((root / PYPROJECT).read_text())
    if not match:
        raise ReleaseError(f"{PYPROJECT}: no version line")
    return match.group(1)


def _replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text()
    if len(pattern.findall(text)) != 1:
        raise ReleaseError(f"{path.name}: expected exactly one version field")
    path.write_text(pattern.sub(replacement, text))


def stamp(root: Path, version: str) -> None:
    """Write version into pyproject.toml, plugin.json and marketplace.json, leaving all else untouched."""
    _replace_once(root / PYPROJECT, _PYPROJECT_VERSION, f'version = "{version}"')
    _replace_once(root / PLUGIN_JSON, _JSON_VERSION, f'"version": "{version}"')
    _replace_once(root / MARKETPLACE_JSON, _JSON_VERSION, f'"version": "{version}"')


def _changelog_section(body: str) -> str:
    lines = body.replace("\r\n", "\n").split("\n")
    collected: list[str] = []
    inside = False
    for line in lines:
        if re.match(r"^##\s", line):
            if inside:
                break
            inside = line[2:].strip().lower() == "changelog"
            continue
        if inside:
            collected.append(line)
    return "\n".join(collected).strip()


def changelog_entry(version: str, pr: dict) -> str:
    """Build a CHANGELOG section from the PR's '## Changelog' body section, else its title."""
    items = _changelog_section(pr.get("body") or "") or f"- {pr['title'].strip()} (#{pr['number']})"
    labels = {label["name"] for label in pr.get("labels") or []}
    heading = "### ⚠️ BREAKING" if "breaking" in labels else "### Changes"
    return f"## {version}\n\n{heading}\n{items}\n"


def prepend_changelog(path: Path, entry: str) -> None:
    """Insert entry above the newest release, below the file's header paragraph."""
    text = path.read_text()
    match = re.search(r"^## ", text, re.M)
    cut = match.start() if match else len(text)
    path.write_text(f"{text[:cut]}{entry}\n{text[cut:]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is not set", file=sys.stderr)
        return 2
    pr = json.loads(Path(event_path).read_text())["pull_request"]

    version = next_version(read_version(args.root), today())
    stamp(args.root, version)
    prepend_changelog(args.root / CHANGELOG, changelog_entry(version, pr))
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
