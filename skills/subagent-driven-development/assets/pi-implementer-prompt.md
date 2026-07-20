# Pi Implementer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The implementer model is **pi codex** (`openai-codex/gpt-5.3-codex:xhigh`).

## Prompt body

The agent-facing instructions are identical regardless of runtime. Use the body
from `implementer-prompt.md` (everything inside the prompt block — Task
Description, Context, Before You Begin, Your Job, Code Organization, When You're
in Over Your Head, Self-Review, Report Format).

Substitute Task N, task description, context, and working directory the same
way you would for the Claude path.

**Parallel-mode note:** in `WORKTREE_PARALLEL` mode the orchestrator may
instruct the worker NOT to run `git commit` — the orchestrator commits after
the review chain passes, to avoid git index-lock races across concurrent
workers. When this instruction is given, strip step 4 ("Commit your work")
from the prompt body's Your Job list and tell the worker to report files
changed instead of a commit SHA in its final report.

## Invocation

Write the assembled prompt body to `prompt.md` in the worktree, then:

```bash
cd <worktree>
[ -f prompt.md ] || { echo "prompt missing" >&2; exit 1; }
pi -p \
  --no-session \
  --offline \
  --model openai-codex/gpt-5.3-codex:xhigh \
  --tools read,bash,edit,write \
  @prompt.md
```

Verify the prompt file exists before dispatching — never fall back to
something like `cat prompt.md || echo MISSING` that pipes garbage into a live
worker; a bad prompt burns the entire dispatch.

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
