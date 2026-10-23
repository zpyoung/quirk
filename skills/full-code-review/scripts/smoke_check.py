#!/usr/bin/env python3
"""Check one smoke-corpus review: did the expected lens catch the planted bug?

Pass when some Must or Should finding carries the expected lens, names the expected
file, and has a line range overlapping [line_min, line_max]. Two optional expected.json
keys tighten or invert that:

  "recommendation_contains": "<marker>"  the matching finding's recommendation_md or
      recommendation must also contain the marker (only the correct fix has it).
  "absent": true  planted false positive: pass only when NO Must or Should finding, from
      any lens and with any adjudication outcome (Disputed included), names the file
      with an overlapping range. The lens key is not used for matching.

When the report's run.adjudication.status is "complete", a non-absent case's matching
finding must also carry a production statement. Exit 0 pass, 1 miss (printing what was
found instead, or for an absent case the offending findings), 2 bad input.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jsonio import load_object  # noqa: E402

POSTABLE = ("Must fix", "Should fix")


def _range(line):
    match = re.match(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s*$", str(line))
    if not match:
        return None
    start = int(match.group(1))
    return start, int(match.group(2) or start)


def _lenses(finding):
    lenses = finding.get("dimensions") or []
    if finding.get("dimension"):
        lenses = list(lenses) + [finding["dimension"]]
    return set(lenses)


def _overlaps(finding, expected):
    span = _range(finding.get("line"))
    return bool(finding.get("file") == expected["file"] and span
                and span[0] <= expected["line_max"] and span[1] >= expected["line_min"])


def _summary(finding):
    return {k: finding.get(k) for k in ("severity", "file", "line", "dimension", "dimensions", "title")}


def check(report, expected):
    """Return (passed, matching_finding_or_None, considered_findings)."""
    for key in ("lens", "file", "line_min", "line_max"):
        if key not in expected:
            raise ValueError("expected.json is missing %s" % key)
    absent = expected["absent"] if "absent" in expected else False
    if not isinstance(absent, bool):
        raise ValueError("expected.json absent must be true or false")
    marker = None
    if "recommendation_contains" in expected:
        marker = expected["recommendation_contains"]
        if not isinstance(marker, str) or not marker:
            raise ValueError("expected.json recommendation_contains must be a non-empty string")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report has no findings list")
    postable = [f for f in findings if f.get("severity") in POSTABLE]
    if absent:
        offending = [_summary(f) for f in postable if _overlaps(f, expected)]
        return not offending, None, offending
    adjudication = (report.get("run") or {}).get("adjudication") or {}
    needs_production = adjudication.get("status") == "complete"
    for finding in postable:
        if not (expected["lens"] in _lenses(finding) and _overlaps(finding, expected)):
            continue
        recommendation = "%s\n%s" % (finding.get("recommendation_md") or "", finding.get("recommendation") or "")
        if marker is not None and marker not in recommendation:
            continue
        if needs_production and not finding.get("production"):
            continue
        return True, finding, [_summary(f) for f in postable]
    return False, None, [_summary(f) for f in postable]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score one smoke-corpus review.")
    ap.add_argument("--report", required=True)
    ap.add_argument("--expected", required=True)
    args = ap.parse_args(argv)
    try:
        report = load_object(args.report, "report")
        expected = load_object(args.expected, "expected")
        passed, match, considered = check(report, expected)
    except (ValueError, AttributeError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    if passed:
        print(json.dumps({"pass": True, "finding": match.get("title") if match else None}))
        return 0
    print(json.dumps({"pass": False, "expected": expected, "found": considered}, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
