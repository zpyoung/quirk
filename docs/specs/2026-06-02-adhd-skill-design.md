# ADHD Skill Design Specification

**Date**: 2026-06-02
**Status**: Approved for implementation
**Version**: 3 (supersedes PR draft `docs/specs/2026-05-30-adhd-skill-design.md`)

---

## Executive Summary

This spec defines the ADHD (divergent-ideation) skill as a **peer skill** at `skills/adhd/`. It provides a structured process for surfacing N non-obvious viable options at decision points through parallel agent dispatch and thinking frames.

Three rounds of research + adversarial review have produced a stable design. This spec represents the final locked decisions.

---

## Decision

Ship ADHD as a **peer skill** at `skills/adhd/`. Advisory opt-in sub-bullet in brainstorming step 6. No mandatory gates, no checklist changes, no process graph changes.

---

## Locked Decisions

| # | Question | Answer |
|---|---|---|
| 1 | Port style | **Verbatim** upstream + one added paragraph (standalone exit + context handling + nesting fallback) + attribution footer |
| 2 | Naming | **Keep `adhd`** |
| 3 | Companion CLI | **Skill-only** — no `adhd-agent` npm dep |
| 4 | Brainstorming hook | **Advisory** sub-bullet in step 6 only — HARD-GATE, checklist, graph unchanged |
| 5 | Description routing guard | Description scoped to explicit `/adhd` + brainstorming-delegated only — no generic "brainstorm/ideate" trigger wording |
| 6 | Score/Cluster phase | Run **inline** by main agent — only Diverge (N) + Deepen (K) use the Task tool |
| 7 | Context handling | Summarize raw Task results in the *next turn* after they land — cannot intercept `tool_result` blocks |
| 8 | Nesting fallback | If deepen Tasks fail due to nesting depth, run deepen sequentially in-context |
| 9 | Standalone exit | After rendering output for explicit `/adhd`, skill releases control to normal agent loop |

---

## Why Peer Skill

| | `brainstorming` | `adhd` |
|---|---|---|
| **Goal** | Fuzzy idea → approved spec | Surface N non-obvious viable options |
| **Shape** | Sequential, conversational, gated | Parallel, mechanical, generator/critic-split |
| **When** | Every creative project (HARD-GATE) | Decision-point subroutine (5–10× cost) |
| **Integration** | Entry point for all creative work | Advisory opt-in from brainstorming step 6 |

### Rationale

Making ADHD a peer skill instead of integrating it into brainstorming:
- **Preserves brainstorming efficiency**: Brainstorming covers idea → spec lifecycle. ADHD is a point-in-time subroutine.
- **Manages cost**: ADHD is 5-10× more expensive (N+K parallel agents). Making it mandatory would bloat every brainstorming session.
- **Enables reusability**: ADHD can be invoked standalone or from other contexts, not just brainstorming.

---

## Files Changed

| File | Change |
|------|--------|
| `skills/adhd/SKILL.md` | **Create** — verbatim upstream + 3 added paragraphs (standalone exit, context handling, nesting fallback) |
| `skills/adhd/frames.md` | **Create** — verbatim upstream (15 thinking frames) |
| `skills/adhd/SOURCE-SPEC.md` | **Create** — verbatim upstream (design rationale) |
| `skills/adhd/UPSTREAM-LICENSE` | **Create** — MIT license (required for compliance) |
| `skills/adhd/reference/when-to-use.md` | **Create** — verbatim upstream (use case guidance) |
| `skills/adhd/reference/divergence-prompts.md` | **Create** — extracted prompts (quirk-original) |
| `skills/brainstorming/SKILL.md` | **Edit** — one advisory sub-bullet in "Exploring approaches" section |
| `.claude-plugin/plugin.json` | **Edit** — bump version 5.6.1 → 5.6.2, add keywords: `adhd`, `divergent-ideation`, `divergent-thinking` |
| `.claude-plugin/marketplace.json` | **Edit** — bump version 5.6.1 → 5.6.2 |
| `README.md` | **Edit** — skill count 15 → 16, add "divergent ideation" to description |
| `docs/specs/2026-06-02-adhd-skill-design.md` | **Create** — this spec |
| `tests/test_adhd_skill.py` | **Create** — 13 content-conformance assertions |

---

## Content Structure

### skills/adhd/SKILL.md

**Frontmatter**:
```yaml
---
name: adhd
description: "Divergent-ideation subroutine for surfacing N non-obvious viable options when facing decision points. Explicitly invoked via /adhd or delegated from brainstorming step 6. Uses parallel agent dispatch (Diverge + Deepen) + inline Score/Cluster to generate structured option lists with critiques."
---
```

**Key sections**:
1. When to use / When NOT to use
2. Cost profile (5-10× normal ideation)
3. Process overview (dot graph)
4. The Process (6 phases: Diverge → Score → Cluster → Deepen → Render → Exit)
5. Integration with brainstorming
6. Reference materials
7. Attribution footer

**Quirk-specific additions** (3 paragraphs):
- **Standalone exit**: After rendering `/adhd` output, release control to normal agent loop
- **Context handling**: Summarize Task results in next turn (cannot intercept tool_result blocks)
- **Nesting fallback**: If deepen fails due to nesting depth, run sequentially in-context

### skills/adhd/frames.md

15 thinking frames:
1. Constraint inversion
2. Opposite day
3. Time travel
4. Cross-domain analogy
5. Stakeholder rotation
6. Failure pre-mortem
7. Sensory shift
8. Scale extremes
9. Role reversal
10. Material substitution
11. Process reversal
12. Success post-mortem
13. Beginner's mind
14. Expert blind spots
15. Adjacent possible

Each frame includes:
- Principle
- Prompt template
- Example

### skills/adhd/reference/divergence-prompts.md

Quirk-original prompt templates for Task agents:
- Base template (applies to all frames)
- 15 frame-specific variants

Used during Diverge phase to ensure consistent, effective agent prompts.

---

## Tests (Content-Conformance)

`tests/test_adhd_skill.py` — 13 assertions:

1. **YAML frontmatter parse** — valid YAML structure
2. **Description length** — ≥50 characters (sufficient for routing)
3. **Routing guard** — description does NOT contain generic "brainstorm" or "ideate" triggers (prevents router collision with brainstorming skill)
4. **Upstream attribution** — SKILL.md contains "Attribution" section
5. **UPSTREAM-LICENSE file** — exists and is readable
6. **HARD-GATE presence** — SKILL.md contains `<HARD-GATE>` tag with clarification (advisory only, no mandatory gates)
7. **Standalone exit** — SKILL.md documents exit behavior after `/adhd`
8. **Score/Cluster inline** — SKILL.md clarifies these phases run inline (not via Task)
9. **Context handling** — SKILL.md documents "summarize in next turn" approach
10. **Nesting fallback** — SKILL.md documents sequential deepen fallback
11. **15 frames in frames.md** — all frames present with descriptions
12. **Output shape sections** — SKILL.md includes "Option A/B/C" + "Recommendation" structure
13. **Plugin keywords** — `plugin.json` contains `adhd`, `divergent-ideation`, `divergent-thinking`

**Note**: These validate SKILL.md structure, not runtime isolation. Live-agent isolation tests are deferred per the existing deferred list.

---

## Key Corrections from Adversarial Review

### 1. Routing Guard

**Problem**: Upstream description included "brainstorm/ideate intents" which would compete with quirk's brainstorming skill in the description-based router.

**Fix**: Narrowed description to explicit `/adhd` + brainstorming-delegated only. Removed generic "brainstorm" wording.

### 2. Context Interception Impossible

**Problem**: Original spec implied LLM could intercept its own `tool_result` blocks to summarize before they display.

**Fix**: Rewritten as "summarize in your next turn after results land" (this is technically feasible).

### 3. Score/Cluster Are Inline

**Problem**: Upstream cost math implied sub-Tasks for score+cluster but no prompts were provided.

**Fix**: Locked as inline main-agent work (lightweight heuristics, fast execution).

### 4. Nesting Fallback

**Problem**: ADHD invoked from brainstorming may exceed Task nesting depth during deepen phase.

**Fix**: Added sequential in-context fallback: "If deepen Tasks fail due to nesting, run deepen sequentially instead."

### 5. Standalone Exit

**Problem**: HARD-GATE language previously blocked follow-through after `/adhd` debugging (user couldn't continue conversation).

**Fix**: Added explicit exit transition: "After rendering output for explicit `/adhd`, skill releases control to normal agent loop."

---

## Deferred Enhancements

- **`adhd-agent` npm CLI** — standalone CLI tool for ADHD outside Quirk context
- **Wired gray-area trigger** — automatically invoke ADHD when brainstorming detects ≥3 gray areas + high uncertainty
- **Quirk-native voice rewrite** — current version uses upstream voice; could be rewritten in Quirk's terser style
- **Runtime-isolation test scenarios** — validate ADHD works when invoked from different entry points (standalone, brainstorming, nested)
- **N tiering by stakes** — use 3 frames for low-stakes, 5 for medium, 7 for high
- **ADHD in skill index** — add to `using-quirk` skill catalog + `dispatching-parallel-agents` cross-ref

---

## Integration with Brainstorming

### Advisory Sub-Bullet (Step 6)

In `skills/brainstorming/SKILL.md`, section "Exploring approaches", add:

> **Advisory**: For decisions with high uncertainty, 3+ gray areas, or meaningful architectural/UX stakes, consider using the `adhd` skill to surface non-obvious options through structured divergent ideation (5-10× cost, opt-in only)

### No Process Changes

- **HARD-GATE unchanged**: Still blocks implementation until design approved
- **Checklist unchanged**: ADHD is not a checklist step
- **Graph unchanged**: ADHD is not a graph node

### Delegation Pattern

When brainstorming delegates to ADHD:
1. Agent says: "This decision warrants ADHD. Invoking `/adhd` to explore alternatives..."
2. ADHD runs full process (Diverge → Score → Cluster → Deepen → Render)
3. ADHD returns structured output (Options A/B/C + Recommendation)
4. Brainstorming continues with informed options

---

## Upstream Attribution

This skill is based on the ADHD divergent-thinking framework originally developed as an open-source brainstorming methodology under the MIT license.

Quirk-specific additions:
1. Standalone exit + context handling
2. Nesting fallback
3. Score/Cluster inline clarification
4. Integration points with Quirk's brainstorming skill
5. Quirk-original divergence prompts (`reference/divergence-prompts.md`)

See `skills/adhd/UPSTREAM-LICENSE` for the original MIT license.

---

## Cost Profile

ADHD is 5-10× more expensive than normal ideation:
- **Diverge**: N parallel haiku agents (typically 5-7 frames × 30s each = 2.5-3.5 min)
- **Score**: Inline by main agent (fast, <30s)
- **Cluster**: Inline by main agent (fast, <30s)
- **Deepen**: K parallel sonnet agents (typically 3 clusters × 60s each = 3 min)
- **Total**: ~6-7 minutes + token costs for N+K agents

Use this when the decision justifies the cost:
- High-stakes architectural decisions
- User-facing features with high impact
- Decisions with 3+ gray areas or high uncertainty
- Performance-critical optimizations

---

## Success Criteria

1. **Routing works**: `/adhd` triggers the skill, no collision with brainstorming
2. **Brainstorming integration works**: Advisory sub-bullet appears, delegation pattern succeeds
3. **Tests pass**: All 13 content-conformance assertions pass
4. **Version bump**: `plugin.json` + `marketplace.json` show 5.6.2
5. **README accurate**: Skill count shows 16
6. **Attribution clear**: SKILL.md + UPSTREAM-LICENSE present

---

## Implementation Checklist

- [x] Create `skills/adhd/` directory structure
- [x] Create `skills/adhd/SKILL.md`
- [x] Create `skills/adhd/frames.md`
- [x] Create `skills/adhd/SOURCE-SPEC.md`
- [x] Create `skills/adhd/UPSTREAM-LICENSE`
- [x] Create `skills/adhd/reference/when-to-use.md`
- [x] Create `skills/adhd/reference/divergence-prompts.md`
- [x] Edit `skills/brainstorming/SKILL.md` (add advisory sub-bullet)
- [x] Edit `.claude-plugin/plugin.json` (bump version, add keywords)
- [x] Edit `.claude-plugin/marketplace.json` (bump version)
- [x] Edit `README.md` (update skill count)
- [x] Create `docs/specs/2026-06-02-adhd-skill-design.md`
- [ ] Create `tests/test_adhd_skill.py`
- [ ] Run all tests to verify implementation

---

**End of Spec v3 (2026-06-02)**
