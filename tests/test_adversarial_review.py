"""Behavior tests for skills/adversarial-review/scripts/adversarial-review.

`conftest.py`'s `run_script` resolves against `bin/` only, and no skill-local-script
harness survived the SDD rewrite, so this module defines its own.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "adversarial-review" / "scripts" / "adversarial-review"


def run_ar(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def resolve(*args: str, cwd: Path | None = None) -> dict:
    """Run `resolve` and parse its single JSON object; assert it succeeded."""
    proc = run_ar("resolve", *args, cwd=cwd)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# --- profile detection precedence -------------------------------------------------

@pytest.mark.parametrize(
    "target, expected_profile, expected_kind",
    [
        ("main..HEAD", "code-diff", "git-range"),
        ("origin/main..feature", "code-diff", "git-range"),
        ("", "code-diff", "worktree"),
        ("WORKTREE", "code-diff", "worktree"),
        ("docs/plans/2026-01-01-thing.md", "plan", "path"),
        ("notes/plan-for-x.md", "plan", "path"),
        ("docs/quirk/specs/x/logic.md", "spec-design", "path"),
        ("docs/quirk/specs/x/tech.md", "spec-design", "path"),
        ("docs/adr/0001-choice.md", "spec-design", "path"),
        ("notes/my-design.md", "spec-design", "path"),
        ("notes/api-spec.md", "spec-design", "path"),
        ("README.md", "prose-claim", "path"),
        ("src/auth.py", "code-diff", "path"),
    ],
)
def test_profile_detection_precedence(target, expected_profile, expected_kind, tmp_path):
    if expected_kind == "path":
        _touch(tmp_path / target)
    result = resolve("--target", target, "--repo-root", str(tmp_path))
    assert result["profile"] == expected_profile
    assert result["target_kind"] == expected_kind


def test_plan_precedence_beats_spec_design(tmp_path):
    """A file under docs/plans/ named like a spec is still a plan (rule 3 before rule 4)."""
    _touch(tmp_path / "docs/plans/my-design.md")
    result = resolve("--target", "docs/plans/my-design.md", "--repo-root", str(tmp_path))
    assert result["profile"] == "plan"


def _touch(path: Path, content: str = "placeholder\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_explicit_profile_overrides_detection(tmp_path):
    result = resolve(
        "--target", "main..HEAD", "--profile", "prose-claim", "--repo-root", str(tmp_path)
    )
    assert result["profile"] == "prose-claim"


def test_unknown_profile_is_an_error(tmp_path):
    _touch(tmp_path / "x.md")
    proc = run_ar("resolve", "--target", "x.md", "--profile", "nope", "--repo-root", str(tmp_path))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


# --- depth auto-selection ---------------------------------------------------------

@pytest.mark.parametrize(
    "changed_lines, expected_depth",
    [(10, "quick"), (50, "quick"), (51, "standard"), (150, "standard"), (151, "deep")],
)
def test_code_depth_thresholds(changed_lines, expected_depth, tmp_path):
    diff = _diff_with_added_lines(changed_lines)
    patch = tmp_path / "d.patch"
    patch.write_text(diff)
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == changed_lines
    assert result["depth_suggestion"] == expected_depth


@pytest.mark.parametrize("words, expected_depth", [(100, "quick"), (499, "quick"), (500, "standard")])
def test_prose_depth_thresholds(words, expected_depth, tmp_path):
    doc = tmp_path / "notes.md"
    doc.write_text(" ".join(["word"] * words) + "\n")
    result = resolve("--target", str(doc), "--repo-root", str(tmp_path))
    assert result["size_metric"] == words
    assert result["depth_suggestion"] == expected_depth


def test_contract_surface_forces_deep_regardless_of_size(tmp_path):
    """A tiny diff touching a contract surface still gets the deepest review."""
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n+`CONTRACT:` def f() -> int: ...\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["contract_surface"] is True
    assert result["depth_suggestion"] == "deep"


def test_schema_anchor_also_counts_as_contract_surface(tmp_path):
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n+# SCHEMA: {id: str}\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["contract_surface"] is True


def test_contract_anchor_on_removed_line_is_not_a_contract_surface(tmp_path):
    """The regex anchors on added lines only — deleting a contract is not changing one."""
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -1,2 +1 @@\n-# CONTRACT: def f() -> int\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["contract_surface"] is False


# --- artifact hash ----------------------------------------------------------------

def test_path_target_hashes_content_and_is_stable(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text("hello")
    first = resolve("--target", str(doc), "--repo-root", str(tmp_path))
    second = resolve("--target", str(doc), "--repo-root", str(tmp_path))
    assert first["artifact_hash"] == second["artifact_hash"]
    assert len(first["artifact_hash"]) == 64

    doc.write_text("goodbye")
    changed = resolve("--target", str(doc), "--repo-root", str(tmp_path))
    assert changed["artifact_hash"] != first["artifact_hash"]


def test_missing_path_target_is_an_error(tmp_path):
    proc = run_ar("resolve", "--target", str(tmp_path / "nope.md"), "--repo-root", str(tmp_path))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


# --- output conventions -----------------------------------------------------------

def test_stdout_is_exactly_one_sorted_json_object(tmp_path):
    proc = run_ar("resolve", "--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)  # raises if not exactly one object
    assert proc.stdout == json.dumps(payload, sort_keys=True) + "\n"
    assert proc.stderr == ""


def test_no_subcommand_is_a_usage_error():
    proc = run_ar()
    assert proc.returncode != 0


def _diff_with_added_lines(n: int) -> str:
    body = "".join(f"+line {i}\n" for i in range(n))
    return f"--- a/x.py\n+++ b/x.py\n@@ -0,0 +1,{n} @@\n{body}"
