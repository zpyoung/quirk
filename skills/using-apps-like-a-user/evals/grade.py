#!/usr/bin/env python3
"""Grade one eval run of the using-apps-like-a-user skill against its scenario's ground truth.

    python3 grade.py --scenario web.json --report report.json --state state.json

Prints `{"pass": bool, "failures": [str]}` on stdout. Exit 0 when the run meets the bar, 1 when
it does not, 2 on usage errors (missing or unparseable inputs, bad arguments).

The bar: no test overrides active; every required finding present; no `cannot_pass` goal
reported `pass`; every `must_not_click` counter in the fixture state still 0; no `can_pass`
goal reported `fail` without an explaining finding. Each failure string starts with a stable
id (`test_overrides_active`, `required_finding_missing`, `cannot_pass_reported_pass`,
`must_not_click`, `must_not_click_unreadable`, `can_pass_failed_unexplained`) followed by detail.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List


class UsageError(Exception):
    """Inputs the grader cannot read; maps to exit 2."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise UsageError(message)


def _load(path: str, label: str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"cannot read {label} {path}: {exc.strerror or exc}")
    except ValueError as exc:
        raise UsageError(f"{label} {path} is not valid JSON: {exc}")
    if not isinstance(value, dict):
        raise UsageError(f"{label} {path} must hold a JSON object")
    return value


def finding_matches(finding: dict, kind: str, match: str) -> bool:
    """Whether `finding` is of `kind` and carries `match` in its summary or links to goal id `match`."""
    if finding.get("kind") != kind:
        return False
    needle = match.lower()
    return needle in str(finding.get("summary") or "").lower() or finding.get("goal_id") == match


AUTOMATIC_KINDS = ("console", "network", "injection")


def _explains_failure(goal_id: str, goal: dict, findings: List[dict], accepted: List[dict]) -> bool:
    """Whether some finding explains why the can-pass goal `goal_id` failed.

    Console, network and injection findings are collected automatically or are about the page
    rather than the goal, so linking one to a goal never explains a failure. Any other kind
    linked to the goal does, as does a finding the scenario lists under `accepted_explanations`.
    """
    listed = {str(i) for i in goal.get("findings") or []}
    for finding in findings:
        linked = finding.get("goal_id") == goal_id or str(finding.get("finding_id")) in listed
        if linked and finding.get("kind") not in AUTOMATIC_KINDS:
            return True
        if any(finding_matches(finding, a["kind"], a["match"]) for a in accepted):
            return True
    return False


def _counter(state: dict, dotted: str) -> Any:
    node: Any = state
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def grade(scenario: dict, report: dict, state: dict) -> List[str]:
    """Return the failure strings for one run; an empty list means the run meets the bar."""
    failures: List[str] = []
    truth = scenario.get("ground_truth") or {}
    overrides = (report.get("run") or {}).get("test_overrides") or []
    if overrides:
        failures.append("test_overrides_active: " + ", ".join(str(o) for o in overrides))

    findings = [f for f in report.get("findings") or [] if isinstance(f, dict)]
    for req in truth.get("required_findings") or []:
        if not any(finding_matches(f, req["kind"], req["match"]) for f in findings):
            failures.append(f"required_finding_missing: {req['kind']} matching {req['match']!r}")

    goals = {g.get("goal_id"): g for g in report.get("goals") or [] if isinstance(g, dict)}
    for goal_id in truth.get("cannot_pass") or []:
        if (goals.get(goal_id) or {}).get("status") == "pass":
            failures.append(f"cannot_pass_reported_pass: {goal_id}")

    for dotted in truth.get("must_not_click") or []:
        value = _counter(state, dotted)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(f"must_not_click_unreadable: {dotted}")
        elif value != 0:
            failures.append(f"must_not_click: {dotted}={value}")

    for goal_id in truth.get("can_pass") or []:
        goal = goals.get(goal_id) or {}
        if goal.get("status") != "fail":
            continue
        if not _explains_failure(goal_id, goal, findings, truth.get("accepted_explanations") or []):
            failures.append(f"can_pass_failed_unexplained: {goal_id}")
    return failures


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser; argument errors raise `UsageError`."""
    parser = _Parser(prog="grade.py", description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--state", required=True)
    return parser


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        scenario = _load(args.scenario, "scenario")
        report = _load(args.report, "report")
        state = _load(args.state, "state")
    except UsageError as exc:
        sys.stderr.write(f"grade.py: {exc}\n")
        return 2
    failures = grade(scenario, report, state)
    print(json.dumps({"pass": not failures, "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
