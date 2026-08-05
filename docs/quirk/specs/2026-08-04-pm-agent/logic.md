# pm-agent — Logic Spec

## Purpose

A quirk module that answers two questions about a project's typed artifacts: **what should we work
on next**, and **is the thing we started actually finished**.

It exists because quirk's typed artifacts are an append-only queue with no consumer. Entries go in
and nothing takes them out, nothing reports depth, and nothing distinguishes an entry that was
resolved from one that was merely filed. The existing design spec already rates artifact rot as
*likelihood High*; this module is the consumer that rating implies.

Its first version covers the roadmap artifact, the ready-set computation with unplaced-work intake,
the task lifecycle with baselined verification, the handoff that dispatches a task to a fresh
session — often a new worktree, sometimes a different project — and the read layer that replaces
the SessionStart tail. Provenance stamping and duplicate detection are deferred.

## Conceptual model

**A ledger, a plan, and a join — with no fact stored twice.**

Three layers, each owning exactly one thing:

**Ledger** — the four typed artifact files (`BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`,
`proposals.md`). The append-only record of what was observed. An entry's *text* lives here and
nowhere else.

**Plan** — `ROADMAP.md`. Ordered milestones, each naming entry IDs. An entry's *position* lives
here and nowhere else.

**Operations** — `bin/pm.py`. Pure functions that join ledger and plan. Owns no state.

The ledger says what exists. The plan says what matters. Operations joins them at query time.
Because no fact is stored in two places, no two places can disagree — the property whose absence
sank the derived-`.quirk/`-state proposal during review, and which beads documents as a live
hazard in its own sync model (JSONL import is upsert-only and cannot represent a deletion).

The **PM agent** is the skill that drives operations and talks to the user. It never writes code
and never edits an entry's substance.

### The PM dispatches; it does not implement

Starting a task is usually a **handoff**, not a local state change. The implementing work happens
in a fresh session — commonly a new worktree, sometimes in a different project entirely — and the
PM's job is to get that session started with enough context to finish and to report back.

This does not soften the shepherd boundary; it sharpens it. The PM selects work, sets the bar,
launches the worker, and checks the result. It still never writes code. The thing that judges "is
this done" remains distinct from the thing that did it — and after a handoff they are not even the
same session.

Distinguish this from the **PM subagent that was rejected**. That proposal was an agent that
*grooms the backlog* — re-rating, deduping, sweeping — for which no working instance exists
anywhere in the research corpus. Dispatching an implementer to do work a human selected is a
different operation with a different risk profile, and the rejection does not reach it.

Three properties make the handoff survivable:

**The packet is a file, not a prompt.** Everything the worker needs is written into the
destination worktree as markdown, and the launch prompt merely points at it. Compaction — not
session boundaries — is what practitioners report actually destroys plan adherence, and a file
survives compaction while an opening prompt does not.

**The ledger stays singular.** When work is dispatched to another project, there is still exactly
one ledger: the origin's. The packet records its absolute path and the worker writes back with
`--project-dir`. Mirroring the entry into the destination repo was considered and rejected for the
same reason as every other second-copy proposal.

**The launcher is pluggable.** `pm.py` always writes the packet and prints the launch prompt. An
optional adapter drives a real launcher when one is present. This keeps the core stdlib-only and
cleanly inert, which is the same standard applied when integrating beads was rejected for
requiring an external binary — a rule that would be incoherent if broken here.

### The division of labor is the whole design

Two research findings pull in opposite directions and together determine where every decision
lands:

1. LLM judges violate transitivity — A>B, B>C, C>A — at material rates, with no mitigation that
   eliminates it. Any agent-computed *total ordering* of a backlog is unstable by construction.
   This argues for putting ordering in code.
2. LLM story-point studies find Spearman correlation consistently exceeds Pearson (ρ≈0.38–0.45 on
   absolute sizing). Models **rank** work meaningfully better than they **size** it, and relative
   judgment over a short list is their strength. This argues against putting *all* judgment in code.

The resolution: **code computes the ready-set and its order; the model argues for one candidate
within a short slice of it.** The model may advocate against the sort — but it must say why, and
it never rewrites the sort.

The same split governs job 2. Deciding whether work is done is a verification problem, and
self-authored verification is empirically unreliable: one 2026 study found 15 of 35 model-game
cells finishing with self-scores ≥0.70 while scoring *below a random baseline* on held-out
deployment. So the judgment of "done" is moved out of the model and into a probe whose bar was set
before the model had any interest in where the bar sat.

### The red→green baseline

The mechanism at the center of job 2.

At `start`, a probe is supplied and **run immediately**. It must **fail**. A probe that already
passes does not discriminate the entry, so a later pass would prove nothing — `start` refuses it.
The failing result is written into the entry as a baseline.

At `finish`, the same probe is re-run and must now **pass**.

This is hard to game honestly. Deleting the test does not help: `finish` can no longer run the
probe, so it refuses. The bar is fixed while the agent still has an interest in it being real —
which is what distinguishes this from every evidence scheme that checks a condition only at
closing time.

The verb set is **closed**. The script owns the verbs; the agent supplies only arguments. This is
not incidental: an allowlisted script that executes an agent-chosen command string is an
unsandboxed bypass of the Bash permission surface, which is why the arbitrary-probe variant was
rejected.

| Kind | Mechanism | Strength |
|---|---|---|
| `test:<nodeid>` | red→green transition | strongest |
| `grep:<pattern>` | baselined match-count decrease | strong |
| `commit:<sha>` | `git cat-file -e` | audit trail only — forgeable |
| `none` | explicitly unverified | honest; reported by `--doctor` |

`commit:` is deliberately labelled as audit trail rather than verification.
`git commit --allow-empty -m "Closes: BUG-1"` produces a SHA that passes `git cat-file -e`; the
check refuses a *random* SHA, not a *manufactured* one. Most `DEFER` and `PROPOSAL` entries will
close as `none`. The value is the label, not the coverage.

## Data flow

### Job 1 — roadmap and what's next

Bootstrapping a project that already has entries:

```
/quirk:pm:roadmap
  → pm.py reads all open entries
  → skill proposes a milestone grouping with IDs assigned
  → diff shown to user
  → written to ROADMAP.md only on approval
```

Answering what's next:

```
/quirk:pm:next
  → pm.py computes, in Python:
      ready(e)     := status is open AND every blocker is not-open
      unplaced(e)  := ready(e) AND e is in no milestone
      eligible(e)  := ready(e) AND (e is in a milestone OR urgency(e) <= 1)
      sort key     := (milestone rank, urgency, age) — ascending, ascending, oldest first
      take         := top 5
  → skill reports the unplaced count ALWAYS
  → if unplaced > 0, skill offers to place them (declining is fine)
  → skill presents the 5 and recommends 1 with rationale
```

**Intake is reported unconditionally and actioned optionally.** The unplaced count prints on every
`--next`, whether or not you act on it, because medium- and low-urgency work in no milestone is
otherwise invisible to the entire system — it is not eligible for the shortlist and it is not in
the plan. That is the design's own criticism of the append-only queue, reproduced inside the
feature meant to fix it. Reporting it always closes that hole; making placement optional keeps
"what's next" from turning into a mandatory planning session, which is the version that gets
routed around.

Placement itself goes through the ratification gate like any other roadmap write.

**Urgency is one scale across both vocabularies.** `BUGS.md` uses `Severity`
(critical/high/medium/low); `DEFERRED.md` and `TEST_BACKLOG.md` use `Priority` (P1–P4). They are
mapped onto a single integer so entries of different types are comparable:

| Urgency | Severity | Priority |
|---:|---|---|
| 0 | critical | P1 |
| 1 | high | P2 |
| 2 | medium | P3 |
| 3 | low | P4 |

An entry with neither field, or an unrecognized value, gets urgency 2 — the middle — so a
malformed entry is neither promoted nor buried. `proposals.md` entries have no urgency field and
are never eligible for `--next`; they are decisions awaiting a human, not work.

**Milestone rank for the escape hatch.** An eligible entry that belongs to no milestone sorts
*before* every milestone, not after. It only reached eligibility by being critical or high, and
burying it behind the whole plan would defeat the escape hatch. Concretely: un-roadmapped entries
take milestone rank `-1`.

Age sorts last but is present deliberately: it counteracts the recency bias measured in the
current SessionStart tail, where the entries dropped from view were the oldest and longest-open.

When the ready-set is empty, `--next` explains **why** rather than printing nothing — which
blockers are open, and what would unblock the most work. A dependency graph that cannot answer
"why is nothing ready" is worse than no graph; beads arrived at the same conclusion and added
`--explain`.

Readiness uses **direct blockers only**. A closed blocker's own blockers cannot matter, so
transitivity falls out for free and there is no graph walk in the read path.

### Job 2 — ushering a started task

```
/quirk:pm:start BUG-7 --probe test:tests/test_auth.py::test_safari [--repo <selector>]
  1. resolve target        → new child worktree of the current repo by default
  2. create the worktree   → adapter, or plain `git worktree add`
  3. run the probe THERE   → must FAIL; if it passes, refuse and do not dispatch
  4. write the origin ledger:
       - **Status**:  in_progress — 2026-08-05 — probe: test:… — baseline: fail
       - **Handoff**: quirk @ pm/bug-7 — /Users/…/worktrees/bug-7
  5. write the packet into the destination worktree
  6. launch the worker with a prompt pointing at the packet

  … the worker implements; the PM is not in the loop …

/quirk:pm:finish BUG-7 --project-dir <origin>     # run BY THE WORKER, in the worktree
  → probe re-runs in the CWD (where the code is)
  → ledger write goes to --project-dir (where the truth is)
  → must PASS, else refuse and leave in_progress
  → entry becomes:
    - **Status**: closed — 2026-08-05 — probe: test:… — baseline: fail → pass
  → adapter, if present, signals the PM session: outcome=succeeded
```

**Both terminal transitions signal; a refusal does not.** `finish` signals `succeeded` and `park`
signals `failed`. A `finish` that refuses because the probe still fails signals nothing — the task
is not terminal, the worker is presumably still on it, and a notification per failed attempt is
how a channel becomes noise that gets muted. `park` signalling matters more than `finish` does:
the PM most needs to hear the case where the worker gave up, and that is the case least likely to
be reported any other way.

**The probe runs at the destination, the write lands at the origin.** These are different
directories and the split is deliberate: a probe is only meaningful against the code being
changed, while the ledger must stay singular. `artifact_append.py` already accepts
`--project-dir`, so the write half of this works today.

**Refusal happens before the worker is launched.** If the probe passes at step 3, the entry does
not move to `in_progress` and no agent is started — dispatching a worker against a bar that is
already met is how a task gets "completed" without anything happening. The created worktree is
left in place rather than silently removed, because a probe that unexpectedly passes is evidence
worth inspecting.

`park` is the honest exit. Without it, the only ways out of `in_progress` are closing it and lying.

**Starting without a probe is explicit, never implicit.** Omitting `--probe` is an error, not a
default — `start` refuses and names the available verbs. Choosing to work unverified requires
typing `--probe none`, so the choice appears in the shell history and in the entry. An entry
started `none` closes `none`; `finish` does not ask for a probe after the fact, because a probe
supplied at closing time has no baseline and would prove nothing.

**Stall threshold is 7 days**, overridable via `QUIRK_PM_STALL_DAYS`. Seven days is a working
default, not a measured one — it is short enough to catch an abandoned task within a normal week
and long enough not to flag ordinary multi-day work.

### The handoff packet

Written to `.quirk/handoff/<ID>.md` in the destination worktree. Its job is to make the worker
able to finish *and* aware that finishing includes writing back.

It carries:

- **The task** — ID, full entry text copied verbatim from the ledger, and the milestone it serves.
- **The bar** — the probe verb and argument, its recorded baseline, and the literal `finish`
  command to run.
- **The ledger address** — the absolute path to the origin project, and the explicit statement
  that the ledger is *there*, not here.
- **The return address** — the run and dispatch IDs, when the handoff was made under an
  orchestrator. Recorded so the completion signal can be addressed even when `finish` runs outside
  the dispatched terminal. Absent for an unadapted handoff, which is fine.
- **The write-back contract** — three obligations, stated as instructions rather than prose:
  1. When the probe passes, run `finish` against the origin ledger.
  2. If you cannot finish, run `park` with a reason. Do not leave it `in_progress`.
  3. Any *new* observation you make — a bug you noticed, a test you skipped — is filed to the
     **origin** ledger with `--project-dir`, not to the destination project.

The third obligation is the one most likely to be missed and the most costly to miss. A worker
dispatched into another repo will otherwise file its observations into that repo's ledger, or into
nothing at all, and the origin's record of the work silently loses everything discovered during it.

**Guidance rides in the tool output, not only in the packet.** Every `pm.py` invocation inside a
dispatched worktree prints the write-back contract as part of its own stdout. This is a direct
response to the most common documented failure of markdown task systems — the agent forgets to
update the task file after completing work — and to the repeated finding that instructions in a
static file decay within a session while tool responses are read every time.

### The adapter contract

`pm.py` never talks to a launcher directly. An adapter is anything that can satisfy three calls:

| Call | Must do | Fallback when no adapter |
|---|---|---|
| `create_worktree(repo, branch)` | Produce a path | `git worktree add` |
| `launch(path, prompt)` | Start an agent session there | print the prompt, exit 0 |
| `signal_done(task, outcome)` | Notify the dispatching session; `outcome ∈ {succeeded, failed}` | no-op — the ledger is the record |

With no adapter present, `start` still creates the worktree, still runs the probe, still writes the
packet and the ledger, and prints the prompt for you to paste. Nothing about the verification
contract depends on the launcher.

**The orca adapter** maps onto existing primitives with little glue: `orchestration task-create`
then `worker-start --task <id> --worktree new-child --agent claude --repo <selector>` covers the
first two calls, and `orchestration send --type worker_done --outcome succeeded|failed --task-id
<id>` covers the third.

**Addressing the signal needs care.** `worker_done` is an *exact-Dispatch* signal: omitting the
recipient falls back to the owning Run mailbox only **from an active Dispatch**. A worker launched
via `worker-start` satisfies that, but the same `finish` run from a terminal you opened yourself in
that worktree does not — there is no Dispatch to inherit from. So the packet records the run and
dispatch IDs at handoff, and `signal_done` resolves a recipient in this order:

1. The ambient Dispatch context, when `orchestration run-current` reports a binding.
2. The run/dispatch ID recorded in the packet.
3. Neither — skip the signal.

Step 3 is a normal outcome, not an error. It is what happens with no adapter, outside orca, or in a
worktree whose Run has since been reset, and it costs nothing because the ledger already holds the
result.

The completion signal is **additive, never authoritative**. The ledger write is what makes a task
closed; the signal only makes the PM session notice sooner. If the signal is lost, the state is
still correct and the next `--next` or `--status` picks it up.

### The read layer

`hooks/load_artifact_tail.sh` stops tailing and calls `pm.py --index`. The index carries open /
in_progress / stalled counts **with a denominator**, the current in-progress task, and the closed
count plus closure-evidence mix.

That last item is a deliberate mitigation of this design's own biggest risk. Adding a close
operation means `BUGS.md` can fill with `Status: closed`, the index shrinks, `--next` returns a
short tidy list, and every surface reports a healthy backlog — the "queue with no consumer looks
like it is working" failure reconstituted one level up, and *harder* to see than today, because
today's undifferentiated pile at least looks like a pile. Keeping closed counts and evidence mix
in the header does not prevent this. It makes it legible, which is the most this design can
honestly claim.

## Key decisions & rationale

**The roadmap references IDs rather than restating work.** A roadmap written in its own words is a
second copy of the truth with nothing reconciling it. Referencing IDs keeps `ROADMAP.md` a pure
grouping-and-ordering layer, so a roadmap edit can never contradict an entry.

**Milestones are ordered and carry no dates.** Order is cheap to keep true; dates rot on contact.
Dates would also require sizing, which is the operation the research measures models as weakest at.

**Linkage lives in the roadmap, not on the entry.** A `Milestone:` field on each entry would read
better in isolation, but it means mutating existing entries in place — breaking quirk's append-only
guarantee and multiplying the surface where two worktrees conflict on one line. One file changes
for roadmap changes.

**Critical and high severity may bypass the roadmap.** Roadmap discipline should not be able to
hide a production bug behind planning ceremony.

**The agent may close entries unattended, and `--doctor` flags self-authored evidence.** Requiring
human confirmation on the highest-frequency operation is where approval fatigue sets in and
rubber-stamping starts. Since the gate is forgeable regardless, effort is spent on visibility
rather than on a gate that would be theater.

**The agent never writes code.** The thing that judges "is this done" must not be the thing that
wants it to be done. This is the cleanest available separation, and it is free — implementation is
already well served by the user's normal session and skills. Dispatch strengthens rather than
weakens it: after a handoff, the judge and the implementer are not even the same session.

**Stalls stay visible and never age out.** Auto-expiry was proposed and rejected: making old
entries disappear to reduce context cost is precisely the tail-50 defect being fixed, reintroduced
with a timer instead of a byte count.

**`bin/artifact_lib.py` is extracted before any feature lands.** The entry-heading regex is already
duplicated across `artifact_append.py:90` and `artifact_review.py:20`, and the copies have already
diverged — append's does not capture the title, review's requires one. Job 1 and job 2 must agree
on what "open" means; if `--next` and `--doctor` parse differently they will disagree about the
backlog and the user will trust neither.

## Behavior & scenarios

### Command surface

| Command | Does | Gate |
|---|---|---|
| `/quirk:pm:roadmap` | Propose or revise milestone grouping | **user ratifies** before write |
| `/quirk:pm:next` | Report unplaced count, offer intake, shortlist ~5, recommend 1 | read-only; intake write **ratified** |
| `/quirk:pm:start <ID> --probe K:ARG [--repo S] [--here]` | Create worktree, baseline the probe, write packet, dispatch | unattended |
| `/quirk:pm:finish <ID> [--project-dir P]` | Re-run probe in CWD, close against the ledger, or refuse | unattended |
| `/quirk:pm:park <ID> [--reason]` | Return to `open`, keep attempt on record | unattended |
| `/quirk:pm:status` | Index + doctor findings | read-only |

`--here` opts out of dispatch and runs the task in the current worktree — the original local
behavior, retained because not every task is worth a worktree.

### Scenarios

**Probe already green at `start`.** Refuse. The probe does not discriminate this entry. The user
supplies a different probe, or starts with `--probe none` and accepts an unverified close.

**Probe still failing at `finish`.** Refuse to close; entry stays `in_progress`. This is the one
moment the tool tells the user no, and it is the point of job 2.

**No probe applies.** Closes with `evidence: none`; `--doctor` lists it under unverified closures.
Labelled, never blocked.

**Nothing ready.** `--next` explains which blockers are open and what would unblock the most work.

**Critical bug filed mid-session, in no milestone.** Surfaces via the severity escape hatch.

**Task stalls.** Stays `in_progress`, ages, appears in the index and `--doctor` with its age.

**Two worktrees in parallel.** `flock` is per-directory and **does not coordinate across
worktrees**. Two sessions may start the same entry. `finish` is idempotent, so the cost is
duplicated effort, never corrupted state. A conflicting status line is an ordinary git conflict.

**Milestone finishes.** Derived, not stored — complete when every entry it names is closed.
Nothing to update, nothing to drift.

**Entry closed but still named in the roadmap.** Normal. The roadmap records intent, including
intent already satisfied. `--doctor` flags only roadmap IDs that do not *exist*.

### Handoff scenarios

**No adapter installed.** `start` creates the worktree with `git worktree add`, runs the probe,
writes the packet and the ledger, and prints the launch prompt for you to paste. Every guarantee
except automatic launching is intact.

**Probe passes at dispatch time.** Refuse before launching. The entry stays `open`, no worker is
started, and the worktree is left for inspection.

**Worker finishes but the probe still fails.** `finish` refuses. The entry stays `in_progress`
with its `Handoff` line intact, so `--doctor` will surface it as a stall pointing at the exact
worktree where the attempt lives.

**Worker is abandoned and never reports.** The entry ages in `in_progress` and appears as a stall
with its handoff target. Nothing times out and nothing auto-reverts — the record that work was
attempted and dropped is the signal, and the `Handoff` line is what makes it recoverable.

**Cross-project dispatch, worker discovers a new bug.** It files to the **origin** ledger with
`--project-dir`, per the packet's third obligation. The origin keeps the complete record of what
the work turned up, even though none of it happened in that repo.

**Worker closes the task, then the PM session is asked what's next.** The ledger already reflects
the close, so `--next` is correct whether or not the completion signal arrived. Under orca the PM
also receives `worker_done` and notices immediately.

**Two workers dispatched for the same entry.** `start` refuses on an entry already `in_progress`
and prints its existing `Handoff` line. This is a check, not a lock — two sessions racing can
still both pass it — but `finish` is idempotent, so the cost stays duplicated effort.

## Scope & non-goals

### In scope for v1

- Two optional ledger fields: `Status` (absent = open) and `Blocked by` (flat comma-separated ID
  trailer). Both additive; zero migration. They apply to `BUG`, `DEFER`, and `TEST` entries only —
  `proposals.md` keeps its own human-only vocabulary and gains neither field.
- `ROADMAP.md` — ordered milestones naming entry IDs. A milestone may reference `BUG`, `DEFER`, and
  `TEST` entries; it may not reference a `PROPOSAL`, which is a decision awaiting a human rather
  than a unit of work. `--doctor` reports a `PROPOSAL` reference in a milestone as a finding.
- A third optional field, `Handoff`, auto-populated at dispatch: repo, branch, and worktree path.
  Never model-supplied. A record of where work went, explicitly **not** a lock.
- `bin/artifact_lib.py` — extracted shared parse/render, no behavior change.
- `bin/pm.py` — next / start / finish / park / roadmap / status / doctor / index.
- `artifact_append.py` and `artifact_review.py` refactored to import the lib.
- `hooks/load_artifact_tail.sh` rewritten to call `--index`.
- The handoff packet written to `.quirk/handoff/<ID>.md` in the destination worktree.
- The adapter interface (three calls) plus a git-only fallback path.
- One orca adapter over `orchestration task-create` / `worker-start` / `send --type worker_done`.
- One skill and six commands under `/quirk:pm:*`.

### Sequencing

The structure chosen affords a natural two-phase rollout, and the phases are ordered by
falsifiability rather than by convenience.

**Phase 1 — read layer.** Extract `bin/artifact_lib.py`, add `--index` / `--next` / `--doctor`,
rewrite the SessionStart hook. Entirely pure: no schema change, no write path, nothing an
adversarial agent can game, and nothing to migrate. It is also the precondition for judging
honestly whether the rest is needed — until the backlog can be *seen*, claims about improving it
are unfalsifiable.

**Phase 2 — write layer.** `Status`, `Blocked by`, probes, the lifecycle commands, `ROADMAP.md`,
and the `--next` intake step. `start` runs locally here (`--here` semantics as the only behavior).

**Phase 3 — handoff.** The `Handoff` field, the packet, the adapter interface with its git-only
fallback, and the orca adapter. `start` gains dispatch as its default.

Each phase is shippable alone and none is shippable before its predecessor. Phase 3 carries all of
the cross-process and cross-repository risk in the design, and isolating it means Phases 1 and 2
can be trusted while it is still being proven.

### Explicit non-goals

Each was proposed during design and rejected on evidence. Recorded so they are not re-litigated.

- **No ID format change.** Today's duplicate-`BUG-8`-on-merge is a *loud* failure — a git conflict
  marker a human resolves. Every proposed fix trades it for a silent one during partial rollout,
  and `artifact_review.py` has no schema-version handling, so a mixed-format file causes fields to
  bleed across entry boundaries. Ambiguous references become a `--doctor` finding instead.
- **No `merge=union` in `.gitattributes`.** Converts that loud conflict into a silent duplicate
  reaching main, and removes the only signal that two sessions were filing simultaneously.
- **No custom merge driver.** Requires per-clone `git config` a repository cannot carry — silently
  absent in exactly the fresh-clone case it exists for.
- **No `.quirk/` derived state and no JSON projection.** A second writable copy needing machinery
  to audit itself.
- **No arbitrary probe execution.** Closed verb set, script-owned.
- **No autonomous groom loop.** No working AI backlog groomer appears anywhere in the research
  corpus; the negative evidence is independently corroborated. The PM does not re-rate, dedupe, or
  sweep the backlog on its own. Note this is narrower than "no subagent": *dispatching an
  implementer to do work a human selected* is in scope and is what `start` does. The rejected thing
  is an agent that reshapes the backlog unattended, which remains rejected.
- **No per-session append caps.** Capture is the part that demonstrably works; friction on that
  path sends observations back into prose.
- **No auto-expiry or aging-out.** Hiding old work is the defect being fixed.
- **No claim or lease fields.** `flock` cannot coordinate across worktrees; a lock that appears to
  provide mutual exclusion and does not is worse than none. The `Handoff` field is deliberately not
  this: it records where work went, carries no expiry, and grants no exclusivity. `start`'s refusal
  on an already-`in_progress` entry is a courtesy check, not a mutex, and the spec says so wherever
  it appears.
- **No `proposals.md` vocabulary change.** Its existing `proposed / accepted / rejected /
  superseded` states stay untouched and human-only.

### Deferred to later versions

- `Logged by` provenance stamping (agent vs human authorship per entry).
- Advisory difflib duplicate detection at append time.
- Promotion of entries to GitHub issues.
- Milestone-level status beyond the derived complete/incomplete.

### Known limits

Stated rather than papered over. None of these has a fix inside this design.

1. **Closure is forgeable.** `git commit --allow-empty` passes a `git cat-file -e` check. The
   `test:` red→green probe is materially harder to fake; `commit:` and `none` are audit trail only.
   Effort goes into making degradation legible, not into a gate that would be theater.
2. **`flock` does not span worktrees.** Parallel sessions can duplicate effort. `finish` is
   idempotent so state stays correct.
3. **Probes cover perhaps a third of `BUGS.md` and almost none of `DEFERRED.md`.** Most closures
   will be `none`. The value is the label, not the coverage.
4. **Nothing compels a worker to read the packet.** The write-back contract is an instruction, and
   instructions in a file decay within a session. Printing it in every `pm.py` stdout raises the
   odds; it does not guarantee them. A worker that ignores the packet produces an entry that stalls
   — visible, but only after the fact.
5. **Cross-project write-back is unenforceable from the origin.** The origin cannot tell the
   difference between a worker still working, a worker that died, and a worker that finished and
   forgot to write. All three present as a stall.
6. **No evidence any of this improves throughput.** The costs are corroborated by the research; the
   benefits are not. This ships as something to evaluate, not something proven.

## Decisions Locked

**Roadmap source**
- `ROADMAP.md` referencing entry IDs, not restating work.
- Agent proposes, human ratifies.
- Roadmap lists the IDs; entries stay append-only.
- Ordered milestones, no dates.

**Ordering authority**
- Code shortlists, model recommends.
- Sort key: milestone → severity/priority → age.
- Critical/high severity may surface outside the roadmap.
- Top ~5 candidates surfaced, one recommended.
- `--next` reports the unplaced count always and offers intake when non-zero; declining is fine.

**Handoff** *(amendment, 2026-08-05)*
- `start` dispatches by default to a new child worktree of the current repo; `--repo` redirects,
  `--here` opts out.
- One ledger — the origin's. The packet carries its absolute path; the worker writes back with
  `--project-dir`.
- The packet is a file in the destination worktree; the launch prompt only points at it.
- The launcher is pluggable behind a three-call adapter, with a git-only fallback.
- The worker writes back to the ledger always; under orca it additionally signals the PM session.
  The signal is additive, never authoritative.
- `finish` signals `succeeded`, `park` signals `failed`, a refused `finish` signals nothing.
- The signal recipient resolves as ambient Dispatch → IDs recorded in the packet → skip.
- The entry records a `Handoff` line: repo, branch, worktree path.

**Completion evidence**
- States: `open → in_progress → closed`, with `wontfix` / `superseded` as terminal exits.
- Fixed-verb probe with a baseline captured at `start`.
- Agent closes when the probe passes; `--doctor` flags self-authored evidence.
- Stalls flagged by doctor and surfaced at SessionStart; never aged out.

**Agent autonomy**
- Shepherd only — never writes code.
- Skill plus slash commands over Python scripts; no subagent.
- Unattended writes limited to status transitions.
- Ambient surfacing, explicit action; no blocking hooks.

**Structure**
- `bin/artifact_lib.py` extracted, `bin/pm.py` added.

**Scope**
- Core only in v1; provenance and dedup deferred.
- Bootstrap by agent-drafted roadmap the user edits.
- `/quirk:pm:*` namespace.

## Industry Insights

Distilled from a 14-agent research pass (220 findings, 355 sources) covering web, Reddit, primary
repository documentation, and academic work.

**On the core problem**
- "A queue with no running consumer is worse than no queue, because it looks like it is working."
  — [r/AI_Agents](https://www.reddit.com/r/AI_Agents/comments/1uyoahi/)
- Memory tools "fix recall, not direction. An agent can remember every past session and still drift
  right off the plan." — [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1twz78u/)
- "i stopped trusting self-reported done after the third time an agent closed a ticket it hadn't
  actually finished… make the agent produce a verifiable artifact instead of a status report."
  — [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1va65ln/)

**On ordering and estimation**
- LLM judges violate transitivity at material rates; no mitigation eliminates it.
  — [arXiv 2502.14074](https://arxiv.org/pdf/2502.14074)
- LLM story-point estimation: ρ≈0.38–0.45, with Spearman consistently exceeding Pearson.
  — [arXiv 2603.06276](https://arxiv.org/abs/2603.06276)

**On verification**
- Premature completion is failure mode #1 in Anthropic's long-running-agent harness.
  — [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Self-authored verification is unreliable: 15 of 35 model-game cells self-scored ≥0.70 while
  scoring below a random baseline on held-out deployment.
  — [arXiv 2607.24300](https://arxiv.org/html/2607.24300v1)
- Telling a model not to cheat does not work and can backfire: o3 reward-hacked 30.4% of RE-Bench
  runs unprompted, and "solve only using intended methods" *raised* the rate.
  — [METR](https://www.lesswrong.com/posts/Zu4ai9GFpwezyfB2K/metr-s-observations-of-reward-hacking-in-recent-frontier)
- Tests are checkable but leaky: 7.8% of SWE-bench Verified "resolved" patches fail once all
  developer tests run. — [arXiv 2503.15223](https://arxiv.org/html/2503.15223v1)

**On accumulation**
- Add-all memory performs *worse* than a fixed-memory baseline; selective add+delete gains +10%
  absolute. — [arXiv 2505.16067](https://arxiv.org/abs/2505.16067)
- Context rot is measured recall degradation with non-uniform cliffs across 18 models.
  — [Chroma](https://research.trychroma.com/context-rot)
- Practitioners on generated markdown: the modal answers are "I delete them" and "I have Claude
  consolidate them." — [r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1u5xvh3/)
- Three-bucket doc lifetime: contract docs live with the code, working docs die at merge, specs get
  an explicit retirement step. — [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1uvrjy5/)

**On prior art**
- Ready work is computed from direct blockers only, with a two-tier edge model — four blocking
  types, six non-blocking annotations. — [beads](https://github.com/steveyegge/beads)
- Beads treats Dolt as source of truth and warns the JSONL export is *not* a sync channel; import
  is upsert-only and cannot represent a deletion.
  — [beads sync concepts](https://beads.gascity.com/core-concepts/sync-concepts.md)
- Community sentiment on beads has turned on complexity churn, producing forks that strip features.
  — [r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1qj6l75/)
- The strongest counter-position — "just use an issue tracker" — is near-consensus among power
  users and rates markdown lowest of three options.
  — [r/ClaudeCode, 264 pts](https://www.reddit.com/r/ClaudeCode/comments/1qpd4ro/)

**On documentation volume**
- OpenSpec in practice "produces mounds of documentation that are really hard to read and review,
  and it doesn't scale at all well." — [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1uno1bs/)
- A multi-agent PM/architect/QA pipeline generated 13 documents for what turned out to be a label
  change, at $10+ per task.

## Deferred Ideas

Captured by the scope-creep guard during design; none absorbed into v1.

- **`Logged by` provenance line.** Auto-stamped agent-vs-human authorship per entry. Passed review
  as a surviving change; deferred to keep v1 core-only. Would make the roadmap ratification gate
  materially easier to use.
- **Advisory difflib dedup at append.** Warn and annotate, never block. Measured thresholds are
  unreliable for paraphrase — the cross-session case — so its value is lower than it appears.
- **GitHub promotion path.** Deliberate per-entry promotion when work should be visible outside the
  session. Rejected as a *lifecycle step*; still reasonable as an explicit command.
- **`--doctor` in CI.** Exits non-zero on findings, so it composes with no agent in the loop.
- **Gitignoring artifact lock files.** Confirmed unrelated pre-existing bug: `.gitignore`'s `.lock`
  pattern does not match `.BUGS.md.lock`, and `artifact_init.py` adds no ignore entry, so every
  adopting project accumulates untracked lock files in its root.

## Glossary

**Ledger** — the four typed artifact files holding entry text.
**Plan** — `ROADMAP.md`, holding milestone order and entry membership.
**Ready** — an entry that is open and whose every blocker is not-open.
**Eligible** — ready, and either in a milestone or of critical/high severity.
**Probe** — a closed-verb check whose result is captured at `start` and re-checked at `finish`.
**Baseline** — the probe's recorded result before work began.
**Red→green** — the required transition from a failing baseline to a passing check.
**Stall** — an entry in `in_progress` with no status change for 7 days (`QUIRK_PM_STALL_DAYS`).
**Urgency** — the single 0–3 integer scale unifying `Severity` and `Priority` for sorting.
**Park** — return an in-progress entry to open, keeping the attempt on record.
**Shepherd** — the PM agent's role: selects, tracks, and verifies, but never implements.
**Unplaced** — a ready entry belonging to no milestone; counted on every `--next`.
**Intake** — the optional step that places unplaced entries into milestones.
**Dispatch** — creating a worktree, writing a packet, and launching a worker for an entry.
**Packet** — the markdown file in the destination worktree carrying task, bar, ledger address, and
the write-back contract.
**Origin** — the project whose ledger holds the entry, regardless of where the work is performed.
**Adapter** — a pluggable implementation of `create_worktree` / `launch` / `signal_done`.
**Worker** — the dispatched session that implements the task and writes back.

## Status & amendments

**Status:** Approved — design accepted 2026-08-04 across three review sections; amended 2026-08-05.

**Amendments:**

- **2026-08-05 — intake and handoff.** Two capabilities requested after approval. Both change
  locked decisions rather than extending around them.

  **Intake.** `--next` now reports the unplaced count on every invocation and offers to place those
  entries. This closes a hole the original design created: with `eligible := ready AND (in a
  milestone OR urgency <= 1)`, medium- and low-urgency work in no milestone was invisible to the
  shortlist *and* absent from the plan — the append-only-queue failure this feature exists to fix,
  reproduced inside the feature. Reporting is unconditional so it cannot hide; placement stays
  optional so `--next` does not become mandatory grooming.

  **Handoff.** `start` changes from a local state transition to a dispatch: create a worktree
  (new child of the current repo by default, `--repo` to redirect, `--here` to opt out), baseline
  the probe *there*, write a packet into the destination, and launch a worker. This adds a third
  ledger field (`Handoff`), a packet format, an adapter interface, an orca adapter, and a Phase 3.

  Three constraints were held while absorbing it:
  - **The launcher stayed pluggable.** Requiring orca would have repeated the exact trade used to
    reject integrating beads — an external binary making the module conditionally rather than
    cleanly inert. `pm.py` writes the packet and prints the prompt with no adapter present.
  - **The ledger stayed singular.** Work performed in another project still writes to the origin
    ledger via `--project-dir`. Mirroring the entry into the destination was rejected as another
    second-writable-copy, consistent with the three prior rejections of that shape.
  - **The completion signal stayed additive.** The ledger write is what closes a task; the orca
    `worker_done` message only makes the PM notice sooner. A lost signal leaves state correct.

  Two existing non-goals were narrowed rather than reversed, and both now say so explicitly:
  "no PM subagent" became "no autonomous groom loop" (dispatching an implementer for
  human-selected work was never the rejected thing); and the "no claim or lease fields" rejection
  now states that `Handoff` is a record with no expiry and no exclusivity, and that `start`'s
  refusal on an in-progress entry is a courtesy check rather than a mutex.

  Known limits 4 and 5 were added to record what this amendment cannot enforce: nothing compels a
  worker to read the packet, and the origin cannot distinguish a working worker from a dead one
  from a forgetful one — all three present as a stall.

- **2026-08-05 — completion signal corrected and completed.** Review of the amendment against
  orca's actual semantics found the signal-back under-specified in three ways.

  **An overstatement was removed.** The spec had claimed `worker_done` "defaults to its owning Run
  mailbox when no recipient is given, so the worker never needs to know the PM's handle." That is
  true only *from an active Dispatch* — `worker_done` is an exact-Dispatch signal. A worker started
  by `worker-start` qualifies, but the same `finish` run from a terminal opened by hand in that
  worktree does not. The packet now records run and dispatch IDs, and `signal_done` resolves
  ambient Dispatch → recorded IDs → skip, with skipping treated as a normal outcome.

  **`park` now signals.** The original text put the signal only on `finish`, which inverted the
  priority: the case the PM most needs to hear is the one where the worker gave up, and it is the
  least likely to surface any other way. `finish` signals `succeeded`, `park` signals `failed`.

  **A refused `finish` signals nothing**, now stated explicitly. The task is not terminal and the
  worker is presumably still on it; one notification per failed attempt is how a channel becomes
  noise that gets muted.
