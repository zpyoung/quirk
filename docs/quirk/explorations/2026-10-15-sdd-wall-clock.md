> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: cutting SDD wall-clock time

**Date**: 2026-10-15 · **Emphasis**: research-heavy · **Intensity**: 0.5 (Exploratory)

## Framing

A page-shapes SDD run (session `bd307ed1`) took 5h52m before reaching its final review loop, and the orchestrator itself only worked for about 35 minutes of that. The question is where the rest goes and which levers would cut it, across SDD orchestration, the adversarial-review pipeline, test execution in target repos, and human-in-the-loop latency. Claude Code harness features were out of scope. On rigor, some trade is acceptable as long as the final review stays strict.

Depth was deep and multi-round. A breadth round of six agents (two internal, four web) ran first, then a second round on three gaps: two agents mining past transcripts and one deep-research agent.

## What was explored

- Where the SDD and adversarial-review protocols require serial waits, repeated verification and user questions, with file:line evidence
- Whether the reference run's waste patterns recur across 7 other SDD runs on this machine
- Every human question asked across 8 runs: wait time, category, and how often the recommended option won
- Review rounds across 8 runs: duration, severity mix, and what late rounds found
- What makes review staging slow (pre-pass, diff size, prompt size)
- External evidence: multi-agent scheduling, LLM review cost against quality, test-suite acceleration, human-in-the-loop latency, and stopping rules for review→fix loops
- Left out: Claude Code harness features (agent teams, prompt caching, background dispatch mechanics)
- _Steered:_ at scoping, the user excluded harness features and allowed some review-rigor trade. At the idea gate, they flagged all eleven directions to go deeper and dropped none.

## Findings

### Theme: waiting on people is the biggest and most repeated cost

- 839 minutes of user waits across 8 runs, from 35 Orca cards and 45 questions. Seven waits over 40 minutes make up 714 of those minutes. (mined transcripts)
- A question stalled the critical path in 5 of 7 runs, from 12 to 154 minutes. Two of those ended the turn with the card still pending. The rest blocked in a background `orca ask wait` loop, but the wait was just as long. (mined transcripts)
- The recommended option was accepted 38 of 43 times (88%). Review-finding adjudication was the biggest category at 448 minutes, and its recommendation was accepted 15 of 15 times. (mined transcripts)
- Four of the five non-recommended answers involved state only the human knew: their own uncommitted edits, a local install fix, or a preference to fix later. A 10-minute default-on-timeout would have auto-answered 10 of 27 cards, covered 661 of 839 minutes, and got one wrong (a loop-exit "fix and finish" call). A 5-minute timeout would have got four wrong. (mined transcripts)
- In the SDD skill, every failure-routing row "defaults to stop and ask rather than improvise", with no timeout or default specified (`skills/subagent-driven-development/SKILL.md:206-208, 412-414, 648-650, 677-679`). The captain control-plane spec names the problem ("Human gates stall the run when the user steps away") and deferred the fix. (protocol map)
- Anthropic measured that Claude Code's most common reason for stopping is a choice between approaches (35%). Devin 2.1 asks for approval only when its plan confidence is low. Temporal's approval pattern pairs a blocking wait with a durable timeout and an explicit unanswered branch. — [Anthropic autonomy study](https://www.anthropic.com/research/measuring-agent-autonomy), [Devin 2.1](https://cognition.com/blog/devin-2-1), [Temporal approval pattern](https://docs.temporal.io/design-patterns/approval)
- Delivering notifications at interruptible moments nearly halved response times (7,745 notifications). Decision-fatigue evidence is weak and contested, so it isn't a design basis. — [Kunkel et al. 2023](https://eprints.bournemouth.ac.uk/38820/1/Kunkel,%20Hayduk,%20&%20Lock%20(2023)%20Push%20it%20real%20good.pdf)

### Theme: the same tree gets tested many times

- Review staging is slow because the pre-pass runs the full suite once per lens, serially or in parallel, on a tree the orchestrator gated minutes earlier. In run `c632d703`, about 71 minutes of setup were 70.7 minutes of pytest. Run `569f4f36` spent about 46 minutes in pre-pass, and three parallel runs caused vitest timeouts. Diff generation and hashing take 0.2 s. (staging dissection)
- Per round, the suite ran 4 to 10 times on an identical tree: the orchestrator's gate, the per-lens pre-pass, and reviewer reproductions. (staging dissection)
- The orchestrator reruns each implementer's acceptance command by design ("a claim never overrides a run", `SKILL.md:418-421, 670-672`). This happened in 6 of 7 runs and cost 28, 24 and 11 minutes in the three heaviest. (protocol map, mined transcripts)
- In the reference run, promote reviewers ran broad browser-test subsets of up to 10 minutes. Several hit the 580 to 601 s timeouts. Nothing in `profiles/code-diff.md` bounds a reproduction, so this behavior is allowed. In the other runs, reviewer test time was small. (staging dissection, protocol map)
- The script can already share one pre-pass across three lenses: run `cdaba84f` did it and its gates passed. It can't take a precomputed gate result. `run_prepass` always executes `--check-cmd`, and the artifact hash is the diff's sha256, which doesn't identify the checked-out tree (`scripts/adversarial-review:306-328, 424-435`). (staging dissection)

### Theme: late review rounds rarely change the outcome

- After final round 1, a HIGH blocking finding appeared in 6 of 16 rounds. Five of those came from one run (`3cbb7331`). Without it, the rate is 1 in 11. Final round 1 itself had a HIGH in 5 of 8 runs, and checkpoints had one in 2 of 14. No CRITICAL appeared anywhere. (mined transcripts)
- Rounds ≥3 ran in 4 of 8 runs, about 76 active minutes in total. Outside `3cbb7331`, only one of those rounds added a new accepted finding. (mined transcripts)
- Re-reporting shows up in three forms:
  - Several lenses report the same defect in one round. 13 raw findings collapsed to 5 in one run, and 8 to 5 in another.
  - The same defect class recurs after a fix. q-compare overflow came back across 3 rounds and quadratic regexes across 4.
  - Already-dismissed findings get re-raised. (mined transcripts)
- In a measured study, multi-turn review lowered F1 from 0.376 to 0.303 and independent re-review dropped it to 0.263. False positives rose as real errors ran out. — [More Rounds, More Noise](https://arxiv.org/abs/2603.16244)
- Fixers damage correct code. With search/replace edits, damage outran repair (0.29 against 0.023 for one model), and loops fall into pseudo-fix cycles. — [If It's Not Buggy, Don't Fix It](https://arxiv.org/html/2609.10123v1)
- Anthropic's Code Review docs suggest a "re-review convergence" rule: after the first review, report only Important findings. Cursor Bugbot defaults to incremental review of changes since the last review. One reported failure mode is that Bugbot marked a finding resolved after an unrelated commit. — [Claude Code Review docs](https://code.claude.com/docs/en/code-review), [Bugbot docs](https://cursor.com/docs/bugbot), [Bugbot forum report](https://forum.cursor.com/t/bugbot-appears-to-resolve-prior-inline-findings-after-an-unrelated-commit/154401)
- Extra LLM reviewers are correlated: a 9-judge panel carries about 2 independent votes. Majority voting matched or beat debate. — [Nine Judges](https://arxiv.org/html/2605.29800v1), [Debate or Vote](https://arxiv.org/html/2508.17536v1)
- SDD hard-codes `deep` depth for every checkpoint and final round. The skill itself calls cheaper checkpoints an open question (`SKILL.md:530, 546-550`). (protocol map)

### Theme: test suites and scheduling matter in some repos, not all

- Suites over 5 minutes dominated 2 of 7 runs plus the reference run, where tests took about 40% of machine time. The other runs' suites take 3 minutes or less. (mined transcripts)
- In the reference repo, each browser test spawns a Node harness that launches a fresh Chromium, and pytest-xdist isn't installed. Playwright treats a new browser context as cheap and isolated compared with a new browser. One vendor measurement: 476 ms median for a cold launch plus workflow, against 218 ms for a reused browser. — [Playwright contexts](https://playwright.dev/python/docs/browser-contexts), [Skyvern](https://www.skyvern.com/blog/puppeteer-vs-playwright-complete-performance-comparison-2025/)
- Concurrent browser suites contend: one measurement got 5.2x from 8 workers. Parallel pre-pass runs caused vitest timeouts in run `569f4f36`. — [TestMu AI](https://www.testmuai.com/learning-hub/playwright-parallel-testing/)
- Test impact analysis (pytest-testmon) is coverage-based and can't see the Node subprocess. JS-only changes would miss the browser tests without explicit path triggers. — [testmon](https://www.testmon.org/)
- Out-of-scope test files blocked tasks in 2 of 7 runs plus the reference run. (mined transcripts)
- Wave imbalance (slowest task more than 2x the median) appeared in 3 of 6 runs but cost at most 6 minutes in each. The reference run's 17-minute imbalance is the outlier. (mined transcripts)
- Co-Coder replaced layer barriers with dependency-driven dispatch and reported 1.8 to 2.1x speedups. Naive file-level parallelism didn't help, because agents produced conflicting interfaces. These are author-reported numbers on 28 tasks, read from a summarizing fetch. — [Co-Coder](https://arxiv.org/html/2606.00953v1)

### Theme: review prompt size and model time

- The script applies no exclusions to the diff (`scripts/adversarial-review:129-150`). One run's range diff was 7.0 MB, 90% of it vendored. Every orchestrator hand-rolled its own excludes. Refute and tiebreak prompts inline the artifact again. (staging dissection)
- Model generation was 43% of subagent time in the reference run. All 58 subagents inherited high effort. (reference timing report)
- In a verification study, Opus cost about 21x Qwen-3-Coder for 9 more recall points. One reported GPT-5 judging result is that high effort cost about 3x low for about 1.5 accuracy points. That result came from a search summary and wasn't verified. — [Tencent LLM4PFA](https://arxiv.org/html/2601.18844), [arXiv 2512.01232](https://arxiv.org/pdf/2512.01232)

## Idea landscape

Eleven directions, unranked. At the idea gate, all eleven were flagged to go deeper and none were dropped. Each one notes the minutes it could address across the 8 mined runs, from the findings above. These are upper bounds and they overlap, because the same minute can be claimed by more than one direction.

### Direction: test each tree once
Record every green test run by the tree it ran on (`HEAD^{tree}`, a clean status and the exact command). The pre-pass, the orchestrator's acceptance rerun and reviewer reproductions would consult that record before running anything. The principle "a claim never overrides a run" still holds, because the reused result is the orchestrator's own run of the same command on the same bytes. What changes is that the run counts once.
*why this might actually work:* The suite ran 4 to 10 times per review round on an identical tree. The script already chains artifacts by `run_id` and re-hashes cheaply, so the missing piece is binding to tree identity rather than diff identity.
*addressable:* about 70 min of pre-pass in `c632d703`, 46 min in `569f4f36`, and roughly 90 min of acceptance reruns across four runs. Most of this sits on the critical path.
*surfaced by:* first-principles (what does each check need to know?) · *sits at intensity:* Grounded

### Direction: questions with a deadline
Every question carries a recommended default and a timeout scaled by how reversible the choice is. The run keeps working on anything the question doesn't block, and notifies when the deadline is near. Questions about state only the human knows (their uncommitted edits, local installs) move to preflight, where a wrong default does the most damage and the human is most likely present.
*why this might actually work:* 88% of 43 questions went with the recommendation, and 4 of the 5 misses were about human-held state that preflight could have asked up front. A 10-minute timeout would have covered 661 of 839 waiting minutes with one wrong answer.
*addressable:* up to 661 min across 8 runs. 128 min in the reference run alone.
*surfaced by:* assumption reversal (assume nobody is watching) · *sits at intensity:* Exploratory

### Direction: log adjudications instead of asking
Adjudicating review findings stops being a question. The orchestrator decides with the gate's verdict and records each decision in the run journal. The human gets a digest they can veto asynchronously, and a veto becomes a follow-up fix task rather than a rollback.
*why this might actually work:* This category was the largest wait (448 min, median 21.6 min per card), and the recommendation was accepted 15 of 15 times.
*addressable:* about 448 min across 8 runs.
*surfaced by:* overlooked value (the recommendation already does the work) · *sits at intensity:* Exploratory

### Direction: closure rounds after final round 1
After the first full final review, later rounds do two things. They verify each prior finding against the current code, and they review only the fix delta with surrounding context. A full pass returns only when a fix touches files or behavior outside its finding. The loop exits when no HIGH survives refutation, and LOW and MEDIUM findings go to a log.
*why this might actually work:* Outside one outlier run, HIGH blockers appeared in 1 of 11 rounds after final round 1. Measured studies show repeated full re-review adds false positives faster than recall. Anthropic's and Cursor's shipped reviewers already converge by severity or review incrementally.
*addressable:* about 76 active minutes in rounds ≥3, plus loop-exit questions (182 min of waiting) that a clear exit rule would remove.
*surfaced by:* research, stopping-rule literature · *sits at intensity:* Exploratory

### Direction: escalate recurring defects
When a finding in the same defect class comes back after a fix, the next step changes. Instead of another fixer and another round, the defect goes to a root-cause task with design-level scope, or to the human.
*why this might actually work:* In 4 runs a defect class recurred across 3 to 5 rounds (q-compare overflow, quadratic regexes, invented values, a read-only tab). The literature describes the same pattern as pseudo-fix cycles, with fixer damage outrunning repair.
*addressable:* most of `3cbb7331`'s 44 active minutes in rounds 3 to 6, plus repeat rounds elsewhere.
*surfaced by:* contrarian inversion (a recurring finding is a planning signal, not a review signal) · *sits at intensity:* Exploratory

### Direction: checkpoint review off the critical path
Once wave N passes its gate, wave N+1 starts building on that tree while wave N's checkpoint review runs in the background. Its findings join the next fix batch instead of blocking the wave.
*why this might actually work:* The skill itself says the final loop "re-examines everything anyway" (`SKILL.md:510-511`). Merge queues (GitHub, Uber SubmitQueue) already test speculatively on top of unmerged work and only discard on failure.
*addressable:* checkpoint rounds took 90 min in the reference run, about 55 in `569f4f36`, 46 in `c632d703` and 35 in `cdaba84f`. Overlap would recover most of that wall clock, minus rebase and rework cost.
*surfaced by:* analogical transfer (speculative merge queues) · *sits at intensity:* Bold

### Direction: size review by stage
Checkpoints run lighter: `standard` depth, or one merged lens with the three concerns in a single prompt. The final loop keeps three lenses at `deep`.
*why this might actually work:* Checkpoints produced a HIGH in 2 of 14. Lenses overlap heavily (13 raw findings collapsed to 5 in one round), and correlated reviewers add little beyond the second. The skill already leaves cheaper checkpoints as an open question.
*addressable:* a share of the same checkpoint minutes as the previous direction, with no change to scheduling.
*surfaced by:* SCAMPER (eliminate and combine) · *sits at intensity:* Grounded

### Direction: plan-time test topology
At decomposition, the planner names which tests each task owns, gives every shared test file exactly one owner, and scopes each task's acceptance to its own tests. The full suite runs only at the gate.
*why this might actually work:* Out-of-scope test files blocked tasks in 3 of 8 runs. In the reference run, that block caused the re-plan question that sat for 128 minutes. Claude Code's own guidance prefers single tests over the whole suite.
*addressable:* the reference run's 128-minute stall (shared with "questions with a deadline"), plus narrower acceptance runs in every task.
*surfaced by:* first-principles · *sits at intensity:* Grounded

### Direction: faster suites in target repos
In repos where tests are slow:
- run pytest-xdist
- share one Chromium per worker with a fresh context per test
- cap concurrent suite runs machine-wide with a lock, so parallel agents don't starve each other

Quirk can only nudge here, for example by having the preflight or a planning note flag a suite over 5 minutes.
*why this might actually work:* Suites over 5 minutes drove about 40% of machine time in the runs where they existed. Playwright treats contexts as cheap and isolated compared with launches. Contention already caused timeouts.
*addressable:* about 175 machine-minutes of tests in the reference run, and 121 and 149 test minutes in the two other heavy-test runs.
*surfaced by:* research · *sits at intensity:* Grounded

### Direction: diff hygiene in the review script
The script excludes vendored, generated and lockfile paths by default and lists them by `--stat`, so every orchestrator stops hand-rolling excludes. Refute and tiebreak prompts could reference findings and line ranges rather than re-inlining the full artifact.
*why this might actually work:* One range diff was 7.0 MB and 90% vendored, and an 818 KB first attempt was discarded and re-staged. Each orchestrator reinvented its own excludes.
*addressable:* hard to measure. Re-staging rework was about 8 to 17 min in `c632d703`, and smaller prompts mean faster reviewer turns.
*surfaced by:* radical simplification · *sits at intensity:* Grounded

### Direction: effort and model by role
Set reasoning effort per role: medium for refuters, fixers, surveys and tiebreak arbiters, and high for implementers and promoters. Make the tiebreak cross-family wherever one is reachable.
*why this might actually work:* Model time was 43% of subagent time, and every subagent inherited high effort. In the verification studies found, higher effort or bigger models bought a few accuracy points at many times the cost.
*addressable:* small for the roles it targets. In the reference run, promoters took 50% of subagent model time (70 min) and implementers 33% (46 min). Refuters, fixers, surveys and tiebreaks together took 16% (23 min), and most of that was off the critical path. Promoters averaged 8.5 s per turn and implementers 10.7 s, against about 5 s for refuters and fixers. Part of each turn is reading the large prompt, which effort doesn't change. The transcripts redact thinking, so the share effort could cut is unknown.
*measured on promoters (one commit, one run per arm):* the reference run's wave 2 promote prompts were rerun on Sonnet at medium and again at high, against a clone of the reviewed commit (`9628c57`). Medium cut model time from 16.8 to 5.8 agent-minutes and the slowest lens from about 6 to 3 minutes of model time. Seconds per turn barely moved (7 to 13 at both levels). The saving came from medium taking 9 to 14 turns per lens against 26 to 52, so medium investigates less, not faster. It raised 5 distinct issues against 7 at high and 10 in the original high run. Five issues turned up in both high runs. Medium found 4 of them and missed the longform sidenote overlap, which the original run gated as a blocking MEDIUM. Medium also graded the other two blocking MEDIUMs (the unscoped 70ch cap and the last-section nav highlight) as LOW. The two high runs shared only 5 of their 12 issues, so run-to-run noise is about as large as the effort effect.
*measured on refuters and fixers (same setup):* the three wave 2 refuters at medium and high took 1.6 and 3.0 agent-minutes of model time, against 2.3 originally, and none ran longer than 2 minutes wall. On the 10 findings, all real, medium and high gave the same disposition every time. Where either differed from the original run (C4 standing rather than contested, X2 graded LOW rather than MEDIUM), they differed the same way, so the cause is noise, not effort. Medium reproduced less. It called X2 "a known scrollspy limit" where high rebuilt the page and scrolled it. No refuter in the reference run ever refuted anything, so this doesn't test whether medium lets a fabricated finding through. Fixers spent 0.4 to 2.4 minutes of model time and 18 to 22 minutes in tool calls, most of it test runs. For the one-finding create.py fix, both levels were correct, and each new test failed on the unfixed code. For the eight-finding layout fix, both passed their own acceptance run. High's fix also passed medium's test file and the original run's (`e0587b3`). Medium's failed 2 tests in both. It lifted the 70ch cap inside longform and rewrote the existing prose-cap test to check only unclassed paragraphs, so small-type paragraphs now run past 70ch.
*surfaced by:* research · *sits at intensity:* Grounded

## Tensions & trade-offs

- The tree-once record pulls against the rule that the orchestrator verifies by running. That rule exists because a captain and the orchestrator once used different grep flags and got different answers. Reusing a result is only as sound as the key, and environment variables, time, external services and built JS bundles aren't in a tree hash.
- Defaults on timeout pull toward throughput. The 4 of 5 wrong recommendations pull toward asking, because each was about something only the human could see. Both are true, so the open question is which questions belong at preflight.
- Logging adjudications assumes the 15 of 15 acceptance rate means the recommendations were right. It may instead mean the human was rubber-stamping, which the autonomy literature calls "meaningless approvals". Removing the question would hide the difference.
- Closure rounds and stage-sized review both say late or early review adds little. The outlier run `3cbb7331` used codex reviewers at full independence and kept finding real HIGHs through round 6. That suggests "late rounds rarely find much" may partly reflect same-family reviewers missing things.
- Moving checkpoint review off the critical path saves the most wall clock, but it removes the checkpoint's stated purpose: not building wave N+1 on a defect. Stage-sized review keeps that purpose and saves less.
- Repo-level test speed is where the biggest machine-time savings sit, but quirk doesn't own target repos, so its lever there is indirect.
- Lower effort on promoters buys real speed, about 3x less model time, by cutting investigation depth. That is the same thing recall depends on, and in the one trial it dropped a blocking finding that both high runs caught. For refuters and fixers the speed side is close to nothing, under a minute of model time each, because they are short or test-bound. The quality side wasn't free either: one of two medium fixes weakened an existing test to pass.

## Challenge notes

- **Test each tree once.**
  - Steelman: identical bytes and an identical command give an identical result, so a rerun only buys flake detection.
  - Strongest counter: the suites aren't hermetic. Browser tests depend on installed Chromium, Node and the network, and a flaky pass gets cached as truth.
  - Would be disproven if: re-running cached-green trees in past runs ever turned up a failure.
- **Questions with a deadline.**
  - Steelman: almost all of the wall clock lost to people came from questions whose recommended answer was taken anyway.
  - Strongest counter: a wrong default on a loop-exit or scope question can waste more time than the wait, and nobody notices until later.
  - Would be disproven if: replaying past runs with the default applied showed the five misses causing rework longer than the waits saved.
- **Log adjudications instead of asking.**
  - Steelman: the gate's verdict already encodes the evidence, and the human agreed every time.
  - Strongest counter: the human's agreement may be the only check on a reviewer pipeline that is reduced-independence in 4 of 7 runs.
  - Would be disproven if: a later digest review vetoes adjudications at a meaningful rate.
- **Closure rounds after final round 1.**
  - Steelman: the data and the literature both say late full rounds mostly find noise and re-reports.
  - Strongest counter: fixers damage code, and a fix-delta review might miss a regression the fix causes elsewhere.
  - Would be disproven if: replaying rounds 3 to 6 as delta-only shows a blocking finding that delta review would have missed. `3cbb7331` is the test case.
- **Escalate recurring defects.**
  - Steelman: a defect that survives two fixes is a design problem, and another fixer round treats the symptom.
  - Strongest counter: some recurrences are distinct bugs that share a label. Escalating them all adds human waits back in.
  - Would be disproven if: recurring-class findings in the 4 runs turn out to be different root causes most of the time.
- **Checkpoint review off the critical path.**
  - Steelman: the final loop re-checks everything, and the gate already proves the tree builds and passes.
  - Strongest counter: a checkpoint finding that changes an interface forces rework across the whole next wave, which costs more than the wait.
  - Would be disproven if: checkpoint findings in past runs touched interfaces the next wave built on.
- **Size review by stage.**
  - Steelman: checkpoints rarely find HIGHs, and three lenses mostly re-find the same issues.
  - Strongest counter: the 2 checkpoint HIGHs might be exactly the ones worth catching early.
  - Would be disproven if: a single merged lens misses findings the three lenses caught at past checkpoints.
- **Plan-time test topology.**
  - Steelman: the 128-minute stall started as a test-ownership gap that the plan could have closed.
  - Strongest counter: shared test files are often unknowable at plan time, because the plan can't predict which assertions an implementation will break.
  - Would be disproven if: blocks in the 3 runs came from test files the planner couldn't have identified.
- **Faster suites in target repos.**
  - Steelman: this is the biggest machine-time lever, and the techniques are standard.
  - Strongest counter: xdist exposes shared temp dirs and ports in older suites, and fixing those is repo work SDD can't do mid-run.
  - Would be disproven if: the heavy suites turn out to be serial for a reason, such as shared fixtures or global state.
- **Diff hygiene in the review script.**
  - Steelman: vendored and generated bytes can't be reviewed meaningfully, and every orchestrator already drops them by hand.
  - Strongest counter: a malicious or broken vendored file is precisely what a security lens should see.
  - Would be disproven if: past findings ever came from vendored or generated paths.
- **Effort and model by role.**
  - Steelman: refuters and fixers do narrow, well-specified work, where extra thinking buys least.
  - Strongest counter: refutation is the main defense against false positives, and weakening it lets noise through to fixers, which cost more than the thinking saved.
  - Would be disproven if: an eval on past findings shows medium-effort refuters keeping findings that high-effort refuters killed.

## Open questions & gaps

- No controlled evidence exists, internal or external, on delta review against full re-review for catching fixer-introduced bugs. The natural experiment is replaying `3cbb7331`'s rounds 3 to 6.
- The reviewer-family confound needs untangling: do codex-reviewed runs find more late HIGHs because the reviewer is better, because the code was worse, or because the runs differed in other ways?
- Recommended-acceptance measures agreement, not correctness. No run checked whether accepted recommendations were later reversed.
- The effort trials are one commit with one run per arm. In the promoter trial, the clone had no `node_modules`, so browser tests skipped in both new arms. The refuter and fixer trials had them. Nobody has measured whether medium refuters pass fabricated findings, because no real refuted finding exists to replay. Planting known-false findings would test it.
- The review-prompt size effect on reviewer turn latency wasn't measured.
- Co-Coder's dependency-driven speedups and the GPT-5 effort figure weren't verified against the papers' tables.
- Five Orca cards were still open when their transcripts ended, so those waits are lower bounds.
- This analysis covers 8 runs from one person's machine over about a month.

## Sources

- Internal evidence comes from read-only analysis of Claude Code transcripts `bd307ed1`, `d1d0ad87`, `cdaba84f`, `c632d703`, `273d9a68`, `b5fa0b44`, `3cbb7331` and `569f4f36`, plus the session scratchpads where they still exist. Role labels and round boundaries were parsed heuristically, and the counts for `d1d0ad87` and `b5fa0b44` are approximate. `bd307ed1` was still running when it was read.
- Protocol citations point to `skills/subagent-driven-development/SKILL.md`, `skills/adversarial-review/SKILL.md`, `skills/adversarial-review/scripts/adversarial-review` and `skills/adversarial-review/profiles/code-diff.md` in this repo, as of commit 55098ba.
- External sources are linked inline. Brave Search was unavailable, so web research used WebSearch and WebFetch only. Co-Coder's numbers and the GPT-5 effort figure came from summarizing fetches or search snippets and weren't checked against the papers' tables.

---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
