# Design Spec: `writing-skills` Skill Rewrite

**Date:** 2026-07-05
**Status:** Approved design — ready for implementation planning
**Target:** `skills/writing-skills/` in the quirk plugin
**Informed by:** [docs/quirk/explorations/2026-07-05-writing-claude-code-skills.md](../explorations/2026-07-05-writing-claude-code-skills.md) (22-agent deep dive)
**Audience:** the author's own workflows (subagent/Team-heavy orchestration), general-usable but not general-first.

---

## 1. Problem & Goal

The current `writing-skills` skill is a strong `obra/superpowers` descendant whose two load-bearing doctrines overreach and whose biggest real-world gap goes unaddressed:

- **Overclaim 1 — CSO "body-skip":** "if a description summarizes the workflow, Claude follows it and skips the body" is single-source (obra N=1), never replicated, and contradicted by official docs (which say description = *both* what + when, and to be assertive).
- **Overclaim 2 — Iron Law:** "no skill without a failing test first, including edits, no exceptions" is refuted as universal by Anthropic's own conditional guidance and by obra's later walk-back — and it contradicts the skill's *own* skill-type carve-outs.
- **Overclaim 3 — Rationalization-resistance as default posture:** it's a niche toolkit for one of four skill types, not the organizing principle; official tooling flags the all-caps MUST/NEVER style it depends on as a "yellow flag."
- **Biggest gap — Activation/triggering:** the community's #1 reported failure mode (skills that never fire) is barely mentioned; the skill optimizes the body and assumes triggering is handled.
- **Unaddressed areas:** supply-chain/security (author + consumer), and skill availability inside subagents/Teams — the latter directly load-bearing for this author's workflow.

**Goal:** a substantial restructure that keeps the skill's validated instincts, corrects the overclaims to their defensible scope, foregrounds activation, and adds the missing sections — while dogfooding the practices it teaches. Findings are stated **directionally** (no unverified numbers, no version-pinned bug references), the skill stays **self-contained**, and SKILL.md stays **under ~500 lines**.

---

## 2. Architecture: SKILL.md as a lean hub + one-level-deep references

The rewritten `SKILL.md` is a spine/table-of-contents that points to reference files loaded on demand. Every reference is one level deep from SKILL.md (dogfooding the skill's own rule).

### 2.1 SKILL.md sections (in order)

1. **Overview** — what a skill is; the **two-failure-mode mental model** (Activation vs Execution) as the organizing frame; a short **lineage note** attributing TDD / CSO / Iron Law to `obra/superpowers` and naming the official frame (evaluation-driven-development).
2. **When to create a skill** (tightened) + a brief **Skills vs Commands vs Subagents vs CLAUDE.md vs MCP** decision spine.
3. **Skill types** — discipline-enforcing / technique / pattern / reference / creative. Promoted to load-bearing: it drives testing rigor downstream.
4. **Activation** (the foregrounded #1 failure mode) — description = **both what + when**, trigger-forward, keyword/synonym coverage, appropriately assertive phrasing; `name` matches directory; a should-trigger / should-not-trigger test set. → reference `activation-testing.md`.
5. **Execution** — progressive disclosure, degrees of freedom, **operationalize rules (don't just describe them)**, workflows/checklists, one excellent example.
6. **Testing & validation, scoped by skill type** — RED-GREEN-REFACTOR with the **Iron Law scoped to discipline-enforcing skills**; lighter application / retrieval / **rubric** validation for the rest; explicit **subjective/creative carve-out**. → reference `testing-skills-with-subagents.md`.
7. **Discipline-enforcing skills (scoped)** — rationalization-resistance, red-flags, operationalization; all-caps MUST/NEVER **softened from the default**. → reference `persuasion-principles.md` (with a scope note).
8. **Skills in subagents / Teams** (new; durable principles only) — a dispatched subagent may not see custom skills; built-in agents may not access them; GREEN-phase tests must **confirm the skill actually loaded**, not assume it.
9. **CSO, reframed** — the "description-summary → body-skip" claim as a **hedged, attributed hypothesis**, with the official "both what + when, be assertive" contrast.
10. **Structure & token discipline** — progressive disclosure, one-level-deep references (also converts the skill's own `@file` links to markdown links), body budget, flowchart usage (kept), naming conventions.
11. **Security & trust** — brief inline summary → reference `security-vetting.md`.
12. **Deployment** — checklist (kept) + short **distribution note** (default team-private; publish only if generalizable and maintained).

### 2.2 Reference files

| File | Disposition | Change |
|---|---|---|
| `testing-skills-with-subagents.md` | Keep | Reframe intro to scope to discipline-enforcing skills; keep the pressure-testing methodology. |
| `persuasion-principles.md` | Keep | Add a scope note (applies to discipline skills; not a default posture). |
| `anthropic-best-practices.md` | Keep + freshness header | Add a snapshot/"may drift" note + canonical URL; otherwise verbatim (on-demand, offline-safe). |
| `graphviz-conventions.dot` | Keep | No change. |
| `render-graphs.js` | Keep | No change. |
| `examples/CLAUDE_MD_TESTING.md` | Keep | No change (referenced by the testing methodology). |
| `activation-testing.md` | **New** | The description-eval loop: should-trigger/should-not-trigger set, train/held-out split, iterate. |
| `security-vetting.md` | **New** | Author side (principle of least surprise) + consumer side (vetting checklist), durable practices only. |

---

## 3. Decisions Locked

**Area 1 — Scope & risk**
- Substantial restructure (not surgical, not full rebuild).
- Audience: the author's own workflows (subagent/Team-heavy); general-usable but not general-first.
- Findings stated **directionally**; drop single-source/unverified hard numbers (versions, Snyk/ETH/Vercel figures, star counts).
- **Sharpen the skill's own `description`** to front-load real triggers (skill authoring, SKILL.md, frontmatter, "skill won't activate", editing a skill) — dogfooding.

**Area 2 — TDD / Iron-Law spine**
- Primary spine = **two-failure-mode** (Activation vs Execution), with testing scoped by skill type underneath.
- Iron Law **scoped by skill type** (discipline-enforcing keep failing-test-first; others get lighter/conditional validation; subjective/creative carve-out).
- Rationalization tables + `persuasion-principles.md` **kept but scoped + softened** (not removed).
- CSO body-skip claim **reframed as a hedged, attributed hypothesis** with official contrast.

**Area 3 — Security & operational gotchas**
- Security coverage = **both author + consumer**, as a compact checklist.
- Security lives in a **dedicated reference file** (`security-vetting.md`).
- **Dedicated "skills in subagents/Teams" section** in SKILL.md.
- **Omit volatile/version-specific mechanics and named bugs** → security + subagent content stays at the level of durable principles.

**Area 4 — File structure & bundling**
- `anthropic-best-practices.md` **kept as bundled reference + freshness pointer**.
- New content organized as **focused one-level-deep reference files** with a lean SKILL.md hub.
- SKILL.md body target **under ~500 lines**.

---

## 4. Industry Insights (from the deep dive; see exploration doc for full citations)

Directional findings that shaped the design. Primary/high-confidence sources are directly fetched; specific mid-2026 statistics are single-source and deliberately **not** quoted as numbers in the skill.

- **Activation is the dominant failure mode.** Practitioner reports and controlled experiments converge: baseline auto-activation is low; assertive, trigger-forward descriptions plus keyword coverage raise it substantially. Anthropic's own `skill-creator` tells authors to make descriptions "pushy" to combat under-triggering. Sources: `code.claude.com/docs/en/skills` (triggering troubleshooting), `github.com/anthropics/skills` (skill-creator), Seleznov activation study, Scott Spence, Marc Bara (activation vs execution split).
- **CSO body-skip is folklore.** Traces to one obra anecdote; no independent replication; official docs say description = both what + when. Source: `github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md`, `platform.claude.com/.../best-practices`.
- **Iron Law is too universal.** Anthropic conditions rigor on skill type ("subjective outputs often don't need tests… let the user decide"); obra's own repo cut enforcement scaffolding (issue #832). Source: `github.com/anthropics/skills` skill-creator, `github.com/obra/superpowers/issues/832`.
- **Rationalization-resistance is a scoped subtype toolkit,** not a general posture; official style guidance flags all-caps MUST/NEVER as a yellow flag. Independently, the technique *is* validated for guardrail skills ("operationalize the rule, don't just describe it" — reproduced by practitioners). Source: `anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills`, skill-creator, r/ClaudeAI eval-harness threads.
- **Progressive disclosure, one-level-deep references, token discipline** — confirmed by official docs and the open spec (`agentskills.io`).
- **Security is a live 2026 concern** (malicious skills, invisible-Unicode instructions, test-file execution surface, tool-declarations-are-not-a-sandbox) — spans authoring and consuming. Directional; specifics omitted per Area 3. Source: Snyk ToxicSkills, Embrace The Red, `agnix` linter.
- **Subagent skill access is limited** — dispatched/built-in agents may not see custom skills; relevant to Team orchestration. Directional; version specifics omitted.

---

## 5. Deferred Ideas (captured, out of scope)

- Deep marketplace/distribution coverage (personal audience → kept to a short note).
- A visual divergence-map artifact of the exploration.
- A verification pass to harden the single-source mid-2026 numbers (author chose directional framing instead).
- Broad team/enterprise governance of skills (org catalogs, SSO-gated deployment) — not relevant to a personal-workflow audience.

---

## 6. Validating the rewrite (dogfood)

Because this is a skill *about* testing skills, validation applies the skill to itself, kept light:
- **Activation check:** confirm the sharpened `description` triggers on realistic skill-authoring prompts and doesn't over-fire.
- **Execution check:** read the restructured body against its own two-failure-mode and skill-type-scoped criteria; confirm the Iron-Law scoping no longer self-contradicts.
- **Structural check:** references one level deep; no `@file` force-loads; SKILL.md under ~500 lines.

---

## 7. Success Criteria

1. SKILL.md reorganized around Activation vs Execution, under ~500 lines, references one level deep (markdown links, no `@`).
2. Iron Law scoped by skill type; internal self-contradiction resolved; subjective/creative carve-out explicit.
3. CSO claim reframed as attributed hypothesis with official contrast.
4. Rationalization machinery retained but scoped to discipline skills and stylistically softened.
5. New `activation-testing.md` and `security-vetting.md` present; new "skills in subagents/Teams" section present.
6. `anthropic-best-practices.md` retained with a freshness header.
7. Skill's own description sharpened.
8. No unverified hard numbers, no version-pinned bug references anywhere.
