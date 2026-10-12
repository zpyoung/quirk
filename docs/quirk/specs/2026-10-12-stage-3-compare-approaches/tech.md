# Stage 3 — compare approaches: tech spec

Logic spec: [logic.md](logic.md). This document says where to work and what must hold. Paths are relative to `skills/writing-specs/interactive/` unless they start with `tests/` or `docs/`. Line anchors are against `f4d7eb4`.

## 1. Files and ownership

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

| Area | Files | Change |
|---|---|---|
| Renderer | `render_spec.py` | comparison loading and validation, payload extension, stage-3 export validation, `check-export` branch, new `challenges` subcommand |
| App types | `app/src/spec-types.ts`, new `app/src/compare-types.ts` | payload fields; all stage-3 types live in the new file |
| App routing | `app/src/review-state.ts` | type-only: widen `ViewId` with `s3-guidance`, `s3-overview`, `s3-approaches`, `s3-effort`, `s3-blast`, `s3-tradeoffs`; `isPayload` tolerates the new optional keys (it never rejects on them) |
| App state | new `app/src/compare-state.ts` | stage-3 state, storage, drift carry-over, export builder, type guards |
| App shell | `app/src/App.tsx` | conditional third stepper step, stage-3 tabs prepended, delegate rendering to the stage-3 views |
| App views | new `app/src/views/compare/*.tsx` | Guidance, Overview (cards, matrix, drawer, choices), Approaches, Effort, Blast radius, Trade-offs, control strip, tray |
| Diagrams | new `app/src/views/compare/diagrams/*.tsx` | process flow, sequence, schema renderers with deterministic layout |
| Template | `review-template.html` | rebuilt by `pnpm run build`, committed |
| Fixtures | new `tests/fixtures/interactive/v2/compare/`, new `tests/fixtures/interactive/golden/` | synthetic signed spec plus comparison; golden renders |
| Tests | `tests/test_interactive_logic_spec.py` (golden tests), new `tests/test_compare_stage.py` | |
| App check | new `app/scripts/check-compare.ts`, `app/package.json` | type-check the fixture comparison against the TS types |
| Docs | `skills/writing-specs/interactive-logic-spec.md`, new `skills/writing-specs/comparison-schema.md` | new "Stage 3: compare approaches" section; the schema reference ships with the skill |

## 2. comparison.json

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

`comparison.json` sits beside `logic.json`. The coordinator writes it; nothing generates it. All prose fields are plain text rendered as text (never HTML), except `specMarkdown`, which renders through Astryx `Markdown`.

`SCHEMA:` top level
```
{
  "kind": "quirk-approach-comparison",
  "schemaVersion": 1,
  "builtAgainst": { "signoffRenderId": str },          // logic.signoff.renderId when built
  "approaches": [Approach, ...],                       // 2..5, ids unique, ^[A-Z]$
  "scores": { "<REQ id>": { "<approach id>": Score } },
  "findings": [Finding, ...],                          // optional, default []
  "pairings": [Pairing, ...],                          // optional
  "choices": [ { "question": str, "answers": { "<approach id>": str } } ],   // optional
  "keyDifferences": [str],                             // optional
  "example": { "scenario": str, "stages": [str] },     // optional; stage labels shared by every approach's trace
  "flowStages": [str],                                 // optional; fixed stage names for every approach's flow, 3..8
  "guidance": Guidance                                 // optional
}
```

`SCHEMA:` Approach
```
{
  "id": "A", "title": str, "overview": str,            // overview: coordinator, plain text
  "revision": str,                                     // opaque; changes when the proponent's spec changes
  "anchors": [ { "repo": str, "commit": str } ], "readAt": "YYYY-MM-DD",
  "specMarkdown": str,                                 // optional; the full tech spec
  "repos": [ { "name": str, "files": int } ],
  "schemaChange": str, "hotPaths": [str],
  "deploy": { "status": "stated" | "implied" | "not-stated", "steps": [str] },
  "criticalPath": str | null,
  "slices": [Slice, ...],
  "flow": [ { "stage": str, "lane": str, "text": str, "kind": "new" | "changed" | "reused", "focal": bool? } ],  // optional
  "sequence": { "participants": [str], "messages": [ { "from": str, "to": str, "label": str, "kind": "call" | "return" | "async" | "focal" } ] },  // optional
  "schema": { "tables": [Table], "refs": [ { "from": [table, column], "to": [table, column], "kind": "fk" | "json" } ] },  // optional
  "exampleTrace": [str],                               // optional; one entry per example.stages
  "restsOn": [str], "undo": { "flagOff": str, "hardToReverse": str, "cheapestNext": str },   // optional
  "rivalClaims": { "<other approach id>": [str] },     // optional; proponent advocacy
  "effortGaps": [str]                                  // optional; coordinator notes shown inline on the Effort tab
}
```

`SCHEMA:` Slice, Table, Score, Finding, Pairing, Guidance
```
Slice   { "id": str, "name": str, "size": SizeLabel, "band": "v1" | "fast-follow" | "optional",
          "area": str, "risk": str, "riskHeadline": str?, "lines": { "<repo>": [int lo, int hi] }? }
Table   { "name": str, "status": "new" | "changed" | "existing",
          "columns": [ { "name": str, "type": str, "chip": "PK" | "FK" | "UQ" | null?, "highlight": bool? } ],
          "moreColumns": str? }
Score   { "status": "met" | "met with workaround" | "very hard" | "not met", "qualifier": str?,
          "wording": str, "note": str, "citations": [str],
          "requirementHash": str, "requirementText": str,   // hash and signed text of the requirement when scored
          "check": str?,                                // coordinator verification; absent = claimed
          "history": [ { "previous": { "status": ..., "qualifier": str? }, "challenge": str, "reply": str,
                         "outcome": "revised" | "held" } ]? }
Finding { "requirementId": str, "approaches": [id] | "all", "type": "disputes" | "same score, different design",
          "text": str, "citation": str }
Pairing { "name": str, "items": { "<approach id>": str }, "text": str }
Guidance { "intro": str, "steps": [ { "title": str, "body": str, "tab": TabKey } ], "questions": [str],
           "recommendation": { "approachId": str, "headline": str, "confidence": "low" | "medium" | "high",
                               "confidenceReason": str, "why": [str], "costs": [str], "changeMyMind": [str] },
           "suggestedChallenges": [ { "requirementId": str, "approachId": str, "note": str, "want": ScoreStatus } ],
           "changeNote": str? }
```

`CONFIG:` size labels and points (shared by Python validation and TS display)
```
S [2,2] · S-M [2,3] · M [3,3] · M-L [3,5] · L [5,5] · L-XL [5,8] · XL [8,8]
```

`CONFIG:` TabKey — `overview`, `approaches`, `effort`, `blast`, `tradeoffs`.

Every enum, required key and type in these SCHEMA blocks is enforced: a violation is a validation error with a JSON pointer, in Python and in the TS guard alike. Slice ids are unique per approach. `readAt` is `YYYY-MM-DD`. `refs` counts every reference, `fk` and `json` together, against the limit of 6.

**Hashed content.** `targetHash` covers only the content a reviewer argues with, so a coordinator adding a `check` or `history` entry never invalidates drafts:
- score target: `status`, `qualifier`, `wording`, `note`, `citations`, `requirementHash`
- slice target: `name`, `size`, `band`, `lines`

Hashed objects hold only strings, integers, booleans, arrays and objects with ASCII keys, which keeps Python's and JS's canonical JSON identical.

## 3. Renderer contract (`render_spec.py`)

Back-link: [Entry and lifecycle](logic.md#entry-and-lifecycle), [Challenges and rounds](logic.md#challenges-and-rounds).

`CONTRACT:`
```
COMPARISON_KIND = "quirk-approach-comparison"
COMPARE_EXPORT_KIND = "quirk-approach-comparison-challenges"
POINT_MAP: Dict[str, Tuple[int, int]]
def spec_is_signed_stage2(logic: dict) -> bool
def comparison_id(comparison: dict) -> str                         # sha256(canonical_json)[:12], like render_id
def validate_comparison(comparison: Any, logic: dict) -> Tuple[List[Tuple[str, str]], List[str]]
def load_comparison(spec_dir: Path, logic: dict) -> Tuple[Optional[dict], Optional[str], int]
    # -> (comparison, comparison_id, status) ; status 0 = loaded or absent, 1 = invalid
def target_hash(obj: dict, kind: str) -> str                       # kind: "score" | "slice"; hashes the fields in §2
def _export_kind(export_path: Path) -> Optional[str]                # reads only "kind"; None when unreadable
def prepare_render_files(spec_dir, logic, current_render_id, prior=None,
                         comparison: Optional[dict] = None, comparison_id: Optional[str] = None) -> Tuple[str, str]
def render_files(spec_dir, logic, current_render_id, prior=None, open_page=False,
                 comparison: Optional[dict] = None, comparison_id: Optional[str] = None) -> None
def validate_compare_export_shape(export: Any) -> List[Tuple[str, str]]
def command_challenges(spec_dir: Path, export_path: Path, as_json: bool) -> int
```

- **Signed predicate.** `logic.get("schemaVersion") == 2`, `logic.get("stage") == 2`, `str(logic.get("status", ""))` starts with `"Approved"`, and `"signoff"` is present. `"Stage 1 approved"` is not signed. A v1 spec is never signed for stage 3: `load_comparison` returns `(None, None, 0)` for it with no warning, and `command_render`'s v1 path returns before calling it.
- **load_comparison.** Absent file → `(None, None, 0)`, silent. Present beside an unsigned spec → one stderr warning `comparison.json ignored: stage 3 waits for stage-2 sign-off`, `(None, None, 0)`. Present beside a signed spec → `load_json`, then `validate_comparison`; errors print through `emit_errors` and return status 1; warnings print to stderr only when there are no errors.
- **validate_comparison errors** (Validator pointers, as in `_validate_custom_views` at `render_spec.py:657`): wrong `kind` or `schemaVersion`; approach count outside 2..5; duplicate or malformed approach id; an in-scope requirement (scope not `out`) missing a score for any approach; a score for an unknown requirement or approach; status outside the four values; a finding without `citation` or naming an unknown requirement/approach; a slice size outside `POINT_MAP`; `exampleTrace` length different from `example.stages`; a `flow` stage not in `flowStages`; sequence over 5 participants or 12 messages, or a message naming an unknown participant; schema over 5 tables or 6 refs, or a ref naming an unknown table/column; guidance `tab` outside TabKey; recommendation or suggested challenge naming an unknown approach/requirement.
- **validate_comparison warnings:** `builtAgainst.signoffRenderId` differs from `logic.signoff.renderId`; a score's `requirementHash` differs from `item_hashes(logic)[REQ]` (the page shows these as "scored against older text", so this is informational).
- **Render.** `command_render` and `command_validate` call `load_comparison` after `load_logic`; status 1 exits 1. Only `command_render` passes `comparison` and `comparison_id` to `render_files`, which passes them to `prepare_render_files`. When they are not `None`, the payload gains exactly two keys, `comparison` and `comparisonId`. When they are `None`, the payload and `logic.md` are byte-identical to today. `render_id(logic)` never includes the comparison. `_fold_write_outputs` (`:2895`) and the v1 path pass nothing, so a fold never embeds a comparison; the next `render` does.
- **Stage-3 export.** `check-export`, `fold` and `reapprove` call `_export_kind` after their v1 exit-6 check and before `_read_export_and_validate`. In `check-export`, For `COMPARE_EXPORT_KIND`: validate shape (exit 1 on errors); exit 3 when `slug` differs from the spec dir or `comparisonId` differs from the current comparison's id (or no comparison loads); print `stage-3: <n> challenges, <m> stars` and exit 0. In `fold` and `reapprove`, the stage-3 kind exits 2 with `stage-3 exports carry challenges, not decisions; use check-export or challenges`. In `check-export` and `challenges`, a comparison that fails to load exits 1.
- **validate_compare_export_shape** checks: `kind` and `schemaVersion`; required keys and types; unique challenge ids; nonempty `note`; `want` is a score status for a score target and a size label for a slice target; `stars` is an array of strings. Against the current comparison, a target that does not resolve exits 1 with a pointer.
- **challenges subcommand.** `render_spec.py challenges <spec_dir> <export> [--json]`. Same validation and staleness rules as stage-3 `check-export`. Prints challenges grouped by approach id, each with requirement id and text (or slice id and name), current score or size, the reviewer's note and wanted value, and `target changed` when its `targetHash` no longer matches. `--json` prints `{ "<approach id>": [ ... ] }` plus `"stars": [...]`. Exit 0.

`SCHEMA:` stage-3 export
```
{
  "kind": "quirk-approach-comparison-challenges", "schemaVersion": 1,
  "slug": str, "renderId": str, "comparisonId": str, "exportedAt": ISO,
  "challenges": [ { "id": str,
                    "target": { "type": "score", "requirementId": str, "approachId": str }
                            | { "type": "slice", "approachId": str, "sliceId": str },
                    "note": str (nonempty), "want": ScoreStatus | SizeLabel, "targetHash": str } ],
  "stars": [REQ id],
  "approachRevisions": { "<approach id>": str }
}
```

`targetHash` is the first 12 hex of sha256 over `canonical_json` of the hashed fields in §2. Python and TS compute it identically: sorted keys, `(",", ":")` separators, UTF-8, no ASCII escaping.

## 4. App contract

Back-link: [Guidance tab](logic.md#guidance-tab), [Overview tab](logic.md#overview-tab), [Approaches tab](logic.md#approaches-tab), [Effort and Blast radius tabs](logic.md#effort-and-blast-radius-tabs), [Trade-offs tab](logic.md#trade-offs-tab), [Cross-tab controls](logic.md#cross-tab-controls).

- **Payload.** `LogicSpecPayload` (`spec-types.ts:348`) gains optional `comparison?: Comparison` and `comparisonId?: string`. `isPayload` (`review-state.ts:222`) ignores them. The shell runs `isComparison` from `compare-state.ts`; when it fails, stage 3 stays inactive and a `Banner` names the first failing pointer, so a Python/TS drift never breaks stages 1 and 2.
- **Activation.** Stage 3 is active when `payload.comparison` and `payload.spec.signoff` are both present. Inactive means nothing in the stage 1-2 render path changes: same tabs, same Stepper markup, same default view, same storage writes.
- **Shell.** In `App.tsx`, when active: the Stepper (`:299-302`) renders a third `Step` "Stage 3 · Compare approaches" with `activeStep={2}`; the `tabs` memo (`:129-157`) prepends `s3-guidance` (only when `comparison.guidance` exists), `s3-overview`, `s3-approaches`, `s3-effort`, `s3-blast`, `s3-tradeoffs`; `defaultView` becomes `s3-guidance`, or `s3-overview` without guidance. Stage-3 views render from a `CompareShell` that owns its own state and the control strip and tray; stage 1-2 views and hooks are untouched.
- **Types.** `ScoreStatus` and `SizeLabel` are the §2 enums. `Draft` has the shape of a stage-3 export challenge entry.
- **State.** `compare-state.ts` owns a `CompareState` `{ comparisonId, drafts: Draft[], needsLook: Draft[], stars: string[], focus: "all" | "<id><id>", includeConditional: bool, droppedStars: string[], lastExport: { at, approachRevisions, scoreHashes: { "<REQ>|<approach>": targetHash } } | null }` stored under `quirk-compare:${slug}` with try/catch like `persist` (`App.tsx:97-104`). On load with a different `comparisonId`: keep drafts whose `targetHash` equals the current target's hash, move the rest to `needsLook`; drop stars for requirements no longer in-scope and list them in `droppedStars`.
- **Hashing.** `compare-state.ts` holds a small synchronous pure-TS SHA-256 and canonical-JSON writer for `targetHash`. No dependency is added, and `crypto.subtle` is not used because it is async and unreliable on `file://`.
- **Derived views.** `focusApproaches(state)`; `coverageCounts(approach, requirements)` returning per-status counts for `group == "min"` and for every other group, plus `notFullyMet: REQ id[]`; matrix rows grouped by `requirement.area`; `visibleRequirements(comparison, spec, state)` (applies the conditional toggle); `defaultRows(...)` (differences across the focused approaches, plus rows no focused approach fully meets, plus rows with a finding); points per approach and band from `POINT_MAP`; MRs per slice per repo as `ceil(lines/500)` for each end of the range; `staleScore(score, itemHashes)` when `requirementHash` differs, with the diff shown between `requirementText` and the current text; `revisedRows(approach)` = rows whose score hash differs from `lastExport.scoreHashes` and that gained no `history` entry since; `anchorMismatch` = the same repo anchored at different commits across approaches; `guidanceNotes(state)` = starred requirements the recommended approach doesn't fully meet, conditional requirements left out, and a pair focus that excludes the recommended approach.
- **Pair focus.** Overview cards, the matrix, the choices table and the Trade-offs columns show only the two focused approaches, and the matrix and choices table also hide rows where those two agree. Approaches pills, Effort and Blast radius show only the two approaches, without a difference filter.
- **Matrix layout.** On narrow screens the table scrolls horizontally with the requirement column sticky.
- **Drawer.** Astryx `Dialog` with `position={{ end: 0, top: 0, bottom: 0 }}`, read-only content plus the challenge form.
- **Markdown.** `specMarkdown` renders like `views/spec-view.tsx:7-14` (`Markdown` with `OFFLINE_MARKDOWN_COMPONENTS`, `headingLevelStart={2}`), inside an Astryx `Collapsible`, closed by default. Relative links render as plain text.
- **Diagram layout rules.** Flow lanes come from distinct `lane` values in first-appearance order, and two boxes on the same lane and stage are a validation error. Schema tables fill a 3-column grid in array order. A ref leaves from its source row's right edge when the target sits to the right or in the same column, otherwise from the left edge. Two refs that land on the same row offset their attach points by ±8px.
- **Diagrams.** Inline React SVG in the style of `views/state-machine-diagram.tsx` (theme via the CSS variables at `:17-21`), with deterministic layout computed in TS (no ELK): fixed lanes and stage columns for flow; fixed participant columns and 36px message rows for sequence; explicit grid placement for schema tables with orthogonal rounded connectors. Follow diagram-design's connector rules: right-angle connectors with radius 8, label masks with a 6px gap, no shared attach points, a bottom legend, and at most 2 accent elements. Long identifiers wrap at `_` boundaries, never mid-word.
- **Status chips.** The four statuses always render with an icon (✓ ◐ ▲ ✕) and an accessible label, never color alone.
- **Export.** `createCompareExport()` builds the stage-3 export; the tray downloads it as `${slug}-challenges-${stamp}.json`. Import of a stage-3 export restores drafts and stars; a stage 1-2 export imported on a stage-3 tab, or the reverse, is rejected with a message naming the kind.

## 5. DO-NOT-CHANGE fences

Back-link: [Entry and lifecycle](logic.md#entry-and-lifecycle).

- `render_id`, `item_hashes`, `canonical_json` (`render_spec.py:172-200`): exports and pins depend on their exact output.
- The payload and `logic.md` produced when no comparison loads: the golden tests pin them.
- `EXPORT_KIND`, `validate_export_shape`, `isDecisionExport`, `isReviewState`, `bootstrap`, the `quirk-logic-spec:${slug}` key and `persist`: every signed and in-flight stage 1-2 export depends on them.
- `tests/fixtures/interactive/v2/stage2/logic.json` `views.stateMachine`: `app/scripts/check-layout.ts` imports it.
- The `#v1-specs-are-read-only` heading in `interactive-logic-spec.md`: `tests/test_writing_specs_skill.py` resolves an inbound link to it.

## 6. Always / Ask / Never

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **Always:** keep the stage 1-2 payload and `logic.md` byte-identical when no comparison loads; mirror every validation rule between Python and the TS type guard; rebuild and commit `review-template.html` with any app change; keep fixtures synthetic.
- **Ask:** before changing any fenced region; before adding a dependency to `app/package.json`; before changing exit codes of existing subcommands.
- **Never:** put HTML or SVG strings in `comparison.json`; let stage 3 write `logic.json`; add weights or totals; commit private or customer content (quirk is public).

## 7. Testing strategy

Back-link: [Decisions Locked](logic.md#decisions-locked).

1. **Golden masters first, before any renderer or app change.** For each case, render with the current renderer into a tmp dir named after the case (the payload embeds `slug = spec_dir.name`) and commit the outputs under `tests/fixtures/interactive/golden/<case>/`:
   - `sample` (v1): `logic.md` only; v1 never writes `review.html`.
   - `stage1`, `stage2`: `logic.md` and `payload.json`, the text between `PAYLOAD_OPEN` and `PAYLOAD_CLOSE` in `review.html`.
   - `stage2-signed`: copy `v2/stage2` into a dir named `stage2`, run `fold` with `exports/signed.json`, render, then commit the same two files.
   A test re-renders each case and byte-compares `logic.md` and the extracted payload. A second test asserts `review.html == template.replace(PAYLOAD_PLACEHOLDER, PAYLOAD_OPEN + payload + PAYLOAD_CLOSE)`, which proves the renderer adds nothing else and survives template rebuilds. No golden is ever re-blessed.
2. **Fixture.** `tests/fixtures/interactive/v2/compare/` holds a committed signed stage-2 `logic.json` (the stage2 fixture folded with `signed.json`) and a synthetic `comparison.json` with three invented approaches covering every schema field, a finding of each type, a check, a held and a revised history entry, a stale `requirementHash`, and guidance. `invalid/` holds one `comparison.json` per validation error.
3. **Python (`tests/test_compare_stage.py`):** each invalid fixture exits 1 with a pointer; the unsigned-spec warning; render embeds `comparison` and `comparisonId` and leaves `renderId` unchanged; stage-3 `check-export` (valid, stale comparison id, wrong slug, bad shape); `fold` and `reapprove` refuse the stage-3 kind with exit 2; `challenges` text and `--json` output, including `target changed`; `targetHash` matches a fixed known value.
4. **App:** `pnpm run check` passes (typecheck, layout-check, template-check), plus new `check-compare` that imports the fixture `comparison.json`, asserts `isComparison` accepts it, rejects each invalid fixture, and asserts the TS `targetHash` equals the Python fixed value.
5. **Visual:** render the compare fixture and screenshot every stage-3 tab in light and dark at 1280 and 390 wide; check for overflow and label collisions.

`COMMAND:`
```
pytest -q
cd skills/writing-specs/interactive/app && pnpm install --frozen-lockfile && pnpm run build && pnpm run check
```

## 8. Docs

Back-link: [Decisions Locked](logic.md#decisions-locked).

New `skills/writing-specs/comparison-schema.md` carries the §2 schema, the hashed-content rule and the point map, since it ships with the plugin and this spec does not. `interactive-logic-spec.md` gains a "Stage 3: compare approaches" section after "Final sign-off and fold": when to use it, a link to `comparison-schema.md`, the round loop with `check-export` and `challenges`, and the new exit-code meanings (stage-3 `check-export` 3 = comparison changed; `fold`/`reapprove` 2 = stage-3 export). The command list at `:28-36` adds `challenges`.

## 9. Cross-cutting

Back-link: [Data flow](logic.md#data-flow).

- **Security:** all comparison text renders as text; `specMarkdown` goes through Astryx `Markdown` with `OFFLINE_MARKDOWN_COMPONENTS` (no images, no raw HTML); the payload `<` escaping at `render_spec.py:2410` already covers the new keys.
- **Size:** embedded specs can add hundreds of KB to `review.html`; no limit is enforced.
- **Rollback:** deleting `comparison.json` and re-rendering returns the page to stage 1-2 exactly.

## 10. Non-goals

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

A stage-3 fold or any write to `logic.json`; `find-export` support for stage-3 exports (the coordinator passes the path); dispatching challenges to proponents; parsing tech-spec markdown; weights or totals; the deferred glossary, CODEOWNERS, and leaning ideas.
