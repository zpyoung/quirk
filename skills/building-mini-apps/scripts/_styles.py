"""Style sources for building-mini-apps: validation, CSS rendering and the WCAG contrast gate.

Each visual style lives in styles/<slug>.json. This module is the one place that knows the schema,
the slug list, the generated CSS layout and the contrast rules, so build_styles.py, check_docs.py,
new_app.py and set_style.py all agree. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple

SLUGS = (
    "neutral-house", "calm-paper", "airy-white", "cool-tool",
    "dense-dark", "glass-launcher", "split-tone",
)
DEFAULT_SLUG = SLUGS[0]

SHADCN_KEYS = (
    "background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
    "primary", "primary-foreground", "secondary", "secondary-foreground", "muted",
    "muted-foreground", "accent", "accent-foreground", "destructive", "border", "input", "ring",
    "chart-1", "chart-2", "chart-3", "chart-4", "chart-5", "sidebar", "sidebar-foreground",
    "sidebar-primary", "sidebar-primary-foreground", "sidebar-accent", "sidebar-accent-foreground",
    "sidebar-border", "sidebar-ring",
)
MINI_KEYS = ("mini-accent", "mini-accent-soft", "mini-pending", "mini-added", "mini-removed")
TOKEN_KEYS = SHADCN_KEYS + MINI_KEYS
TOP_LEVEL_KEYS = ("slug", "name", "studied_from", "radius", "fonts", "font_packages",
                  "light", "dark", "extra_css")
FONT_ROLES = ("sans", "heading", "data")
MODES = ("both", "light", "dark")

BASE_FONT_SIZE = "15px"
ROW_HEIGHT = "2rem"
GAP = "0.5rem"

EXTRA_CSS_PROPERTIES = frozenset((
    "background", "background-color", "background-image", "color", "border-color",
    "border-left-color", "border-bottom-color", "border-left-width", "border-radius",
    "box-shadow", "backdrop-filter", "-webkit-backdrop-filter", "font-family", "font-weight",
    "letter-spacing", "opacity", "outline-color",
))
FONT_PACKAGE_RE = re.compile(r"^@fontsource(-variable)?/[a-z0-9-]+$")
BANNED_FONTS = ("sf pro", "sf compact", "sf mono", "new york")
FORBIDDEN_VALUE_FRAGMENTS = ("url(", "@import", "!important", ";", "{", "}", "/*")

_NUM = r"[0-9]*\.?[0-9]+"
OKLCH_RE = re.compile(
    rf"^oklch\(\s*({_NUM})\s+({_NUM})\s+({_NUM})(?:\s*/\s*({_NUM})%)?\s*\)$"
)
LENGTH_RE = re.compile(rf"^(0|{_NUM}(px|rem|em))$")
_ATTR = r"""\[[A-Za-z_][\w-]*(?:[~|^$*]?=(?:"[^"\\]*"|'[^'\\]*'|[\w.-]+))?\]"""
_COMPOUND = rf"(?:{_ATTR})+(?::hover|:focus-visible|::before|::after)*"
SELECTOR_RE = re.compile(rf"^{_COMPOUND}(?: +{_COMPOUND})*$")
HEADER_RE = re.compile(r"^/\* mini-style: ([a-z0-9-]+) sha256=([0-9a-f]{64}) \*/$")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
DECLARATION_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
ROOT_BLOCK_RE = re.compile(r"(?<![\w.#\]:-])html:root\s*\{([^}]*)\}")
DARK_BLOCK_RE = re.compile(r"(?<![\w.#\]:-])html\.dark\s*\{([^}]*)\}")

MAX_CHROMA = 0.5

AA_TEXT = 4.5
AA_UI = 3.0
CONTRAST_PAIRS: Tuple[Tuple[str, str, float], ...] = (
    ("foreground", "background", AA_TEXT),
    ("muted-foreground", "background", AA_TEXT),
    ("primary", "background", AA_TEXT),
    ("destructive", "background", AA_TEXT),
    ("card-foreground", "card", AA_TEXT),
    ("muted-foreground", "card", AA_TEXT),
    ("popover-foreground", "popover", AA_TEXT),
    ("primary-foreground", "primary", AA_TEXT),
    ("secondary-foreground", "secondary", AA_TEXT),
    ("muted-foreground", "muted", AA_TEXT),
    ("accent-foreground", "accent", AA_TEXT),
    ("sidebar-foreground", "sidebar", AA_TEXT),
    ("sidebar-primary-foreground", "sidebar-primary", AA_TEXT),
    ("sidebar-accent-foreground", "sidebar-accent", AA_TEXT),
    ("ring", "background", AA_UI),
    ("sidebar-ring", "sidebar", AA_UI),
)

Style = Dict[str, Any]
Rgb = Tuple[float, float, float]


class StyleError(ValueError):
    """A style source or generated tokens file is invalid; the message names the file and field."""


class Failure(NamedTuple):
    """One foreground/background pair that misses its contrast minimum in one mode."""

    slug: str
    mode: str
    fg: str
    bg: str
    ratio: float
    needed: float

    def __str__(self) -> str:
        return f"{self.slug} {self.mode}: {self.fg} on {self.bg} {self.ratio:.2f}:1 < {self.needed}:1"


# --- colour math ---

def parse_oklch(value: str) -> Tuple[float, float, float, float]:
    """Return (L, C, H, alpha in 0..1) for an `oklch(L C H)` or `oklch(L C H / A%)` string."""
    match = OKLCH_RE.match(value.strip()) if isinstance(value, str) else None
    if not match:
        raise StyleError(f"not an oklch(L C H) or oklch(L C H / A%) colour: {value!r}")
    lightness, chroma, hue = (float(match.group(i)) for i in (1, 2, 3))
    alpha = float(match.group(4)) if match.group(4) is not None else 100.0
    if not all(math.isfinite(n) for n in (lightness, chroma, hue, alpha)):
        raise StyleError(f"oklch components must be finite numbers: {value!r}")
    if not 0.0 <= lightness <= 1.0:
        raise StyleError(f"oklch lightness must be 0-1: {value!r}")
    if not 0.0 <= chroma <= MAX_CHROMA:
        raise StyleError(f"oklch chroma must be 0-{MAX_CHROMA}: {value!r}")
    if not 0.0 <= hue <= 360.0:
        raise StyleError(f"oklch hue must be 0-360: {value!r}")
    if not 0.0 <= alpha <= 100.0:
        raise StyleError(f"oklch alpha must be 0-100%: {value!r}")
    return lightness, chroma, hue, alpha / 100.0


def _oklab_to_linear(lightness: float, a: float, b: float) -> Rgb:
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def _in_gamut(rgb: Rgb) -> bool:
    return all(-1e-6 <= c <= 1.0 + 1e-6 for c in rgb)


def _linear_rgb(lightness: float, chroma: float, hue: float) -> Rgb:
    """Linear sRGB for an oklch colour, reducing chroma at fixed L and H until it is in gamut."""
    radians = math.radians(hue)

    def at(c: float) -> Rgb:
        return _oklab_to_linear(lightness, c * math.cos(radians), c * math.sin(radians))

    rgb = at(chroma)
    if not _in_gamut(rgb):
        low, high = 0.0, chroma
        while high - low > 1e-4:
            mid = (low + high) / 2.0
            if _in_gamut(at(mid)):
                low = mid
            else:
                high = mid
        rgb = at(low)
    return (min(1.0, max(0.0, rgb[0])), min(1.0, max(0.0, rgb[1])), min(1.0, max(0.0, rgb[2])))


def oklch_to_linear_srgb(value: str) -> Rgb:
    """Gamut-mapped linear sRGB for an oklch string; alpha is ignored."""
    lightness, chroma, hue, _ = parse_oklch(value)
    return _linear_rgb(lightness, chroma, hue)


def composite(fg: str, bg: str) -> Rgb:
    """Linear sRGB of `fg` composited over the opaque colour `bg`."""
    lightness, chroma, hue, alpha = parse_oklch(fg)
    top = _linear_rgb(lightness, chroma, hue)
    under = oklch_to_linear_srgb(bg)
    return tuple(t * alpha + u * (1.0 - alpha) for t, u in zip(top, under))  # type: ignore[return-value]


def _luminance(rgb: Rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _ratio(first: Rgb, second: Rgb) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio of `fg` (alpha composited) on `bg`."""
    return _ratio(composite(fg, bg), oklch_to_linear_srgb(bg))


def _resolved(tokens: Mapping, key: str, mode_background: Rgb) -> Rgb:
    """Linear sRGB of a token; a translucent surface is composited over the page background."""
    lightness, chroma, hue, alpha = parse_oklch(tokens[key])
    rgb = _linear_rgb(lightness, chroma, hue)
    if key == "background" or alpha >= 1.0:
        return rgb
    return tuple(c * alpha + b * (1.0 - alpha) for c, b in zip(rgb, mode_background))  # type: ignore[return-value]


def contrast_failures(style: Mapping) -> List[Failure]:
    """Every checked pair that misses its minimum, in light then dark; empty when the style passes.

    Borders and input outlines are deliberately not checked.
    """
    failures: List[Failure] = []
    slug = str(style.get("slug", "?"))
    for mode in ("light", "dark"):
        tokens = style[mode]
        page = oklch_to_linear_srgb(tokens["background"])
        for fg_key, bg_key, needed in CONTRAST_PAIRS:
            background = _resolved(tokens, bg_key, page)
            lightness, chroma, hue, alpha = parse_oklch(tokens[fg_key])
            top = _linear_rgb(lightness, chroma, hue)
            foreground = tuple(t * alpha + b * (1.0 - alpha) for t, b in zip(top, background))
            ratio = _ratio(foreground, background)  # type: ignore[arg-type]
            if ratio < needed:
                failures.append(Failure(slug, mode, fg_key, bg_key, math.floor(ratio * 100) / 100, needed))
    return failures


# --- validation ---

def _fail(source: str, field: str, problem: str) -> StyleError:
    return StyleError(f"{source}: {field}: {problem}")


def _check_text(source: str, field: str, value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value.strip() and not allow_empty):
        raise _fail(source, field, "must be a non-empty string")
    return value


def _check_value(source: str, field: str, value: Any) -> str:
    text = _check_text(source, field, value)
    lowered = text.lower()
    for fragment in FORBIDDEN_VALUE_FRAGMENTS:
        if fragment in lowered:
            raise _fail(source, field, f"must not contain {fragment!r}")
    return text


def _check_font_stack(source: str, field: str, stack: str) -> None:
    lowered = " ".join(stack.lower().split())
    for banned in BANNED_FONTS:
        if banned in lowered:
            raise _fail(source, field, f"must not name {banned!r}")


def _check_tokens(source: str, mode: str, tokens: Any) -> None:
    if not isinstance(tokens, dict):
        raise _fail(source, mode, "must be an object of tokens")
    missing = [k for k in TOKEN_KEYS if k not in tokens]
    extra = [k for k in tokens if k not in TOKEN_KEYS]
    if missing:
        raise _fail(source, mode, f"missing token(s): {', '.join(missing)}")
    if extra:
        raise _fail(source, mode, f"unknown token(s): {', '.join(extra)}")
    for key in TOKEN_KEYS:
        try:
            _, _, _, alpha = parse_oklch(tokens[key])
        except StyleError as exc:
            raise _fail(source, f"{mode}.{key}", str(exc)) from None
        if key == "background" and alpha < 1.0:
            raise _fail(source, f"{mode}.background", "alpha must be 100%")


def _check_extra_css(source: str, rules: Any) -> None:
    if not isinstance(rules, list):
        raise _fail(source, "extra_css", "must be a list")
    for index, rule in enumerate(rules):
        field = f"extra_css[{index}]"
        if not isinstance(rule, dict) or set(rule) != {"selector", "mode", "declarations"}:
            raise _fail(source, field, "must have exactly selector, mode and declarations")
        selector = rule["selector"]
        if not isinstance(selector, str) or "[data-mini=" not in selector:
            raise _fail(source, f"{field}.selector", "must contain [data-mini=")
        if "\\" in selector:
            raise _fail(source, f"{field}.selector", "must not contain a backslash")
        if not SELECTOR_RE.match(selector):
            raise _fail(
                source, f"{field}.selector",
                "may use only attribute selectors, :hover, :focus-visible, ::before, ::after "
                "and the descendant combinator (no commas)",
            )
        if rule["mode"] not in MODES:
            raise _fail(source, f"{field}.mode", f"must be one of {', '.join(MODES)}")
        declarations = rule["declarations"]
        if not isinstance(declarations, dict) or not declarations:
            raise _fail(source, f"{field}.declarations", "must be a non-empty object")
        for prop, value in declarations.items():
            if prop not in EXTRA_CSS_PROPERTIES:
                raise _fail(source, f"{field}.declarations.{prop}", "property is not allowed")
            checked = _check_value(source, f"{field}.declarations.{prop}", value)
            if "\\" in checked:
                raise _fail(source, f"{field}.declarations.{prop}",
                            "must not contain a backslash (CSS escapes can hide url( and fonts)")
            if prop == "font-family":
                _check_font_stack(source, f"{field}.declarations.{prop}", checked)


def validate_style(data: Any, source: str, stem: Optional[str] = None) -> None:
    """Raise StyleError, naming `source` and the field, when `data` is not a valid style source."""
    if not isinstance(data, dict):
        raise _fail(source, "(root)", "must be a JSON object")
    unknown = [k for k in data if k not in TOP_LEVEL_KEYS]
    missing = [k for k in TOP_LEVEL_KEYS if k not in data]
    if unknown:
        raise _fail(source, "(root)", f"unknown key(s): {', '.join(unknown)}")
    if missing:
        raise _fail(source, "(root)", f"missing key(s): {', '.join(missing)}")
    slug = _check_text(source, "slug", data["slug"])
    if slug not in SLUGS:
        raise _fail(source, "slug", f"{slug!r} is not one of {', '.join(SLUGS)}")
    if stem is not None and slug != stem:
        raise _fail(source, "slug", f"{slug!r} must equal the file name {stem!r}")
    _check_text(source, "name", data["name"])
    studied = data["studied_from"]
    if not isinstance(studied, list) or not all(isinstance(s, str) and s for s in studied):
        raise _fail(source, "studied_from", "must be a list of app slugs")
    radius = _check_text(source, "radius", data["radius"])
    if not LENGTH_RE.match(radius):
        raise _fail(source, "radius", f"must be a CSS length such as 0.5rem: {radius!r}")
    fonts = data["fonts"]
    if not isinstance(fonts, dict) or set(fonts) != set(FONT_ROLES):
        raise _fail(source, "fonts", f"must have exactly {', '.join(FONT_ROLES)}")
    for role in FONT_ROLES:
        _check_font_stack(source, f"fonts.{role}", _check_value(source, f"fonts.{role}", fonts[role]))
    packages = data["font_packages"]
    if not isinstance(packages, list):
        raise _fail(source, "font_packages", "must be a list")
    for package in packages:
        if not isinstance(package, str) or not FONT_PACKAGE_RE.match(package):
            raise _fail(source, "font_packages",
                        f"{package!r} must be an @fontsource or @fontsource-variable package")
    _check_tokens(source, "light", data["light"])
    _check_tokens(source, "dark", data["dark"])
    _check_extra_css(source, data["extra_css"])
    if slug == DEFAULT_SLUG and data["extra_css"]:
        raise _fail(source, "extra_css", f"must be empty for {DEFAULT_SLUG}: the gallery loads its CSS unscoped")


def load_style(path: Path) -> Style:
    """Read and validate one style source; the file stem must equal its slug."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StyleError(f"{path.name}: cannot read: {exc}") from None
    except json.JSONDecodeError as exc:
        raise StyleError(f"{path.name}: invalid JSON: {exc}") from None
    validate_style(data, path.name, path.stem)
    return data


def source_paths(styles_dir: Path) -> List[Path]:
    """Every styles/*.json file, sorted by name."""
    return sorted(Path(styles_dir).glob("*.json"))


def unknown_sources(styles_dir: Path) -> List[Path]:
    """Source files whose stem is not one of SLUGS."""
    return [p for p in source_paths(styles_dir) if p.stem not in SLUGS]


def load_styles(styles_dir: Path) -> Dict[str, Style]:
    """Load every present source in SLUGS order; a stem outside SLUGS raises StyleError."""
    unknown = unknown_sources(styles_dir)
    if unknown:
        raise StyleError(f"{unknown[0].name}: not one of the known styles ({', '.join(SLUGS)})")
    by_slug = {p.stem: load_style(p) for p in source_paths(styles_dir)}
    return {slug: by_slug[slug] for slug in SLUGS if slug in by_slug}


# --- rendering ---

def _declarations(items: Iterable[Tuple[str, str]], indent: str = "  ") -> List[str]:
    return [f"{indent}{name}: {value};" for name, value in items]


def _root_block(style: Style) -> List[str]:
    lines = [f"font-size: {BASE_FONT_SIZE};", ""]
    light = style["light"]
    lines += [f"--{k}: {light[k]};" for k in SHADCN_KEYS]
    lines.append(f"--radius: {style['radius']};")
    lines.append("")
    lines += [f"--{k}: {light[k]};" for k in MINI_KEYS]
    lines += [f"--mini-row-height: {ROW_HEIGHT};", f"--mini-gap: {GAP};"]
    lines += [f"--mini-font-{role}: {style['fonts'][role]};" for role in FONT_ROLES]
    return lines


def _dark_block(style: Style) -> List[str]:
    dark = style["dark"]
    lines = [f"--{k}: {dark[k]};" for k in SHADCN_KEYS]
    lines.append("")
    lines += [f"--{k}: {dark[k]};" for k in MINI_KEYS]
    return lines


def _block(selector: str, lines: List[str]) -> str:
    body = "".join(f"  {line}\n" if line else "\n" for line in lines)
    return f"{selector} {{\n{body}}}\n"


def _rule(selector: str, declarations: Mapping) -> str:
    inner = " ".join(f"{prop}: {value};" for prop, value in declarations.items())
    return f"{selector} {{ {inner} }}\n"


def _style_blocks(style: Style, root: str, dark: str, both: str, light: str, dark_prefix: str) -> List[str]:
    blocks = [
        _block(root, _root_block(style)),
        _block(dark, _dark_block(style)),
        _rule(f'{both}[data-mini="title"]', {"font-family": "var(--mini-font-heading)"})
        + _rule(f'{both}[data-mini="cell"]', {"font-family": "var(--mini-font-data)"}),
    ]
    prefixes = {"both": both, "light": light, "dark": dark_prefix}
    extra = [_rule(prefixes[r["mode"]] + r["selector"], r["declarations"]) for r in style["extra_css"]]
    if extra:
        blocks.append("".join(extra))
    return blocks


def _imports(packages: Iterable[str]) -> List[str]:
    return [f'@import "{package}";\n' for package in packages]


def render_app_css(style: Style) -> str:
    """The tokens file an app imports, led by a `mini-style` header that hashes the rest."""
    parts = _imports(style["font_packages"])
    if parts:
        parts = ["".join(parts)]
    parts += _style_blocks(style, "html:root", "html.dark", "", "html:not(.dark) ", "html.dark ")
    body = "\n".join(parts)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"/* mini-style: {style['slug']} sha256={digest} */\n{body}"


def render_gallery_css(styles: Any) -> str:
    """Every style except neutral-house, scoped under `html[data-mini-style="<slug>"]`."""
    chosen = list(styles.values() if isinstance(styles, Mapping) else styles)
    chosen = [s for s in chosen if s["slug"] != DEFAULT_SLUG]
    imports: List[str] = []
    for style in chosen:
        for line in _imports(style["font_packages"]):
            if line not in imports:
                imports.append(line)
    parts = ["".join(imports)] if imports else []
    for style in chosen:
        x = f'html[data-mini-style="{style["slug"]}"]'
        parts += _style_blocks(style, f"{x}:root", f"{x}.dark", f"{x} ", f"{x}:not(.dark) ", f"{x}.dark ")
    return "\n".join(parts)


def parse_header(text: str) -> Tuple[Optional[str], bool]:
    """Return (slug, ok): slug is None unless line 1 is a valid header; ok means the hash matches."""
    first, newline, rest = text.partition("\n")
    match = HEADER_RE.match(first)
    if not match or not newline:
        return None, False
    return match.group(1), hashlib.sha256(rest.encode("utf-8")).hexdigest() == match.group(2)


# --- hand-edited tokens files ---

def parse_tokens_css(text: str, label: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Read the effective light (`html:root`) and dark (`html.dark`) token values from a tokens file.

    Every block of a selector is applied in file order, so a later declaration overrides an earlier one
    as it does in CSS.
    """
    stripped = COMMENT_RE.sub("", text)
    found: List[Dict[str, str]] = []
    for pattern, name in ((ROOT_BLOCK_RE, "html:root"), (DARK_BLOCK_RE, "html.dark")):
        blocks = pattern.findall(stripped)
        if not blocks:
            raise StyleError(f"{label}: no {name} block")
        values: Dict[str, str] = {}
        for body in blocks:
            values.update({k[2:]: v.strip() for k, v in DECLARATION_RE.findall(body)})
        missing = [k for k in TOKEN_KEYS if k not in values]
        if missing:
            raise StyleError(f"{label}: {name} is missing token(s): {', '.join(missing)}")
        found.append(values)
    return found[0], found[1]


def tokens_failures(text: str, label: str, slug: str) -> List[Failure]:
    """Contrast failures for an app tokens file; StyleError on a missing or unparsable token."""
    light, dark = parse_tokens_css(text, label)
    style = {"slug": slug, "light": light, "dark": dark}
    for mode, tokens in (("light", light), ("dark", dark)):
        for key in TOKEN_KEYS:
            try:
                _, _, _, alpha = parse_oklch(tokens[key])
            except StyleError as exc:
                raise StyleError(f"{label}: {mode}.{key}: {exc}") from None
            if key == "background" and alpha < 1.0:
                raise StyleError(f"{label}: {mode}.background: alpha must be 100%")
    return contrast_failures(style)
