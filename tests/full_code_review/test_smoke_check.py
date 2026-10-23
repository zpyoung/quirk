import contextlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import smoke_check as m

SMOKE = Path(__file__).resolve().parents[1] / "fixtures" / "full-code-review" / "smoke"
EXPECTED = {"lens": "db", "file": "report.py", "line_min": 3, "line_max": 4}


def finding(**over):
    return dict({"severity": "Should fix", "dimension": "db", "file": "report.py", "line": "4",
                 "title": "Query in a loop"}, **over)


@pytest.mark.parametrize("value, passed", [
    (finding(), True),
    (finding(line="1-3"), True),
    (finding(line="1-2"), False),
    (finding(line="5-9"), False),
    (finding(line="3", dimension=None, dimensions=["resilience", "db"]), True),
    (finding(dimension="resilience"), False),
    (finding(file="other.py"), False),
    (finding(severity="Nit"), False),
    (finding(severity="Must fix"), True),
])
def test_check_matches_lens_file_overlap_and_severity(value, passed):
    assert m.check({"findings": [value]}, EXPECTED)[0] is passed


def test_cli_exit_codes(tmp_path):
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(EXPECTED))
    for findings, code in (([finding()], 0), ([finding(file="x.py")], 1)):
        report = tmp_path / "report.json"
        report.write_text(json.dumps({"findings": findings}))
        with contextlib.redirect_stdout(io.StringIO()):
            assert m.main(["--report", str(report), "--expected", str(expected)]) == code
    expected.write_text(json.dumps({"lens": "db"}))
    with contextlib.redirect_stdout(io.StringIO()):
        assert m.main(["--report", str(report), "--expected", str(expected)]) == 2


@pytest.mark.parametrize("report, expected", [
    ([], EXPECTED),
    ({"findings": ["not an object"]}, EXPECTED),
    ({"findings": [finding()]}, dict(EXPECTED, line_max="four")),
])
def test_malformed_input_exits_2_not_as_a_smoke_miss(tmp_path, report, expected):
    report_path, expected_path = tmp_path / "report.json", tmp_path / "expected.json"
    report_path.write_text(json.dumps(report))
    expected_path.write_text(json.dumps(expected))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert m.main(["--report", str(report_path), "--expected", str(expected_path)]) == 2
    assert "error" in json.loads(out.getvalue())


@pytest.mark.parametrize("name, content, message", [
    ("report", "[]", "report must be a JSON object"),
    ("expected", "not json", "could not read expected"),
])
def test_bad_input_error_names_which_file_was_wrong(tmp_path, name, content, message):
    paths = {"report": tmp_path / "report.json", "expected": tmp_path / "expected.json"}
    paths["report"].write_text(json.dumps({"findings": []}))
    paths["expected"].write_text(json.dumps(EXPECTED))
    paths[name].write_text(content)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert m.main(["--report", str(paths["report"]), "--expected", str(paths["expected"])]) == 2
    assert message in json.loads(out.getvalue())["error"]


ABSENT = dict(EXPECTED, absent=True)
PRODUCTION = {"label": "Reachable", "path": "report.render -> run"}


def run_cli(tmp_path, report, expected):
    report_path, expected_path = tmp_path / "report.json", tmp_path / "expected.json"
    report_path.write_text(json.dumps(report))
    expected_path.write_text(json.dumps(expected))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = m.main(["--report", str(report_path), "--expected", str(expected_path)])
    return code, json.loads(out.getvalue())


@pytest.mark.parametrize("value, passed", [
    (None, True),
    (finding(file="other.py"), True),
    (finding(line="9"), True),
    (finding(severity="Nit"), True),
    (finding(severity="Nit", adjudication={"outcome": "unreachable"}), True),
    (finding(), False),
    (finding(dimension="resilience"), False),
    (finding(severity="Must fix", line="1-3"), False),
    (finding(adjudication={"outcome": "disputed"}), False),
    (finding(adjudication={"outcome": "survived"}), False),
])
def test_absent_passes_only_when_no_postable_finding_overlaps(value, passed):
    ok, match, considered = m.check({"findings": [value] if value else []}, ABSENT)
    assert ok is passed
    assert match is None
    assert bool(considered) is (not passed)


def test_absent_failure_lists_only_the_offending_findings(tmp_path):
    other = finding(file="other.py", title="Elsewhere")
    code, out = run_cli(tmp_path, {"findings": [other, finding()]}, ABSENT)
    assert code == 1
    assert [row["title"] for row in out["found"]] == ["Query in a loop"]


def test_absent_pass_prints_a_pass_result(tmp_path):
    code, out = run_cli(tmp_path, {"findings": [finding(severity="Nit")]}, ABSENT)
    assert code == 0
    assert out["pass"] is True


@pytest.mark.parametrize("rec_field", ["recommendation_md", "recommendation"])
@pytest.mark.parametrize("text, passed", [
    ("Use ceil_div(total, size) pages", True),
    ("Change < to <= in the loop", False),
])
def test_recommendation_marker_must_appear_in_the_matched_finding(rec_field, text, passed):
    expected = dict(EXPECTED, recommendation_contains="ceil_div")
    assert m.check({"findings": [finding(**{rec_field: text})]}, expected)[0] is passed


def test_marker_pass_requires_the_same_finding_that_matches_lens_file_and_lines():
    expected = dict(EXPECTED, recommendation_contains="ceil_div")
    wrong_place = finding(file="other.py", recommendation="ceil_div")
    right_place = finding(recommendation="no marker here")
    assert m.check({"findings": [wrong_place, right_place]}, expected)[0] is False
    assert m.check({"findings": [wrong_place, finding(recommendation="ceil_div")]}, expected)[0] is True


def test_production_is_required_only_when_adjudication_completed():
    complete = {"run": {"adjudication": {"status": "complete"}}}
    for run, status in (({}, "absent"), ({"run": {"adjudication": {"status": "failed"}}}, "failed"),
                        ({"run": {"adjudication": {"status": "disabled"}}}, "disabled")):
        assert m.check(dict(run, findings=[finding()]), EXPECTED)[0] is True, status
    assert m.check(dict(complete, findings=[finding()]), EXPECTED)[0] is False
    assert m.check(dict(complete, findings=[finding(production=PRODUCTION)]), EXPECTED)[0] is True


def test_production_skips_unproven_finding_and_takes_the_next_match():
    report = {"run": {"adjudication": {"status": "complete"}},
              "findings": [finding(title="bare"), finding(title="proven", production=PRODUCTION)]}
    ok, match, _ = m.check(report, EXPECTED)
    assert ok is True and match["title"] == "proven"


def test_absent_does_not_require_production_under_complete_adjudication():
    report = {"run": {"adjudication": {"status": "complete"}}, "findings": []}
    assert m.check(report, ABSENT)[0] is True


@pytest.mark.parametrize("extra", [
    {"absent": "yes"},
    {"absent": 1},
    {"absent": None},
    {"recommendation_contains": 3},
    {"recommendation_contains": ["ceil_div"]},
    {"recommendation_contains": None},
    {"recommendation_contains": ""},
    {"absent": None, "recommendation_contains": "ceil_div"},
])
def test_non_bool_absent_or_non_string_marker_is_bad_input(tmp_path, extra):
    code, out = run_cli(tmp_path, {"findings": [finding()]}, dict(EXPECTED, **extra))
    assert code == 2
    assert "error" in out


@pytest.mark.parametrize("extra", [
    {"recommendation_contains": None},
    {"recommendation_contains": ""},
    {"absent": None},
])
def test_check_rejects_present_but_null_or_empty_keys(extra):
    with pytest.raises(ValueError):
        m.check({"findings": [finding()]}, dict(EXPECTED, **extra))


def test_absent_false_behaves_like_an_ordinary_case():
    expected = dict(EXPECTED, absent=False)
    assert m.check({"findings": [finding()]}, expected)[0] is True
    assert m.check({"findings": []}, expected)[0] is False


def test_the_two_adjudicator_cases_are_present_and_well_formed():
    guarded = json.loads((SMOKE / "correctness-guarded" / "expected.json").read_text())
    wrong_fix = json.loads((SMOKE / "correctness-wrong-fix" / "expected.json").read_text())
    assert guarded["absent"] is True and guarded["lens"] == "correctness"
    assert isinstance(wrong_fix["recommendation_contains"], str) and wrong_fix["recommendation_contains"]
    assert "absent" not in wrong_fix


def patch_hunk_ranges(patch, file):
    """New-side (start, end) line ranges of every hunk the patch applies to `file`."""
    ranges, current = [], False
    for row in patch.splitlines():
        if row.startswith("+++ "):
            current = row == "+++ b/%s" % file
        elif current and (hunk := re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", row)):
            start, count = int(hunk[1]), int(hunk[2] if hunk[2] is not None else 1)
            ranges.append((start, start + max(count, 1) - 1))
    return ranges


@pytest.mark.parametrize("case", sorted(p.name for p in SMOKE.iterdir() if (p / "expected.json").is_file()))
def test_each_smoke_case_patch_applies_and_names_a_changed_file(tmp_path, case):
    source = SMOKE / case
    repo = tmp_path / "repo"
    shutil.copytree(source / "repo", repo)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "apply", "--check", str(source / "change.patch")], check=True)
    expected = json.loads((source / "expected.json").read_text())
    assert case == expected["lens"] or case.startswith(expected["lens"] + "-")
    assert "+++ b/%s" % expected["file"] in (source / "change.patch").read_text()
    ranges = patch_hunk_ranges((source / "change.patch").read_text(), expected["file"])
    assert any(start <= expected["line_max"] and expected["line_min"] <= end for start, end in ranges)
