"""Shared primitives for filing-requests scripts: JSON I/O, schema versioning, slugs, and the
per-type field cores. No CLI surface -- every other script in the skill imports from here.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1

CORE_FIELDS = {
    "bug": ["current_behavior", "expected_behavior", "steps_to_reproduce", "environment"],
    "feature": ["problem", "who_benefits", "current_behavior", "acceptance_criteria"],
    "code-change": ["scope", "why_now", "blast_radius"],
}

OPTIONAL_FIELDS = {
    "bug": ["stack_trace", "frequency", "regression_range", "workaround"],
    "feature": ["value_or_impact", "constraints", "out_of_scope", "prior_art"],
    "code-change": ["migration", "rollback", "test_plan", "perf_impact"],
}

NON_WAIVABLE = {
    "feature": ["problem", "acceptance_criteria"],
}

# tech.md -> markdown_render.py -> "the exact wording of the hedge prefix, the attribution line,
# the headless banner, and the disclosure footer is fixed in _common.py as four module-level
# string constants". They are asserted verbatim in tests, so a wording change is a deliberate
# edit with a failing test behind it, not drift.
HEDGE_PREFIX = "Inferred, not directly confirmed — "
ATTRIBUTION_LINE = "*Proposed by the reporter, included as an open suggestion rather than a directive.*"
HEADLESS_BANNER = "> **Headless run: no human confirmed this artifact.**"
DISCLOSURE_FOOTER = "*This report was drafted with AI assistance.*"

_SLUG_COLLAPSE = re.compile(r"[^a-z0-9]+")


class SchemaVersionError(Exception):
    """Raised when a document's schema_version exceeds CURRENT_SCHEMA_VERSION."""


def read_json_arg(path_or_dash: str) -> dict:
    """Read and parse a canonical JSON document from a file path, or stdin when given "-".

    Raises OSError for an unreadable path and json.JSONDecodeError for malformed content --
    callers map both to the shared exit code 2 (usage error).
    """
    if path_or_dash == "-":
        text = sys.stdin.read()
    else:
        text = Path(path_or_dash).read_text(encoding="utf-8")
    return json.loads(text)


def slugify(text: str, sep: str = "-") -> str:
    """Lowercase `text`, collapse non-alphanumeric runs to `sep`, trim, cap at 60 chars."""
    slug = _SLUG_COLLAPSE.sub(sep, text.lower()).strip(sep)
    return slug[:60].rstrip(sep)


def check_schema_version(doc: dict) -> None:
    """Raise SchemaVersionError if `doc`'s schema_version exceeds CURRENT_SCHEMA_VERSION.

    A missing schema_version is not this function's concern -- that's a structural
    validation error (canonical_schema.validate), not a forward-compatibility one.
    """
    if not isinstance(doc, dict):
        return
    version = doc.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool) and version > CURRENT_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"schema_version {version} exceeds CURRENT_SCHEMA_VERSION {CURRENT_SCHEMA_VERSION}"
        )
