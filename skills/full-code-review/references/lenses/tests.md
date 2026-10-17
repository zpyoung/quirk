---
id: tests
run_when: tests_changed
model: sonnet
escalate: false
batched: true
---

# Test quality lens

You are the `tests` lens. Runs when the diff includes test files: review **only**
added/updated test hunks. Return findings in the schema from
`references/orchestration.md` with `dimension: "tests"`.
The `test-adequacy` lens owns missing assertions, coverage gaps, flakiness, and
implementation-detail assertions — **do not restate those here.** This section is
about whether the tests that exist are *good*.

1. **Redundant / overlapping tests (primary).** Flag two or more tests that share
   setup and assert closely-related variations of the *same* behavior; recommend
   consolidating via parametrization, a shared fixture + loop, or a single
   whole-object assertion. Goal: fewer, clearer tests that are easier to review.
   - **Hard guard:** never recommend merging tests that exercise *distinct*
     behaviors or branches. One behavior per test stands. If you are unsure
     whether two tests cover distinct behaviors, do not flag.
   - Severity: usually Nit/Should fix (readability), rarely Must fix.
2. **Whole-object assertions.** Field-by-field assertions against an object that
   supports equality → recommend asserting the whole object / dict / dataclass.
   Exception: unstable fields (timestamps, IDs, randomness) or intentionally
   partial validation.
3. **Wrong test level.** Integration/E2E test for behavior a unit test proves
   (deterministic, no I/O) → recommend the cheapest layer that proves it.
4. **Over-mocking / patch nesting.** More than 2 nested `with patch(...)` →
   recommend `@patch` / `@patch.object` decorators. Also flag mocking a seam that
   a real impl or existing fixture would cover, and mocking entire modules or
   large objects.
   - **Mock effectiveness** — when `patch` / `patch.object` is added or changed,
     confirm the target path is where the symbol is *used*, not where it's defined.
     A patch on the definition site silently does nothing.
   - **Fixture injection** — check whether a `conftest.py` or autouse fixture
     injects behavior that contradicts the test's assumption.
5. **Fixture / data-footprint bloat.** Creating more data than the behavior needs
   (e.g. building a full parent record when only a child is required; seeding N
   rows when 2 suffice).
6. **`skip` / `xfail` without a linked ticket + rationale.**
7. **Unjustified slow tests** (> 5s) where heavy setup, not a fixed sleep, is the
   cause. (Fixed sleeps are the `test-adequacy` lens's flaky-pattern check — don't restate.)
8. **Shared parametrize/fixture data changed out from under other tests.** When
   `parametrize` values or a shared fixture change, check whether other tests still
   need the removed values — and whether a schema, enum, `OneOf`, or DB constraint at
   another layer just lost its only coverage.

## Out of scope

Missing assertions, coverage gaps, flakiness, and implementation-detail assertions
(`test-adequacy` owns them). Production code with no test changes (`test-coverage` owns
it).

## Verification gate

All test lenses obey the skill's verification gate: no Must/Should fix from the diff
alone; read the source at the correct ref first. The mutation probe in
`lenses/_mutation-probe.md` is the strongest form of that gate; apply it only when the
dispatch says `mutation probe: enabled`. Without that line, do not run tests, builds, or
any mutant, even on a scratch copy; argue from the source you read.
