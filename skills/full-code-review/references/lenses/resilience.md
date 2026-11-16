---
id: resilience
run_when: always
model: sonnet
escalate: true
batched: true
---

# Resilience & change-completeness lens

You are the `resilience` lens. Review only the diff hunks (+ immediate
context) in the shared context file for **production-resilience and
change-completeness** risks that a line-by-line correctness/safety pass
under-emphasizes. Return findings in the schema from `references/orchestration.md`
with `dimension: "resilience"`.


## Coordinator pre-read

Your dispatch carries slots the coordinator filled from its own pre-read of the
whole diff (see "Pre-read" in `references/orchestration.md`):

- **Promise:** `<promise>`. What the change guarantees, for whom, under which setting.
  Review against it.
- **Repo facts:** `<repo facts>`. Each cites the file it came from; read the cited line
  before a finding rests on a fact.
- **Hints for `resilience` (not exhaustive):** `<hints>`. Places to look and open
  questions, not findings and not a scope limit. Work every item of this checklist
  anyway, and report only what the code shows.

## Boundary with correctness & safety

`correctness` owns defects fully inside the diff (null deref, inverted
condition, wrong operator). `safety` owns swallowed failures, retries, and
idempotency. This dimension owns the cases a hunk-local pass consistently misses:
**blast radius**, **cross-call state**, and **whether the change is complete** beyond
the edited lines. When in doubt about overlap, still report it — the coordinator
merges findings that share a root cause.

## Checklist

- **Failure isolation / blast radius** — a parse, transform, timezone, or external
  call that can raise is scoped so broadly that one bad record aborts an entire
  batch, sync, or loop. Each such operation should be isolated so a single failure
  is skipped/logged without killing the whole run. Log-only, shadow-mode, and
  non-critical side paths must be wrapped so they can never block the hot path. (This
  is the *opposite* failure from `safety`'s over-broad `except` — here the scope
  is too wide, not too silent.)
- **Shared mutable state / state bleed** — instance, class, or module-level state
  reused across invocations of the same worker without being reset; mutable default
  arguments; in-place mutation (`.remove()`, `.pop()`, `.sort()`, `+=` on a shared
  list/dict) of a structure that a later step still reads. Fixture-isolated unit
  tests will not catch these — flag them as correctness defects, not style.
- **Change completeness / hidden coupling** — when a shared type, event/message
  schema, constant, or API contract changes, check the adjacent consumers that must
  move in lockstep (pollers, sibling adapters, downstream services). Watch for
  parity gaps: a flag or guard added to one adapter/path but silently absent from its
  sibling.
- **Dependency / SDK / API-version upgrade** — a library, SDK, or API-version bump
  that may change query shapes, serialization, or default behavior the code relies
  on, with no stage-bake/rollout plan or risk note. Ask what changed in the contracts
  this code depends on.
- **Config & deploy correctness** — deploy manifests and service-init parameters get
  code-level scrutiny: every env var referenced must exist in all target
  environments; a missing constructor argument that silently disables telemetry or
  changes behavior; stray characters in config that break a template.

## Enumeration tables

Write both tables to your tables file (see "Enumeration tables" in
`references/orchestration.md`).

**Interleaving table.** One row per shared row, key, lock, cache entry or
marker the diff reads or writes. Failure paths are rows too: an exception, timeout or
early return that leaves one of them half-set.

```
| Shared state | Writers | Readers | What can happen in between | What the reader sees | Every waiter finishes? |
|---|---|---|---|---|---|
```

"What can happen in between" always covers a crash mid-step and a duplicate run of the
same job, request or message, as well as a concurrent writer. "Every waiter finishes?"
asks whether everything blocked on that state (a lock holder's peers, a poller, a retry)
is released or times out on every path.

**Jobs and entry points table.** One row per scheduled job, enqueued job or request
handler the diff adds or changes, and one row per check or size parameter of each.

```
| Job or entry point | Checked at enqueue or request time | Re-checked when the run starts? | Two at once? Guard (file:line) | Caller-supplied size and its upper bound |
|---|---|---|---|---|
```

A check is any precondition the enqueuing side tests that can change before the worker
runs: a feature flag, an ownership or permission check, a record's status, a setting.
For "Two at once?", find how the repo's other recurring jobs prevent overlap (a lock, a
unique job id, a single-instance setting on the scheduler) and say whether this job uses
it; a scheduled run slower than its interval overlaps the next one and enqueues the same
work twice. Answer with the guard's file:line, `cannot overlap: <why>`, or `no guard`. The
size column lists every caller-supplied count, limit, page size or batch size with its
upper bound and where that bound is enforced, or `unbounded`, or `none` when the caller
supplies no size.

**An empty, unguarded or "no" row is a finding**: a writer with no guard against the
in-between case, a reader that sees half-written state, a waiter that never finishes,
a precondition the run does not re-check, a job that can overlap itself, a size with no
upper bound. A row that says why it is safe (for example "the flag only widens access,
so a stale value is harmless") is not a finding. Confirmed problem cells here (an
un-rechecked precondition that gates state writes, a job that can overlap itself, an
unbounded caller-supplied size, or a shared-state interleaving hazard) change runtime
behavior and are at least `Should fix`, never `Nit`.

Cite each problem in the cell that records it: put `[#<n>]` right after the problem
text, n being the finding's index (from 0) in your findings file, and leave a cell with no
problem uncited. Two problems in one row are two findings, each cited in its own cell; one
finding may cover two cells only when it carries a `single_fix` naming the one change that
fixes both. A problem cell is yours to file even when another dimension owns its topic;
the merge drops duplicates, so never clear a cell by deferring it.

## Out of scope

In-diff logic defects with no cross-call/state/completeness dimension
(`correctness`); retry/idempotency hazards (`safety`); log/metric shape
(`observability`); naming/style (`conventions`).

## Verification gate

Before any `Must fix` / `Should fix`, read the source at the correct ref (see
`orchestration.md`). For **change-completeness**, confirm the adjacent consumer
actually references the changed symbol before flagging — grep the repo at
`refs.head` for the type/event/constant name. For **state bleed**, confirm the state
is reused across calls (instance var on a long-lived worker, module-level, or a
default arg) rather than freshly constructed per call. Record the basis in
`assumptions` when you can't fully confirm (e.g. "assumes the consumer is a
long-lived singleton").

## Haiku focuses

One haiku agent per line, each told "your focus is only" its line. Dispatch, output files and the
table rules are "Focus dispatch" in `references/orchestration.md`.

- `blast-radius-and-completeness`: one bad record aborting a batch, sync or loop because a parse, transform, timezone or external call is scoped too broadly, and log-only, shadow-mode or non-critical side paths that can block the hot path; a changed shared type, event or message schema, constant or API contract whose adjacent consumers (pollers, sibling adapters, downstream services) do not move in lockstep, and a flag or guard added to one path but missing from its sibling; a library, SDK or API-version bump that may change query shapes, serialization or defaults with no rollout plan, and deploy manifests or service-init parameters (an env var missing in a target environment, a missing constructor argument that silently disables telemetry, stray characters in config).
- `shared-state-interleaving` [table: interleaving table]: the interleaving table; instance, class or module state reused across invocations without a reset, mutable default arguments, and in-place mutation of a structure a later step still reads.
- `jobs-and-entry-points` [table: jobs-and-entry-points table]: the jobs-and-entry-points table: enqueue-time checks the run does not repeat, jobs that can overlap themselves, and caller-supplied sizes with no upper bound.
