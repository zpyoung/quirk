<!-- generated from logic.json by render_spec.py — do not edit -->

# Interactive Logic Spec v2 — scenario-first two-stage review

## Status & amendments

**Status:** Approved

**Amendments:**
none

## Purpose

v1's review page asks the reviewer to rule on requirements Claude phrased. Polished, abstract requirement text is exactly where rubber-stamping happens, and nothing ties a requirement back to anything the reviewer agreed to. v2 fixes both problems equally: the reviewer first signs what should happen, as concrete scenarios under named behaviors plus a short constraints list, and only then sees requirements, each derived from and traced to something already signed. Human judgment lands on concrete examples, where it is most reliable, and every requirement has an accountable origin.

## Conceptual model

A **v2 interactive logic spec** is still one `logic.json`, now `schemaVersion: 2`, reviewed in two stages recorded in the file.

**Stage 1 — what should happen.**
- **Behaviors** — a named one-line rule.
- **Scenarios** — Given / When / Then with alternatives, each belonging to exactly one behavior; at most three key examples per behavior before each extra needs Claude's reason.
- **Constraints** — non-behavioral requirements drawn from Decisions Locked and scope: placement, verification, naming, non-goals.
- Scenarios and constraints carry **provenance**; Claude-added ones form the queue, with Claude's pick preselected and marked Claude-added.
- **Assumptions** and **blind spots** reference scenario and constraint ids; a blind spot is resolved by a scenario or constraint, or accepted in the reviewer's words.
- **Research** findings, as in v1.

**Stage 2 — what to build.** **Requirements** Claude derives after stage 1 is signed: v1's fields without provenance, plus `derivedFrom` — one or more approved scenario or constraint ids. Group, certainty, conflicts, and the optional views work as in v1.

**Stage record.** A stage marker; after stage 1 folds, a **stage-1 pin** (signed-at, render, and the hash of every stage-1 item as signed); the final sign-off after stage 2.

**v1 files** stay valid but read-only: they validate, regenerate `logic.md`, and take amendments; page review, `check-export`, and `fold` refuse them.

## Data flow

The design is approved → Claude writes a stage-1 `logic.json` (no requirements) → validate and render → the reviewer works the stage-1 tabs (Behaviors & scenarios, Constraints, Risks) with v1's feedback rounds (unsigned export, Claude revises, diff-aware re-render) → the reviewer signs stage 1 → Claude folds it, locking the stage-1 items and recording the stage-1 pin → Claude derives requirements and re-renders; the page now shows the stage-2 tabs (Scope board, Coverage as a trace matrix) with the stage-1 tabs read-only → stage-2 feedback rounds, where a *derivation-wrong* dispute makes Claude re-derive and a *scenario-wrong* dispute reopens that one scenario for re-approval and withdraws requirements derived only from it → the reviewer signs stage 2 → Claude folds it, re-pins any re-approved scenarios, marks the spec Approved, regenerates `logic.md`, and commits both files.

## Behavior & scenarios

1. **SC-01**
   - **Given** The reviewer chose interactive at brainstorming's spec-writing step.
   - **When** Claude writes the spec following the interactive rubric.
   - **Then** A v2 `logic.json` with behaviors, scenarios, constraints, and risks but no requirements validates and renders, and the page opens on stage 1.
   - **Alternatives** The page opens with stage-2 tabs visible but empty.
   - Stage 1 is the only reviewable content until it is signed.
   - **Requirements** REQ-01, REQ-02, REQ-05, REQ-31

2. **SC-02**
   - **Given** A scenario Claude added without asking.
   - **When** The reviewer opens it in Behaviors & scenarios.
   - **Then** Claude's Then is preselected but marked Claude-added.
   - **Alternatives** No Then option is selected; Claude's pick is shown as a recommendation; the scenario sits under its behavior.
   - The Claude-added queue now applies to scenarios, preselected but visibly marked.
   - **Requirements** REQ-06, REQ-10

3. **SC-03**
   - **Given** A behavior with four scenarios, the fourth carrying Claude's reason.
   - **When** Claude validates and the reviewer opens the page.
   - **Then** Validation prints a warning and exits 0; the page flags the behavior and shows the reason on the fourth scenario.
   - **Alternatives** Validation fails until the fourth scenario moves to another behavior.
   - Soft limit: sprawl is visible and justified, not forbidden.
   - **Requirements** REQ-07

4. **SC-04**
   - **Given** The reviewer rejected a constraint without writing a reason.
   - **When** They open Sign-off for stage 1.
   - **Then** Signing is blocked, and the missing reason is listed with a link to the constraint.
   - Every drop and rejection needs a reason.
   - **Requirements** REQ-09, REQ-14

5. **SC-05**
   - **Given** The reviewer dropped a scenario with a reason and approved everything else.
   - **When** Stage 1 is signed and folded.
   - **Then** The dropped scenario is recorded as a non-goal, derives nothing, and is not an under-derived gap in stage 2.
   - Cutting a behavior early is final unless the reviewer reverses it.
   - **Requirements** REQ-11, REQ-19, REQ-22

6. **SC-06**
   - **Given** A blind spot Claude closed by adding a constraint.
   - **When** The reviewer approves that constraint.
   - **Then** The blind spot shows as resolved by the constraint and needs no acceptance sentence.
   - **Alternatives** The reviewer must still accept it in their own words.
   - Blind spots resolve against stage-1 items.
   - **Requirements** REQ-12, REQ-13

7. **SC-07**
   - **Given** All stage-1 gates pass.
   - **When** The reviewer signs, exports, and tells Claude.
   - **Then** Claude folds the export, records the stage-1 pin, derives requirements each with `derivedFrom`, and re-renders; the page shows the stage-2 tabs with the stage-1 tabs read-only.
   - The hand-off between stages.
   - **Requirements** REQ-15, REQ-16, REQ-17, REQ-18

8. **SC-08**
   - **Given** A derived requirement pre-placed in scope.
   - **When** The reviewer moves it out of scope.
   - **Then** The page asks for a reason and warns about the requirements that depend on it; its sources stay visible inline.
   - Stage 2 reviews scope and conditions.
   - **Requirements** REQ-20, REQ-21

9. **SC-09**
   - **Given** An approved scenario with no derived requirement and a non-goal constraint with one out-of-scope requirement.
   - **When** The reviewer opens Coverage and then Sign-off.
   - **Then** The trace matrix shows the scenario as a gap and the constraint as covered; signing is blocked until Claude derives for the scenario.
   - Under-derived items block; non-goals are covered by out-of-scope requirements.
   - **Requirements** REQ-22, REQ-23, REQ-24, REQ-32

10. **SC-10**
   - **Given** A requirement whose scenario is right but whose wording is not.
   - **When** The reviewer disputes it as derivation wrong with a reason and sends the export.
   - **Then** Claude re-derives that requirement; stage 1 and its pin are untouched.
   - Derivation errors stay in stage 2.
   - **Requirements** REQ-25

11. **SC-11**
   - **Given** A requirement whose source scenario is itself wrong, plus a second requirement derived from that scenario and another.
   - **When** The reviewer disputes the first as scenario wrong with a reason and sends the export.
   - **Then** Only that scenario reopens; the first requirement is withdrawn, the shared one is flagged changed-since-reviewed, and stage-2 signing is blocked until the revised scenario is re-approved and Claude re-derives.
   - **Alternatives** All of stage 1 reopens.
   - Reopen one scenario, not the stage.
   - **Requirements** REQ-26, REQ-27, REQ-33

12. **SC-12**
   - **Given** All stage-2 gates pass.
   - **When** The reviewer signs and Claude folds the export.
   - **Then** `logic.json` is marked Approved with any re-approved scenario re-pinned; `logic.md` is regenerated with behaviors, constraints, and derivations; both are committed and execution starts without a chat approval.
   - The final signature is the approval.
   - **Requirements** REQ-27, REQ-28, REQ-29

13. **SC-13**
   - **Given** A stage-2 page and an export from the stage-1 render.
   - **When** Claude runs `check-export`.
   - **Then** The export is refused as stale, as in v1.
   - Round-trip rules hold in both stages.
   - **Requirements** REQ-30

14. **SC-14**
   - **Given** An existing v1 `logic.json`.
   - **When** Claude validates it, renders it, then tries to fold an export against it.
   - **Then** Validation passes and `logic.md` is regenerated; the fold is refused with a message naming it a read-only v1 spec.
   - v1 specs are read-only.
   - **Requirements** REQ-03, REQ-04

## Requirements

### In scope

| ID | Area | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|
| REQ-01 | Format | An interactive spec is one `logic.json` at `schemaVersion: 2` holding both stages and a stage marker. | One file, two stages. | Stage-1 content and stage-2 requirements live in the same source file; the file records which stage it is in. | min | you-recommended |
| REQ-02 | Format | Brainstorming's spec-format question stays two-way — markdown (default) or interactive — and interactive produces v2. | Same offer; interactive means v2. | No three-way choice; single-stage review is not offered for new specs. | min | you-recommended |
| REQ-03 | Compatibility | v1 `logic.json` files still validate, regenerate `logic.md`, and accept dated amendments. | v1 specs stay readable. | Existing v1 specs keep their generated markdown current without migration. | min | you-chose |
| REQ-04 | Compatibility | Page review, `check-export`, and `fold` refuse a v1 file with a message naming it as a read-only v1 spec. | v1 review is refused clearly. | The refusal says why, so nobody mistakes it for a malformed file. | i3 | claude |
| REQ-05 | Stage 1 | Claude first writes and renders a stage-1 spec with behaviors, scenarios, constraints, assumptions, blind spots, and research, and no requirements. | Stage 1 comes first, without requirements. | The reviewer never sees requirement text before the behavior is signed. | min | you-chose |
| REQ-06 | Stage 1 | Every scenario belongs to exactly one named behavior, a one-line rule; the page shows behaviors with their key examples. | Scenarios grouped by behavior. | Mirrors Example Mapping's rules-with-examples and Gherkin's Rule keyword. | min | you-recommended |
| REQ-07 | Stage 1 | A behavior may hold more than three scenarios only if each extra carries Claude's reason; the page flags the behavior and validation warns without failing. | Soft limit of three key examples per behavior. | The reason states what the extra scenario covers that the others miss. | i3 | you-recommended |
| REQ-08 | Stage 1 | Stage 1 includes a constraints list of non-behavioral requirements drawn from Decisions Locked and scope: placement, verification, naming, non-goals. | Constraints sit beside scenarios. | Requirements a scenario cannot express still get signed in stage 1. | min | you-chose |
| REQ-09 | Stage 1 | Each constraint is approved, rewritten in the reviewer's words, or rejected with a written reason; there is no approve-all. | Constraints ruled one at a time. | A rejected constraint cannot be derived from. | min | you-recommended |
| REQ-10 | Stage 1 | Scenarios and constraints carry provenance; a Claude-added one arrives with Claude's pick preselected and marked Claude-added, and counts as decided only once the reviewer approves, rewrites, drops, or rejects it; items the reviewer decided in brainstorming arrive pre-filled. | The queue moves to stage 1, preselected but marked. | Replaces v1's requirement queue, which preselected nothing. | min | you-chose |
| REQ-11 | Stage 1 | The reviewer may drop a scenario with a written reason; it becomes a recorded non-goal and derives nothing. | Cut a behavior early. | Graded scope placement stays in stage 2. | i3 | you-recommended |
| REQ-12 | Stage 1 | Assumptions and blind spots reference scenario and constraint ids instead of requirement ids. | Risks point at stage-1 items. | Risks are ruled on before requirements exist. | min | you-chose |
| REQ-13 | Stage 1 | A blind spot is resolved by a scenario or constraint, or accepted with a sentence in the reviewer's own words. | Blind spots close in stage 1. | Claude can close a blind spot by adding a scenario or constraint the reviewer then approves. | i3 | you-recommended |
| REQ-14 | Stage 1 | Stage-1 signing requires: every Claude-added scenario and constraint decided; every scenario approved or dropped with no scenario request pending; every constraint approved, rewritten, or rejected; every assumption ruled on; every open blind spot accepted; a reason for every drop and rejection. | Stage-1 gates. | The v1 gates, restated for stage-1 items. | min | claude |
| REQ-15 | Hand-off | Claude folds a signed stage-1 export into `logic.json` before deriving requirements; the status then reads stage 1 approved. | Stage 1 is folded, then derived from. | Derivation works from a fixed, committed input rather than an export file. | min | you-recommended |
| REQ-16 | Hand-off | The stage-1 fold records a pin: signed-at, render, and the hash of every stage-1 item as signed. | Stage-1 sign-off pinned to hashes. | Makes it exact which signed items a later change or dispute touches. | min | you-recommended |
| REQ-17 | Hand-off | One page with a stage indicator: stage-2 tabs appear only after the stage-1 fold, and stage-1 tabs stay visible read-only in stage 2. | One page across both stages. | A dispute is raised from a requirement; the scenario it traces to is one click away. | min | you-recommended |
| REQ-18 | Stage 2 | Claude derives requirements after the stage-1 fold, each with `derivedFrom` naming at least one scenario or constraint. | Every requirement is traced. | Validation rejects a requirement without a derivation. | min | you-chose |
| REQ-19 | Stage 2 | `derivedFrom` may name only approved scenarios and approved or rewritten constraints, never a dropped scenario or rejected constraint. | Derive only from signed items. | Keeps cut behaviors from reappearing as requirements. | i3 | claude |
| REQ-20 | Stage 2 | Derived requirements arrive with Claude's group and placement pre-filled (in / conditional: no code, under 10, under 30 lines / out); any move needs a written reason and moving one out warns about its dependents. | Scope board with Claude's placement pre-filled. | Stage 2 reviews scope and conditions only. | min | you-recommended |
| REQ-21 | Stage 2 | Each requirement shows its sources inline; there is no per-requirement derivation tick. | Disputes are the exception path. | The reviewer disputes derivations that look wrong instead of confirming every one. | i3 | you-recommended |
| REQ-22 | Stage 2 | An approved scenario or constraint that derives no requirement blocks stage-2 signing. | No under-derived stage-1 items. | A gap in Claude's derivation is surfaced, not signed past. | min | you-recommended |
| REQ-23 | Stage 2 | Stage-2 signing requires: no under-derived stage-1 item; a reason for every placement move; no scope warnings, unresolved conflicts, or orphans; no open dispute or reopened scenario. | Stage-2 gates. | The v1 scope gates plus the derivation and dispute conditions. | min | claude |
| REQ-24 | Stage 2 | All four v1 optional views remain where the data supports them; Coverage becomes a trace matrix of approved stage-1 items beside their requirements, each gap linked to where it is closed. | Views kept; Coverage traces. | Impact × certainty, Story map, and State machine are unchanged. | i2 | you-recommended |
| REQ-25 | Rework | A stage-2 dispute carries a written reason and is typed derivation wrong (Claude re-derives; stage 1 untouched) or scenario wrong (the scenario returns for re-approval). | Two dispute kinds. | A derivation can be wrong while its scenario is right. | min | you-recommended |
| REQ-26 | Rework | A scenario-wrong dispute reopens only that scenario; requirements derived only from it are withdrawn until Claude re-derives, and the rest of stage 1 stays signed. | Reopen one scenario, not the stage. | Avoids the invalidate-everything loop multi-stage sign-offs decay into. | min | you-recommended |
| REQ-27 | Rework | A reopened scenario is revised by Claude and re-approved in the stage-2 page; the final fold re-pins its hash. | Re-approval without regressing the page. | The page does not fall back to stage 1 for one scenario. | i3 | claude |
| REQ-28 | Downstream | A signed stage-2 export is the approval: Claude folds it, marks the spec Approved, regenerates `logic.md`, commits `logic.json` and `logic.md`, and hands off to execution with no second chat approval. | Final signature is the approval. | Carries v1's signing-is-the-approval rule to the final stage. | min | you-chose |
| REQ-29 | Downstream | The generated v2 `logic.md` presents Behavior & scenarios grouped by behavior, a Constraints section, and each requirement with the stage-1 items it derives from. | Downstream markdown shows the trace. | Downstream skills keep reading `logic.md`. | i3 | claude |
| REQ-30 | Carried from v1 | v1's round-trip mechanics apply in both stages: download and copy hand-off, stale-export refusal, diff-aware carry-over, lost-state recovery, UI feedback to the shared page, and dated amendments after approval. | Round trip unchanged. | Each stage's feedback rounds behave exactly as v1's. | min | you-chose |
| REQ-31 | Authoring | The interactive rubric and the brainstorming and writing-specs wiring describe v2 authoring: behaviors, key examples, constraints, the stage-1 fold, derivation, and disputes. | Skills teach v2. | Claude cannot produce v2 specs unless the rubric describes them. | min | claude |
| REQ-32 | Stage 2 | A non-goal constraint derives an out-of-scope requirement, which satisfies the under-derived gate. | Non-goals derive out-of-scope items. | Matches v1, where non-goals were out-of-scope requirements. | i3 | claude |
| REQ-33 | Rework | A requirement derived from several items, one of which is reopened, stays in stage 2 flagged changed-since-reviewed until Claude re-derives it. | Shared derivations are flagged, not withdrawn. | Only-derived requirements are withdrawn; shared ones stay visible but return to review. | i2 | claude |
| REQ-34 | Carried from v1 | The page's `pnpm run check` rebuilds the template into a temporary directory and fails when it differs byte-for-byte from the committed `review-template.html`. | Stale templates fail the page check. | Runs where page dependencies are installed, beside typecheck and layout-check; the offline Python suite is unchanged. | i3 | claude |

### Conditionally in scope

| ID | Area | Condition | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|---|
| _None_ | | | | | | | |

### Out of scope

| ID | Area | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|
| OOS-01 | Compatibility | Migrate v1 `logic.json` files to v2. | No migration. | Lossy: v1 requirements were not traced to scenarios. | i1 | you-chose |
| OOS-02 | Format | Review and derive one behavior at a time in a rolling pipeline. | No per-behavior pipeline. | Stage 1 is signed as a whole. | i1 | you-chose |
| OOS-03 | Format | Split the spec into one file per stage. | No per-stage files. | Cross-file traceability drifts. | i1 | you-chose |
| OOS-04 | Stage 1 | Reject a fourth scenario per behavior outright. | No hard scenario cap. | The soft limit with a reason applies instead. | i1 | you-recommended |
| OOS-05 | Stage 2 | Require the reviewer to tick each derivation as faithful. | No derivation tick. | Disputes are the exception path. | i1 | you-recommended |
| OOS-06 | Compatibility | Review v1 specs in the page. | No v1 page review. | v1 specs are read-only. | i1 | you-chose |

## Assumptions & blind spots

### Assumptions

- **ASM-01 — Reviewers catch errors in concrete scenarios more reliably than in abstract requirement text.** (assumed)
  - Basis: Example Mapping and specification-by-example practice; v1's rubber-stamping research.
  - If wrong: The stage split adds a round trip without improving review quality.
  - Affects: REQ-05, REQ-18
  - Meaning: Putting examples first is what makes the review better, not just longer.
  - Check: Compare the number of substantive changes the reviewer makes in stage 1 against v1 reviews of similar size. (cost: Medium — needs a few real v2 runs.)
  - Reviewer ruling: build-on
- **ASM-02 — Claude derives requirements from signed scenarios and constraints faithfully enough that disputes are the exception.** (assumed)
  - Basis: Requirements are formalizations of already-agreed examples and rules.
  - If wrong: Stage 2 turns into a second full review, and a per-requirement derivation check becomes necessary.
  - Affects: REQ-21, REQ-25
  - Meaning: Stage 2 stays light because most derivations are right.
  - Check: Count disputes per stage-2 review in the end-to-end run. (cost: Low)
  - Reviewer ruling: build-on
- **ASM-03 — Approve, rewrite, or reject is enough review for a constraint.** (assumed)
  - Basis: Constraints are single statements with no Given / When / Then to vary.
  - If wrong: Constraints need alternatives or scope conditions of their own.
  - Affects: REQ-08, REQ-09
  - Meaning: Constraints do not need their own scope board.
  - Check: Review the constraints of one real v2 spec. (cost: Low)
  - Reviewer ruling: build-on
- **ASM-04 — No v1 spec is mid-review when v2 ships.** (confirmed)
  - Basis: The only v1 `logic.json` in the repository is the test fixture.
  - If wrong: A spec in review is stranded read-only.
  - Affects: REQ-03, REQ-04
  - Meaning: Freezing v1 strands nothing.
  - Check: Search the repository for `logic.json` files. (cost: Low — done.)
  - Reviewer ruling: build-on
- **ASM-05 — Three key examples cover most behaviors.** (assumed)
  - Basis: Adzic's sufficient set: rule, edge case, known problem.
  - If wrong: Most behaviors carry justified extras and the limit is noise.
  - Affects: REQ-07
  - Meaning: The limit flags real sprawl, not normal behaviors.
  - Check: Count scenarios per behavior in the first v2 specs. (cost: Low)
  - Reviewer ruling: build-on

### Blind spots

- **BS-01 — Constraints that legitimately derive nothing**
  - A non-goal constraint has no behavior to build, so the under-derived gate would block signing on it.
  - Sources: REQ-22, REQ-08
  - Resolved by: REQ-32
- **BS-02 — Requirements shared by a reopened scenario**
  - Withdrawing only requirements derived solely from the reopened scenario leaves shared ones in place, possibly stale.
  - Sources: REQ-26
  - Resolved by: REQ-33
- **BS-03 — Two round trips minimum**
  - Every v2 spec needs at least two sign-offs and a derivation pass between them; sequential gates add latency and fatigue, and a small spec pays the same fixed cost.
  - Sources: REQ-15, REQ-05
  - Reviewer acceptance: We can evaluate once v2 is live
- **BS-04 — Page changes can ship without a rebuilt template**
  - No test checks that the committed `review-template.html` matches the page source, and v2 changes most of the page.
  - Sources: REQ-17, REQ-24
  - Resolved by: REQ-34
  - **Research finding (2026-09-24T14:05:26Z)** The template build is deterministic, so a rebuild-and-compare check is exact. — Two `vite build` runs of the current page source produced byte-identical output, and that output matches the on-disk `review-template.html`. A check can rebuild into a temporary directory and compare bytes. It needs installed page dependencies, so it belongs in the page's `pnpm run check` rather than the offline Python suite. REQ-34 proposes it.

## Decisions Locked

### Format

- One `logic.json` at `schemaVersion: 2`, stage-gated, with the stage-1 sign-off pinned to item hashes (Approach A).
- Brainstorming's offer is unchanged — markdown (default) or interactive — and interactive now means v2.
- v1 specs are read-only: validate, regenerate `logic.md`, and amend; no page review, `check-export`, or `fold`.

### Stage 1

- Scenarios are grouped under named behaviors, with a soft limit of three key examples per behavior; each extra carries Claude's reason, the page flags it, and validation warns without failing.
- Constraints are approved, rewritten in the reviewer's words, or rejected with a reason, one at a time; no approve-all.
- Provenance and the Claude-added queue live on scenarios and constraints; Claude's pick is preselected and marked Claude-added, and still needs the reviewer's action.
- A scenario may be dropped in stage 1 with a reason and becomes a recorded non-goal.
- Assumptions and blind spots reference scenario and constraint ids; a blind spot is resolved by a scenario or constraint, or accepted.

### Hand-off

- Claude folds the signed stage-1 export before deriving requirements.
- One page with a stage indicator; stage-2 tabs appear after the stage-1 fold, and stage-1 tabs stay visible read-only.

### Stage 2

- Derived requirements arrive with Claude's placement pre-filled; any move needs a written reason.
- No per-requirement derivation tick; disputes are the exception path.
- An approved stage-1 item that derives no requirement blocks stage-2 signing.
- All four v1 optional views stay; Coverage becomes a scenario/constraint → requirement trace matrix.

### Rework

- Disputes are typed — derivation wrong or scenario wrong — each with a written reason.
- A scenario-wrong dispute reopens only that scenario and what derives from it; the rest of stage 1 stays signed.

### Carried from v1

- Build, Round trip, and Downstream decisions of the v1 interactive logic spec hold unchanged: prebuilt page with no build at spec time, local file only, download and copy hand-off, diff-aware revisions, signing is the approval, commit only `logic.json` and `logic.md`, dated amendments with no re-review.

### Success criteria

- One end-to-end v2 run: brainstorm → stage-1 review → signed stage-1 fold → derivation → stage-2 review → signed fold → execution reads the generated `logic.md`.


## Industry Insights

- **Example Mapping agrees rules and examples before requirements.** Rules (behaviors) each illustrated by a few concrete examples are agreed first, and requirements are formalized from them afterwards — the stage order v2 adopts. — https://cucumber.io/blog/bdd/better-requirements-by-harnessing-the-power-of-exa/, https://johnfergusonsmart.com/feature-mapping-a-lightweight-requirements-discovery-practice-for-agile-teams/
- **Key examples, not exhaustive ones.** A sufficient set covers the business rule, the technical edge cases, and known problem areas; exhaustive combinations create maintenance debt. Grouping scenarios under a rule (Gherkin `Rule`) makes sprawl visible per rule. Supports behaviors plus a soft per-behavior limit. — https://gojko.net/2010/01/06/how-to-effectively-define-a-sufficient-set-of-bdd-scenariosacceptance-tests/, https://cucumber.io/blog/bdd/gherkin-rules/, https://insideproduct.co/example-mapping/
- **Scenarios do not express non-functional requirements.** BDD has no established pattern for constraints, placement, naming, or non-goals; they must be documented separately. Hence a stage-1 constraints list alongside scenarios. — https://www.3e.pl/blog/documentation-of-requirements-in-projects-bdd-gherkin-approach
- **Later stages invalidating earlier approvals is the classic multi-stage failure.** When a later reviewer's change voids every preceding approval the process restarts; folded approvals also become ambiguous unless tied to the exact version approved. Supports reopening only the disputed scenario and pinning the stage-1 sign-off to item hashes. — https://www.wrike.com/workflow-guide/approval-workflow/, https://flowdence.io/blog/posts/the-complete-guide-to-confluence-approval-workflows/, https://cogniver.com/insights/policy-approval-workflow
- **Split specification documents drift.** Manual synchronization across linked documents is the primary failure mode; generating from one structured source prevents it. Supports one `logic.json` over one file per stage. — https://gitdoc.ai/resources/documentation-as-code, https://cucumber.io/blog/bdd/how-does-bdd-affect-traceability/
- **Incremental per-rule approval finds conflicts early but loses the whole-feature view.** Story-by-story discovery reduces rework, yet cross-rule interactions can surface late. Weighed against the ledger's requirement that stage 1 be signed as a whole before derivation. — https://cucumber.io/blog/bdd/user-stories-and-bdd-part-2-discovery/, https://cucumber.io/blog/bdd/user-stories-and-bdd-features-are-not-stories/
- **Sequential gates add latency.** Every delay in one stage blocks the next. v2 accepts a second round trip in exchange for reviewing examples before requirements. — https://velt.dev/blog/review-workflows-types-breaking-points
- **Prior art:** the v1 interactive logic spec and its research on rubber-stamping, `file://` storage, and hand-off paths. — docs/quirk/specs/2026-09-23-interactive-logic-spec/logic.md

## Scope & non-goals

- The markdown logic-spec path is unchanged.
- No migration of v1 `logic.json` files to v2.
- No page review of v1 specs.
- No per-behavior rolling pipeline; stage 1 is signed as a whole.
- No split into separate files per stage.
- No hard cap on scenarios per behavior.
- No per-requirement derivation tick.
- Everything v1 excluded stays excluded: artifact hosting, a local review server, review-behavior signals, a delivery tier, interactive `tech.md`.

## Deferred Ideas

- A v1 → v2 migration command.
- [tech-spec] The v2 schema shape and how the validator and page branch on `schemaVersion`.
- [tech-spec] How the stage-1 pin's item hashes are computed and compared after a reopen.
- [tech-spec] Whether the stage gates are shared between the Python renderer and the page or duplicated as in v1.
- [tech-spec] Layout of the generated v2 `logic.md` (behavior grouping, constraints section, derivation links).

## Glossary

| Term | Definition |
|---|---|
| Behavior | A named one-line rule grouping its key scenarios. |
| Key example | A scenario chosen to illustrate a behavior's rule, an edge case, or a known problem — not an exhaustive combination. |
| Constraint | A non-behavioral requirement — placement, verification, naming, non-goal — reviewed in stage 1. |
| Stage 1 | Review and signature of what should happen: behaviors, scenarios, constraints, risks. |
| Stage 2 | Review and signature of what to build: requirements derived from stage 1, reviewed for scope and conditions. |
| Derivation | A requirement's `derivedFrom` link to one or more approved scenarios or constraints. |
| Dispute | A stage-2 objection with a written reason, typed derivation wrong or scenario wrong. |
| Reopened scenario | A signed scenario sent back for re-approval by a scenario-wrong dispute. |
| Stage-1 pin | The signed-at time, render, and per-item hashes recorded when the stage-1 export is folded. |
| Trace matrix | The v2 Coverage view: each approved stage-1 item beside the requirements derived from it, with gaps. |
