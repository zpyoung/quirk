#!/usr/bin/env python3
"""Score a deep review against a verified defect answer key."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

from jsonio import load_object, write_json


_LINE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")
_TEXT_FIELDS = ("title", "issue", "body_md", "impact", "fix_md", "recommendation",
                "recommendation_md")
_SEVERITIES = ("Must fix", "Should fix")
_VERDICTS = ("confirmed", "plausible", "refuted")


def _line_span(line: str) -> tuple[int, int]:
    if not isinstance(line, str):
        raise ValueError("finding line must be a string")
    match = _LINE.fullmatch(line)
    if match is None:
        raise ValueError("finding line must be a number or numeric range")
    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    if start < 1 or end < start:
        raise ValueError("finding line must be a positive, ascending range")
    return start, end


def _require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise ValueError("%s must be a list" % label)
    return value


def _validate_inputs(report: dict, answer_key: dict, spot_check: dict | None,
                     budget_minutes: float) -> dict:
    _require_object(report, "report")
    findings = _require_list(report.get("findings"), "report.findings")
    for index, finding in enumerate(findings, 1):
        _require_object(finding, "finding %d" % index)
        for field in ("id", "file", "line", "title", "severity"):
            if not isinstance(finding.get(field), str):
                raise ValueError("finding %d %s must be a string" % (index, field))
        _line_span(finding["line"])

    _require_object(answer_key, "answer key")
    if type(answer_key.get("schema_version")) is not int or answer_key["schema_version"] != 1:
        raise ValueError("answer key schema_version must be 1")
    _require_object(answer_key.get("target"), "answer key target")
    defects = _require_list(answer_key.get("defects"), "answer key defects")
    non_defects = _require_list(answer_key.get("examined_non_defects"),
                                "answer key examined_non_defects")
    for index, item in enumerate(non_defects, 1):
        _require_object(item, "examined non-defect %d" % index)
        for field in ("source_id", "file", "disposition", "reason"):
            if not isinstance(item.get(field), str):
                raise ValueError("examined non-defect %d %s must be a string" % (index, field))
        if type(item.get("line")) is not int or item["line"] < 1:
            raise ValueError("examined non-defect %d line must be a positive integer" % index)
    for index, defect in enumerate(defects, 1):
        _require_object(defect, "defect %d" % index)
        for field in ("id", "title"):
            if not isinstance(defect.get(field), str):
                raise ValueError("defect %d %s must be a string" % (index, field))
        anchors = _require_list(defect.get("anchors"), "defect %d anchors" % index)
        if not anchors:
            raise ValueError("defect %d must have an anchor" % index)
        for anchor in anchors:
            _require_object(anchor, "defect %d anchor" % index)
            if not isinstance(anchor.get("file"), str):
                raise ValueError("defect %d anchor file must be a string" % index)
            lo, hi = anchor.get("line_min"), anchor.get("line_max")
            if (type(lo) is not int or type(hi) is not int or lo < 1 or hi < lo):
                raise ValueError("defect %d anchor lines must be positive, ascending integers" % index)
        keywords = defect.get("keywords", [])
        if not isinstance(keywords, list) or any(not isinstance(word, str) for word in keywords):
            raise ValueError("defect %d keywords must be a list of strings" % index)

    if spot_check is None:
        verdicts = {}
    else:
        _require_object(spot_check, "spot check")
        verdicts = _require_object(spot_check.get("verdicts", spot_check), "spot check verdicts")
        if any(not isinstance(key, str) or verdict not in _VERDICTS
               for key, verdict in verdicts.items()):
            raise ValueError("spot check verdicts must map strings to confirmed, plausible or refuted")
    if isinstance(budget_minutes, bool) or not isinstance(budget_minutes, (int, float)) \
            or not math.isfinite(budget_minutes) or budget_minutes < 0:
        raise ValueError("budget minutes must be a non-negative finite number")
    run = report.get("run", {})
    _require_object(run, "report.run")
    deep = run.get("deep", {})
    _require_object(deep, "report.run.deep")
    elapsed = deep.get("elapsed_minutes")
    if elapsed is not None and (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                                or not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError("report.run.deep.elapsed_minutes must be a non-negative finite number")
    return verdicts


def match_defect(defect: dict, findings: list[dict]) -> dict | None:
    """Return the first eligible finding overlapping a defect anchor and describing its cause."""
    keywords = [word.casefold() for word in defect.get("keywords", [])]
    for finding in findings:
        if finding.get("severity") not in _SEVERITIES:
            continue
        start, end = _line_span(finding["line"])
        if not any(finding["file"] == anchor["file"] and
                   start <= anchor["line_max"] and anchor["line_min"] <= end
                   for anchor in defect["anchors"]):
            continue
        if keywords:
            explanation = " ".join(str(finding.get(field) or "") for field in _TEXT_FIELDS).casefold()
            if not any(word in explanation for word in keywords):
                continue
        return finding
    return None


def score_report(report: dict, answer_key: dict, spot_check: dict | None = None,
                 budget_minutes: float = 60.0) -> dict:
    """Calculate recall, refuted share and budget compliance without changing inputs."""
    verdicts = _validate_inputs(report, answer_key, spot_check, budget_minutes)
    findings = report["findings"]
    caught = []
    missed = []
    for defect in answer_key["defects"]:
        finding = match_defect(defect, findings)
        if finding is None:
            missed.append({"defect_id": defect["id"], "title": defect["title"],
                           "anchors": defect["anchors"]})
        else:
            caught.append({"defect_id": defect["id"], "title": defect["title"],
                           "finding_id": finding["id"], "file": finding["file"],
                           "line": finding["line"]})
    shown_count = len(findings)
    if spot_check is None:
        refuted_count = sum(finding.get("spot_check") == "refuted" or
                            finding.get("verification_status") == "refuted" for finding in findings)
    else:
        refuted_count = sum(verdicts.get(finding["id"],
                                    verdicts.get("%s:%s" % (finding["file"], finding["line"]))) == "refuted"
                            for finding in findings)
    elapsed = report.get("run", {}).get("deep", {}).get("elapsed_minutes")
    recall = len(caught) / len(answer_key["defects"]) if answer_key["defects"] else 1.0
    refuted_share = refuted_count / max(1, shown_count)
    within_budget = elapsed is None or elapsed <= budget_minutes
    return {"caught": caught, "missed": missed, "caught_count": len(caught),
            "total_defects": len(answer_key["defects"]), "recall": recall,
            "shown_count": shown_count, "refuted_count": refuted_count,
            "refuted_share": refuted_share, "elapsed_minutes": elapsed,
            "within_budget": within_budget,
            "passed": bool(recall == 1.0 and refuted_share <= 0.20 and within_budget)}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Print a JSON score and optionally write it to disk; return the scoring exit code."""
    parser = _JsonArgumentParser(description="Score a deep review against an answer key.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--answer-key", required=True)
    parser.add_argument("--spot-check")
    parser.add_argument("--budget-minutes", type=float, default=60.0)
    parser.add_argument("--out")
    try:
        args = parser.parse_args(argv)
        report = load_object(args.report, "report")
        answer_key = load_object(args.answer_key, "answer key")
        spot_check = load_object(args.spot_check, "spot check") if args.spot_check else None
        result = score_report(report, answer_key, spot_check, args.budget_minutes)
        if args.out:
            write_json(args.out, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
