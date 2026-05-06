# Pi Spec Compliance Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The spec reviewer model is **pi gemini** (`google/gemini-3-1-pro-preview:high`).

## Prompt body

Use the prompt body from `spec-reviewer-prompt.md` (everything inside the
prompt block — What Was Requested, What Implementer Claims, CRITICAL: Do Not
Trust the Report, Your Job, Report).

## Invocation

Write the assembled prompt body to `spec-review-prompt.md` in the worktree,
then:

```bash
cd <worktree>
pi -p \
  --no-session \
  --offline \
  --model google/gemini-3-1-pro-preview:high \
  --tools read,bash \
  @spec-review-prompt.md
```

`--tools read,bash` lets the reviewer inspect the implementation (read files,
grep) without granting edit/write — pi's closest match to read-only review.
The prompt body itself forbids any modifications.

For the hardened multi-arg recipe, see **quirk:pi-dev → Canonical headless
dispatch recipe**.

## Output parsing

The prompt body asks the reviewer to end with one of:
- `✅ Spec compliant`
- `❌ Issues found: ...`

Parse pi's stdout for that marker. Apply the same review-loop handling as the
Claude path (SKILL.md → The Process).

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude agents for the rest of the plan (SKILL.md → Fallback).
