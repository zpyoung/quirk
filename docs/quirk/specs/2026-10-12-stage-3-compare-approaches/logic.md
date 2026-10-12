# Stage 3 — compare approaches

## Status & amendments

**Status:** Approved — Tech spec: requested

**Amendments:** none yet.

## Purpose

After stage 2 is signed, a spec often has several competing ways to build it, each written up by a proponent who argues for it and scores its own coverage. Today the reviewer has to read every tech spec end to end and build the comparison in their head. Stage 3 puts that comparison into the review page: what each approach is, where they differ, what each costs and touches, how much of each claim has been checked, and a clearly labeled recommendation. The reviewer can push back on specific claims and see the proponents' answers in the next round. Picking an approach still happens outside the page.

The design was approved against a mockup built from a private project's comparison, which is kept out of this repo. A synthetic stage-3 fixture with invented approaches replaces it here; the tech spec defines it.

## Conceptual model

- **Approach** — one way to build the spec, with a tech spec written by its **proponent**. A comparison holds 2 to 5 approaches.
- **Coordinator** — Claude in the role that builds the comparison, adds checks, findings, pairings and guidance, and routes challenges.
- **Comparison** — `comparison.json` beside `logic.json`, written by the coordinator from the tech specs. It is the only input stage 3 reads besides the signed spec.
- **Score** — a proponent's verdict on one in-scope requirement: `met`, `met with workaround`, `very hard` or `not met`, an optional qualifier (for example `v1 scope`), the proponent's own wording, a note and citations. Every score records the hash of the requirement text it was scored against.
- **Check** — a coordinator mark that a score was verified, saying what was checked. A score without one reads as claimed.
- **Finding** — a coordinator marker on a score: `disputes` or `same score, different design`. A finding names a requirement, a citation and a consequence, and never a preference. A **pairing** links risks from different approaches that share an exposure.
- **Slice** — a unit of a proponent's plan with its own size label, a band (`v1`, `fast-follow`, `optional`), and per-repo line estimates. Size labels map to points: S 2, M 3, L 5, XL 8, with in-between labels as ranges (S-M 2-3, L-XL 5-8).
- **Guidance** — the coordinator's mentor-style walkthrough and recommendation. It is the only place on the page where the coordinator states a preference.
- **Challenge** — the reviewer's note plus the score or size they think is right, aimed at one score or one slice size.
- **Round** — one export of challenges and stars, then a regenerated comparison that answers them.

Stage 3 never edits `logic.json`. It has no gates, no signature and no fold.

## Data flow

1. The coordinator writes `comparison.json` from the approach tech specs. Proponents supply the parts they own: scores, slices with sizes and line estimates, risks, rival claims, flowchart boxes against fixed stages, and a worked-example trace for a scenario the coordinator picks. The coordinator adds checks, findings, pairings, the design-choices table, its overview of each approach, and guidance.
2. `render_spec.py render` validates the comparison, embeds it in `review.html` with its own comparison id, and leaves stages 1 and 2 byte-identical.
3. The reviewer reads stage 3, stars must-haves, and drafts challenges, all kept in browser storage. When ready they export. The export carries challenges and stars.
4. The coordinator checks the export and prints the challenges grouped by approach, then sends each group to its proponent.
5. Each proponent revises or holds the score in its tech spec and writes a reply.
6. The coordinator regenerates `comparison.json` with the new scores, the replies and the challenges they answer, rewrites the guidance with a note on what changed its mind, and re-renders.

## Behavior & scenarios

### Entry and lifecycle

1. A signed spec with a valid `comparison.json` renders with a three-step stepper and opens on the Guidance tab. Stage 1 and stage 2 tabs follow the stage-3 tabs, read-only.
2. A spec with no `comparison.json` renders exactly as today.
3. A `comparison.json` beside an unsigned spec renders stages 1 and 2 as normal, and the render warns that stage 3 waits for stage-2 sign-off.
4. An invalid `comparison.json` fails the render and names the problem. Invalid means: fewer than 2 or more than 5 approaches, a missing score for an in-scope requirement, an unknown requirement id, a score off the four-value scale, a finding without a citation, or a size label outside the point map.
5. A missing optional part (line estimates, flowchart boxes, worked example) renders as "not provided". Missing guidance hides the Guidance tab and the page opens on Overview.

### Guidance tab

6. The tab walks through four steps: what doesn't separate the approaches, where the data lives, why effort shouldn't decide it, and the risks nobody scored. Each step links to the tab that shows it. Then come questions for the reviewer, the recommendation, and a "Before you decide" list of suggested challenges.
7. The recommendation shows the pick, a confidence level with its reason (including how many scores are checked), why, what it costs, and what would change the coordinator's mind.
8. A live note under the recommendation reacts to the reviewer's view: starred requirements the pick doesn't fully meet, conditional requirements left out, or a two-way focus that excludes the pick.
9. "Draft these" turns the suggested challenges into editable drafts.

### Overview tab

10. One card per approach shows: a coverage bar with icon counts, v1 effort in points, slice count, disputed-finding count, "Your must-haves" (misses N of M starred, named, or meets all), and evidence (scores checked out of total, unverified assumptions).
11. The matrix shows one row per in-scope requirement, grouped by area. By default it shows rows where scores differ, rows no approach fully meets, and rows with a finding. "+ N requirements all three meet" expands the rest. Cells are icon chips (✓ ◐ ▲ ✕ on the status colors) with the label on hover; markers show ⚑ disputes, ≠ same score different design, and · checked.
12. Clicking a row opens a side drawer: the signed requirement text, then each approach's score, proponent wording, first sentence of the note, any check or finding, "Full note and citations", and "Challenge".
13. Out-of-scope requirements collapse to one line. A conditional requirement is a normal row with a badge.
14. The design-choices table ("Same question, N answers") sits at the bottom: one row per design decision, one short answer per approach.

### Approaches tab

15. Pills switch between approaches. Each shows: the coordinator's three-sentence overview, the proponent's worked-example trace, repos touched with file counts, a process flow across fixed stages with each box tagged new / changed / reused, a runtime sequence diagram, a schema diagram, the deploy order (stated, implied or not stated), "Rests on", "Undo and evolve", and the full tech spec rendered as markdown in a collapsed section.
16. Diagrams follow diagram-design's rules (right-angle connectors, masked labels, bottom legend, at most one or two accent elements, 5 lifelines and 12 messages at most in a sequence, 5 tables and 6 foreign keys at most in a schema) and use the page theme in light and dark.

### Effort and Blast radius tabs

17. Effort shows one bar per approach whose segments are slices sized by points: solid for v1, hatched for fast-follow, dashed for optional, with the slice named on hover. Beside each bar: v1 points and the critical path, or "not stated". Gaps are called out inline, such as a missing verification slice or a slice counted in a different band. A work-area table sits behind a disclosure.
18. Blast radius shows, per approach: MRs and lines in total and per repo, files touched per repo, schema changes, hot paths touched, and deploy order. MRs are counted per slice per repo as ceil(lines / 500); slices are never merged.

### Trade-offs tab

19. Key differences come first, then the coordinator's "same exposure" pairings, then each approach's risks as short coordinator headlines with the proponent's words on hover, then rival claims grouped by target ("B on A") behind a disclosure labeled as advocacy.

### Cross-tab controls

20. A strip under the tabs holds the focus picker (all, or any pair) and the conditional-requirements toggle. A pair focus reduces every tab to the two approaches and to where they differ. Leaving conditional requirements out removes them from the matrix, counts and cards.
21. Stars mark must-haves from the matrix or the drawer. They are a view, not a score: there are no weights and no totals.

### Challenges and rounds

22. A challenge on a score or a slice size carries a note and the wanted value. Drafts live in browser storage. The bottom tray shows the draft count, the "needs another look" count, and Export.
23. Export writes a stage-3 export with its own kind, the comparison id, the challenges and the stars. It has no signature.
24. `check-export` validates a stage-3 export and exits 3 if the comparison changed since. A stage-2 export loaded into a stage-3 page, or the reverse, is rejected by kind.
25. A new command prints the challenges grouped by approach, ready to route.
26. After regeneration, an answered cell shows "revised after challenge" or "held after challenge". The expand shows the old score, the reviewer's note and the proponent's reply, and a held score can be challenged again.
27. A requirement whose signed text changed after scoring shows "scored against older text" on its cells, with the diff on expand. An approach whose spec changed outside a challenge shows "revised since your last export", with its changed rows highlighted. Each approach header shows its anchor commits and read date, and flags a mismatch.
28. Drafts aimed at a score that is unchanged after regeneration stay put. Drafts aimed at a changed score move to "needs another look" and are never re-aimed silently. A star on a requirement that no longer exists is dropped with a note.

## Decisions Locked

**Placement**
- Stage 3 lives in the shared writing-specs app and `render_spec.py`, as a real third stage in the same single-file page. It is not a view inside stage 2 and not a separate page.
- It appears automatically when the spec is signed and a comparison exists. `logic.json` stays untouched.
- Stage-3 tabs, in order: Guidance, Overview, Approaches, Effort, Blast radius, Trade-offs. Then the stage 1-2 tabs, read-only. The page opens on Guidance.

**Data**
- Data comes from a structured `comparison.json` written by the coordinator, not parsed from tech-spec markdown.
- Stage 3 has its own export kind, its own comparison id, and its own browser-storage slot. The stage 1-2 renderId, exports and storage are unchanged.

**Matrix and scores**
- Layout: table with a side drawer for detail, grouped by area, horizontal scroll with a sticky requirement column on narrow screens.
- Default rows: differences, plus rows no approach fully meets, plus rows with a finding.
- Fixed four-value scale with an optional qualifier; proponent wording on expand.
- Only coordinator-verified scores carry "checked"; everything else reads as claimed.
- No totals. Counts are split between the minimum group and increments, plus a named "not fully met" list.

**Coordinator voice**
- A proponent's score always stays visible. A coordinator finding sits beside it and never replaces it.
- Findings are strictly factual. Opinion lives only on the Guidance tab, labeled as the coordinator's.
- Risks stay verbatim in each approach's column, with coordinator pairings and coordinator-written headlines marked as such.
- Rival claims are shown, labeled as advocacy.

**Effort and blast radius**
- Points, not weeks, mapped from each proponent's own size labels. No coordinator re-sizing and no coordinator estimates.
- Three bands (v1, fast-follow, optional), each tallied separately. The critical path is shown only where a proponent states one.
- Line estimates come from proponents, per slice per repo. MRs are counted per slice per repo at under 500 lines.
- Blast radius also shows schema changes, hot paths touched and deploy order.

**Approaches tab**
- The overview is written by the coordinator: neutral, three sentences. The full spec is embedded and rendered, not linked.
- Flowchart boxes are filled by proponents against fixed stages the coordinator defines per spec.
- Diagrams use diagram-design rules in the page theme. Schemas are database-schema diagrams.
- Worked examples sit in each approach's own sub-tab; proponents write them for a scenario the coordinator picks.

**Challenges**
- Targets are scores and slice sizes. A challenge carries a note and the wanted value.
- After an answer: "revised after challenge" or "held after challenge", with the trail on expand. A held score can be challenged again.
- Export whenever; no gates and no signature.

**Decision aids**
- Must-have stars, a conditional-requirements toggle, two-way focus, and evidence strength on every card.
- Stars travel in the export.
- Guidance is rewritten every round with a note on what changed the coordinator's mind. Suggested challenges have a "Draft these" button.

**Drift**
- Cells scored against older requirement text are marked, with a diff.
- Drafts survive regeneration only if their target score is unchanged.
- Out-of-challenge spec revisions are flagged per approach.
- Anchor commits and read dates are shown per approach, with mismatches flagged.

**Edge cases**
- With an unsigned spec, render warns and skips stage 3.
- A comparison holds 2 to 5 approaches.
- Missing optional parts render as "not provided"; only scores are required.

**Done means**
- The feature is on a quirk branch with tests, and stage 1-2 rendering is byte-identical under golden-master tests written before any change.
- A synthetic stage-3 fixture renders every tab, control and diagram described here.
- Coordinator tooling: comparison validation, stage-3 `check-export`, and challenges grouped by approach.
- Docs: a stage-3 and `comparison.json` section in `interactive-logic-spec.md`.

## Scope & non-goals

**In scope**
- `render_spec.py`: comparison schema and validation, embedding, comparison id, stage-3 export kind, `check-export` support, and a challenges-by-approach command.
- The review app's stage-3 tabs, controls, drawer, challenge drafts and export, and the diagram components.
- Golden-master tests for stages 1-2, Python tests for the new commands and validation, and `pnpm run check` passing.
- Docs in `interactive-logic-spec.md`.
- A synthetic stage-3 fixture (`comparison.json` beside a signed stage-2 `logic.json`) with three invented approaches, used by the tests and as the visual reference.

**Non-goals**
- Picking or signing an approach; any stage-3 fold.
- Automatically dispatching challenges to proponent sessions.
- Documenting the multi-proponent workflow (briefs, stances, update briefs).
- Weighted scores or totals.
- Parsing tech-spec markdown automatically.
- A quirk release, push or PR without asking first.

## Industry Insights

- Comparison tables work best with options as columns and stay readable at 3 to 4 options. "Show only differences" is an established pattern, and identical values must be worded identically for it to work. [NN/G comparison tables](https://www.nngroup.com/articles/comparison-tables/), [NN/G mobile tables](https://www.nngroup.com/articles/mobile-tables/)
- Status must not be conveyed by color alone (WCAG 1.4.1), so every score pairs an icon and a label with its color. [W3C Understanding 1.4.1](https://www.w3.org/TR/UNDERSTANDING-WCAG20/visual-audio-contrast-without-color.html)
- Self-assessment inflates "met": judges were more than 50% more likely to wrongly mark their own output as satisfying a rubric, even on objective criteria. This is why checks are visible and unchecked scores read as claimed. [Self-Preference Bias in Rubric-Based Evaluation (arXiv 2604.06996)](https://arxiv.org/abs/2604.06996)
- Weighted totals give false precision and hide deal-breakers. Must-have gates before scoring, and sensitivity checks, are the safer pattern, hence stars and the conditional toggle instead of weights. [ASQ decision matrix](https://asq.org/quality-resources/decision-matrix), [CI Toolkit Pugh matrix](https://citoolkit.com/articles/pugh-matrix/)
- Decision records lose their value when they keep only the winner. Rejected options and their reasons are the useful part, hence rival claims, "what would change my mind", and the challenge trail. [Zimmermann on ADR anti-patterns](https://ozimmer.ch/practices/2023/04/03/ADRCreation.html)
- Signed records should stay frozen, with later annotations kept as separate, linked records. This is why stage 3 has its own export kind instead of riding in the signed stage-2 export. [Azure ADR guidance](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record), [Gerrit review labels](https://gerrit-review.googlesource.com/Documentation/config-labels.html)
- vite-plugin-singlefile cannot emit two HTML pages from one build, and `file://` localStorage behavior varies by browser. That ruled out a separate compare page. [vite-plugin-singlefile #51](https://github.com/richardtallent/vite-plugin-singlefile/issues/51), [MDN localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)

## Deferred Ideas

- A hover glossary for codebase terms in overviews and diagrams.
- Owning teams per repo from CODEOWNERS in Blast radius.
- Recording a leaning and its reason in the export, without a signature.
- Hyphen-free wrapping of long code identifiers inside diagram boxes.

## Glossary

- **renderId** — the hash of `logic.json` that stamps a rendered page and its exports; a mismatch makes an export stale.
- **Comparison id** — the equivalent hash for `comparison.json`, used only by stage-3 exports.
- **Golden-master test** — a test that records today's output and fails on any difference, used here to prove stages 1 and 2 are unchanged.
- **Point map** — S 2, M 3, L 5, XL 8; in-between labels become ranges.
