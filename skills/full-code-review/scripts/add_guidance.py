#!/usr/bin/env python3
"""Append a timestamped review lesson to REVIEW.md, the project pack, or the user pack.

Targets:
  review-md     <git-root>/REVIEW.md (created with empty front matter if absent)
  project-pack  <git-root>/.quirk/review/guidance/lessons.md
  user-pack     ${XDG_CONFIG_HOME:-~/.config}/quirk/review/guidance/lessons.md

Prints {"path", "commit_hint"} and never commits; exit 2 with {"error"} on bad input.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

TARGETS = ("review-md", "project-pack", "user-pack")
LESSONS_HEADER = "# Review lessons\n\nReview emphases captured with `--add-guidance`.\n"


def _git_toplevel(path):
    try:
        r = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return None


def target_path(target, git_root):
    """Return the file a lesson for `target` is appended to."""
    if target == "review-md":
        return os.path.join(git_root, "REVIEW.md")
    if target == "project-pack":
        return os.path.join(git_root, ".quirk", "review", "guidance", "lessons.md")
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(config, "quirk", "review", "guidance", "lessons.md")


def add_note(path, note, scaffold, now=None):
    """Append `note` under a timestamp heading, writing `scaffold` first if the file is new."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    created = not os.path.exists(path)
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as fh:
        if created:
            fh.write(scaffold)
        fh.write("\n## %s\n\n%s\n" % (stamp, note.strip()))
    return created


def _error(message):
    print(json.dumps({"error": message}))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capture a review lesson for later reviews.")
    ap.add_argument("--note", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--git-root", default=".")
    args = ap.parse_args(argv)

    if args.target not in TARGETS:
        return _error("--target must be one of %s" % ", ".join(TARGETS))
    if not args.note.strip():
        return _error("--note must not be empty")
    git_root = None
    if args.target in ("review-md", "project-pack"):
        git_root = _git_toplevel(args.git_root) if os.path.isdir(args.git_root) else None
        if not git_root:
            return _error("--git-root is not a git work tree: %s" % args.git_root)
    path = target_path(args.target, git_root)
    scaffold = "---\n---\n" if args.target == "review-md" else LESSONS_HEADER
    add_note(path, args.note, scaffold)
    enclosing = _git_toplevel(os.path.dirname(path))
    commit_hint = ('git -C "%s" add "%s" && git commit -m "review: add guidance"' % (enclosing, path)
                   if enclosing else None)
    print(json.dumps({"path": path, "commit_hint": commit_hint}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
