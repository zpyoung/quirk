from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.split_branch_fixtures import FixtureRepo, build_fixture


ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "skills/split-branch/scripts/slice.sh"
ANALYZE = ROOT / "skills/split-branch/scripts/analyze.sh"


def git(repo: Path, *args: str, text: bool = True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=text
    ).stdout.strip() if text else subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True
    ).stdout


def hunk_ids(fixture: FixtureRepo) -> list[str]:
    # T4 must not depend on T3 landing first. Prefer analyze.sh --hunks when it
    # exists; otherwise derive the materializer's stable global IDs from -U0.
    result = subprocess.run(
        [str(ANALYZE), "--hunks", "--base", fixture.base, "--head", fixture.head],
        cwd=fixture.path, capture_output=True, text=True,
    )
    if result.returncode == 0:
        try:
            value = json.loads(result.stdout)
            records = value.get("hunks", value) if isinstance(value, dict) else value
            ids = [str(record["id"]) for record in records]
            if ids:
                return ids
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    diff = git(fixture.path, "diff", "-U0", "--binary", fixture.base, fixture.head)
    count = len(re.findall(r"^@@ ", diff, re.MULTILINE))
    # Binary and metadata-only file sections have one all-or-nothing identity.
    sections = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    count += sum(
        1 for section in sections
        if section.startswith("diff --git ")
        and "@@ " not in section
        and ("GIT binary patch" in section or re.search(
            r"^(?:old mode|new mode|rename from|rename to|new file mode|deleted file mode) ",
            section, re.MULTILINE,
        ))
    )
    return [f"hunk-{number:04d}" for number in range(1, count + 1)]


def run_slice(fixture: FixtureRepo, branch: str, ids: list[str], *, parent: str | None = None):
    selected = fixture.path.parent / f"{branch.replace('/', '-')}.hunks"
    selected.write_text("".join(f"{item}\n" for item in ids))
    args = [
        str(SLICE), "--base", fixture.base, "--head", fixture.head,
        "--branch", branch, "--hunks", str(selected),
    ]
    if parent:
        args.extend(["--parent", parent])
    return subprocess.run(args, cwd=fixture.path, capture_output=True, text=True)


def test_one_hunk_and_all_hunks_are_exact_and_leave_status_untouched(tmp_path: Path):
    fixture = build_fixture(tmp_path, "simple")
    ids = hunk_ids(fixture)
    before = git(fixture.path, "status", "--porcelain")

    one = run_slice(fixture, "slice-one", ids[:1])
    assert one.returncode == 0, one.stderr
    assert git(fixture.path, "status", "--porcelain") == before
    changed = git(fixture.path, "diff", "--name-only", fixture.base, "slice-one").splitlines()
    assert changed == ["file-1.txt"]
    content = git(fixture.path, "show", "slice-one:file-1.txt")
    assert "changed 2" in content
    assert "line 11" in content

    all_result = run_slice(fixture, "slice-all", ids)
    assert all_result.returncode == 0, all_result.stderr
    assert git(fixture.path, "rev-parse", "slice-all^{tree}") == git(
        fixture.path, "rev-parse", f"{fixture.head}^{{tree}}"
    )
    assert git(fixture.path, "status", "--porcelain") == before


@pytest.mark.parametrize("kind", ["rename_mode", "no_newline_eof", "deletion_only", "binary"])
def test_special_diff_forms(tmp_path: Path, kind: str):
    fixture = build_fixture(tmp_path, kind)
    result = run_slice(fixture, f"slice-{kind}", hunk_ids(fixture))
    assert result.returncode == 0, result.stderr
    assert git(fixture.path, "rev-parse", f"slice-{kind}^{{tree}}") == git(
        fixture.path, "rev-parse", f"{fixture.head}^{{tree}}"
    )
    if kind == "rename_mode":
        assert git(fixture.path, "ls-tree", "slice-rename_mode", "new-script.sh").startswith("100755 ")
    elif kind == "no_newline_eof":
        assert not git(fixture.path, "show", "slice-no_newline_eof:unterminated.txt", text=False).endswith(b"\n")
    elif kind == "deletion_only":
        assert "deleted.txt" not in git(fixture.path, "ls-tree", "--name-only", "slice-deletion_only")
    else:
        assert git(fixture.path, "show", "slice-binary:data.bin", text=False) == git(
            fixture.path, "show", f"{fixture.head}:data.bin", text=False
        )


def test_close_hunks_reconcile_context_and_stack(tmp_path: Path):
    fixture = build_fixture(tmp_path, "closely_spaced")
    first_id, second_id = hunk_ids(fixture)
    assert run_slice(fixture, "close-first", [first_id]).returncode == 0
    first = git(fixture.path, "show", "close-first:close.txt")
    assert "changed 3" in first
    assert "line 6" in first
    assert "changed 6" not in first

    second = run_slice(fixture, "close-second", [second_id], parent="close-first")
    assert second.returncode == 0, second.stderr
    assert git(fixture.path, "rev-parse", "close-second^{tree}") == git(
        fixture.path, "rev-parse", f"{fixture.head}^{{tree}}"
    )


def test_documented_errors_and_at_commit(tmp_path: Path):
    fixture = build_fixture(tmp_path, "simple")
    missing = run_slice(fixture, "missing", ["hunk-9999"])
    assert missing.returncode == 2

    ids = hunk_ids(fixture)
    assert run_slice(fixture, "duplicate", ids[:1]).returncode == 0
    assert run_slice(fixture, "duplicate", ids[:1]).returncode == 4

    replay = subprocess.run(
        [str(SLICE), "--at-commit", fixture.head, "--parent", fixture.base,
         "--branch", "commit-replay"],
        cwd=fixture.path, capture_output=True, text=True,
    )
    assert replay.returncode == 0, replay.stderr
    assert git(fixture.path, "rev-parse", "commit-replay^{tree}") == git(
        fixture.path, "rev-parse", f"{fixture.head}^{{tree}}"
    )
