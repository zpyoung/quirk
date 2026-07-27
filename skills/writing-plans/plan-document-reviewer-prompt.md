# Plan Document Reviewer Prompt Template

Use this template when dispatching a plan document reviewer subagent.

**Purpose:** Verify the plan is complete, matches the tech spec (`tech.md`) when present — else the logic spec / requirements — and has proper task decomposition.

**Dispatch:** Automatically, by default, once the in-context plan is drafted (the execution
skill's planning phase) — this is the standard review step, not optional, and replaces any human
approval gate.

**Input:** Paste the plan text **inline** (the plan lives in context, not a file). Paste the tech
spec (`tech.md`) when present — else the logic spec / requirements — text or its path for
reference. The reviewer does not read a plan file.

```
Task tool (general-purpose):
  description: "Review plan document"
  prompt: |
    You are a plan document reviewer. Verify this plan is complete and ready for implementation.

    **Plan to review (inline):**
    [PASTE FULL PLAN TEXT HERE]

    **Spec for reference (tech spec `tech.md` when present, else logic spec):** [PASTE TECH.MD OR LOGIC SPEC TEXT / FILE PATH]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Completeness | TODOs, placeholders, vague/ambiguous steps (no behavioral goal, no acceptance check) — AND pasted implementation/test bodies (over-specification). Both are defects. |
    | Spec Alignment | Plan covers the tech spec (or logic spec) requirements, no major scope creep |
    | Task Decomposition & Cohesion | Does the plan show a file-coupling map/rationale based on imports and shared files before declaring dependencies and waves, and minimize cross-task coupling? Tasks should be vertical slices of user-visible behavior, not unjustified horizontal layers such as "all API routes." Hub-file isolation is a scored heuristic, not a mandate: prefer the slice that owns the behavior; require explicit rationale and serialized integration for a standalone hub task when no slice owns it. |
    | Scope Declarations | Does every task that may run in parallel declare a complete `scope.files`? A list is complete only if it covers the task's tests and any index/barrel file it must re-export from — the orchestrator audits each task's diff against it, so an under-declared file stops the wave mid-run. Flag any two tasks in the same wave that share a file path: they cannot run in parallel. |
    | Coherence Sweep | When the plan changes a protocol, vocabulary, or event set, did it use repository-wide greps to enumerate every file referencing the changed old or new terms? Is every result either scoped into a task or explicitly recorded as `unchanged, verified consistent`? Check that the sweep searched the vocabulary terms themselves, not only the names of the components being changed — a file can encode a protocol without naming the skill or module that owns it, and those are exactly the ones a name-based search misses. |
    | Granularity Economics | Flag every overhead-unjustified split: a split must land tasks in different waves to buy real parallelism. Same-risk sequential runs should collapse; projected diffs under roughly 50–100 lines should merge into a neighbor. Review isolation should use per-sub-step commit boundaries inside one task, and target task count should follow achievable wave width rather than requirement-bullet count. |
    | Contract Completeness | Does every task specify the contract it must satisfy — preconditions, postconditions, invariants, error behavior — for any unit other tasks or systems depend on? Is every interface referenced by one task actually specified by some task? |
    | Altitude | Does each task specify WHAT (behavior, contract, acceptance) rather than HOW (literal code)? Any code present must be a justified, tagged exception — `CONTRACT:` signature sketch, `SCHEMA:`, `COMMAND:`, `REGEX:`, `CONFIG:`, or `PSEUDOCODE (justified):` (≤3 lines). Flag any untagged code block, runnable function body, or full test body. |
    | Acceptance Criteria | Is every acceptance criterion a literal, copy-runnable command with exact flags and an expected result, never a prose description of a check? Could the orchestrator and the worker execute exactly the same command without choosing flags? |
    | Buildability | Could an engineer follow this plan without getting stuck? |

    ## Calibration

    **Only flag issues that would cause real problems during implementation.**
    An implementer building the wrong thing or getting stuck is an issue.
    Minor wording, stylistic preferences, and "nice to have" suggestions are not.

    Approve unless there are serious gaps — missing requirements from the tech
    spec (or logic spec), contradictory steps, ambiguity that yields two or more
    reasonable implementations, OR full implementation/test bodies that pre-empt
    the implementor, or tasks so vague they can't be acted on.

    ## Output Format

    ## Plan Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Task X, Step Y]: [specific issue] - [why it matters for implementation]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

**Reviewer returns:** Status, Issues (if any), Recommendations
