# Writing an Interactive Logic Spec

Use this rubric only when the user chose the interactive format at brainstorming's spec-writing step. Brainstorming offers the choice once; markdown remains the default and follows [logic-spec.md](logic-spec.md). An interactive spec is one `logic.json`, `schemaVersion: 2`, reviewed in two stages: stage 1 signs what should happen (behaviors, scenarios, constraints, risks); the stage-1 fold derives requirements the reviewer signs off in stage 2 (what to build). This rubric follows the approved [Behavior & scenarios](../../docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/logic.md#behavior--scenarios) and [Decisions Locked](../../docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/logic.md#decisions-locked) contracts.

## When to use

The user explicitly chose interactive when brainstorming offered markdown (the default) or interactive. Do not offer the format again or convert an existing markdown spec to interactive. Follow [Where the specs live](SKILL.md#where-the-specs-live) for the chosen location; an interactive spec has `logic.json` as its source of truth and a generated `logic.md` beside it, both eventually committed.

## What to write in stage 1

Write `<spec-dir>/logic.json` at `schemaVersion: 2`, `stage: 1`, `requirements: []`, using the `LogicSpecV2` shape in [Data models / schemas](../../docs/quirk/specs/2026-09-24-interactive-logic-spec-v2/tech.md#data-models--schemas) and the page's [TypeScript source of truth](interactive/app/src/spec-types.ts). Include every section [logic-spec.md](logic-spec.md) requires; the Requirements section renders as a single placeholder line until stage 1 is signed.

- **Behaviors**: a named one-line rule. Every scenario belongs to exactly one behavior.
- **Scenarios**: Given/When/Then plus `alternatives`, grouped under their behavior. Write a scenario for every case a reviewer could rule on differently: each branch of the rule, each edge case, each known failure mode. There is no per-behavior limit, so never merge or cut a scenario to keep a behavior short; skip only one whose outcome another scenario under the same behavior already shows. A case no behavior's rule covers gets a new behavior rather than a stretched one. Specs written under the old three-per-behavior limit may still carry `extraReason`; it is ignored.
- **Constraints**: non-behavioral requirements of kind `placement`, `verification`, `naming`, or `non-goal`, plus `other` for anything the four don't fit. Draw them from Decisions Locked and scope.
- **Provenance**: a scenario or constraint Claude adds without asking carries `provenance: "claude"` and a `rationale`; anything decided in brainstorming carries the deciding `question` instead. A Claude-added item is preselected — Claude's `then` or `approve` shows as the value — but stays marked as Claude-added until a state entry exists; the preselection is not itself a decision.
- Point assumption `affects` and blind-spot `sources` / `resolvedBy` at scenario or constraint ids, not requirement ids — requirements do not exist yet.

Keep IDs unique across every kind — behaviors, scenarios, constraints, assumptions, and blind spots all key one `itemHashes` map — and every cross-reference resolvable.

## The render loop

Use the `render_spec.py` script shipped with `quirk:writing-specs` (Python 3.9+, standard library only):

```text
render_spec.py validate     <spec-dir>
render_spec.py render       <spec-dir> [--prior <export.json>] [--open]
render_spec.py find-export  <spec-dir> [--downloads <dir>]
render_spec.py check-export <spec-dir> <export.json>
render_spec.py fold         <spec-dir> <export.json> [--tech-spec-requested]
render_spec.py reapprove    <spec-dir> <export.json>
```

`<spec-dir>` contains `logic.json`; its basename is the spec `slug`. Before opening a review, run `validate`, then `render --open`. `render` writes `review.html`, `logic.md`, and `.gitignore`, and prints the current `renderId`; it is deterministic for identical input. Do not install packages, build the page, or use a network path at spec time: the page is a local file and the renderer embeds the data in the prebuilt template.

Exit codes: 0 ok, 1 invalid input, 2 usage error, 3 stale render, wrong slug, or stage mismatch, 4 (fold/reapprove) unsigned export or a failed gate named on stderr, 5 (find-export) no export found, 6 the spec is a read-only v1 file — see [v1 specs are read-only](#v1-specs-are-read-only).

Never work around an invalid or stale result by applying its decisions directly.

## Stage-1 feedback rounds

When the reviewer says they exported decisions, locate and check the export exactly as v1 does:

```text
render_spec.py find-export  <spec-dir> [--downloads <dir>]
render_spec.py check-export <spec-dir> <export.json>
```

`find-export` searches the spec folder and `~/Downloads` (or `--downloads`) and prints the newest matching export for the current `logic.stage`; a stage-1 export never matches a stage-2 spec, or the reverse. An export found in Downloads is moved into the spec folder, next to `review.html`, and the new path is printed; it stays put if that name is already taken there. If the reviewer pasted Copy into chat, save it as `<slug>-decisions-<YYYYMMDDTHHMMSS>.json` in the spec folder and check that path. `check-export` prints `signed` or `unsigned`; proceed only on exit 0.

For a current **unsigned** stage-1 export:

1. Answer research requests in `research[]` and turn scenario requests into new `scenarios[]`, retaining each request's ID.
2. Apply the reviewer's requested content changes — new or edited scenario and constraint text — to `logic.json`. Rewrite each scenario named in `state.scenarioUpdates` (also `record.scenarios[].update`) as its feedback asks; the rewrite changes the scenario's hash, which clears the request and returns the scenario for a fresh decision. A scenario you leave unchanged keeps its update request, and stage 1 cannot sign while one is open.
3. Do **not** write drops, constraint rulings, or rewritten constraint text into `logic.json`; they live only in the export's state and travel forward until the fold. Re-render with `--prior` so unchanged decisions carry into the next review:

   ```text
   render_spec.py render <spec-dir> --prior <export.json>
   ```

Never fold a stale or unsigned export.

## Stage-1 sign-off and fold

Stage 1 signs when every Claude-added scenario and constraint is decided, every scenario is approved or dropped with a reason and no scenario request or update is pending, every constraint is approved, rewritten with text, or rejected with a reason, every assumption is ruled, and every active blind spot is either accepted with the reviewer's own sentence or has a research request. Asking for research settles a blind spot the way a verify-first ruling settles an assumption. Run `check-export` first and fold only a current signed export:

```text
render_spec.py fold <spec-dir> <export.json>
```

`fold` applies each scenario's `then` and `dropReason`, each constraint's `ruling` (with `originalText` on a rewrite), and the assumption and blind-spot rulings (an assumption whose certainty the reviewer changed gets the new `certainty` and keeps Claude's as `originalCertainty`; a blind spot settled by a still-unanswered research request gets that request as `researchRequest`), then sets `stage: 2`, `status: "Stage 1 approved"`, and a `stage1Pin` — the signed-at time, `renderId`, and the hash of every stage-1 item as signed. It does not write `signoff`. Passing `--tech-spec-requested` here is a usage error; that flag belongs on the [final fold](#final-sign-off-and-fold).

## Derivation

After the stage-1 fold, first answer every blind spot that carries a `researchRequest` (a research request still open at sign-off) with a `research[]` finding whose `requestId` is that request's `id`. Then derive `requirements[]` yourself, plus any [optional views](#optional-views) the requirements support — no page round is needed for this step. Each requirement's `derivedFrom` names one or more approved scenarios (no `dropReason`) or approved/rewritten constraints, never a dropped scenario or a rejected constraint. An approved or rewritten **non-goal** constraint derives one `scope: "out"` requirement, which satisfies the under-derived gate for it. Pre-fill each requirement's `group` and `placement` (in / conditional / out) with your best judgment; the reviewer only needs to move the ones you got wrong, with a reason. Requirements carry no `provenance`, `question`, or `rationale` — `derivedFrom` is their only origin. Re-render so the page shows the stage-2 tabs with stage 1 read-only.

## Optional views

While deriving, also write every optional view the spec's content supports, under `views` in `logic.json`. Validation rejects `views` in stage 1 because views point at requirement IDs, so derivation is the first point where you can add them; add or revise them in any later stage-2 round too. Each view appears on the page only when its data exists, so a view you skip simply never shows.

- **`stateMachine`**: write one when requirements describe something moving through states: a status, lifecycle, or workflow such as a row's update status or a job's progress. States are the distinct conditions a reviewer can name, `entries` are where things start, and every transition names its event and the `reqs` that govern it (plus `blindSpot` when one applies). Drawing it is a completeness check: a state with no way out, or an event with no transition, is a question for the reviewer.
- **`storyMap`**: write one when requirements follow a user journey through ordered steps. `journey` lists the requirement `area`s in journey order, each with a label; `crossCutting` lists areas that apply at every step.
- **`custom`**: a list of task-specific tables, each its own tab. Add one when the reviewer would otherwise have to hold a set of cross-cutting facts in their head: the same facts about each of several subjects (each supported tool's install method and update path), or every piece of user-facing text the spec commits to. Each view has an `id`, a `title`, an optional `intro`, typed `columns`, and `rows` of `cells` keyed by column. Column types:
  - `text` or `markdown`: a string, or `{text, certainty}` when the fact could be wrong; item IDs in markdown become links.
  - `items`: a list of scenario, requirement, constraint, assumption, or blind-spot IDs; requirements moved out of scope show as such.
  - `status`: a short label, colored through the column's `statuses` map from label to `green`, `yellow`, `orange`, `red`, `blue`, or `default`.
  - `quote`: exact user-facing text, with `<...>` for placeholders. `checkedAgainst` names an `items` column in the same row, and `validate`, `render`, and the page all flag any of those items that words it differently.

  Keep to two or three custom views per spec. A new column type is added to the page only when a real need cannot be expressed with these; a one-column `markdown` table is the fallback for content that fits nothing else, at the cost of those checks.

Coverage and Impact × certainty need no data of their own: they appear automatically once requirements exist and, for the heatmap, carry a certainty.

## Stage-2 feedback rounds

Process a stage-2 unsigned export the same way as stage 1, plus disputes:

- A `derivation` dispute: rewrite that requirement's text. Stage 1 and its pin are untouched.
- A `scenario` dispute against target `SC-x`: revise `SC-x` and set `reopened = {requirementId, reason, raisedAt}` on it. Every requirement derived only from that scenario now shows withdrawn; one derived from it and something else shows flagged, not withdrawn.
- Once the reviewer re-approves a reopened scenario on the page and exports again (this export need not be signed), run:

  ```text
  render_spec.py reapprove <spec-dir> <export.json>
  ```

  which clears `reopened` and sets `reapprovedHash` on every scenario the reviewer re-approved against its current hash, then re-derive every requirement whose `derivedFrom` names that scenario.
- Then re-render with the checked export:

  ```text
  render_spec.py render <spec-dir> --prior <export.json>
  ```

`reapprove` is the only command that applies a decision from an unsigned export; it touches nothing but `reopened` and `reapprovedHash` on qualifying scenarios. It exits 4 with `nothing to re-approve` when no scenario qualifies, and 3 on a stale export.

## Final sign-off and fold

Stage 2 signs when no approved stage-1 item is under-derived, every placement move has a reason, there are no scope warnings, unresolved conflicts, or orphans, and `state.disputes` is empty with no scenario left `reopened`. A signed stage-2 export is the approval — there is no second chat approval. Fold it:

```text
render_spec.py fold <spec-dir> <export.json> [--tech-spec-requested]
render_spec.py render <spec-dir>
```

`fold` applies placement, condition, and `reviewReason` as v1 does, moves any `reapprovedHash` into `stage1Pin.itemHashes` and drops the field, then sets `signoff` and marks the spec `Approved` (or `Approved — Tech spec: requested`). Pass `--tech-spec-requested` here, not at the stage-1 fold, when the user asked for a tech spec. Commit `logic.json` and the regenerated `logic.md`, not `review.html` or exports. Hand off to [subagent-driven-development](../subagent-driven-development/SKILL.md) or [executing-plans](../executing-plans/SKILL.md); execution continues from `logic.md` without asking for another approval.

## UI feedback

A requested change to the review page belongs in the shared `interactive/app/` source, not in a spec-specific page. From `skills/writing-specs/interactive/app/`, rebuild the committed template with:

```sh
pnpm install --frozen-lockfile && pnpm run build && pnpm run check
```

Build before check: `pnpm run check` now includes a template-freshness check that compares against the freshly built template, so a stale build fails it. The build emits `../review-template.html`. Then re-render the current spec with `render_spec.py render <spec-dir>` so its `review.html` uses the rebuilt template. This build is for shared page changes, never part of ordinary spec authoring.

## Amendments after approval

For a later, user-approved change to a locked decision, add an entry with a `YYYY-MM-DD` `date` and `text` to `logic.json`'s `amendments` array, then update the source content. Regenerate the outputs with:

```text
render_spec.py validate <spec-dir>
render_spec.py render <spec-dir>
```

Do not edit generated `logic.md`. The chat approval and dated amendment are sufficient; do not send the spec through page review again.

## v1 specs are read-only

A `logic.json` at `schemaVersion: 1` still validates and regenerates `logic.md`, and still takes amendments. `find-export`, `check-export`, `fold`, and `reapprove` all refuse it and exit 6 with `read-only v1 spec: page review, check-export, reapprove, and fold are refused; amend logic.json and re-render`; `render --prior` and `render --open` exit 6 before writing anything. Never give a v1 spec a review page — amend `logic.json` directly and re-render instead.

## Self-review

Run the four [logic-spec.md self-review checks](logic-spec.md#logic-spec-self-review) against `logic.json`: scan for placeholders or incomplete sections; check internal consistency; check scope; and remove ambiguity. Also confirm every `dependsOn`, `derivedFrom`, `affects`, `sources`, `resolvedBy`, and `requestId` resolves. Run `render_spec.py validate <spec-dir>`; it checks the schema, unique IDs across every item kind, all cross-references, and, once stage 2 exists, the stage-1 lock. Fix all failures before rendering or hand-off.
