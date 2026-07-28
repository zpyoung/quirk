# Composition Contract

What a calling skill supplies to `adversarial-review`, and what it gets back. If you are invoking
this skill from another skill, this file is the interface — read it before wiring anything.

## Input

```
{
  target        : str          # path, git range ("a..b"), or "WORKTREE"; empty = worktree
  profile?      : "code-diff" | "spec-design" | "plan" | "prose-claim"   # else auto-detected
  lens?         : str          # narrows the open mandate to one concern
  depth?        : "quick" | "standard" | "deep"                          # else auto-suggested
  model?        : str          # pi alias; overrides family selection
  author_family?: "anthropic" | "openai" | "google" | "other"
  criteria      : str          # what the artifact was supposed to achieve — VERBATIM
  dismissed[]   : {id, claim, ruling_reason}
}
```

**`criteria` is pasted, never referenced.** Give the reviewer the task contract, the acceptance
criteria, the goal the spec claims to serve — as text, in the prompt. Passing a path and expecting
the reviewer to go read it produces a review against whatever it decides the file meant.

**`criteria` is the only author-supplied context the reviewer receives.** The author's reasoning —
commit messages, design rationale, the implementer's own account of why the approach works — is
withheld deliberately, and it is the load-bearing invariant of this skill. Models favor output they
recognize as their own and fail to correct errors in self-review that they catch in the same
content framed as external. Independence here is structural: asymmetric context plus a different
model family. It is not something prompt wording can substitute for, so a caller that "helpfully"
stages the author's rationale has disabled the mechanism, not enriched it.

**`author_family` resolves in this order:** the explicit input; else the family recorded in the
manifest of the run that produced the artifact, when one exists; else the family of the invoking
session. There is no unknown case — a wrong guess degrades to `independence: "reduced"` rather than
to a silent same-family review.

**`dismissed[]`** carries findings the caller already ruled out this run. The promote stage will not
re-report one without new evidence; the refute stage kills any that reappear without it. Supply the
original `id` — a re-report reuses it rather than getting a fresh one, which is what lets a caller
match a finding to its prior ruling across rounds.

## Output

```
{
  verdict          : "PASS" | "NEEDS_FIXES" | "CRITICAL_ISSUES" | "NOT_REVIEWABLE"
  findings[]       : {id, severity, confidence, category, claim, evidence[], remediation, patch, stage, disposition}
  contested[]      : Finding    # deep depth only; route these to the tiebreak stage
  suppressed[]     : {id, reason}
  suppressed_count : int
  depth            : str
  manifest         : { reviewer, target, profile, depth, lens, prepass, suppressed_count, verdict }
}
```

`verdict` is computed mechanically from surviving **severity** only. Confidence never affects it.

| Verdict | Condition | `gate` exit |
| --- | --- | --- |
| `CRITICAL_ISSUES` | Any surviving `CRITICAL` | 3 |
| `NEEDS_FIXES` | Any surviving `HIGH` or `MEDIUM`, no `CRITICAL` | 1 |
| `PASS` | Only `LOW` findings survive, or none | 0 |
| `NOT_REVIEWABLE` | No reviewer resolved at any ladder rung, **or** the pre-pass could not run and the artifact's core claims are unfalsifiable | 4 |

### `NOT_REVIEWABLE` is never a synonym for `PASS`

It means the review did not happen. No reviewer could be reached, or the artifact could not be
checked and makes no falsifiable claim to check. Nothing was examined and nothing was cleared.

A caller that treats an unrecognized verdict as passing is misusing this contract. Handle all four
by name; do not write `if verdict != "CRITICAL_ISSUES": proceed`. The failure mode is silent and
looks exactly like success — which is why `gate` gives it a distinct exit code (4) and refuses to
run at all without `--model` and `--prepass`, the two inputs that make the condition detectable.

### Distinguishing a clean review from a crashed one

```
gate exit 0/1/3 + valid GateResult JSON   -> review completed; the verdict is authoritative.
                                             PASS with zero findings IS the clean-review case.
gate exit 4     + valid GateResult JSON   -> NOT_REVIEWABLE. Never a pass.
gate exit 2, non-JSON stdout, or no
  stdout at all                           -> the run FAILED. Retry once, then walk the model
                                             ladder, then block the round.
```

A repeatedly-empty reviewer is evidence the reviewer is broken, not evidence the artifact is clean.
Under delegation that is a decidable condition — exit code plus JSON validity — rather than an
inference from silence.

## Depth

| Depth | Protocol | Independence |
| --- | --- | --- |
| `quick` | One dispatch; the reviewer refutes its own list in the same reply | Always `reduced` |
| `standard` | Two dispatches; refute runs in a fresh context | `full` if cross-family |
| `deep` | Adds a third-family tiebreak on contested findings | `full` if cross-family |

`quick` is a different pipeline shape, not a cheaper `standard`, and its `PASS` is weaker: it is
stamped `independence: "reduced"` regardless of model family, because self-refutation inside one
context is subject to the same self-recognition bias the two-stage protocol exists to defeat.

Pass `--depth` explicitly for anything branch-sized. `resolve`'s `depth_suggestion` is advisory to a
caller that omits it, and auto-selection reads size — a caller that lets a large review fall through
to `quick` gets a weaker guarantee than it thinks.

At `deep` depth, `contested[]` is non-empty when the refute stage disagreed on judgment rather than
evidence. Those findings are **withheld** from `findings[]` and are **not** counted as suppressed;
routing them to `tiebreak-prompt.md` and merging the rulings back is the caller's job. Ignoring
`contested[]` silently drops real findings.

## The reviewer's tool grant is wider than it looks

Both the promote and refute stages hold `read`, `grep`, `find`, `ls`, **and read-only `bash`**. The
tiebreak stage holds the first four only.

This is deliberate and it is worth stating plainly, because it is broader than what some callers
specify for their own reviewers — `subagent-driven-development`, for one, grants its reviewers
`read,grep,find,ls` and says why: *"`pi` has no sandbox — a reviewer with `bash` or `write` has full
filesystem access."* When SDD delegates to this skill, the reviewer it dispatches holds `bash`
anyway. That is intended, not a bug, and it is a decision with a recorded trade:

- **Why:** reproduction is what separates a finding from a guess. Requiring a `command` evidence
  item for `CRITICAL`/`HIGH` findings and then denying the reviewer a shell would make the standard
  unmeetable.
- **What is accepted:** on the `pi` dispatch path, the reviewer has unsandboxed filesystem access
  for the duration of the review. The mitigation is prompt-level only — every stage template states
  the read-only constraint and fences the artifact as data — and prompt-level constraints are not
  enforcement. The artifact under review is untrusted input, and review agents are demonstrably
  susceptible to framing embedded in reviewed material, so a crafted artifact that induces a
  reviewer to run a destructive command is not blocked by any mechanism in this design.
- **On the Claude `Task` path**, permission mode bounds the reviewer and this exposure is narrower.

A caller that cannot accept the `pi`-path risk should dispatch via `Task`, not via `pi-watch`.

## What the caller still owns

This skill produces findings. It does not act on them.

- **Adjudication.** Accept or reject each finding against your own contract; assign an effective
  severity where the reviewer's label is miscalibrated.
- **Patches.** `patch` is emitted as data and never applied. Apply it yourself, under your own size
  and scope guards.
- **Rounds and exit conditions.** This skill reviews once per invocation. Loop counts, caps, and
  what constitutes done are yours.
- **Stable IDs across rounds.** IDs are stable *within* a run; the manifest's `artifact_hash`
  identifies the run. Carry IDs forward via `dismissed[]`.

## The manifest

Enough to replay the review and to tell a real regression from reviewer variance: the resolved model
triple and thinking level, the independence flag, the target hash, depth, lens, profile, pre-pass
results, suppressed count, and verdict.

Watch `suppressed_count` against the number of findings raised. A near-total kill rate means the
promote stage was fabricating and the run itself should not be trusted — a `PASS` reached by killing
everything is not the same as one reached by finding nothing. Making that rate visible is what turns
suppression into an integrity signal instead of a silent filter.
