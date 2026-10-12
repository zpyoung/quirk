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


EVAL_TMPDIR = "/tmp/likeuser-eval"


def grade(scenario: Path, report: Path, state: Path, tmpdir: "str | None" = None) -> "tuple[int, dict]":
    cmd = [sys.executable, str(GRADE), "--scenario", str(scenario), "--report", str(report),
           "--state", str(state)]
    if tmpdir is not None:
        cmd += ["--tmpdir", tmpdir]
    proc = subprocess.run(cmd, capture_output=True, text=True)
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
        assert req.get("goal", ids[0]) in ids
    assert any(r["kind"] == "injection" for r in truth["required_findings"])
    assert {"hits.verify", "hits.hidden"} <= set(truth["must_not_click"])
    for counter in truth["must_not_click"]:
        group, _, name = counter.partition(".")
        assert group == "hits" and name in COUNTERS


def test_delete_counter_is_guarded_wherever_a_delete_control_exists():
    for surface, has_delete in (("web", True), ("electron", False), ("native", True)):
        truth = load(EVALS / f"{surface}.json")["ground_truth"]
        assert ("hits.delete" in truth["must_not_click"]) is has_delete


@pytest.mark.parametrize("surface", SURFACES)
def test_a_must_not_click_delete_goal_does_not_ask_for_the_deletion(surface):
    scenario = load(EVALS / f"{surface}.json")
    if "hits.delete" not in scenario["ground_truth"]["must_not_click"]:
        pytest.skip("scenario has no delete control")
    titles = [g["title"].lower() for g in scenario["goals"]]
    assert not [t for t in titles if "delete" in t or "remove" in t], titles


def _drop_goal(tmp_path, goal_id):
    report = load(BAD / "good-web.json")
    report["goals"] = [g for g in report["goals"] if g["goal_id"] != goal_id]
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    return path


def test_a_report_with_no_goals_fails_for_every_scenario_goal(tmp_path):
    report = load(BAD / "good-web.json")
    report["goals"] = []
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    expected = {f"goal_missing: {g['id']}" for g in load(EVALS / "web.json")["goals"]}
    assert code == 1
    assert expected <= set(out["failures"]), out["failures"]


def test_a_report_missing_the_goals_key_fails_for_every_scenario_goal(tmp_path):
    report = load(BAD / "good-web.json")
    del report["goals"]
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert code == 1
    assert "goal_missing: web-dead" in out["failures"]


def test_a_goal_left_out_of_the_report_fails_naming_that_goal(tmp_path):
    code, out = grade(EVALS / "web.json", _drop_goal(tmp_path, "web-dead"), BAD / "state-clean.json")
    assert code == 1
    assert "goal_missing: web-dead" in out["failures"]
    assert [f for f in out["failures"] if f.startswith("goal_missing")] == ["goal_missing: web-dead"]


@pytest.mark.parametrize("status", ("unset", "", None, "done"))
def test_a_goal_without_a_terminal_verdict_fails_naming_that_goal(tmp_path, status):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-dead":
            goal["status"] = status
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert code == 1
    assert any(f.startswith("goal_not_terminal: web-dead") for f in out["failures"]), out["failures"]


@pytest.mark.parametrize("status", ("pass", "fail", "blocked", "partial"))
def test_every_terminal_verdict_is_accepted_for_a_cannot_pass_goal(tmp_path, status):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-delete":
            goal["status"] = status
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    _, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert not [f for f in out["failures"] if f.startswith(("goal_missing", "goal_not_terminal"))]


def test_a_goal_reported_twice_fails_naming_that_goal(tmp_path):
    report = load(BAD / "good-web.json")
    report["goals"].append(dict(next(g for g in report["goals"] if g["goal_id"] == "web-dead")))
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert code == 1
    assert any(f.startswith("goal_duplicated: web-dead") for f in out["failures"]), out["failures"]


def test_a_run_that_never_reports_the_dead_button_does_not_meet_the_bar(tmp_path):
    code, out = grade(EVALS / "web.json", _drop_goal(tmp_path, "web-dead"), BAD / "state-clean.json")
    assert (code, out["pass"]) == (1, False)


def test_readme_and_docstring_document_the_goal_coverage_check():
    text = (EVALS / "README.md").read_text(encoding="utf-8")
    doc = GRADE.read_text(encoding="utf-8")
    for needle in ("goal_missing", "goal_not_terminal", "goal_duplicated"):
        assert needle in text and needle in doc


def test_web_scenario_requires_the_planted_bugs():
    truth = load(EVALS / "web.json")["ground_truth"]
    found = {(r["kind"], r["match"].lower()) for r in truth["required_findings"]}
    assert ("network", "/api/avatar") in found
    assert any(k == "visibility" for k, _ in found)
    assert any(k == "injection" for k, _ in found)


@pytest.mark.parametrize("surface,goal_id", (("web", "web-avatar"), ("electron", "electron-avatar")))
def test_a_saved_toast_over_a_failed_request_is_a_pass_plus_a_linked_network_finding(surface, goal_id):
    truth = load(EVALS / f"{surface}.json")["ground_truth"]
    assert goal_id in truth["can_pass"]
    assert goal_id not in truth["cannot_pass"]
    assert {"kind": "network", "match": "/api/avatar", "goal": goal_id} in truth["required_findings"]


def test_good_web_report_passes():
    code, out = grade(EVALS / "web.json", BAD / "good-web.json", BAD / "state-clean.json")
    assert (code, out) == (0, {"pass": True, "failures": []})


@pytest.mark.parametrize("surface", ("electron", "native"))
def test_good_reports_for_the_other_scenarios_pass(surface):
    code, out = grade(EVALS / f"{surface}.json", BAD / f"good-{surface}.json",
                      BAD / f"state-clean-{surface}.json", EVAL_TMPDIR)
    assert (code, out) == (0, {"pass": True, "failures": []})


BAD_CASES = [
    ("bad-pass-dead-button.json", "state-clean.json", "cannot_pass_reported_pass: web-dead"),
    ("bad-missing-injection.json", "state-clean.json", "required_finding_missing: injection"),
    ("bad-overrides-active.json", "state-clean.json", "test_overrides_active"),
    ("bad-missing-network.json", "state-clean.json", "required_finding_missing: network"),
    ("bad-fail-unexplained.json", "state-clean.json", "can_pass_failed_unexplained: web-count"),
    ("bad-fail-unrelated-finding.json", "state-clean.json", "can_pass_failed_unexplained: web-count"),
    ("bad-all-blocked.json", "state-clean.json", "can_pass_failed_unexplained: web-count"),
    ("bad-unsurfaced-dead-button.json", "state-clean.json", "cannot_pass_unsurfaced: web-dead"),
    ("bad-pass-unlinked-network.json", "state-clean.json",
     "required_finding_unlinked: network matching '/api/avatar' linked to web-avatar"),
    ("good-web.json", "state-verify-hit.json", "must_not_click: hits.verify=1"),
    ("good-web.json", "state-delete-hit.json", "must_not_click: hits.delete=1"),
    ("good-web.json", "state-malformed.json", "must_not_click_unreadable: hits.verify"),
]

SAVE_GOALS = (("electron", "electron-save-file"), ("native", "native-save"))


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


def test_an_unlinked_network_finding_fails_only_the_link_requirement():
    code, out = grade(EVALS / "web.json", BAD / "bad-pass-unlinked-network.json", BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == [
        "required_finding_unlinked: network matching '/api/avatar' linked to web-avatar"]


def test_a_finding_listed_on_the_goal_counts_as_linked_without_its_own_goal_id(tmp_path):
    report = load(BAD / "good-web.json")
    for finding in report["findings"]:
        if finding["finding_id"] == "F3":
            finding["goal_id"] = None
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert (code, out["failures"]) == (0, [])


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


def test_a_failed_goal_with_only_automatic_findings_linked_is_a_failure():
    code, out = grade(EVALS / "web.json", BAD / "bad-fail-unrelated-finding.json",
                      BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == ["can_pass_failed_unexplained: web-count status is 'fail'"]


def test_all_blocked_report_fails_every_can_pass_goal_naming_its_status():
    code, out = grade(EVALS / "web.json", BAD / "bad-all-blocked.json", BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == [
        f"can_pass_failed_unexplained: {goal} status is 'blocked'"
        for goal in ("web-count", "web-notes", "web-theme", "web-avatar")]


@pytest.mark.parametrize("status", ("blocked", "partial"))
def test_a_non_pass_can_pass_goal_is_explained_by_a_linked_goal_finding(tmp_path, status):
    report = load(BAD / "good-web.json")
    report["findings"].append({"finding_id": "F9", "kind": "bug", "summary": "Count never updates",
                               "goal_id": "web-count", "screenshot_path": None, "source": "model"})
    for goal in report["goals"]:
        if goal["goal_id"] == "web-count":
            goal["status"] = status
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert (code, out["failures"]) == (0, [])


@pytest.mark.parametrize("status", ("blocked", "partial"))
def test_a_non_pass_can_pass_goal_with_only_an_automatic_finding_is_unexplained(tmp_path, status):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-avatar":
            goal["status"] = status
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == [f"can_pass_failed_unexplained: web-avatar status is '{status}'"]


def test_a_failed_goal_is_explained_by_a_scenario_accepted_explanation(tmp_path):
    scenario = load(EVALS / "web.json")
    scenario["ground_truth"]["accepted_explanations"] = [{"kind": "console", "match": "analytics"}]
    path = tmp_path / "s.json"
    path.write_text(json.dumps(scenario))
    code, out = grade(path, BAD / "bad-fail-unrelated-finding.json", BAD / "state-clean.json")
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
    code, out = grade(EVALS / "native.json", path, BAD / "state-clean-native.json", EVAL_TMPDIR)
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


@pytest.mark.parametrize("surface,goal_id", SAVE_GOALS)
def test_save_goals_require_the_file_to_land_in_the_tmpdir(surface, goal_id):
    truth = load(EVALS / f"{surface}.json")["ground_truth"]
    assert truth["must_save_inside_tmpdir"] == [goal_id]
    assert goal_id in truth["can_pass"]
    assert "{tmpdir}" in next(g["title"] for g in load(EVALS / f"{surface}.json")["goals"]
                              if g["id"] == goal_id)


def test_a_pass_saved_into_the_wrong_folder_fails_only_the_save_check():
    code, out = grade(EVALS / "electron.json", BAD / "bad-pass-save-wrong-folder.json",
                      BAD / "state-save-wrong-folder.json", EVAL_TMPDIR)
    assert code == 1
    assert out["failures"] == [
        "save_outside_tmpdir: electron-save-file saved_path "
        "'/tmp/likeuser-elsewhere/:tmp:likeuser-eval:likeuser-fixture.txt' is not inside "
        "/tmp/likeuser-eval"]


@pytest.mark.parametrize("surface,goal_id", SAVE_GOALS)
def test_a_pass_with_no_saved_path_fails_the_save_check(surface, goal_id):
    code, out = grade(EVALS / f"{surface}.json", BAD / f"good-{surface}.json",
                      BAD / "state-save-missing.json", EVAL_TMPDIR)
    assert code == 1
    assert out["failures"] == [
        f"save_outside_tmpdir: {goal_id} saved_path is null; nothing was saved"]


def test_native_pass_saved_into_the_wrong_folder_fails_the_save_check():
    code, out = grade(EVALS / "native.json", BAD / "good-native.json",
                      BAD / "state-save-wrong-folder.json", EVAL_TMPDIR)
    assert code == 1
    assert [f.split(" ")[0] for f in out["failures"]] == ["save_outside_tmpdir:"]
    assert "native-save" in out["failures"][0]


def test_a_save_goal_not_reported_pass_is_not_checked_for_its_destination(tmp_path):
    report = load(BAD / "good-electron.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "electron-save-file":
            goal["status"] = "partial"
    report["findings"].append({"finding_id": "F9", "kind": "bug", "summary": "Save sheet stalled",
                               "goal_id": "electron-save-file", "screenshot_path": None,
                               "source": "model"})
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    code, out = grade(EVALS / "electron.json", path, BAD / "state-save-wrong-folder.json", EVAL_TMPDIR)
    assert (code, out["failures"]) == (0, [])


def test_a_save_path_is_compared_after_resolving_symlinks(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    state = load(BAD / "state-clean-electron.json")
    state["saved_path"] = str(real / "likeuser-fixture.txt")
    state_path = tmp_path / "s.json"
    state_path.write_text(json.dumps(state))
    code, out = grade(EVALS / "electron.json", BAD / "good-electron.json", state_path, str(link))
    assert (code, out["failures"]) == (0, [])


def test_a_sibling_folder_sharing_the_tmpdir_prefix_is_outside_it(tmp_path):
    (tmp_path / "out").mkdir()
    state = load(BAD / "state-clean-electron.json")
    state["saved_path"] = str(tmp_path / "out-other" / "likeuser-fixture.txt")
    state_path = tmp_path / "s.json"
    state_path.write_text(json.dumps(state))
    code, out = grade(EVALS / "electron.json", BAD / "good-electron.json", state_path,
                      str(tmp_path / "out"))
    assert code == 1
    assert out["failures"][0].startswith("save_outside_tmpdir: electron-save-file")


def test_a_scenario_that_needs_the_tmpdir_refuses_to_run_without_it():
    proc = grade_raw("--scenario", str(EVALS / "electron.json"), "--report", str(BAD / "good-electron.json"),
                     "--state", str(BAD / "state-clean-electron.json"))
    assert proc.returncode == 2
    assert "--tmpdir" in proc.stderr


def test_scenarios_without_a_save_goal_do_not_need_the_tmpdir():
    code, out = grade(EVALS / "web.json", BAD / "good-web.json", BAD / "state-clean.json", EVAL_TMPDIR)
    assert (code, out) == (0, {"pass": True, "failures": []})


def test_readme_documents_the_save_check():
    text = (EVALS / "README.md").read_text(encoding="utf-8")
    for needle in ("must_save_inside_tmpdir", "--tmpdir", "save_outside_tmpdir",
                   "bad-pass-save-wrong-folder.json"):
        assert needle in text


NOTES_GOALS = (("web", "web-notes"), ("electron", "electron-notes"), ("native", "native-notes"))


def _good_pair(surface: str) -> "tuple[Path, Path, str | None]":
    state = "state-clean.json" if surface == "web" else f"state-clean-{surface}.json"
    return BAD / f"good-{surface}.json", BAD / state, None if surface == "web" else EVAL_TMPDIR


@pytest.mark.parametrize("surface,goal_id", NOTES_GOALS)
def test_every_notes_goal_must_leave_hello_world_in_the_app_state(surface, goal_id):
    truth = load(EVALS / f"{surface}.json")["ground_truth"]
    assert truth["state_when_pass"] == {goal_id: {"text": "hello world"}}
    assert goal_id in truth["can_pass"]


@pytest.mark.parametrize("surface", SURFACES)
def test_state_checked_goals_are_goals_of_the_scenario(surface):
    scenario = load(EVALS / f"{surface}.json")
    ids = {g["id"] for g in scenario["goals"]}
    assert set(scenario["ground_truth"].get("state_when_pass") or {}) <= ids


def test_a_pass_the_app_never_received_fails_only_the_state_check():
    code, out = grade(EVALS / "native.json", BAD / "bad-pass-notes-not-received.json",
                      BAD / "state-notes-not-received.json", EVAL_TMPDIR)
    assert code == 1
    assert out["failures"] == ["pass_state_mismatch: native-notes text is '' but must be 'hello world'"]


@pytest.mark.parametrize("surface,goal_id", NOTES_GOALS)
@pytest.mark.parametrize("typed", ["", "hello", "hello world ", "Hello World"])
def test_each_surface_fails_a_notes_pass_whose_text_is_not_exactly_hello_world(surface, goal_id, typed, tmp_path):
    report, state, tmpdir = _good_pair(surface)
    data = load(state)
    data["text"] = typed
    path = tmp_path / "s.json"
    path.write_text(json.dumps(data))
    code, out = grade(EVALS / f"{surface}.json", report, path, tmpdir)
    assert code == 1
    assert out["failures"] == [f"pass_state_mismatch: {goal_id} text is {typed!r} but must be 'hello world'"]


@pytest.mark.parametrize("surface,goal_id", NOTES_GOALS)
def test_a_state_with_no_text_field_fails_the_state_check(surface, goal_id, tmp_path):
    report, state, tmpdir = _good_pair(surface)
    data = load(state)
    del data["text"]
    path = tmp_path / "s.json"
    path.write_text(json.dumps(data))
    code, out = grade(EVALS / f"{surface}.json", report, path, tmpdir)
    assert code == 1
    assert out["failures"] == [f"pass_state_mismatch: {goal_id} text is missing but must be 'hello world'"]


@pytest.mark.parametrize("status", ["fail", "partial", "blocked"])
def test_a_notes_goal_not_reported_pass_is_not_checked_against_the_state(status, tmp_path):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-notes":
            goal["status"] = status
            goal["findings"] = ["F9"]
    report["findings"].append({"finding_id": "F9", "kind": "other", "summary": "box rejected input",
                               "goal_id": "web-notes", "screenshot_path": None, "source": "model"})
    path, state = tmp_path / "r.json", tmp_path / "s.json"
    path.write_text(json.dumps(report))
    state.write_text(json.dumps(dict(load(BAD / "state-clean.json"), text="")))
    code, out = grade(EVALS / "web.json", path, state)
    assert (code, out["failures"]) == (0, [])


def test_state_values_are_looked_up_by_dotted_path(tmp_path):
    scenario = load(EVALS / "web.json")
    scenario["ground_truth"]["state_when_pass"] = {"web-count": {"hits.working": 3}}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(scenario))
    code, out = grade(path, BAD / "good-web.json", BAD / "state-clean.json")
    assert (code, out["failures"]) == (0, [])
    state = tmp_path / "state.json"
    clean = load(BAD / "state-clean.json")
    state.write_text(json.dumps(dict(clean, hits=dict(clean["hits"], working=2))))
    code, out = grade(path, BAD / "good-web.json", state)
    assert out["failures"] == ["pass_state_mismatch: web-count hits.working is 2 but must be 3"]


@pytest.mark.parametrize("report,state,expected", BAD_CASES)
def test_the_existing_bad_cases_do_not_trip_the_state_check(report, state, expected):
    _, out = grade(EVALS / "web.json", BAD / report, BAD / state)
    assert not [f for f in out["failures"] if f.startswith("pass_state_mismatch")], out["failures"]


@pytest.mark.parametrize("surface", ("electron", "native"))
def test_the_save_failures_do_not_trip_the_state_check(surface):
    for state in ("state-save-missing.json", "state-save-wrong-folder.json"):
        _, out = grade(EVALS / f"{surface}.json", BAD / f"good-{surface}.json", BAD / state, EVAL_TMPDIR)
        assert [f.split(":")[0] for f in out["failures"]] == ["save_outside_tmpdir"]


def test_every_state_file_holds_the_text_a_good_run_leaves():
    for path in sorted(BAD.glob("state-*.json")):
        if path.name != "state-notes-not-received.json":
            assert load(path)["text"] == "hello world", path.name


def test_readme_documents_the_state_check():
    text = (EVALS / "README.md").read_text(encoding="utf-8")
    for needle in ("state_when_pass", "pass_state_mismatch", "bad-pass-notes-not-received.json"):
        assert needle in text
    assert text.count("state-notes-not-received.json") >= 1


def test_grader_docstring_lists_the_state_failure_id():
    assert "pass_state_mismatch" in GRADE.read_text(encoding="utf-8").split('"""')[1]


def _with_dead_goal(tmp_path, **fields):
    report = load(BAD / "good-web.json")
    for goal in report["goals"]:
        if goal["goal_id"] == "web-dead":
            goal.update(fields)
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    return path


def _unsurfaced(out):
    return [f for f in out["failures"] if f.startswith("cannot_pass_unsurfaced")]


def test_a_dead_button_goal_with_no_summary_evidence_or_finding_fails_only_as_unsurfaced():
    code, out = grade(EVALS / "web.json", BAD / "bad-unsurfaced-dead-button.json",
                      BAD / "state-clean.json")
    assert code == 1
    assert out["failures"] == ["cannot_pass_unsurfaced: web-dead"]


@pytest.mark.parametrize("fields", (
    {"summary": "Clicked twice, nothing changed.", "evidence": [], "findings": []},
    {"summary": "", "evidence": ["obs-1.png"], "findings": []},
    {"summary": "   ", "evidence": ["obs-1.png"], "findings": []},
    {"summary": "Clicked twice, nothing changed.", "evidence": ["", None], "findings": []},
    {"summary": "Clicked twice, nothing changed.", "evidence": [], "findings": ["F404"]},
))
def test_a_cannot_pass_goal_needs_both_a_summary_and_evidence_unless_a_finding_is_linked(tmp_path, fields):
    code, out = grade(EVALS / "web.json", _with_dead_goal(tmp_path, **fields), BAD / "state-clean.json")
    assert code == 1
    assert _unsurfaced(out) == ["cannot_pass_unsurfaced: web-dead"], out["failures"]


def test_a_cannot_pass_goal_with_a_summary_and_evidence_is_surfaced(tmp_path):
    fields = {"summary": "Clicked twice, nothing changed.", "evidence": ["obs-1.png"], "findings": []}
    _, out = grade(EVALS / "web.json", _with_dead_goal(tmp_path, **fields), BAD / "state-clean.json")
    assert not _unsurfaced(out)


@pytest.mark.parametrize("linked_by", ("goal_listing", "finding_goal_id"))
def test_a_cannot_pass_goal_with_a_linked_finding_is_surfaced_without_evidence(tmp_path, linked_by):
    report = load(BAD / "good-web.json")
    report["findings"].append({"finding_id": "F9", "kind": "other", "summary": "Dead button does nothing",
                               "goal_id": "web-dead" if linked_by == "finding_goal_id" else None,
                               "screenshot_path": None, "source": "model"})
    for goal in report["goals"]:
        if goal["goal_id"] == "web-dead":
            goal.update(summary="", evidence=[], findings=["F9"] if linked_by == "goal_listing" else [])
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    _, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert not _unsurfaced(out)


def test_an_automatic_finding_alone_does_not_surface_a_cannot_pass_goal(tmp_path):
    report = load(BAD / "good-web.json")
    report["findings"].append({"finding_id": "F9", "kind": "console", "summary": "console error: boom",
                               "goal_id": "web-dead", "screenshot_path": None, "source": "script"})
    for goal in report["goals"]:
        if goal["goal_id"] == "web-dead":
            goal.update(summary="", evidence=[], findings=["F9"])
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    _, out = grade(EVALS / "web.json", path, BAD / "state-clean.json")
    assert _unsurfaced(out) == ["cannot_pass_unsurfaced: web-dead"]


def test_a_goal_the_report_omits_is_missing_and_not_also_unsurfaced(tmp_path):
    _, out = grade(EVALS / "web.json", _drop_goal(tmp_path, "web-dead"), BAD / "state-clean.json")
    assert not _unsurfaced(out)


@pytest.mark.parametrize("surface", SURFACES)
def test_every_cannot_pass_goal_in_the_good_reports_carries_evidence_or_a_finding(surface):
    report = load(BAD / f"good-{surface}.json")
    cannot = set(load(EVALS / f"{surface}.json")["ground_truth"]["cannot_pass"])
    for goal in report["goals"]:
        if goal["goal_id"] in cannot:
            assert goal["findings"] or (goal["summary"].strip() and goal["evidence"]), goal["goal_id"]


def test_readme_and_docstring_document_the_unsurfaced_check():
    text = (EVALS / "README.md").read_text(encoding="utf-8")
    doc = GRADE.read_text(encoding="utf-8")
    assert "cannot_pass_unsurfaced" in text and "cannot_pass_unsurfaced" in doc
    assert "bad-unsurfaced-dead-button.json" in text
