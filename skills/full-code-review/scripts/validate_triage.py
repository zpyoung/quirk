#!/usr/bin/env python3
"""Validate a complete HTML triage export against the trusted report JSON."""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_report  # noqa: E402
import review_memory  # noqa: E402
from forge import change_label  # noqa: E402

GROUPS = {
    "author": [("fix", "Will fix"), ("later", "Fix later"),
               ("detail", "Needs detail"), ("ignore", "Ignore"),
               ("none", "Undecided")],
    "reviewer": [("fix", "Blocking"), ("later", "Non-blocking"),
                 ("detail", "Question"), ("ignore", "Drop"),
                 ("none", "Undecided")],
}
GROUP_RE = re.compile(r"^## (Will fix|Fix later|Needs detail|Ignore|Blocking|Non-blocking|Question|Drop|Undecided) \((\d+)\)$")
ITEM_RE = re.compile(r"^- \*\*(F\d+)\*\* — (.+?)\s*$")
ANCHOR_RE = re.compile(r"^  `(.+)` · (Must fix|Should fix|Nit)$")
NOTE_RE = re.compile(r"^  > (.*)$")
REPLY_RE = re.compile(r"^  reply: ([1-9][0-9]{0,18})$")
HANDOFF_DELIM = "<!-- quirk-review handoff: not validated, not used for posting -->"


def export_label(meta):
    if meta["target"] == "change":
        return change_label(meta["forge"], meta["number"])
    if meta["target"] == "branch":
        return meta["branch"]
    return "local changes"


def export_header(meta):
    seat = meta.get("seat", "author")
    return "# %s — triage decisions [mode: %s]" % (export_label(meta), seat)


def expected_order(prepared):
    return {
        finding["id"]: {
            "file": finding["file"], "line": finding["line"],
            "severity": finding["severity"], "title": finding["title"],
            "open_threads": {entry["note_id"] for entry in render_report.open_human_threads(finding)},
        }
        for finding in prepared["findings"]
    }


def parse_export(text, prepared):
    """Parse and validate the entire export; return normalized slot decisions."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("a complete triage paste is required")
    if "\u2028" in text or "\u2029" in text or "\r" in text:
        raise ValueError("paste contains a non-canonical line separator")
    meta = prepared["meta"]
    seat = meta.get("seat", "author")
    if seat not in GROUPS:
        raise ValueError("report seat must be author or reviewer")
    lines = text.split("\n")
    handoff_present = HANDOFF_DELIM in lines
    if handoff_present:
        lines = lines[:lines.index(HANDOFF_DELIM)]
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != export_header(meta):
        raise ValueError("triage header target or mode does not match this review")
    index = 1
    if index >= len(lines) or lines[index] != "":
        raise ValueError("triage header must be followed by a blank line")
    index += 1
    seen = {}
    parsed_groups = []
    for slot, label in GROUPS[seat]:
        if index >= len(lines):
            raise ValueError("missing triage group %s" % label)
        match = GROUP_RE.match(lines[index])
        if not match or match.group(1) != label:
            raise ValueError("expected triage group %s in canonical order" % label)
        declared = int(match.group(2))
        parsed_groups.append(label)
        index += 1
        if index >= len(lines) or lines[index] != "":
            raise ValueError("group %s must be followed by a blank line" % label)
        index += 1
        count = 0
        while index < len(lines) and not lines[index].startswith("## "):
            if lines[index] == "":
                index += 1
                continue
            item_match = ITEM_RE.match(lines[index])
            if not item_match:
                raise ValueError("unrecognized line in %s: %s" % (label, lines[index]))
            finding_id = item_match.group(1)
            if finding_id in seen:
                raise ValueError("duplicate finding ID %s" % finding_id)
            pasted_title = item_match.group(2).rstrip()
            index += 1
            if index >= len(lines):
                raise ValueError("finding %s is missing its anchor" % finding_id)
            anchor_match = ANCHOR_RE.match(lines[index])
            if not anchor_match:
                raise ValueError("finding %s has an invalid anchor line" % finding_id)
            anchor, severity = anchor_match.groups()
            index += 1
            reply_note_id = None
            if index < len(lines) and lines[index].startswith("  reply:"):
                reply_match = REPLY_RE.match(lines[index])
                if not reply_match:
                    raise ValueError("finding %s has an invalid reply line" % finding_id)
                reply_note_id = int(reply_match.group(1))
                index += 1
            notes = []
            while index < len(lines) and lines[index].startswith("  > "):
                note_match = NOTE_RE.match(lines[index])
                if not note_match:
                    raise ValueError("finding %s has an invalid note line" % finding_id)
                notes.append(note_match.group(1))
                index += 1
            seen[finding_id] = {
                "id": finding_id, "slot": slot, "disposition": label,
                "anchor": anchor, "severity": severity,
                "note": "\n".join(notes), "pasted_title": pasted_title,
            }
            if reply_note_id is not None:
                seen[finding_id]["reply_note_id"] = reply_note_id
            count += 1
        if count != declared:
            raise ValueError("group %s declares %d items but contains %d" % (label, declared, count))
    if index != len(lines):
        raise ValueError("unrecognized trailing content in triage paste")

    order = expected_order(prepared)
    missing = sorted(set(order) - set(seen))
    unknown = sorted(set(seen) - set(order))
    if missing or unknown:
        raise ValueError("finding ID set mismatch (missing: %s; unknown: %s)" %
                         (", ".join(missing) or "none", ", ".join(unknown) or "none"))
    for finding_id, decision in seen.items():
        trusted = order[finding_id]
        expected_anchor = "%s:%s" % (trusted["file"], trusted["line"])
        if decision["anchor"] != expected_anchor:
            raise ValueError("anchor mismatch for %s" % finding_id)
        if decision["severity"] != trusted["severity"]:
            raise ValueError("severity mismatch for %s" % finding_id)
        reply_note_id = decision.get("reply_note_id")
        if reply_note_id is not None:
            if seat != "reviewer":
                raise ValueError("reply line is only valid in reviewer mode (%s)" % finding_id)
            if reply_note_id not in trusted["open_threads"]:
                raise ValueError("reply target for %s is not an unresolved thread on this finding"
                                 % finding_id)
    return {
        "schema": 1,
        "seat": seat,
        "header": lines[0],
        "target": export_label(meta),
        "head_sha": meta.get("head_sha"),
        "groups": parsed_groups,
        "decisions": [seen[finding_id] for finding_id in order],
        "handoff_present": handoff_present,
    }


_report_sha256 = review_memory._report_digest


def validate(report, paste):
    prepared, warnings = render_report._prepare_report(report)
    result = parse_export(paste, prepared)
    result["report_sha256"] = _report_sha256(report)
    result["warnings"] = warnings
    return result


def validate_zero_findings(report):
    """Create the only paste-free reviewer decision artifact: an empty clean review."""
    prepared, warnings = render_report._prepare_report(report)
    if prepared["meta"].get("seat") != "reviewer":
        raise ValueError("--zero-findings is only valid in reviewer mode")
    if prepared["findings"]:
        raise ValueError("--zero-findings requires a report with no findings")
    return {
        "schema": 1,
        "seat": "reviewer",
        "header": export_header(prepared["meta"]),
        "target": export_label(prepared["meta"]),
        "head_sha": prepared["meta"].get("head_sha"),
        "groups": [label for _, label in GROUPS["reviewer"]],
        "decisions": [],
        "report_sha256": _report_sha256(report),
        "warnings": warnings,
        "zero_findings": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a complete review triage paste.")
    parser.add_argument("--report", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--paste")
    source.add_argument("--zero-findings", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        with open(args.report, encoding="utf-8") as fh:
            report = json.load(fh)
        if args.zero_findings:
            result = validate_zero_findings(report)
        else:
            with open(args.paste, encoding="utf-8", newline="") as fh:
                paste = fh.read()
            result = validate(report, paste)
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            with open(args.out + ".tmp", "w", encoding="utf-8") as fh:
                fh.write(encoded)
            os.replace(args.out + ".tmp", args.out)
        print(encoded, end="")
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
