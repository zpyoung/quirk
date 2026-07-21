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
    | Task Decomposition & Cohesion | Does the plan show a file-coupling map/rationale based on imports and shared files before declaring independence, dependencies, and waves, and minimize cross-task coupling? Tasks should be vertical slices of user-visible behavior, not unjustified horizontal layers such as "all API routes." Hub-file isolation is a scored heuristic, not a mandate: prefer the slice that owns the behavior; require explicit rationale and serialized integration for a standalone hub task when no slice owns it. If no wave of at least two disjoint tasks is possible, does the plan keep the same captain state machine at width 1? Remember that task count is not the gate: two disjoint tasks are a valid width-2 wave. |
    | Scope & Never-Touch Lists | In captain mode, does every task declare both allowed `scope.files` and forbidden `scope.never_touch`? Where a wave has adjacent-file ownership risk, does each never-touch list cover the adjacent files its peers own (negative scope beats positive scope)? |
    | Granularity Economics | Flag every overhead-unjustified split: each split must either land tasks in different waves (real parallelism) or cross a risk-tier boundary (a cheaper review chain). Same-risk sequential runs should collapse; projected diffs under roughly 50–100 lines should merge into a same-tier neighbor at the maximum tier. Review isolation should use per-sub-step commit boundaries inside one task, and target task count should follow achievable wave width rather than requirement-bullet count. |
    | Risk & Contract Fields | For captain-mode plans, does every task have an explicit `risk` field with a one-line rationale? Omission is a finding: there is no silent default. Judge every tier's rationale, including `logic`, and demand the strongest justification for `pattern`/`mechanical` downgrades because they remove review passes. `mechanical` tasks must touch no executable logic AND state an exact, verifiable acceptance gate (build/test/grep command with expected output); `pattern` tasks must name the exemplar task they mirror. Does every `.contract` dependency target a `logic` or `pattern` task (never `mechanical`) that specifies the consumed contract in a tagged `CONTRACT:`/`SCHEMA:` block? |
    | Altitude | Does each task specify WHAT (behavior, contract, acceptance) rather than HOW (literal code)? Any code present must be a justified, tagged exception — `CONTRACT:` signature sketch, `SCHEMA:`, `COMMAND:`, `REGEX:`, `CONFIG:`, or `PSEUDOCODE (justified):` (≤3 lines). Flag any untagged code block, runnable function body, or full test body. |
    | Acceptance Criteria | Does each task carry an observable, testable success condition? |
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
