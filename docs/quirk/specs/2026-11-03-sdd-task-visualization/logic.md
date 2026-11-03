# Logic spec: live task view for subagent-driven development

## Status & amendments

**Status**: Draft

**Amendments:** none yet.

`quirk:subagent-driven-development` (SDD) runs tasks in parallel waves and chains, but the only way
to follow a run today is to read the orchestrator's prose journal in the terminal. This spec adds a
live run view in the companion tab: a dependency graph colored by status, a timeline, a Reviews
section and a needs-you banner. You can answer SDD's questions, stop a chain or retry a failed task
from it. It builds on the companion's app mode from the companion-first brainstorming work (PR #62),
so a brainstorm that hands off to SDD keeps the same tab.

## Conceptual model

A **run** is one SDD execution on one feature branch. A run has **waves**, in order. Each wave has
one or more **chains**: tasks that share files and so run one after another. Each chain holds one or
more **tasks**. Tasks in different chains of the same wave run at the same time. **Review rounds**
sit beside the waves: a checkpoint round after a wave that has a successor, and the rounds of the
final loop. A **fix task** belongs to the round whose finding it fixes.

Every task has exactly one status at a time, from this set:

| Status | Meaning |
|---|---|
| queued | Planned; its wave or its turn in the chain hasn't come |
| running | A worker is building it |
| needs you | SDD asked you a question about it and is waiting |
| retrying | A previous attempt failed and SDD is running it again |
| passed | Accepted and committed |
| failed | Out of attempts, or failed in a way SDD won't retry |
| skipped | SDD decided not to run it |
| stopped | You or SDD stopped its chain before it ran or finished |

The view adds two states of its own. Neither is a task status SDD reports:

- **missing**: the task was in the wave's expected list but SDD never reported it.
- **stale**: the view has heard nothing from SDD or git for a while, so it no longer claims to know.

A task downstream of a failed task keeps its status (queued) and is labeled **blocked by** the
failed task.

Two sources feed the view, and each owns only what it can know:

- **SDD owns intent**: running, needs you, retrying, skipped, stopped, the question being asked, and
  the outcome of a stop or retry.
- **Git owns facts**: a task's commit, its merge into the feature branch, and the files it touched.

When they disagree, the node keeps SDD's status and carries a **mismatch mark** showing both
readings. The view never estimates. There are no percentages and no ETAs, only counts (wave 2 of 4,
7 of 12 passed) and measured elapsed times.

## Data flow

At each point where SDD already acts (wave start, dispatch, scope audit, retry, question, commit,
merge, review round, run end), SDD sends one short report to the companion. At wave start the report
lists every task the wave expects, so a task that never reports shows up as missing rather than
silently absent. Sending a report never waits on the companion: if the companion is slow or gone,
the report is dropped and SDD carries on.

While the run is live, a read-only watcher looks at the task worktrees and branches every few seconds
and records what git shows: files changed, commits made and merges into the feature branch.

The companion folds both into one picture per task and serves it to the tab, which polls it about
once a second. When you act in the tab (answer a question, stop a chain, retry a task), the companion
hands the action to SDD. SDD applies it at its next decision point and reports the result like any
other step, so the graph changes only once SDD has acted. A question SDD asks is also sent to
orca ask when no tab has checked in recently, and whichever answer arrives first is the one SDD uses.

The reports for a run are kept with the run, so a resumed run, a reloaded tab or a reopened tab
shows the same history.

## Key decisions and rationale

- **Hybrid source: SDD reports intent and a watcher checks git facts.** Only SDD knows about
  questions, retries and stops, and the banner, retry ring and answer-in-tab decisions depend on
  them. Git is what keeps statuses honest, and it catches a report SDD forgot within seconds. The
  research named a forgotten report as the main risk of an event-fed view. This was suggested by the
  user in chat, over an SDD-only event log.
- **Mismatches are shown, never resolved silently.** Two sources can drift. Each source owns
  different states, and a visible mark when they disagree keeps the view trustworthy without
  pretending either side is always right.
- **The view never sits on SDD's critical path.** A run with the view on takes no longer than one
  without it, and a dead companion changes nothing about how the run goes.
- **Graph first, as a real DAG.** You open the view mainly to spot what's stuck, failing or waiting
  on you, and to watch overall progress. A dependency graph shows why a task is waiting, which a list
  can't. The user asked to see it drawn as a DAG with dependency arrows during design review.
- **Light drawer, with diffs and findings on their own pages.** The node face already carries the
  status signals. The drawer stays small, and diffs and findings open in a new tab so the run view
  keeps polling.
- **Four actions only.** Answer questions, stop a chain, retry a failed task, and open diffs or
  findings. Pausing the whole run or skipping a task was rejected because skipping leaves
  dependents building on missing work.
- **orca ask stays the fallback.** A closed tab must never stall a run.
- **SDD runs only.** Waves and parallel chains are what make a graph worth having. executing-plans is
  one sequential chain, and past runs are covered by the end-of-run summary.

## Behavior and scenarios

### Main path

1. **SC-1 Brainstorm hands off to SDD**
   - **Given** a brainstorm running in the companion tab, and the user picks SDD at hand-off
   - **When** SDD starts
   - **Then** the same tab turns into the run view; ✓ no new URL is printed and no new tab or browser
     window opens
   - **Screen states:**

     | Moment | Tab shows |
     |---|---|
     | Hand-off picked | The brainstorm's done step: "Starting SDD in this tab" |
     | Preflight | Run header with the branch name, and the status line "Preflight: checking backends" |
     | Wave 1 starts | The graph with every wave 1 task queued, waves 2 to 4 faded |

2. **SC-2 SDD started on its own**
   - **Given** no companion tab is open
   - **When** the user starts SDD with the view on (the default)
   - **Then** preflight prints the view's URL once in the terminal; ✓ nothing opens a browser by itself

3. **SC-3 A wave starts**
   - **Given** a plan whose wave 2 has three chains: chain A (T4 then T5), T6 and T7
   - **When** SDD starts wave 2
   - **Then** all four tasks appear as queued with their dependency arrows, chain A drawn as two
     joined cards, and the header reads wave 2 of 4
   - **Data before:** **Run**: wave 1 done (T1 ✓ passed, T2 ✓ passed); header "Wave 1 of 4 · 2 passed"
   - **Walkthrough:**
     1. SDD reports wave 2's expected tasks: T4, T5, T6, T7
     2. The companion adds them as queued, with arrows from T1 and T2
     3. SDD reports T4, T6 and T7 dispatched; they turn running, and T5 stays queued behind T4
   - **Data after:** **Run**: "Wave 2 of 4 · 2 passed · 3 running · 1 queued"; **T5**: queued, joined to T4 by a chain link

4. **SC-4 A task is working**
   - **Given** T6 is running
   - **When** its worker edits files in its worktree
   - **Then** T6's node shows a live elapsed time, a growing files-touched count and an activity
     shimmer; ✓ the counts come from git, not from the worker's report
   - **Data before:** **T6**: running, 0m 40s*, 0 files
   - **Data after:** **T6**: running, 2m 31s*, 3 files

5. **SC-5 A task passes**
   - **Given** T4 is running
   - **When** SDD accepts and commits T4, and the commit appears on its branch
   - **Then** T4 turns passed, its final time freezes, and T5 (next in chain A) turns running when SDD
     dispatches it

6. **SC-6 SDD needs you, answered in the tab**
   - **Given** a tab is open and T5 wrote a file outside its declared scope
   - **When** SDD asks "Widen T5's scope or re-plan?"
   - **Then** a needs-you banner pins under the header and T5 pulses; ✓ "Show on graph" pans and zooms
     to T5 and opens a question card beside it with the same options orca ask would offer; ✓ after
     the user answers, the card closes, the banner clears, and T5's status changes once SDD acts on
     the answer
   - **Data before:** **T5**: needs you; **Banner**: "T5 wrote a file outside its scope. Widen scope or re-plan?"
   - **Walkthrough:**
     1. The user clicks Show on graph; the graph zooms to T5 and the card opens
     2. The user picks "Widen T5's scope to include appstate.py"
     3. SDD receives the answer and resumes T5
   - **Data after:** **T5**: running, attempt 1; **Banner**: gone; **orca ask copy**: none posted, because a tab was open

7. **SC-7 Several things need you at once**
   - **Given** T5 and T9 both wait on a question
   - **When** the banner is shown
   - **Then** both items stack in the banner, oldest first, and each has its own Show on graph

8. **SC-8 A task retries**
   - **Given** T6's first attempt fails its acceptance check
   - **When** SDD runs it again
   - **Then** T6 shows a spinning retry ring and a "try 2" badge; ✓ the timeline shows attempt 1 and
     attempt 2 as separate segments

9. **SC-9 A task fails**
   - **Given** T7 fails because it wrote `appstate.py`, which is outside its scope
   - **When** SDD marks T7 failed
   - **Then** T7 turns red and names the reason; ✓ its outgoing arrows turn red, and T10, which
     depends on it, reads "blocked by T7" while staying queued
   - **Data after:** **T7**: ✓ failed, "wrote appstate.py (out of scope)"; **T10**: queued, ✓ "blocked by T7"

10. **SC-10 Stopping a chain**
    - **Given** chain B holds T6 (failed, attempt 2 of 2) and T9 (queued, depends on T6)
    - **When** the user clicks Stop chain on T6 and confirms
    - **Then** before anything happens, the confirm lists the consequences; ✓ after confirming, T9 is
      marked stopped, and every other chain keeps running
    - **Confirm text:**

      Stop chain B?
      - T6 stays failed; any uncommitted work in its worktree is discarded.
      - T9 won't run and is marked stopped.
      - T4 and T5 are committed and stay.
      - Chains A and C keep going.

11. **SC-11 Retrying a failed task**
    - **Given** T7 is failed and T10 is blocked by it
    - **When** the user clicks Retry on T7 and confirms
    - **Then** the confirm names the attempt number and what the last attempt failed on; ✓ T7 re-runs
      in its chain as the next attempt, and T10 goes from "blocked by T7" back to plain queued
    - **Data before:** **T7**: failed, attempt 2, "wrote appstate.py (out of scope)"; **T10**: queued, blocked by T7
    - **Data after:** **T7**: retrying, attempt 3; **T10**: ✓ queued, no longer blocked

12. **SC-12 A review round runs**
    - **Given** wave 1 finished and has a successor
    - **When** SDD runs the checkpoint review and accepts one finding, which becomes a fix task
    - **Then** the Reviews section gains a card for "Checkpoint after wave 1" listing each finding with
      its ruling; ✓ the fix task appears on the graph with a tag naming its round, and the same tag
      shows on the card
    - **Review card:**

      | Line | Shown |
      |---|---|
      | Title | Checkpoint after wave 1 |
      | Summary | 2 findings · 1 accepted |
      | Finding 1 | ✓ CP1-X1 type checks, with the tag "fix T3 · CP1" |
      | Finding 2 | ✗ CP1-S1 dismissed: covered by T4 |

13. **SC-13 The run ends**
    - **Given** the final loop exits clean
    - **When** SDD reports the run finished
    - **Then** the tab switches to the summary: every task's final status and time, each review
      round's outcome, the branch, and the next step (merge, PR or keep); ✓ the summary stays
      readable after SDD exits, until another run starts

14. **SC-14 Opening a diff or findings**
    - **Given** the drawer is open on T3
    - **When** the user clicks Diff
    - **Then** a read-only page with T3's diff opens in a new browser tab; ✓ the run view keeps updating

### Edges and fallback

15. **SC-15 SDD and git disagree**
    - **Given** SDD reported T4 passed
    - **When** the watcher finds no commit for T4 on its branch
    - **Then** T4 stays passed and shows a mismatch mark; ✓ hovering the mark shows "SDD says passed;
      git has no commit for T4 yet"; ✓ the mark clears on its own once git agrees

16. **SC-16 A task SDD never reported**
    - **Given** wave 2 expected T8, and SDD sent no report for it
    - **When** (a) the watcher finds a commit on T8's branch, or (b) the wave ends with nothing for T8
      from either source
    - **Then** (a) T8 shows passed with the label "seen in git, not reported"; (b) T8 shows
      missing

17. **SC-17 The view loses track**
    - **Given** tasks are running
    - **When** neither SDD nor the watcher has reported anything for the stale threshold [ASK: How
      long without any update from SDD or git before the view greys out?]
    - **Then** the graph greys out and the header reads "No update for 4 min*"; ✓ no task is shown as
      passed or failed that wasn't reported that way; ✓ the first new update restores the normal view

18. **SC-18 No tab open when SDD asks**
    - **Given** no tab has checked in for the fallback threshold [ASK: How long without a tab checking
      in before a question also goes to orca ask?]
    - **When** SDD asks a question
    - **Then** the question also goes to orca ask; ✓ if the user later opens the tab, the card reads
      "Answered in orca ask: widen scope" with the pick that won

19. **SC-19 Two answers race**
    - **Given** a question was sent to both the tab and orca ask
    - **When** the user answers in orca ask, then answers the same question in the tab
    - **Then** SDD uses the orca ask answer; ✓ the tab's answer is refused with a note saying it was
      already answered in orca ask, and showing that pick

20. **SC-20 The view is off or can't run**
    - **Given** (a) the user passed the opt-out flag, (b) the companion can't start, or (c) the
      companion stops mid-run
    - **When** SDD runs
    - **Then** the run goes exactly as it would without the view, and questions use orca ask; ✓ (b)
      prints one line in the terminal saying why; ✓ (c) the tab, if still open, says it lost the
      connection, and SDD never waits on it

21. **SC-21 SDD stops or crashes**
    - **Given** a run in wave 3
    - **When** SDD stops without reporting the end of the run
    - **Then** the view goes stale as in SC-17; ✓ it never shows the run as finished

22. **SC-22 A run resumes in a new session**
    - **Given** a run that stopped in wave 3 and keeps its reports
    - **When** SDD resumes that run in a new session
    - **Then** the view shows the history up to the stop and continues from there; ✓ a newly opened
      tab shows the same picture

23. **SC-23 Mid-run actions only exist in the tab**
    - **Given** a run with no tab open
    - **When** a task fails
    - **Then** SDD applies its own retry and stop rules exactly as today; ✓ nothing waits for a tab
      action that no one can take

## Scope and non-goals

In scope: the live run view for SDD runs, in the companion tab, fed by SDD's reports and the git
watcher, with the four tab actions and the end-of-run summary.

Not in scope:

- **executing-plans runs.** They are one sequential chain, so a graph adds little.
- **Browsing past runs.** Only the current run, and its summary after it ends.
- **A full drawer with raw worker reports.** The light drawer plus diff and findings pages was chosen.
- **Pausing a whole run, or skipping a task, from the tab.**
- **Estimates.** No percentages, no ETAs.
- **Changing how SDD schedules, retries or reviews.** The view reports and relays actions; SDD's
  rules are unchanged.

## Decisions Locked

### Where and when

- Surface: a live view in the companion tab; a brainstorm that hands off to SDD keeps the same tab
- Timing: live during the run, plus a final summary view at the end
- Opening: URL printed once at preflight; a brainstorm hand-off reuses the open tab; nothing opens on its own
- Default: on by default, with an opt-out flag
- Presentation: maximize visuals (motion and interactive elements wherever they help you read the run)

### Layout

- Main view: dependency graph, colored live by status, drawn as a DAG with dependency arrows and wave bands
- Second view: a timeline of task durations per wave
- Reviews: a Reviews section with a card per checkpoint and final-loop round; fix tasks tagged with their round
- Chains: chained tasks drawn as joined cards

### What each task shows

- Node face: name, live elapsed time, files touched, an activity shimmer and an attempt badge
- Click a task: a light drawer with the contract and current status; diffs and findings link out
- Needs you: a pinned banner above the graph that pans and zooms to the node, which pulses
- Failures: a spinning retry ring with the attempt count; a failed node turns red and names the reason

### Watch or act

- Answering: in the tab, a question card beside the waiting task; orca ask stays as a fallback, and the first answer wins
- Controls: stop a chain or retry a failed task, each behind a confirm that says what happens
- Links: diff and findings open as rendered companion pages in a new tab
- Tab closed: if no tab has checked in recently, the question also goes to orca ask

### Purpose and scope

- Purpose: spot what's stuck, failing or waiting on you, and monitor overall progress
- Success: questions reach the tab within seconds; you never need the journal mid-run; every status matches git and the gates; no added run time
- Scope: SDD runs only
- Lost track: grey the graph and say how long since the last update

### Approach

- SDD reports each step (intent); a read-only watcher checks git (facts); disagreements show on the node

## Industry Insights

- **Agent tools group parallel work by status, with the graph as a second view.** The Claude Code
  agent view and Temporal's compact and timeline views lead with status. This spec leads with the
  graph because the user asked for it, and it keeps status prominent through color, counts and the
  banner. Sources: https://code.claude.com/docs/en/agent-view, https://docs.temporal.io/web-ui,
  https://temporal.io/blog/the-dark-magic-of-workflow-exploration
- **Status has to come from events, never from a model's guess, and unknown states must be
  explicit.** That is why the view has missing and stale and never estimates. Sources:
  https://www.aiuxdesign.guide/patterns/agent-status-monitoring,
  https://dev.to/jackm-singularity/ai-agent-status-updates-build-progress-users-can-trust-without-exposing-chain-of-thought-1mnd
- **Don't fake progress; parallel ETAs mislead.** Hence counts and real elapsed times only. Source:
  https://hatchworks.com/blog/ai-agents/agent-ux-patterns/
- **Interrupts are a budget.** Questions should be rare and easy to act on in context, which shaped
  the card-beside-the-task design. Sources: https://www.mypryme.com/blog/approval-fatigue-ai-agents,
  https://docs.langchain.com/oss/python/langgraph/interrupts
- **Dependencies and groups are first-class in CI views.** Sources:
  https://buildkite.com/docs/pipelines/configure/depends-on,
  https://buildkite.com/docs/pipelines/configure/step-types/group-step
- **Event-fed views fail on forgotten emits, races between an event and a status field, and silent
  gaps.** Fold status from events, number them, and flag gaps. Sources:
  https://github.com/dagster-io/dagster/pull/34327,
  https://docs.ecotone.tech/modelling/event-sourcing/setting-up-projections/gap-detection-and-consistency,
  https://docs.temporal.io/workflow-execution/event
- **Inferring status from git alone can't see intent.** It also misreads squash and rebase merges and
  leftover worktrees, and running git inside untrusted worktrees needs hardening. This is why git
  owns facts only. Sources: https://git-scm.com/docs/git-worktree,
  https://dillionmegida.com/p/why-git-merged-does-not-show-merged-branches/,
  https://dev.to/dekita/your-agent-ran-git-so-did-the-repo-auditing-repositories-that-arrive-as-files-4apa
- **Snapshot pages regenerated per wave are blind inside a wave, and meta-refresh fails an
  accessibility rule.** Rejected as the main view. Sources: https://playwright.dev/docs/test-reporters,
  https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html,
  https://visualstudiomagazine.com/articles/2026/02/09/hands-on-with-new-multi-agent-orchestration-in-vs-code.aspx

## Deferred Ideas

- [tech-spec] How SDD sends a report (a companion CLI call or an appended file), and how a dropped
  report is detected
- [tech-spec] The watcher's poll interval, and how it runs git safely in untrusted worktrees
  (read-only, no fsmonitor, no hooks)
- [tech-spec] Where a run's reports are stored, and when they are cleaned up
- [tech-spec] The opt-out flag's name and how it reaches the companion
- [tech-spec] How the companion relays a tab action to SDD at its next decision point
- [tech-spec] How a brainstorm session's tab switches into run mode without a reload
- A run view for executing-plans
- Browsing and comparing past runs

## Glossary

- **Run**: one SDD execution on one feature branch.
- **Wave**: a set of tasks whose dependencies are met, started together.
- **Chain**: tasks in one wave that share files, run in order in one worktree.
- **Review round**: a checkpoint review after a wave, or one round of the final review loop.
- **Fix task**: a task created to apply an accepted review finding.
- **Report**: one short message from SDD to the companion at a step it already takes.
- **Watcher**: the read-only process that reads git facts about each task.
- **Mismatch mark**: the mark on a node when SDD and git disagree.
- **Missing**: a task expected at wave start that was never reported.
- **Stale**: the view has had no update from SDD or git for longer than the threshold.
- **Blocked by**: the label on a queued task whose dependency failed.
- **Needs-you banner**: the strip under the header listing every question waiting on you.
