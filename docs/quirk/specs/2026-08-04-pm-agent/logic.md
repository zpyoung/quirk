# pm-agent — Logic Spec

## Purpose

A quirk module that answers two questions about a project's typed artifacts: **what should we work
on next**, and **is the thing we started actually finished**.

It exists because quirk's typed artifacts are an append-only queue with no consumer. Entries go in
and nothing takes them out, nothing reports depth, and nothing distinguishes an entry that was
resolved from one that was merely filed. The existing design spec already rates artifact rot as
*likelihood High*; this module is the consumer that rating implies.

Its first version covers the roadmap artifact, the ready-set computation with unplaced-work intake,
the task lifecycle with baselined probes, the handoff that dispatches a task to a fresh session —
often a new worktree, sometimes a different project — and the read layer that replaces the
SessionStart tail. Provenance stamping and duplicate detection are deferred.

**It records and surfaces state; it does not enforce it.** The design assumes a cooperative worker
and says so throughout — see *Threat model*. Two adversarial review rounds established that no
enforcement mechanism available to a repo-local tool survives a worker that shares the repository,
so the goal is a record that is accurate when reported honestly and *visibly wrong* when not.

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

### Threat model: cooperative worker, not adversarial

**This design does not defend against a worker that wants to fake completion. It cannot, and it
stops pretending to.**

Two adversarial review rounds established this empirically rather than by argument. Every
enforcement mechanism reachable from here lives on local git state, and local git state is fully
writable by the thing being checked:

- A linked worktree forges the integration check in one command —
  `git update-ref refs/remotes/origin/main <its own sha>` makes `merge-base --is-ancestor` return
  0, and the forged ref is visible from the origin worktree, because linked worktrees share refs.
- `git rev-parse --git-common-dir` returns the same value for every worktree of a repository, so it
  identifies the repo, not the checkout.
- A worker can rewrite the probe it is measured by, or retry a flaky one until it passes.

A real trust boundary would mean consulting the remote or the forge — network access, credentials,
and a hard dependency, which is the posture used to reject integrating beads. That is a different
product, and it is out of scope here.

So the design's purpose is **legibility, not enforcement**. It answers "what does the record say,
and who said it" — never "is this claim true". Every state is a *report* with an attributed source,
and the value is that a false report is visible in a diff and in `--doctor`, not that it is
prevented.

This is also what the research supported. The corpus contained no evidence that enforcement
mechanisms work on agents — METR measured anti-cheating instructions backfiring — and considerable
evidence that making state visible is what practitioners find useful.

The checks that remain are **mistake-catchers, not security controls**: they catch an honest worker
finishing in the wrong directory or on a dirty tree, which is a common accident. They are described
that way throughout, and nowhere in this spec should a check be read as a guarantee.

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
The failing result and a fingerprint of the probe are written into the entry as a baseline.

At `finish`, the same probe is re-run against a **committed** revision and must now **pass**.

The bar is fixed while the agent still has an interest in it being real, which is what
distinguishes this from every evidence scheme that checks a condition only at closing time. But
red→green alone is not sufficient, and this design does not claim it is — see *What red→green does
not prove*.

The verb set is **closed**. The script owns the verbs; the agent supplies only arguments. This is
not incidental: an allowlisted script that executes an agent-chosen command string is an
unsandboxed bypass of the Bash permission surface, which is why the arbitrary-probe variant was
rejected.

| Kind | Passes when | Refuses when |
|---|---|---|
| `test:<nodeid>` | the node runs and passes on `HEAD` | node missing, errors, or fails |
| `grep:<pattern> [-- <paths>]` | baseline count > 0, final count == 0 | a file that matched at baseline no longer exists |
| `none` | never checked — explicitly unverified | — |

Two rules close deletion loopholes. `test:` refuses when the node is **missing** rather than
reading absence as success, so deleting the test cannot close the entry. `grep:` refuses when a
file that matched at baseline is **gone**, because deleting the code that carried the symptom is
not a fix, and a naive count-decrease is satisfied by it.

`commit:<sha>` was removed from this table. It cannot be a probe: red→green requires the checked
condition to be false at `start`, and no worker can name the SHA of a commit it has not yet made.
The commit belongs to the `delivered` state below, which is where it always belonged.

Most `DEFER` entries will use `none`. The value is the label, not the coverage. `PROPOSAL` entries
never enter this flow at all — see the command surface.

### What red→green does not prove

Under the cooperative-worker model these are not holes to be plugged — they are the boundary of
what the signal means, stated so nobody mistakes it for more.

**It does not prove the fix was delivered.** A probe passing in a worktree says nothing about the
origin's integration branch. The two-state split below records both facts separately.

**It does not distinguish a fix from flakiness.** A probe with independent pass probability *p*
eventually passes under enough retries. An attempt counter and a refusal count are kept so an entry
that reached green on the fourth try shows it, and `--doctor` reports it. This makes retrying
*visible*; it does not make it harder.

**It does not prevent the probe being weakened.** A worker can edit the test it is measured by. The
probe spec, and for `test:` its containing file, are hashed at `start` and re-hashed at `finish`; a
change is **recorded and flagged, never blocked** — adding a regression test is a normal part of
fixing a bug. The hash is provenance, not a lock.

### Delivered is what the worker reported; closed is what the origin observed

The terminal transition splits in two — not as a trust boundary, but because "a probe passed
somewhere" and "the fix reached the project" are **different facts with different sources**, and
collapsing them loses the attribution.

**`delivered`** — reported by the worker. Records the commit it finished on and the probe result.

**`closed`** — observed by the origin. Records that the delivering commit is reachable from the
project's integration ref:

```
git merge-base --is-ancestor <delivered-sha> <integration-ref>
```

The integration ref defaults to the repository's default branch from `refs/remotes/origin/HEAD`,
falls back to the checked-out branch when that symref is absent (repos created by `git init` plus
`git remote add` have none), and is overridable via `QUIRK_PM_INTEGRATION_REF`.

**This check is not a trust boundary and is not described as one.** A linked worktree can point
`refs/remotes/origin/main` at its own commit and the check returns 0 — verified during review, in
one command, with the forged ref visible from the origin worktree because linked worktrees share
refs. Its actual value is catching the ordinary case: work that was delivered and genuinely has not
been merged, which is the state most likely to be silently forgotten.

**`reconcile` runs in the repository that produced the commit.** For a same-repo worktree that is
the origin, whose object store is shared. For cross-project work it is the repo named in `Handoff`
— the origin cannot resolve a foreign SHA at all, and `merge-base` exits **128, "Not a valid commit
name"**, rather than returning false. Three outcomes are therefore distinguished, because
collapsing them is how an entry stalls forever with no diagnosis:

| git result | Meaning | Recorded as |
|---|---|---|
| exit 0 | reachable | `closed` |
| exit 1 | known, not reachable | stays `delivered` — "awaiting integration, N days" |
| exit 128 | object unknown here | stays `delivered` — `--doctor` reports "cannot evaluate" |

`reconcile` fetches the target remote before evaluating, since remote-tracking refs are local
snapshots and a stale one reads as "not merged" indefinitely. A failed fetch yields "cannot
evaluate", never "not integrated".

**Rebase, cherry-pick, and squash all break commit identity**, so ancestry returns false for work
that did land. These are reported as *undetermined* and surfaced for a human to close. An earlier
draft searched integration-ref commit messages for the entry ID as a fallback; that is **removed**
— the search was unbounded, so an old commit, a revert, or a doc merely mentioning `BUG-7` could
close the entry. A wrong close is worse than an unresolved one.

**Reachability proves the change landed, not that it survived.** A later commit can revert it.
`reconcile --verify` re-runs the probe against the integration ref in a temporary checkout for
projects wanting more; the default is reachability alone, because CI is the right place to catch a
post-merge regression.

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
      satisfied(b) := b resolves AND b.status ∈ {closed, wontfix, superseded}
      ready(e)     := status is open AND every blocker is satisfied
      unplaced(e)  := status is open AND e is in no milestone     # NOT limited to ready
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

**Age needs one comparable scale across types.** `BUG`, `DEFER`, and `PROPOSAL` entries get an
auto-stamped date (`Observed` / `Deferred` / `Proposed`); `TEST` entries have **no date field** at
all, in the template or the append schema. An earlier draft patched this by falling back to ID
ordinal — but dates and per-file integers are different domains, so it never defined whether
`TEST-7` is older than a `BUG` dated 2026-08-01, and two implementers would order them differently.

Schema v2 therefore **adds a `Logged` date to `TEST` entries**, auto-stamped like every other type.
Age is one date for everything. This is cheap because v2 is already a migration; it was only worth
avoiding when "zero migration" was still the goal.

Entries predating the migration have no date. They sort as **oldest**, which is both true and the
safe direction — the sort key exists to stop old work sinking out of view. Remaining ties break on
ID ordinal, then type name, so the order is total and reproducible across clones.

Age sorts last but is present deliberately: it counteracts the recency bias measured in the
current SessionStart tail, where the entries dropped from view were the oldest and longest-open.

When the ready-set is empty, `--next` explains **why** rather than printing nothing — which
blockers are open, and what would unblock the most work. A dependency graph that cannot answer
"why is nothing ready" is worse than no graph; beads arrived at the same conclusion and added
`--explain`.

Readiness uses **direct blockers only**. A closed blocker's own blockers cannot matter, so
transitivity falls out for free and there is no graph walk in the read path.

**Satisfaction is an allowlist, not "anything but open".** Writing the rule as "every blocker is
not-open" silently counts `in_progress` and `delivered` as satisfied — so merely *starting* a
blocker, or a worker reporting it delivered, would unblock everything downstream before the work
integrated. That inverts the point of having dependencies. Only the three terminal states satisfy a
blocker, and each for a stated reason: `closed` because the work landed; `wontfix` and `superseded`
because a human decided the dependency no longer applies.

**An unresolvable blocker blocks — it never unblocks.** If `Blocked by: BUG-99` names an entry that
does not exist, an allowlist rule already refuses it, which is the safe direction. It leaves the
entry blocked and raises a `DANGLING` finding. The same applies to a self-block and to any entry in
a cycle — `--doctor` findings rather than silent behavior.

**Unplaced counts all open entries, not just ready ones.** Restricting it to ready entries would
leave blocked, unroadmapped, medium-urgency work counted nowhere — invisible to the shortlist *and*
absent from the plan, which is the exact failure this reporting exists to prevent. The count is
broken out as ready / blocked / malformed so a large number is diagnosable rather than merely
alarming.

### Job 2 — ushering a started task

```
/quirk:pm:start BUG-7 --probe test:tests/test_auth.py::test_safari [--repo <selector>]
  1. resolve target        → new child worktree of the current repo by default
  2. create the worktree   → adapter's create_worktree, or plain `git worktree add`.
                             NOTHING IS LAUNCHED YET.
  3. run the probe THERE   → must FAIL; if it passes, refuse and do not dispatch
  4. write the packet to $XDG_STATE_HOME/quirk/handoff/<ID>.md — OUTSIDE the worktree
  5. write the origin ledger:
       - **Status**:  in_progress — 2026-08-05 — attempt 1
       - **Probe**:   test:tests/test_auth.py::test_safari — baseline: fail — spec#a1b2 file#c3d4
       - **Handoff**: quirk @ pm/bug-7 — /Users/…/worktrees/bug-7 — repo:<origin-abs-path>
  6. launch the worker against THAT worktree, with a prompt naming the packet path

  … the worker implements; the PM is not in the loop …

/quirk:pm:finish BUG-7 --project-dir <origin>     # run BY THE WORKER, in the worktree
  preconditions, each refusing on failure — mistake-catchers, not guarantees:
    a. CWD's worktree root == the path recorded in Handoff
    b. working tree is clean            → catches passing on uncommitted edits
    c. probe passes on HEAD             → yields a real, named commit
  → re-hash the probe spec and file; record any change, do not block
  → ledger write goes to --project-dir:
    - **Status**: delivered — 2026-08-05 — attempt 1 — commit: 9a3f21c
  → adapter, if present, signals the PM session: outcome=succeeded

/quirk:pm:reconcile [--verify]                    # run BY THE ORIGIN, later, no worker
  for each delivered entry:
    → resolve the repo from Handoff; fetch its remote
    → git merge-base --is-ancestor <sha> <integration-ref>, run IN THAT REPO
    → exit 0    → **Status**: closed — 2026-08-06 — integrated: 9a3f21c
    → exit 1    → stays delivered; --doctor: "awaiting integration, N days"
    → exit 128  → stays delivered; --doctor: "cannot evaluate — commit not in this repo"
    → no fetch  → stays delivered; --doctor: "cannot evaluate — fetch failed"
```

**`finish` produces `delivered`, never `closed`.** Promotion is the origin's job. This is a
division of labour that keeps the two facts attributable, not a permission boundary — a worker with
filesystem access can edit the ledger markdown directly, and this design does not try to stop it.

**The packet lives outside the worktree.** Writing it into the destination as `.quirk/handoff/…`
would make `start` itself dirty the tree, and `finish` requires a clean one — so an honest worker
could never finish unless it committed an operational file. `.quirk/` is not gitignored in quirk's
own repo and cannot be assumed ignored in an arbitrary target, so the packet goes to
`$XDG_STATE_HOME/quirk/handoff/<ID>.md` (falling back to `~/.local/state`) and the launch prompt
carries its absolute path.

**The three `finish` preconditions catch mistakes, not cheating.** Comparing the *worktree root* —
not the git common dir, which is identical across every worktree of a repository and so identifies
only the repo — catches finishing in a sibling checkout. A clean tree catches passing on
uncommitted edits. Probing `HEAD` yields a commit someone else can inspect later. Each is a guard
against a plausible accident; none survives deliberate circumvention, and none is claimed to.

**Both terminal transitions signal; a refusal does not.** `finish` signals `succeeded` and `park`
signals `failed`. A `finish` that refuses signals nothing — the task is not terminal, the worker is
presumably still on it, and a notification per failed attempt is how a channel becomes noise that
gets muted. `park` signalling matters more than `finish` does: the PM most needs to hear the case
where the worker gave up, and that is the case least likely to surface any other way.

**Attempt and refusal counts are aggregates, not a history.** `start` stamps an attempt number and
each refused `finish` increments a refusal count, so an entry that took four tries shows it. What
this deliberately does *not* preserve is per-attempt detail — which attempt mutated the probe, where
each one failed, what a previous park's reason was. A later `start` overwrites `Probe` and
`Handoff` for the new attempt and the earlier values are gone.

That is a real limitation and the claim is narrowed to match: the counters make retrying *visible*,
they do not make it *auditable*. Preserving full history would need immutable per-attempt records,
which the current parser cannot express — it collapses repeated field labels into a dict
(`bin/artifact_review.py:29`) — and which would be the wrong trade for a file a human reads in a
diff. Git history holds the prior values for anyone who needs them.

**The probe runs at the destination, the write lands at the origin.** A probe is only meaningful
against the code being changed, while the ledger must stay singular. Note the write path is *new
code*: `artifact_append.py` accepts `--project-dir` (`bin/artifact_append.py:122`) but only appends
whole entries and rejects unknown fields (`:139`), so it cannot perform a lifecycle transition. The
mutator is `bin/pm.py`, which reuses the same `--project-dir` convention and locking discipline.

**Refusal happens before the worker is launched.** If the probe passes at step 3, the entry does
not move to `in_progress` and no agent starts — dispatching a worker against a bar already met is
how a task gets "completed" without anything happening. This ordering constrains the adapter: it
must be able to create a worktree *without* launching into it, and launch into an existing one.

The created worktree is left in place rather than silently removed, because a probe that
unexpectedly passes is evidence worth inspecting. `start` refuses to reuse a name that already
exists and reports the path, so a retry cannot silently collide with it.

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

Written to `$XDG_STATE_HOME/quirk/handoff/<ID>.md` (falling back to `~/.local/state`), **outside**
the destination worktree so it cannot dirty the tree `finish` requires to be clean. Its job is to
make the worker able to finish *and* aware that finishing includes writing back.

It carries:

- **The task** — ID, full entry text copied verbatim from the ledger, and the milestone it serves.
- **The bar** — the probe verb and argument, its recorded baseline, and the literal `finish`
  command to run.
- **The ledger address** — the absolute path to the origin project, and the explicit statement
  that the ledger is *there*, not here.
- **The return address** — the run, task, and dispatch IDs when the handoff was made under an
  orchestrator. These identify the attempt for logging and correlation. They do **not** authorize a
  completion signal from an arbitrary terminal; see the adapter contract.
- **Provenance and integrity** — a packet schema version and a digest of the ledger entry as of
  handoff, so a stale packet can be detected rather than silently trusted.
- **The write-back contract** — three obligations, stated as instructions rather than prose:
  1. When the probe passes, commit, then run `finish` against the origin ledger. `finish` yields
     `delivered`, not `closed`; you cannot close an entry and should not try.
  2. If you cannot finish, run `park --project-dir <origin> --reason "<why>"`. Do not leave it
     `in_progress`.
  3. Any *new* observation you make — a bug you noticed, a test you skipped — is filed to the
     **origin** ledger with `--project-dir`, not to the destination project.

**The copied entry text is data, not instruction.** The packet reproduces the ledger entry
verbatim, and that text was written by whoever filed the observation. It is fenced and explicitly
marked untrusted, because an entry body is an injection surface into every worker the packet is
handed to.

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
| `create_worktree(repo, name, base)` | Produce a path. **Must not launch anything.** | `git worktree add` |
| `launch(path, prompt)` | Start an agent session in an **existing** worktree | print the prompt, exit 0 |
| `signal_done(attempt, task, dispatch, outcome)` | Notify the dispatching session; `outcome ∈ {succeeded, failed}` | no-op — the ledger is the record |

**The split between the first two calls is a hard requirement, not a convenience.** The probe must
run and possibly refuse between them. An adapter that can only create-and-launch atomically cannot
implement this contract, because it would start a worker before the bar was checked.

With no adapter present, `start` still creates the worktree, still runs the probe, still writes the
packet and the ledger, and prints the prompt for you to paste. Nothing about the verification
contract depends on the launcher.

**The orca adapter** must therefore use the two-step path, not the convenience path:

```
create_worktree → orca worktree create --name <n> --repo <sel> [--base-branch <ref>]
                  (deliberately WITHOUT --agent, so nothing launches)
     … probe runs here, may refuse …
launch          → orca orchestration task-create
                  orca orchestration worker-start --task <id> --worktree path:<path> --agent claude
signal_done     → orca orchestration send --type worker_done --outcome <o> --task-id <id>
```

`worker-start --worktree new-child` is **not** usable: it creates the worktree and launches the
worker as one operation, leaving nowhere to run the baseline. Targeting `path:<path>` against the
already-created worktree is what makes refusal-before-launch possible.

**The signal can only be sent from the live assigned Dispatch.** Orca rejects `worker_done` from a
foreign pane even when the payload carries the correct task and dispatch IDs — rejection keys on
the sender's pane identity and returns `sender_not_assignee`
(`orca/hind/src/main/runtime/orchestration/lifecycle-reconciliation.test.ts:178`). Recorded IDs
therefore do **not** authorize a signal, and `signal_done` resolves in two cases only:

1. Running as the assigned Dispatch → send `worker_done`.
2. Anything else → **skip the signal** and write only the ledger.

Case 2 covers a hand-opened terminal, a reset Run, a non-orca launcher, and no adapter at all. It is
a normal outcome, not an error: the ledger already holds the result and the coordinator reconciles
from it. An earlier draft of this spec proposed falling back to the packet's recorded IDs; that
cannot work and has been removed.

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

**Linkage lives in the roadmap, not on the entry.** The reason is single-source-of-truth for
*position*, not append-only purity: a milestone's membership is one fact, and putting it on both
the entry and the roadmap would make two places able to disagree. One file changes for roadmap
changes, and reordering a milestone touches no entries at all.

**Append-only applies to an entry's substance, not its lifecycle.** This needs saying plainly
because an earlier draft rejected the `Milestone` field *on append-only grounds* and then added
mutable `Status` and `Handoff` fields to the same entries — an incoherent pair. The actual rule:
title, description, file, severity, and the other observation fields are never rewritten by any
script; lifecycle fields are mutable in place by `pm.py` alone. Lifecycle history is not preserved
by field duplication — the existing parser collapses repeated labels into a dict
(`bin/artifact_review.py:29`) — but by an attempt counter and the recorded refusal count, which are
single-valued and survive that collapse.

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
| `/quirk:pm:finish <ID> [--project-dir P]` | Check preconditions, probe `HEAD`, mark **delivered** | unattended |
| `/quirk:pm:park <ID> --reason R [--project-dir P]` | Return to `open`, keep the attempt on record | unattended |
| `/quirk:pm:decide <ID> --as wontfix\|superseded --reason R [--by ID]` | Terminal human decision | **human-gated** |
| `/quirk:pm:reconcile [--verify]` | Promote `delivered` → `closed` from git | unattended, origin-side |
| `/quirk:pm:migrate` | Idempotent v1 → v2 schema upgrade | unattended |
| `/quirk:pm:status` | Index + doctor findings | read-only |

`park` takes `--project-dir` for the same reason `finish` does — a dispatched worker parks against
the **origin** ledger, and the packet instructs it to. Its `--reason` is required rather than
optional: the entire value of park over abandonment is the recorded why.

**`wontfix` and `superseded` are human decisions, and need their own transition.** They were named
as terminal states with no way to reach them — no command, no actor, no source state. They are
produced by `/quirk:pm:decide <ID> --as wontfix|superseded [--by <ID>] --reason R`, which:

- may be invoked from any non-terminal state, including `open`, since deciding not to do something
  rarely waits for someone to start it;
- is **human-gated** — the agent may propose it and must not run it unattended, because it is the
  one transition that removes work from the board without anything being done;
- requires `--reason`, and `superseded` additionally requires `--by` naming the entry that replaces
  it, so the trail stays followable;
- satisfies blockers, per the allowlist above.

This is also the exit for work with no commit, which `finish` cannot handle.

**PM lifecycle commands reject `PROPOSAL` entries.** `proposals.md` keeps its own human vocabulary
(`proposed` / `accepted` / `rejected` / `superseded`) and gains no PM fields, so `start`, `finish`,
`park`, and `decide` all refuse a `PROPOSAL` ID and say why. Without this, one implementer rejects
them and another overwrites a human's `Status: proposed` with a lifecycle value that means
something else entirely.

`--here` opts out of dispatch and runs the task in the current worktree — the original local
behavior, retained because not every task is worth a worktree.

### Scenarios

**Probe already green at `start`.** Refuse. The probe does not discriminate this entry. The user
supplies a different probe, or starts with `--probe none` and accepts an unverified close.

**Probe still failing at `finish`.** Refuse; entry stays `in_progress` and its refusal count
increments. This is the one moment the tool tells the user no, and it is the point of job 2.

**Dirty working tree at `finish`.** Refuse, naming the uncommitted paths. Passing on edits that are
then discarded is the most direct route to a false `delivered`.

**`finish` run in the wrong checkout.** Refuse. The worktree root did not match the one recorded in
`Handoff`, which means the probe would have measured code the handoff never pointed at. This
catches the accident of finishing from a sibling worktree; it is not a barrier to someone who wants
around it.

**`--probe none` entries follow the same path as any other.** `finish` still requires a clean tree
and still records `HEAD`, so a `none` entry reaches `delivered` with a commit and `reconcile`
promotes it exactly like a probed one. Only the probe result differs: it reads `evidence: none` and
`--doctor` lists it under unverified deliveries.

An earlier draft had `none` close directly at `finish`, on the reasoning that there was "no SHA for
reconcile to check". That was simply wrong — `finish` runs against `HEAD`, which always names a
commit — and it created a shortcut whose only cost was honesty: choosing `none` skipped the failing
baseline, the final probe, and the integration check at once. Removing the special case removes the
incentive.

**Work with no commit at all** — a `DEFER` resolved by deciding not to do it, a `PROPOSAL` settled
in discussion — does not go through `finish`. It takes a terminal decision transition instead.

**Delivered but never merged.** Stays `delivered`. `--doctor` reports "awaiting integration, N
days". The work is done and the ledger says exactly that — neither closed nor stalled, because
neither would be true.

**Squash-merged.** Reachability fails, so `reconcile` falls back to matching the entry ID in
integration-ref commit messages, promotes on that, and records the weaker justification.

**Nothing ready.** `--next` explains which blockers are open and what would unblock the most work.

**Critical bug filed mid-session, in no milestone.** Surfaces via the severity escape hatch.

**Task stalls.** Stays `in_progress`, ages, appears in the index and `--doctor` with its age.

**Two PMs in different origin worktrees.** This is not coordinated and the spec does not pretend
otherwise. Each worktree has its own checkout of `BUGS.md` and its own lock file, so both sessions
see `open`, both transitions succeed, and compare-and-swap does not help — CAS is per-file, and
these are different files. The result is two branches carrying divergent lifecycle state, resolved
as an ordinary git conflict when they merge.

Making this genuinely singular would mean a repository-global store outside the worktree, which
gives up the property the whole design is built on: artifacts a human reads and reviews in a diff.
The trade is taken deliberately. CAS is retained because it does prevent the *same-directory* race
— two processes in one worktree — which is the common case; it is simply not a distributed lock and
is no longer described as one.

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

- **Schema version 2, with a migration command.** Templates and the shared schema dict declare the
  new fields and the marker moves to 2. An earlier draft claimed "additive; zero migration" — wrong,
  because lifecycle semantics in files still marked v1 let a mixed-version install disagree without
  the version guard ever firing (`bin/artifact_append.py:184-190`).

  Declaring v2 is not enough on its own either: `artifact_init.py:41` *skips* existing artifact
  files unless `--force`, which overwrites them wholesale — so an existing project would sit on v1
  forever or lose its entries. `bin/pm.py migrate` therefore performs an idempotent, `flock`ed
  v1→v2 upgrade that rewrites **only** the schema-version marker and the schema comment block,
  adds the `Logged` field to the `TEST` schema, and touches no entry body. Re-running it reports
  "already v2" and changes nothing. A partial run is safe to repeat, because the marker is written
  last.

  *No entry is rewritten* is the guarantee worth keeping; *no schema migration* is not one this
  design can honestly make.
- New ledger fields on `BUG`, `DEFER`, and `TEST` entries: `Status` (absent = open), `Probe`,
  `Blocked by`, and `Handoff`. `proposals.md` keeps its own human-only vocabulary and gains none of
  them.
- `ROADMAP.md` — ordered milestones naming entry IDs. A milestone may reference `BUG`, `DEFER`, and
  `TEST` entries; it may not reference a `PROPOSAL`, which is a decision awaiting a human rather
  than a unit of work. `--doctor` reports a `PROPOSAL` reference in a milestone as a finding.
  `Handoff` is auto-populated at dispatch — target repo path, branch, and canonical worktree root —
  never model-supplied. It records where work went and is explicitly **not** a lock. `reconcile`
  reads the repo path from it to know where the delivered commit can be resolved.
- `bin/artifact_lib.py` — extracted shared parse/render, no behavior change.
- `bin/pm.py` — next / start / finish / park / reconcile / roadmap / status / doctor / index.
- `artifact_append.py` and `artifact_review.py` refactored to import the lib.
- `hooks/load_artifact_tail.sh` rewritten to call `--index`.
- The handoff packet written to `$XDG_STATE_HOME/quirk/handoff/<ID>.md`, outside the worktree.
- The adapter interface (three calls) plus a git-only fallback path.
- One orca adapter over `worktree create` / `worker-start --worktree path:` / `send worker_done`.
- `bin/pm.py migrate` — idempotent v1 → v2 schema upgrade for existing projects.
- One skill and nine commands under `/quirk:pm:*`.

### Sequencing

The structure chosen affords a natural three-phase rollout, and the phases are ordered by
falsifiability rather than by convenience.

**Phase 1 — read layer.** Extract `bin/artifact_lib.py`, add `--index` / `--next` / `--doctor`,
rewrite the SessionStart hook. Entirely pure: no schema change, no write path, nothing an
adversarial agent can game, and nothing to migrate. It is also the precondition for judging
honestly whether the rest is needed — until the backlog can be *seen*, claims about improving it
are unfalsifiable.

**Phase 2 — write layer.** Schema v2 plus `migrate`, `Status`, `Probe`, `Blocked by`, the lifecycle
commands (`start` / `finish` / `park` / `decide` / `reconcile`), `ROADMAP.md`, and the `--next`
intake step. `start` runs locally here (`--here` semantics as the only behavior), so the full
`open → in_progress → delivered → closed` machine including integration checking is exercised
**before** any cross-process complexity exists.

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

1. **Nothing here is enforceable against a determined worker.** `delivered` can be reached by
   weakening the probe or retrying a flaky one. `closed` can be reached by pointing
   `refs/remotes/origin/main` at your own commit — one command, verified during review, and visible
   from the origin worktree because linked worktrees share refs. The ledger itself is markdown any
   worker can edit. Read every state as *a report with an attributed source*, never as a proven
   fact. The design's claim is that a false report is visible; not that it is prevented.
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
- The signal is sent **only** from the live assigned Dispatch; otherwise it is skipped. Recorded IDs
  do not authorize it — orca rejects a foreign pane with `sender_not_assignee`.
- `create_worktree` must not launch; `launch` targets an existing worktree. Refusal happens between
  them, so `worker-start --worktree new-child` is unusable.
- The packet marks the copied entry body as untrusted data and carries a schema version and a
  digest of the entry as of handoff.
- The entry records a `Handoff` line: repo, branch, worktree path.

**Threat model** *(established 2026-08-05, round 2)*
- Cooperative worker, not adversarial. The design provides **legibility, not enforcement**.
- No check in this spec is a security control; all are mistake-catchers and are described as such.
- A real trust boundary would require consulting the remote or forge, which is out of scope.

**Completion evidence** *(reworked 2026-08-05, revised after round 2)*
- States: `open → in_progress → delivered → closed`, with `wontfix` / `superseded` reachable from
  any non-terminal state via `decide`.
- `finish` yields `delivered`; the origin's `reconcile` yields `closed`. A division of labour that
  preserves attribution, not a permission boundary.
- `--probe none` follows the same path as any probe; it does not shortcut to `closed`.
- Work with no commit exits via `decide`, not `finish`.
- `finish` preconditions: worktree **root** matches `Handoff` (not the git common dir, which is
  shared across worktrees), clean tree, probe passes on `HEAD`.
- `reconcile` runs in the repo named in `Handoff`, fetches first, and distinguishes reachable /
  not-reachable / cannot-evaluate. Rebase, cherry-pick, and squash yield *undetermined*, surfaced
  for a human — the entry-ID commit-message fallback was removed as unbounded.
- Probe verbs are `test:`, `grep:`, `none`. `commit:` is not a probe.
- Probe spec and test file are hashed at `start` and `finish`; changes recorded, never blocked.
- Attempt and refusal counts are aggregates, not per-attempt history.
- CAS guards the same-directory race only; it is not a distributed lock.
- A blocker is satisfied only by `closed` / `wontfix` / `superseded` — never by `in_progress` or
  `delivered`.
- `PROPOSAL` entries are rejected by every PM lifecycle command.
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
**Ready** — an entry that is open and whose every blocker is *satisfied*, i.e. `closed`, `wontfix`,
or `superseded`. `in_progress` and `delivered` blockers do **not** satisfy.
**Eligible** — ready, and either in a milestone or of critical/high severity.
**Probe** — a closed-verb check whose result is captured at `start` and re-checked at `finish`.
**Baseline** — the probe's recorded result before work began.
**Red→green** — the required transition from a failing baseline to a passing check.
**Stall** — an entry in `in_progress` with no status change for 7 days (`QUIRK_PM_STALL_DAYS`).
**Urgency** — the single 0–3 integer scale unifying `Severity` and `Priority` for sorting.
**Park** — return an in-progress entry to open, keeping the attempt on record.
**Shepherd** — the PM agent's role: selects, tracks, and verifies, but never implements.
**Unplaced** — any *open* entry belonging to no milestone, ready or not; counted on every `--next`
and broken out ready / blocked / malformed.
**Intake** — the optional step that places unplaced entries into milestones.
**Dispatch** — creating a worktree, writing a packet, and launching a worker for an entry.
**Packet** — the markdown file in the destination worktree carrying task, bar, ledger address, and
the write-back contract.
**Origin** — the project whose ledger holds the entry, regardless of where the work is performed.
**Adapter** — a pluggable implementation of `create_worktree` / `launch` / `signal_done`.
**Worker** — the dispatched session that implements the task and writes back.
**Delivered** — reported by the worker: it committed and the probe passed on that commit.
**Closed** — observed by the origin: the delivering commit is reachable from the integration ref.
**Undetermined** — `reconcile` could not evaluate reachability (foreign repo, failed fetch, or a
rebase/squash that changed commit identity). Surfaced for a human, never guessed.
**Decide** — the human-gated transition producing `wontfix` or `superseded`.
**Mistake-catcher** — a check that guards against a plausible accident, not against circumvention.
Every check in this spec is one.
**Integration ref** — what a project treats as integrated; `refs/remotes/origin/HEAD` by default,
overridable via `QUIRK_PM_INTEGRATION_REF`.
**Reconcile** — the origin-side pass promoting `delivered` entries to `closed`.
**Attempt** — one `start`-to-terminal cycle; numbered on the entry and counted across refusals.

## Status & amendments

**Status:** Approved — accepted 2026-08-04; amended twice and reworked 2026-08-05; threat model revised 2026-08-05 after a second adversarial review (`review-2026-08-05-codex-round2.md`). **Tech spec: requested.**
2026-08-05, then reworked 2026-08-05 following adversarial review
(`review-2026-08-05-codex.md`, 18 findings).

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

- **2026-08-05 — completion contract reworked after adversarial review.** An adversarial review
  (`review-2026-08-05-codex.md`, 18 findings: 5 critical, 9 high, 4 medium) verified the spec
  against quirk's source and orca's runtime. Two findings were not patchable and forced a design
  change; the rest were corrections.

  **`closed` no longer means "a probe passed somewhere".** The design had `finish` writing `closed`
  to the origin after a probe passed in whatever directory invoked it — no check that the tree was
  clean, that the checkout matched the handoff, or that anything was committed, let alone merged.
  A worker could pass on uncommitted edits, close the entry, and delete the worktree while the
  origin's default branch still carried the bug. The terminal transition now splits:
  `delivered` is the furthest a worker may go and requires a matching git-common-dir fingerprint,
  a clean tree, and the probe passing on a named commit; `closed` is computed by the origin from
  `git merge-base --is-ancestor` against a configurable integration ref. Squash-merge falls back to
  an entry-ID commit-message match, recorded as the weaker signal. `--probe none` entries close
  directly, since they have no SHA for reconcile to check.

  **The packet-ID signal fallback was removed, not fixed.** The previous amendment had
  `signal_done` fall back to run/dispatch IDs recorded in the packet when no ambient Dispatch
  existed. Orca rejects `worker_done` from a foreign pane *even with correct task and dispatch IDs*
  — rejection keys on sender pane identity and returns `sender_not_assignee`
  (`lifecycle-reconciliation.test.ts:178`). The fallback could never work in the scenario it was
  added for. Signalling now happens only from the live assigned Dispatch, and is skipped otherwise.

  **The orca adapter sequencing was wrong.** `worker-start --worktree new-child` creates the
  worktree and launches atomically, leaving nowhere to run the baseline probe — so refusal could
  not precede launch. The adapter now uses `orca worktree create` without `--agent`, then
  `worker-start --worktree path:<path>`. `create_worktree` must not launch is now a stated contract
  requirement rather than an implicit assumption.

  Corrections applied in the same pass:
  - `commit:` removed from the probe table — it cannot be a red→green probe, since no worker can
    name the SHA of a commit it has not made.
  - `grep:` now refuses when a file that matched at baseline is gone; `test:` refuses on a missing
    node. Deleting the evidence no longer reads as fixing the bug.
  - Age defined for `TEST` entries, which have no date field in the template or append schema —
    date when present, ID ordinal otherwise. A third of the sort key had been undefined for a whole
    artifact type.
  - `unplaced` widened from ready-only to all open entries, broken out ready / blocked / malformed.
    The previous definition left blocked unroadmapped work counted nowhere — the invisible-work
    hole the intake amendment claimed to close.
  - An unresolvable `Blocked by` ID now blocks fail-closed and raises `DANGLING`, instead of reading
    as "not open" and silently marking work ready.
  - `park` gained `--project-dir` and a required `--reason`; the packet had instructed workers to
    park against the origin using a command that could not target it.
  - Schema bumped to v2. "Additive; zero migration" was false — lifecycle semantics in files still
    marked v1 would let mixed versions disagree without the version guard firing.
  - The append-only rationale was corrected: it governs an entry's substance, not its lifecycle
    fields. The earlier draft rejected a `Milestone` field on append-only grounds and then added
    mutable `Status` and `Handoff` to the same entries.
  - Transitions are compare-and-swap on `(ID, attempt, expected status)`; every attempt including
    refusals is recorded, making retry-until-green visible.
  - The packet marks copied entry text as untrusted data and carries a schema version and digest.

  Deferred to the tech spec rather than fixed here: `ROADMAP.md` grammar, `Blocked by` lexical
  rules, parser strict/compat modes, exit-code table, and the fault-injection test matrix. The
  review filed these as logic defects; they are implementation contracts and belong in `tech.md`.

  Not adopted: re-running the probe on the integrated revision by default. `reconcile --verify`
  offers it, but reachability alone is the default because it is cheap, honest about what it
  measures, and CI is the right place to catch a post-merge regression.

- **2026-08-05 — threat model dropped to cooperative; enforcement claims withdrawn.** A second
  adversarial review (`review-2026-08-05-codex-round2.md`) audited the rework: 11 regressions, 3 new
  findings, and only 7 of round 1's 18 findings fully closed. Several of the top findings were
  round 1's *fixes* contradicting themselves.

  **The decisive result was empirical.** Three claims this spec relied on were falsified by direct
  test:
  - "Reachability is not something a worktree can fabricate" — a linked worktree ran
    `git update-ref refs/remotes/origin/main <its own sha>`; `merge-base --is-ancestor` then
    returned 0, and the forged ref was visible from the origin worktree, because linked worktrees
    share refs.
  - The git-common-dir precondition "stops a worker finishing in some other checkout" — every
    worktree of a repository returns the *same* common dir, so it identifies the repo, not the
    checkout. Replaced with a worktree-root comparison.
  - Cross-project reconciliation — `merge-base --is-ancestor` on a foreign SHA exits **128**, not 1,
    so cross-project entries could never promote and would look identical to awaiting-merge.

  Rather than patch each defeat, **the threat model changed**: this design assumes a cooperative
  worker and provides legibility, not enforcement. Every enforcement mechanism available to a
  repo-local tool lives on local git state, which the worker can write; a genuine trust boundary
  would require consulting the remote or forge, i.e. network, credentials, and a hard dependency —
  the posture used to reject integrating beads. The research supported this reading: the corpus had
  no evidence that enforcement works on agents (METR measured anti-cheating instructions
  backfiring) and considerable evidence that visible state is what practitioners get value from.

  Reframing dissolved several findings rather than fixing them — the checks remain as
  mistake-catchers for honest accidents and are now described that way everywhere.

  Fixed as genuine defects, independent of threat model:
  - **Blocker satisfaction is an allowlist.** `ready` had required blockers be "not-open", which
    silently counted `in_progress` and `delivered` as satisfied — so *starting* a blocker unblocked
    its dependents. Only `closed` / `wontfix` / `superseded` satisfy.
  - **The packet moved out of the worktree.** Writing `.quirk/handoff/<ID>.md` into the destination
    dirtied the tree that `finish` requires to be clean, so an honest worker could never finish.
    `.quirk/` is not gitignored in quirk's own repo and cannot be assumed ignored elsewhere. It now
    lives under `$XDG_STATE_HOME/quirk/handoff/`.
  - **`--probe none` no longer shortcuts to `closed`.** It contradicted "a worker can never write
    closed" and rested on a false premise — `finish` runs on `HEAD`, which always names a commit —
    while creating an incentive to pick the weakest evidence. It now follows the normal path.
  - **`reconcile` fetches, resolves the repo from `Handoff`, and separates cannot-evaluate from
    not-reachable.** The squash fallback that searched commit messages for the entry ID was
    **removed**: unbounded, so a revert or a doc mentioning `BUG-7` could close the entry. Rebase,
    cherry-pick, and squash now report *undetermined* for a human to close.
  - **`decide` added.** `wontfix` and `superseded` were named as terminal states with no command,
    actor, or source-state rule. `decide` is human-gated, requires a reason, and is the exit for
    work with no commit.
  - **`PROPOSAL` entries are rejected by all PM commands**, resolving a contradiction between the
    probe discussion and the scope section.
  - **Schema v2 gained `pm.py migrate`.** Declaring v2 was inert: `artifact_init.py:41` skips
    existing files unless `--force`, which overwrites them, so existing projects would have stayed
    v1 — the exact mixed-version failure v2 was meant to fix. v2 also adds a `Logged` date to `TEST`
    entries, making age one comparable scale instead of dates-versus-ordinals.
  - **Overclaims narrowed.** "Every attempt is recorded" became aggregate counters with the lost
    history stated. CAS is described as guarding the same-directory race only, not as a distributed
    lock; two PMs in different origin worktrees are explicitly uncoordinated.
  - The glossary's `unplaced` definition, which still said "ready", now matches the algorithm.

  Left open and stated rather than solved: cross-worktree ledger divergence (fixing it means a
  repository-global store, giving up the reviewable-in-a-diff property the design exists for), and
  orca `worker-start`'s requirement to run from a Run-bound coordinator terminal with the dispatch
  ID only existing after launch — a Phase 3 sequencing problem.
