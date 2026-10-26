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
    assert not [warning for warning in warnings if "Incomplete reports can only" in warning]
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


def test_committed_sample_asset_matches_the_renderer():
    import build_sample_report

    assert build_sample_report.render_sample() == TEMPLATE


SINCE = {"ref": "origin/main~3", "sha": "b" * 40}


def test_run_since_is_accepted_without_an_unknown_field_warning():
    prepared, warnings = m._prepare_report(report(since=dict(SINCE)))
    assert prepared["run"]["since"] == SINCE
    assert not [warning for warning in warnings if "Unknown" in warning]


@pytest.mark.parametrize("since", [
    "origin/main", [], {"ref": "main"}, {"sha": "b" * 40}, {"ref": "", "sha": "b" * 40},
    {"ref": "  ", "sha": "b" * 40}, {"ref": 3, "sha": "b" * 40}, {"ref": "main", "sha": "B" * 40},
    {"ref": "main", "sha": "b" * 39}, {"ref": "main", "sha": None},
])
def test_malformed_run_since_is_rejected(since):
    with pytest.raises(ValueError, match="run.since"):
        m._prepare_report(report(since=since))


def hunk_deep(**area):
    base = {"id": "A1", "status": "completed", "lines": 40,
            "hunks": [{"id": "A1.h1", "file": "a.py", "header": "@@ -1 +1 @@"}],
            "hunkless_files": ["bin.dat"], "examined": ["A1.h1"], "priority": 1}
    base.update(area)
    return {"enabled": True, "areas": [base], "unexamined": {"A1": ["A1.h1"]},
            "hunk_coverage": {"areas": 1, "hunks": 1, "examined": 1, "mean_area_lines": 40.0}}


def test_hunk_shaped_deep_areas_are_accepted_without_warnings():
    _, warnings = m._prepare_report(report(deep=hunk_deep()))
    assert not [warning for warning in warnings if "Unknown" in warning]


@pytest.mark.parametrize("area, path", [
    ({"hunks": "A1.h1"}, "run.deep.areas.hunks"),
    ({"hunks": ["A1.h1"]}, "run.deep.areas.hunks"),
    ({"hunks": [{"id": "A1.h1", "file": "a.py"}]}, "run.deep.areas.hunks"),
    ({"hunks": [{"id": 1, "file": "a.py", "header": "@@"}]}, "run.deep.areas.hunks"),
    ({"examined": "A1.h1"}, "run.deep.areas.examined"),
    ({"examined": [1]}, "run.deep.areas.examined"),
    ({"hunkless_files": "bin.dat"}, "run.deep.areas.hunkless_files"),
    ({"hunkless_files": [2]}, "run.deep.areas.hunkless_files"),
    ({"priority": "1"}, "run.deep.areas.priority"),
    ({"priority": True}, "run.deep.areas.priority"),
    ({"priority": 1.5}, "run.deep.areas.priority"),
])
def test_malformed_deep_area_hunk_keys_are_rejected(area, path):
    with pytest.raises(ValueError, match=path):
        m._prepare_report(report(deep=hunk_deep(**area)))


@pytest.mark.parametrize("key, value, path", [
    ("unexamined", ["A1.h1"], "run.deep.unexamined"),
    ("unexamined", {"A1": "A1.h1"}, "run.deep.unexamined"),
    ("unexamined", {"A1": [1]}, "run.deep.unexamined"),
    ("hunk_coverage", [], "run.deep.hunk_coverage"),
])
def test_malformed_deep_hunk_summaries_are_rejected(key, value, path):
    deep = hunk_deep()
    deep[key] = value
    with pytest.raises(ValueError, match=path):
        m._prepare_report(report(deep=deep))


PRODUCTION = {"label": "Common path", "path": "POST /refunds retried -> RefundService.apply"}
TALLY = {"checked": 3, "agreed": 1, "dropped": 1, "fixes_replaced": 0, "unreachable": 0,
         "survived": 1, "disputed": 0, "merged": 0}


def adjudicated(**changes):
    """A report whose findings all carry production and whose run.adjudication is complete."""
    value = report(adjudication=dict(
        {"status": "complete", "model": "opus", "reason": None, "tally": dict(TALLY),
         "checked_and_dropped": [{"file": "c.py", "line": "4", "title": "Guarded", "reason": "Checked",
                                  "proof": "c.py:3 guards it"}]}, **changes))
    for finding in value["findings"]:
        finding["production"] = dict(PRODUCTION)
    return value


def test_adjudication_fields_are_accepted_without_warnings():
    value = adjudicated()
    value["findings"][0]["adjudication"] = {
        "outcome": "fix_replaced", "objection": "Off by one", "proof": "a.py:3 quote",
        "what_would_settle": None,
        "severity_change": {"from": "Must fix", "to": "Should fix", "reason": "Edge case only"},
        "original_fix": {"fix_md": "Old fix.", "recommendation": "```diff\n-a\n+b\n```"},
        "merged_from": [{"file": "z.py", "line": "1", "dimension": "safety"}]}
    value["findings"][1]["adjudication"] = {"outcome": "unreachable", "objection": "No caller",
                                            "proof": None, "what_would_settle": None,
                                            "severity_change": None, "original_fix": None}
    prepared, warnings = m._prepare_report(value)
    assert not [w for w in warnings if "Unknown" in w]
    assert prepared["findings"][0]["production"] == PRODUCTION
    assert prepared["run"]["adjudication"]["status"] == "complete"


@pytest.mark.parametrize("production", [
    "Common path", {"label": "Likely", "path": "x"}, {"label": "Common path"},
    {"label": "Common path", "path": ""}, {"label": "Common path", "path": 3},
    {"label": "Common path", "path": "a\nb"}, {"label": "Common path", "path": "a b"},
    {"label": "Common path", "path": "x" * 201},
])
def test_malformed_production_is_rejected(production):
    value = report()
    value["findings"][0]["production"] = production
    with pytest.raises(ValueError, match="production"):
        m._prepare_report(value)


@pytest.mark.parametrize("label", ["Common path", "Edge case", "Unreachable", "Would miss", "N/A"])
def test_every_production_label_is_accepted_and_the_cap_is_inclusive(label):
    value = report()
    value["findings"][0]["production"] = {"label": label, "path": "x" * 200}
    m._prepare_report(value)


def test_existing_posted_text_caps_are_unchanged():
    assert m._POSTED_TEXT_CAPS == {"impact": 200, "fix_md": 160}


@pytest.mark.parametrize("adjudication, message", [
    ("agreed", "adjudication must be an object"),
    ({"outcome": "kept"}, "adjudication.outcome"),
    ({}, "adjudication.outcome"),
    ({"outcome": "disputed"}, "what_would_settle"),
    ({"outcome": "disputed", "what_would_settle": "  "}, "what_would_settle"),
    ({"outcome": "fix_replaced"}, "original_fix"),
    ({"outcome": "fix_replaced", "original_fix": {"fix_md": "x"}}, "original_fix"),
    ({"outcome": "fix_replaced", "original_fix": {"recommendation": 3}}, "original_fix"),
    ({"outcome": "unreachable"}, "Nit"),
    ({"outcome": "agreed", "objection": 3}, "objection"),
    ({"outcome": "agreed", "merged_from": "z.py"}, "merged_from"),
])
def test_malformed_finding_adjudication_is_rejected(adjudication, message):
    value = report()
    value["findings"][0]["adjudication"] = adjudication
    with pytest.raises(ValueError, match=message):
        m._prepare_report(value)


def test_unreachable_outcome_is_accepted_on_a_nit():
    value = report()
    value["findings"][1]["adjudication"] = {"outcome": "unreachable"}
    m._prepare_report(value)


@pytest.mark.parametrize("changes, message", [
    ({"status": "done"}, "run.adjudication.status"),
    ({"tally": None}, "run.adjudication.tally"),
    ({"tally": []}, "run.adjudication.tally"),
    ({"tally": dict(TALLY, agreed=-1)}, "run.adjudication.tally"),
    ({"tally": dict(TALLY, agreed=1.5)}, "run.adjudication.tally"),
    ({"tally": dict(TALLY, agreed=True)}, "run.adjudication.tally"),
    ({"tally": dict(TALLY, agreed="1")}, "run.adjudication.tally"),
    ({"checked_and_dropped": "x"}, "run.adjudication.checked_and_dropped"),
    ({"checked_and_dropped": [{"file": "a", "line": "1", "title": "t"}]},
     "run.adjudication.checked_and_dropped"),
    ({"checked_and_dropped": [{"file": "a", "line": 1, "title": "t", "reason": "r"}]},
     "run.adjudication.checked_and_dropped"),
    ({"checked_and_dropped": [{"file": "a", "line": "1", "title": "t", "reason": "r", "proof": 3}]},
     "run.adjudication.checked_and_dropped"),
])
def test_malformed_run_adjudication_is_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        m._prepare_report(adjudicated(**changes))


def test_run_adjudication_must_be_an_object():
    with pytest.raises(ValueError, match="run.adjudication must be an object"):
        m._prepare_report(report(adjudication="complete"))


def test_complete_adjudication_requires_production_on_every_finding():
    value = adjudicated()
    del value["findings"][1]["production"]
    with pytest.raises(ValueError, match="production"):
        m._prepare_report(value)


@pytest.mark.parametrize("status", ["failed", "disabled"])
def test_failed_and_disabled_adjudication_require_a_reason_but_not_production(status):
    base = {"status": status, "model": None, "tally": None, "checked_and_dropped": []}
    for reason in (None, "", "  "):
        with pytest.raises(ValueError, match="run.adjudication.reason"):
            m._prepare_report(report(adjudication=dict(base, reason=reason)))
    prepared, warnings = m._prepare_report(report(adjudication=dict(base, reason="turned off by policy")))
    assert not [w for w in warnings if "Unknown" in w]
    assert prepared["run"]["adjudication"]["status"] == status


@pytest.mark.parametrize("status", ["failed", "disabled"])
@pytest.mark.parametrize("changes, message", [
    ({"tally": TALLY}, "run.adjudication.tally"),
    ({"tally": {}}, "run.adjudication.tally"),
    ({"checked_and_dropped": [{"file": "a.py", "line": "1", "title": "t", "reason": "r"}]},
     "run.adjudication.checked_and_dropped"),
])
def test_failed_and_disabled_adjudication_reject_a_tally_or_dropped_entries(status, changes, message):
    base = {"status": status, "model": None, "reason": "adjudicator timed out",
            "tally": None, "checked_and_dropped": []}
    with pytest.raises(ValueError, match=message):
        m._prepare_report(report(adjudication=dict(base, **changes)))


@pytest.mark.parametrize("status", ["failed", "disabled"])
def test_failed_and_disabled_adjudication_accept_absent_tally_and_dropped(status):
    prepared, _ = m._prepare_report(report(adjudication={"status": status, "reason": "adjudicator timed out"}))
    assert prepared["run"]["adjudication"]["status"] == status
