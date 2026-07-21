# Codex Adversarial Reviewer Prompt Template

Use this template when the task captain dispatches the **third per-task review pass** — the Codex adversarial reviewer. If no captain can be dispatched, the orchestrator uses it while acting as the fallback dispatcher.

**Purpose:** Find gaps between the task spec and its implementation that the spec-compliance and code-quality reviewers may have missed. Adversarial: only critique, never validate.

The task captain (or the orchestrator acting as fallback dispatcher when no captain can be
dispatched) dispatches this concurrently with the other reviewers applicable to the task's risk
tier (spec compliance always runs; code quality only for `logic` tasks — a `pattern` task has no
code-quality pass), after the implementer reports.

**Fix loop cap:** 2 cycles. After two cycles, an unresolved CRITICAL finding emits an
`ESCALATION` event, is appended to the unresolved-findings ledger, and follows the §4 escalation
handling in `SKILL.md`; the Phase 1 full-chain gate remains closed. An unresolved HIGH finding
may carry forward only via that ledger pasted into the final whole-branch reviewer's dispatch
prompt (SKILL.md → The Codex adversarial reviewer specifically).

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

    ## Suggested patch
    For each LOW or MEDIUM finding, and each HIGH finding whose fix is mechanical/objective
    rather than a judgment call, attach a proposed unified diff capped at roughly 20 changed
    lines. Patch paths must stay within the task's declared `scope.files` and outside every
    path in `scope.never_touch`. For CRITICAL findings or any finding requiring judgment,
    attach no patch; those findings stay report-only.

    You remain report-only for every finding: propose eligible patch text as part of the
    finding, but never apply it, run `git apply`, or edit files.

    ## Output Format
    For each finding:
    SEVERITY: [CRITICAL | HIGH | MEDIUM | LOW]
    REQUIREMENT: [which task requirement, if applicable]
    FILE: [file path and line range]
    FINDING: [what's wrong, 1-2 sentences]
    SUGGESTED_FIX: [how to fix, 1-2 sentences]
    SUGGESTED_PATCH: [required unified diff for LOW/MEDIUM/mechanical-HIGH; NONE for
      CRITICAL or judgment-requiring findings]

    End with:
    SUMMARY: [total counts per severity]
    VERDICT: [PASS | NEEDS_FIXES | CRITICAL_ISSUES]
```

## Handling the verdict

Codex is **report-only**: it never marks a task complete, triggers a merge, applies a patch, runs
`git apply`, or edits files on its own. Every verdict and finding — PASS, LOW, MEDIUM, HIGH, or
CRITICAL — feeds the task captain's fan-in across all reviewers applicable to the task's risk
tier (or the orchestrator's when it is acting as fallback dispatcher). Task completion (and, in
`WORKTREE_PARALLEL` mode, the rolling auto-merge) is decided only after all applicable reviewers
have reported and every accepted finding has been resolved, per SKILL.md → Adjudication.

- **PASS:** no findings to adjudicate from this reviewer; the captain (or fallback orchestrator)
  proceeds once the other applicable reviewers have also cleared.
- **LOW, MEDIUM, or mechanical/objective HIGH findings:** report each with its attached Suggested
  patch. Do not apply it or dispatch a fix loop yourself. The captain (or fallback orchestrator)
  adjudicates it and may apply an accepted patch directly only after enforcing the roughly-20-
  changed-line cap, running `git apply --check` against the current tree, and confirming all patch
  paths are within `scope.files` and outside `scope.never_touch`; it then reruns the task's affected
  acceptance checks.
- **CRITICAL or judgment-requiring findings:** report them with no patch and do not dispatch a fix
  loop yourself. The captain (or fallback orchestrator) merges them with the spec-compliance and
  code-quality findings, adjudicates overlaps/conflicts, and routes accepted findings to the fix
  worker in **one consolidated fix dispatch** covering all applicable reviews. Re-run Codex (and
  the other reviewers as needed) against the fix for CRITICAL/HIGH findings. Repeat up to **2
  cycles** total — see SKILL.md → The Codex adversarial reviewer specifically for the cycle
  definition and what happens to findings still unresolved after cycle 2 (CRITICAL blocks the
  task; HIGH may carry forward only via the unresolved-findings ledger).
