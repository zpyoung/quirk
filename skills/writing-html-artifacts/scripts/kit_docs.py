#!/usr/bin/env python3
"""Generate the component kit's authoring reference and per-element example sources from its catalog.

``reference [--check]`` writes (or checks) ``references/components.md``; ``examples OUT_DIR`` writes a
``report``-template source per element. Every subcommand prints exactly one JSON object to stdout.
Exit codes: 0 success; 1 ``reference --check`` found the file stale; 2 usage error or a failure to
read the catalog or write the output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NoReturn, Optional, Sequence

# the skill directory holds htmlkit and is not on sys.path when this file is run by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from htmlkit import SKILL_DIR, kitcheck  # noqa: E402
from htmlkit.assemble import _skill_store  # noqa: E402

EXIT_OK, EXIT_STALE, EXIT_USAGE = 0, 1, 2

REFERENCE_PATH = Path("references") / "components.md"
EXAMPLE_TEMPLATE = "report"
EXAMPLE_SKIPPED = frozenset({"q-diff-note"})
_MARKUP = re.compile(r"<(/?[a-z][^<>]*)>")


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(json.dumps({"error": message}))
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def load(skill_dir: Path) -> kitcheck.Catalog:
    """Load the current kit catalog through the skill's own vendor registry."""
    return kitcheck.load_catalog(_skill_store(Path(skill_dir), None), None)


def _prose(text: str) -> str:
    """Escape table-breaking pipes and code-format any markup so Markdown does not swallow it."""
    return _MARKUP.sub(lambda m: f"`<{m.group(1)}>`", text).replace("|", "\\|")


def _fence(example: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", example)), default=0)
    return "`" * max(3, longest + 1)


def _attribute_table(element: kitcheck.Element) -> list[str]:
    if not element.attributes:
        return ["This element takes no attributes of its own.", ""]
    lines = [
        "| Name | Required | Kind | Values | Default | Description |",
        "|---|---|---|---|---|---|",
    ]
    for a in element.attributes:
        values = ", ".join(f"`{v}`" for v in a.values) if a.values else "-"
        default = f"`{a.default}`" if a.default is not None else "-"
        required = "yes" if a.required else "no"
        lines.append(f"| `{a.name}` | {required} | {a.kind} | {values} | {default} | {_prose(a.description)} |")
    lines.append("")
    return lines


def _section(element: kitcheck.Element) -> list[str]:
    lines = [f"## `{element.tag}`", "", _prose(element.use_when), ""]
    if element.parent:
        lines += [f"Must be a child of `{element.parent}`.", ""]
    lines += ["### Attributes", "", *_attribute_table(element)]
    lines += ["### Children", "", _prose(element.children), ""]
    fence = _fence(element.example)
    lines += ["### Example", "", f"{fence}html", element.example, fence, ""]
    allowed = "not allowed (interactive)" if element.interactive else "allowed"
    lines += [f"Companion option html: {allowed}", ""]
    return lines


def render_reference(catalog: kitcheck.Catalog) -> str:
    """Render ``references/components.md`` for ``catalog``; the same catalog always gives the same text."""
    version = catalog.kit_version
    lines = [
        "# Component kit reference",
        "",
        f"Generated from `vendor/kit/{version}/catalog.json` by `scripts/kit_docs.py reference`. Do not edit by hand.",
        "",
        "## How inclusion works",
        "",
        "Write any `q-*` tag in a source and the builder inlines the kit automatically; `q-chart` also inlines "
        "Chart.js. Never list `kit` in the source header's `libraries`. A tag that breaks its element's contract "
        "below fails the build's `kit` check, which names the element and the problem.",
        "",
        "## Tag index",
        "",
    ]
    for tag, element in catalog.elements.items():
        note = f" (inside `{element.parent}`)" if element.parent else ""
        lines.append(f"- [`{tag}`](#{tag}){note}")
    lines.append("")
    for element in catalog.elements.values():
        lines += _section(element)
    return "\n".join(lines).rstrip("\n") + "\n"


def _placeholder(slot: str) -> str:
    if slot == "aside":
        return '<aside aria-label="Notes">\n<p>Supporting notes for the example.</p>\n</aside>'
    return f"<p>Content for the {slot} slot.</p>"


def render_example(tag: str, example: str, required_slots: Sequence[str]) -> str:
    """Render the ``report`` source that shows ``example``, with a placeholder for every other required slot."""
    header = {"template": EXAMPLE_TEMPLATE, "title": f"{tag} example", "mode": "offline", "interactions": []}
    parts = [
        f"<!-- quirk-src {json.dumps(header)} -->",
        "<!-- slot: summary -->",
        f"<p>A page that shows the {tag} element.</p>",
        "<!-- slot: main -->",
        example.strip("\n"),
    ]
    for slot in required_slots:
        if slot != "main":
            parts += [f"<!-- slot: {slot} -->", _placeholder(slot)]
    return "\n".join(parts) + "\n"


def _required_slots(skill_dir: Path) -> list[str]:
    manifest = json.loads((Path(skill_dir) / "templates" / EXAMPLE_TEMPLATE / "template.json").read_text(encoding="utf-8"))
    slots = manifest.get("slots") if isinstance(manifest, dict) else None
    if not isinstance(slots, dict) or not all(isinstance(spec, dict) for spec in slots.values()):
        raise ValueError(f"templates/{EXAMPLE_TEMPLATE}/template.json: slots must be an object of slot objects")
    return [name for name, spec in slots.items() if spec.get("required")]


def _cmd_reference(args: argparse.Namespace, skill_dir: Path) -> int:
    target = skill_dir / REFERENCE_PATH
    text = render_reference(load(skill_dir))
    if args.check:
        try:
            current: Optional[str] = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        stale = current != text
        print(json.dumps({"stale": stale}))
        return EXIT_STALE if stale else EXIT_OK
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(json.dumps({"written": [str(target)]}))
    return EXIT_OK


def _cmd_examples(args: argparse.Namespace, skill_dir: Path) -> int:
    catalog = load(skill_dir)
    slots = _required_slots(skill_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for tag, element in catalog.elements.items():
        if tag in EXAMPLE_SKIPPED:
            continue
        path = out / f"{tag}.src.html"
        path.write_text(render_example(tag, element.example, slots), encoding="utf-8")
        written.append(str(path))
    print(json.dumps({"written": written}))
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="kit_docs.py", description="Generate the component kit's reference and examples.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    reference = sub.add_parser("reference", help="write references/components.md from the kit catalog")
    reference.add_argument("--check", action="store_true", help="write nothing; exit 1 when the file is stale")
    examples = sub.add_parser("examples", help="write a report-template source per element")
    examples.add_argument("out_dir", metavar="OUT_DIR")
    return parser


def main(argv: Optional[Sequence[str]] = None, skill_dir: Optional[Path] = None) -> int:
    args = _parser().parse_args(argv)
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    handler = _cmd_reference if args.command == "reference" else _cmd_examples
    try:
        return handler(args, skill)
    except (kitcheck.KitError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"kit_docs.py: {exc}", file=sys.stderr)
        print(json.dumps({"error": str(exc)}))
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
