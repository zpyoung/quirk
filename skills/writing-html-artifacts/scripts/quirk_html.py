#!/usr/bin/env python3
"""Command line for the writing-html-artifacts skill: build, check, verify and describe pages.

Every subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 success; 1 the build finished but a static or verify check failed; 2 usage
error, unknown or invalid template, or malformed source. Subcommands are registered in
``COMMANDS`` so a new one is a ``configure`` function, a handler and one table entry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, NoReturn, Optional

# the skill directory holds htmlkit and is not on sys.path when this file is run by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from htmlkit import SKILL_DIR, assemble, manifest, resolve, verify_runner  # noqa: E402

EXIT_OK, EXIT_CHECK_FAILED, EXIT_USAGE = 0, 1, 2


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        _emit({"error": message})
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    _emit({"error": message})
    return EXIT_USAGE


def _project_dir(args: argparse.Namespace) -> Path:
    given = getattr(args, "project_dir", None)
    return Path(given) if given else resolve.default_project_dir()


def _require_file(path: Path) -> Optional[str]:
    return None if path.is_file() else f"{path} is not a file"


def _cmd_templates_list(args: argparse.Namespace) -> int:
    roots = resolve.template_roots(SKILL_DIR, _project_dir(args), resolve.default_user_dir())
    templates, warnings = resolve.list_templates(roots, skill_dir=SKILL_DIR)
    _emit(
        {
            "templates": [
                {
                    "name": t.name,
                    "level": t.level,
                    "tier": t.tier,
                    "description": t.description,
                    "path": str(t.dir),
                }
                for t in templates
            ],
            "warnings": warnings,
        }
    )
    return EXIT_OK


def _cmd_templates_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_dir():
        errors = [f"{path} is not a directory"]
    else:
        errors = manifest.validate_template(path, require_verified=False, skill_dir=SKILL_DIR)
    _emit({"valid": not errors, "errors": errors})
    return EXIT_OK if not errors else EXIT_USAGE


def _cmd_build(args: argparse.Namespace) -> int:
    source = Path(args.source)
    problem = _require_file(source)
    if problem:
        return _fail(problem)
    try:
        result = assemble.build_tier1(
            source,
            out=Path(args.out) if args.out else None,
            upgrade=args.upgrade,
            project_dir=_project_dir(args),
            user_dir=resolve.default_user_dir(),
        )
    except assemble.BuildError as exc:
        return _fail(str(exc))
    _emit(result)
    return EXIT_OK if result["checks"]["passed"] else EXIT_CHECK_FAILED


def _cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.file)
    problem = _require_file(path)
    if problem:
        return _fail(problem)
    try:
        result = assemble.check_artifact(
            path, project_dir=_project_dir(args), user_dir=resolve.default_user_dir()
        )
    except assemble.BuildError as exc:
        return _fail(str(exc))
    _emit(result)
    return EXIT_OK if result["passed"] else EXIT_CHECK_FAILED


def _cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.file)
    problem = _require_file(path)
    if problem:
        return _fail(problem)
    try:
        meta = assemble.read_artifact_header(path)
    except assemble.BuildError:
        meta = None
    mode = "connected" if meta and meta.get("mode") == "connected" else "offline"
    result = verify_runner.run_verify(path, Path(args.out_dir) if args.out_dir else None, mode)
    _emit(result)
    return EXIT_CHECK_FAILED if result.get("status") == "failed" else EXIT_OK


def _cmd_note(args: argparse.Namespace) -> int:
    path = Path(args.file)
    problem = _require_file(path)
    if problem:
        return _fail(problem)
    try:
        note = assemble.delivery_note(
            path, project_dir=_project_dir(args), user_dir=resolve.default_user_dir()
        )
    except assemble.BuildError as exc:
        return _fail(str(exc))
    _emit(note)
    return EXIT_OK


def _project_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-dir", help="project root (default: git toplevel of the current directory)")


def _configure_templates(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("templates", help="list and validate templates")
    nested = parser.add_subparsers(dest="templates_command", required=True, parser_class=_Parser)
    for configure in TEMPLATE_COMMANDS.values():
        configure(nested)


def _configure_templates_list(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("list", help="list templates that resolve and the ones skipped")
    _project_option(parser)
    parser.set_defaults(func=_cmd_templates_list)


def _configure_templates_validate(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("validate", help="check a template directory's manifest and skeleton")
    parser.add_argument("path", help="template directory")
    parser.set_defaults(func=_cmd_templates_validate)


def _configure_build(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("build", help="build a tier-1 source file into one HTML file")
    parser.add_argument("source", help="SRC.src.html")
    parser.add_argument("--out", help="output file (default: <project>/.quirk/html/<slug>.html)")
    parser.add_argument("--upgrade", action="store_true", help="use current library versions, not the recorded ones")
    _project_option(parser)
    parser.set_defaults(func=_cmd_build)


def _configure_check(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("check", help="run the static checks on a built file")
    parser.add_argument("file")
    _project_option(parser)
    parser.set_defaults(func=_cmd_check)


def _configure_verify(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("verify", help="verify a built file in a real browser")
    parser.add_argument("file")
    parser.add_argument("--out-dir", help="where the report and screenshots go (default: <file stem>.verify/)")
    parser.set_defaults(func=_cmd_verify)


def _configure_note(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("note", help="render the delivery note for a built file")
    parser.add_argument("file")
    _project_option(parser)
    parser.set_defaults(func=_cmd_note)


Configure = Callable[[argparse._SubParsersAction], None]
TEMPLATE_COMMANDS: dict[str, Configure] = {
    "list": _configure_templates_list,
    "validate": _configure_templates_validate,
}
COMMANDS: dict[str, Configure] = {
    "templates": _configure_templates,
    "build": _configure_build,
    "check": _configure_check,
    "verify": _configure_verify,
    "note": _configure_note,
}


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="quirk_html.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    for configure in COMMANDS.values():
        configure(sub)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
