"""Contract checks for scoring a review against a human reviewer's comments."""
import json
from pathlib import Path

import pytest

import score_human_review as scorer

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "full-code-review" / "human-reviews"
HEAD = "0495fdb39536d5f7d581b76ac784c75835e8e90e"


def _key(*defects):
    return {
        "schema_version": 1,
        "target": {"project": "example/app", "number": 7, "head_sha": HEAD},
        "defects": list(defects),
    }


def _defect(identifier="H1", **overrides):
    return dict(
        {
            "id": identifier,
            "title": "Hidden error blocks Save",
            "anchors": [{"file": "src/Field.tsx", "line_min": 30, "line_max": 40}],
            "keywords": ["clearError"],
        },
        **overrides,
    )


def _report(*findings):
    return {"meta": {"project": "example/app", "iid": 7, "head_sha": HEAD}, "findings": list(findings)}


def _finding(identifier="F1", **overrides):
    return dict({"id": identifier, "file": "src/Field.tsx", "line": "35", "title": "Call clearError on unmount"}, **overrides)


def test_anchor_overlap_plus_keyword_is_caught():
    result = scorer.score(_report(_finding()), _key(_defect()))
    assert result["caught_count"] == 1
    assert result["caught"][0]["finding_ids"] == ["F1"]
    assert result["recall"] == 1.0


def test_anchor_overlap_without_keyword_is_only_partial():
    result = scorer.score(_report(_finding(title="Unmount effect copied from FormCheckbox")), _key(_defect()))
    assert (result["caught_count"], result["partial_count"]) == (0, 1)


def test_keyword_in_another_file_is_missed():
    result = scorer.score(_report(_finding(file="src/Other.tsx")), _key(_defect()))
    assert result["missed_count"] == 1


def test_line_ranges_overlap_on_either_edge():
    assert scorer.score(_report(_finding(line="25-30")), _key(_defect()))["caught_count"] == 1
    assert scorer.score(_report(_finding(line="41-50")), _key(_defect()))["missed_count"] == 1


def test_any_severity_counts_because_humans_file_nits():
    result = scorer.score(_report(_finding(severity="Nit")), _key(_defect()))
    assert result["caught_count"] == 1


def test_target_mismatch_is_reported():
    report = _report(_finding())
    report["meta"]["head_sha"] = "f" * 40
    assert scorer.score(report, _key(_defect()))["target_matches"] is False


@pytest.mark.parametrize(
    "bad",
    [
        {"schema_version": 2},
        {"defects": []},
        {"defects": [_defect(), _defect()]},
        {"defects": [_defect(anchors=[])]},
        {"defects": [_defect(anchors=[{"file": "a", "line_min": 9, "line_max": 3}])]},
        {"defects": [_defect(keywords=[])]},
    ],
)
def test_invalid_answer_keys_are_rejected(bad):
    with pytest.raises(ValueError):
        scorer.score(_report(), dict(_key(_defect()), **bad))


def test_cli_exits_1_below_min_recall_and_2_on_wrong_target(tmp_path, capsys):
    report_path, key_path = tmp_path / "report.json", tmp_path / "key.json"
    key_path.write_text(json.dumps(_key(_defect(), _defect("H2", keywords=["absent"]))))
    report_path.write_text(json.dumps(_report(_finding())))
    assert scorer.main(["--report", str(report_path), "--answer-key", str(key_path), "--min-recall", "0.5"]) == 0
    assert scorer.main(["--report", str(report_path), "--answer-key", str(key_path), "--min-recall", "0.9"]) == 1
    wrong = _report(_finding())
    wrong["meta"]["iid"] = 8
    report_path.write_text(json.dumps(wrong))
    assert scorer.main(["--report", str(report_path), "--answer-key", str(key_path)]) == 2
    capsys.readouterr()


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_every_human_review_fixture_is_a_valid_answer_key(path):
    key = json.loads(path.read_text(encoding="utf-8"))
    scorer._validate_key(key)
    assert len(key["target"]["head_sha"]) == 40
