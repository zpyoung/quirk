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
- **Two-report contract.** The captain reports upward exactly twice:
  1. `MERGE_READY` — spec-compliance PASS + green build (contract confirmed).
  2. `CHAIN_COMPLETE` — trailing passes and fixes done; includes the adjudication log,
     per-stage timestamps, and any ledger entries.
- **Model:** captains run on sonnet (orchestration-tier routing).
- **Worker dispatch mechanism:**
  - *Pi path:* captains dispatch through the **quirk:pi-dev ladder** — the pi-dev skill
    recipe first, falling back to `pi-watch`, falling back to raw `pi -p`.
  - *Claude path:* nested agent dispatch where the harness allows it; else headless
    `claude -p` via Bash. The captain template includes a preflight check that picks the
    mechanism before the first dispatch.
- **Instrumentation:** captain reports carry per-stage timestamps (dispatch → DONE →
  reviews → fixes → MERGE_READY → CHAIN_COMPLETE); the orchestrator aggregates a
  latency table into the run summary so the next optimization round has a profile.
- **Fallback:** if no captain can be dispatched (harness restriction), the orchestrator
  runs the captain protocol inline — the current flat chain, documented in one
  paragraph, no longer the primary path.

### 2. Chain economics (inside the captain)

- **Codex adversarial scales by diff size.** Per-task Codex runs only when the task's
  diff crosses a threshold — default **>150 changed lines or touches a
  `CONTRACT:`/`SCHEMA:` surface** (tunable). Below threshold, the task is queued for the
  **branch-level adversarial pass** that runs alongside the final whole-branch review.
- **Reviewers attach patches.** Reviewer templates gain a required *Suggested patch*
  block for LOW/MEDIUM and mechanical-HIGH findings. The captain applies these directly
  and verifies by diff-read — extending PR #24's fully-specified-gap exception. The fix
  worker is reserved for CRITICAL and judgment-requiring findings.
- **Captain adjudicates; orchestrator audits.** The captain adjudicates all findings
  (fresh context, not the implementer) and records accept/reject reasoning in a
  machine-readable adjudication log. The orchestrator spot-audits the log at merge time
  and may reopen a call.
- **Risk-tier honesty** (`writing-plans` change): every `risk: logic` tag requires a
  one-line rationale; untagged tasks still default to `logic`. The plan-document
  reviewer checks for missing rationales.

### 3. Merge lane, trailing reviews, speculation

- **Merge on `MERGE_READY`,** not chain completion: the fast spec pass + green build
  gate the rolling merge. Quality/Codex continue as **trailing reviews** after merge.
- **Worktree tears down at merge.** Trailing reviewers read the task's immutable commit
  SHAs from the parent repo — no worktree needed.
- **Trailing fixes** land via a micro-branch from the parent tip: the captain requests
  it, the orchestrator creates it (serialized `git worktree add`, per the PR #24 lock
  rule), and it merges through the same serialized rolling-merge lane. No captain ever
  edits the parent branch directly.
- **Wave boundary =** all wave captains at `CHAIN_COMPLETE` + trailing fixes merged +
  the integration build/test (unchanged from PR #24). Any CRITICAL/HIGH still open at
  the boundary is resolved per §4 (auto-resolve + ledger) before the next wave starts —
  the boundary never idles on a human.
- **Speculative dependent start.** Dependents branch from the upstream task branch at
  the **implementer-DONE commit** — before spec confirmation. The existing
  contract-invalidation rule handles corrections (upstream captain notifies the
  orchestrator; the orchestrator triggers the dependent's re-check). The **early-merge
  barrier holds**: a speculative dependent never merges before its upstream has merged.

### 4. Escalation auto-resolve + audit

Unchanged gates (user chose to keep): the runtime-selection prompt at Step 0, and the
serial plan-review gate before wave 1.

All other escalation classes **auto-resolve with a recorded conservative default** so
the run never idles on a human:

| Escalation class | Auto-resolution | Record |
| --- | --- | --- |
| `NEEDS_CONTEXT` | Captain derives the answer from spec/codebase; if underivable, makes the most conservative assumption | Assumption noted in captain report |
| Plan-vs-spec conflict | Follow `logic.md` Decisions-Locked | Dated entry in the logic spec's Amendments log |
| Capped-out CRITICAL (post 2-cycle Codex cap) | Orchestrator applies the safest fix interpretation and merges | Ledger entry tagged `AUTO-RESOLVED-CRITICAL` |

**Guardrails** (this reverses PR #24's hard block on unresolved CRITICALs — the audit
trail is mandatory, not optional):

1. Every auto-resolution lands in the unresolved-findings ledger.
2. The final whole-branch reviewer **must** re-examine each `AUTO-RESOLVED-CRITICAL`
   entry; its prompt receives the ledger verbatim (as in PR #24).
3. The run summary lists all auto-resolutions at the top, before any other content.

## Decisions Locked

**Quality-vs-speed budget**
- Codex adversarial: per-task only above the diff threshold; otherwise branch-level.
- Merge gates on spec-PASS + green build; quality/Codex trail as fix commits.
- Reviewers attach patches for LOW/MEDIUM + mechanical-HIGH; captain applies directly.
- Every `risk: logic` tag needs a planner rationale; untagged defaults to `logic`.

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
- Pi-path dispatch: pi-dev skill → `pi-watch` → `pi -p` ladder (user amendment).

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

## Deferred Ideas

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
- `skills/writing-plans/SKILL.md` — `risk: logic` rationale requirement.
- `skills/writing-plans/plan-document-reviewer-prompt.md` — check risk rationales.
