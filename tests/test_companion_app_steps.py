"""Tests for the companion app-mode step contract validator (``htmlkit.steps``).

Fixture-driven: every file under ``fixtures/steps/valid`` must validate, and every file under
``fixtures/steps/invalid`` must fail with the exact field path listed in ``invalid/expected.json``.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import steps  # noqa: E402
from htmlkit.steps import STAGES, STEP_KINDS, StepError, validate_step  # noqa: E402

FIXTURES = SKILL / "companion-app" / "fixtures" / "steps"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID_DIR = FIXTURES / "invalid"
INVALID = sorted(p for p in INVALID_DIR.glob("*.json") if p.name != "expected.json")
EXPECTED = json.loads((INVALID_DIR / "expected.json").read_text(encoding="utf-8"))


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_constants():
    assert STEP_KINDS == ("questions", "approaches", "design-section", "spec-review", "edit-card", "hand-off", "done")
    assert STAGES == ("context", "gray-areas", "questions", "approaches", "design", "spec", "hand-off")
    assert issubclass(StepError, ValueError)
    assert steps.StepError("msg", field="a.b").field == "a.b"


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixture_validates(path):
    raw = load(path)
    before = copy.deepcopy(raw)
    out = validate_step(raw)
    assert raw == before, "validate_step must not mutate its input"
    assert out["kind"] == raw["kind"]
    assert out is not raw


def test_every_step_kind_has_a_valid_fixture():
    assert {load(p)["kind"] for p in VALID} >= set(STEP_KINDS)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixture_reports_expected_field(path):
    assert path.name in EXPECTED
    with pytest.raises(StepError) as info:
        validate_step(load(path))
    assert info.value.field == EXPECTED[path.name], str(info.value)
    assert str(info.value)


def test_expected_json_covers_exactly_the_invalid_fixtures():
    assert set(EXPECTED) == {p.name for p in INVALID}


@pytest.mark.parametrize("raw", [None, [], "questions", 1, [{"v": 1}]])
def test_non_dict_is_rejected_at_root(raw):
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == ""


def test_mixed_questions_fixture_has_the_required_shapes():
    raw = load(FIXTURES / "valid" / "questions-mixed.json")
    kinds = {q["type"] for q in raw["questions"]}
    assert kinds == {"single", "multi", "text"}
    assert any("content_html" in q for q in raw["questions"])
    assert any("diagram" in q for q in raw["questions"])


def test_spec_review_fixtures_cover_both_formats():
    formats = {load(p)["format"] for p in VALID if load(p)["kind"] == "spec-review"}
    assert formats == {"markdown", "interactive"}


def test_empty_optional_strings_are_dropped():
    out = validate_step(load(FIXTURES / "valid" / "questions-empty-optionals.json"))
    assert "intro_md" not in out and "intro_html" not in out
    q = out["questions"][0]
    assert not {"header", "content_html", "diagram"} & set(q)


def test_approach_lists_default_to_empty():
    raw = {
        "v": 1, "kind": "approaches", "stage": "approaches", "title": "t",
        "approaches": [
            {"id": "a", "title": "A", "summary_md": "s", "recommended": True},
            {"id": "b", "title": "B", "summary_md": "s", "recommended": False},
        ],
    }
    out = validate_step(raw)
    for a in out["approaches"]:
        assert a["pros"] == [] and a["cons"] == [] and a["sources"] == []
    assert "pros" not in raw["approaches"][0]


def test_normalized_result_is_a_deep_copy():
    raw = load(FIXTURES / "valid" / "questions-mixed.json")
    out = validate_step(raw)
    out["questions"][0]["options"][0]["label"] = "changed"
    assert raw["questions"][0]["options"][0]["label"] != "changed"


def test_recommendation_is_optional_for_single_questions():
    raw = load(FIXTURES / "valid" / "questions-single.json")
    assert "recommended" not in raw["questions"][0]
    validate_step(raw)


@pytest.mark.parametrize("value", [None, 0, False, ["a"]])
def test_present_non_string_recommendation_is_rejected(value):
    raw = load(FIXTURES / "valid" / "questions-single.json")
    raw["questions"][0]["recommended"] = value
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == "questions[0].recommended"


def test_empty_string_recommendation_is_treated_as_absent():
    raw = load(FIXTURES / "valid" / "questions-single.json")
    raw["questions"][0]["recommended"] = ""
    assert "recommended" not in validate_step(raw)["questions"][0]


def test_at_most_one_recommended_per_question_is_structural():
    raw = load(FIXTURES / "valid" / "questions-mixed.json")
    raw["questions"][0]["recommended"] = ["narrow", "wide"]
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == "questions[0].recommended"


def test_changed_blocks_only_need_to_be_non_empty_strings():
    raw = load(FIXTURES / "valid" / "questions-single.json")
    raw["changed"] = {"summary": "s", "blocks": ["question:q1", "approach:a"]}
    assert validate_step(raw)["changed"]["blocks"] == ["question:q1", "approach:a"]
    raw["changed"]["blocks"] = ["ok", ""]
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == "changed.blocks[1]"


def test_empty_optional_step_id_is_dropped():
    raw = load(FIXTURES / "valid" / "edit-card.json")
    raw["invalidates"] = [{"label": "Design", "step_id": ""}]
    assert validate_step(raw)["invalidates"] == [{"label": "Design"}]


@pytest.mark.parametrize("bad_id", ["Q1", "a_b", "a b", "", "x" * 41, "é"])
def test_ids_must_match_the_option_id_pattern(bad_id):
    raw = load(FIXTURES / "valid" / "edit-card.json")
    raw["decision_id"] = bad_id
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == "decision_id"


def test_forty_char_id_is_accepted():
    raw = load(FIXTURES / "valid" / "edit-card.json")
    raw["decision_id"] = "x" * 40
    assert validate_step(raw)["decision_id"] == "x" * 40


@pytest.mark.parametrize("field", ["index", "total"])
def test_int_fields_reject_floats(field):
    raw = load(FIXTURES / "valid" / "design-section.json")
    raw[field] = 2.0
    with pytest.raises(StepError) as info:
        validate_step(raw)
    assert info.value.field == field
