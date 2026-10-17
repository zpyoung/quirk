# Tech spec: `q-sequence`, an interactive sequence diagram element

**Status**: Reviewed (tech-spec reviewer, fixes applied) · Logic spec: [logic.md](logic.md) · Builds on [the q-flow tech spec](/docs/quirk/specs/2026-10-16-q-flow/tech.md) and [the q-flow traces tech spec](/docs/quirk/specs/2026-10-17-q-flow-traces/tech.md)

All paths are relative to the repository root. `S` = `skills/writing-html-artifacts`, `K` = `skills/writing-html-artifacts/vendor/kit/1.0.0`, `H` = `skills/writing-html-artifacts/scripts/htmlkit`. Line numbers are from commit `c4e34ff`, before the rebase onto q-schema; task prompts carry re-resolved anchors.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Kit check & no-JS fallback | `H/kitcheck.py`, `H/assemble.py`, `H/checks.py` | New `sequence-data` rule; warnings; render and inject the no-JS list |
| Kit runtime & styles | `K/kit.js`, `K/kit.css` | New `QSequence` class: parse, lay out columns and rows, draw, pinned headers, focus, drawer, keyboard, text list, trace mode through q-flow's panel |
| Catalog, reference & pins | `K/catalog.json`, `S/references/components.md` (generated), `S/vendor/libraries.json` (restamped) | Document the element |
| Verify & test harness | `S/scripts/verify/verify.mjs`, `tests/fixtures/html-kit/harness.mjs` | Wait for `data-q-sequence-ready` as they wait for q-flow |
| Typings | `S/templates/app/project/src/quirk-kit.d.ts` | JSX intrinsic |
| Skill guidance & evals | `S/SKILL.md`, `S/references/design-reference.md`, `S/templates/{report,components,app,companion}/rules.md`, `S/evals/flow-evals.json`, `tests/test_writing_html_artifacts_skill.py` | Sequence diagrams on HTML pages use `q-sequence` |
| Example page | `S/templates/report/examples/explainer.src.html` | The checkout sequence with its two traces |

No new library. The renderer is plain SVG in `kit.js`; nothing new touches `window.quirkFlow`, so `needs_flow` and the flow bundle are unchanged.

**Reuse model.** Trace mode reuses q-flow's panel by borrowing `QFlow.prototype` methods onto `QSequence.prototype` (contract 5), not by copying them and not by moving them. The one q-flow change is a step-label hook. The pulse is borrowed the same way. Shared canvas helpers that fit: `canvasMeasureFactory` for label widths and `canvasBuildDrawer` for the drawer shell; `canvasBuildControls` does not fit, because it always adds zoom, fit and expand over a canvas. Module-level pure helpers (`traceDiff`, `renderTraceField`, `traceValueOk`, `tracePretty`, `sanitizeFlowDetail`, `isValidFlowDetail`, `isBlankFlowId`, `svgNode`, `kitNode`, `uid`, `onTheme`, `watchChildren`, `nextFrame`, `pulseSchedule`) are called directly.

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

### `H/kitcheck.py`
- `FLOW_TAG` `:31`, `KNOWN_RULES` `:33-35`, `_RULES` `:1618-1626` with its assert `:1627`: add `SEQUENCE_TAG` (`<q-sequence[\s/>]`) beside `FLOW_TAG`, `"sequence-data"` to both sets.
- Reuse unchanged: `_check_and_sanitize_flow_detail` `:905-942`, `_flow_value_lines` `:1000-1010`, the limit constants `:878-880`, `_LONE_SURROGATE` `:1140`, `_text`, `_Index.nodes_of`.
- `_validate_flow_traces` `:1013-1137`: lift the per-step value and note block `:1106-1122` into a helper that takes the tag name for its message prefix, called by both validators. q-flow messages must stay byte-identical.
- JSON-child extraction `:1180-1201`: lift into a helper taking the tag name, called by both validators; q-flow messages unchanged.
- New `_validate_sequence_node(node, report_fail, report_warn)` modelled on `_validate_flow_node` `:1173-1450` (the `fail`/`before_fails` pattern `:1203-1207`), `_rule_sequence_data` beside `_rule_flow_data` `:1453-1458`.
- `check_html_warnings` `:1461-1481`: its early return `:1463` and `q-flow` filter `:1478` widen to also run `_validate_sequence_node` on `q-sequence` nodes.
- New `_render_sequence_fallback_html` and `inject_sequence_fallbacks` modelled on `_render_flow_fallback_html` `:1484-1583` and `inject_flow_fallbacks` `:1586-1615` (same four skip rules).

### `H/assemble.py`, `H/checks.py`
- `assemble.py:524` and `:529`: call `inject_sequence_fallbacks` after `inject_flow_fallbacks`.
- `checks.py:382` calls `check_html_warnings`; no change beyond kitcheck's. `checks.py:389-394` (flow-not-inlined) unchanged.

### `K/kit.js`
- Header element list `:8`; `define(...)` list `:6023-6034`: add `define('q-sequence', QSequence)` last.
- New module-level sequence helpers and `class QSequence` between the end of `QFlow` `:6021` and the define list.
- `QFlow` trace methods to borrow: `_buildTracePanel` `:3770-3913`, `_toggleTracePlay` `:5676-5716`, `_stopTracePlay` and `_traceStepBy` `:5718-5740`, `_buildTraceDots` `:5769-5793`, `_renderTracePanel` `:5863-5891`, `_renderTraceValue` `:5893-5916`.
- Step-label hook: replace `data.nodeMap[step.node].label` at `:5780` and `:5868` with `this._traceStepLabel(step)`, and add `QFlow.prototype._traceStepLabel` returning that same label.
- Pulse methods to borrow: `_startPulse` `:5278`, `_placePulseDots` `:5298`, `_pointAlong` `:5322`, `_stopPulse` `:5340`; the record shape they read is built at `:4702-4710`; the dot gradient at `:4514-4519`, the per-edge `<mask>` and mask dot at `:4610-4625`, `pulsePath` at `:4660-4669`.
- Patterns to follow, not borrow: `_parseData` `:3550-3724`, `_ensureScaffold` `:3726-3768`, `_populateList` `:3915-4064`, `_failLayout` `:4067-4083`, `_setup` `:4101`, `connectedCallback`/`_onDocKey` `:3480-3512`, `_signature` `:3519-3527`, `disconnectedCallback`, `_showTraceStep` `:5795-5861` (how each step resets every edge's stroke, markers, `pulsePath` and mask dots before lighting the current one), `_openDrawer` `:5347-5466`, `_setRoving` `:5918`.
- Ready flag pattern: `data-q-flow-ready` removed at `:4105`, set `'true'` at `:4877`, `'error'` at `:4082`.

### `K/kit.css`
- Shared display rule `:37` (`:where(q-tabs, …, q-flow)`): add `q-sequence`.
- Trace panel rules `:1341-1525`, the 700px touch-target rule `:1529-1533`, and print `:1605-1607`: every `q-flow > aside…` and `q-flow aside…` selector widens to `:is(q-flow, q-sequence) > aside…` / `:is(q-flow, q-sequence) aside…`. `:is()` takes its most specific argument, a single type selector, so specificity is unchanged.
- These stay q-flow-only, and the q-sequence block writes its own equivalents: the tracing layout rules `:1295-1340` and `:1356` (`margin-top: 0` on the open panel), the pressed trace-button rule `:1438`, and `q-flow > details` `:1282-1290`.
- New `/* q-sequence */` block after the q-flow block; its 700px rules join the existing `@media (max-width: 700px)` region; its print rules join `@media print`.

### Other
- `S/scripts/verify/verify.mjs:226-236` and `tests/fixtures/html-kit/harness.mjs:156-165` and `:188-195`: the wait predicate also requires every `q-sequence` to have `data-q-sequence-ready`; the timeout message names `q-sequence` when it's the one not ready.
- `K/catalog.json:360-405`: new entry after `q-flow`.
- `S/templates/app/project/src/quirk-kit.d.ts:24`: add `'q-sequence': KitElementProps` after `q-flow`.
- `S/SKILL.md:138` and `:148`; `S/references/design-reference.md:200-202` and `:217-219`; `S/templates/report/rules.md:29-30`; `S/templates/components/rules.md:26`; `S/templates/app/rules.md:53-55`; `S/templates/companion/rules.md:35-36`.
- `S/evals/flow-evals.json` (eval id 10 expects `mermaid` for an OAuth sequence on an HTML page); `tests/test_writing_html_artifacts_skill.py:138-151` (allowed values `:145`).
- `tests/test_html_kit_catalog.py`: `SECTION_3_4` `:32-95` (q-flow `:81-92`; order is asserted `:126`), example script check `:156-166`, `test_known_rules_are_exactly_the_spec_set` `:216-226`.

## Contracts & interfaces

### 1. Data contract
Back-links: [Conceptual model](logic.md#conceptual-model), [Decisions Locked](logic.md#decisions-locked).

```
SCHEMA: the <q-sequence> JSON payload (one <script type="application/json"> child)
{
  kinds?: { <name>: 1..8 },                       // as q-flow: at most 8, integer, bool excluded
  participants: [                                 // 1..16
    { id: str, label: str, kind?: str, detail?: str }   // detail: q-flow's HTML whitelist
  ],
  steps: [Step],                                  // at least 1 message overall
  traces?: [ { id: str, label: str, steps: [ { message: str, value: <any JSON>, note?: str } ] } ]
}
Step =
  | { from: str, to: str, label: str, type: "call"|"reply"|"async", id?: str, detail?: str, create?: true }
  | { note: str, over: [str] }                    // 1+ participant ids
  | { end: str }                                  // a participant id
  | { fragment: "opt"|"loop", label?: str, steps: [Step] }
  | { fragment: "alt"|"par",  label?: str, branches: [ { label: str, steps: [Step] } ] }
```

- **Step kind** is decided by which key is present: `fragment`, then `note`, then `end`, then `from`. An object with none of them, or with more than one of `fragment`/`note`/`end`/`from`, is a malformed step.
- **Ids.** Participant ids and message ids share one namespace. Trace ids are their own namespace. Every id, label and branch label is a non-empty string after `strip()` (JS: `isBlankFlowId`).
- **Message number.** Messages are numbered 1..M in drawn order: a pre-order walk of `steps`, entering a fragment's `steps`, or each branch's `steps` in order. Notes, ends and fragments are not numbered. Both runtimes use this numbering in every message.
- **Touch.** A message touches `from` and `to`; a note touches each id in `over`; an end touches its participant.
- **Lookups** use own-property maps (`Object.create(null)` in JS, `dict` in Python), so an id such as `"constructor"` is an ordinary id.

### 2. Activation and reply matching (both runtimes)
Back-links: [Drawing](logic.md#drawing), SC-6.

State is an ordered list of open calls `{caller, callee, number}`. Walk `steps` in drawn order:

| Step | Effect |
|---|---|
| call, `from ≠ to` | push `{from, to, n}` |
| reply, `from ≠ to` | remove the last open call with `caller = to` and `callee = from`; none → `stray reply` |
| async, or any self-message | nothing |
| end `X` | remove every open call with `callee = X`, each → `no reply` |
| `opt` / `loop` with entry state `S` | walk the body from a copy of `S` to `S'`; calls in `S'` not in `S` → `no reply`, closed at the fragment's end; result `S ∩ S'` |
| `alt` with entry state `S` | each branch from a copy of `S` to `Si`; calls opened in the branch and open at its end → `no reply`, closed at the branch's end; result `{c ∈ S : c ∈ some Si}` |
| `par` with entry state `S` | as `alt`, but result `{c ∈ S : c ∈ every Si}` |
| end of steps | every open call → `no reply` |

Calls are compared by `number`. `no reply` and `stray reply` are warnings in Python only (contract 3). In JS the same walk records, for each row, the open calls in effect; a call's bar covers every row at which it is open, so a call answered in the first `alt` branch shows its bar again from the second branch's first row. A bar's nesting level is the count of calls with the same callee still open beneath it, drawn offset.

### 3. Kit check (`sequence-data`)
Back-links: [Authoring and building](logic.md#authoring-and-building), SC-2, SC-8.

Failures go through `report_fail` at the `<q-sequence>` start line; the element returns `None`. `N` is a message number, `<t>` a trace id, `K` a 1-based trace step. Messages, in check order:

| Case | Message |
|---|---|
| no JSON child, unparseable, not an object | as q-flow's, with `<q-sequence>` in place of `<q-flow>` |
| `kinds` checks | q-flow's kinds messages with the `<q-sequence>` prefix |
| `participants` not a non-empty list | `<q-sequence> needs at least one participant` |
| a participant without a non-empty `id` or `label` | `<q-sequence> each participant needs an id and a label` |
| more than 16 participants | `<q-sequence> has <P> participants; at most 16` |
| a participant `kind` not in `kinds` | `<q-sequence> participant "<id>" has undeclared kind "<kind>"` |
| a detail failing the whitelist | `<q-sequence> detail may hold only paragraphs, lists, code and links` |
| a detail whose elements nest more than 32 deep (counted the same way in both runtimes, without recursion) | `<q-sequence> detail may hold only paragraphs, lists, code and links` |
| a duplicate participant or message id | `<q-sequence> has duplicate id "<id>"` (once per id) |
| `steps` not a non-empty list, or no message anywhere | `<q-sequence> needs at least one message` |
| a malformed step | `<q-sequence> step must be one message, note, end or fragment` |
| a message without `from`, `to` or a non-empty `label` | `<q-sequence> message N needs from, to and a label` |
| a message `id` present and not a non-empty string | `<q-sequence> message N id must be a non-empty string` |
| `from` or `to` not a participant | `<q-sequence> message N names unknown participant "<id>"` |
| `type` not call, reply or async | `<q-sequence> message N has unknown type "<type>"; use call, reply or async` |
| `create` present and not `true` | `<q-sequence> message N create must be true` |
| `create` on a self-message | `<q-sequence> message N can't create its own sender` |
| a participant created twice | `<q-sequence> "<label>" is created twice` |
| a touch before the creating message | `<q-sequence> message N touches "<label>" before it is created` (`note touches …` / `end touches …` for those steps) |
| a touch after the participant ends | `<q-sequence> message N touches "<label>" after it ends` (likewise) |
| a participant ended twice | `<q-sequence> "<label>" ends twice` |
| a note without a non-empty `note` or with `over` not a non-empty list | `<q-sequence> note needs text and the participants it sits over` |
| a note over an unknown id | `<q-sequence> note names unknown participant "<id>"` |
| an end naming an unknown id | `<q-sequence> end names unknown participant "<id>"` |
| a fragment type outside the four | `<q-sequence> unknown fragment type "<type>"; use alt, opt, loop or par` |
| a fragment `label` present and not a non-empty string | `<q-sequence> <type> label must be a non-empty string` |
| `alt`/`par` with `branches` missing or fewer than 2 | `<q-sequence> alt needs at least 2 branches` (`par` likewise) |
| a branch without a non-empty `label` | `<q-sequence> each alt branch needs a label` (`par` likewise) |
| `opt`/`loop` with `steps` missing or empty, or a branch with no steps | `<q-sequence> fragment "<label or type>" has no steps` |
| trace shape | spec 2's messages with the `<q-sequence>` prefix: `traces must be a list`, `each trace needs an id and a label`, `has duplicate trace id`, `trace "<t>" needs at least 2 steps` |
| a trace step without a string `message` or a `value` key | `<q-sequence> trace "<t>" step K needs a message and a value` |
| `message` not a message id | `<q-sequence> trace "<t>" step K names unknown message "<id>"` |
| value and note | the shared helper from Code references: not JSON, over 400 lines, note not a string |
| any other string holding an unpaired surrogate | `<q-sequence> sequence data holds text that can't be written as UTF-8` (once) |
| no `summary` | the catalog's required-attribute message (no rule code) |

Warnings go through `report_warn` and never affect `passed`:

| Case | Message |
|---|---|
| more than 8 participants | `<q-sequence> has <P> participants: sequences over 8 participants are hard to follow; split it` |
| `no reply` from contract 2 | `<q-sequence> call N "<label>" has no matching reply` |
| `stray reply` from contract 2 | `<q-sequence> reply N "<label>" answers no call` |
| label over 40 characters | `<q-sequence> message N label is <C> characters: labels over 40 characters crowd the row; move the rest to the detail` |
| more than 60 messages | `<q-sequence> has <M> messages: sequences over 60 messages are hard to follow; split it` |
| trace value over 40 lines, note over 120 characters, trace over 30 steps | the shared helper's warnings with the `<q-sequence>` prefix |

- Checks that need a known participant or message run only when it is known.
- Any nesting depth the validator accepts must also render in both runtimes' text lists; neither renderer may overflow a recursion limit on a sequence the check passed.
- The JS element applies every failure that JSON can carry and returns `null` on any (the fail-hard notice). JS emits no warnings.
- Invariant: every q-flow message, its order and its line are unchanged.

### 4. Text list and no-JS fallback (same text in both runtimes)
Back-links: [Text list and fallbacks](logic.md#text-list-and-fallbacks), SC-18.

```
SCHEMA: list markup inside <q-sequence>
details.q-sequence-list[data-q-kit][data-q-sequence-list] > summary "Diagram as a list"
  > div[data-q-sequence-list-body]
      ul[data-q-sequence-list-participants] > li  "<label> (<kind>)" + ": " + sanitized detail when present
      ol[data-q-sequence-list-steps]          one li per step:
        message   li[data-q-sequence-list-message="<N>"]  "<N>. <from label> → <to label>: <label> (<type>)"
                  create adds ", creates <to label>" inside the parentheses
                  a message with a detail appends div[data-q-sequence-list-detail] holding the sanitized detail
        note      li[data-q-sequence-list-note]  "Note over <labels joined by ', '>: <text>"
        end       li[data-q-sequence-list-end]   "<label> ends"
        fragment  li[data-q-sequence-list-fragment="<type>"]  "<type>: <label>" then a nested ol of its steps;
                  alt/par: "<type>: <branch labels joined by ' / '>" then one nested li per branch,
                  "<branch label>" followed by its nested ol
      div[data-q-sequence-list-trace="<id>"] > p > strong "Trace: <label>"
        > ol > li[data-q-sequence-list-step="<K>"]
          then pre > code with the 2-space pretty JSON (see the K rule below)
```

- In a trace step's entry `K` is the trace step, so the text is `"<K>. message <N>, <from label> → <to label>, <label>"`, then `": <note>"` when present, then the code block, as in SC-18's `4. message 5, Stripe → Billing, card declined`.

- The injector skips an element only when it already has a direct-child list or stage element (`details[data-q-sequence-list]` or `[data-q-sequence-stage]`), never because the attribute name appears in its JSON or text.
- The no-JS fallback is `div.q-sequence-stage[data-q-kit][data-q-sequence-stage] > p.q-sequence-notice[data-q-sequence-notice]` "JavaScript is off, so the diagram is shown as a list below." followed by the list with `open`.
- Python writes no whitespace between tags and escapes with `html_lib.escape` (`quote=True` in attributes). JS uses `textContent`; the detail goes through `sanitizeFlowDetail`.
- The two allowed differences are spec 2's (integral floats, integer-like key order).
- Number in a nested `ol` uses the message number in the text, not the `ol`'s own counter, so CSS sets `list-style: none` on the steps lists.

### 5. Runtime (`kit.js`, `kit.css`)
Back-links: [Drawing](logic.md#drawing), [Narrow screens](logic.md#narrow-screens), [Exploring](logic.md#exploring), [Stepping through a trace](logic.md#stepping-through-a-trace).

**Element shell.** `class QSequence extends HTMLElement`, `observedAttributes = ['summary']`. Lifecycle as `QFlow`: `connectedCallback` sets `_uid = uid('q-sequence-')`, the document Escape listener (it acts when this element has focus, an open drawer or a trace; when the key came from inside another `q-sequence` or a `q-flow` it yields; from outside every diagram it closes this element's trace or focus without moving DOM focus, as spec 2's `:3482-3500` does; q-flow's own listener is unchanged, so an Escape inside a `q-sequence` also closes a tracing `q-flow`'s trace, which is spec 2's "from outside every graph" rule), `onTheme`, `watchChildren` with a `_signature` of the JSON text and summary; `disconnectedCallback` stops Play and the pulse and tears down listeners. `_setup` removes `data-q-sequence-ready`, parses, builds the scaffold and list, then after `document.fonts.ready` (when present) measures and draws, then sets `data-q-sequence-ready="true"`; parse failure → notice "This diagram could not be drawn. The full diagram is listed below.", list opened, `data-q-sequence-ready="error"`.

```
CONTRACT: QSequence parse result
{ participants: [{id, label, kind|null, color|null, detail|null, index}], partMap,
  messages: [{number, id|null, from, to, label, type, detail|null, create, self, frags: [fragment refs]}],
  steps: <the tree with messages replaced by references to messages[]>,
  traces: [{id, label, steps: [{message, value, note|null}]}],   // message: index into messages
  ends: {participantId: row}, creates: {participantId: messageNumber} }
```

**DOM.** Direct children of `<q-sequence>` in this order: toolbar, pinned strip, scroll box (`_stage`), the trace panel (inserted after `_stage` by the borrowed `_buildTracePanel`), drawer, live region, list.

| Part | Element |
|---|---|
| toolbar | `div[data-q-sequence-controls][role=toolbar][aria-label="Diagram controls"]`, holding "Step through" `button[data-q-sequence-action="trace"]` with `aria-pressed` only when there are traces; no other buttons |
| pinned strip | `div[data-q-sequence-pinned]`, sticky, outside the scroll box; one `button[data-q-sequence-header="<id>"]` per participant |
| scroll box | `div[data-q-sequence-stage]` with `overflow-x: auto` holding `svg[data-q-sequence-svg][role=img][aria-label=<summary>]` |
| message | `g[data-q-sequence-message="<N>"][role=button][tabindex]` with a line, arrowhead, label text and `aria-label="Message N of M, <from> to <to>, <label>, <type>"` (M = message count; SC-12's announcement is this label) |
| lifeline, bar, fragment, note | `[data-q-sequence-lifeline="<id>"]`, `[data-q-sequence-bar="<id>"]`, `[data-q-sequence-fragment="<type>"]`, `[data-q-sequence-note]` |
| created header | `g[data-q-sequence-created="<id>"]` in the SVG at the creating row, a click target but not in the roving order (the strip header is the participant's roving stop); end `[data-q-sequence-end="<id>"]` X |
| drawer | `aside.q-flow-drawer[data-q-flow-drawer][aria-label="Details"][data-q-inactive]`, built by the shared `canvasBuildDrawer(host, label, parent)` with `parent` = the element (the helper's optional third argument, defaulting to `host._stage` for q-flow and q-schema); styled only from the q-sequence block |
| live region | `div.q-visually-hidden[aria-live=polite][data-q-sequence-live]` |
| trace panel | built by the borrowed `_buildTracePanel`, so it is `aside[data-q-flow-trace-panel]` with spec 2's parts and `data-q-flow-*` names |
| list | contract 4 |

**Layout.**
- Columns in `participants` order. Spacing: adjacent column centres sit at least the widest header apart; any message between columns `a < b` forces `x[b] − x[a] ≥` its label width plus padding; a self-message forces room to the right of its column. Labels and notes wrap at 16em, and a single word wider than that breaks across lines, so nothing draws outside the SVG; rows grow to fit wrapped text.
- Rows top to bottom: each message, note and end is a row; a self-message row is taller; a fragment adds a tab row at its top, a divider row between branches, and a closing row.
- A fragment spans from the leftmost to the rightmost column any of its steps touch (nested steps included), inset per nesting level so both edges show.
- Message styles from SC-3: call solid with a filled head, reply dashed with an open head, async solid with an open head. The label reads `<N>. <label>`.
- A created participant's lifeline starts at its creating row; an ended one stops at its end row with an X.
- Every colour is a `--q-*` token, through `var()` in attributes so the theme toggle needs no redraw; kind accents use `var(--q-color-chart-<n>)`.

**Pinned headers.** The strip is `position: sticky; top: 0` with `overflow: hidden`; its inner row is translated by `-scrollLeft` of the scroll box on its `scroll` event, so headers stay over their lifelines. The strip sets `data-q-sequence-stuck` while the element's top is above the viewport and its bottom below the strip; a created participant's strip header is hidden unless stuck, so the column above its creating row is empty at rest. Nothing in the page's flow above the element may set `overflow`, or sticky breaks; the test at 375px proves it in the report template.

**Focus.**
- Participant (header click, Enter): `data-q-sequence-focus="<id>"` on the element; lifeline and touching messages `data-q-sequence-lit`; every other message, lifeline, bar and note `data-q-sequence-dim`; fragment boxes neither. The drawer opens: label, kind tag, sanitized detail, then the messages it sends and receives as buttons `"sends N. label"` / `"receives N. label"`.
- Message (click, Enter): the message lit, its two headers `data-q-sequence-lit`, the rest dim. The drawer: title `"N. label"`, `"<from> → <to>"`, type, `"answered by M. label"` or `"answers M. label"` as a button when contract 2 pairs them, the fragments holding it (`"inside loop: up to 3 attempts, alt: card declined"`), then the detail.
- Clicking a drawer button moves focus to that message or participant. Clicking the same thing again, clicking empty diagram space, the drawer's Close button, or Escape clears focus and closes the drawer.
- Live region on each focus: `"<label>, <kind>, sends S, receives R"` for a participant; the message's `aria-label` for a message.

**Keyboard.** One roving tabindex across the strip headers and the message groups; the first Tab lands on the first participant's strip header, and a created participant's strip header stays in the roving order (visible while focused). ArrowLeft/ArrowRight between headers; ArrowDown on a header to the first message touching that participant; ArrowUp/ArrowDown on messages by number; ArrowUp on message 1 to its sender's header; Enter acts as a click; Escape clears. Moving focus scrolls the element and the scroll box so the target is in view (`behavior: 'auto'` under reduced motion).

**Drawer and panel placement.**
- Wider than 700px: while the drawer or the trace panel is open, `q-sequence` is a two-column grid, `minmax(0, 1fr) min(22rem, 40%)`, with every child in column 1 except the open aside, which is in column 2 spanning the strip and stage rows; the list spans both columns. The open aside is `position: sticky`, `top` below the strip, `max-height: calc(100vh - <strip> - var(--q-space-4))`, `overflow-y: auto`.
- 700px and narrower: the drawer is `position: fixed` at the bottom, full width, `max-height: 55vh`. The trace panel is `position: fixed` at the bottom, full width, `max-height: 50vh`, `overflow-y: auto`, and gains `button[data-q-sequence-trace-collapse]` with `aria-expanded`, appended to `.q-flow-trace-buttons` after every `_buildTracePanel` call (which empties the panel); collapsed, only the counter row, Back, Next, Play and the collapse button show. The page gets bottom padding equal to the open panel's height so the last row can scroll above it.

**Trace mode.** `QSequence` borrows the panel and the pulse:

```
CONTRACT: borrowing
for name in [_buildTracePanel, _renderTracePanel, _renderTraceValue, _buildTraceDots,
             _toggleTracePlay, _stopTracePlay, _traceStepBy,
             _startPulse, _placePulseDots, _pointAlong, _stopPulse]:
  QSequence.prototype[name] = QFlow.prototype[name]
QSequence supplies: _uid, _stage, _data.traces, _trace, _traceEls, _tracePanel, _traceChangesOnly,
  _pulseFrame, and the methods _startTrace(i), _showTraceStep(i), _traceStepLabel(step),
  _openTrace(i), _closeTrace(restoreFocus), _clearFocus(); its own _traceBtn and _lastTraceIndex
QFlow gains: _traceStepLabel(step) -> data.nodeMap[step.node].label  (its only change)
```

- `_traceStepLabel(step)` in `QSequence` returns `"message N, <from> to <to>, <label>"`, which the borrowed counter turns into `"Step 3 of 6, message 3, Billing to Stripe, create charge"` and the dots into `"Step 3: message 3, …"`.
- `_openTrace(i)` and `_startTrace(i)` follow `QFlow`'s `:5615-5656` without the canvas calls: stop Play, clear focus and close the drawer, set `_trace = {index, step: 0, messages: {N: true}}`, set `data-q-sequence-tracing`, `aria-pressed="true"`, show the panel, set the picker, build the dots, show step 0; `_openTrace` then focuses Next.
- `_closeTrace(restoreFocus)` mirrors `:5658-5674` without the canvas calls and clears every lit, dim and pulse attribute.
- `_showTraceStep(i)`: the step's message gets `data-q-sequence-current` and `data-q-sequence-lit`; messages on the trace no attribute; messages off it, and the note rows, `data-q-sequence-dim`. Not reduced motion: start the pulse on the current message with `pulseSchedule([{rec, down: true}], rec.edge.from)`; reduced motion: `_stopPulse()` and a 3.5 stroke on the current line. Every other message's stroke returns to rest and its `pulsePath` and mask dots get `data-q-inactive`, as `QFlow._showTraceStep` `:5795-5861` does for edges. Then scroll the current message into view (`behavior: 'auto'` under reduced motion; vertical on the page, horizontal in the scroll box, and above the fixed panel at 700px and narrower), then `_renderTracePanel(i)`.
- Pulse record per message, built when drawn: `{edge: {from, to}, basePath, pulsePath, mask, maskDots, points}` with a `<mask>` and a gradient circle in the SVG's `<defs>`, ids prefixed with `_uid`, the same shape `QFlow` builds at `:4702-4710`; `pulsePath` carries `data-q-inactive` when idle.
- Clicks while tracing: a message on the trace jumps to its next visit after the current step, else its first; a message off the trace or a header: `_closeTrace(false)`, then the normal focus; empty space: nothing. Escape, or the toolbar button again: `_closeTrace(true)`.
- The borrowed `_startPulse` keeps running while `self._focusedNode || self._trace`; `QSequence` never sets `_focusedNode`, so the pulse runs only in trace mode.

**Ready flag.** Every setup, including one whose parse fails, invalidates any draw still waiting on fonts, so a stale draw never replaces the error notice. `data-q-sequence-ready` is absent while setting up, `"true"` once drawn, `"error"` after a parse failure.

### 6. Skill guidance and evals
Back-links: [Choosing](logic.md#choosing), [Success criteria](logic.md#success-criteria).

- `SKILL.md:138`, `design-reference.md:200`, the four `rules.md` lines: sequence diagrams on HTML pages use `<q-sequence>` (call, reply, async; fragments; traces for the payload); `q-flow` stays for graphs; Mermaid keeps diagrams inside Markdown and state charts and ER diagrams on HTML pages. Remove "sequence" from every Mermaid-keeps list.
- `SKILL.md:148` and the References list: name `q-sequence`.
- `design-reference.md:217-219`: the motion exception also covers the q-sequence trace pulse and Play.
- `templates/companion/rules.md:35-36`: `<q-sequence>` may go in `content`, never in an option's `html`, as `<q-flow>`.
- `flow-evals.json`: eval 10 expects `q-sequence`; add sequence-on-HTML prompts expecting `q-sequence` to reach at least 6; keep `mermaid` at 6 or more with Markdown sequence diagrams and state charts. `test_flow_evals_are_balanced_and_unique` allows `("q-flow", "mermaid", "q-sequence")` and requires at least 6 of each.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

```
SCHEMA: cleaned sequence from _validate_sequence_node (Python)
{"participants": [{"id", "label", "kind", "detail"}], "part_map": {id: participant},
 "messages": [{"number", "id", "from", "to", "label", "type", "detail", "create"}],
 "steps": <tree, messages as {"message": number}>,
 "traces": [{"id", "label", "steps": [{"message": number, "value", "note"}]}]}
```

```
SCHEMA: catalog.json q-sequence entry
tag "q-sequence", parent null, interactive true,
attributes [{name "summary", required true, kind "text", description}],
requires [["script"]], rules ["sequence-data"],
use_when "Use when …" (single line), children (single line; names kinds, participants, steps of
messages/notes/ends/fragments, traces pointing at messages), example: one <q-sequence> with one
<script type="application/json"> child, a small sequence with one fragment and one trace, clean with no warnings
```

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **q-flow behavior and markup.** Every `data-q-flow-*` name, every q-flow kit-check message, its fallback and its tests stay as they are; q-flow's only code change is the `_traceStepLabel` hook (and the two helper lifts in `kitcheck.py`, which keep messages byte-identical). The q-flow browser suite pins this.
- **The borrowed methods' bodies** (`_buildTracePanel`, `_renderTracePanel`, `_renderTraceValue`, `_buildTraceDots`, `_toggleTracePlay`, `_stopTracePlay`, `_traceStepBy`, `_startPulse`, `_placePulseDots`, `_pointAlong`, `_stopPulse`) apart from the label hook. Both elements run them; a q-sequence need is met in `QSequence`, not by editing them.
- **`pulseSchedule` and the pulse constants `K/kit.js:3007-3063`.** Pulse-speed tests pin them.
- **`needs_flow`, `FLOW_TAG` and the flow-not-inlined check `H/checks.py:389-394`.** A `q-sequence` must never pull in the flow bundle.
- **The trace panel's specificity.** Selector widening uses `:is()` so existing rules keep their weight under the `:where()` convention in the header of `K/kit.css`.

## Always / Ask / Never

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Run `python3 S/scripts/pins.py stamp kit 1.0.0` after any edit to `K/kit.js` or `K/kit.css`, and `python3 S/scripts/kit_docs.py reference` after any edit to `K/catalog.json`.
- Keep the Python and JS failure rules, message numbering and list text identical.
- Write labels, notes and values with `textContent`; details only through `sanitizeFlowDetail`.

**Ask**
- Any change to the data contract or a message in contract 3.
- Any change to q-flow behavior.

**Never**
- Load or reference `window.quirkFlow` from `QSequence`.
- Animate anything under reduced motion; start Play without a click.
- Copy a trace-panel or pulse method into `QSequence`.

## Cross-cutting

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).


- **Security:** details go through the existing whitelist in both runtimes; every other string is text. Own-property maps keep prototype names ordinary ids.
- **Performance:** at most 16 columns and a few hundred rows; layout is arithmetic, and measuring uses one canvas context.
- **Page weight:** a page with only `q-sequence` carries `kit` and no `flow`.
- **Rollback:** the element is additive; removing its define, catalog entry and rule leaves q-flow as before.

## Testing strategy

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Success criteria](logic.md#success-criteria).

| File | Coverage |
|---|---|
| `tests/test_html_kit_check.py` (new q-sequence section) | One test per contract-3 failure and warning; the logic spec's checkout sequence with both traces passes with no warnings; the activation table rows that warn; an id named `"constructor"` is ordinary |
| `tests/test_html_builder.py` | The injected no-JS list for the checkout sequence, including a create, an end, nested fragments and a trace step; a page with only `q-sequence` lists `kit` and not `flow`; a page with both lists `flow` once |
| `tests/test_html_kit_elements.py` (new `SEQ_CHECKOUT` page and fixture) | Numbering and row order (SC-3); self-message row (SC-4); fragment rows and columns (SC-5); bars from contract 2, including the alt resumption (SC-6); headers with kind colours (SC-7); create and end (SC-8); pinned headers at 375px scrolled down and sideways (SC-9); participant focus dims the rest and opens the drawer (SC-10); message drawer with the paired reply (SC-11); keyboard (SC-12); trace mode open, dim and pulse (SC-13); stepping with the loop revisit and change marks (SC-14); clicks while tracing (SC-15); reduced motion (SC-16); the phone panel (SC-17); the runtime list matches the builder's (SC-18); theme toggle recolours (SC-22); a bad payload fails to the notice with `data-q-sequence-ready="error"`; on a page with a tracing `q-flow` and a tracing `q-sequence`, Escape inside the sequence closes both traces and Escape inside the graph closes only the graph's; the q-flow trace tests still pass. The fixture and example give ids to every message a trace names (the logic spec's list gives ids only to messages 3 to 7, so add `place-order`, `charge-order` and `show-receipt`) |
| `tests/test_html_kit_catalog.py` | `SECTION_3_4` entry, the example's single JSON script, `sequence-data` in the known rules |
| `tests/test_html_kit_examples.py`, `tests/test_html_kit_docs.py` | The catalog example builds clean and verifies with and without JS; `kit_docs.py reference --check` |
| `tests/test_html_layout_shapes.py` | The report explainer with the checkout sequence builds, checks and verifies |
| `tests/test_html_vendor.py` | `pins.py verify` after restamping |
| `tests/test_writing_html_artifacts_skill.py` | The widened flow evals |

Browser tests need `S/scripts/verify/node_modules`. On this machine run them through the node relay for BUG-14: start its server from zsh, and put its `bin/` first on `PATH` for pytest.

## Answers to the logic spec's deferred items

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Deferred item | Resolution |
|---|---|
| Field names for create and end | `create: true` on the message; `{end: "<id>"}` as a step (contract 1) |
| Pinned headers in a sideways box | A sticky strip outside the scroll box, translated by its `scrollLeft` (contract 5) |
| Row heights | Measured labels wrapped at 16em; taller self-message rows; tab, divider and closing rows for fragments |
| Fragment insets | One inset step per nesting level; spans the touched columns |
| Where the panel and tree live | They stay in `QFlow`; `QSequence` borrows the methods; CSS selectors widen with `:is()` |
| The pulse on a message arrow | Borrowed `_startPulse` family with a per-message record and `pulseSchedule` |
| Readiness signal | `data-q-sequence-ready`, waited on by verify and the harness |
| Numbering in both runtimes | Contract 1's pre-order message number |

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- Everything under Not in scope in the logic spec.
- JS-side warnings.
- Moving the trace panel out of `QFlow` into a shared class. The logic spec's "factoring spec 2's trace panel and value tree so both elements share them" is met by borrowing the methods with one label hook, which shares one copy without moving code that a parallel branch is also changing.
- Tier-2 JSX rule checks (`check_jsx` checks attributes only, as for q-flow).
