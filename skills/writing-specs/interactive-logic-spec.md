# Writing an Interactive Logic Spec

Use this rubric only when the user chose the interactive format at brainstorming's spec-writing step. Brainstorming offers the choice once; markdown remains the default and follows [logic-spec.md](logic-spec.md). An interactive spec is an alternative source for the same logic spec, not a companion document. This rubric follows the approved [Behavior & scenarios](../../docs/quirk/specs/2026-09-23-interactive-logic-spec/logic.md#behavior--scenarios) and [Decisions Locked](../../docs/quirk/specs/2026-09-23-interactive-logic-spec/logic.md#decisions-locked) contracts.

## When to use

The user explicitly chose interactive when brainstorming offered markdown (the default) or interactive. Do not offer the format again or change an existing markdown spec to interactive. Follow [Where the specs live](SKILL.md#where-the-specs-live) for the user's chosen location; an interactive spec has `logic.json` as its source of truth and a generated `logic.md` beside it.

## What to write

Write `<spec-dir>/logic.json` using the exact `LogicSpec` shape in [Data models / schemas](../../docs/quirk/specs/2026-09-23-interactive-logic-spec/tech.md#data-models--schemas) and the page's [TypeScript source of truth](interactive/app/src/spec-types.ts). The renderer validates that same shape. Include every section required by [logic-spec.md](logic-spec.md)—Status & amendments, Purpose, Conceptual model, Data flow, Behavior & scenarios, Decisions Locked, Industry Insights, Scope & non-goals, Deferred Ideas, and Glossary—plus structured requirements, conflicts, assumptions, blind spots, scenarios, research, and any optional view data supported by the schema. Use `schemaVersion: 1`.

Every requirement must carry its `provenance`; requirements not decided by the user need the corresponding question, and Claude-added requirements need Claude's rationale. Claude writes every plain-language field. Scenarios are the structured form of Behavior & scenarios. Keep all IDs unique and every cross-reference resolvable. The `logic-spec.md` section definitions remain authoritative; do not invent a second set of meanings for shared sections.

Never hand-write or edit `logic.md` for an interactive spec: it is generated from `logic.json` and is read-only. The renderer also creates the local `review.html` and `.gitignore`. `review.html` and decision exports are not committed; after approval, commit `logic.json` and generated `logic.md`.

## The render loop

Use the `render_spec.py` script shipped with `quirk:writing-specs` (Python 3.9+, standard library only). Its CLI contract is:

```text
render_spec.py validate     <spec-dir>
render_spec.py render       <spec-dir> [--prior <export.json>] [--open]
render_spec.py find-export  <spec-dir> [--downloads <dir>]
render_spec.py check-export <spec-dir> <export.json>
render_spec.py fold         <spec-dir> <export.json> [--tech-spec-requested]
```

`<spec-dir>` contains `logic.json`; its basename is the spec `slug`. Before opening a review, run `validate`, then `render --open`. After every edit to `logic.json`, validate and re-render; `render` runs validation itself, writes `review.html`, `logic.md`, and `.gitignore`, and prints the current `renderId`. It is deterministic for identical input. Do not install packages, build the page, or use a network path at spec time: the page is a local file and the renderer embeds the data in the prebuilt template.

`validate` exits 0 for valid input and 1 for invalid schema or references. For export commands, exit 0 means success, 1 invalid input, 2 usage error, 3 stale render or wrong slug, 4 (fold only) unsigned export or a failed gate, and 5 (find-export only) no export found. Invalid-input diagnostics and failed fold gates are reported on stderr. Never work around an invalid or stale result by applying its decisions directly.

## The feedback round

When the reviewer says they exported decisions, first locate and check the export:

```text
render_spec.py find-export <spec-dir> [--downloads <dir>]
render_spec.py check-export <spec-dir> <export.json>
```

`find-export` searches the spec folder and `~/Downloads` (or the `--downloads` directory) together; it prints the absolute path of the newest matching export by its `exportedAt` value, preferring one from the current render over any stale one. If the reviewer pasted Copy into chat, save that JSON in the spec folder as `<slug>-decisions-<YYYYMMDDTHHMMSS>.json` (the ignored export name) and pass its path to `check-export`. The check prints `signed` or `unsigned`: proceed only when it exits 0. A stale or wrong-slug export is refused; render the current source and ask for an export from that review instead.

For a current **unsigned** export:

1. Answer its research requests in `research[]`, retaining each request ID and blind-spot ID; add the answer and timestamp.
2. Convert scenario requests into `scenarios[]`, retaining each request ID.
3. Apply the reviewer's requested content changes to `logic.json`.
4. Do **not** write unsigned scope decisions or other review-state choices into `logic.json`; they travel in the export and are carried into the next page review.
5. Re-render with the checked export so unchanged decisions carry over and changed or new items return to the review queue:

   ```text
   render_spec.py render <spec-dir> --prior <export.json>
   ```

   Open the new `review.html` for the reviewer. The `--prior` export may now have an older render ID because the source changed; that is the intended carry-over path. Never fold a stale or unsigned export.

If the source did not change, still use the renderer to produce the review with the prior export embedded. The page's import and storage mechanisms are recovery aids; the export is the durable hand-off record.

## Sign-off

A signed export is the approval; there is no second chat approval. Signing is permitted only when all six gates pass: every Claude-added requirement has a placement; every assumption has a ruling (with a note unless it is `build-on`); every active blind spot is accepted with a non-empty sentence in the reviewer's own words; every scenario is approved and no scenario request is pending; every changed scope placement has a reason; and there are no scope warnings, unresolved conflicts, or orphans. Any page update after signing clears the signature.

Run `check-export` first and fold only a current signed export. The renderer re-checks the gates in Python; do not bypass a failed gate. Then run:

```text
render_spec.py fold <spec-dir> <export.json> [--tech-spec-requested]
render_spec.py render <spec-dir>
```

Pass `--tech-spec-requested` when the user asked for a tech spec. `fold` writes the signed decisions to `logic.json`, marks it Approved (or `Approved — Tech spec: requested`), records sign-off, and renders the generated `logic.md`; the explicit `render` leaves the final outputs current. Commit `logic.json` and `logic.md`, not `review.html` or exports. Hand off to [subagent-driven-development](../subagent-driven-development/SKILL.md) or [executing-plans](../executing-plans/SKILL.md); downstream execution continues from the generated `logic.md` without asking for another approval.

## UI feedback

A requested change to the review page belongs in the shared `interactive/app/` source, not in a spec-specific page. From `skills/writing-specs/interactive/app/`, rebuild the committed template with:

```sh
pnpm install --frozen-lockfile && pnpm run check && pnpm run build
```

The build emits `../review-template.html`. Then re-render the current spec with `render_spec.py render <spec-dir>` so its `review.html` uses the rebuilt template. This build is for shared page changes, never part of ordinary spec authoring.

## Amendments after approval

For a later, user-approved change to a locked decision, add an entry with a `YYYY-MM-DD` `date` and `text` to `logic.json`'s `amendments` array, then update the source content. Regenerate the outputs with:

```text
render_spec.py validate <spec-dir>
render_spec.py render <spec-dir>
```

Do not edit generated `logic.md`. The chat approval and dated amendment are sufficient; do not send the spec through page review again.

## Self-review

Run the four [logic-spec.md self-review checks](logic-spec.md#logic-spec-self-review) against `logic.json`: scan for placeholders or incomplete sections; check internal consistency; check scope; and remove ambiguity. Also confirm every `dependsOn`, `affects`, `sources`, `refs`, `reqs`, and `resolvedBy` ID resolves. Run `render_spec.py validate <spec-dir>`; it checks the schema, unique IDs, all cross-references, and distinct requirement IDs in every `conflicts` pair. Fix all failures before rendering or hand-off.
