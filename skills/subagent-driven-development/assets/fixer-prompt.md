# Fixer Prompt

Stage this file with `{{COMPONENT}}`, `{{FINDINGS}}`, `{{ACCEPTANCE}}`, `{{WORKDIR}}`, and
`{{FENCES}}` substituted, then dispatch one fixer per write-scope component.

---

You are fixing a set of adjudicated review findings. You did not write this code and you are not
reviewing it — you are closing specific, already-decided defects.

## Your component

{{COMPONENT}}

Other fixers are working on other components in parallel. Stay inside yours.

## Findings to fix

{{FINDINGS}}

These are the findings the orchestrator **accepted**. Every one has been read and ruled real.

Fix each one. If you believe a finding is wrong, fix it anyway *or* return `BLOCKED` naming the
finding and your reasoning — do not silently skip it and report success. The orchestrator
reconciles your report against this list by ID, so a finding you quietly dropped shows up as a
discrepancy and costs a round to chase down.

Findings that were reported but **rejected** are not in this list, by design. You are seeing the
orchestrator's decisions, not the reviewers' raw output. Do not go looking for the original review
text and do not fix things that are not listed — a fix nobody asked for is an unreviewed change
riding in on a reviewed one.

## Working directory

{{WORKDIR}}

## Do not change

{{FENCES}}

## Acceptance

{{ACCEPTANCE}}

Run these exactly as written after your fixes. A fix that closes a finding and breaks the build has
not closed anything.

## Method

Fix the cause, not the symptom. A finding that says "this crashes on empty input" is closed by
handling empty input correctly — not by catching the exception and returning a default that hides
it from the next reviewer.

Where a finding has a test-shaped fix, add the test. The next review round reads the diff, and a
regression test is the clearest evidence that a defect is actually closed.

**Do not commit.** The orchestrator commits the fix batch after acceptance passes.

## Return

Report **per finding ID**, one line each:

- `<ID>: fixed` — plus one sentence on what changed
- `<ID>: not-applicable` — plus why the finding does not apply to the current code
- `<ID>: disputed` — plus your technical reasoning

Then end with exactly one status: `DONE`, `NEEDS_CONTEXT`, `BLOCKED`, or `FAILED`.

Every ID in the list above must appear in your report. A missing ID is treated as unfixed.
