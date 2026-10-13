"""Tier-2 build: scaffold a Vite and React project from a template, bundle it, and wrap the bundle.

``build_app`` copies the template's ``project/`` and ``example/`` into
``<project>/.quirk/html/<slug>/`` once and never touches that folder again, so edits to the source
survive every rebuild, except ``src/quirk-tokens.css``: every build rewrites it with the merged token
layers (house, user, project, template) that tier 1 applies, and the scaffold's ``theme.css`` imports it.
Each build installs with
``pnpm install --frozen-lockfile --ignore-scripts --ignore-pnpmfile`` and runs ``pnpm run build``.
The install never runs package scripts or pnpmfile hooks, for built-in and custom templates alike.
The build itself runs the template's own build code (``scripts.build`` and ``vite.config.ts``), so
only a template you trust should be built. The bundle (``dist/index.html``) then gets the artifact header, one license comment per
production dependency and its ``<title>`` set to the saved title, and is written to ``<project>/.quirk/html/<slug>.html`` and statically checked.

Problems the author can fix (slug, mode, template, missing title) raise ``BuildError`` and are exit 2
in the CLI. A missing toolchain or a failed install or build raises ``AppUnavailable`` (exit 3),
the signal to write a tier-1 source instead; this module never falls back on its own.
Package installation is the only network access, and it happens inside pnpm.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import SKILL_DIR
from .assemble import BuildError, _quirk_version, _skill_store
from .checks import default_shells, run_checks
from .fsutil import atomic_write, ensure_self_ignoring
from .header import render_header
from .resolve import TemplateNotFound, default_user_dir, find_template, template_roots
from .tokens import merge_tokens, token_layers, tokens_css
from .vendor import _comment_safe

APP_MODES = ("offline", "connected")
DEFAULT_TEMPLATE = "app"
APP_FILE = "quirk-app.json"
TOKENS_FILE = "src/quirk-tokens.css"
STEP_TIMEOUT_S = 600
TAIL_LINES = 40
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}\Z")
_TITLE = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
_COPY_SKIP = shutil.ignore_patterns("node_modules", "dist", ".DS_Store")


class AppUnavailable(Exception):
    """Tier 2 cannot be built here: ``reason`` is no-node, no-pnpm, install-failed or build-failed."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-TAIL_LINES:])


def _pnpm_command() -> list[str]:
    """``pnpm`` when it is on PATH, else ``corepack pnpm``; raises AppUnavailable when neither is."""
    if shutil.which("node") is None:
        raise AppUnavailable("no-node", "node is not on PATH; tier 2 needs Node to build")
    if shutil.which("pnpm"):
        return ["pnpm"]
    if shutil.which("corepack"):
        return ["corepack", "pnpm"]
    raise AppUnavailable("no-pnpm", "neither pnpm nor corepack is on PATH")


def _run(command: list[str], cwd: Path, reason: str) -> None:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=STEP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raise AppUnavailable(reason, _tail(f"{partial}\n{' '.join(command)} timed out after {STEP_TIMEOUT_S} s")) from exc
    except OSError as exc:
        raise AppUnavailable(reason, f"{' '.join(command)}: {exc}") from exc
    if proc.returncode != 0:
        raise AppUnavailable(reason, _tail(proc.stdout) or f"{' '.join(command)} exited {proc.returncode}")


def _read_app_file(path: Path) -> dict:
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise BuildError(f"cannot read {path}: {exc}") from exc
    if not isinstance(saved, dict):
        raise BuildError(f"{path} must hold a JSON object")
    return saved


def _scaffold(template_dir: Path, project_rel: str, example_rel: Optional[str], dest: Path) -> None:
    """Copy ``project/`` then the ``example/`` overlay to ``dest``, atomically, skipping an existing ``dest``."""
    base = Path(template_dir) / project_rel
    staging = dest.with_name(f"{dest.name}.new-{os.getpid()}")
    try:
        shutil.copytree(base, staging, ignore=_COPY_SKIP)
        if example_rel:
            overlay = Path(template_dir) / example_rel
            if not overlay.is_dir():
                raise BuildError(f"template example {example_rel!r} is not a directory")
            shutil.copytree(overlay, staging, ignore=_COPY_SKIP, dirs_exist_ok=True)
        os.rename(staging, dest)
    except OSError as exc:
        raise BuildError(f"cannot create the source folder {dest}: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _licenses(source: Path) -> tuple[dict[str, str], list[str]]:
    """Installed versions and license comments for the source folder's production dependencies."""
    try:
        deps = json.loads((source / "package.json").read_text(encoding="utf-8")).get("dependencies", {})
    except (OSError, ValueError, AttributeError) as exc:
        raise BuildError(f"cannot read {source / 'package.json'}: {exc}") from exc
    versions: dict[str, str] = {}
    comments: list[str] = []
    for name in sorted(deps):
        installed = source / "node_modules" / name / "package.json"
        try:
            meta = json.loads(installed.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AppUnavailable("install-failed", f"{name} is listed in package.json but {installed} is unreadable: {exc}") from exc
        version = str(meta.get("version", "unknown"))
        license_id = meta.get("license")
        if isinstance(license_id, dict):
            license_id = license_id.get("type")
        license_id = license_id if isinstance(license_id, str) and license_id else "UNKNOWN"
        versions[name] = version
        comments.append(f"<!-- license: {_comment_safe(name)} {_comment_safe(version)} {_comment_safe(license_id)} -->")
    return versions, comments


def build_app(
    slug: str,
    *,
    title: Optional[str],
    mode: Optional[str],
    signal: Optional[str],
    template_name: Optional[str],
    upgrade: bool,
    project_dir: Path,
    user_dir: Optional[Path],
    skill_dir: Optional[Path] = None,
) -> dict:
    """Build the tier-2 app ``slug`` and return a ``BuildResult`` dict (see tech.md section 4.1).

    ``title``, ``mode``, ``signal`` and ``template_name`` come from ``quirk-app.json`` in the
    source folder when ``None``; a value given overrides the saved one and is saved. The first
    build needs a title. ``upgrade`` has no effect on tier 2 because ``pnpm-lock.yaml`` pins every
    version; it adds a warning saying so. The source folder is created only when absent.

    Raises BuildError for an invalid slug, mode or template, or a missing title; AppUnavailable
    when Node or pnpm is missing or an install or build fails; a failed static check is reported
    in ``checks`` and still leaves the bundle written.
    """
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    project_dir = Path(project_dir)
    user = Path(user_dir) if user_dir is not None else default_user_dir()
    if not _SLUG.match(slug):
        raise BuildError(f"slug {slug!r} must match [a-z0-9-] and start with a letter or digit (at most 61 characters)")

    html_dir = project_dir / ".quirk" / "html"
    source = html_dir / slug
    saved = _read_app_file(source / APP_FILE)
    settings = {
        "template": template_name or saved.get("template") or DEFAULT_TEMPLATE,
        "title": title if title is not None else saved.get("title"),
        "mode": mode or saved.get("mode") or "offline",
        "tier_signal": signal if signal is not None else saved.get("tier_signal"),
    }
    if not isinstance(settings["title"], str) or not settings["title"].strip():
        raise BuildError("--title is required on the first build of an app")
    if settings["mode"] not in APP_MODES:
        raise BuildError(f"mode must be offline or connected, got {settings['mode']!r}")
    if not isinstance(settings["tier_signal"], (str, type(None))):
        raise BuildError(f"{APP_FILE} tier_signal must be a string")

    try:
        template, skipped = find_template(settings["template"], template_roots(skill, project_dir, user), skill_dir=skill)
    except TemplateNotFound as exc:
        raise BuildError(str(exc)) from exc
    if template.tier != 2:
        raise BuildError(f"template {template.name!r} is tier 1; write a .src.html and build it with build")
    warnings = [
        f"template {w['name']!r} at {w['level']} level was skipped ({w['path']}): {w['reason']}" for w in skipped
    ]
    if upgrade:
        warnings.append("--upgrade has no effect on tier 2: pnpm-lock.yaml pins every dependency version")

    pnpm = _pnpm_command()

    try:
        ensure_self_ignoring(html_dir)
    except OSError as exc:
        raise BuildError(f"cannot write the build output under {html_dir}: {exc}") from exc
    if not source.exists():
        _scaffold(template.dir, template.project or "project/", template.example, source)
    try:
        atomic_write(source / APP_FILE, json.dumps(settings, indent=2) + "\n")
    except OSError as exc:
        raise BuildError(f"cannot write {source / APP_FILE}: {exc}") from exc

    try:
        css = tokens_css(merge_tokens(token_layers(skill, user, project_dir, template)))
        (source / TOKENS_FILE).parent.mkdir(parents=True, exist_ok=True)
        atomic_write(source / TOKENS_FILE, css)
    except ValueError as exc:
        raise BuildError(str(exc)) from exc
    except OSError as exc:
        raise BuildError(f"cannot write {source / TOKENS_FILE}: {exc}") from exc

    _run([*pnpm, "install", "--frozen-lockfile", "--ignore-scripts", "--ignore-pnpmfile"], source, "install-failed")
    dist = source / "dist" / "index.html"
    dist.unlink(missing_ok=True)
    _run([*pnpm, "run", "build"], source, "build-failed")
    try:
        bundle = dist.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AppUnavailable("build-failed", f"the build did not produce a readable dist/index.html: {exc}") from exc
    doctype, newline, rest = bundle.partition("\n")
    if not doctype.strip().lower().startswith("<!doctype html") or not newline:
        raise AppUnavailable("build-failed", "dist/index.html must start with a doctype line")

    versions, licenses = _licenses(source)
    meta = {
        "schema": 1,
        "template": template.name,
        "template_level": template.level,
        "tier": 2,
        "tier_signal": settings["tier_signal"],
        "mode": settings["mode"],
        "libraries": versions,
        "sidecar": None,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quirk_version": _quirk_version(skill),
    }
    first_script = rest.find("<script")
    found = _TITLE.search(rest)
    if found and (first_script < 0 or found.start() < first_script):
        rest = f"{rest[: found.start()]}<title>{html_lib.escape(settings['title'])}</title>{rest[found.end():]}"
    page = "\n".join([doctype, render_header(meta), *licenses]) + "\n" + rest
    out_path = html_dir / f"{slug}.html"
    try:
        page_size = len(page.encode("utf-8"))
        atomic_write(out_path, page)
    except UnicodeEncodeError as exc:
        raise BuildError(f"the page contains a character UTF-8 cannot encode: {exc}") from exc
    except OSError as exc:
        raise BuildError(f"cannot write the build output under {html_dir}: {exc}") from exc

    checks = run_checks(
        page, mode=settings["mode"], tier=2, vendor=_skill_store(skill, template.dir), shells=default_shells(skill)
    )
    return {
        "path": str(out_path),
        "size": page_size,
        "sidecar": None,
        "source_dir": str(source),
        "template": template.name,
        "template_level": template.level,
        "tier": 2,
        "tier_signal": settings["tier_signal"],
        "mode": settings["mode"],
        "libraries": versions,
        "warnings": warnings,
        "checks": checks,
        "cut": [],
    }
