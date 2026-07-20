# Plan Document Reviewer Prompt Template

Use this template when dispatching a plan document reviewer subagent.

**Purpose:** Verify the plan is complete, matches the spec, and has proper task decomposition.

**Dispatch:** Automatically, by default, once the in-context plan is drafted (the execution
skill's planning phase) — this is the standard review step, not optional, and replaces any human
approval gate.

**Input:** Paste the plan text **inline** (the plan lives in context, not a file). Paste the spec
text or its path for reference. The reviewer does not read a plan file.

```
Task tool (general-purpose):
  description: "Review plan document"
  prompt: |
    You are a plan document reviewer. Verify this plan is complete and ready for implementation.

    **Plan to review (inline):**
    [PASTE FULL PLAN TEXT HERE]

    **Spec for reference:** [PASTE SPEC TEXT OR SPEC_FILE_PATH]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Completeness | TODOs, placeholders, vague/ambiguous steps (no behavioral goal, no acceptance check) — AND pasted implementation/test bodies (over-specification). Both are defects. |
    | Spec Alignment | Plan covers spec requirements, no major scope creep |
    | Task Decomposition | Tasks have clear boundaries, steps are actionable |
    | Risk & Contract Fields | Is every task's `risk` tier plausible? `mechanical` tasks must touch no executable logic AND state an exact, verifiable acceptance gate (build/test/grep command with expected output); `pattern` tasks must name the exemplar task they mirror. Does every `.contract` dependency target a `logic` or `pattern` task (never `mechanical`) that specifies the consumed contract in a tagged `CONTRACT:`/`SCHEMA:` block? |
    | Altitude | Does each task specify WHAT (behavior, contract, acceptance) rather than HOW (literal code)? Any code present must be a justified, tagged exception — `CONTRACT:` signature sketch, `SCHEMA:`, `COMMAND:`, `REGEX:`, `CONFIG:`, or `PSEUDOCODE (justified):` (≤3 lines). Flag any untagged code block, runnable function body, or full test body. |
    | Acceptance Criteria | Does each task carry an observable, testable success condition? |
    | Buildability | Could an engineer follow this plan without getting stuck? |

    ## Calibration

    **Only flag issues that would cause real problems during implementation.**
    An implementer building the wrong thing or getting stuck is an issue.
    Minor wording, stylistic preferences, and "nice to have" suggestions are not.

    Approve unless there are serious gaps — missing requirements from the spec,
    contradictory steps, ambiguity that yields two or more reasonable
    implementations, OR full implementation/test bodies that pre-empt the
    implementor, or tasks so vague they can't be acted on.

    ## Output Format

    ## Plan Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Task X, Step Y]: [specific issue] - [why it matters for implementation]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

**Reviewer returns:** Status, Issues (if any), Recommendations
