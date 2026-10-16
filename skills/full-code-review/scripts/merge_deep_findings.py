"""Assemble a deep review from checked candidates and execution coverage."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Literal, NoReturn, overload

import jsonio


_SEVERITY_RANK = {"Nit": 0, "Should fix": 1, "Must fix": 2}
_LINE_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _items(value: object, label: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("%s must be an array of JSON objects" % label)
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % label)
    return value.strip()


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _one_line(value: str, limit: int, *, sentence: bool = False) -> str:
    text = " ".join(value.split())
    if sentence:
        text = _SENTENCE_END.split(text, maxsplit=1)[0]
    return text[:limit].rstrip()


def _line(value: object, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("%s must be a line or line range" % label)
    return str(value).strip()


def _dimensions(source: dict, *, is_lens: bool) -> list[str]:
    default = "contract" if is_lens or source.get("area") == "contract" else "correctness"
    raw = source.get("dimensions", [])
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("dimensions must be an array of strings")
    names = {name for item in raw if (name := item.strip())}
    if isinstance(source.get("dimension"), str) and source["dimension"].strip():
        names.add(source["dimension"].strip())
    return sorted(names or {default})


def _budget(value: dict) -> dict:
    for name, minimum in (("budget_minutes", 0), ("elapsed_minutes", -1)):
        number = value.get(name)
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not math.isfinite(number) or number <= minimum):
            raise ValueError("budget %s must be %s" % (
                name, "positive" if name == "budget_minutes" else "non-negative"))
    if not isinstance(value.get("cutoff_reached"), bool):
        raise ValueError("budget cutoff_reached must be a boolean")
    return value


def _finding(source: dict, checker: dict | None, *, is_lens: bool) -> dict:
    identifier = _required_text(source.get("id"), "candidate id")
    verdict = checker.get("verdict", "confirmed") if checker is not None else "confirmed"
    severity = checker.get("severity") if checker is not None else source.get("severity")
    if severity not in _SEVERITY_RANK:
        raise ValueError("checker severity for %s must be Must fix, Should fix, or Nit" % identifier)
    evidence = checker.get("evidence_tag") if checker is not None else "read from code"
    if evidence not in ("read from code", "reproduced"):
        raise ValueError("checker evidence_tag for %s must be reproduced or read from code" % identifier)

    file = _required_text(
        _first_text(checker.get("refined_file") if checker else None, source.get("file")),
        "file for %s" % identifier,
    )
    refined_line = checker.get("refined_line") if checker else None
    line = _line(refined_line if refined_line is not None else source.get("line"),
                 "line for %s" % identifier)
    title = _required_text(_first_text(checker.get("refined_title") if checker else None,
                                       source.get("title"), source.get("summary")), "title for %s" % identifier)
    issue = _first_text(checker.get("refined_issue") if checker else None,
                        source.get("failure_scenario"), source.get("issue"), source.get("body_md"))
    recommendation = _first_text(checker.get("refined_recommendation") if checker else None,
                                 source.get("recommendation"), source.get("recommendation_md"))
    impact = _first_text(checker.get("refined_impact") if checker else None,
                         source.get("impact"), source.get("failure_scenario"), source.get("issue"),
                         source.get("body_md"))
    fix = _first_text(checker.get("refined_fix_md") if checker else None, source.get("fix_md"))
    dimensions = _dimensions(source, is_lens=is_lens)
    finding = {
        "id": identifier,
        "severity": severity,
        "dimension": dimensions[0],
        "dimensions": dimensions,
        "file": file,
        "line": line,
        "title": _one_line(title, 80),
        "impact": _one_line(impact, 200, sentence=True),
        "fix_md": _one_line(fix, 160),
        "issue": issue,
        "body_md": issue,
        "recommendation": recommendation,
        "recommendation_md": recommendation,
        "verification_status": verdict,
        "verified": verdict == "confirmed",
        "evidence": evidence,
        "what_would_confirm": None,
    }
    if "area" in source:
        finding["area"] = source["area"]
    if source.get("dedup_key"):
        finding["dedup_key"] = source["dedup_key"]
    if verdict == "plausible":
        assert checker is not None
        finding["what_would_confirm"] = _required_text(
            checker.get("what_would_confirm"), "what_would_confirm for %s" % identifier)
    if evidence == "reproduced":
        assert checker is not None
        finding["repro"] = {
            "command": _required_text(checker.get("repro_command"), "repro_command for %s" % identifier),
            "output": _required_text(checker.get("repro_output"), "repro_output for %s" % identifier),
        }
    return finding


def _overlaps(first: str, second: str) -> bool:
    a = _LINE_RANGE.fullmatch(first)
    b = _LINE_RANGE.fullmatch(second)
    if not a or not b:
        return False
    a_start, a_end = int(a[1]), int(a[2] or a[1])
    b_start, b_end = int(b[1]), int(b[2] or b[1])
    return a_start <= b_end and b_start <= a_end


def _same_defect(first: dict, second: dict) -> bool:
    key = first.get("dedup_key")
    if key and key == second.get("dedup_key"):
        return True
    if first["file"] != second["file"]:
        return False
    if first["line"] == second["line"]:
        return True
    return ("-" in first["line"] or "-" in second["line"]) and _overlaps(
        first["line"], second["line"]) and first["title"].casefold() == second["title"].casefold()


def _deduplicate(findings: list[dict]) -> list[dict]:
    parents = list(range(len(findings)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for right in range(len(findings)):
        for left in range(right):
            if _same_defect(findings[left], findings[right]):
                parents[root(right)] = root(left)

    groups: dict[int, list[dict]] = {}
    for index, finding in enumerate(findings):
        groups.setdefault(root(index), []).append(finding)

    merged = []
    for group in groups.values():
        best = max(group, key=lambda item: (_SEVERITY_RANK[item["severity"]],
                                            item["verified"], item["evidence"] == "reproduced"))
        item = dict(best)
        dimensions = sorted({dimension for found in group for dimension in found["dimensions"]})
        item["dimensions"] = dimensions
        item["dimension"] = dimensions[0]
        item["verification_status"] = "confirmed" if any(found["verified"] for found in group) else "plausible"
        item["verified"] = item["verification_status"] == "confirmed"
        item["what_would_confirm"] = None if item["verified"] else next(
            found["what_would_confirm"] for found in group if found["what_would_confirm"])
        reproduced = next((found for found in group if found["evidence"] == "reproduced"), None)
        item["evidence"] = "reproduced" if reproduced else "read from code"
        if reproduced:
            item["repro"] = reproduced["repro"]
        else:
            item.pop("repro", None)
        merged.append(item)
    return merged


def merge_deep_run(
    lens_findings: list[dict],
    deep_candidates: list[dict],
    checker_verdicts: list[dict],
    area_map: dict,
    trust_info: dict,
    budget_info: dict,
) -> dict:
    """Only show checked defects, retaining refutations and review coverage."""
    lens_findings = _items(lens_findings, "lens findings")
    deep_candidates = _items(deep_candidates, "deep candidates")
    checker_verdicts = _items(checker_verdicts, "checker verdicts")
    areas = _items(_object(area_map, "area map").get("areas"), "area map areas")
    trust_info = _object(trust_info, "trust")
    budget_info = _budget(_object(budget_info, "budget"))
    verdicts = {}
    for checker in checker_verdicts:
        identifier = _required_text(checker.get("id"), "checker id")
        if identifier in verdicts:
            raise ValueError("duplicate checker verdict for %s" % identifier)
        if checker.get("verdict") not in ("confirmed", "plausible", "refuted"):
            raise ValueError("invalid checker verdict for %s" % identifier)
        verdicts[identifier] = checker

    findings = []
    dropped = []
    for source, is_lens in [(source, False) for source in deep_candidates] + [
        (source, True) for source in lens_findings
    ]:
        identifier = _required_text(source.get("id"), "candidate id")
        checker = verdicts.get(identifier)
        if checker is None and (not is_lens or source.get("severity") != "Nit"):
            raise ValueError("missing checker verdict for %s" % identifier)
        if checker is not None and checker["verdict"] == "refuted":
            dimensions = _dimensions(source, is_lens=is_lens)
            dropped.append({
                "id": identifier,
                "area": "lens:%s" % _first_text(source.get("dimension"), dimensions[0]) if is_lens
                        else _first_text(source.get("area"), "unknown"),
                "file": _required_text(source.get("file"), "file for %s" % identifier),
                "line": _line(source.get("line"), "line for %s" % identifier),
                "title": _one_line(_required_text(_first_text(source.get("title"), source.get("summary")),
                                                 "title for %s" % identifier), 80),
                "reason": _required_text(checker.get("reason"), "reason for %s" % identifier),
            })
            continue
        findings.append(_finding(source, checker, is_lens=is_lens))

    allowed = trust_info.get("allowed")
    consent = trust_info.get("consent")
    if not isinstance(allowed, bool) or not isinstance(consent, bool):
        raise ValueError("trust allowed and consent must be booleans")
    execution_enabled = allowed and consent
    coverage_notes = []
    assumptions = []
    disabled_reason = None
    if execution_enabled:
        assumptions.append(
            "Deep mode execution consent granted: code ran in isolated throwaway copies "
            "(%s, %s, budget %sm, no gh/glab)." % (
                trust_info.get("sandbox_kind"), trust_info.get("copy_kind"), budget_info.get("budget_minutes")))
    elif not allowed:
        disabled_reason = _required_text(trust_info.get("reason"), "trust reason")
        coverage_notes.append("⚠ Deep repros disabled: %s" % disabled_reason)
    else:
        disabled_reason = "execution consent was declined"
        coverage_notes.append("⚠ Deep repros disabled: %s" % disabled_reason)

    unreached = []
    for area in areas:
        identifier = _required_text(area.get("id"), "area id")
        if area.get("status") == "read_only_degraded":
            reason = _required_text(area.get("degraded_reason"), "degraded reason for %s" % identifier)
            coverage_notes.append("⚠ Area %s ran read-only: %s" % (identifier, reason))
        elif area.get("status") == "unreached":
            unreached.append(identifier)
    if unreached:
        coverage_notes.append("⚠ Incomplete deep review: budget expired before reaching " + ", ".join(unreached))

    deep = {
        "enabled": True,
        "budget_minutes": budget_info.get("budget_minutes"),
        "elapsed_minutes": budget_info.get("elapsed_minutes"),
        "cutoff_reached": budget_info.get("cutoff_reached"),
        "execution_allowed": allowed,
        "execution_consent": consent,
        "execution_enabled": execution_enabled,
        "execution_disabled_reason": disabled_reason,
        "sandbox_kind": trust_info.get("sandbox_kind"),
        "copy_kind": trust_info.get("copy_kind"),
        "areas": areas,
        "unreached_areas": unreached,
        "checked_and_dropped": dropped,
    }
    return {"findings": _deduplicate(findings), "deep": deep, "incomplete": bool(unreached),
            "verdict_override": "Incomplete review" if unreached else None,
            "coverage_notes": coverage_notes, "assumptions": assumptions}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


@overload
def _load(path: str, label: str, *, array: Literal[True]) -> list[dict]: ...


@overload
def _load(path: str, label: str, *, array: Literal[False]) -> dict: ...


def _load(path: str, label: str, *, array: bool) -> list[dict] | dict:
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("could not read %s: %s" % (label, exc)) from exc
    return _items(value, label) if array else _object(value, label)


def main(argv: list[str] | None = None) -> int:
    """Read review inputs and atomically write the checked merge as JSON."""
    try:
        parser = _Parser(description=__doc__)
        for argument in ("lens-findings", "deep-candidates", "checker-verdicts", "area-map", "trust", "budget", "out"):
            parser.add_argument("--" + argument, required=True)
        args = parser.parse_args(argv)
        result = merge_deep_run(
            _load(args.lens_findings, "lens findings", array=True),
            _load(args.deep_candidates, "deep candidates", array=True),
            _load(args.checker_verdicts, "checker verdicts", array=True),
            _load(args.area_map, "area map", array=False),
            _load(args.trust, "trust", array=False),
            _load(args.budget, "budget", array=False),
        )
        jsonio.write_json(args.out, result)
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
