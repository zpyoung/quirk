from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.split_branch_fixtures import build_fixture

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_KINDS = [
    "simple",
    "closely_spaced",
    "binary",
    "split_floor",
    "rename_mode",
    "no_newline_eof",
    "deletion_only",
    "merge_commits",
    "squash_merged_base",
]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_build_fixture_creates_clean_repo_with_nonempty_diff(tmp_path: Path, kind: str) -> None:
    fixture = build_fixture(tmp_path, kind)

    assert git(fixture.path, "rev-parse", "--verify", fixture.base).strip() == fixture.base
    assert git(fixture.path, "rev-parse", "--verify", fixture.head).strip() == fixture.head
    assert git(fixture.path, "diff", fixture.base, fixture.head)
    assert git(fixture.path, "status", "--porcelain") == ""


def test_simple_fixture_has_three_files_with_two_separate_hunks_each(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    diff = git(fixture.path, "diff", "-U3", fixture.base, fixture.head)
    sections = diff.split("diff --git ")[1:]

    assert len(sections) == 3
    assert all(
        sum(line.startswith("@@") for line in section.splitlines()) == 2
        for section in sections
    )


def test_binary_fixture_contains_binary_change(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "binary")
    rows = git(fixture.path, "diff", "--numstat", fixture.base, fixture.head).splitlines()

    assert any(row.split("\t", 1)[0] == "-" for row in rows)


def test_split_floor_has_no_context_between_changes(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "split_floor")
    diff = git(fixture.path, "diff", "-U3", fixture.base, fixture.head)
    body = diff.split("@@", 2)[2].splitlines()
    changed_indexes = [i for i, line in enumerate(body) if line.startswith(("+", "-"))]

    assert changed_indexes
    assert not any(
        body[i].startswith(" ")
        for i in range(changed_indexes[0], changed_indexes[-1] + 1)
    )


def test_closely_spaced_hunks_collapse_with_context(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "closely_spaced")
    zero_context = git(fixture.path, "diff", "-U0", fixture.base, fixture.head)
    normal_context = git(fixture.path, "diff", "-U3", fixture.base, fixture.head)

    assert sum(line.startswith("@@") for line in zero_context.splitlines()) == 2
    assert sum(line.startswith("@@") for line in normal_context.splitlines()) == 1


def test_rename_mode_fixture_renames_and_makes_executable(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "rename_mode")
    diff = git(fixture.path, "diff", fixture.base, fixture.head)

    assert "rename from old-script.sh" in diff
    assert "rename to new-script.sh" in diff
    assert "old mode 100644" in diff
    assert "new mode 100755" in diff


def test_no_newline_fixture_has_unterminated_line_marker(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "no_newline_eof")
    diff = git(fixture.path, "diff", fixture.base, fixture.head)

    assert r"\ No newline at end of file" in diff


def test_deletion_only_fixture_has_subtractive_hunk_and_deleted_file(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "deletion_only")
    diff = git(fixture.path, "diff", fixture.base, fixture.head)
    hunks = diff.split("@@")[2::2]

    assert "deleted file mode" in diff
    assert any(
        any(line.startswith("-") for line in hunk.splitlines())
        and not any(line.startswith("+") for line in hunk.splitlines())
        for hunk in hunks
    )


def test_merge_fixture_contains_merge_commit(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "merge_commits")

    assert git(fixture.path, "log", "--merges", "--format=%H", f"{fixture.base}..{fixture.head}").strip()


def test_squash_merged_base_makes_naive_rebase_fail(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "squash_merged_base")
    worktree = tmp_path / "naive-rebase"
    git(fixture.path, "worktree", "add", "--detach", str(worktree), fixture.head)

    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    result = subprocess.run(
        ["git", "rebase", fixture.base],
        cwd=worktree,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0, result.stdout + result.stderr


def test_unknown_fixture_kind_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown fixture kind"):
        build_fixture(tmp_path, "nope")
