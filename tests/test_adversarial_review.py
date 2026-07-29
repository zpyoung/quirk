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
    extra: tuple[str, ...] = ()
    if expected_kind == "path":
        _touch(tmp_path / target)
    else:
        extra = ("--diff-file", str(_touch(tmp_path / "empty.patch", "")))
    result = resolve("--target", target, "--repo-root", str(tmp_path), *extra)
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


def _git_repo(path: Path) -> Path:
    """A real repo, so `git diff` succeeds instead of erroring on a non-repo."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    return path


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)


def test_explicit_profile_overrides_detection(tmp_path):
    patch = _touch(tmp_path / "empty.patch", "")
    result = resolve(
        "--target", "main..HEAD", "--profile", "prose-claim",
        "--repo-root", str(tmp_path), "--diff-file", str(patch),
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


def test_code_path_target_is_measured_in_lines_not_words(tmp_path):
    """The unit belongs to the profile: `code-diff` thresholds are lines everywhere.

    160 lines of 4 words reads as `deep` by line count and `standard` by word count.
    """
    src = tmp_path / "auth.py"
    src.write_text("".join("a b c d\n" for _ in range(160)))
    result = resolve("--target", str(src), "--repo-root", str(tmp_path))
    assert result["profile"] == "code-diff"
    assert result["size_metric"] == 160
    assert result["depth_suggestion"] == "deep"


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


def test_a_replacement_hunk_of_dash_and_plus_prefixed_text_is_counted(tmp_path):
    """`--- old` / `+++ new` inside a hunk is content, not a file-header pair.

    No prefix rule can decide this. The hunk header declares how many lines follow,
    and that is the only unambiguous answer.
    """
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.md\n+++ b/x.md\n@@ -1 +1 @@\n--- old bullet\n+++ new bullet\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == 2


def test_context_lines_are_not_counted_as_changes(tmp_path):
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,3 @@\n context\n-removed\n+added\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == 2


def test_no_newline_marker_is_not_counted(tmp_path):
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n\\ No newline at end of file\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == 2


def test_multi_file_diff_counts_every_hunk(tmp_path):
    patch = tmp_path / "d.patch"
    patch.write_text(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+one\n"
        "diff --git a/y.py b/y.py\n--- a/y.py\n+++ b/y.py\n@@ -0,0 +1,2 @@\n+two\n+three\n"
    )
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == 3


def test_added_lines_whose_text_begins_with_plus_or_minus_are_counted(tmp_path):
    """`git diff` renders an added line containing `++i` as `+++i` — that is content.

    Only a `+++`/`---` pair outside a hunk names a file.
    """
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -0,0 +1,3 @@\n+normal\n+++counter\n+--dashes\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["size_metric"] == 3


def test_a_contract_anchor_on_an_added_line_beginning_with_plus_still_counts(tmp_path):
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+++ CONTRACT: def f() -> int\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["contract_surface"] is True


def test_contract_anchor_in_diff_metadata_is_not_a_contract_surface(tmp_path):
    """`+++` names a file; a filename containing `SCHEMA:` is not a changed contract.

    The size metric already skips these headers, so the two must agree on what counts
    as an added line.
    """
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/SCHEMA:weird.py\n+++ b/SCHEMA:weird.py\n@@ -1 +1,2 @@\n+x = 1\n")
    result = resolve(
        "--target", "main..HEAD", "--repo-root", str(tmp_path), "--diff-file", str(patch)
    )
    assert result["contract_surface"] is False
    assert result["depth_suggestion"] == "quick"


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


# --- unreadable targets -----------------------------------------------------------
#
# The worst failure mode a review tool has is reviewing nothing and saying so
# calmly. A target we cannot read is an error, never an empty artifact.

def test_unknown_git_range_is_an_error_not_an_empty_review(tmp_path):
    _git_repo(tmp_path)
    proc = run_ar("resolve", "--target", "no-such-ref-xyz..also-fake", "--repo-root", str(tmp_path))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr
    assert proc.stdout == ""


def test_non_repo_root_is_an_error(tmp_path):
    proc = run_ar("resolve", "--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


def test_valid_range_with_no_changes_is_still_a_clean_zero(tmp_path):
    """The legitimate empty case must stay distinguishable from the broken one."""
    _git_repo(tmp_path)
    result = resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert result["size_metric"] == 0
    assert result["depth_suggestion"] == "quick"


def test_worktree_includes_staged_changes(tmp_path):
    """WORKTREE promises the uncommitted work — `git diff` alone hides the index."""
    _git_repo(tmp_path)
    src = tmp_path / "a.py"
    src.write_text("original\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    src.write_text("original\nstaged change\n")
    _git(tmp_path, "add", "a.py")
    result = resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert result["size_metric"] == 1, "staged change was omitted from the artifact"


def test_worktree_still_works_before_the_first_commit(tmp_path):
    """An unborn branch has no HEAD to diff against; that is not a failure."""
    _git_repo(tmp_path)
    assert resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))["size_metric"] == 0


def test_worktree_includes_untracked_files(tmp_path):
    """A brand-new module is uncommitted work; leaving it out reviews a hole."""
    _git_repo(tmp_path)
    (tmp_path / "seed.txt").write_text("x\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (tmp_path / "brand_new.py").write_text("def f():\n    return 1\n")
    result = resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert result["size_metric"] == 2, "untracked file was omitted from the artifact"


def test_staged_new_file_is_visible_before_the_first_commit(tmp_path):
    """The gap between `git diff` (blind to it) and the untracked scan (skips staged).

    With no HEAD the empty tree is the baseline, so nothing falls between the two.
    """
    _git_repo(tmp_path)
    (tmp_path / "new.py").write_text("def f():\n    return 1\n")
    _git(tmp_path, "add", "new.py")
    assert resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))["size_metric"] == 2


def test_headings_inside_a_code_fence_do_not_satisfy_required_sections(tmp_path):
    """Showing `## Purpose` in a sample block is not declaring the section.

    Raised in the very first review pass and left unfixed until the eighth.
    """
    doc = _touch(tmp_path / "logic.md",
                 "# Title\n\n```markdown\n## Purpose\n## Scope\n## Decisions Locked\n```\n\n"
                 "Body text with no references.\n")
    result = prepass("--profile", "spec-design", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert result["status"] == "fail"
    section = next(c for c in result["checks"] if c["name"] == "section-coverage")
    assert section["status"] == "fail"


def test_real_headings_outside_a_fence_still_satisfy_required_sections(tmp_path):
    doc = _touch(tmp_path / "logic.md",
                 "# Title\n\n## Purpose\nwhy\n\n## Scope\nwhat\n\n## Decisions Locked\nchoices\n\n"
                 "```python\n# not a heading\n```\n")
    assert prepass("--profile", "spec-design", "--target", str(doc),
                   "--repo-root", str(tmp_path))["status"] == "pass"


def test_untracked_files_with_non_ascii_names_are_included(tmp_path):
    """git C-quotes them; the quoted string is not a path any command can open."""
    _git_repo(tmp_path)
    (tmp_path / "seed.txt").write_text("x\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (tmp_path / "café.py").write_text("def f():\n    return 1\n")
    result = resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))
    assert result["size_metric"] == 2, "C-quoted filename dropped from the artifact"


def test_a_backticked_token_does_not_suppress_the_same_named_link(tmp_path):
    """Two different claims about the same text; only the link is unambiguous."""
    doc = _touch(tmp_path / "notes.md",
                 "Mentioned as `missing.pdf` first, then [linked](missing.pdf).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert "missing.pdf" in [f["evidence"][0]["ref"] for f in result["findings"]]


def test_a_colored_git_config_does_not_blank_the_diff(tmp_path):
    """color.ui=always puts ANSI escapes in hunk headers; the parser saw no hunks.

    A deep contract-changing range silently became zero lines and `quick`.
    """
    _git_repo(tmp_path)
    _git(tmp_path, "config", "color.ui", "always")
    (tmp_path / "x.py").write_text("a\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (tmp_path / "x.py").write_text("a\nb\nc\n")
    assert resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))["size_metric"] == 2


def test_path_artifact_hash_distinguishes_undecodable_bytes(tmp_path):
    """`errors="replace"` maps distinct bytes onto one string — and one identity."""
    first, second = tmp_path / "a.md", tmp_path / "b.md"
    first.write_bytes(b"head \xff\xfe tail")
    second.write_bytes(b"head \xfe\xff tail")
    left = resolve("--target", str(first), "--repo-root", str(tmp_path))
    right = resolve("--target", str(second), "--repo-root", str(tmp_path))
    assert left["artifact_hash"] != right["artifact_hash"]


def test_worktree_respects_gitignore(tmp_path):
    """`--exclude-standard`: ignored files are not uncommitted work under review."""
    _git_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("junk/\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (tmp_path / "junk").mkdir()
    (tmp_path / "junk" / "noise.py").write_text("noise = 1\n" * 20)
    assert resolve("--target", "WORKTREE", "--repo-root", str(tmp_path))["size_metric"] == 0


def test_prose_profile_override_on_a_range_is_measured_in_words(tmp_path):
    """The unit follows the profile on the diff path too, not just the path target."""
    patch = tmp_path / "d.patch"
    patch.write_text("--- a/doc.md\n+++ b/doc.md\n@@ -0,0 +1,2 @@\n"
                     + "".join("+" + "word " * 50 + "\n" for _ in range(2)))
    result = resolve("--target", "main..HEAD", "--profile", "prose-claim",
                     "--repo-root", str(tmp_path), "--diff-file", str(patch))
    assert result["size_metric"] == 100


# --- output conventions -----------------------------------------------------------

def test_stdout_is_exactly_one_sorted_json_object(tmp_path):
    _git_repo(tmp_path)
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


@pytest.mark.parametrize("target", ["missing.pdf", "gone.csv", "absent.xlsx", "nope.tar.gz"])
def test_a_broken_markdown_link_is_reported_whatever_the_extension(tmp_path, target):
    """`[text](target)` is a link by construction — no suffix guessing needed.

    The allowlist exists to keep backticked *prose* from being read as a path. A
    Markdown link carries no such ambiguity.
    """
    doc = _touch(tmp_path / "notes.md", f"See [the thing]({target}).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert target in [f["evidence"][0]["ref"] for f in result["findings"]]


def test_a_resolvable_markdown_link_with_an_odd_extension_passes(tmp_path):
    _touch(tmp_path / "paper.pdf", "%PDF\n")
    doc = _touch(tmp_path / "notes.md", "See [the paper](paper.pdf).\n")
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


def test_prose_in_backticks_is_still_not_treated_as_a_path(tmp_path):
    """The noise guard stays: a link is explicit, a backticked phrase is not."""
    doc = _touch(tmp_path / "notes.md", "Handle this `carefully. always` when reviewing.\n")
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


def test_symbol_resolution_outside_a_git_worktree_is_could_not_run(tmp_path):
    """A tool that failed proves nothing about absence.

    Outside a worktree `git grep` errors, and reading that as "not found" turns
    every symbol in the document into a HIGH finding — the noise flood the pre-pass
    exists to avoid.
    """
    doc = _touch(tmp_path / "notes.md", "The `retry_handler` helper does the work.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path))
    high = [f for f in result["findings"] if f["severity"] == "HIGH"]
    assert not high, f"tool failure reported as absence: {[f['claim'] for f in high]}"
    assert "skipped" in result["checks"][0]["output"]


def test_a_symbol_is_not_resolved_by_the_document_that_names_it(tmp_path):
    """The document's own mention is the claim, not evidence for it.

    `git grep` searches the whole tree including the tracked target, so a document
    citing an invented symbol was satisfying its own reference check.
    """
    _git_repo(tmp_path)
    doc = _touch(tmp_path / "notes.md",
                 "The function `totally_invented_symbol_xyz` handles retries.\n")
    _git(tmp_path, "add", "-A")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    refs = [f["evidence"][0]["ref"] for f in result["findings"]]
    assert "totally_invented_symbol_xyz" in refs


def test_a_symbol_defined_elsewhere_still_resolves(tmp_path):
    _git_repo(tmp_path)
    _touch(tmp_path / "src.py", "def genuinely_present_symbol():\n    return 1\n")
    doc = _touch(tmp_path / "notes.md", "See `genuinely_present_symbol` for details.\n")
    _git(tmp_path, "add", "-A")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["findings"] == []


def test_link_fragment_is_not_part_of_the_filesystem_path(tmp_path):
    """`./design.md#goals` names design.md; the fragment is an in-document anchor."""
    _touch(tmp_path / "design.md", "# Goals\n")
    doc = _touch(tmp_path / "notes.md", "See [goals](./design.md#goals).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc), "--repo-root", str(tmp_path))
    assert result["status"] == "pass"
    assert result["findings"] == []


def test_link_fragment_does_not_hide_a_genuinely_missing_file(tmp_path):
    doc = _touch(tmp_path / "notes.md", "See [goals](./gone.md#goals).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert "./gone.md#goals" in [f["evidence"][0]["ref"] for f in result["findings"]]


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


def test_failing_code_check_files_a_finding(tmp_path):
    """A failed check must become a finding, or nothing carries it to the verdict.

    The prose branch already files findings; the code branch recorded the failure in
    `checks` alone, where `compute_verdict` never looks.
    """
    result = prepass("--profile", "code-diff", "--target", "WORKTREE",
                     "--repo-root", str(tmp_path), "--check-cmd", "exit 3", expect=1)
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["severity"] == "HIGH"
    assert finding["stage"] == "prepass"
    assert finding["category"] == "failing-check"
    assert finding["evidence"][0]["kind"] == "prepass"


def test_failing_code_check_cannot_produce_a_pass_verdict(tmp_path):
    """The end-to-end version of the same defect: red tests must never read as PASS."""
    pre = prepass("--profile", "code-diff", "--target", "WORKTREE",
                  "--repo-root", str(tmp_path), "--check-cmd", "exit 1", expect=1)
    result = gate(tmp_path, [], prepass_status=pre["status"],
                  prepass_findings=pre["findings"], expect=1)
    assert result["verdict"] == "NEEDS_FIXES"


# --- the class invariant: no failed check reaches the verdict as a pass ------------
#
# Three separate defects were the same defect — a failure recorded somewhere the
# verdict does not read. These cover the rule itself, per branch, rather than the
# instance that happened to be found.

def _failing_prepass_cases(tmp_path):
    """(label, argv) for each way a check can fail, one per pre-pass branch."""
    code = tmp_path / "code"
    code.mkdir()
    spec = tmp_path / "spec"
    spec.mkdir()
    # Required headings absent, and no references at all, so the reference check passes
    # and only section coverage fails.
    (spec / "logic.md").write_text("# Unrelated Heading\n\nProse with no references.\n")
    prose = tmp_path / "prose"
    prose.mkdir()
    (prose / "notes.md").write_text("See `src/does_not_exist.py`.\n")
    return [
        ("code-diff / failing check",
         ("--profile", "code-diff", "--target", "WORKTREE",
          "--repo-root", str(code), "--check-cmd", "exit 3")),
        ("spec-design / section coverage",
         ("--profile", "spec-design", "--target", str(spec / "logic.md"),
          "--repo-root", str(spec))),
        ("prose-claim / reference resolution",
         ("--profile", "prose-claim", "--target", str(prose / "notes.md"),
          "--repo-root", str(prose))),
    ]


def test_every_failed_check_is_carried_by_a_finding(tmp_path):
    """`status: fail` with an empty findings list is the bug, in any branch."""
    for label, argv in _failing_prepass_cases(tmp_path):
        result = prepass(*argv, expect=1)
        assert result["status"] == "fail", label
        failed = [c["name"] for c in result["checks"] if c["status"] == "fail"]
        assert failed, label
        assert result["findings"], f"{label}: failed {failed} but filed no finding"


def test_no_failing_prepass_branch_can_reach_a_pass_verdict(tmp_path):
    """The invariant that actually matters, asserted end-to-end for every branch."""
    for label, argv in _failing_prepass_cases(tmp_path):
        pre = prepass(*argv, expect=1)
        result = gate(tmp_path, [], prepass_status=pre["status"],
                      prepass_findings=pre["findings"], expect=1)
        assert result["verdict"] != "PASS", f"{label}: failed pre-pass produced PASS"


def test_a_failed_check_that_files_no_finding_of_its_own_still_gets_one(tmp_path):
    """Section coverage reports no per-heading findings; the generic one covers it."""
    (tmp_path / "logic.md").write_text("# Unrelated\n\nNo references here.\n")
    result = prepass("--profile", "spec-design", "--target", str(tmp_path / "logic.md"),
                     "--repo-root", str(tmp_path), expect=1)
    categories = {f["category"] for f in result["findings"]}
    assert "failing-check" in categories


def test_reference_failures_are_not_double_reported(tmp_path):
    """A check that files its own findings must not also get the generic one."""
    doc = _touch(tmp_path / "notes.md", "See `src/does_not_exist.py`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    categories = [f["category"] for f in result["findings"]]
    assert categories == ["unresolvable-reference"], categories


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
    "$WORK/findings.json",     # unexpanded shell variable
    "${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/adversarial-review",
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


@pytest.mark.parametrize("family", ["OPENAI", "OpenAI", " openai ", "OpenAI\n"])
def test_author_family_matching_is_not_case_or_whitespace_sensitive(family):
    """The one invariant the skill is built on must not turn on a capital letter.

    A miscased family failed to match, so the author's own family was selected and
    then stamped `full` — same-family review reported as structurally independent.
    """
    result = select_model("--author-family", family, "--check-cmd", "true")
    assert result["family"] != "openai", "author's own family selected"
    assert result["independence"] == "full"


def test_an_unknown_author_family_is_rejected_rather_than_silently_trusted():
    """`--author-family typo` must not look identical to a genuine cross-family run."""
    proc = run_ar("select-model", "--author-family", "not-a-real-family", "--check-cmd", "true")
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


def test_the_documented_other_author_family_is_accepted():
    """`other` is in the composition contract: an author this ladder cannot be.

    Rejecting it locks out every caller whose author is a human or a local model.
    """
    result = select_model("--author-family", "other", "--check-cmd", "true")
    assert result["resolved"] is True
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


# ============================ gate + manifest =====================================

def _finding(**over) -> dict:
    base = {
        "id": "F1", "severity": "HIGH", "confidence": "HIGH",
        "category": "correctness", "claim": "x breaks",
        "evidence": [{"kind": "command", "command": "pytest -q", "output": "1 failed"}],
        "remediation": "fix x", "patch": None, "stage": "promote",
        "disposition": "standing",
    }
    base.update(over)
    return base


def _write(tmp_path: Path, name: str, payload) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return str(p)


def _inputs(tmp_path, findings, *, model=None, prepass_status="pass", prepass_findings=None):
    model = model or {"resolved": True, "alias": "codex", "family": "openai",
                      "provider": "openai-codex", "model": "gpt-5.6-sol",
                      "thinking": "high", "independence": "full", "ladder": []}
    pre = {"status": prepass_status, "checks": [], "findings": prepass_findings or []}
    return (
        "--findings", _write(tmp_path, "f.json", findings),
        "--model", _write(tmp_path, "m.json", model),
        "--prepass", _write(tmp_path, "p.json", pre),
    )


def gate(tmp_path, findings, *, expect=0, extra=(), repo_root=None, **kw) -> dict:
    if repo_root is not None:
        extra = (*extra, "--repo-root", str(repo_root))
    proc = run_ar("gate", *_inputs(tmp_path, findings, **kw), *extra)
    assert proc.returncode == expect, f"exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


# --- required inputs --------------------------------------------------------------

def test_gate_without_model_input_fails_loudly(tmp_path):
    """A missing input must never collapse silently onto the severity path."""
    proc = run_ar("gate", "--findings", _write(tmp_path, "f.json", []),
                  "--prepass", _write(tmp_path, "p.json", {"status": "pass", "checks": [], "findings": []}))
    assert proc.returncode == 2


@pytest.mark.parametrize("model", [
    {"resolved": True},
    {"resolved": True, "alias": "codex"},
    {"resolved": True, "alias": "codex", "family": "openai", "provider": "openai-codex"},
])
def test_a_model_claiming_resolved_must_actually_name_a_reviewer(tmp_path, model):
    """`resolved: true` alone walks past NOT_REVIEWABLE and emits PASS.

    That branch exists precisely so an artifact nothing looked at cannot read as
    clean; a malformed model file must not be the way around it.
    """
    proc = run_ar("gate", *_inputs(tmp_path, [], model=model))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


@pytest.mark.parametrize("bad", [{}, {"unrelated": "object"}, {"status": "pass"}])
def test_a_prepass_that_never_ran_cannot_supply_a_clean_result(tmp_path, bad):
    """An empty object defaults to no findings — the shape of a clean pre-pass."""
    proc = run_ar("gate", "--findings", _write(tmp_path, "f.json", []),
                  "--model", _write(tmp_path, "m.json", {
                      "resolved": True, "alias": "codex", "family": "openai",
                      "provider": "openai-codex", "model": "gpt-5.6-sol",
                      "thinking": "high", "independence": "full", "ladder": []}),
                  "--prepass", _write(tmp_path, "p.json", bad))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


def test_duplicate_caller_supplied_ids_are_rejected(tmp_path):
    """IDs match a finding to its prior ruling; an ambiguous one must not pass.

    Silently renumbering would be worse than failing — it breaks the match a
    caller relies on across rounds.
    """
    findings = [_finding(id="F1", severity="HIGH"), _finding(id="F1", severity="MEDIUM")]
    proc = run_ar("gate", *_inputs(tmp_path, findings))
    assert proc.returncode == 2
    assert "duplicate ids" in proc.stderr


def test_an_unresolved_model_needs_no_reviewer_fields(tmp_path):
    """The NOT_REVIEWABLE path is the one case where naming nobody is correct."""
    dead = {"resolved": False, "alias": None, "family": None, "provider": None,
            "model": None, "thinking": None, "independence": "reduced", "ladder": []}
    assert gate(tmp_path, [], model=dead, expect=4)["verdict"] == "NOT_REVIEWABLE"


def test_gate_without_prepass_input_fails_loudly(tmp_path):
    proc = run_ar("gate", "--findings", _write(tmp_path, "f.json", []),
                  "--model", _write(tmp_path, "m.json", {"resolved": True, "independence": "full"}))
    assert proc.returncode == 2


# --- verdicts ---------------------------------------------------------------------

def test_verdict_pass_when_only_low_survives(tmp_path):
    result = gate(tmp_path, [_finding(severity="LOW")], expect=0)
    assert result["verdict"] == "PASS"


def test_verdict_needs_fixes_on_medium(tmp_path):
    assert gate(tmp_path, [_finding(severity="MEDIUM")], expect=1)["verdict"] == "NEEDS_FIXES"


def test_verdict_critical_issues(tmp_path):
    assert gate(tmp_path, [_finding(severity="CRITICAL")], expect=3)["verdict"] == "CRITICAL_ISSUES"


def test_not_reviewable_when_no_reviewer_resolved(tmp_path):
    """First branch: the review never happened."""
    dead = {"resolved": False, "alias": None, "family": None, "provider": None,
            "model": None, "thinking": None, "independence": "reduced", "ladder": []}
    result = gate(tmp_path, [], model=dead, expect=4)
    assert result["verdict"] == "NOT_REVIEWABLE"


def test_not_reviewable_beats_pass_with_zero_findings(tmp_path):
    """The dangerous case: no reviewer AND no findings must not read as PASS."""
    dead = {"resolved": False, "alias": None, "family": None, "provider": None,
            "model": None, "thinking": None, "independence": "reduced", "ladder": []}
    assert gate(tmp_path, [], model=dead, expect=4)["verdict"] == "NOT_REVIEWABLE"


def test_not_reviewable_second_branch_unfalsifiable_plus_could_not_run(tmp_path):
    result = gate(tmp_path, [_finding(category="unfalsifiable-claim", severity="MEDIUM")],
                  prepass_status="could-not-run", expect=4)
    assert result["verdict"] == "NOT_REVIEWABLE"


def test_unfalsifiable_alone_does_not_block_when_prepass_ran(tmp_path):
    """Review proceeds; the claim is reported, not fatal."""
    result = gate(tmp_path, [_finding(category="unfalsifiable-claim", severity="MEDIUM")], expect=1)
    assert result["verdict"] == "NEEDS_FIXES"
    assert result["findings"][0]["category"] == "unfalsifiable-claim"


def test_unfalsifiable_claim_sorts_first(tmp_path):
    findings = [_finding(id="F1", severity="CRITICAL"),
                _finding(id="F2", category="unfalsifiable-claim", severity="LOW")]
    result = gate(tmp_path, findings, expect=3)
    assert result["findings"][0]["category"] == "unfalsifiable-claim"


# --- evidence gate: three outcomes ------------------------------------------------

def test_verified_finding_keeps_its_confidence(tmp_path):
    result = gate(tmp_path, [_finding(severity="CRITICAL", confidence="HIGH")], expect=3)
    assert result["findings"][0]["confidence"] == "HIGH"


def test_unverified_critical_is_capped_to_low_confidence_not_downgraded(tmp_path):
    """Severity tracks consequence; proof only speaks to likelihood."""
    unproven = _finding(severity="CRITICAL", confidence="HIGH",
                        evidence=[{"kind": "quote", "ref": "spec#3", "quote": "must not lose data"}])
    result = gate(tmp_path, [unproven], expect=3)
    assert result["findings"][0]["severity"] == "CRITICAL"
    assert result["findings"][0]["confidence"] == "LOW"
    assert result["verdict"] == "CRITICAL_ISSUES"


def test_unverified_medium_keeps_its_confidence(tmp_path):
    """logic.md permits reasoned argument below CRITICAL/HIGH — no cap there."""
    unproven = _finding(severity="MEDIUM", confidence="HIGH",
                        evidence=[{"kind": "quote", "ref": "spec#3", "quote": "text"}])
    assert gate(tmp_path, [unproven], expect=1)["findings"][0]["confidence"] == "HIGH"


def test_falsified_evidence_is_dropped_and_counted(tmp_path):
    bad = _finding(evidence=[{"kind": "file-line", "ref": "no/such/file.py:1-2", "quote": "zzz"}])
    result = gate(tmp_path, [bad], expect=0)
    assert result["findings"] == []
    assert result["suppressed_count"] == 1
    assert result["suppressed"][0]["reason"] == "falsified"


def test_one_true_evidence_item_does_not_shield_a_fabricated_one(tmp_path):
    """Every falsifiable item must hold. Otherwise a real citation launders a bogus one."""
    mixed = _finding(evidence=[
        {"kind": "command", "command": "pytest -q", "output": "1 failed"},
        {"kind": "file-line", "ref": "no/such/file.py:1-2", "quote": "zzz"},
    ])
    result = gate(tmp_path, [mixed], expect=0)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_unfalsifiable_items_alongside_a_real_one_still_survive(tmp_path):
    """`all` must not become a purity test: what we cannot check is not a failure."""
    survivor = _finding(severity="MEDIUM", evidence=[
        {"kind": "command", "command": "pytest -q", "output": "1 failed"},
        {"kind": "quote", "ref": "spec#3", "quote": "must not lose data"},
    ])
    result = gate(tmp_path, [survivor], expect=1)
    assert len(result["findings"]) == 1
    assert result["suppressed_count"] == 0


# --- evidence gate: the cited location ---------------------------------------------

def test_line_anchor_beyond_end_of_file_is_falsified(tmp_path):
    """A quote that exists somewhere must not launder an impossible line number."""
    (tmp_path / "src.py").write_text("a\nb\nc\nthe quoted text\n")
    bad = _finding(evidence=[
        {"kind": "file-line", "ref": "src.py:999999-1000000", "quote": "the quoted text"},
    ])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_quote_outside_the_cited_range_is_falsified(tmp_path):
    (tmp_path / "src.py").write_text("a\nb\nc\nthe quoted text\n")
    bad = _finding(evidence=[
        {"kind": "file-line", "ref": "src.py:1-2", "quote": "the quoted text"},
    ])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []


def test_a_quote_whose_first_line_merely_recurs_in_range_is_falsified(tmp_path):
    """The whole quote must start in the range — not its first line, separately.

    Checking "first line in range" and "quote somewhere in file" independently lets
    two different places each satisfy half the test.
    """
    (tmp_path / "src.py").write_text("alpha\nbeta\ngamma\nalpha\nomega\n")
    bad = _finding(evidence=[
        {"kind": "file-line", "ref": "src.py:1-2", "quote": "alpha\nomega"},
    ])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []


def test_a_quote_running_past_the_end_of_its_cited_range_still_resolves(tmp_path):
    """A short range is a citation nit; pointing somewhere else is the falsehood.

    Reviewers routinely cite the line a passage starts on and undershoot its end.
    Killing those drops real findings — observed twice in one live run — while
    catching nothing a fabricator would do.
    """
    (tmp_path / "src.py").write_text("a\nb\nfirst line\nsecond line\nthird line\n")
    finding = _finding(severity="MEDIUM", evidence=[
        {"kind": "file-line", "ref": "src.py:3-4",
         "quote": "first line\nsecond line\nthird line"},
    ])
    assert len(gate(tmp_path, [finding], expect=1, repo_root=tmp_path)["findings"]) == 1


def test_quote_inside_the_cited_range_resolves(tmp_path):
    (tmp_path / "src.py").write_text("a\nb\nc\nthe quoted text\n")
    good = _finding(severity="MEDIUM", evidence=[
        {"kind": "file-line", "ref": "src.py:4", "quote": "the quoted text"},
    ])
    assert len(gate(tmp_path, [good], expect=1, repo_root=tmp_path)["findings"]) == 1


def test_file_line_evidence_without_an_anchor_still_searches_the_whole_file(tmp_path):
    """No anchor is no claim about location; only a cited range is checked."""
    (tmp_path / "src.py").write_text("a\nb\nc\nthe quoted text\n")
    good = _finding(severity="MEDIUM", evidence=[
        {"kind": "file-line", "ref": "src.py", "quote": "the quoted text"},
    ])
    assert len(gate(tmp_path, [good], expect=1, repo_root=tmp_path)["findings"]) == 1


def test_absence_evidence_naming_a_missing_file_is_falsified(tmp_path):
    """The search is not re-run, but the scope it names is checkable."""
    bad = _finding(evidence=[
        {"kind": "absence", "command": "grep -rn foo src/gone.py", "ref": "src/gone.py", "output": ""},
    ])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


@pytest.mark.parametrize("ref", ["pyproject.toml", "config.yaml", "data.csv", "notes.rst"])
def test_absence_scope_is_checked_whatever_the_extension(tmp_path, ref):
    """The scope check must not depend on a source-suffix allowlist.

    `evidence.ref` is a declared scope, not prose that might be a path, so any
    token carrying an extension is checkable.
    """
    bad = _finding(severity="MEDIUM",
                   evidence=[{"kind": "absence", "command": f"grep -rn x {ref}", "ref": ref, "output": ""}])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_absence_evidence_whose_own_output_shows_a_hit_is_falsified(tmp_path):
    """The claim is that the search came back empty; its own output says otherwise."""
    (tmp_path / "src.py").write_text("x = 1\n")
    bad = _finding(evidence=[{"kind": "absence", "command": "grep -rn foo src.py",
                              "ref": "src.py", "output": "src.py:1:foo is right here"}])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_absence_evidence_naming_a_real_scope_survives(tmp_path):
    (tmp_path / "src.py").write_text("nothing here\n")
    good = _finding(severity="MEDIUM", evidence=[
        {"kind": "absence", "command": "grep -rn foo src.py", "ref": "src.py", "output": ""},
    ])
    assert len(gate(tmp_path, [good], expect=1, repo_root=tmp_path)["findings"]) == 1


def test_a_fragment_does_not_shield_a_missing_file(tmp_path):
    """`spec#3` names a section; `no/such/file.md#x` names a file that is not there."""
    bad = _finding(evidence=[
        {"kind": "file-line", "ref": "no/such/file.md#section", "quote": "zzz"},
    ])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


@pytest.mark.parametrize("ref", ["Makefile:12", "Dockerfile:3-4", "totally-invented:1"])
def test_file_line_evidence_naming_a_missing_extensionless_file_is_falsified(tmp_path, ref):
    """`file-line` is a claim about a file. No extension is not a licence to skip it."""
    bad = _finding(evidence=[{"kind": "file-line", "ref": ref, "quote": "never written"}])
    result = gate(tmp_path, [bad], expect=0, repo_root=tmp_path)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_a_section_anchor_naming_no_file_is_still_unfalsifiable(tmp_path):
    """The escape hatch stays open for what it was for."""
    survivor = _finding(severity="MEDIUM", evidence=[
        {"kind": "quote", "ref": "spec#3", "quote": "must not lose data"},
    ])
    assert len(gate(tmp_path, [survivor], expect=1, repo_root=tmp_path)["findings"]) == 1


# --- evidence schema ---------------------------------------------------------------

@pytest.mark.parametrize("evidence", [
    {"kind": "command", "command": "", "output": ""},
    {"kind": "command", "command": "pytest -q", "output": "   "},
    {"kind": "file-line", "ref": "", "quote": "x"},
])
def test_empty_evidence_values_are_rejected(tmp_path, evidence):
    """Presence is not content: an empty command must not buy reproduction credit."""
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(evidence=[evidence])]))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


# --- gate input shapes -------------------------------------------------------------

def test_gate_accepts_the_quick_mode_object_and_keeps_its_suppressed_count(tmp_path):
    """`quick` emits {findings, suppressed}; rejecting it breaks the documented pipeline.

    The self-refuted count must survive, or the kill-rate integrity signal reads zero.
    """
    quick = {"findings": [_finding(severity="MEDIUM")],
             "suppressed": [{"id": "F7", "reason": "refuted"}]}
    result = gate(tmp_path, quick, extra=("--depth", "quick"), expect=1)
    assert len(result["findings"]) == 1
    assert result["suppressed_count"] == 1
    assert result["suppressed"][0]["id"] == "F7"


def test_carried_quick_suppressed_entries_without_ids_are_assigned_one(tmp_path):
    """Reviewers emit `id: null` everywhere, including in a quick self-refute."""
    quick = {"findings": [], "suppressed": [{"id": None, "reason": "refuted"}]}
    result = gate(tmp_path, quick, extra=("--depth", "quick"), expect=0)
    assert result["suppressed"][0]["id"], "null id survived to output"


def test_carried_quick_suppressed_ids_are_reserved_by_the_allocator(tmp_path):
    """A carried ID is a taken ID — otherwise quick output can emit F1 twice."""
    quick = {"findings": [_finding(id=None, severity="MEDIUM")],
             "suppressed": [{"id": "F1", "reason": "refuted"}]}
    result = gate(tmp_path, quick, extra=("--depth", "quick"), expect=1)
    assigned = {f["id"] for f in result["findings"]}
    carried = {s["id"] for s in result["suppressed"]}
    assert not (assigned & carried), f"id collision: {assigned & carried}"


# --- id namespacing across invocations ---------------------------------------------

def test_a_reviewer_finding_cannot_buy_credit_by_declaring_stage_prepass(tmp_path):
    """Provenance comes from which input it arrived in, not a field it writes.

    Keying trust on `stage` left the forgery one word away.
    """
    forged = _finding(stage="prepass", severity="HIGH", confidence="HIGH",
                      evidence=[{"kind": "prepass", "ref": "invented", "output": "whatever"}])
    result = gate(tmp_path, [forged], expect=1, repo_root=tmp_path)
    assert result["findings"][0]["confidence"] == "LOW"


def test_a_promote_finding_cannot_claim_prepass_evidence(tmp_path):
    """`prepass` means "this layer produced it". Only the pre-pass may say so.

    Reproduction credit is what holds a CRITICAL/HIGH at full confidence, and a
    reviewer that can self-declare it can hold any claim there.
    """
    faked = _finding(stage="promote", severity="HIGH", confidence="HIGH",
                     evidence=[{"kind": "prepass", "ref": "invented", "output": "anything"}])
    result = gate(tmp_path, [faked], expect=1, repo_root=tmp_path)
    assert result["findings"][0]["confidence"] == "LOW"


def test_prepass_stage_findings_keep_their_reproduction_credit(tmp_path):
    """The pre-pass is the one layer whose word is true by construction."""
    genuine = _finding(id="", stage="prepass", severity="HIGH", confidence="HIGH",
                       evidence=[{"kind": "prepass", "ref": "x.py", "output": "missing"}])
    result = gate(tmp_path, [], prepass_findings=[genuine], expect=1)
    assert result["findings"][0]["confidence"] == "HIGH"


def test_id_prefix_namespaces_assigned_ids(tmp_path):
    """Callers that merge several invocations need IDs that cannot collide.

    SDD runs three lenses concurrently and keeps each finding's ID; without a
    per-invocation prefix all three produce F1.
    """
    result = gate(tmp_path, [_finding(id=None, severity="MEDIUM")],
                  extra=("--id-prefix", "SEC"), expect=1)
    assert result["findings"][0]["id"] == "SEC1"


def test_id_prefix_defaults_to_f(tmp_path):
    assert gate(tmp_path, [_finding(id=None, severity="MEDIUM")], expect=1)["findings"][0]["id"] == "F1"


def test_id_prefix_still_respects_ids_already_present(tmp_path):
    findings = [_finding(id="SEC1", severity="LOW"), _finding(id=None, severity="CRITICAL")]
    result = gate(tmp_path, findings, extra=("--id-prefix", "SEC"), expect=3)
    ids = [f["id"] for f in result["findings"]]
    assert len(ids) == len(set(ids)), ids


@pytest.mark.parametrize("suppressed", [5, "refuted", {"id": "F1"}])
def test_quick_object_with_a_wrong_shaped_suppressed_is_a_diagnostic(tmp_path, suppressed):
    """Exit 2 with a message, never a traceback — the same rule as any bad input."""
    quick = {"findings": [], "suppressed": suppressed}
    proc = run_ar("gate", *_inputs(tmp_path, quick), "--depth", "quick")
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("bad", ["a string", 42, ["not", "an", "object"]])
def test_gate_rejects_non_object_model_input_with_exit_2(tmp_path, bad):
    """Valid JSON of the wrong shape must be a diagnostic, not an AttributeError."""
    proc = run_ar("gate", *_inputs(tmp_path, [], model=bad))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


def test_gate_rejects_non_object_prepass_input_with_exit_2(tmp_path):
    proc = run_ar("gate", "--findings", _write(tmp_path, "f.json", []),
                  "--model", _write(tmp_path, "m.json", {"resolved": True}),
                  "--prepass", _write(tmp_path, "p.json", ["not", "an", "object"]))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr


# --- disposition / tie resolution -------------------------------------------------

def test_refuted_finding_is_dropped_at_any_depth(tmp_path):
    result = gate(tmp_path, [_finding(disposition="refuted")], expect=0)
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "refuted"


def test_contested_is_dropped_below_deep(tmp_path):
    result = gate(tmp_path, [_finding(disposition="contested")],
                  extra=("--depth", "standard"), expect=0)
    assert result["findings"] == []
    assert result["contested"] == []
    assert result["suppressed"][0]["reason"] == "refuted"


def test_contested_finding_with_false_evidence_is_falsified_not_tiebroken(tmp_path):
    """The evidence gate runs first: a demonstrable falsehood is not a disagreement.

    Sending one to a third model spends a dispatch adjudicating something already
    known to be wrong.
    """
    bogus = _finding(disposition="contested", severity="MEDIUM",
                     evidence=[{"kind": "file-line", "ref": "no/such/file.py:1-2", "quote": "zzz"}])
    result = gate(tmp_path, [bogus], extra=("--depth", "deep"), expect=0, repo_root=tmp_path)
    assert result["contested"] == []
    assert result["suppressed"][0]["reason"] == "falsified"


def test_contested_at_deep_is_withheld_not_suppressed(tmp_path):
    result = gate(tmp_path, [_finding(disposition="contested")],
                  extra=("--depth", "deep"), expect=0)
    assert result["findings"] == []
    assert [f["id"] for f in result["contested"]] == ["F1"]
    assert result["suppressed_count"] == 0


def test_absent_disposition_is_treated_as_standing(tmp_path):
    f = _finding()
    del f["disposition"]
    assert gate(tmp_path, [f], expect=1,
                extra=("--repo-root", str(tmp_path)))["findings"][0]["id"] == "F1"


# --- prepass merge ----------------------------------------------------------------

def test_gate_merges_prepass_findings_itself(tmp_path):
    pre = _finding(id="", severity="HIGH", stage="prepass",
                   evidence=[{"kind": "prepass", "ref": "x.py", "output": "missing"}])
    result = gate(tmp_path, [], prepass_findings=[pre], expect=1)
    assert len(result["findings"]) == 1
    assert result["findings"][0]["stage"] == "prepass"


def test_prepass_evidence_satisfies_the_reproduction_requirement(tmp_path):
    pre = _finding(id="", severity="HIGH", confidence="HIGH", stage="prepass",
                   evidence=[{"kind": "prepass", "ref": "x.py", "output": "missing"}])
    result = gate(tmp_path, [], prepass_findings=[pre], expect=1)
    assert result["findings"][0]["confidence"] == "HIGH"


# --- schema validation ------------------------------------------------------------

@pytest.mark.parametrize("field", ["severity", "confidence", "claim", "evidence", "remediation"])
def test_missing_required_field_is_rejected(field, tmp_path):
    bad = _finding()
    del bad[field]
    proc = run_ar("gate", *_inputs(tmp_path, [bad]))
    assert proc.returncode == 2
    assert field in proc.stderr


@pytest.mark.parametrize("field", ["claim", "category", "remediation"])
def test_blank_core_fields_are_rejected(field, tmp_path):
    """A finding with no claim is not a finding; presence is not content."""
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(**{field: "   "})]))
    assert proc.returncode == 2
    assert field in proc.stderr


def test_invalid_stage_is_rejected(tmp_path):
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(stage="invented")]))
    assert proc.returncode == 2


def test_invalid_severity_is_rejected(tmp_path):
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(severity="SEVERE")]))
    assert proc.returncode == 2


def test_empty_evidence_array_is_rejected(tmp_path):
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(evidence=[])]))
    assert proc.returncode == 2


# --- ids and depth ----------------------------------------------------------------

def test_ids_are_assigned_in_severity_order_when_absent(tmp_path):
    findings = [_finding(id="", severity="LOW"), _finding(id="", severity="CRITICAL")]
    result = gate(tmp_path, findings, expect=3)
    assert result["findings"][0]["id"] == "F1"
    assert result["findings"][0]["severity"] == "CRITICAL"


def test_assigned_ids_never_collide_with_ids_already_present(tmp_path):
    """Finding-ID stability is a contract: two findings must never share an ID.

    A blank-ID finding sorting into position 1 must not be handed an ID that a
    reviewer-supplied finding already carries.
    """
    findings = [_finding(id="F1", severity="LOW"), _finding(id="", severity="CRITICAL")]
    result = gate(tmp_path, findings, expect=3)
    ids = [f["id"] for f in result["findings"]]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_suppressed_records_carry_a_usable_id(tmp_path):
    """The promote prompt instructs `id: null`; a null in `suppressed` names nothing.

    A caller cannot carry a dismissal forward — or reuse its ID, as the prompt
    requires — if the record it was given has no ID.
    """
    result = gate(tmp_path, [_finding(id=None, disposition="refuted")], expect=0)
    assert result["suppressed"][0]["id"], "suppressed record has no usable id"


def test_contested_records_carry_a_usable_id(tmp_path):
    result = gate(tmp_path, [_finding(id=None, disposition="contested")],
                  extra=("--depth", "deep"), expect=0)
    assert result["contested"][0]["id"], "contested record has no usable id"


def test_ids_are_unique_across_survivors_suppressed_and_contested(tmp_path):
    findings = [_finding(id=None, disposition="refuted"),
                _finding(id=None, disposition="contested"),
                _finding(id=None, disposition="standing", severity="MEDIUM")]
    result = gate(tmp_path, findings, extra=("--depth", "deep"), expect=1)
    ids = ([f["id"] for f in result["findings"]]
           + [f["id"] for f in result["contested"]]
           + [s["id"] for s in result["suppressed"]])
    assert all(ids), f"blank id present: {ids}"
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_gate_echoes_the_depth_it_used(tmp_path):
    assert gate(tmp_path, [], extra=("--depth", "deep"))["depth"] == "deep"


# --- manifest ---------------------------------------------------------------------

def _manifest_inputs(tmp_path, *, depth="standard", independence="full", family="openai"):
    resolve_doc = {"profile": "code-diff", "target_kind": "git-range", "target_ref": "main..HEAD",
                   "artifact_hash": "abc", "size_metric": 200, "depth_suggestion": "deep",
                   "contract_surface": False}
    prepass_doc = {"status": "pass", "checks": [{"name": "code-check", "command": "pytest -q",
                                                 "exit_code": 0, "status": "pass", "output": ""}],
                   "findings": []}
    model_doc = {"resolved": True, "alias": "codex", "family": family, "provider": "openai-codex",
                 "model": "gpt-5.6-sol", "thinking": "high", "independence": independence,
                 "ladder": []}
    gate_doc = {"verdict": "PASS", "findings": [], "contested": [], "suppressed": [],
                "suppressed_count": 2, "depth": depth}
    return (
        "--resolve", _write(tmp_path, "r.json", resolve_doc),
        "--prepass", _write(tmp_path, "p2.json", prepass_doc),
        "--model", _write(tmp_path, "m2.json", model_doc),
        "--gate", _write(tmp_path, "g.json", gate_doc),
    )


def manifest(tmp_path, *, extra=(), expect=0, **kw) -> dict:
    proc = run_ar("manifest", *_manifest_inputs(tmp_path, **kw), *extra)
    assert proc.returncode == expect, f"exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def test_manifest_records_the_depth_actually_used_not_the_suggestion(tmp_path):
    """resolve suggested deep; the caller ran standard. The manifest must say standard."""
    result = manifest(tmp_path, depth="standard")
    assert result["depth"] == "standard"


def test_manifest_carries_a_replayable_reviewer_triple(tmp_path):
    reviewer = manifest(tmp_path)["reviewer"]
    assert reviewer["provider"] == "openai-codex"
    assert reviewer["model"] == "gpt-5.6-sol"
    assert reviewer["thinking"] == "high"


def test_quick_depth_forces_reduced_independence_even_cross_family(tmp_path):
    """Self-refutation in one context cannot deliver structural independence."""
    result = manifest(tmp_path, depth="quick", independence="full", family="openai")
    assert result["reviewer"]["independence"] == "reduced"


def test_standard_depth_preserves_full_independence(tmp_path):
    result = manifest(tmp_path, depth="standard", independence="full")
    assert result["reviewer"]["independence"] == "full"


def test_reduced_independence_is_never_upgraded(tmp_path):
    result = manifest(tmp_path, depth="deep", independence="reduced")
    assert result["reviewer"]["independence"] == "reduced"


def test_manifest_propagates_verdict_and_suppressed_count(tmp_path):
    result = manifest(tmp_path)
    assert result["verdict"] == "PASS"
    assert result["suppressed_count"] == 2


def test_manifest_records_the_lens(tmp_path):
    assert manifest(tmp_path, extra=("--lens", "security"))["lens"] == "security"
    assert manifest(tmp_path)["lens"] is None


@pytest.mark.parametrize("broken", ["resolve", "prepass", "model", "gate"])
def test_manifest_rejects_unrelated_json_for_any_input(tmp_path, broken):
    """A replay record of nulls is worse than no record — it looks like a real run."""
    payloads = {
        "resolve": {"profile": "code-diff", "target_kind": "git-range", "target_ref": "a..b",
                    "artifact_hash": "x", "size_metric": 1, "depth_suggestion": "quick",
                    "contract_surface": False},
        "prepass": {"status": "pass", "checks": [], "findings": []},
        "model": {"resolved": True, "alias": "codex", "family": "openai", "provider": "openai-codex",
                  "model": "gpt-5.6-sol", "thinking": "high", "independence": "full", "ladder": []},
        "gate": {"verdict": "PASS", "findings": [], "contested": [], "suppressed": [],
                 "suppressed_count": 0, "depth": "quick"},
    }
    payloads[broken] = {"unrelated": "object"}
    args = []
    for name, payload in payloads.items():
        args += [f"--{name}", _write(tmp_path, f"{name}.json", payload)]
    proc = run_ar("manifest", *args)
    assert proc.returncode == 2, f"accepted an unrelated {broken} payload"
    assert "adversarial-review:" in proc.stderr


def _review_inputs(work, repo):
    """A complete set of stage outputs for a real target, written outside the repo."""
    proc = run_ar("resolve", "--target", "WORKTREE", "--repo-root", str(repo))
    assert proc.returncode == 0, proc.stderr
    (work / "r.json").write_text(proc.stdout)
    _write(work, "p.json", {"status": "pass", "checks": [], "findings": []})
    _write(work, "m.json", {"resolved": True, "alias": "codex", "family": "openai",
                            "provider": "openai-codex", "model": "gpt-5.6-sol",
                            "thinking": "high", "independence": "full", "ladder": []})
    _write(work, "g.json", {"verdict": "PASS", "findings": [], "contested": [],
                            "suppressed": [], "suppressed_count": 0, "depth": "quick"})
    return ["--resolve", str(work / "r.json"), "--prepass", str(work / "p.json"),
            "--model", str(work / "m.json"), "--gate", str(work / "g.json"),
            "--repo-root", str(repo), "--verify-artifact"]


def test_manifest_verify_artifact_passes_on_an_unchanged_tree(tmp_path):
    repo, work = tmp_path / "repo", tmp_path / "work"
    repo.mkdir(); work.mkdir()
    _git_repo(repo)
    (repo / "x.py").write_text("a\nb\n")
    proc = run_ar("manifest", *_review_inputs(work, repo))
    assert proc.returncode == 0, proc.stderr


def test_manifest_verify_artifact_catches_a_tree_that_moved_mid_review(tmp_path):
    """A fix applied between stages makes refute 'refute' findings that were real.

    The stages after it judged content the earlier ones never saw, and the run
    comes out looking clean — the opposite of what happened.
    """
    repo, work = tmp_path / "repo", tmp_path / "work"
    repo.mkdir(); work.mkdir()
    _git_repo(repo)
    (repo / "x.py").write_text("a\nb\n")
    args = _review_inputs(work, repo)
    (repo / "x.py").write_text("a\nb\nc\nd\n")   # the tree moves under the review
    proc = run_ar("manifest", *args)
    assert proc.returncode == 2
    assert "artifact changed during the review" in proc.stderr


def test_manifest_without_verify_artifact_does_not_re_resolve(tmp_path):
    """Opt-in: a caller reviewing a detached diff has no tree to re-hash."""
    repo, work = tmp_path / "repo", tmp_path / "work"
    repo.mkdir(); work.mkdir()
    _git_repo(repo)
    (repo / "x.py").write_text("a\nb\n")
    args = [a for a in _review_inputs(work, repo) if a != "--verify-artifact"]
    (repo / "x.py").write_text("totally different\n")
    assert run_ar("manifest", *args).returncode == 0


def test_manifest_fails_cleanly_on_a_missing_input(tmp_path):
    proc = run_ar("manifest", "--resolve", str(tmp_path / "absent.json"),
                  "--prepass", _write(tmp_path, "p3.json", {}),
                  "--model", _write(tmp_path, "m3.json", {}),
                  "--gate", _write(tmp_path, "g3.json", {}))
    assert proc.returncode == 2
    assert "adversarial-review:" in proc.stderr



# ============ eighth review pass ==================================================

@pytest.mark.parametrize("target", ["vendor/plans/notes.md", "third_party/adr/notes.md"])
def test_a_nested_plans_or_adr_directory_does_not_hijack_the_profile(target, tmp_path):
    """Detection is specified as docs/plans/ and docs/adr/, not any directory so named."""
    _touch(tmp_path / target, "# Notes\n")
    assert resolve("--target", target, "--repo-root", str(tmp_path))["profile"] == "prose-claim"


@pytest.mark.parametrize("target", ["docs/plans/p.md", "docs/adr/0001-x.md"])
def test_the_documented_plan_and_adr_locations_still_detect(target, tmp_path):
    _touch(tmp_path / target, "# X\n")
    expected = "plan" if "plans" in target else "spec-design"
    assert resolve("--target", target, "--repo-root", str(tmp_path))["profile"] == expected


@pytest.mark.parametrize("suffix", [".c", ".h", ".cpp", ".hpp", ".cc", ".m", ".swift", ".kt",
                                    ".php", ".cs", ".scala", ".ex", ".erl", ".lua", ".pl", ".r"])
def test_unresolved_source_references_are_not_silently_skipped(suffix, tmp_path):
    """An unrecognized suffix meant the token was not a reference at all — a false pass."""
    doc = _touch(tmp_path / "notes.md", f"See `src/missing{suffix}`.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert any(f"missing{suffix}" in f["evidence"][0]["ref"] for f in result["findings"])


def test_a_markdown_link_to_a_directory_is_not_a_resolved_file_reference(tmp_path):
    (tmp_path / "somedir").mkdir()
    doc = _touch(tmp_path / "doc.md", "See [d](./somedir).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert any("somedir" in f["evidence"][0]["ref"] for f in result["findings"])


def test_a_backticked_directory_path_still_resolves(tmp_path):
    """Prose legitimately names directories; only link targets must be files."""
    (tmp_path / "somedir").mkdir()
    doc = _touch(tmp_path / "doc.md", "Files live under `somedir/`.\n")
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


@pytest.mark.parametrize("category", ["Not Kebab Case", "has_underscores", "x" * 41, ""])
def test_a_category_violating_the_schema_is_rejected(category, tmp_path):
    """The gate emitted these unchanged, so a caller keying on category got garbage."""
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(category=category)]))
    assert proc.returncode == 2
    assert "category" in proc.stderr


def test_a_valid_kebab_category_is_accepted(tmp_path):
    assert gate(tmp_path, [_finding(category="missing-error-path")], expect=1)["findings"]


# ============ ninth review pass ===================================================

def test_a_quote_citation_with_a_section_anchor_still_checks_the_quote(tmp_path):
    """A ref naming no file excused the quote entirely, so a fabricated one survived."""
    doc = _touch(tmp_path / "spec.md", "# Spec\n\nreal text here\n")
    bad = _finding(evidence=[{"kind": "quote", "ref": "spec.md#3",
                              "quote": "THIS TEXT APPEARS NOWHERE"}])
    result = gate(tmp_path, [bad], expect=0,
                  extra=("--repo-root", str(tmp_path)))
    assert result["findings"] == []
    assert result["suppressed"][0]["reason"] == "falsified"
    assert doc.exists()


def test_a_quote_citation_with_an_anchor_passes_when_the_quote_is_real(tmp_path):
    _touch(tmp_path / "spec.md", "# Spec\n\nthe real sentence\n")
    good = _finding(evidence=[{"kind": "quote", "ref": "spec.md#intro",
                               "quote": "the real sentence"}])
    assert gate(tmp_path, [good], expect=1,
                extra=("--repo-root", str(tmp_path)))["findings"]


def test_an_anchor_naming_no_resolvable_file_is_unverifiable_not_falsified(tmp_path):
    """We cannot check it either way; killing it would suppress real defects."""
    f = _finding(severity="MEDIUM",
                 evidence=[{"kind": "quote", "ref": "#section-3", "quote": "anything"}])
    assert gate(tmp_path, [f], expect=1,
                extra=("--repo-root", str(tmp_path)))["findings"]


def test_a_markdown_link_carrying_a_title_is_still_resolved(tmp_path):
    """[d](./nope.md "Title") matched nothing, so a missing target passed silently."""
    doc = _touch(tmp_path / "t.md", 'See [d](./nope.md "The Title").\n')
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert any("nope.md" in f["evidence"][0]["ref"] for f in result["findings"])


def test_a_titled_link_to_a_real_file_produces_no_finding(tmp_path):
    _touch(tmp_path / "real.md", "x\n")
    doc = _touch(tmp_path / "t.md", 'See [d](./real.md "The Title").\n')
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


def test_a_bare_installed_executable_is_not_a_false_unresolved_symbol(tmp_path):
    """`pytest` in a repo that never mentions it produced a false HIGH."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    doc = _touch(tmp_path / "doc.md", "Run `python3` to verify.\n")
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


def test_a_bare_uninstalled_unknown_token_is_still_reported(tmp_path):
    """The fix must not blanket-excuse every single-word token."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    doc = _touch(tmp_path / "doc.md", "Call `someFunctionNobodyDefined` first.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert result["findings"]


# ============ tenth review pass ===================================================

def test_a_backticked_path_containing_spaces_is_still_a_reference(tmp_path):
    """A space meant 'command or prose', so a path with a space left the scan."""
    doc = _touch(tmp_path / "doc.md", "See `docs/my notes/missing.md` for detail.\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert any("my notes" in f["evidence"][0]["ref"] for f in result["findings"])


def test_prose_with_spaces_is_still_not_treated_as_a_reference(tmp_path):
    """The fix must not reclassify ordinary backticked prose as a path."""
    doc = _touch(tmp_path / "doc.md", "The `review loop` runs twice.\n")
    assert prepass("--profile", "prose-claim", "--target", str(doc),
                   "--repo-root", str(tmp_path))["findings"] == []


def test_an_angle_bracket_link_destination_with_spaces_is_extracted(tmp_path):
    doc = _touch(tmp_path / "doc.md", "See [d](<missing file.md>).\n")
    result = prepass("--profile", "prose-claim", "--target", str(doc),
                     "--repo-root", str(tmp_path), expect=1)
    assert any("missing file.md" in f["evidence"][0]["ref"] for f in result["findings"])


def test_absence_evidence_omitting_output_is_rejected(tmp_path):
    """Omitting it asserted nothing, yet read as 'the search came back empty'."""
    f = _finding(evidence=[{"kind": "absence", "command": "grep -r zzz .", "ref": "skills/"}])
    proc = run_ar("gate", *_inputs(tmp_path, [f]))
    assert proc.returncode == 2
    assert "output" in proc.stderr


def test_absence_evidence_with_an_empty_output_field_is_accepted(tmp_path):
    """Empty output IS the claim for an absence — the one place empty is content."""
    f = _finding(evidence=[{"kind": "absence", "command": "grep -r zzz .",
                            "ref": "tests/", "output": ""}])
    assert gate(tmp_path, [f], expect=1)["findings"]


@pytest.mark.parametrize("patch", [{"not": "a diff"}, 42, ["a"], True])
def test_a_patch_that_is_not_a_diff_string_or_null_is_rejected(patch, tmp_path):
    proc = run_ar("gate", *_inputs(tmp_path, [_finding(patch=patch)]))
    assert proc.returncode == 2
    assert "patch" in proc.stderr


def test_a_string_patch_and_a_null_patch_are_both_accepted(tmp_path):
    assert gate(tmp_path, [_finding(patch=None)], expect=1)["findings"]
    assert gate(tmp_path, [_finding(patch="--- a\n+++ b\n")], expect=1)["findings"]
