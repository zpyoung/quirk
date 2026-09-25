"""Behavioral contract for the interactive logic-spec renderer CLI."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive"
SAMPLE = FIXTURES / "sample"
EXPORTS = SAMPLE / "exports"
V2_STAGE1 = FIXTURES / "v2" / "stage1"
V2_STAGE2 = FIXTURES / "v2" / "stage2"
V2_STAGE1_EXPORTS = V2_STAGE1 / "exports"
V2_STAGE2_EXPORTS = V2_STAGE2 / "exports"
INVALID_V2 = FIXTURES / "invalid-v2"

# Imported directly (rather than only shelling out) so tests can compute exact
# hashes/renderIds for exports built against mutated logic snapshots.
sys.path.insert(0, str(SCRIPT.parent))
import render_spec  # noqa: E402
PLACEHOLDER = '<script type="application/json" id="quirk-logic-spec-payload">null</script>'
EXIT6_MESSAGE = (
    "read-only v1 spec: page review, check-export, reapprove, and fold are refused; "
    "amend logic.json and re-render"
)


def run_script(
    script: Path, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_script(SCRIPT, *args, cwd=cwd)


def make_spec(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "sample"
    spec_dir.mkdir(parents=True)
    shutil.copy(SAMPLE / "logic.json", spec_dir / "logic.json")
    return spec_dir


def make_v2_spec(tmp_path: Path, source_dir: Path, name: str = "stage1") -> Path:
    spec_dir = tmp_path / name
    spec_dir.mkdir(parents=True)
    shutil.copy(source_dir / "logic.json", spec_dir / "logic.json")
    return spec_dir


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PayloadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_payload = False
        self.payload: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "quirk-logic-spec-payload":
            self.in_payload = True

    def handle_data(self, data: str) -> None:
        if self.in_payload:
            self.payload.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_payload:
            self.in_payload = False


def extract_payload(html: str) -> tuple[str, Dict[str, Any]]:
    parser = PayloadParser()
    parser.feed(html)
    raw = "".join(parser.payload)
    return raw, json.loads(raw)


def export_fixture(name: str) -> Path:
    return EXPORTS / (name + ".json")


def test_validate_accepts_complete_fixture_and_reports_invalid_variants(tmp_path: Path) -> None:
    result = run_cli("validate", str(SAMPLE))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

    expected_pointers = {
        "missing-key": "/title:",
        "bad-enum": "/requirements/0/provenance:",
        "dangling-dependson": "/requirements/0/dependsOn/0:",
        "duplicate-id": "/assumptions/0/id:",
    }
    for name, pointer in expected_pointers.items():
        invalid_spec = tmp_path / name
        invalid_spec.mkdir()
        shutil.copy(FIXTURES / "invalid" / (name + ".json"), invalid_spec / "logic.json")
        result = run_cli("validate", str(invalid_spec))
        assert result.returncode == 1
        assert pointer in result.stderr
        assert result.stdout == ""


def test_validate_rejects_object_prototype_names_as_ids(tmp_path: Path) -> None:
    for index, unsafe_id in enumerate(("__proto__", "constructor", "toString")):
        spec_dir = tmp_path / str(index)
        spec_dir.mkdir()
        logic = load_json(SAMPLE / "logic.json")
        logic["requirements"][0]["id"] = unsafe_id
        save_json(spec_dir / "logic.json", logic)
        result = run_cli("validate", str(spec_dir))
        assert result.returncode == 1
        assert "/requirements/0/id:" in result.stderr
        assert "reserved JavaScript object property" in result.stderr


def test_render_writes_only_logic_md_and_gitignore_for_v1(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    first_markdown = (spec_dir / "logic.md").read_text(encoding="utf-8")
    ignored = (spec_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert len(result.stdout.strip()) == 12
    int(result.stdout.strip(), 16)
    assert not (spec_dir / "review.html").exists()
    assert ignored.count("review.html") == 1
    assert ignored.count("*-decisions-*.json") == 1

    for heading in (
        "## Status & amendments",
        "## Purpose",
        "## Conceptual model",
        "## Data flow",
        "## Behavior & scenarios",
        "## Requirements",
        "## Assumptions & blind spots",
        "## Decisions Locked",
        "## Industry Insights",
        "## Scope & non-goals",
        "## Deferred Ideas",
        "## Glossary",
    ):
        assert heading in first_markdown
    assert first_markdown.startswith("<!-- generated from logic.json by render_spec.py — do not edit -->\n")
    assert "[tech-spec] Add archive signing" in first_markdown
    assert "### Conditionally in scope" in first_markdown
    assert "Research finding" in first_markdown
    assert "destination permission check can be performed before writing" in first_markdown

    repeated = run_cli("render", str(spec_dir))
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout == result.stdout
    assert (spec_dir / "logic.md").read_text(encoding="utf-8") == first_markdown
    assert (spec_dir / ".gitignore").read_text(encoding="utf-8").splitlines() == ignored
    assert not (spec_dir / "review.html").exists()


def test_v1_specs_refuse_every_page_review_path(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)

    for extra_args in (("--prior", str(export_fixture("signed"))), ("--open",)):
        refused = run_cli("render", str(spec_dir), *extra_args)
        assert refused.returncode == 6
        assert refused.stderr.strip() == EXIT6_MESSAGE
        assert not (spec_dir / "review.html").exists()
        assert not (spec_dir / "logic.md").exists()
        assert not (spec_dir / ".gitignore").exists()

    for args in (
        ("check-export", str(spec_dir), str(export_fixture("signed"))),
        ("find-export", str(spec_dir)),
        ("fold", str(spec_dir), str(export_fixture("signed"))),
        ("reapprove", str(spec_dir), str(export_fixture("signed"))),
    ):
        refused = run_cli(*args)
        assert refused.returncode == 6, args
        assert refused.stderr.strip() == EXIT6_MESSAGE, args

    # a plain render still succeeds and writes only the v1 outputs
    plain = run_cli("render", str(spec_dir))
    assert plain.returncode == 0, plain.stderr
    assert (spec_dir / "logic.md").exists()
    assert not (spec_dir / "review.html").exists()


def test_relative_dot_spec_dir_uses_folder_name_as_slug(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    result = run_cli("render", ".", cwd=spec_dir)
    assert result.returncode == 0, result.stderr
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    assert payload["slug"] == "stage1"


def test_v2_render_escapes_script_content_and_hashes_only_changed_constraint(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1)
    assert run_cli("render", str(spec_dir)).returncode == 0
    before = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]

    logic = load_json(spec_dir / "logic.json")
    for constraint in logic["constraints"]:
        if constraint["id"] == "CON-01":
            constraint["text"] = 'Literal adversarial content </script><script>alert("x")</script>.'
    save_json(spec_dir / "logic.json", logic)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    html = (spec_dir / "review.html").read_text(encoding="utf-8")
    raw, after = extract_payload(html)
    assert "<" not in raw
    changed = [c for c in after["spec"]["constraints"] if c["id"] == "CON-01"][0]
    assert changed["text"] == logic["constraints"][0]["text"]
    assert html.count('<script type="application/json" id="quirk-logic-spec-payload">') == 1
    assert after["renderId"] != before["renderId"]
    for item_id, old_hash in before["itemHashes"].items():
        if item_id == "CON-01":
            assert after["itemHashes"][item_id] != old_hash
        else:
            assert after["itemHashes"][item_id] == old_hash


def test_v2_render_is_deterministic(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    first = run_cli("render", str(spec_dir))
    assert first.returncode == 0, first.stderr
    first_html = (spec_dir / "review.html").read_text(encoding="utf-8")
    first_markdown = (spec_dir / "logic.md").read_text(encoding="utf-8")
    second = run_cli("render", str(spec_dir))
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert (spec_dir / "review.html").read_text(encoding="utf-8") == first_html
    assert (spec_dir / "logic.md").read_text(encoding="utf-8") == first_markdown


def test_v2_item_hashes_cover_behaviors_and_constraints(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    logic = load_json(spec_dir / "logic.json")
    expected_ids = {item["id"] for kind in ("behaviors", "scenarios", "constraints", "assumptions", "blindSpots", "requirements") for item in logic[kind]}
    assert set(payload["itemHashes"].keys()) == expected_ids


def test_v2_stage1_validates_without_warnings() -> None:
    result = run_cli("validate", str(V2_STAGE1))
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr.strip() == ""


def test_v2_behavior_scenario_count_is_unlimited_and_legacy_extra_reason_is_ignored(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    logic = load_json(spec_dir / "logic.json")
    template = next(item for item in logic["scenarios"] if item["behavior"] == "BH-01")
    for number in range(1, 5):
        extra = copy.deepcopy(template)
        extra["id"] = "SC-EXTRA-" + str(number)
        extra.pop("extraReason", None)
        logic["scenarios"].append(extra)
    # a leftover extraReason on an early scenario was an error under the old limit
    template["extraReason"] = "written under the old three-per-behavior limit"
    save_json(spec_dir / "logic.json", logic)

    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == ""


def test_v2_stage2_validates() -> None:
    result = run_cli("validate", str(V2_STAGE2))
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_v2_stage_rejects_boolean(tmp_path: Path) -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    logic["stage"] = True
    spec_dir = tmp_path / "stage-boolean"
    spec_dir.mkdir()
    save_json(spec_dir / "logic.json", logic)
    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 1
    assert "/stage: expected 1 or 2" in result.stderr


def test_v2_status_must_match_stage(tmp_path: Path) -> None:
    stage1 = load_json(V2_STAGE1 / "logic.json")
    for status in ("Approved", "nonsense"):
        stage1["status"] = status
        spec_dir = tmp_path / ("stage1-status-" + status.replace(" ", "-"))
        spec_dir.mkdir()
        save_json(spec_dir / "logic.json", stage1)
        result = run_cli("validate", str(spec_dir))
        assert result.returncode == 1, status
        assert "/status:" in result.stderr, result.stderr

    stage2 = load_json(V2_STAGE2 / "logic.json")
    for status in ("Draft", "totally invalid"):
        stage2["status"] = status
        spec_dir = tmp_path / ("stage2-status-" + status.replace(" ", "-"))
        spec_dir.mkdir()
        save_json(spec_dir / "logic.json", stage2)
        result = run_cli("validate", str(spec_dir))
        assert result.returncode == 1, status
        assert "/status:" in result.stderr, result.stderr

    stage2["status"] = "Approved — Tech spec: requested"
    spec_dir = tmp_path / "stage2-status-approved-suffix"
    spec_dir.mkdir()
    save_json(spec_dir / "logic.json", stage2)
    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 0, result.stderr


def test_v2_stage1_rejects_ruling_note_on_assumptions(tmp_path: Path) -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    logic["assumptions"][0]["rulingNote"] = "unsigned fold output"
    spec_dir = tmp_path / "stage1-ruling-note"
    spec_dir.mkdir()
    save_json(spec_dir / "logic.json", logic)
    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 1
    assert "/assumptions/0/rulingNote: must be absent in stage 1" in result.stderr


def test_v2_invalid_fixtures_each_fail_with_a_pointer(tmp_path: Path) -> None:
    for fixture_path in sorted(INVALID_V2.glob("*.json")):
        spec_dir = tmp_path / fixture_path.stem
        spec_dir.mkdir()
        shutil.copy(fixture_path, spec_dir / "logic.json")
        result = run_cli("validate", str(spec_dir))
        assert result.returncode == 1, fixture_path.name
        assert any(line.startswith("/") for line in result.stderr.splitlines()), (fixture_path.name, result.stderr)


def test_v2_logic_md_stage1_and_stage2_sections(tmp_path: Path) -> None:
    stage1_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    assert run_cli("render", str(stage1_dir)).returncode == 0
    stage1_markdown = (stage1_dir / "logic.md").read_text(encoding="utf-8")
    assert "Derived after stage 1 is signed." in stage1_markdown
    assert "### Archiving writes a portable index." in stage1_markdown
    assert "## Constraints" in stage1_markdown
    assert (stage1_dir / "review.html").exists()

    stage2_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    assert run_cli("render", str(stage2_dir)).returncode == 0
    stage2_markdown = (stage2_dir / "logic.md").read_text(encoding="utf-8")
    assert "Derived from" in stage2_markdown
    assert "### Archiving writes a portable index." in stage2_markdown
    assert "## Constraints" in stage2_markdown


def test_v2_reopened_scenario_may_change_while_a_different_locked_scenario_may_not(tmp_path: Path) -> None:
    logic = load_json(V2_STAGE2 / "logic.json")

    reopened = json.loads(json.dumps(logic))
    for scenario in reopened["scenarios"]:
        if scenario["id"] == "SC-01":
            scenario["then"] = "A revised archive behavior after reopening."
            scenario["reopened"] = {
                "requirementId": "REQ-01",
                "reason": "Wording needs revision.",
                "raisedAt": "2026-09-25T10:00:00Z",
            }
    reopened_dir = tmp_path / "reopened"
    reopened_dir.mkdir()
    save_json(reopened_dir / "logic.json", reopened)
    result = run_cli("validate", str(reopened_dir))
    assert result.returncode == 0, result.stderr

    locked = json.loads(json.dumps(logic))
    for scenario in locked["scenarios"]:
        if scenario["id"] == "SC-02":
            scenario["then"] = "An edit nobody signed off on."
    locked_dir = tmp_path / "locked"
    locked_dir.mkdir()
    save_json(locked_dir / "logic.json", locked)
    failed = run_cli("validate", str(locked_dir))
    assert failed.returncode == 1
    assert "/stage1Pin/itemHashes/SC-02: stage-1 item changed after sign-off" in failed.stderr


def test_v2_validate_rejects_a_raised_at_timestamp_that_overflows_during_parsing(tmp_path: Path) -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["scenarios"][0]["reopened"] = {
        "requirementId": "REQ-01",
        "reason": "review",
        "raisedAt": "0001-01-01T00:00:00+14:00",
    }
    spec_dir = tmp_path / "overflow-timestamp"
    spec_dir.mkdir()
    save_json(spec_dir / "logic.json", logic)

    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 1
    assert "/scenarios/0/reopened/raisedAt: expected an ISO 8601 date-time" in result.stderr


def test_fold_prepares_template_before_writing_any_artifacts(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path / "template-failure", V2_STAGE1, name="stage1")
    tool_dir = tmp_path / "isolated-tool"
    tool_dir.mkdir()
    script = tool_dir / "render_spec.py"
    shutil.copy(SCRIPT, script)
    (tool_dir / "review-template.html").write_text("missing payload marker", encoding="utf-8")

    result = run_script(script, "render", str(spec_dir))
    assert result.returncode == 1
    assert not (spec_dir / "review.html").exists()
    assert not (spec_dir / "logic.md").exists()


def test_render_refuses_to_write_when_output_path_is_blocked(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path / "blocked-output", V2_STAGE1, name="stage1")
    (spec_dir / "logic.md").mkdir()

    result = run_cli("render", str(spec_dir))
    assert result.returncode == 1
    assert not (spec_dir / "review.html").exists()


def test_fold_preflights_output_paths_before_approving_source(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path / "blocked-output-fold", V2_STAGE1, name="stage1")
    (spec_dir / "logic.md").mkdir()
    before = (spec_dir / "logic.json").read_bytes()

    result = run_cli("fold", str(spec_dir), str(V2_STAGE1_EXPORTS / "signed.json"))
    assert result.returncode == 1
    assert not (spec_dir / "review.html").exists()
    assert (spec_dir / "logic.json").read_bytes() == before


def test_v2_check_export_exits_3_on_stage_mismatch(tmp_path: Path) -> None:
    stage2_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    assert run_cli("render", str(stage2_dir)).returncode == 0
    result = run_cli("check-export", str(stage2_dir), str(V2_STAGE1_EXPORTS / "signed.json"))
    assert result.stdout.strip() == "signed"
    assert result.returncode == 3


def test_v2_stage1_fold_applies_decisions_and_advances_stage(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    result = run_cli("fold", str(spec_dir), str(V2_STAGE1_EXPORTS / "with-drop-and-rewrite.json"))
    assert result.returncode == 0, result.stderr
    folded_id = result.stdout.strip()
    assert len(folded_id) == 12

    folded = load_json(spec_dir / "logic.json")
    assert folded["stage"] == 2
    assert folded["status"] == "Stage 1 approved"
    assert "signoff" not in folded

    dropped = next(s for s in folded["scenarios"] if s["id"] == "SC-04")
    assert dropped["dropReason"] == "Space-exhaustion cleanup is deferred; tracked separately."

    rewritten = next(c for c in folded["constraints"] if c["id"] == "CON-02")
    assert rewritten["ruling"] == "rewritten"
    assert rewritten["originalText"] == "Index entries use forward slashes for paths."
    assert rewritten["text"] == "Index entries always use forward slashes for paths, even on Windows."

    rejected = next(c for c in folded["constraints"] if c["id"] == "CON-04")
    assert rejected["ruling"] == "rejected"
    assert rejected["rejectReason"] == "Permission checks are handled by the OS; skip this."

    approved = next(c for c in folded["constraints"] if c["id"] == "CON-01")
    assert approved["ruling"] == "approved"

    assumption = next(a for a in folded["assumptions"] if a["id"] == "ASM-01")
    assert assumption["ruling"] == "verify-first"
    assert assumption["rulingNote"]

    for spot in folded["blindSpots"]:
        assert spot["acceptance"]

    assert folded["stage1Pin"]["itemHashes"] == render_spec.stage1_item_hashes(folded)
    assert (spec_dir / "review.html").exists()
    assert "logic.md" in [p.name for p in spec_dir.iterdir()]

    # a second fold of the same (now stale) export is refused
    again = run_cli("fold", str(spec_dir), str(V2_STAGE1_EXPORTS / "with-drop-and-rewrite.json"))
    assert again.returncode == 3


def test_v2_stage1_gate_variants_exit4_naming_gate(tmp_path: Path) -> None:
    for gate_id, fixture_name in (
        ("scenarios", "gate-scenarios"),
        ("constraints", "gate-constraints"),
        ("assumptions", "gate-assumptions"),
        ("blind-spots", "gate-blind-spots"),
    ):
        spec_dir = make_v2_spec(tmp_path / fixture_name, V2_STAGE1, name="stage1")
        result = run_cli("fold", str(spec_dir), str(V2_STAGE1_EXPORTS / (fixture_name + ".json")))
        assert result.returncode == 4, (fixture_name, result.stderr)
        assert ("gate " + gate_id) in result.stderr, (fixture_name, result.stderr)
        folded = load_json(spec_dir / "logic.json")
        assert folded["stage"] == 1, "a failed gate must not advance the stage"


def test_v2_stage1_tech_spec_requested_is_a_usage_error(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    result = run_cli(
        "fold", str(spec_dir), str(V2_STAGE1_EXPORTS / "signed.json"), "--tech-spec-requested"
    )
    assert result.returncode == 2
    assert "pass --tech-spec-requested at the final fold" in result.stderr
    folded = load_json(spec_dir / "logic.json")
    assert folded["stage"] == 1


def test_v2_final_fold_gate_variants_exit4_naming_gate(tmp_path: Path) -> None:
    for gate_id, fixture_name in (
        ("move-reasons", "gate-move-reasons"),
        ("scope-warnings", "gate-scope-warnings"),
        ("disputes", "gate-disputes"),
    ):
        spec_dir = make_v2_spec(tmp_path / fixture_name, V2_STAGE2, name="stage2")
        result = run_cli("fold", str(spec_dir), str(V2_STAGE2_EXPORTS / (fixture_name + ".json")))
        assert result.returncode == 4, (fixture_name, result.stderr)
        assert ("gate " + gate_id) in result.stderr, (fixture_name, result.stderr)
        folded = load_json(spec_dir / "logic.json")
        assert folded["status"] == "Stage 1 approved", "a failed gate must not sign off the spec"


def test_v2_final_fold_derivation_gate_names_the_underived_scenario(tmp_path: Path) -> None:
    """SC-03 becomes underived once REQ-01 stops naming it; the out-of-scope,
    non-goal-derived OOS-01/CON-03 pairing is untouched and keeps passing."""
    mutated_dir = tmp_path / "stage2"
    mutated_dir.mkdir()
    mutated_logic = load_json(V2_STAGE2 / "logic.json")
    for requirement in mutated_logic["requirements"]:
        if requirement["id"] == "REQ-01":
            requirement["derivedFrom"] = ["SC-01"]
    save_json(mutated_dir / "logic.json", mutated_logic)
    render_result = run_cli("render", str(mutated_dir))
    assert render_result.returncode == 0, render_result.stderr
    mutated_render_id = render_result.stdout.strip()

    export = load_json(V2_STAGE2_EXPORTS / "gate-derivation.json")
    export["renderId"] = mutated_render_id
    export_path = tmp_path / "gate-derivation-patched.json"
    save_json(export_path, export)

    result = run_cli("fold", str(mutated_dir), str(export_path))
    assert result.returncode == 4, result.stderr
    assert "gate derivation" in result.stderr
    assert "SC-03" in result.stderr
    # OOS-01's derivation from the non-goal constraint CON-03 is unaffected
    assert "OOS-01" not in result.stderr and "CON-03" not in result.stderr


def test_v2_final_fold_out_of_scope_non_goal_derivation_passes(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    result = run_cli("fold", str(spec_dir), str(V2_STAGE2_EXPORTS / "signed.json"))
    assert result.returncode == 0, result.stderr
    folded = load_json(spec_dir / "logic.json")
    oos = next(r for r in folded["requirements"] if r["id"] == "OOS-01")
    assert oos["derivedFrom"] == ["CON-03"]
    assert oos["scope"] == "out"


def test_v2_final_fold_sets_status_with_and_without_tech_spec_flag(tmp_path: Path) -> None:
    plain_dir = make_v2_spec(tmp_path / "plain", V2_STAGE2, name="stage2")
    plain_result = run_cli("fold", str(plain_dir), str(V2_STAGE2_EXPORTS / "signed.json"))
    assert plain_result.returncode == 0, plain_result.stderr
    plain_logic = load_json(plain_dir / "logic.json")
    assert plain_logic["status"] == "Approved"
    assert plain_logic["signoff"]["renderId"] == load_json(V2_STAGE2_EXPORTS / "signed.json")["renderId"]
    moved = next(r for r in plain_logic["requirements"] if r["id"] == "REQ-05")
    assert moved["scope"] == "out"
    assert moved["reviewReason"]

    tech_dir = make_v2_spec(tmp_path / "tech", V2_STAGE2, name="stage2")
    tech_result = run_cli(
        "fold", str(tech_dir), str(V2_STAGE2_EXPORTS / "signed.json"), "--tech-spec-requested"
    )
    assert tech_result.returncode == 0, tech_result.stderr
    tech_logic = load_json(tech_dir / "logic.json")
    assert tech_logic["status"] == "Approved — Tech spec: requested"


def test_v2_check_export_accepts_unsigned_dispute_exports(tmp_path: Path) -> None:
    for fixture_name in ("unsigned-derivation-dispute", "unsigned-scenario-dispute"):
        spec_dir = make_v2_spec(tmp_path / fixture_name, V2_STAGE2, name="stage2")
        result = run_cli("check-export", str(spec_dir), str(V2_STAGE2_EXPORTS / (fixture_name + ".json")))
        assert result.stdout.strip() == "unsigned", (fixture_name, result.stdout)
        assert result.returncode == 0, (fixture_name, result.stderr)


def _reopen_sc01(logic: Dict[str, Any]) -> Dict[str, Any]:
    reopened = copy.deepcopy(logic)
    for scenario in reopened["scenarios"]:
        if scenario["id"] == "SC-01":
            scenario["then"] = "An archive and compact index are written locally, retrying once on transient I/O errors."
            scenario["reopened"] = {
                "requirementId": "REQ-01",
                "reason": "Wording needs another pass.",
                "raisedAt": "2026-09-25T10:00:00Z",
            }
    return reopened


def test_v2_reapprove_moves_reopened_scenario_to_reapproved_hash(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    reopened_logic = _reopen_sc01(load_json(V2_STAGE2 / "logic.json"))
    save_json(spec_dir / "logic.json", reopened_logic)
    render_result = run_cli("render", str(spec_dir))
    assert render_result.returncode == 0, render_result.stderr
    render_id = render_result.stdout.strip()
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    current_hash = payload["itemHashes"]["SC-01"]

    export = {
        "kind": "quirk-logic-spec-decisions",
        "schemaVersion": 2,
        "stage": 2,
        "slug": "stage2",
        "renderId": render_id,
        "exportedAt": "2026-09-25T11:00:00Z",
        "signed": False,
        "seen": {"SC-01": current_hash},
        "state": {
            "stage": 2,
            "scenarioOutcomes": {},
            "scenarioApproved": {"SC-01": True},
            "scenarioDrops": {},
            "scenarioRequests": [],
            "constraintRulings": {},
            "assumptions": {},
            "blindSpots": {},
            "researchRequests": [],
            "placements": {},
            "conditions": {},
            "moveReasons": {},
            "notes": {},
            "disputes": {},
            "verdict": "send-back",
            "verdictNote": "Reopened wording is fine now.",
            "updatedAt": "2026-09-25T11:00:00Z",
        },
        "record": {
            "stage": 2,
            "verdict": "send-back",
            "verdictNote": "Reopened wording is fine now.",
            "signedAt": None,
            "scenarios": [],
            "constraints": [],
            "assumptions": [],
            "blindSpots": [],
            "placements": [],
            "disputes": [],
            "scenarioRequests": [],
            "researchRequests": [],
            "openWarnings": [],
        },
    }
    export_path = tmp_path / "unsigned-reapproved.json"
    save_json(export_path, export)

    result = run_cli("reapprove", str(spec_dir), str(export_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SC-01"

    updated = load_json(spec_dir / "logic.json")
    scenario = next(s for s in updated["scenarios"] if s["id"] == "SC-01")
    assert "reopened" not in scenario
    assert scenario["reapprovedHash"] == current_hash

    # the spec still validates: the lock's reapprovedHash exception covers SC-01
    assert run_cli("validate", str(spec_dir)).returncode == 0

    # the export used above is now stale (the fold changed logic.json's renderId)
    stale_result = run_cli("reapprove", str(spec_dir), str(export_path))
    assert stale_result.returncode == 3

    # a fresh, current export has nothing left to re-approve: SC-01 is no longer reopened,
    # so a current export no longer carries an approval for it
    rerender = run_cli("render", str(spec_dir))
    assert rerender.returncode == 0, rerender.stderr
    fresh_export = copy.deepcopy(export)
    fresh_export["renderId"] = rerender.stdout.strip()
    fresh_export["state"]["scenarioApproved"] = {}
    fresh_path = tmp_path / "fresh-reapprove.json"
    save_json(fresh_path, fresh_export)
    again = run_cli("reapprove", str(spec_dir), str(fresh_path))
    assert again.returncode == 4
    assert "nothing to re-approve" in again.stderr


def test_v2_reapprove_exits_4_when_nothing_qualifies(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    render_result = run_cli("render", str(spec_dir))
    assert render_result.returncode == 0
    export = {
        "kind": "quirk-logic-spec-decisions",
        "schemaVersion": 2,
        "stage": 2,
        "slug": "stage2",
        "renderId": render_result.stdout.strip(),
        "exportedAt": "2026-09-25T11:00:00Z",
        "signed": False,
        "seen": {},
        "state": {
            "stage": 2,
            "scenarioOutcomes": {},
            "scenarioApproved": {},
            "scenarioDrops": {},
            "scenarioRequests": [],
            "constraintRulings": {},
            "assumptions": {},
            "blindSpots": {},
            "researchRequests": [],
            "placements": {},
            "conditions": {},
            "moveReasons": {},
            "notes": {},
            "disputes": {},
            "verdict": "send-back",
            "verdictNote": "n/a",
            "updatedAt": "2026-09-25T11:00:00Z",
        },
        "record": {
            "stage": 2,
            "verdict": "send-back",
            "verdictNote": "n/a",
            "signedAt": None,
            "scenarios": [],
            "constraints": [],
            "assumptions": [],
            "blindSpots": [],
            "placements": [],
            "disputes": [],
            "scenarioRequests": [],
            "researchRequests": [],
            "openWarnings": [],
        },
    }
    export_path = tmp_path / "no-reapprovals.json"
    save_json(export_path, export)
    result = run_cli("reapprove", str(spec_dir), str(export_path))
    assert result.returncode == 4
    assert "nothing to re-approve" in result.stderr


def test_v2_final_fold_moves_reapproved_hash_into_pin(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    reopened_logic = _reopen_sc01(load_json(V2_STAGE2 / "logic.json"))
    save_json(spec_dir / "logic.json", reopened_logic)
    assert run_cli("render", str(spec_dir)).returncode == 0
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    current_hash = payload["itemHashes"]["SC-01"]

    for scenario in reopened_logic["scenarios"]:
        if scenario["id"] == "SC-01":
            scenario.pop("reopened", None)
            scenario["reapprovedHash"] = current_hash
    save_json(spec_dir / "logic.json", reopened_logic)

    render_result = run_cli("render", str(spec_dir))
    assert render_result.returncode == 0, render_result.stderr
    render_id = render_result.stdout.strip()

    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["renderId"] = render_id
    export_path = tmp_path / "final-signed.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 0, result.stderr
    folded = load_json(spec_dir / "logic.json")
    scenario = next(s for s in folded["scenarios"] if s["id"] == "SC-01")
    assert "reapprovedHash" not in scenario
    assert folded["stage1Pin"]["itemHashes"]["SC-01"] == current_hash


def test_v2_validate_rejects_a_stale_reapproved_hash_even_when_the_pin_still_matches() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    assert render_spec.validate_logic_v2(logic)[0] == []

    logic["scenarios"][0]["reapprovedHash"] = "not-the-current-hash"

    errors = dict(render_spec.validate_logic_v2(logic)[0])
    assert errors.get("/scenarios/0/reapprovedHash") == "reapprovedHash does not match the item's current hash"


def test_v2_fold_refuses_a_logic_json_with_a_stale_reapproved_hash(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    logic = load_json(spec_dir / "logic.json")
    logic["scenarios"][0]["reapprovedHash"] = "not-the-current-hash"
    save_json(spec_dir / "logic.json", logic)

    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export_path = tmp_path / "signed.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    unchanged = load_json(spec_dir / "logic.json")
    assert unchanged["stage1Pin"]["itemHashes"]["SC-01"] != "not-the-current-hash"


def test_v2_final_fold_refuses_to_write_when_post_fold_logic_is_invalid(tmp_path: Path, monkeypatch: Any) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    render_result = run_cli("render", str(spec_dir))
    assert render_result.returncode == 0, render_result.stderr

    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["renderId"] = render_result.stdout.strip()
    export_path = tmp_path / "signed.json"
    save_json(export_path, export)

    before = (spec_dir / "logic.json").read_text(encoding="utf-8")
    real_final_fold = render_spec.final_fold

    def corrupting_final_fold(logic: dict, export: dict, tech_spec_requested: bool) -> None:
        real_final_fold(logic, export, tech_spec_requested)
        logic["scenarios"][0]["behavior"] = "BH-DOES-NOT-EXIST"

    monkeypatch.setattr(render_spec, "final_fold", corrupting_final_fold)

    result = render_spec.command_fold(spec_dir, export_path, False)
    assert result == 1
    assert (spec_dir / "logic.json").read_text(encoding="utf-8") == before


def test_v2_fold_prepares_template_before_writing_any_artifacts(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    tool_dir = tmp_path / "isolated-tool"
    tool_dir.mkdir()
    script = tool_dir / "render_spec.py"
    shutil.copy(SCRIPT, script)
    (tool_dir / "review-template.html").write_text("missing payload marker", encoding="utf-8")

    before = load_json(spec_dir / "logic.json")
    result = run_script(script, "fold", str(spec_dir), str(V2_STAGE1_EXPORTS / "signed.json"))
    assert result.returncode == 1
    assert not (spec_dir / "review.html").exists()
    assert not (spec_dir / "logic.md").exists()
    assert load_json(spec_dir / "logic.json") == before


def test_derived_requirement_status_and_gate_exclusion_for_withdrawn_requirements() -> None:
    scenario_by_id = {
        "SC-A": {"id": "SC-A"},
        "SC-B": {
            "id": "SC-B",
            "reopened": {"requirementId": "REQ-X", "reason": "Wording review.", "raisedAt": "2026-01-01T00:00:00Z"},
        },
    }
    assert render_spec.derived_requirement_status({"derivedFrom": ["SC-B"]}, scenario_by_id) == "withdrawn"
    assert render_spec.derived_requirement_status({"derivedFrom": ["SC-A", "SC-B"]}, scenario_by_id) == "flagged"
    assert render_spec.derived_requirement_status({"derivedFrom": ["SC-A"]}, scenario_by_id) == "active"

    logic = {
        "scenarios": [scenario_by_id["SC-A"], scenario_by_id["SC-B"]],
        "constraints": [],
        "requirements": [
            {"id": "REQ-X", "scope": "in", "dependsOn": ["REQ-OUT"], "derivedFrom": ["SC-B"]},
            {"id": "REQ-OUT", "scope": "out", "dependsOn": [], "derivedFrom": ["SC-A"]},
        ],
        "conflicts": [],
    }
    state = {"placements": {}, "conditions": {}, "moveReasons": {}, "disputes": {}}
    failures = dict(render_spec.stage2_gate_failures(logic, state))
    # SC-B is approved (no dropReason) but its only deriving requirement is withdrawn,
    # so the withdrawn requirement does not count towards coverage.
    assert "derivation" in failures and "SC-B" in failures["derivation"]
    # REQ-X would otherwise warn about depending on the out-of-scope REQ-OUT, but a
    # withdrawn requirement is excluded from scope warnings entirely.
    assert "scope-warnings" not in failures


def test_validate_export_shape_requires_state_and_record_stage_to_match_root() -> None:
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["stage"] = 1
    export["record"]["stage"] = 1
    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/stage" in errors
    assert "/record/stage" in errors


def test_v2_fold_rejects_export_with_mismatched_state_and_record_stage(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["stage"] = 1
    export["record"]["stage"] = 1
    export_path = tmp_path / "mismatched-stage.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "/state/stage" in result.stderr
    assert "/record/stage" in result.stderr
    folded = load_json(spec_dir / "logic.json")
    assert folded["stage"] == 2, "a shape-invalid export must never be foldable"


def test_discover_export_skips_candidates_that_fail_shape_validation(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    valid = load_json(V2_STAGE2_EXPORTS / "signed.json")
    malformed = dict(valid)
    del malformed["record"]
    malformed["exportedAt"] = "2026-09-25T12:00:00Z"
    save_json(downloads / "malformed.json", malformed)
    save_json(spec_dir / "valid.json", valid)

    found = render_spec.discover_export(spec_dir, downloads, valid["renderId"], required_stage=2)
    assert found == (spec_dir / "valid.json").resolve()

    # with only the shape-invalid candidate present, nothing qualifies
    (spec_dir / "valid.json").unlink()
    assert render_spec.discover_export(spec_dir, downloads, valid["renderId"], required_stage=2) is None


def test_find_export_reports_an_unreadable_search_directory(tmp_path: Path, capsys: Any) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can read a 0o000 directory")
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    downloads.chmod(0o000)
    try:
        result = render_spec.command_find_export(spec_dir, downloads)
    finally:
        downloads.chmod(0o755)
    assert result == 1
    captured = capsys.readouterr()
    assert str(downloads) in captured.err


def test_find_export_moves_a_downloaded_export_next_to_the_review_page(tmp_path: Path, capsys: Any) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    save_json(downloads / "stage2-decisions.json", export)

    assert render_spec.command_find_export(spec_dir, downloads) == 0
    moved = spec_dir / "stage2-decisions.json"
    assert capsys.readouterr().out.strip() == str(moved.resolve())
    assert load_json(moved) == export
    assert not (downloads / "stage2-decisions.json").exists()


def test_find_export_leaves_a_download_whose_name_is_taken_in_the_spec_folder(tmp_path: Path, capsys: Any) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    newer = dict(export, exportedAt="2099-01-01T00:00:00Z")
    save_json(downloads / "stage2-decisions.json", newer)
    # an unrelated file already holds the name, so the download must not overwrite it
    (spec_dir / "stage2-decisions.json").write_text("not an export", encoding="utf-8")

    assert render_spec.command_find_export(spec_dir, downloads) == 0
    assert capsys.readouterr().out.strip() == str((downloads / "stage2-decisions.json").resolve())
    assert (spec_dir / "stage2-decisions.json").read_text(encoding="utf-8") == "not an export"


def test_stage2_move_reasons_gate_excludes_withdrawn_requirements() -> None:
    scenario_by_id = {
        "SC-A": {"id": "SC-A"},
        "SC-W": {
            "id": "SC-W",
            "reopened": {"requirementId": "REQ-W", "reason": "Wording review.", "raisedAt": "2026-01-01T00:00:00Z"},
        },
    }
    logic = {
        "scenarios": [scenario_by_id["SC-A"], scenario_by_id["SC-W"]],
        "constraints": [],
        "requirements": [
            {"id": "REQ-W", "scope": "in", "dependsOn": [], "derivedFrom": ["SC-W"]},
            {"id": "REQ-A", "scope": "in", "dependsOn": [], "derivedFrom": ["SC-A"]},
        ],
        "conflicts": [],
    }
    # REQ-W is withdrawn (its only deriving scenario is reopened) and moved to "out"
    # with no recorded reason; the gate must not flag a withdrawn requirement.
    state = {"placements": {"REQ-W": "out"}, "conditions": {}, "moveReasons": {}, "disputes": {}}
    failures = dict(render_spec.stage2_gate_failures(logic, state))
    assert "move-reasons" not in failures


def test_logic_reference_errors_rejects_scenario_dispute_target_that_is_not_a_scenario(tmp_path: Path) -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-scenario-dispute.json")
    # CON-02 is in REQ-01's derivedFrom but is a constraint, not a scenario
    export["state"]["disputes"]["REQ-01"]["target"] = "CON-02"
    export["record"]["disputes"][0]["target"] = "CON-02"
    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert "/state/disputes/REQ-01/target" in errors
    assert "/record/disputes/0/target" in errors


def test_v2_check_export_rejects_scenario_dispute_targeting_a_constraint(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-scenario-dispute.json")
    export["state"]["disputes"]["REQ-01"]["target"] = "CON-02"
    export["record"]["disputes"][0]["target"] = "CON-02"
    export_path = tmp_path / "scenario-dispute-targets-constraint.json"
    save_json(export_path, export)

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "target" in result.stderr


def test_validate_export_shape_rejects_blank_dispute_reason() -> None:
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-derivation-dispute.json")
    export["state"]["disputes"]["REQ-05"]["reason"] = ""
    export["record"]["disputes"][0]["reason"] = ""
    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/disputes/REQ-05/reason" in errors
    assert "/record/disputes/0/reason" in errors


def test_v2_check_export_rejects_blank_dispute_reason(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-derivation-dispute.json")
    export["state"]["disputes"]["REQ-05"]["reason"] = ""
    export["record"]["disputes"][0]["reason"] = ""
    export_path = tmp_path / "blank-dispute-reason.json"
    save_json(export_path, export)

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "reason" in result.stderr


def test_v2_render_accepts_a_shape_valid_prior_for_the_same_slug(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    result = run_cli("render", str(spec_dir), "--prior", str(V2_STAGE1_EXPORTS / "signed.json"))
    assert result.returncode == 0, result.stderr
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    assert payload["priorDecisions"]["slug"] == "stage1"


def test_v2_render_rejects_a_shape_invalid_prior_without_writing(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    prior = load_json(V2_STAGE1_EXPORTS / "signed.json")
    del prior["record"]
    prior_path = tmp_path / "malformed-prior.json"
    save_json(prior_path, prior)

    result = run_cli("render", str(spec_dir), "--prior", str(prior_path))
    assert result.returncode == 1
    assert "/record" in result.stderr
    assert not (spec_dir / "review.html").exists()


def test_v2_render_rejects_a_prior_export_from_a_different_spec(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    result = run_cli("render", str(spec_dir), "--prior", str(V2_STAGE2_EXPORTS / "signed.json"))
    assert result.returncode == 3
    assert not (spec_dir / "review.html").exists()


def test_v2_state_machine_ids_may_reuse_a_scenario_id() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["views"]["stateMachine"]["states"][0]["id"] = "SC-01"
    for transition in logic["views"]["stateMachine"]["transitions"]:
        if transition["from"] == "ST-READY":
            transition["from"] = "SC-01"
        if transition["to"] == "ST-READY":
            transition["to"] = "SC-01"
    errors, _ = render_spec.validate_logic_v2(logic)
    assert errors == []


def test_v2_state_machine_ids_must_still_be_unique_among_themselves() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["views"]["stateMachine"]["entries"] = [{"id": "ST-READY", "label": "Start"}]
    errors = dict(render_spec.validate_logic_v2(logic)[0])
    assert "/views/stateMachine/entries/0/id" in errors


def test_validate_export_shape_rejects_stage2_state_with_stage1_only_maps_populated() -> None:
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["constraintRulings"] = {"CON-01": {"ruling": "approve", "text": "", "reason": ""}}
    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/constraintRulings" in errors


def test_validate_export_shape_rejects_stage1_state_with_stage2_only_maps_populated() -> None:
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["disputes"] = {"REQ-01": {"kind": "derivation", "target": None, "reason": "Needs another look."}}
    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/disputes" in errors


def test_logic_reference_errors_rejects_scenario_approved_for_a_non_reopened_scenario_in_stage2() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["scenarioApproved"] = {"SC-01": True}
    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert "/state/scenarioApproved/SC-01" in errors


def test_v2_check_export_rejects_stage2_export_with_stage1_maps_populated(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["constraintRulings"] = {"CON-01": {"ruling": "approve", "text": "", "reason": ""}}
    export_path = tmp_path / "leaked-stage1-maps.json"
    save_json(export_path, export)

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "/state/constraintRulings" in result.stderr


def test_load_json_reports_deeply_nested_input_instead_of_crashing(tmp_path: Path) -> None:
    deeply_nested = tmp_path / "deep.json"
    deeply_nested.write_text("[" * 1100 + "]" * 1100, encoding="utf-8")
    value, errors = render_spec.load_json(deeply_nested, str(deeply_nested))
    assert value is None
    assert dict(errors)["/"] == "invalid JSON in " + str(deeply_nested) + ": input is too deeply nested"


def test_v2_check_export_exits_1_without_a_traceback_on_deeply_nested_export(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export_path = tmp_path / "deep.json"
    export_path.write_text("[" * 1100 + "]" * 1100, encoding="utf-8")

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "input is too deeply nested" in result.stderr


def test_load_json_rejects_python_only_nan_and_infinity_constants(tmp_path: Path) -> None:
    non_standard = tmp_path / "non-standard.json"
    non_standard.write_text('{"unexpected": NaN, "other": Infinity, "neg": -Infinity}', encoding="utf-8")
    value, errors = render_spec.load_json(non_standard, str(non_standard))
    assert value is None
    assert "NaN" in dict(errors)["/"]


def test_v2_render_rejects_nan_in_an_otherwise_ignored_field_instead_of_emitting_invalid_json(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    logic = load_json(spec_dir / "logic.json")
    logic["behaviors"][0]["unexpected"] = float("nan")
    save_json(spec_dir / "logic.json", logic)

    result = run_cli("render", str(spec_dir))
    assert result.returncode == 1, result.stderr
    assert not (spec_dir / "review.html").exists()


def test_logic_reference_errors_rejects_scenario_both_approved_and_dropped() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["scenarioDrops"]["SC-01"] = "drop despite approval"

    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert "/state/scenarioDrops/SC-01" in errors


def test_v2_fold_refuses_a_scenario_that_is_both_approved_and_dropped(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["scenarioDrops"]["SC-01"] = "drop despite approval"
    export_path = tmp_path / "approved-and-dropped.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "SC-01" in result.stderr
    folded = load_json(spec_dir / "logic.json")
    assert folded["stage"] == 1, "a rejected export must not advance the stage"


def test_logic_reference_errors_rejects_a_record_scenario_request_with_an_unknown_behavior() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["record"]["scenarioRequests"] = [
        {"id": "REQUEST-X", "behavior": "BH-NOT-THERE", "text": "x", "requestedAt": "2026-09-23T16:00:00Z"}
    ]

    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert errors.get("/record/scenarioRequests/0/behavior") == "unknown behavior id: BH-NOT-THERE"


def test_v2_check_export_rejects_a_record_scenario_request_with_an_unknown_behavior(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["record"]["scenarioRequests"] = [
        {"id": "REQUEST-X", "behavior": "BH-NOT-THERE", "text": "x", "requestedAt": "2026-09-23T16:00:00Z"}
    ]
    export_path = tmp_path / "unknown-behavior-request.json"
    save_json(export_path, export)

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "BH-NOT-THERE" in result.stderr


def test_validate_export_shape_rejects_a_non_null_target_on_a_derivation_record_dispute() -> None:
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-derivation-dispute.json")
    export["record"]["disputes"][0]["target"] = "SC-01"

    errors = dict(render_spec.validate_export_shape(export))
    assert "/record/disputes/0/target" in errors


def test_v2_check_export_rejects_a_non_null_target_on_a_derivation_record_dispute(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    export = load_json(V2_STAGE2_EXPORTS / "unsigned-derivation-dispute.json")
    export["record"]["disputes"][0]["target"] = "SC-01"
    export_path = tmp_path / "derivation-dispute-with-target.json"
    save_json(export_path, export)

    result = run_cli("check-export", str(spec_dir), str(export_path))
    assert result.returncode == 1, result.stderr
    assert "target" in result.stderr


def test_validate_logic_v2_reports_an_error_instead_of_raising_on_an_item_missing_an_id() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["behaviors"][0] = {}

    errors, _warnings = render_spec.validate_logic_v2(logic)
    assert dict(errors).get("/behaviors/0/id") == "required key is missing"


def test_v2_render_reports_errors_instead_of_raising_on_an_item_missing_an_id(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    logic = load_json(spec_dir / "logic.json")
    logic["behaviors"][0] = {}
    save_json(spec_dir / "logic.json", logic)

    result = run_cli("render", str(spec_dir))
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "/behaviors/0/id" in result.stderr


def test_validate_logic_v2_rejects_reopened_scenario_naming_an_unknown_requirement() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["scenarios"][0]["reopened"] = {
        "requirementId": "REQ-NOT-THERE",
        "reason": "review",
        "raisedAt": "2026-09-24T00:00:00Z",
    }
    errors = dict(render_spec.validate_logic_v2(logic)[0])
    assert errors.get("/scenarios/0/reopened/requirementId") == "unknown requirement id: REQ-NOT-THERE"


def test_validate_logic_v2_rejects_reopened_scenario_not_in_the_named_requirements_derived_from() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    # SC-01 derives REQ-01, not REQ-02: the reopened requirement must actually depend on this scenario.
    assert logic["scenarios"][0]["id"] == "SC-01"
    logic["scenarios"][0]["reopened"] = {
        "requirementId": "REQ-02",
        "reason": "review",
        "raisedAt": "2026-09-24T00:00:00Z",
    }
    errors = dict(render_spec.validate_logic_v2(logic)[0])
    assert (
        errors.get("/scenarios/0/reopened/requirementId")
        == "requirement REQ-02 does not derive from this scenario"
    )


def test_validate_logic_v2_rejects_transition_blind_spot_naming_an_unknown_id() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["views"]["stateMachine"]["transitions"][0]["blindSpot"] = "BS-NOT-THERE"
    errors = dict(render_spec.validate_logic_v2(logic)[0])
    assert errors.get("/views/stateMachine/transitions/0/blindSpot") == "unknown blind spot id: BS-NOT-THERE"


def test_validate_logic_v2_accepts_transition_blind_spot_naming_a_known_id() -> None:
    logic = load_json(V2_STAGE2 / "logic.json")
    logic["views"]["stateMachine"]["transitions"][0]["blindSpot"] = "BS-01"
    errors, _warnings = render_spec.validate_logic_v2(logic)
    assert errors == []


def test_load_json_rejects_nesting_well_short_of_pythons_own_recursion_limit(tmp_path: Path) -> None:
    # 300 levels parses fine (well under Python's own ~1000-frame recursion limit) but
    # is deeper than any real spec, and deep enough to blow the stack later during
    # canonical-JSON serialization once combined with the rest of the call stack.
    deep_path = tmp_path / "deep.json"
    deep_path.write_text("[" * 300 + "]" * 300, encoding="utf-8")
    value, errors = render_spec.load_json(deep_path, str(deep_path))
    assert value is None
    too_deep_pointer = "/" + "/".join(["0"] * (render_spec.JSON_MAX_DEPTH + 1))
    assert dict(errors)[too_deep_pointer] == (
        "invalid JSON in " + str(deep_path) + ": input is too deeply nested"
    )


def test_v2_validate_exits_1_without_a_traceback_on_a_deeply_nested_unknown_field(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE2, name="stage2")
    logic = load_json(spec_dir / "logic.json")
    nested: Any = 0
    for _ in range(300):
        nested = [nested]
    logic["unexpected"] = nested
    save_json(spec_dir / "logic.json", logic)

    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "input is too deeply nested" in result.stderr


def test_logic_reference_errors_rejects_scenario_both_approved_and_awaiting_update() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["scenarioUpdates"] = {"SC-01": "tighten the timeout"}

    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert "/state/scenarioUpdates/SC-01" in errors


def test_logic_reference_errors_rejects_an_update_for_an_unknown_scenario() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["scenarioUpdates"] = {"SC-NOT-THERE": "x"}

    errors = dict(render_spec.logic_reference_errors(export, logic))
    assert errors.get("/state/scenarioUpdates/SC-NOT-THERE") == "unknown scenario id: SC-NOT-THERE"


def test_validate_export_shape_rejects_stage2_state_with_scenario_updates() -> None:
    export = load_json(V2_STAGE2_EXPORTS / "signed.json")
    export["state"]["scenarioUpdates"] = {"SC-01": "change it"}

    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/scenarioUpdates" in errors


def test_v2_stage1_fold_gate_names_a_scenario_awaiting_an_update(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    # the signed fixture predates update feedback, so it also proves the field stays optional
    assert "scenarioUpdates" not in export["state"]
    del export["state"]["scenarioApproved"]["SC-01"]
    export["state"]["scenarioUpdates"] = {"SC-01": "tighten the timeout"}
    export_path = tmp_path / "awaiting-update.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 4, result.stderr
    assert "gate scenarios" in result.stderr
    assert "update requested: SC-01" in result.stderr
    assert load_json(spec_dir / "logic.json")["stage"] == 1


def test_v2_stage1_fold_carries_a_pending_research_request_in_place_of_acceptance(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    # rejecting CON-04 leaves BS-01 active; asking for research must settle it without an acceptance
    reject = {"ruling": "reject", "text": "", "reason": "Permission checks belong to the tech spec."}
    export["state"]["constraintRulings"]["CON-04"] = reject
    for constraint in export["record"]["constraints"]:
        if constraint["id"] == "CON-04":
            constraint.update(reject)
    request = {"id": "research-bs01", "blindSpotId": "BS-01", "question": "Is this real on macOS?", "requestedAt": "2026-09-23T15:00:00Z"}
    export["state"]["researchRequests"] = [request]
    export["record"]["researchRequests"] = [request]
    export_path = tmp_path / "research-instead-of-acceptance.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 0, result.stderr
    folded = load_json(spec_dir / "logic.json")
    spot = next(item for item in folded["blindSpots"] if item["id"] == "BS-01")
    assert "acceptance" not in spot
    assert spot["researchRequest"] == {"id": "research-bs01", "question": "Is this real on macOS?", "requestedAt": "2026-09-23T15:00:00Z"}
    assert "Research requested at sign-off: Is this real on macOS?" in (spec_dir / "logic.md").read_text(encoding="utf-8")
    assert run_cli("validate", str(spec_dir)).returncode == 0


def test_v2_stage1_logic_rejects_a_folded_research_request() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    logic["blindSpots"][0]["researchRequest"] = {"id": "r", "question": "", "requestedAt": "2026-09-23T15:00:00Z"}
    errors, _ = render_spec.validate_logic_dispatch(logic)
    assert "/blindSpots/0/researchRequest" in dict(errors)


def test_v2_stage1_fold_applies_the_reviewers_certainty_and_keeps_claudes(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path, V2_STAGE1, name="stage1")
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["assumptions"]["ASM-01"]["certainty"] = "confirmed"
    export_path = tmp_path / "reviewer-certainty.json"
    save_json(export_path, export)

    result = run_cli("fold", str(spec_dir), str(export_path))
    assert result.returncode == 0, result.stderr
    folded = load_json(spec_dir / "logic.json")
    assumption = next(item for item in folded["assumptions"] if item["id"] == "ASM-01")
    assert assumption["certainty"] == "confirmed"
    assert assumption["originalCertainty"] == "assumed"
    assert "(confirmed, set by the reviewer; Claude said assumed)" in (spec_dir / "logic.md").read_text(encoding="utf-8")
    assert run_cli("validate", str(spec_dir)).returncode == 0


def test_v2_stage1_logic_rejects_original_certainty() -> None:
    logic = load_json(V2_STAGE1 / "logic.json")
    logic["assumptions"][0]["originalCertainty"] = "assumed"
    errors, _ = render_spec.validate_logic_dispatch(logic)
    assert "/assumptions/0/originalCertainty" in dict(errors)


def test_validate_export_shape_rejects_an_unknown_reviewer_certainty() -> None:
    export = load_json(V2_STAGE1_EXPORTS / "signed.json")
    export["state"]["assumptions"]["ASM-01"]["certainty"] = "certain"
    errors = dict(render_spec.validate_export_shape(export))
    assert "/state/assumptions/ASM-01/certainty" in errors
