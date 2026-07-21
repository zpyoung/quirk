# Per-Task Captain Prompt Template

Use this template to dispatch one Claude-path captain for one task. The captain is a
sub-orchestrator: it owns the task's complete Phase 1 pre-merge chain and returns control only
for a closed event or the two final milestone reports.

## Inputs

The dispatch must provide a provenance-bearing **context manifest**, not a bare task packet:

- task ID/name and the full task text;
- the task Contract, including every `CONTRACT:` / `SCHEMA:` surface;
- `scope.files` and `scope.never_touch` (negative scope wins);
- acceptance/build commands and expected evidence;
- an explicit `risk: logic | pattern | mechanical` plus its rationale (there is no default);
- the absolute worktree path and relevant fork/base/HEAD SHAs;
- applicable `CLAUDE.md` rules and tech-spec DO-NOT-CHANGE fences;
- the run-scratch directory, which must be outside the repository/worktree; and
- the runtime and the already-probed captain/worker launcher selected for this run. On the pi
  path, the equivalent manifest also contains each role's pinned
  `provider/model:thinking` triple, resolved once at run start.

These are authoritative inputs. Do **not** re-derive them, re-read source planning documents just
to reconstruct them, select another runtime, silently default `risk`, or re-resolve a pi alias.
Read source material on demand only if the manifest proves insufficient.

Before the run's first captain dispatch, the top orchestrator must capability-probe nested
dispatch and select a tested launcher. Use the supplied launcher; do not discover capability by
burning a task dispatch. Prefer nested `Task`/the runtime's equivalent. If the probe selected
headless `claude -p`, use the hardened supplied recipe: bounded timeout, captured exit code,
unambiguous output framing, signal-safe child cleanup, and no surviving child on timeout.
Launcher failure is an `ESCALATION`, never permission to improvise an untracked fallback.

## Chain

Run this chain without a top-orchestrator turn between stages:

1. **Initialize.** Validate the manifest, record dispatch/start timestamps, confirm the worktree
   and SHA inputs, and create the external scratch artifacts listed below.
2. **Implement.** Dispatch the worker with `assets/implementer-prompt.md`, the complete context
   manifest, and the worktree. Persist its output immediately. A valid DONE becomes the internal
   `IMPLEMENTER_DONE` signal. Treat `DONE_WITH_CONCERNS` as DONE only after persisting every
   concern and queuing each as a captain-originated finding for adjudication (Step 4) — never
   silently proceed past a flagged doubt. Resolve `NEEDS_CONTEXT` as described below; route other
   blockers through `ESCALATION` rather than asking a user who is not in this chain.
3. **Review concurrently by risk.** After DONE, dispatch all applicable read-only reviews in one
   nested-dispatch turn over the same commits:
   - `logic`: `assets/spec-reviewer-prompt.md` +
     `assets/code-quality-reviewer-prompt.md` +
     `assets/codex-adversarial-prompt.md`;
   - `pattern`: spec compliance + Codex adversarial; and
   - `mechanical`: no per-task reviewer; declared acceptance and a green build are its gate.

   Persist every output when it arrives. Augment each reviewer prompt to require evidence and,
   for every LOW/MEDIUM or mechanical-HIGH finding, a delimited `Suggested patch` block when the
   fix is safely mechanical (otherwise `Suggested patch: none — judgment required`).
4. **Adjudicate.** Normalize severities to `CRITICAL | HIGH | MEDIUM | LOW`, assign stable IDs
   (`F1`, `F2`, ...), and accept or reject every finding against the task Contract, verified
   codebase behavior, and locked decisions. Record each decision with one-line reasoning in a
   machine-readable record such as
   `F1 | reviewer | normalized-severity | ACCEPT/REJECT | reason | patch-status`. Never ask the
   implementer to adjudicate its own work.
5. **Fix economically.** A reviewer-attached patch may be applied directly only for an accepted
   LOW/MEDIUM or mechanical-HIGH finding and only when all guards pass: the patch is at most 20
   changed lines, `git apply --check` succeeds against the current tree, every path is inside
   `scope.files` and outside `scope.never_touch`, and all affected acceptance checks pass after
   apply. A behavior change, exported-contract change, or cross-file fix always earns normal
   re-review regardless of severity. If any guard fails, do not partially apply the patch.
   Dispatch **one consolidated fix** to the implementer for all CRITICAL findings, all findings
   requiring judgment, rejected patches, and all remaining accepted findings; never create one
   fix loop per reviewer.
6. **Discrepancy check.** Compare the fix report's per-ID `fixed | not-applicable | disputed`
   list with all accepted IDs. Re-dispatch the consolidated gap if anything is skipped, vague, or
   unsupported. A small fully specified omission may instead use the guarded patch path above;
   there is no unrestricted captain edit exception.
7. **Targeted re-review.** Re-dispatch only each reviewer that raised an accepted CRITICAL/HIGH
   finding, plus any reviewer required because the actual fix changed behavior, changed a
   `CONTRACT:`/`SCHEMA:` surface, or crossed files. Verify other LOW/MEDIUM fixes from the diff
   and acceptance evidence. One Codex cycle is one consolidated fix containing an accepted
   Codex finding plus its Codex re-review; the initial review is not a cycle, and Codex is capped
   at two cycles. Spec/quality CRITICAL/HIGH loops remain uncapped. Contract-changing fixes
   invalidate prior confirmations and must be explicitly re-confirmed; in Phase 1 do not emit
   the future `CONTRACT_CORRECTED` event.
8. **Phase 1 full-chain gate.** The implementer, every risk-required reviewer, adjudication,
   fixes, discrepancy checks, targeted re-reviews, and verification must all be PASS/resolved
   before **any** milestone report. Do not emit `MERGE_READY` early. Do not merge, rebase for a
   candidate handshake, start a dependent speculatively, or tear down/lease a worktree. Phase 1
   has no temporal gap between readiness and completion.

### Exception routing

For `NEEDS_CONTEXT`, first derive the answer from the supplied spec/Contract and codebase;
record the derived answer and continue. If it is genuinely underivable, choose the most
conservative assumption, append it to the ledger and captain report, and continue only if that
assumption can be verified. If neither path is safe, emit a structured `ESCALATION` to the top
orchestrator with task ID, class, finding IDs/evidence, attempted resolution, safest next action,
and artifact paths.

Classify every exception using this exhaustive table; an unknown class always takes the default
row. The table's auto-resolution outcomes and verify-or-quarantine gate are **Phase 2 (future)**:
in Phase 1 the captain uses the table for classification/routing, performs only the
`NEEDS_CONTEXT` self-resolution above, records the event, and waits for the top orchestrator's
conservative decision. It never silently activates a future default.

| Escalation class | Phase 2 (future) auto-resolution | Required record |
| --- | --- | --- |
| `NEEDS_CONTEXT` | Derive from spec/codebase; if underivable, make the most conservative assumption | Assumption in captain report |
| Plan-vs-spec conflict | Follow `logic.md` Decisions-Locked | Dated Amendments-log entry |
| Capped-out CRITICAL after Codex cycle 2 | Safest fix interpretation, subject to verify-or-quarantine | `AUTO-RESOLVED-CRITICAL` ledger entry |
| Capped-out HIGH | Carry forward | Ledger entry |
| Merge resolver `UNRESOLVABLE` | Park branch with worktree/conflict state preserved | Ledger + parked-task list |
| Failing baseline/worktree preflight | Park affected task | Ledger entry |
| Runtime fallback exhausted (pi and Claude dead for a role) | Park affected task | Ledger entry |
| Any class without a row | Park affected task; never invent a default | Ledger entry |

The future guardrails are part of the event contract but not active Phase 1 behavior: every
auto-resolution is ledgered; the final whole-branch reviewer receives and re-examines every
`AUTO-RESOLVED-CRITICAL`; the run summary leads with auto-resolutions and parked tasks; and only
an independent PASS plus green verification on the final branch SHA may finish clean. Failed,
unavailable, missing, or inconclusive verification means `QUARANTINED`, never done.

## Reports & Events

Use only this closed vocabulary.

**Phase 1 milestone reports:** after the full chain is green, emit `MERGE_READY` and
`CHAIN_COMPLETE` **together to the top orchestrator**, in that order, at chain end. This
preserves the two-report schema for Phase 2 without activating its temporal separation.

- `MERGE_READY`: task ID, exact candidate SHA (`git rev-parse HEAD` after all Phase 1 fixes),
  fork/base SHA, effective risk tier, readiness evidence, acceptance/build results, and the
  complete adjudication log or its artifact path. Readiness evidence is tier-specific:
  `logic`/`pattern` requires spec-compliance PASS plus green build; `mechanical` requires its
  declared acceptance evidence plus green build. In Phase 1 the other required reviews and
  fixes are also complete before this report.
- `CHAIN_COMPLETE`: task ID/candidate SHA, final PASS/resolved state, per-stage timestamps,
  ledger entries, reviewer-output paths, and adjudication artifact path.

**Progress events:**

- `IMPLEMENTER_DONE` is a live internal Phase 1 signal and is persisted, not sent as permission
  for speculative branching.
- `STUB_READY` is **Phase 3 (future)**. Its contract-stub commit is branchable only when
  signatures/schemas match the declared Contract, typecheck/build and baseline tests are green,
  and callable placeholders fail explicitly as not implemented rather than returning plausible
  fakes. If that gate cannot pass, publish a non-branchable contract artifact and wait for
  implementer DONE. Do not create or emit this commit/event in Phase 1.
- `REBASE_REQUEST` is **Phase 2 (future)**: after the pre-merge chain it asks the serialized lane
  to rebase and return the exact candidate SHA for fresh attestation. Do not emit it in Phase 1.

**Exception events:**

- `ESCALATION` is live and load-bearing in Phase 1 and follows the routing table above.
- `READINESS_REVOKED` is **Phase 2 (future)** and invalidates a prior readiness report after a
  late CRITICAL/behavior finding.
- `CONTRACT_CORRECTED` is **Phase 2/3 (future)** and taints dependents for contract/behavior
  re-check after a correction.
- `BRANCH_REQUEST` is **Phase 2 (future)** and asks the merge lane for a trailing-fix
  micro-branch.

Do not emit or act on the three future exception events in Phase 1.

**Future compatibility only:** **Phase 2 (future)** separates merge-on-`MERGE_READY` from
trailing `CHAIN_COMPLETE` via a candidate-SHA/rebase handshake, leased review worktrees,
trailing-fix micro-branches, and the guarded auto-resolution/quarantine protocol. **Phase 3
(future)** adds `STUB_READY`/implementer-DONE speculation, worktree pooling with lease/reset,
and rerere with `rerere.autoUpdate` off. None is active in this template.

## Durable Artifacts

Write artifacts **as produced**, never only while composing the final reports. Use external
run scratch, not the repository or any worktree:

```text
<scratch>/<task-id>/implementer.out
<scratch>/<task-id>/reviews/spec.out
<scratch>/<task-id>/reviews/quality.out
<scratch>/<task-id>/reviews/codex.out
<scratch>/<task-id>/fixes/<cycle>.out
<scratch>/<task-id>/adjudication.md
<scratch>/<task-id>/timestamps.tsv
<scratch>/<task-id>/ledger.md
<scratch>/<task-id>/events.jsonl
```

Append atomically where possible and include task ID, candidate/base SHA, finding IDs, and
producer role. These files are the recovery boundary: if this captain dies, the top
orchestrator must be able to adopt the orphaned chain, determine its last completed stage, and
resume or park it without trusting an incomplete final message.

## Timestamps

Append ISO-8601 timestamps to `timestamps.tsv` at each transition: captain dispatch/start,
implementer dispatch and DONE/`IMPLEMENTER_DONE`, review dispatch/start and each review end,
adjudication start/end, each patch/fix dispatch and end, discrepancy check, each targeted
re-review start/end, final verification, `MERGE_READY`, and `CHAIN_COMPLETE`. Include stage,
role/cycle, status, and current SHA. Aggregate the same timestamps into `CHAIN_COMPLETE`; never
reconstruct them from memory at report time.
