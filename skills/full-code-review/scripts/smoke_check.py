#!/usr/bin/env python3
"""Check one smoke-corpus review: did the expected lens catch the planted bug?

Pass when some Must or Should finding carries the expected lens, names the expected
file, and has a line range overlapping [line_min, line_max]. Exit 0 pass, 1 miss
(printing what was found instead), 2 bad input.
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


def check(report, expected):
    """Return (passed, matching_finding_or_None, considered_findings)."""
    for key in ("lens", "file", "line_min", "line_max"):
        if key not in expected:
            raise ValueError("expected.json is missing %s" % key)
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report has no findings list")
    considered = []
    for finding in findings:
        if finding.get("severity") not in POSTABLE:
            continue
        span = _range(finding.get("line"))
        considered.append({k: finding.get(k) for k in ("severity", "file", "line", "dimension", "dimensions", "title")})
        if (expected["lens"] in _lenses(finding) and finding.get("file") == expected["file"]
                and span and span[0] <= expected["line_max"] and span[1] >= expected["line_min"]):
            return True, finding, considered
    return False, None, considered


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
        print(json.dumps({"pass": True, "finding": match.get("title")}))
        return 0
    print(json.dumps({"pass": False, "expected": expected, "found": considered}, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
