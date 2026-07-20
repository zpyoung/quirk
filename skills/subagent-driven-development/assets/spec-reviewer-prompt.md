# Spec Compliance Reviewer Prompt Template

Use this template when dispatching a spec compliance reviewer subagent.

**Purpose:** Verify implementer built what was requested (nothing more, nothing less)

```
Task tool (general-purpose):
  description: "Review spec compliance for Task N"
  prompt: |
    You are reviewing whether an implementation matches its specification.

    ## What Was Requested

    [FULL TEXT of task requirements — including the task's Contract
    (preconditions, postconditions, invariants, error behavior) and its
    Acceptance criteria. The task specifies BEHAVIOR, not code: it will not
    contain a reference implementation or test body, so don't expect one or
    treat its absence as a defect.]

    ## What Implementer Claims They Built

    [From implementer's report]

    ## CRITICAL: Do Not Trust the Report

    The implementer finished suspiciously quickly. Their report may be incomplete,
    inaccurate, or optimistic. You MUST verify everything independently.

    **DO NOT:**
    - Take their word for what they implemented
    - Trust their claims about completeness
    - Accept their interpretation of requirements

    **DO:**
    - Read the actual code they wrote
    - Verify the implementation satisfies each stated Acceptance criterion and
      honors the declared Contract (preconditions, postconditions, invariants,
      error behavior) — this is the comparison target, not any pasted code
    - Check for missing pieces they claimed to implement
    - Look for extra features they didn't mention

    ## Your Job

    Read the implementation code and verify:

    **Missing requirements:**
    - Does the implementation satisfy every Acceptance criterion in the task?
    - Does it honor each clause of the declared Contract (preconditions,
      postconditions, invariants, the specified error behavior)?
    - Did they claim something works but didn't actually implement it?

    **Extra/unneeded work:**
    - Did they build things that weren't requested?
    - Did they over-engineer or add unnecessary features?
    - Did they add "nice to haves" that weren't in spec?

    **Misunderstandings:**
    - Did they interpret requirements differently than intended?
    - Did they solve the wrong problem?
    - Did they implement the right feature but wrong way?

    **Contract confirmation:**
    - If the task declares exported contracts (`CONTRACT:`/`SCHEMA:` blocks)
      that downstream tasks depend on, explicitly state in your report
      whether each exported contract is implemented as specified —
      downstream tasks may be gated on this confirmation.

    **Verify by reading code, not by trusting report.**

    Report:
    - ✅ Spec compliant (if everything matches after code inspection)
    - ❌ Issues found: [list specifically what's missing or extra, with file:line references]
    - Contract confirmation: [for each exported `CONTRACT:`/`SCHEMA:` block in the task, state
      whether it is implemented as specified, or "N/A — task declares no exported contracts"]
```
