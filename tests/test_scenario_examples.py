"""Behavioral contract for scenario data-state examples in the interactive logic-spec renderer."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive" / "v2"
EXAMPLES = FIXTURES / "examples"
EXAMPLES_EXPORTS = EXAMPLES / "exports"
STAGE1 = FIXTURES / "stage1"

sys.path.insert(0, str(SCRIPT.parent))
import render_spec  # noqa: E402

MALFORMED = "malformed [ASK] marker; write [ASK: <question>]"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_spec(tmp_path: Path, name: str = "examples") -> Path:
    spec_dir = tmp_path / name
    spec_dir.mkdir(parents=True)
    shutil.copy(EXAMPLES / "logic.json", spec_dir / "logic.json")
    return spec_dir


def example_logic() -> dict:
    return load_json(EXAMPLES / "logic.json")


def scenario(logic: dict, ident: str) -> dict:
    return next(item for item in logic["scenarios"] if item["id"] == ident)


def errors_for(logic: dict) -> List[tuple]:
    return render_spec.validate_logic_v2(logic)[0]


def valid_example() -> dict:
    return {"before": "Before.", "steps": ["One.", "Two."], "after": "After."}


def test_validate_accepts_the_example_fixture() -> None:
    result = run_cli("validate", str(EXAMPLES))
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_scenario_without_example_is_still_valid() -> None:
    logic = example_logic()
    assert "example" not in scenario(logic, "SC-04")
    assert errors_for(logic) == []


@pytest.mark.parametrize(
    "mutate, pointer",
    [
        (lambda ex: ex.pop("before"), "/scenarios/0/example/before"),
        (lambda ex: ex.pop("steps"), "/scenarios/0/example/steps"),
        (lambda ex: ex.pop("after"), "/scenarios/0/example/after"),
        (lambda ex: ex.update(steps=[]), "/scenarios/0/example/steps"),
        (lambda ex: ex.update(steps=["One.", ""]), "/scenarios/0/example/steps/1"),
        (lambda ex: ex.update(steps=["One.", 3]), "/scenarios/0/example/steps/1"),
        (lambda ex: ex.update(steps="One."), "/scenarios/0/example/steps"),
        (lambda ex: ex.update(before=""), "/scenarios/0/example/before"),
        (lambda ex: ex.update(before=7), "/scenarios/0/example/before"),
        (lambda ex: ex.update(after=["After."]), "/scenarios/0/example/after"),
        (lambda ex: ex.update(extra="x"), "/scenarios/0/example/extra"),
    ],
)
def test_validate_rejects_malformed_example_shapes(mutate: Any, pointer: str) -> None:
    logic = example_logic()
    example = valid_example()
    mutate(example)
    logic["scenarios"][0]["example"] = example
    assert pointer in [path for path, _ in errors_for(logic)]


def test_validate_rejects_a_non_object_example() -> None:
    logic = example_logic()
    logic["scenarios"][0]["example"] = "text"
    assert ("/scenarios/0/example", "expected an object") in errors_for(logic)


@pytest.mark.parametrize("marker", ["[ask: is this right?]", "[ASK]", "[ASK:x]", "[ Ask: x]", "[ASK: ]"])
def test_validate_rejects_malformed_ask_markers_in_every_part_in_stage_1(marker: str) -> None:
    for part, pointer in (
        ("before", "/scenarios/0/example/before"),
        ("after", "/scenarios/0/example/after"),
        ("steps", "/scenarios/0/example/steps/1"),
    ):
        logic = example_logic()
        example = valid_example()
        if part == "steps":
            example["steps"][1] = "Step " + marker
        else:
            example[part] = "Text " + marker
        logic["scenarios"][0]["example"] = example
        assert (pointer, MALFORMED) in errors_for(logic), (marker, part)


def test_validate_accepts_a_well_formed_open_ask_in_stage_1() -> None:
    logic = example_logic()
    logic["scenarios"][0]["example"]["after"] = "Result. [ASK: which one?]"
    assert errors_for(logic) == []


def test_scenario_open_asks_collects_questions_in_part_order() -> None:
    sc = {
        "example": {
            "before": "A [ASK: first?] B [ASK: second?]",
            "steps": ["no gap", "[ASK: third?]"],
            "after": "[ASK: fourth?]",
        }
    }
    assert render_spec.scenario_open_asks(sc) == ["first?", "second?", "third?", "fourth?"]
    assert render_spec.scenario_open_asks({"id": "SC-9"}) == []


def test_scenario_open_asks_is_case_sensitive_and_single_line() -> None:
    assert render_spec.scenario_open_asks({"example": {"before": "[ask: x]", "steps": ["s"], "after": "a"}}) == []
    assert render_spec.scenario_open_asks({"example": {"before": "[ASK: a\nb]", "steps": ["s"], "after": "a"}}) == []


def test_stage_2_open_ask_on_a_live_scenario_fails_and_on_a_dropped_one_passes(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    fold = run_cli("fold", str(spec_dir), str(EXAMPLES_EXPORTS / "drop-open-ask.json"))
    assert fold.returncode == 0, fold.stderr
    folded = load_json(spec_dir / "logic.json")
    assert folded["stage"] == 2
    assert render_spec.scenario_open_asks(scenario(folded, "SC-02"))
    assert "dropReason" in scenario(folded, "SC-02")
    assert errors_for(folded) == []

    live = copy.deepcopy(folded)
    index = next(i for i, item in enumerate(live["scenarios"]) if item["id"] == "SC-01")
    live["scenarios"][index]["example"]["after"] += " [ASK: still open?]"
    assert (pointer_of(index), "open [ASK] after stage-1 sign-off") in errors_for(live)


def pointer_of(index: int) -> str:
    return "/scenarios/" + str(index) + "/example"


def test_item_hash_covers_the_example() -> None:
    logic = example_logic()
    base = render_spec.item_hashes(logic)

    without = copy.deepcopy(logic)
    del scenario(without, "SC-01")["example"]
    assert render_spec.item_hashes(without)["SC-01"] != base["SC-01"]

    edited = copy.deepcopy(logic)
    scenario(edited, "SC-01")["example"]["steps"][0] += " "
    assert render_spec.item_hashes(edited)["SC-01"] != base["SC-01"]
    assert render_spec.item_hashes(edited)["SC-02"] == base["SC-02"]


def test_scenarios_without_an_example_keep_their_existing_hashes() -> None:
    logic = load_json(STAGE1 / "logic.json")
    signed = load_json(STAGE1 / "exports" / "signed.json")
    hashes = render_spec.item_hashes(logic)
    for ident in ("SC-01", "SC-02", "SC-03", "SC-04", "SC-05"):
        assert hashes[ident] == signed["seen"][ident]
    assert render_spec.render_id(logic) == signed["renderId"]


def test_example_markdown_lines_are_exact_for_single_line_parts() -> None:
    lines = render_spec._example_markdown_lines(scenario(example_logic(), "SC-01")["example"])
    assert lines == [
        '   - **Data before:** **Charge 1**: Coffee line $100.00; "Loyalty" 10% off; "Winback" 15% off',
        "   - **Walkthrough:**",
        '     1. "Loyalty": $100.00 × 0.90 = $90.00',
        '     2. "Winback": $90.00 × 0.85 = $76.50',
        '   - **Data after:** **Charge 1**: ✓ Coffee line $76.50; "Loyalty" took $10.00; "Winback" took $13.50',
    ]


def test_example_markdown_lines_hard_break_and_indent_multi_line_parts() -> None:
    lines = render_spec._example_markdown_lines(scenario(example_logic(), "SC-03")["example"])
    assert lines == [
        '   - **Data before:** **Discount definition** "Loyalty": 10% off  ',
        "     (a) used 4* times  ",
        "     (b) never used",
        "   - **Walkthrough:**",
        '     1. The merchant changes "Loyalty" to 15%  ',
        "        (a) The request succeeds, but the change is ignored  ",
        "        (b) The change is saved",
        '   - **Data after:** (a) ✗ "Loyalty" stays 10%  ',
        "     (b) ✓ \"Loyalty\" is 15%; queued charges pick it up on their next regen",
    ]


def test_example_markdown_lines_normalize_line_endings_and_pass_marks_through() -> None:
    lines = render_spec._example_markdown_lines(
        {"before": "a\r\nb\rc", "steps": ["**x** *y* [ASK: z?]"], "after": "done"}
    )
    assert lines[0] == "   - **Data before:** a  "
    assert lines[1:3] == ["     b  ", "     c"]
    assert lines[4] == "     1. **x** *y* [ASK: z?]"
    assert render_spec._example_markdown_lines({"before": "a", "steps": ["s"], "after": "b"}) == (
        render_spec._example_markdown_lines({"before": "a", "steps": ["s"], "after": "b"})
    )


def test_render_places_example_between_alternatives_and_explanation(tmp_path: Path) -> None:
    logic = example_logic()
    lines = render_spec.render_markdown_v2(logic).split("\n")
    start = lines.index("1. **SC-01**")
    block = lines[start : start + 12]
    assert block[4].startswith("   - **Alternatives** ")
    assert block[5].startswith("   - **Data before:**")
    assert block[9].startswith("   - **Data after:**")
    assert block[10] == "   - Percentage discounts compound instead of adding."

    plain = lines.index("1. **SC-04**") if "1. **SC-04**" in lines else lines.index("2. **SC-04**")
    assert lines[plain + 4] == "   - Selection stays explicit."
    assert not any("Data before" in line for line in lines[plain : plain + 6])


def test_render_leaves_markdown_unchanged_for_specs_without_examples() -> None:
    logic = load_json(STAGE1 / "logic.json")
    assert "Data before" not in render_spec.render_markdown_v2(logic)


def fold_export(tmp_path: Path, name: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    spec_dir = make_spec(tmp_path)
    result = run_cli("fold", str(spec_dir), str(EXAMPLES_EXPORTS / (name + ".json")))
    return result, spec_dir


def test_exports_are_consistent_with_the_fixture() -> None:
    logic = example_logic()
    for path in sorted(EXAMPLES_EXPORTS.glob("*.json")):
        export = load_json(path)
        assert export["renderId"] == render_spec.render_id(logic), path.name
        hashes = render_spec.item_hashes(logic)
        assert all(hashes[ident] == value for ident, value in export["seen"].items()), path.name
        assert export["signed"] is True


def test_fold_refuses_an_approved_scenario_with_an_open_ask(tmp_path: Path) -> None:
    result, spec_dir = fold_export(tmp_path, "approve-open-ask")
    assert result.returncode == 4, result.stderr
    assert "gate examples: open [ASK] in SC-02" in result.stderr
    assert load_json(spec_dir / "logic.json")["stage"] == 1


def test_fold_refuses_an_approved_scenario_whose_outcome_changed(tmp_path: Path) -> None:
    result, spec_dir = fold_export(tmp_path, "approve-changed-outcome")
    assert result.returncode == 4, result.stderr
    assert "gate examples: outcome changed on SC-01; Claude must rewrite its example first" in result.stderr
    assert "open [ASK]" not in result.stderr
    assert load_json(spec_dir / "logic.json")["stage"] == 1


def test_fold_accepts_a_dropped_open_ask_scenario_and_keeps_its_example_and_pin(tmp_path: Path) -> None:
    result, spec_dir = fold_export(tmp_path, "drop-open-ask")
    assert result.returncode == 0, result.stderr
    folded = load_json(spec_dir / "logic.json")
    original = example_logic()
    assert scenario(folded, "SC-02")["example"] == scenario(original, "SC-02")["example"]
    assert scenario(folded, "SC-01")["example"] == scenario(original, "SC-01")["example"]
    assert folded["stage1Pin"]["itemHashes"] == render_spec.stage1_item_hashes(folded)
    assert "SC-02" in folded["stage1Pin"]["itemHashes"]


@pytest.mark.parametrize("choice, custom", [("custom", ""), ("custom", "Other."), ("alt-0", "")])
def gate_state(approved: List[str], drops: Dict[str, str], outcomes: Dict[str, Any]) -> dict:
    state = copy.deepcopy(load_json(EXAMPLES_EXPORTS / "drop-open-ask.json")["state"])
    state["scenarioApproved"] = {ident: True for ident in approved}
    state["scenarioDrops"] = drops
    state["scenarioOutcomes"] = outcomes
    return state


@pytest.mark.parametrize("choice, custom", [("custom", ""), ("custom", "Other."), ("alt-0", "")])
def test_gate_treats_any_non_spec_choice_as_changed(choice: str, custom: str) -> None:
    logic = example_logic()
    state = gate_state(["SC-01"], {}, {"SC-01": {"choice": choice, "custom": custom}})
    failures = render_spec.stage1_gate_failures(logic, state)
    assert ("examples", "outcome changed on SC-01; Claude must rewrite its example first") in failures


def test_gate_ignores_spec_choice_dropped_scenarios_and_scenarios_without_examples() -> None:
    logic = example_logic()
    state = gate_state(["SC-01", "SC-02", "SC-04"], {"SC-02": "deferred"}, {"SC-01": {"choice": "spec", "custom": ""}})
    assert [name for name, _ in render_spec.stage1_gate_failures(logic, state)].count("examples") == 0
    state["scenarioOutcomes"]["SC-04"] = {"choice": "custom", "custom": "x"}
    assert [name for name, _ in render_spec.stage1_gate_failures(logic, state)].count("examples") == 0


def test_gate_reports_one_failure_per_offending_scenario_in_scenario_order() -> None:
    logic = example_logic()
    scenario(logic, "SC-03")["example"]["after"] += " [ASK: open?]"
    state = gate_state(["SC-01", "SC-02", "SC-03", "SC-04"], {}, {"SC-01": {"choice": "alt-0", "custom": ""}})
    messages = [msg for name, msg in render_spec.stage1_gate_failures(logic, state) if name == "examples"]
    assert messages == [
        "outcome changed on SC-01; Claude must rewrite its example first",
        "open [ASK] in SC-02",
        "open [ASK] in SC-03",
    ]


def test_gate_emits_only_the_open_ask_tuple_when_the_outcome_also_changed() -> None:
    logic = example_logic()
    state = gate_state(["SC-02"], {}, {"SC-02": {"choice": "custom", "custom": "Other."}})
    examples = [msg for name, msg in render_spec.stage1_gate_failures(logic, state) if name == "examples"]
    assert examples == ["open [ASK] in SC-02"]


class PayloadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_payload = False
        self.chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "script" and dict(attrs).get("id") == "quirk-logic-spec-payload":
            self.in_payload = True

    def handle_data(self, data: str) -> None:
        if self.in_payload:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_payload = False


def test_review_page_payload_lists_open_asks_for_exactly_the_open_scenario(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    parser = PayloadParser()
    parser.feed((spec_dir / "review.html").read_text(encoding="utf-8"))
    payload = json.loads("".join(parser.chunks))
    assert payload["openAsks"] == {
        "SC-02": ['does "Welcome" stay on the subscription once its uses run out, or get removed?']
    }
    assert "**Data before:**" in payload["logicMarkdown"]


def test_review_page_payload_has_an_empty_open_asks_object_without_gaps(tmp_path: Path) -> None:
    spec_dir = tmp_path / "plain"
    spec_dir.mkdir()
    shutil.copy(STAGE1 / "logic.json", spec_dir / "logic.json")
    assert run_cli("render", str(spec_dir)).returncode == 0
    parser = PayloadParser()
    parser.feed((spec_dir / "review.html").read_text(encoding="utf-8"))
    assert json.loads("".join(parser.chunks))["openAsks"] == {}
