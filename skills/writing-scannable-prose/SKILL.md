---
name: writing-scannable-prose
description: Use when writing or revising a human-facing technical document — README, guide, ADR, PR description, changelog — or when asked to tighten, shorten, or declutter one ("tighten this", "too long", "hard to scan", "make this scannable"). Separates what the reader's decision depends on from detail they do not want, cutting whole sections that earn no keep; then treats every remaining cut as a dependency problem, so compression removes real bulk without orphaning the claims it leaves behind.
---

# Writing Scannable Prose

## Overview

Treat the document as a dependency graph, not a pile of words to shorten: a cut is safe only when nothing depends on what got removed. Watch for **orphaning** — a claim whose scope, evidence, or antecedent got cut out from under it, leaving a reader confidently wrong, not visibly confused. **Verbosity** — words carrying no information — is real, but secondary and easy.

A document gets read twice: as a visual surface (headings, bold, layout) and as a linear stream where none of that survives — screen readers, TTS, plain-text extraction. Only markup-level structure survives the second read.

**Gate:** fires on a document carrying claims, reasoning, or procedure — README, guide, ADR, PR description, changelog, or similar — not on line count. A three-line changelog entry is in scope; a one-line typo-fix PR body is not.

## Authoring inputs

Decide two things once, before drafting:

| Decision | Consumed by | Controls |
|---|---|---|
| Reader, and what they decide next | F1, F2, F4 | Whether a section survives, what counts as author-facing detail |
| Passage procedural or explanatory | A4 | How hard cutting may go within that passage |

Diátaxis mode (tutorial / how-to / reference / explanation) is **not** an authoring input — A6 alone consumes it, relocating a paragraph misfiled for its section's mode.

## Revision protocol

1. **Derive F1's line.** Check sibling artifacts, the template, and whether the content already lives canonically; state the result: `Reader: <who> — Decision: <what they do next>`. No signal resolves it → say so.
2. **Run F2 against every section** against F1's line: does its absence change the named decision? Mark keep or remove. **F1 is unresolved whenever either field is missing — a reader named with no decision, or a decision with no reader — and an unresolved F1 means F2 doesn't run; every section defaults to keep.** Name the gap as a non-blocking escalation — not a second blocking point, since it doesn't halt the pass.
3. **For every section marked remove, run F3**: name the section that owns each load-bearing item; no owning section → find one, or reclassify it as not load-bearing only when it fails F1's line like any other cut, naming the reclassification to the user beside the removal proposal.
4. **Emit the removal proposal** (shape below) in one batch, then **stop for an answer before step 5** — the protocol's one blocking point. Nothing marked → straight to step 5.
5. **If removals were proposed, apply the answer**: perform the approved F2 removals and their F3 moves, and retain the sections the user rejected. Then **run F4** on every surviving section: route author-facing detail to its destination (table below); a deliberately-not-made decision stays.
6. **Run groups A–E** on the surviving, routed content. Reuse a passage's procedural/explanatory classification from the authoring phase when one was made there; otherwise — the common case, since authoring rarely runs against an existing draft — classify it in place, immediately before A4 fires, passage grain only, never at document or section grain. A call here that can't be self-verified is non-blocking: apply it provisionally and name it in the report.
7. **Emit the revision report** (shape below): everything steps 1–6 changed and why, including the escalations from steps 2 and 6.

**Removal proposal shape** (step 4's output):

```
## Proposed section removals
| Section | Why it fails F2 (against the Reader/Decision line) | Load-bearing items | Destination |
|---|---|---|---|
```

One row per removed section, empty when nothing was marked — including the F1-undecided case, named in the report. An item F3 reclassifies out of load-bearing status is named beside the proposal too, with the F1 line it failed — approving a removal means approving what goes with it.

## Escalation modes

Escalation has two modes, and only one of them blocks:

| Mode | Applies to | Behavior |
|---|---|---|
| Blocking | F2 section removals only | Proposed in one batch before A–E begins; the pass waits |
| Non-blocking | An unresolved F1 line | Not applied: F2 is skipped, every section defaults to keep, the gap is named in the report |
| Non-blocking | Any unverifiable A–E judgment call | Applied provisionally, named in the report; the pass doesn't wait |

The asymmetry is reversibility: an A–E edit is visible in a diff, so a wrong call costs a word. A section removal leaves no trace once gone.

## The 28 checks

Six groups, one table each. `mech` is judgment-free, `judg` reduces to yes/no, `prin` makes no enforcement claim; `precautionary` rests on convergence, not a settled result ([evidence-and-limits.md](evidence-and-limits.md)).

Group F runs first: compressing a doomed section risks a **residue stub** — bulk gone, shell remaining, passing every check while the reader still gets a section they didn't want.

### F — Does this section belong?

| ID | Check | Tag |
|---|---|---|
| F1 | Name the reader and decision in one visible line, from repo signals — everything downstream tests against it | `judg` |
| F2 | Section materiality: absence unchanged decision → section goes, not compressed. Removals proposed, not performed | `judg` |
| F3 | Re-home before removing: every load-bearing item lands in the section that owns it — no stub left behind | `judg` |
| F4 | Detail level: within a surviving section, route author-facing detail away from what the reader needs | `judg` |

F4 routes surviving detail to:

| Category | Destination |
|---|---|
| Review-round history, feedback tables | The review threads themselves |
| Approaches tried and rejected | Commit body, or an ADR if it outlives the change |
| How it was verified — transcripts, run counts, methodology | Test docstrings, or the test itself |
| Tooling and process narrative | Nowhere; work-in-progress residue |
| A decision deliberately not made, with its rationale | Stays — changes what a reader concludes |

These categories make F4 actionable, not exhaustive: content outside the table is still tested against F1's line rather than passing by default. And a destination outside the document under revision — for F4 or A6 alike — is proposed, not performed, unless that file is already in the task's scope; the material stays put until the move is authorized. Non-blocking: it routes to the report like any other non-blocking item, not a second checkpoint.

### A — What a cut may touch

| ID | Check | Tag |
|---|---|---|
| A1 | Name the operation: word, claim, or qualifier scoping a surviving claim | `judg` |
| A2 | Qualifiers (hedges), scope conditions, sample sizes, exceptions, platform caveats stay in the same visual unit as their claim — never demoted to a footnote or a later bullet. Tighten wording, not the fact | `judg` |
| A3 | **Orphan check.** Diff backward pointers and demonstratives against the deletion — cut pointer with referent, inline a restatement, or keep both | `mech` |
| A4 | Cut license by content class: procedural cuts toward bare imperatives; explanatory cuts filler only — trade-offs, scope conditions, sample sizes, limitations survive. `precautionary` | `judg` |
| A5 | Dead words: nominalizations back to verbs, expletive constructions, circumlocutions, redundant intensifiers | `mech` |
| A6 | Route before deleting: material that is true and relevant but doesn't change the reader's action moves — footnote, appendix, its owning document — never dies | `judg` |

### B — Which device carries the logic

| ID | Check | Tag |
|---|---|---|
| B1 | **Reversal test.** Reversing two items changes what's true or doable → chain with a *because*-class connective; independent items may stay bulleted — burden of proof favors keeping the list. `precautionary` | `judg` |
| B2 | Label the list relation — order / choose one / all must hold. A bare list implies AND | `judg` |
| B3 | A table earns its place by being countable, not by attribute count: multiply condition cardinalities, check row count, mark gaps `impossible per §X` or `unspecified` — never blank, never "N/A". Band continuous conditions first. `precautionary` | `judg` |
| B4 | A figure needs genuine spatial, sequential, or relational shape, paired with a sentence naming what it shows; keep diagrams as text, so they diff | `judg` |
| B5 | Code answers mechanical "how do I call this." Composition, design rationale, version scope need prose | `judg` |

### C — Order and repetition

| ID | Check | Tag |
|---|---|---|
| C1 | **Tail-chain test.** Read each sentence's last words alone, top to bottom: advancing facts, or filler and a repeated noun? | `judg` |
| C2 | **Subject-swap test.** Passive's subject echoes the prior sentence → leave it. No echo → rewrite active | `mech` |
| C3 | Sections open with the conclusion, so a reader who stops there still has the takeaway | `judg` |
| C4 | Restate only where the thread was plausibly lost — heading intervened, or antecedent distant and ambiguous. One orienting clause or a real link, never a re-explanation. Aggressive on reference/how-to, light on tutorial, never changelogs. `precautionary` | `judg` |

### D — Emphasis and the linear channel

| ID | Check | Tag |
|---|---|---|
| D1 | Bolded spans must be lexically complete statements — strip the bold and nothing is lost | `mech` |
| D2 | Emphasis goes to the claim whose misreading is unrecoverable (data loss, security exposure, binding commitment), not to what feels important | `judg` |
| D3 | The heading outline must convey the document alone: no skipped levels, no "Overview" / "Details" / "More" | `mech` |
| D4 | Nothing load-bearing carried only by bold, color, position, or emoji | `mech` |
| D5 | List length is channel-dependent: a re-consultable list may run long; an unaided one stays short, split with prose | `judg` |
| D6 | Tables need header cells with `scope`, and a caption | `mech` |

### E — Staying true

| ID | Check | Tag |
|---|---|---|
| E1 | Tag facts stable vs. perishable. Perishable → generate from source, assert against source in CI, or point at the constant, not the value | `mech` |
| E2 | Executable examples where the genre allows — the literal quickstart runs in CI | `mech` |
| E3 | Never gate anything on a readability score | `mech` |

## Do-not-cite blocklist

None of these are sourceable. They stay inline, not in a reference file, to catch the reflex before anyone opens a link:

- A 30%-bold maximum as a ceiling on emphasis density
- "Users read 25% faster with bullets"
- 7±2 as a hard cap on list length
- "Bold enables 30% faster scanning"
- The F-pattern as a design target for layout

## Falsification notes

Four `precautionary` checks rest on convergence, not a settled result. One line each; full notes in [evidence-and-limits.md](evidence-and-limits.md):

- **A4** — cut license by content class: a two-content-type RCT, not a spectrum.
- **B1** — reversal implies chaining: what causal connectives do cognitively, not a bullets-vs-prose trial.
- **B3** — a table earns its place by countability: a completeness argument, not a comprehension study.
- **C4** — restate only when the thread is plausibly lost: a screen-deficit study, not restatement itself.

## Deference and scope

An existing project template wins on structure — sections, names, ordering; this skill governs the prose inside its slots. `quirk:artifacts:adr` output keeps its shape.

An explicit user request wins outright: the rules stand down wherever they'd fight it, though they still apply elsewhere — structure, orphan checks, the linear channel.

The skill applies to the whole document, not only text written after it loaded. A README scannable in its back half and dense in its front fails the property it claims.

## Skill applies to itself

This file obeys its own structure rules: sections open with the conclusion, no list implies an order where none exists, no bold carries anything load-bearing alone. It deviates where the agent-facing genre differs from prose for a human skimmer — the tables above exist to be grepped, not read as narrative.

## Report shape

Step 7's output:

```
## Revision report
- Removed: <section> — <one-line F2 reason>. Moved: <item> → <destination> (repeat per item)
- Routed (F4): <item> — <category> → <destination>
- Changed (A–E): <check ID> — <what changed> — <why>
- Escalated (non-blocking, F1 undecided): <repo signals checked> — <why no reader/decision line could be derived> — F2 skipped, every section kept
- Escalated (non-blocking, A–E only): <check ID> — <the call> — <how to reverse it>
```

Not a checklist transcript: each line names a concrete edit and its reason; skip a line type when nothing fired.

## Real-user gap

These rules were never validated against real readers, and that can't happen inside a session. Several `judg`-tagged calls above are best-available procedure, not settled findings — apply them, but hold them as claims, not results.

## Links out

Worked before/after examples for all 28 checks: [worked-examples.md](worked-examples.md). Grounded-vs-precautionary status and full falsification notes: [evidence-and-limits.md](evidence-and-limits.md).
