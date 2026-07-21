# SDD Captain Control Plane — Wall-Clock Round 2

**Date:** 2026-07-21
**Status:** Approved (design), pending implementation
**Prior art:** PR #24 (concurrent reviews, consolidated fix, risk tiers, `.contract` early-start, verification economics, dispatch hygiene)

## Problem

After PR #24, `quirk:subagent-driven-development` runs are still too slow on the wall
clock. The remaining serial costs are structural, not incremental:

1. **Orchestrator turns on every critical path.** Each task chain waits on ~4–6 top-level
   orchestrator turns (dispatch, adjudicate, fix dispatch, discrepancy check, re-review,
   merge), and one orchestrator serializes event handling for all parallel chains — N
   concurrent tasks queue behind a single control loop.
2. **The slowest reviewer gates every merge.** Rolling merge waits for the full chain
   (spec + quality + Codex xhigh + fixes) to PASS; dependents and the parent branch wait
   with it.
3. **Every accepted finding costs a full round trip** (fix worker + discrepancy check +
   possible re-review), even for trivially-specified fixes.
4. **Human gates stall the run** when the user steps away (escalations idle everything).

## Approach (chosen)

**Restructure around per-task captain sub-orchestrators** (Approach B). The per-task
chain moves wholesale into a captain prompt template; the top orchestrator shrinks to
waves, captain dispatch, a serialized merge lane, adjudication audits, and the
escalation ledger. The flat chain survives only as a degraded inline fallback.

Rejected alternatives:
- **A: Additive captain mode** beside the flat chain — two control planes to maintain,
  skill grows past 900 lines.
- **C: Deterministic Workflow-engine core** — strongest wall-clock in the 2026
  literature, but harness-dependent and the largest rewrite. Deferred (see Deferred
  Ideas).

## Design

### 1. Captain control plane

- New `assets/captain-prompt.md` + `assets/pi-captain-prompt.md`: a per-task
  sub-orchestrator that runs the full chain internally — implementer → concurrent
  reviewers (per risk tier) → adjudication → patch-apply / fix-worker → targeted
  re-review — with **no top-orchestrator turn between stages**.
- **Milestone reports + exception events.** The captain reports two milestones on the
  happy path:
  1. `MERGE_READY` — readiness evidence bound to a specific **candidate SHA**, plus the
     pre-merge adjudication log (so the orchestrator's merge-time audit has material).
     Readiness is defined **per effective risk tier**: `logic`/`pattern` = spec-compliance
     PASS + green build; `mechanical` (no reviewers) = the task's declared acceptance
     evidence + green build.
  2. `CHAIN_COMPLETE` — trailing passes and fixes done; full adjudication log,
     per-stage timestamps, ledger entries.

  Plus a small closed event set (not free-form messages), in two classes:
  - *Progress events* the orchestrator needs for branching and the merge lane:
    `IMPLEMENTER_DONE` (speculative-fork point, §3), `STUB_READY` (earliest fork point,
    §5), `REBASE_REQUEST` (pre-merge chain done — asks the merge lane for a candidate
    SHA; see §3's handshake).
  - *Exception events*: `READINESS_REVOKED` (late CRITICAL/behavior finding invalidates
    a prior `MERGE_READY`), `CONTRACT_CORRECTED` (dependents must re-check),
    `BRANCH_REQUEST` (trailing-fix micro-branch), `ESCALATION` (feeds §4).
- **Durable artifacts (crash safety, minimal).** Captains write reviewer outputs, the
  adjudication log, and ledger entries to run-scratch files *as they are produced*, not
  only at report time. If a captain dies mid-chain, the orchestrator adopts the orphaned
  chain from those artifacts and resumes or rolls back the merge. (Heartbeats,
  stuck-detection, and the rest of robustness group C remain deferred.)
- **Model:** captains run on sonnet (orchestration-tier routing).
- **Worker dispatch mechanism:**
  - *Pi path:* captains follow **quirk:pi-dev doctrine** — `pi-watch` is the canonical
    dispatch tool; raw `pi -p` only per pi-dev's documented escape hatches.
  - *Claude path:* nested agent dispatch where the harness allows it; else headless
    `claude -p` via Bash.
  - **Captain launcher requirement:** the implementation must ship a tested launcher per
    supported path — capability probe *before* the first dispatch (a probe cannot
    conjure a missing nested-dispatch capability; it selects the fallback), hardened
    headless recipe (timeouts, exit-code capture, output framing, child cleanup) in the
    style of pi-dev's canonical recipe. This is the riskiest feasibility item and lands
    in Delivery Phase 1 (see **Delivery Phases**).
- **Instrumentation:** captain reports carry per-stage timestamps (dispatch → DONE →
  reviews → fixes → MERGE_READY → CHAIN_COMPLETE); the orchestrator aggregates a
  latency table into the run summary so the next optimization round has a profile.
- **Fallback:** if no captain can be dispatched (harness restriction), the orchestrator
  runs the captain protocol inline — the current flat chain, documented in one
  paragraph, no longer the primary path.

### 2. Chain economics (inside the captain)

- **Codex adversarial scales by diff size.** Per-task Codex runs only when the task's
  diff crosses a threshold — default **>150 changed lines or touches a
  `CONTRACT:`/`SCHEMA:` surface** (tunable). Deterministic accounting: changed lines =
  `git diff --numstat` added+deleted against the task's fork base; "touches a surface" =
  the diff modifies any hunk containing a `CONTRACT:`/`SCHEMA:` anchor or any file the
  plan lists under a contract. Below threshold, the task is queued for the
  **branch-level adversarial pass**, which is a defined protocol, not a vague fallback:
  bound to explicit base/head SHAs, its prompt receives the aggregated contracts of all
  queued tasks plus the unresolved-findings ledger, and its findings go through the same
  adjudication → fix → re-review loop (2-cycle cap) before the run can finish.
- **Reviewers attach patches.** Reviewer templates gain a required *Suggested patch*
  block for LOW/MEDIUM and mechanical-HIGH findings. The captain applies these directly
  under hard guards — this deliberately extends PR #24's fully-specified-gap exception,
  and the guards are what keep it from becoming "apply arbitrary untrusted patches":
  size cap (≤ ~20 lines), `git apply --check` against the current tree before applying,
  patch paths must be inside the task's `scope.files` and outside every
  `scope.never_touch`, and the task's affected acceptance checks re-run after apply.
  Any patch that changes behavior, an exported contract, or crosses files triggers
  normal re-review regardless of severity. The fix worker is reserved for CRITICAL and
  judgment-requiring findings.
- **Captain adjudicates; orchestrator audits.** The captain adjudicates all findings
  (fresh context, not the implementer) and records accept/reject reasoning in a
  machine-readable adjudication log. The orchestrator spot-audits the log at merge time
  and may reopen a call.
- **Risk-tier honesty** (`writing-plans` change): captain-mode plans require an
  **explicit `risk` field on every task** (no silent default — omission is a plan-review
  finding), with a one-line rationale for **every** tier. Downgrades (`pattern`,
  `mechanical`) need the strongest justification, since they remove review passes. The
  plan-document reviewer checks presence and rationale quality.

### 3. Merge lane, trailing reviews, speculation

- **Merge on `MERGE_READY`,** not chain completion — but readiness attaches to a
  **candidate SHA produced after the merge-lane rebase**, not the pre-rebase tree. The
  handshake (breaks the request/readiness circularity): captain finishes its pre-merge
  chain → emits `REBASE_REQUEST` → the orchestrator's serialized merge lane rebases the
  task branch onto the parent tip and returns the **candidate SHA** (if any conflict
  fired or the range-diff is non-trivial, the lane returns REBASE_DIRTY instead and the
  captain re-verifies before re-requesting) → captain runs **fresh build/spec
  attestation on the exact candidate SHA** → emits `MERGE_READY(candidate)` → the
  orchestrator merges, provided the parent tip hasn't advanced past the candidate's
  base (if it has, the lane re-runs the handshake). Quality/Codex continue as
  **trailing reviews** after merge.
- **Worktree tears down at `CHAIN_COMPLETE`,** not at merge — trailing reviewers keep a
  leased, read-only view of the exact reviewed tree; no reviewer ever races a deleted
  filesystem. (The pooled worktree returns to the pool at `CHAIN_COMPLETE`; see §5.)
- **Trailing fixes** land via a micro-branch from the parent tip (captain sends
  `BRANCH_REQUEST`; the orchestrator creates it — serialized `git worktree add`, per the
  PR #24 lock rule) and merge through the same serialized rolling-merge lane. The fix
  worker **reinterprets each finding against the current parent tip** — reviewer patches
  were generated against an older task tree, and a cleanly-applying patch can still
  semantically undo intervening tasks' work. `git apply --check`, never-touch
  enforcement against other tasks' files, and re-verification of every affected task
  surface (not just the originating task) are mandatory before the micro-branch merges.
  No captain ever edits the parent branch directly.
- **Wave boundary =** all wave captains at `CHAIN_COMPLETE` + trailing fixes merged +
  the integration build/test (unchanged from PR #24). Any finding still open at the
  boundary is resolved per §4's exhaustive table before the next wave starts — the
  boundary never idles on a human.
- **Speculative dependent start.** This **explicitly redefines plain-dependency start
  semantics** (PR #24: plain `dependencies: [T1]` waited for T1's full chain).
  Dependents now branch from the upstream task branch at the earliest safe point: the
  **`STUB_READY` contract-stub commit** when one exists (§5), else the
  **implementer-DONE commit** — both before spec confirmation. Plans can opt back into
  the old full-chain wait per dependency with `dependencies: [T1.full]`.
  - **Fork bookkeeping (rebase-replay guard):** the orchestrator records each
    dependent's exact `FORK_SHA` at branch time. Because merge-lane rebases rewrite
    upstream SHAs, a dependent must never run a plain `git rebase <parent-tip>` — it
    rebases with `git rebase --onto <parent-tip> <FORK_SHA>`, and the merge lane asserts
    the replayed range contains only dependent-owned commits before merging. This
    closes the sequence where obsolete pre-review upstream commits get silently
    replayed into the parent under the dependent's name.
  - **Merge barrier (strengthened):** a speculative dependent's merge waits for its
    upstream's **`CHAIN_COMPLETE`** — not merely its merge — because under
    merge-on-spec-PASS, "merged" no longer implies "fully reviewed", and a trailing
    semantic/security fix can invalidate a dependent without changing any exported
    signature. A behavior-changing trailing fix on the upstream **taints** every
    speculative descendant for re-check (`CONTRACT_CORRECTED` covers the
    signature-changing case; taint covers the rest). Later-wave speculative tasks
    inherit the same rule: start any time, merge only after all tainted/upstream chains
    complete.

### 4. Escalation auto-resolve + audit

Unchanged gates (user chose to keep): the runtime-selection prompt at Step 0, and the
serial plan-review gate before wave 1.

All other escalation classes **auto-resolve with a recorded conservative default** so
the run never idles on a human:

The table is **exhaustive by construction** — every failure/status class the skill can
produce has a defined row, and the default row is safe:

| Escalation class | Auto-resolution | Record |
| --- | --- | --- |
| `NEEDS_CONTEXT` | Captain derives the answer from spec/codebase; if underivable, makes the most conservative assumption | Assumption noted in captain report |
| Plan-vs-spec conflict | Follow `logic.md` Decisions-Locked | Dated entry in the logic spec's Amendments log |
| Capped-out CRITICAL (post 2-cycle Codex cap) | Orchestrator applies the safest fix interpretation and merges — subject to the verify-or-quarantine gate below | Ledger entry tagged `AUTO-RESOLVED-CRITICAL` |
| Capped-out HIGH | Carries forward in the ledger (PR #24 behavior, unchanged) | Ledger entry |
| Merge resolver `UNRESOLVABLE` | Park the task branch (worktree + conflict state preserved); run continues | Ledger entry + parked-task list |
| Failing baseline / worktree preflight | Park the affected task; run continues | Ledger entry |
| Runtime fallback exhausted (pi → Claude both dead for a role) | Park the affected task; run continues | Ledger entry |
| **Any class without a defined row** | **Park the task, run continues — never invent an undocumented default** | Ledger entry |

**Guardrails** (this reverses PR #24's hard block on unresolved CRITICALs — the audit
trail is mandatory, not optional):

1. Every auto-resolution lands in the unresolved-findings ledger.
2. The final whole-branch reviewer **must** re-examine each `AUTO-RESOLVED-CRITICAL`
   entry; its prompt receives the ledger verbatim (as in PR #24).
3. The run summary lists all auto-resolutions and parked tasks at the top, before any
   other content.
4. **Verify-or-quarantine gate:** an `AUTO-RESOLVED-CRITICAL` requires an independent
   reviewer PASS plus green verification **on the final branch SHA** before the run may
   report clean. **Only affirmative verification produces a clean finish** — failed
   verification, a confirmed defect, an unavailable reviewer, an inconclusive verdict,
   or verification that never ran all end the run **QUARANTINED** (branch intact,
   explicitly not "done"). Auto-resolve removes mid-run stalls; it never manufactures a
   clean bill of health.

### 5. Dispatch-latency reductions (round-2 research amendments)

- **Contract-first stubs with a `STUB_READY` gate.** When a task has dependents in a
  later wave, its captain's implementer commits the interface stubs (signatures/schemas
  matching the plan's `CONTRACT:` surface) as its **first commit**, before the full
  implementation. A stub commit is a valid fork base only when it passes the
  `STUB_READY` gate: typecheck/build green, baseline tests still green, and no callable
  placeholder behavior (stubs raise/return explicit not-implemented markers, never
  plausible fakes). If a green stub commit isn't achievable, the captain publishes a
  **contract artifact** (schema/signature file) instead of a branchable commit, and
  dependents wait for implementer-DONE. Dependents branch at `STUB_READY` — the earliest
  speculative start point (§3).
- **Resolve pi models once per run, dispatch pinned triples.** At run start the
  orchestrator resolves each role's alias via `pi-watch --check`/`--list-aliases` and
  records the resolved `provider/model:thinking` triple per role. Every subsequent
  dispatch uses the exact recorded triple (alias re-resolution per dispatch is the
  cold-start tax the kestrel profile measured on all 24 dispatches). On an auth/rate
  failure the orchestrator performs one recorded **re-resolution epoch** (re-check the
  alias, pin the new triple) rather than silent per-dispatch fallback. This inverts
  pi-dev's "hard-pinning is the exception" rule *within a run only*; freshness is
  preserved run-to-run.
- **Context manifests (not bare packets).** Workers receive a staged, provenance-bearing
  manifest: task text, contract, scope (`files` + `never_touch`), the applicable
  `CLAUDE.md` rules and tech-spec DO-NOT-CHANGE fences, acceptance commands, and the
  relevant SHAs. Redundant re-reads of the source documents the manifest distills are
  suppressed (CLI flags where supported), but workers **may** read sources on demand
  when the manifest proves insufficient — completeness beats purity.
- **Pre-warmed worktree pool with a lease/reset protocol.** The orchestrator provisions
  the wave's worktrees up front (serial `git worktree add`, as PR #24 requires) and
  reuses pooled worktrees across waves. Reuse is only sanctioned through the reset
  protocol: lease flag per worktree (no double-assignment); on return — assert no live
  worker process, `git rebase --abort`/`git merge --abort` if mid-operation,
  `git checkout --detach`, `git clean -fdx`, `git reset --hard <new-base>`, then assert
  clean `git status` + expected HEAD + baseline build before the next lease.
  Dependencies shared via copy-on-write (`cp -c` on APFS) or the pnpm store.
- **Merge-lane git hygiene.** `git config rerere.enabled true` with
  **`rerere.autoUpdate` OFF** — reused resolutions are surfaced for inspection in the
  merge lane, never silently staged. Each task branch rebases onto the parent tip before
  its rolling merge (with the `--onto <FORK_SHA>` discipline from §3 for speculative
  branches).

### 6. Decomposition upgrades (writing-plans)

- **Cohesion-aware partitioning.** During the File Structure pass, build a
  file-coupling map (imports/shared files) and partition the work to minimize cross-task
  coupling *before* declaring `independent`/`dependencies` and computing waves.
  Hub-file isolation is a **scored heuristic, not a mandate**: prefer assigning a hub
  change to the vertical slice that owns the behavior; carve a standalone hub task only
  when no single slice owns it, with explicit rationale and serialized integration —
  a mandatory hub task is horizontal decomposition through the back door. (Co-Coder,
  arXiv:2606.00953: up to 2.1× wall-clock on dependency-dense projects; parallelism
  without cohesion awareness can be worse than sequential.)
- **Vertical-slice discipline.** Decompose by user-visible behavior slices, not
  horizontal layers ("all API routes") — fewer inherent cross-wave dependencies.
- **Never-touch lists.** Each task declares `scope.files` (allowed) **and**
  `scope.never_touch` (forbidden — adjacent files the wave's other tasks own). Captains
  paste both into implementer prompts; negative scope beats positive scope because
  agents drift into adjacent files.
- **Single-implementer fast path = width-1, same machinery.** If partitioning cannot
  produce a wave of ≥2 disjoint tasks, run the **same captain state machine at
  concurrency width 1** — not a separate flat control plane (dual control planes were
  rejected in Approach A for exactly this maintenance cost). Task count alone is not the
  gate: two disjoint tasks are a valid width-2 wave. Per-task risk tiers, fresh context,
  and the report contract all still apply; only the parallelism is gone.

## Delivery Phases

Codex-max design review (2026-07-21, 22 findings, verdict CRITICAL_ISSUES — all
findings adjudicated; this spec revision incorporates the accepted set) established
that a single big-bang rewrite is unsafe. Delivery is staged so each phase is
independently shippable and testable:

1. **Phase 1 — Captains, conservative gates.** Captain control plane (launcher,
   milestone reports + exception events, durable artifacts, adjudication-with-audit)
   with the **existing pre-merge full-chain gate** — no trailing merge yet. This alone
   removes the orchestrator-turn tax and serialization.
2. **Phase 2 — Trailing merge + audit.** Merge-on-MERGE_READY with candidate-SHA
   attestations, trailing reviews on leased worktrees, trailing-fix micro-branches,
   exhaustive escalation table + verify-or-quarantine gate.
3. **Phase 3 — Speculation + pooling + hygiene.** STUB_READY speculative starts with
   FORK_SHA/`--onto` discipline and CHAIN_COMPLETE merge barriers; worktree pool with
   lease/reset protocol; rerere (autoUpdate off). Gated on git-topology integration
   tests for the §3 sequences.

writing-plans changes (§6) land alongside Phase 1 (they're upstream inputs and
backward-compatible).

## Validation Against a Real Session

The kestrel "kanban→list redesign" session (2026-07-20, 6h00m) was profiled
event-by-event against this design:

- 64% of wall-clock was human-in-the-loop (two ~103-min away gaps during brainstorming
  questions) — out of scope for this design by deliberate choice.
- Implementation + review took 101 min; this design's levers model out to **~55–60 min
  (40–45% reduction)**. Largest measured lever: speculative dependent start (37.5 min of
  trailing-tail delay observed; 25–35 min recoverable). Reviewer patches and
  merge-on-spec-PASS each 10–15 min (overlapping). Escalation auto-resolve: ~0 in this
  session (its value case is long unattended runs).
- Confirmed wave waste: two independent tasks (`T2`/`T5`) ran sequentially — the mode
  gates in this design would have overlapped them.
- Surfaced the pi cold-start tax that §5 now addresses.

## Decisions Locked

**Quality-vs-speed budget**
- Codex adversarial: per-task only above the diff threshold; otherwise branch-level.
- Merge gates on spec-PASS + green build; quality/Codex trail as fix commits.
- Reviewers attach patches for LOW/MEDIUM + mechanical-HIGH; captain applies directly.
- Captain-mode plans require an explicit `risk` field on every task, with a rationale
  for every tier (no silent default — superseded the earlier "untagged defaults to
  logic" form per design-review finding #22).

**Orchestration architecture**
- Per-task captain agents run the full chain; two-report contract.
- Captain adjudicates; orchestrator audits at merge.
- Dependents start speculatively at upstream implementer-DONE.

**Startup & human gates**
- Runtime-selection prompt: kept, every run (status quo).
- Serial plan-review gate: kept (status quo).
- Escalations: auto-resolve with recorded defaults — including capped-out CRITICALs,
  with the mandatory audit trail above.

**Approach**
- B: restructure around captains; flat chain becomes an inline fallback paragraph.
- Pi-path dispatch follows quirk:pi-dev doctrine: `pi-watch` canonical, raw `pi -p`
  only via pi-dev's escape hatches (user amendment, wording corrected per design
  review finding #18).

**Round-2 research amendments (approved 2026-07-21)**
- Group A — dispatch-latency fixes (§5): contract-first stubs, per-run alias pinning,
  minimal context packets, pre-warmed worktree pool, rerere + rebase-before-merge.
- Group B — decomposition upgrades (§6): cohesion-aware partitioning, vertical slices,
  never-touch lists, single-implementer fast path.
- Groups C (robustness guards) and D (brainstorming idle-while-away fix) were reviewed
  and deferred — see Deferred Ideas.

**Design-review adjudication (codex-max, 2026-07-21, approved)**
- Verify-or-quarantine gate on every `AUTO-RESOLVED-CRITICAL` (finding #2): auto-resolve
  stays, but a run cannot report clean without independent PASS + green verification on
  the final SHA.
- Minimal crash-safety persistence (findings #10/#16): durable per-stage artifacts +
  orphan adoption. Heartbeats/stuck-detection remain deferred with group C.
- Speculative start explicitly redefines plain-dependency semantics; `[T1.full]` opts a
  dependency back into the full-chain wait (finding #7).
- Staged delivery in three phases (finding #16) — see Delivery Phases.
- Remaining accepted findings folded into §§1–6: FORK_SHA/`--onto` rebase discipline,
  candidate-SHA attestations, CHAIN_COMPLETE worktree teardown and descendant-merge
  barrier, STUB_READY gate, patch-apply guards, exhaustive escalation table,
  context manifests, branch-level adversarial protocol, pool lease/reset protocol,
  rerere autoUpdate off, per-tier MERGE_READY, hub-isolation heuristic, width-1 fast
  path, explicit risk fields.

## Industry Insights

- **Hierarchical sub-orchestrators past ~5–8 workers**: flat single-orchestrator fan-out
  is an all-to-all bottleneck; delegation distributes coordination. (TrueFoundry 2026,
  Google ADK)
- **Deterministic backbones beat LLM-driven control loops** — control returns to the
  orchestrator only at intentional decision points. Captains approximate this within a
  skill; a full Workflow-engine core is the deferred end state. (Anthropic 2026
  guidance; LangGraph/Temporal two-layer pattern)
- **Speculative execution is where 2–5× latency wins live** — prefetching, staged
  parallel calls, reversible side effects. (MIT/Cornell Speculative Actions,
  arXiv:2510.04371; PASTE, arXiv:2603.18897)
- **Cloudflare production AI review** (48,095 MRs, Mar–Apr 2026): ~7 concurrent
  specialized reviewers, per-file scoping, structured cached findings → P50 3m39s, P99
  10m21s, $1.19/review; stalled-reviewer timeouts; only 0.6% human override.
  (blog.cloudflare.com/ai-code-review)
- **Deep review only pays on high-risk diffs** — Meta's semi-formal reasoning hit 93%
  accuracy but its latency pushes developers to route around it when applied uniformly.
  (InfoWorld 2026 coverage)
- **Reviewer-generated patches cut fix round trips** — Meta measured +19.75%
  ActionableToApplied after shipping patch-suggestion in all reviews.
  (arXiv:2507.13499)
- **Adversarial second-model review earns its cost** on architectural violations,
  negation-encoded constraints, and performance contracts — not on routine diffs.
  (asdlc.io adversarial-code-review)
- **Cohesion-aware partitioning beats naive decomposition**: up to 2.1× wall-clock, 14%
  pass-rate lift, 35% cost cut on dependency-dense projects; parallelism that ignores
  coupling can be worse than sequential. (Co-Coder, arXiv:2606.00953)
- **Contract/interface-first stubs enable true parallelism** — backend agents emit
  interface definitions that dependents consume directly. (Osmani, "Code Agent
  Orchestra"; multiple practitioner writeups)
- **Community-converged practices** (Reddit, 27 threads deep-read): file-ownership
  boundaries decided before dispatch (8+ independent posters); 4–6 concurrent agents
  before merge overhead dominates; never-touch negative scope lists; reviewers
  committing patches instead of prose; verify diffs, never agent summaries.

## Deferred Ideas

- **Robustness guards (round-2 group C, deferred by user):** wave width capped by
  review/adjudication throughput (community sweet spot 4–6 concurrent); stuck-agent
  detection via failure-signature hashing → fresh-context hint after 3 identical
  failures; hook-enforced tests-pass gate before implementer→reviewer handoff; per-wave
  append-only decision log against cross-captain drift.
- **Brainstorming idle-while-away fix (round-2 group D, deferred by user):** deliver
  queued research results and pre-draft artifacts while an `AskUserQuestion` is
  outstanding — the kestrel session's #1 sink (57% of wall-clock) lives in the
  brainstorming skill, not SDD.
- **Deterministic Workflow-engine core** (Approach C): encode the per-task chain as a
  harness Workflow/pipeline script — zero control-loop turns between stages. Revisit
  once captain-mode latency data exists.
- **Latency-evidence instrumentation as a first-class phase**: the user deselected
  measurement as a gray area; per-stage timestamps in captain reports are the
  lightweight substitute. If round 3 is needed, profile before designing.
- **Config-default runtime selection**: user kept the per-run prompt; revisit if the
  Step 0 stall proves material in the timestamp data.

## Files to Change

- `skills/subagent-driven-development/SKILL.md` — restructure per Approach B.
- `skills/subagent-driven-development/assets/captain-prompt.md` — **new**.
- `skills/subagent-driven-development/assets/pi-captain-prompt.md` — **new** (pi-dev
  ladder dispatch).
- `skills/subagent-driven-development/assets/{spec,code-quality}-reviewer-prompt.md` and
  pi variants — add *Suggested patch* block; dispatch-context now the captain.
- `skills/subagent-driven-development/assets/codex-adversarial-prompt.md` + pi variant —
  diff-threshold note; dispatch-context now the captain.
- `skills/writing-plans/SKILL.md` — explicit per-task `risk` field + per-tier rationale;
  cohesion-aware partitioning with the hub-isolation heuristic in the File Structure
  pass; vertical-slice discipline; `scope.never_touch` field; width-1 fast-path gate.
- `skills/writing-plans/plan-document-reviewer-prompt.md` — check risk-field presence
  and rationale quality, never-touch coverage, and partition cohesion.
- `skills/subagent-driven-development/assets/implementer-prompt.md` + pi variant —
  contract-first stub commit rule for tasks with dependents.
- `skills/using-git-worktrees/SKILL.md` (or SDD mode mechanics) — pooled worktree
  reuse/reset + copy-on-write dependency sharing.
