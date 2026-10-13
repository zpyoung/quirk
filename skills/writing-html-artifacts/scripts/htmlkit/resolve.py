"""Template lookup across the project, user and built-in levels.

Levels are searched in that order and the first *valid* match wins. A match that fails
validation is skipped with a warning and the search continues, so a broken or stale custom
template degrades to the next level instead of blocking a build. Custom levels (project,
user) must carry a matching ``verified.json``; built-ins are trusted.
"""
from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path
from typing import Optional

from .manifest import NAME_RE, ManifestError, Template, load_template, validate_template

LEVELS = ("project", "user", "builtin")


class TemplateNotFound(Exception):
    """No level holds a valid template of that name."""


def default_user_dir() -> Path:
    """``$QUIRK_HTML_USER_DIR`` when set, else ``~/.quirk/html-templates``."""
    env = os.environ.get("QUIRK_HTML_USER_DIR")
    return Path(env) if env else Path.home() / ".quirk" / "html-templates"


def default_project_dir(cwd: Optional[Path] = None) -> Path:
    """The git toplevel of ``cwd`` (default: the current directory), else ``cwd`` itself."""
    base = Path(cwd) if cwd is not None else Path.cwd()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return base
    top = out.stdout.strip()
    return Path(top) if out.returncode == 0 and top else base


def template_roots(
    skill_dir: Path, project_dir: Path, user_dir: Optional[Path] = None
) -> list[tuple[str, Path]]:
    """The directories to search, in precedence order: project, user, built-in."""
    user = Path(user_dir) if user_dir is not None else default_user_dir()
    return [
        ("project", Path(project_dir) / ".quirk" / "html-templates"),
        ("user", user),
        ("builtin", Path(skill_dir) / "templates"),
    ]


def _skill_dir_for(roots: list[tuple[str, Path]], skill_dir: Optional[Path]) -> Optional[Path]:
    if skill_dir is not None:
        return Path(skill_dir)
    for level, root in roots:
        if level == "builtin":
            return root.parent
    return None


def _check(path: Path, level: str, skill_dir: Optional[Path]) -> tuple[Optional[Template], Optional[str]]:
    errors = validate_template(path, require_verified=level != "builtin", skill_dir=skill_dir)
    if errors:
        return None, "; ".join(errors)
    try:
        tpl = load_template(path, skill_dir=skill_dir)
    except ManifestError as exc:
        return None, "; ".join(exc.errors)
    return dataclasses.replace(tpl, level=level), None


def _warning(name: str, level: str, path: Path, reason: str) -> dict:
    return {"name": name, "level": level, "path": str(path), "reason": reason}


def find_template(
    name: str, roots: list[tuple[str, Path]], *, skill_dir: Optional[Path] = None
) -> tuple[Template, list[dict]]:
    """Return the first valid template called ``name`` and a warning per invalid one skipped.

    Raises TemplateNotFound when no level has a valid match; the message lists the skipped
    candidates' reasons. ``skill_dir`` defaults to the parent of the built-in root.
    """
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise TemplateNotFound(f"{name!r} is not a valid template name ([a-z0-9-]{{1,40}})")
    skill = _skill_dir_for(roots, skill_dir)
    warnings: list[dict] = []
    for level, root in roots:
        path = Path(root) / name
        if not path.is_dir():
            continue
        tpl, reason = _check(path, level, skill)
        if tpl is not None:
            return tpl, warnings
        warnings.append(_warning(name, level, path, reason or "invalid"))
    detail = "; ".join(f"{w['level']} {w['path']}: {w['reason']}" for w in warnings)
    raise TemplateNotFound(f"no valid template named {name!r}" + (f" ({detail})" if detail else ""))


def list_templates(
    roots: list[tuple[str, Path]], *, skill_dir: Optional[Path] = None
) -> tuple[list[Template], list[dict]]:
    """Every valid template once (a higher level shadows a lower one), plus skip warnings."""
    skill = _skill_dir_for(roots, skill_dir)
    seen: set[str] = set()
    templates: list[Template] = []
    warnings: list[dict] = []
    for level, root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for path in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if path.name in seen:
                continue
            tpl, reason = _check(path, level, skill)
            if tpl is None:
                warnings.append(_warning(path.name, level, path, reason or "invalid"))
            else:
                seen.add(path.name)
                templates.append(tpl)
    templates.sort(key=lambda t: t.name)
    return templates, warnings
