#!/usr/bin/env python3
"""Score a finished review report against the comments a human reviewer left on the same MR head.

The answer key lists each human comment as a defect with file anchors and keywords. A comment
counts as caught when some reported finding overlaps one of its anchors and mentions one of its
keywords; a finding that only overlaps the anchor counts as partial. Any severity matches,
because human reviewers file nits too. Exit 0 when recall meets `--min-recall`, 1 when it does
not, and 2 on invalid input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

_LINE = re.compile(r"^\s*([0-9]+)(?:\s*-\s*([0-9]+))?\s*$")
_TEXT_FIELDS = ("title", "issue", "impact", "fix_md", "recommendation", "recommendation_md", "body_md")


def _line_span(value: object) -> tuple[int, int]:
    match = _LINE.match(str(value or ""))
    if not match:
        raise ValueError("unparseable line %r" % (value,))
    start = int(match.group(1))
    return start, int(match.group(2) or start)


def _validate_key(key: dict) -> None:
    if key.get("schema_version") != 1:
        raise ValueError("answer key schema_version must be 1")
    target = key.get("target")
    if not isinstance(target, dict) or not all(target.get(f) for f in ("project", "number", "head_sha")):
        raise ValueError("answer key target needs project, number and head_sha")
    defects = key.get("defects")
    if not isinstance(defects, list) or not defects:
        raise ValueError("answer key defects must be a non-empty list")
    seen = set()
    for defect in defects:
        identifier = defect.get("id")
        if not identifier or identifier in seen:
            raise ValueError("defect ids must be present and unique: %r" % (identifier,))
        seen.add(identifier)
        anchors = defect.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            raise ValueError("%s needs at least one anchor" % identifier)
        for anchor in anchors:
            if not anchor.get("file") or not 0 < anchor.get("line_min", 0) <= anchor.get("line_max", 0):
                raise ValueError("%s has an invalid anchor %r" % (identifier, anchor))
        keywords = defect.get("keywords")
        if not isinstance(keywords, list) or not keywords or not all(isinstance(k, str) and k for k in keywords):
            raise ValueError("%s needs a non-empty keywords list" % identifier)


def _overlaps(finding: dict, anchor: dict) -> bool:
    if str(finding.get("file") or "").strip() != anchor["file"]:
        return False
    try:
        start, end = _line_span(finding.get("line"))
    except ValueError:
        return False
    return start <= anchor["line_max"] and anchor["line_min"] <= end


def _mentions(finding: dict, keywords: list[str]) -> bool:
    text = " ".join(str(finding.get(field) or "") for field in _TEXT_FIELDS).casefold()
    return any(word.casefold() in text for word in keywords)


def score(report: dict, key: dict) -> dict:
    """Return caught, partial and missed human comments for one report."""
    _validate_key(key)
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report.findings must be a list")
    meta = report.get("meta") or {}
    target = key["target"]
    target_matches = (
        meta.get("project") == target["project"]
        and meta.get("iid") == target["number"]
        and str(meta.get("head_sha") or "").startswith(target["head_sha"])
    )
    caught, partial, missed = [], [], []
    for defect in key["defects"]:
        located = [f for f in findings if any(_overlaps(f, a) for a in defect["anchors"])]
        hits = [f for f in located if _mentions(f, defect["keywords"])]
        row = {"defect_id": defect["id"], "title": defect.get("title", "")}
        if hits:
            caught.append(dict(row, finding_ids=[f.get("id") for f in hits]))
        elif located:
            partial.append(dict(row, finding_ids=[f.get("id") for f in located]))
        else:
            missed.append(row)
    total = len(key["defects"])
    return {
        "target_matches": target_matches,
        "total": total,
        "caught_count": len(caught),
        "partial_count": len(partial),
        "missed_count": len(missed),
        "recall": len(caught) / total,
        "caught": caught,
        "partial": partial,
        "missed": missed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a review report against a human reviewer's comments.")
    parser.add_argument("--report", required=True, help="review report JSON (report.json or its memory copy)")
    parser.add_argument("--answer-key", required=True, help="human-review answer key JSON")
    parser.add_argument("--min-recall", type=float, default=0.0, help="fail (exit 1) below this recall")
    args = parser.parse_args(argv)
    try:
        with open(args.report, encoding="utf-8") as fh:
            report = json.load(fh)
        with open(args.answer_key, encoding="utf-8") as fh:
            key = json.load(fh)
        result = score(report, key)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    if not result["target_matches"]:
        print(json.dumps({"ok": False, "error": "report targets a different MR or head than the answer key"}))
        return 2
    passed = result["recall"] >= args.min_recall
    print(json.dumps(dict(result, ok=True, passed=passed), indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
