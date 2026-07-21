# Pi Spec Compliance Reviewer Dispatch Template

Use this when the task captain dispatches the spec compliance reviewer on the **pi** runtime
(see SKILL.md → Runtime Selection). If no captain can be dispatched, the orchestrator uses it
while acting as the fallback dispatcher.

The spec reviewer model is the **pi-dev `gemini` alias** (see **quirk:pi-dev**) — not a frozen
model id. `pi-watch` resolves the newest authed model in the alias's fallback ladder;
hard-pinning an exact id via `--provider`/`--model` is the documented exception, not the default.

## Prompt body

Use the prompt body from `spec-reviewer-prompt.md` (everything inside the
prompt block — What Was Requested, What Implementer Claims, CRITICAL: Do Not
Trust the Report, Your Job, Suggested patch, Report).

## Suggested patch

The assembled prompt must require the reviewer to attach a unified diff capped at roughly 20
changed lines for each mechanical/objective finding. It must forbid patches for
judgment-requiring findings, confine patch paths to `scope.files` and outside
`scope.never_touch`, and keep the reviewer report-only: it proposes patch text in the finding
but never applies it, runs `git apply`, or edits files.

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

Parse pi's stdout for that marker and any per-finding `Suggested patch` content. The task
captain (or the orchestrator acting as fallback dispatcher) may apply an accepted eligible patch
only after enforcing the roughly-20-changed-line cap, confirming its paths are within
`scope.files` and outside `scope.never_touch`, and running `git apply --check` against the
current tree. CRITICAL and judgment-requiring findings have no patch and route to the fix worker.
The reviewer only proposes patch text; it never applies a patch or edits files. Apply the same
review-loop handling as the Claude path (SKILL.md → The Process).

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude agents for the rest of the plan (SKILL.md → Fallback).
