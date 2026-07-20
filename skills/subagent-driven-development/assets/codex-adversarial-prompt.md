# Codex Adversarial Reviewer Prompt Template

Use this template when dispatching the **third per-task review pass** — the Codex adversarial reviewer.

**Purpose:** Find gaps between the task spec and its implementation that the spec-compliance and code-quality reviewers may have missed. Adversarial: only critique, never validate.

Dispatched concurrently with the other reviewers applicable to the task's risk tier (spec
compliance always runs; code quality only for `logic` tasks — a `pattern` task has no
code-quality pass), after the implementer reports.

**Fix loop cap:** 2 cycles. After two cycles, an unresolved CRITICAL finding BLOCKS the task
(escalate to the user); an unresolved HIGH finding may carry forward only via the
unresolved-findings ledger pasted into the final whole-branch reviewer's dispatch prompt (SKILL.md
→ The Codex adversarial reviewer specifically).

## Invocation

```
mcp__pal__clink:
  cli_name: "codex"
  role: "codereviewer"
  absolute_file_paths: [<every file the implementer created or modified for this task>]
  prompt: |
    You are an adversarial code reviewer for a single task in an implementation plan.
    Find GAPS between the task spec and its implementation. Do NOT validate — only critique.

    IMPORTANT: You have the actual implementation files via absolute_file_paths.
    You MUST read and inspect the code directly. Do NOT trust worker self-reports —
    verify every claim against the files.

    ## Task Spec
    Title: [task title]
    Body: [full task body from plan — paste verbatim]
    Files declared: [list from task]

    ## Implementer Self-Report
    [paste implementer's structured output]

    ## Prior Reviewer Outputs
    Other reviewers are running concurrently; their outputs are not available — verify every
    claim independently.

    ## Review Protocol
    The task specifies BEHAVIOR, not code — it carries a Contract and Acceptance
    criteria, not a reference implementation. Treat each Acceptance criterion and
    each Contract clause (preconditions, postconditions, invariants, error
    behavior) as a requirement. For EACH such requirement:
    1. Find the file:line where it's satisfied — cite evidence.
    2. Verify the implementation honors that criterion / contract clause.
    3. Check for hidden complexities (over-engineering, unrequested features).
    4. Check error handling and edge cases.
    5. Verify any cross-file consistency the task implies.

    If a claim cannot be located in the files, rate as CRITICAL.
    If a previous reviewer's PASS verdict appears unsupported by the files, flag as HIGH.

    ## Output Format
    For each finding:
    SEVERITY: [CRITICAL | HIGH | MEDIUM | LOW]
    REQUIREMENT: [which task requirement, if applicable]
    FILE: [file path and line range]
    FINDING: [what's wrong, 1-2 sentences]
    SUGGESTED_FIX: [how to fix, 1-2 sentences]

    End with:
    SUMMARY: [total counts per severity]
    VERDICT: [PASS | NEEDS_FIXES | CRITICAL_ISSUES]
```

## Handling the verdict

Codex is **report-only**: it never marks a task complete and never triggers a merge on its own.
Every verdict and finding — PASS, LOW, MEDIUM, HIGH, or CRITICAL — feeds the orchestrator's
fan-in across all reviewers applicable to the task's risk tier. Task completion (and, in
`WORKTREE_PARALLEL` mode, the rolling auto-merge) is decided only after all applicable reviewers
have reported and every accepted finding has been resolved, per SKILL.md → Adjudication.

- **PASS / LOW only:** no findings to adjudicate from this reviewer; the orchestrator proceeds
  once the other applicable reviewers have also cleared.
- **MEDIUM, HIGH, or CRITICAL findings:** report them back to the orchestrator. Do not dispatch a
  fix loop yourself. The orchestrator merges them with the spec-compliance and code-quality
  findings, adjudicates overlaps/conflicts (accepted findings of ANY severity enter the
  consolidated fix — severity controls re-review depth, not whether a finding gets fixed), and
  issues **one consolidated fix dispatch** to the implementer covering all applicable reviews.
  Re-run Codex (and the other reviewers as needed) against the fix for CRITICAL/HIGH findings.
  Repeat up to **2 cycles** total — see SKILL.md → The Codex adversarial reviewer specifically for
  the cycle definition and what happens to findings still unresolved after cycle 2 (CRITICAL
  blocks the task; HIGH may carry forward only via the unresolved-findings ledger).
