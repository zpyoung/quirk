"""Behavioral contract for the interactive logic-spec renderer CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive"
SAMPLE = FIXTURES / "sample"
EXPORTS = SAMPLE / "exports"
V2_STAGE1 = FIXTURES / "v2" / "stage1"
V2_STAGE2 = FIXTURES / "v2" / "stage2"
INVALID_V2 = FIXTURES / "invalid-v2"
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


def test_v2_stage1_validates_with_exactly_one_scenario_count_warning() -> None:
    result = run_cli("validate", str(V2_STAGE1))
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    warnings = [line for line in result.stderr.splitlines() if line.strip()]
    assert warnings == ["warning: behavior BH-01 has 4 scenarios; extras carry reasons"]


def test_v2_stage2_validates() -> None:
    result = run_cli("validate", str(V2_STAGE2))
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


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


def test_fold_preflights_output_paths_before_approving_source(tmp_path: Path) -> None:
    spec_dir = make_v2_spec(tmp_path / "blocked-output", V2_STAGE1, name="stage1")
    (spec_dir / "logic.md").mkdir()

    result = run_cli("render", str(spec_dir))
    assert result.returncode == 1
    assert not (spec_dir / "review.html").exists()
