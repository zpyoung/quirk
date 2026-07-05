> ⚠️ **THIS IS AN EXPLORATION — NOT A SPEC.**
> It captures research and a landscape of options for updating the `quirk:writing-skills`
> skill. It declares **no winner**, locks **no decisions**, and contains **no implementation
> plan**. Turning any direction into changes is a separate, user-initiated step
> (`quirk:brainstorming` → `writing-plans`).

# Deep Dive: Writing Claude Code Skills (to inform updating `quirk:writing-skills`)

**Date:** 2026-07-05
**Emphasis:** research-heavy · **Intensity:** 0.5 (exploratory)
**Source lean:** community/Reddit-forward, with official docs as ground truth and divergences flagged
**Method:** 22-agent fan-out (12 breadth web+Reddit findings · 5 adversarial verdicts on contested claims · 1 completeness critic · 4 gap-fill deep dives). ~1.5M research tokens, 612 tool calls.

---

## 1. Framing

The current `quirk:writing-skills` skill is a direct descendant of Jesse Vincent's (**obra**) **`superpowers`** lineage. Its spine is *"writing skills IS TDD for process documentation"*: RED (pressure-test a subagent without the skill) → GREEN (write the minimal skill) → REFACTOR (close rationalization loopholes), governed by an **Iron Law** ("no skill without a failing test first — including edits"), plus rationalization tables, red-flag lists, and Cialdini persuasion framing. It bundles Anthropic's official best-practices doc verbatim and centers a **CSO** ("Claude Search Optimization") rule: *description = ONLY when-to-use; if it summarizes the workflow, Claude follows the summary and skips the body.*

The deep dive asked: **where does 2026 practice (community-first) and current official guidance confirm, extend, contradict, or ignore that skill?** The answer is a clean four-way divergence map. The headline: the skill's *instincts* are largely right and often independently corroborated, but its two load-bearing doctrines (the CSO "body-skip" mechanism and the universal Iron Law) are **narrower and softer than the skill presents them**, and the skill is **silent on the two things the community argues about most in 2026** — reliable *triggering* and *skill supply-chain security*.

---

## 2. What was explored

Six web facets (triggering/descriptions · structure & progressive disclosure · anti-patterns · example repos · skill-vs-command/agent/CLAUDE.md/MCP · discovery & loading internals), three Reddit angles (sentiment · shared setups · skeptics), three deep dives (triggering mechanics · testing/eval methodology · plugins/marketplace ecosystem), five adversarial verifications of the most decision-relevant claims, and four gap-fill probes (subjective-skill carve-out · supply-chain security · distribution · subagent skill access).

---

## 3. The Divergence Map

Each finding is tagged by its relation to the **current** skill. This is the core deliverable — it tells you *where* a rewrite would add, cut, or correct.

### 3A. ✅ CONFIRMED — the skill is right, keep it (often now independently corroborated)

| Finding | Evidence / note |
|---|---|
| **Description is the single highest-leverage lever.** Get the trigger right before polishing body prose. | Near-universal across official docs, Reddit war stories ("I wrote 74 skills, most were theater — getting the trigger right beat any body wording"), and controlled experiments. |
| **Progressive disclosure architecture** (metadata preload → body on trigger → references on demand); **references one level deep**; TOC in long reference files. | Confirmed verbatim in Anthropic docs and the agentskills.io spec. Nested references cause partial (`head`-style) reads. |
| **Conciseness/token discipline is real** and people genuinely get it wrong. | A community tool author claimed dormant skills "burn 23k tokens/session"; commenters corrected — dormant skills cost only their ~100-token *description*, not the body. The confusion itself proves the discipline matters. |
| **For discipline-enforcing skills, operationalizing beats describing.** "Telling Claude what to *say back*, what an acceptable reply looks like, what failure looks like" constrains behavior; prose principles get rationalized away. | Independently reproduced by two practitioners (`rag-eval-harness` anecdote: a skill verbally acknowledged its own rule, then violated it under pressure until the refusal was scripted). This is the skill's central thesis, **validated in the wild**. |
| **"Don't ship untested instruction files"** is now officially endorsed, not just community lore. | Anthropic's own `skill-creator` ships a with-skill vs without-skill eval/benchmark pipeline. |
| **Skill-type differentiation** (discipline / technique / pattern / reference need different tests). | The skill already has this section — and it's the key to fixing the Iron Law tension below. |

### 3B. ➕ EXTEND — missing but fully compatible; high-value additions

| Gap | What the research shows | Why it matters for the rewrite |
|---|---|---|
| **The activation gap is the #1 real-world failure mode — and the skill barely mentions it.** | Baseline auto-activation is widely reported at **~20–56%**. Directive/"pushy" descriptions alone push to **~88–100%** in controlled trials; adding a `UserPromptSubmit` hook + `skill-rules.json` reaches ~84–95%+. Anthropic's *own* `skill-creator` tells authors to make descriptions **"pushy"** because "Claude has a tendency to *undertrigger* skills." | The skill optimizes the body and assumes CSO handles triggering. In practice a perfect body is wasted if the skill never fires. Needs a **dedicated "make it trigger" section**. |
| **Split ACTIVATION failure from EXECUTION failure.** | Two *different* problems with *different* fixes: (a) skill never invoked (well-evidenced; fixed by description engineering), (b) skill loads but Claude skips internal steps (real but under-studied — "no one has run a controlled experiment on step-level execution"). | The current CSO section conflates them under one banner. Separating them is the single clearest structural improvement. |
| **A rigorous, *official* description-testing loop already exists.** | `skill-creator`'s optimizer: ~20 labeled *should-trigger / should-not-trigger* queries, **60/40 train/held-out split**, 3 runs each for a trigger-rate estimate, iterate ≤5 rounds, pick the best description **by held-out score** (anti-overfit). The vendor-neutral agentskills.io spec documents the same method with a runnable script. | The skill's TDD tests whether the *body* is obeyed under pressure; this is a parallel discipline for whether the *description triggers*. The skill has no equivalent. |
| **Cite the real limits precisely; fix the units.** | `name` ≤ **64 chars, must match the parent directory name**; `description` ≤ **1024 chars** (spec validation). But Claude Code's *runtime listing* caps combined `description`+`when_to_use` at **1,536 chars/skill** (`skillListingMaxDescChars`) and total listing at **~1% of context window** (`skillListingBudgetFraction` / `SLASH_COMMAND_TOOL_CHAR_BUDGET`) — overflow silently **drops the least-invoked skills' descriptions first**. Body guidance is **500 *lines*, ~5000 tokens** — *not* "500 words." Metadata ≈ 100 tokens/skill. | The skill's invented word-budgets (`<150/<200/<500 words`) don't match reality and undershoot the body by ~3–5×. Concrete, verifiable numbers beat folklore for a technical audience. |
| **Full Claude-Code frontmatter field list.** | Beyond `name`/`description`: `when_to_use`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context: fork`, `agent`, `hooks`, `argument-hint`, `paths`. Only `description` is "recommended"; rest optional. (The 6-field open spec undershoots what CC supports.) | The skill lists ~2 fields + `context:fork`. Authors need the CC-specific set — especially `disable-model-invocation` for gated/side-effecting skills. |
| **Skill sprawl / cardinality is a first-class problem.** | Past ~10–20 skills, discovery degrades and least-used descriptions get dropped silently. Community consensus has swung to **many small single-purpose skills** over monolithic ones (tighter descriptions trigger more reliably). Audit which skills *actually fire* via session JSONL (`skillvitals`-type tools). | The skill assumes linear "add one, test one" growth. It should warn about the budget ceiling and recommend small scope + fire-rate auditing. |
| **Ecosystem: open standard + plugins + marketplaces.** | Agent Skills became an **open cross-tool standard** (agentskills.io) adopted by many agents; a skill can be portable, but **CC-only fields (`disable-model-invocation`, `context:fork`) aren't honored elsewhere**. Plugins are the distribution unit (bundle skills+MCP+hooks) with a semver/dependency system; install UIs now show a per-plugin **context-cost estimate**. | The skill is oriented to "CC + Codex personal/plugin" and never mentions portability implications or the plugin packaging/versioning layer. |
| **Lead with disambiguation: Skills vs Commands vs Subagents vs CLAUDE.md vs MCP.** | The single highest-signal community artifact found is a ~700-upvote thread literally titled *"Can someone explain the real difference between Hooks, Skills, Plugins, SKILL.md, CLAUDE.md and agents.md?"* Rough decision spine: external access → **MCP**; context isolation/specialist → **subagent**; reusable procedural knowledge → **skill**; user-controlled trigger → **command / `disable-model-invocation`**. Commands have effectively merged into skills. | A year after launch, *basic conceptual disambiguation* — not advanced TDD — is the dominant unmet need. The skill jumps straight into methodology assuming this is settled. |

### 3C. ⚠️ CONTRADICT — presented too strongly; needs revision

| Claim in current skill | Adversarial verdict | Recommended reframing |
|---|---|---|
| **"If a description summarizes the workflow, Claude follows it and SKIPS the body."** (CSO) | **MIXED.** Traces to a **single N=1 anecdote** in obra/superpowers (one skill did 1 review instead of 2). Never replicated; not in any official doc. Seleznov's rigorous 650-trial study tests *activation*, not post-load body-skipping. Official docs *contradict the framing*: description should be **both what-it-does AND when** — and be *pushy*, not minimal. | Demote from stated mechanism to **attributed, hedged hypothesis** ("one reported case… treat as worth testing in your own skills"). Fix "ONLY when-to-use" → "**both what + when, trigger-forward**." Note the irony (for a TDD skill) that this specific claim was never RED-GREEN-tested. |
| **"Iron Law: NO SKILL WITHOUT A FAILING TEST FIRST — including edits, no exceptions."** | **MIXED.** Core instinct sound for discipline skills; the *universal, edit-inclusive, no-exceptions* framing is refuted by (a) Anthropic's own `skill-creator`: "subjective outputs often don't need [tests]… let the user decide"; (b) obra's *own* repo walking back enforcement scaffolding (issue #832, ~69% line reduction, kept the Iron Law's substance, cut the tables); (c) the skill **already contradicts itself** — Iron-Law banner sits above its own "Testing All Skill Types" carve-outs. | **Scope it.** Keep RED-GREEN for discipline-enforcing skills. Make rigor **conditional on skill type**. Drop "including edits / delete means delete" as blanket — trivial/non-behavioral edits don't need a fresh RED. Add explicit **subjective/creative carve-out** (rubrics + human judgment, not failing tests). |
| **Skills are authored primarily to resist rationalization** (rationalization tables, Cialdini as default posture). | **REFUTED as a general principle.** Anthropic's engineering post never mentions rationalization/persuasion/Cialdini. Even obra scopes it to **1 of 4 skill types**. Most real skills are technique/reference where it's irrelevant. `skill-creator` explicitly flags **ALL-CAPS MUST/ALWAYS/NEVER as a "yellow flag"** — prefer explaining *why*. | Explicitly **demote to a scoped toolkit for discipline-enforcing skills only**. Soften caps-heavy rigid-rule style as the *default*; reserve it for the narrow case where flexibility is genuinely undesirable. |
| **"CSO" and "Iron Law" as if they were the standard vocabulary.** | Both are **community coinages** (obra/superpowers), not Anthropic terms. "CSO" appears in no official doc. | Attribute the lineage openly (the skill already half-does this for CSO) — a Reddit-leaning audience respects provenance honesty. |

### 3D. 🕳️ UNADDRESSED — whole areas the skill ignores that 2026 practice treats as central

> ⚠️ Several stats below come from single studies / mid-2026 sources beyond my training cutoff — see §7 provenance note. Directionally strong; specific numbers warrant a verification pass before quoting.

| Area | What surfaced | Relevance |
|---|---|---|
| **Supply-chain / malicious-skill security** | Snyk "ToxicSkills" reportedly scanned ~3,984 skills: ~**37% had ≥1 issue, ~13% critical**, ~36% showed prompt-injection patterns, dozens of live malicious payloads. Vectors: **invisible Unicode-tag instructions** (survive visual review), **shadow features**, and **test files that execute with full permissions but aren't scanned**. **`allowed-tools` is NOT enforced** — informational only (multiple open issues). "Principle of least surprise" is in Anthropic's own `skill-creator`. | The skill is authoring-only and **silent** on both making your skill *trustworthy-by-inspection* and *vetting a skill you didn't write* — the biggest live community conversation. |
| **Subagent skill access** | Skills preloaded into a dispatched subagent may **not fire** (subagents don't see the parent's `available_skills`); **built-in agents (Explore/Plan) can't access custom skills**; a subagent-preloaded skill loses `Agent` access unless its `tools:` includes it; nesting carries a severe (~7×/level) token multiplier. | **Directly load-bearing** given this user's heavy subagent/Team orchestration. A skill assumed available to a worker may be **silently broken**. The RED phase (no skill) is fine; the GREEN phase must *verify the skill actually loaded*. |
| **Distribution: public vs team-private** | Emerging default: **team-private** (commit to `.claude/skills/` in-repo) first; publish only if generalizable + battle-tested + you'll maintain it. **No official verified marketplace** exists (feature request closed "not planned"); ecosystem is fragmented across 8+ community hubs. | The skill's deployment checklist says "consider contributing back via PR" without the *when/whether* framework or the security-driven "default private." |
| **Versioning / deprecation** | **Stale skills are worse than none** — "they actively lie to the agent, and it trusts them over reality." Plugin semver/dependency system exists; `skill-creator` has an official "Improve" update mode. | The Iron Law treats "edits" as testable events but says nothing about changelog/version/deprecation discipline at scale. |
| **`disable-model-invocation` landmine** | Reported open bug: setting it can **hide the skill entirely** (not invokable by model *or* slash command). | Worth flagging when recommending the gated/manual-invocation pattern for dangerous skills. |

---

## 4. Divergent directions for the rewrite (options, not decisions)

Five non-obvious structural directions, each insight-paired. **No winner declared** — these are the shape of the option space if you later decide to build.

- **D1 — Reorganize around the two-failure-mode spine (Activation vs Execution).** *Insight:* it's how the best practitioners (Bara, Seleznov) and Anthropic's own tooling (a description-optimizer loop *and* a behavior eval) already split the work; the current single "CSO" banner hides the more common failure (never triggering).
- **D2 — Add an "Author *and* Consumer" half (security/vetting).** *Insight:* the loudest 2026 community question is "can I trust a skill I didn't write?" — an authoring-only guide is teaching in a vacuum the ecosystem no longer lives in.
- **D3 — Keep the powerful discipline machinery, but gate it behind the skill *type*.** *Insight:* resolves the skill's own internal contradiction (Iron-Law banner vs skill-type carve-outs) *and* aligns with both Anthropic guidance and obra's own walk-back — you lose nothing, you just stop over-applying it.
- **D4 — "Cite, don't invent."** Replace invented word-budgets and vague limits with the actual spec + runtime numbers and point to real tooling (`skill-creator`, agentskills.io validator, linters like `agnix`, fire-rate auditors). *Insight:* the audience is technical and Reddit-leaning; precision and named tools earn trust where round-number folklore loses it.
- **D5 — Attribute the lineage explicitly.** Label CSO / Iron Law / rationalization-tables as `superpowers` heritage and contrast with Anthropic-official side-by-side. *Insight:* provenance honesty is exactly what this audience rewards, and the skill already does it halfway for CSO.

---

## 5. Tensions & trade-offs (preserved, not resolved)

- **Pushy triggering ↔ over-triggering.** All the activation evidence is one-sided ("more directive = more activation"); the symmetric cost (false positives, firing on irrelevant prompts, token waste, skill collisions) is **under-studied**. "Always use ALWAYS" could teach authors to build noisy skills.
- **Enforcement style ↔ official style.** The skill leans on ALL-CAPS MUST/NEVER + rationalization tables; `skill-creator` calls that a "yellow flag" and prefers "explain the why." Community field-evidence says *operationalized* rules work — but "operationalized" (scripted refusals, checklists) is not the same as "shouty."
- **Minimalism ↔ enforcement bulk.** RED-GREEN is meant to keep skills *minimal*; rationalization tables + persuasion framing push toward *more* text. The skill's two halves pull opposite directions — and independent research (an ETH Zurich AGENTS.md study, per mid-2026 reporting) suggests **over-specified context files can *hurt* task success by ~3% and cost ~20% more.** (Caveat: that study is on always-loaded AGENTS.md/CLAUDE.md, not progressively-disclosed skill bodies — the distinction is unresolved.)
- **Model-invoked autonomy ↔ deterministic hooks.** Anthropic's vision is skills that auto-activate; the community's production reality is hooks that force activation. A guide has to decide how much to endorse the hook workaround (powerful, but off the official happy-path and outside the skill's current scope).
- **Official "evaluation-driven development" ↔ community "TDD for skills."** Not enemies — complementary intensities. EDD = build 3 evals, baseline, minimal instructions, iterate (qualitative rubrics). TDD-for-skills = strict RED-GREEN-REFACTOR with adversarial pressure. The rewrite can position them as a **rigor dial**, not a doctrine choice.

---

## 6. Challenge notes (steelman → counter → what would disprove)

**Steelman the current skill.** Its core bet — *instruction files should be tested like code, and rules that can be rationalized away must be adversarially pressure-tested and operationalized* — is now **independently corroborated in the wild** (the `rag-eval-harness` story is almost verbatim the skill's thesis) and **partially adopted by Anthropic itself** (`skill-creator`'s baseline-vs-skill eval pipeline). For the specific class of discipline-enforcing skills, the skill is arguably *ahead* of the official docs.

**Strongest counter.** The skill **over-generalizes a niche discipline into a universal doctrine** and, in doing so, (a) buries the problem the whole community is actually stuck on (triggering), (b) stakes its most-quoted rule (CSO body-skip) on an untested N=1, (c) contradicts itself (Iron Law vs skill-types), and (d) ignores the two fastest-growing concerns of 2026 (security, subagent access). Its rigid-rule style is precisely what Anthropic's own tooling now flags as a smell.

**What would disprove the recommended reframing.** (1) A controlled experiment showing a workflow-summarizing *description* specifically causes body-skipping (would re-elevate CSO from hypothesis to mechanism). (2) Evidence that ALL-CAPS/rigid-rule skills measurably outperform "explain-the-why" skills under real pressure tests (would defend the enforcement style as default). (3) Data that over-triggering from "pushy" descriptions is negligible (would justify recommending directive descriptions unconditionally). None of these currently exist in the corpus — which is itself the finding.

---

## 7. Open questions & gaps (+ provenance honesty)

- Does community practice, under real pressure tests, actually side with ALL-CAPS/rigid rules or with Anthropic's "that's a yellow flag"? **No source settles it.**
- What is the *over-triggering / false-positive* cost of pushy descriptions? **Unmeasured.**
- Is the "description summarizes → body-skip" mechanism real, or is the observed behavior just ordinary step-drift once loaded? **Untested either way.**
- Current (as of writing) status of subagent skill access — confirmed zero, workaround, or patched? Findings conflict across dates; **needs a live verification pass, not carried-over inference.**
- Should some content currently taught as "put it in a skill" actually be "don't write it down at all," given the over-specification-hurts finding? **Open.**
- **Provenance caveat (important):** the strongly-corroborated spine of this dive rests on directly-fetched primary sources — Anthropic docs (`code.claude.com/docs/en/skills`, `platform.claude.com`), the `anthropics/skills` `skill-creator`, `obra/superpowers`, and `agentskills.io`. Many *specific mid-2026 data points* — exact CC version numbers, superpowers star counts, the Snyk ToxicSkills percentages, the ETH Zurich AGENTbench figures, Vercel's "56% uninvoked" stat — came from **single secondary sources beyond my training cutoff** and the verification agents themselves flagged several as single-source. **Treat the *directions* as solid and the *precise numbers* as needing a confirmation pass before they go into a shipped skill.**

---

## 8. Key sources

**Official / primary (high confidence):**
- Anthropic — Skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Claude Code — Extend Claude with skills (frontmatter, triggering troubleshooting, listing budget): https://code.claude.com/docs/en/skills
- Anthropic — Equipping agents for the real world with Agent Skills (engineering): https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- `anthropics/skills` `skill-creator` (eval pipeline + description optimizer + style guidance): https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Agent Skills open spec: https://agentskills.io/specification · description optimization: https://agentskills.io/skill-creation/optimizing-descriptions
- `obra/superpowers` writing-skills (origin of CSO/SDO + Iron Law): https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md · line-reduction walk-back: https://github.com/obra/superpowers/issues/832

**Community / practitioner (directional; Reddit-leaning per request):**
- "I wrote 74 Claude Code skills. Most were theater." — https://www.reddit.com/r/ClaudeAI/comments/1tut2z7/
- "After testing 2,300 community + self-built skills over three months" — https://www.reddit.com/r/ClaudeAI/comments/1t1m9xg/
- "Can someone explain the real difference between Hooks, Skills, Plugins, SKILL.md, CLAUDE.md and agents.md?" (~700 upvotes) — https://www.reddit.com/r/ClaudeCode/comments/1tmq9kz/
- "What I learned writing an eval harness for my own SKILL.md files (caught two real bugs)" — https://www.reddit.com/r/ClaudeAI/comments/1u6f7cr/
- "Claude Code skills went from 84% to 100% activation (250 sandboxed evals)" — https://www.reddit.com/r/ClaudeCode/comments/1qzjy2h/
- Ivan Seleznov — 650-trial activation study — https://medium.com/@ivan.seleznov1/why-claude-code-skills-dont-activate-and-how-to-fix-it-86f679409af1
- Scott Spence — making skills activate reliably (forced-eval hook) — https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably
- Marc Bara — "two reliability problems, not one" (activation vs execution) — https://medium.com/@marc.bara.iniesta/claude-skills-have-two-reliability-problems-not-one-299401842ca8
- Claude Code skill-listing budget mechanics — https://claudefa.st/blog/guide/mechanics/skill-listing-budget

**Security (single-study, verify before quoting):**
- Snyk ToxicSkills — https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/
- Embrace The Red — hidden Unicode instructions in skills — https://embracethered.com/blog/posts/2026/scary-agent-skills/
- `agnix` linter (156 rules for SKILL.md/CLAUDE.md/hooks/plugins/MCP) — https://github.com/avifenesh/agnix

---

*Exploration only. If you want to turn any of these directions into an actual update to `quirk:writing-skills`, invoke `quirk:brainstorming` → `writing-plans` and I'll carry the chosen direction(s) over. I will not start editing the skill from this document.*
