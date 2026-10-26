"""Style generator checks: colour math, source validation, rendering, the contrast gate and the CLI."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "building-mini-apps"
SCRIPTS_DIR = SKILL_DIR / "scripts"
STYLES_DIR = SKILL_DIR / "styles"


def _copy_skill(dest: Path) -> Path:
    """Copy the skill tree; scripts anchor on their own location, so the copy is self-contained."""
    target = dest / "building-mini-apps"
    shutil.copytree(SKILL_DIR, target, ignore=shutil.ignore_patterns("node_modules", "media"))
    return target


def _load_script(name: str) -> ModuleType:
    # the scripts import their siblings by bare name
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(f"_bma_{name}", SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Make any subprocess launch fail the test; returns the list of attempted commands."""
    attempts: List[str] = []

    def _forbidden(*args, **kwargs):
        attempts.append(str(args[0] if args else kwargs.get("args")))
        raise AssertionError(f"subprocess launched: {attempts[-1]}")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    return attempts


@pytest.fixture(scope="module")
def styles() -> ModuleType:
    return _load_script("_styles")


@pytest.fixture(scope="module")
def build_styles() -> ModuleType:
    return _load_script("build_styles")


@pytest.fixture
def neutral(styles: ModuleType) -> Dict[str, Any]:
    return styles.load_style(STYLES_DIR / "neutral-house.json")


def _write(tmp_path: Path, data: Dict[str, Any], slug: str = "calm-paper") -> Path:
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _variant(neutral: Dict[str, Any], **changes: Any) -> Dict[str, Any]:
    data = copy.deepcopy(neutral)
    data["slug"] = "calm-paper"
    data["name"] = "Calm Paper"
    data.update(changes)
    return data


def _rule(selector: str, mode: str = "both", **declarations: str) -> Dict[str, Any]:
    return {"selector": selector, "mode": mode,
            "declarations": {k.replace("_", "-"): v for k, v in declarations.items()}}


# --- colour math ---

def test_white_on_black_is_21_to_1(styles: ModuleType) -> None:
    assert round(styles.contrast_ratio("oklch(1 0 0)", "oklch(0 0 0)"), 2) == 21.0


def test_767676_on_white_is_4_54(styles: ModuleType) -> None:
    assert round(styles.contrast_ratio("oklch(0.565836 0 0)", "oklch(1 0 0)"), 2) == 4.54


def test_out_of_gamut_oklch_maps_into_gamut(styles: ModuleType) -> None:
    rgb = styles.oklch_to_linear_srgb("oklch(0.7 0.4 150)")
    assert all(0.0 <= channel <= 1.0 for channel in rgb)
    assert max(rgb) > 0.9 or min(rgb) < 0.1  # chroma was reduced, not the colour thrown away


def test_half_alpha_foreground_composites_over_background(styles: ModuleType) -> None:
    half_black = styles.contrast_ratio("oklch(0 0 0 / 50%)", "oklch(1 0 0)")
    solid = styles.contrast_ratio("oklch(0 0 0)", "oklch(1 0 0)")
    assert 1.0 < half_black < solid
    # 50% black over white is linear 0.5, which has luminance 0.5: (1.05)/(0.55)
    assert half_black == pytest.approx(1.05 / 0.55, abs=0.01)


def test_alpha_composites_in_linear_light(styles: ModuleType) -> None:
    # 50% black over white is linear 0.5, not the oklch lightness 0.5
    rgb = styles.composite("oklch(0 0 0 / 50%)", "oklch(1 0 0)")
    assert all(channel == pytest.approx(0.5, abs=1e-3) for channel in rgb)


# --- validation ---

def test_real_neutral_house_loads_and_passes_the_gate(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    assert neutral["slug"] == "neutral-house"
    assert neutral["name"] == "Neutral House"
    assert styles.contrast_failures(neutral) == []


def test_loading_all_sources_follows_slug_order(styles: ModuleType) -> None:
    loaded = styles.load_styles(STYLES_DIR)
    assert list(loaded) == [s for s in styles.SLUGS if s in loaded]
    assert "neutral-house" in loaded


def test_valid_variant_is_accepted(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    data = _variant(neutral, extra_css=[_rule('[data-mini="title"]', font_weight="650")])
    assert styles.load_style(_write(tmp_path, data))["slug"] == "calm-paper"


def _bad_missing_token(d: Dict[str, Any]) -> None:
    del d["light"]["ring"]


def _bad_extra_token(d: Dict[str, Any]) -> None:
    d["dark"]["mini-bogus"] = "oklch(0.5 0 0)"


def _bad_unparsable(d: Dict[str, Any]) -> None:
    d["light"]["primary"] = "#336699"


def _bad_alpha_background(d: Dict[str, Any]) -> None:
    d["light"]["background"] = "oklch(0.98 0.002 250 / 90%)"


def _bad_package(d: Dict[str, Any]) -> None:
    d["font_packages"] = ["left-pad"]


def _bad_remote_package(d: Dict[str, Any]) -> None:
    d["font_packages"] = ["https://fonts.example/x.css"]


def _bad_sf_pro(d: Dict[str, Any]) -> None:
    d["fonts"]["sans"] = "'SF Pro Text', system-ui, sans-serif"


def _bad_selector_without_hook(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-row="x"]', opacity="1")]


def _bad_selector_comma(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"], [data-mini="cell"]', opacity="1")]


def _bad_selector_class(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"] .x', opacity="1")]


def _bad_selector_child_combinator(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"] > [data-mini="cell"]', opacity="1")]


def _bad_property(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', display="none")]


def _bad_url(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="url(https://x.example/a.png)")]


def _bad_important(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', opacity="0.5 !important")]


def _bad_extra_css_sf_pro(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="title"]', font_family="'SF Pro Text', sans-serif")]


def _bad_extra_css_new_york_cased(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="title"]', font_family="  'NEW   York', serif")]


def _bad_escaped_url(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image=r"u\72l(https://example.com/pixel)")]


def _bad_image_set_string(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image='image-set("https://example.com/pixel.png" 1x)')]


def _bad_image_function(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="image(oklch(0.5 0 0))")]


def _bad_cross_fade(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="-webkit-cross-fade(none, none, 50%)")]


def _bad_element_function(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="element(#other)")]


def _bad_src_function(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="src(var(--x))")]


def _bad_quoted_string_outside_font_family(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background_image="linear-gradient('https://example.com/a.png')")]


def _bad_single_quote_string(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', background="'https://example.com/a.png'")]


def _bad_escaped_selector(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule(r'[data-mini="row"] [data-mini=a\62]', opacity="1")]


def _bad_huge_chroma(d: Dict[str, Any]) -> None:
    d["light"]["primary"] = "oklch(0.5 " + "9" * 400 + " 205)"


def _bad_chroma_above_range(d: Dict[str, Any]) -> None:
    d["light"]["primary"] = "oklch(0.5 0.51 205)"


def _bad_hue_above_range(d: Dict[str, Any]) -> None:
    d["dark"]["primary"] = "oklch(0.5 0.1 361)"


def _bad_alpha_above_range(d: Dict[str, Any]) -> None:
    d["dark"]["border"] = "oklch(0.5 0.1 200 / 101%)"


def _bad_lightness_above_range(d: Dict[str, Any]) -> None:
    d["dark"]["primary"] = "oklch(1.01 0.1 200)"


def _bad_mode(d: Dict[str, Any]) -> None:
    d["extra_css"] = [_rule('[data-mini="row"]', mode="sepia", opacity="1")]


def _bad_unknown_key(d: Dict[str, Any]) -> None:
    d["density"] = "tight"


def _bad_missing_key(d: Dict[str, Any]) -> None:
    del d["radius"]


@pytest.mark.parametrize("mutate", [
    _bad_missing_token, _bad_extra_token, _bad_unparsable, _bad_alpha_background, _bad_package,
    _bad_remote_package, _bad_sf_pro, _bad_selector_without_hook, _bad_selector_comma,
    _bad_selector_class, _bad_selector_child_combinator, _bad_property, _bad_url, _bad_important,
    _bad_mode, _bad_unknown_key, _bad_missing_key, _bad_extra_css_sf_pro,
    _bad_extra_css_new_york_cased, _bad_escaped_url, _bad_escaped_selector, _bad_huge_chroma,
    _bad_chroma_above_range, _bad_hue_above_range, _bad_alpha_above_range,
    _bad_lightness_above_range, _bad_image_set_string, _bad_image_function, _bad_cross_fade,
    _bad_element_function, _bad_src_function, _bad_quoted_string_outside_font_family,
    _bad_single_quote_string,
])
def test_validation_rejects_bad_source(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, mutate: Any
) -> None:
    data = _variant(neutral)
    mutate(data)
    path = _write(tmp_path, data)
    with pytest.raises(styles.StyleError) as err:
        styles.load_style(path)
    assert path.name in str(err.value)


def test_font_family_may_quote_font_names(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    data = _variant(neutral)
    data["extra_css"] = [_rule('[data-mini="title"]', font_family='"Inter Variable", sans-serif')]
    styles.load_style(_write(tmp_path, data))


def test_neutral_house_must_have_empty_extra_css(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    data = copy.deepcopy(neutral)
    data["extra_css"] = [_rule('[data-mini="title"]', font_weight="700")]
    with pytest.raises(styles.StyleError, match="extra_css"):
        styles.load_style(_write(tmp_path, data, slug="neutral-house"))


def test_slug_must_equal_file_stem(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(styles.StyleError, match="slug"):
        styles.load_style(_write(tmp_path, neutral, slug="calm-paper"))


def test_font_stack_check_covers_every_role(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    for banned in ("SF Compact", "SF Mono", "New York"):
        data = _variant(neutral)
        data["fonts"]["data"] = f"'{banned}', monospace"
        with pytest.raises(styles.StyleError):
            styles.load_style(_write(tmp_path, data))


def test_fontsource_packages_are_accepted(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    data = _variant(neutral, font_packages=["@fontsource-variable/source-serif-4", "@fontsource/inter"])
    assert styles.load_style(_write(tmp_path, data))["font_packages"][0].endswith("source-serif-4")


# --- rendering ---

def test_app_css_header_round_trips_through_parse_header(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    assert css.startswith("/* mini-style: neutral-house sha256=")
    assert css.endswith("\n") and "\r" not in css
    assert styles.parse_header(css) == ("neutral-house", True)


def test_edited_body_fails_the_hash(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    assert styles.parse_header(css.replace("2rem", "3rem")) == ("neutral-house", False)


def test_parse_header_rejects_non_headers(styles: ModuleType) -> None:
    assert styles.parse_header("html:root {}\n") == (None, False)
    assert styles.parse_header("") == (None, False)
    assert styles.parse_header("/* mini-style: x sha256=zz */\nbody") == (None, False)


def test_app_css_contents_and_order(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    assert css == styles.render_app_css(copy.deepcopy(neutral))
    root = css.index("html:root {")
    dark = css.index("html.dark {")
    assert root < dark
    assert "font-size: 15px;" in css[root:dark]
    for token in ("--radius: 0.5rem;", "--mini-row-height: 2rem;", "--mini-gap: 0.5rem;",
                  "--mini-font-sans: 'Geist Variable', sans-serif;",
                  "--mini-font-heading: 'Geist Variable', sans-serif;",
                  "--mini-font-data: 'Geist Variable', sans-serif;"):
        assert token in css[root:dark]
    assert "--mini-font-sans" not in css[dark:css.index('[data-mini="title"]')]
    assert css.index('[data-mini="title"] { font-family: var(--mini-font-heading); }') > dark
    assert '[data-mini="cell"] { font-family: var(--mini-font-data); }' in css


def test_app_css_emits_imports_and_mode_prefixes(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    style = _variant(
        neutral,
        font_packages=["@fontsource-variable/source-serif-4"],
        extra_css=[_rule('[data-mini="row"]', "both", opacity="1"),
                   _rule('[data-mini="row"]:hover', "light", color="oklch(0.2 0 0)"),
                   _rule('[data-mini="row"]', "dark", color="oklch(0.9 0 0)")],
    )
    css = styles.render_app_css(style)
    body = css.split("\n", 1)[1]
    assert body.startswith('@import "@fontsource-variable/source-serif-4";\n')
    assert '\n[data-mini="row"] { opacity: 1; }' in css
    assert '\nhtml:not(.dark) [data-mini="row"]:hover { color: oklch(0.2 0 0); }' in css
    assert '\nhtml.dark [data-mini="row"] { color: oklch(0.9 0 0); }' in css


def test_gallery_css_applies_the_scoping_table(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    synthetic = _variant(
        neutral,
        font_packages=["@fontsource-variable/source-serif-4"],
        extra_css=[_rule('[data-mini="row"]', "both", opacity="1"),
                   _rule('[data-mini="row"]', "light", color="oklch(0.2 0 0)"),
                   _rule('[data-mini="row"]', "dark", color="oklch(0.9 0 0)")],
    )
    other = _variant(neutral, slug="airy-white", name="Airy White",
                     font_packages=["@fontsource-variable/source-serif-4"])
    css = styles.render_gallery_css({"neutral-house": neutral, "calm-paper": synthetic, "airy-white": other})
    x = 'html[data-mini-style="calm-paper"]'
    assert "mini-style:" not in css
    assert "neutral-house" not in css
    assert css.count('@import "@fontsource-variable/source-serif-4";') == 1
    assert css.startswith('@import "@fontsource-variable/source-serif-4";\n')
    assert f"\n{x}:root {{" in css
    assert f"\n{x}.dark {{" in css
    assert f'\n{x} [data-mini="title"] {{ font-family: var(--mini-font-heading); }}' in css
    assert f'\n{x} [data-mini="cell"] {{ font-family: var(--mini-font-data); }}' in css
    assert f'\n{x} [data-mini="row"] {{ opacity: 1; }}' in css
    assert f'\n{x}:not(.dark) [data-mini="row"] {{ color: oklch(0.2 0 0); }}' in css
    assert f'\n{x}.dark [data-mini="row"] {{ color: oklch(0.9 0 0); }}' in css
    assert 'html[data-mini-style="airy-white"]:root {' in css
    assert "\nhtml:root {" not in css and "\nhtml.dark {" not in css


def test_gallery_css_is_empty_without_other_styles(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    assert styles.render_gallery_css({"neutral-house": neutral}).strip() == ""


# --- contrast gate ---

def test_gate_reports_a_failing_pair(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    weak = copy.deepcopy(neutral)
    weak["light"]["muted-foreground"] = "oklch(0.8 0.01 250)"
    failures = styles.contrast_failures(weak)
    assert failures
    pairs = {(f.mode, f.fg, f.bg) for f in failures}
    assert ("light", "muted-foreground", "background") in pairs
    first = failures[0]
    assert first.slug == "neutral-house" and first.needed in (4.5, 3.0)
    assert first.ratio < first.needed and round(first.ratio, 2) == first.ratio


def test_gate_checks_ring_at_3_to_1(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    weak = copy.deepcopy(neutral)
    weak["dark"]["ring"] = "oklch(0.25 0.01 250)"
    failures = styles.contrast_failures(weak)
    assert [(f.fg, f.bg, f.needed) for f in failures if f.mode == "dark"] == [("ring", "background", 3.0)]


@pytest.mark.parametrize("token", ["mini-added", "mini-removed", "mini-pending"])
def test_gate_checks_foreground_on_staged_tints(
    styles: ModuleType, neutral: Dict[str, Any], token: str
) -> None:
    weak = copy.deepcopy(neutral)
    weak["light"][token] = weak["light"]["foreground"]
    failures = styles.contrast_failures(weak)
    assert [(f.mode, f.fg, f.bg, f.needed) for f in failures] == [
        ("light", "foreground", token, 4.5),
        ("light", "muted-foreground", token, 4.5),
    ]


@pytest.mark.parametrize("token", ["mini-added", "mini-removed", "mini-pending"])
def test_gate_checks_muted_foreground_on_staged_tints(
    styles: ModuleType, neutral: Dict[str, Any], token: str
) -> None:
    weak = copy.deepcopy(neutral)
    weak["dark"][token] = "oklch(0.6 0 0)"
    weak["dark"]["muted-foreground"] = "oklch(0.7 0 0)"
    failures = styles.contrast_failures(weak)
    assert ("dark", "muted-foreground", token, 4.5) in {(f.mode, f.fg, f.bg, f.needed) for f in failures}


def test_gate_does_not_check_borders(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    faint = copy.deepcopy(neutral)
    faint["light"]["border"] = faint["light"]["background"]
    faint["light"]["input"] = faint["light"]["background"]
    assert styles.contrast_failures(faint) == []


@pytest.mark.parametrize("fg, bg", [
    ("muted-foreground", "sidebar"),
    ("muted-foreground", "popover"),
    ("muted-foreground", "accent"),
    ("foreground", "accent"),
    ("sidebar-foreground", "sidebar-accent"),
])
def test_gate_checks_the_pairs_blocks_render(
    styles: ModuleType, neutral: Dict[str, Any], fg: str, bg: str
) -> None:
    weak = copy.deepcopy(neutral)
    weak["light"][fg] = weak["light"][bg]
    pairs = {(f.mode, f.fg, f.bg) for f in styles.contrast_failures(weak)}
    assert ("light", fg, bg) in pairs


def test_gate_checks_the_kbd_chip_over_a_primary_button(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    glass = copy.deepcopy(neutral)
    glass["light"]["primary"] = "oklch(0.55 0.15 50)"
    glass["light"]["muted"] = "oklch(0.2 0.01 60 / 6%)"
    glass["light"]["muted-foreground"] = "oklch(0.46 0.008 60)"
    failures = [f for f in styles.contrast_failures(glass) if f.mode == "light"]
    assert [(f.fg, f.bg) for f in failures] == [("muted-foreground", "muted over primary")]
    assert failures[0].ratio < 2.0


def test_opaque_muted_passes_over_any_primary(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    assert not [f for f in styles.contrast_failures(neutral) if "over" in f.bg]


def _dark_sidebar(neutral: Dict[str, Any]) -> Dict[str, Any]:
    style = copy.deepcopy(neutral)
    style["light"]["sidebar"] = "oklch(0.23 0.006 280)"
    style["light"]["sidebar-foreground"] = "oklch(0.95 0.004 280)"
    style["light"]["sidebar-accent"] = "oklch(0.3 0.008 280)"
    style["light"]["sidebar-accent-foreground"] = "oklch(0.97 0.003 280)"
    return style


def test_dark_sidebar_on_a_light_page_needs_a_muted_remap(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    style = _dark_sidebar(neutral)
    failures = [(f.mode, f.fg, f.bg) for f in styles.contrast_failures(style)]
    assert ("light", "muted-foreground", "sidebar") in failures
    style["extra_css"] = [
        _rule('[data-mini="shell-sidebar"] [class*=" text-muted-foreground"]', mode="light", color="oklch(0.78 0.008 280)")
    ]
    assert styles.contrast_failures(style) == []


def test_a_weak_muted_remap_is_reported(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    style = _dark_sidebar(neutral)
    style["extra_css"] = [
        _rule('[data-mini="shell-sidebar"] [class*=" text-muted-foreground"]', mode="light", color="oklch(0.4 0 0)")
    ]
    assert [(f.mode, f.fg, f.bg) for f in styles.contrast_failures(style)] == [
        ("light", "muted-foreground", "sidebar")
    ]


def test_a_remap_outside_the_sidebar_surfaces_does_not_excuse_the_token(
    styles: ModuleType, neutral: Dict[str, Any]
) -> None:
    style = _dark_sidebar(neutral)
    style["extra_css"] = [
        _rule('[data-mini="row"] [class*=" text-muted-foreground"]', mode="light", color="oklch(0.78 0.008 280)")
    ]
    assert ("light", "muted-foreground", "sidebar") in {
        (f.mode, f.fg, f.bg) for f in styles.contrast_failures(style)
    }


def test_placeholder_pseudo_element_is_an_allowed_selector(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    rule = _rule('[data-mini="row"] [class*="placeholder:text-muted-foreground"]::placeholder', color="oklch(0.78 0 0)")
    assert styles.load_style(_write(tmp_path, _variant(neutral, extra_css=[rule])))["slug"] == "calm-paper"


# --- build_styles CLI ---

def test_check_passes_on_a_fresh_copy(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    root = _copy_skill(tmp_path)
    assert build_styles.main(["--check"], skill_root=root) == 0
    assert "styles are fresh" in capsys.readouterr().out
    assert no_subprocess == []


def test_check_fails_after_a_one_byte_edit(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    root = _copy_skill(tmp_path)
    dist = root / "styles" / "dist" / "neutral-house.css"
    dist.write_bytes(dist.read_bytes() + b" ")
    assert build_styles.main(["--check"], skill_root=root) == 1
    assert "styles/dist/neutral-house.css" in capsys.readouterr().err


def test_check_fails_when_a_generated_file_is_missing(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    root = _copy_skill(tmp_path)
    (root / "gallery" / "src" / "gallery" / "style-list.json").unlink()
    assert build_styles.main(["--check"], skill_root=root) == 1
    assert "style-list.json" in capsys.readouterr().err


def test_build_regenerates_outputs_byte_for_byte(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    root = _copy_skill(tmp_path)
    outputs = [*sorted((root / "styles" / "dist").glob("*.css")),
               root / "gallery" / "src" / "styles" / "mini-tokens.css",
               root / "gallery" / "src" / "styles" / "gallery-styles.css",
               root / "gallery" / "src" / "gallery" / "style-list.json"]
    expected = [p.read_bytes() for p in outputs]
    for path in outputs:
        path.write_text("stale", encoding="utf-8")
    assert build_styles.main([], skill_root=root) == 0
    assert "styles built: 8" in capsys.readouterr().out
    assert [p.read_bytes() for p in outputs] == expected


def test_style_list_is_slug_and_name_in_display_order() -> None:
    data = json.loads((SKILL_DIR / "gallery" / "src" / "gallery" / "style-list.json").read_text())
    assert data[0] == {"slug": "neutral-house", "name": "Neutral House"}


def test_build_writes_nothing_on_a_contrast_failure(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    root = _copy_skill(tmp_path)
    source = root / "styles" / "neutral-house.json"
    data = json.loads(source.read_text())
    data["light"]["muted-foreground"] = "oklch(0.8 0.01 250)"
    source.write_text(json.dumps(data), encoding="utf-8")
    dist = root / "styles" / "dist" / "neutral-house.css"
    before = dist.read_bytes()
    assert build_styles.main([], skill_root=root) == 1
    err = capsys.readouterr().err
    assert "neutral-house light: muted-foreground on background" in err
    assert ":1 < 4.5:1" in err
    assert dist.read_bytes() == before


def test_unknown_source_slug_and_missing_dir_exit_2(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str]
) -> None:
    root = _copy_skill(tmp_path)
    shutil.copy(root / "styles" / "neutral-house.json", root / "styles" / "bogus.json")
    assert build_styles.main(["--check"], skill_root=root) == 2
    (root / "styles" / "bogus.json").unlink()
    shutil.rmtree(root / "styles")
    assert build_styles.main([], skill_root=root) == 2


def test_check_file_passes_on_generated_css(
    build_styles: ModuleType, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    path = SKILL_DIR / "styles" / "dist" / "neutral-house.css"
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 0
    assert f"{path}: passes AA" in capsys.readouterr().out


@pytest.mark.parametrize("slug", sorted(p.stem for p in (STYLES_DIR / "dist").glob("*.css")))
def test_check_file_passes_every_shipped_tokens_file(
    build_styles: ModuleType, no_subprocess: List[str], capsys: pytest.CaptureFixture, slug: str
) -> None:
    path = STYLES_DIR / "dist" / f"{slug}.css"
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 0, capsys.readouterr().err


def test_every_slug_has_a_shipped_tokens_file(styles: ModuleType) -> None:
    assert sorted(p.stem for p in (STYLES_DIR / "dist").glob("*.css")) == sorted(styles.SLUGS)


def test_check_file_fails_when_split_tone_sidebar_remap_is_weakened(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    text = (STYLES_DIR / "dist" / "split-tone.css").read_text()
    weak = text.replace("{ color: oklch(0.78 0.008 280); }", "{ color: oklch(0.4 0.008 280); }")
    assert weak != text
    path = tmp_path / "split-tone.css"
    path.write_text(weak, encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "light: muted-foreground on sidebar" in capsys.readouterr().err


def test_parse_extra_css_round_trips_the_rendered_rules(styles: ModuleType) -> None:
    source = styles.load_style(STYLES_DIR / "split-tone.json")
    parsed = styles.parse_extra_css(styles.render_app_css(source))
    assert parsed[2:] == source["extra_css"]


def test_trailing_declaration_without_semicolon_is_gated(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    assert styles.tokens_failures(css + "\nhtml:root { --muted-foreground: oklch(0.8 0.01 250) }\n",
                                  "t.css", "neutral-house")
    assert styles.tokens_failures(css + "\nhtml.dark { --ring: oklch(0.25 0.01 250) }", "t.css", "neutral-house")


def test_declaration_separator_forms_are_all_read(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    for block in (
        "html:root { --a: 1;; --muted-foreground: oklch(0.8 0.01 250); }",
        "html:root{--muted-foreground:oklch(0.8 0.01 250)}",
        "html:root {\n  --muted-foreground :\n    oklch(0.8 0.01 250)\n}",
    ):
        assert styles.tokens_failures(css + "\n" + block + "\n", "t.css", "neutral-house"), block


def test_check_file_fails_on_a_weak_hand_edit(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    text = (SKILL_DIR / "styles" / "dist" / "neutral-house.css").read_text()
    weak = text.replace("--muted-foreground: oklch(0.5 0.01 250)", "--muted-foreground: oklch(0.8 0.01 250)", 1)
    assert weak != text
    path = tmp_path / "tokens.css"
    path.write_text(weak, encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "light: muted-foreground on background" in capsys.readouterr().err


def test_check_file_fails_on_a_missing_token(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    lines = (SKILL_DIR / "styles" / "dist" / "neutral-house.css").read_text().splitlines()
    path = tmp_path / "tokens.css"
    path.write_text("\n".join(line for line in lines if not line.strip().startswith("--ring:")), encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "ring" in capsys.readouterr().err


def test_check_file_on_a_missing_path_is_a_usage_error(build_styles: ModuleType, tmp_path: Path) -> None:
    assert build_styles.main(["--check-file", str(tmp_path / "nope.css")], skill_root=SKILL_DIR) == 2


def test_conflicting_flags_are_a_usage_error(build_styles: ModuleType) -> None:
    assert build_styles.main(["--check", "--check-file", "x.css"], skill_root=SKILL_DIR) == 2


def test_check_file_applies_a_later_override_block(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    text = (SKILL_DIR / "styles" / "dist" / "neutral-house.css").read_text()
    path = tmp_path / "tokens.css"
    path.write_text(text + "\nhtml:root { --muted-foreground: oklch(0.8 0.01 250); }\n", encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "light: muted-foreground on background" in capsys.readouterr().err
    path.write_text(text + "\nhtml.dark { --ring: oklch(0.25 0.01 250); }\n", encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "dark: ring on background" in capsys.readouterr().err


def test_later_override_can_repair_an_earlier_weak_block(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    css = styles.render_app_css(neutral)
    weak = css.replace("--muted-foreground: oklch(0.5 0.01 250)", "--muted-foreground: oklch(0.8 0.01 250)", 1)
    assert styles.tokens_failures(weak, "t.css", "neutral-house")
    fixed = weak + "\nhtml:root { --muted-foreground: oklch(0.5 0.01 250); }\n"
    assert styles.tokens_failures(fixed, "t.css", "neutral-house") == []


def test_check_file_rejects_out_of_range_colours_quickly(
    build_styles: ModuleType, tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    text = (SKILL_DIR / "styles" / "dist" / "neutral-house.css").read_text()
    path = tmp_path / "tokens.css"
    path.write_text(text + "\nhtml:root { --primary: oklch(0.5 " + "9" * 400 + " 205); }\n", encoding="utf-8")
    assert build_styles.main(["--check-file", str(path)], skill_root=SKILL_DIR) == 1
    assert "finite" in capsys.readouterr().err


# --- the real sources ---

STUDIED_FROM = {
    "neutral-house": [],
    "calm-paper": ["granola", "craft"],
    "airy-white": ["notion", "things"],
    "cool-tool": ["linear", "figma"],
    "dense-dark": ["tableplus", "obsidian"],
    "glass-launcher": ["raycast"],
    "split-tone": ["fantastical"],
    "ink-panel": ["sentry"],
}
APP_DISPLAY_NAMES = ("Linear", "Things", "Raycast", "Craft", "Obsidian", "TablePlus",
                     "Fantastical", "Notion", "Granola", "Figma", "Sentry")


def test_every_source_exists_and_stems_equal_slugs(styles: ModuleType) -> None:
    stems = sorted(p.stem for p in STYLES_DIR.glob("*.json"))
    assert stems == sorted(styles.SLUGS)
    assert list(styles.load_styles(STYLES_DIR)) == list(styles.SLUGS)


@pytest.mark.parametrize("slug", list(STUDIED_FROM))
def test_real_source_validates_and_passes_the_gate(styles: ModuleType, slug: str) -> None:
    style = styles.load_style(STYLES_DIR / f"{slug}.json")
    assert style["slug"] == slug
    assert styles.contrast_failures(style) == []


@pytest.mark.parametrize("slug", list(STUDIED_FROM))
def test_extra_css_rules_that_set_both_colours_keep_text_readable(styles: ModuleType, slug: str) -> None:
    for rule in styles.load_style(STYLES_DIR / f"{slug}.json")["extra_css"]:
        declared = rule["declarations"]
        if "color" in declared and "background-color" in declared:
            if "var(" in declared["color"] + declared["background-color"]:
                continue  # token pairs are covered by the contrast gate
            ratio = styles.contrast_ratio(declared["color"], declared["background-color"])
            assert ratio >= styles.AA_TEXT, f"{slug} {rule['selector']}: {ratio:.2f}:1"


@pytest.mark.parametrize("tint", ["added", "removed", "pending"])
def test_dense_dark_selected_staged_cells_keep_their_tint(styles: ModuleType, tint: str) -> None:
    style = styles.load_style(STYLES_DIR / "dense-dark.json")
    selected = '[data-mini="row"][aria-selected="true"] [data-mini="cell"]'
    selectors = [r["selector"] for r in style["extra_css"]]
    rule = style["extra_css"][selectors.index(f'{selected}[data-tint="{tint}"]')]
    assert rule["mode"] == "both"
    assert rule["declarations"] == {
        "background-color": f"var(--mini-{tint})",
        "color": "var(--foreground)",
    }
    assert selectors.index(rule["selector"]) > selectors.index(selected)


def test_dense_dark_selected_tinted_cells_restore_muted_text(styles: ModuleType) -> None:
    style = styles.load_style(STYLES_DIR / "dense-dark.json")
    muted = '[data-mini="row"][aria-selected="true"] [class*="text-muted-foreground"]'
    tinted = '[data-mini="row"][aria-selected="true"] [data-mini="cell"][data-tint] [class*="text-muted-foreground"]'
    selectors = [r["selector"] for r in style["extra_css"]]
    rule = style["extra_css"][selectors.index(tinted)]
    assert rule["mode"] == "both"
    assert rule["declarations"] == {"color": "var(--muted-foreground)"}
    # more specific than the white rule (one extra attribute pair), so it wins wherever it matches
    assert selectors.index(muted) < selectors.index(tinted)
    assert tinted.count("[") > muted.count("[")


def test_staged_table_cells_expose_their_staged_state() -> None:
    source = (STYLES_DIR.parent / "gallery/src/patterns/staged-table-edit/staged-table.tsx").read_text()
    assert "data-tint={stagedState}" in source
    for state in ("added", "removed", "pending"):
        assert f'"{state}"' in source


def test_dense_dark_selected_cells_set_a_background_with_their_text_colour(styles: ModuleType) -> None:
    # staged-table tints selected cells with bg-accent, which is pale in light mode
    style = styles.load_style(STYLES_DIR / "dense-dark.json")
    rules = [r for r in style["extra_css"]
             if r["selector"] == '[data-mini="row"][aria-selected="true"] [data-mini="cell"]']
    assert len(rules) == 1 and rules[0]["mode"] == "both"
    declared = rules[0]["declarations"]
    assert styles.contrast_ratio(declared["color"], declared["background-color"]) >= styles.AA_TEXT


@pytest.mark.parametrize("slug", list(STUDIED_FROM))
def test_real_source_studied_from(styles: ModuleType, slug: str) -> None:
    assert styles.load_style(STYLES_DIR / f"{slug}.json")["studied_from"] == STUDIED_FROM[slug]


def test_no_studied_app_name_appears_in_generated_output() -> None:
    pattern = re.compile(r"\b(" + "|".join(APP_DISPLAY_NAMES) + r")\b")
    files = sorted((STYLES_DIR / "dist").glob("*.css")) + [
        SKILL_DIR / "gallery" / "src" / "styles" / "gallery-styles.css",
        SKILL_DIR / "gallery" / "src" / "gallery" / "style-list.json",
    ]
    for path in files:
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
    for source in STYLES_DIR.glob("*.json"):
        name = json.loads(source.read_text(encoding="utf-8"))["name"]
        assert not pattern.search(name), source.name


def test_style_list_lists_every_style_in_slug_order(styles: ModuleType) -> None:
    data = json.loads((SKILL_DIR / "gallery" / "src" / "gallery" / "style-list.json").read_text())
    loaded = styles.load_styles(STYLES_DIR)
    assert [entry["slug"] for entry in data] == list(styles.SLUGS)
    assert data == [{"slug": s, "name": loaded[s]["name"]} for s in styles.SLUGS]


def test_ink_panel_wraps_motion_hover_and_forced_colors_rules() -> None:
    css = (STYLES_DIR / "dist" / "ink-panel.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert "@media (hover: hover)" in css
    assert "@media (forced-colors: active)" in css
    assert "Sentry" not in css


# --- outlines, press motion and media-guarded rules ---

def _load_with_rule(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, rule: Dict[str, Any]) -> Path:
    path = _write(tmp_path, _variant(neutral, extra_css=[rule]))
    styles.load_style(path)
    return path


def _reject_rule(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, rule: Dict[str, Any]
) -> str:
    path = _write(tmp_path, _variant(neutral, extra_css=[rule]))
    with pytest.raises(styles.StyleError) as err:
        styles.load_style(path)
    message = str(err.value)
    assert path.name in message and "extra_css[0]" in message
    return message


GOOD_VALUES = [
    ("border-width", "2px"), ("border-width", "0"), ("outline-width", "2px"),
    ("outline-offset", "3px"), ("outline-offset", "-2px"), ("outline-offset", "0"),
    ("border-style", "solid"), ("border-style", "none"), ("outline-style", "solid"),
    ("transform", "none"), ("transform", "translate(3px, 3px)"), ("transform", "translate(-1px, -1px)"),
    ("transform", "translate(0, 0)"), ("transform", "translate(8px,-8px)"),
    ("transition", "none"), ("transition", "transform 120ms"),
    ("transition", "transform 120ms ease-out, box-shadow 120ms ease-out"),
    ("transition", "opacity 0s linear"), ("transition", "color 0.2s ease-in-out"),
    ("transition", "transform 1ms, box-shadow 2ms, background-color 3ms, border-color 4ms"),
    ("transition-duration", "0s"), ("transition-duration", "200ms"), ("transition-duration", "0.1s"),
    ("translate", "none"),
]
BAD_VALUES = [
    ("transition", "all 2s", "must name what it moves"),
    ("transition", "all 100ms", "must name what it moves"),
    ("transition", "transform 2s", "at most 200ms"),
    ("transition", "transform 201ms", "at most 200ms"),
    ("transition", "transform 0.3s", "at most 200ms"),
    ("transition", "transform 120ms bounce", "easing"),
    ("transition", "transform", "<property> <time>"),
    ("transition", "transform 120ms, ", "<property> <time>"),
    ("transition", "transform 1ms, box-shadow 1ms, opacity 1ms, color 1ms, border-color 1ms", "at most four"),
    ("transition-duration", "201ms", "at most 200ms"),
    ("translate", "1px", "none"),
    ("translate", "1px 2px", "none"),
    ("transition-duration", "fast", "time"),
    ("transform", "scale(2)", "may only translate"),
    ("transform", "rotate(1deg)", "may only translate"),
    ("transform", "translate(9px, 0)", "at most 8px"),
    ("transform", "translate(0, -9px)", "at most 8px"),
    ("transform", "translate(1em, 0)", "px"),
    ("transform", "translate(1px)", "may only translate"),
    ("border-style", "dashed", "solid or none"),
    ("outline-style", "dotted", "solid or none"),
    ("border-width", "thin", "length"),
    ("border-width", "-1px", "length"),
    ("outline-width", "2px 3px", "length"),
    ("outline-offset", "- 2px", "length"),
    ("outline-offset", "3%", "length"),
]


@pytest.mark.parametrize(("prop", "value"), GOOD_VALUES)
def test_new_property_grammars_accept_good_forms(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, prop: str, value: str
) -> None:
    rule = {"selector": '[data-slot="button"]', "mode": "both", "declarations": {prop: value}}
    _load_with_rule(styles, neutral, tmp_path, rule)


@pytest.mark.parametrize(("prop", "value", "reason"), BAD_VALUES)
def test_new_property_grammars_reject_bad_forms_naming_property_and_reason(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, prop: str, value: str, reason: str
) -> None:
    rule = {"selector": '[data-slot="button"]', "mode": "both", "declarations": {prop: value}}
    message = _reject_rule(styles, neutral, tmp_path, rule)
    assert prop in message
    assert reason in message


@pytest.mark.parametrize(("prop", "value"), [
    ("transform", "translate(url(x), 0)"), ("border-width", "2px !important"),
    ("transition", "transform 1ms; color: red"), ("outline-width", "'2px'"), ("transform", "none\\"),
])
def test_old_value_bans_still_cover_new_properties(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, prop: str, value: str
) -> None:
    rule = {"selector": '[data-slot="button"]', "mode": "both", "declarations": {prop: value}}
    _reject_rule(styles, neutral, tmp_path, rule)


def test_motion_properties_are_the_three_motion_names(styles: ModuleType) -> None:
    assert set(styles.MOTION_PROPERTIES) == {"transform", "transition", "transition-duration"}


@pytest.mark.parametrize("media", ["hover", "forced-colors"])
def test_media_key_accepts_hover_and_forced_colors(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, media: str
) -> None:
    rule = dict(_rule('[data-mini="row"]', opacity="1"), media=media)
    _load_with_rule(styles, neutral, tmp_path, rule)


@pytest.mark.parametrize("media", ["print", "", None, 1, "Hover"])
def test_media_key_rejects_other_values(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, media: Any
) -> None:
    rule = dict(_rule('[data-mini="row"]', opacity="1"), media=media)
    message = _reject_rule(styles, neutral, tmp_path, rule)
    assert "media" in message and "forced-colors" in message


def test_unknown_rule_key_is_rejected(styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path) -> None:
    rule = dict(_rule('[data-mini="row"]', opacity="1"), query="hover")
    _reject_rule(styles, neutral, tmp_path, rule)


def test_motion_with_forced_colors_is_rejected(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    rule = dict(_rule('[data-slot="button"]', transition="transform 120ms"), media="forced-colors")
    message = _reject_rule(styles, neutral, tmp_path, rule)
    assert "forced-colors" in message


@pytest.mark.parametrize("selector", [
    '[data-slot="button"]',
    '[data-slot="button"][data-variant="default"]:hover',
    '[data-slot="button"]:active',
    '[data-mini="row"]:active',
    '[data-slot="button"][data-mini-pressed]',
    '[data-mini="panel"] [data-slot="button"]:focus-visible',
])
def test_slot_and_active_selectors_are_accepted(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, selector: str
) -> None:
    _load_with_rule(styles, neutral, tmp_path, _rule(selector, opacity="1"))


@pytest.mark.parametrize("selector", [
    '[data-slot="button"]:not([disabled])',
    '[data-slot="button"]:focus',
    '[data-slot="button"], [data-slot="toggle"]',
    '[data-slot="button"]:disabled',
    '.x [data-slot="button"]',
])
def test_disallowed_selectors_stay_rejected(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path, selector: str
) -> None:
    _reject_rule(styles, neutral, tmp_path, _rule(selector, opacity="1"))


def test_selector_without_a_hook_names_both_hooks(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    message = _reject_rule(styles, neutral, tmp_path, _rule("[data-mini-pressed]", opacity="1"))
    assert "[data-mini=" in message and "[data-slot=" in message


def test_pseudo_class_error_text_names_active_and_data_slot(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    message = _reject_rule(styles, neutral, tmp_path, _rule('[data-slot="button"]:focus', opacity="1"))
    assert ":active" in message and "[data-slot=" in message


def _render_both(styles: ModuleType, neutral: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, str]:
    style = _variant(neutral, extra_css=rules)
    other = _variant(neutral, slug="airy-white", name="Airy White")
    return {
        "app": styles.render_app_css(style),
        "gallery": styles.render_gallery_css({"neutral-house": neutral, "calm-paper": style, "airy-white": other}),
    }


def _prefixes(mode: str) -> Dict[str, str]:
    app = {"both": "", "light": "html:not(.dark) ", "dark": "html.dark "}[mode]
    x = 'html[data-mini-style="calm-paper"]'
    gallery = {"both": f"{x} ", "light": f"{x}:not(.dark) ", "dark": f"{x}.dark "}[mode]
    return {"app": app, "gallery": gallery}


MOTION_QUERY = "(prefers-reduced-motion: no-preference)"
HOVER_MOTION_QUERY = "(hover: hover) and (prefers-reduced-motion: no-preference)"


@pytest.mark.parametrize(("rule", "mode", "query", "inner"), [
    (_rule('[data-slot="button"]', "both", transition="transform 120ms ease-out"),
     "both", MOTION_QUERY, 'transition: transform 120ms ease-out;'),
    (_rule('[data-slot="button"]:hover', "light", transform="translate(-1px, -1px)"),
     "light", HOVER_MOTION_QUERY, 'transform: translate(-1px, -1px);'),
    (_rule('[data-slot="button"][data-mini-pressed]', "dark", transform="translate(3px, 3px)"),
     "dark", MOTION_QUERY, 'transform: translate(3px, 3px);'),
    (dict(_rule('[data-slot="button"]', "both", transform="translate(1px, 1px)"), media="hover"),
     "both", HOVER_MOTION_QUERY, 'transform: translate(1px, 1px);'),
    (dict(_rule('[data-slot="button"]', "both", box_shadow="4px 4px 0 var(--foreground)"), media="hover"),
     "both", "(hover: hover)", 'box-shadow: 4px 4px 0 var(--foreground);'),
    (dict(_rule('[data-mini="row"][aria-selected="true"]', "light", outline_width="2px"), media="forced-colors"),
     "light", "(forced-colors: active)", 'outline-width: 2px;'),
])
def test_wrapped_rules_render_in_the_right_media_block_with_the_prefix_inside(
    styles: ModuleType, neutral: Dict[str, Any], rule: Dict[str, Any], mode: str, query: str, inner: str
) -> None:
    for where, css in _render_both(styles, neutral, [rule]).items():
        selector = _prefixes(mode)[where] + rule["selector"]
        assert f"\n@media {query} {{\n  {selector} {{ {inner} }}\n}}\n" in css
        assert f"\n{selector} {{" not in css


@pytest.mark.parametrize("declarations", [
    {"transition": "none"},
    {"transform": "none", "border_color": "var(--foreground)"},
    {"translate": "none", "transition": "none", "box_shadow": "3px 3px 0 var(--foreground)"},
    {"transition_duration": "0s"},
])
def test_motion_free_rules_are_not_wrapped_in_the_reduced_motion_query(
    styles: ModuleType, neutral: Dict[str, Any], declarations: Dict[str, str]
) -> None:
    rule = _rule('[data-slot="button"]', **declarations)
    for css in _render_both(styles, neutral, [rule]).values():
        assert "@media" not in css


def test_motion_free_rule_keeps_its_own_media_query(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    rule = dict(_rule('[data-slot="button"]:hover', transition="none"), media="hover")
    for css in _render_both(styles, neutral, [rule]).values():
        assert "@media (hover: hover) {" in css
        assert "prefers-reduced-motion" not in css


def test_motion_free_rule_may_use_forced_colors(
    styles: ModuleType, neutral: Dict[str, Any], tmp_path: Path
) -> None:
    rule = dict(_rule('[data-slot="button"]', transform="none"), media="forced-colors")
    _load_with_rule(styles, neutral, tmp_path, rule)


def test_real_motion_stays_wrapped_beside_a_motion_free_declaration(
    styles: ModuleType, neutral: Dict[str, Any]
) -> None:
    rule = _rule('[data-slot="button"]', transition_duration="0s", transform="translate(3px, 3px)")
    for css in _render_both(styles, neutral, [rule]).values():
        assert f"@media {MOTION_QUERY} {{" in css


def test_ink_panel_base_control_rules_are_motion_free_and_precede_the_wrapped_transition() -> None:
    css = (STYLES_DIR / "dist" / "ink-panel.css").read_text(encoding="utf-8")
    for selector in ('[data-slot="button"][data-variant="default"]', '[data-slot="toggle"]',
                     '[data-slot="toggle-group-item"]'):
        plain = re.search(
            rf"^{re.escape(selector)} \{{[^}}]*\btranslate: none;[^}}]*\btransition: none;[^}}]*\}}$", css, re.M)
        wrapped = re.search(
            rf"^@media \(prefers-reduced-motion: no-preference\) \{{\n  {re.escape(selector)} \{{ transition: "
            rf"transform 120ms ease-out, box-shadow 120ms ease-out; \}}", css, re.M)
        assert plain and wrapped, selector
        assert plain.start() < wrapped.start(), selector


@pytest.mark.parametrize("variant", ["ghost", "link"])
def test_ink_panel_ghost_and_link_buttons_stay_still_without_motion_queries(variant: str) -> None:
    css = (STYLES_DIR / "dist" / "ink-panel.css").read_text(encoding="utf-8")
    selector = f'[data-slot="button"][data-variant="{variant}"]'
    plain = re.search(rf"^{re.escape(selector)} \{{ translate: none; transition: none; \}}$", css, re.M)
    assert plain, selector


def test_a_plain_rule_is_not_wrapped_and_a_wrapped_one_does_not_leak(
    styles: ModuleType, neutral: Dict[str, Any]
) -> None:
    rules = [_rule('[data-slot="button"]', border_width="2px"),
             _rule('[data-slot="button"]:active', outline_offset="3px")]
    for css in _render_both(styles, neutral, rules).values():
        assert "@media" not in css
    app = _render_both(styles, neutral, rules)["app"]
    assert '\n[data-slot="button"] { border-width: 2px; }\n' in app
    assert '\n[data-slot="button"]:active { outline-offset: 3px; }\n' in app


def test_each_wrapped_entry_gets_its_own_block_in_source_order(
    styles: ModuleType, neutral: Dict[str, Any]
) -> None:
    rules = [
        _rule('[data-slot="button"]', opacity="1"),
        dict(_rule('[data-slot="button"]', box_shadow="none"), media="hover"),
        _rule('[data-slot="toggle"]', transition="transform 120ms"),
        _rule('[data-slot="toggle"]', opacity="1"),
        dict(_rule('[data-slot="card"]', outline_width="2px"), media="forced-colors"),
    ]
    app = _render_both(styles, neutral, rules)["app"]
    assert app.count("@media") == 3
    positions = [
        app.index('\n[data-slot="button"] { opacity: 1; }'),
        app.index("@media (hover: hover) {"),
        app.index("@media (prefers-reduced-motion: no-preference) {"),
        app.index('\n[data-slot="toggle"] { opacity: 1; }'),
        app.index("@media (forced-colors: active) {"),
    ]
    assert positions == sorted(positions)


def test_parse_extra_css_returns_the_rule_inside_a_media_block(
    styles: ModuleType, neutral: Dict[str, Any]
) -> None:
    rule = dict(_rule('[data-mini="row"][aria-selected="true"]', "light", outline_width="2px"),
                media="forced-colors")
    plain = _rule('[data-mini="row"]', "dark", opacity="1")
    css = styles.render_app_css(_variant(neutral, extra_css=[rule, plain]))
    assert "@media (forced-colors: active) {" in css
    parsed = styles.parse_extra_css(css)
    assert parsed[2:] == [_rule('[data-mini="row"][aria-selected="true"]', "light", outline_width="2px"), plain]


@pytest.mark.parametrize("slug", [
    "neutral-house", "calm-paper", "airy-white", "cool-tool", "dense-dark", "glass-launcher", "split-tone",
])
def test_existing_sources_render_to_the_committed_dist_bytes(styles: ModuleType, slug: str) -> None:
    rendered = styles.render_app_css(styles.load_style(STYLES_DIR / f"{slug}.json"))
    assert rendered.encode("utf-8") == (STYLES_DIR / "dist" / f"{slug}.css").read_bytes()
