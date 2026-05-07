# Pi Code Quality Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The code-quality reviewer model is **pi gemini** (`google/gemini-3.1-pro-preview:high`).

**Only dispatch after spec compliance review passes.**

## Prompt body

The Claude path uses the `quirk:code-reviewer` agent template (see
`code-quality-reviewer-prompt.md`). The pi path needs the same review prompt
inlined, because pi has no awareness of Claude Code agent definitions.

Build the prompt body from the template at
`requesting-code-review/code-reviewer.md` — substitute the placeholders the
same way the Claude `Task` invocation would:

- `WHAT_WAS_IMPLEMENTED`: from the implementer's report
- `PLAN_OR_REQUIREMENTS`: Task N from `[plan-file]`
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

Write the assembled prompt body to `quality-review-prompt.md` in the worktree,
then:

```bash
cd <worktree>
pi -p \
  --no-session \
  --offline \
  --model google/gemini-3.1-pro-preview:high \
  --tools read,bash \
  @quality-review-prompt.md
```

`--tools read,bash` keeps the reviewer read-only. The prompt body forbids
modifications.

For the hardened multi-arg recipe, see **quirk:pi-dev → Canonical headless
dispatch recipe**.

## Output parsing

The reviewer's final message contains `Strengths`, `Issues` grouped by
severity, and an `Assessment`. Parse pi's stdout for that structure. If
issues exist, dispatch the implementer to fix and re-review (same loop as the
Claude path).

If pi's response is unparseable, apply **quirk:pi-dev → Reviewer JSON parse
fallback** (cascade: whole-message JSON → fenced block → balanced braces →
synthesize a NEEDS_FIX verdict). Never count an unparseable response as PASS.

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude agents for the rest of the plan (SKILL.md → Fallback).
