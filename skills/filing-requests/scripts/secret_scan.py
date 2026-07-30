#!/usr/bin/env python3
"""Scan a filing-requests canonical JSON document for hardcoded secrets before emission.

Invoked directly by filename; there is no separate console-script entry point.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# loaded both as `python3 .../secret_scan.py` (sys.path[0] is already this directory)
# and via importlib file-path loading in tests (which doesn't set sys.path at all) -- make
# the sibling import to _common work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _common import SchemaVersionError, check_schema_version, read_json_arg  # noqa: E402

# v1 starter set (tech.md -> secret_scan.py -> REGEX:); expanding this is a script change,
# never a schema change.
_PATTERNS = (
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("github_oauth_token", re.compile(r"gh[oprsu]_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    ("private_key_block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("connection_string_credential", re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:]+:[^/\s@]+@")),
    ("generic_assignment", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
)


def _redact(match_text: str) -> str:
    """First 4 + last 4 characters with an ellipsis between -- never the full secret."""
    return f"{match_text[:4]}…{match_text[-4:]}"


def _scan_string(text: str, path: str, findings: list) -> None:
    for name, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            findings.append({
                "path": path,
                "pattern": name,
                "match": _redact(m.group(0)),
                "span": [m.start(), m.end()],
            })


def scan(doc) -> list:
    """Scan every string `doc` will render into an emitted artifact for secrets.

    Scope-by-output (logic.md -> Data flow): fields[].value, title, proposed_solution.value,
    verified_against[] entries, and fields[].reason -- every locator that can appear in the
    rendered issue. Malformed shapes are skipped, not raised; schema structure is
    canonical_schema.py's concern, not this script's.
    """
    findings: list = []
    if not isinstance(doc, dict):
        return findings

    title = doc.get("title")
    if isinstance(title, str):
        _scan_string(title, "title", findings)

    fields = doc.get("fields")
    if isinstance(fields, list):
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                continue
            value = field.get("value")
            if isinstance(value, str):
                _scan_string(value, f"fields[{i}].value", findings)
            reason = field.get("reason")
            if isinstance(reason, str):
                _scan_string(reason, f"fields[{i}].reason", findings)

    proposed_solution = doc.get("proposed_solution")
    if isinstance(proposed_solution, dict):
        value = proposed_solution.get("value")
        if isinstance(value, str):
            _scan_string(value, "proposed_solution.value", findings)

    verified_against = doc.get("verified_against")
    if isinstance(verified_against, list):
        for i, entry in enumerate(verified_against):
            if isinstance(entry, str):
                _scan_string(entry, f"verified_against[{i}]", findings)

    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan a filing-requests canonical JSON document for hardcoded secrets.",
    )
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    try:
        doc = read_json_arg(args.input)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        check_schema_version(doc)
    except SchemaVersionError as exc:
        print(str(exc), file=sys.stderr)
        return 8

    findings = scan(doc)
    print(json.dumps(findings, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
