"""Seams between the page-shape parts: templates, skeletons, CLI, companion and the layout check.

Each part has its own unit and browser tests; these run the real templates, skeletons, CLI and
companion server together with nothing stubbed. Fixtures and helpers come from the per-part test
modules. Browser tests skip when node or a browser is missing; the tier-2 tests also need pnpm and
QUIRK_HTML_NETWORK_TESTS=1.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from tests.test_html_app import APP, build_app, source_dir
from tests.test_html_builder import run_cli, seal
from tests.test_html_companion import EXAMPLE as COMPANION_PLAIN
from tests.test_html_companion import server, session  # noqa: F401  (fixtures)
from tests.test_html_layout_shapes import (  # noqa: F401  (fixtures and helpers)
    CLI,
    SKILL,
    REGIONS,
    TEMPLATES,
    MAIN,
    NAV,
    SUMMARY,
    _example,
    _regions,
    at,
    browser_ready,
    pages,
    rect,
)

from htmlkit.header import read_header  # noqa: E402
from htmlkit.layouts import LAYOUTS  # noqa: E402

COMPANION_EXAMPLES = SKILL / "templates" / "companion" / "examples"
NETWORK = pytest.mark.skipif(
    shutil.which("pnpm") is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)

# the page wrapper's children, classified the way `_Regions` classifies them for tier 1
PAGE_REGIONS = (
    "(() => { const page = document.querySelector('.q-page');"
    " return {layout: page.getAttribute('data-layout'), regions: [...page.children].map((e) => {"
    " if (e.matches('section.q-summary')) return 'summary'; if (e.matches('nav.q-nav')) return 'nav';"
    " if (e.matches('main')) return 'main'; if (e.matches('aside')) return 'aside'; return null; }).filter(Boolean)}; })()"
)


@pytest.fixture
def home(tmp_path: Path) -> tuple[Path, dict]:
    """A project directory and an env whose user template dir is empty."""
    project = tmp_path / "project"
    project.mkdir()
    user = tmp_path / "user"
    user.mkdir()
    return project, {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}


# --- 1. companion widening through the real server and skeleton -------------------------------

MAIN_WRAP = "main.q-wrap"


def _show_example(server, path: Path) -> Path:
    out = server.show(json.loads(path.read_text(encoding="utf-8")))
    assert out["checks"]["passed"] is True, out
    return server.session / "screens" / f"{out['screen']}.html"


@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("shape", [s for s in LAYOUTS if s != "dashboard"])
def test_a_companion_screen_with_a_shape_is_wider_than_960_and_capped_at_1440(server, shape: str) -> None:
    page = _show_example(server, COMPANION_EXAMPLES / f"{shape}.screen.json")
    wide = at(page, 1600, ("wrap", rect(MAIN_WRAP)), ("masthead", rect("header.q-masthead > .q-wrap")), ("fits", "document.documentElement.scrollWidth <= innerWidth"))
    assert 960 < wide["wrap"]["width"] <= 1440, wide
    assert wide["masthead"]["width"] == wide["wrap"]["width"]
    assert wide["fits"]
    huge = at(page, 2000, ("wrap", rect(MAIN_WRAP)))
    assert huge["wrap"]["width"] == 1440


@pytest.mark.usefixtures("browser_ready")
def test_a_companion_dashboard_has_no_cap(server) -> None:
    page = _show_example(server, COMPANION_EXAMPLES / "dashboard.screen.json")
    assert at(page, 1600, ("wrap", rect(MAIN_WRAP)))["wrap"]["width"] > 960
    wide = at(page, 2000, ("wrap", rect(MAIN_WRAP)), ("masthead", rect("header.q-masthead > .q-wrap")))
    assert wide["wrap"]["width"] > 1440
    assert wide["masthead"]["width"] == wide["wrap"]["width"]


@pytest.mark.usefixtures("browser_ready")
def test_a_companion_screen_with_no_layout_stays_at_960(server) -> None:
    page = _show_example(server, COMPANION_PLAIN)
    assert 'data-layout=""' in page.read_text(encoding="utf-8")
    for width in (1600, 2000):
        assert at(page, width, ("wrap", rect(MAIN_WRAP)))["wrap"]["width"] == 960


# --- 2. tier-1 parity across templates ---------------------------------------------------------


@pytest.mark.parametrize("shape", LAYOUTS)
def test_the_report_and_components_examples_agree_on_layout_region_order_and_nav(pages: dict, shape: str) -> None:
    report_layout, report_regions = _regions(pages[("report", shape)][0])
    components_layout, components_regions = _regions(pages[("components", shape)][0])
    assert report_layout == components_layout == shape
    assert report_regions == components_regions == REGIONS[shape]


def _source_for(template: str, shape: str, as_template: str, dest: Path) -> Path:
    """The ``shape`` example of ``template`` re-pointed at ``as_template`` and written to ``dest``."""
    lines = _example(template, shape).read_text(encoding="utf-8").split("\n")
    meta = json.loads(re.fullmatch(r"<!-- quirk-src (.*) -->", lines[0]).group(1))
    meta["template"] = as_template
    lines[0] = f"<!-- quirk-src {json.dumps(meta)} -->"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


@pytest.mark.parametrize("base", TEMPLATES)
def test_a_freshly_created_template_builds_every_shape_with_the_same_region_order(
    pages: dict, home: tuple[Path, dict], tmp_path: Path, base: str
) -> None:
    project, env = home
    code, created = run_cli("templates", "new", "mine", "--level", "project", "--base", base, "--project-dir", project, env=env)
    assert code == 0, created
    seal(Path(created["path"]))
    for shape in LAYOUTS:
        src = _source_for(base, shape, "mine", tmp_path / f"{shape}.src.html")
        out = tmp_path / f"{shape}.html"
        code, result = run_cli("build", src, "--out", out, "--project-dir", project, env=env)
        assert code == 0 and result["checks"]["passed"] is True, (shape, result)
        assert read_header(out.read_text(encoding="utf-8"))["layout"] == shape
        layout, regions = _regions(out)
        assert layout == shape
        assert regions == _regions(pages[(base, shape)][0])[1] == REGIONS[shape], shape


# --- 3. rebuild stability through the CLI ------------------------------------------------------


def _without_key(src: Path, key: str) -> None:
    lines = src.read_text(encoding="utf-8").split("\n")
    meta = json.loads(re.fullmatch(r"<!-- quirk-src (.*) -->", lines[0]).group(1))
    assert key in meta
    del meta[key]
    lines[0] = f"<!-- quirk-src {json.dumps(meta)} -->"
    src.write_text("\n".join(lines), encoding="utf-8")


@pytest.mark.parametrize("shape", LAYOUTS)
def test_a_rebuild_after_deleting_layout_from_the_source_keeps_the_shape_and_nav(
    home: tuple[Path, dict], tmp_path: Path, shape: str
) -> None:
    project, env = home
    src = _source_for("report", shape, "report", tmp_path / "p.src.html")
    out = tmp_path / "p.html"
    code, first = run_cli("build", src, "--out", out, "--project-dir", project, env=env)
    assert code == 0 and first["layout"] == shape and first["layout_defaulted"] is False, first
    before = _regions(out)

    _without_key(src, "layout")
    code, again = run_cli("build", src, "--out", out, "--project-dir", project, env=env)
    assert code == 0 and again["checks"]["passed"] is True, again
    assert again["layout"] == shape and again["layout_defaulted"] is False
    meta = read_header(out.read_text(encoding="utf-8"))
    assert meta["layout"] == shape and "layout_defaulted" not in meta
    assert _regions(out) == before == (shape, REGIONS[shape])
    _, note = run_cli("note", out, "--project-dir", project, env=env)
    assert "no layout named" not in note["markdown"]


def test_a_page_built_with_no_layout_says_so_in_the_note_on_the_first_build_and_on_a_rebuild(
    home: tuple[Path, dict], tmp_path: Path
) -> None:
    project, env = home
    src = _source_for("report", "explainer", "report", tmp_path / "p.src.html")
    _without_key(src, "layout")
    out = tmp_path / "p.html"
    for attempt in ("first build", "rebuild"):
        code, result = run_cli("build", src, "--out", out, "--project-dir", project, env=env)
        assert code == 0, (attempt, result)
        assert result["layout"] == "explainer" and result["layout_defaulted"] is True, attempt
        assert _regions(out) == ("explainer", REGIONS["explainer"]), attempt
        _, note = run_cli("note", out, "--project-dir", project, env=env)
        assert "- Layout: explainer (no layout named)" in note["markdown"].splitlines(), attempt


# --- 5. the layout check across tiers ----------------------------------------------------------

HAND_GRID = ".cards { display: grid; grid-template-columns: 1fr 1fr; }"


def test_a_hand_written_grid_in_a_slot_style_fails_the_tier_1_build_and_names_q_grid(
    home: tuple[Path, dict], tmp_path: Path
) -> None:
    project, env = home
    src = _source_for("report", "explainer", "report", tmp_path / "p.src.html")
    src.write_text(src.read_text(encoding="utf-8") + f"\n<style>{HAND_GRID}</style>\n", encoding="utf-8")
    code, result = run_cli("build", src, "--out", tmp_path / "p.html", "--project-dir", project, env=env)
    assert code == 1 and result["checks"]["passed"] is False
    layout = [f for f in result["checks"]["failures"] if f["check"] == "layout"]
    assert layout and all("q-grid" in f["detail"] for f in layout)
    assert any("grid-template-columns" in f["detail"] for f in layout)


# --- 4 and 5. tier 2 (real pnpm build) ---------------------------------------------------------

TIER_2_SHAPES = ("explainer", "reference", "tool")


def _scaffold_app(project: Path, slug: str, shape: str) -> Path:
    src = source_dir(project, slug)
    ignore = shutil.ignore_patterns("node_modules", "dist", ".DS_Store")
    shutil.copytree(APP / "project", src, ignore=ignore)
    shutil.copytree(APP / "examples" / shape, src, ignore=ignore, dirs_exist_ok=True)
    return src


@pytest.fixture(scope="module")
def app_pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The tier-2 example of each compared shape, built once through the CLI with pnpm."""
    work = tmp_path_factory.mktemp("tier-2-examples")
    project = work / "project"
    project.mkdir()
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(work / "user")}
    built: dict[str, Path] = {}
    for shape in TIER_2_SHAPES:
        _scaffold_app(project, shape, shape)
        code, result = build_app(project, env, shape, "--title", f"{shape} example")
        assert code == 0 and result["checks"]["passed"] is True, (shape, result)
        built[shape] = Path(result["path"])
    return built


def _app_view(page: Path, width: int = 1280, *evals: tuple[str, str]) -> dict:
    # the app mounts its regions after load and builds the nav from the rendered main
    steps = ({"waitFor": "document.querySelector('.q-page > main')", "timeout": 10000}, {"wait": 300})
    return at(page, width, ("page", PAGE_REGIONS), *evals, steps=steps)


@NETWORK
@pytest.mark.usefixtures("browser_ready")
@pytest.mark.parametrize("shape", TIER_2_SHAPES)
def test_the_app_page_has_the_region_order_and_layout_of_the_tier_1_example(pages: dict, app_pages: dict, shape: str) -> None:
    app = _app_view(app_pages[shape])["page"]
    tier_1 = at(pages[("report", shape)][0], 1280, ("page", PAGE_REGIONS))["page"]
    assert app["layout"] == tier_1["layout"] == shape
    assert app["regions"] == tier_1["regions"]


@NETWORK
@pytest.mark.usefixtures("browser_ready")
def test_at_1280_the_app_reference_nav_pane_and_the_tool_summary_sit_beside_main(app_pages: dict) -> None:
    reference = _app_view(app_pages["reference"], 1280, ("nav", rect(NAV)), ("main", rect(MAIN)))
    assert reference["nav"]["right"] <= reference["main"]["left"]
    tool = _app_view(app_pages["tool"], 1280, ("summary", rect(SUMMARY)), ("main", rect(MAIN)))
    assert tool["summary"]["left"] >= tool["main"]["right"]


@NETWORK
def test_a_hand_written_grid_in_an_app_css_source_fails_the_tier_2_build_and_names_q_grid(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    src = _scaffold_app(project, "cards", "explainer")
    (src / "src" / "views" / "cards.css").write_text(HAND_GRID + "\n", encoding="utf-8")
    code, result = build_app(project, env, "cards", "--title", "cards example")
    assert code == 1 and result["checks"]["passed"] is False, result
    layout = [f for f in result["checks"]["failures"] if f["check"] == "layout"]
    assert layout and all("q-grid" in f["detail"] for f in layout)
    assert any("src/views/cards.css line 1" in f["detail"] and "grid-template-columns" in f["detail"] for f in layout)
