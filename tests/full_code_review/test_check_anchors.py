import contextlib
import io
import json

import pytest

import render_report
from check_anchors import check_anchors, line_count


def _source(tmp_path):
    root = tmp_path / "src"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "service.py").write_text("".join("line %d\n" % n for n in range(1, 41)))
    (root / "pkg" / "tail.py").write_text("a\nb\nc")
    return root


def _finding(file, line, **extra):
    value = {"file": file, "line": line}
    value.update(extra)
    return value


def test_line_count_counts_an_unterminated_last_line(tmp_path):
    root = _source(tmp_path)
    assert line_count(str(root / "pkg" / "service.py")) == 40
    assert line_count(str(root / "pkg" / "tail.py")) == 3
    (root / "empty.py").write_text("")
    assert line_count(str(root / "empty.py")) == 0


def test_in_range_single_lines_and_ranges_pass(tmp_path):
    root = _source(tmp_path)
    findings = [_finding("pkg/service.py", "1"), _finding("pkg/service.py", "12-40"),
                _finding("pkg/tail.py", "3")]
    assert check_anchors(findings, str(root)) == ([], [])


def test_a_line_past_the_end_of_the_file_is_a_problem(tmp_path):
    problems, _ = check_anchors([_finding("pkg/service.py", "41")], str(_source(tmp_path)))
    assert problems == ["pkg/service.py:41 (file has 40 lines)"]


def test_a_range_straddling_the_end_of_the_file_is_a_problem(tmp_path):
    problems, _ = check_anchors([_finding("pkg/service.py", "35-48")], str(_source(tmp_path)))
    assert problems == ["pkg/service.py:35-48 (file has 40 lines)"]


def test_a_reversed_range_is_a_problem(tmp_path):
    problems, _ = check_anchors([_finding("pkg/service.py", "9-3")], str(_source(tmp_path)))
    assert problems == ["pkg/service.py:9-3 (range ends before it starts)"]


def test_a_deleted_file_is_skipped_with_a_note(tmp_path):
    problems, notes = check_anchors([_finding("pkg/removed.py", "300")], str(_source(tmp_path)))
    assert problems == []
    assert notes == ["pkg/removed.py is not in the review source; treating it as a deleted file "
                     "and skipping its line check."]


def test_an_old_side_anchor_is_not_checked_against_the_new_file(tmp_path):
    findings = [_finding("pkg/service.py", "90", anchor_side="old")]
    assert check_anchors(findings, str(_source(tmp_path))) == ([], [])


def test_a_path_escaping_the_source_is_a_problem(tmp_path):
    (tmp_path / "outside.py").write_text("x\n")
    problems, _ = check_anchors([_finding("../outside.py", "1")], str(_source(tmp_path)))
    assert problems == ["../outside.py:1 (path is outside the review source)"]


def test_a_missing_source_root_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        check_anchors([], str(tmp_path / "nowhere"))


def _render(tmp_path, findings, source_root):
    report = {"meta": {"target": "local", "title": "Demo", "verdict": "Fix, then merge"},
              "run": {"clean_notes": []}, "findings": findings}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = render_report.main(["--in", str(path), "--out-dir", str(tmp_path / "out"), "--no-open",
                                 "--format", "md", "--source-root", str(source_root)])
    return rc, json.loads(stdout.getvalue())


def test_render_fails_on_an_out_of_range_anchor_and_names_it(tmp_path):
    root = _source(tmp_path)
    findings = [{"severity": "Should fix", "dimension": "correctness", "file": "pkg/service.py",
                 "line": "38-52", "issue": "Off by one."}]
    rc, payload = _render(tmp_path, findings, root)
    assert rc == 2
    assert "new-file line numbers at head" in payload["error"]
    assert "pkg/service.py:38-52 (file has 40 lines)" in payload["error"]
    assert not (tmp_path / "out").exists()


def test_render_passes_in_range_anchors_and_reports_skipped_deleted_files(tmp_path):
    root = _source(tmp_path)
    findings = [{"severity": "Should fix", "dimension": "correctness", "file": "pkg/service.py",
                 "line": "38-40", "issue": "Off by one."},
                {"severity": "Nit", "dimension": "comments", "file": "pkg/removed.py",
                 "line": "7", "issue": "Stale note."}]
    rc, payload = _render(tmp_path, findings, root)
    assert rc == 0
    assert any("pkg/removed.py is not in the review source" in w for w in payload["warnings"])
