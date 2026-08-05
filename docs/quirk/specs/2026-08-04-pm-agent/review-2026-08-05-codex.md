## Verdict

The spec is not implementable as written. Its worst defect is that `finish` closes the authoritative ledger after a probe passes in an arbitrary, potentially uncommitted and unmerged checkout. It therefore verifies “some directory passed once,” not that the fix was durably delivered to the target project.

## Findings

### [SEVERITY: critical] “Closed” does not mean delivered

- **Where**: `logic.md:213-219`, `logic.md:229-232`, `logic.md:316-318`
- **Problem**: `finish` runs against whatever CWD invoked it, while writing `closed` to another directory. It does not verify that CWD is the recorded handoff worktree, that it is the same repository, that changes are committed, or that the branch was merged. A worker can pass using uncommitted edits, another checkout, or a modified environment and then delete the worktree.
- **Why it matters**: The origin reports completion while its production/default branch still contains the bug. This defeats the module’s central purpose.
- **Fix**: Record repository identity, worktree realpath, base revision, target branch, and attempt ID. Require `finish` to run in that worktree, require a durable commit, integrate it into the declared target, and rerun the probe on the integrated revision before closing.

### [SEVERITY: critical] The red→green gate is trivially gameable and rewards retries

- **Where**: `logic.md:96-125`, `logic.md:222-225`, `logic.md:389-395`
- **Problem**: One initial failure and one eventual success cannot distinguish a fix from flakiness, missing dependencies, test-order effects, environment setup, or replacing the test with a trivial passing test. Refused finishes are neither signalled nor recorded, so an agent can retry a flaky probe until it passes without leaving evidence. The probe is stored in editable markdown, so the worker can also weaken it.
- **Why it matters**: A probe with independent pass probability `p` eventually closes with probability approaching 1 under unlimited retries. The system converts flaky tests into false completion certificates.
- **Fix**: Define exact runners, environment, timeout and exit semantics; fingerprint the probe file/config and baseline revision; record every attempt; require repeated stable results or an independent acceptance suite; reject probe mutations unless explicitly ratified.

### [SEVERITY: critical] Two advertised probe kinds are internally broken

- **Where**: `logic.md:104-121`
- **Problem**: `commit:<sha>` must name an object that is absent at `start` but present at `finish`. A normal worker cannot predict the SHA of a future commit; if the object already exists, `start` refuses. `grep:<pattern>` has no defined target or pass threshold, and deleting matching code is itself a count decrease. The blanket claim that deleting verification does not help is therefore unsupported.
- **Why it matters**: One verb is practically unusable; another directly rewards deletion. Different implementers will invent incompatible semantics.
- **Fix**: Remove `commit:` from red→green and accept a SHA only at finish as labelled audit evidence. Define grep roots, exclusions, baseline count, required final count, missing-file behavior, and rename/deletion handling.

### [SEVERITY: critical] The claimed existing cross-project write path cannot perform lifecycle writes

- **Where**: `logic.md:229-232`
- **Problem**: It is true that `artifact_append.py` accepts `--project-dir` (`bin/artifact_append.py:122`), but the conclusion that “the write half works today” is false. The script only appends new entries (`bin/artifact_append.py:192-203`). BUG, DEFER, and TEST schemas accept neither `Status`, `Blocked by`, nor `Handoff` (`bin/artifact_append.py:19-64`); unknown fields are rejected (`bin/artifact_append.py:139-142`).
- **Why it matters**: The existing code cannot update the origin entry at all. A separate mutation protocol, locking scheme, and state machine are required.
- **Fix**: Retract the claim and specify a lifecycle mutator with compare-and-swap on `(ID, attempt_id, expected_status)`, canonical locking, atomic replacement, and explicit exit codes.

### [SEVERITY: critical] The Orca adapter contradicts Orca’s actual sequencing and authority model

- **Where**: `logic.md:283-310`, `logic.md:731-745`
- **Problem**: The required sequence is create worktree → probe → packet → launch, but Orca `worker-start --worktree new-child` creates the worktree and launches/injects the worker as one operation; the documented invocation also requires `--name` (`../../orca/hind/skill-guides/orchestration.md:178-195`). Additionally, `run-current` reports only a bound Run, not an active Dispatch (`../../orca/hind/src/cli/help.ts:90`; `../../orca/hind/src/cli/handlers/orchestration.ts:456-464`). Recorded IDs do not authorize a manually opened terminal: Orca rejects `worker_done` from a foreign pane even when it claims the correct handle and IDs (`../../orca/hind/src/main/runtime/orchestration/lifecycle-reconciliation.test.ts:178-207`).
- **Why it matters**: The adapter can launch before refusal, and the amendment’s packet-ID fallback cannot emit an authoritative completion signal from the scenario it was added to support.
- **Fix**: Use Orca’s low-level worktree creation first, then launch against the exact existing worktree after baseline and packet creation. Signal only from the live assigned Dispatch; external terminals should update the ledger and let the coordinator reconcile separately.

### [SEVERITY: high] The “singular ledger” is not singular across Git worktrees

- **Where**: `logic.md:63-67`, `logic.md:404-406`, `logic.md:508-510`, `logic.md:530-531`
- **Problem**: An absolute path identifies one checkout, not a repository-global ledger. Another PM started in another worktree naturally treats its own `BUGS.md` as the origin. If all workers truly write one canonical origin path, one lock there can coordinate them; if they write separate worktree copies, there is no singular ledger. The spec simultaneously assumes both models.
- **Why it matters**: Starts, parks, and finishes can diverge between branches. “Idempotent” does not resolve finish-vs-park races, lost updates, or later Git conflicts.
- **Fix**: Define one canonical storage location independent of worktrees, or explicitly accept per-branch ledgers and specify reconciliation. Use an attempt token and expected-state CAS rather than relying on idempotence.

### [SEVERITY: high] The lifecycle violates the append-only invariant it uses to reject other designs

- **Where**: `logic.md:22-35`, `logic.md:336-345`, `logic.md:447-454`, `logic.md:549`
- **Problem**: The spec rejects an entry-level `Milestone` field because mutating an existing entry would break append-only semantics, then adds mutable `Status` and `Handoff` fields to those same entries. It never defines whether transitions overwrite fields, insert duplicate fields, or append event records. Existing parsing collapses duplicate labels into a dictionary (`bin/artifact_review.py:29`), which cannot preserve attempt history.
- **Why it matters**: `park` cannot both return to open and “keep attempt on record” without a defined event representation. Concurrent transitions have no deterministic merge semantics.
- **Fix**: Either explicitly abandon append-only metadata or define separate immutable transition blocks keyed by entry and attempt ID.

### [SEVERITY: high] “Additive; zero migration” breaks the existing schema contract

- **Where**: `logic.md:447-455`
- **Problem**: Templates remain schema version 1 and do not declare the new fields (`templates/BUGS.md:1-12`, `templates/DEFERRED.md:1-11`, `templates/TEST_BACKLOG.md:1-10`). The original design calls templates the schema source of truth and requires hard failure on newer schemas (`docs/specs/2026-05-04-typed-artifacts-design.md:191-198`, `:355-362`). The old review field regex is generic, but old append validation is not.
- **Why it matters**: Files claim schema v1 while containing v2 lifecycle semantics. Mixed plugin versions can write incompatible interpretations without the version guard firing.
- **Fix**: Define schema v2, update templates and the shared schema, and specify mixed-version rollout. “No entry rewrite” is reasonable; “no schema migration” is not.

### [SEVERITY: high] Dispatch has no recoverable partial-failure protocol

- **Where**: `logic.md:201-209`, `logic.md:234-237`, `logic.md:283-295`, `logic.md:416-421`
- **Problem**: Failures after worktree creation can leave orphan resources; failures after the ledger write can leave `in_progress` with no packet or worker; launch failure has no rollback or retry state. An unexpectedly green probe intentionally leaves the worktree, but the next `start` may collide with the same branch/path. Base revision, path allocation, dirty-repository behavior, and adapter receipts are unspecified.
- **Why it matters**: Routine setup, disk, Git, or launcher failures can permanently wedge an entry.
- **Fix**: Add an attempt state machine (`preparing`, `dispatched`, `parked`, etc.), persistent resource IDs, recovery/cleanup commands, idempotent resume, and compensation behavior for every failed step.

### [SEVERITY: high] Cross-project workers cannot perform the required `park`

- **Where**: `logic.md:267-271`, `logic.md:373-382`
- **Problem**: The packet requires the worker to park against the origin, but `/quirk:pm:park` has no `--project-dir`. Its reason is optional in the CLI despite the packet requiring a reason. The text also calls park a “terminal transition” while park returns the entry to nonterminal `open`.
- **Why it matters**: The most important failure-reporting path writes to the wrong project or cannot be invoked as instructed.
- **Fix**: Add required `--project-dir`/attempt context to park, require a reason for dispatched attempts, and distinguish worker-attempt termination from ledger-entry termination.

### [SEVERITY: high] Completion-signal resolution can target the wrong Dispatch

- **Where**: `logic.md:302-310`, `logic.md:316-318`
- **Problem**: Ambient Dispatch wins even if it belongs to a different task than the packet. Recorded IDs can be stale, completed, retried, or from another pane. The adapter signature `signal_done(task, outcome)` does not even include the recipient or dispatch ID required by its own resolution algorithm.
- **Why it matters**: A finish can close one ledger entry while completing an unrelated Orca task, or produce a rejected high-priority lifecycle message.
- **Fix**: Include attempt/task/dispatch identity in the adapter contract, validate all three against the live assignee, and never prefer an unrelated ambient Dispatch.

### [SEVERITY: high] The intake amendment still leaves work invisible

- **Where**: `logic.md:147-160`, `logic.md:699-704`
- **Problem**: `unplaced(e)` is restricted to ready entries. Medium/low work that is unroadmapped and blocked is neither shortlisted nor counted. If any other work is ready, the “nothing ready” explanation also does not surface it. Proposals remain outside both roadmap and next.
- **Why it matters**: The amendment claims to close the invisible-work hole but leaves a substantial class of open work invisible.
- **Fix**: Count all open unplaced entries and break the count down into ready, blocked, malformed, and decision-needed categories.

### [SEVERITY: high] Roadmap and dependency formats are not specified enough to implement

- **Where**: `logic.md:130-196`, `logic.md:336-345`, `logic.md:447-452`
- **Problem**: There is no `ROADMAP.md` grammar, milestone heading format, duplicate-membership rule, escaping rule, or deterministic render/edit algorithm. `Blocked by` does not define unknown IDs, duplicate IDs, self-blocks, cycles, whitespace, or malformed statuses. Under `every blocker is not-open`, a nonexistent blocker is arguably “not open” and may incorrectly unblock work.
- **Why it matters**: Two reasonable implementations will compute different ready sets and roadmap ranks.
- **Fix**: Provide formal grammars and validation rules. Treat unknown/ambiguous blockers as blocking errors; reject cycles/self-dependencies; require exactly one milestone membership.

### [SEVERITY: high] The shared-parser extraction cannot be “no behavior change” without preserving divergence

- **Where**: `logic.md:365-368`, `logic.md:455`
- **Problem**: The factual divergence is real: append recognizes an ID from any `## TYPE-N:` heading (`bin/artifact_append.py:88-92`), while review requires a nonempty title and captures fields (`bin/artifact_review.py:18-30`). A single canonical parser must choose which malformed headings count. Existing append also does not implement the original spec’s promised corrupt-entry exit 4; its implemented exits are 2, 3, 5, and 8 (`bin/artifact_append.py:126-190`).
- **Why it matters**: Extraction can change ID allocation or make entries disappear from PM computations.
- **Fix**: Specify strict and compatibility parsing modes, diagnostics, and malformed-entry behavior before extraction. Add fixtures for empty titles, duplicate IDs, duplicate fields, multiline values, and corrupt blocks.

### [SEVERITY: medium] Age ordering is undefined for TEST entries

- **Where**: `logic.md:149-151`, `logic.md:187-189`
- **Problem**: BUG and DEFER entries have date fields, but TEST entries do not (`templates/TEST_BACKLOG.md:3-10`). The spec never defines whether TEST age comes from ID order, Git history, file position, mtime, or status.
- **Why it matters**: The supposedly deterministic shortlist is not deterministic across implementations or clones.
- **Fix**: Add a creation date to TEST entries or define age as stable file order/ID with explicit tie-breaking.

### [SEVERITY: medium] Replacing the tail with counts can worsen visibility

- **Where**: `logic.md:320-331`
- **Problem**: The existing hook shows the last 50 lines of every artifact with a 1 MB cap (`hooks/load_artifact_tail.sh:12-34`). The proposed index specifies counts, “the current” in-progress task, and evidence mix, but not all in-progress tasks, open IDs/titles, unplaced work, proposal decisions, output caps, or parse-failure fallback.
- **Why it matters**: Users can lose the only ambient view of actual entry content and multiple concurrent tasks.
- **Fix**: Show bounded IDs/titles for all in-progress and stalled entries, unplaced/blocked counts, proposal counts, and a parse-error fallback while retaining output caps.

### [SEVERITY: medium] The packet is an unversioned, stale, injectable second copy

- **Where**: `logic.md:22-35`, `logic.md:59-67`, `logic.md:252-278`
- **Problem**: “No fact stored twice” is contradicted by copying the full entry, probe, and handoff data into a second file. No digest or freshness check exists. Verbatim ledger text can contain prompt instructions, and generating a literal shell command from an arbitrary pattern/path requires escaping that is not specified.
- **Why it matters**: Workers can act on stale or adversarial content, and paths/patterns containing shell metacharacters can produce the wrong command.
- **Fix**: Treat the packet explicitly as an immutable snapshot, include schema version and ledger digest, mark entry text as untrusted data, and use structured arguments rather than rendered shell commands.

### [SEVERITY: medium] The implementation verification plan is missing

- **Where**: Entire spec; especially `logic.md:464-482`
- **Problem**: There is no test plan for lifecycle transitions, races, crashes, probe semantics, worktree failures, cross-project paths, signal rejection, or backward compatibility. Existing tests cover basic append/review behavior only (`tests/test_artifact_append.py:10-228`; `tests/test_artifact_review.py:8-39`).
- **Why it matters**: The highest-risk behavior has no stated acceptance criteria, despite the feature being explicitly about verification.
- **Fix**: Add state-machine, fault-injection, race, parser-compatibility, fake-Git, fake-adapter, and end-to-end cross-worktree test matrices with specified exit codes.

## What the spec gets right

- `artifact_append.py` really does support `--project-dir` (`bin/artifact_append.py:122`).
- The old review field regex is generic and will parse an added one-line `Status` field (`bin/artifact_review.py:21`).
- The heading regexes are duplicated and have diverged (`bin/artifact_append.py:90`; `bin/artifact_review.py:20`).
- The existing artifact lock protects concurrent appends to the same lock file (`bin/artifact_append.py:166-179`; `tests/test_artifact_append.py:181-226`).
- The original design rates artifact rot High (`docs/specs/2026-05-04-typed-artifacts-design.md:405`), and the typed-artifact hooks are written to end with exit 0.

## Claims I could not verify

- The external academic, Reddit, beads, and METR claims were not checked against their linked sources.
- I could inspect the repository’s Orca source and current Hind guidance, but not prove that the user’s installed Orca binary is built from that exact revision.
- Claims about prior rejected PM/derived-state proposals are not documented in the listed original design spec, so their stated rationale could not be verified.
- The assertion that duplicate IDs always produce a loud Git conflict is merge-layout-dependent and was not demonstrated by a repository test.
