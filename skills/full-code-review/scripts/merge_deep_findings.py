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
_REPORT_LINE = re.compile(r"[1-9][0-9]*(?:-[0-9]+)?")


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


def _one_line(value: str, limit: int, label: str = "report text") -> str:
    text = " ".join(value.split())
    if len(text) > limit:
        raise ValueError("%s exceeds %d characters; rewrite it before merging" % (label, limit))
    return text


def _elided(value: str, limit: int) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _bounded(refined: str, fallback: str, limit: int, label: str) -> str:
    """Checker-refined text must fit the cap as written; finder text is shortened instead."""
    return _one_line(refined, limit, label) if refined else _elided(fallback, limit)


def _title(source: dict) -> str:
    """Finder title, else the first clause of its issue text."""
    explicit = _first_text(source.get("title"), source.get("summary"))
    if explicit:
        return explicit
    issue = _first_text(source.get("failure_scenario"), source.get("issue"), source.get("body_md"))
    return re.split(r"(?<=[.!?:;])\s", " ".join(issue.split()))[0]


def _line(value: object, label: str) -> str:
    """Normalize a line anchor to the `N` or `N-M` form the report renderer accepts."""
    if not isinstance(value, bool) and isinstance(value, (str, int)):
        text = re.sub(r"\s*-\s*", "-", str(value).strip())
        if _REPORT_LINE.fullmatch(text):
            start, _, end = text.partition("-")
            if not end or int(end) >= int(start):
                return text
    raise ValueError("%s must be a line number or start-end range" % label)


def _audit_line(value: object) -> str:
    """Best-effort anchor for a dropped entry, which is audit-only and must never abort the merge."""
    try:
        return _line(value, "line")
    except ValueError:
        found = re.search(r"[1-9][0-9]*", str(value)) if not isinstance(value, bool) else None
        return found[0] if found else "1"


def _assumptions(source: dict, identifier: str) -> list[str]:
    raw = source.get("assumptions", [])
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("assumptions for %s must be an array of strings" % identifier)
    return [item.strip() for item in raw if item.strip()]


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
    for name, valid in (("budget_minutes", lambda number: number > 0),
                        ("elapsed_minutes", lambda number: number >= 0)):
        number = value.get(name)
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or (isinstance(number, float) and not math.isfinite(number)) or not valid(number)):
            raise ValueError("budget %s must be %s" % (
                name, "positive" if name == "budget_minutes" else "non-negative"))
    if not isinstance(value.get("cutoff_reached"), bool):
        raise ValueError("budget cutoff_reached must be a boolean")
    return value


def _finding(source: dict, checker: dict | None, *, is_lens: bool) -> dict:
    identifier = _required_text(source.get("id"), "candidate id")
    assumptions = _assumptions(source, identifier)
    unverified_lens_claim = checker is None and source.get("verified") is False
    verdict = (checker.get("verdict", "confirmed") if checker is not None
               else "plausible" if unverified_lens_claim else "confirmed")
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
    refined_title = _first_text(checker.get("refined_title") if checker else None)
    title = _required_text(_first_text(refined_title, _title(source)), "title for %s" % identifier)
    issue = _first_text(checker.get("refined_issue") if checker else None,
                        source.get("failure_scenario"), source.get("issue"), source.get("body_md"))
    recommendation = _first_text(checker.get("refined_recommendation") if checker else None,
                                 source.get("recommendation"), source.get("recommendation_md"))
    refined_impact = _first_text(checker.get("refined_impact") if checker else None)
    impact = _first_text(source.get("impact"), source.get("failure_scenario"), source.get("issue"),
                         source.get("body_md"))
    refined_fix = _first_text(checker.get("refined_fix_md") if checker else None)
    fix = _first_text(source.get("fix_md"))
    dimensions = _dimensions(source, is_lens=is_lens)
    finding = {
        "id": identifier,
        "severity": severity,
        "dimension": dimensions[0],
        "dimensions": dimensions,
        "file": file,
        "line": line,
        "title": _bounded(refined_title, title, 80, "title for %s" % identifier),
        "impact": _bounded(refined_impact, impact, 200, "impact for %s" % identifier),
        "fix_md": _bounded(refined_fix, fix, 160, "fix_md for %s" % identifier),
        "issue": issue,
        "body_md": issue,
        "recommendation": recommendation,
        "recommendation_md": recommendation,
        "verification_status": verdict,
        "verified": verdict == "confirmed",
        "evidence": evidence,
        "what_would_confirm": None,
        "_checked": checker is not None,
    }
    if "area" in source:
        finding["area"] = source["area"]
    if assumptions:
        finding["assumptions"] = assumptions
    if "anchor_side" in source:
        if source["anchor_side"] not in ("new", "old"):
            raise ValueError("anchor_side for %s must be new or old" % identifier)
        finding["anchor_side"] = source["anchor_side"]
    if source.get("dedup_key"):
        finding["dedup_key"] = source["dedup_key"]
    if verdict == "plausible":
        if checker is None:
            finding["what_would_confirm"] = (
                "; ".join(assumptions) or "Confirm the claim against the source; the lens could not verify it.")
        else:
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
    other_key = second.get("dedup_key")
    if key and other_key:
        return key == other_key
    if first["file"] != second["file"]:
        return False
    if first["line"] == second["line"]:
        return True
    return _overlaps(first["line"], second["line"]) and first["title"].casefold() == second["title"].casefold()

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
        judged = [found for found in group if found["_checked"]] or group
        pool = [found for found in judged if found["verified"]] or judged
        best = max(pool, key=lambda item: (_SEVERITY_RANK[item["severity"]],
                                           item["evidence"] == "reproduced"))
        item = dict(best)
        dimensions = sorted({dimension for found in group for dimension in found["dimensions"]})
        item["dimensions"] = dimensions
        item["dimension"] = dimensions[0]
        item["verification_status"] = "confirmed" if any(found["verified"] for found in judged) else "plausible"
        item["verified"] = item["verification_status"] == "confirmed"
        item["what_would_confirm"] = None if item["verified"] else next(
            found["what_would_confirm"] for found in judged if found["what_would_confirm"])
        assumptions = list(dict.fromkeys(text for found in group for text in found.get("assumptions", [])))
        if assumptions:
            item["assumptions"] = assumptions
        if "anchor_side" not in item:
            sides = [found["anchor_side"] for found in group if "anchor_side" in found]
            if sides:
                item["anchor_side"] = sides[0]
        item.pop("_checked")
        reproduced = next((found for found in group if found["evidence"] == "reproduced"), None)
        item["evidence"] = "reproduced" if reproduced else "read from code"
        if reproduced:
            item["repro"] = reproduced["repro"]
        else:
            item.pop("repro", None)
        merged.append(item)
    return merged


_HUNK_CHECKED_STATUSES = ("completed", "read_only_degraded")


def _minutes(value: int | float) -> str:
    try:
        return "%g" % value
    except OverflowError:
        return str(value)


def _area_hunk_ids(area: dict, identifier: str) -> list[str]:
    """Return the area's hunk ids in hunk order, rejecting a malformed `hunks` list."""
    hunks = area["hunks"]
    if not isinstance(hunks, list):
        raise ValueError("hunks for %s must be an array" % identifier)
    ids = []
    for hunk in hunks:
        if not isinstance(hunk, dict):
            raise ValueError("each hunk in %s must be a JSON object" % identifier)
        hunk_id = _required_text(hunk.get("id"), "hunk id in %s" % identifier)
        _required_text(hunk.get("file"), "hunk file for %s" % hunk_id)
        _required_text(hunk.get("header"), "hunk header for %s" % hunk_id)
        if hunk_id in ids:
            raise ValueError("duplicate hunk id %s in %s" % (hunk_id, identifier))
        ids.append(hunk_id)
    return ids


def _examined_ids(area: dict, identifier: str, hunk_ids: list[str]) -> list[str]:
    examined = area.get("examined", [])
    if not isinstance(examined, list) or any(not isinstance(item, str) for item in examined):
        raise ValueError("examined for %s must be an array of hunk id strings" % identifier)
    for hunk_id in examined:
        if hunk_id not in hunk_ids:
            raise ValueError("examined hunk %s is not a hunk of area %s" % (hunk_id, identifier))
    return examined


def _unexamined_hunks(area: dict, identifier: str) -> list[str]:
    """Hunk ids of a completed area that its finder never recorded as examined, in hunk order."""
    hunk_ids = _area_hunk_ids(area, identifier)
    examined = set(_examined_ids(area, identifier, hunk_ids))
    return [hunk_id for hunk_id in hunk_ids if hunk_id not in examined]


def _hunk_coverage(areas: list[dict]) -> dict | None:
    """Summarize self-reported hunk coverage, or None when no area carries hunks."""
    with_hunks = [area for area in areas if "hunks" in area]
    if not with_hunks:
        return None
    total = sum(len(area["hunks"]) for area in with_hunks if isinstance(area["hunks"], list))
    examined = sum(len(set(area.get("examined", []))) for area in with_hunks
                   if area.get("status") in _HUNK_CHECKED_STATUSES)
    lines = [area["lines"] for area in areas
             if isinstance(area.get("lines"), (int, float)) and not isinstance(area["lines"], bool)]
    return {"areas": len(with_hunks), "hunks": total, "examined": examined,
            "mean_area_lines": round(sum(lines) / len(lines), 1) if lines else None}


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
    source_ids = [_required_text(source.get("id"), "candidate id")
                  for source in deep_candidates + lens_findings]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate candidate id")
    verdicts = {}
    for checker in checker_verdicts:
        identifier = _required_text(checker.get("id"), "checker id")
        if identifier not in source_ids:
            raise ValueError("unknown checker id: %s" % identifier)
        if identifier in verdicts:
            raise ValueError("duplicate checker verdict for %s" % identifier)
        if checker.get("verdict") not in ("confirmed", "plausible", "refuted"):
            raise ValueError("invalid checker verdict for %s" % identifier)
        verdicts[identifier] = checker
    checker_failures = _object(budget_info.get("checker_failures", {}), "checker failures")
    for identifier, reason in checker_failures.items():
        if identifier not in source_ids or identifier in verdicts:
            raise ValueError("checker failure must name an unchecked candidate id")
        _required_text(reason, "checker failure reason")

    findings = []
    dropped = []
    for source, is_lens in [(source, False) for source in deep_candidates] + [
        (source, True) for source in lens_findings
    ]:
        identifier = _required_text(source.get("id"), "candidate id")
        checker = verdicts.get(identifier)
        if checker is None and identifier in checker_failures:
            continue
        if checker is None and (not is_lens or source.get("severity") != "Nit"):
            raise ValueError("missing checker verdict for %s" % identifier)
        if checker is not None and checker["verdict"] == "refuted":
            dimensions = _dimensions(source, is_lens=is_lens)
            dropped.append({
                "id": identifier,
                "area": "lens:%s" % _first_text(source.get("dimension"), dimensions[0]) if is_lens
                        else _first_text(source.get("area"), "unknown"),
                "file": _required_text(source.get("file"), "file for %s" % identifier),
                "line": _audit_line(source.get("line")),
                "title": _elided(_required_text(_title(source), "title for %s" % identifier), 80),
                "reason": _required_text(checker.get("reason"), "reason for %s" % identifier),
            })
            continue
        findings.append(_finding(source, checker, is_lens=is_lens))

    allowed = trust_info.get("allowed")
    consent = trust_info.get("consent", False) if allowed is False else trust_info.get("consent")
    if not isinstance(allowed, bool) or not isinstance(consent, bool):
        raise ValueError("trust allowed and consent must be booleans")
    execution_enabled = allowed and consent
    coverage_notes = []
    assumptions = []
    disabled_reason = None
    if execution_enabled:
        assumptions.append(
            "Deep mode execution consent granted for isolated throwaway copies "
            "(%s, %s, budget %sm; forge commands disabled)." % (
                trust_info.get("sandbox_kind"), trust_info.get("copy_kind"), budget_info.get("budget_minutes")))
    elif not allowed:
        disabled_reason = _required_text(trust_info.get("reason"), "trust reason")
        coverage_notes.append("⚠ Deep repros disabled: %s" % disabled_reason)
    else:
        disabled_reason = "execution consent was declined"
        coverage_notes.append("⚠ Deep repros disabled: %s" % disabled_reason)
    isolation_warning = trust_info.get("isolation_warning")
    if execution_enabled and isolation_warning:
        coverage_notes.append("⚠ Deep execution isolation: " + _required_text(
            isolation_warning, "isolation warning"))
        assumptions.append(isolation_warning)

    unreached = []
    budget_expired = []
    over_capacity = []
    unexamined = {}
    for area in areas:
        identifier = _required_text(area.get("id"), "area id")
        status = area.get("status")
        if status == "read_only_degraded":
            reason = _required_text(area.get("degraded_reason"), "degraded reason for %s" % identifier)
            coverage_notes.append("⚠ Area %s ran read-only: %s" % (identifier, reason))
        if status not in _HUNK_CHECKED_STATUSES:
            unreached.append(identifier)
            (over_capacity if area.get("degraded_reason") == "capacity" else budget_expired).append(identifier)
        elif "hunks" in area:
            missing = _unexamined_hunks(area, identifier)
            if missing:
                unexamined[identifier] = missing
                unreached.append(identifier)
    if budget_expired:
        coverage_notes.append("⚠ Incomplete deep review: budget expired before reaching " + ", ".join(budget_expired))
    if over_capacity:
        coverage_notes.append("⚠ Incomplete deep review: not hunted (over capacity): " + ", ".join(over_capacity))
    if unexamined:
        coverage_notes.append("⚠ Incomplete deep review: hunks left unexamined in " + ", ".join(
            "%s (%s)" % (identifier, ", ".join(missing)) for identifier, missing in unexamined.items()))
    if checker_failures:
        coverage_notes.append("⚠ Unchecked claims withheld: " + ", ".join(checker_failures))
    elapsed, budget = budget_info["elapsed_minutes"], budget_info["budget_minutes"]
    if elapsed > budget:
        coverage_notes.append("Deep review exceeded its time budget (%sm of %sm)" % (
            _minutes(elapsed), _minutes(budget)))
    incomplete = bool(unreached or checker_failures)

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
        "snapshot_kind": trust_info.get("snapshot_kind"),
        "os_enforced": trust_info.get("os_enforced"),
        "isolation_warning": isolation_warning,
        "areas": areas,
        "unreached_areas": unreached,
        "unexamined": unexamined,
        "checked_and_dropped": dropped,
        "checker_failures": dict(checker_failures),
    }
    hunk_coverage = _hunk_coverage(areas)
    if hunk_coverage:
        deep["hunk_coverage"] = hunk_coverage
    return {"findings": _deduplicate(findings), "deep": deep, "incomplete": incomplete,
            "verdict_override": "Incomplete review" if incomplete else None,
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
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
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
