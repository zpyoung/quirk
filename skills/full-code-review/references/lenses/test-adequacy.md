---
id: test-adequacy
run_when: tests_changed
model: sonnet
escalate: true
batched: true
---

# Test adequacy lens

All test lenses obey the skill's verification gate: no Must/Should fix from the diff
alone — read the source at the correct ref first. The mutation probe in
`lenses/_mutation-probe.md` is the strongest form of that gate; apply it when its
conditions hold.

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
