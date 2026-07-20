# Pi Code Quality Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The code-quality reviewer model is the **pi-dev `gemini` alias** (see **quirk:pi-dev**) — not a
frozen model id. `pi-watch` resolves the newest authed model in the alias's fallback ladder;
hard-pinning an exact id via `--provider`/`--model` is the documented exception, not the default.

Dispatched concurrently with the spec-compliance and Codex adversarial reviewers, after the implementer reports.

## Prompt body

The Claude path uses the `quirk:code-reviewer` agent template (see
`code-quality-reviewer-prompt.md`). The pi path needs the same review prompt
inlined, because pi has no awareness of Claude Code agent definitions.

Build the prompt body from the template at
`requesting-code-review/code-reviewer.md` — substitute the placeholders the
same way the Claude `Task` invocation would:

- `WHAT_WAS_IMPLEMENTED`: from the implementer's report
- `PLAN_OR_REQUIREMENTS` / `PLAN_REFERENCE`: paste Task N's full text inline (Contract,
  Acceptance, everything) — plans are in-context by default; subagents never read a plan file.
  The underlying template uses both names for the same slot; fill both with the same pasted text.
- `BASE_SHA`: commit before this task
- `HEAD_SHA`: current commit
- `DESCRIPTION`: short task summary

Append the same additional checks the Claude path requires:
- Does each file have one clear responsibility with a well-defined interface?
- Are units decomposed so they can be understood and tested independently?
- Is the implementation following the file structure from the plan?
- Did this implementation create new files that are already large, or
  significantly grow existing files? (Don't flag pre-existing file sizes —
  focus on what this change contributed.)

End the prompt with: "Return Strengths, Issues grouped Critical/Important/Minor,
and an Assessment line."

## Invocation

Write the assembled prompt body to a task/role-keyed file **outside the repository**
(see SKILL.md → Dispatch hygiene — never a generic name inside the worktree, where a
worker could commit or clobber it), e.g. `<scratch>/t<N>-quality-review.md`, then:

```bash
cd <worktree>
PROMPT=<scratch>/t<N>-quality-review.md
[ -f "$PROMPT" ] || { echo "prompt missing" >&2; exit 1; }
pi-watch --alias gemini \
  --tools read,bash \
  "$(cat "$PROMPT")"
```

`pi-watch` has no `@file` include — the prompt is passed as a positional string, so the file's
contents are inlined via `$(cat ...)`. It resolves the newest authed model in the `gemini` alias's
fallback ladder automatically; hard-pinning an exact model id via `--provider`/`--model` is the
documented exception (**quirk:pi-dev**), not the default.

Verify the prompt file exists before dispatching — never fall back to
something like `cat quality-review-prompt.md || echo MISSING` that pipes
garbage into a live worker; a bad prompt burns the entire dispatch.

`--tools read,bash` grants shell access, not enforced read-only — `bash` can mutate the
filesystem; the prompt body forbids modifications behaviorally, not via the tool grant. This
reviewer doesn't need to run builds, tests, or git, so prefer `--tools read,grep,find,ls`
(actually read-only) unless a specific check needs shell.

For the hardened multi-arg recipe, see **quirk:pi-dev →
reference/print-mode.md#canonical-headless-recipe**.

## Output parsing

The reviewer's final message contains `Strengths`, `Issues` grouped by
severity, and an `Assessment`. Parse pi's stdout for that structure. Findings are returned to the
orchestrator for fan-in and adjudication alongside the other reviewers applicable to the task's
risk tier, then folded into the single consolidated fix — there is no per-reviewer fix loop
(SKILL.md → Per-task review chain).

If pi's response is unparseable, apply **quirk:pi-dev → Reviewer JSON parse
fallback** (cascade: whole-message JSON → fenced block → balanced braces →
synthesize a NEEDS_FIX verdict). Never count an unparseable response as PASS.

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude agents for the rest of the plan (SKILL.md → Fallback).
