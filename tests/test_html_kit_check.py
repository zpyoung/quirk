"""The kit static check: tolerant element-stack validation of q-* markup, the JSX check and the
lazy catalog load behind ``run_checks``.

Everything runs offline against the real ``vendor/kit/1.0.0/catalog.json`` unless a test says
otherwise.
"""
from __future__ import annotations

import json
import sys
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
    # html ignores the slash on a non-void element, so the element stays open
    got = messages('<q-tabs/><section><h3>A</h3></section>')
    assert got == []


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
