from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import pm

from .conftest import BIN_DIR, run_script


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


def test_index_ignores_non_positive_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    for bad_value in ("-1", "0"):
        monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", bad_value)
        result = run_script("pm.py", "--index", cwd=initialized_project)
        assert result.returncode == 0, result.stderr
        out = result.stdout
        assert "BUGS 1/1 open" in out, out
        assert "1 unplaced (1 ready, 0 blocked, 0 malformed)" in out
        assert "exceeds" not in out


def test_index_honors_a_raised_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 1/1 open" in result.stdout


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
    assert "BUGS 0/0 open" not in out


def test_max_file_bytes_falls_back_when_override_is_too_large_to_use(monkeypatch) -> None:
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999999999999999")
    assert pm._max_file_bytes() == pm.DEFAULT_MAX_FILE_BYTES


def test_index_does_not_crash_on_an_unusably_large_max_file_bytes(initialized_project: Path, monkeypatch) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", "99999999999999999999")
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert "BUGS 1/1 open" in result.stdout


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
    assert "BUGS 1/1 open" in result.stdout


@pytest.mark.parametrize("value", [sys.maxsize - 1, sys.maxsize])
def test_index_does_not_crash_near_sys_maxsize(initialized_project: Path, monkeypatch, value: int) -> None:
    append_bug(initialized_project / "BUGS.md", 1, "alpha", severity="high", observed="2026-08-01")
    monkeypatch.setenv("QUIRK_PM_MAX_FILE_BYTES", str(value))
    result = run_script("pm.py", "--index", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    # far above MAX_USABLE_FILE_BYTES, so this falls back to the default bound
    assert "BUGS 1/1 open" in result.stdout


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
