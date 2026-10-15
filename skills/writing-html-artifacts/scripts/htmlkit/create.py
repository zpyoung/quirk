"""Custom template authoring: ``templates new`` scaffolds one and ``templates verify`` blesses it.

``create_template`` makes ``<project>/.quirk/html-templates/NAME/`` or ``<user dir>/NAME/`` from a
built-in or custom base, from a quirk-built artifact (its template, plus its sibling
``<slug>.src.html`` as the example) or from any other HTML file (a one-slot skeleton under the
house tokens, for the author to refine). It never writes ``verified.json``, so a new template stays
out of ``templates list`` and out of builds until it is verified.

``verify_template`` builds the template's own example in a scratch project, runs the static checks
and the browser verification, and only on a pass writes ``verified.json`` with the hashes of the
exact bytes it built. A missing Node, browser or verifier install does not fail a template (``browser`` is then
false); a failed static check, a failed browser check, a verifier crash or timeout, or an example
that does not build does. Nothing here
touches the network apart from what ``build_app`` and the verify runner already do.

Problems the author can fix (existing name, unknown base, unreadable input, no such custom template,
invalid manifest) raise ``BuildError`` and are exit 2 in the CLI.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import SKILL_DIR, verify_runner
from .app import AppUnavailable, build_app
from .assemble import _SOURCE_HEADER, BuildError, build_tier1, parse_source
from .fsutil import atomic_write
from .header import read_header
from .manifest import NAME_RE, compute_hashes, validate_template
from .resolve import TemplateNotFound, default_user_dir, find_template, template_roots

DEFAULT_BASE = "report"
EXAMPLE_FILE = "example.src.html"
EXAMPLE_DATA_STEM = "example.data"
ENVIRONMENT_LIMITS = ("no-node", "no-browser", "install-failed")
NOT_A_BASE = ("companion",)
_PROJECT_SKIP = ("node_modules", "dist")
_BODY = re.compile(r"<body\b[^>]*>(.*?)(?:</body\s*>|\Z)", re.IGNORECASE | re.DOTALL)
_HEAD = re.compile(r"<head\b.*?</head\s*>", re.IGNORECASE | re.DOTALL)
_DOCUMENT_TAGS = re.compile(r"<!doctype[^>]*>|</?html\b[^>]*>", re.IGNORECASE)
_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title\s*>", re.IGNORECASE | re.DOTALL)

SKELETON = """<!doctype html>
{{header}}
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
{{head}}
<style>
body { margin: 0; }
header.q-masthead { padding: var(--q-space-4) 0 var(--q-space-5); border-bottom: 1px solid var(--q-color-border); }
header.q-masthead h1 { margin: var(--q-space-3) 0 0; }
.q-chrome { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: var(--q-space-3); }
.q-chrome .q-theme-toggle { position: static; }
</style>
</head>
<body>
<header class="q-masthead">
<div class="q-wrap">
<div class="q-chrome">{{chrome}}</div>
<h1>{{title}}</h1>
</div>
</header>
<div class="q-wrap">
{{regions}}
</div>
{{data}}
{{body_end}}
</body>
</html>
"""


def _project_dir_of(src: Path) -> Optional[Path]:
    """The tier-2 ``project/`` directory of the template at ``src``, or None for any other template."""
    try:
        meta = json.loads((src / "template.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get("tier") != 2:
        return None
    rel = meta.get("project", "project/")
    return (src / rel).resolve() if isinstance(rel, str) and rel else None


def _copy_tree(src: Path, dest: Path) -> None:
    """Copy a template folder without build output.

    ``node_modules`` and ``dist`` are skipped only under a tier-2 ``project/`` and ``verified.json``
    only at the template root, so a tier-1 template that vendors a ``dist/`` path copies whole.
    """
    root = src.resolve()
    project = _project_dir_of(src)

    def ignore(directory: str, names: list[str]) -> set[str]:
        here = Path(directory).resolve()
        skipped = {".DS_Store"} & set(names)
        if here == root:
            skipped |= {"verified.json"} & set(names)
        if project is not None and (here == project or project in here.parents):
            skipped |= set(_PROJECT_SKIP) & set(names)
        return skipped

    shutil.copytree(src, dest, ignore=ignore)


def _read_text(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BuildError(f"cannot read {what} {path}: {exc}") from exc


def _retarget_example(
    example: Path, name: str, data_source: Optional[Path] = None, data_allowed: bool = True
) -> list[str]:
    """Point the source header at template ``name``; returns notes for the author.

    ``data_source`` is where the example's ``data`` field resolved before the example moved into
    the template folder: the file is copied beside the example as ``example.data.<ext>``, or the
    field is dropped with a note when it is gone. None leaves ``data`` alone, for an example whose
    data file is already in the folder. With ``data_allowed`` false the file lies outside the
    directories a build may read data from, so it is never copied and the field is dropped.
    """
    text = _read_text(example, "example").replace("\r\n", "\n")
    first, newline, rest = text.partition("\n")
    match = _SOURCE_HEADER.match(first)
    if not match or not newline:
        raise BuildError(f"{example} does not start with a <!-- quirk-src {{...}} --> header")
    try:
        meta = json.loads(match.group(1))
    except ValueError as exc:
        raise BuildError(f"the source header of {example} is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise BuildError(f"the source header of {example} must be a JSON object")
    notes: list[str] = []
    meta["template"] = name
    given = meta.get("data")
    if isinstance(given, str) and data_source is not None and not data_allowed:
        del meta["data"]
        notes.append(
            f"the example's data file {given!r} is outside the project directory and the source file's directory, "
            "so it was not copied and the example no longer embeds data"
        )
    elif isinstance(given, str) and data_source is not None:
        if data_source.is_file() and data_source.suffix.lower() in (".json", ".csv"):
            target = f"{EXAMPLE_DATA_STEM}{data_source.suffix.lower()}"
            shutil.copyfile(data_source, example.parent / target)
            meta["data"] = target
        else:
            del meta["data"]
            notes.append(f"the example's data file {given!r} was not found, so the example no longer embeds data")
    header = "<!-- quirk-src " + json.dumps(meta, ensure_ascii=False).replace("--", "-\\u002d") + " -->"
    atomic_write(example, header + "\n" + rest)
    return notes


def _rename_manifest(tdir: Path, name: str) -> dict:
    path = tdir / "template.json"
    meta = json.loads(_read_text(path, "template manifest"))
    meta["name"] = name
    atomic_write(path, json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return meta


def _plain_parts(text: str, stem: str) -> tuple[str, str]:
    """The title and the body markup of an arbitrary HTML file."""
    found = _TITLE_TAG.search(text)
    title = html_lib.unescape(found.group(1)).strip() if found else ""
    body = _BODY.search(text)
    if body:
        content = body.group(1)
    else:
        content = _DOCUMENT_TAGS.sub("", _HEAD.sub("", text))
    return title or stem, content.strip("\n")


def _skeleton_template(name: str, stem: str, skill: Path, dest: Path, text: str) -> None:
    title, content = _plain_parts(text, stem)
    if not content.strip():
        raise BuildError("the HTML file has no body content to use as the example")
    label = re.sub(r"\s+", " ", stem)[:80]
    meta = {
        "schema": 1,
        "name": name,
        "description": f"Use when a page should follow the layout of {label}: one main section under the house design tokens. Refine this description before relying on it.",
        "tier": 1,
        "libraries": ["simple-css"],
        "optional_libraries": [],
        "slots": {"main": {"required": True, "description": "The page body. No h1; the title becomes it."}},
        "skeleton": "skeleton.html",
        "tokens": "tokens.json",
        "example": EXAMPLE_FILE,
    }
    dest.mkdir(parents=True)
    atomic_write(dest / "template.json", json.dumps(meta, indent=2) + "\n")
    atomic_write(dest / "skeleton.html", SKELETON)
    shutil.copyfile(skill / "theme" / "house.tokens.json", dest / "tokens.json")
    header = {"template": name, "title": title, "mode": "offline", "libraries": []}
    summary = f"<p>{html_lib.escape(title)}: replace this line with the page's one-sentence answer.</p>"
    source = (
        "<!-- quirk-src " + json.dumps(header, ensure_ascii=False).replace("--", "-\\u002d") + " -->\n"
        f"<!-- slot: summary -->\n{summary}\n<!-- slot: main -->\n{content}\n"
    )
    atomic_write(dest / EXAMPLE_FILE, source)


def _target_dir(name: str, level: str, project_dir: Path, user: Path) -> Path:
    if not NAME_RE.match(name):
        raise BuildError(f"{name!r} is not a valid template name ([a-z0-9-]{{1,40}})")
    if level == "project":
        return Path(project_dir) / ".quirk" / "html-templates" / name
    if level == "user":
        return user / name
    raise BuildError(f"level must be project or user, got {level!r}")


def _find(name: str, roots: list[tuple[str, Path]], skill: Path):
    try:
        found = find_template(name, roots, skill_dir=skill)[0]
    except TemplateNotFound as exc:
        raise BuildError(str(exc)) from exc
    if found.level == "builtin" and found.name in NOT_A_BASE:
        raise BuildError(
            f"the {found.name} template is not a base for custom page templates: its example is a screen.json, not a page source"
        )
    return found


def create_template(
    name: str,
    *,
    level: str,
    base: Optional[str],
    source: Optional[Path],
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
) -> dict:
    """Scaffold template ``name`` and return ``{"path", "next"}``; never writes ``verified.json``.

    Without ``source`` the resolved ``base`` (default ``report``) is copied and renamed, keeping
    its example. With ``source`` (a quirk-built artifact or any HTML file) ``base`` must be None:
    a quirk-built artifact copies its source template and takes its sibling ``<slug>.src.html``
    as the example, and any other HTML becomes a one-slot skeleton. Raises BuildError when the
    template exists, the base or source cannot be used, or the target cannot be written.
    """
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    user = Path(user_dir) if user_dir is not None else default_user_dir()
    dest = _target_dir(name, level, project_dir, user)
    if dest.exists():
        raise BuildError(f"template {name!r} already exists at {dest}")
    if source is not None and base is not None:
        raise BuildError("--base and --from cannot be combined: --from decides where the template starts")

    roots = template_roots(skill, project_dir, user)
    notes: list[str] = []
    staging = dest.with_name(f".{dest.name}.new-{os.getpid()}")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        plain = False
        if source is None:
            origin = _find(base or DEFAULT_BASE, roots, skill)
            _copy_tree(origin.dir, staging)
            if origin.tier == 1:
                notes += _retarget_example(staging / str(origin.example), name)
        else:
            text = _read_text(source, "artifact")
            meta = read_header(text)
            if meta is None:
                plain = True
                _skeleton_template(name, source.name.removesuffix(".html"), skill, staging, text)
            else:
                origin = _find(str(meta.get("template", "")), roots, skill)
                _copy_tree(origin.dir, staging)
                notes += _adopt_artifact_example(origin, source, name, staging, project_dir)
        if not plain:
            _rename_manifest(staging, name)
        os.rename(staging, dest)
    except OSError as exc:
        raise BuildError(f"cannot create the template at {dest}: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    where = f" --project-dir {project_dir}" if level == "project" else ""
    steps = [
        f"edit {dest / 'template.json'}: write a description that starts with \"Use when\" and says when to pick this template",
        *notes,
    ]
    if plain:
        steps.append(
            f"refine {dest / 'skeleton.html'} and {dest / EXAMPLE_FILE}: the example is the source page's body, "
            "so move its styles into the skeleton or tokens.json and swap any external references for vendored ones"
        )
    steps += [
        f"run quirk_html.py templates validate {dest}",
        f"run quirk_html.py templates verify {name}{where}; the template is not listed or built until it passes",
    ]
    return {"path": str(dest), "next": steps}


def _data_name(example_in_staging: Path) -> str:
    """The ``data`` field of an example source, or an empty name when it has none."""
    try:
        first = example_in_staging.read_text(encoding="utf-8").split("\n", 1)[0]
        match = _SOURCE_HEADER.match(first)
        data = json.loads(match.group(1)).get("data") if match else None
    except (OSError, UnicodeDecodeError, ValueError, AttributeError):
        return ""
    return data if isinstance(data, str) else ""


def _data_within(path: Path, project_dir: Path, source_dir: Path) -> bool:
    """True when ``path`` resolves under the project directory or the source file's directory."""
    resolved = path.resolve()
    allowed = (source_dir.resolve(), Path(project_dir).resolve())
    return any(resolved == base or base in resolved.parents for base in allowed)


def _adopt_artifact_example(origin, artifact: Path, name: str, staging: Path, project_dir: Path) -> list[str]:
    """Use the artifact's sibling ``<slug>.src.html`` as the example of the copied template."""
    if origin.tier != 1:
        return [
            f"the artifact was built from tier-2 template {origin.name!r}; its example folder is the template's own, "
            "so replace it with the app source you want as the example"
        ]
    stem = artifact.name.removesuffix(".html")
    src = artifact.with_name(f"{stem}.src.html")
    example = staging / str(origin.example)
    if not src.is_file():
        notes = _retarget_example(example, name)
        return [
            f"{src} was not found, so write the example by hand: {example} still holds the example of {origin.name!r}",
            *notes,
        ]
    atomic_write(example, _read_text(src, "source"))
    data_name = _data_name(example)
    data_source = src.parent / data_name if data_name else None
    allowed = data_source is None or _data_within(data_source, project_dir, src.parent)
    return _retarget_example(example, name, data_source, allowed)


def _locate_custom(name: str, project_dir: Path, user: Path) -> tuple[str, Path]:
    if not NAME_RE.match(name):
        raise BuildError(f"{name!r} is not a valid template name ([a-z0-9-]{{1,40}})")
    levels = (("project", Path(project_dir) / ".quirk" / "html-templates"), ("user", user))
    for level, root in levels:
        if (root / name).is_dir():
            return level, root / name
    raise BuildError(
        f"no custom template named {name!r} in {levels[0][1]} or {levels[1][1]}; built-in templates need no verification"
    )


def _failed(stage: str, error: str, **extra: object) -> dict:
    return {"passed": False, "browser": False, "report": {"stage": stage, "error": error, **extra}}


def _build_example(name: str, tier: int, meta: dict, staged: Path, project: Path, user: Path, out: Path, skill: Path) -> dict:
    if tier == 2:
        return build_app(
            name, title=name, mode=None, signal=None, template_name=name, upgrade=False,
            project_dir=project, user_dir=user, skill_dir=skill,
        )
    example = staged / str(meta["example"])
    declared = parse_source(example).template
    if declared != name:
        raise BuildError(f"the example's header names template {declared!r}, not {name!r}")
    return build_tier1(example, out=out, upgrade=False, project_dir=project, user_dir=user, skill_dir=skill)


def verify_template(
    name: str,
    *,
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
) -> dict:
    """Verify custom template ``name`` and return ``{"passed", "browser", "report"}``.

    The template is found at project level, then user level. The example is built from a scratch
    copy, so an unverified template can be built at all. On a pass ``verified.json`` is written
    with ``browser`` true only when a real browser ran. Raises BuildError when no custom template
    has that name or its manifest is invalid; an example that does not build is a failed result.
    """
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    user = Path(user_dir) if user_dir is not None else default_user_dir()
    level, tdir = _locate_custom(name, Path(project_dir), user)
    errors = validate_template(tdir, require_verified=False, skill_dir=skill)
    if errors:
        raise BuildError(f"template {name!r} at {tdir} is invalid: " + "; ".join(errors))
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    tier = meta["tier"]

    with tempfile.TemporaryDirectory(prefix="quirk-verify-") as scratch:
        root = Path(scratch)
        project = root / "project"
        staged = project / ".quirk" / "html-templates" / name
        _copy_tree(tdir, staged)
        hashes = compute_hashes(staged)
        stamp = {"schema": 1, "verified_at": "", "browser": False, "hashes": hashes}
        atomic_write(staged / "verified.json", json.dumps(stamp))
        out = root / "out"
        out.mkdir()
        try:
            built = _build_example(name, tier, meta, staged, project, root / "user", out / f"{name}.html", skill)
        except AppUnavailable as exc:
            return _failed("build", str(exc), reason=exc.reason)
        except BuildError as exc:
            return _failed("build", str(exc))
        verdict = verify_runner.run_verify(Path(built["path"]), out / "verify", built["mode"])

    status = verdict.get("status")
    checks = built["checks"]
    ran_or_environment_limited = status == "passed" or (
        status == "not-browser-verified" and verdict.get("reason") in ENVIRONMENT_LIMITS
    )
    passed = bool(checks["passed"]) and ran_or_environment_limited
    browser = status == "passed"
    report = {
        "template": {"name": name, "level": level, "tier": tier, "path": str(tdir)},
        "build": {"size": built["size"], "libraries": built["libraries"], "warnings": built["warnings"]},
        "checks": checks,
        "verify": {k: v for k, v in verdict.items() if k != "screenshots"},
    }
    if passed:
        stamp = {
            "schema": 1,
            "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "browser": browser,
            "hashes": hashes,
        }
        try:
            atomic_write(tdir / "verified.json", json.dumps(stamp, indent=2) + "\n")
        except OSError as exc:
            raise BuildError(f"cannot write {tdir / 'verified.json'}: {exc}") from exc
    return {"passed": passed, "browser": browser, "report": report}

