# Outcome-Altitude Elicitation for `quirk:brainstorming`

**Status:** Implemented — tech spec authored (tier gate fired on ≳3 source files)

Applies four PAWNI-derived mechanisms to the brainstorming skill's question layer, plus an
outcome-altitude rule that keeps brainstorming's dialogue at the same level its output document
already claims to own.

## Conceptual model

Brainstorming currently has no model of **what it must learn** before designing, no rule for **what
order** to ask in, no way for the user to **stop early safely**, and no constraint on **what altitude**
its questions sit at. Research grounds the option proposals but not the questions.

This spec adds one mechanism — an **elicitation controller** — that answers all four. It is a
controller over the *dialogue*, never a rubric over the *document*: it emits questions and then
disappears. Nothing it knows is ever written into `logic.md`.

The controller runs three screens over every candidate question, in this order:

| # | Screen | Rejects |
|---|--------|---------|
| 1 | **Altitude** | Questions whose answers change only how the thing is built |
| 2 | **Tier** | Nothing — classifies as Essential (must ask) or Default-able (may default) |
| 3 | **Ordering** | Nothing — sorts survivors most-forking-first, then foundational→edge-case |

Altitude runs first because an implementation-level question is rejected regardless of its tier.

The tier model and the fast-track escape are **the same mechanism seen from two sides**: the Essential
tier defines exactly what can never be defaulted, which is what lets the escape be safe by
construction rather than by warning.

## The Essential set

Six items, reverse-engineered from what `logic.md`'s required sections cannot be written
non-vacuously without:

| Essential item | Section it feeds |
|---|---|
| **Purpose** — why this is being built | Conceptual model |
| **Consumers** — who or what uses it | Behavior & scenarios |
| **Success criteria** — what "working" means | Key decisions |
| **Hard constraints** — what must stay true for the consumer | Key decisions, Scope |
| **Scope boundary** — what is explicitly excluded | Scope & non-goals |
| **Primary behavior** — the main path through the thing | Behavior & scenarios |

Everything else is **Default-able**: it has a defensible recommended default that may be taken and
logged rather than asked.

`CONTRACT:` This list is **original to this spec**. The source paper's eight Essential elements are
prompt-shaped (Role, Input Format, Output Format, Model Settings) and do not transfer to a design
document. The research sweep found evidence **absent** for tiered frameworks applied to open-ended
design work. The list is grounded in a document that already exists — not in the paper's evidence —
and the skill must say so where it states the list.

## The altitude rule

**The test, applied per question:** *would the answer change what the consumer observes, or only how
it is built?*

Observable → ask it here. Build-only → do not ask it here.

**"Observable" is relative to the consumer.** For a UI the consumer is a person, so storage engine and
file layout are out of bounds. For an API or CLI the consumer is a developer, so response shape,
flag design, and exit codes *are* the observable surface and remain in bounds. The rule keys on
consequence-to-the-consumer, never on whether a topic sounds technical.

**The one escape:** an implementation choice may be asked when that choice *is itself* the
user-facing decision — the same exception the skill already grants for naming file structure. Stated
explicitly so it cannot be widened by rationalization.

**Routing, not discarding.** A build-only question that surfaces is captured in the existing
**Deferred Ideas** list tagged `[tech-spec]`, so the tech spec inherits an open question instead of
rediscovering it cold.

## Data flow

1. Phase A research returns findings *(existing)*
2. Each finding implying a decision becomes a **candidate question** *(new)*
3. Candidates pass the three screens; survivors become real questions *(new)*
4. Gray areas resolve as today, drawing from the screened candidate pool *(existing + wiring)*
5. Remaining clarifying questions **batch** via `AskUserQuestion`, ≤4 per call *(changed)*
6. **Essential-coverage gate** — diff what is established against the six; ask the gaps *(new)*
7. Past the gate, a recognized steer resolves remaining Default-able items to their recommended
   defaults, each tagged `assumed — fast-tracked` in Decisions Locked *(new)*
8. Design → approval → `logic.md` via `quirk:writing-specs` *(existing, untouched)*

## Behavior & scenarios

**Normal path.** Indistinguishable from today in shape; questions are better ordered, research-grounded,
and held at observable altitude. The coverage gate passes silently when clarification was thorough.

**Fast-track before coverage.** The steer is declined. The skill names the specific Essential items
still open, asks them, and does not skip. Declining is not a refusal of the user's instruction — it is
the skill reporting which decisions it cannot make on the user's behalf, then asking them.

**Fast-track after coverage.** Remaining Default-able items resolve to recommended defaults. Each
appears in Decisions Locked as `assumed — fast-tracked`, so an assumed decision is never
indistinguishable from an approved one.

**Build-only question surfaces.** Not asked; captured in Deferred Ideas tagged `[tech-spec]`.

**Research unavailable / offline.** The candidate pool is empty. The coverage gate still runs and the
altitude rule still applies. Research failure degrades question *quality*, never *coverage*.

**Trigger recognition.** The fast-track is a recognized free-text steer — "enough, design it", "go with
your recommendations", "stop asking and build it" — never an option inside an `AskUserQuestion` call.
Placing it in an option list would consume one of four slots and put a delegation option in front of
the user on every call, which the Checkpoint Rules forbid.

## Key decisions & rationale

**The rubric emits questions and never enters the spec.** Both research streams converge here:
rubric-based signals get gamed in proportion to model sophistication, and completeness checklists
plausibly induce feature creep. A checklist the same model is later scored against gets padded; one
that can only emit questions to a human cannot be. This kills the "give the logic spec an element
framework" half of the original idea and keeps only the gap-detector half.

**Two tiers, not the paper's three.** The third tier (best practices, confidence, model settings) is
prompt-specific with no design-document analogue. YAGNI applies to the skill itself.

**Batch size is not a design variable.** `AskUserQuestion` caps at four questions per call, so the
paper's ~9-per-turn is unreachable regardless. The change is *which steps* batch, not how many.

**Ordering by forking power.** A model cannot compute entropy, but "which answer eliminates the most
downstream options" is a usable proxy for the same idea, and the underlying technique was
load-bearing in the source research rather than incremental.

**No delegation offered; election permitted.** The Checkpoint Rules forbid the skill *offering* to
decide. They do not constrain the user *electing* to accept stated defaults. One added sentence draws
that line, leaving both the rule and the escape intact.

**Altitude screens research, not just the catalog.** Research findings skew implementation-heavy. Without
the altitude screen, wiring research into question generation would actively worsen the altitude
problem rather than being neutral to it.

## Scope & non-goals

**In scope**

- `skills/brainstorming/SKILL.md` — inline rules, one new checklist step, one new flow-graph node,
  amended Key Principle, amended Checkpoint Rules, gray-area catalog cleanup. Body capped at ~400 lines.
- `skills/brainstorming/references/essential-coverage.md` *(new)* — the Essential six and the
  fast-track procedure.
- `tests/` — new prose pins for each new mechanism; all existing assertions stay green.

**Out of scope**

- **Reverse-reasoning spec validation and the numeric quality gate.** These now belong to
  `quirk:writing-specs`, not brainstorming. Follow-up spec.
- **Persistent cross-session pattern memory.** Needs a storage format and likely a `bin/` script.
  Separate spec.
- **Outcome telemetry.** Would make this work falsifiable; a distinct mechanism.

`CONTRACT:` **`skills/writing-specs/` is not edited by this work.** Both new tags — `assumed —
fast-tracked` and `[tech-spec]` — are *content brainstorming produces* inside sections that already
exist, not new sections. This keeps the change at one skill and one review surface, and preserves the
cross-skill invariant at `tests/test_writing_specs_skill.py:48`, which requires "Industry Insights"
and "Deferred Ideas" to appear in both `brainstorming/SKILL.md` and `writing-specs/logic-spec.md`.

## Decisions Locked

**Essential tier**
- Two tiers: Essential + Default-able. The paper's third tier is dropped.
- Essential derived from what `logic.md`'s sections cannot be written without; capped at ~6.
- Consumed as a gap detector that emits questions only — never a spec section, never a score.

**Batching**
- Batching extends to the "remaining clarifying questions" step; existing 4-per-call cap holds.
- Order within a batch: most-forking-first, then foundational→edge-case.
- Research findings become *candidate* questions filtered by the screens — not questions directly.

**Fast-track**
- Available only once the Essential tier is covered.
- Unasked Default-able items take recommended defaults, each logged `assumed — fast-tracked`.
- Triggered by recognized free-text steer, never an option in a question list.
- Checkpoint Rules gains one sentence distinguishing offered delegation from user-elected defaults.

**Placement**
- Always-in-effect rules inline; the Essential list and fast-track procedure in `references/`.
- `SKILL.md` capped at ~400 lines.
- New prose pins for new rules; all existing pins preserved.

**Gate placement**
- A new explicit checklist step with its own flow-graph node, between "remaining clarifying
  questions" and "propose approaches". Renumbering is safe — no test pins checklist numbers.

**Altitude**
- Build-only questions captured in Deferred Ideas tagged `[tech-spec]`, not discarded.
- Hard rule with one stated escape: an implementation choice that *is* the user-facing decision.
- Operationalized as a one-line per-question test, composed as a third screen on the candidate pass.

## Industry Insights

**Supporting the design**

- Front-loaded structured clarification beat iterative refinement: structural completeness 47.1%→82.6%
  (d=2.98), NASA-TLX workload 39.6→21.7, satisfactory output in a single turn vs 1–12 unaided —
  https://arxiv.org/html/2608.01366 *(N=4 pilot; direction-consistent, effect sizes unstable)*
- Batched clarifying questions shorten dialogues and let users weigh question interdependencies
  holistically — https://arxiv.org/html/2508.08308v1 *(this partially dissolves the "batches cannot
  adapt mid-batch" objection: users see the dependencies themselves)*
- Entropy-based attribute selection was load-bearing, not incremental: 22–30% accuracy gain and 27.5%
  shorter conversations; ablating it dropped success 50%→39% with abandonment at 58.5% —
  https://arxiv.org/html/2606.24194
- Hybrid structured-choice + free-text interfaces outperform pure conversational elicitation —
  https://arxiv.org/pdf/2506.11610
- Question fatigue and cognitive load are real constraints in elicitation; initial specifications
  should deliberately omit detail that belongs in later clarification —
  https://arxiv.org/pdf/2507.02858

**Constraining the design**

- Rubric-based reward signals are gamed in proportion to model sophistication and evaluator
  transparency — https://arxiv.org/pdf/2506.19248 *(the reason the rubric never enters the spec)*
- Goodhart effects in LLM eval suites reach up to 112% score inflation; calibration bias rewards
  verbosity and confident tone — https://tianpan.co/blog/2026/04/14/goodharts-law-in-your-llm-eval-suite
- Self-preference bias in LLM judges is 4–8 points and model-agnostic, uncorrelated with capability —
  https://arxiv.org/html/2604.22891v2 *(supports deferring the numeric quality gate to a spec that can
  design cross-family judging properly)*
- Answer sufficiency is not correctness: 13–23% of high-information-lift sequences still produced
  incorrect answers — https://arxiv.org/html/2510.06478 *("asked enough" and "is it right" must stay
  separate gates; the second is out of scope here)*
- Completeness checklists plausibly induce feature creep in AI systems —
  https://blog.flurdy.com/2026/02/yagni-100-with-ai *(editorial, not empirical; the counter-argument
  that AI strengthens YAGNI is at https://www.natemeyvis.com/yagni-in-2026/)*

**Evidence gaps, stated plainly**

- Evidence is **absent** for tiered completeness frameworks applied to open-ended design work. Every
  published framework assumes a bounded domain with a predefined element set. The Essential six are
  therefore original and unvalidated.
- No empirical study compares 3 vs 5 vs 7 batched questions on abandonment or answer quality.
- The source paper performed **no component ablation**, so it cannot attribute its effect to any
  individual mechanism. Adopting a subset is a judgment call, not an evidence-backed one.

**Session observation (not a finding)**

The design session that produced this spec took the recommended option on all 17 drill-in questions.
That is either well-calibrated recommendations or question fatigue, and the two are indistinguishable
from inside the session. It is a live argument for the fast-track and a caution that batching may make
assent cheaper rather than better-considered.

## Deferred Ideas

- **Outcome telemetry** — recording execution-phase rework per spec, which is what would make every
  mechanism here falsifiable. Raised during design; a distinct mechanism.
- **Reverse-reasoning spec validation** — a fresh-context agent builds a pseudo-plan from `logic.md`
  alone; divergence from conversation intent reveals ambiguity invisible to the author. Belongs to
  `quirk:writing-specs`.
- **Numeric spec-quality gate** — multi-criteria scoring with a cross-family judge, routed through
  existing `adversarial-review` / `pi-watch` infrastructure. Belongs to `quirk:writing-specs`.
- **Persistent pattern memory** — recurrence-weighted store seeding future gray-area questions.
  Needs storage design and a `bin/` script.

## Glossary

| Term | Definition |
|---|---|
| **Elicitation controller** | The combined tier + altitude + ordering logic governing which questions get asked. Governs dialogue, never the document. |
| **Essential tier** | The six items that must be user-determined before design begins; never defaultable. |
| **Default-able tier** | Everything else — has a defensible recommended default that may be taken and logged. |
| **Candidate question** | A question derived from a research finding, before the three screens decide whether it is asked. |
| **Altitude** | Whether a question's answer changes what the consumer observes (in bounds) or only how the thing is built (out of bounds). |
| **Most-forking-first** | Ordering heuristic: ask first whatever answer eliminates the most downstream options. |
| **Fast-track** | User-initiated acceptance of recommended defaults for all remaining Default-able items; legal only after Essential coverage. |
| **Coverage gate** | The checklist step that diffs established decisions against the Essential six and asks the gaps. |

## Status & amendments

**Status:** Implemented. Complexity-tier gate **fired** on ≳3 source files; `tech.md` authored,
reviewed, and built from.

**Amendments:**
- *2026-09-14* — Deferred Ideas filed to `DEFERRED.md` as DEFER-7 (writing-specs validation layer),
  DEFER-8 (pattern memory), DEFER-9 (outcome telemetry), so the pm-agent can see them; the spec
  section remains their design home.
- *2026-09-14* — Outcome-altitude discipline added during design review at user request, after the
  initial three-direction design was presented. Added the altitude screen, the routing tag, and the
  gray-area catalog cleanup; promoted the design from three mechanisms to four. No previously locked
  decision was reversed — all six Essential items were already observable-altitude.
- *2026-09-14* — Review fix: Hard constraints narrowed to the consumer-visible kind, since the
  altitude screen would otherwise reject the very question the gate needs answered. An imposed
  build-only constraint routes to `[tech-spec]` and never blocks the coverage gate.
