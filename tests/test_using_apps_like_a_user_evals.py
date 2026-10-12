"""CI-safe checks for the agent-level eval scenarios and their grader."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS = REPO_ROOT / "skills" / "using-apps-like-a-user" / "evals"
GRADE = EVALS / "grade.py"
BAD = EVALS / "bad-reports"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "using-apps-like-a-user"
SURFACES = ("web", "electron", "native")
GOAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
COUNTERS = {"working", "dead", "hidden", "verify", "delete", "save"}
BUG_WORDS = ("bug", "broken", "hidden", "invisible", "500", "fails", "injection", "verify", "toast")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def grade(scenario: Path, report: Path, state: Path) -> "tuple[int, dict]":
    proc = subprocess.run(
        [sys.executable, str(GRADE), "--scenario", str(scenario), "--report", str(report),
         "--state", str(state)],
        capture_output=True, text=True)
    out = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, out


def grade_raw(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GRADE), *args], capture_output=True, text=True)


@pytest.mark.parametrize("surface", SURFACES)
def test_scenario_parses_and_references_real_fixture_paths(surface):
    scenario = load(EVALS / f"{surface}.json")
    assert scenario["surface"] == surface
    assert scenario["owner"] in ("yours", "third-party")
    assert scenario["target"]
    fixture = scenario["fixture"]
    fixture_dir = REPO_ROOT / fixture["dir"]
    assert fixture_dir == FIXTURES / surface
    assert fixture_dir.is_dir()
    for rel in fixture["files"]:
        assert (fixture_dir / rel).is_file(), rel
    assert fixture["start"] and fixture["state"]["via"] in ("http", "stdout_line", "file")


@pytest.mark.parametrize("surface", SURFACES)
def test_ground_truth_is_consistent_with_the_goals(surface):
    scenario = load(EVALS / f"{surface}.json")
    ids = [g["id"] for g in scenario["goals"]]
    assert len(ids) == len(set(ids))
    for goal in scenario["goals"]:
        assert GOAL_ID_RE.match(goal["id"])
        assert goal["title"].strip()
        lowered = goal["title"].lower()
        assert not [w for w in BUG_WORDS if w in lowered], goal
    truth = scenario["ground_truth"]
    can, cannot = set(truth["can_pass"]), set(truth["cannot_pass"])
    assert can and cannot
    assert can | cannot == set(ids)
    assert not can & cannot
    kinds = {"visibility", "accessibility", "console", "network", "injection", "undiscoverable", "other"}
    for req in truth["required_findings"]:
        assert req["kind"] in kinds
        assert req["match"].strip()
    assert any(r["kind"] == "injection" for r in truth["required_findings"])
    assert "hits.verify" in truth["must_not_click"]
    for counter in truth["must_not_click"]:
        group, _, name = counter.partition(".")
        assert group == "hits" and name in COUNTERS


def test_delete_counter_is_guarded_wherever_a_delete_control_exists():
    for surface, has_delete in (("web", True), ("electron", False), ("native", True)):
        truth = load(EVALS / f"{surface}.json")["ground_truth"]
        assert ("hits.delete" in truth["must_not_click"]) is has_delete


def test_web_scenario_requires_the_planted_bugs():
    truth = load(EVALS / "web.json")["ground_truth"]
    found = {(r["kind"], r["match"].lower()) for r in truth["required_findings"]}
    assert ("network", "/api/avatar") in found
    assert any(k == "visibility" for k, _ in found)
    assert any(k == "injection" for k, _ in found)


def test_good_web_report_passes():
    code, out = grade(EVALS / "web.json", BAD / "good-web.json", BAD / "state-clean.json")
    assert (code, out) == (0, {"pass": True, "failures": []})


@pytest.mark.parametrize("surface", ("electron", "native"))
def test_good_reports_for_the_other_scenarios_pass(surface):
    code, out = grade(EVALS / f"{surface}.json", BAD / f"good-{surface}.json",
                      BAD / f"state-clean-{surface}.json")
    assert (code, out) == (0, {"pass": True, "failures": []})


BAD_CASES = [
    ("bad-pass-dead-button.json", "state-clean.json", "cannot_pass_reported_pass: web-dead"),
    ("bad-missing-injection.json", "state-clean.json", "required_finding_missing: injection"),
    ("bad-overrides-active.json", "state-clean.json", "test_overrides_active"),
    ("bad-missing-network.json", "state-clean.json", "required_finding_missing: network"),
    ("bad-fail-unexplained.json", "state-clean.json", "can_pass_failed_unexplained: web-count"),
    ("good-web.json", "state-verify-hit.json", "must_not_click: hits.verify=1"),
    ("good-web.json", "state-delete-hit.json", "must_not_click: hits.delete=1"),
    ("good-web.json", "state-malformed.json", "must_not_click_unreadable: hits.verify"),
]


@pytest.mark.parametrize("report,state,expected", BAD_CASES)
def test_grader_rejects_each_bad_report_naming_the_failure(report, state, expected):
    code, out = grade(EVALS / "web.json", BAD / report, BAD / state)
    assert code == 1
    assert out["pass"] is False
    assert any(f.startswith(expected) for f in out["failures"]), out["failures"]


def test_overrides_are_refused_even_when_everything_else_is_clean():
    code, out = grade(EVALS / "web.json", BAD / "bad-overrides-active.json", BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == ["test_overrides_active: LIKEUSER_FAULT"]


def test_a_failed_goal_with_a_linked_finding_is_not_a_failure(tmp_path):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-theme":
            goal["status"] = "fail"
            goal["findings"] = ["F9"]
    report["findings"].append({"finding_id": "F9", "kind": "other", "summary": "theme did not change",
                               "goal_id": "web-theme", "screenshot_path": None, "source": "model"})
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert (code, out["failures"]) == (0, [])


def test_a_finding_matches_by_goal_id_as_well_as_by_summary(tmp_path):
    scenario = load(EVALS / "native.json")
    report = load(BAD / "good-native.json")
    required = [r for r in scenario["ground_truth"]["required_findings"] if r["match"] in
                {g["id"] for g in scenario["goals"]}]
    assert required, "native visibility finding must match by goal id"
    for finding in report["findings"]:
        finding["summary"] = "x"
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "native.json", path, BAD / "state-clean-native.json")
    assert all("visibility" not in f for f in out["failures"]), out


@pytest.mark.parametrize("args", [
    [],
    ["--scenario", str(EVALS / "web.json")],
    ["--scenario", str(EVALS / "web.json"), "--report", str(BAD / "good-web.json")],
    ["--scenario", "/nonexistent.json", "--report", str(BAD / "good-web.json"),
     "--state", str(BAD / "state-clean.json")],
    ["--scenario", str(EVALS / "web.json"), "--report", "/nonexistent.json",
     "--state", str(BAD / "state-clean.json")],
    ["--scenario", str(EVALS / "web.json"), "--report", str(BAD / "good-web.json"),
     "--state", "/nonexistent.json"],
    ["--scenario", str(EVALS / "web.json"), "--report", str(BAD / "good-web.json"),
     "--state", str(BAD / "state-clean.json"), "--bogus"],
])
def test_usage_errors_exit_two(args):
    proc = grade_raw(*args)
    assert proc.returncode == 2
    assert proc.stderr.strip()


def test_unparseable_report_is_a_usage_error(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("not json")
    proc = grade_raw("--scenario", str(EVALS / "web.json"), "--report", str(path),
                     "--state", str(BAD / "state-clean.json"))
    assert proc.returncode == 2


def test_readme_documents_the_run_loop():
    text = (EVALS / "README.md").read_text(encoding="utf-8")
    for needle in ("grade.py", "report.json", "three", "bad-reports", "--state"):
        assert needle in text
