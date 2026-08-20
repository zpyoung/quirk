# Wave partitioning for subagent-driven-development

## Status

Draft — approved in brainstorming, pending user review of this document.

## Problem

SDD runs are narrower and longer than the plan they execute requires, for two independent reasons.

**The wave rule collapses on any overlap.** `skills/subagent-driven-development/SKILL.md:165-166`
states that tasks in a wave run in parallel *if and only if* every declared `scope.files` is
disjoint, and that "any overlap means the wave runs sequentially". One overlapping pair therefore
serializes an entire wave: six tasks with a single shared file cost the sum of all six durations,
not the maximum over the groups that could have run concurrently.

**The decomposition rubric never reaches the orchestrator.** `skills/writing-plans/SKILL.md:111-119`
already carries a `Task-Boundary Granularity Economics` section whose closing rule is "Set the
target task count from achievable wave width, never from the number of requirement bullets", plus
vertical-slice partitioning and hub-file-isolation-as-heuristic. `skills/executing-plans/SKILL.md:52`
runs that rubric in full. SDD — the skill that actually has waves — only "cross-reference[s]
**quirk:writing-plans** for the field schema" (`SKILL.md:149`). The wave-width guidance is loaded by
the skill with no waves and skipped by the one with them.

A third effect compounds both: wave count is the depth of the dependency DAG, and
`skills/writing-plans/SKILL.md:141` already forbids declaring `dependencies` for file overlap
rather than semantic ordering — but nothing enforces it. Every over-declared edge manufactures a
whole extra wave *and* its checkpoint review round (`SKILL.md:336-337`).

## Conceptual model

Step 4 stops asking "is this whole wave disjoint?" and asks the question Step 9 already asks:
**which tasks share write scope?**

Tasks become nodes. An edge joins two tasks whose `scope.files` intersect. Each **connected
component** of that graph is one unit of work: serialized inside, concurrent with every other
component. A wave's width becomes its component count rather than collapsing to 1 on any single
overlap.

This is not a new mechanism. `SKILL.md:449-452` already groups accepted review findings into
"**connected components of write scope** — not by cited file", dispatches "one fixer per component,
parallel across components", gives each its own worktree, and audits "each fix diff against its
component's write scope" (`SKILL.md:467-468`). The change makes Step 4 consistent with Step 9.
"Component" is already this skill's vocabulary; no new term is introduced.

Wave *count* is attacked separately at Step 3: the orchestrator runs the `writing-plans` rubric it
currently only borrows a schema from, and audits the dependency graph before computing waves.

## Data flow

Decompose (Step 3, now under the `writing-plans` rubric) → audit dependency edges, demoting any
motivated only by file overlap → sort by the remaining edges into waves → within each wave, build
the scope-conflict graph and take connected components → report the projected wave shape → dispatch
up to the width cap, queueing overflow inside the same wave → each component advances its chain,
each task audited and accepted as it completes → barrier: all components return → HEAD-check and
scope-audit every live tree plus the main tree → per component: commit, merge.

## Design

### Step 3 — decomposition rubric

Step 3 runs **quirk:writing-plans** as its in-context rubric, matching `executing-plans:52`, rather
than cross-referencing it for the field schema alone. Granularity Economics, vertical-slice
partitioning, and the hub-file heuristic all reach the orchestrator.

The existing carve-out survives and must say so explicitly: SDD still does **not** dispatch the
plan-document reviewer (`SKILL.md:151-159`). That prohibition governs plans built *by* writing-plans
as a standalone workflow; running the rubric in-context does not drag in its standalone gate. The
stated rationale is unchanged — this control plane spends its review budget on the branch, where a
reviewer reads code that exists, not at plan time, where it reads a prediction of it.

### Step 3 — dependency-edge audit

Before waves are computed, every declared `dependencies` edge is checked for semantic motivation —
one task genuinely needing another's output. An edge motivated **only** by file overlap is
**demoted**, not deleted: it stops contributing to DAG depth, and the component that contains both
tasks honors it when ordering its chain.

Demotion rather than deletion is load-bearing. Connected components guarantee that two
scope-sharing tasks are **co-located**, but they do not guarantee **order**. A file-overlap edge
can also be genuinely semantic — T_a creates a function in shared file F and T_b modifies it — and
deleting such an edge erases the only recorded ordering hint, surfacing later as a wrong-order
build reported as a confusing acceptance failure. Demotion preserves the full wave-count reduction
at no cost.

### Step 4 — partition the wave

A wave is still the set of tasks whose dependencies are satisfied. Within it:

1. Build the scope-conflict graph: node per task, edge when `scope.files` intersect.
2. Take connected components.
3. Each component runs as a serialized chain; components run concurrently.

The invariant is unchanged in substance — **no two concurrent tasks share a file** — but it is now
enforced by grouping rather than by collapsing the wave. Component union scopes are disjoint across
components by construction, so `SKILL.md:310-311`'s guarantee that merges "cannot conflict" still
holds.

Component ordering honors any demoted edge inside the chain.

### Step 4 — width cap and overflow

Concurrent live trees are bounded by a soft cap of roughly 4–6, because each pi worker is a real
unsandboxed process and each component holds a worktree on disk. When the cap binds, it is recorded
so a throttled run reads as throttled rather than as narrow.

Overflow components **queue inside the same wave**, dispatched as slots free. They are never
deferred to a new wave. Deferral is not the same serialization renamed: a second wave means the
first now "has a successor" and therefore earns a checkpoint review (`SKILL.md:336-337`), and it
forces every component of wave 1 to finish before any of wave 2 starts. Queueing backfills against
the wave-end barrier that exists anyway.

### Step 4 — wave-shape preview

Before dispatch, the orchestrator reports and journals the projected shape: component count per
wave, tasks per component, and whether the width cap bound. On the Claude binding it also states
the lockstep cost (below), so the projection is honest rather than optimistic.

A plan that partitions to a pure chain — depth N, width 1 — is surfaced once, naming the edges
forcing the chain. The orchestrator does not auto-re-decompose: the user may know the ordering is
genuine, and a guess would override real semantic ordering.

### Step 5 — dispatch and the lockstep limit

Each component gets one worktree forked from `WAVE_BASE`; its tasks dispatch one after another into
that same tree, each seeing its predecessor's work.

On the **pi binding**, dispatches are backgrounded per task (`SKILL.md:199-204`), so components
advance independently and the wall-clock model holds as stated.

On the **Claude binding**, dispatch is foreground, "one per task in a single message"
(`SKILL.md:193`). Foreground dispatches all return before the orchestrator's next turn, so chained
components advance in **lockstep rounds**: round *r* costs the maximum over components of that
component's *r*-th link. Components `A=[30,5,5]` and `B=[5,30,5]` minutes give a makespan of 65
rather than the 40 an independent-chaining model predicts.

This is accepted rather than fixed. Backgrounding the Claude binding is precisely what the recorded
incident warns against — "3/3 captains stalled on background-dispatch re-invocation"
(`docs/quirk/specs/2026-07-21-sdd-captain-control-plane-design.md:288`) — and PR #35 kept that
binding foreground deliberately. The preview states the lockstep cost instead of overstating the
gain. Lockstep is still never slower than today's collapse rule.

### Step 6 — audit, accept, commit, merge

The wave-end barrier is **unchanged**. Nothing commits until every component has returned, and the
wave-end HEAD-check and scope audit over all live trees plus the main tree remain authoritative.
Everything PR #35 established holds; wider waves ride the same single pass.

Two things change inside a component:

**Mid-chain acceptance and audit.** As each task in a chain completes, that task's acceptance
commands run and its scope audit runs against its **own** `scope.files`, with the incremental diff
snapshotted for attribution. This restores fail-fast: without it, a task-1 defect propagates
through tasks 2–3 and the retry rule "Task acceptance fails → do not commit; retry once; then stop
and ask" (`SKILL.md:514`) blames task 3 for task 1's cause — attribution is not merely lost but
wrong. It also preserves the per-task scope check that a union-scope audit cannot perform: a
union audit cannot see task 1 writing into a file that belongs only to task 3's scope.

**The commit unit is the component.** The mid-chain passes gate progress, not commits. A live pi
sibling can contaminate a tree after a mid-chain pass has run, so the wave-end re-audit stays
authoritative and the component commits once, as a unit, after the barrier. This mirrors the
existing rule that a retried task re-enters at the HEAD-check (`SKILL.md:317-322`).

What is given up is bisect granularity: history resolves to the component, not the task. That is
accepted.

### writing-plans — Granularity Economics

`skills/writing-plans/SKILL.md:115` currently reads "Split only when the result lands tasks in
**different waves** and therefore buys real parallelism." Under partitioning a split can buy
parallelism *within* a wave, so the rule must say the halves land in different **components**.

Stated as "different waves" the bullet would now advise merging tasks that partitioning could have
run concurrently — actively working against this change.

The same correction applies to `skills/writing-plans/SKILL.md:148` ("Any shared path forces the
wave to run sequentially") and its mirror at `SKILL.md:165-166`. This is not cosmetic: while the
rubric teaches the collapse rule, plan authors keep defensively encoding overlap as `dependencies`
to avoid collapsing a wave, recreating exactly the DAG depth the edge audit then has to strip. The
model is fixed at its source, not only in the executor.

`skills/executing-plans/SKILL.md` is verified to still read correctly against the shared rubric
edit. It has no waves, so partitioning is irrelevant to it, but it runs writing-plans in full and
therefore inherits the wording change.

## Behavior and scenarios

**Six tasks, one overlapping pair.** Today: 6 sequential dispatches, cost ΣDᵢ. After: 5 concurrent
components, the pair chained in one tree, cost max over components. At ~15 min per task, ~90 min
becomes ~30 min.

**A plan whose only dependency edge was declared for file overlap.** Today: 2 waves, 2 dispatch
rounds, and 1 checkpoint review between them. After: the edge is demoted, both tasks land in one
wave and one component, ordering preserved — 1 wave, 0 checkpoints.

**A genuine chain.** Partitions to depth N, width 1. The preview surfaces it once and names the
forcing edges. Nothing is auto-re-planned.

**A plan already fully disjoint per wave.** Partitioning changes nothing; the run pays only the
in-context rubric cost at Step 3, which dispatches nothing.

**Task 3 of a component fails acceptance.** The mid-chain pass catches it at task 3's own boundary
with tasks 1–2 already individually accepted and attributed. Retry applies to task 3. If it fails
again the run stops and asks, with the component uncommitted and its tree preserved.

**A task-1 defect that only manifests later.** Task 1's own acceptance passes; the wave-end audit
and the branch-level review loop remain the backstop, exactly as the core principle states.

## Scope and non-goals

**In scope**

- `skills/subagent-driven-development/SKILL.md`: Steps 3, 4, 5, 6, plus Failure routing and Red
  Flags rows for the new states.
- `skills/writing-plans/SKILL.md`: Granularity Economics and the Task Independence wording.
- `skills/executing-plans/SKILL.md`: verification only, against the shared rubric edit.

**Non-goals**

- The backend record, the pi binding, and the wave-end barrier from PR #35 — untouched.
- Reviewer selection, adjudication, and the final review loop — untouched.
- Auto re-decomposition of a chain.
- Per-wave or per-task backend selection — still one choice per run.
- Backgrounding the Claude implementer binding.
- Restoring per-task commit granularity inside a component.

## Decisions Locked

**wave-partitioning**

- Step 4 partitions the wave instead of collapsing it on any overlap.
- Grouping is by connected components of the scope-conflict graph — deterministic and maximal.
- One worktree per component; its tasks chain into that same tree.
- The **authoritative** HEAD-check and scope audit run once, after the whole wave returns —
  unchanged from PR #35. Mid-chain audits (below) gate a chain's progress; they do not replace it.

**decomposition-rubric**

- Step 3 runs `quirk:writing-plans` as its in-context rubric.
- The plan-document-reviewer carve-out survives and is stated explicitly.
- Granularity Economics is corrected from "different waves" to "different components".
- `executing-plans` is verified against the shared edit; no SDD-specific changes there.

**wave-barrier-cost**

- Soft cap of ~4–6 concurrent live trees, recorded when it binds.
- Overflow queues inside the same wave, never spilling into a new one.
- Zero checkpoints on a single-wave run is accepted as the core principle working as designed.
- `gtimeout 1800` is unchanged.

**dependency-discipline**

- Dependency edges are audited for semantic motivation before waves are computed.
- An overlap-only edge is **demoted** to an intra-component ordering constraint, not dropped.
- The projected wave shape is reported and journaled before dispatch.
- A pure chain is surfaced once for the user, never auto-re-decomposed.

**commit-and-audit granularity**

- Each task in a chain gets its own acceptance run, scope audit, and diff snapshot as it completes.
- The commit unit remains the component, at the wave-end barrier.
- Bisect granularity drops to the component; accepted.

**lockstep**

- Chained components advance in lockstep rounds on the foreground Claude binding; accepted.
- The wave-shape preview states the lockstep cost rather than overstating the modeled gain.

## Industry Insights

External research swarms (brainstorming Phases A–C) were **not run** — this session's operating
instructions bar dispatching agents unless the user asks. The design is instead grounded in
in-repo evidence and one requested adversarial review.

- The mechanism has an in-skill precedent: Step 9 already groups by connected components of write
  scope and dispatches one worker per component in parallel (`SKILL.md:449-452`, `:467-468`). The
  change is a consistency repair, not an invention.
- The rubric misalignment is directly observable: `executing-plans:52` runs writing-plans in full;
  `SKILL.md:149` borrows only the field schema.
- **Adversarial review (Fable subagent, user-requested).** Verdict: faster for the population the
  current rule punishes, with three required repairs — all three adopted here. Its most important
  correction was on the wall-clock model: the baseline for an overlapping wave is ΣDᵢ, not a
  narrower max, so "widening a wave raises the expected max" never bites; sum ≥ max always, making
  partitioning a strict per-wave improvement. It also identified that connected components
  guarantee co-location but not order (driving the demote-don't-drop decision), that unrepaired
  component-level acceptance was "the one configuration where the proposal regresses outright", and
  the foreground-lockstep limit on the Claude binding. All citations were verified against the
  files before adoption.

## Deferred Ideas

- **Backgrounding the Claude implementer binding** to give true per-component chaining on both
  backends. Deferred: contradicts the recorded 3/3 background-dispatch stall, and warrants its own
  reliability work rather than riding along here.
- **Diff-size-triggered mid-wave checkpoints** to compensate for checkpoint erosion on wide
  single-wave runs. Rejected for now — invents a new trigger, and a reviewer cannot read a
  half-finished wave's tree.
- **Per-task commit granularity inside a component**, via committing between chain steps with the
  audit deferred to wave end. Rejected: forces the audit from a working-tree diff to a commit range
  and breaks the `TASK_HEAD` check.
- **Per-task elapsed-time reporting at the barrier** so slow tasks get re-scoped next run. Pure
  observability; not needed for this change.

## Glossary

- **Wave** — the set of tasks whose dependencies are satisfied. Wave count is the depth of the
  dependency DAG.
- **Component** — a connected component of the scope-conflict graph: a maximal set of tasks reachable
  from each other through `scope.files` intersections. Serialized internally, concurrent with other
  components. Already this skill's term for the same grouping applied to fixers.
- **Scope-conflict graph** — node per task in a wave, edge whenever two tasks' `scope.files`
  intersect.
- **Demoted edge** — a `dependencies` edge found to be motivated only by file overlap. Removed from
  the wave graph, retained as an ordering constraint inside its component.
- **Width cap** — the soft bound (~4–6) on concurrent live worktrees in a wave.
- **Lockstep round** — on the foreground Claude binding, one synchronized advance of every chained
  component; the round costs the maximum over components of that round's link.
- **Barrier** — the wave-end synchronization established by PR #35: no audit or commit until every
  worker in the wave has returned.

## Status & amendments

**Status:** Draft — approved in brainstorming, pending user review.

**Amendments:**

- *2026-08-20* — Decision 3 (commit unit) amended after adversarial review. Originally locked as a
  single component-level acceptance and audit; amended to run per-task acceptance, scope audit, and
  diff snapshot mid-chain, with the commit still held to the wave-end barrier. Reason: propagated
  defects and inverted retry attribution under `SKILL.md:514`.
- *2026-08-20* — Decision 6 (bogus dependency edges) amended after adversarial review. Originally
  locked as dropping an overlap-motivated edge on the argument that partitioning serializes those
  tasks anyway; amended to demotion. Reason: connected components guarantee co-location but not
  order, so deletion can lose a genuine ordering constraint.
- *2026-08-20* — Lockstep on the foreground Claude binding recorded as a new accepted limitation,
  with the wave-shape preview required to state it.
