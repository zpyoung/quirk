# Codex Adversarial Reviewer Prompt Template

Use this template when dispatching the **third per-task review pass** — the Codex adversarial reviewer.

**Purpose:** Find gaps between the task spec and its implementation that the spec-compliance and code-quality reviewers may have missed. Adversarial: only critique, never validate.

**Only dispatch after both spec compliance review and code quality review have passed.**

**Fix loop cap:** 2 cycles. After two cycles of CRITICAL/HIGH findings, remaining issues carry forward to the final whole-branch reviewer (do not block the task indefinitely).

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
    Spec compliance: [verdict + summary]
    Code quality: [verdict + summary]

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

- **PASS / LOW only:** mark task complete (or, in `WORKTREE_PARALLEL` mode, proceed to rolling auto-merge).
- **NEEDS_FIXES (MEDIUM):** note in the final report; do not block task completion.
- **NEEDS_FIXES / CRITICAL_ISSUES (CRITICAL or HIGH):** dispatch the **same implementer subagent** with the findings. Re-run Codex. Repeat up to **2 cycles** total. After cycle 2, mark the task complete with unresolved findings flagged for the final whole-branch reviewer.
