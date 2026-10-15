"""Browser tests for the layout elements `q-grid`, `q-panel`, `q-sidenote` and `q-compare`.

Pages are built with the real CLI through the helpers in `tests/test_html_kit_elements.py`, then
driven through the node harness at fixed viewport widths. The tests skip only when node,
`scripts/verify/node_modules` or a launchable browser is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_html_kit_elements import KIT_SCRIPT, _mini_page, assert_clean, ev, run

PANELS = "".join(f"<q-panel><h3>Panel {i}</h3><p>Body {i}.</p></q-panel>\n" for i in range(1, 13))

NO_SCROLL = "document.documentElement.scrollWidth <= window.innerWidth"

OPTIONS = ["Self-host", "Managed", "Hybrid"]


def _compare(element_id: str, options: list[str], recommended: int) -> str:
    head = "<th>Criterion</th>" + "".join(f"<th>{name}</th>" for name in options)
    rows = "".join(
        f"<tr><th>{criterion}</th>" + "".join(f"<td>{criterion} of {name}</td>" for name in options) + "</tr>"
        for criterion in ("Cost", "Setup", "On-call")
    )
    return (
        f'<q-compare id="{element_id}" recommended="{recommended}"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{rows}</tbody></table></q-compare>\n"
    )


MANY_OPTIONS = [f"Option {i}" for i in range(1, 11)]

SIDENOTES = """<div data-layout="longform" id="long"><main>
<p id="para">The build got faster<q-sidenote id="note1">Measured on main, excluding reruns.</q-sidenote> after the cache moved,
and the queue shrank<q-sidenote id="note2">Queue depth is sampled every minute.</q-sidenote> as well.</p>
</main></div>
<div id="plain"><p>A plain page note<q-sidenote id="plain-note">Outside longform.</q-sidenote> stays in the text.</p></div>
"""

BODY = (
    f'<q-grid id="grid">\n{PANELS}</q-grid>\n'
    '<q-grid id="spans">\n'
    '<q-panel id="s1"><h3>One</h3><p>a</p></q-panel>\n'
    '<q-panel id="s2" span="2"><h3>Two</h3><p>b</p></q-panel>\n'
    '<q-panel id="s3" span="3"><h3>Three</h3><p>c</p></q-panel>\n'
    '<q-panel id="sfull" span="full"><h3>Full</h3><p>d</p></q-panel>\n'
    '<div id="sdata" data-span="2"><p>e</p></div>\n'
    "</q-grid>\n" + SIDENOTES + _compare("cmp", OPTIONS, 2) + _compare("wide", MANY_OPTIONS, 3)
)


@pytest.fixture(scope="module")
def layout_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _mini_page(tmp_path_factory.mktemp("layout-elements"), BODY, "layout")


@pytest.fixture(scope="module")
def nojs_page(layout_page: Path) -> Path:
    stripped, count = KIT_SCRIPT.subn("", layout_page.read_text(encoding="utf-8"))
    assert count == 1, "the built page should carry exactly one kit script block"
    page = layout_page.with_name("layout-nojs.html")
    page.write_text(stripped, encoding="utf-8")
    return page


def _width(selector: str) -> str:
    return f"document.querySelector('{selector}').getBoundingClientRect().width"


def _columns(selector: str) -> str:
    return f"getComputedStyle(document.querySelector('{selector}')).gridTemplateColumns.split(' ').length"


# --- q-grid -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("width", "columns"), [(375, 1), (700, 1), (701, 2), (900, 2), (1099, 2), (1280, 4), (1799, 4), (2000, 6)])
def test_grid_column_count_follows_the_viewport_width(layout_page: Path, width: int, columns: int) -> None:
    out = run(layout_page, ev(_columns("#grid"), "columns"), viewport={"width": width, "height": 800})
    assert_clean(out)
    assert out["results"]["columns"] == columns


def test_grid_children_share_equal_columns(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev("[...document.querySelectorAll('#grid > q-panel')].slice(0, 4).map((p) => Math.round(p.getBoundingClientRect().width))", "widths"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    assert len(set(out["results"]["widths"])) == 1


@pytest.mark.parametrize("width", [375, 900, 1280, 2000])
def test_grid_never_scrolls_the_page_sideways(layout_page: Path, width: int) -> None:
    out = run(layout_page, ev(NO_SCROLL, "fits"), viewport={"width": width, "height": 800})
    assert_clean(out)
    assert out["results"]["fits"] is True


# --- q-panel ----------------------------------------------------------------------------------


def _span_widths() -> list[dict]:
    return [
        ev(_width("#s1"), "one"),
        ev(_width("#s2"), "two"),
        ev(_width("#s3"), "three"),
        ev(_width("#sfull"), "full"),
        ev(_width("#sdata"), "data"),
        ev(_width("#spans"), "grid"),
        ev("parseFloat(getComputedStyle(document.querySelector('#spans')).columnGap)", "gap"),
    ]


def test_panel_span_takes_that_many_columns_at_wide_width(layout_page: Path) -> None:
    out = run(layout_page, *_span_widths(), viewport={"width": 1280, "height": 800})
    assert_clean(out)
    r = out["results"]
    one, gap = r["one"], r["gap"]
    assert r["two"] == pytest.approx(2 * one + gap, abs=1.5)
    assert r["three"] == pytest.approx(3 * one + 2 * gap, abs=1.5)
    assert r["full"] == pytest.approx(r["grid"], abs=1.5)
    assert r["data"] == pytest.approx(r["two"], abs=1.5)


def test_panel_span_is_clamped_to_the_columns_of_the_row(layout_page: Path) -> None:
    out = run(layout_page, *_span_widths(), viewport={"width": 900, "height": 800})
    assert_clean(out)
    r = out["results"]
    assert r["three"] == pytest.approx(r["grid"], abs=1.5)
    assert r["two"] == pytest.approx(r["grid"], abs=1.5)
    assert r["one"] < r["grid"]


def test_panel_spans_collapse_to_one_column_on_a_phone(layout_page: Path) -> None:
    out = run(layout_page, *_span_widths(), viewport={"width": 375, "height": 800})
    assert_clean(out)
    r = out["results"]
    assert r["two"] == pytest.approx(r["grid"], abs=1.5)
    assert r["three"] == pytest.approx(r["grid"], abs=1.5)
    assert r["one"] == pytest.approx(r["grid"], abs=1.5)


def test_panel_is_a_bordered_box_with_its_heading_as_title(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const panel = document.querySelector('#s1');
              const style = getComputedStyle(panel);
              const heading = panel.querySelector('h3');
              return {
                border: style.borderTopWidth + ' ' + style.borderTopStyle,
                radius: style.borderTopLeftRadius,
                display: style.display,
                headingTop: getComputedStyle(heading).marginTop,
              };
            })()""",
            "panel",
        ),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    panel = out["results"]["panel"]
    assert panel["border"] == "1px solid"
    assert panel["radius"] == "6px"
    assert panel["display"] == "block"
    assert panel["headingTop"] == "0px"


# --- q-sidenote -------------------------------------------------------------------------------


def _note_state(note: str, toggle: str) -> str:
    return f"""(() => {{
      const note = document.querySelector('{note}');
      const toggle = document.querySelector('{toggle}');
      const style = getComputedStyle(note);
      return {{
        display: style.display,
        toggleShown: !!toggle && getComputedStyle(toggle).display !== 'none',
        expanded: toggle && toggle.getAttribute('aria-expanded'),
        toggleText: toggle && toggle.textContent,
      }};
    }})()"""


TOGGLE = "button[data-q-sidenote-toggle]"


@pytest.mark.parametrize("width", [375, 900])
def test_sidenote_is_a_numbered_toggle_when_narrow(layout_page: Path, width: int) -> None:
    out = run(
        layout_page,
        ev(_note_state("#note1", "#para button[data-q-sidenote-toggle]"), "closed"),
        ev("[...document.querySelectorAll('#para button[data-q-sidenote-toggle]')].map((b) => b.textContent)", "numbers"),
        {"click": "#para button[data-q-sidenote-toggle]"},
        ev(_note_state("#note1", "#para button[data-q-sidenote-toggle]"), "open"),
        ev("document.querySelector('#note1').getBoundingClientRect().width > 0", "noteVisible"),
        {"click": "#para button[data-q-sidenote-toggle]"},
        ev(_note_state("#note1", "#para button[data-q-sidenote-toggle]"), "again"),
        ev(NO_SCROLL, "fits"),
        viewport={"width": width, "height": 800},
    )
    assert_clean(out)
    r = out["results"]
    assert r["closed"]["toggleShown"] is True and r["closed"]["expanded"] == "false"
    assert r["closed"]["display"] == "none"
    assert r["numbers"] == ["1", "2"]
    assert r["open"]["expanded"] == "true" and r["open"]["display"] != "none"
    assert r["noteVisible"] is True
    assert r["again"]["expanded"] == "false" and r["again"]["display"] == "none"
    assert r["fits"] is True


def test_sidenote_toggle_is_a_labelled_button_wired_to_its_note(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const toggle = document.querySelector('#para button[data-q-sidenote-toggle]');
              return {
                tag: toggle.tagName,
                type: toggle.type,
                label: toggle.getAttribute('aria-label'),
                controls: toggle.getAttribute('aria-controls'),
                before: toggle.nextElementSibling && toggle.nextElementSibling.id,
              };
            })()""",
            "toggle",
        ),
        viewport={"width": 375, "height": 800},
    )
    assert_clean(out)
    toggle = out["results"]["toggle"]
    assert toggle == {"tag": "BUTTON", "type": "button", "label": "Note 1", "controls": "note1", "before": "note1"}


def test_sidenote_sits_in_the_right_margin_of_a_wide_longform_page(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const para = document.querySelector('#para').getBoundingClientRect();
              const note = document.querySelector('#note1');
              const box = note.getBoundingClientRect();
              const style = getComputedStyle(note);
              const toggle = document.querySelector('#para button[data-q-sidenote-toggle]');
              return {
                float: style.float,
                display: style.display,
                right: box.left >= para.right - 1,
                inViewport: box.right <= window.innerWidth,
                lead: getComputedStyle(note, '::before').content,
                toggleShown: getComputedStyle(toggle).display !== 'none',
              };
            })()""",
            "wide",
        ),
        ev(NO_SCROLL, "fits"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    wide = out["results"]["wide"]
    assert wide["float"] == "right" and wide["display"] == "block"
    assert wide["right"] is True and wide["inViewport"] is True
    assert "counter(q-sidenote)" in wide["lead"]
    assert wide["toggleShown"] is False
    assert out["results"]["fits"] is True


def test_sidenote_outside_longform_stays_a_toggle_at_wide_width(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(_note_state("#plain-note", "#plain button[data-q-sidenote-toggle]"), "state"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    state = out["results"]["state"]
    assert state["toggleShown"] is True and state["display"] == "none"


@pytest.mark.parametrize("width", [375, 1280])
def test_sidenote_reads_inline_without_the_script(nojs_page: Path, width: int) -> None:
    out = run(
        nojs_page,
        ev(
            """(() => {
              const note = document.querySelector('#plain-note');
              const style = getComputedStyle(note);
              return {
                display: style.display,
                float: style.float,
                before: getComputedStyle(note, '::before').content,
                after: getComputedStyle(note, '::after').content,
                toggles: document.querySelectorAll('button[data-q-sidenote-toggle]').length,
                visible: note.getBoundingClientRect().width > 0,
              };
            })()""",
            "note",
        ),
        ev(NO_SCROLL, "fits"),
        javaScript=False,
        viewport={"width": width, "height": 800},
    )
    assert_clean(out)
    note = out["results"]["note"]
    assert note["display"] == "inline" and note["float"] == "none" and note["visible"] is True
    assert "(" in note["before"] and ")" in note["after"]
    assert note["toggles"] == 0
    assert out["results"]["fits"] is True


def test_sidenote_prints_inline(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const note = document.querySelector('#note1');
              const style = getComputedStyle(note);
              const toggle = document.querySelector('#para button[data-q-sidenote-toggle]');
              return {
                display: style.display,
                float: style.float,
                before: getComputedStyle(note, '::before').content,
                toggle: getComputedStyle(toggle).display,
              };
            })()""",
            "print",
        ),
        media="print",
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    printed = out["results"]["print"]
    assert printed["display"] == "inline" and printed["float"] == "none"
    assert "(" in printed["before"] and printed["toggle"] == "none"


# --- q-compare --------------------------------------------------------------------------------

STACK = """(() => {
  const host = document.querySelector('#cmp');
  const table = host.querySelector(':scope > table');
  const blocks = [...host.querySelectorAll(':scope > [data-q-stack] > [data-q-option]')];
  return {
    tableDisplay: getComputedStyle(table).display,
    stackDisplay: getComputedStyle(host.querySelector(':scope > [data-q-stack]')).display,
    headings: blocks.map((b) => b.querySelector('h3').firstChild.textContent.trim()),
    recommended: blocks.map((b) => b.hasAttribute('data-q-recommended')),
    terms: blocks[0].querySelectorAll('dt').length,
    firstValue: blocks[0].querySelector('dd').textContent,
  };
})()"""


def test_compare_stacks_one_block_per_option_with_the_recommended_first_on_a_phone(layout_page: Path) -> None:
    out = run(layout_page, ev(STACK, "stack"), ev(NO_SCROLL, "fits"), viewport={"width": 375, "height": 800})
    assert_clean(out)
    stack = out["results"]["stack"]
    assert stack["tableDisplay"] == "none"
    assert stack["stackDisplay"] == "block"
    assert stack["headings"] == ["Managed", "Self-host", "Hybrid"]
    assert stack["recommended"] == [True, False, False]
    assert stack["terms"] == 3
    assert stack["firstValue"] == "Cost of Managed"
    assert out["results"]["fits"] is True


def test_compare_stacks_at_exactly_700px_and_not_at_701px(layout_page: Path) -> None:
    out = run(
        layout_page,
        {"viewport": {"width": 700, "height": 800}},
        ev(STACK, "at700"),
        {"viewport": {"width": 701, "height": 800}},
        ev(STACK, "at701"),
    )
    assert_clean(out)
    assert out["results"]["at700"]["tableDisplay"] == "none"
    assert out["results"]["at701"]["tableDisplay"] == "table"
    assert out["results"]["at701"]["stackDisplay"] == "none"


def test_compare_shows_the_table_with_the_recommended_column_marked_at_desktop_width(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(STACK, "stack"),
        ev(
            """(() => {
              const marked = [...document.querySelectorAll('#cmp thead th')].map((th) => th.hasAttribute('data-q-recommended'));
              const badges = document.querySelectorAll('#cmp thead [data-q-badge]').length;
              const host = document.querySelector('#cmp').getBoundingClientRect();
              const column = document.querySelector('main').getBoundingClientRect();
              return { marked, badges, hostWidth: host.width, columnWidth: column.width };
            })()""",
            "table",
        ),
        ev(NO_SCROLL, "fits"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    r = out["results"]
    assert r["stack"]["tableDisplay"] == "table" and r["stack"]["stackDisplay"] == "none"
    assert r["table"]["marked"] == [False, False, True, False]
    assert r["table"]["badges"] == 1
    assert r["table"]["hostWidth"] == pytest.approx(r["table"]["columnWidth"], abs=1.5)
    assert r["fits"] is True


def test_compare_widens_past_the_1440px_column_when_the_options_do_not_fit(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const host = document.querySelector('#wide');
              const box = host.getBoundingClientRect();
              const wrap = document.querySelector('.q-wrap:has(> .q-page)').getBoundingClientRect();
              return {
                width: box.width,
                wrapWidth: wrap.width,
                centre: box.left + box.width / 2,
                viewport: window.innerWidth,
                scrolls: host.scrollWidth > host.clientWidth + 1,
              };
            })()""",
            "wide",
        ),
        ev(NO_SCROLL, "fits"),
        viewport={"width": 2000, "height": 800},
    )
    assert_clean(out)
    wide = out["results"]["wide"]
    assert wide["wrapWidth"] <= 1440 + 1
    assert wide["width"] > wide["wrapWidth"]
    assert wide["width"] <= wide["viewport"] - 2 * 16
    assert wide["centre"] == pytest.approx(wide["viewport"] / 2, abs=2)
    assert wide["scrolls"] is False
    assert out["results"]["fits"] is True


def test_compare_that_does_not_fit_even_widened_scrolls_inside_its_own_box(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            """(() => {
              const host = document.querySelector('#wide');
              const box = host.getBoundingClientRect();
              return {
                width: box.width,
                viewport: window.innerWidth,
                scrolls: host.scrollWidth > host.clientWidth + 1,
                left: box.left,
              };
            })()""",
            "wide",
        ),
        ev(NO_SCROLL, "fits"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    wide = out["results"]["wide"]
    assert wide["scrolls"] is True
    assert wide["left"] >= 0 and wide["width"] <= wide["viewport"] - 2 * 16 + 1
    assert out["results"]["fits"] is True


def test_compare_inside_a_panel_in_a_grid_stays_within_the_panel_and_scrolls_itself(tmp_path: Path) -> None:
    body = (
        '<q-grid id="g"><q-panel id="p1"><h3>Left</h3>'
        + _compare("nested", MANY_OPTIONS, 3)
        + '</q-panel><q-panel id="p2"><h3>Right</h3><p>Neighbour.</p></q-panel></q-grid>\n'
    )
    page = _mini_page(tmp_path, body, "nested")
    out = run(
        page,
        ev(
            """(() => {
              const c = document.querySelector('#nested').getBoundingClientRect();
              const p = document.querySelector('#p1').getBoundingClientRect();
              const n = document.querySelector('#p2').getBoundingClientRect();
              const host = document.querySelector('#nested');
              return {
                cLeft: c.left, cRight: c.right, pLeft: p.left, pRight: p.right, nLeft: n.left,
                scrolls: host.scrollWidth > host.clientWidth + 1,
              };
            })()""",
            "box",
        ),
        ev(NO_SCROLL, "fits"),
        viewport={"width": 1280, "height": 800},
    )
    assert_clean(out)
    box = out["results"]["box"]
    assert box["cLeft"] >= box["pLeft"] - 1 and box["cRight"] <= box["pRight"] + 1
    assert box["cRight"] <= box["nLeft"]
    assert box["scrolls"] is True
    assert out["results"]["fits"] is True


@pytest.mark.parametrize("width", [375, 1280])
def test_compare_reads_as_a_scrolling_table_without_the_script(nojs_page: Path, width: int) -> None:
    out = run(
        nojs_page,
        ev(
            """(() => {
              const host = document.querySelector('#wide');
              const table = host.querySelector('table');
              return {
                tableDisplay: getComputedStyle(table).display,
                stack: host.querySelectorAll('[data-q-stack]').length,
                overflow: getComputedStyle(host).overflowX,
                scrolls: host.scrollWidth > host.clientWidth + 1,
                hostWithinViewport: host.getBoundingClientRect().right <= window.innerWidth,
              };
            })()""",
            "wide",
        ),
        ev(NO_SCROLL, "fits"),
        javaScript=False,
        viewport={"width": width, "height": 800},
    )
    assert_clean(out)
    wide = out["results"]["wide"]
    assert wide["tableDisplay"] == "table" and wide["stack"] == 0
    assert wide["overflow"] == "auto" and wide["scrolls"] is True
    assert wide["hostWithinViewport"] is True
    assert out["results"]["fits"] is True


def test_compare_prints_as_blocks(layout_page: Path) -> None:
    out = run(layout_page, ev(STACK, "stack"), media="print", viewport={"width": 1280, "height": 800})
    assert_clean(out)
    assert out["results"]["stack"]["tableDisplay"] == "none"
    assert out["results"]["stack"]["headings"][0] == "Managed"


def test_compare_drops_the_recommendation_when_the_attribute_leaves_the_option_range(tmp_path: Path) -> None:
    page = _mini_page(tmp_path, _compare("bad", OPTIONS, 3), "bad")
    summary = """(() => {
      const blocks = [...document.querySelectorAll('#bad [data-q-option]')];
      return {
        order: blocks.map((b) => b.querySelector('h3').firstChild.textContent.trim()),
        badges: document.querySelectorAll('#bad [data-q-badge]').length,
      };
    })()"""
    out = run(
        page,
        ev(summary, "before"),
        ev("document.querySelector('#bad').setAttribute('recommended', '9')", "set"),
        ev(summary, "after"),
        viewport={"width": 375, "height": 800},
    )
    assert_clean(out)
    assert out["results"]["before"] == {"order": ["Hybrid", "Self-host", "Managed"], "badges": 2}
    assert out["results"]["after"] == {"order": OPTIONS, "badges": 0}


def test_the_kit_script_defines_the_two_scripted_layout_elements_and_not_the_css_only_ones(layout_page: Path) -> None:
    out = run(
        layout_page,
        ev(
            "['q-grid', 'q-panel', 'q-sidenote', 'q-compare'].map((tag) => !!customElements.get(tag))",
            "defined",
        ),
    )
    assert_clean(out)
    assert out["results"]["defined"] == [False, False, True, True]


def test_the_stacked_blocks_hold_no_duplicate_ids(tmp_path: Path) -> None:
    body = _compare("ids", OPTIONS, 1).replace("<td>Cost of Self-host</td>", '<td><span id="dup">x</span></td>')
    page = _mini_page(tmp_path, body, "ids")
    out = run(page, ev("document.querySelectorAll('#dup').length", "count"), viewport={"width": 375, "height": 800})
    assert_clean(out)
    assert out["results"]["count"] == 1
