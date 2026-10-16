#!/usr/bin/env python3
"""Score a deep review against a verified defect answer key."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

from jsonio import write_json
from render_report import rank_findings


_LINE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")
_TEXT_FIELDS = ("title", "issue", "body_md", "impact", "fix_md", "recommendation",
                "recommendation_md")
_SEVERITIES = ("Must fix", "Should fix")
_VERDICTS = ("confirmed", "plausible", "refuted")
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_KEY_SHA = re.compile(r"[0-9a-f]{7,40}")
_COMPLETED_AREAS = ("completed", "read_only_degraded")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % label)
    return value


def _finite_number(value: object, label: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
            or (isinstance(value, float) and not math.isfinite(value))):
        raise ValueError("%s must be a non-negative finite number" % label)


def _string_list(value: object, label: str) -> list:
    items = _require_list(value, label)
    for item in items:
        _text(item, label + " item")
    return items


def _target(value: dict, label: str, *, required: bool, short_sha: bool) -> None:
    for field in ("project", "number", "head_sha"):
        if field not in value and not required:
            continue
        item = value.get(field)
        if field == "number":
            if type(item) is not int or item < 1:
                raise ValueError("%s.number must be a positive integer" % label)
        elif field == "head_sha":
            pattern = _KEY_SHA if short_sha else _FULL_SHA
            if not isinstance(item, str) or pattern.fullmatch(item) is None:
                raise ValueError("%s.head_sha must be a %slowercase hexadecimal SHA" %
                                 (label, "7-to-40-character " if short_sha else "full "))
        else:
            _text(item, label + "." + field)


def _line_span(line: str | int) -> tuple[int, int]:
    if isinstance(line, bool) or not isinstance(line, (str, int)):
        raise ValueError("finding line must be a string or integer")
    match = _LINE.fullmatch(str(line).strip())
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
                     budget_minutes: float) -> tuple[list[dict], dict]:
    _require_object(report, "report")
    findings = _require_list(report.get("findings"), "report.findings")
    identifiers = set()
    normalized = []
    for index, finding in enumerate(findings, 1):
        _require_object(finding, "finding %d" % index)
        _text(finding.get("file"), "finding %d file" % index)
        if "id" in finding:
            identifier = _text(finding["id"], "finding %d id" % index)
            if identifier in identifiers:
                raise ValueError("duplicate finding id: %s" % identifier)
            identifiers.add(identifier)
        if not isinstance(finding.get("title"), str):
            raise ValueError("finding %d title must be a string" % index)
        if finding.get("severity") not in (*_SEVERITIES, "Nit"):
            raise ValueError("finding %d severity must be Must fix, Should fix or Nit" % index)
        _line_span(finding.get("line"))
        for field in _TEXT_FIELDS:
            if field in finding and finding[field] is not None and not isinstance(finding[field], str):
                raise ValueError("finding %d %s must be a string or null" % (index, field))
        for field in ("verification_status", "spot_check"):
            if field in finding and finding[field] not in _VERDICTS:
                raise ValueError("finding %d %s must be confirmed, plausible or refuted" %
                                 (index, field))
        if "verified" in finding and not isinstance(finding["verified"], bool):
            raise ValueError("finding %d verified must be a boolean" % index)
        normalized.append(dict(finding, file=finding["file"].strip(),
                               line=str(finding["line"]).strip()))
    findings = rank_findings(normalized)
    aliases = {}
    for finding in findings:
        for alias in (finding["id"], "%s:%s" % (finding["file"], finding["line"])):
            aliases.setdefault(alias, []).append(finding["id"])

    _require_object(answer_key, "answer key")
    if type(answer_key.get("schema_version")) is not int or answer_key["schema_version"] != 1:
        raise ValueError("answer key schema_version must be 1")
    target = _require_object(answer_key.get("target"), "answer key target")
    _target(target, "answer key target", required=True, short_sha=True)
    defects = _require_list(answer_key.get("defects"), "answer key defects")
    non_defects = _require_list(answer_key.get("examined_non_defects"),
                                "answer key examined_non_defects")
    for index, item in enumerate(non_defects, 1):
        _require_object(item, "examined non-defect %d" % index)
        for field in ("source_id", "file", "disposition", "reason"):
            _text(item.get(field), "examined non-defect %d %s" % (index, field))
        if type(item.get("line")) is not int or item["line"] < 1:
            raise ValueError("examined non-defect %d line must be a positive integer" % index)
    defect_ids = set()
    for index, defect in enumerate(defects, 1):
        _require_object(defect, "defect %d" % index)
        for field in ("id", "title"):
            _text(defect.get(field), "defect %d %s" % (index, field))
        if defect["id"] in defect_ids:
            raise ValueError("duplicate defect id: %s" % defect["id"])
        defect_ids.add(defect["id"])
        anchors = _require_list(defect.get("anchors"), "defect %d anchors" % index)
        if not anchors:
            raise ValueError("defect %d must have an anchor" % index)
        for anchor in anchors:
            _require_object(anchor, "defect %d anchor" % index)
            _text(anchor.get("file"), "defect %d anchor file" % index)
            lo, hi = anchor.get("line_min"), anchor.get("line_max")
            if type(lo) is not int or type(hi) is not int or lo < 1 or hi < lo:
                raise ValueError("defect %d anchor lines must be positive, ascending integers" % index)
        _string_list(defect.get("keywords", []), "defect %d keywords" % index)

    resolved = {}
    if spot_check is not None:
        _require_object(spot_check, "spot check")
        verdicts = _require_object(spot_check.get("verdicts", spot_check), "spot check verdicts")
        for alias, verdict in verdicts.items():
            _text(alias, "spot check finding id")
            if verdict not in _VERDICTS:
                raise ValueError("spot check verdicts must be confirmed, plausible or refuted")
            matching = aliases.get(alias, [])
            if not matching:
                raise ValueError("unknown spot check finding id: %s" % alias)
            if len(matching) != 1:
                raise ValueError("ambiguous spot check finding id: %s" % alias)
            identifier = matching[0]
            if identifier in resolved:
                raise ValueError("duplicate spot check judgment for finding: %s" % identifier)
            resolved[identifier] = verdict
    _finite_number(budget_minutes, "budget minutes")
    meta = _require_object(report.get("meta", {}), "report.meta")
    _target(meta, "report.meta", required=False, short_sha=False)
    run = _require_object(report.get("run", {}), "report.run")
    deep = _require_object(run.get("deep", {}), "report.run.deep")
    if "incomplete" in run and not isinstance(run["incomplete"], bool):
        raise ValueError("report.run.incomplete must be a boolean")
    for field in ("enabled", "cutoff_reached"):
        if field in deep and not isinstance(deep[field], bool):
            raise ValueError("report.run.deep.%s must be a boolean" % field)
    if "dimensions_failed" in run:
        _string_list(run["dimensions_failed"], "report.run.dimensions_failed")
    if "unreached_areas" in deep:
        _string_list(deep["unreached_areas"], "report.run.deep.unreached_areas")
    if "checker_failures" in deep:
        failures = _require_object(deep["checker_failures"], "report.run.deep.checker_failures")
        for identifier, reason in failures.items():
            _text(identifier, "report.run.deep.checker_failures candidate id")
            _text(reason, "report.run.deep.checker_failures reason")
    if "areas" in deep:
        area_ids = set()
        for area in _require_list(deep["areas"], "report.run.deep.areas"):
            _require_object(area, "report.run.deep area")
            identifier = _text(area.get("id"), "report.run.deep area id")
            if identifier in area_ids:
                raise ValueError("duplicate deep area id: %s" % identifier)
            area_ids.add(identifier)
            if "status" in area:
                _text(area["status"], "report.run.deep area status")
    elapsed = deep.get("elapsed_minutes")
    if elapsed is not None:
        _finite_number(elapsed, "report.run.deep.elapsed_minutes")
    return findings, resolved


def match_defect(defect: dict, findings: list[dict]) -> dict | None:
    """Return the first confirmed finding overlapping an anchor and describing its cause."""
    keywords = [word.casefold() for word in defect.get("keywords", [])]
    for finding in findings:
        if (finding.get("severity") not in _SEVERITIES
                or finding.get("verification_status") != "confirmed"
                or finding.get("verified") is False
                or finding.get("spot_check") in ("plausible", "refuted")):
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
    """Return recall independently; passing requires complete, target-bound evaluation evidence."""
    findings, verdicts = _validate_inputs(report, answer_key, spot_check, budget_minutes)
    eligible = [finding for finding in findings
                if verdicts.get(finding["id"]) not in ("plausible", "refuted")]
    caught = []
    missed = []
    for defect in answer_key["defects"]:
        finding = match_defect(defect, eligible)
        if finding is None:
            missed.append({"defect_id": defect["id"], "title": defect["title"],
                           "anchors": defect["anchors"]})
        else:
            caught.append({"defect_id": defect["id"], "title": defect["title"],
                           "finding_id": finding["id"], "file": finding["file"],
                           "line": finding["line"]})
    shown_count = len(findings)
    checked_count = len(verdicts)
    refuted_count = sum(verdict == "refuted" for verdict in verdicts.values())
    unchecked = [finding["id"] for finding in findings if finding["id"] not in verdicts]
    coverage = ("missing" if spot_check is None else "empty" if not checked_count
                else "partial" if unchecked else "complete")
    refuted_share = refuted_count / checked_count if checked_count else None
    run = report.get("run", {})
    deep = run.get("deep", {})
    elapsed = deep.get("elapsed_minutes")
    within_budget = elapsed is not None and elapsed <= budget_minutes
    target = answer_key["target"]
    meta = report.get("meta", {})
    target_matches = (meta.get("project") == target["project"]
                      and meta.get("number") == target["number"]
                      and isinstance(meta.get("head_sha"), str)
                      and meta["head_sha"].startswith(target["head_sha"]))
    areas = deep.get("areas")
    complete = (deep.get("enabled") is True and run.get("incomplete") is False
                and not run.get("dimensions_failed") and not deep.get("unreached_areas")
                and not deep.get("checker_failures")
                and areas is not None
                and all(area.get("status") in _COMPLETED_AREAS for area in areas))
    evidence_errors = []
    if not target_matches:
        evidence_errors.append("target_missing_or_mismatched")
    if not complete:
        evidence_errors.append("deep_run_disabled_incomplete_or_unproven")
    if elapsed is None:
        evidence_errors.append("elapsed_minutes_missing")
    elif not within_budget:
        evidence_errors.append("budget_exceeded")
    if not checked_count:
        evidence_errors.append("spot_check_missing_or_empty")
    recall = len(caught) / len(answer_key["defects"]) if answer_key["defects"] else 1.0
    return {"caught": caught, "missed": missed, "caught_count": len(caught),
            "total_defects": len(answer_key["defects"]), "recall": recall,
            "shown_count": shown_count, "checked_count": checked_count,
            "unchecked_finding_ids": unchecked, "spot_check_coverage": coverage,
            "refuted_count": refuted_count, "refuted_share": refuted_share,
            "elapsed_minutes": elapsed, "within_budget": within_budget,
            "target_matches": target_matches, "complete_deep_run": complete,
            "evidence_errors": evidence_errors,
            "passed": bool(not evidence_errors and recall == 1.0
                           and refuted_share is not None and refuted_share <= 0.20)}


def _unique_object(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key: %s" % key)
        value[key] = item
    return value


def _load_object(path: str, label: str) -> dict:
    with open(path, encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=_unique_object)
    return _require_object(value, label)


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
        report = _load_object(args.report, "report")
        answer_key = _load_object(args.answer_key, "answer key")
        spot_check = _load_object(args.spot_check, "spot check") if args.spot_check else None
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
