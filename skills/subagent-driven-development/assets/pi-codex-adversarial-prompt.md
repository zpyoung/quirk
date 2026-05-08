# Pi Codex Adversarial Reviewer Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection).

The Codex adversarial reviewer model is **pi codex** (`openai-codex/gpt-5.3-codex:xhigh`), invoked read-only.

**Only dispatch after both pi spec compliance review and pi code quality review have passed.**

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
- `SPEC_REVIEW`: verdict + summary from the spec compliance reviewer
- `QUALITY_REVIEW`: verdict + summary from the code quality reviewer

The prompt MUST instruct the reviewer to:

- Read the actual implementation files (pi codex has filesystem access via
  `--tools read,bash`); do not trust the implementer self-report blindly.
- For each task requirement, find the file:line where it's implemented and
  cite evidence.
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
pi -p \
  --no-session \
  --offline \
  --model openai-codex/gpt-5.3-codex:xhigh \
  --tools read,bash \
  @codex-adversarial-prompt.md
```

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
- **CRITICAL or HIGH:** dispatch the same pi implementer subagent with the
  findings; re-run pi codex review. Cap: 2 cycles total.

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to Claude (PAL clink codex) for the rest of the plan
(SKILL.md → Fallback).
