# Tech spec: decisions, loops and subprocesses in `q-flow`

**Status**: Reviewed (one review round, advisory fixes applied) · Logic spec: [logic.md](logic.md) · Builds on [the q-flow tech spec](/docs/quirk/specs/2026-10-16-q-flow/tech.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`, `K` = `skills/writing-html-artifacts/vendor/kit/1.0.0`, `H` = `skills/writing-html-artifacts/scripts/htmlkit`. Line numbers are from commit `efa903b`.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Kit check & no-JS fallback | `H/kitcheck.py` | Validate `shape`, `flow`, `loop`; resolve `flow` targets against the page's `<q-flow>` ids; warn on long decision labels, duplicate exit labels and unmarked cycles; render decisions, loops and links in the injected list |
| Kit runtime & styles | `K/kit.js`, `K/kit.css` | Parse the new fields, reverse loop edges for ELK, draw diamonds, double-edged boxes, return lines and self-loop arcs, keep loop edges out of the focus walk and the pulse, add "Open flow" to the drawer, write the matching text list |
| Catalog, reference & pins | `K/catalog.json`, `S/references/components.md` (generated), `S/vendor/libraries.json` (restamped) | Document the new fields in `children` and the example |
| Skill guidance & evals | `S/SKILL.md`, `S/references/design-reference.md`, `S/templates/report/rules.md`, `S/templates/components/rules.md`, `S/evals/flow-evals.json` | `q-flow` for every flowchart on an HTML page |
| Example page | `S/templates/report/examples/explainer.src.html` | The checkout retry flow with a decision, a retry loop, a self-loop poll and a linked subprocess graph |

No new library, no new kit-check rule name, no catalog attribute change.

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

### `H/kitcheck.py`
- `_Index` `:495-560`: add a public `nodes_of(key: str) -> list[_Node]` returning `self._nodes.get(key, [])` in document order.
- `_validate_flow_node(node, report_fail, report_warn)` `:934`: add keyword `page_flow_ids: Optional[frozenset[str]] = None`. Per-node checks go in the node loop `:1053-1096`, per-edge checks in the edge loop `:1098-1136` (copy the `async` boolean check at `:1125-1127` for `loop`), graph-level decision and cycle checks after the edge loop and before the return at `:1138`. The cleaned node dict `:1088-1096` gains `shape` and `flow`; the cleaned edge dict `:1128-1136` gains `loop`.
- `_rule_flow_data` `:1149`: pass `page_flow_ids` built from `index.nodes_of("q-flow")` ids, excluding `node` itself.
- `check_html_warnings` `:1153` and `inject_flow_fallbacks` `:1233`: keep passing no `page_flow_ids` (target resolution is a failure, never a warning, and the fallback renders the id as given).
- `_render_flow_fallback_html` `:1176-1226`: `render_node` `:1186-1205` gains the shape meta, decision exits, loop entries and the subprocess link.
- `KNOWN_RULES` `:33-35` and `_RULES` `:1261-1269`: unchanged.

### `K/kit.js`
- `_parseData` `:3126-3253`: node loop `:3181-3212` and `cleanNode` `:3203`; edge loop `:3226-3233` and the clean edge `:3234`. Graph-level decision checks after the edge loop.
- `_populateList` `:3292-3383`: `renderNodeItem` `:3311-3345`.
- `_runLayout` `:3448-3590`: node sizing `:3451-3459`, edge building `:3530-3545`.
- `_renderGraph` `:3592-4042`: bounds `:3626-3682`, markers `:3701-3723`, edge points and fallback `:3811-3835`, edge group `:3858-3864`, base path `:3865-3877`, label `:3895-3923`, node drawing `:3937-4019`.
- `_focusNode` `:4249-4415`: upstream BFS `:4260-4279`, downstream BFS `:4281-4300`, edge records `:4368-4396`, live text `:4413`.
- `_openDrawer` `:4486-4578`: insert the flow section after the detail `:4525-4530`, before the edge sections `:4575`.
- `_toggleExpand` `:4213-4230`, `_fitBounds` `:4148-4170`, `_setRoving` `:4700`.

### `K/kit.css`
- Node focus-visible `:1103-1110` and selected `:1112-1115` target `> rect:where([data-q-flow-box])`; widen to `> :where([data-q-flow-box])` so the diamond polygon gets the same ring.
- Drawer block `:1150-1266`: add the flow section and its button next to `[data-q-flow-edge-btn]` `:1239`.

### Docs, catalog, evals, example
- `K/catalog.json:360-405` (`use_when`, `children` and `example` of `q-flow`).
- `S/SKILL.md:138`, `S/references/design-reference.md:200`, `S/templates/report/rules.md:30`, `S/templates/components/rules.md:26`.
- `S/evals/flow-evals.json` (16 evals, 8 `q-flow`, 8 `mermaid`).
- `S/templates/report/examples/explainer.src.html:16-36` (the existing retry-queue `q-flow`).

## Contracts & interfaces

### 1. Data contract
Back-links: [Conceptual model](logic.md#conceptual-model), [Decisions Locked](logic.md#decisions-locked).

```
SCHEMA: additions to the <q-flow> JSON payload
nodes[i].shape?: "box" | "decision" | "subprocess"   // default "box"
nodes[i].flow?:  str                                  // non-empty; only when shape == "subprocess"
edges[i].loop?:  bool                                 // default false
```

- **Exits** of a decision are all edges whose `from` is that node, loop edges and a self-loop included, in `edges` order.
- **Effective loop:** an edge is a loop when `loop === true` or `from === to`. Both runtimes carry the effective value in the cleaned edge (`loop: true` for a self-loop even if unmarked).
- **Forward edges** are edges whose effective loop is false.

### 2. Kit check (`kitcheck.py`)
Back-links: [Kit check](logic.md#kit-check), [Subprocess links](logic.md#subprocess-links).

```
CONTRACT:
def _validate_flow_node(node: _Node, report_fail: Report, report_warn: Report, *, page_flow_ids: Optional[frozenset[str]] = None) -> Optional[dict[str, Any]]
class _Index:
    def nodes_of(self, key: str) -> list[_Node]
```

Failures (all at the `<q-flow>` start line, through `report_fail`, so the graph returns `None`):

| Case | Message |
|---|---|
| `shape` not one of the three strings | `<q-flow> node "<id>" has unknown shape "<shape>"; use box, decision or subprocess` |
| decision with fewer than 2 exits | `<q-flow> decision "<id>" needs at least 2 exits` |
| decision exit with missing or empty label | `<q-flow> every exit of decision "<id>" needs a label` |
| `flow` present on a node whose shape isn't subprocess | `<q-flow> node "<id>" names a flow, but only a subprocess can name a flow` |
| `flow` on a subprocess but not a non-empty string | `<q-flow> node "<id>" flow must be the id of another q-flow` |
| `page_flow_ids` given and `flow` not in it (an element's own id is never in it) | `<q-flow> flow "<flow>" names no q-flow on this page` |
| `loop` present and not a boolean | `<q-flow> edge loop must be true or false` |

Warnings (through `report_warn`; never affect `passed`):

| Case | Message |
|---|---|
| decision label longer than 24 characters | `<q-flow> decision "<id>" label is <N> characters: decision labels over 24 characters overflow the diamond` |
| two exits of one decision with the same label (exact string match) | `<q-flow> decision "<id>" has two exits labelled "<label>"` |
| a strongly connected component of 2+ nodes over forward edges | `<q-flow> has a cycle with no loop edge through "<a>", "<b>", ...: mark the return edge with loop: true` |

- Cycle warning: one per component, node ids in `nodes` order, components ordered by their first node. Self-loops never produce it.
- Invariants: existing messages and their order are unchanged; a graph with none of the new fields validates and renders byte-identically to today.

### 3. Fallback and runtime text list (same text in both)
Back-links: [Text list and no-script fallback](logic.md#text-list-and-no-script-fallback).

Pre: a graph that passed contract 2 (the fallback is only injected for a graph with zero failures, `inject_flow_fallbacks` `:1233-1258`; the runtime list is written from `_parseData`'s clean data). Post: the text below. Invariant: a node with none of the new fields gets exactly today's entry.

For each node `li[data-q-flow-list-node]`:
- Title: `<strong>label</strong>`, then ` (meta)` where meta joins, with `", "`, the shape when it isn't `box`, then the kind. `Paid? (decision, worker)`; `Ship (worker)`; `Status poller` has no meta.
- Subprocess with `flow`: after the title, `: ` then `<a href="#<flow>">opens the "<flow>" graph</a>`.
- Decision: after the title, `: ` then the exits joined by `", "`. A forward exit reads `<label> → <target label>`; a loop exit reads `<label> ↩ <target label>`; ` (async)` follows an async exit. The decision gets no nested edge list.
- Other nodes keep today's nested `ul` of outgoing edges. A forward edge stays `→ <target> (<label>, async)` as today. A loop edge reads `↩ returns to <target label>`, followed by `: <label>` when it has one and ` (async)` when it is async. A self-loop's target reads `itself`.
- Python escapes every label, kind and id with `html_lib.escape` (`quote=True` in attributes); JS sets text with `textContent` and the link with `setAttribute('href', '#' + flow)`.

### 4. Runtime (`kit.js`, `kit.css`)
Back-links: [Drawing](logic.md#drawing), [Focus and pulse](logic.md#focus-and-pulse), [Subprocess links](logic.md#subprocess-links).

- **Parse.** `_parseData` applies every failure in contract 2 except target resolution, and still returns `null` on any of them (the existing fail-hard notice). It carries `shape` (default `"box"`), `flow` (or `null`) on clean nodes and the effective `loop` on clean edges. No warnings in JS.
- **Node attributes.** Every `g.q-flow-node` gets `data-q-flow-shape="box|decision|subprocess"`. Its `aria-label` and the live announcement at `:4413` include the shape after the label when it isn't `box` (`"Paid?, decision, worker, 2 upstream, 2 downstream"`).
- **Decision drawing.**
  - The label wraps on word boundaries into lines no wider than 120px measured at 13px weight 600; a long label wraps to more lines rather than overflowing. There is no hard two-line cap: the 24-character warning keeps labels to about two lines.
  - ELK size: width `max(96, 2 * (widestLine + 12))`, height `max(64, 2 * (lines * 16 + 8))`.
  - Shape: `polygon[data-q-flow-box]` through the four side midpoints, surface fill. Stroke is `var(--q-color-chart-N)` at width 2 when the node has a kind, otherwise the border token at the box's usual width. No stripe and no kind-tag text; the kind still shows in the drawer, the list and the announcement.
  - Lines are centred in the diamond.
  - Edge ends: after layout, an edge's first point (when leaving a decision) and last point (when entering one) move along their own segment until they meet the diamond outline, so the segment stays axis-aligned and the arrowhead touches the diamond.
- **Subprocess drawing.** Today's box widened by 16px, plus two `line[data-q-flow-subprocess-rule]` running the full height, inset 8px from each side, stroke `var(--q-color-border)`. Stripe, kind tag and label stay and shift right so no rule crosses text.
- **Loop edges in layout.** For a loop edge with `from !== to`, the ELK edge gets `sources: [to]`, `targets: [from]`. After layout, reverse that edge's point list (startPoint, bendPoints, endPoint) before drawing, so the path runs `from` to `to`. Self-loops go to ELK unchanged, so ELK reserves room and places the label.
- **Loop edges on screen.**
  - `g.q-flow-edge` gets `data-q-flow-loop`.
  - The base path keeps the solid or dashed pattern from `async` and gets `marker-start` with a return marker: a small open circle, `q-flow-return-<uid>` at rest and `q-flow-return-lit-<uid>` when lit, stroked with the same tokens as the two arrow markers.
  - The label text is prefixed `↩ `.
  - A self-loop path is drawn from ELK's section points with rounded corners (radius 8). When ELK gives no section, the path is an arc over the node's top edge (or its right edge in `direction="down"`) from 35% to 65% of its width, rising 18px. Either way its points are inside `_bounds`.
  - The straight-line fallback at `:3823-3834` never runs for an edge with `from === to`.
- **Focus.**
  - Both BFS walks skip loop edges.
  - After the lit node set is known, every loop edge with both ends lit gets `data-q-flow-lit`, the accent stroke and the lit markers. It gets no `data-q-flow-hop` and is never pushed to `activePulses`, so `pulseSchedule` never sees it.
  - Reduced motion: lit loop edges take the 3.5px static style like other lit edges.
  - `_focusGroup` and `_clearFocus` handle loop edges like any edge.
- **Open flow.**
  - When the focused node is a subprocess with `flow`, the drawer gets `div[data-q-flow-drawer-flow]` after the detail.
  - If `document.getElementById(flow)` is a connected `Q-FLOW` element other than this one, the section holds `button[type=button][data-q-flow-open-flow]` with text "Open flow".
  - Otherwise it holds `p[data-q-flow-flow-missing]` reading `The linked flow "<flow>" isn't on this page.` and no button.
  - Pressing the button:
    1. if this graph is expanded, `_toggleExpand()` returns it to the page;
    2. the target's `scrollIntoView({block: "start"})` runs, with `behavior: "smooth"` unless reduced motion;
    3. if the target carries `data-q-flow-ready="true"`, it runs `_fitBounds(target._bounds, false)` and moves DOM focus to its node with `tabindex="0"`;
    4. otherwise it focuses the target element itself.
  - This graph's focus and drawer stay as they were. The target's open drawer or focus, if any, is left alone.
- **Styles.** Everything new uses `--q-*` tokens. Selectors stay inside `:where()` per the header comment of `K/kit.css`.

### 5. Skill guidance
Back-links: [Choosing](logic.md#choosing), [Success criteria](logic.md#success-criteria).

- `SKILL.md:138`, `design-reference.md:200`, `report/rules.md:30`, `components/rules.md:26`: `q-flow` is the tool for every flowchart on an HTML page, including decisions (`shape: "decision"`), retries (`loop: true`) and steps that are their own process (`shape: "subprocess"`, optional `flow`). Mermaid stays for diagrams inside Markdown, state charts, and sequence and ER diagrams.
- `K/catalog.json` `use_when` for `q-flow`: also names flowcharts with decisions, retries and sub-processes.
- Companion option cards keep Mermaid `diagram` (`S/references/companion.md:67`, `S/references/design-reference.md:252`), because interactive elements are banned there; only a screen's `content` can hold `q-flow`, as today.
- `flow-evals.json`: add 3 `q-flow` prompts (a flowchart on an HTML page with a decision, a retry or a sub-process) and 3 `mermaid` prompts (the same kinds of flowchart inside a README or other Markdown), ids continuing from 17. The existing balance test needs no change.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

```
SCHEMA: cleaned graph from _validate_flow_node (Python) and _parseData (JS), additions only
node: {..., "shape": "box" | "decision" | "subprocess", "flow": str | None}
edge: {..., "loop": bool}   // effective: true for a marked loop or a self-loop
```

```
SCHEMA: catalog.json q-flow "children" must mention
node shape (box, decision or subprocess), subprocess flow (id of another q-flow on the page),
edge loop boolean for return edges; decisions label every exit
```

The catalog `example` stays one `<q-flow>` with one `<script type="application/json">` (`tests/test_html_kit_catalog.py:162-166`). It gains a decision with two labelled exits and one `loop: true` edge, and no `flow` (it is checked alone, with no second graph to point at).

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **`pulseSchedule` `K/kit.js:3024-3058` and the pulse runtime `:4417-4484`.** The pulse-speed test pins their timing; loop edges are kept out by never entering `activePulses`, not by changing the schedule.
- **ELK root options `K/kit.js:3547-3560` and free port constraints.** The earlier tech spec chose them to avoid ELK #1192 and to keep lanes working; loop handling needs only the per-edge swap.
- **The no-JS notice and list wrapper `H/kitcheck.py:1218-1226`, and `inject_flow_fallbacks`' skip rules `:1233-1258`.** Builder and companion tests pin them.
- **`KNOWN_RULES`, `_RULES` and the catalog `rules` list.** `tests/test_html_kit_catalog.py:224` pins them; target resolution lives in the existing `flow-data` rule.
- **Existing forward-edge list format `→ <target> (<label>, async)`.** `tests/test_html_builder.py:931-943` asserts it.

## Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `python3 S/scripts/pins.py stamp kit 1.0.0` after any edit to `K/kit.js`, `K/kit.css` or `K/catalog.json`, and `python3 S/scripts/kit_docs.py reference` after any edit to `K/catalog.json`.
- Keep the Python and JS failure rules and list text identical.
- Treat a self-loop as a loop everywhere: layout, drawing, focus, pulse, list and the cycle warning.

**Ask**
- Any change to the schema additions above, or to a message in contract 2.
- Any change to ELK root options.

**Never**
- Pulse along a loop edge, or count a loop edge in the upstream/downstream walk.
- Hand ELK a loop edge in its true direction (except self-loops).
- Draw a self-loop with the straight-line fallback.

## Cross-cutting

Back-link: [Text list and no-script fallback](logic.md#text-list-and-no-script-fallback).

- **Security:** `flow` reaches the DOM only through `setAttribute('href', '#' + flow)`, `textContent` and `getElementById`; Python escapes it in the fallback. No new HTML is parsed.
- **Rollback:** graphs without the new fields are unchanged (contract 2 invariant).

## Testing strategy

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Success criteria](logic.md#success-criteria).

| File | Coverage |
|---|---|
| `tests/test_html_kit_check.py` (q-flow section from `:997`, helpers `flow_markup` `:1000`, `warn_messages` `:1004`) | Each SC-5 failure and warning; a self-loop raises no cycle warning; a loop exit counts toward a decision's two and needs a label; a page with two graphs where one subprocess names the other passes; a missing target and a self target fail; a valid graph with every new field passes with no warnings |
| `tests/test_html_builder.py` (near `:931`) | The injected no-JS list carries `Paid? (decision, worker): Yes → Ship, No → Retry queue`, `↩ returns to Charge worker: retry up to 3x`, `↩ returns to itself: every 30s` and the `opens the "refund-flow" graph` link with `href="#refund-flow"` |
| `tests/test_html_kit_elements.py` (q-flow tests from `:3905`, `FLOW_FAKE_CLOCK` `:4037`) | A new page constant with the logic spec's checkout graph, a "refund-flow" graph and a status-poller graph. Covers: diamond polygon with the kind stroke and labelled exits; loop path running from Retry queue to Charge worker while Checkout, Charge worker, Paid?, Ship x-positions increase; self-loop path not a two-point line and above the node; focusing Ship leaves Retry queue dim (SC-6); focusing Charge worker lights the loop edge with no hop (SC-7); under the fake clock no mask dot is ever placed on a loop edge (SC-8); reduced motion styles the lit loop (SC-9); "Open flow" scrolls to and fits the target and focuses one of its nodes, including from expanded (SC-10); missing target message (SC-11); no button without `flow` (SC-12); the JS list text matches the builder test (SC-13) |
| `tests/test_html_kit_catalog.py`, `tests/test_html_kit_examples.py`, `tests/test_html_kit_docs.py` | Updated catalog example is clean and builds; `kit_docs.py reference --check` passes |
| `tests/test_html_layout_shapes.py` | The updated report explainer builds, checks and verifies |
| `tests/test_html_vendor.py` | `pins.py verify` passes after restamping |
| `tests/test_writing_html_artifacts_skill.py:137` | The extended evals stay balanced and unique |

Browser tests need `S/scripts/verify/node_modules` (`pnpm install` there). On this machine they are affected by BUG-14 in `BUGS.md`.

## Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Deferred item | Resolution |
|---|---|
| Routing the return line | The reversed edge goes through ELK's normal layered routing, which never crosses a node; its points are reversed for drawing |
| Diamond sizing and exits | Contract 4, decision drawing: wrapped lines, `2×` text box, edge ends moved onto the outline |
| Self-loop arc | ELK keeps self-loops and reserves space; drawn with rounded corners, with a fixed arc as fallback |
| Page `q-flow` ids in the check | `_Index.nodes_of("q-flow")` inside the existing `flow-data` rule; no new rule. Tier-2 JSX skips element rules (`check_jsx`), so targets there are only checked at runtime (SC-11) |
| Finding unmarked cycles | Strongly connected components over forward edges, in the Python check only |

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- Everything under Not in scope in the logic spec.
- JS-side warnings, and resolving `flow` targets in tier-2 JSX at build time.
- Changing the drawer's edge buttons for loop edges.
