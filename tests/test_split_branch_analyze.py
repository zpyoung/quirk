from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.split_branch_fixtures import build_fixture


SCRIPT = Path(__file__).parents[1] / "skills/split-branch/scripts/analyze.sh"
DEFAULT_KEYS = {
    "current_branch",
    "target_branch",
    "total_files",
    "total_lines_added",
    "total_lines_deleted",
    "total_lines",
    "total_source_lines",
    "total_test_lines",
    "total_excluded_lines",
    "weighted_review_lines",
    "target_lines_per_split",
    "directory_groups",
    "files",
    "warnings",
    "binary_files",
    "excluded_files",
}


def run_analyze(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args], cwd=repo, text=True, capture_output=True
    )


def inventory(tmp_path: Path, kind: str) -> tuple[object, dict]:
    fixture = build_fixture(tmp_path, kind)
    result = run_analyze(fixture.path, "--hunks", "main")
    assert result.returncode == 0, result.stderr
    return fixture, json.loads(result.stdout)


def test_default_output_contract_is_unchanged(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    result = run_analyze(fixture.path, "main")
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == DEFAULT_KEYS


def test_simple_hunk_inventory_has_ordered_ids_and_splittable_hunks(tmp_path: Path) -> None:
    fixture, result = inventory(tmp_path, "simple")
    hunks = result["hunks"]

    assert result["base"] == fixture.base
    assert result["head"] == fixture.head
    assert [hunk["id"] for hunk in hunks] == [
        f"h{number}" for number in range(1, len(hunks) + 1)
    ]
    assert hunks
    assert all(hunk["splittable"] is True for hunk in hunks)
    assert all(hunk["kind"] == "source" for hunk in hunks)


def test_split_floor_contains_an_unsplittable_hunk(tmp_path: Path) -> None:
    _, result = inventory(tmp_path, "split_floor")
    assert any(hunk["splittable"] is False for hunk in result["hunks"])


def test_binary_is_one_unsliceable_hunk(tmp_path: Path) -> None:
    _, result = inventory(tmp_path, "binary")
    binary_hunks = [h for h in result["hunks"] if h["file"] == "data.bin"]
    assert len(binary_hunks) == 1
    assert binary_hunks[0]["is_binary"] is True
    assert binary_hunks[0]["splittable"] is False
    assert result["unsliceable_files"] == ["data.bin"]


def test_rename_uses_new_path(tmp_path: Path) -> None:
    _, result = inventory(tmp_path, "rename_mode")
    assert "new-script.sh" in [hunk["file"] for hunk in result["hunks"]]
    assert "old-script.sh" not in [hunk["file"] for hunk in result["hunks"]]


def test_unknown_flag_exits_five(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    result = run_analyze(fixture.path, "--unknown")
    assert result.returncode == 5
    assert "unknown" in result.stderr.lower()
