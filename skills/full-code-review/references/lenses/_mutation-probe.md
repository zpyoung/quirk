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
The probe mutates files, so it is **opt-in: run it only when the dispatch says
`mutation probe: enabled`, which the coordinator sets after the user agrees.** Without
that line, never run the tests, a build, or a mutant, even on a scratch copy. State what
you intend to mutate and where you will run it. Never probe a shared working tree
without that consent. In reviewer seat the coordinator
asks every run and the current source manifest must say `mutation_consent: true`;
absence or false means skip. Consent never carries between runs.

The probe runs the change's own code, so it is refused for forks and untrusted authors:
`borrow_review_source.py` records `mutation_consent: false` unless `change.is_fork` is
`false` and `change.author_trusted` is `true`. On GitLab `author_trusted` is always null,
so the probe is never offered there. Run the test command with a minimal environment
(`env -i PATH="$PATH" HOME="$(mktemp -d)" <runner>`, plus only the variables the suite
needs) so forge tokens and other credentials in your shell never reach the change's code.

Beyond consent, only when the reviewed code is **locally runnable at `refs.head`** — the
suite executes and you can restore the tree exactly. It does **not** apply to a diff you
can only read at a remote ref.

Lenses run in parallel against one source root, so **never mutate the shared source root
or the reviewer's checkout.** Each probing lens creates its own disposable copy at the exact
`refs.head` (`git -C <source root> worktree add --detach <temp dir> <refs.head>`, or a plain
copy of the tree), runs every mutant and test command inside that copy, and removes it
before returning. In `--local` mode use a plain copy of the working tree so the
uncommitted changes under review are included.

- **Not runnable** (deps missing, suite red at baseline, no copy can be made, or a remote
  change that is not checked out) → **skip the probe**, fall back to static reasoning, and
  record "mutation probe not run (code not locally runnable)" as an assumption.

### Protocol
1. **Green baseline.** Run the changed test file(s) once with the repo's runner. If
   not green, skip probing (a survival signal is meaningless on a red suite) and
   note it.
2. **Prioritize + cap.** Probe the highest-risk behaviors first — money, auth, data
   mutations, guards, matching/keying, failure-isolation (must-not-retry) paths —
   and cap at ~8 mutants. Record in your returned notes which risky candidates you
   did **not** probe (no silent truncation).
3. **One minimal mutant at a time.** Save the file's bytes (`cp <file> <file>.orig`
   inside the copy) before mutating. Break exactly the behavior a test claims to
   protect, then re-run **only the targeted test(s)** (not the whole suite) under a hard
   timeout (for example `timeout 120`); a timeout counts as a killed mutant, and the file
   is reverted before anything else runs:
   flip a comparison (`<= 0` → `== 0`), negate/remove a guard, no-op a branch or an
   early `return`, change a metric name or a low-cardinality dimension value, or
   weaken a composite key (drop a field / its normalization), swap an argument.
4. **Interpret + revert.** Record survive/kill, then **immediately** restore the saved
   bytes (`mv <file>.orig <file>` inside the copy). Never revert with `git checkout`:
   in `--local` mode the copy holds uncommitted changes that a checkout would replace with
   the committed content. Mutate **only production files, never tests**. Never commit.
   Capture `git status --porcelain` in the source root before the probe starts. Before
   ending, including when the probe aborts, remove the copy and confirm the source root's
   `git status --porcelain` output is identical to what was captured.

### Reporting
A mutation-confirmed finding carries the surviving mutant in `issue` (e.g. "key
mutated to variant-only → all N tests still pass") and is `verified: true`. End the
specialist's notes with a **Surviving mutants** line listing every production
mutation no test caught, plus any risky candidate you could not probe.

**Hard rules:** opt-in; private disposable copy only; production-only; targeted
tests only; bounded count; restored after every mutant; never committed; source tree
unchanged at exit. (This is the *only* place the review touches code, and only transiently —
see the Boundaries section of SKILL.md.)
