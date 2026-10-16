# Cutting SDD Wall-Clock Time

## Status & amendments

Status: Draft, approved in brainstorming, pending user review.

Amendments: none yet.

## Purpose

`quirk:subagent-driven-development` (SDD), `quirk:adversarial-review`, and `quirk:writing-plans` spend most of a run's wall clock waiting on people and re-running the same test suite on unchanged trees, rather than doing orchestration or model work. In an eight-run audit (led by reference session `bd307ed1` at 5h52m wall clock with only 35 minutes of orchestrator work), user waits totaled 839 minutes across 35 Orca cards, full test suites ran 4 to 10 times per review round on identical trees, and late full-branch review rounds spent 76 active minutes mostly re-reporting known issues.

This spec cuts SDD wall-clock time across five coordinated areas while keeping final branch review strict. All five conditions below hold together:

1. Every green test run is recorded by its tree identity and command so acceptance checks, wave gates, review pre-passes, and reviewers never re-test identical bytes.
2. Human questions follow a three-tier reversibility protocol: one consolidated preflight card blocks up front, recoverable mid-run questions carry a 10-minute deadline with a recommended default, and review-finding adjudications log to a round digest with asynchronous user veto.
3. Wave checkpoint reviews scale down to `standard` depth, final round 1 runs full `deep` discovery, and final rounds 2 and above run as scoped closure passes with escalation for recurring defect classes.
4. `writing-plans` assigns each test file to a single owning task in a wave and scopes task acceptance commands to owned tests, leaving the full suite to the wave gate.
5. Subagent dispatches pin `high` reasoning effort on implementers, promoters, refuters, and fixers, and use `medium` or `low` only on auxiliary roles.

## Conceptual model

Five domain rules govern how work, verification, and human input move through an SDD run. All five rules apply on every run:

- A tree-test record binds a green test result to `(tree_identity, exact_command)`. For a committed tree (wave gate or git-range review), `tree_identity` is `git rev-parse <ref>^{tree}` with a clean working tree. For an uncommitted component worktree during mid-chain acceptance, `tree_identity` pairs `HEAD^{tree}` with the content digest of `CHAIN_SNAPSHOT_<n>` plus any unstaged changes. Because the orchestrator verifies or records the run against the exact bytes and command string, reusing a green record preserves the rule that a worker's claim never overrides a run.
- A shared review baseline means one `resolve.json` and one `prepass.json` anchor all three concurrent review lenses (`C` correctness, `S` spec, `X` security) in a round, or `prepass` consumes a verified green tree-test record from the wave gate that just passed on the same `HEAD^{tree}` and `artifact_hash`.
- A three-tier human gate separates questions by how reversible the default is:
  - Tier 1 (blocking): preflight setup (consolidated into a single card after alias pre-checks) and blocked final handoffs (reaching the 5-round cap with an open `CRITICAL` or `HIGH` finding, or an unrecoverable chain failure with no safe default).
  - Tier 2 (10-minute deadline with default): recoverable mid-run choices (`NEEDS_CONTEXT`, mid-wave scope splits, reviewer `kind: "question"` items, and recurring-defect escalations) registered via `orca ask --timeout-ms 600000` with an explicit `default`. The orchestrator keeps running unblocked work while waiting, **never ends a turn while an `orca ask` is open**, and records `<decision> (assumed, timed_out)` if the deadline expires.
  - Tier 3 (logged digest with asynchronous veto): review-finding adjudications (accept, dismiss, regrade) execute immediately from `GateResult` and the contract, print as a compact per-round digest table, and treat any later user objection as a follow-up fix task in the next batch.
- A closure round is any final-loop review round after round 1. Round 1 performs full branch discovery over `RUN_BASE..HEAD` at `deep` depth. Rounds 2 through 5 verify whether prior accepted findings are closed (`fixed` vs `still-open`), inspect the fix delta (`LAST_ROUND_HEAD..HEAD`) and its touched contract seams for regressions, and fall back to full-branch discovery only when a fixer modified files outside its assigned component scope. If a defect in the same category and file seam survives or recurs after a fix round, it escalates as a root-cause design task or a Tier 2 question rather than triggering another narrow fixer pass.
- Single-owner test topology means every test file created or modified in a wave belongs to one task's `scope.files` (or one serialized component chain). Each task's `Acceptance` command runs only its owned test files, while Step 7's wave gate runs the full repository build and test suite once.

## Data flow

The steps below run in order across a single SDD execution:

1. At Step 1 (Preflight), the orchestrator checks `git rev-parse --abbrev-ref HEAD`, `git status --porcelain`, and `git rev-parse HEAD`, and runs `pi-watch --check` in a scratch directory across the candidate implementer and reviewer aliases. It then issues one consolidated Tier 1 `orca ask` card covering backend pairing (`IMPLEMENTER` and `REVIEWER_ALIAS`), disposition of any pre-existing dirty or untracked paths, and any environment readiness prompt. The run journal opens in scratch space with an empty `tree_test_cache` map.
2. At Step 3 (Decompose inline via `quirk:writing-plans`), the planner builds the file-coupling map, assigns every touched test file to a single owning task (or a single serialized component chain), and writes literal `Acceptance` commands scoped to each task's owned test files.
3. At Steps 4 through 6 (Wave dispatch and mid-chain gate), the orchestrator dispatches implementers with `effort: "high"` (and Explore/survey helpers at `low` or `medium`). When a task returns, the orchestrator runs the HEAD check and `CHAIN_SNAPSHOT_<n>` scope audit. If the worker's report includes a passing run of the exact literal acceptance command on the current worktree snapshot (or if `tree_test_cache` already holds a green entry for that `(tree_identity, command)`), the orchestrator records or reuses the green entry; otherwise it runs the narrow acceptance command once and caches the green result.
4. At Step 7 (Wave gate), after all components commit and merge into the feature branch, the orchestrator checks `tree_test_cache` for `(HEAD^{tree}, full_suite_cmd)`. On a miss, it runs the project's build and full test suite once and records the green result and elapsed duration. If the suite takes longer than 5 minutes (300 seconds), the orchestrator records a slow-suite advisory in the run journal and final summary recommending `pytest-xdist` (`-n auto`) and Playwright browser-context reuse. If Step 7 fails solely because an unowned test file outside the wave's `scope.files` asserts pre-wave behavior that the wave's contract intentionally replaced, the orchestrator automatically dispatches a scoped wave-gate fixer (`effort: "high"`) with that test file in scope, audits and commits the fix, and re-runs Step 7.
5. At Step 8 (Checkpoint review, for non-final waves), the orchestrator runs `adversarial-review resolve` once (which excludes vendored, generated, and lockfile paths by default and lists them in `excluded_paths[]`) and produces one `prepass.json` by reusing Step 7's green `tree_test_cache` entry via `--reuse-check` (or running `prepass` once and sharing `prepass.json` across all three lenses). It dispatches the `C`, `S`, and `X` lenses concurrently at `--depth standard`, with promoters and refuters pinned to `high` effort and forbidden from running the full test suite when `prepass.status == "pass"`. Refute prompts receive only the diff hunks and surrounding context lines cited by `claims[]` rather than a second copy of the full diff.
6. At Step 9 (Adjudicate and fix), the orchestrator merges the three lenses' `GateResult` payloads, adjudicates findings against the contract without asking a blocking question, records the rulings in the run journal, and prints a compact per-round digest table. Accepted findings are grouped into write-scope components and dispatched to fixers (`effort: "high"`). If the user replies to veto a dismissal or fix, the orchestrator schedules the override as a follow-up fix task in the next batch.
7. At Steps 8 through 10 (Final review loop), round 1 runs across `RUN_BASE..HEAD` at `--depth deep` (with tiebreak arbiters at `medium` effort). If round 1 fixes findings, round 2 (and any subsequent round up to the 5-round cap) runs in closure mode over `LAST_ROUND_HEAD..HEAD` plus prior accepted findings and touched contract seams, reusing the fix batch's green wave-gate test record for `prepass`. If a defect in the same category and seam recurs after a fix round, the orchestrator escalates to a root-cause task or a Tier 2 question (`orca ask --timeout-ms 600000` with a recommended default) instead of dispatching another narrow fixer. The loop exits when a round completes with no accepted finding above `LOW` and a green gate, or **blocks final handoff when the 5-round cap is reached with an open `CRITICAL` or `HIGH` finding**.

## Key decisions & rationale

Each decision below resolves one of the trade-offs identified during the wall-clock exploration:

1. **Deterministic CLI support in `scripts/adversarial-review` beats prose workarounds and a second wrapper binary.** Asking orchestrators in prose to pass `--check-cmd "true"` corrupts the replay manifest (`manifest.prepass.checks` would claim `"true"` ran), and asking them to hand-write git pathspec excludes failed in run `c632d703` (which staged a 7.0 MB diff that was 90% vendored). Conversely, creating a separate `sdd-ctl` wrapper CLI would recreate the fragile helper-script layer earlier SDD versions removed. Giving `prepass` a verified reuse mechanism anchored to `resolve`'s `artifact_hash` and `HEAD^{tree}`, and giving `resolve` built-in default excludes with `excluded_paths[]` reporting, preserves chain integrity in the one script that already owns it.
2. **Three-tier human gates with a 10-minute runtime deadline and logged adjudications cut the largest wait source while keeping irreversible stops safe.** Across 8 historical runs, user waits cost 839 minutes, the recommended option won 88% of the time (38 of 43), and review-finding adjudications cost 448 minutes with 15 of 15 recommendations accepted. A 10-minute timeout (`--timeout-ms 600000`) would have covered 661 of the 839 wait minutes with only 1 miss, whereas a 5-minute timeout would have missed 4. Moving dirty-tree and backend questions into one preflight card handles human-only state up front, while logging adjudications to a round digest eliminates the single largest wait category because a user veto can still queue a follow-up fix task.
3. **Synchronous `standard`-depth wave checkpoints balance speed against cross-wave rework risk.** Across 14 historical checkpoint rounds, `HIGH` findings appeared in only 2 rounds and `CRITICAL` in 0, while the final loop re-examines `RUN_BASE..HEAD` at `deep` depth anyway. Running checkpoints synchronously at `standard` depth (skipping stage-3 tiebreak and sharing the wave gate's green pre-pass) cuts checkpoint latency while preserving the guarantee that wave N+1 never builds on a broken interface.
4. **Closure rounds after final round 1 and recurring-defect escalation stop late-round noise and pseudo-fix loops.** `skills/adversarial-review/SKILL.md` (`## Running rounds`) already specifies that round 1 is discovery and rounds 2+ are closure over prior findings, the fix delta, and touched seams, yet `skills/subagent-driven-development/SKILL.md` currently re-runs full `RUN_BASE..HEAD` discovery on every round. Aligning SDD with closure rounds addresses the 76 active minutes spent in rounds 3+ and matches published evidence that repeated full re-review lowers F1 as false positives accumulate. Escalating recurring defect classes after two failed fixes prevents the 3-to-5-round pseudo-fix cycles seen in `3cbb7331`.
5. **Pinning `high` effort on core roles and `medium`/`low` on auxiliary roles protects recall and test integrity.** Controlled trials on wave 2 of the reference run showed that dropping promoters to `medium` cut model time from 16.8 to 5.8 agent-minutes only by taking a third as many turns, which missed a blocking `MEDIUM` finding (`C1` sidenote overlap) and downgraded two others to `LOW`. Dropping refuters and fixers to `medium` saved under 1 minute of model time per agent while the `medium` layout fixer lifted a CSS prose cap and weakened an existing test selector to pass (failing 2 cross-check tests).

## Behavior & scenarios

### Tree-once caching and review staging hygiene

1. **SC-1: Wave gate seeds the pre-pass for all three review lenses**
   - **Given** Wave 2 has merged at commit `9628c57` with tree `4b825dc`, clean `git status --porcelain`, and Step 7's full test command `python3 -m pytest -q` exited 0 in 462s
   - **When** Step 8 stages the checkpoint review across the `C`, `S`, and `X` lenses for `WAVE_BASE..HEAD` (artifact hash `8f00d1`)
   - **Then** the orchestrator runs `adversarial-review resolve` once and `adversarial-review prepass` once reusing the Step 7 green record for `(4b825dc, "python3 -m pytest -q")`, and all three lenses consume that shared `resolve.json` and `prepass.json` without re-executing `pytest`
   - **Data before:** **Run journal**: `tree_test_cache` holds `(tree: 4b825dc, clean: true, cmd: "python3 -m pytest -q") -> exit 0, duration 462s`; **Pre-pass result**: none
   - **Walkthrough:**
     1. The orchestrator runs `adversarial-review resolve --target WAVE_BASE..HEAD` and writes `resolve.json` with `artifact_hash: 8f00d1`.
     2. The orchestrator runs `adversarial-review prepass` with `--resolve resolve.json` and the cached check record for tree `4b825dc`.
     3. The script verifies that `HEAD^{tree}` is `4b825dc`, the working tree has no unrecorded edits, and the artifact hash is `8f00d1`, then emits `prepass.json` with `status: "pass"` and `observed_artifact_hash: "8f00d1"`.
     4. The orchestrator dispatches lenses `C`, `S`, and `X` against the shared `resolve.json` and `prepass.json`.
   - **Data after:** **Pre-pass result**: ✓ `status: "pass"`; ✓ `pytest` invocations during Step 8 = 0; ✓ `gate` accepts `resolve.json` and `prepass.json` for all three lenses

2. **SC-2: Tree-test cache invalidates when any tracked or untracked file changes**
   - **Given** `tree_test_cache` holds a green result for tree `4b825dc` and command `python3 -m pytest -q`, and a fixer modifies `layout.css` producing snapshot digest `e91a02`
   - **When** the orchestrator evaluates acceptance or pre-pass on the modified tree
   - **Then** the cache lookup misses on `e91a02`, `adversarial-review prepass` refuses any stale check record anchored to `4b825dc`, and the test command runs fresh against the new bytes
   - **Data before:** **Run journal**: `tree_test_cache` keyed on `4b825dc`; **Worktree state**: `layout.css` modified, snapshot digest `e91a02`
   - **Walkthrough:**
     1. The fixer reports `DONE` after editing `layout.css`.
     2. The orchestrator computes the current tree identity `(4b825dc, snapshot: e91a02)` and looks up `"python3 -m pytest -q"`.
     3. No entry matches `e91a02`, so the orchestrator executes the command and records the new result under `(4b825dc, snapshot: e91a02)`.
   - **Data after:** **Run journal**: ✓ fresh run executed and recorded under `(4b825dc, snapshot: e91a02)`; ✗ stale `4b825dc` result is not reused

3. **SC-3: Default diff hygiene excludes vendored and generated files and excerpts refute context**
   - **Given** a branch diff `RUN_BASE..HEAD` contains 420 changed lines (190 KB) in `src/app.py` and 110,000 changed lines (6.8 MB) in `vendor/bundle.js` and `pnpm-lock.yaml`
   - **When** `adversarial-review resolve` and `adversarial-review claims` run for a review round where promote raises findings citing `src/app.py:40-55`
   - **Then** `resolve` excludes `vendor/bundle.js` and `pnpm-lock.yaml` from the staged diff by default, lists both in `ResolveResult.excluded_paths` with line stats, and `claims` emits a `diff_excerpts` block containing only the hunks and surrounding lines cited by `claims[]` so the refute and tiebreak prompts do not re-inline the 190 KB diff
   - **Data before:** **Branch diff**: `src/app.py` (420 lines, 190 KB), `vendor/bundle.js` and `pnpm-lock.yaml` (110,000 lines, 6.8 MB)
   - **Walkthrough:**
     1. `adversarial-review resolve` runs `git diff` with default exclude pathspecs for vendored, generated, and lockfile patterns and captures `--stat` on the excluded set.
     2. `ResolveResult` records `size_metric: 420` and `excluded_paths: ["vendor/bundle.js", "pnpm-lock.yaml"]`.
     3. After promote raises findings citing `src/app.py:40-55`, `claims` extracts those hunks into `claims.json` for `refute-prompt.md`.
   - **Data after:** **ResolveResult**: ✓ staged diff is 190 KB instead of 7.0 MB; ✓ `excluded_paths` lists both omitted files; **Refute prompt**: ✓ stages only cited hunks plus `excluded_paths` notice

4. **SC-4: Reviewers are barred from running the full suite when pre-pass is green**
   - **Given** `prepass.json` reports `status: "pass"` for the repository test suite
   - **When** a promote or refute reviewer needs to reproduce a `HIGH` or `CRITICAL` finding
   - **Then** `profiles/code-diff.md`, `promote-prompt.md`, and `refute-prompt.md` require the reviewer to run only the narrowest single test or command targeting the claim and forbid invoking the full test suite

### Three-tier human gates, preflight consolidation, and adjudication digests

5. **SC-5: Preflight pre-checks aliases and asks a single consolidated card**
   - **Given** an SDD run starts on branch `feat/shapes` with 1 untracked file `notes.tmp` and both `codex` and `gemini` reachable via `pi-watch --check`
   - **When** Step 1 (Preflight) runs
   - **Then** the orchestrator runs `pi-watch --check` in scratch first and registers one Tier 1 `orca ask` card combining implementer selection, cross-family reviewer alias selection, and disposition of `notes.tmp`
   - **Data before:** **Working tree**: `notes.tmp` untracked; **Reachable aliases**: `codex` (openai), `gemini` (google), `sonnet` (anthropic)
   - **Walkthrough:**
     1. The orchestrator runs `git status --porcelain` and `pi-watch --check` for candidate aliases before asking the user anything.
     2. The orchestrator registers one `orca ask` card containing `implementer`, `reviewer_alias` (with `codex` recommended first), and `dirty_tree_action` (`stash/remove notes.tmp` vs `abort`).
     3. The user answers the single card once, and the orchestrator records `IMPLEMENTER`, `AUTHOR_FAMILY`, and `REVIEWER_ALIAS` in the run journal.
   - **Data after:** **Orca ask card**: ✓ 1 blocking preflight card instead of 2+ sequential cards; **Run journal**: ✓ backend record locked for the run

6. **SC-6: Mid-run recoverable question resolves to its recommended default after the 10-minute deadline**
   - **Given** Task T2 returns `NEEDS_CONTEXT` on question `t2_edge_case` (recommended default `clamp_to_zero`) while Component B (Task T3) is still running, and the user has stepped away
   - **When** the orchestrator registers a Tier 2 `orca ask` with `--timeout-ms 600000` and `default: "clamp_to_zero"`
   - **Then** the orchestrator continues managing Component B while polling `orca ask wait` across chunks without ending its turn, and when 600,000 ms elapse with `status: "timed_out"`, it applies `clamp_to_zero`, logs `t2_edge_case: clamp_to_zero (assumed, timed_out)` in the run journal, and dispatches Task T2 with that answer
   - **Data before:** **Orca ask card**: `id: "t2_edge_case"`, `timeout_ms: 600000`, `default: "clamp_to_zero"`; **Component B**: running in parallel
   - **Walkthrough:**
     1. The orchestrator registers `orca ask --timeout-ms 600000` with `default: "clamp_to_zero"`.
     2. Component B finishes its mid-chain audit while the ask is pending; the orchestrator audits and accepts T3 without waiting for the card to clear first.
     3. At 600s, `orca ask wait` returns `{"status": "timed_out", "answers": {"t2_edge_case": {"value": "clamp_to_zero", "source": "default"}}}`.
     4. The orchestrator logs `t2_edge_case: clamp_to_zero (assumed, timed_out)` in the run journal and resumes T2.
   - **Data after:** **Run journal**: ✓ `t2_edge_case: clamp_to_zero (assumed, timed_out)` recorded; ✓ turn never ended with a stranded open card; ✓ Component B was not stalled

7. **SC-7: Review-finding adjudications log to a round digest and accept async user veto**
   - **Given** Wave 2 checkpoint review returns `C1` (`HIGH`, standing), `S1` (`MEDIUM`, standing), and `X1` (`MEDIUM`, standing, out-of-contract pre-existing code)
   - **When** Step 9 adjudicates the findings and the user later replies "fix X1 too" while Fixer batch 1 is running
   - **Then** the orchestrator accepts `C1` and `S1`, dismisses `X1` with a one-line reason, prints the round digest table, and dispatches Fixer batch 1 immediately without registering an `orca ask`; when the user's reply arrives, the orchestrator queues `X1` into the next fix batch without aborting Fixer batch 1
   - **Data before:** **Gate findings**: `C1` (`HIGH`), `S1` (`MEDIUM`), `X1` (`MEDIUM`, touches untouched legacy module)
   - **Walkthrough:**
     1. Step 9 rules `C1: accepted`, `S1: accepted`, `X1: dismissed (pre-existing outside diff scope; routed to typed-artifacts)`, logs all three in the run journal, and prints the 3-row digest table.
     2. Fixer batch 1 dispatches immediately for `C1` and `S1` (0 minutes of human wait).
     3. While Fixer batch 1 runs, the user sends a message vetoing the dismissal of `X1`.
     4. Fixer batch 1 finishes and passes its gate; the orchestrator dispatches a follow-up fixer for `X1` in the next batch.
   - **Data after:** **Run journal**: ✓ 0 blocking adjudication cards registered; ✓ user veto on `X1` honored as a follow-up fix batch without discarding Fixer batch 1

### Stage-sized checkpoints, closure rounds, and recurring-defect escalation

8. **SC-8: Non-final wave checkpoints run at `standard` depth; final round 1 runs at `deep` depth**
   - **Given** a multi-wave SDD plan completes Wave 1 (which has a successor Wave 2) and later completes Wave 2 (the final wave)
   - **When** Step 8 runs after Wave 1 and again at the start of the final loop after Wave 2
   - **Then** Wave 1's checkpoint dispatches the three lenses with `--depth standard` (promote + refute, no stage-3 tiebreak), whereas Final Round 1 dispatches all three lenses with `--depth deep` over `RUN_BASE..HEAD`

9. **SC-9: Final rounds 2 and above run as closure passes and escalate recurring defects**
   - **Given** Final Round 1 (`deep`, over `RUN_BASE..HEAD`) accepted findings `C1` (`layout-overflow` in `layout.css`) and `S2`, and Fixer batch 1 committed fixes touching only `layout.css` and `tests/test_layout.py`
   - **When** Step 8 stages Final Round 2, and `C1`'s `layout-overflow` defect recurs in `layout.css` again after a second fix attempt in Round 3
   - **Then** Round 2 runs in closure mode over the fix delta (`LAST_ROUND_HEAD..HEAD`), the prior accepted findings (`C1`, `S2`), and the contract seams touched by `layout.css` (ignoring untouched modules); when `layout-overflow` recurs in `layout.css` in Round 3 after two fixer passes, the orchestrator stops dispatching narrow fixers for it and escalates to a root-cause design task or a Tier 2 `orca ask` (10-minute deadline)
   - **Data before:** **Round 1 accepted**: `C1` (`layout.css`, category `layout-overflow`), `S2`; **Fixer diff**: `LAST_ROUND_HEAD..HEAD` touches only declared component files `layout.css` and `tests/test_layout.py`
   - **Walkthrough:**
     1. Because Fixer batch 1 stayed within its declared component scope, Round 2 stages closure mode: reviewers check `C1` and `S2` (`fixed` vs `still-open`) and audit `LAST_ROUND_HEAD..HEAD` plus its contract seams for regressions.
     2. Round 2 marks `S2` `fixed` and `C1` `still-open` (the fix shifted the overflow to another breakpoint). Fixer batch 2 attempts a second fix.
     3. Round 3 closure review finds the same `layout-overflow` defect on the same `layout.css` seam for the second consecutive fix round.
     4. The orchestrator triggers the recurring-defect escalation rule instead of dispatching a third narrow fixer.
   - **Data after:** **Round 2 scope**: ✓ delta + prior findings + touched seams (no full-branch re-discovery); **Round 3 action**: ✓ recurring `layout-overflow` escalated to root-cause redesign or Tier 2 ask rather than looping a 3rd narrow fixer

### Plan-time test topology, slow-suite guardrails, and role effort

10. **SC-10: Single-owner test files, narrow task acceptance, and automatic wave-gate test fixer**
    - **Given** Wave 1 has parallel tasks T1 (`create.py`, `tests/test_create.py`) and T2 (`builder.py`, `tests/test_builder.py`), plus an existing cross-cutting test file `tests/test_html_kit_docs.py` asserting pre-Wave-1 template count `4` (which Wave 1's contract changes to `5`)
    - **When** T1 and T2 complete their task acceptance and Step 7 runs the full-suite wave gate (taking 480s and failing only in `tests/test_html_kit_docs.py` on `assert count == 4`)
    - **Then** T1 runs only `pytest tests/test_create.py -q` and T2 runs only `pytest tests/test_builder.py -q`; at Step 7, the orchestrator logs the >5m slow-suite advisory (`pytest-xdist`, browser context reuse), automatically dispatches a wave-gate fixer with `tests/test_html_kit_docs.py` in scope, and re-runs Step 7 without stalling on a human question
    - **Data before:** **T1 scope**: `[create.py, tests/test_create.py]`; **T2 scope**: `[builder.py, tests/test_builder.py]`; **Unowned test**: `tests/test_html_kit_docs.py` asserts old template count `4`
    - **Walkthrough:**
      1. T1 and T2 run in parallel worktrees; each runs only its owned test file instead of the full Playwright suite.
      2. Both components pass mid-chain and wave-end scope audits, commit, and merge.
      3. Step 7 runs `python3 -m pytest -q` (480s), which fails in `tests/test_html_kit_docs.py` (`assert count == 4`, now `5` per Wave 1's contract) and exceeds the 300s slow-suite threshold.
      4. The orchestrator logs the >5m slow-suite advisory and dispatches a wave-gate fixer scoped to `tests/test_html_kit_docs.py` at `effort: "high"`.
      5. The fixer updates the assertion, Step 7 re-runs green and caches the result for tree `HEAD^{tree}`, and Step 8 reuses that cached result.
    - **Data after:** **Wave 1 stall time**: ✓ 0 minutes waiting on user; **Run journal**: ✓ slow-suite advisory logged; ✓ green wave-gate tree cached for Step 8

11. **SC-11: Subagent dispatches pin explicit reasoning effort by role**
    - **Given** a session where the user's global or session default effort level is set to `medium`, `high`, or `xhigh`
    - **When** SDD or `adversarial-review` dispatches workers across the pipeline
    - **Then** implementers, promote reviewers, refute reviewers, and fixers explicitly pass `high` effort (`effort: "high"` on `Agent` calls, `--thinking high` on `pi-watch` calls unless the alias ladder specifies a model-specific ceiling), tiebreak arbiters pass `medium`, and read-only Explore/survey subagents pass `low` or `medium`
    - **Role effort table:**

      | Role | Effort / thinking level | Rationale |
      |---|---|---|
      | Implementer | ✓ `high` | Prevents shallow implementations that add extra review and fix rounds |
      | Promote reviewer (stage 1) | ✓ `high` | Medium effort cut investigation turns by ~67% and missed a blocking `MEDIUM` in controlled replay |
      | Refute reviewer (stage 2) | ✓ `high` | Medium effort skipped browser reproduction on scrollspy and saved only ~1.4 agent-minutes across 3 lenses |
      | Fixer | ✓ `high` | Medium effort lifted a prose-width cap and weakened an existing test selector to pass acceptance |
      | Tiebreak arbiter (stage 3) | ✓ `medium` | Adjudicates already-gathered evidence with no shell tool; under 2 minutes wall time |
      | Explore / codebase survey | ✓ `low` or `medium` | Read-only file and symbol lookup |

## Decisions Locked

All decisions below were confirmed during brainstorming and govern downstream planning:

**Scope and delivery**
- Apply all five researched strategy groups in one cohesive spec, executed in phased waves across `skills/adversarial-review`, `skills/subagent-driven-development`, and `skills/writing-plans`.
- Implement via deterministic CLI extensions in `scripts/adversarial-review` paired with protocol and prompt updates in the three skills (Approach A), rather than prose-only workarounds or a separate `sdd-ctl` wrapper script.

**Test-once caching, pre-pass sharing, and diff hygiene**
- Key every green test execution in the run journal by `(tree_identity, exact_command)` (`HEAD^{tree}` plus clean status for committed trees, or `HEAD^{tree}` plus `CHAIN_SNAPSHOT_<n>` digest for uncommitted worktrees).
- Extend `scripts/adversarial-review prepass` so all three concurrent lenses in a round share a single pre-pass execution or consume the wave gate's verified green check record when `HEAD^{tree}` and `artifact_hash` match.
- Exclude vendored, generated, and lockfile paths by default in `scripts/adversarial-review resolve` (with an override flag to include all paths), and record omitted files in `ResolveResult.excluded_paths` so reviewers see what was filtered.
- Stage only the diff hunks and surrounding context lines cited by `claims[]` or `contested[]` into `refute-prompt.md` and `tiebreak-prompt.md` instead of re-inlining the full diff artifact.
- Forbid promote and refute reviewers from running the full test suite when `prepass.status == "pass"`; reproductions must run the narrowest single test or command that demonstrates the defect.

**Human gates, deadlines, and adjudication logging**
- Classify human interactions into three tiers: Tier 1 blocking (consolidated 1-card preflight and final blocked handoff), Tier 2 10-minute deadline (`orca ask --timeout-ms 600000` with a recommended `default`, logged as `assumed, timed_out` on expiry), and Tier 3 non-blocking logged digest (review-finding adjudications).
- Pre-check candidate aliases (`pi-watch --check`) in scratch before prompting, then present a single consolidated preflight card covering backend pairing, dirty-tree or untracked-file handling, and environment readiness.
- Never end an orchestrator turn while an `orca ask` card is open; continue unblocked components while polling `orca ask wait` across chunks until answered or timed out.
- Emit a compact per-round adjudication digest table (accepted, dismissed, and regraded findings with one-line reasons) and dispatch fixers immediately; treat any asynchronous user veto as a follow-up fix task in the next batch without rolling back in-flight work.
- Never auto-override a 5-round loop cap with open `CRITICAL` or `HIGH` findings or an unrecoverable twice-failed chain on timeout; those remain Tier 1 hard stops at handoff.

**Stage-sized checkpoints, closure rounds, and recurring defects**
- Run non-final wave checkpoint reviews synchronously before wave N+1 at `--depth standard` (independent promote and refute, no tiebreak), while keeping Final Round 1 at `--depth deep`.
- Run Final Rounds 2 through 5 as closure passes (per `adversarial-review` § Running rounds): verify prior accepted findings (`fixed` vs `still-open`), review the fix delta (`LAST_ROUND_HEAD..HEAD`) and touched contract seams for regressions, and fall back to full-branch discovery only when a fixer modified paths outside its declared component scope.
- Escalate any defect that recurs in the same category and file seam after two fixer attempts to a root-cause task or a Tier 2 deadline-backed question rather than dispatching a third narrow fixer.

**Plan-time test topology, slow suites, and role effort**
- Require `writing-plans` decomposition to assign every created or modified test file in a wave to a single owning task (or a single serialized component chain), and scope each task's `Acceptance` command to its owned test files, leaving the full suite to Step 7's wave gate.
- Auto-dispatch a scoped wave-gate fixer before checkpoint review when Step 7's full-suite run fails solely because an unowned test file asserts pre-wave behavior that the wave's contract intentionally changed; ask (with a 10-minute deadline) only if the failure exposes a contract conflict.
- Log a slow-suite optimization advisory (`pytest-xdist`, Playwright browser-context reuse) in the run journal and final summary whenever a wave-gate or pre-pass test run exceeds 5 minutes, while preventing parallel full-suite runs through tree-once reuse and reviewer bounds.
- Explicitly pin reasoning effort per role: `high` for implementers, promoters, refuters, and fixers; `medium` for tiebreak arbiters; and `low` or `medium` for read-only Explore/survey subagents.

## Scope & non-goals

**In scope**
- `skills/adversarial-review/scripts/adversarial-review`: shared/reused pre-pass verification (`--reuse-check` and shared `prepass.json` across lenses), default pathspec excludes with `excluded_paths[]` in `ResolveResult`, and hunk-excerpted claim context in `claims` output.
- `skills/adversarial-review/SKILL.md`, `profiles/code-diff.md`, `assets/promote-prompt.md`, `assets/refute-prompt.md`, `assets/tiebreak-prompt.md`, and `assets/composition-contract.md`: narrow-reproduction rules forbidding full-suite runs when pre-pass is green, excerpted artifact staging in refute/tiebreak, closure-round prompt guidance, and role effort pins.
- `skills/subagent-driven-development/SKILL.md`, `assets/implementer-prompt.md`, and `assets/fixer-prompt.md`: single-card preflight, `tree_test_cache` reuse across acceptance and wave gates, three-tier human gate rules with 10-minute `orca ask` deadlines, non-blocking adjudication digests with follow-up veto, `--depth standard` checkpoints, closure-mode final rounds 2+, recurring-defect escalation, auto-dispatched wave-gate test fixers, >5m slow-suite advisory, and role effort pins.
- `skills/writing-plans/SKILL.md`: single-owner test-file assignment rule, task-scoped `Acceptance` command rule (with full suite reserved for the wave gate), and alignment of the standalone plan-document-reviewer wording with SDD's inline decomposition carve-out.
- Unit and integration tests in `tests/` covering the new `scripts/adversarial-review` flags, chain/hash invariants, default excludes, and excerpt generation.

**Non-goals**
- Directly editing target repositories' test runners or installing `pytest-xdist` inside a target repo during an SDD run.
- Speculative off-critical-path checkpoint execution (starting Wave N+1 before Wave N's checkpoint review finishes).
- Building a separate `sdd-ctl` wrapper binary or SQLite daemon outside `scripts/adversarial-review`.
- Relying on Claude Code harness-specific features (such as experimental agent teams or prompt-caching flags).
- Lowering reasoning effort on implementers, promoters, refuters, or fixers below `high`.

## Industry Insights

External research and in-session transcript mining established four findings that anchor this design:

- Anthropic's autonomy study found that choosing between approaches is the single most common reason agents stop for human input (35%). Temporal's human-in-the-loop approval pattern pairs a blocking signal wait with a durable timeout and an explicit default branch so unattended workflows degrade predictably instead of stalling indefinitely. Delivering notifications at task boundaries also nearly halves response latency across 7,745 measured notifications. Sources: [Anthropic autonomy study](https://www.anthropic.com/research/measuring-agent-autonomy), [Temporal approval pattern](https://docs.temporal.io/design-patterns/approval), [Devin 2.1](https://cognition.com/blog/devin-2-1), [Kunkel et al. 2023](https://eprints.bournemouth.ac.uk/38820/1/Kunkel,%20Hayduk,%20&%20Lock%20(2023)%20Push%20it%20real%20good.pdf).
- Bazel skips re-running a test when a passing result already exists for the same input digest (`--cache_test_results=auto`). In Playwright suites, reusing a browser instance with fresh per-test `BrowserContext` objects cut median fixture time from 476 ms to 218 ms, while running 8 concurrent browser workers yielded 5.2x (rather than 8x) speedup and caused timeouts when multiple suites contended on one machine. Sources: [Bazel command-line reference](https://bazel.build/reference/command-line-reference), [Playwright BrowserContexts](https://playwright.dev/python/docs/browser-contexts), [Skyvern benchmark](https://www.skyvern.com/blog/puppeteer-vs-playwright-complete-performance-comparison-2025/), [TestMu AI parallel testing](https://www.testmuai.com/learning-hub/playwright-parallel-testing/).
- Controlled evaluation of multi-turn LLM code review showed F1 dropping from 0.376 in round 1 to 0.303 in multi-turn review and 0.263 in independent re-review as false positives outpaced new true positives. A separate study of automated repair loops found that search/replace fixers damaged correct code faster than they repaired defects (0.29 damage rate against 0.023 repair rate on one model) when trapped in pseudo-fix cycles. Both Anthropic's Code Review docs and Cursor Bugbot converge after round 1 by restricting re-review to high-severity issues or incremental fix deltas. Sources: [More Rounds, More Noise (arXiv 2603.16244)](https://arxiv.org/abs/2603.16244), [If It's Not Buggy, Don't Fix It (arXiv 2609.10123)](https://arxiv.org/html/2609.10123v1), [Claude Code Review docs](https://code.claude.com/docs/en/code-review), [Cursor Bugbot docs](https://cursor.com/docs/bugbot), [Nine Judges (arXiv 2605.29800)](https://arxiv.org/html/2605.29800v1).
- Replaying wave 2 of reference run `bd307ed1` at `medium` versus `high` effort on Sonnet showed that `medium` promoters ran ~3x faster in model time (5.8 vs 16.8 agent-minutes) only by cutting investigation turns from 26–52 down to 9–14, missing a blocking `MEDIUM` finding (`C1`) and downgrading two others. On refuters and fixers, `medium` saved under 1 minute of model time per agent, and the `medium` layout fixer introduced a test-weakening regression that failed 2 cross-check tests. Source: [`docs/quirk/explorations/2026-10-15-sdd-wall-clock.md`](../../explorations/2026-10-15-sdd-wall-clock.md).

## Deferred Ideas

The following items were considered and excluded from this spec:

- Speculative off-critical-path wave checkpoints (starting Wave N+1 while Wave N's checkpoint review runs in the background), because an interface-changing checkpoint finding would force rework across Wave N+1, and `--depth standard` checkpoints with cached pre-passes capture most of the latency reduction without rework risk.
- Machine-wide lockfile semaphore wrapper for test commands (`[tech-spec]` / future tooling), in favor of eliminating overlapping full-suite runs via tree-once caching, shared pre-passes, and task-scoped acceptance commands.
- Planted-false-finding benchmark for `medium`-effort refuters, because refuters already finish in under 2 minutes wall time, so keeping refuters at `high` costs under 1.5 agent-minutes per round while avoiding false-pass risk.
- Dependency-driven cross-wave task backfilling (Co-Coder style DAG dispatch across wave boundaries), because wave imbalance cost at most 6 minutes outside the single reference outlier, and removing wave barriers would complicate the authoritative wave-end scope audit.

## Glossary

The terms below carry specific meanings throughout this spec:

- `tree_identity`: the content address of a repository state, computed as `git rev-parse <ref>^{tree}` with a clean working tree for committed states, or `(HEAD^{tree}, snapshot_digest)` when uncommitted work is present in a component worktree.
- `tree_test_cache`: the run-journal map from `(tree_identity, exact_command)` to `{exit_code, duration_s, output_tail, recorded_at}` used to avoid re-running identical test commands on unchanged bytes.
- Closure round: any final-loop review round after Round 1. Instead of re-running open-ended discovery over `RUN_BASE..HEAD`, a closure round verifies whether prior accepted findings are closed and checks `LAST_ROUND_HEAD..HEAD` plus touched contract seams for regressions.
- Three-tier human gate: the classification of user interactions into Tier 1 (blocking preflight and blocked final handoff), Tier 2 (10-minute `orca ask` deadline with recommended default for recoverable mid-run questions), and Tier 3 (non-blocking logged round digest with async user veto for review-finding adjudications).
- Recurring defect class: a finding raised in round N+1 that matches an accepted finding from round N in both defect `category` and target file or contract seam after a fixer attempt.
