# Tech spec: `q-schema`, an explorable data model and class diagram element

**Status**: Reviewed (one review round, fixes applied) · Logic spec: [logic.md](logic.md) · Builds on [the q-flow tech spec](/docs/quirk/specs/2026-10-16-q-flow/tech.md) and [the q-flow shapes tech spec](/docs/quirk/specs/2026-10-17-q-flow-shapes/tech.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`, `K` = `S/vendor/kit/1.0.0`, `H` = `S/scripts/htmlkit`, `T` = `tests`. Line numbers are from commit `d0d2618`, except the `K/kit.js` lines, which are re-resolved after the canvas helpers landed (commit `4103840`).

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Shared canvas helpers | `K/kit.js` (new block above `class QFlow`) | Free functions factored out of `QFlow`'s generic canvas methods; `QFlow` keeps its method names as one-line delegates |
| `QSchema` runtime | `K/kit.js` (new `class QSchema`, `define('q-schema', QSchema)`) | Parse, lay out with ELK (per-field-row ports in ER notation, class-to-class edges in class notation), draw cards, marks and markers, focus, drawer, keyboard, text list |
| Styles | `K/kit.css` | Shared chrome selectors widened from `q-flow` to `:is(q-flow, q-schema)`; new `q-schema` card, row, badge and line rules using `--q-*` tokens only |
| Kit check and no-JS fallback | `H/kitcheck.py` | `schema-data` rule, warnings, `needs_flow` matching `q-schema`, `inject_schema_fallbacks` |
| Build wiring | `H/assemble.py`, `H/checks.py` | Inject the schema fallback; the "flow is not inlined" check covers `q-schema` |
| Readiness waits | `S/scripts/verify/verify.mjs`, `T/fixtures/html-kit/harness.mjs` | Wait for `q-flow, q-schema` |
| Catalog, reference, pins, typings | `K/catalog.json`, `S/scripts/kit_docs.py`, `S/references/components.md` (generated), `S/vendor/libraries.json` (restamped), `S/templates/app/project/src/quirk-kit.d.ts` | The new element's contract |
| Skill guidance and evals | `S/SKILL.md`, `S/references/design-reference.md`, `S/templates/report/rules.md`, `S/templates/components/rules.md`, `S/evals/flow-evals.json`, `T/test_writing_html_artifacts_skill.py` | `q-schema` for ER, data model and class diagrams on HTML pages |
| Example page | `S/templates/report/examples/reference.src.html` | The billing model and the parser class diagram |

No new vendored library. The flow bundle (`window.quirkFlow = {ELK, zoom, zoomIdentity, zoomTransform, select}`, built by `S/scripts/vendor-build/build-flow.mjs:26-34`) is reused as is.

Spike result (2026-10-17, elkjs from `S/vendor/flow/0.12.0/flow.bundle.js`): `elk.portConstraints: FIXED_POS` on cards nested in a group under `elk.hierarchyHandling: INCLUDE_CHILDREN` lays out without throwing, and every edge's `startPoint`/`endPoint` lands on its port's centre in ROOT coordinates. ELK #1192 does not reproduce for this shape.

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

### `K/kit.js`
- Module helpers to reuse unchanged: `svgNode` `:2995`, `roundedFlowPath` `:3131`, `sanitizeFlowDetail` `:2891`, `isValidFlowDetail` `:2940`, `isBlankFlowId` `:2936`, `hasCoordKeys` `:2983`, `kitNode` `:250`, `watchChildren` `:278`, `onTheme` `:57`, `uid` `:244`, and the `canvas*` helpers `:3152-3412` (contract 1, landed).
- `QFlow` methods factored (contract 1, landed): `_measureTextFactory`, `_buildControls`, `_buildDrawer`, `_setupZoom`, `_applyTransform`, `_zoomBy`, `_fitBounds`, `_ensureNodeVisible`, `_toggleExpand`, `_setRoving`, `_nearestNeighbor` are now one-line delegates inside `class QFlow` `:3414-5191`.
- Patterns to mirror, not edit: `connectedCallback` `:3419` (Escape, resize refit, `onTheme`, `watchChildren`), `_signature` `:3450`, `_ensureScaffold` `:3638`, `_failLayout` `:3794`, `_setup` `:3816` (`document.fonts.ready`, `window.quirkFlow.ELK` guard), ELK root options in `_runLayout` (`:3845`, options at `:3959`), `collectShapes` and group drawing in `_renderGraph` `:4003`, `_focusGroup` `:5019`, `_clearFocus` `:5108`, `_onNodeKey`/`_onGraphKey` `:5153-5186`.
- New `class QSchema`: insert after `QFlow` ends (`:5191`), before the `define` calls `:5193-5204`; add `define('q-schema', QSchema)` after `define('q-flow', QFlow)` `:5204`.

### `K/kit.css`
- `display:block` list `:35`: add `q-schema`.
- q-flow block `:1046-1372`: chrome rules (expanded fullscreen, stage, svg touch-action, controls, dim, drawer with its `@media (max-width:700px)` bottom sheet, list `details`/`summary`, notice, print) change their leading `q-flow` to `:is(q-flow, q-schema)`. `:is()` keeps the type-selector specificity, so q-flow's cascade is unchanged.
- New `q-schema` rules after the q-flow block.

### `H/kitcheck.py`
- `FLOW_TAG` `:31`: add `SCHEMA_TAG = re.compile(r"<q-schema[\s/>]", re.I)`.
- `KNOWN_RULES` `:33-35` and `_RULES` `:1394-1402`: add `"schema-data"`.
- `needs_flow` `:97-102`: also true when `SCHEMA_TAG` matches.
- Reuse `_check_and_sanitize_flow_detail` `:900-937`, `_FLOW_COORD_KEYS`, `_FLOW_MAX_KINDS` `:871-883`.
- New `_validate_schema_node(node, report_fail, report_warn)` near `_validate_flow_node` `:995`; new `_rule_schema_data` next to `_rule_flow_data` `:1253`.
- `check_html_warnings` `:1261-1281`: add a `SCHEMA_TAG` branch alongside the flow one, gated on `"q-schema" in catalog.elements`.
- New `_render_schema_fallback_html(parsed)` and `inject_schema_fallbacks(html)` after `inject_flow_fallbacks` `:1366-1391`, with their own block and closer regexes.

### `H/assemble.py`, `H/checks.py`, `H/app.py`
- `assemble.py:524` and `:529`: wrap the `inject_flow_fallbacks(...)` result in `inject_schema_fallbacks(...)`.
- `checks.py:389-394`: the flow check fires on `kitcheck.needs_flow(text)` instead of `FLOW_TAG.search`, and names the tag found (`q-flow` or `q-schema`) in its message.
- `assemble.py:284` and `app.py:275` need no edit (they call `needs_flow`).

### Readiness waits
- `S/scripts/verify/verify.mjs:229,234` and `T/fixtures/html-kit/harness.mjs:159,164,190`: selector `"q-flow, q-schema"`; the predicate stays `hasAttribute("data-q-flow-ready")` (contract 3); messages say "graph" or name both tags.

### Catalog, docs, typings
- `K/catalog.json`: append a `q-schema` element after `q-flow` (`:361-404` is the shape to copy).
- `S/scripts/kit_docs.py:95-97`: the hard-coded sentence about `q-flow` inlining the flow library also names `q-schema`.
- `S/templates/app/project/src/quirk-kit.d.ts:24`: add `'q-schema': KitElementProps`.
- `S/SKILL.md:138` and `:148`; `S/references/design-reference.md:200`; `S/templates/report/rules.md:29-30`; `S/templates/components/rules.md:26`; the companion rule that an interactive graph goes in screen `content`, never in an option's `html` (`S/templates/companion/rules.md:36`, `S/references/companion.md:67,71`), and the tier-2 auto-inlining note (`S/templates/app/rules.md:53,55`) also name `q-schema`.
- `S/evals/flow-evals.json` ids 14 and 16.

## Contracts & interfaces

### 1. Shared canvas helpers (factoring, no behaviour change)
Back-links: [Key decisions and rationale](logic.md#key-decisions-and-rationale), [Decisions Locked](logic.md#decisions-locked).

```
CONTRACT: module-level functions in K/kit.js, each taking the host element first
canvasMeasureFactory(host) -> (text, sizePx, weight?) -> int
canvasBuildControls(host, noun)            // noun: 'graph' | 'model' | 'diagram'
canvasBuildDrawer(host, label)             // label: aria-label of the aside
canvasSetupZoom(host)
canvasApplyTransform(host, x, y, k)
canvasZoomBy(host, factor)
canvasFitBounds(host, bounds, reserveDrawer)
canvasEnsureVisible(host, boxId, avoidDrawer)
canvasToggleExpand(host)
canvasSetRoving(host, boxId, moveDomFocus)
canvasNearestNeighbor(host, fromId, key, order) -> id | null   // order: ids for the wrap-around fallback
```

- **Host field contract** (read and written by the helpers, already QFlow's names): `_stage`, `_svg`, `_viewport`, `_drawer`, `_transform`, `_bounds`, `_nodeBoxes` (id → `{x, y, width, height}`, ROOT coordinates), `_nodeElements` (id → focusable SVG `g`), `_expandBtn`, `_d3Zoom`, `_d3Selection`, `_rovingId`, `_focusedAfterExpand`.
- **Host method contract**: helpers that call back (`canvasBuildControls`, `canvasSetRoving`) call `host._zoomBy`, `host._fitBounds`, `host._toggleExpand`, `host._ensureNodeVisible`, so both classes keep those method names.
- **Preconditions and errors**: unchanged from today's methods: each helper returns without effect when `_stage` (or `_svg` for zoom setup, or the box for `canvasEnsureVisible`) is missing, and zoom degrades to setting the viewport transform when `window.quirkFlow.zoom` is absent.
- **Postcondition**: each `QFlow` method listed in Code references becomes a one-line delegate with the same signature, passing the exact strings it uses today (`canvasBuildControls(this, 'graph')` yields "Graph controls" and "Expand graph"; `canvasBuildDrawer(this, 'Node details')`; `_nearestNeighbor` passes `this._data.nodes` ids as `order`). Every attribute, class, aria string, number and fallback is byte-identical in effect. The existing q-flow browser tests in `T/test_html_kit_elements.py` (including `FLOW_SHAPES`) pass unmodified.
- **Invariant**: no other `QFlow` method changes. In particular `_parseData`, `_populateList`, `_runLayout`, `_renderGraph`, `_focusNode`, `_openDrawer`, `_openLinkedFlow`, `_focusGroup`, `_clearFocus`, `_handleEscape`, `_onNodeKey`, `_onGraphKey` and the pulse methods are not edited (DO-NOT-CHANGE).

### 2. Data contract
Back-links: [Conceptual model](logic.md#conceptual-model), [Class notation](logic.md#class-notation), [Decisions Locked](logic.md#decisions-locked).

```
SCHEMA: <q-schema summary="…" notation="er|class"> with one <script type="application/json"> child
{
  kinds?: { [name]: 1..8 },
  groups?: [{ id, label, parent? }],
  entities: [{
    id, label, kind?, group?, detail?,            // detail: short HTML, q-flow detail rules
    stereotype?: "interface" | "abstract" | "enum",               // class only
    fields?: [ER:    { name, type, key?: K | K[], nullable?: bool, note? }
              class: { name, type?, visibility?: V, static?: bool, note? }],
    methods?: [{ signature, visibility?: V, static?: bool, abstract?: bool, note? }]   // class only
  }],
  relationships?: [
    ER:    { from: "entity.field", to: "entity.field", from_card: C, to_card: C, label? },
    class: { from: "entity", to: "entity", type: R, from_mult?: M, to_mult?: M, label?, directed?: bool }
  ]
}
K = "PK" | "FK" | "UK"
C = "zero-or-one" | "one" | "zero-or-many" | "one-or-many"
V = "public" | "private" | "protected" | "package"      // drawn + - # ~
R = "inherits" | "implements" | "composition" | "aggregation" | "association" | "dependency"
REGEX (M): ^(\*|\d+|\d+\.\.(\d+|\*))$  and for n..m, n <= m
```

- `notation` absent means `er`. ER `fields` is required and non-empty per entity; class `fields` and `methods` are optional, and when present must be lists (an explicit `null` fails). An optional string that is present must be non-blank (a whitespace-only `label` fails; it is not treated as absent). An explicit `null` on an optional scalar (`label`, `note`, `kind`, `group`, a multiplicity) means absent, as in q-flow; only the member lists reject `null`.
- An ER end splits on the first `.`: entity id before it, field name after. Entity ids containing `.` fail ("entity ids may not contain '.'").
- Ids, labels, names, types, signatures and notes are non-blank strings (`isBlankFlowId` semantics). `directed` is only valid on `association`.
- Both parsers return the same cleaned shape; JS: `{notation, kinds, groups, groupMap, entities, entityMap, relationships}`; Python: the same keys in snake_case, or `None` on any failure.

### 3. Runtime (`QSchema`)
Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Decisions Locked](logic.md#decisions-locked).

- **Class shape**: `class QSchema extends HTMLElement`, `observedAttributes` `['summary', 'notation']`, lifecycle mirroring QFlow (`connectedCallback` Escape/resize/`onTheme`/`watchChildren`, `_signature`, `_setup` waiting on `document.fonts.ready`, stale-`seq` guard). Canvas methods are one-line delegates to contract 1, with `canvasBuildControls(this, 'model')` in ER notation and `'diagram'` in class notation, and `canvasBuildDrawer(this, 'Entity details')` or `'Class details'`.
- **Ids**: group and entity ids share one namespace, as group and node ids do in q-flow; a clash is a duplicate-id failure.
- **Chrome attributes and classes**: QSchema reuses q-flow's chrome names for everything contract 1 and the shared CSS style: `q-flow-stage`/`data-q-flow-stage`, `data-q-flow-svg`, `data-q-flow-viewport`, `data-q-flow-controls`, `data-q-flow-action`, `data-q-flow-drawer` (+`-head`, `-close`, `-kind`, `-detail`, `-edges`), `data-q-flow-edge-btn` for relationship buttons (44px touch targets on phones), `--q-flow-kind-color` for the kind accent, `data-q-flow-live`, `data-q-flow-notice`, `q-flow-list`/`data-q-flow-list`/`data-q-flow-list-body`, `data-q-flow-group`/`-group-box`/`-group-header`, `data-q-flow-dim`, `data-q-flow-lit`, `data-q-flow-selected`, `data-q-flow-expanded`, and **`data-q-flow-ready`** (`true` after drawing, `error` on failure, removed at the start of setup). Schema-specific parts use `data-q-schema-*`.
- **Test hooks** (schema-specific, stable):
  - card `g[data-q-schema-entity=ID]` (focusable, roving tabindex, `role="button"`, `aria-label` = the announce text), with `data-q-schema-stereotype` when set;
  - row `[data-q-schema-field="NAME"]` / `[data-q-schema-method="INDEX"]` inside the card, each with `data-q-schema-row-y` (row centre, ROOT coordinates); key badges `[data-q-schema-badge="PK"]` etc. carry the text;
  - fold row `[data-q-schema-more]` with text `+N more`;
  - line `g[data-q-schema-rel=INDEX]` with `data-q-schema-from`, `data-q-schema-to` (entity ids), and `data-q-schema-from-mark` / `data-q-schema-to-mark` set to the cardinality (ER) or to `triangle`, `diamond-filled`, `diamond-hollow`, `arrow`, `none` (class); its path's first and last points are the ends;
  - relationship label `[data-q-schema-rel-label]`, multiplicity `[data-q-schema-mult="from|to"]`.
- **ER layout**: `elk.algorithm layered`, `elk.direction RIGHT`, plus q-flow's root options (`INCLUDE_CHILDREN`, `ORTHOGONAL`, ROOT shape and edge coords, its spacing). Each card is an ELK node with `elk.portConstraints: FIXED_POS`; every shown row a relationship uses gets a WEST port at `x = -1` and an EAST port at `x = width`, both at the row centre `y`. A relationship is handed to ELK from the `to` field's EAST port to the `from` field's WEST port. Groups are compound nodes as in q-flow's `buildElkGroup`. Self-relationships are not handed to ELK.
- **Class layout**: `elk.direction DOWN`, no ports. ELK edge direction: `inherits` and `implements` from `to` to `from` (parent first), with `elk.layered.priority.direction: 10`; every other type from `from` to `to` with priority 0, except that an edge whose ELK target is a generalisation ancestor of its ELK source (reachable over `inherits`/`implements` edges) is handed to ELK reversed. Generalisation wins any conflict (logic spec amendment 2026-10-17), so in SC-26 Ast sits above BinaryExpr although BinaryExpr aggregates Ast. Drawing always restores the data's direction.
- **Self-relationship (SC-9)**: drawn as a rounded loop (`roundedFlowPath`) leaving the card's east edge at the `from` row and returning at the `to` row, 24px out; its label sits beside the loop. A card with a self-relationship is handed to ELK 24px plus the label width wider than it is drawn (ports stay at the drawn width), so neighbours keep clear of the loop; bounds include it.
- **Card**: header (stereotype line `«…»` when set, label, kind accent from `--q-color-chart-N`), then rows; class cards draw a rule between the attribute and method compartments. Row text: ER `name  type  [badges]`; class `{+-#~} name: type` or `{+-#~} signature`, static underlined, abstract italic. Width from `canvasMeasureFactory`.
- **Fold**: ER keeps every field with a key or used by a relationship, then the rest in order until 8 shown, preserving the data order; class gives attributes and methods 4 rows each when both overflow, otherwise the shorter one keeps all its rows and the other takes the rest of the 8. `+N more` counts the hidden rows; no row is hidden when the total is 8 or fewer.
- **Marks**: SVG `<marker>`s per mark kind with `orient="auto-start-reverse"` stroked in `var(--q-color-*)`, so theme changes need no redraw (`_applyTheme` stays empty, as in QFlow). Marker ids carry the element's `uid` (as q-flow's `q-flow-arrow-` ids do) so two models on a page never share one. ER: the `from` end carries `from_card`'s mark and the `to` end `to_card`'s. Class:

  | Type | Line | `from` end | `to` end |
  |---|---|---|---|
  | `inherits` | solid | `none` | `triangle` |
  | `implements` | dashed | `none` | `triangle` |
  | `composition` | solid | `diamond-filled` | `none` |
  | `aggregation` | solid | `diamond-hollow` | `none` |
  | `association` | solid | `none` | `arrow` when `directed`, else `none` |
  | `dependency` | dashed | `none` | `arrow` |

  `from_mult` is drawn beside the `from` end and `to_mult` beside the `to` end. Labels are placed from ELK's label position when present, else the path midpoint.
- **Focus**: clicking a card, its `+N more` row, or pressing Enter on it lights the card, its relationships and the cards at their other ends (direct neighbours only), dims the rest with `data-q-flow-dim`, opens the drawer and announces in the live region. Escape, empty-canvas click and the drawer close button clear it. Group header click zooms to the group (`canvasFitBounds`), dims everything outside, opens no drawer. No pulse, no animation; zoom and fit use the same d3 transitions as QFlow (none are eased there today).
- **Drawer**: heading, kind, stereotype, detail (sanitized), then every field or attribute and method (contract 5 text), then one button per relationship (contract 5 text) that focuses the other entity.
- **Text list**: `details` titled "Data model as a list" or "Class diagram as a list", same markup and text as the Python fallback (contract 5).
- **Failure**: unparseable data, an unknown `notation` value, any contract 4 failure, a missing ELK, or a layout rejection sets `data-q-flow-ready="error"`, shows the contract 5 failure notice and opens the list (which shows whatever parsed, or is empty when parsing failed).

### 4. Kit check (`schema-data`)
Back-links: [SC-3](logic.md#authoring-and-building), [SC-4](logic.md#authoring-and-building), [SC-29 and SC-30](logic.md#class-diagrams).

- `_validate_schema_node(node, report_fail, report_warn) -> Optional[dict]`; `_rule_schema_data(node, report, index)` calls it with a no-op warn; `check_html_warnings` calls it with a no-op fail.
- Failures: every row of SC-3 and SC-29, with these thresholds: more than 8 kinds, more than 80 entities. An unknown `notation` value is reported by the catalog's enum check (`<q-schema> notation="uml" is not one of er, class`, `H/kitcheck.py:589-591`), as SC-29 states after the 2026-10-17 amendment; the rule then validates nothing further and adds no second message. Precondition: the catalog's `requires` check reports a missing `<script>`; the validator returns `None` silently in that case, as `_validate_flow_node` does.
- Warnings: every row of SC-4 and SC-30; more than 30 entities, more than 40 fields (ER) or members (class).
- Messages start `<q-schema>` and name the offending id, field or value as SC-3/4/29/30 do. Inheritance loops are detected over `inherits` and `implements` edges.
- JS `_parseData` rejects the same failure set (it does not warn).

### 5. Shared text (Python fallback and JS list must match exactly)
Back-links: [SC-12](logic.md#focusing), [SC-20](logic.md#text-list-and-fallbacks), [SC-28 and SC-31](logic.md#class-diagrams).

- **Plural** of a label: ends in consonant + `y` → drop `y`, add `ies`; ends in `s`, `x`, `z`, `ch`, `sh` → add `es`; else add `s`. Applied to the label as written.
- **Cardinality words**: `zero or one`, `one`, `zero or many`, `one or many`; a `many` word takes the plural label.
- **ER sentence**: `Each {To} {label|has} {from_card words} {From form}, and each {From} has {to_card words} {To form} ({from} → {to})`, e.g. `Each Customer has zero or many Subscriptions, and each Subscription has one Customer (subscription.customer_id → customer.id)`.
- **Class sentence**: `{From} inherits from {To}` · `implements {To}` · `is composed of [{to_mult} ]{To}` · `aggregates [{to_mult} ]{To}` · `is associated with [{to_mult} ]{To}` · `depends on [{to_mult} ]{To}`; then, when either exists, ` (…)` holding first `{from_mult} {From} per {To}` and then the label, joined by `; `, e.g. `BinaryExpr aggregates 2 Ast (operands)`, `Order is associated with 1 Customer (0..* Order per Customer; places)`.
- **Entity line**: `<strong>{Label}</strong>` then ` ({kind}, {stereotype})` with whichever of the two exist, e.g. `Parser (api, interface)`, `Customer (core)`, `Ast (api, abstract)`.
- **ER field line**: `{name}: {type}` then `, {keys…}` in the data's order, `, can be empty` when `nullable`, then ` ({note})`, e.g. `subscription_id: int, FK, can be empty`.
- **Class member line**: `{visibility word} [static ][abstract ]{name: type | name | signature}` then ` ({note})`; a missing visibility shows none.
- **Drawer relationship button**: ER `{label|has}: {Other} ({from field name} → {to field name})` with names as written, e.g. `has: Customer (customer_id → id)` and `generates: Charge (subscription_id → id)`; class, from the `from` side `{label|verb}: {Other}` with verbs `inherits from`, `implements`, `composed of`, `aggregates`, `associated with`, `depends on`; from the `to` side `{reverse verb}: {Other}` with `inherited by`, `implemented by`, `part of`, `aggregated by`, `associated with`, `used by`.
- **Announce**: `{Label}[, {kind}][, {stereotype}], {n} {field|fields}, {m} {relationship|relationships}` in ER notation and `members` in class notation; `n` counts every field or member (not only shown ones) and `1` takes the singular, e.g. `Subscription, billing, 6 fields, 2 relationships`.
- **Notice and title**: notice `JavaScript is off, so this data model is shown as a list below.` (class: `class diagram`); summary `Data model as a list` or `Class diagram as a list`; layout failure notice `This data model could not be drawn.` (class: `class diagram`).
- **List markup**: wrapper identical to q-flow's fallback (`div.q-flow-stage[data-q-flow-stage]` holding the JavaScript-off notice, then `details.q-flow-list[data-q-flow-list][open]`), body `ul` of groups (`li[data-q-flow-list-group]`, nesting as q-flow) and entities (`li[data-q-schema-list-entity=ID]` with a nested `ul` of field/member lines and an optional `div[data-q-flow-list-detail]`), then `p` "Relationships" and `ul[data-q-schema-list-rels]` with one `li` per sentence; both are omitted when the model has no relationships. The browser list stops nesting group `ul`s at depth 64 (deeper groups join the list at that depth in the same reading order), because Chromium crashes laying out list DOM about 1,000 levels deep; the text is unchanged.

### 6. Build, checks and waits
Back-links: [Data flow](logic.md#data-flow), [SC-2](logic.md#authoring-and-building), [SC-24 and SC-25](logic.md#other-surfaces).

- `needs_flow(text)` is true for `q-flow` or `q-schema`; the flow library is inlined once per page either way.
- `inject_schema_fallbacks` follows `inject_flow_fallbacks`' skip rules: a block already holding a `data-q-flow-list` element (an attribute on a tag outside the JSON script; the same text inside the data does not count), a self-closed tag, no `summary`, or data that fails validation is left alone.
- `checks.py` fails a page with `q-schema` and no `flow@` label.
- verify and the harness wait until every `q-flow` and `q-schema` has `data-q-flow-ready`.

### 7. Catalog entry and skill text
Back-links: [Choosing](logic.md#choosing), [Scope and non-goals](logic.md#scope-and-non-goals).

```
SCHEMA: catalog.json element
tag "q-schema", parent null, interactive true,
attributes: summary (required, text), notation (enum ["er", "class"], default "er"),
requires [["script"]], rules ["schema-data"],
use_when "Use when …" (data models, ER and class diagrams on HTML pages),
children: one-line prose of contract 2, example: the billing model (ER, one <script type="application/json">)
```

- Skill text says: data model, ER and class diagrams on HTML pages use `<q-schema>` (`notation="class"` for class diagrams); Mermaid stays for diagrams inside Markdown, state charts and sequence diagrams.
- `flow-evals.json` ids 14 and 16 expect `"q-schema"`; `test_flow_evals_are_balanced_and_unique` accepts `"q-schema"` and requires at least 2 of it, keeping its other bounds.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

Contract 2 is the data model. The Python cleaned dict per entity: `{id, label, kind, group, stereotype, detail_html, fields: [...], methods: [...]}` (the fallback lists every row, so it needs no fold); per relationship: ER `{from_entity, from_field, to_entity, to_field, from_card, to_card, label}`, class `{from_entity, to_entity, type, from_mult, to_mult, label, directed}`.

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **`QFlow` methods outside contract 1's list** (`K/kit.js:3414-5191`). Specs 2 (q-flow traces) and 3 (q-sequence) edit them in parallel; touching them causes merge conflicts.
- **Factored `QFlow` behaviour.** Every string, attribute, number and fallback in contract 1's methods stays the same; the q-flow browser tests pin them.
- **q-flow's ELK root options and free ports** (`K/kit.js:3959`). QSchema sets its own options in its own graph; q-flow keeps free ports for ELK #1192.
- **`_validate_flow_node`, `_render_flow_fallback_html`, `inject_flow_fallbacks`** (`H/kitcheck.py:995-1391`). Builder and companion tests pin them; schema code sits beside them.
- **The q-flow catalog entry and `flow-data` rule.** `T/test_html_kit_catalog.py` pins them.
- **`data-q-flow-ready` semantics** (removed at setup, `true` or `error` after). verify and the harness depend on them.

## Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `python3 S/scripts/pins.py stamp kit 1.0.0` after editing `K/kit.js` or `K/kit.css`, and `python3 S/scripts/kit_docs.py reference` after editing `K/catalog.json` or `S/scripts/kit_docs.py`.
- Keep the Python and JS failure sets and text (contract 5) identical.
- Use `--q-*` tokens only in `kit.css`, and `var(--q-color-*)` in SVG attributes.
- Run browser tests through the BUG-14 relay on this machine (Testing strategy).

**Ask**
- Any change to contract 2, a message in contract 4, or a string in contract 5.
- Any edit to a `QFlow` method outside contract 1.

**Never**
- Write coordinates, positions or sizes from the data.
- Hide a key field or a related field behind `+N more` in ER notation.
- Animate anything on focus.
- Hand ELK a self-relationship.

## Cross-cutting

Back-link: [Text list and fallbacks](logic.md#text-list-and-fallbacks).

- **Security**: author text reaches the DOM only via `textContent` and `setAttribute`; `detail` goes through `sanitizeFlowDetail` (JS) and `_check_and_sanitize_flow_detail` (Python); the fallback escapes every string.
- **Size**: a `q-schema` page carries the flow bundle (~1.5 MB) once; the existing page-weight warning applies.
- **Rollback**: removing the element leaves q-flow unchanged apart from contract 1's delegates.

## Testing strategy

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Success criteria](logic.md#success-criteria).

| File | Coverage |
|---|---|
| `T/test_html_kit_check.py` (new q-schema section after the q-flow one; helper like `flow_markup`) | One case per SC-3, SC-4, SC-29 and SC-30 row; the billing model and the parser diagram pass with no warnings; `entity.field` ends with dots in the field name |
| `T/test_html_builder.py` (near the q-flow fallback tests `:921-1000`) | Library order with `q-schema` alone and with `q-flow` (flow once); the injected list carries SC-20's sentence, Charge's 15 field lines, and SC-31's six sentences |
| `T/test_html_kit_elements.py` (new `SCHEMA_*` page constants and a module fixture like `flow_shapes_page`) | Line ends on the named rows (`data-q-schema-row-y` vs path end points, ±1px); each cardinality and UML mark; Charge shows customer_id and subscription_id with `+7 more`; class fold table of SC-27; parents above children; self-loop path; focus lights direct neighbours and dims the rest (SC-12, SC-28); drawer lists every field and member with contract 5 text; relationship buttons refocus (SC-13); `+N more` click (SC-14); clear focus (SC-15); group focus (SC-16); keyboard (SC-17); theme toggle recolors with no re-layout (SC-10); expand (SC-11); 375px bottom sheet (SC-19); JS list text equals the Python fallback text; no-JS fallback (SC-21); layout failure notice (SC-22); two models independent (SC-5); all existing q-flow tests unchanged and green |
| `T/test_html_kit_catalog.py` | `SECTION_3_4` gains the `q-schema` row last; the scripts branch for `q-schema`; `KNOWN_RULES` gains `schema-data` |
| `T/test_html_kit_examples.py`, `T/test_html_kit_docs.py` | The catalog example builds, checks and verifies with and without JS; `kit_docs.py reference --check` |
| `T/test_html_app.py` (`:540-545`, `:1029-1043`) | Typings match the catalog; tier-2 inlines flow for `q-schema` |
| `T/test_html_companion.py` (`:839-855`) | `q-schema` in screen `content` |
| `T/test_html_vendor.py` | `pins.py verify` passes after restamping |
| `T/test_writing_html_artifacts_skill.py:137` | Evals accept `q-schema` and stay balanced |

BUG-14 (`BUGS.md`): on the author's machine Chrome stalls under a Python ancestor, so browser tests time out unless `harness.mjs`/`verify.mjs` run through a shell-started node relay. The orchestrator runs the relay and passes the shim directory as `SHIM` in each task prompt; with it, browser tests run as:

```
COMMAND: PATH="$SHIM:$PATH" python3 -m pytest -q -p no:cacheprovider tests/test_html_kit_elements.py
```

Without `SHIM` (other machines, CI) run the same command without the `PATH` prefix. Visual check: build the example page and run `quirk_html.py verify` at 375px and 1280px in both themes the same way, and look at the screenshots.

## Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Deferred item | Resolution |
|---|---|
| Which canvas pieces are factored | Contract 1's list; the rest of QFlow is fenced because specs 2 and 3 edit it |
| ELK settings for field ports | Contract 3, ER layout: FIXED_POS ports at row centres, east to west; spike passed with groups |
| "+N more" and ports | Folded rows never carry a port; ER never folds a related field |
| Crow's-foot geometry at low zoom | SVG markers in user space sized to stay legible at the 0.2 zoom floor; implementer's choice within contract 3 |
| Python and JS staying in step | Contract 5 is the single text contract; a browser test compares the JS list with the Python fallback |
| Detecting `q-schema` for the library | `needs_flow` matches both tags (contract 6) |
| UML marker geometry and class direction | Contract 3, class layout and marks |

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- Changing q-flow's behaviour, data, attributes or check rules.
- A Python-side layout or a build-time render.
- Ports in class notation, generics, notes on classes, member-level relationship ends, composite keys.
- Moving q-flow's chrome to new attribute names.
