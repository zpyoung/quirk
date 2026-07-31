#!/usr/bin/env python3
"""Dry-run or file a filing-requests canonical document via `gh issue create`.

Invoked directly by filename, like the other filing-requests scripts. This is the one
script that performs an irreversible outward action, so `--execute` re-checks the
upstream gates itself rather than trusting the caller already ran them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# loaded both as `python3 .../github_file.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling imports work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import canonical_schema  # noqa: E402
import markdown_render  # noqa: E402
import secret_scan  # noqa: E402
from _common import (  # noqa: E402
    SchemaVersionError,
    check_schema_version,
    read_json_arg,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or file a filing-requests canonical document via `gh issue create`.",
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    try:
        doc = read_json_arg(args.input)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        check_schema_version(doc)
    except SchemaVersionError as exc:
        print(str(exc), file=sys.stderr)
        return 8

    target = doc.get("target") if isinstance(doc, dict) else None
    kind = target.get("kind") if isinstance(target, dict) else None
    if kind != "github":
        print(f"unsupported target.kind {kind!r}; github_file.py only files to github", file=sys.stderr)
        return 6

    title = doc.get("title", "")
    # the one renderer: never reimplement formatting here, or the filed issue and the
    # written artifact become two independently-formatted copies of the same document.
    body = markdown_render.render(doc)
    gh_bin = os.environ.get("GH_BIN", "gh")
    exec_argv = [gh_bin, "issue", "create", "--repo", args.repo, "--title", title, "--body", body]

    if not args.execute:
        print(json.dumps({
            "repo": args.repo,
            "title": title,
            "body_preview": body,
            "would_execute": exec_argv,
        }, ensure_ascii=False))
        return 0

    # defense in depth: don't trust that the caller already gated on emission-readiness,
    # secrets, or headlessness -- this script is the last one before an irreversible action.
    result = canonical_schema.validate(doc, for_emission=True)
    if not result["valid"]:
        print(json.dumps(result, ensure_ascii=False))
        return 3

    findings = secret_scan.scan(doc)
    if findings:
        print(json.dumps(findings, ensure_ascii=False))
        return 1

    if doc.get("headless") is True:
        print("refusing to file a headless document: no human confirmed it", file=sys.stderr)
        return 3

    try:
        proc = subprocess.run(exec_argv, capture_output=True, text=True)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 5

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return 5

    sys.stdout.write(proc.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
