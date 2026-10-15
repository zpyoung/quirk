---
id: test-coverage
run_when: source_without_tests
model: sonnet
escalate: false
batched: true
---

# Missing-test coverage lens

All test lenses obey the skill's verification gate: no Must/Should fix from the diff
alone — read the source at the correct ref first. The mutation probe in
`lenses/_mutation-probe.md` is the strongest form of that gate; apply it when its
conditions hold.

Runs **only** when the diff changes production source files and includes **no**
test files. This is the blind spot the `test-adequacy` lens cannot see: with no test hunks to
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
   the `test-adequacy` lens's guard: do not demand tests unless a real correctness risk warrants
   them. Prioritize risk — money, auth, data mutations, and external-service calls
   first.
4. For each finding, name the specific test to add (layer + scenario), not a
   blanket "add tests."
   - Severity: Should fix for risky paths; Nit for low-risk. Never Must fix on
     coverage alone.
