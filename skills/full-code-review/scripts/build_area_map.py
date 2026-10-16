#!/usr/bin/env python3
"""Partition changed files into bounded review areas with concrete boundary checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

from jsonio import load_object, write_json
from prepare_diff import _path_from_diff_git, _strip_ab


_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)\b")
_FROM = re.compile(r"^\s*from\s+(\.*[\w.]+)\s+import\s+(.+)$")
_SHARED_MARKERS = ("quirk-review handoff", "triage decisions")


def _validate_files(changed_files: list[str]) -> list[str]:
    if not isinstance(changed_files, list):
        raise ValueError("changed_files must be a list of repo-relative paths")
    for name in changed_files:
        if (not isinstance(name, str) or not name or "\x00" in name
                or PurePosixPath(name).is_absolute()
                or any(part in (".", "..") for part in name.split("/"))):
            raise ValueError("changed_files must contain only repo-relative paths")
    return list(dict.fromkeys(changed_files))


def _root(source_root: str | None) -> Path | None:
    if source_root is None:
        return None
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise ValueError("source root is not a readable directory: %s" % source_root)
    return root


def _diff_sections(diff_text: str) -> dict[str, tuple[str, int]]:
    sections: dict[str, tuple[str, int]] = {}
    current = None
    content: list[str] = []
    line_count = 0
    in_hunk = False

    def flush() -> None:
        if current is not None:
            previous, previous_count = sections.get(current, ("", 0))
            sections[current] = (previous + "\n".join(content) + "\n", previous_count + line_count)

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            flush()
            current = _path_from_diff_git(line)
            content, line_count, in_hunk = [], 0, False
        elif line.startswith("+++ ") and not in_hunk:
            name = _strip_ab(line[4:])
            if name and name != "/dev/null":
                if current is None:
                    content, line_count = [], 0
                current = name
        elif line.startswith("@@"):
            in_hunk = current is not None
        elif in_hunk and line.startswith(("+", "-", " ")):
            line_count += 1
            if line.startswith(("+", " ")):
                content.append(line[1:])
    flush()
    return sections


def _contents(changed_files: list[str], source_root: str | None,
              diff_text: str) -> tuple[dict[str, str], dict[str, int]]:
    root = _root(source_root)
    sections = _diff_sections(diff_text)
    texts, weights = {}, {}
    for name in changed_files:
        path = root / name if root else None
        if path and path.is_file() and path.resolve().is_relative_to(root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise ValueError("could not read changed file %s: %s" % (name, exc)) from exc
            texts[name] = text
            weights[name] = max(1, text.count("\n") + int(bool(text and not text.endswith("\n"))))
        else:
            text, lines = sections.get(name, ("", 0))
            texts[name] = text
            weights[name] = max(1, lines)
    return texts, weights


def _imports(text: str) -> list[tuple[int, str, list[str]]]:
    imports = []
    for line in text.splitlines():
        direct = _IMPORT.match(line)
        if direct:
            for module in direct.group(1).split(","):
                imports.append((0, module.strip(), []))
            continue
        indirect = _FROM.match(line)
        if indirect:
            module = indirect.group(1)
            names = [part.strip().split(" ", 1)[0] for part in
                     indirect.group(2).strip(" ()").split(",")]
            dots = len(module) - len(module.lstrip("."))
            imports.append((dots, module[dots:], names))
    return imports


def _module_targets(importer: str, dots: int, module: str,
                    imported_names: list[str], changed: set[str]) -> set[str]:
    parent = PurePosixPath(importer).parent
    if dots:
        base = parent
        for _ in range(dots - 1):
            base = base.parent
        bases = [base]
    else:
        bases = [parent, *parent.parents]
    parts = module.split(".") if module else []
    for base in bases:
        prefix = base.joinpath(*parts) if parts else base
        candidates = [str(prefix / "__init__.py")]
        if prefix.name:
            candidates.append(str(prefix.with_suffix(".py")))
        for symbol in imported_names:
            if symbol and symbol != "*":
                child = prefix / symbol
                candidates.extend((str(child.with_suffix(".py")), str(child / "__init__.py")))
        found = set(candidates) & changed
        if found:
            return found - {importer}
    return set()


def _is_test(name: str) -> bool:
    return PurePosixPath(name).name.startswith("test_") and name.endswith(".py")


def _test_pairs(changed_files: list[str]) -> list[tuple[str, str]]:
    subjects = [name for name in changed_files if name.endswith(".py") and not _is_test(name)]
    pairs = []
    for test in (name for name in changed_files if _is_test(name)):
        stem = PurePosixPath(test).name[5:]
        matches = [name for name in subjects if PurePosixPath(name).name == stem]
        if matches:
            directory = set(PurePosixPath(test).parts[:-1]) - {"tests", "test"}
            best = max(matches, key=lambda name: (len(directory & set(PurePosixPath(name).parts[:-1])),
                                                  -changed_files.index(name)))
            pairs.append((test, best))
    return pairs


def _mentions(text: str, target: str, names: list[str]) -> bool:
    path = PurePosixPath(target)
    variants = {target, path.name}
    for folder in ("scripts", "references", "assets"):
        if folder in path.parts:
            variants.add("/".join(path.parts[path.parts.index(folder):]))
    basename = path.stem
    if (len(basename) >= 6 and not basename.startswith("__")
            and ("_" in basename or "-" in basename)):
        variants.add(basename)
    if sum(PurePosixPath(name).name == path.name for name in names) > 1:
        variants.discard(path.name)
    return any(re.search(r"(?<![\w.-])" + re.escape(variant) + r"(?![\w.-])", text)
               for variant in variants)


def build_coupling_graph(changed_files: list[str], source_root: str | None,
                         diff_text: str) -> dict[str, set[str]]:
    """Connect changed files that share an import, reference, export, or test boundary."""
    files = _validate_files(changed_files)
    if not isinstance(diff_text, str):
        raise ValueError("diff must be a unified diff string")
    texts, _ = _contents(files, source_root, diff_text)
    return _graph_from_texts(files, texts)


def _graph_from_texts(files: list[str], texts: dict[str, str]) -> dict[str, set[str]]:
    graph = {name: set() for name in files}
    changed = set(files)

    def connect(first: str, second: str) -> None:
        if first != second:
            graph[first].add(second)
            graph[second].add(first)

    for name in files:
        if name.endswith(".py"):
            for dots, module, imported in _imports(texts[name]):
                for target in _module_targets(name, dots, module, imported, changed):
                    connect(name, target)
        is_doc_hub = name == "README.md" or name.startswith("docs/")
        for target in files:
            target_is_doc_hub = target == "README.md" or target.startswith("docs/")
            if target == name or _is_test(name) or _is_test(target) or is_doc_hub != target_is_doc_hub:
                continue
            if _mentions(texts[name], target, files):
                connect(name, target)
    for first, second in _test_pairs(files):
        connect(first, second)
    for index, name in enumerate(files):
        if not name.endswith((".py", ".html")) or _is_test(name):
            continue
        for other in files[index + 1:]:
            if not other.endswith((".py", ".html")) or _is_test(other):
                continue
            if any(marker in texts[name].lower() and marker in texts[other].lower()
                   for marker in _SHARED_MARKERS):
                connect(name, other)
    return graph


def partition_areas(changed_files: list[str], coupling: dict[str, set[str]],
                    file_lines: dict[str, int], max_lines: int = 1800,
                    max_files: int = 8) -> list[dict]:
    """Pack producer/consumer pairs before tests while enforcing both area limits."""
    files = _validate_files(changed_files)
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or max_lines < 1:
        raise ValueError("max_lines must be a positive integer")
    if isinstance(max_files, bool) or not isinstance(max_files, int) or max_files < 1:
        raise ValueError("max_files must be a positive integer")
    if any(not isinstance(file_lines.get(name), int) or file_lines[name] < 1 for name in files):
        raise ValueError("file_lines must contain a positive line count for each changed file")
    order = {name: index for index, name in enumerate(files)}
    edges = {name: (set(coupling.get(name, set())) & set(files)) - {name} for name in files}
    for first in files:
        for second in edges[first]:
            edges[second].add(first)
    pairs = sorted(
        [(first, second) for first in files if not _is_test(first)
         for second in files[order[first] + 1:] if not _is_test(second) and second in edges[first]],
        key=lambda pair: (
            not ({pair[0].endswith(".html"), pair[1].endswith(".html")} == {True, False}
                 and (pair[0].endswith(".py") or pair[1].endswith(".py"))),
            not (pair[0].endswith(".py") and pair[1].endswith(".py")),
            len([p for p in edges[pair[0]] if not _is_test(p)]) + len([p for p in edges[pair[1]] if not _is_test(p)]),
            order[pair[0]],
            order[pair[1]],
        ),
    )
    remaining = set(files)
    groups = []
    while remaining:
        pair = next(((first, second) for first, second in pairs
                     if first in remaining and second in remaining and max_files >= 2
                     and file_lines[first] + file_lines[second] <= max_lines), None)
        group = set(pair) if pair else {next(name for name in files if name in remaining)}
        remaining.difference_update(group)
        weight = sum(file_lines[name] for name in group)
        if weight <= max_lines:
            while len(group) < max_files:
                candidates = [name for name in files if name in remaining
                              and weight + file_lines[name] <= max_lines]
                adjacent = [name for name in candidates if edges[name] & group]
                if adjacent:
                    chosen = min(adjacent, key=lambda name: (
                        _is_test(name),
                        not name.endswith((".py", ".html")),
                        -len(edges[name] & group),
                        order[name],
                    ))
                else:
                    siblings = [name for name in candidates if any(
                        PurePosixPath(name).parent == PurePosixPath(peer).parent for peer in group)]
                    if not siblings:
                        siblings = [name for name in candidates if any(
                            len(PurePosixPath(name).parts) > 1 and len(PurePosixPath(peer).parts) > 1
                            and PurePosixPath(name).parts[:2] == PurePosixPath(peer).parts[:2]
                            and not (edges[name] - group)
                            for peer in group)]
                    if not siblings:
                        break
                    chosen = siblings[0]
                group.add(chosen)
                remaining.remove(chosen)
                weight += file_lines[chosen]
        groups.append(group)
    merged: list[set[str]] = []
    for group in groups:
        w = sum(file_lines[name] for name in group)
        top = {PurePosixPath(name).parts[0] for name in group}
        target_grp = next((prev for prev in merged
                           if len(prev) + len(group) <= max_files
                           and sum(file_lines[n] for n in prev) + w <= max_lines
                           and (len(group) <= 4 and w <= 400)
                           and {PurePosixPath(n).parts[0] for n in prev} == top), None)
        if target_grp is not None:
            target_grp.update(group)
        else:
            merged.append(group)
    result = []
    for idx, group in enumerate(merged, 1):
        group_files = [name for name in files if name in group]
        coupled = [[first, second] for first in group_files for second in group_files
                   if order[first] < order[second] and second in edges[first]]
        core = [name for name in group_files if not _is_test(name)] or group_files
        title = " + ".join((str(PurePosixPath(name).parent / "__init__.py")
                             if name.endswith("/__init__.py") else PurePosixPath(name).name)
                            for name in core[:2])
        result.append({"id": "A%d" % idx, "title": title,
                       "files": group_files, "test_files": [name for name in group_files if _is_test(name)],
                       "coupled_edges": coupled, "lines": sum(file_lines[n] for n in group), "questions": [],
                       "status": "pending", "degraded_reason": None})
    return result


def _boundary_question(first: str, second: str) -> str:
    a, b = PurePosixPath(first).name, PurePosixPath(second).name
    if _is_test(first) or _is_test(second):
        return "Does %s exercise the changed behavior of %s, including failure cases?" % (
            first if _is_test(first) else second, second if _is_test(first) else first)
    if a == "__init__.py" or b == "__init__.py":
        return "Do %s and %s agree on imported names and return values across their package boundary?" % (first, second)
    if a.endswith(".md") or b.endswith(".md"):
        return "Do %s and %s agree on referenced paths, CLI flags, and documented outputs?" % (first, second)
    if a.endswith(".html") or b.endswith(".html"):
        return "Do %s and %s agree on template fields and escaped content crossing their boundary?" % (first, second)
    return "Do %s and %s agree on imported interfaces, arguments, and output schemas?" % (first, second)


def _questions(area: dict, risk: dict | None) -> list[str]:
    files = area["files"]
    representative = next((name for name in files if not _is_test(name)), files[0])
    questions = [_boundary_question(a, b) for a, b in area["coupled_edges"]
                 if not (_is_test(a) or _is_test(b))][:2]
    test_edges = [(a, b) for a, b in area["coupled_edges"] if _is_test(a) or _is_test(b)]
    if test_edges:
        questions.append(_boundary_question(*test_edges[0]))
    if risk:
        level = risk.get("level")
        note = risk.get("verbatim_md")
        if isinstance(level, str) and level.strip() and isinstance(note, str) and note.strip():
            questions.append("For %s, is the %s risk real: %s?" % (
                representative, level.strip(), note.strip()))
        caveats = risk.get("caveats")
        if isinstance(caveats, str):
            caveats = [caveats]
        if isinstance(caveats, list):
            for caveat in caveats:
                if isinstance(caveat, str) and caveat.strip():
                    questions.append("For %s, does this caveat hold: %s?" % (representative, caveat.strip()))
                    break
    path = PurePosixPath(representative)
    if path.suffix == ".py":
        fallback = ["Does %s handle malformed or untrusted input without changing expected exit codes?" % representative,
                    "Does %s preserve its output schema and handle paths and command arguments safely?" % representative]
    elif path.suffix == ".html":
        fallback = ["Does %s escape untrusted values before inserting them into HTML?" % representative,
                    "Does %s keep the fields and markup that other files depend on intact?" % representative]
    else:
        fallback = ["Are paths and command examples in %s valid for the changed files?" % representative,
                    "Does %s describe the actual inputs, outputs, and failure modes?" % representative]
    for question in fallback:
        if len(questions) >= 2:
            break
        questions.append(question)
    return questions[:5]


def build_area_map(context: dict, source_root: str | None = None, risk: dict | None = None,
                   max_lines: int = 1800, max_files: int = 8) -> dict:
    """Return deterministic review areas covering every changed path exactly once."""
    if not isinstance(context, dict):
        raise ValueError("context must be a JSON object")
    files = _validate_files(context.get("changed_files"))
    diff = context.get("diff")
    if not isinstance(diff, str):
        raise ValueError("diff must be a unified diff string")
    if risk is not None and not isinstance(risk, dict):
        raise ValueError("risk must be a JSON object")
    texts, weights = _contents(files, source_root, diff)
    graph = _graph_from_texts(files, texts)
    areas = partition_areas(files, graph, weights, max_lines, max_files)
    for area in areas:
        area["questions"] = _questions(area, risk)
    return {"schema_version": 1, "areas": areas}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Write a review area map and print the same JSON; print JSON errors on failure."""
    parser = _JsonArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--risk")
    parser.add_argument("--max-lines", type=int, default=1800)
    parser.add_argument("--max-files", type=int, default=8)
    parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(argv)
        context = load_object(args.context, "context")
        risk = load_object(args.risk, "risk") if args.risk else None
        result = build_area_map(context, args.source_root, risk, args.max_lines, args.max_files)
        write_json(args.out, result)
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
