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
    _bad_lightness_above_range,
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


def test_gate_does_not_check_borders(styles: ModuleType, neutral: Dict[str, Any]) -> None:
    faint = copy.deepcopy(neutral)
    faint["light"]["border"] = faint["light"]["background"]
    faint["light"]["input"] = faint["light"]["background"]
    assert styles.contrast_failures(faint) == []


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
    assert "styles built: 7" in capsys.readouterr().out
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


# --- the seven real sources ---

STUDIED_FROM = {
    "neutral-house": [],
    "calm-paper": ["granola", "craft"],
    "airy-white": ["notion", "things"],
    "cool-tool": ["linear", "figma"],
    "dense-dark": ["tableplus", "obsidian"],
    "glass-launcher": ["raycast"],
    "split-tone": ["fantastical"],
}
APP_DISPLAY_NAMES = ("Linear", "Things", "Raycast", "Craft", "Obsidian", "TablePlus",
                     "Fantastical", "Notion", "Granola", "Figma")


def test_all_seven_sources_exist_and_stems_equal_slugs(styles: ModuleType) -> None:
    stems = sorted(p.stem for p in STYLES_DIR.glob("*.json"))
    assert stems == sorted(styles.SLUGS)
    assert list(styles.load_styles(STYLES_DIR)) == list(styles.SLUGS)


@pytest.mark.parametrize("slug", list(STUDIED_FROM))
def test_real_source_validates_and_passes_the_gate(styles: ModuleType, slug: str) -> None:
    style = styles.load_style(STYLES_DIR / f"{slug}.json")
    assert style["slug"] == slug
    assert styles.contrast_failures(style) == []


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


def test_style_list_lists_the_seven_in_slug_order(styles: ModuleType) -> None:
    data = json.loads((SKILL_DIR / "gallery" / "src" / "gallery" / "style-list.json").read_text())
    loaded = styles.load_styles(STYLES_DIR)
    assert [entry["slug"] for entry in data] == list(styles.SLUGS)
    assert data == [{"slug": s, "name": loaded[s]["name"]} for s in styles.SLUGS]
