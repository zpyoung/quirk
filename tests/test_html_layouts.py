"""Tests for page shapes in the tier-1 build: the registry, the generated nav, region placement,
the summary rule, the layout record in the header, and the manifest rules for ``{{regions}}``.

Builds run against the skill's real vendor store and built-in templates; custom templates live
under tmp_path. No test needs a browser or the network.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import assemble, header, layouts, manifest, tokens  # noqa: E402

CLI = SKILL / "scripts" / "quirk_html.py"
SEVEN = ("report", "explainer", "longform", "tool", "comparison", "dashboard", "reference")

# a custom skeleton as `templates new` wrote it before shapes existed: {{slot:main}}, no {{regions}}
LEGACY_SKELETON = (
    "<!doctype html>\n{{header}}\n<html lang=\"en\"><head><title>{{title}}</title>{{head}}</head>\n"
    '<body data-layout-name="{{layout}}">{{chrome}}<main id="main">{{slot:main}}</main>{{data}}{{body_end}}</body></html>\n'
)
REGIONS_SKELETON = (
    "<!doctype html>\n{{header}}\n<html lang=\"en\"><head><title>{{title}}</title>{{head}}</head>\n"
    "<body>{{chrome}}{{regions}}{{data}}{{body_end}}</body></html>\n"
)
DESCRIPTION = "Use when you need a fixture template for the layout tests."
SUMMARY_HINT = {
    "report": "the answer or findings under the h1",
    "explainer": "the answer or findings under the h1",
    "longform": "the answer or findings under the h1",
    "comparison": "the recommendation line above the table",
    "tool": "the live result beside the inputs",
    "dashboard": "the headline metric, top-left",
    "reference": "a one-line purpose under the h1",
}


@pytest.fixture
def env(tmp_path: Path) -> dict:
    user = tmp_path / "user-templates"
    user.mkdir()
    return {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


def run_cli(*args: object, env: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, env=env, timeout=120
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    return proc.returncode, json.loads(out)


def build(src: Path, out: Path, env: dict, project: Path) -> tuple[int, dict]:
    return run_cli("build", src, "--out", out, "--project-dir", project, env=env)


def src_file(path: Path, meta: dict, slots: dict[str, str]) -> Path:
    parts = [f"<!-- quirk-src {json.dumps(meta)} -->"]
    for name, body in slots.items():
        parts += [f"<!-- slot: {name} -->", body]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def report_src(tmp_path: Path, meta: dict | None = None, slots: dict[str, str] | None = None, name: str = "p") -> Path:
    base = {"template": "report", "title": "T"}
    body = slots if slots is not None else {"summary": "<p>The answer.</p>", "main": "<p>Body.</p>"}
    return src_file(tmp_path / f"{name}.src.html", {**base, **(meta or {})}, body)


def page_header(out: Path) -> dict:
    meta = header.read_header(out.read_text(encoding="utf-8"))
    assert meta is not None
    return meta


def h2s(count: int) -> str:
    return "\n".join(f"<h2>Part {i}</h2>\n<p>text</p>" for i in range(1, count + 1))


def custom_template(project: Path, skeleton: str, name: str = "fx", slots: dict | None = None) -> Path:
    tdir = project / ".quirk" / "html-templates" / name
    tdir.mkdir(parents=True)
    meta = {
        "schema": 1,
        "name": name,
        "description": DESCRIPTION,
        "tier": 1,
        "libraries": [],
        "slots": slots or {"main": {"required": True, "description": "Main content."}},
        "skeleton": "skeleton.html",
        "example": "example.src.html",
    }
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    (tdir / "skeleton.html").write_text(skeleton, encoding="utf-8")
    src_file(tdir / "example.src.html", {"template": name, "title": "Fixture"}, {"summary": "<p>s</p>", "main": "<p>Hello.</p>"})
    stamp = {"schema": 1, "verified_at": "2026-10-15T00:00:00Z", "browser": False, "hashes": manifest.compute_hashes(tdir)}
    (tdir / "verified.json").write_text(json.dumps(stamp), encoding="utf-8")
    return tdir


# --- validate_layout -------------------------------------------------------------------------


def test_layouts_are_the_seven_shapes_in_documented_order() -> None:
    assert layouts.LAYOUTS == SEVEN
    assert layouts.DEFAULT_LAYOUT == "report"
    assert layouts.NAV_MODES == ("auto", "on", "off")


@pytest.mark.parametrize("name", SEVEN)
def test_validate_layout_returns_a_valid_name(name: str) -> None:
    assert layouts.validate_layout(name) == name


@pytest.mark.parametrize("bad", ["Report", "slides", "", None, 3, ["report"]])
def test_validate_layout_rejects_anything_else_and_lists_all_seven(bad: object) -> None:
    with pytest.raises(assemble.SourceError) as info:
        layouts.validate_layout(bad)
    assert ", ".join(SEVEN) in str(info.value)


def test_validate_layout_names_the_origin_it_is_given() -> None:
    with pytest.raises(assemble.SourceError) as info:
        layouts.validate_layout("slides", origin="--layout flag")
    message = str(info.value)
    assert message.startswith("--layout flag must be one of") and "header field" not in message


# --- build_nav -------------------------------------------------------------------------------


def nav_of(main: str, layout: str = "explainer", nav: str = "auto", reserved: set[str] | None = None):
    return layouts.build_nav(main, layout=layout, nav=nav, reserved_ids=reserved or {"main", "quirk-data"})


def test_nav_needs_five_h2s_on_auto() -> None:
    four = h2s(4)
    assert nav_of(four) == (None, four)
    built, _ = nav_of(h2s(5))
    assert built is not None and built.count('href="#part-') == 10


def test_nav_on_forces_it_and_off_suppresses_it() -> None:
    assert nav_of(h2s(1), nav="on")[0] is not None
    six = h2s(6)
    assert nav_of(six, nav="off") == (None, six)


def test_reference_always_has_a_nav_and_cannot_turn_it_off() -> None:
    built, _ = nav_of(h2s(1), layout="reference")
    assert built is not None and 'aria-label="Sections"' in built and "<summary>Sections</summary>" in built
    with pytest.raises(assemble.SourceError, match="reference always has its section nav"):
        nav_of(h2s(6), layout="reference", nav="off")


def test_reference_with_nav_auto_and_no_headings_is_an_error() -> None:
    with pytest.raises(assemble.SourceError, match="reference page needs h2 sections"):
        nav_of("<p>just prose</p>", layout="reference")


def test_reference_with_nav_auto_and_only_h3s_keeps_a_populated_nav() -> None:
    built, _ = nav_of("<h3>Sub one</h3><p>x</p><h3>Sub two</h3>", layout="reference")
    assert built is not None and built.count('href="#sub-') == 4


def test_nav_on_without_an_h2_is_an_error() -> None:
    with pytest.raises(assemble.SourceError, match="nav needs at least one h2 in main"):
        nav_of("<h3>Only a sub heading</h3>", nav="on")


def test_nav_markup_has_a_menu_copy_and_a_rail_copy_of_the_same_list() -> None:
    main = "<h2>First</h2><h3>One A</h3><h3>One B</h3><h2>Second</h2>"
    built, page = nav_of(main, nav="on")
    assert built is not None
    assert built.startswith('<nav class="q-nav" aria-label="On this page">')
    assert '<details class="q-nav-menu"><summary>On this page</summary><ol>' in built
    assert '<ol class="q-nav-rail">' in built
    nested = '<li><a href="#first">First</a><ol><li><a href="#one-a">One A</a></li><li><a href="#one-b">One B</a></li></ol></li>'
    assert built.count(nested) == 2
    assert built.count('<li><a href="#second">Second</a></li>') == 2
    assert page == '<h2 id="first">First</h2><h3 id="one-a">One A</h3><h3 id="one-b">One B</h3><h2 id="second">Second</h2>'


def test_nav_ids_slugify_collide_and_keep_existing_ids() -> None:
    main = (
        "<h2>Hello, World!</h2>\n<h2>Hello World</h2>\n<h2>!!!</h2>\n<h2>Main</h2>\n"
        '<h2 class="x" id="mine">Kept</h2>\n<h3>Quirk Data</h3>\n<h2>Hello world</h2>\n<h2>Edge</h2>'
    )
    _, page = nav_of(main, reserved={"main", "quirk-data"})
    ids = re.findall(r'<h[23][^>]* id="([^"]+)"', page)
    assert ids == ["hello-world", "hello-world-2", "section", "main-2", "mine", "quirk-data-2", "hello-world-3", "edge"]
    assert '<h2 class="x" id="mine">Kept</h2>' in page


def test_generated_ids_avoid_ids_already_in_the_page() -> None:
    main = '<h2>Setup</h2><p id="setup">x</p><h2 id="setup-2">Later</h2>'
    _, page = nav_of(main, nav="on")
    assert '<h2 id="setup-3">Setup</h2>' in page


@pytest.mark.parametrize("tag", ["q-panel", "q-compare", "q-tabs", "q-board"])
def test_headings_inside_layout_and_kit_containers_are_neither_counted_nor_listed(tag: str) -> None:
    main = f'<h2>Real</h2>\n<{tag} title="T"><h2>Inside</h2><h3>Deeper</h3></{tag}>\n<h3>After</h3>'
    built, page = nav_of(main, nav="on")
    assert built is not None
    assert "Inside" not in built and "Deeper" not in built
    assert 'href="#real"' in built and 'href="#after"' in built
    assert f"<{tag} title=\"T\"><h2>Inside</h2><h3>Deeper</h3></{tag}>" in page


def test_only_excluded_h2s_do_not_reach_the_threshold() -> None:
    main = "<h2>One</h2>" + '<q-panel title="p"><h2>a</h2><h2>b</h2><h2>c</h2><h2>d</h2></q-panel>'
    assert nav_of(main)[0] is None


def test_nav_labels_and_ids_are_escaped() -> None:
    built, page = nav_of("<h2>Fish &amp; <em>chips</em> &lt;b&gt;</h2>", nav="on")
    assert built is not None
    assert "Fish &amp; chips &lt;b&gt;" in built
    assert 'id="fish-chips-b"' in page


def test_nav_is_not_built_so_main_is_returned_untouched_when_absent() -> None:
    main = "<h2>One</h2><h2>Two</h2>"
    assert nav_of(main) == (None, main)


def test_build_nav_rejects_an_unknown_mode() -> None:
    with pytest.raises(ValueError):
        nav_of("<h2>x</h2>", nav="sometimes")


# --- render_regions --------------------------------------------------------------------------


def regions(layout: str, *, legacy: bool = False, nav: str | None = "<nav>N</nav>", aside: str = "<aside>A</aside>") -> str:
    return layouts.render_regions(layout, summary="<p>S</p>", main="<p>M</p>", aside=aside, nav=nav, legacy=legacy)


def order(html: str) -> list[str]:
    marks = {"S": "<p>S</p>", "N": "<nav>N</nav>", "M": "<p>M</p>", "A": "<aside>A</aside>"}
    found = [(html.index(text), key) for key, text in marks.items() if text in html]
    return [key for _, key in sorted(found)]


@pytest.mark.parametrize(
    "layout, expected",
    [
        ("report", ["S", "N", "M", "A"]),
        ("explainer", ["S", "N", "M"]),
        ("longform", ["S", "N", "M"]),
        ("reference", ["S", "N", "M"]),
        ("comparison", ["S", "N", "M"]),
        ("dashboard", ["S", "N", "M"]),
        ("tool", ["N", "M", "S"]),
    ],
)
def test_regions_follow_the_shapes_dom_order(layout: str, expected: list[str]) -> None:
    html = regions(layout)
    assert order(html) == expected
    assert html.startswith(f'<div class="q-page" data-layout="{layout}">') and html.endswith("</div>")
    assert '<section class="q-summary" aria-label="Summary">\n<p>S</p>\n</section>' in html


def test_only_the_report_shape_emits_an_aside() -> None:
    assert "<aside>A</aside>" in regions("report")
    assert "<aside>" not in regions("explainer")


def test_main_is_wrapped_unless_the_skeleton_already_does() -> None:
    assert '<main id="main">\n<p>M</p>\n</main>' in regions("report", legacy=False)
    legacy = regions("report", legacy=True)
    assert "<main" not in legacy and "<p>M</p>" in legacy


def test_absent_nav_and_empty_summary_are_left_out() -> None:
    html = layouts.render_regions("explainer", summary="", main="<p>M</p>", aside="", nav=None, legacy=False)
    assert "q-summary" not in html and "<nav" not in html and "<p>M</p>" in html


def test_render_regions_rejects_an_unknown_layout() -> None:
    with pytest.raises(ValueError):
        regions("slides")


# --- parse_source ----------------------------------------------------------------------------


def test_parse_source_reads_layout_and_nav(tmp_path: Path) -> None:
    parsed = assemble.parse_source(report_src(tmp_path, {"layout": "tool", "nav": "off"}))
    assert (parsed.layout, parsed.nav) == ("tool", "off")
    plain = assemble.parse_source(report_src(tmp_path, name="q"))
    assert (plain.layout, plain.nav) == (None, "auto")


@pytest.mark.parametrize("meta, fragment", [({"layout": "slides"}, "layout"), ({"nav": "maybe"}, "nav"), ({"layout": 4}, "layout")])
def test_parse_source_rejects_bad_layout_and_nav(tmp_path: Path, meta: dict, fragment: str) -> None:
    with pytest.raises(assemble.SourceError) as info:
        assemble.parse_source(report_src(tmp_path, meta))
    assert fragment in str(info.value)


def test_a_bad_layout_in_the_header_exits_2_and_lists_the_shapes(tmp_path: Path, env: dict, project: Path) -> None:
    rc, result = build(report_src(tmp_path, {"layout": "slides"}), tmp_path / "o.html", env, project)
    assert rc == 2 and ", ".join(SEVEN) in result["error"]
    assert result["error"].startswith("header field 'layout' must be one of")
    assert not (tmp_path / "o.html").exists()


def test_a_bad_layout_in_quirk_app_json_is_reported_as_that_key(tmp_path: Path, env: dict, project: Path) -> None:
    source = project / ".quirk" / "html" / "demo"
    source.mkdir(parents=True)
    (source / "quirk-app.json").write_text(json.dumps({"layout": "poster"}))
    rc, result = run_cli("build-app", "demo", "--project-dir", project, "--title", "T", env=env)
    assert rc == 2 and ", ".join(SEVEN) in result["error"]
    assert result["error"].startswith("quirk-app.json key 'layout' must be one of")
    assert "header field" not in result["error"]


def test_a_bad_layout_flag_is_reported_as_the_flag_not_a_header_field(tmp_path: Path, env: dict, project: Path) -> None:
    rc, result = run_cli("build-app", "demo", "--project-dir", project, "--title", "T", "--layout", "poster", env=env)
    assert rc == 2 and ", ".join(SEVEN) in result["error"]
    assert result["error"].startswith("--layout flag must be one of")
    assert "header field" not in result["error"]


# --- build: layout record and rebuild --------------------------------------------------------


@pytest.mark.parametrize("name", SEVEN)
def test_every_shape_builds_on_the_report_template_and_is_recorded(name: str, tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / f"{name}.html"
    slots = {"summary": "<p>The answer.</p>", "main": "<h2>Part</h2>\n<p>Body.</p>"}
    rc, result = build(report_src(tmp_path, {"layout": name}, slots, name=name), out, env, project)
    assert rc == 0 and result["layout"] == name and result["layout_defaulted"] is False
    assert result["checks"]["passed"]
    assert page_header(out)["layout"] == name
    html = out.read_text(encoding="utf-8")
    assert f'<div class="q-page" data-layout="{name}">' in html
    assert '<section class="q-summary" aria-label="Summary">' in html
    assert "layout_defaulted" not in page_header(out)


def test_a_rebuild_without_a_layout_keeps_the_recorded_one(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    rc, _ = build(report_src(tmp_path, {"layout": "explainer"}), out, env, project)
    assert rc == 0
    rc, result = build(report_src(tmp_path), out, env, project)
    assert rc == 0
    assert result["layout"] == "explainer" and result["layout_defaulted"] is False
    assert page_header(out)["layout"] == "explainer"
    assert 'data-layout="explainer"' in out.read_text(encoding="utf-8")


def test_a_source_layout_beats_the_recorded_one(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path, {"layout": "explainer"}), out, env, project)
    rc, result = build(report_src(tmp_path, {"layout": "dashboard"}), out, env, project)
    assert rc == 0 and result["layout"] == "dashboard" and page_header(out)["layout"] == "dashboard"


def test_no_layout_anywhere_builds_as_report_and_the_note_says_so(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    rc, result = build(report_src(tmp_path), out, env, project)
    assert rc == 0 and result["layout"] == "report" and result["layout_defaulted"] is True
    assert page_header(out)["layout"] == "report"
    rc, note = run_cli("note", out, "--project-dir", project, env=env)
    lines = note["markdown"].splitlines()
    template_at = next(i for i, line in enumerate(lines) if line.startswith("- Template:"))
    assert lines[template_at + 1] == "- Layout: report (no layout named)"


def test_a_rebuild_with_no_layout_stays_defaulted_until_the_source_names_one(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    for _ in range(2):
        rc, result = build(report_src(tmp_path), out, env, project)
        assert rc == 0 and result["layout"] == "report" and result["layout_defaulted"] is True
        assert page_header(out)["layout_defaulted"] is True
        _, note = run_cli("note", out, "--project-dir", project, env=env)
        assert "- Layout: report (no layout named)" in note["markdown"]
    rc, result = build(report_src(tmp_path, {"layout": "report"}), out, env, project)
    assert rc == 0 and result["layout_defaulted"] is False and "layout_defaulted" not in page_header(out)
    rc, result = build(report_src(tmp_path), out, env, project)
    assert rc == 0 and result["layout_defaulted"] is False and "layout_defaulted" not in page_header(out)
    _, note = run_cli("note", out, "--project-dir", project, env=env)
    assert "no layout named" not in note["markdown"]


def test_the_note_names_a_chosen_layout(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path, {"layout": "tool"}), out, env, project)
    _, note = run_cli("note", out, "--project-dir", project, env=env)
    assert "- Layout: tool\n" in note["markdown"] + "\n"
    assert "no layout named" not in note["markdown"]


def test_nav_is_generated_at_five_h2s_and_the_header_can_force_it_off(tmp_path: Path, env: dict, project: Path) -> None:
    slots = {"summary": "<p>S</p>", "main": h2s(5)}
    out = tmp_path / "o.html"
    rc, _ = build(report_src(tmp_path, {"layout": "explainer"}, slots), out, env, project)
    html = out.read_text(encoding="utf-8")
    assert rc == 0 and html.index("q-summary") < html.index('class="q-nav"') < html.index('<h2 id="part-1">')
    assert '<h2 id="part-1">Part 1</h2>' in html
    rc, _ = build(report_src(tmp_path, {"layout": "explainer", "nav": "off"}, slots), out, env, project)
    assert rc == 0 and 'class="q-nav"' not in out.read_text(encoding="utf-8")


def test_nav_errors_exit_2(tmp_path: Path, env: dict, project: Path) -> None:
    rc, result = build(report_src(tmp_path, {"layout": "reference", "nav": "off"}), tmp_path / "a.html", env, project)
    assert rc == 2 and "reference always has its section nav" in result["error"]
    rc, result = build(report_src(tmp_path, {"nav": "on"}, name="b"), tmp_path / "b.html", env, project)
    assert rc == 2 and "nav needs at least one h2 in main" in result["error"]


def test_generated_ids_avoid_ids_in_the_summary_and_aside(tmp_path: Path, env: dict, project: Path) -> None:
    slots = {
        "summary": '<p id="part-1">S</p>',
        "main": h2s(5),
        "aside": '<aside aria-label="n" id="part-2"><p>n</p></aside>',
    }
    out = tmp_path / "o.html"
    rc, _ = build(report_src(tmp_path, {"layout": "report"}, slots), out, env, project)
    html = out.read_text(encoding="utf-8")
    assert rc == 0 and '<h2 id="part-1-2">Part 1</h2>' in html and '<h2 id="part-2-2">Part 2</h2>' in html


def test_layout_css_is_inlined_after_base_css(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path), out, env, project)
    html = out.read_text(encoding="utf-8")
    base = (SKILL / "theme" / "base.css").read_text(encoding="utf-8")
    layout_css = (SKILL / "theme" / "layout.css").read_text(encoding="utf-8")
    assert layout_css.strip()
    assert html.index(base) < html.index(layout_css)


# --- build: summary rule and aside rule ------------------------------------------------------


@pytest.mark.parametrize("name", SEVEN)
def test_a_missing_summary_fails_and_says_where_it_goes(name: str, tmp_path: Path, env: dict, project: Path) -> None:
    src = report_src(tmp_path, {"layout": name}, {"main": "<p>Body.</p>"}, name=name)
    rc, result = build(src, tmp_path / "o.html", env, project)
    assert rc == 2
    assert f"the {name} shape needs a summary slot" in result["error"]
    assert SUMMARY_HINT[name] in result["error"]
    assert not (tmp_path / "o.html").exists()


def test_a_missing_summary_on_a_fresh_default_names_report(tmp_path: Path, env: dict, project: Path) -> None:
    rc, result = build(report_src(tmp_path, slots={"main": "<p>x</p>"}), tmp_path / "o.html", env, project)
    assert rc == 2 and "the report shape needs a summary slot" in result["error"]


def test_a_blank_summary_counts_as_missing(tmp_path: Path, env: dict, project: Path) -> None:
    rc, result = build(report_src(tmp_path, slots={"summary": "\n", "main": "<p>x</p>"}), tmp_path / "o.html", env, project)
    assert rc == 2 and "summary slot" in result["error"]


@pytest.mark.parametrize("name", [n for n in SEVEN if n != "report"])
def test_an_aside_on_any_other_shape_is_an_error(name: str, tmp_path: Path, env: dict, project: Path) -> None:
    slots = {"summary": "<p>S</p>", "main": "<p>M</p>", "aside": '<aside aria-label="x"><p>n</p></aside>'}
    rc, result = build(report_src(tmp_path, {"layout": name}, slots), tmp_path / "o.html", env, project)
    assert rc == 2 and "only the report shape places an aside" in result["error"]


def test_a_report_aside_follows_main_in_the_dom(tmp_path: Path, env: dict, project: Path) -> None:
    slots = {"summary": "<p>S</p>", "main": "<p>M</p>", "aside": '<aside aria-label="x"><p>side</p></aside>'}
    out = tmp_path / "o.html"
    rc, _ = build(report_src(tmp_path, {"layout": "report"}, slots), out, env, project)
    html = out.read_text(encoding="utf-8")
    assert rc == 0 and html.index("q-summary") < html.index("<p>M</p>") < html.index("<aside")


def test_summary_is_not_a_slot_a_template_can_declare(tmp_path: Path) -> None:
    problems = _tier1_problems(tmp_path, REGIONS_SKELETON, {"main": {"required": True}, "summary": {"required": False}})
    assert any("summary" in p and "reserved" in p for p in problems)


# --- build: pages that predate shapes --------------------------------------------------------


def strip_layout_from_header(out: Path) -> None:
    """Make ``out`` look like a page built before shapes: no ``layout`` (or flag) in its header."""
    text = out.read_text(encoding="utf-8")
    meta = header.read_header(text)
    assert meta is not None
    for key in ("layout", "layout_defaulted", "legacy_summary"):
        meta.pop(key, None)
    lines = text.split("\n")
    lines[1] = header.render_header(meta)
    out.write_text("\n".join(lines), encoding="utf-8")


def test_a_pre_shapes_page_rebuilds_without_a_summary_and_keeps_doing_so(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path), out, env, project)
    strip_layout_from_header(out)
    bare = report_src(tmp_path, slots={"main": "<p>Body.</p>"}, name="bare")

    rc, result = build(bare, out, env, project)
    assert rc == 0 and result["layout"] == "report" and result["legacy_summary"] is True
    assert any(w["check"] == "summary" and "summary" in w["detail"] for w in result["checks"]["warnings"])
    meta = page_header(out)
    assert meta["layout"] == "report" and meta["legacy_summary"] is True
    assert 'class="q-summary"' not in out.read_text(encoding="utf-8")

    rc, result = build(bare, out, env, project)
    assert rc == 0 and result["legacy_summary"] is True and page_header(out)["legacy_summary"] is True

    rc, result = build(report_src(tmp_path), out, env, project)
    assert rc == 0 and "legacy_summary" not in result and "legacy_summary" not in page_header(out)
    assert "q-summary" in out.read_text(encoding="utf-8")

    rc, result = build(bare, out, env, project)
    assert rc == 2 and "the report shape needs a summary slot" in result["error"]


def test_a_pre_shapes_page_takes_a_named_layout(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path), out, env, project)
    strip_layout_from_header(out)
    rc, result = build(report_src(tmp_path, {"layout": "explainer"}, {"main": "<p>x</p>"}), out, env, project)
    assert rc == 0 and result["layout"] == "explainer" and result["legacy_summary"] is True


def test_a_page_with_a_recorded_layout_gets_no_exemption(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    build(report_src(tmp_path, {"layout": "explainer"}), out, env, project)
    rc, result = build(report_src(tmp_path, slots={"main": "<p>x</p>"}), out, env, project)
    assert rc == 2 and "the explainer shape needs a summary slot" in result["error"]


# --- build: custom skeletons -----------------------------------------------------------------


@pytest.mark.parametrize("name", SEVEN)
def test_a_legacy_custom_skeleton_builds_every_shape(name: str, tmp_path: Path, env: dict, project: Path) -> None:
    custom_template(project, LEGACY_SKELETON)
    out = tmp_path / "o.html"
    slots = {"summary": "<p>The answer.</p>", "main": h2s(5)}
    rc, result = build(src_file(tmp_path / "l.src.html", {"template": "fx", "title": "T", "layout": name}, slots), out, env, project)
    assert rc == 0, result
    html = out.read_text(encoding="utf-8")
    assert result["layout"] == name and page_header(out)["layout"] == name
    assert f'<body data-layout-name="{name}">' in html
    assert f'<main id="main"><div class="q-page" data-layout="{name}">' in html
    assert html.count('<main id="main">') == 1
    assert "<p>The answer.</p>" in html and 'class="q-nav"' in html
    assert html.index("The answer.") < html.index('class="q-nav"') or name == "tool"


def test_a_legacy_skeletons_aside_stays_outside_the_wrapper(tmp_path: Path, env: dict, project: Path) -> None:
    slots = {"main": {"required": True}, "aside": {"required": False}}
    custom_template(project, LEGACY_SKELETON.replace("{{data}}", "{{slot:aside}}{{data}}"), slots=slots)
    out = tmp_path / "o.html"
    src = src_file(
        tmp_path / "l.src.html",
        {"template": "fx", "title": "T"},
        {"summary": "<p>S</p>", "main": "<p>M</p>", "aside": '<aside aria-label="n">side</aside>'},
    )
    rc, _ = build(src, out, env, project)
    html = out.read_text(encoding="utf-8")
    assert rc == 0 and html.index("</div></main>") < html.index("<aside")


def test_a_regions_skeleton_places_main_and_aside_itself(tmp_path: Path, env: dict, project: Path) -> None:
    slots = {"main": {"required": True}, "aside": {"required": False}}
    custom_template(project, REGIONS_SKELETON, slots=slots)
    out = tmp_path / "o.html"
    src = src_file(
        tmp_path / "r.src.html",
        {"template": "fx", "title": "T", "layout": "report"},
        {"summary": "<p>S</p>", "main": "<p>M</p>", "aside": '<aside aria-label="n">side</aside>'},
    )
    rc, result = build(src, out, env, project)
    html = out.read_text(encoding="utf-8")
    assert rc == 0, result
    assert html.index("q-summary") < html.index('<main id="main">') < html.index("<aside")
    assert html.count('<main id="main">') == 1


def test_layout_placeholder_is_the_resolved_name(tmp_path: Path, env: dict, project: Path) -> None:
    custom_template(project, REGIONS_SKELETON.replace("<body>", '<body data-shape="{{layout}}">'))
    out = tmp_path / "o.html"
    src = src_file(tmp_path / "r.src.html", {"template": "fx", "title": "T", "layout": "dashboard"}, {"summary": "<p>S</p>", "main": "<p>M</p>"})
    assert build(src, out, env, project)[0] == 0
    assert '<body data-shape="dashboard">' in out.read_text(encoding="utf-8")


def test_a_skeleton_without_region_placeholders_needs_no_summary(tmp_path: Path, env: dict, project: Path) -> None:
    skeleton = "<!doctype html>\n{{header}}\n<html><head><title>{{title}}</title>{{head}}</head><body data-l=\"{{layout}}\">{{chrome}}{{slot:content}}{{data}}{{body_end}}</body></html>\n"
    custom_template(project, skeleton, slots={"content": {"required": True}})
    out = tmp_path / "o.html"
    plain = src_file(tmp_path / "c.src.html", {"template": "fx", "title": "T"}, {"content": "<p>c</p>"})
    rc, result = build(plain, out, env, project)
    assert rc == 0 and result["layout"] == "" and result["layout_defaulted"] is False
    assert 'data-l=""' in out.read_text(encoding="utf-8") and "layout" not in page_header(out)
    named = src_file(tmp_path / "n.src.html", {"template": "fx", "title": "T", "layout": "tool"}, {"content": "<p>c</p>"})
    rc, result = build(named, out, env, project)
    assert rc == 0 and result["layout"] == "tool" and 'data-l="tool"' in out.read_text(encoding="utf-8")
    assert 'class="q-page"' not in out.read_text(encoding="utf-8")


def test_summary_is_accepted_by_a_template_that_does_not_declare_it(tmp_path: Path, env: dict, project: Path) -> None:
    out = tmp_path / "o.html"
    rc, _ = build(report_src(tmp_path), out, env, project)
    assert rc == 0
    rc, result = build(report_src(tmp_path, slots={"summary": "<p>s</p>", "main": "<p>m</p>", "extra": "x"}), out, env, project)
    assert rc == 2 and "extra" in result["error"] and "summary" not in result["error"].split("(declared")[0]


def test_a_summary_slot_the_skeleton_has_no_place_for_is_an_error(tmp_path: Path, env: dict, project: Path) -> None:
    skeleton = "<!doctype html>\n{{header}}\n<html><head><title>{{title}}</title>{{head}}</head><body>{{chrome}}{{slot:content}}{{data}}{{body_end}}</body></html>\n"
    custom_template(project, skeleton, slots={"content": {"required": True}})
    out = tmp_path / "o.html"
    src = src_file(
        tmp_path / "c.src.html", {"template": "fx", "title": "T"}, {"summary": "<p>LOSTSUMMARY</p>", "content": "<p>c</p>"}
    )
    rc, result = build(src, out, env, project)
    assert rc == 2 and "summary" in result["error"] and "no place" in result["error"]
    assert not out.exists()


# --- manifest --------------------------------------------------------------------------------


def _tier1_problems(base: Path, skeleton: str, slots: dict) -> list[str]:
    tdir = base / "fx"
    tdir.mkdir(exist_ok=True)
    meta = {
        "schema": 1,
        "name": "fx",
        "description": DESCRIPTION,
        "tier": 1,
        "libraries": [],
        "slots": slots,
        "skeleton": "skeleton.html",
        "example": "example.src.html",
    }
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    (tdir / "skeleton.html").write_text(skeleton, encoding="utf-8")
    src_file(tdir / "example.src.html", {"template": "fx", "title": "T"}, {"summary": "<p>s</p>", "main": "<p>m</p>"})
    return manifest.validate_template(tdir, require_verified=False, skill_dir=tdir.parent / "skill")


MAIN_ONLY = {"main": {"required": True}}
MAIN_ASIDE = {"main": {"required": True}, "aside": {"required": False}}


def test_manifest_accepts_regions_without_main_or_aside_placeholders(tmp_path: Path) -> None:
    assert _tier1_problems(tmp_path, REGIONS_SKELETON, MAIN_ASIDE) == []


def test_manifest_accepts_the_layout_placeholder_with_either_main_style(tmp_path: Path) -> None:
    assert _tier1_problems(tmp_path, REGIONS_SKELETON.replace("<body>", "<body data-x={{layout}}>"), MAIN_ONLY) == []
    assert _tier1_problems(tmp_path, LEGACY_SKELETON, MAIN_ONLY) == []


def test_manifest_rejects_regions_mixed_with_slot_main(tmp_path: Path) -> None:
    problems = _tier1_problems(tmp_path, REGIONS_SKELETON.replace("{{regions}}", "{{regions}}{{slot:main}}"), MAIN_ONLY)
    assert any("{{regions}}" in p and "{{slot:main}}" in p for p in problems)


def test_manifest_rejects_regions_mixed_with_slot_aside(tmp_path: Path) -> None:
    problems = _tier1_problems(tmp_path, REGIONS_SKELETON.replace("{{regions}}", "{{regions}}{{slot:aside}}"), MAIN_ASIDE)
    assert any("{{slot:aside}}" in p for p in problems)


def test_manifest_still_needs_other_declared_slots_beside_regions(tmp_path: Path) -> None:
    slots = {"main": {"required": True}, "extra": {"required": False}}
    assert any("{{slot:extra}}" in p for p in _tier1_problems(tmp_path, REGIONS_SKELETON, slots))
    assert _tier1_problems(tmp_path, REGIONS_SKELETON.replace("{{regions}}", "{{regions}}{{slot:extra}}"), slots) == []


def test_manifest_without_regions_still_needs_slot_main(tmp_path: Path) -> None:
    skeleton = REGIONS_SKELETON.replace("{{regions}}", "")
    assert any("{{slot:main}}" in p for p in _tier1_problems(tmp_path, skeleton, MAIN_ONLY))


def test_manifest_rejects_a_declared_summary_slot(tmp_path: Path) -> None:
    slots = {"main": {"required": True}, "summary": {"required": True}}
    problems = _tier1_problems(tmp_path, REGIONS_SKELETON.replace("{{regions}}", "{{regions}}{{slot:summary}}"), slots)
    assert any("summary" in p and "reserved" in p for p in problems)


def test_regions_and_layout_are_not_required_placeholders() -> None:
    assert "{{regions}}" not in manifest.REQUIRED_PLACEHOLDERS and "{{layout}}" not in manifest.REQUIRED_PLACEHOLDERS


# --- tokens ----------------------------------------------------------------------------------


def test_tokens_css_ends_with_a_print_block_that_restores_the_light_colors() -> None:
    css = tokens.tokens_css(
        {"color": {"bg": ["#fff", "#000"], "text": ["#111", "#eee"]}, "font": {"sans": "system-ui"}, "space": {"1": "4px"}}
    )
    start = css.index("@media print")
    block = css[start:]
    assert css.rstrip().endswith("}") and start > css.index(':root[data-theme="dark"] {')
    for selector in (":root:root:root", ':root[data-theme="dark"]', ":root.wa-dark"):
        assert selector in block
    assert "--q-color-bg: #fff;" in block and "--q-color-text: #111;" in block
    assert "#000" not in block and "#eee" not in block
    assert "--q-font-sans" not in block and "--q-space-1" not in block


def test_print_block_selectors_outrank_both_dark_blocks() -> None:
    css = tokens.tokens_css({"color": {"bg": ["#fff", "#000"]}})
    selector_line = css[css.index("@media print") :].split("{", 1)[1].rsplit("{", 1)[0]
    # every print selector carries at least three class-level parts; the dark blocks carry two
    for sel in (s.strip() for s in selector_line.split(",")):
        classes = len(re.findall(r"\[[^\]]+\]|\.[\w-]+|:root", sel))
        assert classes >= 3, sel


def test_tokens_css_without_colors_has_no_print_block() -> None:
    assert "@media print" not in tokens.tokens_css({"space": {"1": "4px"}})
