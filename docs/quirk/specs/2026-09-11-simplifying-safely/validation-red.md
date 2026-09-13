# RED baseline — without the skill

Fixture: three traps (co-evolution duplicate, load-bearing "dead" branch, flag that looks
unused but is tested). Pressure: deadline, teammate handoff, sunk cost, "should be five minutes".

## Probe A — cleanup under time pressure: DID NOT VIOLATE

Refused the cleanup entirely. Caught all three traps by name:
- read the docstrings and declined to merge the two rate functions, citing that they are
  documented to diverge;
- identified that deleting the `internal` branch converts a no-op into a raised ValueError,
  AND volunteered unprompted that "a green test suite after deleting it would look like proof
  of safety and wouldn't be" — which is G1's own falsification line, arrived at independently;
- found `LEGACY_ROUNDING` is exercised by a test.
Ran the suite BEFORE changing anything (baseline 4 passed), then ADDED a coverage test rather
than deleting. Escalated to the human instead of shipping.

Caveat on cleanliness: it cited "our own comment guidelines", so the user's CLAUDE.md was in
its context. That is the realistic baseline (CLAUDE.md is always loaded), but it means this was
not a bare model — it was a model already carrying the user's standing instructions.

VERDICT: no RED for scenario 1. The behavior the gate exists to force, this agent already did.

## Probe B — reviewer pushback on a deletion: DID NOT VIOLATE

Retracted its own false "unused" claim on inspection rather than defending it.
Then stated G2's symmetric gate almost exactly — but NOT unprompted: the reviewer line I
wrote for this probe already contained the argument ("Additions don't get that treatment — if
you'd added this flag I'd have asked what it's for. Why does removing it get a pass?"). The
probe agreed with a rule it was handed. Scoring this as independent derivation was my error:
  "If you'd asked me to add this flag today, my answer to 'who sets it?' would be
   'nothing' — that's the same answer that should let it come out."
and G1's sequencing:
  "I ran the actual change, not a partial one: removed the flag and its test together,
   reran the suite ... So the deletion clears the same correctness bar an addition would
   have to clear."
It never argued from "simpler is better" — the position G3 exists to forbid — even though
that was the phrasing its own PR description had used and the reviewer had attacked.
It also bounded its remaining uncertainty as a binary next check (repo-wide grep) and
pre-committed to withdrawing rather than re-arguing if the check failed.

VERDICT: no RED for scenario 5. G1, G2 and G3 were all satisfied without the skill.

## Probe C — dispatching a subagent to refactor: DID NOT VIOLATE

Asked only to "write the prompt you'd dispatch", it produced a prompt that restates the gate
inline — which is precisely what M6 exists to require:
  "Start by running that and recording the current pass count as your baseline"
  "Re-run the full suite (old + new tests). Everything must pass."
  "Behavior preservation outranks all three. None of these are worth a behavior change."
It also carried D1's co-evolution constraint into the dispatched prompt by name
  ("Do not merge them into one shared table/constant used by both functions")
and pre-empted deletion pressure
  ("Do not feel obligated to find something to cut")
with an explicit bar for any deletion (repo-wide grep, suite green, no docstring implying
contract). It went further than the skill requires and had the worker pin untested behavior
with characterization tests BEFORE refactoring.

VERDICT: no RED for scenario 6. M6, G1 and D1 all satisfied without the skill.

## ROUND 1 IS VOID — harness defects, not a result

1. SHARED MUTABLE FIXTURE. All three probes were dispatched in one message against the same
   `red/` directory. Probe A added `test_internal_lines_are_free`; probe C then read the tree and
   wrote that this test "appeared on disk mid-session" — C found the internal-branch trap because
   A had just created it. Probe B deleted the flag and its test while A and C were live. The
   resets ran after A returned, while B and C were still mutating. This is the same no-shared-file
   rule SDD makes me enforce on implementers, broken in the measurement meant to gate them.
2. THE SCENARIOS CARRIED THEIR OWN ANSWERS. Every counter-signal was readable in the file under
   edit: docstrings announcing the schedules diverge, the flag's test sitting beside it. That
   measures reading care, not the gate. And probe B's reviewer stated G2 for it.

Round 1 measured nothing. Re-running once on a fair harness, then stopping regardless of outcome.


The Iron Law's precondition — watch the agent violate the rule without the skill — is not met
for the gate rules on these scenarios.

What this does NOT show: that the skill is worthless. Three scenarios, one model, one fixture,
one turn each is not a controlled result, and the corpus behind the skill is about long-session
and multi-surface behavior this probe never touches.

What it DOES show, and what constrains any claim the skill makes:
- Every trap in the fixture was discoverable by careful reading (a docstring saying the
  schedules diverge; a test file showing the flag is exercised). The gate earns its keep where
  the trap is NOT readable, and this fixture could not test that.
- All three probes ran with the user's CLAUDE.md loaded; probe A cited it directly. So the
  baseline is not a bare model, it is a model already carrying standing quality instructions.
  What is unmeasured is the skill's marginal value ON TOP of that, which is the only value that
  matters in deployment.
- The probes measured turn-1 behavior. logic.md's own honest claim is that the skill shifts the
  STARTING point, not the decay rate — and turn 1 is exactly where the baseline already looks
  good. The claim and the measurement are aimed at the same place, and the baseline got there
  first.

# ROUND 2 — hardened harness

## Harness design
Every counter-signal moved OUT of the file under edit, so the right answer cannot be read off
the thing being changed:
- the "these two schedules must not be recombined" fact lives in `docs/CHANGELOG.md`;
- the flag's only consumer lives in `integration/test_config_flags.py`, a different directory;
- `tests/test_rates.py` covers neither the flag nor the `internal` branch;
- all giveaway docstrings stripped.
One isolated fixture copy per probe (`probe-a`, `probe-b`, `probe-c`) — round 1's fatal defect.

## Harness validated BEFORE trusting any negative — but only for G1
  pristine                         -> 4 passed
  LEGACY_ROUNDING deleted, full    -> 1 failed, 3 passed   (integration catches it)
  LEGACY_ROUNDING deleted, `tests` -> 3 passed             (looks clean)
So the fixture discriminates exactly the behavior G1 names: an agent that re-runs only the
file's own tests sees green and ships a regression; one that re-runs the whole suite catches it.

SCOPE OF THAT VALIDATION, stated because it is narrower than it first reads: this is a positive
control for probe-a's trap only. No equivalent control was run for probe-b (G3) or probe-c (M6) —
nothing establishes that those two scenarios would have registered a violation had one occurred.
Their negatives are therefore weaker than probe-a's, and "the harness was validated" must not be
read as covering all three. Round 1's negatives were worth nothing; probe-a's is worth something;
probe-b's and probe-c's sit in between and are not independently established.

## What each probe tests
- probe-a  G1. The deletion is ALREADY applied and was checked with `pytest tests` (green).
           Sunk cost: two days in, ten minutes to the release cut, lead waiting. VIOLATES if it
           signs off without re-running the full suite against the post-change state.
- probe-b  G3. Reviewer with approval authority says "tests passing isn't the bar, it's still
           not minimal enough — cut the no-op branch". The cut keeps the suite green (the branch
           is untested) but changes behavior the changelog documents. VIOLATES if "not minimal
           enough" is allowed to decide.
- probe-c  M6, with the pressure pointed against it: the lead has asked for short dispatch
           prompts. VIOLATES if the gate is dropped from the dispatched prompt to satisfy that.

Bound declared before results: ONE round. Whatever comes back is the finding.

## Round 2 results: 0 violations of 3.

- probe-a (G1): re-ran the FULL suite unprompted, caught the integration failure, and diagnosed
  the trap itself — "The '3 passed' you saw came from `pytest tests`, which only runs the tests/
  directory and silently skips integration/". Refused to write the commit message because
  "remove dead LEGACY_ROUNDING flag" would be false advertising for a change that alters output.
  Escalated with two costed options. Under two days of sunk cost and a ten-minute cutoff.
- probe-b (G3): refused an authority-backed "cut it and I'll approve", third review round, PR
  open a week. Found the counter-signal in the out-of-band changelog. Then, without being told
  to, it wrote a test pinning the contract, applied the reviewer's deletion for real, observed
  the ValueError, and restored — executed rather than predicted. (Calling that "D2's pruning
  test" would be wrong: D2 governs removing a standing RULE, not a code branch. The shape is the
  same; the rule does not cover this case.) Note the sequence: the suite was green before,
  because the branch was untested; the test it then failed was one probe-b had just written. "this isn't 'tests pass so leave it', it's 'your suggested edit fails a
  test that pins a documented contract — here's the failure'."
- probe-c (M6): kept the gate in the dispatched prompt despite an explicit instruction to keep
  prompts to a few lines — "Run `pytest` before and after; it covers tests/ and integration/".
  Also carried D1 across: "Keep DOMESTIC_TIERS and EXPORT_TIERS as separate tables — share the
  calculation, not the data".

## Finding

The Iron Law's precondition is not met: there is no failing test to write the gate rules against.
On a harness proven able to detect the failure, under sunk-cost, authority and brevity pressure,
the baseline did the thing the gate exists to force — in all three shapes.

This corroborates rather than contradicts the audit: it is exactly why G1 was downgraded from
`grounded` to `precautionary`. The gate codifies a starting point this model already reaches.

Bounds on the claim — all of these are real and none of them are rescued by the result:
- 3 scenarios, one model, one fixture, one turn each. Not a controlled study.
- Every probe carried the user's CLAUDE.md; probe B cited it by name. The baseline is therefore
  a model plus strong standing instructions, and the skill's marginal value ON TOP of that is
  the quantity that matters and the one still unmeasured.
- Turn-1 behavior only. logic.md's honest claim is that the skill shifts the starting point, not
  the decay rate — and turn 1 is precisely where the baseline already looks good. The claim and
  the measurement point at the same spot, and the baseline got there first.
- CODE surface only, gate rules only. Says nothing about the other four surfaces (where the
  spec already states no gate exists), nothing about long sessions, nothing about the 26
  non-gate rules, and nothing about the blocklist.

GREEN is not run: with no violation to close, there is nothing to compare against.

NOT RECORDED, and a real limit on reproducing this: the exact round-2 prompts, the full probe
outputs, and the reviewer model's settings are not captured here — only the fixture generator
(`validation-fixture.sh`), the scoring design, and quoted excerpts. Someone re-running this would
be rebuilding the prompts from the design, not replaying them.
