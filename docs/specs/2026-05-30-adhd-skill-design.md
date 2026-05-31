# ADHD skill incorporation — design

**Date:** 2026-05-30
**Issue:** [#1 Enhancement: ADHD](https://github.com/zpyoung/quirk/issues/1)
**Status:** Approved (decisions locked 2026-05-30)
**Upstream:** [UditAkhourii/adhd](https://github.com/UditAkhourii/adhd) ·
[preprint](https://adhdstack.github.io/)

## Problem

Quirk's `brainstorming` skill is sequential, conversational, and gated. It
turns a fuzzy idea into an approved spec. It does **not** widen the option
space at decision points where the obvious answer is likely wrong.

Issue #1 asks whether to fold the ADHD method (parallel divergent ideation
under cognitive frames, generator/critic split) into `brainstorming`, or
ship it as its own skill.

## Decision

Ship ADHD as a **peer skill** at `skills/adhd/`. Add a single advisory
hand-off from `brainstorming` step 6 ("Propose 2-3 approaches") so
brainstorming can delegate when stuck on the option space. Do not make
ADHD a mandatory step in any flow.

## Decisions Locked (2026-05-30)

| # | Question | Locked answer |
|---|---|---|
| 1 | Port style | **Verbatim** port of upstream `skills/adhd/SKILL.md` with attribution header. Preserves invariants (parallel isolated branches, mechanical generator/critic split) and gives Udit Akhouri full credit. |
| 2 | Naming | **Keep `adhd`.** Matches upstream, matches the preprint, matches the npm package, matches existing community recognition. Renaming would fragment discoverability. |
| 3 | Companion CLI | **Skill-only.** The `adhd-agent` npm CLI is referenced in the skill body but not a runtime dependency. The skill runs entirely via the Task tool inside Claude Code / Codex / Gemini CLI. |
| 4 | Brainstorming hook | **Advisory.** A single sub-bullet in step 6 explaining when to invoke ADHD as a subroutine. Not wired into gray-area resolution, not mandatory. |

## Architecture

```
skills/adhd/
├── SKILL.md                          # verbatim upstream + attribution footer
├── frames.md                         # verbatim — the 15 cognitive frames
├── SOURCE-SPEC.md                    # verbatim — original divergent-ideation spec
├── UPSTREAM-LICENSE                  # verbatim MIT license from upstream
└── reference/
    ├── when-to-use.md                # verbatim — use/don't-use catalog
    └── divergence-prompts.md         # new — extracted generator + critic prompts
```

### Components

- **`SKILL.md`** — frontmatter intact (description ≤600 chars for Codex
  compatibility), pre-flight 3-question gate, two-phase loop (Diverge →
  Focus), 15-frame table, output shape, anti-patterns, calibration, cost.
  Footer attributes upstream and links to companion docs.
- **`frames.md`** — full 15-frame reference with vantage prompts and tags.
- **`reference/divergence-prompts.md`** — quirk-original: extracts the
  exact generator and critic system-prompt strings into a copy-paste
  reference so Task tool calls don't require scrolling the main body.
- **`SOURCE-SPEC.md`** — the original prose spec, preserved verbatim for
  auditability per upstream convention.
- **`UPSTREAM-LICENSE`** — MIT license file from upstream, preserved
  verbatim per MIT § 1.

### Data / control flow

The skill itself orchestrates two phases via Claude Code's Task tool:

1. **Phase 1 (Diverge):** N parallel Task calls, one per frame. No shared
   context between branches. Generator-only system prompt. Each returns
   `k` JSON ideas.
2. **Phase 2 (Focus):** three sequential critic calls — Score, Cluster,
   Deepen. Deepen spawns one Task call per top-K survivor.

Total: ~10 Task calls per run, 30–90s wall clock, 5–10× a single-shot
answer.

### Brainstorming hook

Single sub-bullet added to `skills/brainstorming/SKILL.md` "Exploring
approaches" section:

> **Stuck on the option space?** If after Phase B research you cannot
> articulate 2–3 *structurally different* approaches (only minor
> variations of one underlying angle), the `adhd` skill is an opt-in
> subroutine for parallel divergent ideation under cognitive frames.
> Invoke it on the framed decision and use the returned `shortlist` +
> `traps` + `deepened` to seed the proposal; cite the ADHD run in the
> spec's **Industry Insights** section. ADHD costs roughly 5–10× a
> single answer — use it only at genuine decision points.

No changes to the HARD-GATE, no changes to the checklist count, no
changes to the process flow graph.

### Plugin registration

- `.claude-plugin/plugin.json` — bump version to `5.7.0`, add `adhd` and
  `divergent-ideation` to keywords.
- `.claude-plugin/marketplace.json` — bump version to `5.7.0`.
- `README.md` — bump skill count from 15 to 16, link the ADHD skill.

## Why peer skill, not merger

| | `brainstorming` (existing) | `adhd` (new) |
|---|---|---|
| Goal | Turn a fuzzy idea into an approved spec | Surface N non-obvious viable options at a decision point |
| Shape | Sequential, conversational, gated | Parallel, mechanical, generator/critic-split |
| Parallelism | External web research | Internal isolated ideation |
| Output | `docs/specs/*-design.md` | Wide set + shortlist + traps + deepened branches |
| When | Every creative project (HARD-GATE) | Decision-point subroutine (5–10× cost) |
| Cost | Cheap by default | Expensive — gated by self-judge |

Folding ADHD into `brainstorming/SKILL.md` would either bloat the
HARD-GATE flow with optional machinery, or weaken the divergence
invariants by mixing them with conversational clarifying questions. The
upstream skill is already battle-tested at this shape.

## Industry Insights

- **Premature convergence is the failure mode ADHD targets.** Autoregressive
  models bias toward the first three high-probability answers. CoT and ToT
  share context across branches and anchor each other. ADHD's load-bearing
  invariant is isolation, not search. ([preprint](https://adhdstack.github.io/),
  [vs-cot-and-tot.md](https://github.com/UditAkhourii/adhd/blob/main/documentation/vs-cot-and-tot.md))
- **Reported evals:** ADHD wins 5/6 problems vs single-shot baseline. Mean
  +5.17 novelty, +7.67 trap detection, +4.17 breadth, +3.00 actionability
  on a 0–10 scale, judged by an independent LLM with skeptical-staff-engineer
  prompt. ([evals.md](https://github.com/UditAkhourii/adhd/blob/main/documentation/evals.md))
  Limitations: 6 problems only, same-model judging, frame library is
  hand-authored, deepen quality confounds actionability.
- **Independent adoption:** [repowire](https://github.com/prassanna-ravishankar/repowire)
  ported ADHD to its mesh-orchestrator primitives in
  [PR #313](https://github.com/prassanna-ravishankar/repowire/pull/313)
  (merged). [The New Stack feature](https://thenewstack.io/claude-code-adhd/).
  Independent
  [evidence-based review](https://github.com/testdouble/han/blob/adhd-swarm-research/docs/research/adhd-application-to-han.md)
  with 11 sources / 8 validation rounds.
- **The generator/critic split must be mechanical.** Separate LLM calls
  with opposite system prompts — not promised in one prompt. Mixing them
  is the second anti-pattern called out in the upstream skill.

## Deferred Ideas

- **`adhd-agent` npm CLI as runtime dependency** — deferred. Skill-only
  for now; users can install the CLI separately if they want batch/offline
  runs.
- **Wire ADHD into a specific gray-area trigger** (e.g. when ≥3 gray
  areas resolve to "uncertain") — deferred. Advisory hook only for now;
  promote to gated trigger if usage data shows brainstorming users
  consistently get stuck at the same point.
- **Quirk-native rewrite of SKILL.md voice** — deferred. Verbatim port
  preserves invariants and gives upstream proper credit; rewrite can
  happen later if voice drift becomes a maintenance issue.
- **Test scenarios per `skills/writing-skills/testing-skills-with-subagents.md`** —
  deferred to a follow-up PR.
- **Add ADHD to `using-quirk/SKILL.md` skill index** — deferred to
  whatever PR refreshes that index (it currently doesn't enumerate skills).
- **Cross-reference from `dispatching-parallel-agents/SKILL.md`** —
  deferred; ADHD already documents its parallel-isolation invariant
  internally.

## Acceptance

- `skills/adhd/SKILL.md` loads with valid YAML frontmatter and a
  description ≤600 chars.
- All 15 frames present in `frames.md`.
- Generator and critic prompts in `reference/divergence-prompts.md` are
  byte-identical to those in `SKILL.md`.
- `brainstorming/SKILL.md` references the new skill in step 6 only — not
  in the HARD-GATE, not in the checklist, not in the process graph.
- `.claude-plugin/plugin.json` and `marketplace.json` bumped to `5.7.0`.
- `README.md` skill count updated.
- Upstream MIT license preserved at `skills/adhd/UPSTREAM-LICENSE`.
- Attribution to Udit Akhouri visible in `SKILL.md` footer.
