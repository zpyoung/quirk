# Tech Spec: Interactive Logic Spec v2

**Status:** Authored — reviewed, fixes applied — ready for planning
**Logic spec:** [logic.md](logic.md)

## Architecture

The three units and the direction of dependency are unchanged from v1: **rubric → renderer → page
template**. v2 changes what each unit understands. The renderer reads both `schemaVersion` 1 and 2,
but only v2 gets page review. The page understands only v2 and switches its tab set on the spec's
`stage`.
Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Path | Tech | State |
|---|---|---|---|
| Rubric | `skills/writing-specs/interactive-logic-spec.md` | Markdown | Rewrite for v2 |
| Renderer CLI | `skills/writing-specs/interactive/render_spec.py` | python3 ≥3.9, **stdlib only** | Modify: v2 schema, stages, `reapprove`, v1 read-only |
| Page source | `skills/writing-specs/interactive/app/src/` | Vite 8 + React 19 + TS 6 + `@astryxdesign/core` 0.6.2 + elkjs | Modify: v2 types, state, gates, views |
| Page checks | `skills/writing-specs/interactive/app/scripts/`, `app/package.json` | tsx | Add a template-freshness check |
| Prebuilt page | `skills/writing-specs/interactive/review-template.html` | Single-file HTML, committed build output | Rebuild |
| Skill wiring | `skills/writing-specs/SKILL.md`, `skills/brainstorming/SKILL.md`, `README.md` | Markdown | Modify |
| Tests | `tests/test_interactive_logic_spec.py`, `tests/fixtures/interactive/` | pytest | Modify and add v2 fixtures |

A v2 spec moves through these states, all recorded in `logic.json`:

| `stage` | `status` | Holds | Written by |
|---|---|---|---|
| 1 | `Draft` | behaviors, scenarios, constraints, assumptions, blind spots, research; `requirements: []` | Claude |
| 2 | `Stage 1 approved` | the above, locked by `stage1Pin`, plus derived `requirements` | the stage-1 `fold`, then Claude |
| 2 | `Approved` / `Approved — Tech spec: requested` | the above plus `signoff` | the stage-2 `fold` |

## Code references

Line numbers are against HEAD `21c9220`.

### Renderer (`skills/writing-specs/interactive/render_spec.py`)

| Anchor | Current | Change |
|---|---|---|
| `:19-29` constants | `RENDER_OUTPUT_FIELDS`, `PLACEMENTS`, `RULINGS`, `SCENARIO_CHOICES`, … | Add the v2 constants from [Data models](#data-models--schemas). Extend `RENDER_OUTPUT_FIELDS` with v2's fold- and Claude-written marker fields |
| `Validator.exact_version` `:124-128` | Hard-codes `value != 1` | Take the allowed versions as an argument. `logic.json` accepts `{1, 2}`; an export accepts `{2}` only |
| `item_hashes` `:155-161` | Hashes requirements, assumptions, blindSpots, scenarios | For v2, also hash `behaviors` and `constraints`. The key set is the item kinds in the logic |
| `validate_logic` `:204-581` | v1 schema and cross-references | Keep it unchanged for v1. Add `validate_logic_v2` and dispatch on `schemaVersion` |
| `validate_export_shape` `:584-768` | v1 export shape | Replace with the v2 export shape. v1 exports are never accepted again, because v1 has no page review |
| `logic_reference_errors` `:771-825` | Checks v1 state ids | Rework for v2 state maps |
| `load_logic` `:845` | Validates and returns `(logic, renderId)` | Dispatch validation on version. Print v2 warnings to stderr |
| `render_markdown` `:886-1010` | v1 `logic.md` | Keep it unchanged for v1. Add `render_markdown_v2` |
| `prepare_render_files` `:1057-1079`, `render_files` `:1082-1092` | Always writes `review.html` | For v1, write only `logic.md` and `.gitignore` |
| `command_render` `:1108-1130` | `--prior` and `--open` | For v1, refuse `--prior` and `--open` with exit 6 |
| `command_check_export` `:1145`, `command_find_export` `:1190`, `command_fold` `:1330` | v1 flow | For v1, refuse with exit 6. For v2, use the stage-aware flow |
| `scope_warnings` `:1202`, `active_blind_spots` `:1217`, `gate_failures` `:1232`, `apply_fold` `:1284` | v1 gates and fold | Add stage-1 and stage-2 equivalents. Keep the v1 versions only as long as something still calls them; delete them otherwise |
| `build_parser` `:1372-1391` | Five subcommands | Add `reapprove <spec-dir> <export>` |

### Page (`skills/writing-specs/interactive/app/src/`)

| Anchor | Current | Change |
|---|---|---|
| `spec-types.ts:1-245` | v1 `LogicSpec`, `ReviewState`, `Export`, `DecisionRecord` | Replace with the v2 shapes in [Data models](#data-models--schemas). The page is v2-only |
| `review-state.ts:17` `ViewId` | Nine view ids | Add `'constraints'` |
| `review-state.ts:46` `emptyState` | v1 maps | v2 maps with `stage` |
| `review-state.ts:71-154` `isReviewState` / `isDecisionExport` / `isLogicSpec` / `isPayload` | `schemaVersion === 1` | Check for v2 and the `stage` field |
| `review-state.ts:195-283` `itemIds` / `changedItemIds` / `carryOver` | v1 item kinds | Add behaviors and constraints. The changed set also includes requirements that are [withdrawn or flagged](#derived-requirement-status) |
| `review-state.ts:302-324` `bootstrap` | Local vs prior | Ignore any snapshot or prior whose `state.stage` differs from `spec.stage` |
| `review-state.ts:326-432` placement helpers, `scopeWarnings`, `activeBlindSpots`, `gateList` | v1 gates | Add stage-aware gates matching the Python ids |
| `review-state.ts:434` `decisionRecord`, `:490` `coverageGaps` | v1 | Build a v2 record. Coverage becomes the trace matrix |
| `App.tsx:113-126` tab `useMemo` | Always `board, risks, scenarios` | Tabs depend on the stage ([contract](#page-tabs-and-stage-indicator)). Add the stage indicator to the header at `App.tsx:241-259` |
| `App.tsx:147-160` `createExport` | `schemaVersion: 1` | Set `schemaVersion: 2` and `stage` |
| `views/scenarios-view.tsx` | Two tables, awaiting approval and approved, not grouped by behavior | Group by behavior. Add the Claude-added preselection token, the extra-reason flag, and drop-with-reason. Read-only in stage 2 except for reopened scenarios |
| `views/constraints-view.tsx` | — | **Create.** Approve, rewrite, or reject each constraint, one at a time |
| `views/risks-view.tsx` | `sources` and `resolvedBy` point at requirements | Point them at scenarios and constraints. Read-only in stage 2 |
| `views/board-view.tsx`, `views/board-model.ts`, `views/requirement-dialog.tsx` | v1 queue and placements | Remove the Claude queue from the board. Placements come pre-filled. The dialog shows `derivedFrom` sources inline and the dispute control |
| `views/call-queue.tsx` | The v1 Claude-requirement queue | **Delete.** Requirements no longer carry provenance |
| `views/coverage-view.tsx` | A gap list | The trace matrix |
| `views/sign-off-view.tsx` | Six v1 gates | Stage-aware gates. The heading names the stage being signed |
| `views/shared.tsx:60-61` `ProvenanceToken` | Labels `claude` | Reuse it for scenarios and constraints. Add a "preselected — confirm" variant |
| `scripts/check-layout.ts:6` | Reads `tests/fixtures/interactive/sample/logic.json` | Read `tests/fixtures/interactive/v2/stage2/logic.json` |
| `scripts/check-template.ts` | — | **Create** ([REQ-34](logic.md#in-scope)) |
| `package.json:6-12` scripts | `check = typecheck && layout-check` | Add `template-check` and include it in `check` |

### Skill wiring and tests

| Anchor | Change |
|---|---|
| `skills/writing-specs/interactive-logic-spec.md` (all, 96 lines) | Rewrite for v2 ([contract](#rubric-contract)) |
| `skills/writing-specs/SKILL.md:18`, `:27` | The interactive pipeline line becomes `brainstorming → logic.json stage 1 → signed stage-1 fold → derivation → stage 2 → signed fold → generated logic.md` |
| `skills/brainstorming/SKILL.md:34` | For an interactive spec, the gate is the page's **final (stage-2)** sign-off |
| `README.md:80-83` | Change the contributor chain to `pnpm install --frozen-lockfile && pnpm run build && pnpm run check`. This deliberately puts build before check, because `template-check` compares against the freshly built template |
| `tests/test_interactive_logic_spec.py` | Keep the v1 validate and render tests. Convert every v1 page-review test (check-export, fold, `--prior`, find-export) into a v2 test, and add a v1-refusal test |

## Contracts & interfaces

### Renderer CLI

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios), [Decisions Locked → Format](logic.md#format).

`CONTRACT:` Exit codes are v1's (0 ok, 1 invalid input, 2 usage, 3 stale or wrong slug, 4 unsigned or
failed gate, 5 no export found), plus **6: read-only v1 spec**. The exit-6 stderr line is
`read-only v1 spec: page review, check-export, reapprove, and fold are refused; amend logic.json and re-render`.

| Command | v1 `logic.json` | v2 `logic.json` |
|---|---|---|
| `validate <dir>` | As today | Schema, references, lock ([REQ-16](logic.md#in-scope)), and warnings. Exit 0 or 1 |
| `render <dir> [--prior E] [--open]` | Writes `logic.md` and `.gitignore` only. `--prior` or `--open` → exit 6 before writing | Writes `review.html`, `logic.md`, `.gitignore`. Prints the renderId |
| `find-export <dir>` | Exit 6 | As v1, but a candidate must be a v2 export whose `stage` matches `logic.stage` |
| `check-export <dir> <E>` | Exit 6 | Prints `signed` or `unsigned`. Exit 3 when stale **or** when `export.stage != logic.stage` |
| `fold <dir> <E> [--tech-spec-requested]` | Exit 6 | Stage 1 → [stage-1 fold](#fold-and-reapprove). Stage 2 → [final fold](#fold-and-reapprove) |
| `reapprove <dir> <E>` | Exit 6 | Stage 2 only ([contract](#fold-and-reapprove)) |

`CONTRACT:` **Warnings.** `validate` and `render` print one stderr line per behavior with more than
three scenarios and still exit 0:
`warning: behavior <id> has <n> scenarios; extras carry reasons`. This is [REQ-07](logic.md#in-scope).
An `extraReason` that is missing on the fourth or a later scenario of a behavior, or present on
one of the first three, is an **error**. "Fourth" means array order among that behavior's
scenarios.

### Validation invariants (v2)

Back-links: [REQ-06, REQ-07, REQ-10, REQ-12, REQ-13, REQ-16, REQ-18, REQ-19](logic.md#in-scope), [Decisions Locked → Stage 1](logic.md#stage-1).

- IDs are unique **across all item kinds**: behaviors, scenarios, constraints, requirements,
  assumptions, and blind spots. The IDs key the single `itemHashes` map.
- `scenario.behavior` resolves to a behavior, and every behavior has at least one scenario.
- `provenance == "claude"` requires `rationale`; any other provenance requires `question`.
  The same rule applies to scenarios and constraints.
- `assumption.affects[]` and `blindSpot.sources[]` resolve to scenario or constraint ids.
  `blindSpot.resolvedBy` resolves to one scenario or constraint id.
- **In stage 1**, all of these are empty or absent: `requirements`, `conflicts`, `views`,
  `stage1Pin`, `signoff`. So are the fold-written and Claude-written markers: `dropReason`,
  `reopened`, `reapprovedHash`, constraint `ruling`/`originalText`/`rejectReason`, assumption
  `ruling`, and blind-spot `acceptance`.
- **In stage 2**, the following hold:
  - `stage1Pin` is present.
  - Every constraint has a `ruling`.
  - Every requirement has a non-empty `derivedFrom`. Each entry names a scenario without
    `dropReason`, or a constraint whose `ruling` is `approved` or `rewritten`
    ([REQ-18, REQ-19](logic.md#in-scope)).
  - `dependsOn`, `conflicts`, and `views.*.reqs` resolve to requirement ids.
- **The stage-1 lock (stage 2).** Take the set of ids across behaviors, scenarios, constraints,
  assumptions, and blind spots. It must equal the key set of `stage1Pin.itemHashes`. For each id,
  the current item hash must equal the pinned hash, with two exceptions:
  - a scenario with `reopened`;
  - a scenario whose `reapprovedHash` equals its current hash.

  A violation is reported at `/stage1Pin/itemHashes/<id>` with
  `stage-1 item changed after sign-off`.
- `reopened` and `reapprovedHash` are never both present on one scenario.

### Derived-requirement status

Back-links: [REQ-26, REQ-33](logic.md#in-scope), [Rework](logic.md#rework).

`CONTRACT:` This status is computed, never stored. Python and TS implement it identically.
- **withdrawn**: every `derivedFrom` id is a scenario with `reopened`.
- **flagged**: some `derivedFrom` ids are reopened scenarios, but not all.
- **active**: no `derivedFrom` id is a reopened scenario.

The effects:
- Withdrawn requirements are excluded from the board, the gates, and trace coverage. The page
  lists them under "Withdrawn pending re-derivation".
- The page adds withdrawn and flagged ids to `changedIds`. `carryOver` therefore drops their
  placement, move reason, note, and dispute, and they show `ChangedToken`.

### Gates

Back-links: [REQ-14, REQ-22, REQ-23](logic.md#in-scope). The Python gates are authoritative for
`fold`. The TS `gateList` uses the same ids and meanings as done/total counts. The duplication is
deliberate, as in v1; a shared engine is a non-goal here.

| Stage | Gate id | Passes when |
|---|---|---|
| 1 | `scenarios` | Every scenario is either approved (`scenarioApproved[id]`) or dropped with a non-blank `scenarioDrops[id]`, and no `scenarioRequests` entry lacks a scenario with that `requestId` |
| 1 | `constraints` | Every constraint has a `constraintRulings[id]`. `rewrite` needs non-blank `text`; `reject` needs non-blank `reason` |
| 1 | `assumptions` | Same as v1 |
| 1 | `blind-spots` | Every *active* blind spot is accepted with a non-blank note. A blind spot is active unless its `resolvedBy` is a scenario approved and not dropped in state, or a constraint ruled `approve` or `rewrite` in state |
| 2 | `derivation` | Every approved stage-1 item is named by at least one non-withdrawn requirement's `derivedFrom`. Approved means a scenario without `dropReason`, or a constraint ruled `approved` or `rewritten` |
| 2 | `move-reasons` | Same as v1 |
| 2 | `scope-warnings` | Same as v1, over non-withdrawn requirements |
| 2 | `disputes` | `state.disputes` is empty, and no scenario has `reopened` |

There is no separate queue gate. A Claude-added scenario or constraint counts as decided only
through an explicit state entry, which is the state entry the `scenarios` and `constraints` gates
already require ([REQ-10](logic.md#in-scope)).

### Fold and reapprove

Back-links: [Hand-off](logic.md#hand-off), [Rework](logic.md#rework), [REQ-15, REQ-16, REQ-27, REQ-28](logic.md#in-scope).

`CONTRACT:` The checks run in v1's order: load → export shape → stale or stage mismatch (3) →
references (1) → unsigned (4) → gates (4, naming the gate) → apply → prepare the template →
write atomically.

**Stage-1 fold** (`logic.stage == 1`) applies the decisions and sets the stage:
- Scenarios:
  - `then` from the outcome, using v1's `apply_fold` rules at `:1316-1324`;
  - `dropReason` from `scenarioDrops`.
- Constraints:
  - `approve` → `ruling: "approved"`;
  - `rewrite` → `ruling: "rewritten"`, `originalText` set to the old text, and `text` set to the
    reviewer's text;
  - `reject` → `ruling: "rejected"` and `rejectReason`.
- Assumption `ruling` and `rulingNote`, as v1.
- Blind-spot `acceptance` for active blind spots only.
- Then:
  - `stage = 2`;
  - `status = "Stage 1 approved"`;
  - `stage1Pin = {signedAt: state.signedAt, renderId: export.renderId, itemHashes}`, where
    `itemHashes` is taken from `item_hashes` over the **post-fold** logic, restricted to the
    stage-1 kinds.

It does not write `signoff`. `--tech-spec-requested` at stage 1 is a usage error (exit 2) with
the message `pass --tech-spec-requested at the final fold`.

**Final fold** (`logic.stage == 2`):
- Applies requirement placement, condition, and `reviewReason` as v1 does (`:1286-1306`).
- For each scenario with `reapprovedHash`, sets `stage1Pin.itemHashes[id] = reapprovedHash` and
  deletes the field.
- Sets `signoff` and `status` as v1 does.

**`reapprove <dir> <E>`**, for stage 2 only:
- Requires a current export (exit 3 otherwise) that is valid in shape and references. It may be
  unsigned.
- For every scenario with `reopened` where `state.scenarioApproved[id] === true` and
  `export.seen[id]` equals the scenario's current hash: deletes `reopened`, sets
  `reapprovedHash` to the current hash, and prints the id.
- Exits 4 with `nothing to re-approve` when no scenario qualifies.
- Writes `logic.json` and re-renders `logic.md` and `review.html` atomically.

This is the only command that applies a decision from an unsigned export. The lock's
`reapprovedHash` exception makes it safe.

`CONTRACT:` Processing a stage-2 unsigned export (the rubric's instructions to Claude, not code):
- A `derivation` dispute: Claude rewrites that requirement.
- A `scenario` dispute against target `SC-x`: Claude revises `SC-x` and sets
  `reopened = {requirementId, reason, raisedAt}` from the dispute.
- An export in which a reopened scenario is approved: Claude runs `reapprove`, then re-derives
  every requirement whose `derivedFrom` names that scenario.
- Then `render --prior`.

### Page tabs and stage indicator

Back-links: [REQ-17, REQ-24](logic.md#in-scope), [Decisions Locked → Hand-off](logic.md#hand-off).

`CONTRACT:`
- **Stage 1 tabs:** `scenarios` ("Behaviors & scenarios"), `constraints`, `risks`, `spec`,
  `sign-off`. The default is `scenarios`.
- **Stage 2 tabs:** `board`, `coverage` (always shown), then `heatmap`, `story-map`, and `states`
  under v1's data conditions, then `scenarios`, `constraints`, `risks`, `spec`, `sign-off`. The
  default is `board`.
- The header shows `Stage 1 of 2 — what should happen` or `Stage 2 of 2 — what to build`.
- In stage 2, the stage-1 tabs render read-only: no inputs, except the approve control on
  reopened scenarios.
- The optional views appear only in stage 2.

`CONTRACT:` **Preselection** ([REQ-10](logic.md#in-scope)).
- A scenario or constraint with `provenance: "claude"` shows Claude's pick as the selected value:
  the `spec` outcome for a scenario, `approve` for a constraint.
- It carries `ProvenanceToken` plus a "preselected — confirm" marker until a state entry exists.
- Confirming Claude's pick writes the same state entry an explicit choice would.
- The marker never disappears without a state write.

`CONTRACT:` **Disputes** (stage 2, requirement dialog).
- The dialog shows each `derivedFrom` source inline:
  - for a scenario, its behavior rule and Given / When / Then;
  - for a constraint, its kind and text.
- It offers **Dispute** with `kind` (`derivation` | `scenario`) and a required reason. `scenario`
  also requires a `target` chosen from the requirement's `derivedFrom` scenario ids.
- Saving writes `state.disputes[requirementId]`, and withdrawing a dispute deletes it.
- Moving a requirement out of scope keeps v1's dependents guard (`scope-out-guard.tsx`).

`CONTRACT:` **Trace matrix** (`coverage` tab).
- One row per approved stage-1 item, with its id, kind, and one-line text, and the ids of the
  non-withdrawn requirements derived from it, each linking to its board dialog.
- The status is `covered` or `gap`.
- Dropped scenarios and rejected constraints appear in a separate "Not derived (non-goals)" list,
  with their reasons.

### Template freshness check

Back-link: [REQ-34](logic.md#in-scope), [BS-04](logic.md#blind-spots).

`CONTRACT:` `scripts/check-template.ts`:
- builds the page with Vite's config into a fresh temporary directory, overriding only
  `build.outDir` and `emptyOutDir`;
- compares the produced `review-template.html` byte-for-byte with `../review-template.html`;
- deletes the temporary directory;
- on a mismatch, exits 1 with `review-template.html is stale; run pnpm run build`; otherwise
  exits 0.

It never writes `../review-template.html`.

`CONFIG:` `package.json` scripts: `"template-check": "tsx scripts/check-template.ts"`, `"check": "pnpm run typecheck && pnpm run layout-check && pnpm run template-check"`.

### Rubric contract

Back-link: [REQ-31](logic.md#in-scope).

`CONTRACT:` `interactive-logic-spec.md` states, in this order:
1. When to use: unchanged in substance.
2. What to write in stage 1:
   - behaviors with key examples, three per behavior before an `extraReason` is needed;
   - constraints of the four kinds, plus `other`;
   - provenance with the preselected queue;
   - `requirements: []` and `schemaVersion: 2`.
3. The render loop, with exit 6 and warnings.
4. Stage-1 feedback rounds: v1's unsigned-export steps, including drops and constraint rewrites
   carried in the export.
5. Stage-1 sign-off and fold.
6. Derivation:
   - `derivedFrom` rules;
   - non-goal constraints derive an out-of-scope requirement;
   - pre-filled group and placement;
   - no provenance on requirements.
7. Stage-2 feedback rounds: disputes, `reopened`, `reapprove`, and re-derivation.
8. Final sign-off and fold. This is the approval; hand off to execution.
9. UI feedback, with the new `build && check` order.
10. Amendments after approval: unchanged.
11. v1 specs are read-only.
12. Self-review.

The rubric links to this tech spec's [Data models](#data-models--schemas) for the shape.

## Data models / schemas

Back-links: [Conceptual model](logic.md#conceptual-model), [Glossary](logic.md#glossary).

`SCHEMA:` v2 `logic.json`. Fields marked † are written only by `fold` or `reapprove`; ‡ are written
by Claude while processing a dispute. Both kinds are excluded from item hashes.

```ts
type LogicSpecV2 = {
  schemaVersion: 2
  stage: 1 | 2
  title: string
  status: string                       // "Draft" | "Stage 1 approved" | "Approved" | "Approved — Tech spec: requested"
  amendments: { date: string; text: string }[]   // as v1
  sections: LogicSections                         // as v1
  behaviors: { id: string; rule: string; detail?: string }[]
  scenarios: {
    id: string; behavior: string
    given: string; when: string; then: string; alternatives: string[]; explanation: string
    provenance: Provenance; question?: string; rationale?: string
    extraReason?: string; requestId?: string
    dropReason?: string                                        // †
    reopened?: { requirementId: string; reason: string; raisedAt: string }  // ‡
    reapprovedHash?: string                                    // †
  }[]
  constraints: {
    id: string; area: string
    kind: 'placement' | 'verification' | 'naming' | 'non-goal' | 'other'
    text: string
    provenance: Provenance; question?: string; rationale?: string; requestId?: string
    ruling?: 'approved' | 'rewritten' | 'rejected'             // †
    originalText?: string; rejectReason?: string               // †
  }[]
  assumptions: Assumption[]          // as v1; affects → scenario/constraint ids
  blindSpots: BlindSpot[]            // as v1; sources/resolvedBy → scenario/constraint ids
  research: ResearchFinding[]        // as v1
  requirements: {
    id: string; area: string; text: string; summary: string; detail: string
    scope: 'in' | 'out'; condition?: ScopeCondition; group: RequirementGroup
    certainty: Certainty | null; dependsOn: string[]; derivedFrom: string[]
    reviewReason?: string                                      // †
  }[]                                // no provenance / question / rationale
  conflicts: [string, string][]      // requirement ids
  views?: { stateMachine?: StateMachine; storyMap?: StoryMap }   // stage 2 only
  stage1Pin?: { signedAt: string; renderId: string; itemHashes: Record<string, string> }  // †
  signoff?: { signedAt: string; renderId: string }                                       // †
}
```

`SCHEMA:` `RENDER_OUTPUT_FIELDS` for v2 = v1's `{reviewReason, ruling, rulingNote, acceptance}` ∪
`{dropReason, reopened, reapprovedHash, originalText, rejectReason}`. A rewrite changes `text`,
which is hashed. The pin is taken after the fold, so it records the rewritten text.

`SCHEMA:` v2 review state and export (TS `ReviewState` / `Export`, Python `validate_export_shape`).

```ts
type ReviewStateV2 = {
  stage: 1 | 2
  scenarioOutcomes: Record<string, { choice: 'spec' | 'custom' | `alt-${number}`; custom: string }>
  scenarioApproved: Record<string, boolean>
  scenarioDrops: Record<string, string>                        // reason
  scenarioRequests: { id: string; behavior: string; text: string; requestedAt: string }[]
  constraintRulings: Record<string, { ruling: 'approve' | 'rewrite' | 'reject'; text: string; reason: string }>
  assumptions: Record<string, { ruling?: AssumptionRuling; note: string }>
  blindSpots: Record<string, { accepted: boolean; note: string }>
  researchRequests: { id: string; blindSpotId: string; question: string; requestedAt: string }[]
  placements: Record<string, Placement>; conditions: Record<string, ScopeCondition>
  moveReasons: Record<string, string>; notes: Record<string, string>
  disputes: Record<string, { kind: 'derivation' | 'scenario'; target: string | null; reason: string }>
  verdict?: 'approve' | 'send-back'; verdictNote: string; signedAt?: string; updatedAt: string
}
type ExportV2 = {
  kind: 'quirk-logic-spec-decisions'; schemaVersion: 2; stage: 1 | 2
  slug: string; renderId: string; exportedAt: string; signed: boolean
  seen: Record<string, string>; state: ReviewStateV2; record: DecisionRecordV2
}
type DecisionRecordV2 = {
  stage: 1 | 2; verdict: 'approve' | 'send-back' | null; verdictNote: string; signedAt: string | null
  scenarios: { id: string; approved: boolean; dropped: string | null; then: string; changesSpec: boolean }[]
  constraints: { id: string; ruling: 'approve' | 'rewrite' | 'reject' | null; text: string; reason: string }[]
  assumptions: { id: string; ruling: AssumptionRuling | null; note: string }[]
  blindSpots: { id: string; accepted: boolean; note: string }[]
  placements: { id: string; from: Placement; to: Placement; condition: ScopeCondition | null; reason: string }[]
  disputes: { requirementId: string; kind: 'derivation' | 'scenario'; target: string | null; reason: string }[]
  scenarioRequests: ReviewStateV2['scenarioRequests']; researchRequests: ReviewStateV2['researchRequests']
  openWarnings: string[]
}
```

- All state maps are always present. A stage-1 state has empty stage-2 maps, and a stage-2 state
  keeps only `scenarioApproved` entries for reopened scenarios.
- `signed: true` requires `state.signedAt` and `state.verdict == "approve"`, as in v1.
- `disputes[*].target` is non-null exactly when `kind == "scenario"`, and it must be in that
  requirement's `derivedFrom`.

`SCHEMA:` Payload (unchanged keys): `{spec, slug, renderId, itemHashes, logicMarkdown, priorDecisions}`.

`SCHEMA:` Generated v2 `logic.md` section order ([REQ-29](logic.md#in-scope)):
- Title, Status & amendments, Purpose, Conceptual model, Data flow.
- **Behavior & scenarios**: one `###` per behavior rule, with its scenarios, each marked with any
  extra reason.
- **Constraints**: a table of id, kind, text, and ruling.
- **Requirements**: In scope / Conditionally in scope / Out of scope. Each row adds a
  "Derived from" cell. In stage 1 this section is a single line,
  `Derived after stage 1 is signed.`
- Assumptions & blind spots.
- Decisions Locked, Industry Insights.
- **Scope & non-goals**: `sections.scopeNonGoals`, plus dropped scenarios and rejected
  constraints with their reasons.
- Deferred Ideas, Glossary.

The first line stays v1's generated banner.

## DO-NOT-CHANGE fences

1. **v1 validation and `logic.md` output (`validate_logic` `:204-581`, `render_markdown`
   `:886-1010`).** Existing v1 specs (the `sample` fixture and this spec's own `logic.json`)
   must keep validating and regenerating identically ([REQ-03](logic.md#in-scope)). The v1 render
   tests pin this output.
2. **Payload marker and escaping (`PAYLOAD_PLACEHOLDER` `:19`, the `<` escape at `:1076-1077`).**
   These are the only injection boundary, and the template and renderer must agree byte-for-byte.
3. **`write_files_atomically` `:1029-1054`, and "prepare the template before writing"** (pinned
   by `test_fold_prepares_template_before_writing_any_artifacts` and
   `test_fold_preflights_output_paths_before_approving_source`). A fold must never approve the
   source when it cannot write the outputs. `reapprove` inherits this.
4. **`skills/brainstorming/SKILL.md` stays ≤400 lines** (374 today; capped by
   `tests/test_brainstorming_elicitation.py`). Keep its 12-step checklist and the literals v1's
   tech spec listed.
5. **This spec's own folder** (`docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/logic.json`)
   is a v1-format, Approved spec. It must keep validating as v1, and no implementation task edits it.
   Only the orchestrator records rulings in its `status`, and amendments go in `amendments`.
6. **`skills/adversarial-review/scripts/adversarial-review` `SPEC_DESIGN_NAMES`.** Do not add
   `logic.json` (line 50 is `{"logic.md", "tech.md"}`). The generated `logic.md` beside
   `logic.json` already routes a spec to the `spec-design` profile, and a JSON source would feed
   the reviewer the wrong artifact.

## Always / Ask / Never

**Always**
- Keep `render_spec.py` stdlib-only and Python 3.9-compatible: no `match`, and no `X | Y` unions
  at runtime.
- Keep the IDs, meanings, and ordering of the Python and TS gates identical.
- Rebuild and commit `review-template.html` with any `app/` change. `pnpm run check` now
  enforces this.
- Keep the full suite green. The baseline is **1066 passed** at `21c9220` (`python3 -m pytest -q`).
- Keep the payload the page's only input.

**Ask**
- If the stage-1 lock turns out to reject a legitimate stage-2 edit the logic spec allows, stop
  and surface it. Do not loosen the lock.
- If the built template grows by more than 25% over the current size, surface it.

**Never**
- Never accept a v1 export, or give a v1 spec a review page.
- Never let `reapprove` touch anything except `reopened` and `reapprovedHash` on qualifying
  scenarios.
- Never fold an unsigned, stale, or stage-mismatched export.
- Never write `logic.md` by hand.

## Cross-cutting

- **Security:** unchanged from v1. The payload escape and the Markdown rendering path hold, and
  Import validates `kind`, `slug`, `schemaVersion`, and `stage`.
- **Migration:** none ([OOS-01](logic.md#out-of-scope)). v1 files stay readable. A browser's
  `localStorage` snapshot from a v1 page fails `isReviewState` and is ignored.
- **Rollback:** revert the branch. v1 specs are unaffected, since their path is the fenced v1 code.
- **Observability:** CLI exit codes, stderr diagnostics, and the new warning line.

## Testing strategy

Back-link: [Decisions Locked → Success criteria](logic.md#success-criteria).

**New fixtures** under `tests/fixtures/interactive/v2/`:
- `stage1/logic.json`. It has:
  - two behaviors, one with four scenarios (the fourth with `extraReason`);
  - a Claude-added scenario and constraint, and constraints of three kinds including `non-goal`;
  - an assumption, and blind spots: one resolvable by a constraint, one not;
  - research, and a scenario with `alternatives`.
- `stage1/exports/`: `signed`, `unsigned`, `stale`, `gate-<id>` variants for each stage-1 gate,
  and `with-drop-and-rewrite`.
- `stage2/logic.json`. It is the output of folding `stage1/exports/signed.json`, plus derived
  requirements (including an out-of-scope one derived from the non-goal constraint), a
  `conflicts` pair, and a state-machine view. Generate it with the CLI, then hand-add the
  requirements. The lock proves nothing else changed.
- `stage2/exports/`: `signed`, `unsigned-derivation-dispute`, `unsigned-scenario-dispute`,
  `unsigned-reapproved`, and `gate-<id>` variants.
- `invalid-v2/`: missing `derivedFrom`, `derivedFrom` naming a dropped scenario, requirements
  present in stage 1, a locked item edited in stage 2, a missing `extraReason`, a duplicate id
  across kinds, and a scenario with an unknown `behavior`.

**`tests/test_interactive_logic_spec.py` must cover:**
- v1: `validate` and `render` still pass and are byte-identical to today. `render --prior`,
  `render --open`, `check-export`, `find-export`, `fold`, and `reapprove` on the v1 sample exit 6
  with the message, and `render --prior` writes nothing.
- v2 `validate`:
  - exit 0 plus exactly one warning line for the stage-1 fixture;
  - exit 1 with a pointer for each `invalid-v2` variant.
- v2 `render`:
  - deterministic;
  - `itemHashes` covers behaviors and constraints;
  - editing one constraint changes only its hash;
  - `logic.md` has the v2 headings, per-behavior grouping, the Constraints table, and
    "Derived from" cells (stage 2) or the stage-1 placeholder line.
- `check-export`: exit 3 on a stage-1 export against the stage-2 fixture ([SC-13](logic.md#behavior--scenarios)).
- Stage-1 `fold`:
  - applies drops, rewrites (`originalText` kept), rejections, rulings, and acceptance;
  - `stage` becomes 2, `status` becomes `Stage 1 approved`, and `stage1Pin` equals `item_hashes`
    of the result;
  - each stage-1 gate variant exits 4 naming the gate;
  - `--tech-spec-requested` exits 2.
- Final `fold`:
  - each stage-2 gate variant exits 4 naming the gate, including `derivation` for an
    under-derived scenario, while the out-of-scope non-goal derivation passes
    ([SC-09](logic.md#behavior--scenarios));
  - `reapprovedHash` is moved into the pin;
  - the status is set with and without `--tech-spec-requested`.
- Reopen flow ([SC-11](logic.md#behavior--scenarios)):
  - Setting `reopened` on a scenario in the stage-2 fixture and editing its text still
    validates.
  - Editing a *different* locked scenario fails the lock.
  - `reapprove` with `unsigned-reapproved` moves the scenario to `reapprovedHash` and prints the
    id. It exits 4 when nothing qualifies and 3 when the export is stale.
- The derived-requirement status is exercised through the `derivation` and `scope-warnings`
  gates: a withdrawn requirement neither covers nor warns.

**Page checks**, run from `skills/writing-specs/interactive/app/`:

`COMMAND:` `pnpm install --frozen-lockfile && pnpm run build && pnpm run check`

The layout check now runs against the v2 stage-2 fixture. The template check must fail when a
source edit is not rebuilt; verify that once by hand, by editing a string without building.

**Browser smoke** (manual, `playwright-cli`):
1. Render `v2/stage1`.
2. Open it and confirm the stage-1 tabs and the header label, the Claude-added preselection
   marker, the extra-scenario flag, drop with reason, and a constraint rewrite.
3. Export, then run `check-export`.
4. Render `v2/stage2` and confirm the stage-2 tabs, the read-only stage-1 tabs, the trace matrix
   gap, a dispute of each kind, and sign-off gates naming `derivation` and `disputes`.
5. Take screenshots in light and dark mode.

**Success criterion (manual):** one end-to-end v2 run on a toy topic in a scratch dir: brainstorm
→ stage-1 review → signed stage-1 fold → derivation → stage-2 review with one dispute → signed
fold → `quirk:writing-plans` reads the generated `logic.md`.

## Non-goals

- A shared gate engine between Python and TS. The duplication stays, as in v1.
- A v1 → v2 migration command ([Deferred Ideas](logic.md#deferred-ideas)).
- A JS unit-test runner for the page. The page is covered by typecheck, the layout and template
  checks, and the manual smoke.
- Everything in the logic spec's [Scope & non-goals](logic.md#scope--non-goals).
