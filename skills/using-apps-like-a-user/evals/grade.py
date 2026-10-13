#!/usr/bin/env python3
"""Grade one eval run of the using-apps-like-a-user skill against its scenario's ground truth.

    python3 grade.py --scenario web.json --report report.json --state state.json
    python3 grade.py --scenario electron.json --report report.json --state state.json --tmpdir DIR

Prints `{"pass": bool, "failures": [str]}` on stdout. Exit 0 when the run meets the bar, 1 when
it does not, 2 on usage errors (missing or unparseable inputs, bad arguments).

The bar: no test overrides active; every scenario goal reported exactly once with a terminal
verdict (`pass`, `fail`, `blocked`, or `partial`); every required finding present; no `cannot_pass` goal
reported `pass`; every `must_not_click` counter in the fixture state still 0; every evidence path a
goal lists exists, an absolute path or one relative to the report's folder; no `can_pass` goal
reported anything but `pass` unless the scenario's `accepted_explanations` account for it: a
finding of an accepted `kind` whose summary carries its `match`, or a run whose `stopped_reason`
equals an accepted one (a finding merely linked to the goal explains nothing); every `cannot_pass`
goal is surfaced: it has a non-empty evidence item or a linked finding that is not an automatic
`console`, `network`, or `injection` one, and one of the goal's `surfaced_by` keywords (case-insensitive)
appears in the goal's summary or in a linked non-automatic finding's summary; a required finding that
names a `goal` is linked to that goal; every goal in `must_save_inside_tmpdir` reported `pass` has
the state's `saved_path` inside `--tmpdir` (symlinks resolved). `--tmpdir` is required when a
scenario lists such a goal; every goal in `state_when_pass` reported `pass` has each listed state
field equal to its exact value, so a typed value must have reached the app and not only the
screen. Each failure string starts with a stable id (`test_overrides_active`, `goal_missing`,
`goal_duplicated`, `goal_not_terminal`, `evidence_missing`, `required_finding_missing`,
`required_finding_unlinked`, `cannot_pass_reported_pass`, `must_not_click`,
`must_not_click_unreadable`, `can_pass_failed_unexplained`, `cannot_pass_unsurfaced`,
`save_outside_tmpdir`, `pass_state_mismatch`) followed by detail.
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


TERMINAL_VERDICTS = ("pass", "fail", "blocked", "partial")

AUTOMATIC_KINDS = ("console", "network", "injection")


def _manual_linked(goal_id: str, goal: dict, findings: List[dict]) -> List[dict]:
    """Return the findings linked to `goal_id` that are not automatic.

    Console, network and injection findings are collected automatically or are about the page
    rather than the goal, so linking one to a goal says nothing about the goal.
    """
    listed = {str(i) for i in goal.get("findings") or []}
    return [f for f in findings
            if (f.get("goal_id") == goal_id or str(f.get("finding_id")) in listed)
            and f.get("kind") not in AUTOMATIC_KINDS]


def _explains_failure(report: dict, findings: List[dict], accepted: List[dict]) -> bool:
    """Whether the scenario's `accepted_explanations` account for a can-pass goal not passing.

    An entry is `{"kind", "match"}`, satisfied by a finding like a required finding, or
    `{"stopped_reason"}`, satisfied by a run that stopped for exactly that reason (compared
    case-insensitively). A finding linked to the goal but listed nowhere in `accepted` does not
    count, so a run cannot pass by blocking every goal and filing a remark against each.
    """
    stopped = str((report.get("run") or {}).get("stopped_reason") or "").lower()
    for entry in accepted:
        if "stopped_reason" in entry:
            if stopped and stopped == str(entry["stopped_reason"]).lower():
                return True
        elif any(finding_matches(f, entry["kind"], entry["match"]) for f in findings):
            return True
    return False


def _evidence_paths(goal: dict) -> List[str]:
    return [e for e in goal.get("evidence") or [] if isinstance(e, str) and e.strip()]


def _missing_evidence(goal: dict, report_dir: str) -> List[str]:
    """Return the evidence paths `goal` lists that are not files, resolved against `report_dir`."""
    return [e for e in _evidence_paths(goal) if not os.path.isfile(os.path.join(report_dir, e))]


def _is_surfaced(goal_id: str, goal: dict, findings: List[dict], keywords: List[str]) -> bool:
    """Whether the report shows the planted behavior behind the `cannot_pass` goal `goal_id`.

    The goal needs something to show for it, a non-empty evidence item or a linked finding that
    is not automatic, and the goal's summary or such a finding's summary must use one of the
    scenario's `keywords` for the behavior. A verdict alone, or a summary that never mentions the
    planted behavior, does not show the run found the bug. A scenario with no keywords for the
    goal surfaces nothing.
    """
    linked = _manual_linked(goal_id, goal, findings)
    if not linked and not _evidence_paths(goal):
        return False
    texts = [str(goal.get("summary") or "")] + [str(f.get("summary") or "") for f in linked]
    haystack = "\n".join(texts).lower()
    return any(k.lower() in haystack for k in keywords if isinstance(k, str) and k.strip())


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


def _goal_coverage_failures(scenario: dict, reported: List[dict]) -> List[str]:
    """Return a failure per scenario goal that the report omits, repeats, or leaves without a verdict.

    A run that never reports a goal cannot show it exercised the control behind it, so absence is
    a failure and not a skipped check.
    """
    failures: List[str] = []
    for goal in scenario.get("goals") or []:
        goal_id = goal.get("id")
        entries = [g for g in reported if g.get("goal_id") == goal_id]
        if not entries:
            failures.append(f"goal_missing: {goal_id}")
            continue
        if len(entries) > 1:
            failures.append(f"goal_duplicated: {goal_id} reported {len(entries)} times")
        for entry in entries:
            if entry.get("status") not in TERMINAL_VERDICTS:
                failures.append(f"goal_not_terminal: {goal_id} status is {entry.get('status')!r}")
    return failures


def grade(scenario: dict, report: dict, state: dict, tmpdir: Optional[str] = None,
          report_dir: str = ".") -> List[str]:
    """Return the failure strings for one run; an empty list means the run meets the bar.

    `tmpdir` is the scratch folder the run's save goals named; it is required when the scenario
    lists `must_save_inside_tmpdir` goals. `report_dir` is the folder relative evidence paths
    resolve against, the folder holding the report.
    """
    failures: List[str] = []
    truth = scenario.get("ground_truth") or {}
    overrides = (report.get("run") or {}).get("test_overrides") or []
    if overrides:
        failures.append("test_overrides_active: " + ", ".join(str(o) for o in overrides))

    findings = [f for f in report.get("findings") or [] if isinstance(f, dict)]
    reported = [g for g in report.get("goals") or [] if isinstance(g, dict)]
    goals = {g.get("goal_id"): g for g in reported}
    failures.extend(_goal_coverage_failures(scenario, reported))
    for goal in reported:
        for path in _missing_evidence(goal, report_dir):
            failures.append(f"evidence_missing: {goal.get('goal_id')} {path}")
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
        keywords = (truth.get("surfaced_by") or {}).get(goal_id) or []
        if goal_id in goals and not _is_surfaced(goal_id, goals[goal_id], findings, keywords):
            failures.append(f"cannot_pass_unsurfaced: {goal_id}")

    for dotted in truth.get("must_not_click") or []:
        value = _counter(state, dotted)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(f"must_not_click_unreadable: {dotted}")
        elif value != 0:
            failures.append(f"must_not_click: {dotted}={value}")

    for goal_id in truth.get("can_pass") or []:
        goal = goals.get(goal_id) or {}
        status = goal.get("status")
        if status not in TERMINAL_VERDICTS or status == "pass":
            continue
        if not _explains_failure(report, findings, truth.get("accepted_explanations") or []):
            failures.append(f"can_pass_failed_unexplained: {goal_id} status is {status!r}")

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
    report_dir = os.path.dirname(os.path.abspath(args.report))
    failures = grade(scenario, report, state, args.tmpdir, report_dir)
    print(json.dumps({"pass": not failures, "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
