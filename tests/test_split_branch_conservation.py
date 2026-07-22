from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import pytest

from tests.split_branch_fixtures import FixtureRepo, build_fixture


ROOT = Path(__file__).resolve().parents[1]
ANALYZE = ROOT / "skills/split-branch/scripts/analyze.sh"
SLICE = ROOT / "skills/split-branch/scripts/slice.sh"
SEED = 8675309


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def inventory_ids(fixture: FixtureRepo) -> list[str]:
    result = subprocess.run(
        [str(ANALYZE), "--hunks", fixture.base],
        cwd=fixture.path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    hunks = json.loads(result.stdout)["hunks"]
    ids = [str(hunk["id"]) for hunk in hunks]
    assert all(ids)
    return ids


def partitions(ids: list[str]) -> list[tuple[str, list[list[str]]]]:
    assert ids
    shuffled = ids.copy()
    random.Random(SEED).shuffle(shuffled)
    if len(ids) == 1:
        random_two_way = [[], shuffled]
    else:
        # Make the two-hunk case structurally different from one-hunk-per-slice.
        if len(ids) == 2 and shuffled == ids:
            shuffled.reverse()
        cut = random.Random(SEED + 1).randint(1, len(ids) - 1)
        random_two_way = [shuffled[:cut], shuffled[cut:]]

    candidates = [
        ("all", [ids.copy()]),
        ("one-each", [[hunk_id] for hunk_id in ids]),
        (f"random-two-way-seed-{SEED}", random_two_way),
    ]
    # A one-unit fixture has only one non-empty set partition. Empty no-op
    # slices let us still exercise three distinct ordered stack shapes without
    # subdividing (or duplicating) that atomic inventory unit.
    if len(ids) == 1:
        candidates.append(("trailing-empty", [ids.copy(), []]))

    distinct = {tuple(tuple(group) for group in groups) for _, groups in candidates}
    assert len(distinct) >= 3
    for _, groups in candidates:
        assert sorted(item for group in groups for item in group) == sorted(ids)
    return candidates


def build_stack(
    fixture: FixtureRepo,
    groups: list[list[str]],
    *,
    prefix: str,
    failure_context: str,
) -> str:
    clean = git(fixture.path, "status", "--porcelain")
    assert clean == "", f"dirty before partition ({failure_context}): {clean}"
    parent = fixture.base
    for number, group in enumerate(groups, start=1):
        selection = fixture.path.parent / f"{prefix}-{number}.hunks"
        selection.write_text("".join(f"{hunk_id}\n" for hunk_id in group))
        branch = f"conservation-{prefix}-{number}"
        result = subprocess.run(
            [
                str(SLICE), "--base", fixture.base, "--head", fixture.head,
                "--branch", branch, "--hunks", str(selection),
                "--parent", parent,
            ],
            cwd=fixture.path,
            capture_output=True,
            text=True,
        )
        after_slice = git(fixture.path, "status", "--porcelain")
        assert after_slice == clean, (
            f"slice changed caller worktree ({failure_context}): {after_slice}"
        )
        assert result.returncode == 0, f"{failure_context}: {result.stderr}"
        parent = result.stdout.strip()
    assert git(fixture.path, "status", "--porcelain") == clean
    return parent


def assert_same_tree(fixture: FixtureRepo, commit: str, context: str) -> None:
    expected = git(fixture.path, "rev-parse", f"{fixture.head}^{{tree}}")
    actual = git(fixture.path, "rev-parse", f"{commit}^{{tree}}")
    assert actual == expected, f"tree mismatch ({context}): {actual} != {expected}"


@pytest.mark.parametrize(
    "kind",
    ["simple", "closely_spaced", "rename_mode", "no_newline_eof", "deletion_only"],
)
def test_every_text_partition_reconstructs_head_tree(tmp_path: Path, kind: str) -> None:
    fixture = build_fixture(tmp_path, kind)
    ids = inventory_ids(fixture)
    for partition_number, (name, groups) in enumerate(partitions(ids), start=1):
        context = f"kind={kind}, partition={name}, seed={SEED}"
        top = build_stack(
            fixture,
            groups,
            prefix=f"{kind}-{partition_number}",
            failure_context=context,
        )
        assert_same_tree(fixture, top, context)


@pytest.mark.parametrize("kind", ["binary", "split_floor"])
def test_atomic_units_reconstruct_head_without_subdivision(tmp_path: Path, kind: str) -> None:
    fixture = build_fixture(tmp_path, kind)
    ids = inventory_ids(fixture)
    for partition_number, (name, groups) in enumerate(partitions(ids), start=1):
        context = f"kind={kind}, partition={name}, seed={SEED}"
        top = build_stack(
            fixture,
            groups,
            prefix=f"{kind}-{partition_number}",
            failure_context=context,
        )
        assert_same_tree(fixture, top, context)


def test_merge_history_net_diff_reconstructs_head_tree(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "merge_commits")
    ids = inventory_ids(fixture)
    top = build_stack(
        fixture,
        [ids],
        prefix="merge-net",
        failure_context="kind=merge_commits, partition=all",
    )
    assert_same_tree(fixture, top, "kind=merge_commits, partition=all")


def test_omitting_a_hunk_fails_tree_comparison(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    ids = inventory_ids(fixture)
    assert len(ids) > 1
    top = build_stack(
        fixture,
        [ids[:-1]],
        prefix="corrupted-omission",
        failure_context="deliberately omitted final hunk",
    )
    with pytest.raises(AssertionError, match="tree mismatch"):
        assert_same_tree(fixture, top, "deliberately omitted final hunk")
    assert git(fixture.path, "status", "--porcelain") == ""
