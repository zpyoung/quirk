---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
---

# Subagent-Driven Development

Execute plan by dispatching fresh subagent per task, with two-stage review after each: spec compliance review first, then code quality review.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused and succeed at their task. They should never inherit your session's context or history — you construct exactly what they need. This also preserves your own context for coordination work.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

## When to Use

```dot
digraph when_to_use {
    "Have implementation plan?" [shape=diamond];
    "Tasks mostly independent?" [shape=diamond];
    "Stay in this session?" [shape=diamond];
    "subagent-driven-development" [shape=box];
    "executing-plans" [shape=box];
    "Manual execution or brainstorm first" [shape=box];

    "Have implementation plan?" -> "Tasks mostly independent?" [label="yes"];
    "Have implementation plan?" -> "Manual execution or brainstorm first" [label="no"];
    "Tasks mostly independent?" -> "Stay in this session?" [label="yes"];
    "Tasks mostly independent?" -> "Manual execution or brainstorm first" [label="no - tightly coupled"];
    "Stay in this session?" -> "subagent-driven-development" [label="yes"];
    "Stay in this session?" -> "executing-plans" [label="no - parallel session"];
}
```

**vs. Executing Plans (parallel session):**
- Same session (no context switch)
- Fresh subagent per task (no context pollution)
- Two-stage review after each task: spec compliance first, then code quality
- Faster iteration (no human-in-loop between tasks)

## Runtime Selection

**This skill supports two agent runtimes.** Before reading the plan, ask the user
which to use via `AskUserQuestion`:

> **Which agent runtime for this plan?**
> - **Claude subagents** (default) — `Task` tool with general-purpose / quirk:code-reviewer agents
> - **Pi agents** — `pi -p` headless dispatch with codex implementer + gemini reviewer

The choice is locked once and applies uniformly to per-task implementer + per-task
spec reviewer + per-task code-quality reviewer for the rest of the run.

**The final whole-branch reviewer always uses the Claude `quirk:code-reviewer`
agent**, regardless of choice — cross-task synthesis benefits from Claude's agent
context, and pi has no equivalent role.

| Role | Claude path | Pi path |
|---|---|---|
| Implementer | `Task` (general-purpose) + `assets/implementer-prompt.md` | `pi -p` codex (`openai-codex/gpt-5.3-codex:xhigh`) + `assets/pi-implementer-prompt.md` |
| Spec reviewer | `Task` (general-purpose) + `assets/spec-reviewer-prompt.md` | `pi -p` gemini (`google/gemini-3.1-pro-preview:high`) + `assets/pi-spec-reviewer-prompt.md` |
| Code-quality reviewer | `Task` (quirk:code-reviewer) + `assets/code-quality-reviewer-prompt.md` | `pi -p` gemini (`google/gemini-3.1-pro-preview:high`) + `assets/pi-code-quality-reviewer-prompt.md` |
| Final whole-branch reviewer | `Task` (quirk:code-reviewer) | `Task` (quirk:code-reviewer) — always Claude |

When the pi path is selected, **REQUIRED:** consult `quirk:pi-dev` for the
canonical hardened dispatch recipe, failure-detection rules, and reviewer JSON
parse fallback.

## The Process

```dot
digraph process {
    rankdir=TB;

    subgraph cluster_per_task {
        label="Per Task";
        "Dispatch implementer (assets/<runtime>-implementer-prompt.md)" [shape=box];
        "Implementer asks questions?" [shape=diamond];
        "Answer questions, provide context" [shape=box];
        "Implementer implements, tests, commits, self-reviews" [shape=box];
        "Dispatch spec reviewer (assets/<runtime>-spec-reviewer-prompt.md)" [shape=box];
        "Spec reviewer confirms code matches spec?" [shape=diamond];
        "Implementer fixes spec gaps" [shape=box];
        "Dispatch code quality reviewer (assets/<runtime>-code-quality-reviewer-prompt.md)" [shape=box];
        "Code quality reviewer approves?" [shape=diamond];
        "Implementer fixes quality issues" [shape=box];
        "Mark task complete in TodoWrite" [shape=box];
    }

    "Ask: pi or Claude runtime?" [shape=diamond];
    "Read plan, extract all tasks with full text, note context, create TodoWrite" [shape=box];
    "More tasks remain?" [shape=diamond];
    "Dispatch final code reviewer (Claude quirk:code-reviewer, regardless of runtime)" [shape=box];
    "Use quirk:finishing-a-development-branch" [shape=box style=filled fillcolor=lightgreen];

    "Ask: pi or Claude runtime?" -> "Read plan, extract all tasks with full text, note context, create TodoWrite";
    "Read plan, extract all tasks with full text, note context, create TodoWrite" -> "Dispatch implementer (assets/<runtime>-implementer-prompt.md)";
    "Dispatch implementer (assets/<runtime>-implementer-prompt.md)" -> "Implementer asks questions?";
    "Implementer asks questions?" -> "Answer questions, provide context" [label="yes"];
    "Answer questions, provide context" -> "Dispatch implementer (assets/<runtime>-implementer-prompt.md)";
    "Implementer asks questions?" -> "Implementer implements, tests, commits, self-reviews" [label="no"];
    "Implementer implements, tests, commits, self-reviews" -> "Dispatch spec reviewer (assets/<runtime>-spec-reviewer-prompt.md)";
    "Dispatch spec reviewer (assets/<runtime>-spec-reviewer-prompt.md)" -> "Spec reviewer confirms code matches spec?";
    "Spec reviewer confirms code matches spec?" -> "Implementer fixes spec gaps" [label="no"];
    "Implementer fixes spec gaps" -> "Dispatch spec reviewer (assets/<runtime>-spec-reviewer-prompt.md)" [label="re-review"];
    "Spec reviewer confirms code matches spec?" -> "Dispatch code quality reviewer (assets/<runtime>-code-quality-reviewer-prompt.md)" [label="yes"];
    "Dispatch code quality reviewer (assets/<runtime>-code-quality-reviewer-prompt.md)" -> "Code quality reviewer approves?";
    "Code quality reviewer approves?" -> "Implementer fixes quality issues" [label="no"];
    "Implementer fixes quality issues" -> "Dispatch code quality reviewer (assets/<runtime>-code-quality-reviewer-prompt.md)" [label="re-review"];
    "Code quality reviewer approves?" -> "Mark task complete in TodoWrite" [label="yes"];
    "Mark task complete in TodoWrite" -> "More tasks remain?";
    "More tasks remain?" -> "Dispatch implementer (assets/<runtime>-implementer-prompt.md)" [label="yes"];
    "More tasks remain?" -> "Dispatch final code reviewer (Claude quirk:code-reviewer, regardless of runtime)" [label="no"];
    "Dispatch final code reviewer (Claude quirk:code-reviewer, regardless of runtime)" -> "Use quirk:finishing-a-development-branch";
}
```

`<runtime>` is `` (empty) for the Claude path and `pi-` for the pi path. So the
implementer template is `assets/implementer-prompt.md` (Claude) or
`assets/pi-implementer-prompt.md` (pi), and so on.

## Model Selection

**Pi path:** Models are fixed by role — codex (`openai-codex/gpt-5.3-codex:xhigh`) for the
implementer, gemini (`google/gemini-3.1-pro-preview:high`) for both reviewers. Skip the
rest of this section.

**Claude path:** Use the least powerful model that can handle each role to conserve
cost and increase speed.

**Mechanical implementation tasks** (isolated functions, clear specs, 1-2 files): use a fast, cheap model. Most implementation tasks are mechanical when the plan is well-specified.

**Integration and judgment tasks** (multi-file coordination, pattern matching, debugging): use a standard model.

**Architecture, design, and review tasks**: use the most capable available model.

**Task complexity signals:**
- Touches 1-2 files with a complete spec → cheap model
- Touches multiple files with integration concerns → standard model
- Requires design judgment or broad codebase understanding → most capable model

## Handling Implementer Status

Implementer subagents report one of four statuses. Handle each appropriately:

**DONE:** Proceed to spec compliance review.

**DONE_WITH_CONCERNS:** The implementer completed the work but flagged doubts. Read the concerns before proceeding. If the concerns are about correctness or scope, address them before review. If they're observations (e.g., "this file is getting large"), note them and proceed to review.

**NEEDS_CONTEXT:** The implementer needs information that wasn't provided. Provide the missing context and re-dispatch.

**BLOCKED:** The implementer cannot complete the task. Assess the blocker:
1. If it's a context problem, provide more context and re-dispatch with the same model
2. If the task requires more reasoning, re-dispatch with a more capable model
3. If the task is too large, break it into smaller pieces
4. If the plan itself is wrong, escalate to the human

**Never** ignore an escalation or force the same model to retry without changes. If the implementer said it's stuck, something needs to change.

## Prompt Templates

All templates live in `assets/`. The dispatch path is selected by the runtime
chosen in **Runtime Selection**.

**Claude path:**
- `assets/implementer-prompt.md` — dispatch implementer via `Task` (general-purpose)
- `assets/spec-reviewer-prompt.md` — dispatch spec compliance reviewer via `Task` (general-purpose)
- `assets/code-quality-reviewer-prompt.md` — dispatch code quality reviewer via `Task` (quirk:code-reviewer)

**Pi path:**
- `assets/pi-implementer-prompt.md` — `pi -p` codex with `--tools read,bash,edit,write`
- `assets/pi-spec-reviewer-prompt.md` — `pi -p` gemini with `--tools read,bash` (read-only review)
- `assets/pi-code-quality-reviewer-prompt.md` — `pi -p` gemini with `--tools read,bash` (read-only review)

The pi templates reference **quirk:pi-dev** for the canonical hardened dispatch
recipe (timeout wrapper, exit-code capture, JSONL events file) and failure-detection
rules. Use that recipe verbatim when scripting; the pi templates show the minimum
interactive form.

## Example Workflow

```
You: I'm using Subagent-Driven Development to execute this plan.

[Read plan file once: docs/quirk/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[Create TodoWrite with all tasks]

Task 1: Hook installation script

[Get Task 1 text and context (already extracted)]
[Dispatch implementation subagent with full task text + context]

Implementer: "Before I begin - should the hook be installed at user or system level?"

You: "User level (~/.config/quirk/hooks/)"

Implementer: "Got it. Implementing now..."
[Later] Implementer:
  - Implemented install-hook command
  - Added tests, 5/5 passing
  - Self-review: Found I missed --force flag, added it
  - Committed

[Dispatch spec compliance reviewer]
Spec reviewer: ✅ Spec compliant - all requirements met, nothing extra

[Get git SHAs, dispatch code quality reviewer]
Code reviewer: Strengths: Good test coverage, clean. Issues: None. Approved.

[Mark Task 1 complete]

Task 2: Recovery modes

[Get Task 2 text and context (already extracted)]
[Dispatch implementation subagent with full task text + context]

Implementer: [No questions, proceeds]
Implementer:
  - Added verify/repair modes
  - 8/8 tests passing
  - Self-review: All good
  - Committed

[Dispatch spec compliance reviewer]
Spec reviewer: ❌ Issues:
  - Missing: Progress reporting (spec says "report every 100 items")
  - Extra: Added --json flag (not requested)

[Implementer fixes issues]
Implementer: Removed --json flag, added progress reporting

[Spec reviewer reviews again]
Spec reviewer: ✅ Spec compliant now

[Dispatch code quality reviewer]
Code reviewer: Strengths: Solid. Issues (Important): Magic number (100)

[Implementer fixes]
Implementer: Extracted PROGRESS_INTERVAL constant

[Code reviewer reviews again]
Code reviewer: ✅ Approved

[Mark Task 2 complete]

...

[After all tasks]
[Dispatch final code-reviewer]
Final reviewer: All requirements met, ready to merge

Done!
```

## Advantages

**vs. Manual execution:**
- Subagents follow TDD naturally
- Fresh context per task (no confusion)
- Parallel-safe (subagents don't interfere)
- Subagent can ask questions (before AND during work)

**vs. Executing Plans:**
- Same session (no handoff)
- Continuous progress (no waiting)
- Review checkpoints automatic

**Efficiency gains:**
- No file reading overhead (controller provides full text)
- Controller curates exactly what context is needed
- Subagent gets complete information upfront
- Questions surfaced before work begins (not after)

**Quality gates:**
- Self-review catches issues before handoff
- Two-stage review: spec compliance, then code quality
- Review loops ensure fixes actually work
- Spec compliance prevents over/under-building
- Code quality ensures implementation is well-built

**Cost:**
- More subagent invocations (implementer + 2 reviewers per task)
- Controller does more prep work (extracting all tasks upfront)
- Review loops add iterations
- But catches issues early (cheaper than debugging later)

## Red Flags

**Never:**
- Start implementation on main/master branch without explicit user consent
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Make subagent read plan file (provide full text instead)
- Skip scene-setting context (subagent needs to understand where task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance (spec reviewer found issues = not done)
- Skip review loops (reviewer found issues = implementer fixes = review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is ✅** (wrong order)
- Move to next task while either review has open issues

**If subagent asks questions:**
- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

**If reviewer finds issues:**
- Implementer (same subagent) fixes them
- Reviewer reviews again
- Repeat until approved
- Don't skip the re-review

**If subagent fails task:**
- Dispatch fix subagent with specific instructions
- Don't try to fix manually (context pollution)

## Fallback (Pi runtime only)

Pi has no built-in retries beyond rate-limit backoff and no auto-detect for stale
versions. Apply the **quirk:pi-dev → Failure detection** rules in order. On
detection:

| Failure | Action |
|---|---|
| Auth (401, invalid api key, authentication_error) | **Fall back to Claude** for the rest of the run. Warn the user once. Don't consume retry budget — every worker hits the same wall. |
| Billing (`insufficient_quota`, `quota.exceeded`) | **Fall back to Claude** for the rest of the run. Warn the user once. |
| Rate limit (429, `rate_limit_error`, `RESOURCE_EXHAUSTED`) | One retry with 60s backoff. If the retry also fails, fall back to Claude for that role only. |
| Timeout (`gtimeout` exit 124) | Treat the worker as FAIL. Re-dispatch once with a longer timeout; if it times out again, fall back to Claude for that role. |
| Empty/missing JSONL events | Worker hung or never started. Re-dispatch once. If still empty, fall back to Claude for that role. |
| Unparseable reviewer output | Apply **quirk:pi-dev → Reviewer JSON parse fallback**. Never count unparseable as PASS — synthesize a NEEDS_FIX verdict and let the implementer fix-and-retry. |
| Pi version < 0.65.1 (preflight check) | Don't dispatch any pi worker. Tell the user to upgrade (`pnpm add -g @mariozechner/pi-coding-agent`) or fall back to Claude. |

When falling back, mark any partially completed task as needing re-review on the
Claude path before continuing to the next task. Don't silently continue with a
mixed-runtime task.

## Integration

**Required workflow skills:**
- **quirk:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
- **quirk:writing-plans** - Creates the plan this skill executes
- **quirk:requesting-code-review** - Code review template for reviewer subagents
- **quirk:finishing-a-development-branch** - Complete development after all tasks

**Required when pi runtime is selected:**
- **quirk:pi-dev** - Canonical hardened dispatch recipe, failure detection, reviewer JSON parse fallback, model alias resolution

**Subagents should use:**
- **quirk:test-driven-development** - Subagents follow TDD for each task

**Alternative workflow:**
- **quirk:executing-plans** - Use for parallel session instead of same-session execution
