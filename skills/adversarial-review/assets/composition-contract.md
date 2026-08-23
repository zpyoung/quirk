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
session. A *wrong* guess among the known families degrades to `independence: "reduced"` rather than
to a silent same-family review. An *unrecognized* string is **exit 2**, not a degrade: the whole
independence guarantee is one string comparison, and a family nothing matches would leave the
author's own model in the candidate pool and stamp the result `full`. A caller whose producer is
not one of `anthropic`, `google`, `openai` must pass `other` — naming the gap is the contract, and
guessing a label the script does not know is a usage error.

**The refute seam is mechanical, not prose.** Run `claims` before the refute dispatch and `merge`
after it. `claims` assigns IDs (promote emits `id: null`, but refute keys judgments by ID), holds
`limitation`/`question` records back from a stage that has no mandate over them, and refuses a
finding some stage already ruled on — re-staging one discards the ruling and buys a second refute
round to overturn it. `merge` proves the stage ran: every judgment needs a `reason`, and it fails when a claim went unjudged, when a judgment
names an unknown ID, when one finding draws two rulings, or when tiebreak rules on something nobody
contested. Feed its output to `gate` directly. Each script-produced payload carries a `chain` — run ID,
artifact hash, producing step, and a digest of the input it came from — and every stage refuses
input whose chain does not name its expected predecessor. `prepass` and `select-model` take
`--resolve` for this reason: they are the two inputs the `NOT_REVIEWABLE` branch rests on, and while
they carried no chain either could be swapped for a file from an earlier run — a green pre-pass
saved before the break, or a hand-written `{"resolved": true}` — and neither swap needed forging
anything. `prepass` also records the artifact hash it observed, so `gate` can tell a pre-pass that
ran against other content from one that ran against the artifact under review.

**Every binding above proves the inputs agree with each other, not that they describe the tree as it
stands.** Run IDs are minted at random, so a complete, unmodified bundle from an earlier round — no
forgery, just stale paths — satisfies all of them. `gate` therefore takes `--resolve` and re-hashes
the target, refusing a verdict over an artifact that has moved on; `manifest` does the same, and
both do it by default rather than behind a flag, because an opt-in guarantee is one most callers
never opt into. `--no-verify-artifact` exists for a target with no tree behind it and turns off the
one check that distinguishes this review from a replay of the last one.

This is what covers `quick`, where the reviewer hand-writes its report and no findings chain exists
to anchor — and `quick` is what auto-selection picks for a small diff, not an exotic opt-in.

**Read the guarantee precisely.** The chain makes a skipped stage, an out-of-order call, and a file
from another run fail loudly. It does not authenticate content: nothing in this script observes a
model dispatch, so an orchestrator that fabricates a consistent chain end to end still can. A
verdict means *the deterministic math was applied correctly to the inputs received* — not that the
dispatches happened. Callers that need the stronger claim must supply it themselves, by journalling
each stage's real prompt and raw response for a human to audit.

`manifest` refuses a gate result with a non-empty `contested[]`. Route those to tiebreak, merge the
rulings, and re-run `gate` first; a deep review must not be recorded over an unsettled dispute.

**`model.resolved` must be a JSON boolean** and `triple_verified` tells you whether the returned
provider/model pair was confirmed dispatchable or came from the static ladder.

**Running more than one round?** Read SKILL.md § Running rounds first. Round 1 is discovery;
every round after it is a closure pass over the prior findings, the fix delta, and the seams those
fixes touched — not a fresh discovery pass over a target that just moved. Re-running discovery each
round makes findings-per-round a measure of the reviewer rather than the artifact, and it does not
terminate. Hold the baseline, criteria, profile, lens/scope, and rubric fixed for the campaign;
changing any of them starts a new one.

**`dismissed[]`** carries findings the caller already ruled out this run. The promote stage will not
re-report one without new evidence; the refute stage kills any that reappear without it. Supply the
original `id` — a re-report reuses it rather than getting a fresh one, which is what lets a caller
match a finding to its prior ruling across rounds.

The gate assigns IDs to **every** finding it is given, before dispositions are applied, so entries in
`suppressed[]` and `contested[]` carry real IDs too. Reviewers are told to emit `id: null`; a
dismissal a caller cannot name is a dismissal it cannot carry forward. IDs are assigned in severity
order, so a suppressed finding leaves a gap in the surviving sequence rather than renumbering it.

## Output

```
{
  verdict          : "PASS" | "NEEDS_FIXES" | "CRITICAL_ISSUES" | "NOT_REVIEWABLE"
  findings[]       : {id, severity, adjudicated_severity?, effective_severity, blocking,
                      confidence, category, kind, claim, evidence[], remediation, patch,
                      stage, disposition}
  limitations[]    : Finding    # kind: "limitation" — the protocol could not evaluate it
  questions[]      : Finding    # kind: "question"   — a decision needing its owner
  contested[]      : Finding    # deep depth only; route these to the tiebreak stage
  suppressed[]     : {id, reason}
  suppressed_count : int
  depth            : str
  severity_histogram : {SEVERITY: int}   # by effective severity, survivors only
  blocking_count   : int
  advisory_count   : int
  contested_count  : int        # pending disputes; non-zero means the result is not final
  unreviewed_paths[] : str      # appeared after the artifact was captured; no stage saw them
  regrade_count    : int        # findings a later stage re-graded
  manifest         : { reviewer, target, profile, depth, lens, prepass, verdict,
                       suppressed_count, severity_histogram, blocking_count,
                       advisory_count, regrade_count, limitation_count, question_count }
}
```

`verdict` is computed from the **effective severity of the blocking findings**. Effective severity
is `adjudicated_severity` when a stage that attacked the finding supplied one, else the severity
promote proposed — promote raises candidates at a deliberately low bar, so it proposes rather than
decides.

| Verdict | Condition | `gate` exit |
| --- | --- | --- |
| `CRITICAL_ISSUES` | Any blocking `CRITICAL`, or any pending `contested` `CRITICAL` | 3 |
| `NEEDS_FIXES` | Any blocking `HIGH` or `MEDIUM`, or any pending `contested` finding at all, and no `CRITICAL` | 1 |
| `PASS` | No blocking finding above `LOW` and nothing contested | 0 |
| `NOT_REVIEWABLE` | No reviewer resolved at any ladder rung, **or** the pre-pass could not run and the artifact's core claims are unfalsifiable | 4 |

**A pending contest never yields `PASS`, at any severity.** An unadjudicated finding has no settled
grade — tiebreak may re-grade it in either direction — so `contested[]` escalates on presence rather
than on severity, and `contested_count` is what explains a non-`PASS` verdict sitting beside a
`blocking_count` of zero. Run the tiebreak stage and gate again; the second gate's verdict is the
final one.

A `HIGH` or `MEDIUM` that only the recall stage asserted, at `LOW` confidence, is an **advisory**:
`blocking: false`, reported in `findings[]`, not escalating the verdict. `CRITICAL` is exempt.
Nothing is dropped by that rule — it decides what buys a fix round, not what is reported. So
**`PASS` means no unresolved finding met the blocking bar**, not that the artifact is clean; a
caller rendering it must show `advisory_count`, `limitations[]`, and `questions[]` beside it.

### How the gate scores evidence

Severity is consequence; confidence is likelihood. The evidence gate moves only confidence, and
only where proof is required:

- **verified** — evidence re-resolves and includes a `command` or `prepass` item → unchanged.
- **unverified** — evidence re-resolves, no reproduction → severity unchanged, confidence capped at
  `LOW`, and only for `CRITICAL`/`HIGH`, which is exactly where reproduction is required. A
  high-consequence finding nobody can prove survives as `CRITICAL`/`LOW` rather than being
  downgraded into invisibility.
- **falsified** — *any* evidence item fails to re-resolve → dropped and counted. One true citation
  does not shield a fabricated one beside it; evidence that cannot be checked either way counts as
  holding, so this drops only demonstrable falsehoods.

What "re-resolve" checks, per evidence kind:

| Kind | Checked | Not checked |
| --- | --- | --- |
| `file-line`, `quote` | The file exists, and the quote **begins** within the cited line range | Whether it ends there |
| `absence` | The scope it names exists — a search over a missing file proves nothing | The search is never re-run |
| `command`, `prepass` | — | Never re-run |

A quote may run past the end of its cited range: reviewers routinely cite where a passage starts and
undershoot where it stops, and killing those drops real findings without catching anything a
fabricator would do. A quote that begins *outside* the range is still falsified — that is pointing
at the wrong place, not measuring it short.

**Only a `stage: "prepass"` finding may claim `prepass` evidence.** That kind means the
deterministic layer produced it, which is why it counts as reproduction; a reviewer that can
self-declare it can hold any `CRITICAL`/`HIGH` at full confidence on evidence of its own invention.
A promote-stage finding carrying `prepass` evidence gets the unverified cap.

Every evidence field must be a non-empty string. Presence is not content: an empty `command`/`output`
pair would otherwise satisfy the schema and buy reproduction credit, holding a finding at `HIGH`
confidence on evidence of nothing. A `#fragment` keeps a ref unfalsifiable only when what precedes it
names no file — `spec#3` is a section, `docs/gone.md#x` is a missing file and is falsified.

A cited range is a claim about location, so citing `src.py:400` for a quote that lives at line 12
is falsified even though the quote is real. A ref with no anchor makes no such claim and is matched
against the whole file. **Commands are never re-executed**: running model-supplied shell inside the
one deterministic stage would make it neither deterministic nor safe. That is a deliberate limit —
`command` evidence is trusted as written, which is why it grants reproduction credit but cannot be
falsified here.

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
gate exit 1/3   + contested_count > 0     -> mid-flight, not completed. The tiebreak stage
                                             never ran. Adjudicate; do not spend a fix round.
any exit        + unreviewed_paths nonempty -> the verdict does not cover those files. They
                                             appeared after the artifact was captured, so no
                                             stage saw them. Usually the review's own check
                                             output; when it is real work, `PASS` stopped
                                             short of it and only this says so.
any exit        + advisory_count > 0      -> real findings that no stage beyond promote stood
                                             behind. Reported, not blocking; `PASS` does not
                                             mean they were dismissed.
any exit        + limitations nonempty    -> the protocol could not evaluate these. Not defects
                                             and not clean either — they mark where the review
                                             could not reach.
any exit        + questions nonempty      -> decisions that need their owner. `PASS` means no
                                             finding met the bar, not that these were answered.
gate exit 2     + "artifact changed"      -> the tree moved, or the bundle is left over from
                                             an earlier round. Re-run; do not record.
gate exit 4     + valid GateResult JSON   -> NOT_REVIEWABLE. Never a pass.
gate exit 2, non-JSON stdout, or no
  stdout at all                           -> the run FAILED. Retry once, then walk the model
                                             ladder, then block the round.
```

**The verdict is authoritative over the artifact `resolve` captured, which is not the same as the
tree as it stands.** A `WORKTREE` target fixes its untracked set at capture; anything appearing
afterwards is outside the review by construction, and `unreviewed_paths[]` is the only place that
says so. Check it before reporting a `PASS` as covering everything currently in the tree — the same
obligation as `contested_count`, for the same reason.

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
`contested[]` silently drops real findings — which is why a gate result carrying one is never
`PASS` and never exits 0, and why `manifest` refuses to record it.

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
- **On the Claude `Agent` path**, permission mode bounds the reviewer and this exposure is narrower.

A caller that cannot accept the `pi`-path risk should dispatch via `Agent`, not via `pi-watch`.

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
