from __future__ import annotations

import artifact_lib
import artifact_review


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
