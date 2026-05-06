# Pi Implementer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The implementer model is **pi codex** (`openai-codex/gpt-5-5:xhigh`).

## Prompt body

The agent-facing instructions are identical regardless of runtime. Use the body
from `implementer-prompt.md` (everything inside the prompt block — Task
Description, Context, Before You Begin, Your Job, Code Organization, When You're
in Over Your Head, Self-Review, Report Format).

Substitute Task N, task description, context, and working directory the same
way you would for the Claude path.

## Invocation

Write the assembled prompt body to `prompt.md` in the worktree, then:

```bash
cd <worktree>
pi -p \
  --no-session \
  --offline \
  --model openai-codex/gpt-5-5:xhigh \
  --tools read,bash,edit,write \
  @prompt.md
```

For the canonical hardened dispatch recipe (`gtimeout` wrapper, `PIPESTATUS`
capture, positional-args quoting, JSONL events file), see **quirk:pi-dev →
Canonical headless dispatch recipe**. Use that recipe verbatim when running pi
non-interactively from a script; the snippet above is the minimum viable form
for an interactive orchestrator session.

## Status parsing

Pi has no Task-tool `status` field. The Report Format in the prompt body
already requires the agent to start its final report with:

    Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT

Parse that line from pi's stdout. Apply the same handling as the Claude path
(SKILL.md → Handling Implementer Status).

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules in order. Auth/billing
failures short-circuit the run; on detection, fall back to Claude agents for
the remainder of the plan and warn the user (SKILL.md → Fallback).
