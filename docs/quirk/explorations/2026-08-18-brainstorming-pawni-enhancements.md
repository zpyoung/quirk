> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: Enhancing quirk:brainstorming with learnings from PAWNI (arXiv 2608.01366)

**Date**: 2026-08-18 · **Emphasis**: blended · **Intensity**: 0.5 (Exploratory)

## Framing

How can the `quirk:brainstorming` skill be enhanced with learnings from *"Asking Questions the Right Way: A Multi-Agent Conversational System for Prompt Formulation in Complex Task Resolution"* (Sankar, Yadav, Girish, Amogh A S — IISc Bangalore, arXiv 2608.01366v1)? The paper presents PAWNI, an 8-agent pipeline that front-loads guided Q&A to turn vague user queries into structured prompts. Its problem — eliciting a complete, unambiguous specification from a user before expensive downstream work — is structurally the same problem brainstorming solves, making it a near-direct analogical source.

Scoped to: the paper (primary source, read in full via two targeted passes) + the current `skills/brainstorming/SKILL.md`. No wider literature sweep.

## What was explored

- **Research facets**: PAWNI's Architect Q&A strategy (question selection, ordering, batching, stopping); Scout dual-track domain knowledge; pattern-file self-evolving knowledge base; Forge/Judge/Mirror reverse-reasoning loop; study findings and limitations.
- **Ideation**: mapped each PAWNI mechanism onto the brainstorming skill's current phases (context research → gray areas → clarifying questions → design → logic spec → self-review) and generated enhancement directions where the mapping surfaced a real gap.
- **Left out of scope**: POML/Cipher structured-output format (logic spec is already a structured markdown template — weak mapping, rejected at quality gate); EEG/cognitive-load measurement methodology (not actionable for a skill).
- _Ran headless:_ plan-preview and idea-landscape checkpoints auto-skipped (autonomous turn). Defaults taken: emphasis=blended, wild=0.5, scope = paper + skill only.

## Findings / Idea landscape

### Key findings from the paper (grounding for the directions)

- **Front-loaded structured clarification beat iterative refinement decisively**: 100% vs 70% task-criteria satisfaction; single-turn success vs 1–12 unaided turns; quality score 3.12→4.56 (d=2.07). — §Results
- **Structural completeness was the strongest measured lever**: 47.1%→82.6% of prompt elements present (d=2.98), driven by an 18-element / three-tier framework (8 Essential, 7 Enhancement, 3 Elevation) with gap-detection against it. — §Framework
- **Batched multiple-choice questions (~9/turn) *reduced* subjective workload**: NASA-TLX 39.6→21.7 (−43%), frustration −57%. Load was *redistributed* from iterative correction into upfront structuring, not eliminated. — §RQ2
- **Questions were grounded in fetched domain knowledge** (Scout's dual track: task-type best practices + topic-specific context) and **prioritized by pattern weights** (conventions confirmed across prior invocations asked first). — §Architect, §Scout
- **Reverse-reasoning validation**: generate the ideal *response* from the draft prompt, judge it with 4 LLMs against a 4-criterion rubric, refine via Mirror; threshold 8/10, max 3 iterations. Exposes implicit assumptions the drafter cannot see. — §Forge/Judge/Mirror
- **Users kept an escape hatch**: `/done` ends clarification at any point. — §Architect
- **Caveats**: N=4 pilot; direction consistency (4/4) is the evidence, not effect sizes; **no component ablation** — the paper cannot say which mechanism carried the effect; failure modes of the guided Q&A are not catalogued. — §7.8, §Limitations

### Direction: Tiered element-completeness rubric with gap-driven questioning

Give the logic spec an explicit Essential/Enhancement/Elevation element framework (analogous to PAWNI's 18 elements — e.g. Essential: goal, users, constraints, success criteria, scope/non-goals, error behavior, data shape, integration surface). At the start of clarification, diff the user's request against the Essential tier and generate questions *from the detected gaps*, rather than only from the domain gray-area catalog. The catalog covers domain ambiguity; nothing today checks element coverage.
*why this might actually work:* structural completeness was PAWNI's largest measured effect (47%→83%, d=2.98), and the skill currently has no completeness model at all — its self-review checks for placeholders, not absences.
*surfaced by:* analogical-transfer · *sits at intensity:* Grounded

### Direction: Reverse-reasoning spec validation (a Forge/Judge for logic specs)

Before the user-review gate, spawn a fresh-context agent that reads *only* the logic spec (no conversation history) and produces a brief pseudo-plan of what it would build. A judge compares that pseudo-plan against the conversation's actual requirements; divergences are ambiguities in the spec, fixed before the user ever reviews it. Bounded like PAWNI: max 2–3 iterations, then ship best version.
*why this might actually work:* the spec author cannot see their own ambiguity — PAWNI's Forge step exists precisely to "expose implicit assumptions"; a fresh reader is a harness that can genuinely detect failure, unlike the current same-context self-review.
*surfaced by:* analogical-transfer · *sits at intensity:* Exploratory

### Direction: Persistent pattern memory across brainstorming sessions

A lightweight, append-only pattern store (per domain: which gray areas the user selected, which options they chose, which research findings recurred), with simple recurrence counts instead of PAWNI's pgvector embeddings. Future sessions seed gray-area questions high-weight-first and pre-mark recurring choices as the recommended option. Could live in the plugin's data dir or piggyback on Claude's memory directory.
*why this might actually work:* PAWNI's pattern files are what made its questioning *adaptive* rather than checklist-shaped; brainstorming currently re-derives everything each session — the only reuse rule is "same session."
*surfaced by:* analogical-transfer · *sits at intensity:* Exploratory

### Direction: Hard-wire research findings into question generation

Make the Phase A research → questions link mechanical instead of the current soft "refine wording": every research finding that implies a decision becomes a candidate question, with the finding cited in the option descriptions ("PAWNI-style: knowledge-grounded options"). Optionally split Phase A along PAWNI's dual track — one agent for task-*type* conventions, one for this-*specific*-topic context — instead of the current patterns/anti-patterns split.
*why this might actually work:* PAWNI grounds every Architect question in Scout output, and grounded options are what let users answer with one keystroke instead of composing free-text; the skill already pays for the research, it just under-uses it.
*surfaced by:* analogical-transfer · *sits at intensity:* Grounded

### Direction: Lean harder into batching + an explicit fast-track escape

The skill's "one question at a time" core principle is contradicted by the paper's evidence: ~9 batched MCQs per turn *reduced* NASA-TLX workload 43%. Extend AskUserQuestion batching beyond gray-area drill-ins to the "remaining clarifying questions" step, and add a PAWNI-style `/done` escape: "enough — design it," which takes all remaining recommended defaults and records them as *Assumed (user fast-tracked)* in Decisions Locked (reconciling with the no-delegation rule by logging assumptions rather than hiding them).
*why this might actually work:* the paper's central cognitive-load finding is that structured batches beat drawn-out iterative dialogue — and the escape hatch is the mechanism PAWNI used to keep front-loading from feeling like an interrogation.
*surfaced by:* assumption-reversal (negating "one question at a time reduces load") · *sits at intensity:* Exploratory

### Direction: Numeric spec-quality gate with a cross-family judge

Score the finished logic spec against a 4-criterion rubric adapted from PAWNI's Judge (Essential elements present · alignment with user requirements · clarity/no ambiguity · structural completeness), each 0–10, threshold ~8, max 2 refinement iterations. Rather than new machinery, route through existing infrastructure: `quirk:adversarial-review` with a spec rubric, or a `pi-watch` cross-family reviewer (codex/gemini) per the user's established multi-model workflow.
*why this might actually work:* PAWNI bounded its refinement loop with a numeric threshold and multi-model mean — and the cross-family judge de-correlates errors the same way its 4-model panel did; the user already runs this pattern elsewhere.
*surfaced by:* analogical-transfer · *sits at intensity:* Bold

## Tensions & trade-offs

- **Batching pulls against dialogue quality.** The paper's load data favors big MCQ batches; the skill's one-at-a-time principle exists because sequential dialogue lets each answer reshape the next question. Batch questions can't adapt mid-batch.
- **The fast-track escape pulls against the no-delegation rule.** `/done` is functionally "you decide, for everything remaining." Logging assumptions softens but doesn't dissolve the conflict — a user who fast-tracks past an Essential-tier gap gets a spec with a silent hole that's now *labeled*, not *filled*.
- **Persistent pattern memory pulls against freshness and context-fit.** High-weight patterns front-load established conventions, but conventions learned on project A can mis-seed project B; PAWNI needed convergence tracking and a background merge crawler to keep files honest — complexity the lightweight version would omit.
- **Every validation loop pulls against cost and latency.** Reverse-reasoning + judge gates add agent calls to *every* brainstorm; the paper has **no ablation**, so adopting all mechanisms copies unvalidated complexity — some of PAWNI's effect may come from one or two components.
- **Rubric-driven completeness pulls against YAGNI.** An 18-element checklist invites filling elements because the rubric lists them; the skill's "YAGNI ruthlessly" principle pushes the other way. Tier gating (only Essential is mandatory) mitigates but doesn't eliminate.

## Challenge notes

- **Tiered element rubric** — steelman: the single largest measured effect in the paper, and the cheapest to adopt (a checklist plus gap-diff, no new agents). · strongest counter: prompts and logic specs are different artifacts; PAWNI's elements (Role, Output Format, Model Settings…) mostly don't transfer, so the tier *structure* transfers but the element *list* must be invented — and an invented list carries none of the paper's evidence. · would be disproven if: specs written with the rubric show the same execution-phase rework rate as specs without it.
- **Reverse-reasoning spec validation** — steelman: it's the only proposed mechanism that detects the failure mode nothing currently catches (ambiguity invisible to the author), and fresh-context reading is a provably-can-fail harness. · strongest counter: a pseudo-plan diverging from conversation intent may reflect the *reader* agent's weakness, not spec ambiguity — false positives could trigger needless refinement churn. · would be disproven if: seeded-ambiguity specs pass the forge-judge loop undetected (the harness can't actually detect the failure it exists for).
- **Persistent pattern memory** — steelman: adaptivity across sessions is the one PAWNI capability with no analogue anywhere in quirk, and recurrence counts are nearly free. · strongest counter: N of one user, low session volume per domain — weights may never accumulate enough signal to beat the static catalog, while stale patterns actively mislead. · would be disproven if: after ~10 sessions the store's top-weighted areas are the same ones the static catalog already lists.
- **Batching + fast-track** — steelman: directly evidence-backed (43% workload drop, 4/4 consistency) and reduces the skill's biggest friction (long serial Q&A). · strongest counter: N=4 pilot on prompt-formulation tasks, not software design dialogues; design questions have deeper dependencies between answers than prompt-element questions do. · would be disproven if: batched sessions produce more mid-design reversals ("actually, go back — my earlier answer changes this") than serial ones.

## Open questions & gaps

- What is the right Essential-tier element list *for a logic spec*? (The paper's 18 elements are prompt-shaped; this needs original design work.)
- Where should persistent pattern memory live — plugin data dir, repo `docs/quirk/`, or Claude's memory system — and is cross-project sharing wanted or a leak?
- Should the reverse-reasoning validator run on every spec or only above a complexity tier (mirroring `writing-tech-spec`'s existing gate)?
- No outcome telemetry exists today: without recording execution-phase rework per spec, none of these enhancements can be validated or disproven. (A meta-direction that makes every other direction falsifiable.)
- Coverage gap: no sweep of related work (other prompt-elicitation / requirements-elicitation systems) — this exploration is single-paper by scope.

## Sources

- All PAWNI claims (framework, agents, pattern files, evaluation loop, all quantitative results and caveats) — https://arxiv.org/html/2608.01366v1 (fetched 2026-08-18, two targeted passes)
- Current brainstorming skill behavior — `skills/brainstorming/SKILL.md` (quirk repo, read 2026-08-18)
- User's existing multi-model review infrastructure (pi-watch, adversarial-review) — user CLAUDE.md / quirk skill listing

---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
