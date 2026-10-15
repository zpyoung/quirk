# Tech spec: data-state examples for logic-spec scenarios

**Status:** Reviewed
**Logic spec:** [logic.md](logic.md) (Approved. Tech spec: requested)

All paths are relative to the repo root (`/Users/zpyoung/orca/workspaces/quirk/scenario-data-states`).
Line numbers are as of `RUN_BASE` `1a39a23` and drift as tasks land; the symbol names are the stable anchor.

## Architecture

Implements [Where an example lives](logic.md#where-an-example-lives) and [Data flow](logic.md#data-flow).

Four units change, and they talk only through `logic.json` and the render payload:

| Unit | Files | Role |
|---|---|---|
| Rubrics | `skills/writing-specs/logic-spec.md`, `skills/writing-specs/interactive-logic-spec.md`, new `skills/writing-specs/scenario-examples.md` | Tell Claude when and how to write an example. The new file is the one home for the conventions; both rubrics link to it. |
| Renderer | `skills/writing-specs/interactive/render_spec.py` (Python 3.9+, stdlib only) | Validates `example`, hashes it with its scenario, gates the stage-1 fold, renders sub-bullets into `logic.md`, and puts `openAsks` into the page payload. It is the **only** place that decides whether an `[ASK]` is open. |
| Page types and state | `skills/writing-specs/interactive/app/src/spec-types.ts`, `review-state.ts` | Type the new field and payload key; one pure helper that says why Approve is blocked. |
| Page views | `app/src/views/scenarios-view.tsx`, `app/src/views/scenario-focus-dialog.tsx`, new `app/src/views/scenario-example.tsx`, `app/src/index.css` | Row tokens, any-row-opens-dialog, three-column example with the palette, outcome change → update request. |

The page is React 19 + `@astryxdesign/core` 0.6.2, built by Vite with `vite-plugin-singlefile` into the
committed `skills/writing-specs/interactive/review-template.html`. `render_spec.py` embeds the payload
into that template at its single `PAYLOAD_PLACEHOLDER`. Tests are pytest (`pytest -q` from the repo root,
`tests/` per `pyproject.toml`); the page has no JS test runner, only `tsx` check scripts under `app/scripts/`.

`renderId` is `render_id(logic)` over `logic.json` alone (`render_spec.py` `render_id`, ~L176), so
template or payload changes never move a spec's `renderId`.

## Code references

### Renderer: `skills/writing-specs/interactive/render_spec.py`

Back-links: [4](logic.md#4-an-open-gap-blocks-its-scenario-until-the-answer-is-in-the-then),
[5](logic.md#5-an-example-changes-with-its-scenario),
[7](logic.md#7-logicmd-shows-examples-as-labelled-sub-bullets),
[9](logic.md#9-specs-without-examples-are-unchanged).

| Symbol | Where | Change |
|---|---|---|
| `RENDER_OUTPUT_FIELDS_V2` | ~L25-37 | **None.** `example` must stay hashed. See fences. |
| `item_hashes`, `stage1_item_hashes`, `canonical_json`, `render_id` | ~L172-209 | **None.** |
| `Validator` (`error`, `string`, `string_array`, `object`, ...) | ~L72 | Use as-is to validate `example`. |
| `validate_logic_v2` scenario loop | ~L898-937 | Add `example` validation and the malformed-marker check after the `answeredComment` check (~L935). |
| `validate_logic_v2` stage-2 branch | ~L1321-1353 | Add the open-`[ASK]` error for non-dropped scenarios. |
| `stage1_gate_failures(logic, state)` | ~L2653 | Add an `examples` gate after the `scenarios` gate. |
| `command_fold` | ~L2914-2958 | **None.** It already prints `gate <name>: <message>` per failure and exits 4 (~L2942). |
| `render_markdown_v2` scenario block | ~L2207-2231 | Emit example lines after the `**Alternatives**` line (~L2222) and before the explanation line (~L2223). |
| `prepare_render_files` | ~L2387-2413 | Add `openAsks` to the embedded payload. |
| new `scenario_open_asks`, `_example_markdown_lines`, regex constants | module level, near the other helpers | Create. |

### Page: `skills/writing-specs/interactive/app/src/`

Back-links: [4](logic.md#4-an-open-gap-blocks-its-scenario-until-the-answer-is-in-the-then),
[5](logic.md#5-an-example-changes-with-its-scenario),
[6](logic.md#6-the-review-page-shows-examples-in-the-focus-dialog), [Conventions](logic.md#conventions).

| Symbol | Where | Change |
|---|---|---|
| `Scenario` | `spec-types.ts` ~L35-56 | Add `example?: ScenarioExample`. |
| `LogicSpecPayload` | `spec-types.ts` ~L348-355 | Add `openAsks: Record<ScenarioId, string[]>`. |
| `isPayload` (used by `readPayload`) | `review-state.ts` ~L222 | Also require `openAsks`: an object whose values are arrays of strings. A payload without it fails the existing schema-mismatch error instead of crashing later. |
| new `approveBlockReason` | `review-state.ts`, next to `scenarioThen` (~L581-588) | Create. |
| new `EXAMPLE_OUTCOME_UPDATE_PREFIX`, `exampleOutcomeUpdate` | `review-state.ts` | Create. |
| `isScenarioUndecided`, `gateList`, `carryOver`, `changedSinceReviewIds` | `review-state.ts` ~L306-666 | **None.** See fences. |
| `OutcomeCell` `set` | `views/scenarios-view.tsx` ~L41-79 (`set` ~L44-53) | Write/remove the automatic update when the scenario has an example. |
| `DecisionCell` | `views/scenarios-view.tsx` ~L83-144 (Approve item ~L116, hint ~L120) | Disable Approve from `approveBlockReason`; show its hint. |
| `scenarioColumns` `id` column | `views/scenarios-view.tsx` ~L258-274 | Example / Open question tokens; the ID becomes a button that opens the dialog. |
| `BehaviorGroup` | `views/scenarios-view.tsx` ~L351-371 | Own the browse-dialog state; add a row-click `TablePlugin`; render `ScenarioFocusDialog` in browse mode. |
| row-click precedent | `views/board-view.tsx` ~L245-260 (`dragPlugin.transformBodyRow`, `onClick`) | Follow this pattern. |
| `ScenarioFocusDialog`, `OpenFocusDialog`, `FocusedScenario`, `undecidedQueue` | `views/scenario-focus-dialog.tsx` (export ~L46, queue ~L12-18, width ~L76, body ~L28-43) | Add browse mode, example pane, width rule, stage-2 read-only body. |
| `SpecMarkdown` | `views/shared.tsx` ~L21-28 | Reuse. Its `_` → `_​` trick stays. |
| `MarkdownInlinePlugin` | `@astryxdesign/core/Markdown`; usage in `views/item-links.tsx` (`ItemLinksProvider`) | Mark colouring uses the same `{ pattern, render }` plugin shape. |
| new `ScenarioExampleView`, `exampleMarkPlugins` | new `views/scenario-example.tsx` | Create. |
| `.scenario-example` rules | `index.css` (after the decision colours, ~L27-38) | Create. |

### Rubrics

Back-links: [1](logic.md#1-claude-writes-an-example-for-every-scenario-with-data-to-show),
[2](logic.md#2-examples-follow-the-shared-conventions), [3](logic.md#3-the-then-is-the-contract),
[8](logic.md#8-later-stages-take-their-contract-from-the-then).

| File | Anchor | Change |
|---|---|---|
| new `skills/writing-specs/scenario-examples.md` | | The conventions reference. Content contract below. |
| `skills/writing-specs/logic-spec.md` | `## Writing it` bullets (L13-27, coverage at L16) | One bullet: scenarios with data to show carry an example per `scenario-examples.md`, written in the same pass. |
| same | `## Logic-spec self-review` checks (L33-36) | Add check 5, the example check. |
| same | `## User Review Gate` (between L44 and L46) | List every open `[ASK]` with its scenario; answers go into the Thens before approval. |
| `skills/writing-specs/interactive-logic-spec.md` | `## What to write in stage 1`, Scenarios bullet (L14) | `example` field, linked to `scenario-examples.md`. |
| same | `## Stage-1 feedback rounds` step 2 (L54) | Handling updates on scenarios with examples, including the automatic outcome update. |
| same | `## Stage-1 sign-off and fold` (L65-71) | The `examples` gate. |
| same | `## Derivation` (L77) | Derive from scenario text; ignore examples. |
| same | `## Amendments after approval` (L137-146), `## Self-review` (L152-154) | Point at the sync rule and the example check in `scenario-examples.md`. |

## Contracts & interfaces

### Open-`[ASK]` detection (renderer only)

Back-link: [4](logic.md#4-an-open-gap-blocks-its-scenario-until-the-answer-is-in-the-then).

`REGEX:` open gap, case-sensitive: `\[ASK: ([^\[\]\n]+)\]` (no square brackets inside the question, which keeps detection linear and makes a nested marker malformed)

`REGEX:` anything that looks like a gap, case-insensitive: `\[\s*ask\b`

`CONTRACT: scenario_open_asks(scenario: dict) -> List[str]`
- Pre: `scenario` passed `validate_logic_v2`'s scenario checks (or has no `example`).
- Post: the captured question text of every open-gap match across `before`, each of `steps` in order, then `after`. `[]` when there is no `example`.
- Invariant: pure; no I/O; the only function in the repo that decides whether a gap is open. The page reads its result from the payload.

### Validation (`validate_logic_v2`)

Back-links: [Where an example lives](logic.md#where-an-example-lives), [9](logic.md#9-specs-without-examples-are-unchanged).

- `example` absent: no change in behavior.
- `example` present: must be an object with exactly the keys `before`, `steps`, `after`. `before` and `after` are non-empty strings; `steps` is a non-empty array of non-empty strings. Each violation is one `Validator.error` at the JSON pointer of the offending key (`/scenarios/<i>/example`, `/scenarios/<i>/example/steps/<j>`, ...). Unknown keys inside `example` are errors.
- Malformed marker: every match of the look-alike regex in any part must start a match of the open-gap regex at the same offset. Otherwise `Validator.error` at that part's pointer with the message `malformed [ASK] marker; write [ASK: <question>]`. Applies in both stages.
- Stage 2 only: a scenario without `dropReason` whose `scenario_open_asks` is non-empty gets `Validator.error` at `/scenarios/<i>/example` with the message `open [ASK] after stage-1 sign-off`.
- Errors never raise; they surface through the existing `emit_errors` path with exit 1.

### Stage-1 fold gate (`stage1_gate_failures`)

Back-links: [4.3](logic.md#4-an-open-gap-blocks-its-scenario-until-the-answer-is-in-the-then), [5.2](logic.md#5-an-example-changes-with-its-scenario).

A new gate named `examples`, appended after `scenarios` in the returned list, one failure tuple per offending scenario, in scenario order:

| Condition, read from the export's `state` | Message |
|---|---|
| `scenarioApproved[id]` is true, `id` is not in `scenarioDrops`, and `scenario_open_asks` is non-empty | `open [ASK] in <id>` |
| `scenarioApproved[id]` is true, the scenario has `example`, and `scenarioOutcomes[id].choice` exists and is not `"spec"` | `outcome changed on <id>; Claude must rewrite its example first` |

Any non-`spec` choice counts as changed, including `custom` with blank text. When both conditions hold for one scenario, only the open-`[ASK]` tuple is emitted.

`command_fold` prints these as `gate examples: <message>` and exits 4 through its existing loop. A dropped scenario never fails this gate. The page already prevents both states; this gate is the backstop for a hand-edited or stale export.

### Markdown rendering (`render_markdown_v2`)

Back-links: [7](logic.md#7-logicmd-shows-examples-as-labelled-sub-bullets), [9](logic.md#9-specs-without-examples-are-unchanged).

`CONTRACT: _example_markdown_lines(example: dict) -> List[str]`
- Called once per scenario that has `example`, between the alternatives line and the explanation line. A scenario without `example` emits exactly the lines it emits today.
- Output, in order: `   - **Data before:** <before>`, `   - **Walkthrough:**`, one `     <n>. <step>` per step (1-based), `   - **Data after:** <after>`.
- A newline inside a part renders as a hard break: the line before it ends with two spaces, and the continuation line is indented to that item's content column (5 spaces for Data before/after, 8 for a step, so continuation under `     1. ` aligns). CRLF and CR normalize to LF first, as `markdown_cell` does.
- Mark characters (`✓`, `✗`, `*`, `[ASK: …]`, `**`) pass through unchanged. No escaping.
- Deterministic: same input, same bytes.

### Render payload (`prepare_render_files`)

Back-link: [6](logic.md#6-the-review-page-shows-examples-in-the-focus-dialog).

`SCHEMA:` the payload gains `"openAsks": { "<scenario id>": ["<question>", ...] }`, containing only scenarios with at least one open gap, from `scenario_open_asks`. An empty object when none. v1 specs never build a page payload, so this is v2 only.

### Approve blocking (page)

Back-links: [4.1](logic.md#4-an-open-gap-blocks-its-scenario-until-the-answer-is-in-the-then), [5.2](logic.md#5-an-example-changes-with-its-scenario).

`CONTRACT: approveBlockReason(state: ReviewState, scenario: Scenario, openAsks: Record<ScenarioId, string[]>) -> 'outcome-missing' | 'open-ask' | 'outcome-changed' | null`
- `'outcome-missing'`: the outcome is `custom` with blank text (today's `isOutcomeMissing`, moved here).
- `'open-ask'`: `openAsks[scenario.id]` is non-empty.
- `'outcome-changed'`: `scenario.example` exists and `scenarioThen(state, scenario) !== scenario.then`.
- Otherwise `null`. Checked in that order; the first match wins. Pure.

`DecisionCell` passes `isDisabled={reason !== null}` to the Approve item and shows one hint line per reason: `Write your outcome first.` (unchanged), `Answer the open question in an update first.`, `Claude has to rewrite the example for this outcome first.` Update and Drop are never disabled.

### Outcome change on a scenario with an example (page)

Back-link: [5.2](logic.md#5-an-example-changes-with-its-scenario).

`CONFIG:` `EXAMPLE_OUTCOME_UPDATE_PREFIX = 'Rewrite this scenario for the outcome I picked: '`

`CONTRACT: exampleOutcomeUpdate(outcomeText: string) -> string` returns the prefix, then the outcome in double quotes, then `. Update its Then and example together.`

In `OutcomeCell` `set`, only when `s.example` exists, in the same `update` call that clears approval:
- New choice is not `spec`: set `scenarioUpdates[s.id]` to `exampleOutcomeUpdate(<the chosen outcome's text>)`, unless the existing update text exists and does not start with the prefix (the reviewer wrote their own; leave it).
- A `custom` choice with blank text counts as `spec` here: it is the moment before the reviewer has typed an outcome, Approve is already blocked by `'outcome-missing'`, and an update quoting an empty outcome would give Claude nothing to act on. The fold gate still treats it as changed, as a backstop.
- Typing in the custom outcome field re-derives the update text the same way, under the same "unless" rule.
- New choice is `spec`: delete `scenarioUpdates[s.id]` only if its text starts with the prefix.
- A scenario without `example` behaves exactly as today.

### Browse mode and the example pane (page)

Back-link: [6](logic.md#6-the-review-page-shows-examples-in-the-focus-dialog).

`CONTRACT: ScenarioFocusDialog({ isOpen, onClose, behaviorId?, startScenarioId?, props })`
- No `startScenarioId`: the undecided queue, exactly as today (`undecidedQueue`, Approve advances).
- With `startScenarioId`: the queue is every scenario of that scenario's behavior, in spec order, regardless of decision or stage. It opens at `startScenarioId`. The queue is captured once at open, as today. Previous/Next and arrow keys work as today; Approve still advances.
- Width: `1040` when any scenario in the queue has `example`, else `760`.
- Body order: Given, When, Then, the example pane (when present), Why, decision, comment. In stage 2 the Then is the read-only `Clause` of `scenarioThen`, and the decision area shows what the table's stage-2 decision column shows (Approved/Dropped token, or the re-approve checkbox for a reopened scenario). There is no comment field in stage 2.

`CONTRACT: ScenarioExampleView({ example }: { example: ScenarioExample })`
- Three labelled panes, `Data before`, `Walkthrough`, `Data after`, in a CSS grid of three columns (`1fr 1.2fr 1fr`) that stacks to one column below 720px.
- `before` and `after` render through `SpecMarkdown` with every single newline turned into a markdown hard break, after CRLF and CR normalize to LF as on the markdown side. `steps` render as an ordered list, one `SpecMarkdown` per step.
- Mark colouring is via `exampleMarkPlugins`, passed only inside this view, alongside the existing item-link plugins.

The pane colours marks in two ways:

- `CONTRACT: EXAMPLE_PHRASE`: result and rejection phrases are cut out of each line before parsing. `REGEX:` `([✓✗])([^;\n]+)`. Each phrase is rendered through inline Markdown inside a green bold (`✓`) or red (`✗`) span, so nested records and invented values stay inside the colour.
- `CONTRACT: exampleMarkPlugins: MarkdownInlinePlugin[]`: two global `{ pattern, render }` plugins, as in `ItemLinksProvider`, for the marks that survive parsing:
  - Invented value, rendered as a grey italic span with the `*` kept. `REGEX:` `(?<=^|\s|\*,)[^\s*]+\*(?=[\s,;:.)\]]|$)` finds it in the source text. Because the Astryx parser pairs two such stars in one part as emphasis, the pane first escapes any literal U+E000 in the text, then swaps each matched `*` for the private-use placeholder U+E000; the plugin matches the placeholder and the rendered span restores the `*`.
  - Gap, rendered as an amber underlined span. `REGEX:` `\[ASK: [^\[\]\n]+\]`

The gap pattern here is display only and must match the renderer's open-gap regex. An invented value inside a result or rejection phrase renders as an invented-value span nested inside that phrase's span. Invented-value matching starts only at whitespace or right after a previous value's `*,` (so `4*,5*` marks both), which keeps long runs without `*` linear. Links in any page markdown render only for `http:`, `https:`, `mailto:` and `#` targets, via `OFFLINE_MARKDOWN_COMPONENTS`. Records need no plugin: `strong` inside `.scenario-example` is styled blue.

`CONFIG:` `index.css` colours, using theme variables already in the bundle:

| Selector | Property |
|---|---|
| `.scenario-example strong` | `color: var(--color-text-blue)` |
| `.scenario-example ol > li::marker` | `color: var(--color-text-purple); font-weight: 700` |
| result span | `color: var(--color-text-green); font-weight: 700` |
| rejection span | `color: var(--color-text-red)` |
| invented span | `color: var(--color-text-secondary); font-style: italic` |
| gap span | `color: var(--color-text-orange)`, `background: color-mix(in srgb, var(--color-background-yellow) 45%, transparent)`, underline |
| before pane | `background: var(--color-background-muted)` |
| after pane | `background: color-mix(in srgb, var(--color-background-green) 35%, transparent)` |

### Table changes (page)

Back-link: [6.1-6.2](logic.md#6-the-review-page-shows-examples-in-the-focus-dialog).

- `id` column: when `s.example`, a `Token size="sm"` labelled `Example`. When `openAsks[s.id]` is non-empty, also a `Token size="sm" color="yellow"` labelled `Open question`, with the first question as its description. Existing tokens (Reopened, Claude-added, Requested, changed label) stay.
- The scenario ID text becomes a `Button` (link style) that opens the dialog in browse mode at that scenario. This is the keyboard path.
- `BehaviorGroup` adds a `TablePlugin` whose `transformBodyRow` sets `onClick` on each row (pattern: `board-view.tsx` `dragPlugin`). The handler ignores clicks whose target is inside `button, a, input, textarea, select, label, [role="radiogroup"], [role="switch"], [role="checkbox"]`, and ignores clicks while text is selected. It composes with `changedRowsPlugin`, which keeps working.
- No example content ever renders in the table.

## Data models / schemas

Back-link: [Where an example lives](logic.md#where-an-example-lives).

`SCHEMA:` `logic.json` v2 scenario, new optional key (no `schemaVersion` change):

| Key | Type | Rule |
|---|---|---|
| `example` | object, optional | Exactly `before`, `steps`, `after`. Hashed with the scenario. |
| `example.before` | string, non-empty | Markdown with marks. |
| `example.steps` | string[], length ≥ 1, each non-empty | One step per entry; the renderer numbers them. |
| `example.after` | string, non-empty | Markdown with marks. |

`SCHEMA:` `spec-types.ts`:

| Type | Shape |
|---|---|
| `ScenarioExample` | `{ before: Markdown; steps: string[]; after: Markdown }` |
| `Scenario` | adds `example?: ScenarioExample` |
| `LogicSpecPayload` | adds `openAsks: Record<ScenarioId, string[]>` |

`ReviewState`, `DecisionRecord` and `Export` do not change. The automatic outcome update is an ordinary `scenarioUpdates` entry.

## Shared conventions file

Back-links: [Conventions](logic.md#conventions), [What an example is](logic.md#what-an-example-is), [5](logic.md#5-an-example-changes-with-its-scenario), [8](logic.md#8-later-stages-take-their-contract-from-the-then).

`skills/writing-specs/scenario-examples.md` must contain, each once:
- What an example is (the three parts) and that the Then is the contract.
- When to write one: wherever there's data to show, written in the same pass as the scenario. Request/response scenarios keep the three labels.
- The conventions list from the logic spec, verbatim in substance.
- The exact mark syntax: `**bold**` for records; `✓`/`✗` mark the phrase up to the next `;` or line end; a trailing `*` on an invented value; `[ASK: <question>]`, capitalised, colon and space; `(a)`/`(b)` branches. **No single-asterisk emphasis inside an example**, because a trailing `*` must never pair with an opener.
- Where it lives: the `logic.json` keys, and the markdown sub-bullet layout with the two-trailing-space line-break rule.
- The sync rule: rewrite the example in the same edit as its scenario, amendments included.
- The self-review example check: every example agrees with its Then, and each open `[ASK]` is a question the design didn't already answer.
- The downstream rule: requirements derive from the scenario, and a `*` value is never an expected value. Nothing about turning examples into tests.

## DO-NOT-CHANGE fences

| Region | Why |
|---|---|
| `RENDER_OUTPUT_FIELDS_V2` in `render_spec.py`: never add `example` | Approval covers the example, so it must be hashed ([Key decisions](logic.md#key-decisions--rationale)). |
| `canonical_json`, `item_hashes`, `stage1_item_hashes`, `render_id` | Specs without examples must keep their hashes, pins and `renderId` ([9](logic.md#9-specs-without-examples-are-unchanged)). An absent key already hashes identically. |
| `render_markdown_v2` output for scenarios without `example`, and all of `render_markdown` (v1) | `logic.md` must stay byte-identical for existing specs; the goldens enforce it. |
| `validate_logic` (v1) and every v1 command path | v1 behaves exactly as today ([9.2](logic.md#9-specs-without-examples-are-unchanged)). |
| Existing gate names and messages in `stage1_gate_failures` / `stage2_gate_failures` | Tests and the rubric match on them. |
| `isScenarioUndecided`, `gateList`, `carryOver`, `changedSinceReviewIds` in `review-state.ts` | The undecided queue and decision clearing already do the right thing: an example edit changes the hash and `carryOver` clears the decision. Changing them would ripple through every view. |
| `SpecMarkdown`'s `_` → `_​` replacement in `views/shared.tsx` | Stops underscores in prose becoming emphasis everywhere on the page. |
| `schemaVersion` stays `2` | The new key is optional and additive. |
| Headings in `skills/writing-specs/logic-spec.md` | `tests/test_writing_specs_skill.py` `test_brainstorming_section_names_match_logic_spec` matches brainstorming's references against them. |
| `skills/writing-specs/SKILL.md` "Which document, which rubric" table | It lists one rubric per document; the conventions file is a reference the rubrics link to, not a rubric. |

## Always / Ask / Never

**Always**
- Keep `render_spec.py` stdlib-only and Python 3.9 compatible.
- Decide whether a gap is open in `scenario_open_asks` only; the page reads `openAsks`.
- Rebuild `review-template.html` after any `app/src` change: `pnpm install --frozen-lockfile && pnpm run build && pnpm run check` from `skills/writing-specs/interactive/app/`.
- Keep goldens byte-identical; a golden diff is a regression, never a fixture update.

**Ask**
- Before adding any key to `ReviewState`, `DecisionRecord` or `Export`.
- Before changing an existing gate's name or message.
- If an Astryx component cannot do something this spec assumes (row `onClick` via `htmlProps`, `MarkdownInlinePlugin` seeing a trailing `*` as plain text, `Dialog` `width` 1040).

**Never**
- Add `example` to `RENDER_OUTPUT_FIELDS_V2`.
- Escape or rewrite mark characters in `logic.md`.
- Show example content in table rows.
- Add a JS test framework or any new npm dependency.

## Cross-cutting

- **Migration:** none. Existing v1 and v2 specs validate and render unchanged; `review.html` changes only because the template is rebuilt, and it is never committed.
- **Rollback:** revert the branch. `logic.json` files with `example` would then still validate under the old renderer (unknown keys are ignored) but would hash differently from a pin taken with examples, which is acceptable because no spec carries examples before this ships.
- **Security:** marks and markdown render through Astryx `Markdown` with the existing offline component overrides (images omitted). No raw HTML is injected; inline plugins return React elements.
- **Observability:** not applicable (local CLI and offline page).

## Testing strategy

Back-links: [Key decisions](logic.md#key-decisions--rationale) (success criteria), [9](logic.md#9-specs-without-examples-are-unchanged).

**Goldens, first task, before any renderer change:**
- `tests/fixtures/interactive/goldens/v2-stage1.logic.md` and `v2-stage2.logic.md`, rendered from `tests/fixtures/interactive/v2/stage1/logic.json` and `v2/stage2/logic.json` at `RUN_BASE`.
- A test renders each fixture into `tmp_path` and asserts byte equality with its golden, and asserts that rendering a copy of `docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/logic.json` (v1) reproduces the committed `docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/logic.md` byte for byte (verified true at `RUN_BASE`).

**Example fixture:** `tests/fixtures/interactive/v2/examples/logic.json`, stage 1, built from the exploration's three examples (compounding discounts; the limited discount with its `[ASK]`; the two-branch definition edit with `(a)`/`(b)` and a `✗`), plus one scenario with no example. Exports beside it in `exports/`: a signed export approving the open-`[ASK]` scenario; a signed export dropping it and approving the rest; a signed export approving the compounding scenario with an alternative outcome.

**Python tests** (`tests/test_interactive_logic_spec.py`, or a new `tests/test_scenario_examples.py` using the same `make_v2_spec`-style fixture copying):
- `validate` accepts the example fixture.
- `validate` rejects each malformed shape: missing part, empty `steps`, empty step, non-string part, unknown key inside `example`. Each yields an error at the expected pointer.
- `validate` rejects `[ask: …]`, `[ASK]` and `[ASK:x]` (no space) with the malformed-marker message, in stage 1.
- A stage-2 spec with an open gap on a non-dropped scenario fails with `open [ASK] after stage-1 sign-off`; the same on a dropped scenario passes.
- `item_hashes`: adding an `example` changes the scenario's hash; editing one step changes it; a scenario without `example` hashes the same as at `RUN_BASE` (the goldens' fixtures still validate their pins).
- `render`: the exact example lines, including a multi-line `before` and a multi-line step (hard breaks and continuation indent), and placement between alternatives and explanation.
- `fold`: the open-`[ASK]` export exits 4 with `gate examples: open [ASK] in <id>` on stderr; the alternative-outcome export exits 4 with the outcome message; the drop export folds, and the folded scenario keeps its `example` and pin.
- The payload embedded in `review.html` has `openAsks` with exactly the open-gap scenario.

**Page checks:** a new `app/scripts/check-examples.ts`, wired into `pnpm run check`, that imports `exampleMarkPlugins`, `approveBlockReason` and `exampleOutcomeUpdate` and asserts on fixed strings: each mark pattern matches its sample and not `**bold**`; the invented pattern matches `10%*` and `4*,` and not `**Subscription**`; each block reason fires on a minimal state; the update text round-trips with the prefix; `isPayload` rejects a payload without `openAsks` and accepts one with it. `pnpm run check` must pass, including `template-check` against the rebuilt template.

**Manual fixture review** (the logic spec's success criterion): `render_spec.py render tests/fixtures/interactive/v2/examples --open`, then confirm the tokens on rows, that clicking a row and the ID button both open browse mode, three columns with every mark coloured, Approve disabled with the right hint on the `[ASK]` scenario, and that picking an alternative on the compounding scenario writes the update and disables Approve.

**Doc tests** (`tests/test_writing_specs_skill.py`): add `scenario-examples.md` to `test_skill_files_exist`; assert both rubrics link it. The existing cross-file link and anchor test covers the new file automatically.

**Acceptance bar:** `pytest -q` green from the repo root, and `pnpm run check` green in `skills/writing-specs/interactive/app/`.

## Non-goals

Everything in the logic spec's [Scope & non-goals](logic.md#scope--non-goals), plus:
- No change to `ReviewState`, exports, or the export record.
- No JS unit-test framework; `tsx` check scripts only.
- No change to the brainstorming skill; it already defers to the rubrics.
- The `[tech-spec]` Deferred Ideas are resolved here as follows: the `*` escape rule is "no single-asterisk emphasis in examples, no escaping"; the mark patterns are the table above; near-miss `[ASK]` forms are validation errors; the automatic update wording is `EXAMPLE_OUTCOME_UPDATE_PREFIX`; the dialog width is 1040.
