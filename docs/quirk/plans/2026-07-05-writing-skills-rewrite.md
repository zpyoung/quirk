# writing-skills Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use quirk:subagent-driven-development (recommended) or quirk:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the `writing-skills` skill around a two-failure-mode spine (activation vs execution), scope the Iron Law by skill type, reframe the CSO "body-skip" claim as a hedged hypothesis, add activation-testing + security-vetting references and a skills-in-subagents section, and keep the bundled official doc with a freshness header — all while dogfooding the practices it teaches.

**Architecture:** SKILL.md becomes a lean hub (< 500 lines) of markdown-linked, one-level-deep reference files. New content lives in focused reference files. Small edits reframe existing reference files. Validation is done with shell checks (line counts, grep) instead of unit tests — this is a documentation deliverable.

**Tech Stack:** Markdown, YAML frontmatter, Graphviz (existing), bash for validation. No build system.

**Spec:** [docs/quirk/specs/2026-07-05-writing-skills-rewrite-design.md](../specs/2026-07-05-writing-skills-rewrite-design.md)

---

## Conventions for this plan

- **"Failing test" = a shell check that currently fails.** Run it first to confirm the gap, apply the edit, re-run to confirm it passes.
- Run all commands from the repo root (your worktree root).
- Keep all findings **directional**: no version numbers, no percentages/star-counts, no named version-specific bugs anywhere in the skill.
- Third person / imperative in descriptions; markdown links (never `@file`) for references.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `skills/writing-skills/activation-testing.md` | **Create** | The description/triggering eval loop (should-trigger / should-not-trigger set). |
| `skills/writing-skills/security-vetting.md` | **Create** | Author-side (least surprise) + consumer-side (vetting checklist) trust practices. |
| `skills/writing-skills/testing-skills-with-subagents.md` | Modify | Reframe as the *discipline-enforcing* deep dive; point other types to lighter validation. |
| `skills/writing-skills/persuasion-principles.md` | Modify | Prepend a scope note (discipline skills only). |
| `skills/writing-skills/anthropic-best-practices.md` | Modify | Prepend a "snapshot, not canonical" freshness header. |
| `skills/writing-skills/SKILL.md` | Rewrite | Lean hub on the two-failure-mode spine; all locked decisions land here. |

`graphviz-conventions.dot`, `render-graphs.js`, `examples/CLAUDE_MD_TESTING.md` are unchanged.

---

### Task 1: Create `activation-testing.md`

```yaml
independent: true
dependencies: []
scope:
  files: [skills/writing-skills/activation-testing.md]
```

**Files:**
- Create: `skills/writing-skills/activation-testing.md`

- [ ] **Step 1: Failing check — file absent**

Run: `test -f skills/writing-skills/activation-testing.md && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: Create the file with this exact content**

```markdown
# Activation Testing

**Load this when:** a skill isn't firing when it should (or fires when it shouldn't), or before shipping any skill you want to trigger reliably.

## Why this is a separate discipline

A skill has two independent failure modes. This file is about the first one — **activation**: the model never invokes the skill, so the body never runs. It is fixed in the `description`, not the body. (The second mode, execution, is about whether the body is followed once loaded — that's the SKILL.md body and its type-scoped tests.)

Activation is the single most common real-world skill failure: a well-written body is wasted if the skill never fires. Test for it explicitly.

## The description is the trigger

The model decides whether to invoke a skill from its `name` + `description` alone. So the description must:

- State **both what the skill does and when to use it** — not only "when to use". (Anthropic's own skill-creator recommends making descriptions a little "pushy" because models tend to *under*-trigger.)
- Front-load the **trigger phrases a user would actually type** (symptoms, file types, error phrasings, synonyms).
- Be specific. Vague descriptions ("helps with documents") lose to specific ones.
- Optionally include a short **"not for X"** clause to bound the trigger surface and reduce false positives.

Keep it terse enough to be scannable, assertive enough to fire. These are not in tension: specific + trigger-forward + assertive is the target.

## The should-trigger / should-not-trigger test

Before shipping, write a small labeled set and check activation by observation:

1. Write ~5 prompts that **should** invoke the skill (varied phrasings a real user would type).
2. Write ~3 prompts that are **near-misses** and should **not** invoke it.
3. Run each in a fresh session and record whether the skill fired.
4. Rewrite the description toward the phrasings that missed; re-run. Iterate a few rounds.
5. To avoid overfitting to your own examples, hold back a couple of should-trigger prompts you don't tune against, and confirm they fire too.

This is the activation analogue of RED-GREEN: watch it fail to fire, fix the description, watch it fire — without breaking the should-not cases.

## Tooling

Anthropic's official `skill-creator` ships a description-optimization loop (a labeled trigger set, a train/held-out split, repeated runs, iterate) — a good reference if you want to automate this. Community fire-rate auditors that parse session logs can tell you which of your installed skills actually fire vs sit dormant. Prefer measuring over guessing.

## The over-triggering side

More assertive descriptions raise activation but can also cause false positives — a skill firing on unrelated prompts wastes tokens and derails tasks. If you have many skills, tightly-scoped single-purpose descriptions compete less and trigger more predictably than one broad description. Test both directions: fires when it should, stays quiet when it shouldn't.
```

- [ ] **Step 3: Passing check — file present and covers both directions**

Run:
```bash
test -f skills/writing-skills/activation-testing.md && \
grep -qi "should-not" skills/writing-skills/activation-testing.md && \
grep -qi "under.*trigger" skills/writing-skills/activation-testing.md && echo OK || echo FAIL
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/writing-skills/activation-testing.md
git commit -m "docs(writing-skills): add activation-testing reference"
```

---

### Task 2: Create `security-vetting.md`

```yaml
independent: true
dependencies: []
scope:
  files: [skills/writing-skills/security-vetting.md]
```

**Files:**
- Create: `skills/writing-skills/security-vetting.md`

- [ ] **Step 1: Failing check — file absent**

Run: `test -f skills/writing-skills/security-vetting.md && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: Create the file with this exact content**

```markdown
# Security & Trust for Skills

**Load this when:** authoring a skill others might run, or deciding whether to install a skill you didn't write.

Skills are trusted-by-proxy: once a skill loads, its instructions steer the agent, and the agent's actions look like legitimate user actions. That bypasses most traditional defenses. This applies both to skills you write (don't surprise your future self or teammates) and skills you install (you're granting instruction-level trust). Practices below are durable — verify current platform specifics separately, since mechanics change.

## Authoring: the principle of least surprise

- A skill's actual behavior should not surprise someone who read its description. No hidden side effects, no undocumented network calls, no capabilities the description doesn't imply.
- Don't treat frontmatter tool declarations as a security boundary. Declaring which tools a skill "uses" is documentation, not a sandbox — don't rely on it to contain a skill's blast radius; verify behavior instead.
- For side-effecting/dangerous skills (deploy, delete, publish), gate behind explicit invocation rather than silent auto-trigger — and confirm the gating actually works in your environment before trusting it.
- Keep bundled scripts and any test/fixture files honest: they can execute with full local permissions, so they are part of your skill's trust surface even if the SKILL.md looks clean.

## Consuming: vet before you trust

Before installing a third-party skill, treat it like running someone's script:

- **Read every file, not just SKILL.md** — including bundled scripts and test/fixture files. Executable content anywhere in the bundle runs with your permissions.
- **Scan for hidden/invisible content.** Instructions can be smuggled in invisible Unicode, HTML comments, or otherwise-unreadable markup that a human skim misses but the model reads. If a file looks shorter than its byte size suggests, be suspicious; use a tool that surfaces non-printing characters.
- **Check that stated purpose matches actual instructions.** A skill that claims to "format code" but instructs reading credentials or hitting an unfamiliar endpoint is a red flag.
- **Prefer sources you can inspect and that are maintained.** There is no official verified marketplace or signing; automated scanners help but miss things (notably code hidden in test files) — a clean scan is not proof of safety.
- **Default to team-private.** Commit skills you rely on to your own repo (`.claude/skills/`) rather than pulling from unvetted catalogs.
```

- [ ] **Step 3: Passing check — covers author + consumer sides**

Run:
```bash
test -f skills/writing-skills/security-vetting.md && \
grep -qi "least surprise" skills/writing-skills/security-vetting.md && \
grep -qi "invisible Unicode" skills/writing-skills/security-vetting.md && \
grep -qi "not a sandbox\|not a security boundary\|not treat frontmatter" skills/writing-skills/security-vetting.md && echo OK || echo FAIL
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/writing-skills/security-vetting.md
git commit -m "docs(writing-skills): add security-vetting reference"
```

---

### Task 3: Reframe `testing-skills-with-subagents.md` as the discipline-skill deep dive

```yaml
independent: true
dependencies: []
scope:
  files: [skills/writing-skills/testing-skills-with-subagents.md]
```

**Files:**
- Modify: `skills/writing-skills/testing-skills-with-subagents.md:1-16` (the Overview area)

- [ ] **Step 1: Failing check — no scoping banner yet**

Run: `grep -qi "This file is the deep dive for DISCIPLINE-ENFORCING skills" skills/writing-skills/testing-skills-with-subagents.md && echo HAS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: Insert a scoping banner immediately after the H1 title**

Find the first line `# Testing Skills With Subagents` and insert directly below it (before the existing `**Load this reference when:**` line) this exact block:

```markdown

> **Scope:** This file is the deep dive for **discipline-enforcing skills** — skills whose job is to make an agent follow a rule it's tempted to rationalize away (TDD discipline, verification-before-completion, safety gates). Pressure scenarios and rationalization tables are the right tools *here*. Other skill types use lighter validation (see "Testing & validation, scoped by skill type" in [SKILL.md](SKILL.md)): technique → apply to a fresh scenario; pattern → recognition + counter-examples; reference → retrieval + correct application; creative/subjective → rubric + human read, not a binary failing test.
```

- [ ] **Step 3: Passing check — banner present, still one level deep**

Run:
```bash
grep -qi "deep dive for \*\*discipline-enforcing skills\*\*" skills/writing-skills/testing-skills-with-subagents.md && \
grep -q "\[SKILL.md\](SKILL.md)" skills/writing-skills/testing-skills-with-subagents.md && echo OK || echo FAIL
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/writing-skills/testing-skills-with-subagents.md
git commit -m "docs(writing-skills): scope testing-with-subagents to discipline skills"
```

---

### Task 4: Add scope note to `persuasion-principles.md`

```yaml
independent: true
dependencies: []
scope:
  files: [skills/writing-skills/persuasion-principles.md]
```

**Files:**
- Modify: `skills/writing-skills/persuasion-principles.md:1` (prepend)

- [ ] **Step 1: Failing check — no scope note yet**

Run: `grep -qi "specialized toolkit, not a default authoring style" skills/writing-skills/persuasion-principles.md && echo HAS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: Prepend this exact block above the file's current first line**

```markdown
> **Scope:** These principles apply to **discipline-enforcing skills** — skills whose job is to make an agent follow a rule it's tempted to skip under pressure. They are a specialized toolkit, not a default authoring style. Most skills (technique / pattern / reference / creative) should NOT lean on caps-heavy MUST/NEVER framing — Anthropic's own guidance flags that as a "yellow flag" and prefers explaining the *why*. Reach for this file only when building a guardrail.

```

- [ ] **Step 3: Passing check**

Run: `grep -qi "specialized toolkit, not a default authoring style" skills/writing-skills/persuasion-principles.md && echo OK || echo FAIL`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/writing-skills/persuasion-principles.md
git commit -m "docs(writing-skills): scope persuasion-principles to discipline skills"
```

---

### Task 5: Add freshness header to `anthropic-best-practices.md`

```yaml
independent: true
dependencies: []
scope:
  files: [skills/writing-skills/anthropic-best-practices.md]
```

**Files:**
- Modify: `skills/writing-skills/anthropic-best-practices.md:1` (prepend, above the existing `# Skill authoring best practices` H1)

- [ ] **Step 1: Failing check — no snapshot header yet**

Run: `grep -qi "Snapshot, not canonical" skills/writing-skills/anthropic-best-practices.md && echo HAS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: Prepend this exact block above the current first line**

```markdown
> **Snapshot, not canonical.** This is a bundled copy of Anthropic's skill-authoring best-practices doc, kept for offline, self-contained reference. It may drift from the live version — the canonical source is https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices. Where this snapshot and SKILL.md differ on scope or testing philosophy, SKILL.md reflects deliberate, attributed choices (see the lineage note in SKILL.md).

```

- [ ] **Step 3: Passing check**

Run: `grep -qi "Snapshot, not canonical" skills/writing-skills/anthropic-best-practices.md && echo OK || echo FAIL`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/writing-skills/anthropic-best-practices.md
git commit -m "docs(writing-skills): add freshness header to bundled best-practices"
```

---

### Task 6: Rewrite `SKILL.md` on the two-failure-mode spine

```yaml
independent: false
dependencies: [T1, T2, T3, T4, T5]
scope:
  files: [skills/writing-skills/SKILL.md]
```

**Files:**
- Rewrite: `skills/writing-skills/SKILL.md`

This is the core task. Rebuild SKILL.md section by section. **Preserve** the existing high-quality material (skill types, CSO keyword/naming guidance, flowchart usage, code-example guidance, anti-patterns, deployment checklist) but **reorganize** it under the new spine and **apply the reframes** below. Exact text is given for every load-bearing/contested piece; for "keep" sections, carry the current content across with only the noted edits.

- [ ] **Step 1: Failing checks — capture current state**

Run:
```bash
echo "lines: $(wc -l < skills/writing-skills/SKILL.md)"                 # currently 655 (target < 500)
grep -c '^## ' skills/writing-skills/SKILL.md                           # section count
grep -n '@\(graphviz-conventions\|testing-skills-with-subagents\)' skills/writing-skills/SKILL.md  # @-links to convert (expect 2)
grep -qi "Activation" skills/writing-skills/SKILL.md && echo HAS-ACT || echo NO-ACT   # expect NO-ACT
```
Expected: ~655 lines, two `@`-links present, `NO-ACT`.

- [ ] **Step 2: Replace the frontmatter description (sharpen + dogfood)**

Replace line 3 (`description: Use when creating new skills...`) with exactly:

```yaml
description: Use when creating, editing, or testing a Claude Code skill — writing SKILL.md and its frontmatter/description, choosing skill vs command vs subagent vs CLAUDE.md, fixing a skill that won't trigger, or deciding how strictly to test one. Covers activation (getting a skill to fire) and execution (getting it right once loaded).
```

- [ ] **Step 3: Write the Overview — two-failure-mode frame + lineage note**

Replace the current `## Overview` section with this exact content (it supersedes the old TDD-first framing):

```markdown
## Overview

A **skill** is a reusable reference for a proven technique, pattern, or tool that future agents can find and apply. Skills are reusable guides — NOT narratives about how you solved something once.

**Every skill has two independent failure modes. Design and test for both:**

- **Activation** — the skill never fires; the model doesn't invoke it, so the body never runs. Fixed in the **description**. See [activation-testing.md](activation-testing.md).
- **Execution** — the skill fires, but the model doesn't do what the body says. Fixed in the **body** and its type-scoped tests.

They have different causes and different fixes. Don't conflate them: a perfectly written body is worthless if the skill never activates, and a reliably-firing skill is worthless if its body is ignored.

**Lineage (so you know which rules are which):** the RED-GREEN-REFACTOR discipline, the "Iron Law", "CSO", and rationalization-resistance in this skill come from the community `obra/superpowers` tradition. Anthropic's own framing is lighter — "evaluation-driven development" — and its bundled best-practices doc ([anthropic-best-practices.md](anthropic-best-practices.md)) never mentions rationalization or persuasion. Where the two diverge, this skill says so. Treat the superpowers-heritage rules as sharp tools for a specific job, not universal law.
```

- [ ] **Step 4: Keep "When to Create a Skill" + add the mechanism-choice spine**

Keep the current **When to Create a Skill** bullets (create-when / don't-create-for). Immediately after them, add this exact block:

```markdown
## Skill vs Command vs Subagent vs CLAUDE.md vs MCP

Pick the mechanism before writing:

- **External access** (APIs, databases, live state) → **MCP server**.
- **Context isolation / a specialist persona** → **subagent**.
- **Reusable procedural knowledge the model should apply on its own** → **skill**.
- **Something you want to fire only on explicit command** → **slash command** (or a skill gated from auto-invocation).
- **Always-on project rules/context** → **CLAUDE.md** — but keep it lean; over-stuffed always-loaded context measurably degrades results.

These compose: a subagent can apply a skill that calls an MCP tool. "Which one" is usually "the right layer for this piece", not "only one".
```

- [ ] **Step 5: Keep the Skill Types section, expanded to five types**

Keep the current **Skill Types** section (Technique / Pattern / Reference) and add **Discipline-enforcing** and **Creative/subjective** so all five are named, since types now drive testing rigor:

```markdown
### Discipline-enforcing
Enforces a rule the agent is tempted to rationalize away (TDD, verification-before-completion, safety gates). Highest testing bar.

### Creative / subjective
Shapes voice, tone, design, or ideation, where "correct" is a judgment call, not a binary. Validated by rubric + human read, not a failing test.
```

- [ ] **Step 6: Add the Activation section (new, foregrounded)**

Add this exact section (this is the #1 failure mode, so it comes before execution/testing):

```markdown
## Activation — getting the skill to fire

The model decides whether to invoke a skill from its `name` + `description` alone. This is the most common real-world failure: the skill never fires.

- Description states **both what the skill does AND when to use it** — front-load the trigger phrases a user would actually type (symptoms, file types, error wording, synonyms).
- Be specific and assertive enough to fire. Anthropic's own skill-creator advises making descriptions a little "pushy" because models tend to *under*-trigger. (This is about the description's *content*, not a license for caps-heavy body prose.)
- `name` uses lowercase letters, numbers, hyphens; gerund/active voice; and matches the skill's directory name.
- Prefer small, single-purpose skills — tightly-scoped descriptions compete less and trigger more predictably than one broad skill.
- Watch the other direction too: an over-eager description causes false-positive triggering that wastes tokens and derails tasks.

**Test activation explicitly** — write should-trigger and should-not-trigger prompts and observe. See [activation-testing.md](activation-testing.md).
```

Then carry over the existing **Keyword Coverage** and **Descriptive Naming** subsections (currently under "CSO") into this section — they're activation guidance.

- [ ] **Step 7: Add the CSO reframe (hedged hypothesis)**

Replace the current "Rich Description Field / Description = When to Use, NOT What the Skill Does" subsection with this exact content:

```markdown
## The "description body-skip" hypothesis (reframed)

Older versions of this skill asserted: *if a description summarizes the workflow, the model follows the description and skips reading the body.* Treat that as a **hypothesis, not a law.**

It traces to a single, unreplicated report (`obra/superpowers`): one skill did one review instead of two after its description summarized the workflow, attributed to the model following the description over the body. No controlled experiment has isolated this, and official Anthropic guidance points the other way on description *content* — a description should state **both what the skill does and when to use it**, and be assertive enough to fire.

**So:** keep descriptions terse and trigger-forward for **activation** (well-evidenced), but don't starve the description of "what it does" on the theory that it prevents body-skipping (not evidenced). If a loaded skill isn't being followed, that's an **execution** problem — fix it in the body with explicit steps and checks, not by trimming the description. If you want to know whether summarizing hurts *your* skill, test it (fittingly, this specific claim was never itself tested).
```

- [ ] **Step 8: Add the Execution section**

Add this exact section, folding in the existing "Token Efficiency", "Code Examples", and "Flowchart Usage" material as subsections (keep their content; convert `@graphviz-conventions.dot` on the flowchart line to `[graphviz-conventions.dot](graphviz-conventions.dot)`):

```markdown
## Execution — getting it right once loaded

Once a skill fires, these determine whether the body is actually followed:

- **Progressive disclosure.** SKILL.md is a hub; push heavy material into reference files linked one level deep. Keep the always-on body lean.
- **Match freedom to fragility.** High-freedom prose for flexible tasks; low-freedom exact scripts for fragile, must-be-consistent operations.
- **Operationalize rules; don't just describe them.** The highest-leverage execution fix, independently reproduced by practitioners: telling the model *what to say back*, what an acceptable reply looks like, and what failure looks like constrains behavior; a stated principle gets rationalized away. Prefer explicit checklists and worked steps over exhortation.
- **One excellent example** beats many mediocre ones.
```

- [ ] **Step 9: Add the Testing & validation section (Iron Law scoped)**

Replace the current "Iron Law" + "Testing All Skill Types" + "RED-GREEN-REFACTOR" blocks with this exact content (convert `@testing-skills-with-subagents.md` to a markdown link here):

```markdown
## Testing & validation — scoped by skill type

Match rigor to skill type. Anthropic's own guidance conditions testing on type: objectively-verifiable skills benefit from test cases; subjective/creative skills often don't need them ("you can tell by reading two paragraphs whether the voice is right").

- **Discipline-enforcing → the Iron Law applies: NO SUCH SKILL WITHOUT A FAILING TEST FIRST.** Watch the agent violate the rule *without* the skill before you write it (RED), write the minimal skill that closes those exact rationalizations (GREEN), then plug new loopholes (REFACTOR). Full method: [testing-skills-with-subagents.md](testing-skills-with-subagents.md).
- **Technique → apply it to a fresh scenario; probe for gaps.**
- **Pattern → recognition + counter-examples.**
- **Reference → retrieval + correct application.**
- **Creative/subjective → rubric + human read, not a binary failing test.**

**The Iron Law is scoped, not universal.** It is the right default for discipline-enforcing skills only. Trivial, non-behavioral edits (typos, rewording, reordering) don't need a fresh RED phase; edits that change a rule, a workflow step, or a discipline constraint do.

**Activation is a separate test axis** from all of the above — a skill can be 100% correct in body and still never fire. Test triggering separately: [activation-testing.md](activation-testing.md).
```

- [ ] **Step 10: Keep the Discipline-enforcing subsection (scoped + softened)**

Carry over the current rationalization-table / red-flags / "letter vs spirit" material into a clearly-scoped subsection under Testing, prefaced with this exact lead:

```markdown
### For discipline-enforcing skills only: resisting rationalization

The tools below (rationalization tables, red-flag lists, "violating the letter is violating the spirit", persuasion framing in [persuasion-principles.md](persuasion-principles.md)) are for guardrail skills that must survive adversarial pressure. **Do not apply them by default.** For everything else, prefer explaining the *why* over caps-heavy MUST/NEVER rules — Anthropic's own style guidance flags all-caps absolutism as a "yellow flag".
```

- [ ] **Step 11: Add the Skills in Subagents / Teams section (durable principles)**

Add this exact section:

```markdown
## Skills in subagents and Teams

Skill availability is NOT guaranteed inside a dispatched worker. Before relying on a skill in a subagent or Team task:

- **Don't assume a dispatched subagent sees your custom skills.** Availability differs from the main session.
- **Built-in agents may not access custom skills at all.** If a worker must apply a skill, verify it can — or inline the needed guidance in the dispatch prompt.
- **In the GREEN phase, confirm the skill actually loaded.** A subagent that "passes" may have passed *without* the skill — then you've tested nothing. Check that it was invoked, not just that the output looked right.

Exact mechanics change across Claude Code versions; verify current behavior rather than trusting a fixed rule.
```

- [ ] **Step 12: Keep Anti-Patterns, add Security pointer, keep Deployment (+ distribution note)**

Keep the current **Anti-Patterns** and **Skill Creation Checklist** / **Deployment** sections. Add this exact Security pointer (inline summary → reference) just before Deployment:

```markdown
## Security & trust (brief)

Skills are trusted-by-proxy: a loaded skill steers the agent. When **authoring**, follow the principle of least surprise (behavior matches description; frontmatter tool lists are documentation, not a sandbox). When **installing** someone else's skill, vet every file (including scripts and test fixtures), scan for hidden/invisible instructions, and confirm stated purpose matches actual instructions. Full checklist: [security-vetting.md](security-vetting.md).
```

And append to the Deployment section this exact distribution note:

```markdown
**Distribution:** default to team-private — commit skills you rely on to your own repo (`.claude/skills/`). Publish publicly only when a skill solves a generalizable problem, is battle-tested, and you'll maintain it. There is no official verified marketplace or signing.
```

- [ ] **Step 13: Convert remaining `@`-links and update the checklist wording**

Ensure no `@file` reference links remain (the anti-pattern *example* on the old line ~286 that demonstrates what NOT to do may stay, since it's illustrative). Update the **Skill Creation Checklist** so its "GREEN/RED" items say "for discipline-enforcing skills" and add a checklist item "Description tested for activation (should-trigger / should-not-trigger)".

- [ ] **Step 14: Passing checks — structure, spine, links, budget**

Run:
```bash
F=skills/writing-skills/SKILL.md
echo "lines: $(wc -l < $F)  (target < 500)"
for h in "## Activation" "## Execution" "## Testing & validation" "## Skills in subagents and Teams" "body-skip" "## Skill vs Command vs Subagent"; do
  grep -qi "$h" "$F" && echo "OK: $h" || echo "MISSING: $h"
done
echo "stray @-links (expect only the illustrative anti-pattern example, if any):"
grep -n '@[A-Za-z0-9_./-]*\.\(md\|dot\)' "$F" || echo "(none)"
echo "sharpened description present:"; grep -q "won't trigger" "$F" && echo OK || echo FAIL
echo "reference links resolve:"
for r in activation-testing.md security-vetting.md testing-skills-with-subagents.md persuasion-principles.md anthropic-best-practices.md graphviz-conventions.dot; do
  grep -q "($r)" "$F" && test -f "skills/writing-skills/$r" && echo "OK: $r" || echo "CHECK: $r"
done
```
Expected: line count < 500; all `## ` sections `OK`; no non-illustrative `@`-links; description `OK`; every reference link resolves.

- [ ] **Step 15: Directional-language check — no unverified numbers or version-pinned facts**

Run:
```bash
grep -nEi 'v?[0-9]+\.[0-9]+\.[0-9]+|[0-9]{2,}%|[0-9,]+ (stars|skills|trials)|177|1,?536|SLASH_COMMAND_TOOL_CHAR_BUDGET|skillListing' skills/writing-skills/SKILL.md \
  skills/writing-skills/activation-testing.md skills/writing-skills/security-vetting.md || echo "(clean — no version-pinned/unverified numbers)"
```
Expected: `(clean ...)`. If any hit appears in the new content, reword it to a directional statement.

- [ ] **Step 16: Commit**

```bash
git add skills/writing-skills/SKILL.md
git commit -m "docs(writing-skills): restructure on activation/execution spine; scope Iron Law; reframe CSO"
```

---

### Task 7: Dogfood self-review + final validation

```yaml
independent: false
dependencies: [T6]
scope:
  files: [skills/writing-skills/SKILL.md]
```

**Files:**
- Read/verify only: all `skills/writing-skills/*` files.

- [ ] **Step 1: Activation self-check**

Read the sharpened frontmatter `description`. Confirm it (a) names both what the skill does and when to use it, (b) front-loads real trigger phrases, (c) would fire on "help me write a skill", "my skill isn't triggering", "should this be a skill or a command". If any is weak, tighten and re-commit.

- [ ] **Step 2: Execution self-check (skill applied to itself)**

Confirm the rewritten skill obeys its own rules:
- Two-failure-mode framing present and not conflated.
- Iron Law appears only scoped to discipline-enforcing skills; no unconditional "no exceptions / delete means delete" banner remains.
- CSO reframed as hypothesis with the official contrast.
- Rationalization tooling explicitly gated to discipline skills.

Run:
```bash
grep -qi "No exceptions" skills/writing-skills/SKILL.md && echo "REVIEW: stray absolutism" || echo "OK: no unconditional Iron Law"
```
Expected: `OK: no unconditional Iron Law` (if `REVIEW`, confirm any remaining "No exceptions" is scoped to discipline skills or reword it).

- [ ] **Step 3: Structural self-check**

Run:
```bash
echo "SKILL.md lines: $(wc -l < skills/writing-skills/SKILL.md)  (< 500)"
echo "references one level deep (no nested skill-refs inside reference files that point deeper):"
grep -rn '\](.*\.md)' skills/writing-skills/activation-testing.md skills/writing-skills/security-vetting.md | grep -v 'SKILL.md' || echo "(reference files only link back to SKILL.md — good)"
```
Expected: < 500 lines; reference files don't introduce a second level of skill-to-skill links.

- [ ] **Step 4: Full directional sweep across all changed files**

Run:
```bash
grep -nEi 'v?[0-9]+\.[0-9]+\.[0-9]+|[0-9]{2,}%|177,?000|1,?536|SLASH_COMMAND_TOOL_CHAR_BUDGET|skillListing|Snyk|ETH Zurich|Vercel' \
  skills/writing-skills/SKILL.md skills/writing-skills/activation-testing.md skills/writing-skills/security-vetting.md \
  skills/writing-skills/testing-skills-with-subagents.md skills/writing-skills/persuasion-principles.md \
  || echo "(clean — findings are directional)"
```
Expected: `(clean ...)`. (The bundled `anthropic-best-practices.md` is excluded — it's an official snapshot and keeps its own numbers under the freshness header.)

- [ ] **Step 5: Render flowcharts to confirm graphviz still valid (optional)**

Run: `node skills/writing-skills/render-graphs.js skills/writing-skills 2>/dev/null && echo "render OK" || echo "skip if node/graphviz unavailable"`
Expected: `render OK` (or skip cleanly).

- [ ] **Step 6: Final commit (if any fixes were made)**

```bash
git add -A skills/writing-skills/
git commit -m "docs(writing-skills): dogfood self-review fixes" || echo "nothing to fix — already clean"
```

---

## Self-Review (plan author's pass)

**Spec coverage:** two-failure-mode spine (T6 S3,6,8) ✓ · Iron Law scoped by type (T6 S9) ✓ · CSO reframe (T6 S7) ✓ · discipline machinery kept+scoped (T4, T6 S10) ✓ · activation-testing.md (T1) ✓ · security-vetting.md (T2) ✓ · skills-in-subagents section (T6 S11) ✓ · anthropic-best-practices freshness header (T5) ✓ · SKILL.md < 500 lines (T6 S14, T7 S3) ✓ · directional / no numbers (T6 S15, T7 S4) ✓ · sharpened description (T6 S2, T7 S1) ✓ · `@`→markdown links (T6 S8,9,13) ✓ · skills-vs-alternatives spine (T6 S4) ✓ · distribution note (T6 S12) ✓.

**Placeholder scan:** exact text supplied for every new/contested block; "keep" sections reference concrete existing content by name. No TBD/TODO.

**Parallelism:** T1–T5 are `independent: true` with non-overlapping `scope.files` (parallel wave, IN_PLACE_PARALLEL-eligible). T6 depends on T1–T5 (links to them) and solely owns SKILL.md. T7 depends on T6. No two tasks share a file with `independent: true`.
