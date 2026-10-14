# Component kit: tech spec

**Status**: Authored 2026-10-14 by the subagent-driven-development run · Logic spec: [logic.md](logic.md)

This document says where to work and what must hold. Paths are relative to the repo root. `$SKILL`
means `skills/writing-html-artifacts/` and `$KIT` means `$SKILL/vendor/kit/1.0.0/`. Line anchors are
against `088bc5e`. The sibling feature's contracts live in
`docs/quirk/specs/2026-10-13-writing-html-artifacts/tech.md`; this spec extends them and never
restates them.

Python follows the house rules there: stdlib only, 3.9+, `from __future__ import annotations`, one
JSON object on stdout per CLI call.

## 1. Files and ownership

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

| Area | Files | Change |
|---|---|---|
| Kit runtime | `$KIT/kit.js`, `$KIT/kit.css`, `$KIT/LICENSE` | new; one hand-written vanilla file each |
| Catalog | `$KIT/catalog.json` | new; not listed in `files`, so never inlined (like `vendor/webawesome/3.14.0/NOTES.md`) |
| Library registry | `$SKILL/vendor/libraries.json` | add the `kit` entry (§3.2) |
| Pins | `$SKILL/scripts/pins.py` | add `stamp`; `check` skips first-party entries |
| Manifest validation | `$SKILL/scripts/htmlkit/manifest.py` (`_library_problems`, `:100`) | accept the optional `first_party` boolean |
| Kit check and scans | `$SKILL/scripts/htmlkit/kitcheck.py` | new: catalog loading, inclusion scan, HTML check, JSX check |
| Tier-1 build | `$SKILL/scripts/htmlkit/assemble.py` (`build_tier1` `:288`, `_library_order` `:248`) | auto-include, kit CSS placement, source-side check |
| Static checks | `$SKILL/scripts/htmlkit/checks.py` (`run_checks` `:361`) | call the kit check |
| Tier-2 build | `$SKILL/scripts/htmlkit/app.py` (`build_app` `:150`, page assembly `:236-269`) | source scan, kit inlining into the bundle, JSX check |
| Tier-2 template | `$SKILL/templates/app/project/src/quirk-kit.d.ts`, `$SKILL/templates/app/rules.md` | new d.ts; rules section |
| Tokens | `$SKILL/theme/house.tokens.json` | add `color.chart-1` … `color.chart-8` |
| Verify | `$SKILL/scripts/verify/verify.mjs`, `$SKILL/scripts/htmlkit/verify_runner.py` (`run_verify` `:94`), `$SKILL/scripts/quirk_html.py` (`verify` `:268-271`) | `--no-js` mode and the `fallback` check |
| Docs generator | `$SKILL/scripts/kit_docs.py` | new: `reference`, `examples` |
| Components reference | `$SKILL/references/components.md` | new, generated; never hand-edited |
| Rules and references | `$SKILL/templates/report/rules.md`, `$SKILL/templates/components/rules.md`, `$SKILL/templates/companion/rules.md`, `$SKILL/references/design-reference.md` §9, `$SKILL/references/templates.md`, `$SKILL/references/companion.md`, `$SKILL/SKILL.md` | trim hand-wiring, link the reference (§4.9) |
| Report example | `$SKILL/templates/report/example.src.html` | rewrite onto `q-stat`, `q-chart`, `q-table` |
| Tests | see §8 | new and modified |

## 2. Architecture

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

- **The kit is a first-party library.** It lives in the vendor layout so it inherits pinning,
  checksums, license comments, the header's `libraries` map, frozen rebuilds and `--upgrade` with no
  new mechanism: `VendorStore.resolve` (`vendor.py:132`), `inline_blocks` (`vendor.py:176`),
  `_lib_checksum_failure` (`checks.py:282`), `_frozen_versions` (`assemble.py:237`). A shell block
  (the `chrome.js` route) was the alternative; it has no version, so it can't satisfy pinning.
- **One catalog per kit version**, at `$KIT/catalog.json`. Its three readers are:
  - `kitcheck.py`, which loads the catalog for the kit version the page records, or `current` when
    there is none
  - `kit_docs.py reference`, which writes `references/components.md` from the `current` catalog
  - `kit_docs.py examples`, which writes one example source per element from the same catalog
- **`kitcheck.py` owns all kit logic in Python.** `assemble.py`, `checks.py` and `app.py` call it and
  never parse q-* markup themselves. It has its own `HTMLParser` subclass that records positions with
  `getpos()`; the existing `_Scanner` (`checks.py:98`) is left alone.
- **Runtime order in a tier-1 page** (`{{body_end}}`): library JS in `_library_order` order (Chart.js,
  then `kit.js`, Alpine last), then `chrome.js`. `kit.js` therefore runs before `window.quirkData`
  exists (`chrome.js:313`) and before Alpine starts. Elements upgrade synchronously at `define`.
  Anything that needs `quirkData`, or Alpine-generated children, waits for `DOMContentLoaded`, which
  fires after every body-end script has run.
- **Tier 2 references the kit from the skill; it never copies it.** `app.py` inlines the same
  library blocks into `dist/index.html` after the Vite build. The kit's classic `<script>` runs
  before the bundle's deferred `type="module"` script, so the elements are defined before React
  first renders them. No npm dependency or lockfile change is needed.
- **The companion needs no code change.** `_build_screen` (`companion.py:779-794`) goes through
  `build_tier1`, so a screen whose `content` or option `html` holds a q-* tag gets the kit, the
  source-side check and the built-page check (`check_artifact`, `companion.py:811`) automatically.

## 3. Data models

### 3.1 Catalog: `$KIT/catalog.json`

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

SCHEMA:

```
{
  "schema": 1,
  "kit_version": "1.0.0",                 // must equal its directory name
  "global_attributes": ["id", "class", "style", "hidden", "title", "lang", "dir", "slot"],
                                          // prefixes aria-, data-, x-, :, @ also always allowed
  "elements": [
    {
      "tag": "q-chart",                   // ^q-[a-z]+(-[a-z]+)*$, unique
      "use_when": "<one line, starts 'Use when'>",
      "parent": null | "q-diff",          // required ancestor tag
      "interactive": true | false,        // false: allowed inside a companion option's html
      "attributes": [
        {"name": "summary", "required": true, "kind": "text" | "enum" | "boolean" | "number-list" | "integer" | "ident",
         "values": ["bar", "line"],       // enum only
         "default": "bar",                // optional, docs only
         "description": "<one line>"}
      ],
      "requires": [["table", "@data-from"]],
                                          // each inner list: at least one selector must match
      "rules": ["max-series"],            // named Python rules, §4.2
      "children": "<prose: the wrapped HTML this element expects>",
      "example": "<complete markup, no <script> except a q-chart options block>"
    }
  ]
}
```

`requires` selectors are a closed mini-language, matched against descendants of the element:

REGEX: `^(@[a-z-]+|[a-z][a-z0-9]*(\[[a-z-]+(=[a-z-]+)?\])?|\[[a-z-]+(=[a-z-]+)?\])$`

- `@name` matches when the element itself carries attribute `name`.
- `tag`, `tag[attr]`, `tag[attr=value]` and `[attr=value]` match a descendant.

A selector outside this grammar is a catalog-load error, so the catalog test catches it.

### 3.2 Library entry

Back-link: [Data flow](logic.md#data-flow).

CONFIG, added to `$SKILL/vendor/libraries.json`, in the shape of
`docs/quirk/specs/2026-10-13-writing-html-artifacts/tech.md` §3.2:

```
"kit": {
  "current": "1.0.0",
  "versions": {
    "1.0.0": {
      "package": "quirk-kit", "license": "MIT", "license_file": "LICENSE",
      "first_party": true,
      "files": [
        {"path": "kit.css", "kind": "css", "position": "head",     "inline": true, "sha256": "…", "inline_sha256": "…"},
        {"path": "kit.js",  "kind": "js",  "position": "body-end", "inline": true, "sha256": "…", "inline_sha256": "…"}
      ]
    }
  }
}
```

`LICENSE` is MIT, with the copyright line taken from the repo's root `LICENSE`.

### 3.3 Tokens

Back-link: [`q-chart`](logic.md#q-chart).

Add eight `[light, dark]` pairs under `color` in `theme/house.tokens.json`, `chart-1` … `chart-8`.
They are emitted as `--q-color-chart-1` … `--q-color-chart-8` by the existing `tokens.py` with no
code change. Values follow the Okabe-Ito order of `references/design-reference.md:170`. Each value is
adjusted (darkened for light, lightened for dark) only as far as needed to reach 3:1 against
`color.bg` in its own scheme. Raw `#F0E442`, `#56B4E9` and `#E69F00` fail that on the light
background, so they must change. A test asserts 3:1 for all sixteen values (§8). Timeline tones map to the
existing tokens: `success` → `good`, `warning` → `warn`, `danger` → `critical`, and `neutral` →
`text-muted`.

### 3.4 Element markup: the exact authoring contract

Back-link: [Behavior](logic.md#behavior). This table fills the logic spec's deferred "exact
attribute names". The catalog encodes it, and `references/components.md` is generated from it.

| Element | Attributes (required in **bold**) | Wrapped HTML (`requires` / rules) |
|---|---|---|
| `q-tabs` | `label` text (the tablist's accessible name) | direct-child `<section>`s, each with an `h2`–`h6` as its first element child · requires `section` · rule `heading-sections` |
| `q-chart` | **`summary`** text; `type` enum `bar` `line` `area` `donut` (default `bar`); `x` text (the column header for categories, default first column); `y` text (comma-separated column headers, default every other column); `stacked` boolean; `horizontal` boolean (bar only); `data-from` ident | a `<table>` with `<thead>` `<th>`, or `data-from`; optional child `<script type="application/json">` holding raw Chart.js options · requires `["table", "@data-from"]` · rule `max-series` |
| `q-stat` | `direction` enum `up-good` `down-good` (default `up-good`); `points` number-list (≥2 comma-separated numbers) | children marked with the global `slot` attribute: `slot="label"`, `slot="value"` and `slot="definition"` are required; `slot="delta"` is optional, and its text's leading `+`, `-`, `−` or digit sets the sign · requires `[slot=label]`, `[slot=value]`, `[slot=definition]` |
| `q-table` | `data-from` ident | a `<table>` with `<thead>`; `class="num"` on a `<th>` marks a numeric column. With `data-from`, each `<th>` binds to the row field named by its `data-key`, else by its trimmed text · requires `table` |
| `q-timeline` | none | an `<ol>` whose every `<li>` holds a `<time datetime>`; optional `data-tone` on an `<li>`: `neutral`, `success`, `warning` or `danger` · requires `ol` · rule `timeline-items` |
| `q-code` | `filename` text | `<pre><code>` · requires `pre` |
| `q-diff` | none | a `<pre>` of unified diff text, then zero or more `q-diff-note` children · requires `pre` · rule `diff-notes` |
| `q-diff-note` | **`file`** text (as in the `+++ ` header, with `b/` stripped); **`line`** integer (a new-side line number) | free text · parent `q-diff` |
| `q-board` | **`id`** ident | direct-child `<section>`s, each with an `h2`–`h6` first and then a `<ul>` of `<li>` cards; a card's identity is its `data-id`, else its trimmed text · requires `section` · rule `board-columns` |

Kinds: `ident` matches REGEX `^[A-Za-z][A-Za-z0-9_-]*$`. `integer` must be a positive integer.
`boolean` is present or absent; any value is accepted. `number-list` is comma-separated finite
numbers.

`interactive: false` applies to `q-stat`, `q-chart`, `q-timeline`, `q-diff` and `q-diff-note` (a
`q-diff` carries notes only as `q-diff-note` children). The other elements are interactive.

### 3.5 Board storage

Back-link: [`q-board`](logic.md#q-board).

- The key is `quirk-board:<slug>:<id>`. `<slug>` is the last segment of `location.pathname` with a
  trailing `.html` removed; an empty segment becomes `index`.
- SCHEMA: `{"v": 1, "authored": "<fingerprint>", "columns": [["<card id>", …], …]}`.
- `authored` is a stable string fingerprint of the authored layout: column headings plus card ids,
  in order. A stored value whose `v` or `authored` differs from the current page's is discarded and
  removed.

## 4. Contracts

### 4.1 Inclusion (`kitcheck.py`, `assemble.py`)

Back-link: [Data flow](logic.md#data-flow).

CONTRACT:

```
kitcheck.needs(text: str) -> tuple[bool, bool]          # (kit, chartjs)
kitcheck.KIT_TAG  = REGEX (?i)<q-[a-z]
kitcheck.CHART_TAG = REGEX (?i)<q-chart[\s/>]
```

- `build_tier1` runs `needs` over the **whole raw source file text**, script bodies and comments
  included. That is intentional: a JS string or an Alpine `<template>` that builds q-* markup at
  runtime must still pull the kit in.
- When `kit` is true, `kit` joins the selected libraries. When `chartjs` is true, `chartjs` joins
  too. Neither has to be in the template's `optional_libraries`. `_library_order` still rejects a
  header-declared `kit`, so the kit can't be requested by hand: it's automatic only.
- **Mechanism.** It runs as a post-step in `build_tier1`, right after `_library_order`
  (`assemble.py:342`). `_library_order`'s signature and its rejection of non-optional header
  libraries stay as they are. The post-step inserts the auto names directly, so they bypass that
  check.
- Order: template libraries, then header libraries, then `chartjs`, then `kit`, de-duplicated, with
  Alpine last.
- Kit CSS goes in `{{head}}` **after** `base.css` (`assemble.py:361`), so kit styles beat base
  element styles while template and page `<style>` still override them. Every selector in `kit.css`
  uses `:where()` for zero specificity, except where the element tag alone already suffices.
- Versions follow the existing frozen rule. A page rebuilt after it starts using q-* tags gets
  `current` for `kit` and `chartjs`. A page that drops every q-* tag drops `kit` from its header.
- A source with no `<q-` produces output that is byte-identical to today's apart from `built_at`.

### 4.2 The `kit` check (`kitcheck.py`, `checks.py`)

Back-link: [Data flow](logic.md#data-flow) step 3.

CONTRACT:

```
kitcheck.load_catalog(store: VendorStore, version: Optional[str]) -> Catalog   # raises KitError
kitcheck.check_html(text: str, catalog: Catalog, *, label: str) -> list[dict]
kitcheck.check_jsx(files: list[tuple[str, str]], catalog: Catalog) -> list[dict]   # (label, text)
run_checks(html, *, mode, tier, vendor, shells=None, kit_source: Optional[tuple[str, str]] = None) -> dict
```

- Each failure is `{"check": "kit", "detail": "<label> line <n>: <message>"}`. The dict shape is
  unchanged, so no consumer breaks. `<n>` is 1-based, from `HTMLParser.getpos()`.
- **The check is lazy.** It does nothing unless the scanned text has a q-* tag
  (`kitcheck.KIT_TAG`). Only then does it load the catalog. Pages without q-* tags, and test
  stores with no `kit` entry, behave exactly as today.
- **What `run_checks` scans.**
  - When `kit_source=(label, text)` is given, it scans that text.
  - Otherwise it scans the built page, labelled with the output file name.
  - It loads the catalog for the page header's `libraries.kit`, else `current`.
  - `build_tier1` passes the raw source text and the source file name, so build failures point at
    lines the agent wrote. `quirk_html.py check`, `check_artifact` and the companion scan the
    built page.
- **The scan skips library blocks, shell blocks, and every other `<script>` or `<style>` body**,
  because the parser treats them as raw text. A q-* tag inside a JS string triggers inclusion
  (§4.1) but isn't validated. Tags inside `<template>` are ordinary markup and are validated.
- **Messages.** The phrases are stable because tests match them:
  - `unknown element <q-stats>`
  - `<q-chart> needs attribute summary`
  - `<q-chart> type="pie" is not one of bar, line, area, donut`
  - `<q-stat> points="a,b" is not a number list` (also `integer` and `ident` kinds)
  - `<q-chart> needs one of: table, data-from`
  - `<q-diff-note> must be inside <q-diff>`
  - `<q-chart> cannot be self-closed; write <q-chart …></q-chart>` (HTML only; browsers read a
    self-closed q-* tag as an open tag, so the tolerant tree keeps it open and the failure says why)
  - `<q-chart> has 9 series; the limit is 8` (rule `max-series`, inline tables only)
  - `<q-diff-note> file="x" is not in its diff`
  - `<q-diff-note> line 40 is not a new-side line of x` (rule `diff-notes`)
  - `<q-tabs> section 2 does not start with a heading` (rules `heading-sections`, `board-columns`)
  - `<q-timeline> item 3 has no <time datetime>`, and `data-tone="red" is not one of …` (rule
    `timeline-items`)
  - `kit elements are used but the kit is not inlined`, on a built page with q-* tags and no
    `kit@` library block
- **`max-series`** counts the `y` list when given, else the header cells minus the `x` column.
- **`diff-notes`** parses the parent's `<pre>` text, after unescaping HTML entities.
  - Files come from `+++ ` lines, with a leading `b/` stripped.
  - New-side lines are counted from each `@@ -a,b +c,d @@` header, over context and `+` lines.
- Unknown non-global attributes are not checked. A misspelled required attribute is still caught
  as missing.
- A catalog that fails to load (`KitError`) is caught inside `run_checks` and reported as one
  failure, `{"check": "kit", "detail": "cannot load the kit catalog: <reason>"}`. Every caller
  (`build_tier1`, `check_artifact`, `quirk_html.py check`, `companion._cmd_show`, `app.py`)
  therefore needs no new exception handling.
- **Tree building.** `HTMLParser` builds no tree, so `kitcheck` keeps a tolerant element stack.
  - It applies HTML's implied end tags for `li`, `p`, `tr`, `td`, `th`, `dt`, `dd` and `option`.
  - It ignores void elements.
  - It closes unmatched elements at their ancestor's end tag.
  - Rules read that stack. A malformed document still produces checks, never a crash.

### 4.3 Runtime: `kit.js` and `kit.css`

Back-link: [Shared behavior](logic.md#shared-behavior), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**`kit.js` shape**
- It is one classic-script IIFE with no top-level `this`, `import` or `export`, so it runs
  unchanged as a `<script>` and as a side-effect import.
- Every element is registered through an internal `define(tag, cls)` that does nothing when
  `customElements.get(tag)` is already set.
- It keeps no global state other than the registry. It exposes nothing on `window`.

**Internal helpers.** Element tasks build on these, defined once at the top of the file:
- `whenReady(fn)`: runs `fn` after `DOMContentLoaded`, or immediately when that has already
  fired.
- `token(name)`: returns `getComputedStyle(document.documentElement).getPropertyValue('--q-' + name).trim()`.
- `onTheme(el, fn)`: while `el` is connected, calls `fn` (coalesced to one call per animation
  frame) on any of these, and removes all of them on disconnect:
  - a `quirk-theme` event on `document`
  - a `MutationObserver` change to `data-theme` or `class` on `<html>`
  - a `prefers-color-scheme` `change`

  The observer is required. In tier 1, `kit.js`'s `DOMContentLoaded` listener runs before
  `chrome.js` applies the stored theme (`chrome.js:322-326`, silently at `:137`). Tier 2's
  `theme.ts` never dispatches `quirk-theme`; it only sets `data-theme`.
- `bindData(el, key, fn)`: calls `fn(rows)` after `whenReady`.
  - It resolves `window.quirkData()`. An array is used whole; an object yields `obj[key]`, which
    must be an array of row objects.
  - It re-calls `fn` for every `quirkData.onChange`.
  - When `quirkData` is absent, or the data is missing or malformed, it writes one short message
    into the element. It never throws.
- `readTable(table)`: returns `{columns: string[], rows: string[][]}` from `thead` and `tbody`.

**Lifecycle**
- Upgrade work is idempotent: a second `connectedCallback` after a move doesn't duplicate inserted
  nodes. Inserted nodes carry `data-q-kit` so they can be found and removed.
- Elements read configuration from attributes only. They define no JS properties named like a
  catalog attribute, because React 19 sets a property instead of an attribute whenever
  `name in element`.
- Each element re-renders on `attributeChangedCallback` for its catalog attributes. Elements that
  read a child table re-render on child-list and character-data changes through a
  `MutationObserver`.
- **Never hide content that can't be rebuilt.** The only author nodes the kit may move:
  - the `q-chart` source table, which goes into the "Table view" `<details>` inside the same
    element
  - `q-board` cards, which move between that board's lists
  - Everything else is added alongside, or toggled with an attribute.

**Theme and colors**
- Elements read colors at render time through `token()`, and re-render on `quirk-theme`.
- No colors are hard-coded in JS or CSS. Every color is a `var(--q-…)`.
- The first render reads the tokens directly. `onTheme`'s observer corrects it when `chrome.js`
  applies a stored theme a moment later.

**`kit.css`**
- It styles the wrapped HTML before upgrade, using `:not(:defined)`, and after.
- It never uses `display: none` or `visibility: hidden` on author content before upgrade.
- Layout holds at a 360 px viewport with no page-level horizontal scroll.
- `@media print` shows every tab panel and hides kit-only controls: copy buttons, filters, board
  controls and the theme-dependent canvas's table toggle. It keeps the table view open.

**Per-element contracts**, beyond [Behavior](logic.md#behavior):

- **`q-tabs`**
  - Inserts a `div[role=tablist][data-q-kit]` of `button[role=tab]` before the first section. Tab
    labels come from the heading text.
  - Sections get `role=tabpanel`, `tabindex=0` and `aria-labelledby`.
  - Inactive panels get `data-q-inactive`, which `kit.css` hides outside print. It doesn't use
    `hidden`, because the companion skeleton's `[hidden] { display: none !important }` would beat
    the print rule.
  - The heading stays in the panel, visually hidden.
  - Keys, per the APG: Left/Right with wrap, Home and End. Activation is automatic.
- **`q-chart`**
  - Inserts a fixed-height box (`--q-chart-height`, default 320px) holding a
    `canvas[role=img][aria-label=<summary>]`. Then it moves the table into
    `<details data-q-kit><summary>Table view</summary>…</details>`.
  - Bound data renders a generated table in the same `<details>`.
  - Raw options are parsed from the child JSON block and deep-merged first. The guarantees are
    applied last:
    - `animation: false`, `maintainAspectRatio: false`, `responsive: true`
    - dataset colors from `chart-1`…`chart-8`
    - tick, grid, legend and tooltip colors from `text`, `text-muted` and `border`
    - the canvas `aria-label`
  - Invalid JSON is ignored with a `console.warn` only, so verify's `console` check (errors only)
    passes.
  - The previous Chart instance is destroyed before every redraw.
  - Long category labels are truncated to 24 characters with an ellipsis. The tooltip shows the
    full text.
  - When `window.Chart` is undefined, the table stays visible and nothing throws.
  - Bound data with more than 8 series shows the table, open, with the note "Too many series to
    chart clearly (n); showing the table."
- **`q-stat`**
  - Sets `data-q-trend="good" | "bad" | "flat"` on the delta element, from its sign and
    `direction`.
  - The sparkline is an inline `<svg aria-hidden="true" focusable="false" data-q-kit>` polyline,
    stroked with `accent`.
  - Adjacent stats form a responsive row through CSS alone: `display: inline-grid`, a min/max
    width, and `vertical-align: top`. No wrapper is inserted.
- **`q-table`**
  - The element itself is the scroll container: `display: block`, `overflow: auto`, and a
    `max-height` once a filter is present, so the sticky `thead` works and the page never scrolls
    sideways.
  - Sort buttons go inside each `<th>`. `aria-sort` is set on the active `<th>`, and the others
    have none.
  - `num` columns sort by the first number in the cell, ignoring thousands separators. Other
    columns use `localeCompare`.
  - The filter is an `input[type=search]` labelled "Filter rows", plus a polite live region
    reading "n of m rows". Both are inserted only when the body has more than 12 rows. The filter
    matches a case-insensitive substring of a row's text.
- **`q-timeline`**
  - The rail and markers are CSS on `ol`/`li`.
  - The tone shows as the marker color and a visually hidden tone word, so color is not the only
    signal.
- **`q-code`**
  - Inserts a header bar with the `filename` (if set) and a "Copy" button.
  - On success the button reads "Copied" for 2 s. When the clipboard is blocked it selects the
    code text and announces "Press Ctrl+C (⌘C on Mac) to copy" in a polite live region.
- **`q-diff`**
  - Leaves the `<pre>` in place, marks it `data-q-replaced` (hidden in every medium, print
    included, so print shows the rendered view only), and renders a table-based diff view
    alongside it. The view has file headers, `+`/`-` line classes, and old and new line numbers.
  - Each `q-diff-note` is placed, as a cloned rendering, in a row under its new-side line. The
    original notes are hidden only after their clones exist.
  - Without JS, CSS shows the raw `<pre>` and then the notes as a list: `q-diff-note` is a
    `list-item`.
- **`q-board`**
  - Inserts a toolbar with "Reset", "Copy as Markdown" and the text "Saved in this browser only."
  - When `localStorage` throws, the text reads "Not saved: this browser blocks storage." and moves
    still work in memory.
  - Each card gets a "Move to…" `<select>` listing the other columns.
  - On a card with focus, Alt+Left and Alt+Right move it to the adjacent column, and Alt+Up and
    Alt+Down reorder it. Focus stays on the moved card, and a polite live region announces where
    it went.
  - Pointer drag uses pointer events (mouse and touch) with a drop indicator. Native HTML5 drag is
    not used.
  - "Copy as Markdown" writes `## <column>` and then `- <card text>` per card, with the same
    clipboard fallback as `q-code`.
  - Storage follows §3.5.

### 4.4 Tier 2 (`app.py`, the app template)

Back-link: [Data flow](logic.md#data-flow) step 5.

- **Scan.** Before the Vite build, `build_app` runs `kitcheck.needs` over every
  `src/**/*.{ts,tsx,js,jsx}` file and `index.html` in the app's source folder.
- **Check.** It runs `kitcheck.check_jsx` over those same files.
  - It validates tag names, required-attribute presence (any value form, `{expr}` included), and
    literal string values against `enum`, `integer`, `ident` and `number-list` kinds.
  - Child rules (`requires`, `rules`, `parent`) are skipped, because JSX children aren't statically
    known.
  - Attribute values are read with brace-depth matching, so `style={{…}}` and nested expressions
    don't break the scan.
  - Its failures join the build's `checks.failures`. `passed` is false and the exit is 1. The page
    is still written, as in tier 1.
- **Inlining**, after the build: the kit (and Chart.js when needed) is inlined into the page. The
  test files and `.d.ts` files under `src/` are excluded from the scan.
  - Library CSS blocks go before `</head>` and JS blocks go before `</body>`, each wrapped by
    `wrap_block` exactly as tier 1 does.
  - License comments and `libraries` header entries are added for each.
  - Versions follow the tier-1 frozen rule, read from the existing output header.
  - `--upgrade` (`quirk_html.py:257`) moves `kit` and `chartjs` to `current`, so it now does
    something in tier 2. Update its help text, `app.py`'s "--upgrade has no effect on tier 2"
    warning (keep it only when the page uses no kit), and `tests/test_html_app.py:361`.
- **`src/quirk-kit.d.ts`** declares every catalog tag in React's `JSX.IntrinsicElements`, with
  string attributes and `children`, so `pnpm run typecheck` passes.
  - Use the module-augmentation form, `declare module 'react' { namespace JSX { … } }` plus
    `export {}`. `@types/react` 19 has no global `JSX`, and `isolatedModules` and
    `verbatimModuleSyntax` are on.
  - Comments in it must not contain a literal `<q-`.
  - It is a static file. A test asserts that its tag set equals the catalog's.
- **`templates/app/rules.md`** gains a short "Kit elements" section:
  - Use `className`, not `class`.
  - Keep a q-* element's direct children stable. Change rows or attributes, or give the element a
    `key` to remount it.
  - Never let React re-render `q-board` cards.

### 4.5 Companion

Back-link: [Data flow](logic.md#data-flow) step 5.

- Kit markup goes in `content`, or in an option's `html`, exactly as written. No `screen.json`
  schema change.
- `templates/companion/rules.md` states the boundary:
  - Only elements with `interactive: false` may appear in an option's `html`, because the option is
    a `<button>` with `pointer-events: none` on its mockup (`skeleton.html:30`).
  - Interactive elements go in `content`.
- This is a documented rule, like the existing ban on controls in option `html`. It isn't
  enforced in code.

### 4.6 Verify: `--no-js`

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals) ("Done means").

COMMAND: `python3 $SKILL/scripts/quirk_html.py verify FILE [--out-dir DIR] [--no-js]`

- `verify.mjs` takes an optional fourth argument, `--no-js`. It creates each context with
  `javaScriptEnabled: false` and names screenshots `{width}-{scheme}-nojs.png`.
- In that mode it adds a fifth check, `fallback`. It fails when any element whose tag starts with
  `q-` and that has no `data-from` attribute has empty `innerText` or a zero-height bounding box.
  - It runs at 375 px in both schemes.
  - `console`, `viewports`, `themes` and `network` run as before.
- `run_verify(file, out_dir=None, mode="offline", no_js=False)` passes the flag through, and its
  JSON result carries `"no_js": true|false`.
- With no `--out-dir`, a `--no-js` run writes to `<file stem>.verify-nojs/` beside the file, so it
  never overwrites the JS-enabled report in `<file stem>.verify/`.
- The `report.json` of a `--no-js` run carries `"no_js": true` on disk. A normal report has no
  `no_js` key on disk.
- Without the flag, the report has the same four checks and keys as today.
- The delivery note reads `<file stem>.verify/` by default. If it is pointed at a report with
  `"no_js": true`, its line reads `Verify (no JS): ...`.

### 4.7 Pins

Back-link: [Data flow](logic.md#data-flow) step 2.

COMMAND: `python3 $SKILL/scripts/pins.py stamp NAME VERSION [--vendor-dir DIR]`

- `stamp` recomputes `sha256` and `inline_sha256` for every file of that version, using
  `pins.escape_inline`, and rewrites `libraries.json` in place.
  - It keeps the key order and the existing 2-space JSON layout, with a trailing newline.
  - Exit 0 on success; exit 2 with a JSON error for an unknown name or version.
- `check` skips any version with `"first_party": true` and reports it as `first-party`, not as an
  npm error.
- `verify` treats first-party entries like any other.

### 4.8 Docs generator: `kit_docs.py`

Back-link: [Conceptual model](logic.md#conceptual-model).

COMMAND: `python3 $SKILL/scripts/kit_docs.py reference [--check]` ·
`python3 $SKILL/scripts/kit_docs.py examples OUT_DIR`

- **`reference`** writes `references/components.md` from the `current` catalog.
  - The file opens with "Generated from `vendor/kit/<v>/catalog.json` by
    `scripts/kit_docs.py reference`. Do not edit by hand."
  - A short "How inclusion works" paragraph and a tag index follow.
  - Then one section per element: `use_when`, an attribute table, `children`, an example in a
    fenced `html` block, and whether it may go in a companion option's `html`.
  - Output is deterministic. `--check` writes nothing; it exits 1 when the file differs from what
    it would write.
- **`examples`** writes `<tag>.src.html` per element (`q-diff-note` is shown inside `q-diff`'s
  example).
  - Each is a `report`-template source with header
    `{"template": "report", "title": "<tag> example", "mode": "offline", "interactions": []}`, a
    `main` slot holding the catalog example, and an `aside` slot only when the report template
    requires one.
  - Both commands print one JSON object: `{"written": [paths]}`, or `{"stale": true|false}` for
    `--check`.

### 4.9 Rules and references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- **`templates/report/rules.md`**
  - Replace the Charts section (`:24-30`) with:
    - a pointer to `q-chart` and `references/components.md`
    - the Mermaid line (`:30`)
    - one line saying scatter and histogram charts stay hand-written Chart.js under design
      reference section 9
  - Drop the `q-sort` row (`:22`) for a `q-table` pointer.
  - Keep the `q-chart` class row (`:19`), reworded "Mermaid diagrams only".
  - The `test_report_template_declares_its_contract` assertion (`tests/test_html_builder.py:177-190`)
    moves to asserting `q-chart` and `references/components.md`.
- **`templates/components/rules.md`**: replace the Charts section (`:21-25`) the same way. Keep the
  Web Awesome section, adding one line: "For tabs with no form controls, `q-tabs` avoids loading
  Web Awesome."
- **`references/design-reference.md` §9** (`:143-180`)
  - Keep the Chart choice (`:153-162`) and Drawing (`:164-172`) rules, plus the table presentation
    lines `:147-148`, `:150-151`.
  - Replace `:149`, `:173` and the Chart.js block (`:175-180`) with a pointer to `q-chart` and
    `q-table`. Keep a three-line note covering hand-written Chart.js (scatter, histogram).
  - Point `:88` (series colors) at the new `--q-color-chart-*` tokens.
- **`SKILL.md`**
  - Add `- [Components](references/components.md): …` to the References list (`:121-125`).
  - Add one sentence to "Charts and the theme" (`:113-115`).
  - Add `kit` to the check list (`:41`).
- **`references/templates.md`**
  - At `:82`, add that `kit` and `chartjs` are added automatically when q-* tags appear, and that
    `kit` may not be listed by hand.
  - At `:111`, list the chart tokens.
- **`references/companion.md`**: add one line under `## screen.json` pointing at §4.5's rule.

### 4.10 Report example

Back-link: [Scenarios](logic.md#scenarios) ("A report with KPIs and a trend").

- `templates/report/example.src.html` becomes:
  - three `q-stat`s
  - a `q-chart` with `data-from` over the existing `timings.json`
  - a `q-table` with `data-from` over the same data
- The Alpine `sortBy`, `ariaSort`, `chartLabel` and `drawChart` code (`:77-160`) goes. Alpine stays
  in the template, so the header's `interactions` keep their wording.
- The header drops `"libraries": ["chartjs"]`, because inclusion is automatic.
- If `timings.json` isn't an array of row objects, or an object of them, reshape it, and keep it
  small.

## 5. DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **`vendor/<lib>/<version>/` for every library other than `kit`, and every existing
  `libraries.json` entry.** Frozen artifacts depend on their hashes.
- **`$KIT` after this branch merges.**
  - `1.0.0` is unreleased until then, so `pins.py stamp kit 1.0.0` is allowed on this branch only.
  - Any later change is a new version directory.
- **`theme/chrome.js`.**
  - Its `quirkData` and `quirk-theme` contracts are what the kit consumes.
  - Its checksum is a shell check: an edit breaks every built page's `checksum` until rebuilt.
- **`checks.py` `_Scanner` and `_scan_page` (`:98-216`).** The `external-refs` check depends on
  their raw-text and comment handling. The kit check gets its own parser.
- **The companion server, `screen.json` schema and `companion.js`.** §2 shows no change is needed.
- **`header.py` and the header `schema: 1`.** `kit` and `chartjs` fit in the existing `libraries`
  map.
- **`skills/writing-specs/interactive/**`, `CHANGELOG.md`, and version fields.** Reasons as in the
  sibling tech spec, §5.

## 6. Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `pins.py stamp kit 1.0.0` after any edit to `kit.js` or `kit.css`, in the same task.
- Regenerate `references/components.md` after any catalog edit, in the same task.
- Guard every `customElements.define`.
- Use `var(--q-…)` for every color.
- Keep the wrapped HTML readable with the script removed.

**Ask**
- Any change to the catalog schema (§3.1) or the element markup table (§3.4) after the first task
  that consumes it has landed.
- Adding an element, or an attribute not in §3.4.

**Never**
- Shadow DOM, Lit, Alpine inside `kit.js`, or any dependency besides `window.Chart`.
- Network access from a build, check, test or the kit runtime.
- Hand-editing `references/components.md`.
- Restamping a kit version that has shipped.

## 7. Cross-cutting

Back-link: [Shared behavior](logic.md#shared-behavior).

- **Security.**
  - The kit renders author text with `textContent`, never `innerHTML`, except to clone a
    `q-diff-note`'s child nodes.
  - Board storage is parsed defensively. A malformed value is discarded.
  - The JSON options block is parsed with `JSON.parse`, never evaluated.
- **Rollback.** The change is additive.
  - Pages without q-* tags are unchanged.
  - Reverting the PR leaves already-built pages working, because each page carries its own inlined
    kit.

## 8. Testing strategy

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

CI runs `pytest -q` with no Node and no browser, so browser tests skip there, like
`tests/test_html_verify.py`'s `browser_ready` fixture. Locally, `scripts/verify/node_modules` and
Chrome are present, so they run.

| File | Must cover |
|---|---|
| `tests/test_html_kit_catalog.py` (new) | all sixteen `chart-*` token values reach 3:1 against `color.bg` in their own scheme; the catalog loads and validates: tags unique and well-formed, `requires` selectors match §3.1's regex, rule names are known, `kit_version` matches its directory; the §3.4 table is encoded (spot-check every element's required attributes and enums); `kit_docs.py reference --check` is clean; `quirk-kit.d.ts` declares exactly the catalog's tags; `pins.py stamp` round-trips (stamp twice → no diff) on a tmp copy; `pins.py verify` passes |
| `tests/test_html_kit_check.py` (new) | every message in §4.2 with a positive and a negative case; line numbers point at the source line; tags inside `<script>` aren't validated but still trigger inclusion; tags inside `<template>` are validated; `max-series` and `diff-notes` edges (a `b/` prefix, multi-hunk, a removed line); JSX check (unknown tag, missing attribute, bad literal enum, `{expr}` accepted, `style={{…}}` parses) |
| `tests/test_html_builder.py` (modify) | auto-inclusion (kit only; kit plus chartjs; neither → byte-identical apart from `built_at`); `chartjs` added outside `optional_libraries`; a header-declared `kit` rejected; kit CSS after `base.css`; frozen kit version on rebuild versus `--upgrade` (fake two-version registry); a build with a bad q-* tag exits 1 and names the source line; the report example builds with the kit |
| `tests/test_html_vendor.py` (modify) | the library set at `:46-61` includes `kit` |
| `tests/test_html_companion.py` (modify) | a screen whose `content` holds a `q-stat` shows, passes checks, and inlines the kit; a screen with `<q-stats>` fails `kit` and isn't made current |
| `tests/test_html_app.py` (modify) | `--upgrade` moves kit versions and the old no-effect warning appears only for kit-free apps (`:361`); with the fake pnpm: a `src/*.tsx` using `<q-chart …>` gets kit and Chart.js blocks, license comments and header versions; a JSX misuse fails `kit` |
| `tests/test_html_verify.py` (modify) | `--no-js` passes on a fixture whose q-* content is plain HTML; `fallback` fails a fixture where CSS hides an un-upgraded q-* element; without the flag the report keeps exactly four checks |
| `tests/test_html_kit_elements.py` (new, browser) | Playwright through `scripts/verify/node_modules/playwright-core`, driven by a node harness at `tests/fixtures/html-kit/harness.mjs` that loads a built page and evaluates assertions. One test group per element, covering each [Behavior](logic.md#behavior) bullet: tab keys and ARIA; chart canvas `aria-label`, table view, theme re-render, raw options losing to guarantees, >8 bound series; stat trend and sparkline `aria-hidden`; table sort, `aria-sort`, filter readout at 13 rows; timeline tone text; code copy fallback; diff note placement; board keyboard move, reload persistence, reset, stale-layout discard, Markdown export |
| `tests/test_html_kit_examples.py` (new) | `kit_docs.py examples` into tmp; every example builds and passes all checks; when a browser is available, every example passes `verify` and `verify --no-js` |
| `tests/test_writing_html_artifacts_skill.py` | unchanged; it must keep passing (link resolution now covers `components.md`) |

The acceptance bar is `python3 -m pytest tests/ -q` green locally, browser tests included.

## 9. Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Item | Answer |
|---|---|
| How verify proves the no-JS fallback | `verify --no-js` with the `fallback` check (§4.6), run on every example (§8) |
| How tier 2 gets the kit | referenced from the skill: `app.py` inlines the pinned library blocks after the Vite build (§4.4) |
| How the companion carries kit markup and runs the check | as written in `content` and option `html`; via `build_tier1`'s source check and `check_artifact` (§2, §4.5) |
| Catalog format and reference generation | §3.1; `kit_docs.py reference` (§4.8) |
| Exact attribute names | §3.4 |

## 10. Non-goals

- Everything in [Scope and non-goals](logic.md#scope-and-non-goals) stays out.
- No migration of existing pages to q-* tags.
- No catalog-driven runtime validation in `kit.js`. Misuse is a build failure, not a runtime box.
- No child-structure checking in tier 2 (§4.4).
- No enforcement of the companion's interactive-element boundary (§4.5).

## 11. Amendments

None yet.
