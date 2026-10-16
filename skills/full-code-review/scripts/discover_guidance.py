#!/usr/bin/env python3
"""Discover review guidance for the repo under review.

Gathers the TARGET repo's own conventions (.claude/skills review skills and the
reference docs they route to, the CLAUDE.md hierarchy, .claude/rules/*.md,
AGENTS.md/CONVENTIONS.md). Pack guidance is resolved separately by resolve_policy.py.
Paths whose real location is outside the git root (symlink escapes) are never returned.
With --exclude-changed, guidance files that the change itself touches are withheld and
listed under target_repo.changed_guidance, so a reviewer-seat run does not take its
conventions from the code under review.
Prints JSON.
Exit 0 on all expected outcomes; missing sources yield empty lists / null. Exit 2 when
--exclude-changed is set but the changed-files list is missing or unreadable, because
withholding nothing would let the change under review supply its own guidance.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

REFERENCE_CAP = 200
INDEX_NAMES = ("index.md", "readme.md")
GUIDANCE_LISTS = ("repo_skills", "repo_skill_references", "repo_skill_reference_indexes",
                  "claude_md", "rules", "other")


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
            continue
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


def _inside(root_real, path):
    return Path(path).resolve().is_relative_to(root_real)


def _repo_relative(root, path):
    return Path(path).relative_to(root).as_posix()


def gather(git_root, changed_files, exclude_changed=False):
    """Collect the repo's own guidance files, all confined to `git_root`.

    Any path that resolves outside the root is dropped. With `exclude_changed`, files whose
    repo-relative path is in `changed_files` are removed from every list and returned under
    `changed_guidance` instead.
    """
    git_root = Path(git_root).resolve()
    references, references_dropped = skill_references(git_root)
    found = {
        "repo_skills": sorted(glob.glob(str(git_root / ".claude" / "skills" / "*" / "SKILL.md"))),
        "repo_skill_references": references,
        "repo_skill_reference_indexes": [f for f in references if Path(f).name.lower() in INDEX_NAMES],
        "repo_skill_references_dropped": references_dropped,
        "claude_md": ancestor_claude_mds(git_root, changed_files),
        "rules": sorted(glob.glob(str(git_root / ".claude" / "rules" / "*.md"))),
        "other": [str(git_root / n) for n in ("AGENTS.md", "CONVENTIONS.md") if (git_root / n).is_file()],
    }
    changed = {Path(f).as_posix() for f in changed_files}
    changed_guidance = set()
    for key in GUIDANCE_LISTS:
        kept = []
        for path in found[key]:
            if not _inside(git_root, path):
                continue
            if exclude_changed and _repo_relative(git_root, path) in changed:
                changed_guidance.add(_repo_relative(git_root, path))
                continue
            kept.append(path)
        found[key] = kept
    found["changed_guidance"] = sorted(changed_guidance)
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Discover the reviewed repo's own convention files.")
    ap.add_argument("--git-root", required=True)
    ap.add_argument("--changed-files", help="newline-delimited list of changed repo-relative paths")
    ap.add_argument("--exclude-changed", action="store_true",
                    help="withhold guidance files listed in --changed-files (reviewer seat)")
    args = ap.parse_args(argv)

    changed = []
    if args.changed_files:
        try:
            with open(args.changed_files, encoding="utf-8") as fh:
                changed = [ln.strip() for ln in fh if ln.strip()]
        except OSError as exc:
            if args.exclude_changed:
                print(json.dumps({"error": "cannot read --changed-files: %s" % exc}))
                return 2
    elif args.exclude_changed:
        print(json.dumps({"error": "--exclude-changed requires --changed-files"}))
        return 2

    target = gather(args.git_root, changed, exclude_changed=args.exclude_changed)
    print(json.dumps({"target_repo": target}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
