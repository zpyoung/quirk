# Mutation probe (shared by the three test lenses)

The strongest form of the verification gate for test findings: instead of arguing
from the diff that a test *looks* vacuous or a branch *looks* uncovered, **prove
it** by breaking the production behavior and watching whether a test fails.

- A **surviving mutant** (targeted tests still pass after you break the code) is
  objective proof: for the `test-adequacy` and `tests` lenses, the test that claimed to cover it is
  vacuous; for `test-coverage`, that behavior is genuinely uncovered. → confirmed finding,
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
- **Not runnable** (deps missing, suite red at baseline, or a remote change that is
  not checked out) → **skip the probe**, fall back to static reasoning, and record
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
see the Boundaries section of SKILL.md.)
