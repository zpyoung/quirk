# Logic spec: `writing-scannable-prose` skill

**Date**: 2026-07-29 · **Domain**: Docs · **Source**: [exploration](../../explorations/2026-07-29-scannable-prose.md) + [mechanisms companion](../../explorations/2026-07-29-scannable-prose-mechanisms.md)

## Status

Draft — approved for implementation. Tech spec: not requested.

## Conceptual model

A quirk skill that makes human-facing technical documents scannable and information-dense, built as **a dependency-checker for prose rather than a shortener**.

One principle drives it: *a cut is safe when nothing depends on what you removed.* That reframes the task away from "make it shorter" — which an agent does fluently and dangerously — toward "find what depends on this before touching it."

Two failure modes, named and ranked:

- **Orphaning** — a claim whose scope, evidence, or antecedent was cut out from under it. The primary target, because it is invisible in a diff: claim count unchanged, no false statement introduced, truth-value silently widened. It produces readers who are confidently wrong rather than visibly confused.
- **Verbosity** — words carrying no information and having no destination anywhere. Real, secondary, and the easy one.

A second idea runs orthogonally: **a document is consumed twice** — once as a visual surface, once as a linear stream where bold, position, and layout do not exist. Only markup-level structure survives the second read.

### Why this shape and not a style guide

The exploration's central finding is that the evidence base for standard scannability advice is far thinner than the advice implies. A challenge pass weakened 13 of 16 candidate directions, always the same way: a sound, sourced insight wrapped in invented procedural machinery. Several widely-circulated numbers could not be sourced at all.

So the skill ships **structural and relational rules with no numeric thresholds anywhere**. Not as an aesthetic preference — as the only defensible option. A threshold this skill invents would be folklore with a shorter pedigree, and structural rules are additionally harder to game than numbers.

## Data flow

The skill loads when an agent is about to write, or has just written, a document that carries claims, reasoning, or procedure. It runs in two phases.

**Authoring (short).** Before drafting, three decisions get made: which Diátaxis-style mode the document is in, who reads it, and which passages are procedural versus explanatory. These decisions determine how hard later cutting may go, so making them up front avoids re-deriving them per edit.

**Revision (substantial).** The agent works the checks against the draft, grouped by what the writer is doing. Checks tagged mechanical run without judgment. Checks tagged judgment reduce to a specific yes/no. Where a call genuinely cannot be self-verified, the agent surfaces it to the user rather than resolving it silently — this is the honest substitute for the independent second reader the source material assumes exists and that an agent does not have.

Output is the revised document plus a report of **what changed and why** — not a checklist transcript. The report exists so the pass is visibly either run or not run; a silent pass can be skipped with no signal, which is how these rules decay.

## Key decisions and rationale

### Orphaning over verbosity

The brief asked for cutting verbosity. The exploration's best-evidenced compression finding points the other way: in LLM-compressed financial filings every sentence stayed accurate while context share fell from 25% to 9%. The failure is not false statements but orphaned ones.

An agent author is especially prone to this. It trims toward authoritative-sounding prose, has no felt sense of a reader losing the thread, and is its own only reviewer. A skill tuned purely to shorten would amplify the exact defect the research documents. Verbosity still gets its rule (A5, dead words) — it is simply not the thing the skill is for.

### No numeric thresholds

Sourced findings in this area are findings, not thresholds. Cowan's ~4 chunks measured short-term recall of discrete stimuli; the 71.6% figure describes screen-reader navigation behavior. Turning either into a target is the construct-validity leap the challenge pass caught. And the failed claims — a 30%-bold ceiling, "25% faster with bullets", 7±2 as a list cap — are precisely what happens when a plausible number outlives its derivation.

Consequence accepted: some rules are less crisply checkable than a number would make them. That is the honest trade.

### Structure by topic, enforcement by tag

The source material proposes organizing a guide by how each rule is checked. The genuine payload of that idea is the **demotion rule** — anything that fits no tier becomes a principle making no enforcement claim — not the shelving order. An agent mid-task looks up by problem, so topic order matches retrieval while per-rule tags preserve the epistemics.

Three tags: `mech` (runnable, no judgment), `judg` (a specific yes/no), `prin` (no enforcement claim).

### The second reader does not exist

Every judgment-tier rule in the source assumes an independent reader who can contest the author's classification. Inside a session there is none, and structural proxies are trivially gameable by the same agent being checked.

Resolution: named self-checks, plus explicit escalation of calls that cannot be self-verified. The skill states this limit rather than implying self-review equals review.

### Proxies are smoke detectors, never targets

A 2024 study found 50 years of plain-language mandates produced no measurable decline in processing-difficulty features. The mandates targeted the proxy. A proxy may prompt a look here; it may never be the optimization target or the evidence a document is good. No readability score is ever a gate.

### Human skimmer is the primary reader

Where a human skimmer and a downstream agent consuming the doc as context want opposing formatting, the human wins. The named genres are human-facing, and every piece of evidence available measured human readers. Optimizing for a speculative agent-reader would mean inventing exactly the unsourced machinery this design refuses.

The linear channel (screen readers, TTS) is not a competing third reader — it is a **constraint on the human case**, and the best-grounded material available.

## Rule inventory

24 checks in five groups. Tags as above; `precautionary` marks a rule resting on convergence rather than a settled result, and each carries a falsification note.

### A — What a cut may touch

| | Check | Tag |
|---|---|---|
| A1 | Name the operation before editing: removing a word, a claim, or a qualifier that scopes a surviving claim | `judg` |
| A2 | Scope conditions, sample sizes, platform caveats stay — in the same visual unit as the claim, never demoted to a footnote or a later bullet. Wording tightenable; fact not removable | `judg` |
| A3 | **Orphan check.** Every backward-pointing phrase ("as noted above", "for this reason", "see §X") and every demonstrative whose nearest antecedent falls inside the deletion range — diff against what was cut. Resolve by cutting pointer with referent, inlining a minimal restatement, or keeping both | `mech` |
| A4 | Cut license by content class: procedural cuts hard toward bare imperatives; explanatory cuts filler only, and every trade-off, scope condition, sample size and limitation survives. `precautionary` | `judg` |
| A5 | Dead words: nominalizations back to verbs, expletive constructions, circumlocutions, redundant intensifiers. Default-on, no review | `mech` |
| A6 | Route before deleting — material true and relevant that does not change the reader's next action moves (footnote, appendix, the document that owns that mode) rather than dying | `judg` |

### B — Which device carries the logic

| | Check | Tag |
|---|---|---|
| B1 | **Reversal test.** If reversing two items changes what is true, or what a reader could correctly do, the pair is chained → prose with a *because*-class connective. Independent items may stay bulleted; burden of proof favors keeping the list. `precautionary` | `judg` |
| B2 | Label the list relation — "do these in order" / "choose one" / "all of the following must hold". A bare list reads as an implicit AND | `judg` |
| B3 | A table earns its place by being **countable**, not by attribute count: multiply the condition cardinalities, check the row count, and mark a gap `impossible per §X` or `unspecified` — never blank, never "N/A". Band continuous conditions before gridding. `precautionary` | `judg` |
| B4 | A figure needs genuine spatial, sequential, or relational shape; one encoding no structure actively hurts comprehension. Pair a load-bearing figure with one sentence stating what it shows. Diagrams as text source so they diff | `judg` |
| B5 | Code answers mechanical "how do I call this". Composition across calls, design rationale, and version scope need prose — another snippet will not supply them | `judg` |

### C — Order and repetition

| | Check | Tag |
|---|---|---|
| C1 | **Tail-chain test.** Read the last few words of each sentence in a paragraph, alone, top to bottom: advancing facts, or filler and the same noun landing repeatedly? | `judg` |
| C2 | **Subject-swap test.** For each passive, does its grammatical subject echo the prior sentence? Yes → leave it, the passive is preserving a topic. No → rewrite active. One lookup, no judgment about agency or vagueness | `mech` |
| C3 | Sections open with the conclusion, so a reader who stops there still has the takeaway | `judg` |
| C4 | Restate only where a reader plausibly lost the thread — a heading intervened, or the antecedent is distant and ambiguous. One orienting clause or a real link, never a re-explanation. Aggressive on reference and how-to, light on tutorial, never on changelog entries. `precautionary` | `judg` |

### D — Emphasis and the linear channel

| | Check | Tag |
|---|---|---|
| D1 | Bolded spans must be lexically complete statements — strip the bold and nothing is lost | `mech` |
| D2 | Emphasis goes to the claim whose misreading is unrecoverable (data loss, security exposure, binding commitment), not to what feels important | `judg` |
| D3 | The heading outline must convey the document alone. No skipped levels. No "Overview" / "Details" / "More" | `mech` |
| D4 | Nothing load-bearing carried only by bold, colour, position, or emoji | `mech` |
| D5 | List length is a function of channel: a list the reader can visually re-consult may run long; an unaided one stays short and gets split with intervening prose | `judg` |
| D6 | Tables need header cells with `scope`, and a caption | `mech` |

### E — Staying true

| | Check | Tag |
|---|---|---|
| E1 | Tag facts stable vs perishable. Perishable → generate from source, assert against source in CI, or do not state the value (point at the constant instead) | `mech` |
| E2 | Executable examples where the genre allows — the literal quickstart runs in CI | `mech` |
| E3 | Never gate anything on a readability score | `mech` |

### Also inline in SKILL.md

- **The do-not-cite blocklist** — the 30%-bold maximum, "users read 25% faster with bullets", 7±2 as a list cap, "bold enables 30% faster scanning", the F-pattern as a design target. None sourceable. Inline rather than in a reference file because the whole point is preempting a reflex, and a reflex fires before anyone opens a link.
- **Falsification notes** on the four `precautionary` rules.
- **The self-check protocol**, including which calls escalate to the user.
- **The real-user gap**, named in one short passage: these rules were never validated against real readers, that validation cannot happen in-session, so certain claims remain claims.

## Behavior and scenarios

**Gate.** Fires when a document carries claims, reasoning, or procedure. Not on line count — a three-line changelog entry describing a behaviour change is in scope; a one-line typo-fix PR body is not. Below that bar the machinery is pure overhead, and templated three-section descriptions on trivial changes read as low-effort output that reviewers learn to skim past.

**Scope of application.** The whole artifact, not only text written after the skill loaded. A README scannable in its back half and dense prose in its front fails the property it claims.

**An existing project template disagrees.** The template wins on structure — sections, names, ordering — because other tooling and reviewers depend on them. The skill governs prose inside whatever slots the template defines. Concretely: `quirk:artifacts:adr` output keeps its shape.

**The user explicitly asks for something the rules push against** ("walk me through the whole story"). The explicit request wins outright. The skill may still apply where it does not fight the request — structure, orphan checks, the linear channel — but never compresses what the user asked to be expansive. This matches quirk's own stated priority: user instructions above skills.

**A cut would remove a qualifier.** A2 fires. The qualifier stays, adjacent to its claim. Wording may tighten; the fact may not go.

**A judgment call cannot be self-verified.** The agent names it to the user rather than resolving it silently, producing a short specific list instead of a whole document to re-read.

**The skill applies to itself.** SKILL.md obeys its own structure rules and says so — style guides that visibly ignore their own advice were historically distrusted into shelfware. With an explicit license to deviate where the agent-facing instruction genre legitimately differs.

## File layout

```
skills/writing-scannable-prose/
  SKILL.md              # gate, model, 24 checks by topic with tags, blocklist,
                        # deference rules, self-check protocol
  worked-examples.md    # one before/after per check
  evidence-and-limits.md # grounded vs precautionary status, falsification
                        # notes, pointer to the explorations
```

Plus: both exploration documents committed to `docs/quirk/explorations/` on this branch. They are currently untracked and live in the main checkout, so the skill's citation pointer would otherwise be a dead link for anyone else. They are the evidence layer several locked decisions depend on.

Plus: a test module following `tests/test_skill.py`'s shape — frontmatter valid, name matches directory, description carries the intended trigger phrases, blocklist entries present in SKILL.md, all 24 check IDs present.

## Activation

Description scopes to document artifacts and revision triggers: README, guide, ADR, PR description, changelog, plus phrasings a user types — "tighten this", "too long", "hard to scan", "make this scannable".

It deliberately avoids voice, tone, de-AI, and humanize vocabulary. That is the existing `writing-like-a-human` skill's territory and explicitly out of scope in the exploration, so the two can co-fire on a docs task without competing for activation.

## Scope and non-goals

**In scope:** READMEs, guides, ADRs, PR descriptions, changelogs. Compression safety, logical-structure device choice, information order, emphasis, the linear channel, claim freshness.

**Out of scope:**

- Voice, tone, register — `writing-like-a-human` owns this.
- Typographic and layout parameters (line length, font, paragraph length) — rendering-environment properties, not authoring decisions, in Markdown-based docs.
- Localization, non-native-English readers, readers with cognitive disabilities beyond list length — deferred in the exploration and still unaddressed.
- Agent-facing docs as a target genre.
- Cross-document architecture: shared/transcluded content reuse and link-decay budgeting. Dropped because their citations could not be located anywhere in the research corpus.
- Effect sizes for figures and code guidance. The qualitative rules (B4, B5) ship; every number attached to them in the source was unverifiable and is stripped.

## Validation

Skill type: **technique**. Validated by applying it to a fresh document and probing for gaps — not the Iron Law, which `writing-skills` scopes to discipline-enforcing skills only.

Concretely: run the revision pass against a real document in this repo that was not written under the skill, confirm each check either fires or is correctly skipped, and check that the escalation path produces a specific list rather than silence. Activation tested separately with should-trigger and should-not-trigger prompts, including a should-not on a pure voice/tone request that belongs to `writing-like-a-human`.

## Decisions locked

**Which failure the skill fights**
- Over-compression is the primary target; verbosity secondary.
- Qualifiers stay in the same visual unit as their claim; wording tightenable, fact not removable.
- "Orphaned claim" ships as a named first-class defect with the referential check.
- Cut license granted by content class (procedural vs explanatory), not by genre.

**Reader identity**
- Human skimmer wins over downstream agent on formatting conflicts.
- The serialization check ships as a hard check.
- Emphasis must be lexically redundant with the words; no density threshold.
- List length is a function of channel, not a number.

**Scope breadth**
- Both remaining clean survivors ship; redundancy debt's ~4-entity trigger dropped.
- Bullets-vs-prose ships as a precautionary rule that states its own status.
- Sentence-level: tail-chain and subject-swap only; cold-start and marked-theme apparatus dropped.
- Figures and code-vs-prose kept as qualitative rules, all effect sizes stripped; cross-document reuse and link decay dropped.

**Mode**
- Both authoring and revision, revision-weighted.
- The pass reports what it changed and why, not a checklist transcript.
- Applies to the whole document, not only newly-written text.
- SKILL.md obeys its own rules and says so, with license to deviate where the genre differs.

**Enforcement shape**
- Organized by topic, with a per-rule enforcement tag.
- Named self-checks plus escalation of calls that cannot be self-verified.
- Proxies are smoke detectors, never targets; no readability score is ever a gate.
- The real-user gap is named explicitly with its consequence.

**Evidence representation**
- Blocklist ships short and inline.
- Confidence labels only where status changes application.
- One pointer to the exploration as the citation layer; no inline sources.
- Falsification notes on the precautionary rules.

**Threshold license**
- No new numbers at all. Every rule structural or relational.

**Deference and override**
- Existing project template wins on structure; skill governs prose inside its slots.
- An explicit user request wins outright.
- Gate on the document doing real work, not on line count.

**Skill mechanics**
- Name: `writing-scannable-prose`.
- Hub plus reference files.
- Type: technique.
- Both exploration docs committed alongside the skill.

## Industry insights

Research was **reused, not re-run**. The source exploration is itself a deep multi-round research pass — 82 sourced claims across 8 facets, 3 depth rounds, and a full challenge pass with falsification tests. A fresh web swarm would have returned the folklore that exploration already killed. No new sources were gathered for this spec.

Findings that changed a decision here:

- Compression drops qualifiers before facts: context share 25% → 9% with accuracy held constant — [arXiv](https://arxiv.org/pdf/2606.29251). Drove the orphaning-over-verbosity priority and A2.
- Content class decides compression payoff: n=4,563 RCT, +3.5% on legal text vs +14.6% on PubMed — [arXiv](https://arxiv.org/abs/2505.01980). Drove A4.
- 71.6% of screen-reader users navigate by headings — [WebAIM 2024](https://medium.com/@colleengratzer/key-findings-from-the-webaim-2024-screen-reader-user-survey-bb15864d3bc8). Drove D3.
- Causal connectives do specific cognitive work; "because" triggers inference, "and"/"after" do not — Millis, Golding & Barker 1995. Drove B1, and its precautionary label — the clean bullets-vs-prose RCT does not exist.
- Coherence principle held 23/23, median d=0.86; restoring connective material improves recall — [Cambridge Handbook](https://www.cambridge.org/core/books/abs/cambridge-handbook-of-multimedia-learning/principles-for-reducing-extraneous-processing-in-multimedia-learning-coherence-signaling-redundancy-spatial-contiguit).
- 50 years of plain-language mandates produced no measurable decline in difficulty features — [Martinez, Mollica & Gibson 2024](http://tedlab.mit.edu/tedlab_website/researchpapers/martinez_mollica_gibson_2024.pdf). Drove the proxies-as-smoke-detectors rule and E3.
- Cowan's revision of Miller to ~4, scoped to the no-rehearsal condition — [Journal of Cognition](https://journalofcognition.org/articles/10.5334/joc.387). Drove D5's channel framing and the decision *not* to ship the number.
- Screen deficit is genre-specific: g=−0.27 expository, g=0.01 narrative — [Delgado et al. 2018](https://www.researchgate.net/publication/330854760). Drove C4's genre gate.
- Parnas-style tabular expressions give completeness and consistency — [Tabular Expressions in Software Engineering](https://www.researchgate.net/publication/228939082_Tabular_Expressions_in_Software_Engineering). Drove B3's countability reframe.
- Gopen & Swan on topic/stress position — [PDF](https://www.usenix.org/sites/default/files/gopen_and_swan_science_of_scientific_writing.pdf). Drove C1 and C2.

Unverifiable claims deliberately excluded, per the exploration's own "marked unverified" list: the 30%-bold maximum, "25% faster with bullets", "bold enables 30% faster scanning", 7±2 as a list cap, the F-pattern as a design target, Shannon's redundancy estimate, Lin 1999's optimal compression band, Carroll's minimalism task-time figures.

Gray-area discovery used `adhd` (6 parallel divergence frames, 25 raw areas). Its Deepen phase was skipped deliberately: developing gray areas into options would have preempted the drill-in questions that followed.

## Deferred ideas

- **optimization-unit** (adhd, expert-blind-spots frame) — whether locally scannable sentences compose into a globally scannable document, or whether per-paragraph optimization destroys document-level scan cues. Genuine and unresolved; dropped only to respect the 4-option cap. Revisit if the skill's output reads as locally clean but hard to navigate.
- **Interleaved prose-gate plus scoped grid layout** — how to typeset B1's mixed-content output without the layout becoming a new scannability problem. The exploration flagged this and did not solve it.
- **Genre-specific sub-guides** — whether a README's scannability and an ADR's share enough mechanics to be taught once. Assumed yes by shipping one skill; adhd flagged it as possibly a surface-level illusion.
- **Documents serving two audiences with conflicting natural sequences** (end user vs contributor). The honest fix is probably two documents; no method exists here for detecting the fork.
- **Bateman et al.'s "Useful Junk"** finding sits in tension with the seductive-details basis for B4. Different objects tested; a complete guide should eventually reconcile them.

## Glossary

- **Orphaned claim** — an assertion that survives an edit while the qualifier, evidence, or antecedent it depended on was removed. Reads as confident and current; is neither.
- **Qualifier-level cut** — removing or shortening a hedge, scope condition, sample size, or exception attached to a claim that itself survives. Invisible in a claim-count diff.
- **Chained pair** — two items whose order cannot be reversed without changing what is true or what a reader could correctly do.
- **Crossed pair** — two items whose values combine independently of discovery order.
- **Linear channel** — the document as consumed without visual formatting: screen readers, TTS, plain-text extraction. Bold, position, and layout do not exist in it.
- **Blast radius** — the cost of a reader misreading or missing a given claim; restricted here to irreversible, security-relevant, or binding.
- **Perishable fact** — a specific default value, version, path, count, or topology that changes at code speed.
- **Precautionary rule** — a rule resting on convergence across related findings rather than a direct result, shipped with a falsification note.
- **Serialization check** — verifying a document still works when read as a linear stream.

## Status & amendments

**Amendments:** none yet.
