# Tech spec: `q-flow` for `writing-html-artifacts`

**Status**: Reviewed (one review round, fixes applied) · Logic spec: [logic.md](logic.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`, `K` = `skills/writing-html-artifacts/vendor/kit/1.0.0`.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

| Unit | Files | Role |
|---|---|---|
| Flow vendor bundle | new `S/scripts/vendor-build/build-flow.mjs`, `S/scripts/vendor-build/package.json`, `S/scripts/vendor-build/pnpm-lock.yaml`, new `S/vendor/flow/0.12.0/{flow.bundle.js,LICENSE}`, `S/vendor/libraries.json` | Bundle `elkjs` (0.12.0), `d3-zoom` (3.0.0) and `d3-selection` (3.0.0) into one offline IIFE exposing `window.quirkFlow` |
| Kit catalog & docs | `K/catalog.json`, `S/scripts/kit_docs.py`, `S/references/components.md` (regenerated), `S/templates/app/project/src/quirk-kit.d.ts` | Register `q-flow` in the catalog, TypeScript declarations and generated component reference |
| Kit check & fallback injection | `S/scripts/htmlkit/kitcheck.py`, `S/scripts/htmlkit/checks.py`, `S/scripts/htmlkit/assemble.py`, `S/scripts/htmlkit/app.py` | Auto-include `flow` when `<q-flow>` appears, validate the JSON graph contract and emit warnings, inject the static no-JS `<details open>` list fallback during tier-1 builds |
| Kit runtime & styles | `K/kit.js`, `K/kit.css` | `<q-flow>` custom element: text measurement, ELK layout, SVG rendering of groups/lanes/nodes/edges/labels, focus path & streaming pulse, detail drawer, d3-zoom filter, expand, roving tabindex keyboard model, live theme recoloring |
| Browser verify & test harness | `S/scripts/verify/verify.mjs`, `tests/fixtures/html-kit/harness.mjs` | Wait for every `<q-flow>` on the page to set `data-q-flow-ready` before screenshots, contrast sampling or test steps |
| Skill docs, examples & evals | `S/SKILL.md`, `S/references/{design-reference,templates,companion}.md`, `S/templates/{report,components,companion}/rules.md`, `S/templates/{report,components}/examples/{explainer,reference}.src.html`, new `S/evals/flow-evals.json` | Document `q-flow` vs Mermaid, the section 10 motion exception, kind consistency, shape examples and routing evals |

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

### `S/scripts/vendor-build/` and `S/vendor/`
- `S/scripts/vendor-build/package.json:11-17` `dependencies`: pins `"elkjs": "0.12.0"`, `"d3-zoom": "3.0.0"`, `"d3-selection": "3.0.0"`.
- `S/scripts/vendor-build/build-flow.mjs` modeled on `S/scripts/vendor-build/build-webawesome.mjs:14-121`: bundles `elkjs/lib/elk.bundled.js`, `d3-zoom` and `d3-selection` into `S/vendor/flow/0.12.0/flow.bundle.js` (`:34`), writes `S/vendor/flow/0.12.0/LICENSE` (`:54`) and updates `S/vendor/libraries.json`.
- `S/vendor/libraries.json:167-187`: records the `"flow"` library entry at version `"0.12.0"`, and `kit@1.0.0` is restamped via `S/scripts/pins.py:111` `stamp`.

### `S/scripts/htmlkit/kitcheck.py`
- `KIT_TAG`, `CHART_TAG`, `CODE_TAG` `:28-30`: add `FLOW_TAG`.
- `KNOWN_RULES` `:32`: add `"flow-data"`.
- `needs` `:76`, `needs_highlight` `:85`: add `needs_flow(text: str) -> bool`.
- `check_html` `:593`: add `check_html_warnings(text: str, catalog: Catalog, *, label: str) -> list[dict]` and `inject_flow_fallbacks(html: str) -> str`.
- `_RULES` `:856-864`: register `"flow-data": _rule_flow_data`.

### `S/scripts/htmlkit/assemble.py`, `checks.py`, `app.py`
- `S/scripts/htmlkit/assemble.py:274-287` `_with_auto_libraries`: include `"flow"` before `"kit"` when `kitcheck.needs_flow(raw_source)` is true.
- `S/scripts/htmlkit/assemble.py:517-522` (`render` closure): pass slot and region HTML through `kitcheck.inject_flow_fallbacks` before `_substitute` so built tier-1 pages (and companion screens via `S/scripts/companion.py:788` `_build_screen`) carry the un-upgraded notice and `<details open>` list without touching `<head>` or `{{body_end}}`.
- `S/scripts/htmlkit/assemble.py:712-714` `delivery_note`: explain the over-2 MB warning when `"flow"` is in `libraries`, alongside `"mermaid"`.
- `S/scripts/htmlkit/checks.py:361-388` `_kit_failures` and `:439-449` `run_checks`: append `kitcheck.check_html_warnings` to `warnings`, and fail with `q-flow elements are used but flow is not inlined` if a built page has `<q-flow>` without a `flow@` block.
- `S/scripts/htmlkit/app.py:270-275` and `:316` `build_app`: detect `uses_flow` across `_kit_sources(source)` and inline `"flow"` before `"kit"`.

### `K/catalog.json`, `K/kit.js`, `K/kit.css`, `S/scripts/kit_docs.py`
- `K/catalog.json:336-360`: append the `q-flow` element entry.
- `K/kit.js:7-8` header comment, `:2874-2885` registrations: add `QFlow` and `define('q-flow', QFlow)`.
- `K/kit.css:35-39` block-level element list, `:1046-1099` `@media print`: add `q-flow` styles and print rules.
- `S/scripts/kit_docs.py:95-97` `render_reference`: mention that `q-flow` inlines the flow layout library automatically.
- `S/templates/app/project/src/quirk-kit.d.ts:10-25` `IntrinsicElements`: add `'q-flow': KitElementProps`.

### `S/scripts/verify/verify.mjs` and `tests/fixtures/html-kit/harness.mjs`
- `S/scripts/verify/verify.mjs:219-227`: when `!noJs`, wait up to 10 s for all `q-flow` elements to carry `data-q-flow-ready` before `waitForTimeout(150)` and `page.screenshot`; on timeout, record a `console` check failure (`"<run>: q-flow did not finish laying out within 10s"`) and continue taking screenshots so the run never hangs.
- `tests/fixtures/html-kit/harness.mjs:155` and `:175`: when `spec.javaScript !== false`, wait up to 10 s for all `q-flow` elements to carry `data-q-flow-ready` after `page.goto` and `page.reload`; on timeout, record a failed step in `out.failedSteps` and continue.

## Contracts & interfaces

### 1. Vendored `flow` library (`build-flow.mjs`, `libraries.json`)
Back-links: [Data flow](logic.md#data-flow), [Key decisions and rationale](logic.md#key-decisions-and-rationale), [Industry Insights](logic.md#industry-insights).

```
CONFIG: S/vendor/libraries.json addition under "libraries"
"flow": {
  "current": "0.12.0",
  "versions": {
    "0.12.0": {
      "package": "elkjs",
      "license": "EPL-2.0 AND ISC",
      "license_file": "LICENSE",
      "source": "https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz",
      "files": [
        {
          "path": "flow.bundle.js",
          "kind": "js",
          "position": "body-end",
          "inline": true,
          "sha256": "<64-hex>",
          "inline_sha256": "<64-hex>"
        }
      ]
    }
  }
}
```

```
CONTRACT: window.quirkFlow global exposed by flow.bundle.js
window.quirkFlow = {
  ELK: typeof import("elkjs/lib/elk.bundled.js").default,
  zoom: typeof import("d3-zoom").zoom,
  zoomIdentity: typeof import("d3-zoom").zoomIdentity,
  zoomTransform: typeof import("d3-zoom").zoomTransform,
  select: typeof import("d3-selection").select
}
```

- **Preconditions:** `elkjs@0.12.0`, `d3-zoom@3.0.0` and `d3-selection@3.0.0` installed in `S/scripts/vendor-build/node_modules`.
- **Postconditions:** `flow.bundle.js` is a single self-contained ES2022 browser IIFE with no `import`/`export` statements and no network calls. `S/vendor/flow/0.12.0/LICENSE` opens with a copyright line naming both parts (`Copyright (c) 2008, 2024 Kiel University and others (elkjs, EPL-2.0); Copyright 2010-2023 Mike Bostock (d3-zoom, d3-selection, ISC)`) so `vendor.license_comment` (`S/scripts/htmlkit/vendor.py:204-220`) emits `<!-- license: flow 0.12.0 EPL-2.0 AND ISC | Copyright ... -->` alongside `kit`'s `<!-- license: kit 1.0.0 MIT | ... -->`.
- **Invariants:** Pages without `<q-flow>` never inline `flow.bundle.js` (`SC-2`). `pins.py verify` passes on `S/vendor/`.
- **Error behavior:** If `window.quirkFlow` is absent at runtime or `elk.layout()` rejects, `<q-flow>` catches the error, renders the one-line canvas notice, opens the `"Graph as a list"` `<details>`, and sets `data-q-flow-ready="error"` (`SC-18`).

### 2. Inclusion, validation, warnings & fallback injection (`kitcheck.py`, `checks.py`, `assemble.py`, `app.py`)
Back-links: [Authoring and building](logic.md#authoring-and-building), [Fallbacks](logic.md#fallbacks), [Other surfaces](logic.md#other-surfaces), [Decisions Locked](logic.md#decisions-locked).

```
REGEX:
FLOW_TAG = (?i)<q-flow[\s/>]
```

```
CONTRACT: kitcheck.py additions
def needs_flow(text: str) -> bool
def check_html_warnings(text: str, catalog: Catalog, *, label: str) -> list[dict]
def inject_flow_fallbacks(html: str) -> str
```

- **`needs_flow(text)`:**
  - Pre: raw source or JSX text.
  - Post: `True` iff `FLOW_TAG` matches `text`. When true, `assemble._with_auto_libraries` and `app.build_app` add `"flow"` before `"kit"` (and before `"alpine"`).
  - Invariant: `kitcheck.needs(text)` signature `(kit, chartjs)` is unchanged.
- **`_rule_flow_data` (in `check_html`) and `check_html_warnings`:**
  - Pre: `<q-flow>` node in the tolerant `_TreeBuilder` tree.
  - Post: `check_html` returns `[{"check": "kit", "detail": "<label> line <n>: <message>"}]` for contract violations; `check_html_warnings` returns `[{"check": "kit", "detail": "<label> line <n>: <message>"}]` for warnings; `checks.run_checks` appends those warnings to `result["warnings"]`.
  - Error messages (all cite the `<q-flow>` start line):
    - Missing `summary` attribute → `<q-flow> needs attribute summary` (emitted by `_check_element`'s generic required-attribute check, matching `kitcheck.py:639`).
    - Missing or non-JSON `<script type="application/json">` child, or non-object JSON payload → `<q-flow> needs a <script type="application/json"> child holding a JSON object`
    - Coordinate fields (`x`, `y`, `position`, `positions`) on graph, node, group or edge → `<q-flow> positions are laid out automatically; remove coordinates`
    - More than 8 entries in `kinds` → `<q-flow> declares N kinds; at most eight kinds, one per chart color`
    - A `kinds` value not an integer `1..8` → `<q-flow> kind "<k>" color must be an integer from 1 to 8`
    - Missing or empty `nodes` list → `<q-flow> needs a non-empty nodes list`
    - Node count `> 200` → `<q-flow> has N nodes (more than 200 nodes); split into groups or several graphs`
    - Duplicate `id` across `nodes` and `groups` → `<q-flow> has duplicate id "<id>"`
    - Edge `from` or `to` not in declared node ids → `<q-flow> edge points at unknown node "<id>"`
    - Node `kind` not in `kinds` → `<q-flow> node "<id>" has undeclared kind "<kind>"`
    - Node `group` or group `parent` not in declared group ids → `<q-flow> references unknown group "<id>"`
    - Cycle in `group.parent` chain → `<q-flow> group nesting loops at "<id>"`
    - `groups="lanes"` and either no top-level group exists or any node's `group` chain does not reach a top-level group → `<q-flow> node "<id>" is outside every lane: in lane mode every node belongs to a lane`
    - Node `detail` contains disallowed tags (anything outside the inline/block prose allow-list `p`, `ul`, `ol`, `li`, `code`, `pre`, `a`, `em`, `strong`, `b`, `i`, `br`, `span`, `kbd`, `samp`, `sub`, `sup`, `dl`, `dt`, `dd`), `on*` handlers, `javascript:`/`data:`/`vbscript:` URLs, or `src`/`action` attributes → `<q-flow> node "<id>" detail may hold only paragraphs, lists, code and links`
  - Warning messages (emitted by `check_html_warnings`):
    - Node count `61..200` → `<q-flow> has N nodes: large graphs read poorly, split into groups or several graphs`
    - Edge `label` length `> 30` characters → `<q-flow> edge label "<label>" is N characters: edge labels over 30 characters crowd the layout`
  - Built-page check in `checks._kit_failures`: if `scans_the_page` and `FLOW_TAG.search(text)` and not `any(name.startswith("flow@") for name in labels)`, append failure `{"check": "kit", "detail": "<label> line <n>: q-flow elements are used but flow is not inlined"}`.
- **`inject_flow_fallbacks(html)`:**
  - Pre: slot or region HTML string before `_substitute` in `build_tier1`.
  - Post: parses `html` with `_TreeBuilder` (treating `script` and `style` as raw text). For every `<q-flow>` element that passes `_rule_flow_data` with zero failures and does not already contain `data-q-flow-list`, inserts right before its closing `</q-flow>`:
    1. `<div class="q-flow-stage" data-q-kit data-q-flow-stage><p class="q-flow-notice" data-q-flow-notice>JavaScript is off, so this graph is shown as a list below.</p></div>`
    2. `<details class="q-flow-list" data-q-kit data-q-flow-list open><summary>Graph as a list</summary>…</details>` with HTML-escaped group/node/edge labels and kinds, and allow-list-sanitized `detail` HTML.
  - Error behavior: any `<q-flow>` that fails `_rule_flow_data` is left untouched (nothing injected), so malformed or disallowed `detail` markup is never written as live HTML into the built file.
  - Invariant: pages without `<q-flow>`, and `<script>`/`<style>` blocks, are returned byte-identical.

### 3. `<q-flow>` runtime and styling (`K/kit.js`, `K/kit.css`)
Back-links: [Reading at rest](logic.md#reading-at-rest), [Focusing](logic.md#focusing), [Groups as lanes](logic.md#groups-as-lanes), [Keyboard, motion and phones](logic.md#keyboard-motion-and-phones), [Fallbacks](logic.md#fallbacks), [Decisions Locked](logic.md#decisions-locked).

- **Preconditions / Postconditions / Invariants / Error behavior:**
  - **Preconditions:** `<q-flow>` is connected in a document where `kit.css` and `kit.js` are loaded.
  - **Postconditions:** Sets `data-q-flow-ready="true"` when ELK layout and SVG rendering succeed, or `data-q-flow-ready="error"` when validation or layout fails.
  - **Invariants:** Each instance generates unique SVG `<defs>` IDs (`marker`, `radialGradient`, `mask`) via `uid()` (`kit.js:244`) and keeps all focus/zoom/drawer state on the element instance (`SC-4`). Inserted nodes carry `data-q-kit` (`kitNode`, `kit.js:250`).
  - **Error behavior (`SC-18`):** If `<script type="application/json">` is missing, `JSON.parse` throws, the data breaks any contract rule (missing/empty/>200 `nodes`, >8 `kinds`, invalid `kinds` color, duplicate `id`, unknown group/node ref, group cycle, lane mode node outside lane, coordinates present, or disallowed `detail` HTML), `window.quirkFlow` is missing, or `elk.layout()` rejects, `<q-flow>` never throws: it renders the one-line notice in `.q-flow-stage`, opens `<details data-q-flow-list>`, and sets `data-q-flow-ready="error"`.
- **Upgrade & layout lifecycle (`SC-1`, `SC-5`, `SC-17`, `SC-18`, `SC-19`, `SC-22`):**
  - Observed attributes: `summary`, `direction`, `groups`; child `<script type="application/json">` mutations are observed via `watchChildren` (`kit.js:278`).
  - Ensures `<details class="q-flow-list" data-q-kit data-q-flow-list>` exists (building it in JS when not pre-injected, as in tier-2 apps).
  - Accessible naming (`SC-19`): `<svg class="q-flow-svg" role="group" aria-label="<summary>">` exposes the `summary` attribute as the graph's accessible name, followed by the `<details>` `"Graph as a list"` disclosure carrying every group, node, detail and edge.
  - Waits for `whenReady` and `document.fonts?.ready`, measures node and edge-label sizes with a 2D canvas context using the element's computed font, and runs `new window.quirkFlow.ELK().layout(elkGraph)`.
  - ELK options on root:
    - `elk.algorithm: "layered"` (uses ELK's default `BRANDES_KOEPF` node placement across all valid graph sizes `1..200`)
    - `elk.direction`: `"DOWN"` when `direction="down"`, else `"RIGHT"`
    - `elk.hierarchyHandling: "INCLUDE_CHILDREN"`
    - `elk.edgeRouting: "ORTHOGONAL"`
    - `elk.json.shapeCoords: "ROOT"` and `elk.json.edgeCoords: "ROOT"`
    - `elk.layered.spacing.nodeNodeBetweenLayers: "52"`, `elk.spacing.nodeNode: "28"`, `elk.spacing.edgeNode: "24"`, `elk.edgeLabels.inline: "true"`
    - `elk.partitioning.activate: "true"` when `groups="lanes"`
    - Free port constraints on all nodes and groups (never `FIXED_SIDE` / `FIXED_ORDER`, avoiding ELK issue #1192).
  - In `groups="lanes"` (`SC-13`):
    - Top-level groups (in listed order `0..k-1`) and all their descendant groups/nodes carry `elk.partitioning.partition: String(index)`.
    - After layout, top-level lane bands are stretched across the cross-axis (`y = minY..maxY` in `direction="right"`; `x = minX..maxX` in `direction="down"`) with a header bar at the top of each band; nested groups inside a lane are drawn as tinted panels at their ELK bounds.
  - Edges (`SC-1`, `SC-9`, `SC-15`):
    - Sync edges (`!edge.async`) render as solid lines (no `stroke-dasharray`); async edges (`edge.async === true`) render as dashed lines (`stroke-dasharray="6 4"`).
    - Every edge path carries an arrowhead `<marker>` (`marker-end="url(#q-flow-arrow-<uid>)"` at rest and `url(#q-flow-arrow-lit-<uid>)` when lit).
  - Stage sizing & initial fit (`SC-5`):
    - Stage height is set to fit the laid-out graph plus padding, clamped between `240px` and `Math.min(640, Math.round(window.innerHeight * 0.66))` px, and `_fitBounds` centers and scales the graph before revealing the SVG.
    - Once revealed, `<details data-q-flow-list>` has `open` removed, the fallback notice is hidden, and `el.setAttribute("data-q-flow-ready", "true")`.
- **Zoom, pan, wheel, touch & expand (`SC-5`, `SC-6`, `SC-7`, `SC-15`):**
  - `d3-zoom` attaches to `<svg class="q-flow-svg">` with scale extent `[0.2, 4]`. Zoom and fit operations apply transforms synchronously (jumping rather than easing, satisfying `SC-15`).
  - Filter:
    - `wheel`: allowed iff `event.ctrlKey || event.metaKey`. Plain wheel returns `false` and never prevents default, so the page scrolls (`SC-6`).
    - `touchstart` / `touchmove`: allowed iff `event.touches && event.touches.length >= 2`. CSS sets `touch-action: pan-x pan-y pinch-zoom` on `.q-flow-svg`, so one finger scrolls the page and two fingers pan/zoom (`SC-6`).
    - Pointer/mouse drag: primary button (`!event.button`) outside interactive controls.
  - Controls cluster (`.q-flow-controls`): `<button type="button">` for Zoom in (`data-q-flow-action="zoom-in"`), Zoom out (`data-q-flow-action="zoom-out"`), Fit (`data-q-flow-action="fit"`), and Expand (`data-q-flow-action="expand"`).
  - Expand toggles `data-q-flow-expanded` on `<q-flow>` (`position: fixed; inset: 0; z-index: 1000`), preserving focus and zoom (`SC-7`).
- **Node & group focus, streaming pulse & drawer (`SC-4`, `SC-9`, `SC-10`, `SC-11`, `SC-12`, `SC-15`, `SC-16`):**
  - Clicking a node (or pressing `Enter`/`Space` while it has keyboard focus):
    - Computes upstream nodes/edges (walking incoming edges backwards from the focused node) and downstream nodes/edges (walking outgoing edges forwards from the focused node).
    - Marks lit nodes/edges with `data-q-flow-lit` and off-path nodes/edges/groups with `data-q-flow-dim`.
    - Computes integer hop index `0..H-1` in flow order for each lit edge (`data-q-flow-hop="<hop>"`).
    - When `prefers-reduced-motion: no-preference`, activates the traveling pulse (`data-q-flow-pulsing`) that swells each lit edge (`stroke-width: 6`) through moving SVG mask dots while preserving the edge's solid or dashed `stroke-dasharray` and arrowhead marker (`SC-9`). Pulses move at a constant 180 graph px/s and a new wave leaves every 700 ms; each lit edge's start offset comes from shortest path lengths to and from the focused node, so every wave reaches the focused node, and leaves it, at one instant. Each edge keeps a pool of mask `<circle>` dots, one per wave on it, and only visible dots update `(cx, cy)` per frame. Under `prefers-reduced-motion: reduce`, lit edges render as a thicker static line (`stroke-width: 3.5`) with arrowheads (`url(#q-flow-arrow-lit-<uid>)`) and no animation (`SC-15`).
    - Opens `<aside class="q-flow-drawer">` inside the stage (right side above 700px; bottom sheet at `<= 700px`, `SC-16`), populating title, kind badge, sanitized detail HTML, and clickable incoming/outgoing edge buttons (`[data-q-flow-target="<nodeId>"]`). Clicking an edge button moves focus to that neighbor (`SC-10`). If the drawer covers the focused node's box, pans the view so the focused node remains visible (`SC-9`).
  - Clicking a group/lane header (`[data-q-flow-group-header]`):
    - Zooms to fit that group's bounds, dims nodes/edges/groups outside it (`data-q-flow-dim`), closes the drawer, and runs no pulse (`SC-12`).
  - Clicking empty SVG canvas, clicking the drawer close button, or pressing `Escape` clears focus (or exits expand when expanded with no new focus since expanding) (`SC-7`, `SC-11`).
- **Keyboard model (`SC-14`):**
  - Roving `tabindex`: one `.q-flow-node` has `tabindex="0"`, all others `tabindex="-1"`.
  - Arrow keys (`ArrowRight`, `ArrowLeft`, `ArrowDown`, `ArrowUp`) move `tabindex="0"` and DOM focus to the nearest node in that direction and pan to keep it in view.
  - `Enter` / `Space` focuses the node and announces `"<label>, <kind>, <N> upstream, <M> downstream"` (omitting `<kind>, ` when none) in `[data-q-flow-live]`.
  - `+`/`=` zooms in, `-`/`_` zooms out, `0` fits to view, `Escape` clears focus / exits expand.
- **Theme (`SC-8`):**
  - Every color in `kit.css` and SVG attributes uses `var(--q-color-*)` tokens (`--q-color-chart-1` … `--q-color-chart-8` for kind stripes/tags). Theme toggles recolor immediately via CSS without re-layout.

## Data models / schemas

Back-links: [Conceptual model](logic.md#conceptual-model), [Authoring and building](logic.md#authoring-and-building), [Success criteria](logic.md#success-criteria).

```
SCHEMA: catalog.json entry for q-flow
{
  "tag": "q-flow",
  "use_when": "Use when a system, pipeline or architecture has paths, groups or node details the reader will pan, zoom and click through to explore.",
  "parent": null,
  "interactive": true,
  "attributes": [
    {"name": "summary", "required": true, "kind": "text", "description": "One sentence stating what the graph shows; it becomes the graph's accessible label."},
    {"name": "direction", "required": false, "kind": "enum", "values": ["right", "down"], "default": "right", "description": "Flow direction: left to right or top to bottom."},
    {"name": "groups", "required": false, "kind": "enum", "values": ["panels", "lanes"], "default": "panels", "description": "How top-level groups are drawn: tinted panels or stage bands across the flow."}
  ],
  "requires": [["script"]],
  "rules": ["flow-data"],
  "children": "...",
  "example": "<q-flow summary=\"...\">...</q-flow>"
}
```

```
SCHEMA: <q-flow> JSON payload inside <script type="application/json">
{
  "kinds":  { "<kindName>": 1..8 },                                          // optional, ≤8 entries
  "groups": [ { "id": str, "label": str, "parent"?: str } ],                 // optional, acyclic
  "nodes":  [ { "id": str, "label": str, "kind"?: str, "group"?: str, "detail"?: str } ], // required, 1..200
  "edges":  [ { "from": str, "to": str, "label"?: str, "async"?: bool } ]    // optional
}
```

```
SCHEMA: S/evals/flow-evals.json
{
  "skill_name": "writing-html-artifacts",
  "evals": [
    { "id": int, "prompt": str, "expected": "q-flow" | "mermaid" }
  ]
}
```

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **`S/vendor/<lib>/<version>/` for every library other than `kit` and `flow`.** Existing built artifacts and tests pin their hashes.
- **`S/theme/chrome.js` and `S/templates/companion/companion.js`.** Their shell hashes are verified by `checks.py`; `<q-flow>` needs no change to either.
- **`S/scripts/htmlkit/checks.py` `_Scanner` (`:98-211`).** The `external-refs` check depends on its tokenizer; `q-flow` validation lives in `kitcheck.py`.
- **`S/scripts/htmlkit/header.py` and header `schema: 1`.** `flow` and `kit` record versions in the existing `libraries` map.

## Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `python3 S/scripts/pins.py stamp kit 1.0.0` and `python3 S/scripts/kit_docs.py reference` after any edit to `K/kit.js`, `K/kit.css` or `K/catalog.json`.
- Keep every `K/kit.css` selector inside `:where()` (at or below one-class specificity) or register any necessary lift in `tests/test_html_kit_elements.py:3383`.
- Use `var(--q-*)` tokens for every color in SVG and CSS.
- Ensure `data-q-flow-ready` is set on `<q-flow>` whether layout succeeds (`"true"`) or fails (`"error"`).

**Ask**
- Any change to the `<q-flow>` JSON schema or attribute list above.
- Adding any runtime dependency beyond `elkjs`, `d3-zoom` and `d3-selection`.

**Never**
- Accept hand-placed `x`/`y` coordinates in `<q-flow>` data.
- Capture plain mouse-wheel scroll or single-finger touch scroll over a `<q-flow>`.
- Animate edges at rest, on group focus, or when `prefers-reduced-motion: reduce` is active.
- Render node `detail` with unsanitized `innerHTML`; build DOM nodes only from the allow-listed tags (`p`, `ul`, `ol`, `li`, `code`, `pre`, `a`, `em`, `strong`, `b`, `i`, `br`, `span`, `kbd`, `samp`, `sub`, `sup`, `dl`, `dt`, `dd`) and safe attributes (`href` on `<a>` with `#`, relative, `http:`, `https:`, `mailto:`).

## Cross-cutting

Back-links: [Fallbacks](logic.md#fallbacks), [Other surfaces](logic.md#other-surfaces).

- **Security:** Node `detail` HTML is checked at build time by `kitcheck.py` AND sanitized at runtime in `kit.js` using a `<template>` / `DOMParser` walk that clones only allow-listed elements and text nodes, stripping any other element or attribute before insertion into the drawer or text list.
- **No-JS and screen-reader parity:** `inject_flow_fallbacks` writes the full nested group/node/detail/edge `<details open>` list at build time in tier 1, and `kit.js` builds the same list at runtime when absent and closes `<details>` only after SVG layout succeeds.
- **Rollback:** Pages that do not use `<q-flow>` are unaffected.

## Testing strategy

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Success criteria](logic.md#success-criteria).

| File | Coverage |
|---|---|
| `tests/test_html_vendor.py` | `"flow": "0.12.0"` in `libraries.json`; `flow.bundle.js` is a single-file IIFE with no `import`/`export`; `pins.py verify` passes |
| `tests/test_html_kit_catalog.py` | `SECTION_3_4` includes `q-flow`; catalog example allows `<script type="application/json">` inside `q-flow`; `kit_docs.py reference --check` and `quirk-kit.d.ts` tag set match |
| `tests/test_html_kit_check.py` | All `SC-3` failure and warning cases: duplicate id, unknown edge node, undeclared kind, >8 kinds, group cycle, lane mode node outside lane, disallowed detail HTML (`<script>`, `<form>`, `<img src="https://...">`), missing `summary`, >200 nodes failure, 61..200 nodes warning, >30-char edge label warning, coordinate rejection |
| `tests/test_html_builder.py` & `tests/test_html_app.py` | `SC-1`, `SC-2`, `SC-21`: `<q-flow>` auto-includes `flow` and `kit` with license comments; pages without `<q-flow>` omit `flow`; delivery note explains >2 MB when `flow` is inlined; tier-2 JSX with `<q-flow>` inlines `flow` and `kit` |
| `tests/test_html_companion.py` | `SC-20`: a companion screen with `<q-flow>` in `content` builds, inlines `flow` and `kit`, and passes checks |
| `tests/test_html_kit_elements.py` | Browser tests for `SC-4` through `SC-19` and `SC-22`: layout and `data-q-flow-ready`; panels vs `groups="lanes"` (`direction="right"` and `"down"`, nested group inside lane); plain wheel & 1-finger touch do not zoom while Ctrl+wheel, pinch and buttons zoom; expand & Escape; live theme switch without re-layout; clicking a node lights upstream+downstream path, dims unconnected branches (`Refund worker`), runs a constant-speed streaming pulse keeping dashed/solid pattern, opens drawer (right on desktop, bottom sheet at 375px), drawer edge click moves focus; clicking group header zooms & dims without pulse or drawer; keyboard roving tabindex, arrow keys, Enter live announcement, `+`/`-`/`0`/Escape; reduced motion disables pulse; layout error & no-JS open the text list |
| `tests/test_html_kit_examples.py` & `tests/test_html_layout_shapes.py` | `q-flow` catalog example and updated shape examples (`explainer`, `reference`) pass `build`, `check`, `verify` and `verify --no-js` at 375px and 1280px in light and dark |
| `tests/test_writing_html_artifacts_skill.py` | `S/evals/flow-evals.json` schema, uniqueness and balanced `q-flow` vs `mermaid` prompts |

## Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Deferred item | Resolution in this spec |
|---|---|
| How the graph library is vendored | `S/scripts/vendor-build/build-flow.mjs` bundles `elkjs@0.12.0`, `d3-zoom@3.0.0` and `d3-selection@3.0.0` into `S/vendor/flow/0.12.0/flow.bundle.js` (`window.quirkFlow`), pinned in `S/vendor/libraries.json` with EPL-2.0 and ISC license headers |
| How the companion serves the library | Inlined automatically by `assemble.build_tier1` when `content` contains `<q-flow>` (`companion.py:788`) |
| How a tier-2 build detects `<q-flow>` | `kitcheck.needs_flow` scanned over `_kit_sources` in `app.py:270`, inlining `flow` before `kit` |
| ELK settings | `layered`, `hierarchyHandling: "INCLUDE_CHILDREN"`, `edgeRouting: "ORTHOGONAL"`, `shapeCoords: "ROOT"`, `edgeCoords: "ROOT"`, `nodeNodeBetweenLayers: "52"`, `nodeNode: "28"`, `edgeNode: "24"`, `edgeLabels.inline: "true"`, `partitioning.activate: "true"` in lane mode, free ports, main thread |
| Measure-then-lay-out loop | Waits for `document.fonts?.ready`, measures labels with a 2D canvas context in the element's computed font, then runs `elk.layout` before revealing the graph |
| Verify readiness signal | `data-q-flow-ready` (`"true"` or `"error"`) awaited up to 10 s by `verify.mjs` and `harness.mjs` |
| Pulse implementation | SVG `<mask>` with radial gradient circles over a thick (`stroke-width: 6`) clone of each lit edge path, preserving `stroke-dasharray`; constant speed and a fixed emission interval, so per-frame cost is one dot per wave in flight on each lit edge |
| d3-zoom filter | Wheel only with `ctrlKey`/`metaKey`; touch only with `touches.length >= 2` (`touch-action: pan-x pan-y pinch-zoom`); primary mouse drag |
| Graph data in the tag & kit check | `<script type="application/json">` child validated by `_rule_flow_data` and `check_html_warnings` in `kitcheck.py` |
| Coordinate frames, port constraints & node placement | Root coordinates via `elk.json.shapeCoords: "ROOT"` and `elk.json.edgeCoords: "ROOT"`; free port constraints to avoid ELK #1192; default `BRANDES_KOEPF` layered node placement across all valid graph sizes (`1..200`) |
| Band geometry for lanes & nested groups | Top-level lane groups carry `elk.partitioning.partition` `0..k-1`; band cross-axis extents are stretched to `[min, max]` across all lanes while nested groups inside lanes render as tinted panels at their ELK bounds (proven with `elkjs@0.12.0`) |
| Touch handling | `touch-action: pan-x pan-y pinch-zoom` on `.q-flow-svg` plus two-finger `d3-zoom` filter |
| Keeping keyboard-focused node in view | Arrow-key focus change pans the d3-zoom transform when the target node's box falls outside the visible stage |

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- Everything listed under Not in scope in `logic.md#scope-and-non-goals` (node dragging/editing, group collapse, minimap, search, URL deep links, build-time ELK layout, external data-file binding for `q-flow`, lanes running along the flow).
