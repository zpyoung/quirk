#!/usr/bin/env python3
"""Discover, select among, and derive a field set from a repo's issue templates.

Invoked directly by filename, like the other filing-requests scripts. Three subcommands,
each independently invocable -- split apart deliberately so the "never pick silently" rule
is structural: `fields` cannot run until `select` has returned a single, settled outcome.

This script operates on *template files and candidate lists*, never on a canonical document,
so it is the one script of the six that does not call `check_schema_version`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# loaded both as `python3 .../template_resolve.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling imports work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import _yaml_mini  # noqa: E402
from _common import (  # noqa: E402
    CORE_FIELDS,
    HEADING_SYNONYMS,
    NON_WAIVABLE,
    TYPE_KEYWORDS,
    slugify,
)

TYPES = ("bug", "feature", "code-change")

# logic.md -> Choosing among templates, step 1: GitHub's chooser configuration is not a
# template and is never a candidate.
_NEVER_A_CANDIDATE = {"config.yml", "config.yaml"}

GITHUB_TEMPLATE_DIR = Path(".github") / "ISSUE_TEMPLATE"
GITLAB_TEMPLATE_DIR = Path(".gitlab") / "issue_templates"


# ---- discover ---------------------------------------------------------------


def _kind_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    if rel.parts[:2] == GITLAB_TEMPLATE_DIR.parts:
        return "gitlab-markdown"
    return "github-yaml" if path.suffix in (".yml", ".yaml") else "github-markdown"


def _candidate_paths(root: Path) -> list:
    """Every file the globs match, in a stable order, before any exclusion runs."""
    found = []
    github_dir = root / GITHUB_TEMPLATE_DIR
    for suffix in ("*.yml", "*.yaml", "*.md"):
        found.extend(sorted(github_dir.glob(suffix)))
    found.extend(sorted((root / GITLAB_TEMPLATE_DIR).glob("*.md")))
    return [p for p in found if p.is_file()]


def _split_frontmatter(text: str) -> tuple:
    """Return (frontmatter_text, body_text) for a markdown template, or ("", text)."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", text


def _as_label_list(value) -> list:
    """`labels` reaches us as a list, a comma-separated string, or nothing."""
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _markdown_headings(body: str) -> list:
    """Every `##`-or-deeper heading, in document order, with its content."""
    sections = []
    current = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            marker = stripped.lstrip("#")
            if marker.startswith(" ") or marker == "":
                title = marker.strip().rstrip("?:.!").strip()
                current = {"title": title, "lines": []}
                sections.append(current)
                continue
        if current is not None:
            current["lines"].append(line)
    return sections


def parse_template(path: Path) -> dict:
    """Parse one template file into the shape `select` and `fields` both consume.

    Raises `_yaml_mini.TemplateParseError` for a file outside the supported subset -- the
    caller excludes that one file rather than aborting the sweep over the rest of the repo.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yml", ".yaml"):
        parsed = _yaml_mini.parse_yaml(text, str(path))
        if not isinstance(parsed, dict):
            raise _yaml_mini.TemplateParseError("template is not a mapping", str(path), 1)
        body = parsed.get("body")
        return {
            "name": parsed.get("name") if isinstance(parsed.get("name"), str) else None,
            "labels": _as_label_list(parsed.get("labels")),
            "body": body if isinstance(body, list) else [],
            "sections": [],
        }

    frontmatter, markdown_body = _split_frontmatter(text)
    meta = {}
    if frontmatter.strip():
        parsed = _yaml_mini.parse_yaml(frontmatter, str(path))
        if isinstance(parsed, dict):
            meta = parsed
    return {
        "name": meta.get("name") if isinstance(meta.get("name"), str) else None,
        "labels": _as_label_list(meta.get("labels")),
        "body": [],
        "sections": _markdown_headings(markdown_body),
    }


def has_body_sections(parsed: dict, kind: str) -> bool:
    """logic.md step 1: "any file whose parsed form has no body sections" is not a candidate.

    A YAML form qualifies iff at least one `body[]` element is not static `markdown`; a
    markdown template qualifies iff it carries at least one `##`-or-deeper heading.
    """
    if kind == "github-yaml":
        return any(
            isinstance(element, dict) and element.get("type") != "markdown"
            for element in parsed["body"]
        )
    return bool(parsed["sections"])


def discover(repo_root: Path) -> tuple:
    """Return (candidates, warnings) for every template file that survives step 1."""
    candidates = []
    warnings = []
    for path in _candidate_paths(repo_root):
        if path.name in _NEVER_A_CANDIDATE:
            continue
        kind = _kind_for(path, repo_root)
        try:
            parsed = parse_template(path)
        except _yaml_mini.TemplateParseError as exc:
            # one malformed file is excluded with a warning; failing the whole session over
            # it would be a worse outcome than skipping it
            warnings.append(str(exc))
            continue
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"{path}: {exc}")
            continue
        if not has_body_sections(parsed, kind):
            continue
        candidates.append({
            "path": str(path.relative_to(repo_root)),
            "kind": kind,
            "name": parsed["name"],
            "labels": parsed["labels"],
            "filename_stem": path.stem,
        })
    return candidates, warnings


# ---- select -----------------------------------------------------------------


def _matches(haystacks: list, request_type: str) -> bool:
    keywords = TYPE_KEYWORDS[request_type]
    blob = " ".join(h.lower() for h in haystacks if isinstance(h, str))
    return any(keyword in blob for keyword in keywords)


def select(candidates: list, request_type: str) -> dict:
    """logic.md step 2/3: match on declared identity, then filename stem; never pick silently.

    Ordered, stopping at the first stage that yields exactly one template -- the declared
    identity (`name`, `labels`) is a stronger signal than a filename, so a stem-only match
    never outvotes it.
    """
    by_identity = [
        c for c in candidates
        if _matches([c.get("name")] + list(c.get("labels") or []), request_type)
    ]
    if len(by_identity) == 1:
        return {"resolution": "single", "template": by_identity[0], "ambiguous_candidates": []}

    with_stem = [
        c for c in candidates
        if _matches(
            [c.get("name"), c.get("filename_stem")] + list(c.get("labels") or []), request_type
        )
    ]
    if len(with_stem) == 1:
        return {"resolution": "single", "template": with_stem[0], "ambiguous_candidates": []}

    pool = by_identity or with_stem
    if pool:
        # several match: the caller asks the user to choose, listing each by name and path.
        # Picking here would be a silent change to what gets asked and emitted.
        return {"resolution": "ambiguous", "template": None, "ambiguous_candidates": pool}
    return {"resolution": "none", "template": None, "ambiguous_candidates": []}


# ---- fields -----------------------------------------------------------------


def _canonical_field_name(raw: str) -> str:
    slug = slugify(raw, sep="_")
    return HEADING_SYNONYMS.get(slug, slug)


def _template_field_entries(parsed: dict, kind: str) -> list:
    """The template's own sections, in its own order, with its own requiredness markings."""
    entries = []
    if kind == "github-yaml":
        for element in parsed["body"]:
            if not isinstance(element, dict) or element.get("type") == "markdown":
                continue  # static instructions are never candidate fields
            raw_id = element.get("id")
            if isinstance(raw_id, str) and raw_id.strip():
                name = _canonical_field_name(raw_id)
            else:
                attributes = element.get("attributes")
                label = attributes.get("label") if isinstance(attributes, dict) else None
                if not isinstance(label, str) or not label.strip():
                    continue
                name = _canonical_field_name(label)
            validations = element.get("validations")
            required = bool(validations.get("required")) if isinstance(validations, dict) else False
            entries.append({"name": name, "required": required, "source": "template"})
        return entries

    for section in parsed["sections"]:
        name = _canonical_field_name(section["title"])
        if not name:
            continue
        # a markdown template has no requiredness mechanism, so it contributes no markings;
        # inventing them would let a template silently subtract from the core
        entries.append({"name": name, "required": False, "source": "template"})
    return entries


def fields(request_type: str, parsed: dict | None, kind: str | None) -> list:
    """The ordered field set implementing the union-of-requiredness rule.

    1. The template's sections, in its own order, seed the list.
    2. The per-type core is additive -- any core field the template omits is appended, in
       core order, marked required. A template can add requirements; it can never subtract.
    3. The non-waivable gate is global and cannot be unset by a template of either kind.
    """
    ordered: dict = {}
    if parsed is not None and kind is not None:
        for entry in _template_field_entries(parsed, kind):
            existing = ordered.get(entry["name"])
            if existing is None:
                ordered[entry["name"]] = entry
            else:
                existing["required"] = existing["required"] or entry["required"]

    for name in CORE_FIELDS[request_type]:
        if name in ordered:
            ordered[name]["required"] = True
        else:
            ordered[name] = {"name": name, "required": True, "source": "core"}

    for name in NON_WAIVABLE.get(request_type, []):
        if name in ordered:
            ordered[name]["required"] = True

    return list(ordered.values())


# ---- CLI --------------------------------------------------------------------


def _read_json_arg(path_or_dash: str):
    if path_or_dash == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path_or_dash).read_text(encoding="utf-8"))


def _cmd_discover(args) -> int:
    root = Path(args.repo_root)
    if not root.is_dir():
        print(f"--repo-root {args.repo_root!r} is not a directory", file=sys.stderr)
        return 2
    candidates, warnings = discover(root)
    for warning in warnings:
        print(f"skipping unparsable template: {warning}", file=sys.stderr)
    # the active tier travels with the candidate list: a template that resolves on a machine
    # with PyYAML and is skipped on one without is otherwise a silent, environment-dependent
    # difference in what the skill asks the user.
    print(json.dumps(
        {"yaml_tier": _yaml_mini.YAML_TIER, "candidates": candidates}, ensure_ascii=False
    ))
    return 0


def _candidate_list(payload) -> list | None:
    """Accept `discover`'s object or a bare candidate array, so the two compose either way."""
    if isinstance(payload, dict):
        payload = payload.get("candidates")
    if not isinstance(payload, list):
        return None
    return [c for c in payload if isinstance(c, dict)]


def _cmd_select(args) -> int:
    try:
        payload = _read_json_arg(args.candidates)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    candidates = _candidate_list(payload)
    if candidates is None:
        print("--candidates must be discover's output or an array of candidates", file=sys.stderr)
        return 2
    # all three resolutions are exit 0 -- "ambiguous" and "none" are valid outcomes the
    # caller must act on, not error states
    print(json.dumps(select(candidates, args.type), ensure_ascii=False))
    return 0


def _cmd_fields(args) -> int:
    if args.no_template:
        print(json.dumps(fields(args.type, None, None), ensure_ascii=False))
        return 0

    try:
        candidate = _read_json_arg(args.template)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not isinstance(candidate, dict) or not isinstance(candidate.get("path"), str):
        print("--template must be a candidate object carrying a 'path'", file=sys.stderr)
        return 2

    path = Path(args.repo_root or ".") / candidate["path"]
    try:
        parsed = parse_template(path)
    except _yaml_mini.TemplateParseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    kind = candidate.get("kind")
    if kind not in ("github-yaml", "github-markdown", "gitlab-markdown"):
        kind = "github-yaml" if path.suffix in (".yml", ".yaml") else "github-markdown"
    print(json.dumps(fields(args.type, parsed, kind), ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover, select among, and derive a field set from a repo's issue templates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser("discover")
    p_discover.add_argument("--repo-root", required=True)
    p_discover.set_defaults(func=_cmd_discover)

    p_select = sub.add_parser("select")
    p_select.add_argument("--candidates", required=True)
    p_select.add_argument("--type", required=True, choices=TYPES)
    p_select.set_defaults(func=_cmd_select)

    p_fields = sub.add_parser("fields")
    p_fields.add_argument("--type", required=True, choices=TYPES)
    group = p_fields.add_mutually_exclusive_group(required=True)
    group.add_argument("--template")
    group.add_argument("--no-template", action="store_true")
    p_fields.add_argument("--repo-root")
    p_fields.set_defaults(func=_cmd_fields)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
