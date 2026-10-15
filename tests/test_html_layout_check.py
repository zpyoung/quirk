"""The layout static check: slot content must use page shapes and q-grid, not its own geometry.

Pages are built inline here; nothing depends on the build pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import checks, header, layoutcheck, vendor  # noqa: E402

GRID_HINT = "use q-grid (and q-panel for titled panels)"
WIDTH_HINT = 'page shapes set widths; set "layout" in the header'


def page(slot: str, head: str = "") -> str:
    return (
        f"<!doctype html>\n<html><head><title>t</title>{head}</head><body>\n"
        f'<div class="q-page" data-layout="report">\n{slot}\n</div>\n</body></html>\n'
    )


def check(html: str) -> list[str]:
    return [f["detail"] for f in layoutcheck.check_html(html, label="page")]


def decl_page(decl: str) -> str:
    return page(f"<style>.x {{ {decl} }}</style><p class='x'>hi</p>")


@pytest.mark.parametrize(
    "decl",
    [
        "display: grid",
        "display: inline-grid",
        "grid-template-columns: 1fr 1fr",
        "grid-template-areas: 'a b'",
        "grid-template: auto / auto",
        "grid: auto-flow / 1fr",
        "grid-column: span 2",
        "grid-column-start: 2",
        "grid-row: 1 / 3",
        "grid-row-end: 4",
        "grid-area: head",
    ],
)
def test_grid_declarations_fail_and_name_q_grid(decl: str) -> None:
    got = check(decl_page(decl))
    assert len(got) == 1
    assert GRID_HINT in got[0]
    assert decl.split(":")[0] in got[0]


@pytest.mark.parametrize(
    "decl",
    [
        "float: left",
        "float: right",
        "columns: 3",
        "column-count: 2",
        "width: 400px",
        "min-width: 600px",
        "max-width: 25rem",
        "width: 30em",
        "max-width: 1200px",
    ],
)
def test_width_float_and_column_declarations_fail_and_name_the_layout_header(decl: str) -> None:
    got = check(decl_page(decl))
    assert len(got) == 1
    assert WIDTH_HINT in got[0]
    assert decl.split(":")[0] in got[0]


def test_detail_is_label_line_and_message_with_the_built_page_line() -> None:
    html = page("<p>a</p>\n<style>\n.x {\n  color: red;\n  display: grid;\n}\n</style>")
    line = html[: html.index("display: grid")].count("\n") + 1
    got = check(html)
    assert len(got) == 1 and got[0].startswith(f"page line {line}: ")
    assert layoutcheck.check_html(html, label="deck.html")[0]["check"] == "layout"


def test_style_attribute_is_scanned() -> None:
    got = check(page('<div style="color: red; float: left">x</div>'))
    assert len(got) == 1 and "float" in got[0] and WIDTH_HINT in got[0]


@pytest.mark.parametrize(
    "decl",
    [
        "width: 300px",
        "max-width: 399px",
        "max-width: 24rem",
        "width: 100%",
        "max-width: calc(100% - 2rem)",
        "width: var(--q-w)",
        "max-width: min(90vw, 1200px)",
        "min-width: max(400px, 10%)",
        "width: clamp(300px, 50%, 900px)",
        "max-width: 80vw",
        "width: 90vh",
        "width: auto",
        "float: none",
        "display: flex",
        "display: block",
        "color: red",
    ],
)
def test_allowed_values_pass(decl: str) -> None:
    assert check(decl_page(decl)) == []


def test_head_styles_are_ignored() -> None:
    html = page("<p>x</p>", head="<style>body { display: grid; width: 900px }</style>")
    assert check(html) == []


def test_content_outside_the_wrapper_is_ignored() -> None:
    html = (
        "<html><head></head><body>"
        '<style>.a { display: grid }</style><div style="float: left">x</div>'
        '<div class="q-page"><p>in</p></div>'
        '<aside style="width: 800px">after</aside></body></html>'
    )
    assert check(html) == []


def test_a_page_with_no_wrapper_yields_nothing() -> None:
    html = "<html><body><style>.a { display: grid; width: 900px }</style><p style='float:left'>x</p></body></html>"
    assert check(html) == []


def test_wrapper_class_may_sit_among_other_classes() -> None:
    html = '<div class="foo q-page bar"><div style="display:grid"></div></div>'
    assert len(check(html)) == 1


def test_wrapper_scope_survives_void_and_unclosed_elements() -> None:
    html = (
        '<div class="q-page"><img src="x"><br><p>open<style>.a{float:right}</style></div>'
        '<style>.b{float:left}</style>'
    )
    assert len(check(html)) == 1


def test_media_and_container_nested_declarations_are_scanned() -> None:
    css = (
        "@media (min-width: 600px) { .x { display: grid } }\n"
        "@container card (min-width: 300px) { .y { width: 500px } }\n"
        ".z { color: red }"
    )
    got = check(page(f"<style>{css}</style>"))
    assert len(got) == 2
    assert "display" in got[0] and "width" in got[1]


def test_conditions_in_at_rule_preludes_are_not_declarations() -> None:
    assert check(page("<style>@media (width: 600px) { .x { color: red } }</style>")) == []


def test_comments_and_strings_do_not_confuse_the_scan() -> None:
    css = '/* display: grid */ .x::after { content: "float: left; width: 900px"; color: red }'
    assert check(page(f"<style>{css}</style>")) == []


def test_important_is_stripped_before_matching() -> None:
    assert len(check(decl_page("width: 600px !important"))) == 1
    assert check(decl_page("width: 100% !important")) == []


def test_untokenizable_css_is_skipped_declaration_by_declaration() -> None:
    css = ".a { color: red; background: url(  ; display: grid } .b { float: left"
    got = check(page(f"<style>{css}</style>"))
    assert any("float" in d for d in got)


@pytest.mark.parametrize("junk", ["<style>", "<div style='", '<div class="q-page"><style>.a{', "\x00<style>}{;:"])
def test_check_html_never_raises(junk: str) -> None:
    layoutcheck.check_html(junk, label="page")
    layoutcheck.check_html('<div class="q-page">' + junk, label="page")


def sources(tmp_path: Path, files: dict[str, str]) -> list[Path]:
    paths = []
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def test_app_sources_skip_the_theme_files(tmp_path: Path) -> None:
    css = ".a { display: grid; width: 900px }"
    paths = sources(
        tmp_path,
        {"src/theme.css": css, "src/quirk-tokens.css": css, "src/quirk-layout.css": css, "src/styles/theme.css": css},
    )
    assert layoutcheck.check_app_sources(paths, root=tmp_path) == []


def test_app_sources_flag_a_css_file_with_a_relative_path_and_line(tmp_path: Path) -> None:
    paths = sources(tmp_path, {"src/pages/card.css": ".a {\n  color: red;\n}\n.b {\n  grid-template-columns: 1fr 1fr;\n}\n"})
    got = layoutcheck.check_app_sources(paths, root=tmp_path)
    assert [f["check"] for f in got] == ["layout"]
    assert got[0]["detail"].startswith("src/pages/card.css line 5: ")
    assert GRID_HINT in got[0]["detail"]


def test_app_sources_flag_inline_style_objects_in_tsx(tmp_path: Path) -> None:
    tsx = (
        "export function A() {\n"
        "  return (\n"
        "    <div style={{ gridTemplateColumns: 'repeat(2, 1fr)', color: 'red' }}>\n"
        "      <p style={{\n"
        "        width: 600,\n"
        "        maxWidth: '100%',\n"
        "        float: 'left',\n"
        "      }}>x</p>\n"
        "      <i style={{ width: 300, display: 'flex' }} />\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    )
    got = layoutcheck.check_app_sources(sources(tmp_path, {"src/A.tsx": tsx}), root=tmp_path)
    details = [f["detail"] for f in got]
    assert len(details) == 3
    assert details[0].startswith("src/A.tsx line 3: ") and "grid-template-columns" in details[0]
    assert details[1].startswith("src/A.tsx line 5: ") and "width" in details[1]
    assert details[2].startswith("src/A.tsx line 7: ") and "float" in details[2]


def test_app_sources_ignore_other_files_and_unflagged_tsx(tmp_path: Path) -> None:
    paths = sources(
        tmp_path,
        {
            "src/notes.md": "display: grid",
            "src/a.ts": "const s = { display: 'grid' }",
            "src/B.tsx": "const x = <div style={{ width: '100%', color: 'red' }} className=\"a\" />;\n",
        },
    )
    assert layoutcheck.check_app_sources(paths, root=tmp_path) == []


def test_app_sources_report_an_unreadable_path_and_continue(tmp_path: Path) -> None:
    good = sources(tmp_path, {"src/ok.css": ".a { float: left }"})[0]
    missing = tmp_path / "src" / "gone.css"
    got = layoutcheck.check_app_sources([missing, good], root=tmp_path)
    assert got[0] == {"check": "layout", "detail": f"cannot read {missing}"}
    assert len(got) == 2 and got[1]["detail"].startswith("src/ok.css line 1: ")


def _header_meta() -> dict:
    return {
        "schema": 1,
        "template": "t",
        "template_level": "builtin",
        "tier": 1,
        "tier_signal": None,
        "mode": "offline",
        "libraries": {},
        "sidecar": None,
        "built_at": "2026-10-15T00:00:00Z",
        "quirk_version": "unknown",
    }


def built(slot: str, *, wrapper: bool = True) -> str:
    body = f'<div class="q-page" data-layout="report">{slot}</div>' if wrapper else slot
    return f"<!doctype html>\n{header.render_header(_header_meta())}\n<html><head><title>t</title></head><body>\n{body}\n</body></html>\n"


STORE = vendor.VendorStore([SKILL / "vendor" / "libraries.json"])


def run(html: str, tier: int = 1) -> dict:
    return checks.run_checks(html, mode="offline", tier=tier, vendor=STORE, shells={})


def test_run_checks_fails_a_tier_1_page_with_a_flagged_slot_style() -> None:
    result = run(built('<div style="display: grid">x</div>'))
    assert result["passed"] is False
    assert [f["check"] for f in result["failures"]] == ["layout"]
    assert "display" in result["failures"][0]["detail"]
    assert result["failures"][0]["detail"].startswith("page line ")


def test_run_checks_passes_a_tier_1_page_with_clean_slot_content() -> None:
    assert run(built('<div style="width: 100%">x</div>'))["passed"] is True


def test_run_checks_leaves_pages_without_a_wrapper_alone() -> None:
    assert run(built('<div style="display: grid">x</div>', wrapper=False))["passed"] is True


def test_run_checks_does_not_run_the_layout_check_for_tier_2() -> None:
    assert run(built('<div style="display: grid">x</div>'), tier=2)["passed"] is True
