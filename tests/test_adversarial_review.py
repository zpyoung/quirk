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


# ============================ prepass =============================================

def prepass(*args: str, cwd: Path | None = None, expect: int = 0) -> dict:
    proc = run_ar("prepass", *args, cwd=cwd)
    assert proc.returncode == expect, f"exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def _findings_by_name(result: dict) -> dict:
    return {f["evidence"][0]["ref"]: f for f in result["findings"]}


# --- prose: reference resolution --------------------------------------------------

def test_unresolvable_path_reference_becomes_a_high_prepass_finding(tmp_path):
    doc = _touch(tmp_path / "notes.md", "See `src/does_not_exist.py` for details.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert result["status"] == "fail"
    refs = [f["evidence"][0]["ref"] for f in result["findings"]]
    assert "src/does_not_exist.py" in refs
    finding = next(f for f in result["findings"] if f["evidence"][0]["ref"] == "src/does_not_exist.py")
    assert finding["severity"] == "HIGH"
    assert finding["confidence"] == "HIGH"
    assert finding["stage"] == "prepass"
    assert finding["evidence"][0]["kind"] == "prepass"


def test_resolvable_path_reference_produces_no_finding(tmp_path):
    _touch(tmp_path / "src/real.py", "x = 1\n")
    doc = _touch(tmp_path / "notes.md", "See `src/real.py` for details.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["status"] == "pass"
    assert result["findings"] == []


def test_unresolvable_markdown_link_becomes_a_finding(tmp_path):
    doc = _touch(tmp_path / "notes.md", "See [the design](./design.md).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    refs = [f["evidence"][0]["ref"] for f in result["findings"]]
    assert "./design.md" in refs


def test_http_links_are_recorded_skipped_and_never_fetched(tmp_path):
    doc = _touch(tmp_path / "notes.md", "See [spec](https://example.invalid/nope).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["status"] == "pass"
    assert result["findings"] == []
    ref_check = next(c for c in result["checks"] if c["name"] == "reference-resolution")
    assert "skipped" in ref_check["output"]


def test_unresolvable_command_reference_becomes_a_finding(tmp_path):
    doc = _touch(tmp_path / "notes.md", "Run `definitely-not-a-real-binary-xyz --help`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    refs = [f["evidence"][0]["ref"] for f in result["findings"]]
    assert any("definitely-not-a-real-binary-xyz" in r for r in refs)


# --- prose: section coverage ------------------------------------------------------

def test_missing_required_heading_is_reported(tmp_path):
    doc = _touch(tmp_path / "logic.md", "# Purpose\n\nsome text\n")
    result = prepass("--profile", "spec-design", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    coverage = next(c for c in result["checks"] if c["name"] == "section-coverage")
    assert coverage["status"] == "fail"
    assert "Decisions Locked" in coverage["output"]


def test_all_required_headings_present_passes_coverage(tmp_path):
    doc = _touch(
        tmp_path / "logic.md",
        "# Purpose\n\n## Scope\n\n## Decisions Locked\n\ntext\n",
    )
    result = prepass("--profile", "spec-design", "--target", str(doc), "--repo-root", str(tmp_path))
    coverage = next(c for c in result["checks"] if c["name"] == "section-coverage")
    assert coverage["status"] == "pass"


def test_prose_claim_profile_reports_coverage_not_applicable(tmp_path):
    doc = _touch(tmp_path / "notes.md", "a claim\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    coverage = next(c for c in result["checks"] if c["name"] == "section-coverage")
    assert coverage["status"] == "not-applicable"


# --- could-not-run vs fail --------------------------------------------------------

def test_unreadable_prose_target_is_could_not_run_not_fail(tmp_path):
    """T4's NOT_REVIEWABLE branch depends on this distinction."""
    result = prepass("--profile", "prose-claim", "--target", str(tmp_path / "absent.md"),
                     "--repo-root", str(tmp_path), expect=1)
    assert result["status"] == "could-not-run"


def test_code_profile_with_no_discoverable_command_is_could_not_run(tmp_path):
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), expect=1)
    assert result["status"] == "could-not-run"
    assert result["checks"] == []


def test_failing_check_is_fail_not_could_not_run(tmp_path):
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), "--check-cmd", "exit 3", expect=1)
    assert result["status"] == "fail"
    assert result["checks"][0]["exit_code"] == 3


def test_passing_check_exits_zero(tmp_path):
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), "--check-cmd", "true")
    assert result["status"] == "pass"
    assert result["checks"][0]["status"] == "pass"


def test_check_cmd_overrides_discovery(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), "--check-cmd", "true")
    assert [c["command"] for c in result["checks"]] == ["true"]


def test_code_discovery_finds_pytest_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), "--check-cmd", "true")
    assert result["status"] == "pass"


# --- prepass finding calibration ---------------------------------------------------
# A spec or plan names artifacts that do not exist yet; asserting HIGH confidence on
# that is undecidable and is what earns a check its ignore rate.

def test_spec_design_unresolved_path_is_medium_low_and_names_the_ambiguity(tmp_path):
    doc = _touch(tmp_path / "tech.md", "Create `skills/new-thing/SKILL.md` in this work.\n")
    result = prepass("--profile", "spec-design", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    finding = result["findings"][0]
    assert finding["severity"] == "MEDIUM"
    assert finding["confidence"] == "LOW"
    assert "plans to create" in finding["claim"]


def test_plan_profile_uses_the_same_forward_looking_calibration(tmp_path):
    doc = _touch(tmp_path / "docs/plans/p.md", "Create `src/new.py`.\n")
    result = prepass("--profile", "plan", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    finding = result["findings"][0]
    assert (finding["severity"], finding["confidence"]) == ("MEDIUM", "LOW")


def test_prose_claim_unresolved_path_stays_high_high(tmp_path):
    """A README describes current state, so an unresolved path really is a defect."""
    doc = _touch(tmp_path / "notes.md", "See `src/gone.py`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    finding = result["findings"][0]
    assert (finding["severity"], finding["confidence"]) == ("HIGH", "HIGH")


def test_command_not_on_path_is_never_asserted_confidently(tmp_path):
    """Command-vs-prose is undecidable in every profile."""
    doc = _touch(tmp_path / "notes.md", "Run `definitely-not-real-xyz --help`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    finding = next(f for f in result["findings"] if "definitely-not-real-xyz" in f["claim"])
    assert (finding["severity"], finding["confidence"]) == ("MEDIUM", "LOW")
    assert "may instead be prose" in finding["claim"]


# --- noise regressions found by dogfooding -----------------------------------------

@pytest.mark.parametrize("token", [
    "scripts/sdd-*",           # glob
    "<path>",                  # placeholder
    "#!/usr/bin/env python3",  # shebang
    "/quirk:adversarial-review",
    "resolve --> depth_suggestion",
    "only critique",           # prose, not a command
])
def test_non_reference_tokens_produce_no_finding(token, tmp_path):
    doc = _touch(tmp_path / "notes.md", f"Text with `{token}` inline.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["findings"] == [], f"{token!r} should not be treated as a reference"


def test_line_anchor_is_stripped_before_resolving(tmp_path):
    _touch(tmp_path / "tests/conftest.py", "x = 1\n")
    doc = _touch(tmp_path / "notes.md", "See `tests/conftest.py:35-42`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["findings"] == []


def test_relative_reference_resolves_against_the_document_directory(tmp_path):
    """`logic.md` in a spec means its sibling, not a repo-root path."""
    _touch(tmp_path / "docs/spec/logic.md", "# Purpose\n")
    doc = _touch(tmp_path / "docs/spec/tech.md", "See `logic.md` for rationale.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["findings"] == []


# ============================ select-model ========================================

def select_model(*args: str, expect: int = 0) -> dict:
    proc = run_ar("select-model", *args)
    assert proc.returncode == expect, f"exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def test_author_family_is_excluded_from_selection():
    """Independence is structural: never review Claude output with Claude."""
    result = select_model("--author-family", "anthropic", "--check-cmd", "true")
    assert result["resolved"] is True
    assert result["family"] != "anthropic"
    assert result["independence"] == "full"


def test_openai_authored_work_is_reviewed_by_another_family():
    result = select_model("--author-family", "openai", "--check-cmd", "true")
    assert result["family"] != "openai"
    assert result["independence"] == "full"


def test_ladder_is_walked_until_a_rung_resolves():
    """First rung fails preflight, a later one succeeds."""
    script = 'test "$1" != "codex"'  # codex fails, everything else resolves
    result = select_model("--author-family", "anthropic", "--check-cmd", f"sh -c '{script}' _")
    assert result["resolved"] is True
    attempted = [rung["alias"] for rung in result["ladder"] if rung["checked"]]
    assert len(attempted) >= 1


def test_no_rung_resolves_yields_resolved_false_and_exit_1():
    """Drives the gate's first NOT_REVIEWABLE branch."""
    result = select_model("--author-family", "anthropic", "--check-cmd", "false", expect=1)
    assert result["resolved"] is False
    assert result["alias"] is None
    assert result["family"] is None
    assert all(rung["resolved"] is False for rung in result["ladder"])


def test_fallback_onto_the_author_family_is_flagged_reduced():
    """A PASS from a same-family reviewer must not read as strong as a cross-family one."""
    only_sonnet = 'test "$1" = "sonnet"'
    result = select_model("--author-family", "anthropic", "--check-cmd", f"sh -c '{only_sonnet}' _")
    assert result["resolved"] is True
    assert result["family"] == "anthropic"
    assert result["independence"] == "reduced"


def test_explicit_model_overrides_family_exclusion():
    result = select_model("--author-family", "anthropic", "--model", "sonnet", "--check-cmd", "true")
    assert result["alias"] == "sonnet"
    assert result["independence"] == "reduced"


def test_explicit_model_that_fails_preflight_does_not_silently_fall_back():
    """An explicit --model is a caller instruction, not a suggestion."""
    result = select_model(
        "--author-family", "openai", "--model", "sonnet", "--check-cmd", "false", expect=1
    )
    assert result["resolved"] is False


def test_unknown_alias_is_a_usage_error():
    proc = run_ar("select-model", "--author-family", "openai", "--model", "not-an-alias")
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


def test_resolved_selection_carries_a_dispatchable_triple():
    result = select_model("--author-family", "anthropic", "--check-cmd", "true")
    for field in ("provider", "model", "thinking"):
        assert result[field], f"{field} must be populated for dispatch"
