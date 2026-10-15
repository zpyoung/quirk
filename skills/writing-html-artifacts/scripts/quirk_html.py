#!/usr/bin/env python3
"""Command line for the writing-html-artifacts skill: build, check, verify and describe pages.

Every subcommand prints exactly one JSON object to stdout and sends diagnostics to stderr.
Exit codes: 0 success; 1 the build finished but a static or verify check failed; 2 usage
error, unknown or invalid template, malformed source or data, or an output that cannot be
written; 3 tier 2 is unavailable (``build-app`` only: Node or pnpm missing, install or build
failed), reported as ``{"error": "tier2-unavailable", "reason": ..., "detail": ...}``.
Any other failure that is not a failed check is reported as ``{"error": ...}``. Subcommands are registered in
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

from htmlkit import SKILL_DIR, app, assemble, create, manifest, resolve, verify_runner  # noqa: E402
from htmlkit.layouts import DEFAULT_LAYOUT, LAYOUTS  # noqa: E402

EXIT_OK, EXIT_CHECK_FAILED, EXIT_USAGE, EXIT_TIER2_UNAVAILABLE = 0, 1, 2, 3


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


def _cmd_templates_new(args: argparse.Namespace) -> int:
    source = Path(args.source) if args.source else None
    if source is not None:
        problem = _require_file(source)
        if problem:
            return _fail(problem)
    result = create.create_template(
        args.name,
        level=args.level,
        base=args.base,
        source=source,
        project_dir=_project_dir(args),
        user_dir=resolve.default_user_dir(),
    )
    _emit(result)
    return EXIT_OK


def _cmd_templates_verify(args: argparse.Namespace) -> int:
    result = create.verify_template(
        args.name, project_dir=_project_dir(args), user_dir=resolve.default_user_dir()
    )
    _emit(result)
    return EXIT_OK if result["passed"] else EXIT_CHECK_FAILED


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


def _cmd_build_app(args: argparse.Namespace) -> int:
    try:
        result = app.build_app(
            args.slug,
            title=args.title,
            mode=args.mode,
            signal=args.signal,
            layout=args.layout,
            template_name=args.template,
            upgrade=args.upgrade,
            project_dir=_project_dir(args),
            user_dir=resolve.default_user_dir(),
        )
    except app.AppUnavailable as exc:
        print(f"tier 2 unavailable ({exc.reason}): {exc.detail}", file=sys.stderr)
        _emit({"error": "tier2-unavailable", "reason": exc.reason, "detail": exc.detail})
        return EXIT_TIER2_UNAVAILABLE
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
    result = verify_runner.run_verify(path, Path(args.out_dir) if args.out_dir else None, mode, no_js=args.no_js)
    _emit(result)
    return EXIT_CHECK_FAILED if result.get("status") == "failed" else EXIT_OK


def _cmd_note(args: argparse.Namespace) -> int:
    path = Path(args.file)
    problem = _require_file(path)
    if problem:
        return _fail(problem)
    try:
        note = assemble.delivery_note(
            path,
            project_dir=_project_dir(args),
            user_dir=resolve.default_user_dir(),
            verify_dir=Path(args.verify_dir) if args.verify_dir else None,
        )
    except assemble.BuildError as exc:
        return _fail(str(exc))
    _emit(note)
    return EXIT_OK


def _project_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-dir", help="project root (default: git toplevel of the current directory)")


def _configure_templates(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("templates", help="list, validate, create and verify templates")
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


def _configure_templates_new(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("new", help="create a custom template from a base, a built artifact or any HTML file")
    parser.add_argument("name", help="template name, [a-z0-9-]{1,40}")
    parser.add_argument("--level", required=True, choices=("project", "user"), help="where the template lives")
    parser.add_argument("--base", help="template to copy (default: report); not allowed with --from")
    parser.add_argument("--from", dest="source", metavar="ARTIFACT.html", help="start from a built artifact or any HTML file")
    _project_option(parser)
    parser.set_defaults(func=_cmd_templates_new)


def _configure_templates_verify(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("verify", help="build and check a custom template's example, then write verified.json")
    parser.add_argument("name", help="custom template name (project level first, then user level)")
    _project_option(parser)
    parser.set_defaults(func=_cmd_templates_verify)


def _configure_build(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("build", help="build a tier-1 source file into one HTML file")
    parser.add_argument("source", help="SRC.src.html")
    parser.add_argument("--out", help="output file (default: <project>/.quirk/html/<slug>.html)")
    parser.add_argument("--upgrade", action="store_true", help="use current library versions, not the recorded ones")
    _project_option(parser)
    parser.set_defaults(func=_cmd_build)


def _configure_build_app(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("build-app", help="build a tier-2 React app project into one HTML file")
    parser.add_argument("slug", help="app name; the source folder is <project>/.quirk/html/<slug>/")
    parser.add_argument("--title", help="page title (required on the first build, then saved in quirk-app.json)")
    parser.add_argument("--mode", choices=app.APP_MODES, help="offline or connected (default: the saved value, else offline)")
    parser.add_argument("--signal", help="why this needs tier 2, recorded in the header and quirk-app.json")
    parser.add_argument(
        "--layout",
        help=f"page shape, one of {', '.join(LAYOUTS)} (default: the saved value, else {DEFAULT_LAYOUT})",
    )
    parser.add_argument("--template", help="tier-2 template name (default: the saved value, else app)")
    parser.add_argument("--upgrade", action="store_true", help="move the kit and Chart.js to the current version, not the recorded one; npm versions stay pinned by the lockfile")
    _project_option(parser)
    parser.set_defaults(func=_cmd_build_app)


def _configure_check(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("check", help="run the static checks on a built file")
    parser.add_argument("file")
    _project_option(parser)
    parser.set_defaults(func=_cmd_check)


def _configure_verify(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("verify", help="verify a built file in a real browser")
    parser.add_argument("file")
    parser.add_argument(
        "--out-dir",
        help="where the report and screenshots go (default: <file stem>.verify/, or <file stem>.verify-nojs/ with --no-js)",
    )
    parser.add_argument(
        "--no-js", action="store_true", help="load the page with JavaScript disabled and check the un-upgraded fallback"
    )
    parser.set_defaults(func=_cmd_verify)


def _configure_note(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("note", help="render the delivery note for a built file")
    parser.add_argument("file")
    parser.add_argument("--verify-dir", help="where verify wrote its report (default: <file stem>.verify/)")
    _project_option(parser)
    parser.set_defaults(func=_cmd_note)


Configure = Callable[[argparse._SubParsersAction], None]
TEMPLATE_COMMANDS: dict[str, Configure] = {
    "list": _configure_templates_list,
    "validate": _configure_templates_validate,
    "new": _configure_templates_new,
    "verify": _configure_templates_verify,
}
COMMANDS: dict[str, Configure] = {
    "templates": _configure_templates,
    "build": _configure_build,
    "build-app": _configure_build_app,
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
    try:
        return args.func(args)
    except assemble.BuildError as exc:
        return _fail(str(exc))
    except RecursionError:
        return _fail("input is nested too deeply to process")
    except (OSError, UnicodeError) as exc:
        return _fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
