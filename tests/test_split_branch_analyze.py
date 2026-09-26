from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.split_branch_fixtures import build_fixture


SCRIPT = Path(__file__).parents[1] / "skills/split-branch/scripts/analyze.sh"
PRE_CHANGE_COMMIT = "dd67b7f"


def run_analyze(repo: Path, *args: str, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args], cwd=repo, text=True, capture_output=True
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


def inventory(tmp_path: Path, kind: str) -> tuple[object, dict]:
    fixture = build_fixture(tmp_path, kind)
    result = run_analyze(fixture.path, "--hunks", "main")
    assert result.returncode == 0, result.stderr
    return fixture, json.loads(result.stdout)


def test_default_output_is_byte_identical_to_pre_change_script(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    old_script = tmp_path / "analyze-before-t3.sh"
    old_script.write_bytes(
        subprocess.run(
            ["git", "show", f"{PRE_CHANGE_COMMIT}:skills/split-branch/scripts/analyze.sh"],
            cwd=SCRIPT.parents[3], check=True, capture_output=True,
        ).stdout
    )
    old_script.chmod(0o755)

    old = run_analyze(fixture.path, "main", script=old_script)
    new = run_analyze(fixture.path, "main")
    assert old.returncode == new.returncode == 0
    assert new.stdout.encode() == old.stdout.encode()


def test_simple_inventory_has_exact_objects_in_git_diff_order(tmp_path: Path) -> None:
    fixture, result = inventory(tmp_path, "simple")
    expected_locations = [
        ("h1", "file-1.txt", 2), ("h2", "file-1.txt", 11),
        ("h3", "file-2.txt", 2), ("h4", "file-2.txt", 11),
        ("h5", "file-3.txt", 2), ("h6", "file-3.txt", 11),
    ]
    assert result["base"] == fixture.base
    assert result["head"] == fixture.head
    assert [(h["id"], h["file"], h["old_start"]) for h in result["hunks"]] == expected_locations
    for hunk in result["hunks"]:
        assert hunk == {
            "id": hunk["id"], "file": hunk["file"], "old_start": hunk["old_start"],
            "old_count": 1, "added": 1, "deleted": 1,
            "is_binary": False, "splittable": True, "kind": "source",
        }


def test_u0_keeps_closely_spaced_changes_separate(tmp_path: Path) -> None:
    _, result = inventory(tmp_path, "closely_spaced")
    assert [(h["id"], h["file"], h["old_start"]) for h in result["hunks"]] == [
        ("h1", "close.txt", 3), ("h2", "close.txt", 6)
    ]


def test_numeric_fields_for_deletions(tmp_path: Path) -> None:
    _, result = inventory(tmp_path, "deletion_only")
    assert result["hunks"] == [
        {"id": "h1", "file": "deleted.txt", "old_start": 1, "old_count": 1,
         "added": 0, "deleted": 1, "is_binary": False, "splittable": True, "kind": "source"},
        {"id": "h2", "file": "trim.txt", "old_start": 2, "old_count": 2,
         "added": 0, "deleted": 2, "is_binary": False, "splittable": False, "kind": "source"},
    ]


def test_dirty_staged_and_unstaged_changes_are_not_in_inventory(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    (fixture.path / "README.md").write_text("staged dirty\n")
    git(fixture.path, "add", "README.md")
    (fixture.path / "file-1.txt").write_text("unstaged dirty\n")

    result = run_analyze(fixture.path, "--hunks", "main")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["head"] == fixture.head == git(fixture.path, "rev-parse", "HEAD")
    assert [(h["file"], h["old_start"]) for h in payload["hunks"]] == [
        ("file-1.txt", 2), ("file-1.txt", 11),
        ("file-2.txt", 2), ("file-2.txt", 11),
        ("file-3.txt", 2), ("file-3.txt", 11),
    ]


def test_classification_exclusion_additions_and_unusual_paths(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    files = {
        "tests/new_test.py": "assert True\n",
        "package-lock.json": "generated\n",
        "café.txt": "unicode\n",
        "odd\tname.txt": "tab\n",
        'odd"quote.txt': "quote\n",
        "odd\\slash.txt": "backslash\n",
    }
    for name, body in files.items():
        path = fixture.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    git(fixture.path, "add", "-A")
    git(fixture.path, "commit", "-m", "add classified and unusual paths")

    result = run_analyze(fixture.path, "--hunks", "main")
    assert result.returncode == 0, result.stderr
    hunks = json.loads(result.stdout)["hunks"]
    by_file = {h["file"]: h for h in hunks}
    assert by_file["tests/new_test.py"]["kind"] == "test"
    assert "package-lock.json" not in by_file
    assert {"café.txt", "odd\tname.txt", 'odd"quote.txt', "odd\\slash.txt"} <= by_file.keys()
    for name in files:
        if name != "package-lock.json":
            assert by_file[name]["old_start"] == 0
            assert by_file[name]["old_count"] == 0
            assert by_file[name]["added"] == 1
            assert by_file[name]["deleted"] == 0


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
    assert [h["file"] for h in result["hunks"]] == ["new-script.sh"]


@pytest.mark.parametrize("mode", [(), ("--hunks",)])
def test_detached_head_exits_one(tmp_path: Path, mode: tuple[str, ...]) -> None:
    fixture = build_fixture(tmp_path, "simple")
    git(fixture.path, "checkout", "--detach")
    result = run_analyze(fixture.path, *mode, "main")
    assert result.returncode == 1
    assert "detached" in result.stderr.lower()


@pytest.mark.parametrize("mode", [(), ("--hunks",)])
def test_current_branch_equal_target_exits_one(tmp_path: Path, mode: tuple[str, ...]) -> None:
    fixture = build_fixture(tmp_path, "simple")
    result = run_analyze(fixture.path, *mode, "feature")
    assert result.returncode == 1
    assert "target branch" in result.stderr.lower()


def test_remote_option_and_push_default_select_remote_head(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    git(fixture.path, "update-ref", "refs/heads/trunk", fixture.base)
    git(fixture.path, "update-ref", "refs/remotes/upstream/trunk", fixture.base)
    git(fixture.path, "symbolic-ref", "refs/remotes/upstream/HEAD", "refs/remotes/upstream/trunk")
    explicit = run_analyze(fixture.path, "--remote", "upstream", "--hunks")
    assert explicit.returncode == 0, explicit.stderr
    assert json.loads(explicit.stdout)["base"] == fixture.base
    git(fixture.path, "config", "remote.pushDefault", "upstream")
    configured = run_analyze(fixture.path, "--hunks")
    assert configured.returncode == 0, configured.stderr
    assert json.loads(configured.stdout)["base"] == fixture.base


def test_unknown_flag_exits_five(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, "simple")
    result = run_analyze(fixture.path, "--unknown")
    assert result.returncode == 5
    assert "unknown" in result.stderr.lower()
