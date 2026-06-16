# Exploring-Ideas Skill Design Specification

**Date**: 2026-06-16
**Status**: Approved for implementation
**Version**: 1

---

## Executive Summary

This spec defines `quirk:exploring-ideas` — a blended **deep-research + brainstorming** skill that helps the user explore a topic *without* converging to a spec or implementation plan. It reuses the `brainstorming` skill's process shape and Visual Companion GUI, but inverts its terminal gate: where `brainstorming` drives *fuzzy idea → approved spec → writing-plans*, `exploring-ideas` deliberately **dead-ends at an exploratory artifact** (a cited briefing and/or idea-landscape), with any move toward building left entirely to the user.

It is a single blended skill on an emphasis spectrum (research-heavy ↔ ideation-heavy), auto-detecting which way to lean from the request and confirming only when genuinely ambiguous.

---

## Decision

Ship `exploring-ideas` as a **peer skill** at `skills/exploring-ideas/`, alongside `brainstorming`. It copies the Visual Companion scripts in (self-contained), reuses the existing `web-research-agent`/`deep-research-agent` types as its research engine, applies a curated divergent-thinking toolkit, and enforces a hard "no spec" gate. Output auto-saves to `docs/quirk/explorations/`. A thin `/quirk:explore` command provides an explicit entry point in addition to natural-language triggering.

---

## Locked Decisions

| # | Area | Question | Answer |
|---|------|----------|--------|
| 1 | Scope | Structure | **One blended skill** — research and brainstorm on a spectrum, one pipeline |
| 2 | Scope | Trigger | **Natural language + slash command** (`using-quirk` description match + `/quirk:explore`) |
| 3 | Scope | Ambiguous intent | **Auto-detect emphasis**, confirm with one quick question only when unclear |
| 4 | Output | Primary output | **Adaptive exploration doc** — cited briefing (research) ↔ clustered idea-landscape (brainstorm); always framing + findings/ideas + open questions; **no locked decisions** |
| 5 | Output | Location | **`docs/quirk/explorations/YYYY-MM-DD-<topic>.md`** |
| 6 | Output | Save trigger | **Auto-save at end**, with an explicit NOT-a-spec banner |
| 7 | Output | After exploration | **Dead-end with optional, user-initiated handoff** to `brainstorming` → `writing-plans` |
| 8 | Reuse | Visual Companion | **Copy scripts into the skill** (self-contained) |
| 9 | Reuse | Research engine | **Reuse agent types + iterative loop** (Plan→Search→Reflect→Iterate; `web-research-agent` breadth, `deep-research-agent` depth) |
| 10 | Reuse | Up-front scoping | **Light scoping (2–4 questions)** — not the full gray-areas drill-in |
| 11 | Reuse | Packaging | **Inside the quirk plugin** (`skills/exploring-ideas/`) |
| 12 | Safeguards | Divergent techniques | **Curated toolkit, applied selectively** (SCAMPER, analogy, first-principles, assumption-reversal, "how might we", persona lenses) |
| 13 | Safeguards | Convergence guard | **Quota + iterate-past-obvious** — N distinct directions before drilling; push past clichéd first ideas |
| 14 | Safeguards | Anti-sycophancy | **Built-in challenge passes** — steelman + strongest counter-argument + "what would disprove this" |
| 15 | Safeguards | No-spec enforcement | **Hard gate** — must not emit specs, requirements, locked decisions, or implementation actions |
| 16 | Identity | Name | **`exploring-ideas`** (`quirk:exploring-ideas`, command `/quirk:explore`) |

---

## Why a Peer Skill (vs. extending `brainstorming`)

| | `brainstorming` | `exploring-ideas` |
|---|---|---|
| **Goal** | Fuzzy idea → approved spec | Explore a topic; surface findings + idea-landscape |
| **Convergence** | Converges; locks decisions | Refuses to converge; preserves tensions |
| **Terminal state** | Invokes `writing-plans` | Dead-ends at exploration doc; handoff is opt-in |
| **Output** | `docs/quirk/specs/…-design.md` | `docs/quirk/explorations/…md` (NOT-a-spec) |
| **Research role** | Side input to design decisions | The main event (when research-heavy) |
| **When** | You intend to build something | You want to learn / ideate, build decision deferred |

Extending `brainstorming` would have meant a mode flag on a skill whose entire spine (HARD-GATE → spec → writing-plans) assumes convergence. A peer skill keeps each skill's gate coherent and lets `exploring-ideas` reuse machinery without inheriting the convergence pressure.

---

## Identity, Triggers & the Inverted Gate

- **Skill id:** `quirk:exploring-ideas` · **Command:** `/quirk:explore`
- **Natural-language triggers** (via `using-quirk` description match): "do deep research on X", "research X", "let's brainstorm ideas around X", "explore X", "what are some ideas for X".
- **Description routing guard:** scope the description to exploration/research/brainstorm intent that explicitly does **not** ask to build, so it does not steal creative-build requests from `brainstorming`. When the user clearly wants to build, `brainstorming` wins (process-skill priority is unchanged).

### Inverted HARD-GATE

```
<HARD-GATE>
This skill explores. It MUST NOT produce a spec, requirements, locked
decisions, acceptance criteria, an implementation plan, or any
implementation action. The only artifact is an exploration document.
Moving toward building is ALWAYS user-initiated.
</HARD-GATE>
```

This mirrors `brainstorming`'s HARD-GATE in form but inverts its content: `brainstorming` forbids *implementing before design approval*; `exploring-ideas` forbids *converging at all*.

---

## Emphasis Auto-Detection

Detection only shifts weight between the two engines; most runs are blended.

| Signal in request | Lean | Effect |
|---|---|---|
| research, investigate, find, sources, evidence, compare, "what is", "state of" | Research-heavy | Deeper research loop (more rounds / `deep-research-agent`); ideation pass kept short |
| brainstorm, ideas, "what if", "ways to", "could we", imagine, riff | Ideation-heavy | Stronger divergent pass; research loop kept to grounding breadth |
| mixed / unclear | Blended | Balanced; **one** quick confirm question if genuinely ambiguous |

---

## Process / Architecture

```dot
digraph exploring {
  "Detect emphasis" [shape=box];
  "Light scoping (2-4 Q)" [shape=box];
  "Offer Visual Companion\n(own message, conditional)" [shape=box];
  "Research loop\n(Plan->Search->Reflect->Iterate)" [shape=box];
  "Divergent ideation pass\n(toolkit + quota + iterate-past-obvious)" [shape=box];
  "Challenge pass\n(steelman + counter + disprove)" [shape=box];
  "Synthesize adaptive artifact" [shape=box];
  "Auto-save (NOT-a-spec banner)" [shape=box];
  "Close: optional user-initiated handoff" [shape=doublecircle];

  "Detect emphasis" -> "Light scoping (2-4 Q)";
  "Light scoping (2-4 Q)" -> "Offer Visual Companion\n(own message, conditional)";
  "Offer Visual Companion\n(own message, conditional)" -> "Research loop\n(Plan->Search->Reflect->Iterate)";
  "Research loop\n(Plan->Search->Reflect->Iterate)" -> "Divergent ideation pass\n(toolkit + quota + iterate-past-obvious)";
  "Divergent ideation pass\n(toolkit + quota + iterate-past-obvious)" -> "Research loop\n(Plan->Search->Reflect->Iterate)" [label="gaps surfaced by ideation"];
  "Divergent ideation pass\n(toolkit + quota + iterate-past-obvious)" -> "Challenge pass\n(steelman + counter + disprove)";
  "Challenge pass\n(steelman + counter + disprove)" -> "Synthesize adaptive artifact";
  "Synthesize adaptive artifact" -> "Auto-save (NOT-a-spec banner)";
  "Auto-save (NOT-a-spec banner)" -> "Close: optional user-initiated handoff";
}
```

The Research loop and Divergent pass are weighted by emphasis (one may be brief), and feed each other: research grounds ideation; ideation surfaces new gaps to research.

### Component: Light Scoping (2–4 questions)

`AskUserQuestion`, recommended-option-first, no "you decide". Kept intentionally light so exploration stays open.

- **Research-leaning:** depth (quick scan / standard / deep multi-round), recency window, source preferences or exclusions, the curiosity/decision it serves.
- **Ideation-leaning:** the goal/problem, hard constraints, what "good" looks like, directions already considered (to avoid re-treading).

### Component: Research Engine (Plan → Search → Reflect → Iterate)

1. **Plan** — decompose the scoped topic into facets / sub-questions.
2. **Search (breadth)** — parallel `web-research-agent` (haiku) across facets, dispatched in a single message.
3. **Reflect** — identify gaps, contradictions, and unanswered questions.
4. **Iterate (depth)** — for deep requests, spawn `deep-research-agent` (sonnet, depth=2) on the highest-value gaps; loop **1–3 gap-driven rounds**. Stop when marginal new information drops off (guard against both premature stop *and* runaway).
5. **Provenance + anti-hallucination** — maintain a claim→source map; run a verification pass so only sourced claims enter the artifact (the "ReviewAgent" pattern). Mark unverifiable claims explicitly.

### Component: Divergent Ideation Engine

- **Curated toolkit, applied selectively** — choose the 1–2 most relevant of: SCAMPER, analogical / cross-domain transfer, first-principles decomposition, assumption-reversal, "how might we", persona lenses.
- **Quota** — surface **N (~5) genuinely distinct directions** before drilling into any one.
- **Iterate-past-obvious** — after the first pass, explicitly push for more unconventional variants and discard clichés (first ideas reflect training-data defaults).
- **Grounding** — seed directions with the research loop's findings so ideas are informed, not free-floating.

### Component: Challenge Pass (anti-sycophancy)

For each surviving direction / finding cluster: **steelman** it, then surface the **strongest counter-argument** and **"what would disprove this / why might this fail."** Light and constructive — the goal is honesty, not demolition. Captured into the artifact's Challenge notes.

### Component: Adaptive Output Artifact

Single template, adapts by emphasis; auto-saved to `docs/quirk/explorations/YYYY-MM-DD-<topic>.md`:

```markdown
> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: <topic>
**Date** · **Emphasis**: research-heavy | blended | ideation-heavy

## Framing
The question/goal and how it was scoped.

## What was explored
Facets / sub-questions investigated (research) and/or directions generated (brainstorm).

## Findings / Idea landscape
Cited findings grouped by theme (research) and/or clustered idea
directions with brief annotations (brainstorm). NO winner declared.

## Tensions & trade-offs
Where findings/directions conflict — preserved, not resolved.

## Challenge notes
Counter-arguments, failure modes, disproof conditions.

## Open questions & gaps
What's still unknown / worth exploring next.

## Sources
URLs / provenance for every cited claim.
```

No "Decisions Locked", no requirements, no implementation steps — by gate.

### Component: Visual Companion (reused)

Copy `server.cjs`, `helper.js`, `frame-template.html`, `start-server.sh`, `stop-server.sh` verbatim into `skills/exploring-ideas/scripts/`, plus a `visual-companion.md` (mechanics). Offered **once, in its own message**, only when visual output is anticipated (idea-landscape, option/cluster map, mind map, comparison matrix). Per-question rule unchanged: browser for visual artifacts, terminal for text choices.

### Close: Optional Handoff

End with a short recap and: *"This is exploration only. If you later want to turn a direction into something buildable, invoke `quirk:brainstorming` → `writing-plans`. Say the word and I'll carry [direction] over."* Never automatic.

---

## Files Changed

| File | Change |
|------|--------|
| `skills/exploring-ideas/SKILL.md` | **Create** — frontmatter + process (checklist + dot flow + the components above) |
| `skills/exploring-ideas/exploration-artifact-template.md` | **Create** — the adaptive artifact template |
| `skills/exploring-ideas/visual-companion.md` | **Create** — copied/trimmed companion mechanics |
| `skills/exploring-ideas/scripts/server.cjs` | **Create** — copied verbatim from `brainstorming` |
| `skills/exploring-ideas/scripts/helper.js` | **Create** — copied verbatim |
| `skills/exploring-ideas/scripts/frame-template.html` | **Create** — copied verbatim |
| `skills/exploring-ideas/scripts/start-server.sh` | **Create** — copied verbatim |
| `skills/exploring-ideas/scripts/stop-server.sh` | **Create** — copied verbatim |
| `commands/explore.md` | **Create** — thin `/quirk:explore` entry point that invokes the skill |
| `.claude-plugin/plugin.json` | **Edit** — bump 5.6.2 → 5.7.0; add keywords `research`, `deep-research`, `exploration`, `ideation` |
| `.claude-plugin/marketplace.json` | **Edit** — bump 5.6.2 → 5.7.0 |
| `README.md` | **Edit** — skill count 19 → 20; add "deep research & exploration" to description |

---

## Differentiation from Neighbors

- **vs `quirk:brainstorming`** — brainstorming converges to a spec and invokes `writing-plans`; `exploring-ideas` refuses to converge and dead-ends at an exploration doc.
- **vs the `deep-research` harness / `deep-research-agent`** — those are research-only pipelines producing a cited report; `exploring-ideas` wraps research with divergent ideation, the brainstorming GUI, anti-convergence safeguards, and the no-spec gate. It *uses* the research agents as an engine rather than competing with them.
- **vs `adhd`** — `adhd` is a point-in-time generator of N non-obvious options at a decision; `exploring-ideas` is a full session that may *use* divergent techniques but spans research + ideation + synthesis into a durable artifact.

---

## Error Handling & Fallbacks

- **Research agents unavailable / offline** — proceed in offline mode; mark findings "(offline — unverified)" and lean on the ideation engine; note the gap in the artifact.
- **Partial agent failure** — synthesize from what returned; record which facets lack coverage under Open questions & gaps.
- **`deep-research-agent` fails** — substitute two parallel `web-research-agent` calls (same fallback `brainstorming` uses).
- **Visual Companion can't launch** — fall back to terminal-only; never block the exploration on the GUI.
- **Topic too broad** — surface this early (like `brainstorming`'s scope check) and offer to split into sub-topics, each its own exploration.
- **Convergence pressure detected** ("just give me the plan / write the spec") — honor the user (user instructions outrank the skill) by offering the explicit handoff to `brainstorming`, rather than silently producing a spec inside this skill.

---

## Testing / Verification

- **Skill quality** — review against `quirk:writing-skills` (frontmatter, description triggering, progressive disclosure).
- **Scripts smoke test** — Visual Companion launches, serves the newest HTML, and captures `[data-choice]` clicks to the events file.
- **Dry-run walkthroughs** — one research prompt ("deep research on X") and one brainstorm prompt ("brainstorm ideas around Y"), each confirming: (a) no spec/requirements emitted, (b) artifact saved to `docs/quirk/explorations/` with the NOT-a-spec banner, (c) handoff offered but not auto-invoked, (d) challenge notes present.
- **Routing test** — a clear build request ("build me X") still routes to `brainstorming`, not `exploring-ideas`.

---

## Industry Insights

Distilled from 2026 research swarm (Phase A). Findings that shaped decisions:

- **Deep-research has a converged loop** — Plan → Search → Read → Reflect → Iterate → Synthesize is now standard across OpenAI/Gemini/Anthropic-style systems; multi-agent + a review/attribution pass materially outperforms single-agent and curbs hallucinated citations. → drove the Research Engine design and the provenance/verification pass. Sources: [Deep Research Agent Architectures](https://zylos.ai/research/2026-04-21-deep-research-agent-architectures), [OpenResearcher (arXiv)](https://arxiv.org/pdf/2603.20278), [Gemini Deep Research docs](https://ai.google.dev/gemini-api/docs/deep-research).
- **Divergent vs convergent are complementary, scaffolded — not separate modes** — modern systems blend them and scaffold the transition. → drove the single blended skill + emphasis spectrum. Sources: [Exploration vs. Fixation (arXiv)](https://arxiv.org/pdf/2512.18388), [Brainstorming vs Divergent Thinking](https://medium.com/creativity-hub-by-ideatrapp/brainstorming-vs-divergent-thinking-09d05719c64a).
- **The "idea landscape / briefing" is the right archetype for non-spec output** — maximum coverage, minimal forced conclusion, explicit blindspots; distinct from a decision document. → drove the adaptive artifact (no winner declared, tensions preserved). Source: [Gemini Deep Research docs](https://ai.google.dev/gemini-api/docs/deep-research).
- **AI brainstorming fails via sycophancy, premature convergence, and clichéd first ideas** — AI won't volunteer challenge; it must be structurally prompted, and obvious first ideas need active pushing-past. → drove the quota + iterate-past-obvious guard and the built-in challenge pass. Sources: [AI Sycophancy](https://www.seangoedecke.com/ai-sycophancy/), [Scaffolding Creativity: Divergent/Convergent LLM Personas (arXiv)](https://arxiv.org/pdf/2510.26490), [AI Can Supercharge Divergent Thinking](https://medium.com/@yujiisobe/ai-can-supercharge-divergent-thinking-modern-ai-like-chatgpt-can-generate-a-high-volume-of-ideas-b37e24c380cc).
- **Techniques that translate to a conversational AI partner** — SCAMPER, analogical/cross-domain transfer, first-principles, assumption-reversal, "how might we", persona lenses. → drove the curated toolkit.

---

## Deferred Ideas

Captured during discussion; out of scope for v1:

- **`deep-research` harness delegation** — wholesale delegating the research portion to the existing `deep-research` harness (rejected for v1 in favor of reusing agent types directly, for control over exploratory framing). Revisit if maintaining the loop proves costly.
- **Full gray-areas drill-in** — the heavier `brainstorming`-style multiSelect + per-area drill-in (rejected for v1 as over-gating; light scoping chosen instead).
- **"Seed a brainstorm" auto-carry** — automatically piping a chosen direction into `brainstorming` with context (kept as a manual, user-initiated offer in v1).
- **Shared Visual Companion module** — extracting the companion scripts into one shared location instead of copying per skill (deferred; self-contained copy chosen for v1 robustness).

---

*Generated via the `quirk:brainstorming` process (research swarm + gray-area resolution). Terminal state: implementation plan via `quirk:writing-plans`.*
