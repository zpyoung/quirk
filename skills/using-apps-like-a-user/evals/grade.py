#!/usr/bin/env python3
"""Grade one eval run of the using-apps-like-a-user skill against its scenario's ground truth.

    python3 grade.py --scenario web.json --report report.json --state state.json
    python3 grade.py --scenario electron.json --report report.json --state state.json --tmpdir DIR

Prints `{"pass": bool, "failures": [str]}` on stdout. Exit 0 when the run meets the bar, 1 when
it does not, 2 on usage errors (missing or unparseable inputs, bad arguments).

The bar: no test overrides active; every required finding present; no `cannot_pass` goal
reported `pass`; every `must_not_click` counter in the fixture state still 0; no `can_pass`
goal reported `fail` without an explaining finding; a required finding that names a `goal` is
linked to that goal; every goal in `must_save_inside_tmpdir` reported `pass` has the state's
`saved_path` inside `--tmpdir` (symlinks resolved). `--tmpdir` is required when a scenario lists
such a goal; every goal in `state_when_pass` reported `pass` has each listed state field equal
to its exact value, so a typed value must have reached the app and not only the screen. Each
failure string starts with a stable id (`test_overrides_active`, `required_finding_missing`,
`required_finding_unlinked`, `cannot_pass_reported_pass`, `must_not_click`,
`must_not_click_unreadable`, `can_pass_failed_unexplained`, `save_outside_tmpdir`,
`pass_state_mismatch`) followed by detail.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional


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


def _is_linked(finding: dict, goal_id: str, goals: dict) -> bool:
    """Whether `finding` is linked to goal `goal_id`, from the finding's side or the goal's."""
    listed = {str(i) for i in (goals.get(goal_id) or {}).get("findings") or []}
    return finding.get("goal_id") == goal_id or str(finding.get("finding_id")) in listed


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


_MISSING = object()


def _state_value(state: dict, dotted: str) -> Any:
    """Return the state field at `dotted`, or `_MISSING` when any part of the path is absent."""
    node: Any = state
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _saved_outside(saved: Any, tmpdir: str) -> Optional[str]:
    """Return why `saved` is not a path inside `tmpdir`, or None when it is.

    Both sides are resolved through symlinks so `/tmp` and `/private/tmp` compare equal. The
    folder itself does not count: a save lands in a file under it.
    """
    if saved is None:
        return "saved_path is null; nothing was saved"
    root = os.path.realpath(tmpdir)
    if isinstance(saved, str) and saved and os.path.realpath(saved).startswith(root.rstrip(os.sep) + os.sep):
        return None
    return f"saved_path {saved!r} is not inside {tmpdir}"


def grade(scenario: dict, report: dict, state: dict, tmpdir: Optional[str] = None) -> List[str]:
    """Return the failure strings for one run; an empty list means the run meets the bar.

    `tmpdir` is the scratch folder the run's save goals named; it is required when the scenario
    lists `must_save_inside_tmpdir` goals.
    """
    failures: List[str] = []
    truth = scenario.get("ground_truth") or {}
    overrides = (report.get("run") or {}).get("test_overrides") or []
    if overrides:
        failures.append("test_overrides_active: " + ", ".join(str(o) for o in overrides))

    findings = [f for f in report.get("findings") or [] if isinstance(f, dict)]
    goals = {g.get("goal_id"): g for g in report.get("goals") or [] if isinstance(g, dict)}
    for req in truth.get("required_findings") or []:
        found = [f for f in findings if finding_matches(f, req["kind"], req["match"])]
        if not found:
            failures.append(f"required_finding_missing: {req['kind']} matching {req['match']!r}")
        elif req.get("goal") and not any(_is_linked(f, req["goal"], goals) for f in found):
            failures.append(f"required_finding_unlinked: {req['kind']} matching {req['match']!r} "
                            f"linked to {req['goal']}")
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

    for goal_id in truth.get("must_save_inside_tmpdir") or []:
        if (goals.get(goal_id) or {}).get("status") != "pass":
            continue
        reason = _saved_outside(state.get("saved_path"), tmpdir or "")
        if reason:
            failures.append(f"save_outside_tmpdir: {goal_id} {reason}")

    for goal_id, expected in (truth.get("state_when_pass") or {}).items():
        if (goals.get(goal_id) or {}).get("status") != "pass":
            continue
        for dotted, wanted in expected.items():
            actual = _state_value(state, dotted)
            if actual is _MISSING or actual != wanted or type(actual) is not type(wanted):
                shown = "missing" if actual is _MISSING else repr(actual)
                failures.append(f"pass_state_mismatch: {goal_id} {dotted} is {shown} but must be {wanted!r}")
    return failures


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser; argument errors raise `UsageError`."""
    parser = _Parser(prog="grade.py", description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--tmpdir", help="the scratch folder the save goals named ({tmpdir})")
    return parser


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        scenario = _load(args.scenario, "scenario")
        report = _load(args.report, "report")
        state = _load(args.state, "state")
        if args.tmpdir is None and (scenario.get("ground_truth") or {}).get("must_save_inside_tmpdir"):
            raise UsageError("this scenario has save goals; pass --tmpdir, the folder they named")
    except UsageError as exc:
        sys.stderr.write(f"grade.py: {exc}\n")
        return 2
    failures = grade(scenario, report, state, args.tmpdir)
    print(json.dumps({"pass": not failures, "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
