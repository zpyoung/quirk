# Pi Per-Task Captain Prompt Template

Use this template to dispatch one pi-path captain for one task. The captain owns the complete
Phase 1 pre-merge chain and returns control only for a closed event or the two final milestone
reports. It follows **quirk:pi-dev** doctrine throughout.

## Inputs

The dispatch must provide a provenance-bearing **context manifest**, not a bare task packet:

- task ID/name, full task text, and task Contract, including every
  `CONTRACT:` / `SCHEMA:` surface;
- `scope.files` and `scope.never_touch` (negative scope wins);
- acceptance/build commands and expected evidence;
- an explicit `risk: logic | pattern | mechanical` and one-line rationale (no default);
- execution mode, absolute worktree path, required `FORK_SHA` (the exact commit this task or
  dependent branched from), and explicit base/HEAD SHAs;
- applicable `CLAUDE.md` rules and tech-spec DO-NOT-CHANGE fences;
- an external run-scratch directory and a per-run dispatch-config JSON path; and
- the per-role **pinned** `provider/model:thinking` triples for captain, implementer, spec
  reviewer, quality reviewer, Codex reviewer, and fix worker (the merge resolver triple is not
  part of this manifest — the top orchestrator's serialized merge lane dispatches that role
  directly, never the captain). Before the first dispatch, the top orchestrator
  capability-probed canonical `pi-watch`, then resolved each alias once at run start using
  `pi-watch --check` / `--list-aliases`.

These are authoritative inputs. Do **not** re-derive the manifest, silently default `risk`, or
run alias resolution inside this captain. Read source documents on demand only when the manifest
is insufficient. Never infer `FORK_SHA` from branch topology. Use the received pinned triples
and per-run config for every dispatch in this chain; any recorded re-resolution epoch belongs to
the top orchestrator, not a per-dispatch fallback here.

## Chain

Run this chain without a top-orchestrator turn between stages:

1. **Initialize.** Validate the manifest including required `FORK_SHA`, pinned triples, and
   dispatch config; record dispatch/start timestamps, confirm the worktree and SHA inputs, and
   create the external scratch artifacts below. Query `<run-dir>/run.jsonl` with
   `scripts/sdd-ledger query --type decision` and read other captains' decisions before
   dispatching the implementer.
2. **Implement.** Assemble a task/role-keyed prompt from
   `assets/pi-implementer-prompt.md` plus the context manifest, stage it outside the repository,
   and dispatch it with the pinned implementer triple. Persist output immediately. A valid DONE
   becomes internal `IMPLEMENTER_DONE`. Treat `DONE_WITH_CONCERNS` as DONE only after persisting
   every concern and queuing each as a captain-originated finding for adjudication (Step 4) —
   never silently proceed past a flagged doubt. Resolve `NEEDS_CONTEXT` through the exception
   rule below; route other blockers as `ESCALATION` rather than asking a user who is absent from
   this nested chain.
3. **Review concurrently by risk.** After DONE, bind `TASK_HEAD` to the exact task tree under
   review (`HEAD` on an own-branch/singleton path, or the recorded latest task-owned commit for
   `IN_PLACE_PARALLEL`). Compute the task diff against its supplied fork base by summing the
   numeric added+deleted columns from
   `git diff --numstat "$FORK_BASE" "$TASK_HEAD" -- "${SCOPE_FILES[@]}"`, where `SCOPE_FILES`
   is the manifest's list. Also inspect the changed
   hunks and Contract: a task touches a `CONTRACT:`/`SCHEMA:` surface when a modified hunk
   contains either anchor or the diff changes a file the plan lists under a contract. Dispatch
   per-task pi Codex only when the
   sum is **>150** or that surface test is true. If neither condition is true, Phase 1 gives this
   task **no Codex adversarial pass**. Append `CODEX-DEFERRED(<task-id>)` with the base/task SHAs,
   line count, and surface-test result to both the unresolved-findings ledger and adjudication
   artifact. The final whole-branch reviewer's prompt must receive the complete
   `CODEX-DEFERRED` list. The branch-level Codex protocol ships in **Phase 2 (future)**; do not
   claim or simulate that coverage in Phase 1.

   Stage and dispatch all applicable read-only reviews concurrently over the same commits:
   - `logic`: `assets/pi-spec-reviewer-prompt.md` +
     `assets/pi-code-quality-reviewer-prompt.md`, plus
     `assets/pi-codex-adversarial-prompt.md` only when the diff gate above passes;
   - `pattern`: pi spec compliance, plus pi Codex adversarial only when the diff gate passes; and
   - `mechanical`: no per-task reviewer; declared acceptance and green build are its gate.

   Persist each output on arrival. Augment each reviewer prompt to require evidence and, for
   every LOW/MEDIUM or mechanical-HIGH finding, a delimited `Suggested patch` block when the fix
   is safely mechanical (otherwise `Suggested patch: none — judgment required`).
4. **Adjudicate.** Normalize reviewer vocabularies onto
   `CRITICAL | HIGH | MEDIUM | LOW`: code-quality `Critical` → `CRITICAL`, `Important` → `HIGH`,
   and `Minor` → `LOW`; spec-compliance missing-requirement or extra-requirement findings default
   to `HIGH` because spec compliance has no severity vocabulary of its own. Assign stable IDs
   (`F1`, `F2`, ...), and accept/reject every finding against the task Contract, verified
   codebase behavior, and locked decisions. Append one-line reasoning in a machine-readable
   record such as `F1 | reviewer | normalized-severity | ACCEPT/REJECT | reason | patch-status`.
   The implementer never adjudicates its own work.
5. **Fix economically.** Apply a reviewer-attached patch directly only for an accepted
   LOW/MEDIUM or mechanical-HIGH finding and only if it changes at most 20 lines,
   `git apply --check` succeeds, every path is within `scope.files` and outside
   `scope.never_touch`, and affected acceptance checks pass after apply. Execute the manifest
   commands exactly as supplied with `scripts/sdd-acceptance` and persist its JSON result; do
   not restate or mutate command flags. A behavior change,
   exported-contract change, or cross-file fix always requires normal re-review. If any guard
   fails, apply none of that patch. Send all CRITICAL, judgment-requiring, rejected-patch, and
   remaining accepted findings to **one consolidated fix worker** using the pinned fix-worker
   triple.
6. **Discrepancy check.** Compare the fix report's per-ID
   `fixed | not-applicable | disputed` list against every accepted ID. Re-dispatch the
   consolidated gap when anything is missing, vague, or unsupported. A small fully specified
   omission may use only the same guarded patch path; there is no unrestricted captain-edit
   exception.
7. **Targeted re-review.** Re-dispatch each reviewer that raised an accepted CRITICAL/HIGH
   finding, plus any reviewer required because the actual fix changed behavior, changed a
   `CONTRACT:`/`SCHEMA:` surface, or crossed files. Verify other LOW/MEDIUM fixes from the diff
   and acceptance evidence. A Codex cycle is one consolidated fix containing an accepted Codex
   finding plus its Codex re-review; the initial review is not a cycle, and Codex is capped at
   two cycles. Spec/quality CRITICAL/HIGH loops are uncapped. Contract-changing fixes invalidate
   prior confirmation and require explicit spec re-confirmation; do not emit the future
   `CONTRACT_CORRECTED` event in Phase 1.
8. **Phase 1 full-chain gate.** The implementer, every risk-required review, adjudication,
   fixes, discrepancy checks, targeted re-reviews, and verification must all be PASS/resolved
   before **any** milestone report. Before stopping, append this captain's own `decision` events
   through `scripts/sdd-ledger append`; do not message another captain directly. Do not emit
   `MERGE_READY` early. Do not merge, initiate a candidate-SHA/rebase handshake, start a
   dependent speculatively, lease a worktree, or perform trailing review. Phase 1 has no temporal
   gap between readiness and completion.

### Exception routing

For `NEEDS_CONTEXT`, derive the answer first from the supplied spec/Contract and codebase;
record the derived answer and continue. If it is truly underivable, make the most conservative
assumption, append it to the ledger and report, and continue only when it can be verified. If
neither path is safe, emit a structured `ESCALATION` to the top orchestrator containing task ID,
class, finding IDs/evidence, attempted resolution, safest next action, pinned role/triple
involved where relevant, and artifact paths.

Classify every exception with this exhaustive table; unknown classes take the default row. The
table's auto-resolution outcomes and verify-or-quarantine gate are **Phase 2 (future)**. In
Phase 1 the captain uses the table to classify and route, performs only the `NEEDS_CONTEXT`
self-resolution above, records the event, and waits for the top orchestrator's conservative
decision. It must not silently activate a future default.

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

The future guardrails remain part of the event schema but are not active Phase 1 behavior: every
auto-resolution is ledgered; the final whole-branch reviewer receives and re-examines every
`AUTO-RESOLVED-CRITICAL`; the summary leads with auto-resolutions and parked tasks; and only an
independent PASS plus green verification on the final branch SHA can finish clean. Failed,
unavailable, missing, or inconclusive verification yields `QUARANTINED`, never done.

## Reports & Events

Use only this closed vocabulary.

**Phase 1 milestones:** after the full chain is green, persist complete `MERGE_READY` and
`CHAIN_COMPLETE` report files **together**, in that order, at chain end. Then emit only a
completion/status signal to the top orchestrator. The orchestrator reads those files, never
remembered stdout, before audit and `scripts/sdd-wave merge-lane`. This keeps the schema
forward-compatible without activating Phase 2's temporal separation.

- `MERGE_READY`: task ID, exact candidate SHA (`git rev-parse HEAD` after every Phase 1 fix on
  an own-branch/singleton path; the recorded latest task-owned commit on
  `IN_PLACE_PARALLEL`, never a later sibling-advanced shared `HEAD`), fork/base SHA, effective
  risk tier, readiness evidence, acceptance/build results, and the
  complete adjudication log or artifact path. `logic`/`pattern` readiness means spec-compliance
  PASS plus green build; `mechanical` readiness means declared acceptance evidence plus green
  build. All other required reviews/fixes are also complete before this Phase 1 report.
- `CHAIN_COMPLETE`: task ID/candidate SHA, final PASS/resolved state, per-stage timestamps,
  ledger entries, reviewer-output paths, and adjudication artifact path.

**Progress events:**

- `IMPLEMENTER_DONE` is a live internal Phase 1 signal and is persisted, not sent as permission
  for speculative branching.
- `STUB_READY` is **Phase 3 (future)**. A contract-stub commit is branchable only when its
  signatures/schemas match the Contract, typecheck/build and baseline tests are green, and
  callable placeholders fail explicitly as not implemented rather than returning plausible
  fakes. If the gate cannot pass, publish only a non-branchable contract artifact and wait for
  implementer DONE. Do not create or emit this commit/event in Phase 1.
- `REBASE_REQUEST` is **Phase 2 (future)**: after the pre-merge chain it asks the serialized lane
  to rebase and return an exact candidate SHA for fresh attestation. Do not emit it in Phase 1.

**Exception events:**

- `ESCALATION` is live and load-bearing in Phase 1 and follows the routing table.
- `READINESS_REVOKED` is **Phase 2 (future)** and invalidates prior readiness after a late
  CRITICAL/behavior finding.
- `CONTRACT_CORRECTED` is **Phase 2/3 (future)** and taints dependents for contract/behavior
  re-check after correction.
- `BRANCH_REQUEST` is **Phase 2 (future)** and asks the lane for a trailing-fix micro-branch.

Do not emit or act on the three future exception events in Phase 1.

**Future compatibility only:** **Phase 2 (future)** separates merge-on-`MERGE_READY` from
trailing `CHAIN_COMPLETE` through a candidate-SHA/rebase handshake, leased review worktrees,
trailing-fix micro-branches, and guarded auto-resolution/quarantine. **Phase 3 (future)** adds
`STUB_READY`/implementer-DONE speculation, pooled worktree lease/reset, and rerere with
`rerere.autoUpdate` off. None is active here.

## Durable Artifacts

Write artifacts **as produced**, never only when formatting reports. They live in external run
scratch, never in the repository/worktree. `scripts/sdd-dispatch` owns each role's streamed
`worker.out`, `worker.err`, and `meta.json`; the worker/captain owns its structured report file:

```text
<scratch>/run.jsonl
<scratch>/<task-id>/dispatch/<role>/worker.out
<scratch>/<task-id>/dispatch/<role>/worker.err
<scratch>/<task-id>/dispatch/<role>/meta.json
<scratch>/<task-id>/implementer.out
<scratch>/<task-id>/reviews/spec.out
<scratch>/<task-id>/reviews/quality.out
<scratch>/<task-id>/reviews/codex.out
<scratch>/<task-id>/fixes/<cycle>.out
<scratch>/<task-id>/adjudication.md
<scratch>/<task-id>/timestamps.tsv
<scratch>/<task-id>/ledger.md
<scratch>/<task-id>/events.jsonl
<scratch>/<task-id>/reports/MERGE_READY.json
<scratch>/<task-id>/reports/CHAIN_COMPLETE.json
```

The run-wide `run.jsonl` is append-only and namespaced per agent. Captains read other captains'
`decision` events at start and append their own at stop using `scripts/sdd-ledger`; this is the
only sanctioned cross-captain read surface. **No direct captain-to-captain messaging** is
allowed; control flow stays orchestrator-mediated.

Append atomically where possible and include task ID, base/candidate SHA, finding IDs, producer
role, and the pinned triple used. Worker and captain stdout/final messages are completion signals
only; their report content lives in these artifact files and must be read from disk. These files
are the recovery boundary: if this captain dies, the top orchestrator can adopt the orphaned
chain, identify the last completed stage, and resume or park it without trusting an incomplete
final message or remembered stdout.

## Timestamps

Append ISO-8601 timestamps to `timestamps.tsv` at captain dispatch/start, implementer dispatch
and DONE/`IMPLEMENTER_DONE`, review dispatch/start and each review end, adjudication start/end,
each patch/fix dispatch and end, discrepancy check, each targeted re-review start/end, final
verification, `MERGE_READY`, and `CHAIN_COMPLETE`. Include stage, role/cycle, status, current SHA,
and pinned triple. Also append matching `{stage, status: start|end}` timestamp events to
`run.jsonl` with `scripts/sdd-ledger append --type timestamp`; the orchestrator uses
`scripts/sdd-ledger report` for the deterministic latency table. Aggregate the same records into
`CHAIN_COMPLETE`; do not reconstruct them at report time.

## Dispatch & Failure Handling

`pi-watch` remains the canonical dispatcher from **quirk:pi-dev**, but every captain/worker
command-line launch goes through `scripts/sdd-dispatch` (which defaults to `pi-watch`). Raw
`pi -p` remains limited to pi-dev's documented escape hatches. The top orchestrator materializes
the run-pinned triples as the manifest's per-run JSON config, keyed by role. Never invoke
`pi-watch` directly, hand-roll redirection/timeout handling, call an alias, or re-run `--check` /
`--list-aliases` inside a captain.

Stage one task/role-keyed prompt outside the repository for each launch, then use the wrapper:

```bash
: "${WORKTREE:?}" "${SCRATCH:?}" "${TASK_ID:?}" "${PINNED_CONFIG:?}"
WORKER_TIMEOUT="${WORKER_TIMEOUT:-900}"
cd "$WORKTREE"

dispatch_role() {
  role="$1" tools="$2" prompt="$3" artifact_key="${4:-$1}"
  skills/subagent-driven-development/scripts/sdd-dispatch \
    --prompt "$prompt" \
    --config "$PINNED_CONFIG" --role "$role" \
    --tools "$tools" \
    --out-dir "$SCRATCH/$TASK_ID/dispatch/$artifact_key" \
    --timeout "$WORKER_TIMEOUT"
}

# Implementer and fix roles run alone.
dispatch_role implementer read,bash,edit,write \
  "$SCRATCH/$TASK_ID-implementer.md"
dispatch_role fix read,bash,edit,write \
  "$SCRATCH/$TASK_ID-fix-$CYCLE.md" "fix-$CYCLE"

# Start every risk-applicable reviewer in one batch, retain all PIDs, then wait for all.
dispatch_role spec read,grep,find,ls \
  "$SCRATCH/$TASK_ID-spec-review.md" & spec_pid=$!
dispatch_role quality read,grep,find,ls \
  "$SCRATCH/$TASK_ID-quality-review.md" & quality_pid=$!
dispatch_role codex read,grep,find,ls \
  "$SCRATCH/$TASK_ID-codex-review.md" & codex_pid=$!
# Wait for each retained PID and record each wrapper status before adjudication.
```

These are role launch shapes, not one sequential script: run the implementer first, launch only
the risk-applicable reviewers after `IMPLEMENTER_DONE`, and launch `fix` only when adjudication
requires it. Reviewer wrappers may run in the background only as one supervised batch whose PIDs
are all waited before the captain turn can end.

`sdd-dispatch` hard-fails on a missing prompt, passes the exact pinned triple, tees stdout and
stderr into role-specific `worker.out`/`worker.err` as they stream, preserves partial files on
timeout, and always writes `meta.json`. After every wait, inspect `meta.json` and read the
persisted worker report file. Wrapper stdout/final text is only a completion signal/tee, never
report transport. A nonzero `meta.json` exit code or missing report is not PASS.

Apply **quirk:pi-dev** failure signatures to the persisted artifacts; this template states the
captain policy rather than re-deriving those signatures:

- auth/billing failure: emit `ESCALATION` with the role and pinned triple; never silently switch
  provider/model or runtime mid-chain (the captain has no user to ask);
- rate limit: one retry after a 60-second backoff, then `ESCALATION`;
- empty/missing output: one re-dispatch, then `ESCALATION`;
- timeout/other canonical pi-dev failure: use pi-dev's bounded retry rule, then `ESCALATION`;
- unparseable reviewer output: never count it as PASS; synthesize `NEEDS_FIX`, persist the raw
  output and synthesized verdict, and enter the adjudication/fix path.

Any top-orchestrator runtime fallback or re-resolution epoch is explicit, recorded, and outside
this captain. Resumption receives a new manifest; a live captain never mutates its pinned
triples.
