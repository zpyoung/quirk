#!/usr/bin/env python3
"""Discover review guidance for the repo under review.

Gathers the TARGET repo's own conventions (.claude/skills review skills and the
reference docs they route to, the CLAUDE.md hierarchy, .claude/rules/*.md,
AGENTS.md/CONVENTIONS.md) plus SAKURA-tracked per-repo guidance (_global.md +
<repo-key>.md). Prints JSON.
Exit 0 on all expected outcomes; missing sources yield empty lists / null.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REFERENCE_CAP = 200
INDEX_NAMES = ("index.md", "readme.md")


def normalize_repo_key(origin_url):
    s = origin_url.strip()
    s = re.sub(r'\.git$', '', s)
    s = re.sub(r'^\w+://', '', s)        # strip https:// or ssh://
    s = re.sub(r'^[^@/]+@', '', s)       # strip user@
    s = re.sub(r'^[^/:]+[:/]', '', s)    # strip host and first separator
    parts = [p for p in re.split(r'/', s) if p]
    return '--'.join(parts)


def git_origin_key(git_root):
    try:
        out = subprocess.run(
            ["git", "-C", str(git_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return normalize_repo_key(out.stdout.strip())
    except Exception:
        pass
    return None


def ancestor_claude_mds(git_root, changed_files):
    """Root CLAUDE.md plus nested CLAUDE.md in the ancestor dirs of changed
    files, all within git_root. Returns a sorted, de-duplicated list."""
    git_root = Path(git_root).resolve()
    found = []
    root_md = git_root / "CLAUDE.md"
    if root_md.is_file():
        found.append(str(root_md))
    for rel in changed_files:
        p = (git_root / rel).resolve()
        try:
            p.relative_to(git_root)
        except ValueError:
            continue  # changed path escapes the repo root; skip
        d = p.parent
        while True:
            md = d / "CLAUDE.md"
            if md.is_file():
                found.append(str(md))
            if d == git_root:
                break
            if git_root not in d.parents:
                break
            d = d.parent
    seen, out = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return sorted(out)


def skill_references(git_root):
    """Reference docs bundled with the repo's own review skills.

    A repo may keep the bulk of its review knowledge in `references/` beside each
    SKILL.md rather than inside it, in which case the SKILL.md alone is only a
    router. Returns (paths, dropped_count) as paths only — the consumer routes via
    an index before reading, so listing stays cheap. Capped so a pathological repo
    cannot flood the payload; dropped_count is reported rather than hidden.
    """
    pattern = str(Path(git_root) / ".claude" / "skills" / "*" / "references" / "**" / "*.md")
    found = sorted(glob.glob(pattern, recursive=True))
    return found[:REFERENCE_CAP], max(0, len(found) - REFERENCE_CAP)


def gather(git_root, sakura_dir, changed_files, repo_key):
    git_root = Path(git_root)
    references, references_dropped = skill_references(git_root)
    target = {
        "repo_skills": sorted(glob.glob(str(git_root / ".claude" / "skills" / "*" / "SKILL.md"))),
        "repo_skill_references": references,
        "repo_skill_reference_indexes": [f for f in references if Path(f).name.lower() in INDEX_NAMES],
        "repo_skill_references_dropped": references_dropped,
        "claude_md": ancestor_claude_mds(git_root, changed_files),
        "rules": sorted(glob.glob(str(git_root / ".claude" / "rules" / "*.md"))),
        "other": [str(git_root / n) for n in ("AGENTS.md", "CONVENTIONS.md") if (git_root / n).is_file()],
    }
    sakura_dir = Path(sakura_dir)
    g = sakura_dir / "_global.md"
    r = sakura_dir / ("%s.md" % repo_key) if repo_key else None
    sakura = {
        "global": str(g) if g.is_file() else None,
        "repo": str(r) if (r and r.is_file()) else None,
    }
    return target, sakura


def main(argv=None):
    ap = argparse.ArgumentParser(description="Discover review guidance sources.")
    ap.add_argument("--git-root", required=True)
    ap.add_argument("--sakura-guidance-dir", required=True)
    ap.add_argument("--changed-files", help="newline-delimited list of changed repo-relative paths")
    ap.add_argument("--repo-key")
    args = ap.parse_args(argv)

    repo_key = args.repo_key or git_origin_key(args.git_root)
    changed = []
    if args.changed_files and os.path.isfile(args.changed_files):
        with open(args.changed_files) as fh:
            changed = [ln.strip() for ln in fh if ln.strip()]

    target, sakura = gather(args.git_root, args.sakura_guidance_dir, changed, repo_key)
    print(json.dumps({"repo_key": repo_key, "target_repo": target, "sakura": sakura}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
