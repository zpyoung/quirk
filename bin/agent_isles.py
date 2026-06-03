#!/usr/bin/env python3
"""Stdlib-only Agent Isles bridge for Quirk artifacts.

The helper constructs deterministic Agent Isles commands without making Agent
Isles a hidden hard dependency. It prefers a repo-local binary, then PATH, then
an explicit npx fallback when allowed.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(".quirk") / "isles"
DEFAULT_NPX_PACKAGE = "agent-isles@next"


class AgentIslesUnavailable(RuntimeError):
    """Raised when no usable Agent Isles command path can be constructed."""


@dataclass(frozen=True)
class CommandPlan:
    argv: list[str]
    output: Path | None
    note: str | None = None


def _repo_local_isles(repo_root: Path) -> Path | None:
    candidate = repo_root / "node_modules" / ".bin" / ("isles.cmd" if os.name == "nt" else "isles")
    if candidate.exists() and os.access(candidate, os.X_OK):
        return candidate
    return None


def _which(name: str) -> str | None:
    found = shutil.which(name)
    return found if found else None


def detect_runner(repo_root: Path, *, no_npx: bool = False) -> tuple[list[str], str | None]:
    """Return the executable prefix and optional note for Agent Isles."""
    local = _repo_local_isles(repo_root)
    if local is not None:
        return [str(local)], None
    path_isles = _which("isles")
    if path_isles:
        return [path_isles], None
    if not no_npx:
        npx = _which("npx")
        if npx:
            return [npx, DEFAULT_NPX_PACKAGE], "npx fallback is explicit; it may download agent-isles@next when executed"
    raise AgentIslesUnavailable(
        "No Agent Isles executable found. Install/use a repo-local node_modules/.bin/isles, "
        "put isles on PATH, or rerun without --no-npx to print/use the explicit npx agent-isles@next fallback."
    )


def default_output_for(artifact: Path, repo_root: Path) -> Path:
    stem = artifact.stem or "artifact"
    return repo_root / DEFAULT_OUTPUT_DIR / f"{stem}.html"


def build_command(
    action: str,
    artifact: Path,
    *,
    repo_root: Path | None = None,
    output: Path | None = None,
    no_npx: bool = False,
    with_user_packs: bool = False,
    no_quirk_pack: bool = False,
    extra_packs: list[Path] | None = None,
    execute: bool = False,
) -> CommandPlan:
    """Build a render/preview command. Does not create files unless execute=True."""
    if action not in {"render", "preview"}:
        raise ValueError(f"unsupported action: {action}")
    repo = (repo_root or Path.cwd()).resolve()
    artifact_path = artifact if artifact.is_absolute() else (Path.cwd() / artifact)
    artifact_path = artifact_path.resolve()
    if not artifact_path.exists():
        raise FileNotFoundError(f"artifact not found: {artifact_path}")

    runner, note = detect_runner(repo, no_npx=no_npx)
    argv = [*runner, action, str(artifact_path)]

    output_path: Path | None = None
    if action == "render":
        output_path = (output if output is not None else default_output_for(artifact_path, repo)).resolve()
        argv.extend(["--output", str(output_path)])

    pack_paths: list[Path] = []
    quirk_pack = repo / "packs" / "quirk"
    if not no_quirk_pack and quirk_pack.exists():
        pack_paths.append(quirk_pack)
    pack_paths.extend(extra_packs or [])
    for pack in pack_paths:
        argv.extend(["--pack", str(pack.resolve())])
    if not with_user_packs:
        argv.append("--no-user-packs")

    if execute and output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    return CommandPlan(argv=argv, output=output_path, note=note)


def doctor(repo_root: Path, *, no_npx: bool = False) -> str:
    repo = repo_root.resolve()
    lines = ["Agent Isles bridge doctor", f"repo root: {repo}"]
    local = _repo_local_isles(repo)
    lines.append(f"repo-local isles: {local if local else 'not found'}")
    path_isles = _which("isles")
    lines.append(f"PATH isles: {path_isles if path_isles else 'not found'}")
    npx = _which("npx")
    lines.append(f"npx: {npx if npx else 'not found'}")
    pack = repo / "packs" / "quirk"
    lines.append(f"Quirk pack: {pack if pack.exists() else 'not found'}")
    lines.append(f"default output: {repo / DEFAULT_OUTPUT_DIR}/")
    try:
        runner, note = detect_runner(repo, no_npx=no_npx)
        lines.append("recommended runner: " + " ".join(shlex.quote(part) for part in runner))
        if note:
            lines.append("note: " + note)
    except AgentIslesUnavailable as exc:
        lines.append("recommended runner: unavailable")
        lines.append("reason: " + str(exc))
    lines.append("No packages were installed and no files were written.")
    return "\n".join(lines) + "\n"


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root; defaults to cwd.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quirk Agent Isles bridge helper.")
    _add_common_options(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_p = sub.add_parser("doctor", help="Report detected Agent Isles command paths.")
    _add_common_options(doctor_p)
    doctor_p.add_argument("--no-npx", action="store_true", help="Do not consider npx fallback.")

    for name in ("render", "preview", "command"):
        p = sub.add_parser(name, help=("Print command" if name == "command" else f"Build and run Agent Isles {name}."))
        _add_common_options(p)
        p.add_argument("artifact", type=Path)
        p.add_argument("--output", type=Path, help="Render output path; render only.")
        p.add_argument("--no-npx", action="store_true", help="Disable explicit npx fallback.")
        p.add_argument("--with-user-packs", action="store_true", help="Allow Agent Isles user packs.")
        p.add_argument("--no-quirk-pack", action="store_true", help="Do not add packs/quirk automatically.")
        p.add_argument("--pack", action="append", type=Path, default=[], help="Additional local trusted pack path.")
        if name in {"render", "preview"}:
            p.add_argument("--print-command", action="store_true", help="Print the command instead of executing it.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.command == "doctor":
        print(doctor(repo_root, no_npx=args.no_npx), end="")
        return 0

    action = "render" if args.command == "command" else args.command
    execute = args.command in {"render", "preview"} and not getattr(args, "print_command", False)
    try:
        plan = build_command(
            action,
            args.artifact,
            repo_root=repo_root,
            output=args.output,
            no_npx=args.no_npx,
            with_user_packs=args.with_user_packs,
            no_quirk_pack=args.no_quirk_pack,
            extra_packs=args.pack,
            execute=execute,
        )
    except (AgentIslesUnavailable, FileNotFoundError, ValueError) as exc:
        print(f"agent_isles.py: {exc}", file=sys.stderr)
        return 2

    quoted = " ".join(shlex.quote(part) for part in plan.argv)
    if args.command == "command" or getattr(args, "print_command", False):
        print(quoted)
        if plan.note:
            print(f"# {plan.note}")
        return 0

    if plan.note:
        print(plan.note, file=sys.stderr)
    completed = subprocess.run(plan.argv)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
