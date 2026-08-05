## Verdict

Not buildable as written. The worst defect is the lifecycle/CAS contract: the tech spec explicitly drops `attempt` from the locked `(ID, attempt, expected status)` comparison, resets attempts after `park`, discards park reasons and refusal counts, and permits a stale `finish` to deliver a newer attempt. The Orca adapter is also nonfunctional against the cited CLI: it drops the launch prompt, omits required `--subject`, parses the wrong JSON shape, and never persists the IDs needed by `finish`.

## Findings

### [SEVERITY: critical] The CAS mechanism removes the attempt key it was required to implement

- **Where**: `tech.md:752-805`; `logic.md:405-410,606,1147-1148`
- **Problem**: The locked contract is CAS on `(ID, attempt, expected status)`, but `tech.md:779-785` explicitly reduces it to status alone. That is unsafe even in one directory: finish A can read/probe attempt 1; another process parks and starts attempt 2; finish A then acquires the lock, sees `in_progress`, and writes attempt-1 evidence into attempt 2.
- **Why it matters**: This reintroduces the same-directory stale-transition race CAS was added to prevent.
- **Fix**: Persist an immutable live attempt token and compare ID, exact attempt, expected status, expected probe, and expected Handoff under the lock. `finish` and `park` must receive or derive that token from the current handoff.

### [SEVERITY: critical] `park`, attempts, reasons, and refusals are not actually recorded

- **Where**: `tech.md:764-805`, especially `:772,787-805`; `logic.md:405-410,606`
- **Problem**: `park` removes `Status`, stores no reason anywhere, and the next start resets to attempt 1. Delivered/closed status renderings also omit the refusal count. This directly contradicts “keep the attempt on record” and “an entry that took four tries shows it.” The spec acknowledges the contradiction under Concerns but still declares no open questions.
- **Why it matters**: The principal legibility signal disappears exactly when an attempt parks or succeeds.
- **Fix**: Define persistent lifecycle metadata usable while open, such as a separate `Attempt`/`Refused`/`Last park reason` field, or an `open — attempt N — parked: reason` status grammar. Preserve aggregate refusal counts through delivered and closed.

### [SEVERITY: critical] The Orca adapter cannot launch or signal according to its own Protocol

- **Where**: `tech.md:557-668`; Orca `src/cli/specs/orchestration.ts:45-76,127-141`; `src/cli/specs/orchestration-worker-specs.ts:3-36`; `src/cli/handlers/orchestration.ts:714-730,810-844`
- **Problem**:
  - `launch(path, prompt, ...)` never uses `prompt`. `worker-start` has no `--prompt` flag, and `task-create` happens earlier in `create_worktree`, whose Protocol receives no prompt.
  - `orca orchestration send` requires `--subject`; the specified exact command omits it.
  - `worker-start` returns `result.dispatchId`, not `result.dispatch.id`.
  - `LaunchResult.dispatch_id` is never persisted in `Handoff` or the packet, and the packet deliberately remains `pending`. A later `finish` therefore has no specified source for task/dispatch IDs.
  - Adapter selection and behavior outside a Run-bound coordinator are unspecified.
- **Why it matters**: The advertised Orca path either starts a worker without the packet prompt, fails its completion signal, or cannot obtain the IDs its own method requires.
- **Fix**: Create the orchestration task during `launch`, using the packet-pointing prompt as `--spec`; parse the actual JSON envelope and `dispatchId`; add `--subject`; define active-Dispatch ID discovery or persist a launch receipt; and specify adapter selection/preflight.

### [SEVERITY: high] The packet has no implementable schema or integrity protocol

- **Where**: `tech.md:597-618,1251-1256`; `logic.md:444-480,890-892,1149`
- **Problem**: The tech spec never defines the packet’s complete rendering, XDG path resolution, schema-version literal, entry-digest algorithm/canonical bytes, atomic write behavior, or which operation validates the digest. Tests merely assert selected prose appears. The dispatch ID is permanently rendered as pending.
- **Why it matters**: Two implementations will generate incompatible packets, and the locked promise that stale packets can be detected has no implementation.
- **Fix**: Add an exact packet schema, canonical digest input and algorithm, write/collision policy, parser, and validation point. Specify every return-address field and how a worker-side command obtains current Dispatch identity.

### [SEVERITY: high] Lifecycle fields are not parseable or round-trippable

- **Where**: `tech.md:389-491,502-520`
- **Problem**: Exact renderings are given, but no parsers are. Arbitrary `--reason`, grep regexes, paths, repo labels, and branch names can contain the chosen delimiters (` — `, ` — by:`, commas, parentheses, or newlines). `splice_field` does not define which duplicate field it replaces, how it finds an entry end, or insertion behavior without a trailing blank line. `Entry` only records `start`, not `end`.
- **Why it matters**: Status, Probe, and Handoff are the authoritative machine-readable state. Ambiguous parsing can mutate the wrong field or lose user input.
- **Fix**: Provide formal parsers and escaping/rejection rules for every field, require full commit SHAs, add entry end offsets, and define duplicate-field handling. Add render→parse→render tests using delimiter-bearing values.

### [SEVERITY: high] The ROADMAP grammar rejects its own example and cannot diagnose proposals correctly

- **Where**: `tech.md:260-327`
- **Problem**:
  - The schema example contains blank lines between milestones, but “any other line under a milestone” is `ROADMAP_LINE_MALFORMED`; a strict write therefore rejects the example.
  - The membership regex only recognizes `BUG|DEFER|TEST`, so `- PROPOSAL-1` is merely malformed and can never produce the promised `PROPOSAL_IN_ROADMAP`.
  - No `parse_roadmap` model, renderer, preservation rule for comments/manual prose, or round-trip algorithm exists.
- **Why it matters**: Fresh valid-looking roadmaps can be refused, and revisions/intake require implementers to invent editing behavior.
- **Fix**: Define line classes, including blank/comment lines and syntactically valid-but-disallowed IDs; add parser/result/render contracts; define preservation and canonicalization; test the literal template as valid.

### [SEVERITY: high] The shared parser relocates a dangerous divergence and misstates Python regex behavior

- **Where**: `tech.md:156-247`; `bin/artifact_review.py:18-31`
- **Problem**: `\s*(.+)$` does match a whitespace-only title because `\s*` can backtrack and leave whitespace for `(.+)`; `.strip()` then yields an empty title. More seriously, strict matches remain the block boundaries. A malformed loose heading between valid entries is therefore absorbed into the preceding entry’s `raw` and field scan, allowing its fields to overwrite the preceding entry’s fields under last-value-wins.
- **Why it matters**: PM can read or mutate the wrong lifecycle state while `find_max_id` and doctor merely report a separate malformed heading.
- **Fix**: Use loose headings as all block boundaries, then classify each block as valid or malformed. Require a non-whitespace title (`\S`) and refuse mutation of any block whose boundaries are ambiguous. Test malformed headings between valid entries.

### [SEVERITY: high] Schema-v2 back-compat permits v2 fields to be written into v1 files

- **Where**: `tech.md:65-76,835-922`; `bin/artifact_append.py:181-190`
- **Problem**: `artifact_append.py` gains `blocked_by` and auto-stamped `logged`, while its version check still only rejects `version > EXPECTED_SCHEMA_VERSION`. After bumping the expected version to 2, it accepts a v1 file and can write v2 fields before migration—the exact mixed-version state the matrix claims to prohibit. The matrix excludes `artifact_append.py` from its write-command column.
- **Why it matters**: Existing projects can silently become mixed-schema through the normal append path.
- **Fix**: Specify artifact-append behavior on v1 explicitly: refuse until migration, or suppress all v2-only fields and stamping. Add v1 append tests. Also specify the existing-project sequence that creates missing `ROADMAP.md`.

### [SEVERITY: high] The probe baseline contradicts the approved red→green contract

- **Where**: `tech.md:698-741`; `logic.md:138-140,154-157`
- **Problem**: The tech spec accepts pytest `missing`, internal error, interruption, and timeout as valid failing baselines. The logic spec says the probe must fail and explicitly says `test:` refuses when the node is missing or errors. A timeout or pytest usage error is not a failing test. The Probe rendering nevertheless records all these outcomes as `baseline: fail`.
- **Why it matters**: Broken test configuration can become accepted baseline evidence and later be presented as a genuine red→green transition.
- **Fix**: For pytest, accept only exit 1 as a failing baseline; treat 2/3/4/5/timeout as refusal/error. Either make `test:` pytest-only or define separate exit mappings for configured runners. Render the exact baseline outcome.

### [SEVERITY: high] The grep contract still leaves important inputs undefined

- **Where**: `tech.md:722-741`; `bin/artifact_review.py:21-29`
- **Problem**: There is no lexical parser for separating a regex from `-- <paths>`, no behavior for invalid regex, nonexistent/unreadable paths, symlinks, permission errors, or enforcing the stated timeout in an in-process recursive scan. A newline continuation is not “entirely malformed” as claimed for `Blocked by`; the existing one-line field parser simply ignores the continuation. Leading-zero blocker IDs and Unicode `\d` normalization are also undefined.
- **Why it matters**: Routine malformed or unusual input has implementation-dependent outcomes.
- **Fix**: Define argument tokenization, path resolution, error/timeout outcomes, symlink policy, accepted ASCII ID grammar (`[0-9]+`), and canonical handling of leading zeros and multiline fields.

### [SEVERITY: high] Reconcile does not implement the locked repository and undetermined-state contracts

- **Where**: `tech.md:459-486,924-980`; `logic.md:221-238,754-756`
- **Problem**:
  - Handoff records the origin path and an ephemeral worktree path, not a stable destination-repository path. If the worktree is removed, reconcile cannot evaluate even if the destination repository remains available.
  - Rebase/squash is reported as `AWAITING_INTEGRATION`, while logic calls it undetermined.
  - The prescribed human resolution is `decide`, which can only produce `wontfix` or `superseded`, not human-confirmed `closed`.
  - `POST_MERGE_PROBE_REGRESSION` is not persisted, yet doctor findings are claimed to be freshly derived from disk; after reconcile exits, nothing records the failed verification.
  - Exit 128 is not uniquely “commit unknown”; an invalid integration ref also returns 128.
- **Why it matters**: Cross-project and rewritten-history deliveries can stall permanently or receive false diagnostics, and verification findings vanish.
- **Fix**: Store a stable destination repo root separately from the worktree, pre-resolve commit and integration ref, define a human-ratified close path for rewritten history, and persist reconcile/verify observations or explicitly rerun them in doctor.

### [SEVERITY: high] Start’s launch-failure state is self-contradictory

- **Where**: `tech.md:1178-1191`; `logic.md:351-380`
- **Problem**: One sentence says launch failure leaves the ledger `open` because failure is caught before the ledger write, then states the actual order is write ledger+packet before launch and therefore leaves `in_progress`. Logic’s numbered flow already places the ledger write before launch. There is no resume-launch command or launch receipt.
- **Why it matters**: Implementers cannot determine the state or exit semantics after a routine launcher failure.
- **Fix**: State one ordering and one result. If launch failure leaves `in_progress`, persist a recoverable launch receipt and define resume/park behavior; test it directly.

### [SEVERITY: medium] Exit-code assignments contradict their own command behavior

- **Where**: `tech.md:1065-1093,968-972`
- **Problem**: Code 6 is listed as reachable from reconcile write-back, while reconcile later silently skips CAS mismatches and is then said never to return 6. Code 7 is described as an existing “not writable” convention, but `artifact_init.py:26-29` only checks existence/directory status; permission failures are uncaught. Missing `ROADMAP.md` is both an empty roadmap and an exit-3 target-file failure.
- **Why it matters**: Callers and tests cannot know which exit to expect or whether partial multi-entry operations failed.
- **Fix**: Provide a per-command precedence table, define aggregate reconcile/migrate outcomes, and distinguish nonexistent from unwritable projects based on actual implemented checks.

### [SEVERITY: medium] `atomic_write` overstates crash durability

- **Where**: `tech.md:502-520,807-824`
- **Problem**: Temp-file plus `os.replace()` gives atomic namespace replacement on POSIX, but not power-loss durability without flushing/fsyncing the temp file and parent directory. Temp cleanup and preservation of file permissions are also unspecified. The test only monkeypatches `os.replace` before replacement.
- **Why it matters**: “Crash after replace is indistinguishable from normal completion” is stronger than the mechanism guarantees, and a naïve temp file can change a ledger from 0644 to 0600.
- **Fix**: Narrow the claim to process-crash atomic visibility, or specify flush/fsync, mode preservation, directory fsync, and orphan cleanup.

### [SEVERITY: high] The test matrix would not catch the major specification defects

- **Where**: `tech.md:1221-1280`
- **Problem**: Missing cases include stale finish across park/restart, persistence of park reason/refusal count, whitespace-only/mid-block malformed headings, ROADMAP blank-line round-trip, v2 append against v1, invalid grep regex/path/timeout, launch failure state, deleted destination worktree with surviving repo, malformed integration ref, and doctor after failed `--verify`. The permissive canned Orca stub would not catch missing `--subject`, discarded prompt, or the real `dispatchId` JSON shape.
- **Why it matters**: The named tests can all pass while the central lifecycle and real adapter remain broken.
- **Fix**: Add those fixtures and make the Orca stub validate exact required flags and replay captured real response shapes. Use a real Git cross-project test for reconcile and a stale-attempt interleaving test for CAS.

## False or unverifiable claims by the author

- **“All file:line citations are accurate” — false as a blanket claim.** Many sampled citations are accurate, including the append/review regexes and Orca command definitions. But the cited Orca source contradicts the specified invocation: `send` requires `--subject` (`orchestration.ts:48`), and `worker-start` returns `dispatchId`, not `dispatch.id` (`handlers/orchestration.ts:811-844`). The claimed existing exit-7 “not writable” convention is also absent from `artifact_init.py:26-29`.
- **“All 75 internal back-links resolve” — substantially verified.** I checked the distinct `logic.md#...` targets used throughout; they correspond to real headings, and the filing-requests tech-spec path also exists. I found no broken sampled backlink. I did not independently reproduce the exact count of 75 through a Markdown renderer.
- **“Orca’s real CLI source was read and verified” — source was consulted, verification was incorrect.** Worktree creation without `--agent`, `task-create`, existing-worktree `path:` selection, and worker-start all exist. The exact adapter remains invalid because it omits required `--subject`, drops `prompt`, expects the wrong dispatch JSON shape, and provides no later source for task/dispatch IDs.
- **“Existing behavior is fenced DO-NOT-CHANGE without changing it” — only partly supportable.** The cited legacy `write_text`, init backup/force loop, hook registration, and existing tests are genuinely fenced. However, the proposed v2 `artifact_append` behavior can write new fields into v1 files, and the parser’s claimed whitespace-title behavior is not what Python’s regex does. Passing the existing tests is not evidence of no behavior change for malformed headings because those fixtures are explicitly absent.

## What it gets right

- Correctly preserves loose ID allocation so malformed claimed IDs are not reissued.
- Correctly centralizes strict backlog parsing for PM consumers.
- Correctly uses worktree-root rather than git-common-dir for the finish mistake check.
- Correctly identifies the Orca two-step create-without-agent then existing-worktree launch capability.
- Correctly fetches before ancestry evaluation and distinguishes ordinary non-ancestor from ambiguous Git failure at a high level.
- Correctly retains the cooperative-worker, legibility-not-enforcement threat model.

## What I could not verify

- The claimed installed `pytest 8.4.2` version or its empirical runs; the repository does not pin pytest in `pyproject.toml`.
- Whether the installed `orca` binary was built from the inspected `/Users/zpyoung/orca/workspaces/orca/hind/` source.
- Power-loss behavior on the target filesystem.
- External research claims and linked community sources.
