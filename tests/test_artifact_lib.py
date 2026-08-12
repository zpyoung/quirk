from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
from pathlib import Path

import pytest

import artifact_lib
import artifact_review

from .conftest import TEMPLATES_DIR
from .test_schema_v2 import SPEC_ROADMAP_EXAMPLE

HEX8_RE = re.compile(r"^[0-9a-f]{8}$")


def test_titleless_heading_does_not_consume_following_line_as_title() -> None:
    text = "## BUG-7:\n- **Severity**: low\n"
    result = artifact_lib.parse_entries(text, "BUG")
    assert result.entries == []
    assert len(result.malformed) == 1
    bad = result.malformed[0]
    assert bad.id == 7
    assert bad.reason == "no title"
    assert bad.fields == {"Severity": "low"}


def test_trailing_spaces_after_colon_do_not_backtrack_into_a_title() -> None:
    text = "## BUG-1:   \n- **Severity**: low\n"
    result = artifact_lib.parse_entries(text, "BUG")
    assert result.entries == []
    assert len(result.malformed) == 1
    assert result.malformed[0].id == 1
    assert result.malformed[0].reason == "no title"


def test_titleless_heading_terminates_preceding_block_without_leaking_fields() -> None:
    text = (
        "## BUG-1: alpha\n- **Severity**: high\n"
        "\n## BUG-2:\n- **Severity**: oops\n"
        "\n## BUG-3: gamma\n- **Severity**: low\n"
    )
    result = artifact_lib.parse_entries(text, "BUG")
    assert [e.id for e in result.entries] == [1, 3]
    entry_1 = result.entries[0]
    assert entry_1.title == "alpha"
    assert entry_1.fields == {"Severity": "high"}
    entry_3 = result.entries[1]
    assert entry_3.title == "gamma"
    assert entry_3.fields == {"Severity": "low"}
    assert len(result.malformed) == 1
    assert result.malformed[0].id == 2
    assert result.malformed[0].fields == {"Severity": "oops"}


def test_find_max_id_still_counts_a_titleless_heading() -> None:
    text = "## BUG-7:\n- **Severity**: low\n"
    assert artifact_lib.find_max_id(text, "BUG") == 7


def test_duplicate_id_headings_are_both_returned_as_separate_entries() -> None:
    text = (
        "## BUG-5: first\n- **Severity**: high\n"
        "\n## BUG-5: second\n- **Severity**: low\n"
    )
    result = artifact_lib.parse_entries(text, "BUG")
    assert len(result.entries) == 2
    assert result.entries[0].id == 5
    assert result.entries[1].id == 5
    assert result.entries[0].title == "first"
    assert result.entries[1].title == "second"
    assert result.entries[0].fields == {"Severity": "high"}
    assert result.entries[1].fields == {"Severity": "low"}


def test_find_max_id_gap() -> None:
    text = "## BUG-3: x\n\n## BUG-7: y\n\n## BUG-12: z\n"
    assert artifact_lib.find_max_id(text, "BUG") == 12


def test_find_max_id_sequential() -> None:
    text = "".join(f"## BUG-{n}: x\n\n" for n in range(1, 7))
    assert artifact_lib.find_max_id(text, "BUG") == 6


def test_parse_entries_preserves_unicode() -> None:
    weird = "café — emoji 🐛 quotes \"don't\" newlines\\nliteral"
    text = f"## BUG-1: {weird}\n- **Description**: {weird}\n"
    result = artifact_lib.parse_entries(text, "BUG")
    assert len(result.entries) == 1
    assert result.entries[0].title == weird
    assert result.entries[0].fields == {"Description": weird}


def test_render_report_does_not_drop_a_file_whose_entries_are_all_malformed(tmp_path) -> None:
    (tmp_path / "BUGS.md").write_text(
        "<!-- schema-version: 1 -->\n# BUGS\n\n"
        "## BUG-7:\n- **Severity**: critical\n- **Description**: data loss on save\n"
    )
    out = artifact_review.render_report(tmp_path)
    bugs_line = next(line for line in out.splitlines() if line.startswith("## BUGS.md"))
    assert "no entries" not in bugs_line.lower()
    assert "BUGS.md: 1 entries" in out
    assert "BUG-7" in out
    assert "no title" in out


def test_render_report_count_line_includes_malformed_alongside_well_formed(tmp_path) -> None:
    (tmp_path / "BUGS.md").write_text(
        "<!-- schema-version: 1 -->\n# BUGS\n\n"
        "## BUG-1: alpha\n- **Severity**: high\n"
        "\n## BUG-2:\n- **Severity**: oops\n"
    )
    out = artifact_review.render_report(tmp_path)
    assert "BUGS.md: 2 entries" in out
    assert "BUG-1 [high] alpha" in out
    assert "BUG-2" in out
    assert "no title" in out


FENCED = (
    "## BUG-1: quoting a ledger entry\n"
    "- **Description**: the schema looks like this:\n"
    "\n"
    "```\n"
    "## BUG-9: inside a fence\n"
    "- **Severity**: critical\n"
    "```\n"
    "\n"
    "- **Severity**: low\n"
)


def test_fenced_heading_is_not_an_entry() -> None:
    result = artifact_lib.parse_entries(FENCED, "BUG")
    assert [e.id for e in result.entries] == [1]
    assert result.malformed == []


def test_fenced_heading_does_not_split_the_entry_that_quotes_it() -> None:
    """The real damage: the fence terminated BUG-1's block, orphaning its Severity."""
    result = artifact_lib.parse_entries(FENCED, "BUG")
    assert result.entries[0].fields["Severity"] == "low"


def test_find_max_id_ignores_fenced_headings() -> None:
    """A quoted ID must not push the next allocated ID past it."""
    assert artifact_lib.find_max_id(FENCED, "BUG") == 1


def test_tilde_fenced_heading_is_not_an_entry() -> None:
    text = "## BUG-1: real\n~~~\n## BUG-9: tilde fence\n~~~\n- **Severity**: low\n"
    result = artifact_lib.parse_entries(text, "BUG")
    assert [e.id for e in result.entries] == [1]
    assert result.entries[0].fields["Severity"] == "low"


def test_commented_out_heading_is_not_an_entry() -> None:
    """The artifact templates ship a schema block in an HTML comment."""
    text = "<!--\n## BUG-9: schema example\n-->\n## BUG-1: real\n- **Severity**: low\n"
    result = artifact_lib.parse_entries(text, "BUG")
    assert [e.id for e in result.entries] == [1]
    assert artifact_lib.find_max_id(text, "BUG") == 1


def test_entry_offsets_still_index_the_original_text() -> None:
    """Masking must preserve offsets: `start` and `raw` are used to slice the real file."""
    result = artifact_lib.parse_entries(FENCED, "BUG")
    entry = result.entries[0]
    assert FENCED[entry.start:entry.start + len("## BUG-1:")] == "## BUG-1:"
    assert entry.raw.startswith("## BUG-1: quoting")
    assert "inside a fence" in entry.raw


# --- Entry.end ---------------------------------------------------------------


def test_entry_end_is_len_of_text_for_the_only_entry() -> None:
    text = "## BUG-1: alpha\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert entry.end == len(text)


def test_entry_end_bounds_a_non_final_entry_at_the_next_headings_start() -> None:
    text = "## BUG-1: alpha\n- **Severity**: high\n\n## BUG-2: beta\n- **Severity**: low\n"
    entry_1 = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert entry_1.end == text.index("## BUG-2:")


def test_entry_end_for_the_final_entry_with_no_trailing_newline() -> None:
    text = "## BUG-1: alpha\n- **Severity**: high"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert entry.end == len(text)


def test_entry_end_respects_a_fenced_heading_inside_the_block() -> None:
    """A fenced `## BUG-N:` is not a boundary, so `end` must run past it to the real end."""
    entry = artifact_lib.parse_entries(FENCED, "BUG").entries[0]
    assert entry.end == len(FENCED)


# --- hash_probe_spec / hash_file ----------------------------------------------


def test_hash_probe_spec_matches_sha256_prefix() -> None:
    spec = "test:tests/test_auth.py::test_safari"
    result = artifact_lib.hash_probe_spec(spec)
    assert HEX8_RE.match(result)
    assert result == hashlib.sha256(spec.encode()).hexdigest()[:8]


def test_hash_probe_spec_is_deterministic() -> None:
    spec = "grep:TODO_AUTH -- src/auth/"
    assert artifact_lib.hash_probe_spec(spec) == artifact_lib.hash_probe_spec(spec)


def test_hash_file_matches_sha256_prefix(tmp_path) -> None:
    target = tmp_path / "sample.txt"
    target.write_bytes(b"some file contents\n")
    result = artifact_lib.hash_file(target)
    assert HEX8_RE.match(result)
    assert result == hashlib.sha256(b"some file contents\n").hexdigest()[:8]


def test_hash_file_is_deterministic(tmp_path) -> None:
    target = tmp_path / "sample.txt"
    target.write_bytes(b"stable content")
    assert artifact_lib.hash_file(target) == artifact_lib.hash_file(target)


def test_hash_file_returns_none_for_missing_path(tmp_path) -> None:
    assert artifact_lib.hash_file(tmp_path / "does-not-exist.txt") is None


def test_hash_file_returns_none_for_unreadable_path(tmp_path) -> None:
    target = tmp_path / "locked.txt"
    target.write_bytes(b"secret")
    target.chmod(0o000)
    try:
        if os.access(target, os.R_OK):
            pytest.skip("running as a user that bypasses file permissions")
        assert artifact_lib.hash_file(target) is None
    finally:
        target.chmod(0o644)


def test_hash_file_returns_none_for_a_directory(tmp_path) -> None:
    assert artifact_lib.hash_file(tmp_path) is None


def test_hash_file_returns_none_for_dev_null() -> None:
    dev_null = Path("/dev/null")
    if not dev_null.exists():
        pytest.skip("no /dev/null on this platform")
    assert artifact_lib.hash_file(dev_null) is None


def test_hash_file_returns_none_for_a_fifo_without_blocking(tmp_path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("no FIFOs on this platform")
    fifo_path = tmp_path / "fifo"
    os.mkfifo(fifo_path)
    assert artifact_lib.hash_file(fifo_path) is None


def test_hash_file_returns_none_for_a_path_with_an_embedded_null_byte() -> None:
    assert artifact_lib.hash_file(Path("bad\0name")) is None


# --- atomic_write --------------------------------------------------------------


def test_atomic_write_creates_a_new_file_with_the_given_text(tmp_path) -> None:
    target = tmp_path / "BUGS.md"
    artifact_lib.atomic_write(target, "hello\n")
    assert target.read_text() == "hello\n"


def test_atomic_write_replaces_existing_content(tmp_path) -> None:
    target = tmp_path / "BUGS.md"
    target.write_text("old\n")
    artifact_lib.atomic_write(target, "new\n")
    assert target.read_text() == "new\n"


def test_atomic_write_leaves_the_original_byte_identical_when_replace_fails(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "BUGS.md"
    target.write_bytes(b"original\n")

    def boom(*args, **kwargs):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        artifact_lib.atomic_write(target, "new\n")

    assert target.read_bytes() == b"original\n"


def test_atomic_write_leaves_no_temp_file_behind_when_replace_fails(tmp_path, monkeypatch) -> None:
    target = tmp_path / "BUGS.md"
    target.write_text("original\n")

    def boom(*args, **kwargs):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        artifact_lib.atomic_write(target, "new\n")

    leftover = [p.name for p in tmp_path.iterdir() if p.name != "BUGS.md"]
    assert leftover == []


def test_atomic_write_fsyncs_temp_file_before_replace_and_directory_after(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "BUGS.md"
    calls: list[str] = []
    real_fsync = os.fsync
    real_replace = os.replace

    def tracking_fsync(fd):
        calls.append("fsync")
        return real_fsync(fd)

    def tracking_replace(src, dst):
        calls.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", tracking_fsync)
    monkeypatch.setattr(os, "replace", tracking_replace)

    artifact_lib.atomic_write(target, "content\n")

    assert calls.count("fsync") == 2
    assert calls.count("replace") == 1
    assert calls[0] == "fsync", "temp file must be fsynced before the replace"
    assert calls[-1] == "fsync", "directory must be fsynced after the replace"
    assert calls.index("replace") == 1, "replace must happen strictly between the two fsyncs"
    assert target.read_text() == "content\n"


def test_atomic_write_propagates_a_real_directory_fsync_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "BUGS.md"
    real_fsync = os.fsync
    calls = 0

    def fail_the_directory_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated directory fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_the_directory_fsync)
    with pytest.raises(OSError):
        artifact_lib.atomic_write(target, "new\n")

    assert target.read_text() == "new\n"


def test_atomic_write_degrades_quietly_when_directory_fsync_is_unsupported(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "BUGS.md"
    real_fsync = os.fsync
    calls = 0

    def einval_the_directory_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EINVAL, "simulated EINVAL on directory fsync")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", einval_the_directory_fsync)
    artifact_lib.atomic_write(target, "new\n")

    assert target.read_text() == "new\n"


def test_atomic_write_preserves_an_existing_files_permission_bits(tmp_path) -> None:
    target = tmp_path / "BUGS.md"
    target.write_text("old\n")
    target.chmod(0o644)

    artifact_lib.atomic_write(target, "new\n")

    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_atomic_write_on_a_new_file_uses_the_umask_default_not_mkstemps_0600(tmp_path) -> None:
    target = tmp_path / "BUGS.md"
    old_umask = os.umask(0o022)
    try:
        artifact_lib.atomic_write(target, "new\n")
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_atomic_write_refuses_to_write_through_a_symlink(tmp_path) -> None:
    real_target = tmp_path / "elsewhere.md"
    real_target.write_text("original\n")
    link = tmp_path / "BUGS.md"
    link.symlink_to(real_target)

    with pytest.raises(artifact_lib.SymlinkedLedgerError):
        artifact_lib.atomic_write(link, "new\n")

    assert link.is_symlink()
    assert real_target.read_text() == "original\n"


def test_atomic_write_refusing_a_symlink_leaves_no_temp_file_behind(tmp_path) -> None:
    real_target = tmp_path / "elsewhere.md"
    real_target.write_text("original\n")
    link = tmp_path / "BUGS.md"
    link.symlink_to(real_target)

    with pytest.raises(artifact_lib.SymlinkedLedgerError):
        artifact_lib.atomic_write(link, "new\n")

    leftover = [p.name for p in tmp_path.iterdir() if p.name not in ("BUGS.md", "elsewhere.md")]
    assert leftover == []


# --- field_line ------------------------------------------------------------------


def test_field_line_renders_label_and_value() -> None:
    assert artifact_lib.field_line("Severity", "critical") == "- **Severity**: critical"


# --- splice_field ----------------------------------------------------------------


def test_splice_field_replaces_an_existing_field_line() -> None:
    text = "## BUG-1: alpha\n- **Status**: open\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", "in-progress")
    assert result == "## BUG-1: alpha\n- **Status**: in-progress\n- **Severity**: high\n"


def test_splice_field_inserts_after_the_last_field_line_when_absent() -> None:
    text = "## BUG-1: alpha\n- **Status**: open\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Probe", "none")
    assert result == (
        "## BUG-1: alpha\n- **Status**: open\n- **Severity**: high\n- **Probe**: none\n"
    )


def test_splice_field_inserts_after_heading_when_no_field_lines_exist() -> None:
    text = "## BUG-1: alpha\n\nSome prose.\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", "open")
    assert result == "## BUG-1: alpha\n- **Status**: open\n\nSome prose.\n"


def test_splice_field_anchors_after_an_empty_valued_field_line() -> None:
    text = "## BUG-1: alpha\n- **Empty**:\nSome prose.\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", "open")
    assert result == "## BUG-1: alpha\n- **Empty**:\n- **Status**: open\nSome prose.\n"


def test_splice_field_removes_the_line_when_value_is_none() -> None:
    text = "## BUG-1: alpha\n- **Status**: open\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", None)
    assert result == "## BUG-1: alpha\n- **Severity**: high\n"


def test_splice_field_removing_an_absent_field_is_a_no_op() -> None:
    text = "## BUG-1: alpha\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", None)
    assert result == text


def test_splice_field_refuses_on_a_duplicated_label() -> None:
    text = "## BUG-1: alpha\n- **Status**: open\n- **Status**: closed\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    with pytest.raises(artifact_lib.DuplicateFieldError):
        artifact_lib.splice_field(text, entry, "Status", "in-progress")


def test_splice_field_replaces_in_the_last_entry_with_no_trailing_newline() -> None:
    text = "## BUG-1: alpha\n- **Status**: open"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", "closed")
    assert result == "## BUG-1: alpha\n- **Status**: closed"


def test_splice_field_inserts_into_the_last_entry_with_no_trailing_newline() -> None:
    text = "## BUG-1: alpha\n- **Status**: open"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Severity", "high")
    assert result == "## BUG-1: alpha\n- **Status**: open\n- **Severity**: high"


def test_splice_field_removes_the_only_field_from_the_last_entry_with_no_trailing_newline() -> None:
    text = "## BUG-1: alpha\n- **Status**: open"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", None)
    assert result == "## BUG-1: alpha"


def test_splice_field_removing_the_final_crlf_field_leaves_no_stray_carriage_return() -> None:
    text = "## BUG-1: alpha\r\n- **Status**: open"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    result = artifact_lib.splice_field(text, entry, "Status", None)
    assert result == "## BUG-1: alpha"


def test_splice_field_ignores_a_fenced_duplicate_and_edits_only_the_real_field() -> None:
    """A field label quoted inside a fenced example must not count toward the duplicate check
    or be mistaken for the field to edit — masking must apply the same way `parse_entries` does.
    """
    entry = artifact_lib.parse_entries(FENCED, "BUG").entries[0]
    result = artifact_lib.splice_field(FENCED, entry, "Severity", "critical-updated")
    assert result == FENCED.replace("- **Severity**: low", "- **Severity**: critical-updated")
    assert "- **Severity**: critical\n" in result, "the fenced example must stay untouched"


# --- render_entry: v2-field suppression -------------------------------------------


SCHEMA_WITH_V2_FIELD = {
    "header": "BUG",
    "fields": ["title", "severity", "blocked_by"],
    "labels": {"severity": "Severity", "blocked_by": "Blocker for"},
    "v2_fields": {"blocked_by"},
}


def test_render_entry_suppresses_v2_fields_when_schema_version_is_1() -> None:
    fields = {"title": "alpha", "severity": "high", "blocked_by": "BUG-2"}
    result = artifact_lib.render_entry(SCHEMA_WITH_V2_FIELD, 1, fields, schema_version=1)
    assert "Blocker for" not in result
    assert "- **Severity**: high" in result


def test_render_entry_emits_v2_fields_when_schema_version_is_omitted() -> None:
    fields = {"title": "alpha", "severity": "high", "blocked_by": "BUG-2"}
    result = artifact_lib.render_entry(SCHEMA_WITH_V2_FIELD, 1, fields)
    assert "- **Blocker for**: BUG-2" in result


def test_render_entry_emits_v2_fields_when_schema_version_is_2() -> None:
    fields = {"title": "alpha", "severity": "high", "blocked_by": "BUG-2"}
    result = artifact_lib.render_entry(SCHEMA_WITH_V2_FIELD, 1, fields, schema_version=2)
    assert "- **Blocker for**: BUG-2" in result


def test_render_entry_without_v2_fields_key_is_unaffected_by_schema_version() -> None:
    schema = {
        "header": "BUG",
        "fields": ["title", "severity"],
        "labels": {"severity": "Severity"},
    }
    fields = {"title": "alpha", "severity": "high"}
    result = artifact_lib.render_entry(schema, 1, fields, schema_version=1)
    assert "- **Severity**: high" in result


# --- detect_schema_version ---------------------------------------------------


def test_detect_schema_version_finds_a_real_preamble_marker() -> None:
    text = "<!-- schema-version: 2 -->\n# BUGS\n\n## BUG-1: alpha\n- **Severity**: high\n"
    assert artifact_lib.detect_schema_version(text) == 2


def test_detect_schema_version_ignores_a_marker_quoted_inside_an_entry_body() -> None:
    """A legacy file with no preamble marker of its own must not be misread as v2 just
    because an entry discusses the marker in prose.
    """
    text = (
        "# BUGS\n\n"
        "## BUG-1: migration note\n"
        "- **Description**: this file was migrated, the marker looked like "
        "<!-- schema-version: 2 --> in the changelog.\n"
    )
    assert artifact_lib.detect_schema_version(text) is None


def test_detect_schema_version_prefers_the_preamble_marker_over_a_quoted_one() -> None:
    text = (
        "<!-- schema-version: 2 -->\n# BUGS\n\n"
        "## BUG-1: migration note\n"
        "- **Description**: an earlier draft said <!-- schema-version: 99 --> by mistake.\n"
    )
    assert artifact_lib.detect_schema_version(text) == 2


def test_parse_roadmap_never_raises_on_arbitrary_text() -> None:
    for text in [
        "",
        "\n\n\n",
        "not a roadmap at all",
        "<!-- unterminated comment\n## Milestone: X\n- BUG-1\n",
        "## Milestone: \n- \n-BUG-1\n--- BUG-2\n",
        "## Milestone: X\n" + "�" * 50 + "\n",
        "# ROADMAP\n## Milestone:\n## Milestone: Y\n- TEST-9999999999999999999999999\n",
    ]:
        result = artifact_lib.parse_roadmap(text)
        assert isinstance(result, artifact_lib.RoadmapParse)


# splitlines() treats each of these as a line terminator too, unlike \r\n/\r/\n; masking a
# comment blanks the character but the raw/masked line counts must still agree either way
@pytest.mark.parametrize(
    "separator", ["\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]
)
def test_parse_roadmap_never_raises_on_a_line_separator_inside_a_comment(separator: str) -> None:
    text = f"<!-- comment with a separator{separator}inside -->\n## Milestone: X\n"
    result = artifact_lib.parse_roadmap(text)
    assert isinstance(result, artifact_lib.RoadmapParse)


def test_parse_roadmap_never_raises_on_cr_only_input_with_a_multiline_comment() -> None:
    text = "<!-- line one\rline two -->\r## Milestone: X\r- BUG-1\r"
    result = artifact_lib.parse_roadmap(text)
    assert isinstance(result, artifact_lib.RoadmapParse)


def test_parse_roadmap_with_no_milestones_treats_whole_file_as_preamble() -> None:
    text = "# ROADMAP\n\nNo milestones yet.\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.milestones == []
    assert result.findings == []
    assert result.preamble == text


def test_shipped_roadmap_template_parses_with_zero_findings() -> None:
    text = (TEMPLATES_DIR / "ROADMAP.md").read_text()
    result = artifact_lib.parse_roadmap(text)
    assert result.milestones == []
    assert result.findings == []


def test_shipped_roadmap_template_passes_write_time_validation_unchanged() -> None:
    text = (TEMPLATES_DIR / "ROADMAP.md").read_text()
    result = artifact_lib.parse_roadmap(text)
    assert artifact_lib.validate_roadmap_for_write(result) == []


def test_spec_roadmap_example_parses_with_zero_findings() -> None:
    result = artifact_lib.parse_roadmap(SPEC_ROADMAP_EXAMPLE)
    assert result.findings == []
    assert [m.name for m in result.milestones] == ["Auth hardening", "Search v2"]
    assert result.milestones[0].members == ["BUG-3", "DEFER-7", "TEST-12"]
    assert result.milestones[1].members == ["BUG-9"]


def test_spec_roadmap_example_passes_write_time_validation_unchanged() -> None:
    result = artifact_lib.parse_roadmap(SPEC_ROADMAP_EXAMPLE)
    assert artifact_lib.validate_roadmap_for_write(result) == []


def test_spec_roadmap_example_round_trips_byte_for_byte() -> None:
    result = artifact_lib.parse_roadmap(SPEC_ROADMAP_EXAMPLE)
    assert artifact_lib.render_roadmap(result) == SPEC_ROADMAP_EXAMPLE


def test_round_trip_preserves_comments_and_blank_lines_between_milestones_and_members() -> None:
    text = (
        "<!-- schema-version: 2 -->\n"
        "# ROADMAP\n\n"
        "## Milestone: Alpha\n"
        "- BUG-1\n"
        "\n"
        "- BUG-2\n"
        "<!-- a note about ordering -->\n"
        "- DEFER-3\n"
        "\n"
        "## Milestone: Beta\n"
        "- TEST-4\n"
    )
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert artifact_lib.render_roadmap(result) == text


def test_round_trip_preserves_crlf_line_endings() -> None:
    text = "## Milestone: Alpha\r\n- BUG-1\r\n\r\n## Milestone: Beta\r\n- BUG-2\r\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert artifact_lib.render_roadmap(result) == text


def test_round_trip_preserves_a_final_milestone_heading_with_no_trailing_newline() -> None:
    text = "## Milestone: Alpha\n- BUG-1\n\n## Milestone: Beta"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert result.milestones[-1].members == []
    assert artifact_lib.render_roadmap(result) == text


def test_milestone_rank_is_zero_based_document_position() -> None:
    text = "## Milestone: First\n- BUG-1\n\n## Milestone: Second\n- BUG-2\n\n## Milestone: Third\n- BUG-3\n"
    result = artifact_lib.parse_roadmap(text)
    assert [m.rank for m in result.milestones] == [0, 1, 2]
    assert [m.name for m in result.milestones] == ["First", "Second", "Third"]


def test_blank_line_between_milestones_is_legal() -> None:
    text = "## Milestone: A\n- BUG-1\n\n\n## Milestone: B\n- BUG-2\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert artifact_lib.validate_roadmap_for_write(result) == []


def test_proposal_member_produces_proposal_in_roadmap_not_malformed() -> None:
    text = "## Milestone: X\n- PROPOSAL-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == [("PROPOSAL_IN_ROADMAP", "PROPOSAL-1")]
    assert result.milestones[0].members == []


def test_unknown_header_member_produces_unknown_header_in_roadmap() -> None:
    text = "## Milestone: X\n- WIDGET-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == [("UNKNOWN_HEADER_IN_ROADMAP", "WIDGET-1")]
    assert result.milestones[0].members == []


def test_leading_zero_id_is_malformed_not_normalized() -> None:
    text = "## Milestone: X\n- BUG-007\n"
    result = artifact_lib.parse_roadmap(text)
    assert len(result.findings) == 1
    code, detail = result.findings[0]
    assert code == "ROADMAP_LINE_MALFORMED"
    assert "BUG-007" in detail
    assert result.milestones[0].members == []


def test_non_ascii_digit_id_is_malformed_not_normalized() -> None:
    text = "## Milestone: X\n- BUG-٣\n"
    result = artifact_lib.parse_roadmap(text)
    assert len(result.findings) == 1
    assert result.findings[0][0] == "ROADMAP_LINE_MALFORMED"
    assert result.milestones[0].members == []


def test_duplicate_membership_first_occurrence_wins_for_rank() -> None:
    text = "## Milestone: Alpha\n- BUG-1\n\n## Milestone: Beta\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    first = next(m for m in result.milestones if "BUG-1" in m.members)
    assert first.name == "Alpha"
    assert first.rank == 0


def test_duplicate_membership_finding_names_both_milestones() -> None:
    text = "## Milestone: Alpha\n- BUG-1\n\n## Milestone: Beta\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert len(result.findings) == 1
    code, detail = result.findings[0]
    assert code == "DUPLICATE_MEMBERSHIP"
    assert "Alpha" in detail
    assert "Beta" in detail
    assert "BUG-1" in detail


def test_duplicate_milestone_name_does_not_disturb_rank() -> None:
    text = "## Milestone: A\n- BUG-1\n\n## Milestone: A\n- BUG-2\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == [("DUPLICATE_MILESTONE_NAME", "A")]
    assert [m.rank for m in result.milestones] == [0, 1]
    assert [m.members for m in result.milestones] == [["BUG-1"], ["BUG-2"]]


def test_prose_note_inside_a_milestone_is_malformed() -> None:
    text = "## Milestone: A\nplease group these later\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert len(result.findings) == 1
    code, detail = result.findings[0]
    assert code == "ROADMAP_LINE_MALFORMED"
    assert "A" in detail
    assert "please group these later" in detail


def test_prose_note_inside_a_milestone_is_lost_on_rewrite() -> None:
    text = "## Milestone: A\nplease group these later\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert artifact_lib.render_roadmap(result) == "## Milestone: A\n- BUG-1\n"


def test_prose_note_in_preamble_survives_byte_for_byte() -> None:
    text = "A hand-written note above the milestones.\n\n## Milestone: A\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.preamble == "A hand-written note above the milestones.\n\n"
    assert artifact_lib.render_roadmap(result).startswith(result.preamble)


def test_fenced_content_under_a_milestone_is_malformed_not_masked_away() -> None:
    """The roadmap grammar has no fence class — `_mask_quoted`'s fence handling is for
    `parse_entries` only, and must not let arbitrary fenced prose read as blank (legal) here.
    """
    text = "## Milestone: X\n```text\nnot roadmap grammar\n```\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    codes = [code for code, _ in result.findings]
    assert codes.count("ROADMAP_LINE_MALFORMED") == 3
    assert artifact_lib.validate_roadmap_for_write(result) != []


def test_title_line_under_a_milestone_is_recognized_not_malformed() -> None:
    text = "## Milestone: A\n# ROADMAP\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert artifact_lib.validate_roadmap_for_write(result) == []
    assert artifact_lib.render_roadmap(result) == text


def test_validate_roadmap_for_write_refuses_malformed_line() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\nprose\n- BUG-1\n")
    blocking = artifact_lib.validate_roadmap_for_write(result)
    assert ("ROADMAP_LINE_MALFORMED", "A: prose") in blocking


def test_validate_roadmap_for_write_refuses_disallowed_member_headers() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\n- PROPOSAL-1\n- WIDGET-2\n")
    blocking = artifact_lib.validate_roadmap_for_write(result)
    assert ("PROPOSAL_IN_ROADMAP", "PROPOSAL-1") in blocking
    assert ("UNKNOWN_HEADER_IN_ROADMAP", "WIDGET-2") in blocking


def test_validate_roadmap_for_write_refuses_duplicate_membership() -> None:
    text = "## Milestone: Alpha\n- BUG-1\n\n## Milestone: Beta\n- BUG-1\n"
    result = artifact_lib.parse_roadmap(text)
    blocking = artifact_lib.validate_roadmap_for_write(result)
    assert len(blocking) == 1
    assert blocking[0][0] == "DUPLICATE_MEMBERSHIP"


def test_validate_roadmap_for_write_does_not_refuse_duplicate_milestone_name() -> None:
    text = "## Milestone: A\n- BUG-1\n\n## Milestone: A\n- BUG-2\n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == [("DUPLICATE_MILESTONE_NAME", "A")]
    assert artifact_lib.validate_roadmap_for_write(result) == []


def test_validate_roadmap_for_write_skips_dangling_check_when_known_ids_is_none() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\n- BUG-999\n")
    assert artifact_lib.validate_roadmap_for_write(result, known_ids=None) == []


def test_validate_roadmap_for_write_flags_dangling_ref_against_known_ids() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\n- BUG-1\n- BUG-999\n")
    blocking = artifact_lib.validate_roadmap_for_write(result, known_ids={"BUG-1"})
    assert blocking == [("DANGLING_ROADMAP_REF", "BUG-999")]


def test_validate_roadmap_for_write_passes_when_all_ids_known() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\n- BUG-1\n- DEFER-2\n")
    blocking = artifact_lib.validate_roadmap_for_write(result, known_ids={"BUG-1", "DEFER-2"})
    assert blocking == []


def test_validate_roadmap_for_write_withholds_dangling_ref_for_a_skipped_header() -> None:
    result = artifact_lib.parse_roadmap("## Milestone: A\n- BUG-1\n- DEFER-999\n")
    blocking = artifact_lib.validate_roadmap_for_write(
        result, known_ids={"BUG-1"}, skipped_headers={"DEFER"},
    )
    assert blocking == []


def test_validate_roadmap_for_write_still_flags_dangling_ref_for_a_readable_header() -> None:
    # a skipped header must not become a blanket pass: an unknown id in a header that *was*
    # checked still blocks, even while another header is skipped
    result = artifact_lib.parse_roadmap("## Milestone: A\n- BUG-999\n- DEFER-1\n")
    blocking = artifact_lib.validate_roadmap_for_write(
        result, known_ids={"DEFER-1"}, skipped_headers={"DEFER"},
    )
    assert blocking == [("DANGLING_ROADMAP_REF", "BUG-999")]


def test_member_line_allows_trailing_whitespace() -> None:
    text = "## Milestone: A\n- BUG-1  \n"
    result = artifact_lib.parse_roadmap(text)
    assert result.findings == []
    assert result.milestones[0].members == ["BUG-1"]
    assert artifact_lib.render_roadmap(result) == text


# --- a member-shaped line outside every milestone: write-time only ---------


def test_member_line_outside_every_milestone_is_not_flagged_by_parse_alone() -> None:
    """Scoped to write time only: an ordinary parse (as `--doctor`/`--index` would run against
    an already-committed ROADMAP.md) must not gain a new blocking finding from this."""
    result = artifact_lib.parse_roadmap("# ROADMAP\n- BUG-1\n\n## Milestone: A\n- BUG-2\n")
    assert result.findings == []


def test_validate_roadmap_for_write_refuses_a_member_line_outside_every_milestone() -> None:
    result = artifact_lib.parse_roadmap("# ROADMAP\n- BUG-1\n\n## Milestone: A\n- BUG-2\n")
    blocking = artifact_lib.validate_roadmap_for_write(result, known_ids={"BUG-1", "BUG-2"})
    assert ("MEMBER_OUTSIDE_MILESTONE", "BUG-1") in blocking


def test_validate_roadmap_for_write_refuses_a_member_line_when_no_milestone_exists_at_all() -> None:
    """The reviewer's exact reproduction: `- BUG-1` with no `## Milestone:` heading anywhere in
    the file writes cleanly today and then contributes no membership at all."""
    result = artifact_lib.parse_roadmap("# ROADMAP\n- BUG-1\n")
    blocking = artifact_lib.validate_roadmap_for_write(result, known_ids={"BUG-1"})
    assert blocking == [("MEMBER_OUTSIDE_MILESTONE", "BUG-1")]


def test_validate_roadmap_for_write_refuses_a_disallowed_header_line_outside_every_milestone() -> None:
    result = artifact_lib.parse_roadmap("# ROADMAP\n- PROPOSAL-1\n")
    blocking = artifact_lib.validate_roadmap_for_write(result)
    assert ("MEMBER_OUTSIDE_MILESTONE", "PROPOSAL-1") in blocking


def test_validate_roadmap_for_write_ignores_a_member_line_quoted_inside_the_schema_comment() -> None:
    """The shipped template's schema comment quotes `- BUG-3`, `- DEFER-7`, etc. as a worked
    example above the first milestone; those are documentation, not a real write-time defect."""
    result = artifact_lib.parse_roadmap(SPEC_ROADMAP_EXAMPLE)
    assert artifact_lib.validate_roadmap_for_write(result) == []


def test_prose_only_preamble_with_no_milestones_still_passes_write() -> None:
    result = artifact_lib.parse_roadmap("# ROADMAP\nthis is not legal\n")
    assert artifact_lib.validate_roadmap_for_write(result) == []


# --- field_present_but_empty ------------------------------------------------


def test_field_present_but_empty_detects_a_value_less_field_line() -> None:
    text = "## BUG-1: alpha\n- **Blocked by**:\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert artifact_lib.field_present_but_empty(entry, "Blocked by") is True


def test_field_present_but_empty_is_false_when_the_field_is_never_written() -> None:
    text = "## BUG-1: alpha\n- **Severity**: high\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert artifact_lib.field_present_but_empty(entry, "Blocked by") is False


def test_field_present_but_empty_is_false_when_the_field_has_a_real_value() -> None:
    text = "## BUG-1: alpha\n- **Blocked by**: BUG-2\n"
    entry = artifact_lib.parse_entries(text, "BUG").entries[0]
    assert artifact_lib.field_present_but_empty(entry, "Blocked by") is False
