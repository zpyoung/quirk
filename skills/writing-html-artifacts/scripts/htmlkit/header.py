"""The artifact header: one HTML comment on line 2 recording how a built file was made.

The header is what lets a rebuild reuse the same library versions and lets ``check`` and
``note`` tell what produced a file. ``--`` inside a JSON string is written as ``-\\u002d``
so the comment can never close early, and ``json.loads`` reads it back unchanged.
"""
from __future__ import annotations

import json
import re
from typing import Optional

PREFIX = "<!-- quirk-html-artifact "
SUFFIX = " -->"
_LINE = re.compile(r"^<!-- quirk-html-artifact (\{.*\}) -->\s*$")


def render_header(meta: dict) -> str:
    """Return the single-line header comment for ``meta``."""
    payload = json.dumps(meta, ensure_ascii=True, separators=(", ", ": "))
    return PREFIX + payload.replace("--", "-\\u002d") + SUFFIX


def read_header(html: str) -> Optional[dict]:
    """Parse the header from a built file; None when it is missing or not a JSON object.

    The header must be the line right after the doctype, as ``render_header`` output is
    placed by the builder.
    """
    lines = html.lstrip("﻿").split("\n", 2)
    if len(lines) < 2 or not lines[0].strip().lower().startswith("<!doctype html"):
        return None
    match = _LINE.match(lines[1])
    if not match:
        return None
    try:
        meta = json.loads(match.group(1))
    except ValueError:
        return None
    return meta if isinstance(meta, dict) else None
