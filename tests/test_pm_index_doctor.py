from __future__ import annotations

from pathlib import Path

import pm

from .conftest import run_script


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
    assert "BUGS 0/0 open" in out
    assert "DEFERRED 0/0 open" in out
    assert "TEST 0/0 open" in out
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in out
    assert "doctor:" not in out


def test_index_counts_open_entries_as_unplaced(initialized_project: Path) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    append_defer(initialized_project / "DEFERRED.md", 1, "beta", priority="P2", deferred="2026-08-01")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS 1/1 open" in out
    assert "DEFERRED 1/1 open" in out
    assert "2 unplaced (2 ready, 0 blocked, 0 malformed)" in out


def test_index_reports_malformed_heading_in_denominator_and_unplaced(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1:\n- **Severity**: high\n")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS 0/1 open" in out
    assert "1 unplaced (0 ready, 0 blocked, 1 malformed)" in out
    assert "doctor: 1 findings" in out


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
    assert "BUGS 0/0 open" not in out


# --- --next --------------------------------------------------------------


def test_next_sorts_by_urgency_then_age(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    append_bug(bugs, 1, "low sev old", severity="low", observed="2026-01-01")
    append_bug(bugs, 2, "critical new", severity="critical", observed="2026-08-01")
    defers = initialized_project / "DEFERRED.md"
    append_defer(defers, 1, "high pri", priority="P2", deferred="2026-08-01")
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


# --- internal helpers ------------------------------------------------------


def test_urgency_is_total_for_a_spec_with_no_urgency_table() -> None:
    assert pm._urgency(pm.PROPOSALS, {}) == 2
    assert pm._urgency(pm.PROPOSALS, {"Anything": "value"}) == 2
