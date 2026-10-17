# Tech spec: stepping through a value in `q-flow`

**Status**: Draft · Logic spec: [logic.md](logic.md) · Builds on [the q-flow tech spec](/docs/quirk/specs/2026-10-16-q-flow/tech.md) and [the q-flow shapes tech spec](/docs/quirk/specs/2026-10-17-q-flow-shapes/tech.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`, `K` = `skills/writing-html-artifacts/vendor/kit/1.0.0`, `H` = `skills/writing-html-artifacts/scripts/htmlkit`. Line numbers are from commit `39ea301`.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Kit check & no-JS fallback | `H/kitcheck.py` | Validate edge ids and `traces`; warn on long values, long notes and long traces; render each trace in the injected list |
| Kit runtime & styles | `K/kit.js`, `K/kit.css` | Parse edge ids and traces, write traces into the text list, add "Step through", run trace mode (panel, value tree with change marks, canvas lighting, single-edge pulse, Play, keys) |
| Catalog, reference & pins | `K/catalog.json`, `S/references/components.md` (generated), `S/vendor/libraries.json` (restamped) | Document `traces`, edge `id` and `via` |
| Skill guidance & evals | `S/SKILL.md`, `S/references/design-reference.md`, `S/evals/trace-evals.json` (new), `tests/test_writing_html_artifacts_skill.py` | When to add a trace; motion exception for trace mode |
| Example page | `S/templates/report/examples/explainer.src.html` | Two traces on the existing `retry-flow` graph |

No new library, no new kit-check rule name, no catalog attribute change.

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

### `H/kitcheck.py`
- `_validate_flow_node` `:995-1250`: edge loop `:1135-1171` gains the `id` check and carries `ref` on the clean edge dict `:1162-1170`; trace validation goes after the cycle warning `:1188-1190` and before `if before_fails` `:1192`; the returned dict `:1194-1200` gains `traces`.
- `_render_flow_fallback_html` `:1284-1359`: after `list_html` `:1356`, append the trace sections inside `data-q-flow-list-body`.
- `_rule_flow_data`, `check_html_warnings`, `inject_flow_fallbacks`: unchanged.

### `K/kit.js`
- Module helpers near `pulseSchedule` `:3029` and `roundedFlowPath` `:3131`: add `traceDiff`, `traceLines`, `deepEqualJson` (pure functions).
- `connectedCallback` `:3156-3185`: `_onDocKey` condition `:3166` also fires while tracing.
- `_parseData` `:3217-3373`: edge loop `:3333-3353` and clean edge `:3344-3352`; trace parse after the decision check `:3354-3362`; return value `:3363-3372` gains `traces`.
- `_ensureScaffold` `:3375-3410`: create the trace panel element after the stage.
- `_populateList` `:3412-3529`: append trace sections after `rootUl` `:3527`.
- `_setup` `:3565-3592`: close trace mode before re-layout.
- `_renderGraph` `:3752-4329`: node click `:4296-4300`, svg click `:4308-4312`, group header click `:4046-4049`.
- `_buildControls` `:4331-4367`: "Step through" button.
- `_handleEscape` `:4519-4534`, `_focusNode` `:4536-4712`, `_startPulse` `:4714-4732` (guard at `:4720`), `_clearFocus` `:5013-5048`, `_onNodeKey` `:5111-5126`, `_ensureNodeVisible` `:4459-4498`, `_fitBounds` `:4435-4457`, `_toggleExpand` `:4500-4517`.

### `K/kit.css`
- q-flow block `:1046-1291`: trace mode grid, panel, controls, dots, value tree, change marks.
- `@media (max-width: 700px)` `:1292-1311`: panel below the canvas.
- `@media print` q-flow rule `:1368-1371`: hide the panel too.

### Docs, catalog, evals, example
- `K/catalog.json:360-405` (`children` and `example` of `q-flow`).
- `S/SKILL.md:138`, `S/references/design-reference.md:200-218`.
- `S/evals/` (new `trace-evals.json`), `tests/test_writing_html_artifacts_skill.py:137-148` (pattern for the new balance test).
- `S/templates/report/examples/explainer.src.html:16-44` (`retry-flow`).

## Contracts & interfaces

### 1. Data contract
Back-links: [Conceptual model](logic.md#conceptual-model), [Decisions Locked](logic.md#decisions-locked).

```
SCHEMA: additions to the <q-flow> JSON payload
edges[i].id?:   str                          // non-empty after strip; unique among edges
traces?: [
  {
    id:    str,                              // non-empty after strip; unique among traces
    label: str,                              // non-empty after strip
    steps: [                                 // at least 2
      { node: str,                           // a node id
        value: <any JSON>,                   // key must be present; null is a value
        via?:  str,                          // an edge id; only on steps after the first
        note?: str }
    ]
  }
]
```

- **Incoming edge of step n (n ≥ 2):** the candidates are edges with `from` = step n−1's node and `to` = step n's node, effective loops included, in `edges` order. With `via`, the edge whose `id` equals `via` must exist and be a candidate. Without `via`, there must be exactly one candidate.
- **Pretty-printed lines:** JS `JSON.stringify(value, null, 2).split('\n').length`; Python `json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False).count("\n") + 1`. They agree for every JSON value.

### 2. Kit check (`kitcheck.py`)
Back-links: [Authoring and building](logic.md#authoring-and-building).

Failures (all at the `<q-flow>` start line, through `report_fail`; the graph returns `None`). `N` is the 1-based step number; `<t>` is the trace id.

| Case | Message |
|---|---|
| edge `id` present and not a non-empty string | `<q-flow> edge id must be a non-empty string` |
| two edges with the same `id` | `<q-flow> has duplicate edge id "<id>"` (once per id) |
| `traces` present and not a list | `<q-flow> traces must be a list` |
| a trace that isn't an object, or lacks a non-empty string `id` or `label` | `<q-flow> each trace needs an id and a label` |
| two traces with the same id | `<q-flow> has duplicate trace id "<t>"` (once per id) |
| `steps` not a list, or fewer than 2 | `<q-flow> trace "<t>" needs at least 2 steps` |
| a step that isn't an object, has no string `node`, or has no `value` key | `<q-flow> trace "<t>" step N needs a node and a value` |
| `node` not a node id | `<q-flow> trace "<t>" step N points at unknown node "<node>"` |
| `note` present and not a string | `<q-flow> trace "<t>" step N note must be a string` |
| `via` present on step 1 | `<q-flow> trace "<t>" step 1 has no incoming edge; remove via` |
| `via` not a string, or no edge has that id | `<q-flow> trace "<t>" step N names unknown edge "<via>"` |
| `via` names an edge that isn't a candidate | `<q-flow> trace "<t>" step N: edge "<via>" doesn't run from "<prev node>" to "<node>"` |
| no candidate edge | `<q-flow> trace "<t>" step N: no edge from "<prev node>" to "<node>"` |
| 2+ candidates and no `via` | `<q-flow> trace "<t>" step N: <count> edges run from "<prev node>" to "<node>"; name one with via` |
| value holds NaN or ±Infinity (Python's `json.loads` accepts them; in JS an overflowing literal such as `1e9999` parses to Infinity), or a string or key with an unpaired UTF-16 surrogate such as `"\ud800"` (it can't be written as UTF-8), or nests too deeply to walk (Python's `RecursionError`, JS's `RangeError`) | `<q-flow> trace "<t>" step N has a value that isn't JSON` |
| value over 400 pretty-printed lines | `<q-flow> trace "<t>" step N value is <L> lines; at most 400` |
| any other string anywhere in the graph data (ids, labels, kinds, details, notes, `via`, object keys) holds an unpaired UTF-16 surrogate | `<q-flow> graph data holds text that can't be written as UTF-8` (once per graph; trace values are covered by the row above instead) |

- Edge checks for a step run only when both its node and the previous step's node are known.
- A trace with a bad id or label still has its steps checked, with `<t>` read as `?`.

Warnings (through `report_warn`; never affect `passed`):

| Case | Message |
|---|---|
| value over 40 pretty-printed lines | `<q-flow> trace "<t>" step N value is <L> lines: values over 40 lines are hard to scan; keep the fields the reader needs` |
| note over 120 characters | `<q-flow> trace "<t>" step N note is <C> characters: notes over 120 characters crowd the panel` |
| more than 30 steps | `<q-flow> trace "<t>" has <S> steps: traces over 30 steps are hard to follow; split it` |

Invariants: every existing message and its order are unchanged; a graph with no `traces` and no edge `id` validates and renders byte-identically to today.

### 3. Fallback and runtime text list (same text in both)
Back-links: [Text list and no-script fallback](logic.md#text-list-and-no-script-fallback).

After the root `ul` inside `div[data-q-flow-list-body]`, one block per trace, in `traces` order:

```html
<div data-q-flow-list-trace="<trace id>">
  <p><strong>Trace: <label></strong></p>
  <ol>
    <li data-q-flow-list-step="<N>"><node label><via part><note part><pre><code><pretty JSON></code></pre></li>
  </ol>
</div>
```

- **Via part** appears only when the step names `via` or its incoming edge is a loop: `, via "<edge label>"` when the edge has a label; otherwise `, via "<edge id>"` for a named `via`, or `, around the loop` for an unlabelled loop edge.
- **Note part:** `: <note>` when the step has a non-empty note; an empty note reads as no note.
- **Pretty JSON:** the 2-space pretty print from contract 1, unescaped in JS (`textContent`), `html_lib.escape`d in Python.
- **Two allowed differences** between the lists, both from how each runtime holds JSON: Python writes an integral float such as `18.0` with its `.0` where JS writes `18`, and JS lists integer-like object keys (`"2"`, `"10"`) in ascending numeric order before other keys where Python keeps the authored order. Tests compare the two lists only on values without integral floats or integer-like keys.
- Python escapes every label, id and note with `html_lib.escape` (`quote=True` in attributes). JS uses `textContent` and `setAttribute`.
- Builder whitespace: Python writes the block with no whitespace between tags, so a test can assert `<li data-q-flow-list-step="3">Tax, via &quot;domestic quote&quot;: Tax adds 8.25% sales tax<pre><code>`.

### 4. Runtime (`kit.js`, `kit.css`)
Back-links: [Opening trace mode](logic.md#opening-trace-mode), [Stepping](logic.md#stepping), [Play](logic.md#play), [Keyboard, motion and screen readers](logic.md#keyboard-motion-and-screen-readers), [Leaving trace mode](logic.md#leaving-trace-mode), [Phones and expand](logic.md#phones-and-expand).

**Parse.** `_parseData` applies every failure in contract 2 that JSON can carry, and returns `null` on any of them (the existing fail-hard notice). Clean edges gain `ref: string | null` (the authored `id`; the internal `id: 'e' + index` used by ELK is unchanged). The result gains:

```
traces: [{ id, label, steps: [{ node, value, note: string|null, via: string|null, edge: number|null }] }]
// edge: the incoming edge's index into data.edges; null on step 1
```

`traces` is `[]` when the payload has none. No warnings in JS.

**Diff.** A pure module function:

```
traceDiff(prev, next, hasPrev) -> Field
Field = { key: string|null, change: 'same'|'added'|'changed'|'removed', value, old?, children?: Field[], hasChange: bool }
```

- `hasPrev` false (step 1): every field is `same`.
- Both plain objects: children in `next`'s key order, then keys only in `prev` (as `removed`) in `prev`'s order. Both arrays: by index; extra `next` items `added`, extra `prev` items `removed`, keys `"0"`, `"1"`, …
- Otherwise `same` when deep-equal, else `changed` with `old`. A type change (including object to scalar) is `changed`, not a recursion.
- `hasChange` is true when the field or any descendant is not `same`.

**Toolbar.** When `data.traces.length > 0`, `_buildControls` inserts `button[data-q-flow-action="trace"]` with text "Step through", `aria-label="Step through a trace"`, `aria-pressed` reflecting trace mode, after Fit and before Expand. No button otherwise.

**Panel DOM** (created once in `_ensureScaffold` as `aside.q-flow-trace[data-q-flow-trace-panel][data-q-kit]`, after the stage, `aria-label="Trace"`, `tabindex="-1"`, `data-q-inactive` while closed):

| Part | Element |
|---|---|
| picker | `label` "Trace" + `select[data-q-flow-trace-picker]`, one `option` per trace (value = trace id, text = label) |
| counter | `p[data-q-flow-trace-counter][aria-live="polite"]`: visible "Step n of m", plus a `.q-visually-hidden` span ", <node label>: <note>" (", <node label>" without a note) |
| buttons | `button[data-q-flow-trace-back]` "Back", `button[data-q-flow-trace-next]` "Next", `button[data-q-flow-trace-play]` "Play" or "Pause" with `aria-pressed` |
| dots | `ol[data-q-flow-trace-dots]` of `button[data-q-flow-trace-dot="<n>"]`, `aria-label="Step n: <node label>"`, `aria-current="step"` on the current one |
| note | `p[data-q-flow-trace-note]`, empty and `data-q-inactive` when the step has none |
| toggle | `label` + `input[type=checkbox][data-q-flow-trace-changes]` "Changes only" |
| value | `div[data-q-flow-trace-value]` holding the tree |

Back is disabled on step 1 and Next on the last.

**Value tree.** `ul[data-q-flow-tree]`, one `li[data-q-flow-field]` per field, with `data-q-flow-change` = the field's change, `data-q-flow-has-change` when `hasChange`, and `data-q-flow-depth` (top-level fields are 1).
- A leaf: `span[data-q-flow-mark]` (`+` added, `−` removed, `→` changed, empty for same), `span[data-q-flow-key]` (`key: `, absent for a root scalar), then `span[data-q-flow-val]` holding the JSON text of the value. A changed leaf shows `span[data-q-flow-old]` (JSON text of `old`), ` → `, `span[data-q-flow-new]`. Each mark also carries `.q-visually-hidden` text: "added", "removed", "changed from".
- A container (object or array, and not `changed`): a `details[data-q-flow-branch]` whose `summary` holds the mark, the key and a count (`{3}` for an object of 3 fields, `[2]` for an array of 2), and a nested `ul`. It starts `open` when its depth is under 3 or it `hasChange`, closed otherwise.
- A changed container shows like a changed leaf, with compact JSON (`JSON.stringify`) for both sides.
- "Changes only" sets `data-q-flow-changes-only` on the tree; CSS hides `li[data-q-flow-field]:not([data-q-flow-has-change])`. When nothing changed, the value area shows `p[data-q-flow-trace-empty]` "No changes at this step" instead.
- The toggle's state lives on the element (`this._traceChangesOnly`) and survives steps and trace switches; it resets when the element re-lays out.

**Entering trace mode** (`_openTrace(traceIndex)`, from the button):
1. Stop any Play, `_clearFocus()` (closes the drawer), set `this._trace = {index, step: 0}`, set `data-q-flow-tracing` on the element, `aria-pressed="true"` on the button, remove `data-q-inactive` from the panel.
2. Compute the trace's path: node ids of every step and edge indices of every step's `edge`.
3. `_showTraceStep(0)`, then `_fitBounds(this._bounds, false)` because the stage width changed, then `_ensureNodeVisible(currentNode, false)`.
4. Move DOM focus to the Next button.

**Showing step i** (`_showTraceStep(i)`):
- Nodes: the current node gets `data-q-flow-selected` and `data-q-flow-lit`; other path nodes neither; off-path nodes `data-q-flow-dim`.
- Groups: `data-q-flow-dim` on groups holding no path node (walk parents as `_focusNode` does `:4617-4624`).
- Edges: off-path edges `data-q-flow-dim`. The current edge (step i's `edge`) gets `data-q-flow-lit`, the accent stroke, the lit arrow marker and, for a loop, the lit return marker, with stroke width 3.5 under reduced motion and 2 otherwise. Every other edge returns to the at-rest stroke, width and markers.
- Pulse: when not reduced motion and step i has an edge, set `data-q-flow-pulsing` and `_startPulse(pulseSchedule([{rec, down: true}], rec.edge.from))`; a loop edge pulses like any other here. Otherwise `_stopPulse()` and remove `data-q-flow-pulsing`. Every non-current pulse path keeps `data-q-inactive`.
- `_ensureNodeVisible(node, false)`, which keeps the zoom.
- Panel: counter, dots, Back/Next state, note, value tree from `traceDiff(steps[i-1].value, steps[i].value, i > 0)`.

**Clicks while tracing:**
- A node on the trace: jump to its first visit after the current step, else its first visit (`_showTraceStep`), and stop Play.
- A node off the trace, or a group header: `_closeTrace(false)`, then the normal click (`_focusNode` or `_focusGroup`).
- Empty canvas: nothing (the existing `_clearFocus` call is skipped).
- A dot: jump to that step. Back and Next: step by one. The picker: `_openTrace`'s steps 1–3 for the new trace, keeping focus on the picker.
- Any of these stops Play.

**Play.** `button[data-q-flow-trace-play]` toggles. Starting on the last step jumps to step 1 first. Playing runs a frame loop on `nextFrame` using `performance.now()` (as `_startPulse` does), and advances when 1500 ms have passed since the step was shown. On reaching the last step it stops. The button reads "Pause" with `aria-pressed="true"` while playing. Play never starts on its own. It also stops on close, re-layout and disconnect.

**Keys.** A `keydown` listener on the panel: ArrowRight and ArrowDown go to the next step, ArrowLeft and ArrowUp to the previous one (`preventDefault`), except when `ev.target` is the picker. Escape anywhere in the element or the document (the `_onDocKey` condition gains `self._trace`) runs `_handleEscape`, which closes trace mode first: `_closeTrace(true)` returns focus to the "Step through" button. With several graphs tracing, an Escape whose target is inside a `<q-flow>` closes only that graph's trace; an Escape from outside every graph closes each trace without moving focus. When trace mode is closed, Escape behaves exactly as today. `_onNodeKey` Enter/Space on a node while tracing acts as a click.

**Leaving trace mode** (`_closeTrace(restoreFocus)`): stop Play, clear `this._trace`, remove `data-q-flow-tracing`, set `aria-pressed="false"`, set `data-q-inactive` on the panel, `_clearFocus()` (which also resets every edge and node attribute, stops the pulse), `_fitBounds(this._bounds, false)`, and focus the button when `restoreFocus`. The "Step through" button toggles between `_openTrace(lastIndex)` and `_closeTrace(true)`.

**Pulse guard.** `_startPulse`'s frame loop `:4720` keeps running while `self._focusedNode || self._trace`. `pulseSchedule` and `_placePulseDots` are unchanged.

**Layout (CSS).**
- Wider than 700px: `q-flow[data-q-flow-tracing]` becomes a grid, `grid-template-columns: minmax(0, 1fr) min(22rem, 40%)`, column gap `--q-space-3`. The stage is column 1, the panel column 2 with `contain: size` and `overflow-y: auto`, so the row height stays the stage's; the list `details` spans both columns.
- 700px and narrower: one column; the panel sits below the stage at its natural height.
- Expanded: `q-flow[data-q-flow-expanded][data-q-flow-tracing]` is the same grid with `grid-template-rows: minmax(0, 1fr) auto`; at 700px and narrower the panel takes `max-height: 45vh` and scrolls.
- The drawer never shows in trace mode, because trace mode clears focus.
- Change marks: added uses `--q-color-good`, changed uses `--q-color-accent`, removed uses `--q-color-text-muted` with `text-decoration: line-through` on the key and value. Only `--q-*` tokens; selectors inside `:where()` per the header of `K/kit.css`.
- Print hides the panel with the controls and drawer.

### 5. Skill guidance
Back-links: [Choosing](logic.md#choosing), [Success criteria](logic.md#success-criteria).

- `SKILL.md:138` and `design-reference.md:200-202`: add a trace when the reader needs to see what happens to a value as it moves through the flow; one trace per scenario worth walking, the whole value at every step, only the fields the reader needs, an edge `id` only when a step must pick between parallel edges with `via`.
- `design-reference.md:216-218`: the motion exception also covers trace mode: the pulse on the current edge and Play, which the reader starts and can pause.
- `trace-evals.json`: `{"skill_name": "writing-html-artifacts", "evals": [{"id", "prompt", "expected": "trace" | "no-trace"}]}` with at least 4 of each: "walk through how X changes" prompts expect `trace`; structure-only `q-flow` prompts expect `no-trace`. A new test in `tests/test_writing_html_artifacts_skill.py` checks shape, balance and uniqueness as `test_flow_evals_are_balanced_and_unique` does.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

```
SCHEMA: cleaned graph from _validate_flow_node (Python), additions only
edge:  {..., "ref": str | None}
"traces": [{"id": str, "label": str,
            "steps": [{"node": str, "value": Any, "note": str | None, "via": str | None, "edge": int | None}]}]
```

```
SCHEMA: catalog.json q-flow "children" must mention
edge id (used only by via); traces: id, label, steps of node, value (the whole value as it leaves that node),
optional note, optional via naming an edge id when several edges join two steps
```

The catalog `example` stays one `<q-flow>` with one `<script type="application/json">` (`tests/test_html_kit_catalog.py:162-166`). It gains one trace of 3 or more steps with a note on each, and checks clean with no warnings.

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **`pulseSchedule` `K/kit.js:3029-3063` and `_placePulseDots` `:4734-4756`.** The pulse-speed tests pin their timing; trace mode feeds `pulseSchedule` a one-edge list and only widens `_startPulse`'s keep-running guard.
- **Focus mode.** `_focusNode`, `_focusGroup` and the drawer behave exactly as today whenever trace mode is closed (SC-16). Trace mode adds branches at the entry points; it doesn't change their bodies.
- **The no-JS notice and list wrapper `H/kitcheck.py:1350-1359`, and `inject_flow_fallbacks`' skip rules `:1366-1405`.** Builder and companion tests pin them; traces go inside the existing list body.
- **`KNOWN_RULES`, `_RULES` and the catalog `rules` list.** All trace checks live in the existing `flow-data` rule.
- **ELK input.** Traces never reach ELK; edge `ref` is not an ELK id.

## Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `python3 S/scripts/pins.py stamp kit 1.0.0` after any edit to `K/kit.js`, `K/kit.css` or `K/catalog.json`, and `python3 S/scripts/kit_docs.py reference` after any edit to `K/catalog.json`.
- Keep the Python and JS failure rules and the trace list text identical.
- Write values and notes to the DOM with `textContent` only.

**Ask**
- Any change to the schema additions or a message in contract 2.
- Any change to focus mode's behavior.

**Never**
- Start Play without a click, or animate anything under reduced motion.
- Pulse more than the current edge in trace mode.
- Parse a trace value or note as HTML.

## Cross-cutting

- **Security:** values and notes reach the DOM only as text; Python escapes them in the fallback. The picker's option values are trace ids set with `.value`.
- **Performance:** at most 30-ish steps of up to 400 lines; the tree is rebuilt per step, which is cheap at that size.
- **Rollback:** graphs without traces are unchanged (contract 2 invariant).

## Testing strategy

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Success criteria](logic.md#success-criteria).

| File | Coverage |
|---|---|
| `tests/test_html_kit_check.py` (q-flow section, helpers `flow_markup` and `warn_messages` `:1000-1005`) | One test per contract-2 failure and warning; the logic spec's renewal graph with both traces passes with no warnings; a trace through a loop edge and a self-loop passes |
| `tests/test_html_builder.py` (near `:980`) | The injected no-JS list carries both traces' steps, with the via part, the note and the escaped pretty JSON |
| `tests/test_html_kit_elements.py` (new `FLOW_TRACES` page and `flow_traces_page` fixture beside `FLOW_SHAPES` `:4372`) | No "Step through" button without traces; opening dims off-path nodes and edges, clears focus and closes the drawer (SC-3); Next lights the inferred edge, and `via` picks the right one of two parallel edges (SC-4); the loop edge lights and gets mask dots as the current edge (SC-5); added, changed and removed marks and the one-step strike-through (SC-5, SC-6); "Changes only" hides same fields and persists (SC-7); depth-3 branches start closed unless they hold a change (SC-8); node click jumps to the next visit, dots jump (SC-9); the picker resets to step 1 (SC-10); Play on `FLOW_FAKE_CLOCK` advances at 1500 ms and stops at the end (SC-11); arrow keys and the live counter text (SC-12); reduced motion steps with no mask dots and a 3.5 stroke (SC-13); a far node pans into view keeping zoom (SC-14); Escape, the toggle and an off-trace click leave trace mode and focus works as before (SC-15, SC-16); at 375px the panel is below the stage (SC-17); the runtime list matches the builder test (SC-18); a payload with an unknown `via` fails to the notice |
| `tests/test_html_kit_catalog.py`, `tests/test_html_kit_examples.py`, `tests/test_html_kit_docs.py` | Updated catalog example is clean and builds; `kit_docs.py reference --check` passes |
| `tests/test_html_layout_shapes.py` | The updated report explainer builds, checks and verifies |
| `tests/test_html_vendor.py` | `pins.py verify` passes after restamping |
| `tests/test_writing_html_artifacts_skill.py` | The new trace evals are balanced and unique |

Browser tests need `S/scripts/verify/node_modules` (`pnpm install` there). On this machine they are affected by BUG-14 in `BUGS.md`; run them through spec 1's node relay (a relay server started from zsh, and its `bin/node` shim first on `PATH` for pytest).

## Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Deferred item | Resolution |
|---|---|
| The diff | `traceDiff` in contract 4: objects by key, lists by index, a type change is `changed` |
| Reusing focus and dim attributes; one-edge pulse | `data-q-flow-selected`, `-lit` and `-dim` as focus mode uses them; `pulseSchedule` gets a one-edge list |
| Panel layout | A grid on the element in trace mode; `contain: size` keeps the row at the stage's height |
| Detecting the current node out of view | The existing `_ensureNodeVisible`, which keeps the zoom and only pans; pans are already instant (`_applyTransform` has no transition) |
| Timing Play for tests | A `nextFrame` loop on `performance.now()`, which `FLOW_FAKE_CLOCK` drives |
| Measuring lines the same way | Contract 1's pretty-print rule |

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- Everything under Not in scope in the logic spec.
- JS-side warnings.
- Remembering the open trace or the toggle across page loads.
