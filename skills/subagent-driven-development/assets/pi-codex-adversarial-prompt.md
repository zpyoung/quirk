# Pi Codex Adversarial Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The Codex adversarial reviewer model is the **pi-dev `codex` alias at `xhigh` thinking** (see
**quirk:pi-dev**) — not a frozen model id; hard-pinning an exact id via `--provider`/`--model` is
the documented exception, not the default. It runs with `--tools read,bash`, which grants shell
access, not enforced read-only — see Invocation below.

Dispatched concurrently with the other reviewers applicable to the task's risk tier (spec
compliance always runs; code quality only for `logic` tasks — a `pattern` task has no
code-quality pass), after the implementer reports.

**Fix loop cap:** 2 cycles. After two cycles of CRITICAL/HIGH findings, remaining issues carry forward to the final whole-branch reviewer (Claude `quirk:code-reviewer`, regardless of runtime).

## Prompt body

The Claude path uses `mcp__pal__clink` with the codex codereviewer role (see
`codex-adversarial-prompt.md`). The pi path needs the same review prompt
inlined, because pi has no awareness of PAL clink role definitions.

Build the prompt body using the same review protocol as the Claude path:

- `TASK_TITLE`: from the task in the plan
- `TASK_BODY`: full task body, pasted verbatim
- `FILES_DECLARED`: list of files the task body declared as in scope
- `IMPLEMENTER_REPORT`: the implementer's structured self-report

Do NOT include `SPEC_REVIEW`/`QUALITY_REVIEW` paste-placeholders — under same-turn concurrent
dispatch, those reviewers' outputs are never available yet, so there is nothing to paste. State a
fixed line instead: "Other reviewers are running concurrently; their outputs are not
available — verify every claim independently."

The prompt MUST instruct the reviewer to:

- Read the actual implementation files (pi codex has filesystem access via
  `--tools read,bash`); do not trust the implementer self-report blindly.
- The task specifies behavior, not code (it carries a Contract and Acceptance
  criteria, no reference implementation). For each requirement — each Acceptance
  criterion and each Contract clause (preconditions, postconditions, invariants,
  error behavior) — find the file:line where it's satisfied and cite evidence.
- Flag CRITICAL when a claim cannot be located in the files.
- Flag HIGH when a previous reviewer's PASS appears unsupported.
- Output SEVERITY-tagged findings with REQUIREMENT / FILE / FINDING /
  SUGGESTED_FIX, ending with SUMMARY (counts per severity) and VERDICT
  (`PASS | NEEDS_FIXES | CRITICAL_ISSUES`).

End the prompt with: "Be adversarial. Do NOT validate — only critique."

## Invocation

Write the assembled prompt body to a task/role-keyed file **outside the repository**
(see SKILL.md → Dispatch hygiene — never a generic name inside the worktree, where a
worker could commit or clobber it), e.g. `<scratch>/t<N>-codex-adversarial.md`, then:

```bash
cd <worktree>
PROMPT=<scratch>/t<N>-codex-adversarial.md
[ -f "$PROMPT" ] || { echo "prompt missing" >&2; exit 1; }
pi-watch --alias codex --thinking xhigh \
  --tools read,bash \
  "$(cat "$PROMPT")"
```

`pi-watch` has no `@file` include — the prompt is passed as a positional string, so the file's
contents are inlined via `$(cat ...)`. It resolves the newest authed model in the `codex` alias's
fallback ladder automatically; hard-pinning an exact model id via `--provider`/`--model` is the
documented exception (**quirk:pi-dev**), not the default.

Verify the prompt file exists before dispatching — never fall back to
something like `cat codex-adversarial-prompt.md || echo MISSING` that pipes
garbage into a live worker; a bad prompt burns the entire dispatch.

`--tools read,bash` grants shell access, not enforced read-only — `bash` can mutate the
filesystem; the prompt body forbids modifications behaviorally, not via the tool grant. This
reviewer needs to read and grep implementation files but not run builds/tests/git, so prefer
`--tools read,grep,find,ls` (actually read-only) unless a specific check needs shell.

For the hardened multi-arg recipe, see **quirk:pi-dev →
reference/print-mode.md#canonical-headless-recipe**.

## Output parsing

The reviewer's final message contains SEVERITY-tagged findings and a final
SUMMARY + VERDICT line. Parse pi's stdout for that structure.

If pi's response is unparseable, apply **quirk:pi-dev → Reviewer JSON parse
fallback** (cascade: whole-message JSON → fenced block → balanced braces →
synthesize a NEEDS_FIX verdict). Never count an unparseable response as PASS.

## Handling the verdict

Same principle as the Claude path (`codex-adversarial-prompt.md` → Handling the verdict): Codex is
**report-only**. It never marks a task complete and never triggers rolling auto-merge on its
own — every verdict and finding (PASS, LOW, MEDIUM, HIGH, CRITICAL) feeds the orchestrator's
fan-in across all reviewers applicable to the task's risk tier, and completion is decided only
after adjudication resolves every accepted finding (SKILL.md → Adjudication).

- **PASS / LOW only:** no findings to adjudicate from this reviewer — the orchestrator proceeds
  once the other applicable reviewers have also cleared.
- **MEDIUM, HIGH, or CRITICAL findings:** report them back to the orchestrator; do not dispatch a
  fix loop yourself. The orchestrator merges them with the spec-compliance and code-quality
  findings, adjudicates overlaps/conflicts (any accepted finding gets fixed regardless of
  severity — severity only controls re-review depth, not whether it's fixed), and issues one
  consolidated fix dispatch to the pi implementer covering all applicable reviews. Re-run pi codex
  review (and the other reviewers as needed) against the fix for CRITICAL/HIGH findings. Cap: 2
  cycles total (SKILL.md → The Codex adversarial reviewer specifically has the cycle definition
  and what happens after cap exhaustion).

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude (PAL clink codex) for the rest of the plan
(SKILL.md → Fallback).
