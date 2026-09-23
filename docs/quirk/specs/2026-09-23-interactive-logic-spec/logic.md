# Interactive Logic Spec — logic spec

## Status & amendments

**Status:** Draft — awaiting user review

**Amendments:** none

## Purpose

A logic spec is approved by a human reading prose and saying "looks good" in chat, the gate most
exposed to rubber-stamping, and the risk grows as Claude's specs get more polished. The ultracode
spec in Orca proved a better gate: an interactive review page where the reviewer makes their own
call on everything Claude added, rules on every assumption, and signs only when explicit gates pass.
That page took a bespoke ~3.8k-line app and eleven feedback rounds. This change makes it a spec
*type* quirk can produce for any brainstorm, from data alone, in seconds.

## Conceptual model

An **interactive logic spec** is a logic spec whose source of truth is `logic.json` instead of
hand-written markdown. It is a second format for the same rubric, not a companion to it.

`logic.json` carries every section the markdown rubric requires (Status & amendments, Purpose,
Conceptual model, Data flow, Behavior & scenarios, Decisions Locked, Industry Insights, Scope &
non-goals, Deferred Ideas, Glossary) plus the structured entities the review page acts on:

- **Requirements** — id, area, formal text, plain summary and detail, scope (in / out), Claude's
  group (Minimum, Impact 3 / 2 / 1), provenance (you chose it / you took the recommendation /
  Claude added it), certainty (Confirmed / Assumed / Unverified), depends-on, Claude's rationale.
- **Assumptions** — claim, basis, plain meaning, what breaks if wrong, requirements resting on it,
  how to check it and what that costs.
- **Blind spots** — title, detail, sources.
- **Scenarios** — Given / When / Then with alternative outcomes. These *are* the spec's Behavior &
  scenarios.
- **Conflicts** — pairs of requirements that contradict each other.
- **Optional view data** — states and transitions; journey steps.

Plain-language copy is written by Claude and tagged as Claude-written.

The spec folder holds:

| File | Origin | Committed |
|------|--------|-----------|
| `logic.json` | Claude writes it; the source of truth | yes |
| `logic.md` | generated from `logic.json`, marked "generated — do not edit" | yes |
| `review.html` | quirk's prebuilt page with this spec's data embedded | no |
| decision exports | the reviewer downloads or copies them from the page | no |

Consumers: the human approving the spec (the page), Claude (reads exports, revises, folds back),
and the downstream skills — `tech.md` authoring, `quirk:writing-plans`, and the execution skills —
which keep reading `logic.md` unchanged.

## Data flow

Brainstorming produces an approved design → Claude writes `logic.json` → a schema check rejects a
malformed file before any page exists → the renderer embeds the data into quirk's prebuilt page and
generates `logic.md` → the reviewer works in the page → an export (download or copy) carries their
decisions, notes, and requests back to Claude, stamped with the render it came from → Claude
revises `logic.json` and re-renders with the reviewer's decisions embedded → on a signed export,
Claude folds the decision record into `logic.json`, marks it Approved, regenerates `logic.md`, and
commits both.

## Behavior & scenarios

1. **Offered once.** After the design is approved, brainstorming asks one question: markdown logic
   spec or interactive logic spec. Markdown is the default; nothing else changes for markdown.
2. **Produced.** On interactive, Claude writes `logic.json`, validates it, renders `review.html` and
   `logic.md`, and opens the page. No Node, package install, or build runs at spec time.
3. **Queue.** Items the reviewer decided during brainstorming are pre-placed with their answer.
   Items Claude added without asking wait in "Awaiting your call", each showing Claude's
   recommendation with nothing preselected; the reviewer must make the selection.
4. **Scope board.** Every item is in scope, conditionally in scope (no extra code / under 10 lines /
   under 30 lines), or out of scope. Moving an item out warns with its direct and indirect
   dependents. Any change from where it was placed needs a written reason.
5. **Risks.** Every assumption needs a ruling: build on it, verify first, or wrong. Every blind spot
   is accepted only with a sentence in the reviewer's own words, and may carry a research request
   to Claude; Claude's findings appear on the blind spot once answered.
6. **Scenarios.** Each scenario is approved individually; there is no approve-all. The Then column
   offers the spec's outcome, Claude's alternatives, or free text. The reviewer can request a new
   scenario, which shows as pending until Claude converts it.
7. **Feedback round.** An unsigned export carries decisions, notes, and requests. The reviewer tells
   Claude in chat; Claude answers requests, revises `logic.json`, and re-renders. Unchanged items
   keep the reviewer's calls; changed or new items return to the queue flagged "changed since you
   reviewed". An export stamped with an older render is refused.
8. **Sign-off.** Signing requires six gates: every Claude-added item placed; every assumption ruled
   on; every blind spot accepted in the reviewer's words; every scenario approved with no pending
   requests; a reason for every scope change; no unresolved conflicts or orphans. Any edit after
   signing voids the signature.
9. **Signing is the approval.** On a signed export Claude folds the decision record — scope moves
   with reasons, conditions, assumption rulings, blind-spot acceptances, scenario outcomes — into
   `logic.json`, sets Status to Approved, regenerates `logic.md`, commits both, and hands off to
   execution with no second chat approval. Folding the signed decisions is not an edit after
   signing.
10. **Hand-off paths.** The page offers **Download decisions** and **Copy decisions**. When the
    clipboard is blocked, Copy says so and points to Download. Claude looks for a downloaded export
    in the spec folder, then the downloads folder.
11. **Lost browser state.** The page keeps progress in browser storage when it can. Because storage
    for pages opened from disk is unreliable, every re-render embeds the reviewer's last export, an
    **Import decisions** button restores from a saved export, and when storage is unavailable the
    page says so and prompts an export before closing.
12. **Optional views.** Each appears only when the spec has its data: **Coverage** when in-scope
    requirements lack a scenario or assumptions / blind spots are open (informational, each gap
    linked to the tab that closes it); **Impact × certainty** heatmap when requirements carry
    certainty; **Story map** when journey steps exist; **State machine** when states and
    transitions exist, laid out from the data, with clickable transitions and blind-spot chips.
13. **UI feedback.** A change the reviewer asks for to the page itself lands in quirk's shared page,
    so future specs get it; the current spec is re-rendered with it.
14. **Amendment after approval.** A later change to a locked decision is a dated amendment in
    `logic.json`, approved in chat; `logic.md` and the page are regenerated with no re-review.

## Decisions Locked

**Format**
- Replaces `logic.md` as the source for that spec; `logic.json` is authoritative, `logic.md` is a
  generated read-only rendering.
- Produced only on request: brainstorming offers it once at the spec-writing step; markdown is the
  default.

**Build**
- Generic core plus data-driven optional views; no per-spec code.
- quirk ships one prebuilt single-file page; Claude only injects spec data. No build at spec time.
- UI feedback changes the shared page, not one spec.
- Claude writes the plain-language copy into `logic.json`, marked Claude-written.

**Review mechanics**
- Core tabs: Scope board, Risks, Scenarios, Spec text, Sign-off.
- Claude's recommendation is shown; the reviewer must make their own selection, nothing preselected
  — only on items Claude added without asking.
- Kept: written reason for scope changes, a ruling on every assumption, blind spots accepted in the
  reviewer's words, per-scenario approval, signature voided by any later edit.
- Scope choices: in / conditionally in (no extra code, under 10 lines, under 30 lines) / out. No
  delivery tier.
- No review-behavior signals (agreement rate, time-to-sign).
- v1 optional views: Coverage, Impact × certainty, Story map, State machine — every tab in the
  ultracode example.

**Round trip**
- Local file only; no hosted artifact.
- Hand-off by download and by copy.
- Requests (research, new scenarios) are picked up when the reviewer tells Claude in chat.
- Revisions are diff-aware: unchanged items keep decisions, changed and new items return to the
  queue.
- Signing is the approval gate.

**Downstream**
- Commit `logic.json` and the generated `logic.md`; never `review.html` or exports.
- Post-approval changes are dated amendments in `logic.json`, with no re-review.
- Downstream skills keep reading `logic.md`; the amendment rule points at the source file.

**Success criteria**
- The ultracode spec, converted to `logic.json`, renders in the prebuilt page with its core tabs and
  the optional views its data supports, including the state machine.
- One end-to-end run: brainstorm → interactive spec → review → export → fold-back → signed approval
  → execution reads the generated `logic.md`.

## Industry Insights

- **Polished specs get rubber-stamped most.** Error detection falls to ~30% when a system is
  usually right versus ~75% when it visibly fails sometimes; clear AI rationales increase deference.
  Supports forcing the reviewer's own selection and required written reasons. —
  https://tianpan.co/blog/2026/06/25/approval-fatigue-how-human-in-the-loop-gates-decay-into-rubber-stamps ,
  https://atomicrobot.com/blog/ai-review-fatigue/
- **Zero-friction approval is the anti-pattern;** required written pushback exposes habit versus
  judgment. — https://medium.com/@adnanmasood/the-unbearable-lightness-of-clicking-approve-af8d2ceb25fb
- **Schema-driven rendering beats bespoke per-spec UI:** a generic renderer over a flat JSON of
  requirements, assumptions, and decisions removes per-spec UI code; traceable registers carry id,
  origin, and confirmation state. — https://json-render.dev/ ,
  https://github.com/Kharrthik/SpecForge/issues/34
- **Browser storage on `file://` is unreliable:** MDN says file-URL storage handling may change;
  Safari can throw on access. Hence embedding the last export and an Import button. —
  https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage
- **Downloads land in the downloads folder** and Firefox suffixes duplicates (`(1)`); the File
  System Access save picker is Chromium-only, so it cannot be the primary path. —
  https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker
- **Clipboard hand-off risks:** the async clipboard API needs a secure context and may be blocked on
  `file://`; large pastes into chat can truncate silently. Hence Copy degrades to Download. —
  https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText
- **A local write-back server was rejected:** orphaned background processes, port conflicts, and
  localhost CSRF / DNS-rebinding exposure on a write endpoint. —
  https://docs.python.org/3/library/security_warnings.html
- **Prior art in this workspace:** the ultracode review app's build history and anti-rubber-stamping
  principles, `docs/quirk/specs/2026-09-23-claude-ultracode-effort/review-app-history.md` in the
  Orca checkout.

## Scope & non-goals

- No claude.ai Artifact hosting or live database.
- No local review server.
- No review-behavior signals.
- No delivery tier.
- No per-spec custom page code.
- `review.html` and decision exports are never committed.
- No interactive `tech.md`.
- No conversion of existing markdown specs.
- The ultracode bespoke app is not migrated or retired; it is test data only.

## Deferred Ideas

- Artifact hosting as an optional second delivery path, for live two-way requests.
- Review-behavior signals in the decision record (agreement rate, time-to-sign).
- Converting an existing markdown `logic.md` into an interactive spec.
- `[tech-spec]` Where the page source lives in quirk, how its prebuilt build is produced and kept in
  sync, and how an Astryx single-file bundle is carried in the plugin.
- `[tech-spec]` The `logic.json` schema and its validator.
- `[tech-spec]` The renderer (python3): data embedding and `logic.md` generation.
- `[tech-spec]` State-machine automatic layout that meets the diagram-design rules without
  hand-placed coordinates.
- `[tech-spec]` Export filename, render version stamp, discovery order, and the per-spec storage key.
- `[tech-spec]` Edits to `quirk:brainstorming` and `quirk:writing-specs` (new rubric file, hub table,
  amendment rule).

## Glossary

- **Interactive logic spec** — a logic spec whose source is `logic.json`, reviewed through a
  generated page instead of in chat.
- **Prebuilt page** — the single-file review app quirk ships; each spec's `review.html` is this page
  with the spec's data embedded.
- **Render** — one generation of `review.html` and `logic.md` from `logic.json`; each is stamped so
  exports can be matched to it.
- **Export** — the decisions, notes, and requests the reviewer downloads or copies from the page.
- **Claude-added item** — a requirement Claude included without the reviewer answering a question
  about it; the only items that enter the queue.
- **Claude's group** — Claude's proposed placement: Minimum, or Impact 3 / 2 / 1.
- **Conditionally in scope** — in scope only if it costs no extra code, under 10 lines, or under 30
  lines.
- **Gate** — one of six conditions that must hold before the reviewer can sign.
- **Fold-back** — Claude applying a signed export's decision record to `logic.json`.
- **Optional view** — a tab that appears only when the spec has the data it needs.
