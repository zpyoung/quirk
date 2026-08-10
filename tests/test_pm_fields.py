from __future__ import annotations

import pm


# --- is_valid_free_text ----------------------------------------------------


def test_free_text_rejects_delimiter_sequence() -> None:
    assert pm.is_valid_free_text("folded — into the redesign") is False


def test_free_text_rejects_newline() -> None:
    assert pm.is_valid_free_text("folded into\nthe redesign") is False


def test_free_text_rejects_carriage_return() -> None:
    assert pm.is_valid_free_text("folded into\rthe redesign") is False


def test_free_text_accepts_leading_and_trailing_space() -> None:
    assert pm.is_valid_free_text("  folded into the redesign  ") is True


def test_free_text_accepts_bare_em_dash_with_no_surrounding_spaces() -> None:
    # only the space-emdash-space triple is structural; a tight em dash is ordinary text
    assert pm.is_valid_free_text("before—after") is True


def test_free_text_accepts_lone_ascii_hyphen() -> None:
    assert pm.is_valid_free_text("one - two") is True


# --- Status: render/parse round trip ---------------------------------------


def test_status_parked_open_round_trips() -> None:
    field = pm.StatusField(
        state="open", date="2026-08-07", attempt=1, refused=2, parked="ran out of budget"
    )
    value = pm.render_status(field)
    assert value == "open — 2026-08-07 — attempt 1 — refused 2 — parked: ran out of budget"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_in_progress_round_trips() -> None:
    field = pm.StatusField(state="in_progress", date="2026-08-05", attempt=1)
    value = pm.render_status(field)
    assert value == "in_progress — 2026-08-05 — attempt 1"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_in_progress_after_refusal_round_trips() -> None:
    field = pm.StatusField(state="in_progress", date="2026-08-05", attempt=1, refused=2)
    value = pm.render_status(field)
    assert value == "in_progress — 2026-08-05 — attempt 1 — refused 2"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_delivered_round_trips() -> None:
    sha = "9a3f21c" + "0" * 33
    field = pm.StatusField(state="delivered", date="2026-08-05", attempt=1, commit=sha)
    value = pm.render_status(field)
    assert value == f"delivered — 2026-08-05 — attempt 1 — commit: {sha}"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_delivered_after_refusal_round_trips() -> None:
    sha = "9a3f21c" + "0" * 33
    field = pm.StatusField(state="delivered", date="2026-08-05", attempt=2, refused=3, commit=sha)
    value = pm.render_status(field)
    assert value == f"delivered — 2026-08-05 — attempt 2 — refused 3 — commit: {sha}"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_closed_round_trips() -> None:
    sha = "9a3f21c" + "0" * 33
    field = pm.StatusField(state="closed", date="2026-08-06", attempt=1, integrated=sha)
    value = pm.render_status(field)
    assert value == f"closed — 2026-08-06 — attempt 1 — integrated: {sha}"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_closed_after_refusal_round_trips() -> None:
    sha = "9a3f21c" + "0" * 33
    field = pm.StatusField(state="closed", date="2026-08-06", attempt=2, refused=3, integrated=sha)
    value = pm.render_status(field)
    assert value == f"closed — 2026-08-06 — attempt 2 — refused 3 — integrated: {sha}"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_wontfix_round_trips() -> None:
    field = pm.StatusField(
        state="wontfix", date="2026-08-05", attempt=1, reason="folded into the redesign"
    )
    value = pm.render_status(field)
    assert value == "wontfix — 2026-08-05 — attempt 1 — reason: folded into the redesign"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_superseded_round_trips() -> None:
    field = pm.StatusField(
        state="superseded", date="2026-08-05", attempt=1, by="BUG-12", reason="folded into BUG-12"
    )
    value = pm.render_status(field)
    assert value == "superseded — 2026-08-05 — attempt 1 — by: BUG-12 — reason: folded into BUG-12"
    parsed = pm.parse_status(value)
    assert parsed == field
    assert pm.render_status(parsed) == value


def test_status_wontfix_from_never_started_omits_attempt() -> None:
    field = pm.StatusField(state="wontfix", date="2026-08-05", reason="not worth the maintenance")
    assert field.attempt == 0
    value = pm.render_status(field)
    assert value == "wontfix — 2026-08-05 — reason: not worth the maintenance"
    assert "attempt" not in value
    parsed = pm.parse_status(value)
    assert parsed == field
    assert parsed.attempt == 0
    assert pm.render_status(parsed) == value


def test_status_attempt_zero_never_renders_as_attempt_0() -> None:
    field = pm.StatusField(state="wontfix", date="2026-08-05", reason="never started")
    value = pm.render_status(field)
    assert "attempt 0" not in value


def test_status_refused_and_parked_omitted_when_zero_or_none() -> None:
    field = pm.StatusField(state="in_progress", date="2026-08-05", attempt=1)
    value = pm.render_status(field)
    assert "refused" not in value
    assert "parked" not in value


# --- Status: malformed field detection --------------------------------------


def test_status_short_sha_in_commit_is_malformed() -> None:
    short = "9a3f21c"
    line = f"delivered — 2026-08-05 — attempt 1 — commit: {short}"
    parsed = pm.parse_status(line)
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.raw == line


def test_status_short_sha_in_integrated_is_malformed() -> None:
    short = "9a3f21c"
    line = f"closed — 2026-08-06 — attempt 1 — integrated: {short}"
    parsed = pm.parse_status(line)
    assert isinstance(parsed, pm.MalformedField)


def test_status_full_sha_in_commit_is_accepted() -> None:
    full = "a" * 40
    line = f"delivered — 2026-08-05 — attempt 1 — commit: {full}"
    parsed = pm.parse_status(line)
    assert isinstance(parsed, pm.StatusField)
    assert parsed.commit == full


def test_status_malformed_names_first_failing_segment_state() -> None:
    parsed = pm.parse_status("bogus_state — 2026-08-05 — attempt 1")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "state"


def test_status_malformed_names_first_failing_segment_date() -> None:
    parsed = pm.parse_status("open — not-a-date — attempt 1")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "date"


def test_status_malformed_names_first_failing_segment_not_a_later_one() -> None:
    # both the date AND the commit are bad; the first one (date) must be named, not commit
    parsed = pm.parse_status("delivered — bad-date — attempt 1 — commit: short")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "date"


def test_status_delivered_missing_commit_is_malformed_naming_commit() -> None:
    parsed = pm.parse_status("delivered — 2026-08-05 — attempt 1")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "commit"


def test_status_in_progress_missing_attempt_is_malformed() -> None:
    # in_progress can only exist after a start, so a missing attempt segment is corrupt,
    # not a silently-accepted "never started" reading — that would coerce unknown state to a guess
    parsed = pm.parse_status("in_progress — 2026-08-05")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "attempt"


def test_status_malformed_is_never_coerced_to_open() -> None:
    parsed = pm.parse_status("in_progress — 2026-08-05")
    assert isinstance(parsed, pm.MalformedField)
    assert not hasattr(parsed, "state")


def test_status_trailing_garbage_is_malformed() -> None:
    parsed = pm.parse_status("in_progress — 2026-08-05 — attempt 1 — unexpected junk")
    assert isinstance(parsed, pm.MalformedField)


# --- Status: park preserves counters, next start increments ----------------


def test_park_preserves_counters_and_next_start_increments() -> None:
    parked = pm.StatusField(state="open", date="2026-08-07", attempt=1, refused=2, parked="out of budget")
    value = pm.render_status(parked)
    reparsed = pm.parse_status(value)
    assert reparsed.attempt == 1
    assert reparsed.refused == 2
    assert reparsed.parked == "out of budget"

    restarted = pm.StatusField(
        state="in_progress", date="2026-08-08", attempt=reparsed.attempt + 1, refused=reparsed.refused
    )
    restarted_value = pm.render_status(restarted)
    assert restarted_value == "in_progress — 2026-08-08 — attempt 2 — refused 2"
    assert "parked" not in restarted_value


# --- Probe: render/parse round trip -----------------------------------------


def test_probe_test_verb_at_start_round_trips() -> None:
    spec_hash = pm.hash_probe_spec("test:tests/test_auth.py::test_safari")
    file_hash = pm.hash_file(__file__)  # any readable file stands in for the nodeid's source
    field = pm.ProbeField(
        verb="test",
        arg="tests/test_auth.py::test_safari",
        baseline="fail",
        spec_hash=spec_hash,
        file_hash=file_hash,
    )
    value = pm.render_probe(field)
    assert value == (
        f"test:tests/test_auth.py::test_safari — baseline: fail — "
        f"spec#{spec_hash} file#{file_hash}"
    )
    parsed = pm.parse_probe(value)
    assert parsed == field
    assert pm.render_probe(parsed) == value


def test_probe_test_verb_final_appended_in_place_not_second_line() -> None:
    spec_hash = pm.hash_probe_spec("test:tests/test_auth.py::test_safari")
    file_hash = pm.hash_file(__file__)
    field = pm.ProbeField(
        verb="test",
        arg="tests/test_auth.py::test_safari",
        baseline="fail",
        spec_hash=spec_hash,
        file_hash=file_hash,
        final="pass",
        final_spec_hash=spec_hash,
        final_file_hash=file_hash,
    )
    value = pm.render_probe(field)
    assert "\n" not in value
    assert value == (
        f"test:tests/test_auth.py::test_safari — baseline: fail — "
        f"spec#{spec_hash} file#{file_hash} — final: pass — spec#{spec_hash} file#{file_hash}"
    )
    parsed = pm.parse_probe(value)
    assert parsed == field
    assert pm.render_probe(parsed) == value


def test_probe_baseline_and_final_hashes_are_independent() -> None:
    """A `spec#`/`file#` pair that differs between baseline and final is exactly the case
    `PROBE_SPEC_CHANGED`/`PROBE_FILE_CHANGED` exist to report — it must survive the round trip
    rather than being forced to agree with the other occurrence."""
    field = pm.ProbeField(
        verb="test",
        arg="tests/test_auth.py::test_safari",
        baseline="fail",
        spec_hash="a1b2c3d4",
        file_hash="e5f6a7b8",
        final="pass",
        final_spec_hash="11112222",
        final_file_hash="33334444",
    )
    value = pm.render_probe(field)
    assert value == (
        "test:tests/test_auth.py::test_safari — baseline: fail — "
        "spec#a1b2c3d4 file#e5f6a7b8 — final: pass — spec#11112222 file#33334444"
    )
    parsed = pm.parse_probe(value)
    assert parsed == field
    assert parsed.spec_hash == "a1b2c3d4"
    assert parsed.file_hash == "e5f6a7b8"
    assert parsed.final_spec_hash == "11112222"
    assert parsed.final_file_hash == "33334444"
    assert pm.render_probe(parsed) == value


def test_probe_grep_verb_with_match_count_files_and_skipped_round_trips() -> None:
    spec_hash = pm.hash_probe_spec("grep:TODO_AUTH -- src/auth/")
    field = pm.ProbeField(
        verb="grep",
        arg="TODO_AUTH -- src/auth/",
        baseline="3 matches in 2 files",
        baseline_files=["src/auth/login.py", "src/auth/session.py"],
        skipped_files=1,
        spec_hash=spec_hash,
    )
    value = pm.render_probe(field)
    assert value == (
        "grep:TODO_AUTH -- src/auth/ — "
        "baseline: 3 matches in 2 files (src/auth/login.py, src/auth/session.py) — "
        "skipped 1 unreadable — "
        f"spec#{spec_hash}"
    )
    assert "file#" not in value
    parsed = pm.parse_probe(value)
    assert parsed == field
    assert pm.render_probe(parsed) == value


def test_probe_grep_literal_spec_example_round_trips() -> None:
    line = (
        "grep:TODO_AUTH -- src/auth/ — "
        "baseline: 3 matches in 2 files (src/auth/login.py, src/auth/session.py) — "
        "spec#a1b2c3d4"
    )
    parsed = pm.parse_probe(line)
    assert isinstance(parsed, pm.ProbeField)
    assert parsed.verb == "grep"
    assert parsed.arg == "TODO_AUTH -- src/auth/"
    assert parsed.baseline == "3 matches in 2 files"
    assert parsed.baseline_files == ["src/auth/login.py", "src/auth/session.py"]
    assert parsed.spec_hash == "a1b2c3d4"
    assert parsed.file_hash is None
    assert pm.render_probe(parsed) == line


def test_probe_none_unchanged_start_to_finish() -> None:
    field = pm.ProbeField(verb="none", arg="")
    value = pm.render_probe(field)
    assert value == "none"
    parsed = pm.parse_probe(value)
    assert parsed == field
    # nothing about "none" changes when finish would ordinarily append `final:`
    assert pm.render_probe(parsed) == "none"


def test_probe_none_carries_no_hash() -> None:
    field = pm.ProbeField(verb="none", arg="")
    assert field.spec_hash is None
    assert field.file_hash is None
    value = pm.render_probe(field)
    assert "#" not in value


# --- Probe: malformed field detection ---------------------------------------


def test_probe_malformed_names_first_failing_segment_verb() -> None:
    parsed = pm.parse_probe("bogus:whatever — baseline: fail — spec#a1b2c3d4")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "verb"


def test_probe_malformed_names_first_failing_segment_baseline() -> None:
    parsed = pm.parse_probe("test:tests/test_auth.py::test_safari — not-a-baseline — spec#a1b2c3d4")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "baseline"


def test_probe_malformed_names_first_failing_segment_hashes() -> None:
    parsed = pm.parse_probe("test:tests/test_auth.py::test_safari — baseline: fail — not-a-hash")
    assert isinstance(parsed, pm.MalformedField)
    assert parsed.reason == "hashes"


def test_probe_hashes_require_exactly_8_hex_chars() -> None:
    parsed = pm.parse_probe("test:tests/test_auth.py::test_safari — baseline: fail — spec#a1b2c3d")
    assert isinstance(parsed, pm.MalformedField)


# --- --reason at the CLI boundary: rejected, nothing written ---------------


def test_reason_with_delimiter_is_rejected_before_anything_is_rendered() -> None:
    bad_reason = "folded — into the redesign"
    assert pm.is_valid_free_text(bad_reason) is False
    # a caller (start/park/decide) must refuse before ever building a StatusField from this


def test_reason_survives_verbatim_when_it_looks_structural_but_is_not() -> None:
    tricky = "before—after and one - two, not a delimiter"
    assert pm.is_valid_free_text(tricky) is True
    field = pm.StatusField(state="wontfix", date="2026-08-05", attempt=1, reason=tricky)
    value = pm.render_status(field)
    parsed = pm.parse_status(value)
    assert parsed.reason == tricky
