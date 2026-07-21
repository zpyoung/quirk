# Code Quality Reviewer Prompt Template

Use this template when the task captain dispatches a code quality reviewer subagent. If no captain can be dispatched, the orchestrator uses it while acting as the fallback dispatcher.

**Purpose:** Verify implementation is well-built (clean, tested, maintainable)

The task captain (or the orchestrator acting as fallback dispatcher when no captain can be
dispatched) uses this pass only for a `logic` task and dispatches it concurrently with spec
compliance after the implementer reports. Reviewer selection is tier-based (`logic`: spec +
quality; `pattern`: spec; `mechanical`: none). Codex is separate: an eligible `logic`/`pattern`
task gets per-task Codex only for **>150 added+deleted lines OR a changed contract surface**
(`CONTRACT:`/`SCHEMA:` hunk or a changed file listed under a contract). Otherwise record
`CODEX-DEFERRED(task-id)`; branch-level Codex is **Phase 2 (future)**, not Phase 1 coverage.

```
Task tool (quirk:code-reviewer):
  Use template at requesting-code-review/code-reviewer.md

  WHAT_WAS_IMPLEMENTED: [from implementer's report]
  PLAN_OR_REQUIREMENTS / PLAN_REFERENCE: [paste Task N's full text inline — Contract, Acceptance,
    everything. Plans are in-context by default; never point to a plan file. The underlying
    template uses both names for the same slot; fill both with the same pasted text.]
  BASE_SHA: [commit before task]
  HEAD_SHA: [current commit]
  DESCRIPTION: [task summary]
```

**In addition to standard code quality concerns, the reviewer should check:**
- Does each file have one clear responsibility with a well-defined interface?
- Are units decomposed so they can be understood and tested independently?
- Is the implementation following the file structure from the plan?
- Did this implementation create new files that are already large, or significantly grow existing files? (Don't flag pre-existing file sizes — focus on what this change contributed.)

**Code reviewer returns:** Strengths, Issues (Critical/Important/Minor), Assessment

## Suggested patch

For each Minor finding, and each Important finding whose fix is mechanical/objective rather
than a judgment call, the reviewer must attach a proposed unified diff capped at roughly 20
changed lines. Patch paths must stay within the task's declared `scope.files` and outside every
path in `scope.never_touch`. Critical findings and findings requiring judgment stay report-only
with no patch attached.

The task captain (or fallback orchestrator) may apply an accepted eligible patch only after
enforcing the size and scope guards and running `git apply --check` against the current tree.
The reviewer remains report-only for every finding: it proposes eligible patch text as part of
its report, but never applies it, runs `git apply`, or edits files.
