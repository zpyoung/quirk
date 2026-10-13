"""Design tokens: merge the layered token files and emit them as CSS custom properties.

Layers merge house, then user, then project, then the template, later winning per key within
each group. Colors are always ``[light, dark]`` pairs; the CSS defines light values on
``:root`` and dark values twice, once for the OS preference (unless the user forced light)
and once for an explicit ``data-theme="dark"``.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .manifest import Template

GROUPS = ("color", "font", "size", "space", "radius")
_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_UNSAFE_VALUE = re.compile(r"[;{}<>\\]|url\s*\(|@import|/\*", re.IGNORECASE)


def validate_tokens(tokens: dict) -> list[str]:
    """Return every problem found in one token layer or merged set; empty means valid."""
    errors: list[str] = []
    if not isinstance(tokens, dict):
        return ["tokens must be a JSON object"]
    if "schema" in tokens and tokens["schema"] != 1:
        errors.append(f"tokens schema must be 1, got {tokens['schema']!r}")
    for group, entries in tokens.items():
        if group == "schema":
            continue
        if group not in GROUPS:
            errors.append(f"unknown token group {group!r}")
            continue
        if not isinstance(entries, dict):
            errors.append(f"token group {group!r} must be an object")
            continue
        for key, value in entries.items():
            where = f"{group}.{key}"
            if not isinstance(key, str) or not _KEY.match(key):
                errors.append(f"token key {where!r} must match [a-z0-9-]")
                continue
            if group == "color":
                if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value)):
                    errors.append(f"color {where!r} must be a [light, dark] pair of strings")
                    continue
                values = value
            else:
                if not isinstance(value, str):
                    errors.append(f"token {where!r} must be a string")
                    continue
                values = [value]
            for v in values:
                if not v.strip() or _UNSAFE_VALUE.search(v):
                    errors.append(f"token {where!r} has an empty or unsafe value {v!r}")
    return errors


def merge_tokens(layers: list[dict]) -> dict:
    """Merge token layers, later layers winning per key within each group.

    Raises ValueError when any layer is invalid (for example a color that is not a
    two-item list). Inputs are not mutated.
    """
    merged: dict[str, Any] = {"schema": 1}
    for layer in layers:
        errors = validate_tokens(layer)
        if errors:
            raise ValueError("; ".join(errors))
        for group in GROUPS:
            if group in layer:
                merged.setdefault(group, {}).update(copy.deepcopy(layer[group]))
    return merged


def _declarations(entries: dict, group: str, index: Optional[int]) -> list[str]:
    lines = []
    for key, value in entries.items():
        chosen = value[index] if index is not None else value
        lines.append(f"  --q-{group}-{key}: {chosen};")
    return lines


def tokens_css(tokens: dict) -> str:
    """Render tokens as ``--q-<group>-<key>`` custom properties for light and dark.

    Raises ValueError for an invalid token set. Only colors differ between light and dark.
    """
    errors = validate_tokens(tokens)
    if errors:
        raise ValueError("; ".join(errors))
    light: list[str] = []
    for group in GROUPS:
        entries = tokens.get(group, {})
        light.extend(_declarations(entries, group, 0 if group == "color" else None))
    dark = _declarations(tokens.get("color", {}), "color", 1)

    def block(selector: str, lines: list[str]) -> str:
        return selector + " {\n" + "\n".join(lines) + "\n}\n"

    parts = [block(":root", light)]
    if dark:
        indented = "\n".join("  " + line for line in dark)
        parts.append(
            "@media (prefers-color-scheme: dark) {\n"
            + '  :root:not([data-theme="light"]) {\n'
            + indented
            + "\n  }\n}\n"
        )
        parts.append(block(':root[data-theme="dark"]', dark))
    return "".join(parts)


def _load_layer(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read tokens file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"tokens file {path} must hold a JSON object")
    return data


def token_layers(
    skill_dir: Path,
    user_dir: Optional[Path],
    project_dir: Optional[Path],
    template: "Optional[Template]",
) -> list[dict]:
    """Load the token layers in merge order, skipping files that do not exist.

    Order: the skill's house tokens, ``<user_dir>/tokens.json``,
    ``<project_dir>/.quirk/html-templates/tokens.json``, then the template's own tokens file.
    """
    candidates = [Path(skill_dir) / "theme" / "house.tokens.json"]
    if user_dir is not None:
        candidates.append(Path(user_dir) / "tokens.json")
    if project_dir is not None:
        candidates.append(Path(project_dir) / ".quirk" / "html-templates" / "tokens.json")
    if template is not None and template.tokens:
        candidates.append(Path(template.dir) / template.tokens)
    layers = []
    for path in candidates:
        layer = _load_layer(path)
        if layer is not None:
            layers.append(layer)
    return layers
