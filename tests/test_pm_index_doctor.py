from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import pm

from .conftest import BIN_DIR, HOOKS_DIR, run_script


def append_bug(path: Path, entry_id: int, title: str, severity: str | None = None, observed: str | None = None) -> None:
    lines = [f"\n## BUG-{entry_id}: {title}"]
    if observed:
        lines.append(f"- **Observed**: {observed}")
    if severity:
        lines.append(f"- **Severity**: {severity}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def append_defer(path: Path, entry_id: int, title: str, priority: str | None = None, deferred: str | None = None) -> None:
    lines = [f"\n## DEFER-{entry_id}: {title}"]
    if deferred:
        lines.append(f"- **Deferred**: {deferred}")
    if priority:
        lines.append(f"- **Priority**: {priority}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def append_test(path: Path, entry_id: int, title: str, priority: str | None = None) -> None:
    lines = [f"\n## TEST-{entry_id}: {title}"]
    if priority:
        lines.append(f"- **Priority**: {priority}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def append_proposal(path: Path, entry_id: int, title: str) -> None:
    path.write_text(path.read_text() + f"\n## PROPOSAL-{entry_id}: {title}\n- **Context**: x\n")


# --- --index -----------------------------------------------------------


def test_index_reports_uninitialized_project(project_dir: Path) -> None:
    result = run_script("pm.py", "--index", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    assert "[quirk:pm]" in result.stdout
    assert "/quirk:artifacts:init" in result.stdout


def test_index_empty_project_shows_zero_counts(initialized_project: Path) -> None:
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS 0 open" in out
    assert "DEFERRED 0 open" in out
    assert "TEST 0 open" in out
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in out
    assert "doctor:" not in out
    assert "in_progress" not in out
    assert "delivered" not in out
    assert "closed" not in out


def test_index_counts_open_entries_as_unplaced(initialized_project: Path) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    append_defer(initialized_project / "DEFERRED.md", 1, "beta", priority="P2", deferred="2026-08-01")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS 1 open" in out
    assert "DEFERRED 1 open" in out
    assert "2 unplaced (2 ready, 0 blocked, 0 malformed)" in out


def test_index_reports_a_blocked_open_entry_inline_on_its_file_segment(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 2, "blocker", severity="high", observed="2026-08-01")
    _bug_with_fields(bugs, 1, "waits on its blocker", ("Blocked by", "BUG-2"))
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 2 open (1 blocked)" in result.stdout


def test_index_excludes_malformed_headings_from_open_but_counts_them_unplaced(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1:\n- **Severity**: high\n")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS 0 open" in out
    assert "1 unplaced (0 ready, 0 blocked, 1 malformed)" in out
    assert "doctor: 1 findings" in out
    assert "run /quirk:pm:status for details" in out


def test_index_skips_file_that_fails_to_parse(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md: parse error, skipping" in out
    assert "BUGS" not in out.split("parse error, skipping")[1].split("\n")[0]


def test_index_skips_file_over_the_size_bound(initialized_project: Path, monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "10")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md: exceeds 10 bytes, skipping" in out
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in out
    assert "BUGS" not in out.splitlines()[0]


def test_index_ignores_non_positive_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    for bad_value in ("-1", "0"):
        monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", bad_value)
        result = run_script("pm.py", "--index", cwd=initialized_project)
        assert result.returncode == 0, result.stderr
        out = result.stdout
        assert "BUGS 1 open" in out, out
        assert "1 unplaced (1 ready, 0 blocked, 0 malformed)" in out
        assert "exceeds" not in out


def test_index_honors_a_raised_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 1 open" in result.stdout


# --- --index: bounded in_progress / delivered / closed sections ------------


def test_index_renders_in_progress_and_delivered_sections(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    defers = initialized_project / "DEFERRED.md"
    _bug_with_fields(
        bugs, 7, "auth fails on safari",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
    )
    _bug_with_fields(
        bugs, 2, "auth cookie fix",
        ("Status", _status_line(state="delivered", date="2026-08-04", attempt=1, commit="a" * 40)),
    )
    _entry_with_fields(
        defers, "DEFER", 3, "rethink session storage",
        ("Status", _status_line(state="in_progress", date="2026-07-20", attempt=1)),
    )
    out = pm.render_index(initialized_project, today="2026-08-05")

    assert "[quirk:pm] in_progress (2 shown / 2 total):" in out
    assert "  - BUG-7 auth fails on safari — started 2026-08-01 (4d ago)" in out
    assert "  - DEFER-3 rethink session storage — started 2026-07-20 (16d ago) — STALLED" in out
    assert "worktree:" not in out  # Phase 3 field, never written by Phase 2's --here-only start

    assert "[quirk:pm] delivered, awaiting integration (1 shown / 1 total):" in out
    assert "  - BUG-2 auth cookie fix — delivered 2026-08-04 (1d ago)" in out


def test_index_orders_in_progress_oldest_first(initialized_project: Path) -> None:
    """A bounded list should trim the freshest entries first, not the stalest — so when the cap
    bites it's the newest (least urgent to see) work that gets folded into the overflow line."""
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "newer", ("Status", _status_line(state="in_progress", date="2026-08-04", attempt=1))
    )
    _bug_with_fields(
        bugs, 2, "older", ("Status", _status_line(state="in_progress", date="2026-07-01", attempt=1))
    )
    out = pm.render_index(initialized_project, today="2026-08-05")
    assert out.index("BUG-2 older") < out.index("BUG-1 newer")


def test_index_caps_in_progress_at_ten(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    for i in range(1, 12):
        _bug_with_fields(
            bugs, i, f"bug {i}",
            ("Status", _status_line(state="in_progress", date=f"2026-07-{i:02d}", attempt=1)),
        )
    out = pm.render_index(initialized_project, today="2026-08-01")
    assert "[quirk:pm] in_progress (10 shown / 11 total):" in out
    shown_rows = [line for line in out.splitlines() if line.startswith("  - BUG-")]
    assert len(shown_rows) == 10
    assert "…and 1 more" in out


def test_index_caps_delivered_at_five(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    for i in range(1, 7):
        _bug_with_fields(
            bugs, i, f"bug {i}",
            ("Status", _status_line(
                state="delivered", date=f"2026-07-{i:02d}", attempt=1, commit="a" * 40
            )),
        )
    out = pm.render_index(initialized_project, today="2026-08-01")
    assert "[quirk:pm] delivered, awaiting integration (5 shown / 6 total):" in out
    assert "…and 1 more" in out


def test_index_truncates_titles_at_sixty_characters(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    long_title = "T" * 70
    _bug_with_fields(
        bugs, 1, long_title,
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
    )
    out = pm.render_index(initialized_project, today="2026-08-01")
    assert f"- BUG-1 {'T' * 60} —" in out
    assert "T" * 61 not in out


def test_index_omits_lifecycle_sections_when_only_open_entries_exist(initialized_project: Path) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    out = pm.render_index(initialized_project, today="2026-08-05")
    assert "in_progress" not in out
    assert "delivered" not in out
    assert "closed" not in out


def test_index_reports_closed_evidence_mix(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "probed closure",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="aaaaaaaa", final_file_hash="bbbbbbbb",
        )),
    )
    _bug_with_fields(
        bugs, 2, "unverified closure",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="b" * 40)),
        ("Probe", _probe_line(verb="none", arg="")),
    )
    out = pm.render_index(initialized_project, today="2026-08-01")
    assert "[quirk:pm] closed 2 total (1 probed, 1 unverified/none)" in out


def test_index_reports_a_blocked_open_entry_inline_across_files(initialized_project: Path) -> None:
    """`Blocked by` can name an ID in a different ledger; the per-file blocked count must still
    catch it, since readiness is computed over the whole cross-ledger world, not one file."""
    bugs = initialized_project / "BUGS.md"
    defers = initialized_project / "DEFERRED.md"
    append_defer(defers, 1, "blocker", priority="P2", deferred="2026-08-01")
    _bug_with_fields(bugs, 1, "waits on a defer", ("Blocked by", "DEFER-1"))
    out = pm.render_index(initialized_project, today="2026-08-01")
    assert "BUGS 1 open (1 blocked)" in out


def test_index_finding_count_matches_doctor_finding_count(initialized_project: Path) -> None:
    """`--index`'s summary count and `--doctor`'s actual list must never disagree, since `status`
    prints them back to back in one message."""
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(bugs, 1, "waits on nothing real", ("Blocked by", "BUG-999"))
    _bug_with_fields(
        bugs, 2, "stalled", ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1))
    )
    index_out = pm.render_index(initialized_project, today="2026-08-20")
    doctor_out = pm.render_doctor(initialized_project, today="2026-08-20")

    reported = int(index_out.split("doctor: ")[1].split(" findings")[0])
    assert reported == len(doctor_out.splitlines())
    assert reported == 2


def test_index_skips_file_that_fails_to_parse_but_still_names_other_files_work(
    initialized_project: Path,
) -> None:
    """A parse error in one ledger must not silence the bounded sections built from the others."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    defers = initialized_project / "DEFERRED.md"
    _entry_with_fields(
        defers, "DEFER", 1, "still visible",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
    )
    out = pm.render_index(initialized_project, today="2026-08-05")
    assert "BUGS.md: parse error, skipping" in out
    assert "still visible" in out
    assert "[quirk:pm] in_progress (1 shown / 1 total):" in out


# --- SessionStart hook: exit-0 guarantee ------------------------------------


def test_hook_falls_back_when_pm_index_raises(initialized_project: Path, tmp_path: Path) -> None:
    """The hook's exit-0 guarantee must hold even when pm.py --index itself raises — simulated
    via a broken fixture project standing in for a corrupted plugin install."""
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    broken_plugin_root = tmp_path / "broken_plugin"
    (broken_plugin_root / "bin").mkdir(parents=True)
    (broken_plugin_root / "bin" / "pm.py").write_text("raise RuntimeError('simulated crash')\n")

    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(initialized_project),
        "CLAUDE_PLUGIN_ROOT": str(broken_plugin_root),
    }
    result = subprocess.run(
        ["bash", str(HOOKS_DIR / "load_artifact_tail.sh")], env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "[quirk:pm] index unavailable"
    assert "Traceback" not in result.stdout
    assert "RuntimeError" not in result.stdout


def test_hook_surfaces_bounded_index_output_through_pm(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "auth fails on safari",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
    )
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(initialized_project)}
    result = subprocess.run(
        ["bash", str(HOOKS_DIR / "load_artifact_tail.sh")], env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "auth fails on safari" in result.stdout


# --- --next --------------------------------------------------------------


def test_next_sorts_by_urgency_then_age(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 1, "low sev old", severity="low", observed="2026-01-01")
    append_bug(bugs, 2, "critical new", severity="critical", observed="2026-08-01")
    defers = initialized_project / "DEFERRED.md"
    append_defer(defers, 1, "high pri", priority="P2", deferred="2026-08-01")
    # BUG-1 needs a milestone to be eligible at all: low urgency in no milestone is
    # deliberately absent from the shortlist. Placing it also pins the escape hatch —
    # the two unroadmapped entries rank -1 and must still sort ahead of it.
    (initialized_project / "ROADMAP.md").write_text(
        "# ROADMAP\n\n## Milestone: Cleanup\n- BUG-1\n", encoding="utf-8"
    )
    result = run_script("pm.py", "--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    idx_bug2 = out.index("BUG-2")
    idx_defer1 = out.index("DEFER-1")
    idx_bug1 = out.index("BUG-1")
    assert idx_bug2 < idx_defer1 < idx_bug1


def test_next_treats_missing_date_as_oldest(initialized_project: Path) -> None:
    defers = initialized_project / "DEFERRED.md"
    append_defer(defers, 1, "dated", priority="P2", deferred="2026-08-01")
    tests_file = initialized_project / "TEST_BACKLOG.md"
    append_test(tests_file, 1, "undated", priority="P2")
    result = run_script("pm.py", "--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.index("TEST-1") < out.index("DEFER-1")


def test_next_excludes_proposals(initialized_project: Path) -> None:
    append_proposal(initialized_project / "proposals.md", 1, "should never appear")
    append_bug(initialized_project / "BUGS.md", 1, "real work", severity="high", observed="2026-08-01")
    result = run_script("pm.py", "--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "PROPOSAL" not in result.stdout


def test_next_reports_no_ready_candidates_when_empty(initialized_project: Path) -> None:
    result = run_script("pm.py", "--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "no ready candidates" in out.lower()
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in out


def test_next_caps_at_five(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    for i in range(1, 8):
        append_bug(bugs, i, f"bug {i}", severity="high", observed=f"2026-08-0{i % 9 + 1}")
    result = run_script("pm.py", "--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    shown = [line for line in out.splitlines() if line.strip().startswith("- BUG-")]
    assert len(shown) == 5
    assert "7 unplaced (7 ready, 0 blocked, 0 malformed)" in out


# --- --doctor --------------------------------------------------------------


def test_doctor_reports_no_findings(initialized_project: Path) -> None:
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "no findings" in result.stdout.lower()


def test_doctor_reports_malformed_heading(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1:\n- **Severity**: high\n")
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "MALFORMED_HEADING" in out
    assert "BUG-1" in out
    assert "BUGS.md" in out


def test_doctor_reports_duplicate_id(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + (
        "\n## BUG-5: first\n- **Severity**: high\n"
        "\n## BUG-5: second\n- **Severity**: low\n"
    ))
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "DUPLICATE_ID" in out
    assert "BUG-5" in out


def test_doctor_reports_duplicate_id_when_one_heading_is_malformed(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + (
        "\n## BUG-7: the real one\n- **Severity**: high\n"
        "\n## BUG-7:\n- **Severity**: critical\n"
    ))
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "MALFORMED_HEADING" in out
    assert "DUPLICATE_ID" in out
    assert out.count("BUG-7") >= 2


def test_doctor_reports_duplicate_id_for_two_malformed_headings(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + (
        "\n## BUG-9:\n- **Severity**: high\n"
        "\n## BUG-9:\n- **Severity**: low\n"
    ))
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.count("MALFORMED_HEADING") == 2
    assert out.count("DUPLICATE_ID") == 1
    assert "BUG-9" in out


def test_doctor_exits_zero_with_findings(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1:\n- **Severity**: high\n")
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0


def test_doctor_scans_proposals_file_too(initialized_project: Path) -> None:
    proposals = initialized_project / "proposals.md"
    proposals.write_text(proposals.read_text() + "\n## PROPOSAL-1:\n- **Context**: x\n")
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "MALFORMED_HEADING" in out
    assert "PROPOSAL-1" in out


# --- doctor: catalog rows already implemented, reached here too ------------
#
# tech.md:1894-1898 requires every row of the doctor findings catalog be reached by a fixture in
# this file specifically, even where another test file already exercises the same code path.


def _status_line(**kwargs) -> str:
    return pm.render_status(pm.StatusField(**kwargs))


def _probe_line(**kwargs) -> str:
    return pm.render_probe(pm.ProbeField(**kwargs))


def _verify_line(**kwargs) -> str:
    return pm.render_verify(pm.VerifyField(**kwargs))


def _entry_with_fields(
    path: Path, header: str, entry_id: int, title: str, *field_lines: tuple[str, str]
) -> None:
    """Append a `{header}-N` entry whose field lines are given verbatim (label, value) pairs —
    allows a duplicated label, unlike a kwargs-based helper.
    """
    body = "\n".join(f"- **{label}**: {value}" for label, value in field_lines)
    path.write_text(path.read_text() + f"\n## {header}-{entry_id}: {title}\n{body}\n")


def _bug_with_fields(path: Path, entry_id: int, title: str, *field_lines: tuple[str, str]) -> None:
    _entry_with_fields(path, "BUG", entry_id, title, *field_lines)


def test_doctor_reports_dangling_blocked_by(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(bugs, 1, "waits on nothing real", ("Blocked by", "BUG-999"))
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "DANGLING" in out
    assert "BUG-999" in out


def test_doctor_reports_blocked_by_proposal(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(bugs, 1, "waits on a proposal", ("Blocked by", "PROPOSAL-1"))
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "BLOCKED_BY_PROPOSAL" in out


def test_doctor_reports_blocked_by_duplicate(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 2, "blocker", severity="high", observed="2026-08-01")
    _bug_with_fields(bugs, 1, "double-lists its blocker", ("Blocked by", "BUG-2, BUG-2"))
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "BLOCKED_BY_DUPLICATE" in out


def test_doctor_reports_cycle(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(bugs, 1, "cycle a", ("Blocked by", "BUG-2"))
    _bug_with_fields(bugs, 2, "cycle b", ("Blocked by", "BUG-1"))
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "CYCLE" in out


def test_doctor_reports_dangling_roadmap_ref(initialized_project: Path) -> None:
    (initialized_project / "ROADMAP.md").write_text("# ROADMAP\n\n## Milestone: A\n- BUG-999\n")
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "DANGLING_ROADMAP_REF" in out
    assert "BUG-999" in out


def test_doctor_reports_proposal_in_roadmap(initialized_project: Path) -> None:
    (initialized_project / "ROADMAP.md").write_text("# ROADMAP\n\n## Milestone: A\n- PROPOSAL-1\n")
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "PROPOSAL_IN_ROADMAP" in out


def test_doctor_reports_roadmap_line_malformed(initialized_project: Path) -> None:
    (initialized_project / "ROADMAP.md").write_text(
        "# ROADMAP\n\n## Milestone: A\nnot a valid member line\n"
    )
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "ROADMAP_LINE_MALFORMED" in out


def test_doctor_reports_duplicate_membership(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 1, "in two milestones", severity="high", observed="2026-08-01")
    (initialized_project / "ROADMAP.md").write_text(
        "# ROADMAP\n\n## Milestone: A\n- BUG-1\n\n## Milestone: B\n- BUG-1\n"
    )
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "DUPLICATE_MEMBERSHIP" in out


def test_doctor_reports_duplicate_milestone_name(initialized_project: Path) -> None:
    (initialized_project / "ROADMAP.md").write_text("# ROADMAP\n\n## Milestone: A\n\n## Milestone: A\n")
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "DUPLICATE_MILESTONE_NAME" in out


# --- doctor: lifecycle findings ---------------------------------------------


def test_doctor_reports_stalled_in_progress_entry(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "stuck", ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1))
    )
    out = pm.render_doctor(initialized_project, today="2026-08-10")
    assert "STALLED" in out
    assert "BUG-1" in out


def test_doctor_does_not_flag_in_progress_entry_at_exactly_the_stall_boundary(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "fresh", ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1))
    )
    # exactly QUIRK_PM_STALL_DAYS (7) days old: STALLED requires *more than* the threshold
    out = pm.render_doctor(initialized_project, today="2026-08-08")
    assert "STALLED" not in out


def test_doctor_honors_a_custom_stall_days_env(initialized_project: Path, monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_STALL_DAYS", "2")
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "stuck", ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1))
    )
    out = pm.render_doctor(initialized_project, today="2026-08-04")  # 3 days old
    assert "STALLED" in out


def test_doctor_reports_awaiting_integration_under_the_undetermined_threshold(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "shipped",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-14")  # 13 days
    assert "AWAITING_INTEGRATION" in out
    assert "13 days" in out
    assert "UNDETERMINED" not in out


def test_doctor_reports_undetermined_at_the_threshold(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "shipped",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
    )
    # AWAITING_INTEGRATION and UNDETERMINED are mutually exclusive, chosen by age: exactly at
    # QUIRK_PM_UNDETERMINED_AFTER_DAYS (14) must already be UNDETERMINED, never both.
    out = pm.render_doctor(initialized_project, today="2026-08-15")  # 14 days
    assert "UNDETERMINED" in out
    assert "AWAITING_INTEGRATION" not in out


def test_doctor_reports_malformed_status_field(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(bugs, 1, "broken", ("Status", "bogus"))
    out = pm.render_doctor(initialized_project)
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "BUG-1" in out
    assert "Status" in out


def test_doctor_reports_malformed_probe_field(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "broken probe",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
        ("Probe", "bogus"),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "Probe" in out


def test_doctor_reports_malformed_verify_field(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "broken verify",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="a" * 40)),
        ("Verify", "not-a-date"),
    )
    out = pm.render_doctor(initialized_project)
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "Verify" in out


def test_doctor_reports_malformed_status_for_an_impossible_calendar_date(
    initialized_project: Path,
) -> None:
    # "2026-02-30" matches the YYYY-MM-DD shape but is not a real date: must not crash and must
    # not be silently treated as infinitely old (no STALLED).
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "bad date", ("Status", _status_line(state="in_progress", date="2026-02-30", attempt=1))
    )
    out = pm.render_doctor(initialized_project, today="2026-08-10")
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "STALLED" not in out


def test_doctor_reports_malformed_status_for_an_impossible_calendar_date_on_a_terminal_state(
    initialized_project: Path,
) -> None:
    # _status_age_findings only runs for in_progress/delivered, so the calendar-date check must
    # not live there — a closed entry's impossible date must still be caught.
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "bad closed date",
        ("Status", _status_line(state="closed", date="2026-02-30", attempt=1, integrated="a" * 40)),
    )
    out = pm.render_doctor(initialized_project)
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "BUG-1" in out


def test_doctor_reports_malformed_verify_for_an_impossible_calendar_date(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "bad verify date",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="a" * 40)),
        ("Verify", _verify_line(date="2026-02-30", integration_ref="a" * 40, probe="pass")),
    )
    out = pm.render_doctor(initialized_project)
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "Verify" in out


def test_doctor_reports_a_present_but_empty_status_field(initialized_project: Path) -> None:
    """A `Status` field line with nothing after the colon must not be silently read as the
    ordinary never-started `open` state — the label was written, so a missing value is
    corruption, and must surface as a finding rather than vanish."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: hollow status\n- **Status**:\n")
    out = pm.render_doctor(initialized_project)
    assert "MALFORMED_LIFECYCLE_FIELD" in out
    assert "BUG-1" in out
    assert "Status" in out


def test_doctor_reports_duplicate_status_field(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "dup status",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
        ("Status", _status_line(state="in_progress", date="2026-08-02", attempt=1)),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-02")
    assert "DUPLICATE_LIFECYCLE_FIELD" in out
    assert "Status" in out


def test_doctor_does_not_flag_a_fenced_status_example_as_duplicate(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    live_status = _status_line(state="in_progress", date="2026-08-01", attempt=1)
    fenced_status = _status_line(state="delivered", date="2026-08-02", attempt=1, commit="a" * 40)
    bugs.write_text(
        bugs.read_text()
        + "\n## BUG-1: fenced example\n"
        + f"- **Status**: {live_status}\n"
        + "- **Severity**: high\n"
        + "\n"
        + "Example of the ledger grammar:\n"
        + "```\n"
        + f"- **Status**: {fenced_status}\n"
        + "```\n"
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "DUPLICATE_LIFECYCLE_FIELD" not in out


def test_doctor_reports_unverified_delivery_for_probe_none(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "no evidence",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
        ("Probe", _probe_line(verb="none", arg="")),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "UNVERIFIED_DELIVERY" in out


def test_doctor_does_not_flag_unverified_delivery_when_probe_is_not_none(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "has evidence",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="aaaaaaaa", final_file_hash="bbbbbbbb",
        )),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "UNVERIFIED_DELIVERY" not in out


def test_doctor_reports_probe_spec_changed(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "spec drift",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="cccccccc", final_file_hash="bbbbbbbb",
        )),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "PROBE_SPEC_CHANGED" in out
    assert "PROBE_FILE_CHANGED" not in out


def test_doctor_reports_probe_file_changed(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "file drift",
        ("Status", _status_line(state="delivered", date="2026-08-01", attempt=1, commit="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="aaaaaaaa", final_file_hash="dddddddd",
        )),
    )
    out = pm.render_doctor(initialized_project, today="2026-08-01")
    assert "PROBE_FILE_CHANGED" in out
    assert "PROBE_SPEC_CHANGED" not in out


def test_doctor_reports_post_merge_probe_regression_from_disk_in_a_separate_process(
    initialized_project: Path,
) -> None:
    """Regression fixture for the defect where a `--verify` result existed only in the memory of
    the process that computed it (tech.md:1917): write the `Verify` field directly to disk, then
    read it back via a freshly spawned `pm.py --doctor` process.
    """
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "regressed after merge",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="aaaaaaaa", final_file_hash="bbbbbbbb",
        )),
        ("Verify", _verify_line(date="2026-08-02", integration_ref="origin/main", probe="fail")),
    )
    result = run_script("pm.py", "--doctor", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "POST_MERGE_PROBE_REGRESSION" in result.stdout
    assert "BUG-1" in result.stdout


def test_doctor_does_not_flag_post_merge_probe_regression_when_verify_passed(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    _bug_with_fields(
        bugs, 1, "verified clean",
        ("Status", _status_line(state="closed", date="2026-08-01", attempt=1, integrated="a" * 40)),
        ("Probe", _probe_line(
            verb="test", arg="tests/test_x.py::test_y", baseline="fail",
            spec_hash="aaaaaaaa", file_hash="bbbbbbbb",
            final="pass", final_spec_hash="aaaaaaaa", final_file_hash="bbbbbbbb",
        )),
        ("Verify", _verify_line(date="2026-08-02", integration_ref="origin/main", probe="pass")),
    )
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "POST_MERGE_PROBE_REGRESSION" not in out


# --- doctor: severity grouping -----------------------------------------------


def test_doctor_groups_findings_by_severity_in_order(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 2, "blocker", severity="high", observed="2026-08-01")
    _bug_with_fields(bugs, 3, "dangling", ("Blocked by", "BUG-999"))  # warning
    _bug_with_fields(bugs, 4, "dup blocker", ("Blocked by", "BUG-2, BUG-2"))  # notice
    _bug_with_fields(
        bugs, 5, "stalled",
        ("Status", _status_line(state="in_progress", date="2026-08-01", attempt=1)),
    )  # informational

    out = pm.render_doctor(initialized_project, today="2026-08-20")
    warning_idx = out.index("DANGLING")
    notice_idx = out.index("BLOCKED_BY_DUPLICATE")
    informational_idx = out.index("STALLED")
    assert warning_idx < notice_idx < informational_idx


def test_doctor_skips_file_that_fails_to_parse_and_still_reports_other_findings(
    initialized_project: Path,
) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    defers = initialized_project / "DEFERRED.md"
    defers.write_text(defers.read_text() + "\n## DEFER-1:\n- **Priority**: P2\n")
    out = run_script("pm.py", "--doctor", cwd=initialized_project).stdout
    assert "BUGS.md: parse error, skipping" in out
    assert "MALFORMED_HEADING" in out
    assert "DEFER-1" in out


# --- _read_and_parse --------------------------------------------------------


def test_read_and_parse_does_not_stat_before_reading(initialized_project: Path, monkeypatch) -> None:
    """A stat-then-read gap would let a concurrent append smuggle bytes past the size
    bound between the two calls; the read must be bounded in a single open+read."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")

    real_stat = Path.stat

    def refuse_stat(self, *args, **kwargs):
        if self == bugs:
            raise AssertionError("_read_and_parse must not stat() before reading")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", refuse_stat)
    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert len(fp.entries) == 1


def test_read_and_parse_gives_a_concrete_reason_for_a_vanished_file(initialized_project: Path) -> None:
    (initialized_project / "BUGS.md").unlink()
    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert fp is None
    assert skip_reason is not None
    assert skip_reason != "None"


def test_read_and_parse_type_checks_the_opened_fd_not_a_separately_stat_path(
    initialized_project: Path, monkeypatch
) -> None:
    """A regular file could be replaced by a FIFO between a stat(path) call and a
    later open(path) call; fstat-ing the fd actually opened closes that gap
    instead of moving it. os.stat must not be used for this check at all."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")

    real_stat = os.stat

    def refuse_stat(path, *args, **kwargs):
        if Path(os.fspath(path)) == bugs:
            raise AssertionError("_read_and_parse must not os.stat() the path separately from opening it")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", refuse_stat)
    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert len(fp.entries) == 1


def test_read_and_parse_closes_the_fd_after_a_successful_read(initialized_project: Path, monkeypatch) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")

    captured: list[int] = []
    real_open = os.open

    def capturing_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        captured.append(fd)
        return fd

    monkeypatch.setattr(os, "open", capturing_open)
    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert captured, "expected _read_and_parse to open the file via os.open"
    with pytest.raises(OSError):
        os.fstat(captured[0])


def test_read_and_parse_closes_the_fd_when_the_target_is_not_a_regular_file(
    initialized_project: Path, monkeypatch
) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.unlink()
    os.mkfifo(bugs)

    captured: list[int] = []
    real_open = os.open

    def capturing_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        captured.append(fd)
        return fd

    monkeypatch.setattr(os, "open", capturing_open)
    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert fp is None
    assert skip_reason == "not a regular file, skipping"
    assert captured, "expected _read_and_parse to open the fifo"
    with pytest.raises(OSError):
        os.fstat(captured[0])


def test_read_and_parse_skips_a_fifo_without_blocking(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.unlink()
    os.mkfifo(bugs)

    outcome: list[tuple] = []
    thread = threading.Thread(
        target=lambda: outcome.append(pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "_read_and_parse blocked opening a FIFO instead of skipping it"

    fp, skip_reason = outcome[0]
    assert fp is None
    assert skip_reason is not None and skip_reason != "None"


def test_index_skips_a_fifo_at_an_artifact_path(initialized_project: Path) -> None:
    # bounded directly (not via run_script) so a regression fails fast instead of
    # hanging the whole suite forever on a blocking FIFO open
    bugs = initialized_project / "BUGS.md"
    bugs.unlink()
    os.mkfifo(bugs)

    try:
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "pm.py"), "--index"],
            cwd=initialized_project,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("pm.py --index blocked opening a FIFO instead of skipping it")

    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md: not a regular file, skipping" in out
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in out
    assert "BUGS" not in out.splitlines()[0]


def test_max_file_bytes_falls_back_when_override_is_too_large_to_use(monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999999999999999")
    assert pm._max_file_bytes() == pm.DEFAULT_MAX_FILE_BYTES


def test_index_does_not_crash_on_an_unusably_large_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999999999999999")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 1 open" in result.stdout


def test_max_file_bytes_honors_the_top_of_the_usable_range(monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(pm.MAX_USABLE_FILE_BYTES))
    assert pm._max_file_bytes() == pm.MAX_USABLE_FILE_BYTES


def test_max_file_bytes_falls_back_just_above_the_usable_range(monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(pm.MAX_USABLE_FILE_BYTES + 1))
    assert pm._max_file_bytes() == pm.DEFAULT_MAX_FILE_BYTES


def test_index_does_not_crash_at_the_top_of_the_usable_max_file_bytes_range(
    initialized_project: Path, monkeypatch
) -> None:
    """max_bytes + 1 at this boundary must be a read() size that never raises
    OverflowError, unlike the old sys.maxsize-relative bound it replaced."""
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(pm.MAX_USABLE_FILE_BYTES))
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 1 open" in result.stdout


@pytest.mark.parametrize("value", [sys.maxsize - 1, sys.maxsize])
def test_index_does_not_crash_near_sys_maxsize(initialized_project: Path, monkeypatch, value: int) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(value))
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    # far above MAX_USABLE_FILE_BYTES, so this falls back to the default bound
    assert "BUGS 1 open" in result.stdout


def test_read_and_parse_falls_back_to_locale_encoding_when_utf8_fails(
    initialized_project: Path, monkeypatch
) -> None:
    bugs = initialized_project / "BUGS.md"
    # 'é' as a lone latin-1 byte (0xE9) is not a valid utf-8 continuation sequence
    entry = "\n## BUG-1: caf\xe9 bug\n- **Severity**: high\n".encode("latin-1")
    bugs.write_bytes(bugs.read_bytes() + entry)
    monkeypatch.setattr(pm.locale, "getpreferredencoding", lambda do_setlocale=True: "latin-1")

    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert len(fp.entries) == 1


def test_read_and_parse_still_skips_content_invalid_under_both_encodings(
    initialized_project: Path, monkeypatch
) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    monkeypatch.setattr(pm.locale, "getpreferredencoding", lambda do_setlocale=True: "ascii")

    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert fp is None
    assert skip_reason == "parse error, skipping"


@pytest.mark.parametrize("platform_encoding", ["UTF-8", "utf8", "utf_8", "UTF8"])
def test_read_and_parse_skips_the_encoding_fallback_when_the_platform_is_already_utf8(
    initialized_project: Path, monkeypatch, platform_encoding: str
) -> None:
    """Retrying a failed strict-utf-8 decode under an alias of the same codec
    (UTF-8, utf8, utf_8, ...) can only fail identically, so the platform
    encoding must be compared by canonical codec name via codecs.lookup, not
    by string equality, and the comparison must gate the fallback decode."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_bytes(b"\xff\xfe\x00\x01not utf-8")

    lookups: list[str] = []
    real_lookup = pm.codecs.lookup

    def spying_lookup(name):
        lookups.append(name)
        return real_lookup(name)

    monkeypatch.setattr(pm.codecs, "lookup", spying_lookup)
    monkeypatch.setattr(pm.locale, "getpreferredencoding", lambda do_setlocale=True: platform_encoding)

    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert fp is None
    assert skip_reason == "parse error, skipping"
    assert platform_encoding in lookups, "expected the platform encoding to be compared via codecs.lookup"


def test_read_and_parse_prefers_the_platform_encoding_when_both_decode_cleanly(
    initialized_project: Path, monkeypatch
) -> None:
    """artifact_append.py writes with the platform default codec, not utf-8. When
    bytes happen to be valid under both codecs, decoding must match what that
    writer actually produced instead of guessing utf-8 first."""
    bugs = initialized_project / "BUGS.md"
    # b"\xc3\xa9" is the utf-8 encoding of 'é'; every byte also decodes cleanly
    # under latin-1, just to different (mojibake) characters
    entry = b"\n## BUG-1: caf\xc3\xa9 bug\n- **Severity**: high\n"
    bugs.write_bytes(bugs.read_bytes() + entry)
    monkeypatch.setattr(pm.locale, "getpreferredencoding", lambda do_setlocale=True: "latin-1")

    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert fp.entries[0].title == "caf\xc3\xa9 bug"


def test_read_and_parse_works_when_o_nonblock_is_unavailable(initialized_project: Path, monkeypatch) -> None:
    """os.O_NONBLOCK is Unix-only; Windows has no POSIX FIFOs and does not
    define it, so the open flags must degrade to a no-op there instead of
    raising AttributeError before any OSError handler can run."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")
    monkeypatch.delattr(os, "O_NONBLOCK", raising=False)

    fp, skip_reason = pm._read_and_parse(initialized_project, pm.BACKLOG_FILES[0])
    assert skip_reason is None
    assert fp is not None
    assert len(fp.entries) == 1


def test_index_never_renders_the_none_skip_reason(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setattr(pm, "_read_and_parse", lambda project, spec: (None, None))
    assert "None" not in pm.render_index(initialized_project)


def test_next_never_renders_the_none_skip_reason(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setattr(pm, "_read_and_parse", lambda project, spec: (None, None))
    assert "None" not in pm.render_next(initialized_project)


def test_doctor_never_renders_the_none_skip_reason(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setattr(pm, "_read_and_parse", lambda project, spec: (None, None))
    assert "None" not in pm.render_doctor(initialized_project)


# --- internal helpers ------------------------------------------------------


def test_urgency_is_total_for_a_spec_with_no_urgency_table() -> None:
    assert pm._urgency(pm.PROPOSALS, {}) == 2
    assert pm._urgency(pm.PROPOSALS, {"Anything": "value"}) == 2


def test_max_file_bytes_treats_non_positive_as_unset(monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "-1")
    assert pm._max_file_bytes() == pm.DEFAULT_MAX_FILE_BYTES
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "0")
    assert pm._max_file_bytes() == pm.DEFAULT_MAX_FILE_BYTES
