"""Tier-1 build: turn a ``<slug>.src.html`` source file into one self-contained HTML artifact.

``parse_source`` reads the source format (header comment plus slot sections). ``build_tier1``
resolves the template, inlines the pinned libraries, the tokens, the theme and ``chrome.js``,
writes the file atomically and runs the static checks. ``check_artifact`` and ``delivery_note``
serve the ``check`` and ``note`` CLI commands for any built file.

Problems the author can fix (unknown template, malformed source or data, missing slot, unknown
placeholder, a library version that is no longer vendored, an output that cannot be written)
raise ``BuildError`` so the CLI can report them as usage errors. A build that finishes but fails a static check is not an error here;
the result carries ``checks`` and the caller decides the exit code. Nothing in this module
touches the network.
"""
from __future__ import annotations

import csv
import html as html_lib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import SKILL_DIR, kitcheck
from .checks import MODES, SIZE_FAIL, SIZE_WARN, default_shells, run_checks
from .fsutil import atomic_write, ensure_self_ignoring
from .header import read_header, render_header
from .layouts import DEFAULT_LAYOUT, LAYOUTS, NAV_MODES, build_nav, collect_ids, render_regions, summary_hint, validate_layout
from .manifest import Template
from .resolve import (
    TemplateNotFound,
    default_project_dir,
    default_user_dir,
    find_template,
    template_roots,
)
from .tokens import merge_tokens, token_layers, tokens_css
from .vendor import VendorError, VendorStore, shell_block
from .verify_runner import default_out_dir, report_is_stale

SOURCE_MODES = ("offline", "connected")
RESERVED_SLOTS = ("summary",)
_SOURCE_HEADER = re.compile(r"^<!-- quirk-src (\{.*\}) -->[ \t]*$")
_SLOT_LINE = re.compile(r"^<!-- slot: ([a-z][a-z0-9-]{0,30}) -->$", re.M)
_PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")


class BuildError(Exception):
    """The build cannot proceed because of something the author must change."""


class SourceError(BuildError):
    """The ``.src.html`` file is malformed."""


@dataclass
class Source:
    """A parsed ``.src.html`` file; ``slots`` maps slot name to its raw HTML."""

    path: Path
    template: str
    title: str
    mode: str = "offline"
    libraries: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    data: Optional[str] = None
    tier_reason: Optional[str] = None
    slots: dict[str, str] = field(default_factory=dict)
    layout: Optional[str] = None
    nav: str = "auto"


def _string_list(meta: dict, key: str) -> list[str]:
    value = meta.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SourceError(f"header field {key!r} must be a list of strings")
    return value


def parse_source(path: Path) -> Source:
    """Parse a tier-1 source file; raises SourceError for any deviation from the format."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"cannot read source {path}: {exc}") from exc
    text = text.replace("\r\n", "\n")
    first, _, rest = text.partition("\n")
    match = _SOURCE_HEADER.match(first)
    if not match:
        raise SourceError("line 1 must be a header comment: <!-- quirk-src {...} -->")
    try:
        meta = json.loads(match.group(1))
    except (ValueError, RecursionError) as exc:
        raise SourceError(f"source header is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise SourceError("source header must be a JSON object")

    for key in ("template", "title"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise SourceError(f"header field {key!r} is required and must be a non-empty string")
    mode = meta.get("mode", "offline")
    if mode not in SOURCE_MODES:
        raise SourceError(f"header field 'mode' must be offline or connected, got {mode!r}")
    layout = validate_layout(meta["layout"]) if "layout" in meta else None
    nav = meta.get("nav", "auto")
    if nav not in NAV_MODES:
        raise SourceError(f"header field 'nav' must be one of {', '.join(NAV_MODES)}, got {nav!r}")
    data = meta.get("data")
    if data is not None and not isinstance(data, str):
        raise SourceError("header field 'data' must be a path string")
    reason = meta.get("tier_reason")
    if reason is not None and not isinstance(reason, str):
        raise SourceError("header field 'tier_reason' must be a string")

    marks = list(_SLOT_LINE.finditer(rest))
    if not marks:
        raise SourceError("source has no slot sections; start each with <!-- slot: name -->")
    if rest[: marks[0].start()].strip():
        raise SourceError("text before the first slot line; put all content inside a slot")
    slots: dict[str, str] = {}
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(rest)
        name = mark.group(1)
        if name in slots:
            raise SourceError(f"slot {name!r} appears twice")
        slots[name] = rest[mark.end() : end].strip("\n")

    return Source(
        path=path,
        template=meta["template"],
        title=meta["title"],
        mode=mode,
        libraries=_string_list(meta, "libraries"),
        interactions=_string_list(meta, "interactions"),
        data=data,
        tier_reason=reason or None,
        slots=slots,
        layout=layout,
        nav=nav,
    )


def _quirk_version(skill_dir: Path) -> str:
    plugin = Path(skill_dir).parent.parent / ".claude-plugin" / "plugin.json"
    try:
        version = json.loads(plugin.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return "unknown"
    return version if isinstance(version, str) and version else "unknown"


def _slug(source_path: Path) -> str:
    name = source_path.name
    return name[: -len(".src.html")] if name.endswith(".src.html") else source_path.stem


def _read_text_file(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"cannot read {what} {path}: {exc}") from exc


def _csv_rows(text: str) -> list[dict]:
    rows = [r for r in csv.reader(io.StringIO(text.lstrip("﻿"), newline="")) if r != []]
    if not rows:
        return []
    keys = rows[0]
    return [{k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)} for r in rows[1:]]


@dataclass
class _Data:
    path: Path
    suffix: str
    embedded: str


def _reject_constant(name: str) -> None:
    raise ValueError(f"the constant {name} is not allowed in JSON")


def _load_data(source: Source, project_dir: Path) -> Optional[_Data]:
    """Read and serialise the source's data file for embedding.

    The file must sit under ``project_dir`` or the source file's directory. Malformed content
    (invalid JSON, NaN or Infinity, an oversized CSV field, lone surrogates, nesting too deep
    to parse) raises SourceError naming the file.
    """
    if source.data is None:
        return None
    path = (source.path.parent / source.data).resolve()
    allowed = (source.path.resolve().parent, Path(project_dir).resolve())
    if not any(path == base or base in path.parents for base in allowed):
        raise SourceError(
            f"data file {source.data!r} is outside the project directory and the source file's directory"
        )
    suffix = path.suffix.lower()
    if suffix not in (".json", ".csv"):
        raise SourceError(f"data file {source.data!r} must be .json or .csv")
    text = _read_text_file(path, "data file")
    try:
        if suffix == ".json":
            parsed = json.loads(text, parse_constant=_reject_constant)
        else:
            parsed = _csv_rows(text)
        payload = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        payload.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SourceError(f"data file {source.data!r} contains a lone surrogate that UTF-8 cannot encode") from exc
    except RecursionError as exc:
        raise SourceError(f"data file {source.data!r} is nested too deeply to embed") from exc
    except (ValueError, csv.Error) as exc:
        raise SourceError(f"data file {source.data!r} is not valid {suffix[1:].upper()}: {exc}") from exc
    return _Data(path, suffix, payload.replace("<", "\\u003c"))


def _picker(sidecar: str) -> str:
    name = html_lib.escape(sidecar)
    return (
        '<div class="q-data-picker"><label>This page reads its data from <code>'
        + name
        + '</code>. Choose that file to load it. '
        '<input type="file" id="quirk-data-picker" accept=".json,.csv,application/json,text/csv"></label>'
        '<span id="quirk-data-status" role="status"></span></div>'
    )


def _chrome(sidecar: Optional[str]) -> str:
    toggle = '<button type="button" class="q-theme-toggle" data-quirk-theme-toggle>Theme: auto</button>'
    return toggle + (_picker(sidecar) if sidecar else "")


def _substitute(skeleton: str, values: dict[str, str]) -> str:
    def replace(match: "re.Match[str]") -> str:
        token = match.group(0)[2:-2]
        if token not in values:
            raise BuildError(f"skeleton has an unknown placeholder {match.group(0)}")
        return values[token]

    return _PLACEHOLDER.sub(replace, skeleton)


def _existing_header(out: Path) -> Optional[dict]:
    try:
        return read_header(out.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _frozen_versions(out: Path) -> dict[str, str]:
    meta = _existing_header(out)
    libs = meta.get("libraries") if meta else None
    if not isinstance(libs, dict):
        return {}
    return {k: v for k, v in libs.items() if isinstance(k, str) and isinstance(v, str)}


def _library_order(template: Template, source: Source) -> list[str]:
    extra = [name for name in source.libraries if name not in template.libraries]
    unknown = [name for name in extra if name not in template.optional_libraries]
    if unknown:
        raise BuildError(
            f"libraries {', '.join(unknown)} are not optional libraries of template "
            f"{template.name!r} (optional: {', '.join(template.optional_libraries) or 'none'})"
        )
    names = list(dict.fromkeys(template.libraries + extra))
    return [n for n in names if n != "alpine"] + [n for n in names if n == "alpine"]


def _with_auto_libraries(names: list[str], raw_source: str) -> list[str]:
    """Add the libraries the source's q-* markup needs: Chart.js, highlight.js, flow, then the kit,
    Alpine still last.

    The scan is over the raw source text, so a q-* tag a script or template builds at runtime pulls
    the kit in too. These libraries are automatic, so none has to be an optional library of the
    template.
    """
    kit, chartjs = kitcheck.needs(raw_source)
    highlight = kit and kitcheck.needs_highlight(raw_source)
    flow = kit and kitcheck.needs_flow(raw_source)
    wanted = (
        (["chartjs"] if chartjs else [])
        + (["highlightjs"] if highlight else [])
        + (["flow"] if flow else [])
        + (["kit"] if kit else [])
    )
    names = list(dict.fromkeys(names + wanted))
    return [n for n in names if n != "alpine"] + [n for n in names if n == "alpine"]


@dataclass
class _RegionPlan:
    """How a build places the page's regions: the resolved shape and the rendered region markup.

    ``layout`` is empty for a skeleton with no region placeholder (the companion) whose source names
    no shape. ``defaulted`` means no source or earlier build named one. ``legacy_summary`` marks a page
    built before shapes existed that still has no summary, kept buildable (see ``_plan_regions``).
    """

    region_bearing: bool
    legacy_skeleton: bool
    layout: str
    defaulted: bool
    legacy_summary: bool
    html: str


_SUMMARY_WARNING = (
    "this page has no summary slot; add <!-- slot: summary --> so it gets the summary region"
)


def _plan_regions(source: Source, skeleton: str, existing: Optional[dict]) -> _RegionPlan:
    """Resolve the shape and render the regions for ``skeleton``; raises SourceError on a bad combination.

    Shape: the source's ``layout``, else the one in ``existing`` (the output's current header), else
    ``explainer``. A header carrying ``layout_defaulted`` keeps the page defaulted until a source names a
    shape. Only a skeleton with ``{{regions}}`` or ``{{slot:main}}`` resolves a default and
    requires ``summary``. A missing summary is allowed once for a page whose header predates shapes
    (no ``layout`` key) and stays allowed while the header carries ``legacy_summary``.
    """
    has_regions = "{{regions}}" in skeleton
    legacy_skeleton = not has_regions and "{{slot:main}}" in skeleton
    region_bearing = has_regions or legacy_skeleton
    recorded = existing.get("layout") if existing else None
    layout = source.layout
    defaulted = False
    if layout is None and region_bearing:
        layout = recorded if recorded in LAYOUTS else DEFAULT_LAYOUT
        defaulted = recorded not in LAYOUTS or existing.get("layout_defaulted") is True
    if not region_bearing:
        if source.slots.get("summary", "").strip():
            raise SourceError(
                "the source has a summary slot, but the template's skeleton has no place for it: "
                "add {{regions}} (or {{slot:main}}) to the skeleton, or remove the summary slot"
            )
        return _RegionPlan(False, False, layout or "", False, False, "")

    assert layout is not None
    summary = source.slots.get("summary", "")
    legacy_summary = False
    if not summary.strip():
        pre_shapes = existing is not None and ("layout" not in existing or existing.get("legacy_summary") is True)
        if not pre_shapes:
            raise SourceError(
                f"the {layout} shape needs a summary slot: add <!-- slot: summary --> with "
                f"{summary_hint(layout)}"
            )
        legacy_summary = True
        summary = ""
    reserved = collect_ids(summary, skeleton, _chrome("x")) | {"main", "quirk-data"}
    nav_html, main_html = build_nav(
        source.slots.get("main", ""), layout=layout, nav=source.nav, reserved_ids=reserved
    )
    html = render_regions(
        layout,
        summary=summary,
        main=main_html,
        nav=nav_html,
        legacy=legacy_skeleton,
    )
    return _RegionPlan(True, legacy_skeleton, layout, defaulted, legacy_summary, html)


def _check_slots(template: Template, source: Source) -> None:
    undeclared = [name for name in source.slots if name not in template.slots and name not in RESERVED_SLOTS]
    if undeclared:
        raise SourceError(
            f"source has slots the template does not declare: {', '.join(undeclared)} "
            f"(declared: {', '.join(template.slots)})"
        )
    missing = [n for n, info in template.slots.items() if info.get("required") and n not in source.slots]
    if missing:
        raise SourceError(f"source is missing required slot(s): {', '.join(missing)}")


def _is_quirk_output_dir(directory: Path) -> bool:
    """True when ``directory`` is, or sits under, a ``.quirk/html`` or ``.quirk/brainstorm`` directory."""
    parts = directory.resolve().parts
    return any(
        part == ".quirk" and parts[i + 1] in ("html", "brainstorm")
        for i, part in enumerate(parts[:-1])
    )


def _skill_store(skill_dir: Path, template_dir: Optional[Path]) -> VendorStore:
    paths = [Path(skill_dir) / "vendor" / "libraries.json"]
    if template_dir is not None:
        paths.insert(0, Path(template_dir) / "vendor" / "libraries.json")
    return VendorStore(paths)


def build_tier1(
    source_path: Path,
    *,
    out: Optional[Path],
    upgrade: bool,
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
) -> dict:
    """Build ``source_path`` and return a ``BuildResult`` dict (see tech.md section 4.1).

    ``out`` defaults to ``<project_dir>/.quirk/html/<slug>.html``. An output directory that is,
    or sits under, a ``.quirk/html`` or ``.quirk/brainstorm`` directory gets a self-ignoring
    ``.gitignore``. An existing output file pins every library to the version in its header
    unless ``upgrade`` is set. Oversized data goes to ``<slug>.data.<ext>`` beside the output
    and ``sidecar`` in the result is that file's path; a later build that embeds the data
    removes the stale sidecar. ``out`` may not be the source file or the data file.
    Raises BuildError for anything the author must fix, including an output that cannot be
    written; static-check failures are reported in ``checks`` and still leave the file written.
    """
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    source_path = Path(source_path)
    project_dir = Path(project_dir)
    user = Path(user_dir) if user_dir is not None else default_user_dir()
    source = parse_source(source_path)

    roots = template_roots(skill, project_dir, user)
    try:
        template, skipped = find_template(source.template, roots, skill_dir=skill)
    except TemplateNotFound as exc:
        raise BuildError(str(exc)) from exc
    if template.tier != 1:
        raise BuildError(f"template {template.name!r} is tier 2; build it with build-app")
    warnings = [
        f"template {w['name']!r} at {w['level']} level was skipped ({w['path']}): {w['reason']}"
        for w in skipped
    ]
    _check_slots(template, source)

    default_dir = project_dir / ".quirk" / "html"
    slug = _slug(source_path)
    out_path = Path(out) if out is not None else default_dir / f"{slug}.html"
    data = _load_data(source, project_dir)
    protected = [source_path.resolve()] + ([data.path] if data is not None else [])
    if out_path.resolve() in protected:
        raise BuildError(f"--out {out_path} is the source or data file; choose a different output path")
    frozen = _frozen_versions(out_path)

    store = _skill_store(skill, template.dir)
    versions: dict[str, str] = {}
    head_parts: list[str] = []
    kit_head_parts: list[str] = []
    js_parts: list[str] = []
    licenses: list[str] = []
    try:
        raw_source = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        for name in _with_auto_libraries(_library_order(template, source), raw_source):
            lv = store.resolve(name, None if upgrade else frozen.get(name))
            if upgrade and name in frozen and frozen[name] != lv.version:
                warnings.append(f"library {name} upgraded from {frozen[name]} to {lv.version}")
            versions[name] = lv.version
            blocks = store.inline_blocks(lv)
            if blocks:
                licenses.append(store.license_comment(lv))
            for block in blocks:
                if block.kind == "js":
                    js_parts.append(block.text)
                else:
                    (kit_head_parts if name == "kit" else head_parts).append(block.text)
        chrome_js = shell_block("chrome", skill / "theme" / "chrome.js").text
    except VendorError as exc:
        raise BuildError(str(exc)) from exc

    try:
        token_css = tokens_css(merge_tokens(token_layers(skill, user, project_dir, template)))
    except ValueError as exc:
        raise BuildError(str(exc)) from exc
    base_css = _read_text_file(skill / "theme" / "base.css", "theme")
    layout_css = _read_text_file(skill / "theme" / "layout.css", "theme")
    head = "\n".join(
        head_parts
        + [f"<style>\n{token_css}</style>", f"<style>\n{base_css}</style>", f"<style>\n{layout_css}</style>"]
        + kit_head_parts
    )
    body_end = "\n".join(js_parts + [chrome_js])

    skeleton = _read_text_file(template.dir / str(template.skeleton), "skeleton")
    if data is not None and "{{data}}" not in skeleton:
        raise BuildError(
            f"template {template.name!r} has no {{{{data}}}} placeholder in its skeleton, "
            "so the source's data field cannot be used"
        )
    plan = _plan_regions(source, skeleton, _existing_header(out_path))
    signal = f"judgment: {source.tier_reason}" if source.tier_reason else None
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def render(sidecar: Optional[str]) -> str:
        meta = {
            "schema": 1,
            "template": template.name,
            "template_level": template.level,
            "tier": 1,
            "tier_signal": signal,
            "mode": source.mode,
            "libraries": versions,
            "sidecar": sidecar,
            "built_at": built_at,
            "quirk_version": _quirk_version(skill),
        }
        if plan.layout:
            meta["layout"] = plan.layout
        if plan.defaulted:
            meta["layout_defaulted"] = True
        if plan.legacy_summary:
            meta["legacy_summary"] = True
        embedded = ""
        if data is not None and sidecar is None:
            embedded = f'<script type="application/json" id="quirk-data">{data.embedded}</script>'
        values = {
            "header": "\n".join([render_header(meta), *licenses]),
            "title": html_lib.escape(source.title),
            "head": head,
            "chrome": _chrome(sidecar),
            "data": embedded,
            "body_end": body_end,
        }
        values.update(
            {f"slot:{name}": kitcheck.inject_flow_fallbacks(source.slots.get(name, "")) for name in template.slots}
        )
        values["layout"] = plan.layout
        values["regions"] = ""
        if plan.region_bearing:
            values["slot:main" if plan.legacy_skeleton else "regions"] = kitcheck.inject_flow_fallbacks(plan.html)
        return _substitute(skeleton, values)

    sidecar_name: Optional[str] = None
    page = render(None)
    try:
        page_size = len(page.encode("utf-8"))
        if data is not None and page_size > SIZE_FAIL:
            sidecar_name = f"{slug}.data{data.suffix}"
            page = render(sidecar_name)
            page_size = len(page.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise BuildError(f"the page contains a character UTF-8 cannot encode (a lone surrogate?): {exc}") from exc

    sidecar_path: Optional[Path] = None
    try:
        if _is_quirk_output_dir(out_path.parent):
            ensure_self_ignoring(out_path.parent)
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            stale = out_path.parent / f"{slug}.data{data.suffix}"
            if sidecar_name is not None:
                sidecar_path = stale
                atomic_write(sidecar_path, data.path.read_bytes())
            elif stale.is_file() and stale.resolve() != data.path:
                stale.unlink()
        atomic_write(out_path, page)
    except OSError as exc:
        raise BuildError(f"cannot write the build output under {out_path.parent}: {exc}") from exc

    result_checks = run_checks(
        page,
        mode=source.mode,
        tier=1,
        vendor=store,
        shells=default_shells(skill),
        kit_source=(source_path.name, raw_source),
    )
    if plan.legacy_summary:
        result_checks["warnings"].append({"check": "summary", "detail": _SUMMARY_WARNING})
    return {
        "path": str(out_path),
        "size": page_size,
        "sidecar": str(sidecar_path) if sidecar_path else None,
        "source_dir": None,
        "template": template.name,
        "template_level": template.level,
        "tier": 1,
        "tier_signal": signal,
        "mode": source.mode,
        "libraries": versions,
        "warnings": warnings,
        "checks": result_checks,
        "cut": [],
        "layout": plan.layout,
        "layout_defaulted": plan.defaulted,
        **({"legacy_summary": True} if plan.legacy_summary else {}),
    }


def read_artifact_header(path: Path) -> dict:
    """The header of a built file; raises BuildError when it is unreadable or has none."""
    try:
        meta = read_header(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise BuildError(f"cannot read {path}: {exc}") from exc
    if meta is None:
        raise BuildError(f"{path} has no quirk-html-artifact header; it was not built by this skill")
    return meta


def artifact_mode(meta: Optional[dict]) -> str:
    """The header's mode when it is one the checks know, else ``offline``."""
    mode = meta.get("mode") if meta else None
    return mode if mode in MODES else "offline"


def check_artifact(
    path: Path,
    *,
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
) -> dict:
    """Run the static checks on a built file, using its header's mode and tier.

    A file with no readable header still gets checked as an offline tier-1 page, which
    reports the missing header as a failure.
    """
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    path = Path(path)
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BuildError(f"cannot read {path}: {exc}") from exc
    meta = read_header(html)
    tier = meta.get("tier") if meta and meta.get("tier") in (1, 2) else 1
    template_dir: Optional[Path] = None
    if meta and isinstance(meta.get("template"), str):
        user = Path(user_dir) if user_dir is not None else default_user_dir()
        try:
            found, _ = find_template(meta["template"], template_roots(skill, project_dir, user), skill_dir=skill)
            template_dir = found.dir
        except TemplateNotFound:
            template_dir = None
    return run_checks(
        html,
        mode=artifact_mode(meta),
        tier=tier,
        vendor=_skill_store(skill, template_dir),
        shells=default_shells(skill),
        kit_source=(path.name, html),
    )


def _verify_line(report_path: Path, stale: bool) -> list[str]:
    try:
        report = json.loads(report_path.read_text())
    except (OSError, ValueError):
        return ["Verify: not browser-verified (verify has not been run on this file)."]
    if stale:
        return ["Verify: not browser-verified (the last report is for an earlier version of this file; run verify again)."]
    status = report.get("status")
    label = "Verify (no JS)" if report.get("no_js") is True else "Verify"
    if status == "not-browser-verified":
        reason = report.get("reason")
        return [f"{label}: not browser-verified" + (f" ({reason})." if reason else ".")]
    if status == "failed" and report.get("reason"):
        detail = report.get("detail")
        return [f"{label}: failed ({report['reason']})" + (f": {detail}" if detail else ".")]
    lines = [f"{label}: {status} in {report.get('browser') or 'a browser'}."]
    checks = report.get("checks") or {}
    for name, result in checks.items():
        if isinstance(result, dict) and not result.get("passed", True):
            for detail in result.get("details", [])[:5]:
                lines.append(f"  - {name}: {detail}")
    shots = report.get("screenshots") or []
    if shots:
        lines.append("Screenshots:")
        lines.extend(f"  - {shot}" for shot in shots)
    return lines


def delivery_note(
    path: Path,
    *,
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
    verify_dir: Optional[Path] = None,
) -> dict:
    """The delivery note for a built file: ``{"markdown": str, "verify_stale": bool}``.

    ``verify_stale`` is true when no verify report exists for the file's current contents.
    The report is read from ``verify_dir``, default ``<file stem>.verify/`` beside the file.
    """
    path = Path(path).resolve()
    meta = read_artifact_header(path)
    size = path.stat().st_size
    checked = check_artifact(path, project_dir=project_dir, user_dir=user_dir, skill_dir=skill_dir)
    report_path = (Path(verify_dir) if verify_dir is not None else default_out_dir(path)) / "report.json"
    stale = report_is_stale(path, report_path)
    libraries = meta.get("libraries") if isinstance(meta.get("libraries"), dict) else {}

    lines = [f"Built `{path}` ({size:,} bytes)."]
    sidecar = meta.get("sidecar")
    if sidecar:
        side = path.parent / sidecar
        extra = f" ({side.stat().st_size:,} bytes)" if side.is_file() else ""
        lines.append(f"- Sidecar: `{side}`{extra}. The page asks the reader to pick this file.")
    source_dir = path.parent / path.stem
    if source_dir.is_dir():
        lines.append(f"- Source folder: `{source_dir}`")
    lines.append(f"- Template: {meta.get('template')} ({meta.get('template_level')})")
    layout = meta.get("layout")
    if isinstance(layout, str) and layout:
        lines.append(f"- Layout: {layout}" + (" (no layout named)" if meta.get("layout_defaulted") is True else ""))
    signal = meta.get("tier_signal")
    lines.append(f"- Tier {meta.get('tier')}" + (f", chosen by: {signal}" if signal else " (no tier signal recorded)"))
    mode = meta.get("mode")
    lines.append(
        f"- Mode: {mode}"
        + (" (no network requests)" if mode == "offline" else " (the page's own data calls use the network)")
    )
    lines.append("- Libraries: " + (", ".join(f"{k} {v}" for k, v in libraries.items()) or "none"))
    if checked["passed"]:
        lines.append("- Static checks: passed")
    else:
        lines.append("- Static checks: failed")
        lines.extend(f"  - {f['check']}: {f['detail']}" for f in checked["failures"])
    if size > SIZE_WARN:
        if "mermaid" in libraries:
            why = " Mermaid alone is about 5 MB, so this is expected."
        elif "flow" in libraries:
            why = " The flow layout engine is about 1.5 MB, so this is expected."
        else:
            why = ""
        lines.append(f"- Size: over 2 MB, so the file may be slow to open.{why}")
    lines.extend(f"- {line}" if not line.startswith("  ") else line for line in _verify_line(report_path, stale))
    lines.append("")
    lines.append("Want me to open it or publish it?")
    return {"markdown": "\n".join(lines), "verify_stale": stale}
