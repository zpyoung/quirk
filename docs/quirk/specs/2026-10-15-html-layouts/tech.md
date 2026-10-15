# Tech spec: page shapes for `writing-html-artifacts`

**Status**: Reviewed (one review round, fixes applied) · Logic spec: [logic.md](logic.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`.

## Architecture

Back-links: [conceptual model](logic.md#conceptual-model), [data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Shape registry and regions | new `S/scripts/htmlkit/layouts.py` | The seven shape names, per-shape region order and nav policy, nav generation, region rendering |
| Source and build | `S/scripts/htmlkit/assemble.py`, `S/scripts/htmlkit/manifest.py` | Parse `layout` and `nav`, accept the reserved `summary` slot, substitute `{{regions}}` / `{{layout}}`, inline `theme/layout.css`, record `layout` in the header, add the note line |
| Layout stylesheet | new `S/theme/layout.css`; `S/scripts/htmlkit/tokens.py` (print-light block) | All shape geometry, breakpoints and print rules |
| Layout check | new `S/scripts/htmlkit/layoutcheck.py`; `S/scripts/htmlkit/checks.py` | Fail hand-written layout CSS inside the region wrapper (tier 1) and in app sources (tier 2) |
| Kit elements | `S/vendor/kit/1.0.0/{catalog.json,kit.css,kit.js}`, `S/vendor/libraries.json` (restamp), `S/references/components.md` (regenerated) | `q-grid`, `q-panel`, `q-sidenote`, `q-compare` |
| Nav highlight | `S/theme/chrome.js` | Mark the section in view on the nav rail |
| Built-in skeletons | `S/templates/{report,components}/skeleton.html`, `S/templates/report/template.json`, `S/scripts/htmlkit/create.py` (`SKELETON`) | Switch to `{{regions}}`; move geometry into `layout.css` |
| Companion | `S/scripts/companion.py`, `S/templates/companion/skeleton.html` | `layout` in `screen.json`; question is the summary |
| Tier 2 | `S/scripts/htmlkit/app.py`, `S/templates/app/project/src/*`, `S/templates/app/rules.md` | `layout` in `quirk-app.json`, `quirk-layout.css` copy, `PageLayout` component |
| Docs | `S/SKILL.md`, `S/references/{design-reference,templates,companion}.md`, `S/templates/*/rules.md` | Seven shapes, inference, announcement, summary slot, layout elements |
| Examples and evals | `S/templates/{report,components}/examples/`, `S/templates/companion/examples/`, `S/templates/app/examples/`, new `S/evals/layout-evals.json` | One example per shape per template; the inference eval |

Technologies: Python 3.11+ stdlib (`html.parser`, `re`, `json`), plain CSS (grid, `:has()`, `:where()`), the existing light-DOM kit pattern, React 19 + Vite single-file for tier 2, Playwright via `S/scripts/verify/verify.mjs` (unchanged).

## Code references

### `S/scripts/htmlkit/assemble.py`
- `Source` dataclass `:57`; add `layout: Optional[str]` and `nav: str` (`"auto"` default).
- `parse_source` `:78`; validate `layout` and `nav` next to the `mode` check `:100-102`; pass into the constructor `:123`. Header keys are not allow-listed today, so unknown keys stay ignored.
- `_check_slots` `:275`; treat `summary` as implicitly declared by every template (see contracts).
- `build_tier1` `:303`; order of work `:327-457`. `{{head}}` assembly `:376-384`: insert `<style>` of `theme/layout.css` immediately after base.css (`:380-382`).
- `render` closure `:395`; `values` `:411-419` gains `regions` and `layout`. The header `meta` `:396-407` gains `"layout"`. `BuildResult` dict `:458-472` gains `"layout"`.
- `_frozen_versions` `:237`; add a sibling that reads `layout` from the existing output's header.
- `delivery_note` `:558`; add a `Layout:` line after the template line `:~588`.

### `S/scripts/htmlkit/manifest.py`
- `REQUIRED_PLACEHOLDERS` `:24`, `_SLOT_PLACEHOLDER` `:25`, `_tier1_problems` `:226` (slot/placeholder bidirectional rule `:264-269`). Add `{{regions}}` and `{{layout}}` as optional known placeholders.

### `S/scripts/htmlkit/checks.py`
- `run_checks` `:390-444`; hard-coded check sequence. Add `layout` after `kit` (`:436`). The signature is unchanged; the check reads the built page.
- `_Scanner` `:165`, `_scan_page` `:212`: reuse for tokenizing; `page.css` holds every non-verified `<style>` body.

### `S/scripts/htmlkit/kitcheck.py`
- `KNOWN_RULES` `:32`, `_RULES` and the assert `:842`. Any new catalog `rules` name needs an implementation here.
- `needs` `:76`: a `<q-` scan; new tags pull the kit in with no change.

### `S/scripts/htmlkit/tokens.py`
- `tokens_css` (called at `assemble.py:377`): emits light on `:root`, dark under `prefers-color-scheme` and `[data-theme="dark"]`. Add a trailing `@media print` block.

### `S/scripts/htmlkit/app.py`
- Settings merge `:221-226`, validation `:227-232`, `quirk-app.json` write `:260-263`, `quirk-tokens.css` write `:265-272`, header meta `:315-332`, `run_checks` call `:343`, `_kit_sources` `:158-175`.

### `S/scripts/companion.py`
- `SCREEN_KEYS` `:63`, `load_screen` `:665-704`, `_source_text` `:741-753` (writes the `quirk-src` header at `:746`), `_build_screen` `:779-794`.

### `S/scripts/htmlkit/create.py`
- `SKELETON` `:50-85` (one-slot skeleton for `--from` on plain HTML); `_skeleton_template` `:192-215`.

### Skeletons and templates
- `S/templates/report/skeleton.html`: geometry `:10-28` (`.q-wrap` 1440px `:11`, `.q-layout` `:18-24`, sticky aside `:24`, prose cap `:26-28`); regions `:49-54`.
- `S/templates/components/skeleton.html`: geometry `:10-19`; regions `:40-44`.
- `S/templates/companion/skeleton.html`: `.q-wrap` 960px `:12`; `main` `:44-57`.
- `S/templates/report/template.json:10` (aside description).
- `S/templates/app/project/src/theme.css:1-4` imports, `.q-grid` table class `:33-55`; `src/App.tsx:11-46` `Shell`; `src/quirk-kit.d.ts:8-22`; `src/main.tsx:6`.

### Kit
- `catalog.json` element schema validated in `kitcheck.py:156-205`; shape reference: the `q-stat` entry (`catalog.json:108-145`).
- `kit.css` convention header `:1-10`; pre-upgrade display rule `:35`; print blocks `:636-678`, `:811-821`.
- `kit.js` `define()` `:15-20`, registrations `:2585-2593`, header comment `:7`.
- Restamp: `python3 S/scripts/pins.py stamp kit 1.0.0` (`pins.py:112`). Regenerate docs: `python3 S/scripts/kit_docs.py reference`.

## Contracts & interfaces

### Shape registry — `layouts.py`
Back-link: [conceptual model](logic.md#conceptual-model).

```
CONTRACT:
LAYOUTS: tuple[str, ...] = ("report","explainer","longform","tool","comparison","dashboard","reference")
DEFAULT_LAYOUT = "report"
NAV_MODES = ("auto","on","off")
def validate_layout(value: object) -> str            # raises SourceError
def build_nav(main_html: str, *, layout: str, nav: str, reserved_ids: set[str]) -> tuple[Optional[str], str]
def render_regions(layout: str, *, summary: str, main: str, aside: str, nav: Optional[str], legacy: bool) -> str
```

- `validate_layout`: pre: any value. Post: returns the name. Error: `SourceError` whose message lists all seven names. Invariant: `LAYOUTS` order is the documented order everywhere (docs, eval, errors).
- `build_nav`: pre: `main_html` is the `main` slot text; `reserved_ids` holds every `id` already present in the summary and aside slots and the skeleton (the builder collects them, at least `main` and `quirk-data`). Post: returns `(nav_html or None, main_html)` where `main_html` is unchanged except that `h2`/`h3` lacking an `id` gain one. Ids: lowercase heading text, runs of non `[a-z0-9]` → `-`, trimmed; empty → `section`; a collision with `reserved_ids` or an earlier id gets `-2`, `-3`… Headings inside `q-panel`, `q-compare`, `q-tabs` or `q-board` are neither counted nor listed. Nav appears when `nav == "on"`, or `nav == "auto"` and (`layout == "reference"` or the counted h2s ≥ 5). Errors: `nav == "off"` with `layout == "reference"` raises `SourceError` ("reference always has its section nav"); `nav == "on"` with zero h2s raises `SourceError` ("nav needs at least one h2 in main").
- Nav markup: `<nav class="q-nav" aria-label="On this page">` (`"Sections"` on reference) holding two renderings of the same list: a `<details class="q-nav-menu">` with a `<summary>` reading "On this page" / "Sections" and an `<ol>`, and an `<ol class="q-nav-rail">`. Each is an ordered list of h2 links with nested h3 lists. `layout.css` shows the menu below the rail breakpoint and the rail at and above it; the other is `display:none`, so assistive tech meets one list. Print shows the rail copy as a plain list.
- `render_regions`: pre: `layout` in `LAYOUTS` (else `ValueError`, a programming error since the builder validated it); `summary` may be `""` only on the legacy-summary path (Cross-cutting). Post: one wrapper `<div class="q-page" data-layout="<layout>">` holding the regions in the shape's DOM order below. When `legacy` is false the main content is wrapped in `<main id="main">`; when true it is not (the legacy skeleton already wraps it). The summary region is `<section class="q-summary" aria-label="Summary">`; the aside slot is emitted as written (it is its own `<aside>`).

| Shape | DOM order (also phone and print order) |
|---|---|
| `report` | summary, nav, main, aside |
| `explainer`, `longform`, `reference`, `comparison`, `dashboard` | summary, nav, main |
| `tool` | nav, main, summary |

- Invariant: visual placement never contradicts DOM order within a row of reading; `layout.css` only places regions side by side or stacks them in DOM order. `tool`'s result follows its inputs in the DOM so the phone rule (result directly below the inputs) holds without reordering.
- An `aside` slot on any shape other than `report` raises `SourceError` ("only the report shape places an aside").

### Source header and slots
Back-links: [data flow](logic.md#data-flow), [edge cases](logic.md#edge-cases).

```
SCHEMA: source header (line 1), additions
"layout": one of LAYOUTS        (optional)
"nav":    "auto" | "on" | "off" (optional, default "auto")
```

- Pre: header passes today's validation. Post: `Source.layout` is a valid name or `None`; `Source.nav` is valid. Error: invalid value → `SourceError` → exit 2 (`quirk_html.py:41`).
- Layout resolution order at build: `Source.layout`, else the `layout` in the existing output's header, else `DEFAULT_LAYOUT`. `--upgrade` does not affect it; it concerns library versions only. When the default is used, `BuildResult["layout_defaulted"] = True`, the header records `"layout_defaulted": true`, and the note says "Layout: report (no layout named)". A rebuild whose source still names no layout and whose existing header carries `layout_defaulted` stays defaulted; naming a layout in the source clears it.
- `summary` is a reserved slot name that region-bearing templates take without it appearing in `template.json`; the companion, which is not region-bearing, rejects one. It is required for every template whose skeleton contains `{{regions}}` or `{{slot:main}}` (the legacy path). Missing → `SourceError` naming the shape and where the summary goes (text per shape from the [summary placement table](logic.md#conceptual-model)). Templates may not declare a slot named `summary` themselves (`_tier1_problems` reports it).
- Invariant: a source with no `layout` field and no prior build builds as `report`; the region structure differs from today only by the added summary region.

### Skeleton placeholders
Back-link: [conceptual model](logic.md#conceptual-model).

- `{{regions}}` (optional): replaced by `render_regions(..., legacy=False)`. The template still declares `main` (required) and may declare `aside`; with `{{regions}}` present, those two declared slots are satisfied by `{{regions}}` and their `{{slot:main}}` / `{{slot:aside}}` placeholders must be absent. `_tier1_problems` (`manifest.py:264-269`) relaxes its bidirectional slot/placeholder rule for exactly `main` and `aside` when `{{regions}}` is present; every other declared slot still needs its placeholder. A skeleton containing both `{{regions}}` and `{{slot:main}}` is invalid.
- Legacy path: a skeleton without `{{regions}}` but with `{{slot:main}}` gets `render_regions(..., legacy=True, aside="")` substituted into `{{slot:main}}`; its `{{slot:aside}}` and other slots substitute as today, outside the wrapper. Known gap: the layout check does not see a legacy skeleton's aside.
- Region-bearing skeleton: one with `{{regions}}` or `{{slot:main}}`. Only these resolve a default layout and require `summary`.
- `{{layout}}` (optional): replaced by the resolved layout name for region-bearing skeletons; for any other skeleton (the companion), by the source's `layout` or `""` when none is named.
- Neither placeholder is added to `REQUIRED_PLACEHOLDERS`; existing custom skeletons stay valid and their `verified.json` stays valid (theme files are not hashed, `manifest.py:378-386`).
- `create.py`: `SKELETON` (`:50-85`) switches to `{{regions}}`, and `_skeleton_template` writes its example with a `summary` slot (`:212-213`), so a freshly created template builds.

### Layout stylesheet — `theme/layout.css`
Back-links: [behavior](logic.md#each-shape-at-desktop-width-on-a-phone-and-in-print), [width decisions](logic.md#decisions-locked).

- Inlined into `{{head}}` for every tier-1 build after base.css, and copied into tier-2 apps as `src/quirk-layout.css`.
- Owns all page geometry: `.q-wrap` caps, region grid per `data-layout`, sticky rail and aside, phone collapse, print. Built-in skeletons keep only masthead and chrome styling.
- Observable thresholds it must produce:
  - Every shape except `dashboard`: page content max 1440px, centered. `comparison`'s `q-compare` may exceed it (see kit).
  - `dashboard`: no max width (fluid).
  - Nav rail beside main from 1100px, sticky, with its own scroll (`max-height` of the viewport) when taller than the screen; collapsed menu below 1100px, placed after the summary.
  - Report aside beside main and sticky from 900px.
  - `tool`: summary (result) beside main from 900px; below main narrower.
  - `longform`: a right margin column for `q-sidenote` from 1100px; main's content, figures included, stays within 70ch so notes never overlap it.
  - `reference`: section nav as a left pane from 900px.
  - Prose (`p, ul, ol, blockquote` in main) capped at 70ch in every shape.
  - At 375px no shape scrolls horizontally (verify's existing check).
  - `@media print`: one column in DOM order, nav shown as a plain list after the summary, aside and sidenotes inline, masthead chrome hidden.
- Specificity: rules default to `:where()`-wrapped low specificity. Rules that must beat legacy skeleton geometry (for example a custom skeleton's own `.q-wrap { max-width }`) key on `:root:has(.q-page[data-layout="dashboard"])` or similar, above one class. Sticky elements set `align-self: start` and have no ancestor with `overflow` other than `visible`/`clip`.
- Spacing comes only from `--q-space-*`; one rhythm for every shape.

### Print-light tokens — `tokens.py`
Back-link: [print decisions](logic.md#decisions-locked).

- `tokens_css` output gains one `@media print` block that re-declares every light value on `:root`, `:root[data-theme="dark"]` and `:root.wa-dark`, ordered and specific enough to beat both dark blocks. Pre/post: token values unchanged on screen. Invariant: no new token group (`GROUPS` stays as is).

### Layout check — `layoutcheck.py`
Back-links: [building blocks decisions](logic.md#decisions-locked), [edge cases](logic.md#edge-cases).

```
CONTRACT:
def check_html(html: str, *, label: str) -> list[dict]   # [{"check": "layout", "detail": "<label> line N: <msg>"}]
def check_app_sources(paths: list[Path], *, root: Path) -> list[dict]
```

- Tier 1 input: the built page, the same `html` string `run_checks` already receives. Scope: only `<style>` elements and `style=""` attributes that are descendants of the `.q-page` wrapper (slot content). `<head>` styles (tokens, base, layout, kit, skeleton) are never inspected. A page with no `.q-page` wrapper (the companion) yields no findings. `detail` cites built-page line numbers.
- Tier 2 input: file paths under the app's `src/`. Scope: `src/**/*.css` except `theme.css`, `quirk-tokens.css`, `quirk-layout.css`; and `style={{…}}` objects in `src/**/*.tsx` for the camel-cased equivalents. `detail` cites `<relative path> line N`.
- Flags any of: `display: grid | inline-grid`; any `grid-template*`, `grid`, `grid-column*`, `grid-row*`, `grid-area`; `float: left | right | inline-start | inline-end`; `columns` / `column-count`; `width`, `min-width`, `max-width` with an absolute length ≥ 400px or ≥ 25rem/em. Declarations inside `@media`/`@container` blocks are scanned like top-level ones. `width`, `min-width` and `max-width` values using `%`, `calc()`, `var()`, `min()`, `max()`, `clamp()` or viewport units are never flagged; the grid, float and column properties are flagged whatever their value.
- Detail names the property and the element to use: grid properties → "use q-grid (and q-panel for titled panels)"; widths, floats and columns → "page shapes set widths; set \"layout\" in the header".
- Errors: `check_html` never raises; CSS it cannot tokenize is skipped declaration by declaration. `check_app_sources` reports an unreadable file as a failure `{"check":"layout","detail":"cannot read <path>"}` and continues.
- Wiring: `run_checks` runs the layout check for `tier == 1` after `kit` with no new parameter; `check_artifact` inherits it. `app.py` calls `check_app_sources` after the Vite build and appends its failures to the build's checks. Failure → exit 1, like every static check.
- Invariant: kit, header, checksum and external-refs checks behave exactly as today.

### Kit elements
Back-links: [conceptual model](logic.md#conceptual-model), [responsive decisions](logic.md#decisions-locked).

Geometry for all four is CSS on element and attribute selectors in `kit.css`; nothing depends on `customElements.define` to lay out. `q-sidenote` and `q-compare` add behavior through `kit.js` upgrades and read correctly without the script.

```
SCHEMA: catalog.json entries (shape as q-stat at catalog.json:108-145)
q-grid:    parent null, interactive false, attributes [], requires [], rules []
q-panel:   parent null, interactive false,
           attributes [{name:"span", kind:"enum", values:["1","2","3","4","full"], default:"1", required:false}],
           requires [["h2","h3","h4"]], rules []
q-sidenote: parent null, interactive true, attributes [], requires [], rules []
q-compare: parent null, interactive true,
           attributes [{name:"recommended", kind:"integer", required:true}],
           requires [["table"]], rules ["compare-recommended"]
```

- `compare-recommended` is a new `KNOWN_RULES` entry implemented in `kitcheck.py`: `recommended` must be between 1 and the number of option columns (header cells of the table's first row minus the criteria column); otherwise a `kit` failure naming the allowed range.
- `q-grid`: children flow into equal columns: 1 at 700px and below, up to 2 from 701px to 1099px, up to 4 from 1100px to 1799px, up to 6 at 1800px and above (viewport widths). A child `q-panel[span]` (or any child with `data-span`) spans that many columns, clamped to the row. Gaps are `--q-space-*`.
- `q-panel`: a bordered panel (`--q-radius-md`, 1px `--q-color-border`) whose required first heading is its title. A panel with no h2–h4 fails the kit check (`requires`).
- `q-sidenote`: inline in a paragraph. Wide `longform`: floated into the right margin column, numbered with a CSS counter. Narrow: the upgrade inserts a numbered toggle button (`aria-expanded`) that shows the note in place; without the script the note reads inline in parentheses style. Print: inline.
- `q-compare`: wraps a `<table>` with options as columns. `recommended` is the 1-based option column (excluding the criteria column). At 700px and below the upgrade renders one block per option, recommended first, each a heading plus a criteria list; the table is hidden with `display:none`. Without the script the table scrolls inside its own wrapper. Above 700px, when the table's natural width exceeds the 1440px column and nothing sits beside the column it widens up to the viewport minus page gutters, centered, instead of scrolling; beside a nav rail, aside, pane or margin column, and inside `q-panel`/`q-grid`, it stays within its column and scrolls inside its own box.
- Catalog `example` for each must pass `kitcheck.check_html` (`tests/test_html_kit_check.py:57`) and contain no `<script>`.
- After editing `kit.css`/`kit.js`: restamp with `pins.py stamp kit 1.0.0`; kit version stays `1.0.0`. Consequence: pages built before the restamp fail `check` on the kit checksum until rebuilt (the same trade the 1440px baseline commit made).
- Add the four tags to `S/templates/app/project/src/quirk-kit.d.ts:8-22` (a test requires that list to equal the catalog tags).
- Every new `kit.css` rule follows the `:where()` convention or is added to the named `lifted` set in `tests/test_html_kit_elements.py:3383-3390` with a reason.

### Nav highlight — `chrome.js`
Back-link: [the nav](logic.md#the-nav).

- When a `.q-nav` exists, chrome.js sets `aria-current="location"` on exactly one rail link, the section being read, and updates it as the reader scrolls; at the bottom of the page the last link is current, so short final sections still get marked. `layout.css` styles `[aria-current]` with weight and an indicator mark, never color alone. No nav → no listener. No other chrome.js behavior changes. Tier-2 `PageLayout.tsx` applies the same rule.

### Companion
Back-link: [scope](logic.md#scope-and-non-goals).

- `SCREEN_KEYS` gains `"layout"`, validated with `validate_layout`. `_source_text` writes it into the generated `quirk-src` header.
- The companion skeleton keeps its own slots and is not region-bearing; its `question` slot is the summary region, so no `summary` slot is required. The skeleton tags its `main.q-wrap` and the masthead's `.q-wrap` with `data-layout="{{layout}}"`, which is `""` when the screen names no layout. `layout.css` widens both wrappers with selectors of the form `.q-wrap[data-layout="<shape>"]` scoped to the companion page (specificity above the skeleton's `.q-wrap { max-width: 960px }` at `companion/skeleton.html:12`, which comes later in the cascade): 1440px for every shape except `dashboard` (no cap). `data-layout=""` matches none, so an unnamed screen stays at 960px.
- The layout check does not run on companion screens: their option html and content draw mockups of layouts, not the screen's own layout.

### Tier 2
Back-link: [scope](logic.md#scope-and-non-goals).

```
SCHEMA: quirk-app.json addition
"layout": one of LAYOUTS   (optional; flag --layout on build-app overrides)
```

- `build-app` gains `--layout`, merged like `--mode` (`app.py:221-226`), validated with `validate_layout`, saved in `quirk-app.json`, recorded in the tier-2 header meta (`app.py:315-332`). Default `report`.
- Each build copies `S/theme/layout.css` to `src/quirk-layout.css` (next to the `quirk-tokens.css` write) and writes `src/quirk-page.ts` exporting the layout name. `theme.css` imports `./quirk-layout.css`. Both files are rewritten every build; edit neither by hand (same rule as `quirk-tokens.css`).
- New scaffold component `src/PageLayout.tsx`: renders the same wrapper and region DOM as `render_regions(legacy=False)` (class names, `data-layout`, region order). Props: `summary`, `children` (main), optional `aside`. It builds the nav at runtime from the rendered main content's h2/h3 with the same id, threshold and markup rules as `build_nav`, because app content exists only at runtime. `Shell` (`App.tsx:11-46`) renders each route inside `PageLayout`.
- Rename the scaffold's table class `.q-grid` (`theme.css:33-55`) and its uses to `.q-data-grid`, so it is not confused with the `<q-grid>` element. Existing app sources are never overwritten, so they keep their class.
- `check_app_sources` runs on every build; its failures join `checks.failures` (exit 1).

## Data models / schemas

Back-links: [data flow](logic.md#data-flow), [success criteria](logic.md#success-criteria).

```
SCHEMA: built page header (header.py), additions
"layout": one of LAYOUTS
"layout_defaulted": true    (only when no source or earlier build named a layout)
"legacy_summary": true      (only under the migration exemption in Cross-cutting)
```

```
SCHEMA: BuildResult additions (assemble.py:458-472)
"layout": str, "layout_defaulted": bool
```

```
SCHEMA: S/evals/layout-evals.json
{"skill_name": "writing-html-artifacts",
 "evals": [{"id": int, "prompt": str, "expected_layout": one of LAYOUTS}]}
```

- At least two prompts per shape (14 or more), unique prompts, every shape covered.

Examples (one per shape per template; the existing `example` file each `template.json` names stays as is):

```
SCHEMA: example locations
S/templates/report/examples/<shape>.src.html        (7)
S/templates/components/examples/<shape>.src.html    (7)
S/templates/companion/examples/<shape>.screen.json  (7)
S/templates/app/examples/<shape>/                   (7 overlays copied over project/ like example/, each with quirk-app.json "layout")
```

## DO-NOT-CHANGE fences

Back-link: [scope and non-goals](logic.md#scope-and-non-goals).

- `S/scripts/verify/verify.mjs` (widths `:29`, checks, report shape): print verify is deferred and screen widths are the success bar; changing verify would move the bar under the feature.
- `S/scripts/htmlkit/tokens.py` `GROUPS` and the token file schema: widths in tokens are a logic-spec non-goal.
- Kit version `1.0.0` and its directory name: tests hard-code it (`tests/test_html_kit_catalog.py:25`, `tests/test_html_kit_examples.py:~76`) and built pages record it; restamp, do not bump.
- Existing kit elements' markup contracts and behavior (`q-tabs` … `q-board`, `q-diff-note`): pages already built against them rebuild unchanged.
- `S/scripts/htmlkit/header.py` format (line 2, one JSON object): readers in `app.py`, `companion.py` and rebuilds depend on it; only add the `layout`, `layout_defaulted` and `legacy_summary` keys.
- `app.py` install flags and exit-3 paths (`:59-101`, `:274-284`): the tier-2 safety model.
- Companion server protocol (`companion.py` events, nonce, `companion.js`): the brainstorm loop depends on it.
- `REQUIRED_PLACEHOLDERS` (`manifest.py:24`): adding to it would invalidate every existing custom skeleton.

## Always / Ask / Never

- **Always**: keep DOM order summary → nav → main → aside; run `pins.py stamp kit 1.0.0` and `kit_docs.py reference` after kit edits; keep every built-in example passing `check`; use `--q-*` tokens only.
- **Ask**: before changing any locked width or threshold (1440px, 1800px, 1100px, 900px, 700px, 5 h2s); before exempting anything else from the layout check.
- **Never**: add a token group; bump the kit version; make layout geometry depend on JavaScript; edit a built file instead of its source; touch the fences above.

## Cross-cutting

Back-links: [data flow](logic.md#data-flow), [edge cases](logic.md#edge-cases).

- Security: no new network surface; offline mode and external-refs checks are unchanged. Generated heading ids are derived from text and escaped.
- Rollback: a page's layout is in its header; reverting the feature makes rebuilds ignore the field (unknown header keys are ignored).
- Migration: the logic spec requires both "a missing summary fails the build" and "a page built before this change rebuilds as report, unchanged". They reconcile this way: when the output path already holds a page whose header has no `layout` key (built before this change) and the source has no `summary` slot, the build succeeds with the summary region omitted and a `checks.warnings` entry asking for a summary, and records `"layout": "report", "legacy_summary": true` in the header. A later rebuild whose existing header carries `"legacy_summary": true` gets the same exemption, so the exemption does not lapse after the first rebuild; adding a `summary` slot clears the flag. Every other build without `summary` fails as specified.

## Testing strategy

Back-link: [success criteria](logic.md#success-criteria).

- `tests/test_html_layouts.py` (new):
  - unit: `validate_layout`, `build_nav` (thresholds, ids, collisions, panel headings excluded, reference + off error), `render_regions` DOM order per shape and legacy flag.
  - build: every example in `S/templates/{report,components}/examples/` builds via the CLI with `checks.passed`; header records `layout`; rebuild keeps it; `layout_defaulted` path and note line; missing summary error text per shape; legacy custom skeleton (from `create.py` output before this change, fixture) builds every shape.
  - layout check: each flagged property fails with the named element; head styles and companion screens are not flagged; a 300px width passes.
  - browser (gated by the `browser_ready` pattern in `tests/test_html_kit_examples.py:79-98`): `verify` passes for every report, components and companion example at 375px and 1280px; DOM-order assertion per the shape table; dashboard 4 across at 1600px and 5+ at 2560px; nav rail visible at 1280px and collapsed at 375px.
  - app examples: built and verified at 375px and 1280px only under `QUIRK_HTML_NETWORK_TESTS=1` with a browser, like `test_real_build_of_the_app_template` (`tests/test_html_app.py:628-638`).
- `tests/test_html_kit_catalog.py:32-68` `SECTION_3_4` and `:108` interactive set: add the four tags.
- `tests/test_html_kit_elements.py`: per-element behavior for the four tags (stacking widths, span, sidenote toggle and no-JS read, compare stacked view and widen), and the shared no-page-scroll fixtures.
- `tests/test_html_kit_docs.py:49`: `components.md` regenerated (`--check` not stale).
- `tests/test_htmlkit_core.py`: print block in `tokens_css`; manifest accepts `{{regions}}`/`{{layout}}`, rejects a declared `summary` slot and `{{regions}}` mixed with `{{slot:main}}`.
- `tests/test_html_companion.py`: `layout` accepted and validated in `screen.json`; companion examples per shape build.
- `tests/test_html_app.py`: `--layout` round trip in `quirk-app.json`; `quirk-layout.css` and `quirk-page.ts` written each build; `check_app_sources` failure; `.q-data-grid` rename; real build per shape under `QUIRK_HTML_NETWORK_TESTS=1`.
- `tests/test_writing_html_artifacts_skill.py`: `layout-evals.json` structure (every shape ≥ 2 prompts, unique).
- Inference eval run (manual, recorded in the branch summary): dispatch one fresh agent per prompt with the skill's SKILL.md and design reference, ask which layout it would set, score exact matches against `expected_layout`; the bar is every shape's prompts matched.
- CI runs `pytest -q` without node or browsers (`.github/workflows/test.yml`), so browser tests skip there; they must pass locally before the branch finishes.

## Non-goals

- Print rendering in verify, page-break rules, chart table-view swap in print (logic spec [deferred](logic.md#deferred-ideas)).
- Width tokens, per-section widths, slide or paged layouts.
- Runtime layout switching in the browser.
- An automated eval runner wired into pytest or CI.
