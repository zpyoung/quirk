---
name: executing-plans
description: Use to implement a multi-step task sequentially in one session when subagents aren't available — plans in context, then executes
---

# Executing Plans

## Overview

Plan in context, execute all tasks sequentially, report when complete. This is the
no-subagents path: it builds the plan itself (no separate planning step) and runs the tasks in
the same session. A persisted plan file is an **optional input** — used only when a plan was
handed off from a *separate session*.

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

**Note:** Tell your human partner that Quirk works much better with access to subagents. The quality of its work will be significantly higher if run on a platform with subagent support (such as Claude Code or Codex). If subagents are available, use quirk:subagent-driven-development instead of this skill.

## The Process

### Step 0: Author the tech spec (only when complexity warrants)

Step 0 is the first half of the stage that authors a tech spec when warranted, then plans in context.

1. **Apply the complexity-tier gate.** Author a tech spec if any hold: execution spans more than one
   session, crosses a subsystem boundary, touches ≳3 source files, or your human partner asked
   for one at logic-spec approval. Otherwise skip — plan from the logic spec instead, and
   continue to Step 1.
2. **Record the ruling.** Log which criterion fired, or "skipped — none met," in this run (and in
   `logic.md` Status when a tech spec is authored).
3. **If the gate is met:**
   - **Idempotency:** if a reviewed `tech.md` already exists as the sibling of the actual
     `logic.md` (wherever it was saved — by default `docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md`
     next to `docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md`, handed off from another session),
     load it — do not re-author — unless it's absent or your human partner requests a rewrite.
   - Otherwise, invoke **quirk:writing-tech-spec** to author `tech.md` next to the logic spec, in
     the same directory the logic spec was actually saved to (the path above is the default
     example, not a hard-coded location).
   - On this no-subagent path, perform writing-tech-spec's deep-dive codebase survey in-session,
     directly — parallel `Explore` subagents aren't required here.
   - Dispatch its reviewer and apply fixes inline.
   - Offer your human partner an optional skim (not a gate) surfacing the tech spec's most
     consequential calls — anchored subsystem/files, major DO-NOT-CHANGE fences, riskiest
     contracts.
   - If a conflict with a `logic.md` Decisions-Locked entry surfaces, **STOP** and escalate
     (feasibility escalation) — record the resolution as a dated `logic.md` Amendments entry
     before continuing.
4. **If the gate is not met:** note "no tech spec — plan from the logic spec" and continue to
   Step 1.

### Step 1: Build (or load) the plan, then review
1. **Build the plan in context** via **quirk:writing-plans** — built from `tech.md` when Step 0
   authored one, else from the logic spec / requirements; the task breakdown goes into this
   conversation + a TodoWrite list, no file by default. *(If a persisted plan file was handed off
   from another session, read it once to seed the in-context plan + TodoWrite instead.)*
   - **Complexity-tier upgrade re-check:** once writing-plans' File Structure pass reveals the real
     scope, re-check the complexity-tier gate — if a previously-skipped run now clears it, return
     to Step 0, author `tech.md`, and re-plan the affected tasks.
2. **Agent review (default):** dispatch the plan-document reviewer
   (`../writing-plans/plan-document-reviewer-prompt.md`) on the in-context plan; apply its fixes
   inline. No human approval gate.
3. Only stop for your human partner if the reviewer surfaces a genuine ambiguity you cannot
   resolve (otherwise proceed straight to execution).

### Step 2: Execute Tasks

For each task:
1. Mark as in_progress
2. Follow each step exactly — steps specify behavior (acceptance criteria + contract), not pasted code; you write the implementation. If a contract is ambiguous, ask before guessing.
3. Run verifications as specified
4. Mark as completed

### Step 3: Complete Development

After all tasks complete and verified:
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- **REQUIRED SUB-SKILL:** Use quirk:finishing-a-development-branch
- Follow that skill to verify tests, present options, execute choice

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- Plan conflicts with a `logic.md` Decisions-Locked entry — record the resolution as a dated
  entry in the logic spec's Amendments log before continuing, never a silent plan edit
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

## Remember
- Review plan critically first
- Follow plan steps exactly — satisfy each step's acceptance criteria and contract; don't treat behavioral steps as literal scripts
- Don't skip verifications
- Reference skills when plan says to
- Stop when blocked, don't guess
- Never start implementation on main/master branch without explicit user consent

## Integration

**Required workflow skills:**
- **quirk:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
- **quirk:writing-tech-spec** - Optional pre-plan rubric this skill runs in context as Step 0, when the complexity-tier gate is met
- **quirk:writing-plans** - The planning rubric this skill runs in context as Step 1 (file optional)
- **quirk:finishing-a-development-branch** - Complete development after all tasks
