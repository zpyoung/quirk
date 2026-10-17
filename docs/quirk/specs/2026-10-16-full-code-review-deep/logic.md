# quirk:full-code-review deep mode

## Status & amendments

**Status:** Approved — Tech spec: authored (gate: >3 files; crosses subsystems; multi-session)

**Amendments:**
- 2026-10-17: Deep coverage planning. Areas hold up to 600 changed lines, weighted by the lines the diff changes. Each area lists its diff hunks, and a finder must examine every one. Before finders start, a capacity estimate checks whether the areas fit the budget (data flow steps 4 and 5; scenarios 9 and 10). Exceeding the time budget alone no longer makes a report incomplete (scenario 11; Decisions Locked, Cost and time budget).

## Purpose

On PR #50 at `3605fd8`, the standard full-code-review run found 6 Should fix and 20 Nits in about 33 minutes. The first wave of Claude Code's built-in `/code-review max`, on the same model, found 22 Should-fix-level and 48 Nit candidates before it was stopped. It matched 5 of the 6 Should fix findings and surfaced 17 more that the lenses missed. 51 of its 61 unique candidates were reproduced by running the code.

Deep mode closes that gap for the times you want the most thorough review and can spend the time. The standard run stays the default because it is fast and nearly noise-free, and noise is what makes people stop reading AI reviews.

## Conceptual model

Deep mode is an opt-in `--deep [minutes]` flag on the existing skill. It adds a defect hunt that runs beside the standard lenses, and both feed the same report and triage page.

The hunt has three parts. Area finders read one small area of the change line by line and may run code to prove a bug. A contract lens checks the places where one file's output is another file's input, and where the docs tell an agent to run a command. A checker then judges every candidate fresh, from the claim and the code alone, and reruns any repro itself.

Running code is what found the extra bugs, so it is also the risk. Code only ever runs in a throwaway copy, only on changes whose author is trusted, and only after you agree.

## Data flow

1. Steps 1 to 3 run as today: prepare the diff, source root, policy, guidance and memory.
2. If the seat may run code, one consent prompt says what will run and where. A fork, an untrusted author, or any GitLab reviewer run gets no prompt and no repros.
3. The risk lens runs first, as today.
4. The coordinator builds the area map. It splits the change into areas of up to 600 changed lines, keeps files that feed each other in the same area, lists the diff hunks each area's finder must cover, ranks the areas by priority, and writes a few questions for each area from the risk result and the diff. It then estimates whether the finders can cover every area in the time available. If they can't, an interactive run asks once whether to raise the budget, hunt only the top-priority areas, or continue anyway; a headless run hunts the top-priority areas that fit. The map is shown in the report.
5. The standard lenses, one area finder per area, and the contract lens run in parallel within the budget. Each finder reports which hunks it examined. A hunk it skipped goes to a follow-up finder, and time left before the 80% mark can go to second-wave finders that look at the change from a different angle.
6. Every deep candidate goes to a fresh checker. In deep mode, Must fix and Should fix findings from the standard lenses go to a checker too.
7. The coordinator merges deep findings with lens findings, drops duplicates, tags each finding with its evidence, and puts refuted candidates in a collapsed "checked and dropped" list.
8. Render and triage run as today.

The time budget covers the whole run. At about 80% of it, no new finders start, candidates already in hand still go to checkers, and the report is marked incomplete with the areas it didn't reach. The report is also marked incomplete when areas were left unhunted for capacity or hunks were left unexamined, and it names them. A run that covers everything but finishes after the budget is complete and carries a note saying so.

## Key decisions & rationale

- **Deep mode is opt-in and the standard run is unchanged.** The standard run is the cheap, quiet default; deep mode is for when recall matters more than time.
- **Area finders may run code; standard lenses never do.** Running code found the 17 extra bugs. Keeping the lenses read-only keeps the default run safe and fast.
- **A fresh checker reruns repros itself.** Research found that checkers which trust a finder's repro lean toward "yes, it's a bug".
- **Areas are bounded by size, and files that feed each other stay together.** Recall collapses on large diffs, and several missed bugs sat between a producer and its consumer, such as the triage export in `report.html` and `validate_triage.py`.
- **One trust rule decides who runs code.** It is the mutation probe's rule: the author seat, or the reviewer seat when the PR is not from a fork and the author is trusted.
- **Running out of budget ends in checking, never raw output.** You always get checked findings, and the incomplete label keeps a partial run from reading as a clean one.
- **Incomplete means something went unreviewed.** Finishing late doesn't make a review less thorough, so it is a note. Areas not hunted, hunks not examined and unchecked claims are the gaps that earn the label.
- **Hunks, not areas, are the unit of coverage.** An area can complete while its finder skipped a hunk, so the finder reports what it examined and the coordinator follows up on the rest.
- **Deep mode hunts defects only.** Reuse, simplification and efficiency stay with the standard lenses, which cover them cheaply.
- **Lens Must fix and Should fix findings are checked in deep mode.** Today nothing drops one that fails source verification; the checker closes that gap when it is already running.

## Behavior & scenarios

1. **Your own PR with `--deep`**
   - **Given** you authored PR #50 on GitHub and the checkout is at the PR head
   - **When** you run the skill with `--deep`
   - **Then** you get one consent prompt; ✓ area finders run code in throwaway copies; ✓ each finding is tagged reproduced or read from code; ✓ reproduced findings include the command and its output
   - **Walkthrough:**
     1. The skill asks once: run code in throwaway copies of PR #50 at `3605fd8`, network allowed, no `gh` or `glab`, budget 60 minutes. You agree.
     2. The area finder for the triage export reproduces a file named `a<b.py`* failing validation.
     3. A fresh checker reruns that repro and returns confirmed.
   - **Data after:** **Report**: ✓ "Triage paste fails for a file whose name contains <" (Should fix, reproduced, command and output attached); ✓ consent recorded in Assumptions

2. **A teammate's same-repo GitHub PR, author trusted**
   - **Given** you are reviewing a PR from a trusted author, not from a fork
   - **When** you run the skill with `--deep`
   - **Then** it behaves as in scenario 1, with the copy made from the PR head, never your branch

3. **A fork, an untrusted author, or any GitLab reviewer run**
   - **Given** the reviewer seat on a fork PR
   - **When** you run the skill with `--deep`
   - **Then** ✗ no consent prompt and no code runs; ✓ area finders, the contract lens and checkers run read-only; ✓ the coverage line says repros were off because the author isn't trusted

4. **A copy can't run the code**
   - **Given** an area whose tests need a dependency that isn't installed
   - **When** that area's finder starts
   - **Then** ✓ the finder carries on reading only; ✓ the coverage line names the area and the reason; the rest of the run is unaffected

5. **The budget runs out**
   - **Given** `--deep 30` on a large PR
   - **When** 24 minutes have passed and 3 of 9* areas haven't started
   - **Then** ✗ no new finders start; ✓ candidates already found go to checkers; ✓ the report shows "Incomplete review" and names the 3 areas it didn't reach
   - **Walkthrough:**
     1. At minute 24 (80% of 30), the coordinator stops starting finders.
     2. The 6 running finders finish; their 14* candidates go to checkers.
     3. The report renders with the incomplete label.
   - **Data after:** **Report**: ✓ verdict "Incomplete review"; ✓ coverage line lists the 3 unreached areas; ✗ no unchecked candidates shown

6. **The checker refutes a candidate**
   - **Given** a finder claims nested `REVIEW.md` files merge repo-wide by mistake
   - **When** the checker finds that this is the documented behaviour
   - **Then** ✓ the candidate goes to "checked and dropped" with the checker's reason; ✗ it never reaches triage

7. **A plausible finding**
   - **Given** a candidate whose trigger depends on what GitHub returns for your own pending comments, which can't be checked offline
   - **When** the checker returns plausible
   - **Then** ✓ it shows with what would confirm it; ✗ it can't be posted, even if you mark it Will fix

8. **Scoring a report against the answer key**
   - **Given** the PR #50 answer key at `3605fd8` and a deep-mode report of that commit
   - **When** you run the scoring script on the report
   - **Then** ✓ it lists each answer-key defect as caught or missed; ✓ it reports recall and the share of shown findings that were refuted on spot check

9. **A change too large for the budget**
   - **Given** `--deep 20` on a PR the map splits into 12* areas, with 4* finders running at a time
   - **When** the coordinator estimates capacity: 3* waves of about 8* minutes is 24*, but only 16* minutes (80% of 20) are available, so 8* areas fit
   - **Then** ✓ an interactive run asks once to raise the budget, hunt only the top-priority areas, or continue anyway; ✓ a headless run hunts the 8* highest-priority areas and lists the other 4 as not hunted; ✗ no area is silently skipped
   - **Walkthrough:**
     1. In a headless run, the coordinator ranks the 12 areas by priority and starts the top 8.
     2. The 4 lowest-priority areas are marked not hunted, with the reason "over capacity".
     3. The report renders with the incomplete label.
   - **Data after:** **Report**: ✓ verdict "Incomplete review"; ✓ coverage line names the 4 areas not hunted and says they were over capacity; ✗ no area shown as reviewed that wasn't

10. **A finder leaves hunks unexamined**
    - **Given** area A3 has four hunks, A3.h1 to A3.h4, and its finder returns having examined A3.h1, A3.h2 and A3.h4
    - **When** the coordinator records what the finder examined
    - **Then** ✓ a follow-up finder is dispatched for A3.h3; ✓ if it examines A3.h3, A3 counts as covered; ✗ if time runs out or A3.h3 is still unexamined, A3 is reported as incomplete with A3.h3 named
    - **Data after:** **Report**: ✓ when the follow-up fails, verdict "Incomplete review" and the coverage line names A3.h3 as unexamined

11. **A run finishes over budget with every area covered**
    - **Given** `--deep 30` where all 9* areas are completed with every hunk examined
    - **When** the last checker returns at minute 33*
    - **Then** ✓ the report is complete and its verdict is not "Incomplete review"; ✓ the coverage line notes the review took 33m against a 30m budget; ✗ no unreached areas are listed
    - **Data after:** **Report**: ✓ budget note in the coverage line; ✗ no incomplete banner. The run does not count toward the success criteria below, which need two runs inside the budget.

## Success criteria

Deep mode is done when two deep runs of PR #50 at `3605fd8`, each inside the 60-minute default budget, each catch every defect in the answer key, and no more than 1 in 5 shown findings in either run is refuted on spot check.

The answer key is every candidate from the built-in's first wave that a verification pass confirms as a real Should-fix-level defect, plus the 6 Should fix findings from the standard run. Nits are not in it. Finishing it is part of this work, because 43 of the built-in's candidates were never examined.

## Scope & non-goals

In scope: the `--deep [minutes]` flag and its consent prompt, the area map, area finders, the contract lens, the checker, the throwaway copy, the time budget, evidence tags and the "checked and dropped" list, the answer-key fixture, the scoring script, and finishing the answer key.

Not in scope:
- any change to the standard run; its lenses still never run code
- cleanup angles in deep mode (reuse, simplification, efficiency)
- turning deep mode on automatically by risk, or through a policy or pack key
- repros for forks, untrusted authors, or GitLab reviewer runs
- posting plausible findings, or any other change to posting

## Decisions Locked

**Execution and trust**
- Code runs in the author seat, and in the reviewer seat for trusted non-fork authors (the mutation probe's rule). GitLab reviewer runs never run code, because GitLab never reports author trust.
- One consent prompt per run says what will run and where, and is recorded in the report.
- Code runs only in a throwaway copy: no `gh` or `glab`, a temporary HOME and XDG dirs, your git config and the repo's hooks turned off, and network allowed. An OS-level sandbox is used when one is available, and a temporary worktree otherwise.
- When a copy can't run the code, deep mode carries on reading only and the coverage line says why.

**Cost and time budget**
- A time budget bounds the run, 60 minutes by default, set per run with `--deep <minutes>`.
- When the budget runs out, finding stops, what's in hand is checked, and the report is marked incomplete with the unreached areas named.
- Before finders start, the coordinator estimates whether the areas fit in 80% of the budget. A change that doesn't fit prompts once in an interactive run. A headless run hunts the top-priority areas that fit and names the rest as not hunted.
- A finder must examine every diff hunk in its area. Unexamined hunks get a follow-up, and any still unexamined make the report incomplete and are named.
- Exceeding the budget alone is a note, not an incomplete review. A run that is over budget still fails the success criteria.
- Finders and checkers use Sonnet, with today's risk-based escalation for checkers.

**Noise and output**
- Confirmed and plausible findings show; refuted ones go to a collapsed "checked and dropped" list.
- Each finding is tagged reproduced or read from code, and reproduced ones include the command and its output.
- Plausible findings never post.
- There is no cap on findings shown.

**Success and scope**
- Done means catching every answer-key defect, as defined under Success criteria.
- Deep mode hunts defects only.
- Recall is checked by a rerunnable scoring script against an answer key kept in the repo.
- Approach A: area finders that may run code, plus a fresh checker that reruns repros. Read-only finders with execution only in checking (B) and repeated lens passes with voting (C) were rejected because neither is likely to find the bug classes the lenses missed.

## Industry Insights

- Execution is the strongest precision lever in the literature: AnyPoC produced 37% more valid proofs of concept and rejected 9.7 times more false reports than Claude Code and Codex, and warns that naive LLM checkers lean toward "success" ([arXiv 2604.11950](https://arxiv.org/abs/2604.11950)). Generated reproduction tests doubled SWE-Agent's precision ([arXiv 2406.12952](https://arxiv.org/abs/2406.12952)).
- Commercial reviewers separate finding from checking: Anthropic's Code Review agents "verify bugs to filter out false positives" ([claude.com](https://claude.com/blog/code-review)); Cursor's BugBot uses a validator model and found that a cautious agent hurt its metrics ([cursor.com](https://cursor.com/blog/building-bugbot)); Qodo uses a judge agent ([qodo.ai](https://www.qodo.ai/blog/introducing-qodo-2-0-agentic-code-review/)).
- Recall collapses on large diffs, and ensembles of different models miss the same bugs ([arXiv 2606.15689](https://arxiv.org/html/2606.15689v1)).
- Recall-heavy tools are noisy: one vendor benchmark put Claude Code at 51% recall and 23% precision ([Augment](https://www.augmentcode.com/blog/we-benchmarked-7-ai-code-review-tools-on-real-world-prs-here-are-the-results)). In a CodeRabbit study, 56.3% of reviews were rejected, 43.3% of those as false positives ([arXiv 2607.03316](https://arxiv.org/html/2607.03316)).
- Escapes from AI coding agents in 2026 went through files that run on their own: git `core.fsmonitor` and diff-tool entries, repo hook settings, editor tasks ([CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-coding-agent-sandbox-escapes-20260722-c/)). Prompt injection through PR text leaked API keys from three CI review agents ([CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-comment-control-github-prompt-injection-20/)).
- Anthropic's managed review averages $15 to $25 and about 20 minutes per PR ([Help Net Security](https://www.helpnetsecurity.com/2026/03/10/anthropic-claude-code-review/)).
- The same commit can get different verdicts on different runs ([fullsend-ai #2746](https://github.com/fullsend-ai/fullsend/issues/2746)), which is why success needs two runs.

## Deferred Ideas

- Test Haiku finders on small shards, scored with the eval script.
- Turn deep mode on by policy, or automatically on High risk.
- Add cleanup angles to deep mode if the lenses turn out to miss them.
- Add seeded-bug cases to the smoke corpus from today's confirmed bugs.
- Decide whether a checker should see the finder's reasoning; research found no evidence either way.
- `[tech-spec]` Which OS sandbox to use on macOS and Linux, and how to detect whether one is available.
- `[tech-spec]` How finder copies are made and shared without exhausting disk; the built-in's A10 copy alone was about 11,000 files.

## Glossary

- **Area:** a size-bounded group of changed files that feed each other, up to 600 changed lines, with the diff hunks and questions to check for it.
- **Hunk:** one `@@` block of the diff. A finder must examine every hunk in its area.
- **Area finder:** a deep-mode agent that reviews one area line by line and may run code in its copy.
- **Contract lens:** a lens that checks one file's output against the file that reads it, and documented commands against the scripts.
- **Checker:** a fresh agent that judges one candidate from its claim and the code, and reruns any repro.
- **Confirmed:** the checker can name the trigger and the wrong result. Only confirmed findings can post.
- **Plausible:** the mechanism is real but the trigger is uncertain; shown with what would confirm it.
- **Refuted:** factually wrong, or guarded elsewhere; listed under "checked and dropped".
- **Throwaway copy:** a fresh copy of the change at its head, isolated as described under Decisions Locked.
- **Answer key:** the verified list of real defects in PR #50 at `3605fd8`, used for scoring.
