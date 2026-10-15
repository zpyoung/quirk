# Test dimensions

Three test specialists share this file. Their run conditions are defined in
`references/orchestration.md`; Sections A and B run together when the diff includes
test files, Section C runs instead when it doesn't. Section D is a verification
technique all three use.

Section A is the Recharge org test standard, bundled here so the review runs
standalone (see `references/provenance.md`). Sections B–D are sakura's own.

All sections obey the skill's verification gate: no Must/Should fix from the diff
alone — read the source at the correct ref first. Section D is the strongest form of
that gate.

## Section A — Test adequacy  (specialist: `sakura:test-adequacy`)

Runs when the diff includes test files. Assess whether the tests **meaningfully
validate the changed behavior**.

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

Severity: `Must fix` when an untested path carries real correctness risk (money,
auth, data mutation); otherwise `Should fix`.

## Section B — Test quality  (specialist: `sakura:tests`)

Runs when the diff includes test files. Review **only** added/updated test hunks.
Section A owns missing assertions, coverage gaps, flakiness, and
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
   (e.g. a subscription when only a customer is required; seeding N rows when 2
   suffice).
6. **`skip` / `xfail` without a linked ticket + rationale.**
7. **Unjustified slow tests** (> 5s) where heavy setup, not a fixed sleep, is the
   cause. (Fixed sleeps are Section A's flaky-pattern check — don't restate.)
8. **Shared parametrize/fixture data changed out from under other tests.** When
   `parametrize` values or a shared fixture change, check whether other tests still
   need the removed values — and whether a schema, enum, `OneOf`, or DB constraint at
   another layer just lost its only coverage.

## Section C — Missing-test coverage gap  (specialist: `sakura:test-coverage`)

Runs **only** when the diff changes production source files and includes **no**
test files. This is the blind spot Section A cannot see: with no test hunks to
review, nothing checks whether tests should have been added at all.

The context file's `source_files` list is the authoritative set of "production source
files" — a changed code file that is not a test, docs/markdown, config, or a lockfile.
Its companion `test_files` covers Python, JS/TS, Go, Java/Kotlin, and Ruby test
conventions, so don't re-derive either from path patterns. Both are only a coarse gate —
step 3 below is what decides whether a finding is warranted.

1. Identify changed production **behavior** in the diff — new/changed branches,
   error paths, public-API/contract changes. Ignore pure formatting, comments,
   renames with no behavior change, and config/doc edits.
2. For each, check whether an **existing** test already covers it (search the
   repo's test suite at the correct ref). If covered, no finding.
3. Flag only behavior that is genuinely untested **and** warrants a test. Apply
   Section A's guard: do not demand tests unless a real correctness risk warrants
   them. Prioritize risk — money, auth, data mutations, and external-service calls
   first.
4. For each finding, name the specific test to add (layer + scenario), not a
   blanket "add tests."
   - Severity: Should fix for risky paths; Nit for low-risk. Never Must fix on
     coverage alone.

## Section D — Mutation probe  (all three test specialists)

The strongest form of the verification gate for test findings: instead of arguing
from the diff that a test *looks* vacuous or a branch *looks* uncovered, **prove
it** by breaking the production behavior and watching whether a test fails.

- A **surviving mutant** (targeted tests still pass after you break the code) is
  objective proof: for Sections A–B, the test that claimed to cover it is vacuous;
  for Section C, that behavior is genuinely uncovered. → confirmed finding,
  `verified: true`, with the exact mutant as evidence.
- A **killed mutant** (a test fails) proves the behavior *is* protected → drop the
  candidate finding. This kills false positives as much as it confirms real ones.

### When it applies
The probe mutates files, so it is **opt-in: ask the user before the first mutant and
skip it unless they agree.** State what you intend to mutate and where you will run it.
Never probe a shared working tree without that consent. In reviewer seat the coordinator
asks every run and the current source manifest must say `mutation_consent: true`;
absence or false means skip. Consent never carries between runs.

Beyond consent, only when the reviewed code is **locally runnable at `refs.head`** — the
suite executes and you can restore the tree exactly. It does **not** apply to a diff you
can only read at a remote ref. Applicability by source:

- **Isolated checkout (required in reviewer seat).** Use the borrowed reviewer
  source at the exact `refs.head`; do not create or mutate the reviewer's checkout.
  Run probes serially inside it and restore each production file before another
  specialist relies on it. The coordinator tears the source down at the end.
- **Shared working tree (only if no isolated checkout).** Probe only when the tree
  is already at `refs.head` **and** `git status` is clean; run probes **serially**
  (never two mutation probes, and not while a `--local` specialist reads the tree);
  restore after every mutant.
- **Not runnable** (deps missing, suite red at baseline, gitlab MR not checked
  out) → **skip the probe**, fall back to static reasoning, and record
  "mutation probe not run (code not locally runnable)" as an assumption.

### Protocol
1. **Green baseline.** Run the changed test file(s) once with the repo's runner. If
   not green, skip probing (a survival signal is meaningless on a red suite) and
   note it.
2. **Prioritize + cap.** Probe the highest-risk behaviors first — money, auth, data
   mutations, guards, matching/keying, failure-isolation (must-not-retry) paths —
   and cap at ~8 mutants. Record in your returned notes which risky candidates you
   did **not** probe (no silent truncation).
3. **One minimal mutant at a time.** Break exactly the behavior a test claims to
   protect, then re-run **only the targeted test(s)** (not the whole suite):
   flip a comparison (`<= 0` → `== 0`), negate/remove a guard, no-op a branch or an
   early `return`, change a metric name or a low-cardinality dimension value, or
   weaken a composite key (drop a field / its normalization), swap an argument.
4. **Interpret + revert.** Record survive/kill, then **immediately** revert
   (`git checkout -- <file>` or discard the disposable checkout). Mutate **only
   production files, never tests**. Never commit. Leave the tree byte-identical.

### Reporting
A mutation-confirmed finding carries the surviving mutant in `issue` (e.g. "key
mutated to variant-only → all N tests still pass") and is `verified: true`. End the
specialist's notes with a **Surviving mutants** line listing every production
mutation no test caught, plus any risky candidate you could not probe.

**Hard rules:** opt-in; isolated checkout preferred; production-only; targeted
tests only; bounded count; reverted after every mutant; never committed; tree clean
at exit. (This is the *only* place the review touches code, and only transiently —
see SKILL.md "What this skill does NOT do".)
