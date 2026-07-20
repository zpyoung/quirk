# Pi Spec Compliance Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The spec reviewer model is the **pi-dev `gemini` alias** (see **quirk:pi-dev**) — not a frozen
model id. `pi-watch` resolves the newest authed model in the alias's fallback ladder;
hard-pinning an exact id via `--provider`/`--model` is the documented exception, not the default.

## Prompt body

Use the prompt body from `spec-reviewer-prompt.md` (everything inside the
prompt block — What Was Requested, What Implementer Claims, CRITICAL: Do Not
Trust the Report, Your Job, Report).

## Invocation

Write the assembled prompt body to a task/role-keyed file **outside the repository**
(see SKILL.md → Dispatch hygiene — never a generic name inside the worktree, where a
worker could commit or clobber it), e.g. `<scratch>/t<N>-spec-review.md`, then:

```bash
cd <worktree>
PROMPT=<scratch>/t<N>-spec-review.md
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
something like `cat spec-review-prompt.md || echo MISSING` that pipes garbage
into a live worker; a bad prompt burns the entire dispatch.

`--tools read,bash` grants the reviewer shell access, not read-only access — `bash` can mutate
the filesystem (write files, run git commands, delete things); nothing in the tool grant enforces
read-only behavior. The prompt body instructs the reviewer not to modify anything, but that
constraint is behavioral (the model choosing to comply), not enforced by the allowlist. When the
reviewer doesn't need to run builds, tests, or git commands — the common case for a
spec-compliance pass — prefer `--tools read,grep,find,ls`, which is actually read-only (no shell
at all).

For the hardened multi-arg recipe, see **quirk:pi-dev →
reference/print-mode.md#canonical-headless-recipe**.

## Output parsing

The prompt body asks the reviewer to end with one of:
- `✅ Spec compliant`
- `❌ Issues found: ...`

Parse pi's stdout for that marker. Apply the same review-loop handling as the
Claude path (SKILL.md → The Process).

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude agents for the rest of the plan (SKILL.md → Fallback).
