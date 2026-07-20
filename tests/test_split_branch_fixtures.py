from __future__ import annotations

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


def test_merge_fixture_contains_merge_commit(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "merge_commits")

    assert git(fixture.path, "log", "--merges", "--format=%H", f"{fixture.base}..{fixture.head}").strip()


def test_unknown_fixture_kind_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown fixture kind"):
        build_fixture(tmp_path, "nope")
