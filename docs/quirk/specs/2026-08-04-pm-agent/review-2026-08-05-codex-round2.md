## Verdict

The rework is substantially better, but still not sound or implementable. It correctly separates delivery from integration, repairs Orca’s basic create/launch sequencing, and adds real lifecycle mechanics. It also introduces several load-bearing contradictions: unresolved blockers become ready, `none` restores worker-authored closure, git-common-dir does not identify a worktree, the packet can defeat the clean-tree gate, and reconciliation trusts stale and worker-mutable refs. The spec got better and much bigger, but the new completion model still permits both false closure and permanent false stalls.

## Regressions introduced by the rework

### [SEVERITY: critical] The delivered state incorrectly satisfies dependencies

- **Where**: `logic.md:204`, `logic.md:747-748`
- **Problem**: `ready(e)` requires every blocker to be “not-open.” Both `in_progress` and the newly added `delivered` state are not `open`, despite representing unresolved work.
- **Why it matters**: Starting a blocker—or merely having its worker assert delivery—makes dependent work ready before integration. The delivered/closed split therefore corrupts the ready-set it was meant to strengthen.
- **Fix**: Define an explicit blocker-satisfaction predicate. At minimum, `in_progress` and `delivered` must remain blocking; define separately whether `wontfix` and `superseded` satisfy, redirect, or waive a dependency.

### [SEVERITY: critical] `--probe none` restores exactly the worker-authored closure the split forbids

- **Where**: `logic.md:309-311`, `logic.md:542-545`, `logic.md:747-748`
- **Problem**: The spec says “A worker can never write `closed`,” then allows a worker’s `finish` to write `closed` directly for `none`. The rationale that there is “no SHA” is false: the universal finish precondition runs on `HEAD`, which necessarily identifies a commit.
- **Why it matters**: `none` avoids the failing baseline, final probe, delivered queue, integration check, and reconcile step. That creates a direct incentive to select the weakest evidence. The spec itself recommends this escape when a probe is already green.
- **Fix**: Make `none` produce `delivered_unverified` with its `HEAD` SHA and require origin-side integration plus explicit human ratification to close. Use a separate human decision transition for genuinely non-code work.

### [SEVERITY: critical] The finish guards neither identify the recorded checkout nor compose with the packet

- **Where**: `logic.md:288-297`, `logic.md:313-317`, `logic.md:358`, `logic.md:539-540`; `.gitignore:10`
- **Problem**:
  - Every linked worktree shares the same Git common directory. Its fingerprint identifies the repository, not the recorded handoff worktree. The claim that it stops finishing in “some other checkout” is false.
  - The packet is written inside the destination at `.quirk/handoff/<ID>.md`, but no ignore/exclusion mechanism is specified. On an ordinary target, `start` itself leaves the worktree unclean, so `finish` refuses unless the worker commits an operational packet.
  - Even with a clean tree, probes run in the live checkout and can depend on ignored files, generated artifacts, environment state, or submodules not represented by `HEAD`.
- **Why it matters**: A worker can finish from a clean sibling or integration checkout whose probe passes, record that unrelated `HEAD`, and immediately satisfy reconciliation. Conversely, an honest worker can be unable to finish because of the packet.
- **Fix**: Compare canonical worktree root, recorded branch, attempt identity, and expected ancestry—not only common-dir. Run the final probe in a detached temporary checkout of the named tree. Store the packet outside the tracked worktree or install a deliberate exclusion before writing it.

### [SEVERITY: critical] Reconciliation trusts stale, incomplete, and worker-mutable Git state

- **Where**: `logic.md:158-180`, `logic.md:303-306`
- **Problem**: Reconcile never fetches or verifies that its remote-tracking ref is current. Worse, all linked worktrees share refs, so a worker can fabricate the default check with, for example, `git update-ref refs/remotes/origin/main <delivered-sha>`. This directly contradicts `logic.md:171-172`, which claims reachability cannot be fabricated from the worker worktree.
- **Why it matters**: False or missing promotion occurs in multiple ways:
  - stale local refs after remote force-push can produce false `closed`;
  - stale refs before a merge produce indefinite false `delivered`;
  - a worker can update the shared remote-tracking ref;
  - a configured integration ref can change between start and reconcile;
  - rebase and cherry-pick change commit identity and produce false negatives;
  - shallow history or missing objects make ancestry unknown, not false;
  - missing or direct/detached `origin/HEAD` does not reliably identify a default branch;
  - reachability remains true after a later revert or overwrite, as the spec admits.
- **Fix**: Snapshot the intended remote, integration ref, and base at `start`. Fetch that exact remote at reconcile, verify object completeness, and represent “unknown” separately from “not ancestor.” If workers are adversarial, local shared refs cannot be authoritative; use remote/forge state or another origin-controlled clone.

### [SEVERITY: critical] The squash fallback can close from an unrelated historical commit

- **Where**: `logic.md:174-179`, `logic.md:552-553`
- **Problem**: Searching integration history for the entry ID is unconstrained, while the spec neither requires the delivered commit message to contain the ID nor records a base revision from which to bound the search.
- **Why it matters**: An old commit, prior attempt, revert, documentation change, or unrelated mention of `BUG-7` can close the current delivery. Rebased and cherry-picked deliveries still stall if their messages lack the ID.
- **Fix**: Remove commit-message presence as closure evidence. Use forge merge metadata or a content-derived identity such as patch equivalence, bounded by the recorded base and delivery time; then verify the integrated tree’s probe before closure.

### [SEVERITY: high] Cross-project deliveries have no coherent reconciliation repository

- **Where**: `logic.md:15`, `logic.md:44`, `logic.md:303-306`, `logic.md:618-620`
- **Problem**: A worker may commit in a different repository while the ledger and reconcile command live in the origin project. That delivered SHA generally does not exist in the ledger repository and cannot be reachable from its integration ref. The algorithm never says to resolve/fetch/check the target repository recorded in `Handoff`.
- **Why it matters**: Cross-project probed work—the advertised use case—will either remain delivered forever or be checked against the wrong repository.
- **Fix**: Record a durable target repository identity and remote, snapshot its integration ref, and reconcile in that repository. Define behavior when its worktree is deleted or inaccessible.

### [SEVERITY: high] CAS does not repair the non-singular ledger across origin worktrees

- **Where**: `logic.md:561-566`
- **Problem**: The spec correctly says locks do not span worktrees, but then claims the second write is refused by CAS. If two PMs start from different origin worktrees, they mutate different `BUGS.md` copies and different lock files. Both observe `open`; both CAS operations succeed.
- **Why it matters**: The two attempts can independently become delivered or closed. A later Git conflict is not a refused transition and does not preserve authoritative state.
- **Fix**: Put lifecycle state in one repository-global location, or force all PM operations through a configured canonical ledger checkout and lock. Otherwise explicitly design branch-local ledgers and reconciliation; CAS alone is irrelevant across copies.

### [SEVERITY: high] The two-step Orca path exists, but the adapter contract still cannot fulfill its packet contract safely

- **Where**: `logic.md:368-370`, `logic.md:417-423`; `../../orca/hind/src/main/runtime/rpc/methods/orchestration-workers.ts:35,107,189`; `../../orca/hind/src/cli/specs/orchestration-worker-specs.ts:29`
- **Problem**: Orca does support selecting an existing managed worktree and creating a worker there, so that claim is real. But:
  - `worker-start` requires invocation from the coordinator terminal bound to the Task Run;
  - existing-worktree `worker-start` never runs setup;
  - the packet is written before `launch`, while the dispatch ID is only created by `worker-start`;
  - launch failure occurs after the ledger becomes `in_progress`, with no compensation or resume protocol.
- **Why it matters**: A non-Run PM fails after dispatch state is written; baseline probes may run before setup is ready; and the packet cannot contain the promised dispatch ID without a post-launch race.
- **Fix**: Add `prepare_task`/preflight and a launch receipt, wait for setup before baselining, write only pre-known IDs into the packet, and define rollback/resume after launch failure.

### [SEVERITY: high] Schema v2 is declared but existing projects have no migration mechanism

- **Where**: `logic.md:606-611`, `logic.md:640`; `bin/artifact_init.py:41-47`; `bin/artifact_append.py:184-190`
- **Problem**: Updating templates only affects new projects. `artifact_init.py` skips existing artifact files unless `--force`, which overwrites them. No command upgrades existing v1 markers or schema comments.
- **Why it matters**: Existing files remain marked v1, so an old plugin continues writing them without the newer-schema guard firing—the exact mixed-version failure the amendment claims to fix.
- **Fix**: Specify an idempotent, locked v1→v2 migration that updates markers/schema comments without replacing entries, including partial-migration recovery.

### [SEVERITY: medium] The new age fallback still does not define a cross-type order

- **Where**: `logic.md:247-250`
- **Problem**: Dated entries use calendar dates while TEST entries use per-file integer ordinals. Those are different domains. “Cross-type ties” does not explain whether `TEST-7` is older than `BUG-12` dated 2026-08-01.
- **Why it matters**: Implementers must invent an arbitrary type-tag ordering, so the allegedly deterministic shortlist differs across implementations.
- **Fix**: Add a creation date to TEST schema v2, or define one uniform comparable tuple for every entry.

### [SEVERITY: medium] Counters are not a record of every attempt

- **Where**: `logic.md:325-327`, `logic.md:474-482`
- **Problem**: Mutable attempt and refusal counts preserve totals, not each attempt. Rewriting `Probe`, `Handoff`, and status on the next start loses prior paths, hashes, park reasons, and refusal outcomes.
- **Why it matters**: The spec repeatedly promises that every attempt is recorded, but cannot audit which attempt mutated a probe, failed where, or was parked for what reason.
- **Fix**: Add immutable per-attempt event records, or narrow the claim to aggregate counters and accept the lost history.

## Round-1 closure audit

| Finding | Status | Evidence |
|---|---|---|
| 1. Closed does not mean delivered | **partial** | Delivered/closed split is real, but `none` closes directly, common-dir does not identify the worktree, and reconciliation trusts mutable/stale refs. |
| 2. Red→green is gameable | **partial** | Refusal counts and hashes add visibility, but no stable repetitions/environment control exists and probe mutation is explicitly permitted. |
| 3. Broken `commit:` and `grep:` probes | **partial** | `commit:` was correctly removed and deletion refusal added; default grep target/exclusions remain undefined. |
| 4. Existing cross-project write path cannot mutate | **fixed** | The false append claim was retracted and a dedicated locked CAS mutator is specified at `logic.md:329-333`. |
| 5. Orca adapter sequencing | **partial** | Existing-worktree `path:` launch is source-valid, but Run binding, setup readiness, packet receipt ordering, and failure recovery are missing. |
| 6. Singular ledger across worktrees | **not addressed** | The spec admits per-worktree locks and Git conflicts; CAS against separate files cannot create singular authority. |
| 7. Append-only contradiction/history | **partial** | Substance/lifecycle distinction is clarified, but aggregate counters do not preserve attempt history. |
| 8. Schema v2/migration | **words-only** | The spec names schema v2; `artifact_init.py:41-47` still provides no non-destructive upgrade path for existing files. |
| 9. Dispatch partial failures | **partial** | Green-probe collision behavior is defined, but launch failure, resume, cleanup, and ledger compensation remain absent. |
| 10. Cross-project park | **fixed** | `park` now requires `--reason` and accepts `--project-dir` at `logic.md:515-522`. |
| 11. Completion signal targets wrong Dispatch | **fixed** | Signalling is limited to the live assigned Dispatch; packet IDs no longer authorize fallback. |
| 12. Intake leaves blocked work invisible | **fixed** | `unplaced` now counts all open entries and breaks them down as ready/blocked/malformed. |
| 13. Roadmap/dependency semantics | **fixed** | Unknown, self, and cyclic blockers now fail closed; lexical/grammar contracts are appropriately delegated to `tech.md`. |
| 14. Shared parser extraction | **fixed** | Strict/compatibility behavior is explicitly delegated to the future tech spec, its proper implementation-contract layer. |
| 15. TEST age undefined | **partial** | ID ordinal was added, but it is not comparable to calendar dates across artifact types. |
| 16. Read layer loses visibility | **partial** | Denominators and evidence mix were added, but only “the current” task is shown; bounded lists, all in-progress work, caps, and parse fallback remain unspecified. |
| 17. Packet stale/injectable copy | **partial** | Schema, digest, and untrusted-data marking were added, but no operation validates the digest and literal command rendering remains. |
| 18. Verification plan missing | **fixed** | The test/fault-injection matrix was explicitly moved to `tech.md`, which is the correct layer. |

## New findings

### [SEVERITY: medium] Proposal lifecycle is contradicted by its own scope

- **Where**: `logic.md:131`, `logic.md:542-545`, `logic.md:613-614`; `templates/proposals.md:1-14`
- **Problem**: The probe discussion says most PROPOSAL entries use `none`, and the `none` scenario calls this their honest closure path. Scope simultaneously says proposals gain no PM lifecycle fields and retain human-only statuses.
- **Why it matters**: One implementer will reject `start PROPOSAL-N`; another may overwrite its existing human `Status: proposed`.
- **Fix**: Explicitly reject proposals from all PM lifecycle commands and remove them from probe/finish examples, or design a separate ratified proposal decision flow.

### [SEVERITY: medium] Terminal exits are named but have no authority or transition rules

- **Where**: `logic.md:510-522`, `logic.md:747-748`
- **Problem**: `wontfix` and `superseded` are declared terminal states, but no command, ratification gate, actor, source-state rule, or evidence requirement can produce them.
- **Why it matters**: Their effect on readiness and dependency satisfaction cannot be implemented consistently.
- **Fix**: Define who may perform each transition, from which states, under what gate, and how each affects blockers.

### [SEVERITY: low] The glossary reverted the widened unplaced definition

- **Where**: `logic.md:205`, `logic.md:276-281`, `logic.md:864`
- **Problem**: The main algorithm correctly defines unplaced as every open entry outside a milestone; the glossary still defines it as a ready entry.
- **Why it matters**: The normative summary reintroduces the exact blocked-work invisibility defect the amendment claims to fix.
- **Fix**: Make the glossary match the algorithm.

## What I could not verify

- No `tech.md`, `pm.py`, adapters, schema-v2 templates, or lifecycle tests exist yet, so fetch behavior, hashing, CAS implementation, cleanliness checks, and migration cannot be inspected.
- I verified Orca against `../../orca/hind`, but cannot prove the installed Orca binary was built from that revision.
- External research and community-source claims were not rechecked.
