#!/usr/bin/env python3
"""Maintainer drift report: compare each upstream source in NOTICE.md with its pinned commit.

Reads the sources table in NOTICE.md and, for every row, asks the remote for HEAD. When HEAD
differs from the pin it clones into a temp dir (removed afterwards) and prints the commits and
changed files under the row's path since the pin. It never edits the skill or anything else in
the repo; bumping pins stays a manual step after the affected files are rewritten.

Exit codes: 0 every source at its pin, 1 at least one source moved, 2 parse or git failure.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

HEADER = ("source", "repo", "path", "license", "pinned")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


class NoticeError(Exception):
    """NOTICE.md has no well-formed sources table."""


class GitError(Exception):
    """A git command failed."""


@dataclass(frozen=True)
class Source:
    name: str
    repo: str
    path: str
    license: str
    pinned: str


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_notice(text: str) -> List[Source]:
    """Return the rows of the sources table; raise NoticeError if it is missing or malformed."""
    lines = text.splitlines()
    start: Optional[int] = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith("|") and tuple(c.lower() for c in _cells(line)) == HEADER:
            start = index
            break
    if start is None:
        raise NoticeError(f"no sources table with header: | {' | '.join(HEADER)} |")
    if start + 1 >= len(lines) or not SEPARATOR_RE.match(lines[start + 1].strip()):
        raise NoticeError("sources table header is not followed by a separator row")

    sources: List[Source] = []
    for line in lines[start + 2:]:
        if not line.lstrip().startswith("|"):
            break
        cells = _cells(line)
        if len(cells) != len(HEADER):
            raise NoticeError(f"expected {len(HEADER)} columns, got {len(cells)}: {line.strip()}")
        name, repo, path, license_, pinned = cells
        if not all((name, repo, path, license_)):
            raise NoticeError(f"empty cell in row: {line.strip()}")
        if not SHA_RE.match(pinned):
            raise NoticeError(f"{name}: pinned must be a full 40-char sha, got {pinned!r}")
        sources.append(Source(name, repo, path, license_, pinned.lower()))
    if not sources:
        raise NoticeError("sources table has no rows")
    return sources


def _git(args: Sequence[str], cwd: Optional[Path] = None) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise GitError(f"git {' '.join(args[:2])} failed: {detail}")
    return result.stdout


def remote_head(repo: str) -> str:
    out = _git(["ls-remote", repo, "HEAD"]).strip()
    if not out:
        raise GitError(f"{repo} has no HEAD")
    return out.split()[0].lower()


def drift_report(source: Source, head: str) -> str:
    """Clone into a temp dir and describe what changed under source.path since the pin."""
    tmp = Path(tempfile.mkdtemp(prefix="interface-design-upstream-"))
    try:
        clone = tmp / "clone"
        _git(["clone", "--quiet", "--no-checkout", "--filter=blob:none", source.repo, str(clone)])
        spec = f"{source.pinned}..{head}"
        total = _git(["rev-list", "--count", spec], clone).strip()
        log = _git(["log", "--oneline", spec, "--", source.path], clone).rstrip()
        touching = len(log.splitlines()) if log else 0
        stat = _git(["diff", "--stat", source.pinned, head, "--", source.path], clone).rstrip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    noun = "commit" if total == "1" else "commits"
    lines = [
        f"{source.name}: {total} {noun} since {source.pinned[:12]} "
        f"({touching} touching {source.path}); HEAD {head[:12]}"
    ]
    lines += [f"  {entry}" for entry in log.splitlines()] or ["  (no commits touch this path)"]
    lines += [f"  {entry}" for entry in stat.splitlines()]
    return "\n".join(lines)


def run(sources: Sequence[Source]) -> int:
    moved = False
    failed = False
    for source in sources:
        try:
            head = remote_head(source.repo)
            if head == source.pinned:
                print(f"{source.name}: no change")
                continue
            moved = True
            print(drift_report(source, head))
        except GitError as exc:
            failed = True
            print(f"{source.name}: {exc}", file=sys.stderr)
    if failed:
        return 2
    return 1 if moved else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    default_notice = Path(__file__).resolve().parent.parent / "NOTICE.md"
    parser = argparse.ArgumentParser(description="Report upstream drift against the pins in NOTICE.md.")
    parser.add_argument("--notice", type=Path, default=default_notice, help="path to NOTICE.md")
    args = parser.parse_args(argv)

    try:
        sources = parse_notice(args.notice.read_text())
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read {args.notice}: {exc}", file=sys.stderr)
        return 2
    except NoticeError as exc:
        print(f"{args.notice}: {exc}", file=sys.stderr)
        return 2
    return run(sources)


if __name__ == "__main__":
    sys.exit(main())
