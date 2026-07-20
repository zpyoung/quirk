# Pi Implementer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The implementer model is the **pi-dev `codex` alias at `xhigh` thinking** (see
**quirk:pi-dev**) — not a frozen model id. `pi-watch` resolves the newest authed model in the
alias's fallback ladder; hard-pinning an exact id via `--provider`/`--model` is the documented
exception, not the default.

## Prompt body

The agent-facing instructions are identical regardless of runtime. Use the body
from `implementer-prompt.md` (everything inside the prompt block — Task
Description, Context, Before You Begin, Your Job, Code Organization, When You're
in Over Your Head, Self-Review, Report Format).

Substitute Task N, task description, context, and working directory the same
way you would for the Claude path.

**Parallel-mode note:** workers commit normally in `WORKTREE_PARALLEL` mode — each worker owns its
own worktree/branch, and the rolling auto-merge needs their commits to merge. The no-commit +
orchestrator-commits instruction applies ONLY to the `IN_PLACE_PARALLEL` orchestrator-commits
fallback (shared working directory, disjoint declared `scope.files` — see SKILL.md → Mode
mechanics → Pi-runtime parallelism note), where the orchestrator commits each task's files as
soon as its implementer reports DONE. When that fallback is in effect, strip step 4 ("Commit your
work") from the prompt body's Your Job list and tell the worker to report files changed instead
of a commit SHA in its final report.

## Invocation

Write the assembled prompt body to a task/role-keyed file **outside the repository**
(see SKILL.md → Dispatch hygiene — never a generic name inside the worktree, where a
worker could commit or clobber it), e.g. `<scratch>/t<N>-implementer.md`, then:

```bash
cd <worktree>
PROMPT=<scratch>/t<N>-implementer.md
[ -f "$PROMPT" ] || { echo "prompt missing" >&2; exit 1; }
pi-watch --alias codex --thinking xhigh \
  --tools read,bash,edit,write \
  "$(cat "$PROMPT")"
```

`pi-watch` has no `@file` include — the prompt is passed as a positional string, so the file's
contents are inlined via `$(cat ...)`. It resolves the newest authed model in the `codex` alias's
fallback ladder automatically; hard-pinning an exact model id via `--provider`/`--model` is the
documented exception (**quirk:pi-dev**), not the default.

Verify the prompt file exists before dispatching — never fall back to
something like `cat prompt.md || echo MISSING` that pipes garbage into a live
worker; a bad prompt burns the entire dispatch.

For scripted/CI dispatch that needs JSONL events and exit-code capture instead of this
interactive form, see **quirk:pi-dev → reference/print-mode.md#canonical-headless-recipe**.

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
