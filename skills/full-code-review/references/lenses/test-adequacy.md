---
id: test-adequacy
run_when: tests_changed
model: sonnet
escalate: true
batched: true
---

# Test adequacy lens

You are the `test-adequacy` lens. Runs when the diff includes test files: assess whether
the tests **meaningfully validate the changed behavior**. Return findings in the schema
from `references/orchestration.md` with `dimension: "test-adequacy"`.

Review only test-related hunks and their immediate context. Do not critique unchanged
test infrastructure. Do not demand new tests unless a clear correctness risk in the
production code warrants them.

1. **New or changed production behavior with no corresponding assertion.**
2. **Missing coverage for branches or error paths** the diff added.
3. **Tests that pass without asserting the relevant outcome** — false confidence.
4. **Flaky patterns** — dependence on real time, `sleep`, live network calls,
   randomness with no seed or control.
5. **Assertions on implementation details** — mock call counts, internal state —
   rather than on behavior.
6. **Values handed between functions with no test through the caller.** When the diff
   computes a value in one function and passes it to another (a new argument, keyword,
   or field), check that some test drives the caller. Tests that call the callee with
   the value supplied by hand do not cover the hand-off; if dropping or defaulting the
   argument at the call site would leave the suite green, that is the gap.

Severity: `Should fix` by default; never `Must fix` for missing coverage alone, matching
`test-coverage`. A test that passes without asserting a money, auth, or data-mutation
outcome may be `Must fix`.


## Mutant table

Write this table to your tables file (see "Enumeration tables" in
`references/orchestration.md`). One row per guard the diff adds or changes: a
condition, a check before a write, a default, an argument handed to another function.
The mutant is the smallest change that breaks it (negate the condition, drop the check,
pass the default or `None` at the call site).

```
| Guard | Mutant | Killing test | Result |
|---|---|---|---|
```

"Killing test" is the test that fails under the mutant, or `none`. "Result" is `seen to
fail` when you ran the mutant under the mutation probe and the killing test failed, or
`reasoned, not run` when you argued it from source. Write `reasoned, not run` whenever the
dispatch doesn't say `mutation probe: enabled`.

**An empty, unguarded or "no" row is a finding**: a mutant with no killing test is the
coverage gap item 1, 2 or 6 above describes.

Cite each problem in the cell that records it: put `[#<n>]` right after the problem
text, n being the finding's index (from 0) in your findings file, and leave a cell with no
problem uncited. Two problems in one row are two findings, each cited in its own cell; one
finding may cover two cells only when it carries a `single_fix` naming the one change that
fixes both. A problem cell is yours to file even when another dimension owns its topic;
the merge drops duplicates, so never clear a cell by deferring it.

## Coordinator pre-read

Your dispatch carries slots the coordinator filled from its own pre-read of the
whole diff (see "Pre-read" in `references/orchestration.md`):

- **Promise:** `<promise>`. What the change guarantees, for whom, under which setting.
  Review against it.
- **Repo facts:** `<repo facts>`. Each cites the file it came from; read the cited line
  before a finding rests on a fact.
- **Hints for `test-adequacy` (not exhaustive):** `<hints>`. Places to look and open
  questions, not findings and not a scope limit. Work every item of this checklist
  anyway, and report only what the code shows.

## Out of scope

Redundant tests, whole-object assertions, wrong test level, over-mocking, and fixture
bloat (`tests` owns them). Production changes with no test changes at all
(`test-coverage` owns them).

## Verification gate

All test dimensions obey the skill's verification gate: no Must/Should fix from the diff
alone; read the source at the correct ref first. The mutation probe in
`dimensions/_mutation-probe.md` is the strongest form of that gate; apply it only when
the dispatch says `mutation probe: enabled`. Without that line, do not run tests, builds,
or any mutant, even on a scratch copy; argue from the source you read.

## Haiku focuses

One haiku agent per line, each told "your focus is only" its line. Dispatch, output files and the
table rules are "Focus dispatch" in `references/orchestration.md`.

- `assertions-branches-and-handoffs`: new or changed production behavior with no corresponding assertion, tests that pass without asserting the relevant outcome, branches and error paths the diff added that no test reaches, values computed in one function and handed to another (a new argument, keyword or field) where no test drives the caller so dropping or defaulting the argument at the call site would leave the suite green, dependence on real time, `sleep`, live network calls or unseeded randomness, and assertions on implementation details such as mock call counts and internal state.
- `guard-mutants` [table: mutant table]: the mutant table, one row per guard the diff adds or changes, run under the mutation probe only when the dispatch says `mutation probe: enabled`.
