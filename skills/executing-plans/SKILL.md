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

### Step 1: Build (or load) the plan, then review
1. **Build the plan in context** via **quirk:writing-plans** — the task breakdown goes into this
   conversation + a TodoWrite list, no file by default. *(If a persisted plan file was handed off
   from another session, read it once to seed the in-context plan + TodoWrite instead.)*
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
- **quirk:writing-plans** - The planning rubric this skill runs in context as Step 1 (file optional)
- **quirk:finishing-a-development-branch** - Complete development after all tasks
