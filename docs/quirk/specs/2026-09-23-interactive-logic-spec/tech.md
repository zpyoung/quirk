# Tech Spec: Interactive Logic Spec

**Status:** Authored — reviewed, fixes applied — ready for planning
**Logic spec:** [logic.md](logic.md)

## Architecture

Three units, one direction of dependency: **rubric → renderer → page template**. The rubric tells
Claude what to write and which commands to run. Claude authors and revises `logic.json` as the source.
The renderer validates it and is the only program that reads or writes it; the page is a static
asset with no filesystem access.
Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Path | Tech | State |
|---|---|---|---|
| Rubric | `skills/writing-specs/interactive-logic-spec.md` | Markdown | Create |
| Renderer CLI | `skills/writing-specs/interactive/render_spec.py` | python3 ≥3.9, **stdlib only** | Create |
| Page source | `skills/writing-specs/interactive/app/` | Vite + React 19 + TypeScript + `@astryxdesign/core` 0.6.2 + `@astryxdesign/theme-neutral` 0.6.2 + `vite-plugin-singlefile` + `elkjs` | Create (generalized from the Orca reference app) |
| Prebuilt page | `skills/writing-specs/interactive/review-template.html` | Single-file HTML, **committed build output** | Create |
| Skill wiring | `skills/brainstorming/SKILL.md`, `skills/writing-specs/SKILL.md`, `skills/writing-specs/tech-spec.md`, `skills/executing-plans/SKILL.md` | Markdown | Modify |
| Tests | `tests/test_interactive_logic_spec.py`, `tests/fixtures/interactive/` | pytest | Create |
| Tests | `tests/test_writing_specs_skill.py` | pytest | Modify |

**Per-spec folder at runtime** (in the *user's* project, not this repo):
`logic.json` (source) · `logic.md` (generated) · `review.html` (generated) · `.gitignore`
(generated) · `<slug>-decisions-<stamp>.json` exports (untracked).

**Reference implementation (read-only):**
`/Users/zpyoung/PycharmProjects/orca/docs/quirk/specs/2026-09-23-claude-ultracode-effort/review-app/`.
It is the visual and behavioral baseline for the page. Its hardcoded content moves into
`logic.json`, its tier model is dropped, its artifact-db persistence is replaced, and its hand-placed
diagram coordinates are replaced by computed layout. What to carry over, file by file:

| Reference file | Disposition |
|---|---|
| `src/App.tsx`, `src/main.tsx`, `src/index.css` | Carry over. Tab set becomes data-conditional; `useViewerMode` (`App.tsx:34-47`) kept as is |
| `src/views/board-view.tsx`, `board-model.ts`, `call-queue.tsx`, `requirement-dialog.tsx`, `scope-out-guard.tsx` | Carry over; rewire from `Tier`/`Column` to the `Placement` model below |
| `src/views/risks-view.tsx`, `list-detail-register.tsx` | Carry over; research findings come from `logic.json` `research[]`, not `useResearchFindings` |
| `src/views/scenarios-view.tsx` | Carry over; extra scenarios come from `logic.json`, not `useExtraScenarios` |
| `src/views/coverage-view.tsx`, `impact-certainty-view.tsx`, `story-map-view.tsx` | Carry over as optional views; `story-map-view.tsx:16-17` hardcoded `JOURNEY_AREAS`/`CROSS_AREAS` move to `views.storyMap` |
| `src/views/picker-states-*.tsx/.ts` | Generalize to a `state-machine-*` view; replace `picker-states-diagram.tsx:10-55` constants (`STATES`, `ENTRIES`, `ROUTES`, `BLIND_SPOT_CHIP`) with elkjs output |
| `src/views/spec-view.tsx` | Carry over; replace the `?raw` import of `logic.md` (`spec-view.tsx:3`) with `payload.logicMarkdown` |
| `src/views/sign-off-view.tsx` | Carry over; add Download / Copy / Import and the storage warning |
| `src/review-model.ts`, `src/requirement-copy.ts` | **Delete content**; types move to `src/spec-types.ts`, data comes from the payload |
| `src/views/view-props.ts` | Carry over, but drop its `extra: Scenario[]` prop, since extra scenarios now live in `spec.scenarios` |
| `src/requirement-tokens.tsx` | Do not carry over; nothing imports it |
| `src/review-state.ts` | Keep the pure functions (`gates`, `scopeWarnings`, `activeBlindSpots`, `decisionRecord`) generalized over the payload; delete `getDb`, `useAgentItems`, `useExtraScenarios`, `useResearchFindings`, and the 700ms db debounce (`review-state.ts:277-389`) |
| `to-fragment.py` | Do not carry over. The template is a full document, not an Artifact fragment |

## Code references

### Skill wiring

Line numbers are against HEAD `be51553`.

| Anchor | Current | Change |
|---|---|---|
| `skills/brainstorming/SKILL.md:33` | Checklist step 10, "**Write logic spec** — follow **quirk:writing-specs** (its `logic-spec.md` rubric)…" | Append: ask once *markdown or interactive* (markdown default); interactive follows `interactive-logic-spec.md` |
| `skills/brainstorming/SKILL.md:34` | Step 11, "**User reviews written spec** — the rubric's review gate…" | Append: for an interactive spec, the gate is the page's sign-off |
| `skills/brainstorming/SKILL.md:335-338` | `## After the Design` paragraph naming `logic-spec.md` as owner | Add one sentence naming `interactive-logic-spec.md` as the owner when the user chose interactive |
| `skills/writing-specs/SKILL.md:19-26` | "Which document, which rubric" table, 2 rows | Add a row: `logic.json` + generated `logic.md` · `quirk:brainstorming` · user chose interactive · `interactive-logic-spec.md` |
| `skills/writing-specs/SKILL.md:34-35` | "amends the **logic spec first** — a dated entry in its Amendments log" | Name the source: `logic.json` when present (via the renderer), else `logic.md` |
| `skills/writing-specs/SKILL.md:37-51` | "Where the specs live" layout block | Add `logic.json` as the optional source sibling; `tech.md` stays a sibling of `logic.md` |
| `skills/writing-specs/tech-spec.md:76` | Feasibility escalation: "record the resolution as a dated entry in the logic spec's Amendments log" | Add: in `logic.json` when the spec is interactive |
| `skills/executing-plans/SKILL.md:45-46`, `:85-86` | "a dated `logic.md` Amendments entry" / "the logic spec's Amendments log" | Same source-aware wording |
| `skills/writing-specs/interactive-logic-spec.md` | — | New rubric; see its contract below |

The subagent-driven-development and writing-plans skills are **not** modified. They read `logic.md`,
which still exists.

### Test anchors

- `tests/test_writing_specs_skill.py` verifies that the rubric ships and its cross-file links and
  anchors resolve; it does not pin incidental prose or the spelling of routing instructions.
- `tests/test_interactive_logic_spec.py` exercises the renderer through subprocess and parsed
  outputs, including generated payload, export status, and fold behavior.

## Contracts & interfaces

### Rubric: `skills/writing-specs/interactive-logic-spec.md`

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios),
[Decisions Locked](logic.md#decisions-locked).

`CONTRACT:` The rubric must state, in this order:
1. **When to use.** The user picked interactive at brainstorming's spec step.
2. **What to write.** `logic.json` per the SCHEMA below: every section the markdown rubric requires,
   plus requirements, assumptions, blind spots and scenarios. Every requirement carries a
   `provenance`, and every plain-language field is Claude-written.
3. **The render loop.** `validate` → `render --open`. After any edit to `logic.json`, re-render.
4. **The feedback round.** When the user says they exported:
   - locate the export (`find-export`, or save a pasted Copy to the spec dir) and run `check-export`
   - answer research requests into `research[]`
   - convert scenario requests into `scenarios[]` with `requestId`
   - apply requested content changes
   - run `render --prior <export>`

   Unsigned scope decisions are **not** written into `logic.json`. They ride in the prior export.
5. **Sign-off.** On a signed export, run `fold`, then `render`, then commit `logic.json` and
   `logic.md`, then hand off to an execution skill. There is no second chat approval. Pass
   `--tech-spec-requested` when the user asked for one.
6. **UI feedback.** A change the user asks for to the page itself is a change to
   `skills/writing-specs/interactive/app/`. Rebuild `review-template.html`, then re-render.
7. **Amendments after approval.** Add an `amendments[]` entry and re-render. There is no re-review.
8. **Self-review.** The four checks from `logic-spec.md`, run against `logic.json`, plus: every
   `dependsOn`, `affects`, `sources`, `refs`, `reqs` and `resolvedBy` id resolves (`validate`
   enforces this).

It links to `logic-spec.md` for the shared section definitions rather than restating them.

### Renderer CLI: `render_spec.py`

Back-links: [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios).

`CONTRACT:`
```
render_spec.py validate     <spec-dir>
render_spec.py render       <spec-dir> [--prior <export.json>] [--open]
render_spec.py find-export  <spec-dir> [--downloads <dir>]
render_spec.py check-export <spec-dir> <export.json>
render_spec.py fold         <spec-dir> <export.json> [--tech-spec-requested]
```
`<spec-dir>` contains `logic.json`. `slug` is the spec dir's basename.

| Exit | Meaning |
|---|---|
| 0 | Success |
| 1 | Invalid input: `logic.json` or the export fails schema or id-reference checks; one `<json-pointer>: <message>` line per error on stderr |
| 2 | Usage error |
| 3 | Stale: the export's `renderId` ≠ the current `renderId`, or its `slug` does not match |
| 4 | `fold` only: the export is unsigned, or a gate re-checked in Python fails. Each failing gate is named on stderr |
| 5 | `find-export` only: no export found |

**`validate`**
- *Pre:* `logic.json` exists.
- *Post:* nothing is written.
- *Checks:*
  - the SCHEMA below: required keys, enums and types
  - ids are unique across all entity kinds
  - every cross-reference resolves
  - `conflicts` pairs name two distinct requirements

**`render`**
- *Pre:* `validate` passes (`render` runs it first and exits 1 on failure).
- *Post:* it writes `review.html`, `logic.md` and `.gitignore` in `<spec-dir>`, and prints the
  `renderId` on stdout.
- *Invariants:*
  - the template is read from `review-template.html` next to the script
  - the template contains **exactly one** payload placeholder, else exit 1
  - the output is byte-identical for identical inputs; the renderer embeds no clock or random values
- *`--prior`:* the export is embedded as `payload.priorDecisions` whether or not it is stale. The page
  applies the diff-aware carry-over.
- *`--open`:* uses `webbrowser.open` on the file URI.
- *`.gitignore`:* created, or appended to without duplicating lines, with the lines `review.html` and
  `*-decisions-*.json`.

**`find-export`**
- *Post:* prints the absolute path of the newest export whose `kind` and `slug` match.
- *Search:* `<spec-dir>` and `--downloads` (default `~/Downloads`) together; neither folder wins by
  location. An export whose `renderId` matches the current render beats any stale one. Among the
  rest, the newest wins.
- *Ordering:* "Newest" means greatest `exportedAt` inside the file, not mtime. A file that fails JSON
  parsing, or is not a decision export, is skipped silently, never fatal.
- *Pre:* `logic.json` must be valid (exit 1 otherwise), since the current render ID is needed.

**`check-export`**
- Exit 0 when the export is valid and current, 3 when stale, 1 when invalid.
- It prints `signed` or `unsigned` on stdout.

**`fold`**
- *Pre:* the export is signed and current.
- *Gates:* all six gates are re-checked in Python against the export's `state` and the current
  `logic.json`. Python is authoritative over the page's own gate display.
- *Post:* it rewrites `logic.json` (`indent=2`, key order preserved) as follows.

| Change in `logic.json` | Written from the export |
|---|---|
| Requirement `scope`, and `condition` for conditional items | the final placements |
| `reviewReason` on each requirement whose scope changed | the reviewer's move reasons |
| `ruling` and `rulingNote` on each assumption | the reviewer's rulings |
| `acceptance` on each active blind spot | the reviewer's own sentence |
| a scenario's `then` | the reviewer's outcome, when they chose a different one |
| `signoff` | `{signedAt, renderId}` |
| `status` | `"Approved"`, or `"Approved — Tech spec: requested"` with the flag |

- *After writing:* it runs `render`. It does not commit; the rubric's step 5 does.
- *Idempotence:* folding the same export twice exits 3, because the first fold changed the
  `renderId`.

**`renderId`**

`PSEUDOCODE (justified, ≤3 lines):` the canonicalization must be exact, or Python and the page's
stale check disagree.
`renderId = sha256(json.dumps(logic, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")).hexdigest()[:12]`

**`itemHashes`**

The same canonicalization over each requirement, assumption, blind spot and scenario object, with
its review-output fields removed first (`reviewReason`, `ruling`, `rulingNote`, `acceptance`). That
way a fold does not flag every item "changed since you reviewed". The key is the item id.

### Page: `review-template.html` and `app/`

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios) items 3–13,
[Decisions Locked](logic.md#decisions-locked) → Review mechanics.

- **Input.** One `<script type="application/json" id="quirk-logic-spec-payload">` element. The page
  reads `JSON.parse(el.textContent)` once at startup. When the payload is the unfilled placeholder,
  the page renders an `EmptyState` saying "open a rendered review.html", never a crash.
- **Tabs.**
  - Always: Scope board, Risks, Scenarios, Spec text, Sign-off.
  - Coverage when `coverageGaps(state).length > 0`.
  - Impact × certainty when any requirement has non-null `certainty`.
  - Story map when `views.storyMap` is present.
  - State machine when `views.stateMachine` is present.
- **Queue.** The queue is `requirements.filter(r => r.provenance === "claude")`. A queue item has no
  effective placement until `state.placements[id]` is set; nothing is preselected. Non-queue items
  start at their `logic.json` `scope`.
- **Gates.** These carry over from the reference `gates()` (`review-state.ts:198-219`), minus tiers:
  1. every queue item has a placement
  2. every assumption has a `ruling`, and every ruling other than `build-on` also has a note
  3. every active blind spot is `accepted` with a non-empty note
  4. every scenario is approved and no scenario request is pending
  5. every requirement whose effective placement ≠ its `logic.json` placement has a non-empty reason
  6. `scopeWarnings(state)` is empty
- **Signing.** Sign is enabled only when all six gates pass and `verdict === "approve"`. Any `update()`
  after `signedAt` is set clears `signedAt`.
- **Blind-spot activity.** A blind spot is active iff every id in `sources` has an in-scope
  placement, and `resolvedBy` is absent or its requirement is not unconditionally in scope.
- **Diff-aware carry-over.** On load, the starting state is whichever of `localStorage` and
  `payload.priorDecisions.state` has the later `updatedAt`. Then, for every item id where
  `seen[id] !== payload.itemHashes[id]`, that item's entries are deleted from every per-id map in
  the state, and it is flagged "changed since you reviewed". Items with no `seen` entry are new and
  are flagged the same way.
- **Persistence.**
  - Every `update()` writes `localStorage["quirk-logic-spec:" + slug]` inside try/catch. A failure
    sets `storageOk = false`.
  - When storage fails, a persistent `Banner` asks the reviewer to export before closing, and a
    `beforeunload` prompt fires if state changed since the last export.
  - The page never uses `window.claude` or any network call.
- **Export.** It builds the EXPORT SCHEMA below.
  - **Download** writes a Blob to `<slug>-decisions-<YYYYMMDDTHHMMSS>.json` in local time.
  - **Copy** uses `navigator.clipboard.writeText`. On rejection or absence it shows "Copy is blocked
    here — use Download".
  - **Import** reads a file input, rejects a wrong `kind`/`slug` with a message, and otherwise loads
    it through the same carry-over path.
- **State machine layout.** Computed by elkjs with `elk.algorithm=layered` and
  `elk.edgeRouting=ORTHOGONAL`, with edge labels as ELK label nodes so they are placed without
  collision. Rendering follows the reference diagram's visual rules: rounded orthogonal connectors,
  label backgrounds masking lines, one accent color on `focal` states, and blind-spot chips on
  their transition's label. Clicking a transition or chip opens the detail dialog. The layout is
  computed asynchronously and falls back to the transitions table while pending.
- **Theme.** Astryx `Theme` with `neutralTheme`, following `data-theme` and `prefers-color-scheme`
  as the reference does (`App.tsx:34-47`). The page has no inline styles or `className`; orange
  accents use `--color-text-orange` and `--color-background-orange` because the neutral theme's
  `--color-accent` is gray.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

The TypeScript source of truth is `app/src/spec-types.ts`. `render_spec.py` validates the same
shape by hand, with no `jsonschema` dependency. Drift between the two is caught by the fixture test
under Testing strategy. `?` marks an optional key; every other key is required.

`SCHEMA:` `logic.json`
```
LogicSpec {
  schemaVersion: 1
  title: string
  status: string
  amendments: { date: "YYYY-MM-DD", text: string }[]
  sections: {
    purpose: md, conceptualModel: md, dataFlow: md
    decisionsLocked: { area: string, decision: string }[]
    industryInsights: { finding: md, sources: string[] }[]
    scopeNonGoals: md[]
    deferredIdeas: { text: string, techSpec: boolean }[]
    glossary: { term: string, definition: string }[]
  }
  requirements: Requirement[]
  conflicts: [reqId, reqId][]
  assumptions: Assumption[]
  blindSpots: BlindSpot[]
  scenarios: Scenario[]
  research: { requestId, blindSpotId, summary: md, detail: md, answeredAt: ISO8601 }[]
  views?: { stateMachine?: StateMachine, storyMap?: StoryMap }
  signoff?: { signedAt: ISO8601, renderId: string }
}
Requirement {
  id: string                      // REQ-nn or OOS-nn
  area: string
  text: string
  summary: string
  detail: md
  scope: "in" | "out"
  condition?: "no-code" | "under-10" | "under-30"   // only when scope is "in"
  group: "min" | "i3" | "i2" | "i1"                  // Claude's group, used when in scope
  provenance: "you-chose" | "you-recommended" | "claude"
  question?: string               // required unless provenance is "claude"
  rationale?: md                  // required when provenance is "claude"
  certainty: "confirmed" | "assumed" | "unverified" | null
  dependsOn: reqId[]
  reviewReason?: string           // written by fold
}
Assumption {
  id, claim, basis
  certainty: "confirmed" | "assumed" | "unverified"
  ifWrong
  affects: reqId[]
  meaning: md
  check: md
  checkCost: string
  ruling?: "build-on" | "verify-first" | "wrong"     // written by fold
  rulingNote?: string                                 // written by fold
}
BlindSpot {
  id, title
  detail: md
  sources: reqId[]
  resolvedBy?: reqId
  acceptance?: string             // written by fold
}
Scenario {
  id, given, when, then
  alternatives: string[]
  explanation: md
  refs: reqId[]
  requestId?: string
}
StateMachine {
  states: { id, label, detail: md, focal?: boolean }[]
  entries?: { id, label }[]
  transitions: {
    id
    from: stateId | entryId
    to: stateId
    short: string
    event: md
    reqs: reqId[]
    blindSpot?: blindSpotId
  }[]
}
StoryMap {
  journey: { area: string, label: string }[]
  crossCutting: string[]
}
```

Every plain-language field is Claude-written by definition: `summary`, `detail`, `meaning`,
`check`, `explanation`, `rationale`, and `detail` on blind spots. The page labels them "Claude wrote this".
`provenance` is only about who decided a requirement, not who wrote its copy.

`SCHEMA:` embedded payload (renderer → page)
```
{ spec: LogicSpec, slug: string, renderId: string,
  itemHashes: { [itemId]: string }, logicMarkdown: string, priorDecisions: Export | null }
```
Every `<` in the serialized payload is written as `\u003c`, so no string content can close the
script element.

`CONFIG:` placeholder, exactly once in `review-template.html`:
`<script type="application/json" id="quirk-logic-spec-payload">null</script>`

`SCHEMA:` Export (page → Claude)
```
Export {
  kind: "quirk-logic-spec-decisions"
  schemaVersion: 1
  slug: string
  renderId: string
  exportedAt: ISO8601
  signed: boolean
  seen: { [itemId]: hash }        // payload.itemHashes at export time
  state: ReviewState
  record: DecisionRecord          // human-readable summary shown on Sign-off
}
ReviewState {
  placements: { [reqId]: "in" | "conditional" | "out" }
  conditions: { [reqId]: "no-code" | "under-10" | "under-30" }
  moveReasons: { [reqId]: string }
  notes: { [itemId]: string }
  assumptions: { [id]: { ruling?: "build-on" | "verify-first" | "wrong", note: string } }
  blindSpots: { [id]: { accepted: boolean, note: string } }
  scenarioOutcomes: { [id]: { choice: "spec" | "custom" | "alt-<n>", custom: string } }
  scenarioApproved: { [id]: boolean }
  scenarioRequests: { id, text, requestedAt }[]
  researchRequests: { id, blindSpotId, question, requestedAt }[]
  verdict?: "approve" | "send-back"
  verdictNote: string
  signedAt?: ISO8601
  updatedAt: ISO8601
}
```

A `placements` entry absent for a non-queue item means "as in `logic.json`". For
`scope: "in"` with a `condition`, the `logic.json` placement is `"conditional"`.

`SCHEMA:` generated `logic.md` begins with the line
`<!-- generated from logic.json by render_spec.py — do not edit -->`, then the headings of
`logic-spec.md`'s required sections, in the same order as a hand-written spec:
- `# <title>`
- `## Status & amendments`, with `**Status:**` and `**Amendments:**` lines
- `## Purpose`
- `## Conceptual model`
- `## Data flow`
- `## Behavior & scenarios`: one numbered Given/When/Then item per scenario
- `## Requirements`: tables for in scope, conditionally in scope, and out of scope
- `## Assumptions & blind spots`
- `## Decisions Locked`, grouped by `area`
- `## Industry Insights`
- `## Scope & non-goals`
- `## Deferred Ideas`, with `techSpec` items prefixed `[tech-spec]`
- `## Glossary`

These headings keep the `logic.md#…` anchors that writing-plans and tech specs link to
(`skills/writing-plans/SKILL.md:155`) working.

## DO-NOT-CHANGE fences

1. **Markdown rubric compatibility in `skills/writing-specs/logic-spec.md`:** Preserve the
   `Tech spec: requested` status marker, section headings, amendments format, and existing
   markdown approval path. The markdown rubric remains the default; it gains at most a one-line
   pointer to the interactive rubric.
2. **`skills/brainstorming/SKILL.md` stays ≤400 lines.** It is 375 today, and
   `test_body_within_line_budget` (`tests/test_brainstorming_elicitation.py:207`) caps it. Also
   preserve its literals:
   - `12. **Transition to implementation**` (the checklist stays at 12 steps; the format choice is
     part of step 10, not a new step)
   - `Essential-coverage\ncheck`
   - `Industry Insights` and `Deferred Ideas`
   - the whole adhd Step 0 / Step 1 block, which `tests/test_brainstorming_adhd_offer.py` pins
3. **Ownership remains in `skills/writing-specs/SKILL.md`.** The new rubric must not restate the
   hub's ownership paragraph.
4. **`skills/adversarial-review/scripts/adversarial-review:50` `SPEC_DESIGN_NAMES`**. Do not add
   `logic.json`. The generated `logic.md` sits beside it and already routes to the `spec-design`
   profile, and a JSON source would feed the reviewer the wrong artifact.
5. **The Orca reference app is read-only,** because it backs a published review of a different spec,
   and that repo forbids committing `docs/**`. Never edit anything under
   `/Users/zpyoung/PycharmProjects/orca/`. Never run `pnpm exec` or `npx` there. Never commit its
   `docs/**`. Copy source into `app/`; don't import from it.
6. **No stale skill name in new shipped files.** Do not introduce `writing-tech-spec` under
   `skills/`, `commands/` or `.claude-plugin/`.

## Always / Ask / Never

**Always**
- Keep `render_spec.py` stdlib-only and Python 3.9-compatible: no `match` statements and no
  `X | Y` type unions at runtime.
- Commit `review-template.html` together with any `app/` source change, rebuilt from that source.
  The rebuild check under Testing strategy enforces this.
- Keep the full suite green. The baseline is **1051 passed** at `be51553` (`python3 -m pytest -q`).
- Pin `app/package.json` dependencies to exact versions and commit `pnpm-lock.yaml`.
- Keep the payload the page's only input. The page makes no fetch, `window.claude` or file reads
  other than the Import input.

**Ask**
- If elkjs's layered layout cannot reproduce a readable Picker-states-equivalent diagram for the
  ultracode test data, stop and surface it before hand-tuning coordinates or switching layout
  libraries.
- If the built template exceeds 4 MB (elkjs adds weight), surface it before minifying or lazy-loading
  anything.
- If a gate or behavior from the reference app has no home in the SCHEMA above (for example,
  impact overrides), ask rather than extend the schema. The logic spec dropped tiers and impact
  edits on purpose.

**Never**
- Never write `logic.md` by hand for an interactive spec, and never let the rubric tell Claude to.
- Never commit `review.html` or export files anywhere. The renderer's `.gitignore` enforces this in
  user repos.
- Never fold an unsigned or stale export, even when asked to "just apply it". Re-render and have
  the user sign.
- Never add a network path, local server, or artifact hosting. These are non-goals.

## Cross-cutting

- **Security.**
  - Payload escaping (`<`) is the only injection boundary, because content is Claude-written
    and may quote HTML.
  - The page renders markdown through Astryx `Markdown` only, never `dangerouslySetInnerHTML`.
  - The Import path parses JSON and validates `kind`/`slug` before use.
- **`file://` loading.** `vite-plugin-singlefile` emits one inline `<script type="module">`. Inline
  module scripts with no imports run from `file://`, but this is verified by the browser smoke below,
  not assumed.
- **Storage.** `localStorage` on `file://` is unreliable (MDN; Safari can throw), so every access is
  in try/catch, and the export is the durable record.
- **Rollback.** The feature is additive. Reverting the commit removes the rubric and assets, and
  markdown specs are unaffected. Existing interactive specs keep a readable generated `logic.md`.
- **Observability.** None beyond CLI exit codes and stderr lines.

## Testing strategy

Back-link: [Decisions Locked](logic.md#decisions-locked) → Success criteria.

**`tests/test_interactive_logic_spec.py`** covers the renderer through subprocess and module load,
against `tests/fixtures/interactive/`. The fixtures are:
- `sample/logic.json`: small and synthetic, exercising every entity and both optional views
- invalid variants: a missing key, a bad enum, a dangling `dependsOn`, a duplicate id
- a signed export, an unsigned export, a stale export and a wrong-slug export for `sample`

It must cover:
- `validate`: exit 0 on the sample, and exit 1 with a pointer line for each invalid variant.
- `render`:
  - writes all three outputs, and the payload placeholder is replaced exactly once
  - a `</script>` in content does not close the element: the payload parses back, and no `<` is
    left inside the payload
  - `renderId` is deterministic
  - editing one requirement changes only that item's `itemHashes` entry
  - `logic.md` contains the generated-banner line and every rubric heading
  - `.gitignore` is idempotent
- `find-export`: searches both folders together, prefers the current render, orders by
  `exportedAt` over mtime, and skips unparseable files without a stderr note.
- `check-export`: returns 0 for a current export, 3 for a stale export and for a wrong-slug export,
  and 1 for a malformed export.
- `fold`:
  - applies each decision kind
  - sets the status with and without `--tech-spec-requested`
  - refuses unsigned exports (4), gate-failing exports (4, naming the gate) and stale exports (3)
  - a second fold of the same export exits 3
- A successful render demonstrates that the committed template contains one usable payload slot;
  no separate source-text assertion is needed.

**`tests/test_writing_specs_skill.py`** verifies the rubric file ships and all new relative links
and anchors resolve. Routing text is reviewed as documentation, not pinned to literal wording.

**Page checks** are run from `skills/writing-specs/interactive/app/` and are not part of pytest.

`COMMAND:` `pnpm install --frozen-lockfile && pnpm run check && pnpm run build`
- `check` runs `tsc --noEmit` plus a layout-collision check. The collision check computes the elkjs
  layout for the sample fixture's state machine and fails if any label box intersects another label
  or node box.
- The layout-check script reads `tests/fixtures/interactive/sample/logic.json`, emits its literal
  object into a temporary TypeScript source with `satisfies LogicSpec`, typechecks it, and removes
  the temporary file. Importing JSON directly widens enum strings and cannot satisfy the literal
  TypeScript union types. This is the drift guard between the TS types and Python validator.
- `build` writes `../review-template.html`. Rebuilding without source changes must preserve its
  checksum; after the file is tracked, `git diff --exit-code` can check it as well.

**Browser smoke** (manual acceptance, `playwright-cli`, which is on PATH):
1. Run `render` on `sample`.
2. Open `file://…/review.html`.
3. Confirm each tab renders, and the optional tabs appear only for data that is present.
4. Place a queue item, then confirm the storage warning appears when `localStorage` is stubbed to
   throw.
5. Download an export, then confirm `check-export` accepts it.
6. Screenshot each tab in light and dark mode.

**Success criteria from the logic spec (manual):**
1. Convert the ultracode spec to `logic.json` in a scratch dir outside both repos. Its sources are
   the reference `logic.md`, `requirements.json`, `review-model.ts`, `requirement-copy.ts` and
   `picker-states-model.ts`. Render it, then run the browser smoke, including the state machine.
   This content is **never committed to quirk**.
2. Run one end-to-end brainstorm on a toy topic: choose interactive, review, export unsigned, revise,
   sign, `fold`, then confirm `quirk:writing-plans` reads the generated `logic.md`.

## Non-goals

These carry over from [Scope & non-goals](logic.md#scope--non-goals):
- Artifact hosting
- a local server
- review-behavior signals
- delivery tiers
- per-spec page code
- an interactive `tech.md`
- converting existing markdown specs
- migrating the Orca app

In addition, this tech spec does not cover:
- a JSON Schema file or third-party validator
- vitest or other JS unit tests beyond typecheck and the layout check
- publishing the template anywhere but this repo
- CI for the `app/` build
