"""The kit static check: tolerant element-stack validation of q-* markup, the JSX check and the
lazy catalog load behind ``run_checks``.

Everything runs offline against the real ``vendor/kit/1.0.0/catalog.json`` unless a test says
otherwise.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import checks, kitcheck, vendor  # noqa: E402

REAL_STORE = vendor.VendorStore([SKILL / "vendor" / "libraries.json"])
CATALOG = kitcheck.load_catalog(REAL_STORE, None)

STAT = (
    '<q-stat direction="up-good" points="1,2,3">'
    '<span slot="label">Users</span><span slot="value">3</span>'
    '<span slot="definition">Distinct users.</span></q-stat>'
)
DIFF = (
    "<q-diff><pre>--- a/src/x.py\n+++ b/src/x.py\n@@ -1,3 +1,4 @@\n"
    " keep\n-gone\n+new\n+newer\n tail</pre>{notes}</q-diff>"
)
# new-side numbering of DIFF: keep=1, new=2, newer=3, tail=4


def details(text: str, label: str = "page.html") -> list[str]:
    return [f["detail"] for f in kitcheck.check_html(text, CATALOG, label=label)]


def messages(text: str) -> list[str]:
    """The failure messages with the ``<label> line <n>: `` prefix stripped."""
    return [d.split(": ", 1)[1] for d in details(text)]


def chart(attrs: str = "", body: str = "") -> str:
    return f'<q-chart summary="s" {attrs}>{body}</q-chart>'


def table(columns: int, header_extra: str = "") -> str:
    heads = "".join(f"<th>c{i}</th>" for i in range(columns))
    cells = "".join("<td>1</td>" for _ in range(columns))
    return f"<table><thead><tr>{heads}</tr></thead><tbody><tr>{cells}</tr></tbody></table>"


@pytest.mark.parametrize("element", list(CATALOG.elements.values()), ids=lambda e: e.tag)
def test_every_catalog_example_is_clean(element) -> None:
    assert details(element.example) == []


def test_failure_shape_and_label() -> None:
    failures = kitcheck.check_html("<q-stats></q-stats>", CATALOG, label="deck.src.html")
    assert failures == [{"check": "kit", "detail": "deck.src.html line 1: unknown element <q-stats>"}]


def test_unknown_element() -> None:
    assert messages("<q-stats></q-stats>") == ["unknown element <q-stats>"]
    assert messages(STAT) == []


def test_non_kit_custom_elements_are_ignored() -> None:
    assert details("<my-widget></my-widget><qx-thing></qx-thing><p>q-stat</p>") == []


def test_required_attribute_missing_and_present() -> None:
    assert messages("<q-chart><table><thead><tr><th>a</th><th>b</th></tr></thead></table></q-chart>") == [
        "<q-chart> needs attribute summary"
    ]
    assert messages(chart(body=table(2))) == []


def test_a_valueless_required_attribute_counts_as_present() -> None:
    assert messages(f"<q-chart summary>{table(2)}</q-chart>") == []


def test_attribute_names_are_case_insensitive() -> None:
    assert messages(f'<Q-CHART SUMMARY="s" TYPE="line">{table(2)}</Q-CHART>') == []


def test_enum_kind() -> None:
    assert messages(chart('type="pie"', table(2))) == ["<q-chart> type=\"pie\" is not one of bar, line, area, donut"]
    for ok in ("bar", "line", "area", "donut"):
        assert messages(chart(f'type="{ok}"', table(2))) == []


def test_number_list_kind() -> None:
    bad = STAT.replace('points="1,2,3"', 'points="a,b"')
    assert messages(bad) == ['<q-stat> points="a,b" is not a number list']
    assert messages(STAT.replace('points="1,2,3"', 'points="4"')) == ['<q-stat> points="4" is not a number list']
    assert messages(STAT.replace('points="1,2,3"', 'points="1,,3"')) == ['<q-stat> points="1,,3" is not a number list']
    assert messages(STAT.replace('points="1,2,3"', 'points="1e400,2"')) == ['<q-stat> points="1e400,2" is not a number list']
    for ok in ("1,2", " 1.5 , -2 , .5 ,3e2 "):
        assert messages(STAT.replace('points="1,2,3"', f'points="{ok}"')) == []


def test_integer_kind() -> None:
    notes = '<q-diff-note file="src/x.py" line="{v}">n</q-diff-note>'
    for bad in ("x", "0", "-1", "2.5", ""):
        got = messages(DIFF.format(notes=notes.format(v=bad)))
        assert f'<q-diff-note> line="{bad}" is not a positive integer' in got, (bad, got)
    assert messages(DIFF.format(notes=notes.format(v="2"))) == []


def test_ident_kind() -> None:
    board = '<q-board id="{v}"><section><h3>A</h3><ul><li>x</li></ul></section></q-board>'
    for bad in ("1abc", "has space", "a.b", ""):
        assert messages(board.format(v=bad)) == [f'<q-board> id="{bad}" is not an identifier'], bad
    for ok in ("triage", "Q_1-b"):
        assert messages(board.format(v=ok)) == []
    assert messages(f'<q-chart summary="s" data-from="9x"></q-chart>') == ['<q-chart> data-from="9x" is not an identifier']


def test_boolean_and_text_kinds_accept_any_value() -> None:
    assert messages(chart('stacked horizontal="no" x="Anything"', table(2))) == []


def test_unknown_non_global_attributes_are_not_checked() -> None:
    assert messages(chart('wobble="1" aria-label="x" data-z="y" @click="go" :a="b"', table(2))) == []


def test_requires_group_with_alternatives() -> None:
    assert messages('<q-chart summary="s"></q-chart>') == ["<q-chart> needs one of: table, data-from"]
    assert messages('<q-chart summary="s" data-from="rows"></q-chart>') == []
    assert messages(chart(body=table(2))) == []


def test_requires_selectors() -> None:
    no_slots = '<q-stat><span slot="label">a</span></q-stat>'
    assert messages(no_slots) == ["<q-stat> needs one of: [slot=value]", "<q-stat> needs one of: [slot=definition]"]
    assert messages("<q-code>no pre</q-code>") == ["<q-code> needs one of: pre"]
    assert messages("<q-code><pre><code>x</code></pre></q-code>") == []
    # a descendant at any depth satisfies a tag selector
    assert messages("<q-table><div><table><thead><tr><th>a</th></tr></thead></table></div></q-table>") == []


def test_requires_attribute_selector_matches_the_element_itself() -> None:
    cat = _catalog_with(
        {"tag": "q-probe", "attrs": [], "requires": [["[kind=a]", "[kind=b]", "td[scope]", "@mark"]]}
    )
    assert _probe_messages(cat, "<q-probe></q-probe>") == ["<q-probe> needs one of: [kind=a], [kind=b], td[scope], mark"]
    assert _probe_messages(cat, "<q-probe mark></q-probe>") == []
    assert _probe_messages(cat, '<q-probe><i kind="b"></i></q-probe>') == []
    assert _probe_messages(cat, '<q-probe><i kind="c"></i></q-probe>') != []
    assert _probe_messages(cat, "<q-probe><table><tr><td scope></td></tr></table></q-probe>") == []
    assert _probe_messages(cat, "<q-probe><td></td></q-probe>") != []


def test_parent_rule() -> None:
    note = '<q-diff-note file="src/x.py" line="2">n</q-diff-note>'
    assert messages(note) == ["<q-diff-note> must be inside <q-diff>"]
    assert "<q-diff-note> must be inside <q-diff>" not in messages(DIFF.format(notes=note))
    nested = DIFF.format(notes=f"<div><p>{note}</p></div>")
    assert messages(nested) == []


def test_max_series_boundary_is_eight_y_columns() -> None:
    eight_y = chart(body=table(9))
    nine_y = chart(body=table(10))
    assert messages(eight_y) == []
    assert messages(nine_y) == ["<q-chart> has 9 series; the limit is 8"]


def test_max_series_counts_the_y_list_when_given() -> None:
    nine = ",".join(f"c{i}" for i in range(1, 10))
    eight = ",".join(f"c{i}" for i in range(1, 9))
    wide = table(12)
    assert messages(chart(f'y="{nine}"', wide)) == ["<q-chart> has 9 series; the limit is 8"]
    assert messages(chart(f'y="{eight}"', wide)) == []
    assert messages(chart('y=" c1 , c2 ,"', wide)) == []


def test_max_series_ignores_data_from_charts_without_a_table() -> None:
    assert messages('<q-chart summary="s" data-from="rows"></q-chart>') == []
    assert messages('<q-chart summary="s" data-from="rows" y="a,b,c,d,e,f,g,h,i"></q-chart>') == []


def test_max_series_reads_the_first_row_when_there_is_no_thead() -> None:
    heads = "".join(f"<th>c{i}</th>" for i in range(10))
    assert messages(chart(body=f"<table><tr>{heads}</tr><tr><td>1</td></tr></table>")) == [
        "<q-chart> has 9 series; the limit is 8"
    ]


def test_diff_notes_accepts_new_side_lines_and_context() -> None:
    def note(file: str, line: int) -> str:
        return f'<q-diff-note file="{file}" line="{line}">n</q-diff-note>'

    for line in (1, 2, 3, 4):  # context (1, 4) and added (2, 3)
        assert messages(DIFF.format(notes=note("src/x.py", line))) == [], line


def test_diff_notes_rejects_removed_lines_and_out_of_range() -> None:
    got = messages(DIFF.format(notes='<q-diff-note file="src/x.py" line="5">n</q-diff-note>'))
    assert got == ["<q-diff-note> line 5 is not a new-side line of src/x.py"]
    # the removed line "gone" sits between new-side lines 1 and 2, so no number is "its" line
    assert messages(DIFF.format(notes='<q-diff-note file="src/x.py" line="40">n</q-diff-note>')) == [
        "<q-diff-note> line 40 is not a new-side line of src/x.py"
    ]


def test_a_removed_line_is_not_a_new_side_line() -> None:
    diff = "<q-diff><pre>--- a/f\n+++ b/f\n@@ -5,3 +5,2 @@\n a\n-b\n c</pre>{n}</q-diff>"
    ok = '<q-diff-note file="f" line="{v}">n</q-diff-note>'
    assert messages(diff.format(n=ok.format(v=5))) == []
    assert messages(diff.format(n=ok.format(v=6))) == []
    assert messages(diff.format(n=ok.format(v=7))) == ["<q-diff-note> line 7 is not a new-side line of f"]
    assert messages(diff.format(n=ok.format(v=4))) == ["<q-diff-note> line 4 is not a new-side line of f"]


def test_diff_notes_file_must_be_in_the_diff() -> None:
    got = messages(DIFF.format(notes='<q-diff-note file="x" line="2">n</q-diff-note>'))
    assert got == ['<q-diff-note> file="x" is not in its diff']


def test_diff_notes_strip_only_the_b_prefix_from_the_header() -> None:
    plain = "<q-diff><pre>--- a/m.py\n+++ m.py\n@@ -1 +1 @@\n+x</pre>{n}</q-diff>"
    note = '<q-diff-note file="{f}" line="1">n</q-diff-note>'
    assert messages(plain.format(n=note.format(f="m.py"))) == []
    prefixed = "<q-diff><pre>--- a/b/m.py\n+++ b/b/m.py\n@@ -1 +1 @@\n+x</pre>{n}</q-diff>"
    assert messages(prefixed.format(n=note.format(f="b/m.py"))) == []
    assert messages(prefixed.format(n=note.format(f="m.py"))) == ['<q-diff-note> file="m.py" is not in its diff']


def test_diff_notes_with_several_files_and_hunks() -> None:
    diff = (
        "<q-diff><pre>diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n"
        "@@ -1,2 +1,2 @@\n a\n-b\n+B\n"
        "@@ -20,2 +20,3 @@\n t\n+u\n v\n"
        "--- a/two.py\n+++ b/two.py\n@@ -3 +3,2 @@\n+p\n+q</pre>{n}</q-diff>"
    )
    note = '<q-diff-note file="{f}" line="{v}">n</q-diff-note>'
    good = [("one.py", 2), ("one.py", 20), ("one.py", 21), ("one.py", 22), ("two.py", 3), ("two.py", 4)]
    for f, v in good:
        assert messages(diff.format(n=note.format(f=f, v=v))) == [], (f, v)
    bad = [("one.py", 3), ("one.py", 19), ("two.py", 5), ("two.py", 1)]
    for f, v in bad:
        assert messages(diff.format(n=note.format(f=f, v=v))) == [
            f"<q-diff-note> line {v} is not a new-side line of {f}"
        ], (f, v)


def test_diff_notes_reads_entity_escaped_diff_text() -> None:
    diff = "<q-diff><pre>--- a/f\n+++ b/f\n@@ -1 +1 @@\n-if a &lt; b:\n+if a &amp;&amp; b &gt; 1:</pre>{n}</q-diff>"
    assert messages(diff.format(n='<q-diff-note file="f" line="1">n</q-diff-note>')) == []


def test_diff_notes_is_not_fooled_by_an_added_line_that_looks_like_a_header() -> None:
    diff = "<q-diff><pre>--- a/f\n+++ b/f\n@@ -1,2 +1,3 @@\n a\n--- x\n+++ y\n z</pre>{n}</q-diff>"
    note = '<q-diff-note file="{f}" line="{v}">n</q-diff-note>'
    assert messages(diff.format(n=note.format(f="f", v=3))) == []
    assert messages(diff.format(n=note.format(f="y", v=2))) == ['<q-diff-note> file="y" is not in its diff']


def test_diff_notes_tolerates_blank_context_lines_and_no_newline_markers() -> None:
    diff = "<q-diff><pre>--- a/f\n+++ b/f\n@@ -1,3 +1,3 @@\n a\n\n-c\n\\ No newline at end of file\n+d\n\\ No newline at end of file</pre>{n}</q-diff>"
    note = '<q-diff-note file="f" line="{v}">n</q-diff-note>'
    assert messages(diff.format(n=note.format(v=3))) == []
    assert messages(diff.format(n=note.format(v=4))) == ["<q-diff-note> line 4 is not a new-side line of f"]


def test_diff_notes_without_a_pre_adds_nothing_beyond_requires() -> None:
    assert messages('<q-diff><q-diff-note file="f" line="1">n</q-diff-note></q-diff>') == ["<q-diff> needs one of: pre"]


def test_heading_sections() -> None:
    bad = "<q-tabs><section><h3>A</h3></section><section><p>no heading</p></section></q-tabs>"
    assert messages(bad) == ["<q-tabs> section 2 does not start with a heading"]
    assert messages("<q-tabs><section><h1>A</h1></section></q-tabs>") == ["<q-tabs> section 1 does not start with a heading"]
    # the rule reads the first element child, so bare text before the heading is fine
    assert messages("<q-tabs><section>text<h3>A</h3></section></q-tabs>") == []
    assert messages("<q-tabs><section><p>x</p><h3>A</h3></section></q-tabs>") == ["<q-tabs> section 1 does not start with a heading"]
    assert messages("<q-tabs><section></section></q-tabs>") == ["<q-tabs> section 1 does not start with a heading"]
    for level in range(2, 7):
        assert messages(f"<q-tabs><section><h{level}>A</h{level}></section></q-tabs>") == []
    assert messages("<q-tabs><p>x</p></q-tabs>") == ["<q-tabs> needs one of: section"]


def test_heading_sections_counts_direct_child_sections_only() -> None:
    nested = "<q-tabs><section><h3>A</h3><section><p>inner</p></section></section><div>x</div><section><h3>B</h3></section></q-tabs>"
    assert messages(nested) == []


def test_board_columns() -> None:
    bad = '<q-board id="b"><section><h3>A</h3><ul><li>x</li></ul></section><section><ul><li>y</li></ul></section></q-board>'
    assert messages(bad) == ["<q-board> section 2 does not start with a heading"]
    good = '<q-board id="b"><section><h2>A</h2><ul><li>x</li></ul></section></q-board>'
    assert messages(good) == []
    assert messages('<q-board id="b"></q-board>') == ["<q-board> needs one of: section"]


def test_timeline_items() -> None:
    bad = (
        "<q-timeline><ol>"
        '<li><time datetime="2026-01-01">a</time> one</li>'
        '<li><time datetime="2026-01-02">b</time> two</li>'
        "<li>three</li></ol></q-timeline>"
    )
    assert messages(bad) == ["<q-timeline> item 3 has no <time datetime>"]
    assert messages('<q-timeline><ol><li><time>x</time></li></ol></q-timeline>') == [
        "<q-timeline> item 1 has no <time datetime>"
    ]
    assert messages("<q-timeline><ul><li>x</li></ul></q-timeline>") == ["<q-timeline> needs one of: ol"]


def compare(recommended: str, options: int = 3) -> str:
    heads = "<th>Criterion</th>" + "".join(f"<th>Option {i}</th>" for i in range(1, options + 1))
    cells = "<th>Cost</th>" + "".join("<td>1</td>" for _ in range(options))
    return (
        f'<q-compare recommended="{recommended}"><table><thead><tr>{heads}</tr></thead>'
        f"<tbody><tr>{cells}</tr></tbody></table></q-compare>"
    )


def test_compare_recommended_passes_across_the_option_range() -> None:
    for ok in ("1", "2", "3"):
        assert messages(compare(ok)) == [], ok


def test_compare_recommended_counts_option_columns_without_the_criteria_column() -> None:
    assert messages(compare("3", options=3)) == []
    got = messages(compare("4", options=3))
    assert got == ["<q-compare> recommended=\"4\" must be between 1 and 3 (the option columns)"]


def test_compare_recommended_fails_at_zero_and_names_the_range() -> None:
    got = messages(compare("0"))
    assert any("must be between 1 and 3" in m for m in got), got


def test_compare_with_no_option_columns_says_so() -> None:
    got = messages(compare("1", options=0))
    assert len(got) == 1 and "no option columns" in got[0] and "between 1 and" not in got[0], got


def test_compare_fails_a_table_wrapped_in_another_element() -> None:
    wrapped = compare("1").replace("<table>", "<div><table>").replace("</table>", "</table></div>")
    got = messages(wrapped)
    assert len(got) == 1 and "direct child" in got[0], got


def test_compare_needs_a_table_and_a_recommended_attribute() -> None:
    assert messages('<q-compare recommended="1"></q-compare>') == ["<q-compare> needs one of: table"]
    assert "<q-compare> needs attribute recommended" in messages(compare("1").replace(' recommended="1"', ""))


def test_panel_needs_a_heading_from_h2_to_h4() -> None:
    assert messages("<q-panel><p>body</p></q-panel>") == ["<q-panel> needs one of: h2, h3, h4"]
    assert messages("<q-panel><h5>too small</h5></q-panel>") == ["<q-panel> needs one of: h2, h3, h4"]
    for level in ("h2", "h3", "h4"):
        assert messages(f"<q-panel><{level}>Title</{level}><p>body</p></q-panel>") == [], level


def test_panel_span_is_an_enum() -> None:
    assert messages("<q-panel span=\"7\"><h3>T</h3></q-panel>") == ['<q-panel> span="7" is not one of 1, 2, 3, 4, full']
    for ok in ("1", "2", "3", "4", "full"):
        assert messages(f'<q-panel span="{ok}"><h3>T</h3></q-panel>') == [], ok


def test_timeline_tone() -> None:
    def item(tone: str) -> str:
        return f'<q-timeline><ol><li data-tone="{tone}"><time datetime="2026-01-01">a</time></li></ol></q-timeline>'

    assert messages(item("red")) == ['<q-timeline> item 1 data-tone="red" is not one of neutral, success, warning, danger']
    for ok in ("neutral", "success", "warning", "danger"):
        assert messages(item(ok)) == []


def test_unclosed_list_items_and_paragraphs_do_not_break_the_stack() -> None:
    board = (
        '<q-board id="b"><section><h3>A</h3><ul><li>one<li>two<li>three</ul></section>'
        "<section><h3>B</h3><p>para<p>para two<ul><li>x</ul></section></q-board>"
    )
    assert messages(board) == []
    tabs = "<q-tabs><section><h3>A</h3><p>unclosed<section><h3>B</h3><p>x</section></q-tabs>"
    assert messages(tabs) == []
    # an unclosed <li> before a bad section still counts sections correctly
    bad = '<q-board id="b"><section><h3>A</h3><ul><li>x<li>y</ul></section><section><ul><li>z</ul></section></q-board>'
    assert messages(bad) == ["<q-board> section 2 does not start with a heading"]


def test_implied_end_tags_for_table_cells_and_definition_lists() -> None:
    page = (
        "<q-table><table><thead><tr><th>a<th>b<tbody><tr><td>1<td>2<tr><td>3<td>4</table></q-table>"
        "<dl><dt>t<dd>d<dt>t2<dd>d2</dl><select><option>a<option>b</select>"
    )
    assert details(page) == []


def test_void_elements_do_not_swallow_siblings() -> None:
    tabs = "<q-tabs><section><h3>A</h3><br><img src=x><hr><input></section><section><h3>B</h3></section></q-tabs>"
    assert messages(tabs) == []
    assert messages("<q-tabs><section><br><h3>A</h3></section></q-tabs>") == ["<q-tabs> section 1 does not start with a heading"]


def test_an_end_tag_closes_unclosed_descendants_at_its_ancestor() -> None:
    tabs = "<q-tabs><section><h3>A</h3><div><span>open</section><section><h3>B</h3></section></q-tabs>"
    assert messages(tabs) == []


def test_stray_end_tags_are_ignored() -> None:
    assert details("</div></q-stat></p></section>" + STAT) == []


def test_self_closing_syntax_on_a_custom_element_follows_html() -> None:
    # html ignores the slash on a non-void element, so the element stays open: the section is its
    # child, and the only failure is the self-closing report
    got = messages('<q-tabs/><section><h3>A</h3></section>')
    assert got == ["<q-tabs> cannot be self-closed; write <q-tabs …></q-tabs>"]


def test_line_numbers_point_at_the_source_line() -> None:
    text = "<p>one</p>\n\n<q-stats>\n</q-stats>\n<q-chart>\n<table><thead><tr><th>a</th></tr></thead></table>\n</q-chart>\n"
    assert details(text, "x.src.html") == [
        "x.src.html line 3: unknown element <q-stats>",
        "x.src.html line 5: <q-chart> needs attribute summary",
    ]


def test_line_numbers_for_child_failures_name_the_child() -> None:
    text = (
        "<q-tabs>\n"
        "  <section>\n    <h3>A</h3>\n  </section>\n"
        "  <section>\n    <p>x</p>\n  </section>\n"
        "</q-tabs>\n"
        "<q-timeline>\n  <ol>\n"
        '    <li><time datetime="2026-01-01">a</time></li>\n'
        "    <li>b</li>\n"
        "  </ol>\n</q-timeline>\n"
    )
    assert details(text) == [
        "page.html line 5: <q-tabs> section 2 does not start with a heading",
        "page.html line 12: <q-timeline> item 2 has no <time datetime>",
    ]


def test_line_numbers_for_diff_notes_name_the_note() -> None:
    text = (
        "<q-diff>\n<pre>--- a/f\n+++ b/f\n@@ -1 +1 @@\n+x</pre>\n"
        '<q-diff-note file="f" line="1">ok</q-diff-note>\n'
        '<q-diff-note file="f" line="9">bad</q-diff-note>\n'
        "</q-diff>\n"
    )
    assert details(text) == ["page.html line 7: <q-diff-note> line 9 is not a new-side line of f"]


def test_failures_come_out_in_source_order() -> None:
    text = "<q-stats></q-stats>\n" + chart('type="pie"', table(2)) + "\n<q-bogus></q-bogus>\n"
    lines = [int(d.split(" line ")[1].split(":")[0]) for d in details(text)]
    assert lines == sorted(lines) and len(lines) == 3


def test_script_and_style_bodies_are_not_validated() -> None:
    page = (
        "<script>const html = '<q-stats></q-stats><q-chart>';</script>"
        "<style>/* <q-stats> */ q-stat { color: red }</style>"
        "<script type=\"module\">el.innerHTML = `<q-bogus>`</script>"
    )
    assert details(page) == []
    assert kitcheck.needs(page) == (True, True)


def test_markup_after_a_script_is_still_validated() -> None:
    assert messages("<script>var a = '<q-stats>'</script><q-stats></q-stats>") == ["unknown element <q-stats>"]


def test_template_content_is_validated() -> None:
    page = '<template x-if="open"><q-stats></q-stats></template>'
    assert messages(page) == ["unknown element <q-stats>"]
    ok = f'<template x-if="open">{STAT}</template>'
    assert messages(ok) == []


def test_comments_are_not_validated() -> None:
    assert details("<!-- <q-stats> --><p>x</p>") == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "<",
        "<q-",
        "<q-chart",
        "<q-chart summary=",
        '<q-chart summary="unterminated',
        "</q-chart",
        "<!--",
        "<![CDATA[ <q-stat>",
        "<q-tabs><section><h3>A",
        "<q-tabs></section></q-tabs></q-tabs></q-tabs>",
        "<q-diff><pre>@@ -x +y @@\n+++ \n--- \n@@",
        "<q-diff><pre>@@ -1 +1 @@\n" + "+x\n" * 50 + "</pre><q-diff-note file='f' line='99999999999999999999999'></q-diff-note></q-diff>",
        "<q-board id=b>" + "<section>" * 400 + "</q-board>",
        "<div>" * 5000 + "<q-stat></q-stat>" + "</div>" * 5000,
        "\x00\x01<q-\ud800>",
        "<q-chart summary=s y=\",,,\"><table></table></q-chart>",
    ],
)
def test_malformed_markup_never_crashes(text: str) -> None:
    result = kitcheck.check_html(text, CATALOG, label="m")
    assert isinstance(result, list)
    assert all(set(f) == {"check", "detail"} and f["check"] == "kit" for f in result)


def test_deeply_nested_markup_is_handled_without_recursion_errors() -> None:
    text = "<div>" * 20000 + STAT + "</div>" * 20000
    assert details(text) == []


# -- JSX ------------------------------------------------------------------------------------------


def jsx(*sources: str) -> list[str]:
    files = [(f"src/f{i}.tsx", text) for i, text in enumerate(sources)]
    return [f["detail"] for f in kitcheck.check_jsx(files, CATALOG)]


def test_jsx_accepts_valid_elements_and_expressions() -> None:
    src = """
    export function A({ rows, kind }) {
      return (
        <q-chart summary={`Spend by ${kind}`} type={kind} stacked data-from="rows" className="wide" />
      );
    }
    """
    assert jsx(src) == []


def test_jsx_unknown_tag() -> None:
    assert jsx("const a = <q-stats />;") == ["src/f0.tsx line 1: unknown element <q-stats>"]


def test_jsx_missing_required_attribute_in_any_form() -> None:
    assert jsx("const a = <q-chart type=\"line\" data-from=\"r\" />;") == ["src/f0.tsx line 1: <q-chart> needs attribute summary"]
    for ok in ('summary="s"', "summary={text}", "summary", "summary={'s'}"):
        assert jsx(f'const a = <q-chart {ok} data-from="r" />;') == [], ok
    assert jsx('const a = <q-chart {...props} data-from="r" />;') == []
    assert jsx('const a = <q-diff-note file="f">n</q-diff-note>;') == ["src/f0.tsx line 1: <q-diff-note> needs attribute line"]


def test_jsx_literal_values_are_checked_against_their_kinds() -> None:
    assert jsx('const a = <q-chart summary="s" type="pie" data-from="r" />;') == [
        'src/f0.tsx line 1: <q-chart> type="pie" is not one of bar, line, area, donut'
    ]
    assert jsx("const a = <q-chart summary='s' type={\"pie\"} data-from='r' />;") == [
        'src/f0.tsx line 1: <q-chart> type="pie" is not one of bar, line, area, donut'
    ]
    assert jsx('const a = <q-stat points="a,b"><span slot="label"/></q-stat>;') == [
        'src/f0.tsx line 1: <q-stat> points="a,b" is not a number list'
    ]
    assert jsx('const a = <q-diff-note file="f" line="0" />;') == [
        'src/f0.tsx line 1: <q-diff-note> line="0" is not a positive integer'
    ]
    assert jsx('const a = <q-board id="9x" />;') == ['src/f0.tsx line 1: <q-board> id="9x" is not an identifier']


def test_jsx_expression_values_are_never_checked() -> None:
    assert jsx('const a = <q-chart summary="s" type={kind === "x" ? "pie" : "bar"} data-from="r" />;') == []
    assert jsx('const a = <q-stat points={[1, 2, 3].join(",")} />;') == []


def test_jsx_style_object_and_nested_braces_parse() -> None:
    src = """
    const a = (
      <q-chart
        summary="s"
        style={{ width: '50%', ['--x']: `${a > 1 ? "}" : "{"}` }}
        type="line"
        onClick={() => { if (x) { go({ a: { b: 1 } }); } }}
        data-from="rows"
      >
        <span>{items.map((i) => <b key={i}>{i}</b>)}</span>
      </q-chart>
    );
    """
    assert jsx(src) == []
    bad = src.replace('type="line"', 'type="pie"')
    assert jsx(bad) == ['src/f0.tsx line 3: <q-chart> type="pie" is not one of bar, line, area, donut']


def test_jsx_greater_than_inside_braces_does_not_end_the_tag() -> None:
    assert jsx('const a = <q-chart summary={a > b ? "x" : "y"} data-from="r">hi</q-chart>;') == []
    assert jsx('const a = <q-chart summary={x => x > 1} />;') == []


def test_jsx_child_rules_are_skipped() -> None:
    assert jsx("const a = <q-tabs><p>nothing</p></q-tabs>;") == []
    assert jsx('const a = <q-diff-note file="f" line="1">outside a diff</q-diff-note>;') == []
    assert jsx("const a = <q-stat></q-stat>;") == []
    assert jsx("const a = <q-timeline />;") == []


def test_jsx_lines_are_one_based_per_file_and_labelled() -> None:
    first = "const a = 1;\n\nconst b = <q-stats />;\n"
    second = "\n\n\nconst c = (\n  <q-chart\n    type=\"line\"\n  />\n);\n"
    got = jsx(first, second)
    assert got == [
        "src/f0.tsx line 3: unknown element <q-stats>",
        "src/f1.tsx line 5: <q-chart> needs attribute summary",
    ]


def test_jsx_finds_several_elements_on_one_line() -> None:
    assert jsx("x = <><q-stats /><q-bogus /></>;") == [
        "src/f0.tsx line 1: unknown element <q-stats>",
        "src/f0.tsx line 1: unknown element <q-bogus>",
    ]


def test_jsx_does_not_match_lookalike_tags() -> None:
    assert jsx("const a = <q-Stats />; const b = <qx-stat />; const c = x<q-1; const d = '&lt;q-stats&gt;';") == []


def test_jsx_works_on_plain_html_files_too() -> None:
    assert jsx('<q-stats summary="x"></q-stats>') == ["src/f0.tsx line 1: unknown element <q-stats>"]


@pytest.mark.parametrize(
    "text",
    [
        "<q-chart",
        "<q-chart summary=",
        '<q-chart summary="x',
        "<q-chart summary={",
        "<q-chart summary={`${",
        "<q-chart a={{{{{{{{{",
        "<q-chart a=}}}}} />",
        "<q-chart =",
        "<q-chart / />",
        "<q-chart {...",
        "<q-chart " + "{" * 10000,
        "\x00<q-chart\ud800 />",
    ],
)
def test_jsx_malformed_input_never_crashes(text: str) -> None:
    assert isinstance(kitcheck.check_jsx([("f.tsx", text)], CATALOG), list)


# -- run_checks: lazy loading, version selection, the not-inlined failure --------------------------


def _catalog_with(*specs: dict) -> kitcheck.Catalog:
    elements = {}
    for spec in specs:
        attrs = tuple(
            kitcheck.Attribute(name=n, required=r, kind=k, description="d", values=v)
            for n, r, k, v in spec["attrs"]
        )
        elements[spec["tag"]] = kitcheck.Element(
            tag=spec["tag"],
            use_when="Use when testing.",
            parent=spec.get("parent"),
            interactive=True,
            attributes=attrs,
            requires=tuple(tuple(g) for g in spec.get("requires", [])),
            rules=tuple(spec.get("rules", [])),
            children="c",
            example="e",
        )
    return kitcheck.Catalog(kit_version="0.0.1", global_attributes=("id",), elements=elements)


def _probe_messages(catalog: kitcheck.Catalog, text: str) -> list[str]:
    return [f["detail"].split(": ", 1)[1] for f in kitcheck.check_html(text, catalog, label="p")]


def _registry_without_kit(tmp_path: Path) -> vendor.VendorStore:
    root = tmp_path / "vendor"
    root.mkdir()
    (root / "libraries.json").write_text(json.dumps({"schema": 1, "libraries": {}}), encoding="utf-8")
    return vendor.VendorStore([root / "libraries.json"])


def page(body: str, *, libraries: dict | None = None, blocks: str = "") -> str:
    from htmlkit import header

    meta = {
        "schema": 1,
        "template": "t",
        "template_level": "builtin",
        "tier": 1,
        "tier_signal": None,
        "mode": "offline",
        "libraries": libraries or {},
        "sidecar": None,
        "built_at": "2026-10-14T00:00:00Z",
        "quirk_version": "unknown",
    }
    return f"<!doctype html>\n{header.render_header(meta)}\n<html><head><title>t</title></head><body>\n{body}\n{blocks}</body></html>\n"


def run(html: str, store: vendor.VendorStore, **kwargs):
    return checks.run_checks(html, mode="offline", tier=1, vendor=store, shells={}, **kwargs)


def kit_blocks() -> str:
    lv = REAL_STORE.resolve("kit", None)
    blocks = REAL_STORE.inline_blocks(lv)
    return REAL_STORE.license_comment(lv) + "\n" + "\n".join(b.text for b in blocks) + "\n"


def test_a_page_without_q_tags_never_loads_the_catalog(tmp_path: Path) -> None:
    store = _registry_without_kit(tmp_path)
    result = run(page("<p>plain</p>"), store)
    assert result == {"passed": True, "failures": [], "warnings": []}
    result = run(page("<p>plain</p>"), store, kit_source=("a.src.html", "<p>plain</p>"))
    assert result["passed"] is True


def test_a_missing_kit_entry_is_one_failure_when_q_tags_exist(tmp_path: Path) -> None:
    store = _registry_without_kit(tmp_path)
    result = run(page(STAT, libraries={}, blocks=""), store)
    kit = [f for f in result["failures"] if f["check"] == "kit"]
    assert kit[0]["detail"].startswith("cannot load the kit catalog: ")
    assert "kit" in kit[0]["detail"]
    assert sum(f["detail"].startswith("cannot load") for f in kit) == 1


def test_the_catalog_loads_at_the_version_the_header_records(tmp_path: Path) -> None:
    html = page(STAT, libraries={"kit": "9.9.9"}, blocks=kit_blocks())
    result = run(html, REAL_STORE)
    details_ = [f["detail"] for f in result["failures"] if f["check"] == "kit"]
    assert len(details_) == 1 and details_[0].startswith("cannot load the kit catalog: ")
    assert "kit@9.9.9" in details_[0]


def test_built_page_with_q_tags_and_no_kit_block_fails() -> None:
    html = page(STAT)
    line = html[: html.index("<q-stat")].count("\n") + 1
    result = run(html, REAL_STORE)
    assert [f["detail"] for f in result["failures"] if f["check"] == "kit"] == [
        f"page line {line}: kit elements are used but the kit is not inlined"
    ]
    assert result["passed"] is False


def test_built_page_with_the_kit_block_passes() -> None:
    html = page(STAT, libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    assert run(html, REAL_STORE) == {"passed": True, "failures": [], "warnings": []}


def test_kit_markup_failures_on_a_built_page_cite_the_page_lines() -> None:
    html = page("<q-stats></q-stats>", libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    line = html[: html.index("<q-stats>")].count("\n") + 1
    result = run(html, REAL_STORE, kit_source=("deck.html", html))
    assert [f["detail"] for f in result["failures"]] == [f"deck.html line {line}: unknown element <q-stats>"]


def test_kit_source_text_is_what_gets_scanned() -> None:
    html = page("<p>built page has none</p>")
    source = "<!-- quirk-src {} -->\n<!-- slot: main -->\n<q-stats></q-stats>\n"
    result = run(html, REAL_STORE, kit_source=("a.src.html", source))
    assert [f["detail"] for f in result["failures"]] == ["a.src.html line 3: unknown element <q-stats>"]


def test_script_bodies_in_the_built_page_are_not_validated() -> None:
    html = page("<script>el.innerHTML = '<q-stats>'</script>", libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    assert run(html, REAL_STORE)["passed"] is True


def test_existing_call_signature_still_works(tmp_path: Path) -> None:
    store = _registry_without_kit(tmp_path)
    result = checks.run_checks(page("<p>x</p>"), mode="offline", tier=1, vendor=store)
    assert result["passed"] is True


def test_a_long_digit_run_in_a_number_list_is_rejected_in_linear_time() -> None:
    start = time.perf_counter()
    got = messages(STAT.replace('points="1,2,3"', 'points="' + "1" * 100_000 + 'x,1"'))
    assert time.perf_counter() - start < 1
    assert len(got) == 1 and got[0].endswith("is not a number list")


def test_deeply_nested_kit_elements_are_checked_in_linear_time() -> None:
    depth = 8000
    start = time.perf_counter()
    got = details("<q-code>" * depth + "<pre><code>x</code></pre>" + "</q-code>" * depth)
    assert time.perf_counter() - start < 3
    assert got == []
    assert messages("<q-code>" * 3 + "</q-code>" * 3) == ["<q-code> needs one of: pre"] * 3


def test_requires_still_looks_below_the_element_only() -> None:
    assert messages("<q-code></q-code><pre>x</pre>") == ["<q-code> needs one of: pre"]
    assert messages("<q-code><div><pre>x</pre></div></q-code>") == []


def test_a_self_closed_kit_tag_is_reported_and_the_tree_stays_open() -> None:
    got = messages('<q-chart summary="s" data-from="rows" />')
    assert got == ["<q-chart> cannot be self-closed; write <q-chart …></q-chart>"]
    # the open q-chart reads the next table as its inline table, as a browser would
    assert any("cannot be self-closed" in m for m in messages('<q-chart summary="s" data-from="rows" />' + table(3)))
    assert not any("cannot be self-closed" in m for m in messages(chart('data-from="rows"')))


# -- parser faults and worst-case input -------------------------------------------------------------


def test_a_marked_section_does_not_stop_the_check() -> None:
    got = messages("<![foo ]]>\n<q-stats></q-stats>\n" + chart().replace('summary="s"', ""))
    assert "unknown element <q-stats>" in got
    assert "<q-chart> needs attribute summary" in got


def test_a_parser_exception_is_a_failure_that_keeps_earlier_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(self, data):
        raise AssertionError("boom")

    monkeypatch.setattr(kitcheck._TreeBuilder, "handle_comment", explode)
    got = details("<q-stats></q-stats>\n<q-stat></q-stat>\n<!-- x -->\n<q-nope></q-nope>")
    assert got[0] == "page.html line 1: unknown element <q-stats>"
    assert got[-1] == "page.html line 3: could not parse the markup after this line; the kit check stopped here"
    assert not any("q-nope" in d for d in got)


def test_nested_diffs_are_checked_in_linear_time() -> None:
    depth = 8000
    start = time.perf_counter()
    got = details("<q-diff><pre>x</pre>" * depth + "</q-diff>" * depth)
    assert time.perf_counter() - start < 3
    assert got == []


def test_nested_charts_timelines_and_notes_are_checked_in_linear_time() -> None:
    depth = 8000
    start = time.perf_counter()
    charts = details('<q-chart summary="s" data-from="r">' * depth + "</q-chart>" * depth)
    notes = details("<q-diff-note file='f' line='1'>" * depth + "</q-diff-note>" * depth)
    items = details("<q-timeline><ol><li>" * depth + "</li></ol></q-timeline>" * depth)
    assert time.perf_counter() - start < 6
    with_notes = details("<q-diff><pre>x</pre><q-diff-note file='f' line='1'></q-diff-note>" * depth + "</q-diff>" * depth)
    assert charts == []
    assert len(with_notes) == depth
    assert len(notes) == depth and all(n.endswith("<q-diff-note> must be inside <q-diff>") for n in notes)
    assert len(items) == depth and all(i.endswith("has no <time datetime>") for i in items)


def test_a_note_belongs_to_its_nearest_diff_only() -> None:
    inner = "<q-diff><pre>--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n+x</pre><q-diff-note file='b.py' line='1'></q-diff-note></q-diff>"
    assert messages("<q-diff><pre>--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n+x</pre>" + inner + "</q-diff>") == []


def test_a_paragraph_holding_a_button_does_not_make_block_starts_quadratic() -> None:
    start = time.perf_counter()
    got = details("<q-code></q-code><p><button>" + "<div>" * 20000)
    assert time.perf_counter() - start < 3
    assert got == ["page.html line 1: <q-code> needs one of: pre"]


def test_a_block_start_still_closes_an_open_paragraph_outside_a_scope_marker() -> None:
    assert messages("<q-tabs><p>x<section><h3>A</h3></section></q-tabs>") == messages(
        "<q-tabs><p>x</p><section><h3>A</h3></section></q-tabs>"
    )


def test_jsx_ignores_tags_in_unambiguous_comments() -> None:
    assert jsx("// the <q-chart> element draws it\nconst a = 1;") == []
    assert jsx("  // the <q-chart> element draws it\nconst a = 1;") == []
    assert jsx("/* the <q-chart>\n   element */\nconst a = 1;") == []
    assert jsx("  /* the <q-chart> element */ const a = 1;") == []
    assert jsx("{/* <q-chart> */}") == []
    assert jsx("<p>{ /* the <q-chart>\n element */ }</p>") == []


def test_jsx_comment_masking_stops_at_the_closing_terminator() -> None:
    got = jsx("/* note */ const e = <q-chart />;\n")
    assert got == ["src/f0.tsx line 1: <q-chart> needs attribute summary"]
    assert jsx("{/* note */ <q-chart /> }") == ["src/f0.tsx line 1: <q-chart> needs attribute summary"]


@pytest.mark.parametrize(
    "source",
    [
        'const hint = "glob like src/ /* here";\nexport const A = () => <q-stats />;\n',
        'const glob = "all files /* here";\nexport const A = () => <q-stats />;',
        "const a = <p>see // here</p>; const b = <q-stats />;",
        "const a = <p>glob /* here</p>; const b = <q-stats />;",
        "const a = 1; // see\nconst b = <q-stats />;",
        "/* never closed\nconst b = <q-stats />;",
        "const a = 1; /* never closed\nconst b = <q-stats />;\n",
    ],
)
def test_jsx_text_that_might_be_a_comment_never_hides_a_later_tag(source: str) -> None:
    assert [m for m in jsx(source) if m.endswith("unknown element <q-stats>")] != []


def test_jsx_mid_line_comment_text_is_still_scanned() -> None:
    assert jsx("const a = 1; // see <q-chart>\n") == ["src/f0.tsx line 1: <q-chart> needs attribute summary"]
    assert jsx("/* <q-chart> never closed") == ["src/f0.tsx line 1: <q-chart> needs attribute summary"]


def test_jsx_html_comments_are_masked_in_html_files_only() -> None:
    def labelled(label: str, text: str) -> list[dict]:
        return kitcheck.check_jsx([(label, text)], CATALOG)

    assert labelled("index.html", "<!-- the <q-chart> element -->\n<div id=root></div>") == []
    assert labelled("index.html", "<!-- never closed <q-chart>") != []
    assert labelled("src/a.tsx", "<!-- the <q-chart> element -->") != []
    assert labelled("index.html", "<!-- a --><q-stats />") == [
        {"check": "kit", "detail": "index.html line 1: unknown element <q-stats>"}
    ]


def test_jsx_q_tag_text_in_a_string_is_still_checked() -> None:
    assert jsx('const msg = "use the <q-chart> element";') == [
        "src/f0.tsx line 1: <q-chart> needs attribute summary"
    ]


def test_jsx_comment_masking_keeps_real_tags_and_their_lines() -> None:
    got = jsx('// <q-chart>\nconst u = "http://x"; const e = <q-chart />;\n')
    assert got == ["src/f0.tsx line 2: <q-chart> needs attribute summary"]
    assert jsx('<p>see http://x</p> <q-chart summary="s" src="//cdn.x/y" />') == []


def test_jsx_unterminated_tags_are_scanned_in_linear_time() -> None:
    start = time.perf_counter()
    got = jsx("<q-chart " * 8000)
    assert time.perf_counter() - start < 2
    assert len(got) == 8000


def test_jsx_unterminated_braces_are_scanned_in_linear_time() -> None:
    for source in ("<q-chart a={" * 8000, "<q-chart {" * 8000, "<q-chart summary={" * 8000):
        start = time.perf_counter()
        got = jsx(source)
        assert time.perf_counter() - start < 3
        assert len(got) in (0, 8000)


def test_jsx_attribute_braces_still_end_where_they_close() -> None:
    assert jsx('<q-chart summary={"a}"} />') == []
    assert jsx("<q-chart summary={`x ${a} }`} />") == []
    assert jsx("<q-chart a={<q-stats />} />") == [
        "src/f0.tsx line 1: <q-chart> needs attribute summary",
        "src/f0.tsx line 1: unknown element <q-stats>",
    ]


def test_nested_diffs_over_one_pre_are_checked_in_linear_time() -> None:
    diff = "--- a/f\n+++ b/f\n@@ -1,40000 +1,40000 @@\n" + "\n".join(f" line {i}" for i in range(40000))
    start = time.perf_counter()
    got = details("<q-diff>" * 1000 + "<pre>" + diff + "</pre>" + "</q-diff>" * 1000)
    assert time.perf_counter() - start < 3
    assert got == []


def test_nested_diffs_parse_their_shared_pre_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = kitcheck.parse_diff
    monkeypatch.setattr(kitcheck, "parse_diff", lambda text: calls.append(text) or real(text))
    note = "<q-diff-note file='f' line='1'></q-diff-note>"
    got = details("<q-diff>" * 5 + "<pre>--- a/f\n+++ b/f\n@@ -1 +1 @@\n+x</pre>" + note * 3 + "</q-diff>" * 5)
    assert len(calls) == 1
    assert got == []


def test_nested_timelines_over_one_list_report_each_item_once() -> None:
    items = 3000
    start = time.perf_counter()
    got = messages("<q-timeline>" * items + "<ol>" + "<li>x</li>" * items + "</ol>" + "</q-timeline>" * items)
    assert time.perf_counter() - start < 3
    assert len([m for m in got if m.endswith("has no <time datetime>")]) <= items


def test_nested_charts_over_one_table_with_many_theads_are_checked_in_linear_time() -> None:
    start = time.perf_counter()
    got = details('<q-chart summary="s">' * 8000 + "<table>" + "<thead></thead>" * 8000 + "</table>" + "</q-chart>" * 8000)
    assert time.perf_counter() - start < 3
    assert got == []


def test_unclosed_items_under_an_svg_do_not_make_implied_ends_quadratic() -> None:
    start = time.perf_counter()
    got = details("<q-code></q-code><li><svg>" + "<b>" * 16000 + "<li/>" * 16000)
    assert time.perf_counter() - start < 3
    assert got == ["page.html line 1: <q-code> needs one of: pre"]


def test_implied_ends_for_lists_and_tables_match_the_html_rules() -> None:
    assert messages("<ul><li>a<li>b<ul><li>c</ul><li>d</ul>" + STAT) == []
    assert messages("<q-code><dl><dt>a<dd>b<dt>c</dl><table><tr><td>1<td>2<tr><td>3</table></q-code>") == [
        "<q-code> needs one of: pre"
    ]


# -- q-flow: rule flow-data and warnings (SC-3) -----------------------------------------------------


def flow_markup(payload: dict, attrs: str = 'summary="Orders flow."') -> str:
    return f'<q-flow {attrs}><script type="application/json">{json.dumps(payload)}</script></q-flow>'


def warn_messages(text: str) -> list[str]:
    return [w["detail"].split(": ", 1)[1] for w in kitcheck.check_html_warnings(text, CATALOG, label="page.html")]


def test_flow_valid_graph_passes_with_no_warnings() -> None:
    payload = {
        "kinds": {"ui": 1, "worker": 2},
        "groups": [{"id": "billing", "label": "Billing"}],
        "nodes": [
            {"id": "checkout", "label": "Checkout", "kind": "ui"},
            {"id": "charge", "label": "Charge worker", "kind": "worker", "group": "billing", "detail": "<p>Retries 3x.</p>"},
        ],
        "edges": [{"from": "checkout", "to": "charge", "label": "order.created", "async": True}],
    }
    assert messages(flow_markup(payload)) == []
    assert warn_messages(flow_markup(payload)) == []


def test_flow_missing_summary_and_duplicate_id_and_unknown_edge_node() -> None:
    assert messages('<q-flow><script type="application/json">{"nodes":[{"id":"a","label":"A"}]}</script></q-flow>') == [
        "<q-flow> needs attribute summary"
    ]
    dup = {"nodes": [{"id": "charge", "label": "Charge"}, {"id": "charge", "label": "Charge 2"}]}
    assert any('duplicate id "charge"' in m for m in messages(flow_markup(dup)))
    unknown_edge = {"nodes": [{"id": "a", "label": "A"}], "edges": [{"from": "a", "to": "ledgr"}]}
    assert any('edge points at unknown node "ledgr"' in m for m in messages(flow_markup(unknown_edge)))


def test_flow_undeclared_kind_and_more_than_eight_kinds() -> None:
    undeclared = {"kinds": {"ui": 1}, "nodes": [{"id": "a", "label": "A", "kind": "cache"}]}
    assert any('undeclared kind "cache"' in m for m in messages(flow_markup(undeclared)))
    nine_kinds = {
        "kinds": {f"k{i}": min(i, 8) for i in range(1, 10)},
        "nodes": [{"id": "a", "label": "A"}],
    }
    assert any("at most eight kinds, one per chart color" in m for m in messages(flow_markup(nine_kinds)))


def test_flow_group_nesting_loop_and_lane_mode_membership() -> None:
    self_loop = {
        "groups": [{"id": "g1", "label": "G1", "parent": "g1"}],
        "nodes": [{"id": "a", "label": "A", "group": "g1"}],
    }
    assert any("group nesting loops" in m for m in messages(flow_markup(self_loop)))
    cycle = {
        "groups": [{"id": "g1", "label": "G1", "parent": "g2"}, {"id": "g2", "label": "G2", "parent": "g1"}],
        "nodes": [{"id": "a", "label": "A", "group": "g1"}],
    }
    assert any("group nesting loops" in m for m in messages(flow_markup(cycle)))
    outside_lane = {
        "groups": [{"id": "intake", "label": "Intake"}],
        "nodes": [{"id": "a", "label": "A", "group": "intake"}, {"id": "b", "label": "B"}],
    }
    assert any(
        "in lane mode every node belongs to a lane" in m
        for m in messages(flow_markup(outside_lane, attrs='summary="s" groups="lanes"'))
    )


def test_flow_detail_rejects_scripts_forms_and_external_images() -> None:
    for bad_detail in (
        "<script>alert(1)</script>",
        "<form><input></form>",
        '<img src="https://example.com/x.png">',
        '<p onclick="evil()">hi</p>',
        '<a href="javascript:alert(1)">bad</a>',
    ):
        payload = {"nodes": [{"id": "a", "label": "A", "detail": bad_detail}]}
        assert any("detail may hold only paragraphs, lists, code and links" in m for m in messages(flow_markup(payload))), bad_detail


def test_flow_node_limits_and_edge_label_warning_and_coordinates_rejected() -> None:
    warn_75 = {"nodes": [{"id": f"n{i}", "label": f"Node {i}"} for i in range(75)]}
    assert messages(flow_markup(warn_75)) == []
    assert any("large graphs read poorly, split into groups or several graphs" in w for w in warn_messages(flow_markup(warn_75)))

    fail_210 = {"nodes": [{"id": f"n{i}", "label": f"Node {i}"} for i in range(210)]}
    assert any("more than 200 nodes" in m for m in messages(flow_markup(fail_210)))

    long_lbl = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x" * 45}],
    }
    assert messages(flow_markup(long_lbl)) == []
    assert any("edge labels over 30 characters crowd the layout" in w for w in warn_messages(flow_markup(long_lbl)))

    with_coords = {"nodes": [{"id": "a", "label": "A", "x": 10, "y": 20}]}
    assert any("positions are laid out automatically" in m for m in messages(flow_markup(with_coords)))


def decision_graph(exits: list[dict], label: str = "Paid?", extra_nodes: list[dict] | None = None) -> dict:
    return {
        "nodes": [
            {"id": "paid", "label": label, "shape": "decision"},
            {"id": "ship", "label": "Ship"},
            {"id": "retry", "label": "Retry"},
            *(extra_nodes or []),
        ],
        "edges": [{"from": "paid", **x} for x in exits],
    }


def test_flow_unknown_shape_fails() -> None:
    payload = {"nodes": [{"id": "a", "label": "A", "shape": "oval"}]}
    assert messages(flow_markup(payload)) == ['<q-flow> node "a" has unknown shape "oval"; use box, decision or subprocess']
    assert messages(flow_markup({"nodes": [{"id": "a", "label": "A", "shape": "box"}]})) == []


def test_flow_decision_needs_two_exits() -> None:
    one_exit = decision_graph([{"to": "ship", "label": "Yes"}])
    assert messages(flow_markup(one_exit)) == ['<q-flow> decision "paid" needs at least 2 exits']
    no_exit = decision_graph([])
    assert messages(flow_markup(no_exit)) == ['<q-flow> decision "paid" needs at least 2 exits']


def test_flow_decision_exits_need_labels() -> None:
    expected = ['<q-flow> every exit of decision "paid" needs a label']
    missing = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry"}])
    assert messages(flow_markup(missing)) == expected
    empty = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry", "label": "  "}])
    assert messages(flow_markup(empty)) == expected


def test_flow_loop_exit_counts_toward_a_decisions_two_exits_and_needs_a_label() -> None:
    labelled = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry", "label": "No", "loop": True}])
    assert messages(flow_markup(labelled)) == []
    unlabelled = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry", "loop": True}])
    assert messages(flow_markup(unlabelled)) == ['<q-flow> every exit of decision "paid" needs a label']
    self_exit = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "paid", "label": "Again"}])
    assert messages(flow_markup(self_exit)) == []


def test_flow_decision_label_over_24_characters_warns() -> None:
    exits = [{"to": "ship", "label": "Yes"}, {"to": "retry", "label": "No"}]
    long_label = "Has the customer confirmed their address?"
    payload = decision_graph(exits, label=long_label)
    assert messages(flow_markup(payload)) == []
    assert warn_messages(flow_markup(payload)) == [
        '<q-flow> decision "paid" label is 41 characters: decision labels over 24 characters overflow the diamond'
    ]
    assert warn_messages(flow_markup(decision_graph(exits, label="x" * 24))) == []
    long_box = {"nodes": [{"id": "a", "label": long_label}]}
    assert warn_messages(flow_markup(long_box)) == []


def test_flow_decision_exits_with_the_same_label_warn() -> None:
    twice = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry", "label": "Yes"}])
    assert messages(flow_markup(twice)) == []
    assert warn_messages(flow_markup(twice)) == ['<q-flow> decision "paid" has two exits labelled "Yes"']
    differing_case = decision_graph([{"to": "ship", "label": "Yes"}, {"to": "retry", "label": "yes"}])
    assert warn_messages(flow_markup(differing_case)) == []


def test_flow_names_a_flow_only_on_a_subprocess() -> None:
    expected = ['<q-flow> node "a" names a flow, but only a subprocess can name a flow']
    for shape in ({}, {"shape": "box"}, {"shape": "decision"}):
        payload = {"nodes": [{"id": "a", "label": "A", "flow": "other", **shape}]}
        assert expected[0] in messages(flow_markup(payload)), shape
    non_string = {"nodes": [{"id": "a", "label": "A", "flow": 7}]}
    assert messages(flow_markup(non_string)) == expected


def test_flow_subprocess_flow_must_be_a_non_empty_string() -> None:
    expected = ['<q-flow> node "a" flow must be the id of another q-flow']
    for bad in ("", "  ", 7, True, ["x"]):
        payload = {"nodes": [{"id": "a", "label": "A", "shape": "subprocess", "flow": bad}]}
        assert messages(flow_markup(payload)) == expected, bad
    without_flow = {"nodes": [{"id": "a", "label": "A", "shape": "subprocess"}]}
    assert messages(flow_markup(without_flow)) == []


def test_flow_subprocess_flow_names_another_graph_on_the_page() -> None:
    main = {"nodes": [{"id": "a", "label": "A", "shape": "subprocess", "flow": "refund-flow"}]}
    other = {"nodes": [{"id": "r", "label": "Refund"}]}
    page = flow_markup(main, attrs='id="main-flow" summary="Main."') + flow_markup(
        other, attrs='id="refund-flow" summary="Refund."'
    )
    assert messages(page) == []
    assert warn_messages(page) == []

    swapped = flow_markup(other, attrs='id="refund-flow" summary="Refund."') + flow_markup(
        main, attrs='id="main-flow" summary="Main."'
    )
    assert messages(swapped) == []


def test_flow_subprocess_flow_naming_no_graph_or_its_own_graph_fails() -> None:
    main = {"nodes": [{"id": "a", "label": "A", "shape": "subprocess", "flow": "refunds"}]}
    lone = flow_markup(main, attrs='id="main-flow" summary="Main."')
    assert messages(lone) == ['<q-flow> flow "refunds" names no q-flow on this page']

    elsewhere = flow_markup({"nodes": [{"id": "r", "label": "R"}]}, attrs='id="refund-flow" summary="R."')
    assert messages(lone + elsewhere) == ['<q-flow> flow "refunds" names no q-flow on this page']

    own = {"nodes": [{"id": "a", "label": "A", "shape": "subprocess", "flow": "main-flow"}]}
    assert messages(flow_markup(own, attrs='id="main-flow" summary="Main."')) == [
        '<q-flow> flow "main-flow" names no q-flow on this page'
    ]


def test_flow_loop_must_be_a_boolean() -> None:
    expected = ["<q-flow> edge loop must be true or false"]
    for bad in ("yes", 1, "true", ["x"]):
        payload = {
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a", "loop": bad}],
        }
        assert messages(flow_markup(payload)) == expected, bad


def test_flow_cycle_over_forward_edges_warns_once_per_component() -> None:
    payload = {
        "nodes": [{"id": n, "label": n.upper()} for n in ("a", "b", "c", "d", "e", "f")],
        "edges": [
            {"from": "e", "to": "f"},
            {"from": "f", "to": "e"},
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "a"},
            {"from": "c", "to": "d"},
        ],
    }
    assert messages(flow_markup(payload)) == []
    assert warn_messages(flow_markup(payload)) == [
        '<q-flow> has a cycle with no loop edge through "a", "b", "c": mark the return edge with loop: true',
        '<q-flow> has a cycle with no loop edge through "e", "f": mark the return edge with loop: true',
    ]


def test_flow_cycle_broken_by_a_loop_edge_or_a_self_loop_does_not_warn() -> None:
    marked = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a", "loop": True}],
    }
    assert warn_messages(flow_markup(marked)) == []
    self_loop = {
        "nodes": [{"id": "poll", "label": "Status poller"}],
        "edges": [{"from": "poll", "to": "poll", "label": "every 30s"}],
    }
    assert messages(flow_markup(self_loop)) == []
    assert warn_messages(flow_markup(self_loop)) == []
    marked_self_loop = {**self_loop, "edges": [{"from": "poll", "to": "poll", "loop": True}]}
    assert warn_messages(flow_markup(marked_self_loop)) == []


def test_flow_graph_using_every_new_field_passes_clean() -> None:
    main = {
        "kinds": {"ui": 1, "worker": 2, "queue": 3},
        "nodes": [
            {"id": "checkout", "label": "Checkout", "kind": "ui"},
            {"id": "charge", "label": "Charge worker", "kind": "worker"},
            {"id": "paid", "label": "Paid?", "kind": "worker", "shape": "decision"},
            {"id": "ship", "label": "Ship", "kind": "worker"},
            {"id": "retry", "label": "Retry queue", "kind": "queue"},
            {"id": "refund", "label": "Issue refund", "shape": "subprocess", "flow": "refund-flow"},
            {"id": "poll", "label": "Status poller"},
        ],
        "edges": [
            {"from": "checkout", "to": "charge", "label": "order.created", "async": True},
            {"from": "charge", "to": "paid"},
            {"from": "paid", "to": "ship", "label": "Yes"},
            {"from": "paid", "to": "retry", "label": "No"},
            {"from": "retry", "to": "charge", "label": "retry up to 3x", "loop": True},
            {"from": "ship", "to": "refund", "label": "on return"},
            {"from": "poll", "to": "poll", "label": "every 30s"},
        ],
    }
    page = flow_markup(main, attrs='id="checkout-flow" summary="Checkout."') + flow_markup(
        {"nodes": [{"id": "r", "label": "Refund"}]}, attrs='id="refund-flow" summary="Refund."'
    )
    assert messages(page) == []
    assert warn_messages(page) == []


# -- q-flow: traces and edge ids ---------------------------------------------------------------------

ORDER_V1 = {"order": "R-1042", "status": "queued", "lines": [{"item": "Coffee beans", "qty": 2, "price": 18}]}
ORDER_V2 = {**ORDER_V1, "subtotal": 36, "discount": {"code": "LOYALTY10", "amount": 3.6}, "total": 32.4}
ORDER_V3 = {**ORDER_V2, "tax": 2.67, "total": 35.07}
ORDER_V4 = {**ORDER_V3, "status": "declined", "attempt": 1, "decline": "insufficient_funds"}
ORDER_V6 = {**ORDER_V4, "status": "retry_scheduled", "retry_at": "2026-10-18T09:00Z"}
ORDER_V7 = {
    **{k: v for k, v in ORDER_V6.items() if k not in ("decline", "retry_at")},
    "status": "paid",
    "attempt": 2,
    "charge": "ch_88",
}
ORDER_V9 = {**ORDER_V7, "status": "settled", "settled_at": "2026-10-18T09:02Z"}

RENEWAL_GRAPH = {
    "nodes": [
        {"id": "scheduler", "label": "Renewal scheduler"},
        {"id": "pricing", "label": "Pricing"},
        {"id": "tax", "label": "Tax"},
        {"id": "charge", "label": "Charge worker"},
        {"id": "paid", "label": "Paid?", "shape": "decision"},
        {"id": "retry", "label": "Retry queue"},
        {"id": "settle", "label": "Settlement"},
    ],
    "edges": [
        {"from": "scheduler", "to": "pricing"},
        {"from": "pricing", "to": "tax", "label": "domestic quote", "id": "tax-domestic"},
        {"from": "pricing", "to": "tax", "label": "cross-border quote", "id": "tax-intl"},
        {"from": "tax", "to": "charge"},
        {"from": "charge", "to": "paid"},
        {"from": "paid", "to": "settle", "label": "Yes"},
        {"from": "paid", "to": "retry", "label": "No"},
        {"from": "retry", "to": "charge", "label": "retry up to 3x", "id": "retry", "loop": True},
    ],
    "traces": [
        {
            "id": "succeeds",
            "label": "Card succeeds",
            "steps": [
                {"node": "scheduler", "value": ORDER_V1},
                {"node": "pricing", "value": ORDER_V2},
                {"node": "tax", "value": ORDER_V3, "via": "tax-domestic"},
                {"node": "charge", "value": ORDER_V3},
                {"node": "paid", "value": ORDER_V3},
                {"node": "settle", "value": ORDER_V9},
            ],
        },
        {
            "id": "declined",
            "label": "Card declined, retried",
            "steps": [
                {"node": "scheduler", "value": ORDER_V1},
                {"node": "pricing", "value": ORDER_V2, "note": "Pricing applies the loyalty discount"},
                {"node": "tax", "value": ORDER_V3, "via": "tax-domestic", "note": "Tax adds 8.25% sales tax"},
                {"node": "charge", "value": ORDER_V4, "note": "The card is declined"},
                {"node": "paid", "value": ORDER_V4, "note": "Paid? answers No"},
                {"node": "retry", "value": ORDER_V6, "note": "The retry is booked for tomorrow"},
                {"node": "charge", "value": ORDER_V7, "note": "The second attempt succeeds"},
                {"node": "paid", "value": ORDER_V7, "note": "Paid? answers Yes"},
                {"node": "settle", "value": ORDER_V9, "note": "The order settles"},
            ],
        },
    ],
}


def renewal(traces: object = None, **edge_patch: object) -> str:
    """The renewal graph as markup, with ``traces`` swapped in (a missing key keeps the originals)."""
    payload = json.loads(json.dumps(RENEWAL_GRAPH))
    if traces is not None:
        payload["traces"] = traces
    payload.update(edge_patch)
    return flow_markup(payload)


def one_trace(*steps: dict, id: str = "t", label: str = "T") -> list[dict]:
    return [{"id": id, "label": label, "steps": list(steps)}]


def pair(second: dict) -> list[dict]:
    return one_trace({"node": "scheduler", "value": 1}, {"node": "pricing", "value": 2, **second})


def test_flow_renewal_graph_with_both_traces_passes_clean() -> None:
    assert messages(renewal()) == []
    assert warn_messages(renewal()) == []


def test_flow_trace_steps_may_run_along_loop_edges_and_self_loops() -> None:
    loop = one_trace(
        {"node": "retry", "value": 1}, {"node": "charge", "value": 2}, {"node": "paid", "value": 3}
    )
    assert messages(renewal(loop)) == []
    assert warn_messages(renewal(loop)) == []
    payload = {
        "nodes": [{"id": "poll", "label": "Poller"}],
        "edges": [{"from": "poll", "to": "poll"}],
        "traces": one_trace({"node": "poll", "value": 1}, {"node": "poll", "value": 2}),
    }
    assert messages(flow_markup(payload)) == []
    assert warn_messages(flow_markup(payload)) == []


def test_flow_trace_value_may_be_null() -> None:
    assert messages(renewal(one_trace({"node": "scheduler", "value": None}, {"node": "pricing", "value": None}))) == []


def test_flow_edge_id_must_be_a_non_empty_string() -> None:
    for bad in ("", "  ", 5, None, ["a"]):
        edges = [{"from": "a", "to": "b", "id": bad}]
        payload = {"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "edges": edges}
        assert messages(flow_markup(payload)) == ["<q-flow> edge id must be a non-empty string"], bad


def test_flow_duplicate_edge_id_is_reported_once_per_id() -> None:
    nodes = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    three = [{"from": "a", "to": "b", "id": "x"}] * 3 + [{"from": "b", "to": "a", "id": "y"}] * 2
    assert messages(flow_markup({"nodes": nodes, "edges": three})) == [
        '<q-flow> has duplicate edge id "x"',
        '<q-flow> has duplicate edge id "y"',
    ]


def test_flow_traces_must_be_a_list() -> None:
    assert messages(renewal({"id": "t"})) == ["<q-flow> traces must be a list"]
    assert messages(flow_markup({**RENEWAL_GRAPH, "traces": None})) == ["<q-flow> traces must be a list"]


def test_flow_each_trace_needs_an_id_and_a_label() -> None:
    steps = one_trace({"node": "scheduler", "value": 1}, {"node": "pricing", "value": 2})[0]["steps"]
    for bad in ("nope", 3, {"label": "L", "steps": steps}, {"id": "t", "steps": steps}, {"id": " ", "label": "L", "steps": steps}, {"id": "t", "label": 4, "steps": steps}):
        assert messages(renewal([bad])) == ["<q-flow> each trace needs an id and a label"], bad


def test_flow_bad_trace_id_still_checks_its_steps_under_a_question_mark() -> None:
    bad = [{"label": "L", "steps": [{"node": "nope", "value": 1}, {"node": "pricing", "value": 2}]}]
    assert messages(renewal(bad)) == [
        "<q-flow> each trace needs an id and a label",
        '<q-flow> trace "?" step 1 points at unknown node "nope"',
    ]


def test_flow_trace_with_a_question_mark_id_is_valid_and_kept() -> None:
    node_map = {"a": {"id": "a", "label": "A"}, "b": {"id": "b", "label": "B"}}
    edges = [{"from": "a", "to": "b", "ref": "a>b", "label": "", "loop": False}]
    failures: list[str] = []
    traces = kitcheck._validate_flow_traces(
        {"traces": one_trace({"node": "a", "value": 1}, {"node": "b", "value": 2}, id="?", label="Odd id")},
        1,
        node_map,
        edges,
        lambda _line, msg: failures.append(msg),
        lambda _line, _msg: None,
    )
    assert failures == []
    assert [t["id"] for t in traces] == ["?"]
    assert messages(renewal(one_trace({"node": "scheduler", "value": 1}, {"node": "pricing", "value": 2}, id="?"))) == []


def test_flow_trace_empty_note_is_valid() -> None:
    assert messages(renewal(pair({"note": ""}))) == []
    assert warn_messages(renewal(pair({"note": ""}))) == []


def test_flow_duplicate_trace_id_is_reported_once_per_id() -> None:
    steps = [{"node": "scheduler", "value": 1}, {"node": "pricing", "value": 2}]
    trace = {"id": "t", "label": "T", "steps": steps}
    other = {"id": "u", "label": "U", "steps": steps}
    assert messages(renewal([trace, trace, trace, other, other])) == [
        '<q-flow> has duplicate trace id "t"',
        '<q-flow> has duplicate trace id "u"',
    ]


def test_flow_trace_needs_at_least_two_steps() -> None:
    expected = ['<q-flow> trace "t" needs at least 2 steps']
    assert messages(renewal(one_trace({"node": "scheduler", "value": 1}))) == expected
    assert messages(renewal(one_trace())) == expected
    assert messages(renewal([{"id": "t", "label": "T", "steps": "nope"}])) == expected
    assert messages(renewal([{"id": "t", "label": "T"}])) == expected


def test_flow_trace_step_needs_a_node_and_a_value() -> None:
    expected = ['<q-flow> trace "t" step 2 needs a node and a value']
    for bad in ("pricing", 7, {"value": 2}, {"node": 4, "value": 2}, {"node": "pricing"}):
        assert messages(renewal(one_trace({"node": "scheduler", "value": 1}, bad))) == expected, bad


def test_flow_trace_step_must_point_at_a_known_node() -> None:
    got = messages(renewal(one_trace({"node": "scheduler", "value": 1}, {"node": "nope", "value": 2})))
    assert got == ['<q-flow> trace "t" step 2 points at unknown node "nope"']


def test_flow_trace_step_note_must_be_a_string() -> None:
    assert messages(renewal(pair({"note": 5}))) == ['<q-flow> trace "t" step 2 note must be a string']


def test_flow_trace_first_step_cannot_name_via() -> None:
    first = one_trace({"node": "scheduler", "value": 1, "via": "retry"}, {"node": "pricing", "value": 2})
    assert messages(renewal(first)) == ['<q-flow> trace "t" step 1 has no incoming edge; remove via']


def test_flow_trace_via_must_name_an_edge() -> None:
    for bad in ("missing", 5):
        assert messages(renewal(pair({"via": bad}))) == [f'<q-flow> trace "t" step 2 names unknown edge "{bad}"']


def test_flow_trace_via_must_run_between_the_two_steps() -> None:
    assert messages(renewal(pair({"via": "retry"}))) == [
        '<q-flow> trace "t" step 2: edge "retry" doesn\'t run from "scheduler" to "pricing"'
    ]


def test_flow_trace_step_without_an_edge_between_its_nodes_fails() -> None:
    got = messages(renewal(one_trace({"node": "scheduler", "value": 1}, {"node": "tax", "value": 2})))
    assert got == ['<q-flow> trace "t" step 2: no edge from "scheduler" to "tax"']


def test_flow_trace_step_with_several_edges_needs_via() -> None:
    got = messages(renewal(one_trace({"node": "pricing", "value": 1}, {"node": "tax", "value": 2})))
    assert got == ['<q-flow> trace "t" step 2: 2 edges run from "pricing" to "tax"; name one with via']
    named = one_trace({"node": "pricing", "value": 1}, {"node": "tax", "value": 2, "via": "tax-intl"})
    assert messages(renewal(named)) == []


def test_flow_trace_edge_checks_skip_steps_with_an_unknown_node() -> None:
    steps = one_trace(
        {"node": "nope", "value": 1}, {"node": "pricing", "value": 2, "via": "missing"}, {"node": "tax", "value": 3, "via": "tax-intl"}
    )
    assert messages(renewal(steps)) == ['<q-flow> trace "t" step 1 points at unknown node "nope"']


def test_flow_trace_value_must_be_json() -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        got = messages(renewal(pair({"value": {"a": [bad]}})))
        assert got == ['<q-flow> trace "t" step 2 has a value that isn\'t JSON'], bad


def test_flow_trace_value_with_a_lone_surrogate_is_not_json() -> None:
    expected = ['<q-flow> trace "t" step 2 has a value that isn\'t JSON']
    for bad in ("\ud800", {"k\udc00": 1}, {"a": [{"b": "x\ud800y"}]}):
        assert messages(renewal(pair({"value": bad}))) == expected, bad
    assert messages(renewal(pair({"value": "\U0001f600"}))) == []


GRAPH_UTF8_MESSAGE = "<q-flow> graph data holds text that can't be written as UTF-8"


def _renewal_with(patch) -> str:
    payload = json.loads(json.dumps(RENEWAL_GRAPH))
    patch(payload)
    return flow_markup(payload)


@pytest.mark.parametrize(
    "patch",
    [
        lambda p: p["nodes"][0].update(label="A \ud800"),
        lambda p: p.update(kinds={"k\udc00": 1}),
        lambda p: p["edges"][1].update(label="x\ud800"),
        lambda p: p["traces"][0]["steps"][1].update(note="n\ud800"),
        lambda p: (
            p["edges"][1].update(id="tax-\ud800"),
            p["traces"][0]["steps"][2].update(via="tax-\ud800"),
            p["traces"].pop(),
        ),
        lambda p: p["traces"][0].update(id="t\ud800"),
        lambda p: p["traces"][0].update(label="L\ud800"),
        lambda p: p.update(groups=[{"id": "g", "label": "G\ud800"}]),
        lambda p: p["nodes"][0].update({"k\ud800": "v"}),
    ],
    ids=["node-label", "node-kind", "edge-label", "trace-note", "trace-via", "trace-id", "trace-label", "group-label", "object-key"],
)
def test_flow_graph_text_with_a_lone_surrogate_fails_once(patch) -> None:
    assert messages(_renewal_with(patch)) == [GRAPH_UTF8_MESSAGE]


def test_flow_graph_text_fails_once_even_with_several_bad_strings() -> None:
    def patch(p: dict) -> None:
        p["nodes"][0]["label"] = "\ud800"
        p["nodes"][1]["label"] = "\udc00"
        p["traces"][0]["steps"][1]["note"] = "\ud800"

    assert messages(_renewal_with(patch)) == [GRAPH_UTF8_MESSAGE]


def test_flow_graph_text_with_a_valid_surrogate_pair_passes() -> None:
    def patch(p: dict) -> None:
        p["nodes"][0]["label"] = "Renew \U0001f600"
        p["traces"][0]["steps"][1]["note"] = "ok \U0001f600"

    assert messages(_renewal_with(patch)) == []


def test_flow_trace_value_surrogate_gets_only_the_value_message() -> None:
    assert messages(renewal(pair({"value": "\ud800"}))) == ['<q-flow> trace "t" step 2 has a value that isn\'t JSON']


def test_flow_trace_value_over_400_lines_fails() -> None:
    got = messages(renewal(pair({"value": list(range(399))})))
    assert got == ['<q-flow> trace "t" step 2 value is 401 lines; at most 400']
    assert messages(renewal(pair({"value": list(range(398))}))) == []


def test_flow_trace_value_over_40_lines_warns() -> None:
    warned = renewal(pair({"value": list(range(39))}))
    assert messages(warned) == []
    assert warn_messages(warned) == [
        '<q-flow> trace "t" step 2 value is 41 lines: values over 40 lines are hard to scan; keep the fields the reader needs'
    ]
    assert warn_messages(renewal(pair({"value": list(range(38))}))) == []


def test_flow_trace_note_over_120_characters_warns() -> None:
    long_note = renewal(pair({"note": "n" * 121}))
    assert messages(long_note) == []
    assert warn_messages(long_note) == [
        '<q-flow> trace "t" step 2 note is 121 characters: notes over 120 characters crowd the panel'
    ]
    assert warn_messages(renewal(pair({"note": "n" * 120}))) == []


def test_flow_trace_over_30_steps_warns() -> None:
    def loop_trace(count: int) -> str:
        payload = {
            "nodes": [{"id": "poll", "label": "Poller"}],
            "edges": [{"from": "poll", "to": "poll"}],
            "traces": one_trace(*[{"node": "poll", "value": i} for i in range(count)]),
        }
        return flow_markup(payload)

    assert messages(loop_trace(31)) == []
    assert warn_messages(loop_trace(31)) == [
        '<q-flow> trace "t" has 31 steps: traces over 30 steps are hard to follow; split it'
    ]
    assert warn_messages(loop_trace(30)) == []


def test_flow_trace_failures_keep_id_label_duplicate_steps_order() -> None:
    steps = [{"node": "nope", "value": 1}, {"node": "pricing", "value": 2}]
    traces = [{"id": "t", "label": "T", "steps": steps}, {"id": "t", "label": "T", "steps": [{"node": "pricing", "value": 1}]}]
    assert messages(renewal(traces)) == [
        '<q-flow> trace "t" step 1 points at unknown node "nope"',
        '<q-flow> has duplicate trace id "t"',
        '<q-flow> trace "t" needs at least 2 steps',
    ]

# -- q-schema: rule schema-data and warnings (SC-3, SC-4, SC-29, SC-30) -----------------------------


def schema_markup(payload: dict, attrs: str = 'summary="A model."') -> str:
    return f'<q-schema {attrs}><script type="application/json">{json.dumps(payload)}</script></q-schema>'


def _er_fields(*names: str) -> list[dict]:
    return [{"name": n, "type": "text"} for n in names]


def billing_model() -> dict:
    charge_fields = [
        {"name": "id", "type": "int", "key": "PK"},
        *_er_fields(
            "status", "total_price", "currency", "scheduled_at", "processed_at", "error_type",
            "error", "retry_count", "tags", "note", "created_at", "updated_at",
        ),
        {"name": "customer_id", "type": "int", "key": "FK"},
        {"name": "subscription_id", "type": "int", "key": "FK", "nullable": True},
    ]
    return {
        "kinds": {"core": 1, "billing": 2},
        "groups": [{"id": "billing", "label": "Billing"}],
        "entities": [
            {
                "id": "customer", "label": "Customer", "kind": "core",
                "fields": [
                    {"name": "id", "type": "int", "key": "PK"},
                    {"name": "email", "type": "text", "key": "UK"},
                    *_er_fields("first_name", "last_name", "created_at"),
                ],
            },
            {
                "id": "subscription", "label": "Subscription", "kind": "billing", "group": "billing",
                "detail": "<p>A recurring order.</p>",
                "fields": [
                    {"name": "id", "type": "int", "key": "PK"},
                    {"name": "customer_id", "type": "int", "key": "FK"},
                    *_er_fields("product_title", "status", "next_charge_date", "interval"),
                ],
            },
            {"id": "charge", "label": "Charge", "kind": "billing", "group": "billing", "fields": charge_fields},
            {
                "id": "line_item", "label": "Line item", "kind": "billing", "group": "billing",
                "fields": [
                    {"name": "id", "type": "int", "key": "PK"},
                    {"name": "charge_id", "type": "int", "key": "FK"},
                    *_er_fields("title", "quantity", "price"),
                ],
            },
        ],
        "relationships": [
            {"from": "subscription.customer_id", "to": "customer.id", "from_card": "zero-or-many", "to_card": "one", "label": "has"},
            {"from": "charge.customer_id", "to": "customer.id", "from_card": "zero-or-many", "to_card": "one", "label": "is billed"},
            {"from": "charge.subscription_id", "to": "subscription.id", "from_card": "zero-or-many", "to_card": "zero-or-one", "label": "generates"},
            {"from": "line_item.charge_id", "to": "charge.id", "from_card": "one-or-many", "to_card": "one", "label": "contains"},
        ],
    }


def _cls(cid: str, label: str, **rest) -> dict:
    return {"id": cid, "label": label, **rest}


def parser_model() -> dict:
    private = lambda name, type_: {"name": name, "type": type_, "visibility": "private"}  # noqa: E731
    return {
        "kinds": {"api": 1, "internals": 3},
        "entities": [
            _cls("parser", "Parser", kind="api", stereotype="interface",
                 methods=[{"signature": "parse(src: str) -> Ast", "visibility": "public"}]),
            _cls("recursivedescentparser", "RecursiveDescentParser", kind="internals",
                 fields=[
                     {"name": "max_depth", "type": "int", "visibility": "public", "static": True},
                     private("lexer", "Lexer"), private("pos", "int"), private("depth", "int"),
                     private("errors", "list"), private("options", "dict"),
                 ],
                 methods=[
                     {"signature": "parse(src: str) -> Ast", "visibility": "public"},
                     {"signature": "expr() -> Ast", "visibility": "private"},
                     {"signature": "term() -> Ast", "visibility": "private"},
                     {"signature": "factor() -> Ast", "visibility": "private"},
                     {"signature": "expect(kind: TokenKind) -> Token", "visibility": "private"},
                     {"signature": "peek() -> Token", "visibility": "private"},
                     {"signature": "error(msg: str)", "visibility": "private"},
                 ]),
            _cls("lexer", "Lexer", kind="internals",
                 fields=[private("src", "str"), private("pos", "int")],
                 methods=[{"signature": "next() -> Token", "visibility": "public"},
                          {"signature": "peek() -> Token", "visibility": "public"}]),
            _cls("token", "Token", kind="internals",
                 fields=[{"name": "kind", "type": "TokenKind", "visibility": "public"},
                         {"name": "text", "type": "str", "visibility": "public"},
                         {"name": "line", "type": "int", "visibility": "public"}]),
            _cls("tokenkind", "TokenKind", kind="internals", stereotype="enum",
                 fields=[{"name": n} for n in ("NUMBER", "IDENT", "PLUS", "LPAREN", "RPAREN", "EOF")]),
            _cls("ast", "Ast", kind="api", stereotype="abstract",
                 methods=[{"signature": "accept(v: Visitor)", "visibility": "public", "abstract": True}]),
            _cls("binaryexpr", "BinaryExpr", kind="api",
                 fields=[{"name": "left", "type": "Ast", "visibility": "public"},
                         {"name": "op", "type": "TokenKind", "visibility": "public"},
                         {"name": "right", "type": "Ast", "visibility": "public"}]),
        ],
        "relationships": [
            {"from": "recursivedescentparser", "to": "parser", "type": "implements"},
            {"from": "recursivedescentparser", "to": "lexer", "type": "composition", "to_mult": "1"},
            {"from": "lexer", "to": "token", "type": "dependency", "label": "produces"},
            {"from": "token", "to": "tokenkind", "type": "association", "directed": True},
            {"from": "binaryexpr", "to": "ast", "type": "inherits"},
            {"from": "binaryexpr", "to": "ast", "type": "aggregation", "to_mult": "2", "label": "operands"},
            {"from": "parser", "to": "ast", "type": "dependency", "label": "returns"},
        ],
    }


CLASS_ATTRS = 'notation="class" summary="A diagram."'


def er_with(change) -> dict:
    model = billing_model()
    change(model)
    return model


def class_with(change) -> dict:
    model = parser_model()
    change(model)
    return model


def schema_failures(payload: dict, attrs: str = 'summary="A model."') -> list[str]:
    return messages(schema_markup(payload, attrs))


def schema_warnings(payload: dict, attrs: str = 'summary="A model."') -> list[str]:
    return warn_messages(schema_markup(payload, attrs))


def test_schema_billing_model_and_parser_diagram_pass_with_no_warnings() -> None:
    assert schema_failures(billing_model()) == []
    assert schema_warnings(billing_model()) == []
    assert schema_failures(parser_model(), CLASS_ATTRS) == []
    assert schema_warnings(parser_model(), CLASS_ATTRS) == []
    assert schema_failures(billing_model(), 'notation="er" summary="A model."') == []


def test_schema_missing_summary_and_unknown_notation_report_only_the_catalog_message() -> None:
    assert messages(
        f'<q-schema><script type="application/json">{json.dumps(billing_model())}</script></q-schema>'
    ) == ["<q-schema> needs attribute summary"]
    assert schema_failures(billing_model(), 'notation="uml" summary="s"') == [
        '<q-schema> notation="uml" is not one of er, class'
    ]
    assert schema_failures(parser_model(), 'notation="uml" summary="s"') == [
        '<q-schema> notation="uml" is not one of er, class'
    ]
    assert messages('<q-schema summary="s" notation="uml"></q-schema>') == [
        '<q-schema> notation="uml" is not one of er, class',
        "<q-schema> needs one of: script",
    ]
    assert schema_warnings(billing_model(), 'notation="uml" summary="s"') == []


def test_schema_needs_a_json_script_child() -> None:
    assert messages('<q-schema summary="s"></q-schema>') == ["<q-schema> needs one of: script"]
    assert messages('<q-schema summary="s"><script>1</script></q-schema>') == [
        '<q-schema> needs a <script type="application/json"> child holding a JSON object'
    ]
    assert messages('<q-schema summary="s"><script type="application/json">[1]</script></q-schema>') == [
        '<q-schema> needs a <script type="application/json"> child holding a JSON object'
    ]
    assert messages('<q-schema summary="s"><script type="application/json">{oops</script></q-schema>') == [
        '<q-schema> needs a <script type="application/json"> child holding a JSON object'
    ]


def test_schema_duplicate_entity_id_and_duplicate_field() -> None:
    def two_charges(m):
        m["entities"].append({"id": "charge", "label": "Charge again", "fields": _er_fields("id")})

    assert schema_failures(er_with(two_charges)) == ['<q-schema> duplicate entity id "charge"']

    def repeated_status(m):
        m["entities"][2]["fields"].append({"name": "status", "type": "text"})

    assert schema_failures(er_with(repeated_status)) == ['<q-schema> duplicate field "status" in "charge"']

    def group_clash(m):
        m["entities"][0]["id"] = "billing"
        m["relationships"] = []

    assert schema_failures(er_with(group_clash)) == ['<q-schema> has duplicate id "billing"']


def test_schema_relationship_ends() -> None:
    def to_customers(m):
        m["relationships"][0]["to"] = "customers.id"

    assert schema_failures(er_with(to_customers)) == ['<q-schema> relationship names unknown entity "customers"']

    def to_uuid(m):
        m["relationships"][0]["to"] = "customer.uuid"

    assert schema_failures(er_with(to_uuid)) == ['<q-schema> relationship names unknown field "customer.uuid"']

    def no_field(m):
        m["relationships"][0]["to"] = "customer"

    assert schema_failures(er_with(no_field)) == ['<q-schema> relationship ends are written entity.field']

    def empty_parts(m):
        m["relationships"][0]["to"] = "customer."
        m["relationships"][1]["to"] = ".id"
        m["relationships"][2]["from"] = 7

    assert schema_failures(er_with(empty_parts)) == ["<q-schema> relationship ends are written entity.field"] * 3


def test_schema_relationship_end_splits_on_the_first_dot() -> None:
    def dotted_field(m):
        m["entities"][0]["fields"].append({"name": "meta.id", "type": "int"})
        m["relationships"][0]["to"] = "customer.meta.id"

    assert schema_failures(er_with(dotted_field)) == []

    def dotted_entity(m):
        m["entities"][0]["id"] = "cust.omer"
        m["relationships"] = []

    assert schema_failures(er_with(dotted_entity)) == ['<q-schema> entity ids may not contain \'.\': "cust.omer"']


def test_schema_unknown_cardinality_and_key() -> None:
    def many(m):
        m["relationships"][0]["from_card"] = "many"

    assert schema_failures(er_with(many)) == [
        '<q-schema> unknown cardinality "many"; use zero-or-one, one, zero-or-many or one-or-many'
    ]

    def no_card(m):
        del m["relationships"][0]["to_card"]

    assert schema_failures(er_with(no_card)) == ["<q-schema> relationship needs to_card"]

    def primary(m):
        m["entities"][0]["fields"][0]["key"] = "PRIMARY"

    assert schema_failures(er_with(primary)) == ['<q-schema> unknown key "PRIMARY"; use PK, FK or UK']

    def key_list(m):
        m["entities"][0]["fields"][0]["key"] = ["PK", "FK"]

    assert schema_failures(er_with(key_list)) == []

    def bad_in_list(m):
        m["entities"][0]["fields"][0]["key"] = ["PK", "XX"]

    assert schema_failures(er_with(bad_in_list)) == ['<q-schema> unknown key "XX"; use PK, FK or UK']


def test_schema_coordinates_are_rejected_wherever_they_appear() -> None:
    expected = ["<q-schema> positions are not allowed; the element lays the model out"]

    def on_entity(m):
        m["entities"][0].update({"x": 10, "y": 20})

    def on_root(m):
        m["position"] = {"x": 1}

    def on_field(m):
        m["entities"][0]["fields"][0]["y"] = 3

    def on_group(m):
        m["groups"][0]["x"] = 3

    def on_relationship(m):
        m["relationships"][0]["positions"] = []

    for change in (on_entity, on_root, on_field, on_group, on_relationship):
        assert schema_failures(er_with(change)) == expected, change.__name__

    def on_method(m):
        m["entities"][0]["methods"] = [{"signature": "f()", "x": 1}]

    assert schema_failures(class_with(on_method), CLASS_ATTRS) == expected


def test_schema_kinds_groups_and_detail() -> None:
    def nine(m):
        m["kinds"] = {f"k{i}": min(i, 8) for i in range(1, 10)}
        for e in m["entities"]:
            e.pop("kind", None)

    assert schema_failures(er_with(nine)) == ["<q-schema> at most eight kinds, one per chart color"]

    def audit(m):
        m["entities"][0]["kind"] = "audit"

    assert schema_failures(er_with(audit)) == ['<q-schema> undeclared kind "audit"']

    def ledger(m):
        m["entities"][0]["group"] = "ledger"

    assert schema_failures(er_with(ledger)) == ['<q-schema> unknown group "ledger"']

    def self_parent(m):
        m["groups"][0]["parent"] = "billing"

    assert schema_failures(er_with(self_parent)) == ["<q-schema> group nesting loops"]

    def child_parent(m):
        m["groups"] = [{"id": "a", "label": "A", "parent": "b"}, {"id": "b", "label": "B", "parent": "a"}]
        for e in m["entities"]:
            e.pop("group", None)

    assert schema_failures(er_with(child_parent)) == ["<q-schema> group nesting loops"]

    for bad in ("<script>alert(1)</script>", "<form><input></form>", '<img src="https://example.com/x.png">'):

        def detail(m, bad=bad):
            m["entities"][0]["detail"] = bad

        assert schema_failures(er_with(detail)) == [
            "<q-schema> detail may hold only paragraphs, lists, code and links"
        ], bad

    raw_script = '<q-schema summary="s"><script type="application/json">{"detail": <script>}</script></q-schema>'
    assert messages(raw_script) == ["<q-schema> detail may hold only paragraphs, lists, code and links"]


def test_schema_size_limits() -> None:
    def many(count: int) -> dict:
        return {"entities": [{"id": f"e{i}", "label": f"E{i}", "fields": _er_fields("id")} for i in range(count)]}

    assert schema_failures(many(85)) == ["<q-schema> more than 80 entities"]
    assert schema_failures(many(80)) == []
    assert schema_warnings(many(80)) == [
        "<q-schema> large models read poorly, split them into groups or several models"
    ]
    assert schema_warnings(many(30)) == []
    assert schema_warnings(many(34)) == [
        "<q-schema> large models read poorly, split them into groups or several models"
    ]


def test_schema_entity_must_have_fields_and_summary_is_the_catalogs() -> None:
    def none(m):
        del m["entities"][0]["fields"]
        m["relationships"] = []

    assert schema_failures(er_with(none)) == ['<q-schema> entity "customer" needs a non-empty fields list']

    def empty(m):
        m["entities"][0]["fields"] = []
        m["relationships"] = []

    assert schema_failures(er_with(empty)) == ['<q-schema> entity "customer" needs a non-empty fields list']
    assert schema_failures({"entities": []}) == ["<q-schema> needs a non-empty entities list"]


def test_schema_warnings_for_wide_entities_and_foreign_keys() -> None:
    def forty_five(m):
        m["entities"][2]["fields"] += _er_fields(*(f"extra_{i}" for i in range(30)))

    assert schema_failures(er_with(forty_five)) == []
    assert schema_warnings(er_with(forty_five)) == ['<q-schema> "charge" has more than 40 fields']

    def forty(m):
        m["entities"][2]["fields"] += _er_fields(*(f"extra_{i}" for i in range(25)))

    assert schema_warnings(er_with(forty)) == []

    def unused_fk(m):
        del m["relationships"][3]

    assert schema_failures(er_with(unused_fk)) == []
    assert schema_warnings(er_with(unused_fk)) == ['<q-schema> FK field "line_item.charge_id" has no relationship']

    def not_fk(m):
        m["relationships"].append(
            {"from": "charge.status", "to": "customer.id", "from_card": "zero-or-many", "to_card": "one"}
        )

    assert schema_failures(er_with(not_fk)) == []
    assert schema_warnings(er_with(not_fk)) == [
        '<q-schema> relationship starts at "charge.status", which isn\'t marked FK'
    ]


def test_schema_er_rejects_class_only_data() -> None:
    expected = ['<q-schema> methods, stereotypes and relationship types belong to class diagrams; add notation="class"']

    def methods(m):
        m["entities"][0]["methods"] = [{"signature": "f()"}]

    def stereotype(m):
        m["entities"][0]["stereotype"] = "enum"

    def rel_type(m):
        m["relationships"][0]["type"] = "inherits"

    for change in (methods, stereotype, rel_type):
        assert schema_failures(er_with(change)) == expected, change.__name__


def test_schema_class_duplicates_and_unknown_classes() -> None:
    def two_lexers(m):
        m["entities"].append(_cls("lexer", "Lexer again"))

    assert schema_failures(class_with(two_lexers), CLASS_ATTRS) == ['<q-schema> duplicate class id "lexer"']

    def repeated_attribute(m):
        m["entities"][2]["fields"].append({"name": "pos", "type": "int"})

    assert schema_failures(class_with(repeated_attribute), CLASS_ATTRS) == ['<q-schema> duplicate member in "lexer"']

    def repeated_method(m):
        m["entities"][2]["methods"].append({"signature": "peek() -> Token"})

    assert schema_failures(class_with(repeated_method), CLASS_ATTRS) == ['<q-schema> duplicate member in "lexer"']

    def same_name_attribute_and_method(m):
        m["entities"][2]["methods"].append({"signature": "pos"})

    assert schema_failures(class_with(same_name_attribute_and_method), CLASS_ATTRS) == []

    def tokenizer(m):
        m["relationships"][2]["to"] = "tokenizer"

    assert schema_failures(class_with(tokenizer), CLASS_ATTRS) == ['<q-schema> relationship names unknown class "tokenizer"']

    def member_end(m):
        m["relationships"][2]["from"] = "lexer.next"

    assert schema_failures(class_with(member_end), CLASS_ATTRS) == [
        "<q-schema> class relationships join classes, not members"
    ]

    def dotted_class_id(m):
        m["entities"].append(_cls("a.b", "AB"))
        m["relationships"][2]["to"] = "a.b"

    assert schema_failures(class_with(dotted_class_id), CLASS_ATTRS) == []


def test_schema_class_unknown_type_visibility_stereotype_and_multiplicity() -> None:
    def extends(m):
        m["relationships"][4]["type"] = "extends"

    assert schema_failures(class_with(extends), CLASS_ATTRS) == [
        '<q-schema> unknown relationship type "extends"; '
        "use inherits, implements, composition, aggregation, association or dependency"
    ]

    def no_type(m):
        del m["relationships"][4]["type"]

    assert len(schema_failures(class_with(no_type), CLASS_ATTRS)) == 1

    def internal(m):
        m["entities"][2]["fields"][0]["visibility"] = "internal"

    assert schema_failures(class_with(internal), CLASS_ATTRS) == [
        '<q-schema> unknown visibility "internal"; use public, private, protected or package'
    ]

    def method_internal(m):
        m["entities"][2]["methods"][0]["visibility"] = "internal"

    assert schema_failures(class_with(method_internal), CLASS_ATTRS) == [
        '<q-schema> unknown visibility "internal"; use public, private, protected or package'
    ]

    def mixin(m):
        m["entities"][2]["stereotype"] = "mixin"

    assert schema_failures(class_with(mixin), CLASS_ATTRS) == [
        '<q-schema> unknown stereotype "mixin"; use interface, abstract or enum'
    ]

    for bad in ("many", "", "1..", "..2", "2..1", "-1", "1..2..3", "1\n", "*..2", "١"):

        def multiplicity(m, bad=bad):
            m["relationships"][1]["to_mult"] = bad

        assert schema_failures(class_with(multiplicity), CLASS_ATTRS) == [
            f'<q-schema> unknown multiplicity "{bad}"; use 1, 0..1, *, 0..*, 1..* or n..m'
        ], repr(bad)

    for good in ("1", "0..1", "*", "0..*", "1..*", "2..5", "3..3", "10"):

        def fine(m, good=good):
            m["relationships"][1]["from_mult"] = good

        assert schema_failures(class_with(fine), CLASS_ATTRS) == [], good


def test_schema_class_inheritance_loops_cover_inherits_and_implements() -> None:
    def mutual(m):
        m["relationships"] += [
            {"from": "ast", "to": "binaryexpr", "type": "inherits"},
        ]

    assert schema_failures(class_with(mutual), CLASS_ATTRS) == ["<q-schema> inheritance loops"]

    def mixed(m):
        m["relationships"] += [{"from": "parser", "to": "recursivedescentparser", "type": "inherits"}]

    assert schema_failures(class_with(mixed), CLASS_ATTRS) == ["<q-schema> inheritance loops"]

    def self_loop(m):
        m["relationships"] += [{"from": "token", "to": "token", "type": "inherits"}]

    assert schema_failures(class_with(self_loop), CLASS_ATTRS) == ["<q-schema> inheritance loops"]

    def composition_cycle(m):
        m["relationships"] += [{"from": "ast", "to": "binaryexpr", "type": "composition"}]

    assert schema_failures(class_with(composition_cycle), CLASS_ATTRS) == []


def test_schema_class_directed_only_on_association() -> None:
    def on_dependency(m):
        m["relationships"][2]["directed"] = True

    assert schema_failures(class_with(on_dependency), CLASS_ATTRS) == [
        "<q-schema> directed is only valid on an association"
    ]

    def not_a_boolean(m):
        m["relationships"][3]["directed"] = "yes"

    assert schema_failures(class_with(not_a_boolean), CLASS_ATTRS) == ["<q-schema> directed must be true or false"]


def test_schema_class_rejects_keys_and_cardinality() -> None:
    expected = ["<q-schema> keys and cardinality belong to data models; this is a class diagram"]

    def key(m):
        m["entities"][2]["fields"][0]["key"] = "PK"

    def cardinality(m):
        m["relationships"][1]["from_card"] = "one"

    for change in (key, cardinality):
        assert schema_failures(class_with(change), CLASS_ATTRS) == expected, change.__name__


def test_schema_class_shares_the_coordinate_kind_group_detail_and_size_rules() -> None:
    def audit(m):
        m["entities"][0]["kind"] = "audit"

    assert schema_failures(class_with(audit), CLASS_ATTRS) == ['<q-schema> undeclared kind "audit"']

    def ledger(m):
        m["entities"][0]["group"] = "ledger"

    assert schema_failures(class_with(ledger), CLASS_ATTRS) == ['<q-schema> unknown group "ledger"']

    def detail(m):
        m["entities"][0]["detail"] = "<form></form>"

    assert schema_failures(class_with(detail), CLASS_ATTRS) == [
        "<q-schema> detail may hold only paragraphs, lists, code and links"
    ]

    big = {"entities": [{"id": f"c{i}", "label": f"C{i}"} for i in range(85)]}
    assert schema_failures(big, CLASS_ATTRS) == ["<q-schema> more than 80 classes"]
    assert schema_failures({"entities": [{"id": "c", "label": "C"}]}, CLASS_ATTRS) == []


def test_schema_class_warnings() -> None:
    thirty_four = {"entities": [{"id": f"c{i}", "label": f"C{i}"} for i in range(34)]}
    assert schema_warnings(thirty_four, CLASS_ATTRS) == [
        "<q-schema> large diagrams read poorly, split them into groups or several diagrams"
    ]

    def members(m):
        m["entities"][1]["fields"] += [{"name": f"extra_{i}"} for i in range(30)]

    assert schema_warnings(class_with(members), CLASS_ATTRS) == [
        '<q-schema> "recursivedescentparser" has more than 40 members'
    ]

    def implements_lexer(m):
        m["relationships"].append({"from": "token", "to": "lexer", "type": "implements"})

    assert schema_failures(class_with(implements_lexer), CLASS_ATTRS) == []
    assert schema_warnings(class_with(implements_lexer), CLASS_ATTRS) == [
        '<q-schema> "lexer" is implemented but isn\'t an interface'
    ]

    def inherits_parser(m):
        m["relationships"].append({"from": "token", "to": "parser", "type": "inherits"})

    assert schema_failures(class_with(inherits_parser), CLASS_ATTRS) == []
    assert schema_warnings(class_with(inherits_parser), CLASS_ATTRS) == [
        '<q-schema> "parser" is an interface; use implements'
    ]


def test_schema_fallback_is_skipped_for_data_that_fails_the_check() -> None:
    bad = er_with(lambda m: m["relationships"][0].update({"to": "nobody.id"}))
    markup = schema_markup(bad)
    assert kitcheck.inject_schema_fallbacks(markup) == markup
    assert kitcheck.inject_schema_fallbacks(schema_markup(billing_model(), 'notation="uml" summary="s"')).count("data-q-flow-list") == 0


def test_schema_fallback_skips_blocks_that_already_hold_a_list_or_have_no_summary() -> None:
    good = schema_markup(billing_model())
    once = kitcheck.inject_schema_fallbacks(good)
    assert "data-q-schema-list-rels" in once
    assert kitcheck.inject_schema_fallbacks(once) == once
    no_summary = schema_markup(billing_model(), "")
    assert kitcheck.inject_schema_fallbacks(no_summary) == no_summary
    assert kitcheck.inject_schema_fallbacks('<q-schema summary="s"/>') == '<q-schema summary="s"/>'
    assert kitcheck.inject_schema_fallbacks("<p>none</p>") == "<p>none</p>"


def test_schema_fallback_renders_groups_nested_past_the_recursion_limit() -> None:
    depth = 1100
    groups = [{"id": f"g{i}", "label": f"G{i}", **({"parent": f"g{i - 1}"} if i else {})} for i in range(depth)]
    payload = {
        "groups": groups,
        "entities": [{"id": "e", "label": "E", "group": f"g{depth - 1}", "fields": _er_fields("id")}],
    }
    markup = schema_markup(payload)
    assert schema_failures(payload) == []
    out = kitcheck.inject_schema_fallbacks(markup)
    assert out.count("data-q-flow-list-group=") == depth
    assert 'data-q-schema-list-entity="e"' in out
    assert out.index('data-q-flow-list-group="g0"') < out.index(f'data-q-flow-list-group="g{depth - 1}"')


def test_schema_fallback_keeps_group_children_in_order_and_entities_after_subgroups() -> None:
    payload = {
        "groups": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B", "parent": "a"},
            {"id": "c", "label": "C", "parent": "a"},
            {"id": "d", "label": "D"},
        ],
        "entities": [
            {"id": "e1", "label": "E1", "group": "a", "fields": _er_fields("id")},
            {"id": "e2", "label": "E2", "group": "b", "fields": _er_fields("id")},
            {"id": "e3", "label": "E3", "fields": _er_fields("id")},
        ],
    }
    out = kitcheck.inject_schema_fallbacks(schema_markup(payload))
    body = out.split("data-q-flow-list-body>", 1)[1].split("</div></details>", 1)[0]
    assert body == (
        "<ul>"
        '<li data-q-flow-list-group="a"><strong>A</strong><ul>'
        '<li data-q-flow-list-group="b"><strong>B</strong><ul>'
        '<li data-q-schema-list-entity="e2"><strong>E2</strong><ul><li>id: text</li></ul></li></ul></li>'
        '<li data-q-flow-list-group="c"><strong>C</strong></li>'
        '<li data-q-schema-list-entity="e1"><strong>E1</strong><ul><li>id: text</li></ul></li>'
        "</ul></li>"
        '<li data-q-flow-list-group="d"><strong>D</strong></li>'
        '<li data-q-schema-list-entity="e3"><strong>E3</strong><ul><li>id: text</li></ul></li>'
        "</ul>"
    )


def test_schema_fallback_survives_a_closing_tag_spelled_inside_the_data() -> None:
    def noted(m):
        m["entities"][0]["fields"][0]["note"] = "ends like </q-schema> but is only text"

    payload = er_with(noted)
    before, after = "<p>before</p>\n", "\n<p>after</p>"
    markup = before + schema_markup(payload) + after
    out = kitcheck.inject_schema_fallbacks(markup)
    assert out != markup
    assert out.count("data-q-flow-list-body") == 1
    tail = len("</q-schema>" + after)
    assert out[: len(markup) - tail] == markup[: len(markup) - tail]
    assert out[len(out) - tail :] == markup[len(markup) - tail :]
    assert out[len(markup) - tail : len(out) - tail].endswith("</details>")
    assert kitcheck.inject_schema_fallbacks(out) == out


def test_schema_fallback_ignores_a_closing_tag_spelled_inside_a_comment() -> None:
    markup = schema_markup(billing_model()).replace(
        "</script></q-schema>", "</script><!-- </q-schema> --></q-schema>"
    )
    out = kitcheck.inject_schema_fallbacks(markup)
    assert out.count("data-q-flow-list-body") == 1
    assert out.index("data-q-flow-list-body") > out.index("<!-- </q-schema> -->")
    assert out.endswith("</details></q-schema>")
    assert kitcheck.inject_schema_fallbacks(out) == out


def test_schema_fallback_ignores_opener_text_inside_scripts_and_comments() -> None:
    real = schema_markup(billing_model())
    decoys = (
        '<script>var s = "<q-schema summary=\'x\'>";</script>\n'
        "<!-- <q-schema summary='y'> -->\n"
    )
    out = kitcheck.inject_schema_fallbacks(decoys + real)
    assert out.startswith(decoys)
    assert out.count("data-q-flow-list-body") == 1
    assert out.index("data-q-flow-list-body") > out.index(real[:40])
    assert kitcheck.inject_schema_fallbacks(out) == out


def test_schema_fallback_ends_a_script_only_at_a_real_script_end_tag() -> None:
    real = schema_markup(billing_model())
    # </script-thing> and <q-schema-x> look like tag names to a \b match but are not script or q-schema tags
    decoys = (
        '<script>var s = "</script-thing> <q-schema summary=\'fake\'>";</script>\n'
        '<q-schema-x summary="other"></q-schema-x>\n'
        "<script-x></script-x>\n"
    )
    out = kitcheck.inject_schema_fallbacks(decoys + real)
    assert out.count("data-q-flow-list-body") == 1
    assert out.index("data-q-flow-list-body") > out.index(real[:40])
    assert kitcheck.inject_schema_fallbacks(out) == out


def test_schema_fallback_skips_an_entity_detail_nested_past_the_recursion_limit() -> None:
    def deep(m):
        m["entities"][0]["detail"] = "<ul><li>" * 1100 + "x" + "</li></ul>" * 1100

    payload = er_with(deep)
    markup = schema_markup(payload)
    assert schema_failures(payload) == ["<q-schema> detail may hold only paragraphs, lists, code and links"]
    assert kitcheck.inject_schema_fallbacks(markup) == markup


def test_schema_fallback_fills_two_consecutive_blocks() -> None:
    one = schema_markup(billing_model(), 'summary="One."')
    two = schema_markup(parser_model(), 'notation="class" summary="Two."')
    out = kitcheck.inject_schema_fallbacks(one + "\n" + two)
    assert out.count("data-q-flow-list-body") == 2
    first, second = out.split("</q-schema>")[:2]
    assert "Data model as a list" in first and "Class diagram as a list" not in first
    assert "Class diagram as a list" in second


def test_schema_fallback_skip_guard_ignores_the_marker_text_inside_the_data() -> None:
    def noted(m):
        m["entities"][0]["fields"][0]["note"] = "search for data-q-flow-list in the code"

    markup = schema_markup(er_with(noted))
    out = kitcheck.inject_schema_fallbacks(markup)
    assert out != markup
    assert "data-q-schema-list-rels" in out
    assert kitcheck.inject_schema_fallbacks(out) == out

    real = markup.replace("</q-schema>", "<details open data-q-flow-list><summary>x</summary></details></q-schema>")
    assert kitcheck.inject_schema_fallbacks(real) == real


def test_schema_relationship_label_that_is_present_must_not_be_blank() -> None:
    expected = ["<q-schema> relationship label must not be blank"]
    for blank in ("", "   ", "\n\t"):

        def er_label(m, blank=blank):
            m["relationships"][0]["label"] = blank

        def class_label(m, blank=blank):
            m["relationships"][0]["label"] = blank

        assert schema_failures(er_with(er_label)) == expected, repr(blank)
        assert schema_failures(class_with(class_label), CLASS_ATTRS) == expected, repr(blank)

    def absent(m):
        m["relationships"][0].pop("label", None)

    def padded(m):
        m["relationships"][0]["label"] = " owns "

    assert schema_failures(er_with(absent)) == []
    assert schema_failures(er_with(padded)) == []


def test_schema_present_optional_strings_must_be_non_blank() -> None:
    def field_note(m):
        m["entities"][0]["fields"][0]["note"] = "  "

    def attribute_note(m):
        m["entities"][2]["fields"][0]["note"] = " "

    def method_note(m):
        m["entities"][0]["methods"][0]["note"] = ""

    assert schema_failures(er_with(field_note)) == ['<q-schema> note of "customer.id" must be non-blank text']
    assert schema_failures(class_with(attribute_note), CLASS_ATTRS) == [
        '<q-schema> note of "lexer.src" must be non-blank text'
    ]
    assert schema_failures(class_with(method_note), CLASS_ATTRS) == [
        '<q-schema> note of "parser.parse(src: str) -> Ast" must be non-blank text'
    ]


def test_schema_class_fields_and_methods_default_only_when_absent() -> None:
    def no_keys(m):
        m["entities"].append({"id": "bare", "label": "Bare"})

    assert schema_failures(class_with(no_keys), CLASS_ATTRS) == []

    def null_fields(m):
        m["entities"][0]["fields"] = None

    def null_methods(m):
        m["entities"][0]["methods"] = None

    assert schema_failures(class_with(null_fields), CLASS_ATTRS) == ['<q-schema> "parser" fields must be a list']
    assert schema_failures(class_with(null_methods), CLASS_ATTRS) == ['<q-schema> "parser" methods must be a list']

    for bad in ("x", 3, {}):

        def odd_fields(m, bad=bad):
            m["entities"][0]["fields"] = bad

        def odd_methods(m, bad=bad):
            m["entities"][0]["methods"] = bad

        assert schema_failures(class_with(odd_fields), CLASS_ATTRS) == ['<q-schema> "parser" fields must be a list']
        assert schema_failures(class_with(odd_methods), CLASS_ATTRS) == ['<q-schema> "parser" methods must be a list']


def test_needs_flow_matches_both_tags() -> None:
    assert kitcheck.needs_flow('<q-schema summary="s"></q-schema>')
    assert kitcheck.needs_flow("<q-flow>")
    assert not kitcheck.needs_flow("<q-chart>")
    assert not kitcheck.needs_flow("&lt;q-schema")


def test_a_built_page_with_q_schema_and_no_flow_block_names_the_tag() -> None:
    html = page(schema_markup(billing_model()), libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    line = html[: html.index("<q-schema")].count("\n") + 1
    result = run(html, REAL_STORE)
    assert [f["detail"] for f in result["failures"] if f["check"] == "kit"] == [
        f"page line {line}: q-schema elements are used but flow is not inlined"
    ]
    flow_page = page(flow_markup({"nodes": [{"id": "a", "label": "A"}]}), libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    flow_line = flow_page[: flow_page.index("<q-flow")].count("\n") + 1
    result = run(flow_page, REAL_STORE)
    assert [f["detail"] for f in result["failures"] if f["check"] == "kit"] == [
        f"page line {flow_line}: q-flow elements are used but flow is not inlined"
    ]


def test_a_built_page_with_q_schema_and_the_flow_block_passes() -> None:
    flow_lv = REAL_STORE.resolve("flow", None)
    flow_blocks = REAL_STORE.license_comment(flow_lv) + "\n" + "\n".join(b.text for b in REAL_STORE.inline_blocks(flow_lv)) + "\n"
    html = page(
        schema_markup(billing_model()), libraries={"kit": "1.0.0", "flow": flow_lv.version}, blocks=flow_blocks + kit_blocks()
    )
    result = run(html, REAL_STORE)
    assert [f for f in result["failures"] if f["check"] == "kit"] == []



# -- q-sequence: rule sequence-data and warnings ---------------------------------------------------


def seq_markup(payload: object, attrs: str = 'summary="Checkout charges the card."') -> str:
    return f'<q-sequence {attrs}><script type="application/json">{json.dumps(payload)}</script></q-sequence>'


def seq_messages(payload: object) -> list[str]:
    return messages(seq_markup(payload))


def seq_warnings(payload: object) -> list[str]:
    return warn_messages(seq_markup(payload))


def checkout(patch=None) -> dict:
    """The logic spec's checkout sequence, with ids on every message the traces name."""
    payload = {
        "kinds": {"person": 1, "ui": 2, "service": 3, "external": 4, "store": 5},
        "participants": [
            {"id": "shopper", "label": "Shopper", "kind": "person"},
            {"id": "checkout", "label": "Checkout", "kind": "ui"},
            {"id": "billing", "label": "Billing", "kind": "service"},
            {"id": "stripe", "label": "Stripe", "kind": "external", "detail": "<p>Card processor.</p>"},
            {"id": "ledger", "label": "Ledger", "kind": "store"},
        ],
        "steps": [
            {"id": "place-order", "from": "shopper", "to": "checkout", "label": "place order", "type": "call"},
            {"id": "charge-order", "from": "checkout", "to": "billing", "label": "charge order", "type": "call"},
            {
                "fragment": "loop",
                "label": "up to 3 attempts",
                "steps": [
                    {"id": "create-charge", "from": "billing", "to": "stripe", "label": "create charge", "type": "call"},
                    {
                        "fragment": "alt",
                        "branches": [
                            {
                                "label": "card valid",
                                "steps": [
                                    {"id": "charge-ok", "from": "stripe", "to": "billing", "label": "charge succeeded", "type": "reply"}
                                ],
                            },
                            {
                                "label": "card declined",
                                "steps": [
                                    {"id": "charge-declined", "from": "stripe", "to": "billing", "label": "card declined", "type": "reply"},
                                    {"note": "waits 2 seconds before retrying", "over": ["billing"]},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "fragment": "opt",
                "label": "charge succeeded",
                "steps": [{"id": "record", "from": "billing", "to": "ledger", "label": "record payment", "type": "async"}],
            },
            {"id": "paid", "from": "billing", "to": "checkout", "label": "order paid", "type": "reply"},
            {"id": "show-receipt", "from": "checkout", "to": "shopper", "label": "show receipt", "type": "reply"},
        ],
        "traces": [
            {
                "id": "succeeds",
                "label": "Card succeeds",
                "steps": [
                    {"message": "place-order", "value": {"order": "C-2207", "items": 2, "total": 48.0}},
                    {"message": "charge-order", "value": {"order": "C-2207", "amount": 48.0}, "note": "Checkout asks Billing."},
                    {"message": "create-charge", "value": {"attempt": 1}},
                    {"message": "charge-ok", "value": {"charge": "ch_91", "status": "succeeded"}},
                    {"message": "record", "value": {"charge": "ch_91"}},
                    {"message": "paid", "value": {"status": "paid"}},
                ],
            },
            {
                "id": "declined",
                "label": "Declined, then retried",
                "steps": [
                    {"message": "place-order", "value": 1},
                    {"message": "charge-order", "value": 2},
                    {"message": "create-charge", "value": 3},
                    {"message": "charge-declined", "value": 4},
                    {"message": "create-charge", "value": 5},
                    {"message": "charge-ok", "value": 6},
                    {"message": "record", "value": 7},
                    {"message": "paid", "value": 8},
                ],
            },
        ],
    }
    if patch is not None:
        patch(payload)
    return payload


def small(*steps: dict, extra: dict | None = None) -> dict:
    """Three participants a, b, c and the given steps."""
    return {
        "participants": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
        "steps": list(steps),
        **(extra or {}),
    }


def msg(frm: str, to: str, label: str = "m", kind: str = "call", **more: object) -> dict:
    return {"from": frm, "to": to, "label": label, "type": kind, **more}


def parsed_sequence(payload: dict) -> dict | None:
    builder = kitcheck._TreeBuilder()
    builder.feed(seq_markup(payload))
    builder.close()
    builder.finish()
    node = next(n for n in builder.nodes if n.tag == "q-sequence")
    return kitcheck._validate_sequence_node(node, lambda _l, _m: None, lambda _l, _m: None)


def test_sequence_tag_and_rule_are_registered() -> None:
    assert kitcheck.SEQUENCE_TAG.search("<q-sequence summary='x'>")
    assert not kitcheck.SEQUENCE_TAG.search("<q-sequences>")
    assert "sequence-data" in kitcheck.KNOWN_RULES
    assert "sequence-data" in CATALOG.elements["q-sequence"].rules


def test_sequence_checkout_with_both_traces_passes_with_no_warnings() -> None:
    assert seq_messages(checkout()) == []
    assert seq_warnings(checkout()) == []


def test_sequence_cleaned_data_numbers_messages_in_drawn_order() -> None:
    cleaned = parsed_sequence(checkout())
    assert cleaned is not None
    assert [m["number"] for m in cleaned["messages"]] == list(range(1, 9))
    assert [m["id"] for m in cleaned["messages"]] == [
        "place-order", "charge-order", "create-charge", "charge-ok", "charge-declined", "record", "paid", "show-receipt",
    ]
    assert cleaned["messages"][3] == {
        "number": 4, "id": "charge-ok", "from": "stripe", "to": "billing",
        "label": "charge succeeded", "type": "reply", "detail": None, "create": False,
    }
    assert [p["id"] for p in cleaned["participants"]] == ["shopper", "checkout", "billing", "stripe", "ledger"]
    assert cleaned["participants"][3]["detail"] == "<p>Card processor.</p>"
    assert cleaned["part_map"]["stripe"] is cleaned["participants"][3]
    loop = cleaned["steps"][2]
    assert loop["fragment"] == "loop" and loop["label"] == "up to 3 attempts"
    assert loop["steps"][0] == {"message": 3}
    alt = loop["steps"][1]
    assert [b["label"] for b in alt["branches"]] == ["card valid", "card declined"]
    assert alt["branches"][1]["steps"] == [{"message": 5}, {"note": "waits 2 seconds before retrying", "over": ["billing"]}]
    assert [t["id"] for t in cleaned["traces"]] == ["succeeds", "declined"]
    assert [s["message"] for s in cleaned["traces"][1]["steps"]] == [1, 2, 3, 5, 3, 4, 6, 7]
    assert cleaned["traces"][0]["steps"][1] == {"message": 2, "value": {"order": "C-2207", "amount": 48.0}, "note": "Checkout asks Billing."}
    assert cleaned["traces"][0]["steps"][0]["note"] is None


def test_sequence_failure_returns_none() -> None:
    assert parsed_sequence(small(msg("a", "nope"))) is None


def test_sequence_missing_summary_uses_the_catalog_message() -> None:
    payload = small(msg("a", "b"))
    assert messages(seq_markup(payload, attrs="")) == ["<q-sequence> needs attribute summary"]


def test_sequence_without_a_json_child_or_with_bad_json_fails() -> None:
    assert messages('<q-sequence summary="s"></q-sequence>') == ["<q-sequence> needs one of: script"]
    needs_json = '<q-sequence> needs a <script type="application/json"> child holding a JSON object'
    for body in ("{", "[]", '"text"', "7"):
        page = f'<q-sequence summary="s"><script type="application/json">{body}</script></q-sequence>'
        assert messages(page) == [needs_json], body
    other = '<q-sequence summary="s"><script type="text/plain">{}</script></q-sequence>'
    assert messages(other) == [needs_json]


def test_sequence_unparseable_json_naming_forbidden_markup_reports_the_detail_rule() -> None:
    page = '<q-sequence summary="s"><script type="application/json">{"detail": "<script>x</script>" oops</script></q-sequence>'
    assert messages(page) == ["<q-sequence> detail may hold only paragraphs, lists, code and links"]


def test_sequence_kinds_checks() -> None:
    def set_kinds(value):
        return lambda p: p.update(kinds=value)

    assert seq_messages(checkout(set_kinds([]))) == ["<q-sequence> kinds must be a JSON object"] + [
        f'<q-sequence> participant "{pid}" has undeclared kind "{kind}"'
        for pid, kind in (("shopper", "person"), ("checkout", "ui"), ("billing", "service"), ("stripe", "external"), ("ledger", "store"))
    ]
    nine = {f"k{i}": min(i, 8) for i in range(1, 10)}
    got = seq_messages(small(msg("a", "b"), extra={"kinds": nine}))
    assert got == ["<q-sequence> declares 9 kinds; at most eight kinds, one per chart color"]
    for color in (0, 9, "1", 1.5, True, None):
        got = seq_messages(small(msg("a", "b"), extra={"kinds": {"k": color}}))
        assert got == ['<q-sequence> kind "k" color must be an integer from 1 to 8'], color


def test_sequence_needs_a_non_empty_participant_list() -> None:
    for value in (None, [], "a", {"id": "a"}):
        payload = {"steps": [msg("a", "b")]}
        if value is not None:
            payload["participants"] = value
        got = seq_messages(payload)
        assert got[0] == "<q-sequence> needs at least one participant", value


def test_sequence_participant_needs_id_and_label() -> None:
    bad = [{"id": "a"}, {"label": "A"}, {"id": " ", "label": "A"}, {"id": "a", "label": ""}, 5, None, {"id": 3, "label": "A"}]
    for entry in bad:
        payload = small(msg("b", "c"))
        payload["participants"].append(entry)
        assert seq_messages(payload) == ["<q-sequence> each participant needs an id and a label"], entry


def test_sequence_more_than_16_participants_fails_and_9_warns() -> None:
    def with_participants(count: int) -> dict:
        return {
            "participants": [{"id": f"p{i}", "label": f"P{i}"} for i in range(count)],
            "steps": [msg("p0", "p1", kind="async")],
        }

    assert seq_messages(with_participants(17)) == ["<q-sequence> has 17 participants; at most 16"]
    assert seq_warnings(with_participants(17)) == []
    assert seq_messages(with_participants(16)) == []
    assert seq_warnings(with_participants(16)) == [
        "<q-sequence> has 16 participants: sequences over 8 participants are hard to follow; split it"
    ]
    assert seq_messages(with_participants(9)) == []
    assert seq_warnings(with_participants(9)) == [
        "<q-sequence> has 9 participants: sequences over 8 participants are hard to follow; split it"
    ]
    assert not any("participants" in w for w in seq_warnings(with_participants(8)))


def test_sequence_participant_kind_must_be_declared() -> None:
    def patch(p: dict) -> None:
        p["participants"][0]["kind"] = "cache"

    assert seq_messages(checkout(patch)) == ['<q-sequence> participant "shopper" has undeclared kind "cache"']

    def non_string(p: dict) -> None:
        p["participants"][0]["kind"] = 4

    assert seq_messages(checkout(non_string)) == ['<q-sequence> participant "shopper" has undeclared kind "4"']


@pytest.mark.parametrize(
    "bad_detail",
    ["<script>alert(1)</script>", "<form><input></form>", '<img src="https://x/y.png">', '<p onclick="e()">hi</p>', '<a href="javascript:alert(1)">bad</a>', 7],
)
def test_sequence_detail_whitelist_applies_to_participants_and_messages(bad_detail) -> None:
    detail_rule = ["<q-sequence> detail may hold only paragraphs, lists, code and links"]

    def on_participant(p: dict) -> None:
        p["participants"][4]["detail"] = bad_detail

    def on_message(p: dict) -> None:
        p["steps"][0]["detail"] = bad_detail

    assert seq_messages(checkout(on_participant)) == detail_rule
    assert seq_messages(checkout(on_message)) == detail_rule


def test_sequence_a_detail_nested_too_deeply_fails_with_the_detail_rule() -> None:
    detail_rule = ["<q-sequence> detail may hold only paragraphs, lists, code and links"]
    deep = "<ul><li>" * 1200 + "x" + "</li></ul>" * 1200

    def on_participant(p: dict) -> None:
        p["participants"][4]["detail"] = deep

    def on_message(p: dict) -> None:
        p["steps"][0]["detail"] = deep

    for patch in (on_participant, on_message):
        page = seq_markup(checkout(patch))
        assert messages(page) == detail_rule
        assert kitcheck.inject_sequence_fallbacks(page) == page


def test_sequence_message_detail_is_sanitized_into_the_cleaned_message() -> None:
    cleaned = parsed_sequence(small(msg("a", "b", detail="<p>Hello <b>there</b></p>")))
    assert cleaned is not None
    assert cleaned["messages"][0]["detail"] == "<p>Hello <b>there</b></p>"


def test_sequence_duplicate_ids_are_reported_once_each() -> None:
    dup_participants = {"participants": [{"id": "billing", "label": "A"}, {"id": "billing", "label": "B"}], "steps": [msg("billing", "billing", kind="async")]}
    assert seq_messages(dup_participants) == ['<q-sequence> has duplicate id "billing"']

    def message_clash(p: dict) -> None:
        p["traces"] = []
        p["steps"][0]["id"] = "billing"

    assert seq_messages(checkout(message_clash)) == ['<q-sequence> has duplicate id "billing"']

    def message_twice(p: dict) -> None:
        p["traces"] = []
        p["steps"][0]["id"] = "paid"

    assert seq_messages(checkout(message_twice)) == ['<q-sequence> has duplicate id "paid"']

    def thrice(p: dict) -> None:
        p["traces"] = []
        for step in p["steps"][:2]:
            step["id"] = "billing"

    assert seq_messages(checkout(thrice)) == ['<q-sequence> has duplicate id "billing"']


def test_sequence_trace_ids_are_their_own_namespace() -> None:
    def patch(p: dict) -> None:
        p["traces"][0]["id"] = "billing"

    assert seq_messages(checkout(patch)) == []


def test_sequence_needs_at_least_one_message() -> None:
    expected = ["<q-sequence> needs at least one message"]
    for steps in (None, [], "x", {}, [{"note": "n", "over": ["a"]}], [{"end": "a"}], [{"fragment": "opt", "steps": [{"end": "a"}]}]):
        payload = small()
        del payload["steps"]
        if steps is not None:
            payload["steps"] = steps
        assert seq_messages(payload) == expected, steps


def test_sequence_malformed_steps() -> None:
    malformed = "<q-sequence> step must be one message, note, end or fragment"
    cases = [
        {},
        5,
        None,
        "text",
        [1],
        {"label": "only a label"},
        {"note": "n", "over": ["a"], "end": "a"},
        {"end": "a", "from": "a", "to": "b", "label": "m", "type": "call"},
        {"fragment": "opt", "note": "n", "over": ["a"], "steps": [msg("a", "b")]},
    ]
    for case in cases:
        payload = small(msg("a", "b", kind="async"), case)
        assert seq_messages(payload) == [malformed], case


def test_sequence_message_needs_from_to_and_label() -> None:
    needs = "<q-sequence> message 1 needs from, to and a label"
    for bad in (
        {"from": "a", "label": "m", "type": "call"},
        {"from": "a", "to": "b", "type": "call"},
        {"from": "a", "to": "b", "label": " ", "type": "call"},
        {"from": "", "to": "b", "label": "m", "type": "call"},
        {"from": 3, "to": "b", "label": "m", "type": "call"},
        {"from": "a", "to": ["b"], "label": "m", "type": "call"},
    ):
        assert seq_messages(small(bad)) == [needs], bad


def test_sequence_message_must_name_known_participants() -> None:
    assert seq_messages(small(msg("a", "b"), msg("b", "strip"))) == [
        '<q-sequence> message 2 names unknown participant "strip"'
    ]
    assert seq_messages(small(msg("x", "y"))) == [
        '<q-sequence> message 1 names unknown participant "x"',
        '<q-sequence> message 1 names unknown participant "y"',
    ]
    assert seq_messages(small(msg("x", "x"))) == ['<q-sequence> message 1 names unknown participant "x"']
    assert seq_messages(small({"id": "m1", "from": "m1", "to": "a", "label": "x", "type": "call"})) == [
        '<q-sequence> message 1 names unknown participant "m1"'
    ]


def test_sequence_message_type_must_be_call_reply_or_async() -> None:
    steps = [msg("a", "b", f"m{i}", "async") for i in range(6)] + [msg("a", "b", "bad", "return")]
    assert seq_messages(small(*steps)) == ['<q-sequence> message 7 has unknown type "return"; use call, reply or async']
    missing = {"from": "a", "to": "b", "label": "m"}
    assert seq_messages(small(missing)) == ['<q-sequence> message 1 has unknown type ""; use call, reply or async']
    assert seq_messages(small(msg("a", "b", kind=3))) == ['<q-sequence> message 1 has unknown type "3"; use call, reply or async']


def test_sequence_create_must_be_true_and_cannot_be_a_self_message() -> None:
    for value in (False, 1, "yes", None):
        got = seq_messages(small(msg("a", "b", create=value)))
        assert got == ["<q-sequence> message 1 create must be true"], value
    assert seq_messages(small(msg("a", "b", create=True))) == []
    assert seq_messages(small(msg("a", "a", kind="async", create=True))) == [
        "<q-sequence> message 1 can't create its own sender"
    ]


def worker_sequence(*steps: dict) -> dict:
    return {
        "participants": [{"id": "billing", "label": "Billing"}, {"id": "worker", "label": "Receipt worker"}],
        "steps": list(steps),
    }


def start(**more: object) -> dict:
    return msg("billing", "worker", "start session", "call", create=True, **more)


def test_sequence_create_and_end_checkout_passes() -> None:
    payload = worker_sequence(
        start(),
        msg("worker", "billing", "session ready", "reply"),
        msg("billing", "worker", "send receipt", "async"),
        {"end": "worker"},
    )
    assert seq_messages(payload) == []
    assert seq_warnings(payload) == []


def test_sequence_touch_before_creation_fails_for_messages_notes_and_ends() -> None:
    before = worker_sequence(msg("worker", "billing", "early", "async"), start(), {"end": "worker"})
    assert seq_messages(before) == ['<q-sequence> message 1 touches "Receipt worker" before it is created']
    note = worker_sequence({"note": "hi", "over": ["worker"]}, start(), {"end": "worker"})
    assert seq_messages(note) == ['<q-sequence> note touches "Receipt worker" before it is created']
    early_end = worker_sequence({"end": "worker"}, start())
    assert seq_messages(early_end)[0] == '<q-sequence> end touches "Receipt worker" before it is created'
    numbered = worker_sequence(
        msg("billing", "billing", "tick", "async"),
        msg("billing", "worker", "too soon", "async"),
        start(),
        {"end": "worker"},
    )
    assert seq_messages(numbered) == ['<q-sequence> message 2 touches "Receipt worker" before it is created']


def test_sequence_touch_after_end_fails_for_messages_notes_and_ends() -> None:
    steps = [start(), {"end": "worker"}]
    for i, (extra, expected) in enumerate(
        (
            (msg("billing", "worker", "late", "async"), '<q-sequence> message 2 touches "Receipt worker" after it ends'),
            (msg("worker", "billing", "late", "async"), '<q-sequence> message 2 touches "Receipt worker" after it ends'),
            ({"note": "late", "over": ["billing", "worker"]}, '<q-sequence> note touches "Receipt worker" after it ends'),
        )
    ):
        assert seq_messages(worker_sequence(*steps, extra)) == [expected], i
    spec_example = worker_sequence(
        start(),
        msg("worker", "billing", "session ready", "reply"),
        msg("billing", "worker", "send receipt", "async"),
        {"end": "worker"},
        msg("billing", "worker", "again", "async"),
    )
    assert seq_messages(spec_example) == ['<q-sequence> message 4 touches "Receipt worker" after it ends']


def test_sequence_participant_created_twice_or_ended_twice_fails() -> None:
    twice = worker_sequence(start(), start())
    assert seq_messages(twice) == ['<q-sequence> "Receipt worker" is created twice']
    ends = worker_sequence(start(), {"end": "worker"}, {"end": "worker"})
    assert seq_messages(ends) == ['<q-sequence> "Receipt worker" ends twice']


def test_sequence_a_participant_may_end_without_being_created() -> None:
    payload = worker_sequence(msg("billing", "worker", "hi", "async"), {"end": "billing"})
    assert seq_messages(payload) == []


def test_sequence_creation_inside_alt_branches_follows_drawn_order() -> None:
    payload = worker_sequence(
        {
            "fragment": "alt",
            "branches": [
                {"label": "first", "steps": [start()]},
                {"label": "second", "steps": [msg("billing", "worker", "again", "async")]},
            ],
        }
    )
    assert seq_messages(payload) == []


def test_sequence_note_needs_text_and_over() -> None:
    needs = ["<q-sequence> note needs text and the participants it sits over"]
    for bad in (
        {"note": "", "over": ["a"]},
        {"note": " ", "over": ["a"]},
        {"note": 4, "over": ["a"]},
        {"note": "n"},
        {"note": "n", "over": []},
        {"note": "n", "over": "a"},
    ):
        assert seq_messages(small(msg("a", "b", kind="async"), bad)) == needs, bad


def test_sequence_note_and_end_must_name_known_participants() -> None:
    base = msg("a", "b", kind="async")
    assert seq_messages(small(base, {"note": "n", "over": ["a", "ledgr"]})) == [
        '<q-sequence> note names unknown participant "ledgr"'
    ]
    assert seq_messages(small(base, {"note": "n", "over": ["ledgr", "ledgr"]})) == [
        '<q-sequence> note names unknown participant "ledgr"'
    ]
    assert seq_messages(small(base, {"end": "ledgr"})) == ['<q-sequence> end names unknown participant "ledgr"']
    assert seq_messages(small(base, {"end": 5})) == ['<q-sequence> end names unknown participant "5"']


def test_sequence_unknown_fragment_type() -> None:
    payload = small(msg("a", "b", kind="async"), {"fragment": "critical", "steps": [msg("a", "b", kind="async")]})
    assert seq_messages(payload) == ['<q-sequence> unknown fragment type "critical"; use alt, opt, loop or par']


@pytest.mark.parametrize("kind", ["alt", "par"])
def test_sequence_alt_and_par_need_two_branches(kind: str) -> None:
    one = {"fragment": kind, "branches": [{"label": "only", "steps": [msg("a", "b", kind="async")]}]}
    for branches in (None, [], "x", one["branches"]):
        step = {"fragment": kind}
        if branches is not None:
            step["branches"] = branches
        assert seq_messages(small(msg("a", "b", kind="async"), step)) == [f"<q-sequence> {kind} needs at least 2 branches"], branches


@pytest.mark.parametrize("kind", ["alt", "par"])
def test_sequence_each_branch_needs_a_label(kind: str) -> None:
    for bad in ({"steps": [msg("a", "b", kind="async")]}, {"label": " ", "steps": [msg("a", "b", kind="async")]}, 3):
        step = {"fragment": kind, "branches": [{"label": "ok", "steps": [msg("a", "b", kind="async")]}, bad]}
        assert seq_messages(small(step)) == [f"<q-sequence> each {kind} branch needs a label"], bad


def test_sequence_fragments_and_branches_need_steps() -> None:
    base = msg("a", "b", kind="async")
    for step in (
        {"fragment": "loop", "label": "up to 3 attempts"},
        {"fragment": "loop", "label": "up to 3 attempts", "steps": []},
        {"fragment": "loop", "label": "up to 3 attempts", "steps": "x"},
    ):
        assert seq_messages(small(base, step)) == ['<q-sequence> fragment "up to 3 attempts" has no steps'], step
    assert seq_messages(small(base, {"fragment": "opt", "steps": []})) == ['<q-sequence> fragment "opt" has no steps']
    branchless = {"fragment": "alt", "label": "pick", "branches": [{"label": "x", "steps": [base]}, {"label": "y", "steps": []}]}
    assert seq_messages(small(branchless)) == ['<q-sequence> fragment "pick" has no steps']
    unlabelled = {"fragment": "par", "branches": [{"label": "x"}, {"label": "y", "steps": [base]}]}
    assert seq_messages(small(unlabelled)) == ['<q-sequence> fragment "par" has no steps']


def test_sequence_nested_fragment_data_is_checked_at_depth() -> None:
    inner = {"fragment": "loop", "label": "retry", "steps": [msg("a", "nope", kind="async")]}
    outer = {"fragment": "opt", "steps": [{"fragment": "alt", "branches": [{"label": "x", "steps": [inner]}, {"label": "y", "steps": [msg("a", "b", kind="async")]}]}]}
    assert seq_messages(small(outer)) == ['<q-sequence> message 1 names unknown participant "nope"']


def test_sequence_deeply_nested_fragments_do_not_crash() -> None:
    step: dict = msg("a", "b", kind="async")
    for _ in range(400):
        step = {"fragment": "opt", "steps": [step]}
    got = seq_messages(small(step))
    assert got == [] or got == ["<q-sequence> step must be one message, note, end or fragment"]
    page = seq_markup(small(step))
    assert isinstance(kitcheck.check_html_warnings(page, CATALOG, label="page.html"), list)
    assert isinstance(kitcheck.inject_sequence_fallbacks(page), str)


def test_sequence_a_supplied_message_id_must_be_a_non_empty_string() -> None:
    for bad in ("", "  ", 7, None, ["x"]):
        got = seq_messages(small(msg("a", "b", kind="async", id=bad)))
        assert got == ["<q-sequence> message 1 id must be a non-empty string"], bad
    assert seq_messages(small(msg("a", "b", kind="async"))) == []


def test_sequence_a_supplied_fragment_label_must_be_a_non_empty_string() -> None:
    inner = msg("a", "b", kind="async")
    for kind in ("opt", "loop"):
        for bad in ("", "  ", 7, None):
            step = {"fragment": kind, "label": bad, "steps": [inner]}
            assert seq_messages(small(step)) == [f"<q-sequence> {kind} label must be a non-empty string"], (kind, bad)
    for kind in ("alt", "par"):
        for bad in ("", 7):
            branches = [{"label": "x", "steps": [inner]}, {"label": "y", "steps": [inner]}]
            step = {"fragment": kind, "label": bad, "branches": branches}
            assert seq_messages(small(step)) == [f"<q-sequence> {kind} label must be a non-empty string"], (kind, bad)
    assert seq_messages(small({"fragment": "opt", "steps": [inner]})) == []


def test_sequence_traces_must_be_a_list_with_id_label_and_two_steps() -> None:
    def patch(value):
        return lambda p: p.update(traces=value)

    assert seq_messages(checkout(patch({}))) == ["<q-sequence> traces must be a list"]
    assert seq_messages(checkout(patch("x"))) == ["<q-sequence> traces must be a list"]
    for trace in (5, {"label": "T", "steps": []}, {"id": "t"}, {"id": "", "label": "T"}, {"id": "t", "label": " "}):
        got = seq_messages(checkout(patch([trace])))
        assert got[0] == "<q-sequence> each trace needs an id and a label", trace
    short = {"id": "t", "label": "T", "steps": [{"message": "paid", "value": 1}]}
    assert seq_messages(checkout(patch([short]))) == ['<q-sequence> trace "t" needs at least 2 steps']
    nosteps = {"id": "t", "label": "T"}
    assert seq_messages(checkout(patch([nosteps]))) == ['<q-sequence> trace "t" needs at least 2 steps']
    dup = [
        {"id": "t", "label": "T", "steps": [{"message": "paid", "value": 1}, {"message": "paid", "value": 2}]},
        {"id": "t", "label": "T2", "steps": [{"message": "paid", "value": 1}, {"message": "paid", "value": 2}]},
        {"id": "t", "label": "T3", "steps": [{"message": "paid", "value": 1}, {"message": "paid", "value": 2}]},
    ]
    assert seq_messages(checkout(patch(dup))) == ['<q-sequence> has duplicate trace id "t"']


def trace_with(*steps: dict):
    return lambda p: p.update(traces=[{"id": "t", "label": "T", "steps": list(steps)}])


PAID = {"message": "paid", "value": 1}


def test_sequence_trace_step_needs_message_and_value() -> None:
    needs = ['<q-sequence> trace "t" step 2 needs a message and a value']
    for bad in ({"value": 1}, {"message": "paid"}, {"message": 4, "value": 1}, 5, None, "paid"):
        assert seq_messages(checkout(trace_with(PAID, bad))) == needs, bad
    assert seq_messages(checkout(trace_with(PAID, {"message": "paid", "value": None}))) == []


def test_sequence_trace_step_must_name_a_message_id() -> None:
    got = seq_messages(checkout(trace_with(PAID, {"message": "charge-retry", "value": 1})))
    assert got == ['<q-sequence> trace "t" step 2 names unknown message "charge-retry"']
    got = seq_messages(checkout(trace_with(PAID, {"message": "billing", "value": 1})))
    assert got == ['<q-sequence> trace "t" step 2 names unknown message "billing"']


def test_sequence_trace_value_and_note_rules_match_q_flow() -> None:
    def step(**more):
        return {"message": "paid", "value": 1, **more}

    got = seq_messages(checkout(trace_with(PAID, {"message": "paid", "value": "\ud800"})))
    assert got == ['<q-sequence> trace "t" step 2 has a value that isn\'t JSON']
    got = seq_messages(checkout(trace_with(PAID, step(value=list(range(399))))))
    assert got == ['<q-sequence> trace "t" step 2 value is 401 lines; at most 400']
    assert seq_messages(checkout(trace_with(PAID, step(value=list(range(398)))))) == []
    assert seq_messages(checkout(trace_with(PAID, step(note=5)))) == ['<q-sequence> trace "t" step 2 note must be a string']
    assert seq_messages(checkout(trace_with(PAID, step(note=None)))) == ['<q-sequence> trace "t" step 2 note must be a string']


def test_sequence_text_with_an_unpaired_surrogate_fails_once() -> None:
    expected = ["<q-sequence> sequence data holds text that can't be written as UTF-8"]

    def patch(p: dict) -> None:
        p["participants"][0]["label"] = "Shopper \ud800"
        p["steps"][0]["label"] = "place \udfff order"
        p["traces"][0]["steps"][1]["note"] = "x \ud800"

    assert seq_messages(checkout(patch)) == expected

    def key(p: dict) -> None:
        p["kinds"]["bad\ud800"] = 6

    assert seq_messages(checkout(key)) == expected


def test_sequence_text_with_a_valid_surrogate_pair_passes() -> None:
    def patch(p: dict) -> None:
        p["participants"][0]["label"] = "Shopper \U0001f600"
        p["traces"][0]["steps"][1]["note"] = "ok \U0001f600"

    assert seq_messages(checkout(patch)) == []


def test_sequence_failures_keep_check_order() -> None:
    payload = small(
        msg("a", "nope", "m", "return", create=False),
        {"note": "n", "over": ["ledgr"]},
        extra={"kinds": {"k": 0}, "traces": {}},
    )
    payload["participants"][0]["kind"] = "undeclared"
    assert seq_messages(payload) == [
        '<q-sequence> kind "k" color must be an integer from 1 to 8',
        '<q-sequence> participant "a" has undeclared kind "undeclared"',
        '<q-sequence> message 1 names unknown participant "nope"',
        '<q-sequence> message 1 has unknown type "return"; use call, reply or async',
        "<q-sequence> message 1 create must be true",
        '<q-sequence> note names unknown participant "ledgr"',
        "<q-sequence> traces must be a list",
    ]


def test_sequence_id_constructor_is_an_ordinary_id() -> None:
    payload = {
        "kinds": {"constructor": 1},
        "participants": [
            {"id": "constructor", "label": "Constructor", "kind": "constructor"},
            {"id": "__proto__", "label": "Proto"},
        ],
        "steps": [
            msg("constructor", "__proto__", "call it", "call", id="hasOwnProperty"),
            msg("__proto__", "constructor", "back", "reply", id="toString"),
        ],
        "traces": [
            {"id": "constructor", "label": "T", "steps": [{"message": "hasOwnProperty", "value": 1}, {"message": "toString", "value": 2}]}
        ],
    }
    assert seq_messages(payload) == []
    assert seq_warnings(payload) == []
    unknown = small(msg("a", "toString"), msg("constructor", "a"))
    assert seq_messages(unknown) == [
        '<q-sequence> message 1 names unknown participant "toString"',
        '<q-sequence> message 2 names unknown participant "constructor"',
    ]
    trace = checkout(trace_with(PAID, {"message": "constructor", "value": 1}))
    assert seq_messages(trace) == ['<q-sequence> trace "t" step 2 names unknown message "constructor"']


# warnings


def test_sequence_label_over_40_characters_warns() -> None:
    long = small(msg("a", "b", "x" * 41, "async"))
    assert seq_messages(long) == []
    assert seq_warnings(long) == [
        "<q-sequence> message 1 label is 41 characters: labels over 40 characters crowd the row; move the rest to the detail"
    ]
    assert seq_warnings(small(msg("a", "b", "x" * 40, "async"))) == []
    spec = small(msg("a", "b", "x" * 52, "async"))
    assert "is 52 characters" in seq_warnings(spec)[0]


def test_sequence_over_60_messages_warns() -> None:
    def many(count: int) -> dict:
        return small(*[msg("a", "b", f"m{i}", "async") for i in range(count)])

    assert seq_messages(many(64)) == []
    assert seq_warnings(many(64)) == [
        "<q-sequence> has 64 messages: sequences over 60 messages are hard to follow; split it"
    ]
    assert seq_warnings(many(61)) != []
    assert seq_warnings(many(60)) == []


def test_sequence_trace_warnings_use_the_sequence_prefix() -> None:
    def step(**more):
        return {"message": "paid", "value": 1, **more}

    got = seq_warnings(checkout(trace_with(PAID, step(value=list(range(39))))))
    assert got == [
        '<q-sequence> trace "t" step 2 value is 41 lines: values over 40 lines are hard to scan; '
        "keep the fields the reader needs"
    ]
    assert seq_warnings(checkout(trace_with(PAID, step(value=list(range(38)))))) == []
    got = seq_warnings(checkout(trace_with(PAID, step(note="n" * 121))))
    assert got == ['<q-sequence> trace "t" step 2 note is 121 characters: notes over 120 characters crowd the panel']
    assert seq_warnings(checkout(trace_with(PAID, step(note="n" * 120)))) == []
    got = seq_warnings(checkout(trace_with(*[step() for _ in range(31)])))
    assert got == ['<q-sequence> trace "t" has 31 steps: traces over 30 steps are hard to follow; split it']
    assert seq_warnings(checkout(trace_with(*[step() for _ in range(30)]))) == []


def no_reply(number: int, label: str = "m") -> str:
    return f'<q-sequence> call {number} "{label}" has no matching reply'


def stray(number: int, label: str = "m") -> str:
    return f'<q-sequence> reply {number} "{label}" answers no call'


def test_sequence_a_call_no_reply_answers_warns() -> None:
    payload = checkout(lambda p: p["steps"][4].update(type="async"))
    assert seq_messages(payload) == []
    assert seq_warnings(payload) == [no_reply(2, "charge order")]
    assert seq_warnings(small(msg("a", "b", "ask"))) == [no_reply(1, "ask")]


def test_sequence_reply_with_no_open_call_warns() -> None:
    assert seq_warnings(small(msg("b", "a", "done", "reply"))) == [stray(1, "done")]
    assert seq_warnings(small(msg("a", "b", "ask"), msg("a", "b", "wrong way", "reply"))) == [
        no_reply(1, "ask"),
        stray(2, "wrong way"),
    ]


def test_sequence_reply_closes_the_most_recent_open_call_between_the_pair() -> None:
    payload = small(msg("a", "b", "first"), msg("a", "b", "second"), msg("b", "a", "answer", "reply"))
    assert seq_warnings(payload) == [no_reply(1, "first")]
    other_pair = small(msg("a", "b", "ab"), msg("a", "c", "ac"), msg("c", "a", "answer", "reply"), msg("b", "a", "answer", "reply"))
    assert seq_warnings(other_pair) == []


def test_sequence_async_and_self_messages_open_nothing() -> None:
    assert seq_warnings(small(msg("a", "b", "fire", "async"), msg("a", "a", "think", "call"))) == []
    stray_self = small(msg("a", "a", "back", "reply"))
    assert seq_warnings(stray_self) == []


def test_sequence_ending_a_participant_with_an_open_call_to_it_warns() -> None:
    payload = small(msg("a", "b", "ask"), {"end": "b"})
    assert seq_warnings(payload) == [no_reply(1, "ask")]
    answered = small(msg("a", "b", "ask"), msg("b", "a", "ok", "reply"), {"end": "b"})
    assert seq_warnings(answered) == []
    caller_ends = small(msg("a", "b", "ask"), {"end": "a"}, msg("b", "a", "ok", "reply"))
    assert seq_messages(caller_ends) == ['<q-sequence> message 2 touches "A" after it ends']


def alt_of(kind: str, *branches: list[dict]) -> dict:
    return {"fragment": kind, "branches": [{"label": f"b{i}", "steps": steps} for i, steps in enumerate(branches)]}


def test_sequence_alt_answers_a_call_only_when_every_branch_replies() -> None:
    reply = msg("b", "a", "ok", "reply")
    ping = msg("a", "b", "ping", "async")
    both = small(msg("a", "b", "ask"), alt_of("alt", [reply], [dict(reply)]))
    assert seq_warnings(both) == []
    one = small(msg("a", "b", "ask"), alt_of("alt", [reply], [ping]))
    assert seq_warnings(one) == [no_reply(1, "ask")]


def test_sequence_par_answers_a_call_when_any_branch_replies() -> None:
    reply = msg("b", "a", "ok", "reply")
    ping = msg("a", "b", "ping", "async")
    one = small(msg("a", "b", "ask"), alt_of("par", [reply], [ping]))
    assert seq_warnings(one) == []
    neither = small(msg("a", "b", "ask"), alt_of("par", [ping], [dict(ping)]))
    assert seq_warnings(neither) == [no_reply(1, "ask")]


def test_sequence_a_call_opened_in_a_branch_and_not_answered_there_warns() -> None:
    reply = msg("b", "a", "ok", "reply")
    ping = msg("a", "b", "ping", "async")
    payload = small(alt_of("alt", [msg("a", "b", "ask")], [ping]), reply)
    assert seq_warnings(payload) == [no_reply(1, "ask"), stray(3, "ok")]
    par = small(alt_of("par", [msg("a", "b", "ask")], [ping]), reply)
    assert seq_warnings(par) == [no_reply(1, "ask"), stray(3, "ok")]


def test_sequence_alt_branches_start_from_the_calls_open_when_it_began() -> None:
    first = small(
        msg("a", "b", "ask"),
        alt_of("alt", [msg("b", "a", "ok", "reply")], [msg("b", "a", "no", "reply")]),
        msg("b", "a", "again", "reply"),
    )
    assert seq_warnings(first) == [stray(4, "again")]


def test_sequence_opt_and_loop_answer_calls_when_the_body_does() -> None:
    reply = msg("b", "a", "ok", "reply")
    for kind in ("opt", "loop"):
        answered = small(msg("a", "b", "ask"), {"fragment": kind, "steps": [dict(reply)]})
        assert seq_warnings(answered) == [], kind
        opened = small({"fragment": kind, "steps": [msg("a", "b", "ask")]}, dict(reply))
        assert seq_warnings(opened) == [no_reply(1, "ask"), stray(2, "ok")], kind
        within = small({"fragment": kind, "steps": [msg("a", "b", "ask"), dict(reply)]})
        assert seq_warnings(within) == [], kind


def test_sequence_warnings_do_not_run_the_matching_while_a_failure_stands() -> None:
    payload = small(msg("a", "b", "ask"), msg("a", "nope", "bad"))
    assert seq_messages(payload) == ['<q-sequence> message 2 names unknown participant "nope"']
    assert seq_warnings(payload) == []


def test_sequence_warnings_never_affect_passed() -> None:
    html = page(seq_markup(small(msg("a", "b", "x" * 50))), libraries={"kit": "1.0.0"}, blocks=kit_blocks())
    result = run(html, REAL_STORE)
    assert result["passed"] is True and result["failures"] == []
    assert [w["detail"].split(": ", 1)[1] for w in result["warnings"]] == [
        "<q-sequence> message 1 label is 50 characters: labels over 40 characters crowd the row; move the rest to the detail",
        no_reply(1, "x" * 50),
    ]
