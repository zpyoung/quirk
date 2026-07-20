# Pi Codex Adversarial Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The Codex adversarial reviewer model is **pi codex** (`openai-codex/gpt-5.3-codex:xhigh`), invoked read-only.

Dispatched concurrently with the spec-compliance and code-quality reviewers, after the implementer reports.

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
- `SPEC_REVIEW`: verdict + summary from the spec compliance reviewer, if
  available — it runs concurrently with this reviewer, so it will usually
  still be in progress; note that explicitly in the prompt rather than
  omitting the placeholder
- `QUALITY_REVIEW`: verdict + summary from the code quality reviewer, same
  caveat — assume nothing has been blessed and verify every claim
  independently

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

Write the assembled prompt body to `codex-adversarial-prompt.md` in the
worktree, then:

```bash
cd <worktree>
[ -f codex-adversarial-prompt.md ] || { echo "prompt missing" >&2; exit 1; }
pi -p \
  --no-session \
  --offline \
  --model openai-codex/gpt-5.3-codex:xhigh \
  --tools read,bash \
  @codex-adversarial-prompt.md
```

Verify the prompt file exists before dispatching — never fall back to
something like `cat codex-adversarial-prompt.md || echo MISSING` that pipes
garbage into a live worker; a bad prompt burns the entire dispatch.

`--tools read,bash` keeps the reviewer read-only. The prompt body forbids
modifications.

For the hardened multi-arg recipe, see **quirk:pi-dev → Canonical headless
dispatch recipe**.

## Output parsing

The reviewer's final message contains SEVERITY-tagged findings and a final
SUMMARY + VERDICT line. Parse pi's stdout for that structure.

If pi's response is unparseable, apply **quirk:pi-dev → Reviewer JSON parse
fallback** (cascade: whole-message JSON → fenced block → balanced braces →
synthesize a NEEDS_FIX verdict). Never count an unparseable response as PASS.

## Handling the verdict

Same as the Claude path:

- **PASS / LOW only:** mark task complete (or proceed to rolling auto-merge in
  `WORKTREE_PARALLEL` mode).
- **NEEDS_FIXES (MEDIUM):** note in the final report; do not block.
- **CRITICAL or HIGH:** do not dispatch a fix loop yourself. Report findings
  back to the orchestrator, which merges them with the spec-compliance and
  code-quality reviewers' findings, adjudicates overlaps/conflicts, and
  issues one consolidated fix dispatch to the pi implementer covering all
  three reviews. Re-run pi codex review (and the other reviewers as needed)
  against the fix. Cap: 2 cycles total.

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude (PAL clink codex) for the rest of the plan
(SKILL.md → Fallback).
