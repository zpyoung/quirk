import pytest

import prepare_diff
from forge import hunk_lines

from .fakes import FakeGitHub, forge


def test_hunk_lines_read_header_like_content_inside_a_hunk_as_content():
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n one\n"
            "-- removed dashes\n+++ added pluses\n three\n"
            "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1,2 @@\n six\n+seven\n")
    new, old = hunk_lines(diff, "a.py")
    assert new == {1, 2, 3} and old == {1, 2, 3}
    assert hunk_lines(diff, "b.py") == ({1, 2}, {1})


@pytest.mark.parametrize("path", ["my file.py", "caf\u00e9.py"])
def test_hunk_lines_match_c_quoted_header_paths(path):
    diff = prepare_diff.reconstruct_diff_from_changes(
        [{"old_path": path, "new_path": path, "diff": "@@ -1,2 +1,3 @@\n a\n+b\n c\n"}])
    assert diff.splitlines()[0].count('"') == 4
    assert hunk_lines(diff, path) == ({1, 2, 3}, {1, 2})


def test_hunk_lines_count_only_newlines_as_line_breaks():
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n one\n"
            "+split\u2028here\x0cnow\x85\n two\n")
    new, old = hunk_lines(diff, "a.py")
    assert new == {1, 2, 3} and old == {1, 2}


def test_hunk_lines_anchor_old_side_lines_of_a_deleted_file():
    diff = "diff --git a/gone.py b/gone.py\ndeleted file mode 100644\n--- a/gone.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-x\n-y\n"
    assert hunk_lines(diff, "gone.py") == (set(), {1, 2})
    assert forge(FakeGitHub()).inline_target({}, "gone.py", "gone.py", 2, diff, side="old") == {
        "path": "gone.py", "line": 2, "side": "LEFT"}
