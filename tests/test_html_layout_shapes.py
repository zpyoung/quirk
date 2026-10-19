"""Page-shape geometry: the six examples per template build, verify and lay out as specified.

Builds always run. The browser tests need `scripts/verify/node_modules`, node and a launchable
browser, and skip otherwise; nothing here touches the network. Pages are driven at fixed viewport
widths through the node harness from `tests/test_html_kit_elements.py`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.test_html_kit_elements import _node_ready, ev, run
from tests.test_html_builder import run_cli, seal

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "writing-html-artifacts"
CLI = SKILL / "scripts" / "quirk_html.py"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import create  # noqa: E402
from htmlkit.header import read_header  # noqa: E402
from htmlkit.layouts import LAYOUTS  # noqa: E402

TEMPLATES = ("report", "components")
EXAMPLES = [(template, shape) for template in TEMPLATES for shape in LAYOUTS]
IDS = [f"{template}-{shape}" for template, shape in EXAMPLES]

# DOM order of the regions each example carries, per the shape table in the tech spec
REGIONS = {
    "explainer": ["summary", "nav", "main"],
    "longform": ["summary", "nav", "main"],
    "tool": ["main", "summary"],
    "comparison": ["summary", "main"],
    "dashboard": ["summary", "main"],
    "reference": ["summary", "nav", "main"],
}
NON_DASHBOARD = [shape for shape in LAYOUTS if shape != "dashboard"]


def _example(template: str, shape: str) -> Path:
    return SKILL / "templates" / template / "examples" / f"{shape}.src.html"


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], tuple[Path, dict]]:
    """Every example built through the CLI: its page and the build's JSON result."""
    work = tmp_path_factory.mktemp("shape-examples")
    project = work / "project"
    project.mkdir()
    user = work / "user"
    user.mkdir()
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}
    built: dict[tuple[str, str], tuple[Path, dict]] = {}
    for template, shape in EXAMPLES:
        src = _example(template, shape)
        assert src.is_file(), f"missing example {src}"
        page = work / f"{template}-{shape}.html"
        code, result = run_cli("build", src, "--out", page, "--project-dir", project, env=env)
        assert code == 0, f"{template}/{shape}: {result}"
        built[(template, shape)] = (page, result)
    return built


def _page(pages: dict, template: str, shape: str) -> Path:
    return pages[(template, shape)][0]


def test_there_are_twelve_examples() -> None:
    found = sorted(p.relative_to(SKILL / "templates").as_posix() for p in (SKILL / "templates").glob("*/examples/*.src.html"))
    assert found == sorted(f"{t}/examples/{s}.src.html" for t, s in EXAMPLES)


@pytest.mark.parametrize(("template", "shape"), EXAMPLES, ids=IDS)
def test_example_builds_with_every_check_passing_and_records_its_layout(pages: dict, template: str, shape: str) -> None:
    page, result = pages[(template, shape)]
    assert result["checks"]["passed"] is True, result["checks"]
    assert result["checks"]["failures"] == []
    meta = read_header(page.read_text(encoding="utf-8"))
    assert meta is not None
    assert meta["layout"] == shape
    assert meta["template"] == template
    assert not meta.get("layout_defaulted")


class _Regions(HTMLParser):
    """The region children of the `q-page` wrapper, in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.page_depth: int | None = None
        self.wrapper_layout: str | None = None
        self.regions: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if self.page_depth is None and "q-page" in classes:
            self.page_depth = self.depth
            self.wrapper_layout = attributes.get("data-layout")
        elif self.page_depth is not None and self.depth == self.page_depth + 1:
            if tag == "section" and "q-summary" in classes:
                self.regions.append("summary")
            elif tag == "nav" and "q-nav" in classes:
                self.regions.append("nav")
            elif tag == "main":
                self.regions.append("main")
            elif tag == "aside":
                self.regions.append("aside")
        if tag not in ("br", "img", "input", "meta", "link", "hr", "source", "col", "wbr"):
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.depth -= 1
        if self.page_depth is not None and self.depth == self.page_depth:
            self.page_depth = -1


def _regions(page: Path) -> tuple[str | None, list[str]]:
    parser = _Regions()
    parser.feed(page.read_text(encoding="utf-8"))
    return parser.wrapper_layout, parser.regions


@pytest.mark.parametrize(("template", "shape"), EXAMPLES, ids=IDS)
def test_dom_order_matches_the_shape_table(pages: dict, template: str, shape: str) -> None:
    layout, regions = _regions(_page(pages, template, shape))
    assert layout == shape
    assert regions == REGIONS[shape]


@pytest.mark.parametrize(("template", "shape"), EXAMPLES, ids=IDS)
def test_no_example_places_an_aside_region(pages: dict, template: str, shape: str) -> None:
    assert "aside" not in _regions(_page(pages, template, shape))[1]


@pytest.mark.parametrize("template", TEMPLATES)
def test_shape_examples_use_the_kit_elements_that_show_the_shape(pages: dict, template: str) -> None:
    html = {shape: _page(pages, template, shape).read_text(encoding="utf-8") for shape in LAYOUTS}
    assert html["dashboard"].count("<q-panel") >= 8 and "<q-grid" in html["dashboard"] and "<q-stat" in html["dashboard"]
    assert "<q-compare" in html["comparison"]
    assert "<q-sidenote" in html["longform"]
    assert html["explainer"].count("<h2") >= 5


@pytest.fixture(scope="module")
def browser_ready(pages: dict) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    page = _page(pages, "report", "explainer")
    proc = subprocess.run(
        [sys.executable, str(CLI), "verify", str(page), "--out-dir", str(page.with_suffix(".probe"))],
        capture_output=True,
        text=True,
        check=False,
    )
    if json.loads(proc.stdout)["status"] == "not-browser-verified":
        pytest.skip("no browser could be launched")


def at(page: Path, width: int, *evals: tuple[str, str], height: int = 900, steps: tuple = ()) -> dict:
    """Open ``page`` at ``width``, run ``steps``, then evaluate each ``(name, expression)``; returns the results."""
    out = run(page, *steps, *[ev(expr, name) for name, expr in evals], viewport={"width": width, "height": height})
    assert out["failedSteps"] == [] and out["consoleErrors"] == [] and out["pageErrors"] == []
    return out["results"]


def rect(selector: str) -> str:
    return (
        f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; const r = e.getBoundingClientRect();"
        " return {left: r.left, right: r.right, top: r.top + scrollY, bottom: r.bottom + scrollY, width: r.width, height: r.height}; })()"
    )


NO_SCROLL = "document.documentElement.scrollWidth <= window.innerWidth"
SUMMARY, NAV, MAIN = ".q-page > .q-summary", ".q-page > .q-nav", ".q-page > main"


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize(("template", "shape"), EXAMPLES, ids=IDS)
def test_example_passes_verify_at_375_and_1280(pages: dict, template: str, shape: str) -> None:
    page = _page(pages, template, shape)
    proc = subprocess.run([sys.executable, str(CLI), "verify", str(page)], capture_output=True, text=True, check=False)
    result = json.loads(proc.stdout)
    assert result["status"] == "passed", result
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert all(check["passed"] for check in result["checks"].values()), result["checks"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_dashboard_shows_four_panels_across_at_1600_and_five_or_more_at_2560(pages: dict, template: str) -> None:
    page = _page(pages, template, "dashboard")
    first_row = (
        "(() => { const panels = [...document.querySelectorAll('q-grid > q-panel')];"
        " const top = panels[0].getBoundingClientRect().top;"
        " return panels.filter((p) => Math.abs(p.getBoundingClientRect().top - top) < 2).length; })()"
    )
    capped = "getComputedStyle(document.querySelector('.q-wrap:has(> .q-page)')).maxWidth"
    wrap = rect(".q-wrap:has(> .q-page)")
    at1600 = at(page, 1600, ("across", first_row), ("max", capped), ("wrap", wrap), ("fits", NO_SCROLL))
    at2560 = at(page, 2560, ("across", first_row), ("max", capped), ("wrap", wrap), ("fits", NO_SCROLL))
    assert at1600["across"] == 4
    assert at2560["across"] >= 5
    assert at1600["max"] == "none" and at2560["max"] == "none"
    assert at1600["wrap"]["width"] == 1600 and at2560["wrap"]["width"] == 2560
    assert at1600["fits"] and at2560["fits"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("shape", NON_DASHBOARD)
def test_every_other_shape_keeps_its_content_within_1440_and_centered_at_2000(pages: dict, template: str, shape: str) -> None:
    wrap = at(_page(pages, template, shape), 2000, ("wrap", rect(".q-wrap:has(> .q-page)")), ("fits", NO_SCROLL))
    box = wrap["wrap"]
    assert box["width"] <= 1440
    assert abs(box["left"] - (2000 - box["right"])) <= 1
    assert wrap["fits"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_prose_and_the_lede_fill_their_column_in_every_shape(pages: dict, template: str) -> None:
    probe = (
        "(() => [document.querySelector('.q-page > main > p, .q-page > main section p'), document.querySelector('.q-summary > p')]"
        ".filter(Boolean).map((p) => { const box = p.parentElement; const s = getComputedStyle(box);"
        " const inner = box.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);"
        " return Math.abs(p.getBoundingClientRect().width - inner) <= 1; }))()"
    )
    for shape in LAYOUTS:
        fills = at(_page(pages, template, shape), 1600, ("fills", probe))["fills"]
        assert fills and all(fills), shape


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("shape", ["explainer", "longform", "reference"])
def test_nav_rail_is_visible_and_sticky_at_1280_and_a_collapsed_menu_at_375(pages: dict, template: str, shape: str) -> None:
    page = _page(pages, template, shape)
    state = (
        "(() => { const shown = (s) => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0; };"
        " const nav = document.querySelector('.q-nav'); const style = getComputedStyle(nav);"
        " return {rail: shown('.q-nav-rail'), menu: shown('.q-nav-menu'), position: style.position, overflowY: style.overflowY,"
        " maxHeight: parseFloat(style.maxHeight), open: document.querySelector('.q-nav-menu').open}; })()"
    )
    wide = at(page, 1280, ("state", state), ("nav", rect(NAV)), ("main", rect(MAIN)), ("summary", rect(SUMMARY)), height=800)
    assert wide["state"]["rail"] is True and wide["state"]["menu"] is False
    assert wide["state"]["position"] == "sticky"
    assert wide["state"]["overflowY"] in ("auto", "scroll")
    assert 0 < wide["state"]["maxHeight"] <= 800
    assert wide["nav"]["right"] <= wide["main"]["left"] + 1
    assert wide["nav"]["left"] < wide["main"]["left"]

    scrolled = at(
        page,
        1280,
        ("nav", "document.querySelector('.q-nav').getBoundingClientRect().top"),
        ("scrolled", "scrollY"),
        steps=({"eval": "window.scrollTo(0, 700)", "as": "scroll"}, {"wait": 100}),
        height=800,
    )
    assert scrolled["scrolled"] >= 600
    assert 0 <= scrolled["nav"] <= 40

    narrow = at(page, 375, ("state", state), ("nav", rect(NAV)), ("summary", rect(SUMMARY)), ("main", rect(MAIN)), ("fits", NO_SCROLL))
    assert narrow["state"]["menu"] is True and narrow["state"]["rail"] is False
    assert narrow["state"]["open"] is False
    assert narrow["state"]["position"] != "sticky"
    assert narrow["summary"]["bottom"] <= narrow["nav"]["top"] + 1 <= narrow["main"]["top"] + 1
    assert narrow["fits"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_the_reference_pane_starts_at_900_and_the_other_rails_at_1100(pages: dict, template: str) -> None:
    rail = "getComputedStyle(document.querySelector('.q-nav-rail')).display !== 'none'"
    assert at(_page(pages, template, "reference"), 900, ("rail", rail))["rail"] is True
    assert at(_page(pages, template, "reference"), 899, ("rail", rail))["rail"] is False
    assert at(_page(pages, template, "explainer"), 1100, ("rail", rail))["rail"] is True
    assert at(_page(pages, template, "explainer"), 1099, ("rail", rail))["rail"] is False


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_tool_result_sits_beside_the_inputs_at_1280_and_directly_below_at_375(pages: dict, template: str) -> None:
    page = _page(pages, template, "tool")
    wide = at(page, 1280, ("summary", rect(SUMMARY)), ("main", rect(MAIN)))
    assert wide["summary"]["left"] >= wide["main"]["right"]
    assert wide["summary"]["top"] < wide["main"]["bottom"]
    edge = at(page, 900, ("summary", rect(SUMMARY)), ("main", rect(MAIN)))
    assert edge["summary"]["left"] >= edge["main"]["right"]
    below = at(page, 899, ("summary", rect(SUMMARY)), ("main", rect(MAIN)))
    assert below["summary"]["top"] >= below["main"]["bottom"]
    narrow = at(page, 375, ("summary", rect(SUMMARY)), ("main", rect(MAIN)), ("fits", NO_SCROLL))
    assert narrow["summary"]["top"] >= narrow["main"]["bottom"]
    assert narrow["fits"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_reference_nav_is_the_left_pane_beside_main_from_900(pages: dict, template: str) -> None:
    page = _page(pages, template, "reference")
    wide = at(page, 1280, ("nav", rect(NAV)), ("main", rect(MAIN)), ("summary", rect(SUMMARY)))
    assert wide["nav"]["right"] <= wide["main"]["left"]
    assert wide["summary"]["left"] >= wide["nav"]["right"]
    narrow = at(page, 375, ("nav", rect(NAV)), ("main", rect(MAIN)), ("summary", rect(SUMMARY)))
    assert narrow["nav"]["top"] >= narrow["summary"]["bottom"] - 1
    assert narrow["main"]["top"] >= narrow["nav"]["bottom"] - 1
    pane = "(() => { const s = getComputedStyle(document.querySelector('.q-nav')); return [s.borderInlineEndWidth, s.paddingInlineEnd]; })()"
    assert at(page, 375, ("pane", pane))["pane"] == ["0px", "0px"]
    assert at(page, 900, ("pane", pane))["pane"] == ["1px", "16px"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_aria_current_moves_to_the_section_scrolled_into_view(pages: dict, template: str) -> None:
    page = _page(pages, template, "explainer")
    ids = at(page, 1280, ("ids", "[...document.querySelectorAll('.q-nav-rail > li > a')].map((a) => a.getAttribute('href').slice(1))"))["ids"]
    assert len(ids) >= 5
    for target in (ids[2], ids[1], ids[0]):
        in_target = (
            "(() => { const a = document.querySelector('.q-nav-rail [aria-current]'); if (!a) return false;"
            " const heading = document.getElementById(a.getAttribute('href').slice(1));"
            f" return heading.closest('section') === document.getElementById({json.dumps(target)}).closest('section'); }})()"
        )
        current = (
            "(() => { const marked = [...document.querySelectorAll('.q-nav [aria-current]')];"
            f" return {{count: marked.length, values: marked.map((a) => a.getAttribute('aria-current')), inRail: marked.every((a) => a.closest('.q-nav-rail')), inTarget: {in_target}}}; }})()"
        )
        scroll = f"(() => {{ document.getElementById({json.dumps(target)}).scrollIntoView({{block: 'start'}}); return true; }})()"
        results = at(
            page,
            1280,
            ("now", current),
            steps=({"eval": scroll, "as": "scroll"}, {"waitFor": in_target, "timeout": 3000}),
            height=600,
        )["now"]
        assert results == {"count": 1, "values": ["location"], "inRail": True, "inTarget": True}


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_the_last_nav_link_is_current_at_the_bottom_and_the_highlight_follows_back_up(pages: dict, template: str) -> None:
    page = _page(pages, template, "explainer")
    marked = (
        "(() => { const links = [...document.querySelectorAll('.q-nav-rail a')]; const on = links.filter((a) => a.hasAttribute('aria-current'));"
        " return {count: on.length, index: links.indexOf(on[0]), last: links.length - 1}; })()"
    )
    last_is_current = "(() => { const links = [...document.querySelectorAll('.q-nav-rail a')]; return links[links.length - 1].hasAttribute('aria-current'); })()"
    to_bottom = (
        {"eval": "window.scrollTo(0, document.documentElement.scrollHeight)", "as": "down"},
        {"waitFor": last_is_current, "timeout": 3000},
    )
    at_bottom = at(page, 1280, ("marked", marked), ("bottom", "scrollY + innerHeight >= document.documentElement.scrollHeight - 2"), steps=to_bottom)
    assert at_bottom["bottom"] is True
    assert at_bottom["marked"]["count"] == 1
    assert at_bottom["marked"]["index"] == at_bottom["marked"]["last"]

    back_up = at(
        page,
        1280,
        ("marked", marked),
        steps=(
            *to_bottom,
            {"eval": "document.getElementById(document.querySelectorAll('.q-nav-rail a')[1].getAttribute('href').slice(1)).scrollIntoView({block: 'start'})", "as": "up"},
            {"waitFor": f"!{last_is_current}", "timeout": 3000},
        ),
    )["marked"]
    assert back_up["count"] == 1
    assert back_up["index"] < back_up["last"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_the_current_nav_link_is_marked_by_weight_and_an_indicator_not_color_alone(pages: dict, template: str) -> None:
    page = _page(pages, template, "explainer")
    results = at(
        page,
        1280,
        (
            "style",
            "(() => { const a = document.querySelector('.q-nav-rail [aria-current]'); const base = [...document.querySelectorAll('.q-nav-rail a:not([aria-current])')][0];"
            " const s = getComputedStyle(a); const b = getComputedStyle(base);"
            " const mark = getComputedStyle(a, '::before'); const markBase = getComputedStyle(base, '::before');"
            " return {weight: Number(s.fontWeight), baseWeight: Number(b.fontWeight),"
            " indicator: [s.borderLeftWidth, s.boxShadow, mark.content, mark.width].join('|'),"
            " baseIndicator: [b.borderLeftWidth, b.boxShadow, markBase.content, markBase.width].join('|')}; })()",
        ),
        steps=({"eval": "document.querySelectorAll('.q-nav-rail a')[1].scrollIntoView(); true", "as": "go"}, {"waitFor": "!!document.querySelector('.q-nav-rail [aria-current]')", "timeout": 3000}),
        height=800,
    )["style"]
    assert results["weight"] > results["baseWeight"]
    assert results["indicator"] != results["baseIndicator"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_a_page_without_a_nav_has_no_aria_current(pages: dict, template: str) -> None:
    results = at(_page(pages, template, "dashboard"), 1280, ("marked", "document.querySelectorAll('[aria-current]').length"))
    assert results["marked"] == 0


NOTES = """(() => {
  const notes = [...document.querySelectorAll('.q-page q-sidenote')];
  const shown = (e) => getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  return {count: notes.length, ready: notes.every((n) => n.hasAttribute('data-q-ready')),
          closed: notes.every((n) => !shown(n.querySelector('[slot="note"]')))};
})()"""

OPEN_EACH = """(() => {
  const out = [];
  for (const words of document.querySelectorAll('.q-page q-sidenote')) {
    words.click();
    const box = words.querySelector('[slot="note"]').getBoundingClientRect();
    out.push(box.width > 0 && box.left >= 0 && box.right <= innerWidth);
    words.click();
  }
  return {inside: out, fits: document.documentElement.scrollWidth <= innerWidth};
})()"""


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("width", [375, 1280, 1920])
def test_longform_notes_are_highlighted_phrases_whose_notes_open_inside_the_page(pages: dict, template: str, width: int) -> None:
    out = at(_page(pages, template, "longform"), width, ("notes", NOTES), ("open", OPEN_EACH), ("fits", NO_SCROLL))
    assert out["notes"]["count"] >= 2 and out["notes"]["ready"] and out["notes"]["closed"]
    assert out["open"]["inside"] and all(out["open"]["inside"]), out["open"]
    assert out["open"]["fits"] and out["fits"]


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("template", TEMPLATES)
def test_print_is_one_column_in_dom_order_with_the_nav_as_a_plain_list(pages: dict, template: str) -> None:
    probe = (
        "(() => { const columns = (s) => getComputedStyle(document.querySelector(s)).gridTemplateColumns.split(' ').length;"
        " const shown = (s) => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none'; };"
        " return {page: columns('.q-page'), rail: shown('.q-nav-rail'), menu: shown('.q-nav-menu'), chrome: shown('.q-chrome'),"
        " sticky: [...document.querySelectorAll('.q-page > *')].some((e) => getComputedStyle(e).position === 'sticky')}; })()"
    )
    for shape, expect_nav in (("explainer", True), ("tool", False), ("reference", True)):
        out = run(
            _page(pages, template, shape),
            {"emulate": {"media": "print"}},
            ev(probe, "print"),
            ev(f"[...document.querySelectorAll('.q-page > *')].map((e) => e.getBoundingClientRect().top + scrollY)", "tops"),
            viewport={"width": 1280, "height": 900},
        )
        result = out["results"]["print"]
        assert result["page"] == 1, shape
        assert result["chrome"] is False, shape
        assert result["sticky"] is False, shape
        assert (result["rail"], result["menu"]) == ((True, False) if expect_nav else (False, False)), shape
        tops = out["results"]["tops"]
        assert tops == sorted(tops), shape


def test_create_py_skeleton_is_region_bearing() -> None:
    assert "{{regions}}" in create.SKELETON
    assert "{{slot:main}}" not in create.SKELETON


@pytest.fixture(scope="module")
def custom_env(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("created-template")
    user = root / "user"
    user.mkdir()
    project = root / "project"
    project.mkdir()
    page = root / "board.html"
    page.write_text(
        "<!doctype html><html><head><title>Status board</title></head><body>"
        "<h2>Services</h2><p>Three services are healthy.</p></body></html>",
        encoding="utf-8",
    )
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}
    code, out = run_cli("templates", "new", "board", "--from", page, "--level", "project", "--project-dir", project, env=env)
    assert code == 0, out
    seal(project / ".quirk" / "html-templates" / "board")
    return {"env": env, "project": project, "root": root}


@pytest.mark.parametrize("shape", LAYOUTS)
def test_a_template_created_from_plain_html_builds_every_shape(custom_env: dict, shape: str) -> None:
    root = custom_env["root"]
    src = root / f"{shape}.src.html"
    headings = "".join(f"<h2>Section {n}</h2>\n<p>Body of section {n}.</p>\n" for n in range(1, 7))
    meta = {"template": "board", "title": f"Board {shape}", "mode": "offline", "layout": shape}
    src.write_text(
        f"<!-- quirk-src {json.dumps(meta)} -->\n<!-- slot: summary -->\n<p>Summary of the board.</p>\n<!-- slot: main -->\n{headings}",
        encoding="utf-8",
    )
    page = root / f"{shape}.html"
    code, result = run_cli("build", src, "--out", page, "--project-dir", custom_env["project"], env=custom_env["env"])
    assert code == 0, result
    assert result["checks"]["passed"] is True, result["checks"]
    layout, regions = _regions(page)
    assert layout == shape
    assert "summary" in regions and "main" in regions


def test_the_skeletons_keep_no_page_geometry() -> None:
    for name in ("report", "components"):
        skeleton = (SKILL / "templates" / name / "skeleton.html").read_text(encoding="utf-8")
        assert "{{regions}}" in skeleton and "{{slot:main}}" not in skeleton
        style = re.search(r"<style>(.*?)</style>", skeleton, re.S).group(1)
        assert "max-width: 1440px" not in style
        assert "grid-template-columns" not in style and "q-layout" not in style


COMPANION_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>:root {{ --q-space-4: 16px; --q-space-6: 32px; }}</style>
<style>
{layout_css}
</style>
<style>
body {{ display: block; margin: 0; }}
.q-wrap {{ box-sizing: border-box; max-width: 960px; margin-inline: auto; padding-inline: clamp(var(--q-space-4), 4vw, var(--q-space-6)); }}
</style></head>
<body><header><div class="q-wrap" data-layout="{layout}"><h1>Pick one</h1></div></header>
<main class="q-wrap" id="main" data-layout="{layout}"><h2>Which layout?</h2><p>Choose.</p></main></body></html>
"""


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize(
    ("layout", "expected"),
    [("explainer", 1440), ("longform", 1440), ("tool", 1440), ("comparison", 1440), ("reference", 1440), ("dashboard", None), ("", 960)],
)
@pytest.mark.parametrize("viewport", [1600, 2000])
def test_companion_screens_widen_only_when_they_name_a_layout(tmp_path: Path, layout: str, expected: int | None, viewport: int) -> None:
    page = tmp_path / "screen.html"
    css = (SKILL / "theme" / "layout.css").read_text(encoding="utf-8")
    page.write_text(COMPANION_PAGE.format(layout_css=css, layout=layout), encoding="utf-8")
    boxes = at(page, viewport, ("main", rect("main.q-wrap")), ("header", rect("header .q-wrap")))
    main, header = boxes["main"], boxes["header"]
    assert main["width"] == (viewport if expected is None else expected)
    assert (header["left"], header["right"]) == (main["left"], main["right"])
    narrow = at(page, 800, ("main", rect("main.q-wrap")), ("header", rect("header .q-wrap")))
    assert narrow["main"]["width"] == 800 and narrow["header"]["width"] == 800


@pytest.mark.usefixtures("browser_ready")
def test_a_page_without_q_page_keeps_uncapped_paragraphs(tmp_path: Path) -> None:
    page = tmp_path / "screen.html"
    css = (SKILL / "theme" / "layout.css").read_text(encoding="utf-8")
    page.write_text(COMPANION_PAGE.format(layout_css=css, layout=""), encoding="utf-8")
    probe = (
        "(() => { const p = document.querySelector('main p'); const probe = document.createElement('div');"
        " probe.style.cssText = 'position:absolute;visibility:hidden;width:70ch'; p.appendChild(probe);"
        " const cap = probe.getBoundingClientRect().width; probe.remove();"
        " return {width: p.getBoundingClientRect().width, cap}; })()"
    )
    sizes = at(page, 1600, ("sizes", probe))["sizes"]
    assert sizes["width"] > sizes["cap"] + 1


def _build_src(work: Path, name: str, layout: str, summary: str, main: str) -> Path:
    project = work / "project"
    project.mkdir(exist_ok=True)
    user = work / "user"
    user.mkdir(exist_ok=True)
    meta = {"template": "report", "title": f"Probe {name}", "mode": "offline", "layout": layout}
    parts = [f"<!-- quirk-src {json.dumps(meta)} -->", "<!-- slot: summary -->", summary, "<!-- slot: main -->", main]
    src = work / f"{name}.src.html"
    src.write_text("\n".join(parts) + "\n", encoding="utf-8")
    page = work / f"{name}.html"
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}
    code, result = run_cli("build", src, "--out", page, "--project-dir", project, env=env)
    assert code == 0, result
    return page


def _compare_html(options: int) -> str:
    names = [f"Option {i}" for i in range(1, options + 1)]
    head = "<th>Criterion</th>" + "".join(f"<th>{n}</th>" for n in names)
    rows = "".join(
        f"<tr><th>{c}</th>" + "".join(f"<td>{c} measured for {n}</td>" for n in names) + "</tr>"
        for c in ("Monthly cost", "Setup time", "On-call load")
    )
    return f'<q-compare recommended="2"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></q-compare>'


def _sections(count: int) -> str:
    return "".join(f"<h2>Section {n}</h2>\n<p>Body of section {n}.</p>\n" for n in range(1, count + 1))


@pytest.fixture(scope="module")
def compare_pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    work = tmp_path_factory.mktemp("compare-pages")
    summary = "<p>Summary of the comparison.</p>"
    return {
        "nav5": _build_src(work, "nav5", "comparison", summary, _sections(5) + _compare_html(5)),
        "nav8": _build_src(work, "nav8", "comparison", summary, _sections(5) + _compare_html(8)),
        "plain12": _build_src(work, "plain12", "comparison", summary, _sections(3) + _compare_html(12)),
    }


COMPARE_BOXES = """(() => {
  const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return {left: b.left, right: b.right, width: b.width}; };
  const host = document.querySelector('q-compare');
  return {cmp: r('q-compare'), nav: r('.q-page > .q-nav'), main: r('.q-page > main'),
          fits: document.documentElement.scrollWidth <= window.innerWidth, scrolls: host.scrollWidth > host.clientWidth + 1};
})()"""


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("page", ["nav5", "nav8"])
@pytest.mark.parametrize("width", [1100, 1280, 1440])
def test_a_wide_compare_beside_the_nav_rail_never_overflows_the_page_or_covers_the_rail(compare_pages: dict, page: str, width: int) -> None:
    out = at(compare_pages[page], width, ("boxes", COMPARE_BOXES))["boxes"]
    assert out["nav"] is not None and out["fits"] is True
    assert out["cmp"]["left"] >= out["nav"]["right"] - 0.5
    assert out["cmp"]["left"] >= 0 and out["cmp"]["right"] <= width + 0.5


@pytest.mark.usefixtures("browser_ready")
def test_a_compare_wider_than_a_centred_column_still_widens_past_it(compare_pages: dict) -> None:
    out = at(compare_pages["plain12"], 2000, ("boxes", COMPARE_BOXES))["boxes"]
    assert out["nav"] is None and out["fits"] is True
    assert out["cmp"]["width"] > out["main"]["width"] + 1
    assert (out["cmp"]["left"] + out["cmp"]["right"]) / 2 == pytest.approx(1000, abs=2)


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("width", [375, 1280])
def test_a_longform_sidenote_in_the_summary_opens_inside_the_page(tmp_path: Path, width: int) -> None:
    summary = '<p>The build got <q-sidenote>faster<span slot="note">Measured on main, excluding reruns.</span></q-sidenote> this quarter.</p>'
    page = _build_src(tmp_path, "lf", "longform", summary, _sections(5))
    out = at(page, width, ("open", OPEN_EACH))["open"]
    assert out["inside"] == [True] and out["fits"] is True
