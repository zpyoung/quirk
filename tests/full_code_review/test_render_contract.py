import copy
from pathlib import Path

import pytest

import comment_body
import render_report as m

TEMPLATE = (Path(m.__file__).resolve().parents[1] / "assets" / "report.html").read_text(encoding="utf-8")
HEAD = "a" * 40


def report(**run):
    return {
        "schema_version": 1,
        "meta": {"target": "change", "forge": "github", "number": 7, "project": "o/r",
                 "head_sha": HEAD, "title": "Review", "verdict": "Approve", "seat": "author"},
        "run": dict({"dimensions_run": ["correctness"]}, **run),
        "findings": [
            {"severity": "Should fix", "dimension": "correctness", "file": "a.py", "line": "3",
             "title": "Real bug", "body_md": "b", "impact": "Breaks.", "fix_md": "Fix it."},
            {"severity": "Nit", "dimension": "comments", "file": "b.py", "line": "9",
             "title": "Tiny", "body_md": "b", "impact": "Noise.", "fix_md": "Trim it."},
        ],
    }


def test_schema_version_and_new_run_keys_are_accepted_without_warnings():
    value = report(incomplete=False, dimensions_failed=[], models={"correctness": "opus"},
                   verification={"enabled": True, "model": "codex", "checked": 2, "refuted": 1,
                                 "fallback": None},
                   excluded_generated=["poetry.lock"],
                   policy_sources=[{"kind": "review-md", "path": "REVIEW.md", "ref": None}],
                   severity_floor="Should fix")
    _, warnings = m._prepare_report(value)
    assert not [w for w in warnings if "Unknown" in w]


def test_failed_lenses_force_incomplete_and_replace_a_clean_verdict():
    prepared, warnings = m._prepare_report(report(dimensions_failed=["db", "safety"]))
    assert prepared["run"]["incomplete"] is True
    assert prepared["meta"]["verdict"] == "Incomplete review"
    assert any("Incomplete" in w for w in warnings)


def test_incomplete_report_keeps_a_non_clean_verdict():
    value = report(incomplete=True, dimensions_failed=["db"])
    value["meta"]["verdict"] = "Request changes"
    prepared, _ = m._prepare_report(value)
    assert prepared["meta"]["verdict"] == "Request changes"


@pytest.mark.parametrize("verdict", ["Looks good", "Ship it", "Approve with comments", "approved"])
def test_incomplete_report_rejects_any_verdict_outside_the_blocking_vocabulary(verdict):
    value = report(incomplete=True, dimensions_failed=["db"])
    value["meta"]["verdict"] = verdict
    prepared, _ = m._prepare_report(value)
    assert prepared["meta"]["verdict"] == "Incomplete review"


def test_deep_pending_area_cannot_render_as_a_complete_review():
    value = report(deep={"enabled": True, "areas": [{"id": "A2", "status": "pending"}]})
    prepared, _ = m._prepare_report(value)
    assert prepared["run"]["incomplete"] is True
    assert prepared["run"]["deep"]["unreached_areas"] == ["A2"]
    assert prepared["meta"]["verdict"] == "Incomplete review"


def test_complete_report_keeps_a_free_text_verdict():
    value = report()
    value["meta"]["verdict"] = "Looks good"
    prepared, _ = m._prepare_report(value)
    assert prepared["meta"]["verdict"] == "Looks good"


def test_incomplete_banner_names_the_failed_lenses():
    html = m.render_html(report(incomplete=True, dimensions_failed=["db", "safety"]), TEMPLATE)
    assert "Incomplete review." in html
    assert "db, safety" in html


@pytest.mark.parametrize("run, message", [
    ({"incomplete": "yes"}, "run.incomplete"),
    ({"dimensions_failed": "db"}, "run.dimensions_failed"),
    ({"severity_floor": "Blocker"}, "run.severity_floor"),
    ({"models": ["opus"]}, "run.models"),
])
def test_malformed_contract_keys_are_rejected(run, message):
    with pytest.raises(ValueError) as exc:
        m._prepare_report(report(**run))
    assert message in str(exc.value)


def test_markdown_render_reports_incompleteness_and_models():
    md = m.render_md(report(incomplete=True, dimensions_failed=["db"],
                            models={"correctness": "opus"}))
    assert "**Incomplete:** db did not finish" in md
    assert "correctness: opus" in md


@pytest.mark.parametrize("floor, posted", [
    (None, {"F1"}),
    ("Should fix", {"F1"}),
    ("Nit", {"F1", "F2"}),
    ("Must fix", set()),
])
def test_author_bodies_never_post_below_the_severity_floor(floor, posted):
    value = report() if floor is None else report(severity_floor=floor)
    bodies = comment_body._author_bodies(value)
    assert {fid for fid, entry in bodies["findings"].items() if entry["post"]} == posted


def test_findings_below_the_floor_still_render_on_the_page():
    html = m.render_html(report(severity_floor="Must fix"), TEMPLATE)
    assert "Real bug" in html and "Tiny" in html


def test_below_floor_helper():
    prepared, _ = m._prepare_report(report())
    should, nit = prepared["findings"]
    assert m.severity_floor(prepared) == "Should fix"
    assert not m.below_floor(should, "Should fix")
    assert m.below_floor(nit, "Should fix")
    assert m.below_floor(copy.deepcopy(should), "Must fix")


@pytest.mark.parametrize("deep, path", [
    ([], "run.deep"),
    ({"areas": [None]}, "run.deep.areas"),
    ({"unreached_areas": ["A1", 4]}, "run.deep.unreached_areas"),
    ({"checked_and_dropped": ["bad"]}, "run.deep.checked_and_dropped"),
    ({"checked_and_dropped": [{"file": "a.py", "line": "2", "title": "Bad"}]},
     "run.deep.checked_and_dropped"),
    ({"checked_and_dropped": [{"file": "a.py", "line": 2, "title": "Bad", "reason": "No"}]},
     "run.deep.checked_and_dropped"),
])
def test_deep_contract_rejects_malformed_structures(deep, path):
    with pytest.raises(ValueError, match=path):
        m._prepare_report(report(deep=deep))


@pytest.mark.parametrize("verdict", ["Approve", "Fix, then merge", "Request changes"])
def test_unreached_deep_areas_always_force_incomplete_verdict(verdict):
    value = report(deep={"enabled": True, "unreached_areas": ["A7", "A8"]})
    value["meta"]["verdict"] = verdict
    prepared, warnings = m._prepare_report(value)
    assert prepared["run"]["incomplete"] is True
    assert prepared["meta"]["verdict"] == "Incomplete review"
    assert not [warning for warning in warnings if "Unknown run field" in warning]
    html = m.render_html(value, TEMPLATE)
    assert "Unreached areas: A7, A8" in html
    assert "unknown lenses" not in html
    md = m.render_md(value)
    assert "**Incomplete:** unreached areas (A7, A8) did not finish" in md


@pytest.mark.parametrize("status", ["unconfirmed", None, 3])
def test_finding_rejects_unknown_verification_status(status):
    value = report()
    value["findings"][0]["verification_status"] = status
    with pytest.raises(ValueError, match="verification_status"):
        m._prepare_report(value)


@pytest.mark.parametrize("confirm", [None, "", "  ", 1])
def test_plausible_finding_requires_text_to_confirm(confirm):
    value = report()
    value["findings"][0].update(verification_status="plausible", what_would_confirm=confirm)
    with pytest.raises(ValueError, match="what_would_confirm"):
        m._prepare_report(value)


def test_plausible_finding_is_unverified_even_if_input_says_verified():
    value = report()
    value["findings"][0].update(verification_status="plausible",
                                what_would_confirm="Run the changed path.", verified=True)
    prepared, warnings = m._prepare_report(value)
    assert prepared["findings"][0]["verified"] is False
    assert not [warning for warning in warnings if "Unknown finding" in warning]
    assert value["findings"][0]["verified"] is True


@pytest.mark.parametrize("repro", [False, [], {}, {"command": "run", "output": ""},
                                     {"command": "  ", "output": "failed"},
                                     {"command": "run", "output": 4}])
def test_finding_rejects_invalid_reproduction(repro):
    value = report()
    value["findings"][0]["repro"] = repro
    with pytest.raises(ValueError, match="repro"):
        m._prepare_report(value)


def test_deep_reproduced_evidence_requires_reproduction():
    value = report(deep={"enabled": True})
    value["findings"][0]["evidence"] = "reproduced"
    with pytest.raises(ValueError, match="repro"):
        m._prepare_report(value)
    value["findings"][0]["repro"] = {"command": "python3 test.py", "output": "failed"}
    prepared, _ = m._prepare_report(value)
    assert prepared["findings"][0]["repro"] == value["findings"][0]["repro"]
