#!/usr/bin/env python3
"""Append an entry to a typed-artifact markdown file."""
from __future__ import annotations

import argparse
import fcntl
import os
import sys
import time
from datetime import date
from pathlib import Path

from artifact_lib import (
    detect_schema_version,
    ensure_lock_dir,
    find_max_id,
    render_entry,
)

SCHEMAS: dict[str, dict] = {
    "bug": {
        "header": "BUG",
        "file": "BUGS.md",
        "required": ["title", "file", "description", "severity"],
        "fields": [
            "title", "observed", "file", "description",
            "introduced_by", "severity", "proposed_fix", "blocker_for",
            "blocked_by",
        ],
        "labels": {
            "observed": "Observed",
            "file": "File",
            "description": "Description",
            "introduced_by": "Introduced by",
            "severity": "Severity",
            "proposed_fix": "Proposed fix",
            "blocker_for": "Blocker for",
            "blocked_by": "Blocked by",
        },
        "v2_fields": ("blocked_by",),
    },
    "defer": {
        "header": "DEFER",
        "file": "DEFERRED.md",
        "required": ["title", "why_deferred", "priority"],
        "fields": [
            "title", "deferred", "session_context", "why_deferred",
            "estimated_effort", "priority", "proposed_owner",
            "blocked_by",
        ],
        "labels": {
            "deferred": "Deferred",
            "session_context": "Session context",
            "why_deferred": "Why deferred",
            "estimated_effort": "Estimated effort",
            "priority": "Priority",
            "proposed_owner": "Proposed owner",
            "blocked_by": "Blocked by",
        },
        "v2_fields": ("blocked_by",),
    },
    "test-skip": {
        "header": "TEST",
        "file": "TEST_BACKLOG.md",
        "required": ["title", "file_under_test", "reason_skipped"],
        "fields": [
            "title", "logged", "file_under_test", "test_type", "reason_skipped",
            "edge_cases", "priority", "blocked_by",
        ],
        "labels": {
            "logged": "Logged",
            "file_under_test": "File under test",
            "test_type": "Test type",
            "reason_skipped": "Reason skipped",
            "edge_cases": "Edge cases to cover",
            "priority": "Priority",
            "blocked_by": "Blocked by",
        },
        "v2_fields": ("blocked_by", "logged"),
    },
    "proposal": {
        "header": "PROPOSAL",
        "file": "proposals.md",
        "required": ["title", "context", "recommendation"],
        "fields": [
            "title", "proposed", "context", "options_considered",
            "recommendation", "decision_required_from", "status",
        ],
        "labels": {
            "proposed": "Proposed",
            "context": "Context",
            "options_considered": "Options considered",
            "recommendation": "Recommendation",
            "decision_required_from": "Decision required from",
            "status": "Status",
        },
        "v2_fields": (),
    },
}

EXPECTED_SCHEMA_VERSION = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append to a typed-artifact file.")
    parser.add_argument("type", help="Artifact type")
    parser.add_argument("--field", action="append", default=[],
                        help="Field as key=value (repeatable)")
    parser.add_argument("--project-dir", default=".",
                        help="Project root containing artifact files")
    args = parser.parse_args(argv)

    if args.type not in SCHEMAS:
        valid = ", ".join(sorted(SCHEMAS.keys()))
        print(f"Unknown type {args.type!r}. Valid: {valid}", file=sys.stderr)
        return 2

    schema = SCHEMAS[args.type]

    fields: dict[str, str] = {}
    for raw in args.field:
        if "=" not in raw:
            print(f"Bad --field {raw!r}: expected key=value", file=sys.stderr)
            return 2
        key, value = raw.split("=", 1)
        if key not in schema["fields"]:
            valid = ", ".join(schema["fields"])
            print(f"Unknown field {key!r} for {args.type}. Valid: {valid}", file=sys.stderr)
            return 2
        fields[key] = value

    missing = [k for k in schema["required"] if k not in fields]
    if missing:
        print(
            f"Missing required field: {', '.join(missing)}. "
            f"See schema in templates/{schema['file']}.",
            file=sys.stderr,
        )
        return 2

    project = Path(args.project_dir).resolve()
    target = project / schema["file"]

    if not target.exists():
        print(
            f"{schema['file']} not found in {project}. "
            f"Run /quirk:artifacts:init first.",
            file=sys.stderr,
        )
        return 3

    lock_path = ensure_lock_dir(project) / f"{schema['file']}.lock"
    timeout = float(os.environ.get("ARTIFACT_LOCK_TIMEOUT", "5.0"))
    deadline = time.monotonic() + timeout
    with open(lock_path, "w") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    print(
                        f"Could not acquire lock on {lock_path.name}. Retry.",
                        file=sys.stderr,
                    )
                    return 5
                time.sleep(0.05)

        text = target.read_text()
        version = detect_schema_version(text)
        if version is not None and version > EXPECTED_SCHEMA_VERSION:
            print(
                f"Schema v{version} file, plugin understands v{EXPECTED_SCHEMA_VERSION}. "
                "Upgrade quirk.",
                file=sys.stderr,
            )
            return 8

        # absent marker is legacy v1, the same convention `migrate` uses, so a v2-only
        # field is refused here rather than silently written where a v1 reader can't see it
        effective_version = version if version is not None else 1
        if effective_version < EXPECTED_SCHEMA_VERSION:
            requested_v2 = [k for k in schema.get("v2_fields", ()) if k in fields]
            if requested_v2:
                print(
                    f"Field {requested_v2[0]!r} needs schema v{EXPECTED_SCHEMA_VERSION}, "
                    f"this file is v{effective_version}. Run /quirk:pm:migrate.",
                    file=sys.stderr,
                )
                return 8

        next_id = find_max_id(text, schema["header"]) + 1

        if "observed" in schema["fields"] and "observed" not in fields:
            fields["observed"] = date.today().isoformat()
        if "deferred" in schema["fields"] and "deferred" not in fields:
            fields["deferred"] = date.today().isoformat()
        if "proposed" in schema["fields"] and "proposed" not in fields:
            fields["proposed"] = date.today().isoformat()
        if "logged" in schema["fields"] and "logged" not in fields:
            fields["logged"] = date.today().isoformat()

        entry = render_entry(schema, next_id, fields, schema_version=effective_version)
        new_text = text.rstrip() + "\n\n" + entry + "\n"
        target.write_text(new_text)

        print(f"{schema['header']}-{next_id}: {fields.get('title', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
