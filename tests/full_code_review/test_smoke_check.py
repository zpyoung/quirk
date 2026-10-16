import contextlib
import io
import json
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


@pytest.mark.parametrize("case", sorted(p.name for p in SMOKE.iterdir() if (p / "expected.json").is_file()))
def test_each_smoke_case_patch_applies_and_names_a_changed_file(tmp_path, case):
    source = SMOKE / case
    repo = tmp_path / "repo"
    shutil.copytree(source / "repo", repo)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "apply", "--check", str(source / "change.patch")], check=True)
    expected = json.loads((source / "expected.json").read_text())
    assert expected["lens"] == case
    assert "+++ b/%s" % expected["file"] in (source / "change.patch").read_text()
