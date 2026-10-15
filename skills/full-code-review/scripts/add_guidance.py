#!/usr/bin/env python3
"""Append a timestamped review-guidance note for the current repo (sakura-tracked).

Writes to <sakura-guidance-dir>/<repo-key>.md, scaffolding the file on first use.
The store is a PERSONAL review lens keyed by repo — not the repo's own conventions
(those live in and are read from the repo itself).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HEADER = (
    "# Review guidance: {key}\n\n"
    "Personal review emphases for this repo (sakura-tracked). The repo's OWN "
    "conventions are discovered separately and win for consistency; these are "
    "additive.\n"
)


def normalize_repo_key(origin_url):
    s = origin_url.strip()
    s = re.sub(r'\.git$', '', s)
    s = re.sub(r'^\w+://', '', s)        # strip https:// or ssh://
    s = re.sub(r'^[^@/]+@', '', s)       # strip user@
    s = re.sub(r'^[^/:]+[:/]', '', s)    # strip host and first separator
    parts = [p for p in re.split(r'/', s) if p]
    return '--'.join(parts)


def resolve_repo_key(repo_key, git_root):
    if repo_key:
        return repo_key
    try:
        r = subprocess.run(["git", "-C", git_root or ".", "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return normalize_repo_key(r.stdout.strip())
    except Exception:
        pass
    return None


def add_note(guidance_dir, repo_key, note, now=None):
    os.makedirs(guidance_dir, exist_ok=True)
    path = os.path.join(guidance_dir, "%s.md" % repo_key)
    created = not os.path.exists(path)
    ts = (now or datetime.now()).isoformat(timespec="seconds")
    with open(path, "a") as fh:
        if created:
            fh.write(HEADER.format(key=repo_key))
        fh.write("\n## %s\n\n%s\n" % (ts, note))
    return path, created


def enclosing_git_root(path):
    """Git root containing `path`, or None. Used to tell the user where to commit
    so the guidance is actually tracked (the cache copy is wiped on update)."""
    try:
        r = subprocess.run(["git", "-C", os.path.dirname(path) or ".",
                            "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add sakura-tracked review guidance for a repo.")
    ap.add_argument("--note", required=True)
    ap.add_argument("--sakura-guidance-dir", required=True)
    ap.add_argument("--git-root")
    ap.add_argument("--repo-key")
    args = ap.parse_args(argv)

    key = resolve_repo_key(args.repo_key, args.git_root)
    if not key:
        print(json.dumps({"error": "could not resolve repo-key (no --repo-key and no git origin)"}))
        return 2
    path, created = add_note(args.sakura_guidance_dir, key, args.note)
    abspath = os.path.abspath(path)
    git_root = enclosing_git_root(abspath)
    out = {
        "repo_key": key, "file": abspath, "created": created, "appended": True,
        "git_root": git_root,
    }
    if git_root:
        out["commit_hint"] = (
            'git -C "%s" add "%s" && git commit -m "guidance: %s" && git push'
            % (git_root, abspath, key)
        )
    else:
        out["warning"] = ("guidance dir is not inside a git repo — it will NOT be "
                          "tracked or survive a plugin-cache refresh; point "
                          "--sakura-guidance-dir at your sakura source clone")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
