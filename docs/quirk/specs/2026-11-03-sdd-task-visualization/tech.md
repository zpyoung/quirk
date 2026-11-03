# Tech spec: live task view for subagent-driven development

**Status**: Reviewed. Tier gate fired: the work crosses subsystems (companion server, shell app, SDD skill,
brainstorming hand-off) and touches well over 3 source files.
**Logic spec**: [logic.md](logic.md), which owns the why and the behavior. This document owns where
the work goes and what must hold.

Paths are relative to the repo root. `SK` = `skills/writing-html-artifacts`, `APP` =
`SK/companion-app/app`, `SDD` = `skills/subagent-driven-development`, `BS` = `skills/brainstorming`.

## Architecture

The run view is a second face of the companion's app mode (PR #62). A session that has a registered
run serves the run view instead of the brainstorm view, so a brainstorm that hands off keeps its tab
([Data flow](logic.md#data-flow)).

| Unit | Location | Role |
|---|---|---|
| Run store | `SK/scripts/htmlkit/runstate.py` (new) | `RunStore`: validates and persists run state under `state/run/` (`run.json`, `reports.jsonl`, `questions.json`, `tab-seen`, `git.json`). Blocking calls share the session's `AppState.lock()`; `report` alone uses a bounded acquire on the same `state/app.lock`. |
| Fold | `SK/scripts/htmlkit/runfold.py` (new) | `fold(...)`: one pure function from stored run state plus git facts plus `now` to the run view model the tab renders. All status, mismatch, missing, blocked-by and stale rules live here. `run_view(session)` loads the store and calls `fold`. |
| Git watcher | `SK/scripts/htmlkit/gitwatch.py` (new) | Hardened read-only git runner, `observe()` for one poll, and a thread the server runs while a run is live. Writes `state/run/git.json`. |
| Companion server | `SK/scripts/companion.py` | New run subcommands, run event types on `/_quirk/app/event`, the diff route, `run` in the snapshot, watcher start, idle rule. |
| Shell app | `APP/src/run/**` (new), `APP/src/App.tsx`, `APP/src/types.ts` | Run view, summary, diff and findings pages. Same build into `SK/companion-app/shell.html`. |
| SDD protocol | `SDD/live-view.md` (new), `SDD/SKILL.md` | When SDD starts the view, what it reports at each step, how questions and tab actions flow. |
| Brainstorm hand-off | `BS/SKILL.md`, `BS/visual-companion.md` | Picking SDD keeps the companion running and hands SDD the session. |

Data moves like this. SDD calls `companion.py report` at each event-log step; the call writes one line
under the app lock and returns. The server's watcher thread polls git every 3 s into `git.json`. The
tab polls `/_quirk/app/snapshot`, whose `run` key is `fold(...)` computed at request time. Tab actions
post `run-*` events to `/_quirk/app/event`; SDD drains them with the existing `next` subcommand and
reports the outcome like any other step.

### Mapping the logic spec onto SDD's scheduler

SDD has had no waves since PR #61 (`SDD/SKILL.md:205`, "There are no waves and no barriers"). The
logic spec's 2026-11-03 amendment records this mapping, and every unit below uses it. The view
draws no wave bands and shows no wave counter; it shows the tasks and their edges.

| Logic spec term | What the view computes |
|---|---|
| Wave | Not shown. Internally a task's **level** (the longest chain of dependency edges from a root, starting at 1; ordering edges do not raise it; a fix task takes the level after the highest task its round covers) places it in a layout column and drives the missing rule. |
| Header "wave 2 of 4 · 2 passed · 3 running · 1 queued" | Counts only: "2 of 12 passed · 3 running · 1 queued", plus failed, needs-you and missing when non-zero. |
| "Waves 2 to 4 faded" (SC-1) | Tasks whose dependencies have not all passed are drawn faded. |
| Chain | A maximal path of ordering edges between tasks on the same level. Drawn as joined cards. An ordering edge across levels is drawn as a dashed arrow. |
| "Checkpoint after wave 1" | `Checkpoint k`, listing the tasks it covers. Final rounds are `Final round r`. |
| Missing, "the wave ends" | Nothing heard from either source for the task, its dependencies all passed, and either every other task on its level is terminal or the run ended. |
| Stop chain | Stop the task and every unpassed task downstream of it through any edge. |

## Code references

Traces to [Scope and non-goals](logic.md#scope-and-non-goals).

**Modify**

- `SK/scripts/companion.py`
  - `_build_parser` (1522): add the subcommands under [CLI contract](#cli-contract).
  - `APP_EVENT_TYPES` (77): add `run-answer`, `run-stop`, `run-retry`.
  - `_record_app_event` (677): route `run-*` kinds to a new `_record_run_event` before the
    `current is None` branch, because run events need no current step and no nonce.
  - `_Handler.do_GET` (443): add `GET /_quirk/run/diff`. Every new route still runs `_guard` (433).
  - `_serve_snapshot` (507): call `RunStore.touch_tab()` (throttled) on every request, before the
    204 check, so a tab that sees no change still counts as checked in.
  - `AppState.snapshot` is not changed. `_serve_snapshot` and `_cmd_snapshot` (1478) add
    `"run": run_view(session)` to the dict. The snapshot `rev` stays the integer from
    `counters.json`, because every run write calls `bump_rev()` (see [Snapshot](#snapshot)), so the
    204 check at 509-511 is unchanged.
  - `_Server.__init__` (353) / `_serve` (967): in app mode, start the watcher thread
    (`gitwatch.Watcher`) and stop it on shutdown.
  - `_Server.idle_seconds` (402) and the idle check in `_serve` (1023-1027): while a run is
    registered, idle is measured from the latest of the last request and the last report, and the
    limit becomes `max(idle_minutes, 120)` minutes. This holds after `run-end` too, so a summary
    stays served for two hours after the last report or tab request.
  - `_prepare_session` (198): also make a `.quirk/sdd` parent self-ignoring, the same as
    `.quirk/brainstorm`.
- `SK/scripts/htmlkit/appstate.py`: `EVENT_TYPES` (28) gains `run-answer`, `run-stop`, `run-retry`,
  and a public `bump_rev() -> int` (the existing `_tick()` under the lock), so run writes move the
  snapshot `rev`. Nothing else changes.
- `APP/src/types.ts`: `Snapshot` (159) gains `run: RunView | null`. `Actions` (181) is unchanged; the
  run view posts through `postEvent` (`APP/src/transport.ts`) directly.
- `APP/src/App.tsx`: pick the page by `location.search` (`?view=diff&task=ID`,
  `?view=findings&round=ID`) and, on the main page, render `RunView` when `snapshot.run` is non-null,
  else today's `ShellView`. No reload is involved, because the switch happens on the next poll.
- `APP/package.json`: add `run-check` to `check`.
- `SDD/SKILL.md`: see [SDD protocol](#sdd-protocol).
- `BS/SKILL.md` (96, 317) and `BS/visual-companion.md` (188-195): see
  [Brainstorm hand-off](#brainstorm-hand-off).
- `SK/references/companion.md`: a new `## Run view` section after `## App mode` (130) that points at
  `SDD/live-view.md` and this file. `README.md:79`: one clause naming the SDD run view.

**Create**

- `SK/scripts/htmlkit/runstate.py`, `SK/scripts/htmlkit/runfold.py`, `SK/scripts/htmlkit/gitwatch.py`
- `SK/companion-app/fixtures/run/scenarios/*.json` and `SK/companion-app/fixtures/run/views/*.json`
  (see [Fixtures](#fixtures))
- `APP/src/run/` (`types.ts`, `layout.ts`, `run-view.tsx`, `graph.tsx`, `node.tsx`, `banner.tsx`,
  `question-card.tsx`, `drawer.tsx`, `confirm.tsx`, `timeline.tsx`, `reviews.tsx`, `summary.tsx`,
  `diff-page.tsx`, `findings-page.tsx`, `run.css`)
- `APP/scripts/check-run.ts`, `APP/e2e/run-view.ts`
- `SDD/live-view.md`
- `tests/test_companion_runstate.py`, `tests/test_companion_runfold.py`,
  `tests/test_companion_gitwatch.py`, `tests/test_companion_run_server.py`,
  `tests/test_sdd_live_view_skill.py`

## CLI contract

Traces to [Data flow](logic.md#data-flow) and [Edges and fallback](logic.md#edges-and-fallback).

Same conventions as today: one JSON object on stdout, exit `0` ok, `1` not-ok or timeout, `2` usage
error or no server (`_emit` 150). Every run subcommand needs an app-mode session and exits 2 with
`{"error":"session is not in app mode"}` otherwise. None of them needs a live server except `await`,
which reports `no-server`.

CONTRACT:
```
companion.py run-start SESSION RUN.json        -> {"run": run_id, "resumed": bool, "url": str|null}
companion.py report    SESSION (JSON | --file F) -> {"n": int} | {"dropped": reason}     always exit 0 unless invalid
companion.py ask       SESSION QUESTION.json   -> {"question": id, "tab_seen_ago": float|null, "fallback": bool}
companion.py await     SESSION QID [--timeout S] [--quiet-after S]
                         -> {"answered": Answer}            exit 0
                          | {"status": "tab-quiet"}         exit 1   (no check-in for --quiet-after while open)
                          | {"status": "timeout"}           exit 1
                          | {"status": "no-server"}         exit 2
companion.py answer    SESSION QID --source orca|sdd (--pick VALUE | --text T)
                         -> {"answered": Answer}            exit 0 when this call recorded it
                          | {"answered": Answer, "already": true}  exit 1 when another source won
```

- `run-start` validates RUN.json ([Data models](#data-models)). SDD calls it twice: at preflight
  with `tasks: []`, so the header and `status` lines show during preflight (SC-1), and again with the
  plan. Same `run_id` as the stored run: resumes, keeps every report, returns `resumed: true`; the
  new `tasks` replace the stored list when the stored list is empty, and must otherwise match it by
  id, else exit 2 `{"error","field":"tasks"}`. A different `run_id`: deletes `state/run/`
  and starts empty, which is the cleanup rule (a run's data lives until another run starts in that
  session). It also writes the pointer `<repo>/.quirk/sdd/<branch-slug>.json` =
  `{"session": <absolute session path>, "run_id"}` so a resume in a new session finds the run.
  `branch-slug` is the branch with every run of `[^A-Za-z0-9._-]` replaced by `-`.
- `report` never waits more than 1 s: `RunStore.report` opens `state/app.lock` on its own fd and
  retries `fcntl.flock(LOCK_EX | LOCK_NB)` every 20 ms for up to 1 s, then gives up and prints
  `{"dropped": "lock-busy"}` with exit 0. It is only ever called from the CLI process, never inside
  a held `AppState.lock()` in the same process, because a second fd would wait on its own lock. A filesystem error prints
  `{"dropped": "<error>"}` with exit 0. Only an invalid report exits 2 with `{"error", "field"}`, so
  a malformed call is visible, but SDD carries on either way. No run registered: exit 2
  `{"error":"no run"}`.
- `ask` validates the question, stores it open, and appends a `question` report for its task.
  `fallback` is true when `tab_seen_ago` is null or above `TAB_FALLBACK_AFTER_S`.
- `await` polls `questions.json` every 0.2 s. `--quiet-after` defaults to `TAB_FALLBACK_AFTER_S`.
  It returns `tab-quiet` once, the first time the tab has not checked in for that long while the
  question is still open; the caller re-runs `await` with `--quiet-after 0` (disabled) after posting
  to orca ask.
- `answer` is the single arbiter of "first answer wins" (SC-19): it records the answer only if the
  question is still open, under the lock. A tab answer goes through the same store call from the
  server.

## HTTP contract

Traces to [Data flow](logic.md#data-flow) and SC-6, SC-10, SC-11, SC-14, SC-19 under
[Behavior and scenarios](logic.md#behavior-and-scenarios).

CONTRACT:
```
GET  /_quirk/app/snapshot?rev=R   unchanged route; body gains "run" (RunView | null)
POST /_quirk/app/event            new types, token required, no nonce:
       run-answer  payload {question, pick?: value, text?: str}   204 | 409 {"answered": Answer} | 400
       run-stop    payload {task}                                  204 | 200 {"duplicate":true} | 409 {"refused": reason} | 400
       run-retry   payload {task}                                  204 | 200 {"duplicate":true} | 409 {"refused": reason} | 400
GET  /_quirk/run/diff?task=ID     200 Diff | 404 unknown task or no run
GET  /?view=diff&task=ID, /?view=findings&round=ID   the same shell; App.tsx routes on the query
```

- `run-answer` on an answered question returns 409 with the winning answer, and the card shows
  "Answered in orca ask: <label>" (SC-18, SC-19). Exactly one of `pick` and `text`; `pick` must be
  one of the question's option values.
- `run-stop` is accepted for a task whose folded status is `queued`, `running`, `retrying`,
  `needs-you` or `failed`. `run-retry` is accepted only for `failed`. Otherwise 409
  `{"refused": "<status>"}`. Dedupe runs in two steps: the existing `client_id` check at the top of
  `_record_app_event` (688) first, then a `run-stop` or `run-retry` for a task that already has the
  same `pending_action` returns 200 `{"duplicate":true}` and writes nothing.
- Every accepted `run-*` event is appended to `state/app-events` with a `seq`, so `companion.py next`
  returns it to SDD unchanged.
- The diff route runs git through `gitwatch.git()` with `--no-ext-diff --no-textconv`, caps the
  patch text at 1 MiB and sets `truncated`. `base` is the task's base from its `dispatch` report,
  else `merge-base <head> <feature branch>`. A committed task diffs `base..head` from the repo. A
  running task diffs its listed worktree against `base`, and adds each untracked file as an added
  file whose text is read directly, capped at 256 KiB per file, with binary files listed by name
  only.

SCHEMA (Diff, `GET /_quirk/run/diff`):
```
{task, base: sha, head: sha|null, source: "commit"|"worktree",
 files: [{path, status: "added"|"modified"|"deleted"|"renamed", patch: str, binary: bool}], truncated: bool}
```

## Data models

Traces to [Conceptual model](logic.md#conceptual-model).

SCHEMA (RUN.json, `run-start`; unknown keys rejected):
```
{v:1, run_id: [a-z0-9-]{1,40}, repo: abs path, branch: str, branch_pattern: "sdd/{run}/{task}",
 base: sha (RUN_BASE),
 tasks: [{id: [A-Za-z0-9._-]{1,40}, title: str, contract_md?: str,
          deps: [task id], order_after: [task id]}] (0..200, ids unique, edges name known ids, acyclic)}
```

SCHEMA (report, one line in `state/run/reports.jsonl`; `n` and `at` are assigned by `report`):
```
{n, at, kind, ...}
status        {text}                                              header status line (preflight, gates)
dispatch      {task, attempt, branch, worktree, base}
return        {task, attempt, word: DONE|NEEDS_CONTEXT|BLOCKED|FAILED|none}
retry         {task, attempt, reason}                              attempt = the new attempt number
commit        {task, commit}                                       accepted and committed: passed
merge         {task, head}
fail          {task, reason}
stop          {task, reason, by: "user"|"sdd"}
skip          {task, reason}
supersede     {task, round, reason}                                back to queued
hold          {task, round}
task-add      {task: <RUN.json task>, round}                       a fix task
round-open    {round: [A-Za-z0-9-]{1,20}, round_kind: "checkpoint"|"final", title, covers: [task id]}
round-close   {round, outcome: "clean"|"fixes"|"blocked",
               findings: [{id, lens, severity, ruling: "accepted"|"dismissed", reason, fix_task?}]}
question      {question, task?}                                    written by ask, not by SDD
answered      {question, source}                                   written by answer and run-answer
action        {seq, outcome: "applied"|"declined", reason?}        SDD's response to a tab action
run-end       {outcome: "clean"|"blocked"|"stopped", next_step?: "merge"|"pr"|"keep"}
```

SCHEMA (question, `ask`; mirrors an orca ask `select` so one file serves both):
```
{id: [a-z0-9-]{1,40}, task?: task id, header?: str, prompt: str,
 options[2..6]: {value, label, description?}, recommended?: value, default?: value}
Answer = {question, source: "tab"|"orca"|"sdd", pick?: value, label?: str, text?: str, at}
```

SCHEMA (`state/run/git.json`, written only by the watcher):
```
{observed_at, changed_at, tasks: {ID: {branch_head?: sha, commits: int, merged: bool,
  files: [path], worktree_present: bool, error?: str}}}
```
`changed_at` moves only when some task's facts differ from the previous poll, and only then does
the watcher write the file and call `bump_rev()`. A task whose branch does not exist has no entry.

### Snapshot

SCHEMA (RunView, `snapshot.run`; pinned by `APP/src/run/types.ts` and the view fixtures):
```
{run_id, branch, status_text?, started_at, ended?: {at, outcome, next_step?},
 counts: {<status>: int},
 last_update_at, stale: null | {since: seconds}, stale_after_s, now,
 tasks: [{id, title, contract_md?, level, chain?: chain id, status, attempt, reason?,
          attempts: [{n, start, end?, outcome?}], started_at?, ended_at?,
          files: int, ready: bool, blocked_by: [id], downstream: [id], round?: round id,
          labels: [str], mismatch: null | {sdd: str, git: str, text: str},
          question?: id, pending_action?: "stop"|"retry", held_by?: round id}],
 edges: [{from, to, kind: "dep"|"order"}], chains: [{id, tasks: [id]}],
 rounds: [{id, kind, title, covers, outcome?, findings: [...]}],
 questions: [{...question, asked_at, state: "open"|"answered", answer?: Answer}]}
```
`status` is one of `queued`, `running`, `needs-you`, `retrying`, `passed`, `failed`, `skipped`,
`stopped`, `missing`. Every `RunStore` write except `touch_tab` calls `AppState.bump_rev()`, so the
integer snapshot `rev` moves on every change and the 204 path still fires for an unchanged poll.
Because staleness changes with time and no write, the tab recomputes it every second from
`last_update_at`, `stale_after_s` and its clock offset to the server's `now`; the server-side
`stale` field serves the CLI `snapshot`. `ready` is true when every dependency is `passed`. With
zero tasks the view shows only the header and `status_text` (preflight, SC-1).

## Fold rules

Traces to [Conceptual model](logic.md#conceptual-model) and SC-15 to SC-17, SC-21.

`fold(run, reports, git, questions, actions, now, stale_after_s=STALE_AFTER_S) -> RunView` is pure
and deterministic; `actions` is the list of `run-stop` and `run-retry` events from `app-events`.
`run_view(session)` passes `stale_after_s` from the env override `QUIRK_RUN_STALE_AFTER_S` when
set, for tests. Rules, in the order they apply:

- **Default.** A task with no report and no git fact is `queued`, attempt 0.
- **Status from reports.** The latest status-bearing report for a task wins: `dispatch` gives
  `running` (or `retrying` when `attempt > 1`), `retry` gives `retrying`, `commit` `passed`, `fail`
  `failed`, `stop` `stopped`, `skip` `skipped`, `supersede` `queued`. A `stop` never overrides
  `failed`: a failed task that is the anchor of a stopped chain stays `failed` (SC-10), and SDD
  sends `stop` only for the tasks that become stopped. An open question naming the task overrides
  to `needs-you` until it is answered.
- **Git-only pass** (SC-16a): no report for the task, but git shows `commits > 0` or `merged` on
  its branch (from `branch_pattern`): `passed` with the label "seen in git, not reported".
- **Missing** (SC-16b): no report and no git facts, every dependency is `passed`, and either every
  other task on its level is terminal (`passed`, `failed`, `skipped`, `stopped`) or the run ended.
  A task whose dependencies have not all passed is never missing; it stays `queued`.
- **Mismatch** (SC-15): compared only against git facts observed after the report's `at`, so the
  3 s poll lag never flashes a mark. Cases: SDD `passed` with no commit on the branch ("SDD says
  passed; git has no commit for T4 yet"); git `merged` while SDD says anything but `passed`; SDD
  `running` with `worktree_present: false` after a poll. The node keeps SDD's status.
- **Report gaps**: a report that implies a missing earlier one (a `commit` or `return` with no
  `dispatch` for that task) adds the label "dispatch not reported". This is how a dropped report is
  detected; there is no sequence-number check.
- **Blocked by** (SC-9, SC-11): a `queued` task lists its nearest `failed` ancestors through
  dependency edges. A `retry` clears it because the ancestor is no longer `failed`.
- **Stale** (SC-17): `last_update_at` = max(last report `at`, git `changed_at`). Stale when no
  `run-end` and `now - last_update_at > STALE_AFTER_S`. Stale changes no status. A run without
  `run-end` is never shown as finished (SC-21).
- **Pending actions**: a `run-stop` or `run-retry` event with no later `action` report and no later
  `stop` or `retry` for that task shows as `pending_action`.

CONFIG (`SK/scripts/htmlkit/runfold.py`):
```
STALE_AFTER_S = 180
TAB_FALLBACK_AFTER_S = 120
```

## Git watcher

Traces to [Key decisions and rationale](logic.md#key-decisions-and-rationale) (git owns facts).

- Poll every 3 s while a run is registered and has no `run-end`, plus one final poll after it.
- Task branches come from `dispatch` reports, else from `branch_pattern`. Worktrees come from
  `dispatch` reports only, and a worktree is read only when `git -C <repo> worktree list
  --porcelain` lists it. The repo is trusted; worktree content is not.
- Every git call goes through `gitwatch.git(cwd, *args, timeout=5)`:

CONFIG (git invocation, every call):
```
argv prefix: git --no-optional-locks -c core.fsmonitor=false -c core.hooksPath=/dev/null
             -c core.untrackedCache=false -c diff.external= -c core.pager=cat -C <dir>
env: GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_NO_REPLACE_OBJECTS=1
     GIT_ASKPASS= SSH_ASKPASS=   stdin=DEVNULL, timeout 5 s, never shell=True
diff and log calls also pass --no-ext-diff --no-textconv
```
- Facts per task, because SDD forks each task from the current `GREEN_HEAD` (`SDD/SKILL.md:356`)
  rather than from the run base:
  - `merged`: the branch head is the second parent of a merge commit in
    `git log --merges --format=%H %P <RUN base>..<feature branch>`. SDD merges with
    `git merge --no-ff`, so every task merge leaves one.
  - `commits`: `rev-list --count <task base>..<head>`, where the task base comes from the task's
    `dispatch` report. With no `dispatch` report, it is `rev-list --count <feature branch>..<head>`,
    so a freshly forked branch counts 0 and a merged one counts its own commits through `merged`.
  - `files`: `diff --name-only <task base>..<head>` for a branch with commits; for a running task,
    `status --porcelain=v1 -z --untracked-files=all` in its listed worktree.
  - A failed call records `error` for that task and keeps its previous facts.

## Shell app

Behavior comes from [Behavior and scenarios](logic.md#behavior-and-scenarios). The technical
contracts are:

- **Layout** (`APP/src/run/layout.ts`, pure): columns are levels, left to right; within a level,
  chain members stay adjacent and in order, and rows are ordered by two barycenter sweeps. Output is
  node boxes and edge paths in SVG user units. No layout dependency is added.
- **Graph** (`graph.tsx`): one SVG with no bands or level labels; dependency arrows (solid), chain joins (cards
  touching with a link glyph), cross-level ordering edges (dashed). Wheel zoom and drag pan through a
  `viewBox` transform; `focusTask(id)` animates the viewBox to center and zoom on a node (SC-6).
  Failed tasks' outgoing edges turn red (SC-9). Tasks with `ready: false` are faded. A stale run
  greys the whole SVG.
- **Node face** (`node.tsx`): title, status color, live elapsed (ticks locally every 1 s from
  `started_at`, frozen at `ended_at`), files count, an activity shimmer while `running`, an
  attempt badge "try N" when `attempt > 1`, a spinning ring while `retrying`, a pulse while
  `needs-you`, the mismatch mark with a hover/focus tooltip, labels ("blocked by T7", "seen in git,
  not reported", round tag "fix T3 · CP1").
- **Motion**: every animation is CSS keyframes in `run.css`, scoped under `.run-view`; the existing
  reduced-motion rule (`APP/src/theme.css:471`) stops them, and each final frame stays readable.
- **Banner** (`banner.tsx`): pinned under the header, every open question oldest first, each with
  Show on graph (SC-7).
- **Question card** (`question-card.tsx`): beside the node, the question's options as radios plus an
  Other text box, Send. A 409 shows the winning answer.
- **Drawer** (`drawer.tsx`): contract (markdown-it, as text-safe as `APP/src/markdown.ts`), status,
  attempts, Diff link and Findings link (`target="_blank"` to `/?view=...`), Stop chain and Retry.
- **Confirm** (`confirm.tsx`): Stop chain lists the task's fate, each `downstream` task that will be
  marked stopped, the committed predecessors that stay, and that other chains keep going (SC-10).
  Retry names the next attempt number and the last `reason` (SC-11).
- **Timeline** (`timeline.tsx`): one row per started task, ordered by first start time, one segment
  per attempt on a shared time axis.
- **Reviews** (`reviews.tsx`): a card per round with its findings and rulings and fix-task tags.
- **Summary** (`summary.tsx`): shown when `ended` is set; every task's final status and time, each
  round's outcome, the branch and the next step.
- **Connection lost** (SC-20c): after 3 failed polls the run view keeps rendering the last snapshot
  and shows "Lost connection to the companion" instead of the brainstorm's "Paused, reconnecting".
  When that snapshot has `ended`, it shows the summary with "The companion has stopped; this is the
  final state" instead, so the summary stays readable (SC-13). `start SESSION --app` serves it again
  from disk.
- **Ready signal**: reuse `useReadySignal` (`APP/src/notify.ts:54`) keyed on the newest open
  question id, so a background tab gets the title, badge and tone when SDD asks.

## SDD protocol

Traces to [Data flow](logic.md#data-flow) and SC-1, SC-2, SC-18, SC-20, SC-22, SC-23.

`SDD/live-view.md` holds the protocol; `SDD/SKILL.md` gains a short "Live view" section in Step 1
pointing to it, one line in Failure routing, and an Integration entry. The protocol states:

- **Opt-out.** The skill argument `--no-view` turns the view off. It never reaches the companion:
  SDD with `--no-view` starts nothing and calls no companion subcommand.
- **Start.** At preflight, before the card: reuse the session a brainstorm handed off, else read
  `<repo>/.quirk/sdd/<branch-slug>.json` for a resume, else `.quirk/sdd/<branch-slug>`. Run
  `start SESSION --app`; print the URL once unless a hand-off tab is already open; on failure print
  one line saying why and continue with the view off (SC-20b).
- **Branches.** Task and fixer branches are named `sdd/<run_id>/<task id>`, so the watcher can find
  an unreported task.
- **Reports.** At preflight, `run-start` with `tasks: []` and the run base; after decomposition,
  `run-start` again with the plan. Then one `report` per event-log line SDD
  already writes (`SDD/SKILL.md:140-154`) that has a report kind, plus `status` lines for preflight
  and gates. Ignore a `dropped` result.
- **Questions.** Every Tier 1 and Tier 2 question goes through `ask`. When `fallback` is true, also
  post it to orca ask at once. Otherwise run `await` in the background; on `tab-quiet`, post to orca
  ask and keep awaiting. Whichever answer arrives first is recorded with `answer`; when the tab wins,
  `orca ask cancel` the copy. Tier 2 timeouts and defaults are unchanged: on timeout record
  `answer --source sdd --pick <default>`.
- **Tab actions.** Keep one background `next SESSION --after <cursor> --timeout 43200` running for
  the run, so a tab action wakes the orchestrator. Apply `run-stop` and `run-retry` at the next
  scheduling pass and report `action` plus the resulting `stop` or `retry`/`dispatch`. A retry from
  the tab is a fresh attempt beyond SDD's own retry budget.
- **End.** `run-end` after Step 10. Do not stop the server, so the summary stays readable (SC-13).

## Brainstorm hand-off

Traces to SC-1 under [Main path](logic.md#main-path).

- When the hand-off pick is SDD, the brainstorm sends a `done` step with the message "Starting SDD in
  this tab", does **not** run `stop`, and passes `SESSION` to SDD. Any other pick keeps today's
  done-then-stop sequence.
- `BS/SKILL.md` stays at or under 400 lines (`tests/test_brainstorming_elicitation.py:18`), and every
  string pinned in `tests/test_brainstorming_companion_first.py` survives.

## Fixtures

Traces to [Behavior and scenarios](logic.md#behavior-and-scenarios).

Pinned shapes shared by the Python fold and the shell, so their tasks build in parallel:

- `SK/companion-app/fixtures/run/scenarios/<name>.json`:
  `{run, reports, git, questions, actions, now}` exactly as the fold takes them.
- `SK/companion-app/fixtures/run/views/<name>.json`: the expected `RunView` for that scenario.
- Required scenarios: `wave-start` (SC-3), `working` (SC-4), `needs-you` (SC-6, SC-7), `retrying`
  (SC-8), `failed-blocked` (SC-9), `stop-pending` (SC-10), `review` (SC-12), `ended` (SC-13),
  `mismatch` (SC-15), `git-only` and `missing` (SC-16), `stale` (SC-17), `answered-orca` (SC-18,
  SC-19).

## DO-NOT-CHANGE fences

These protect [Scope and non-goals](logic.md#scope-and-non-goals) ("SDD's rules are unchanged") and
PR #62's contracts.

- **SDD scheduling, retry, gate and review rules** (`SDD/SKILL.md` Steps 3-10). The view reports and
  relays; it never changes when a task dispatches, merges or retries. Pinned by
  `tests/test_subagent_driven_development_scheduling.py` and `tests/test_adversarial_review_skill.py`.
- **App-mode brainstorm contracts**: the step schema (`SK/scripts/htmlkit/steps.py`), existing event
  types and their validation, `AppState` file layout, and the brainstorm shell views. Pinned by
  `tests/test_companion_app_*.py` and `APP` `pnpm run check`.
- **Screen mode** (`start` without `--app`, `show`, `wait`, `events`, `POST /_quirk/event`), pinned
  by `tests/test_html_companion.py`, which must pass unchanged.
- **`_guard` on every route and the token on every app POST.** They are the server's only access
  control.
- **`SK/vendor/kit/1.0.0/kit.js`**: checksum-pinned; this work needs no kit change.

## Always / Ask / Never

Traces to [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**

- Write state with `htmlkit.fsutil.atomic_write`; append JSONL under the app lock.
- Keep `fold` pure: no clock, no I/O, `now` passed in.
- Run every git call through `gitwatch.git()`.
- Render user and report text as text.

**Ask**

- Before adding any runtime dependency to `APP/package.json`.
- Before changing a pinned test rather than satisfying it.

**Never**

- Let `report` block SDD for more than 1 s, or exit non-zero for a reason other than invalid input.
- Run git in a worktree the repo does not list, or with hooks, fsmonitor or external diff enabled.
- Show a status as `passed` or `failed` that no report and no git fact supports.
- Add network fetches beyond same-origin `/_quirk/*`.
- Commit a stale `shell.html`.

## Cross-cutting

Traces to [Edges and fallback](logic.md#edges-and-fallback).

- **Security.** Worktrees hold code written by unsandboxed workers, so the watcher treats them as
  untrusted: the invocation config above, a listed-worktree check, timeouts, no shell. Diff text
  renders as text. The server stays loopback-bound with the existing guard and token.
- **Never on the critical path.** `report` is bounded at 1 s and fails open. `ask` and `answer` are
  disk writes. `await` and `next` run in the background. A dead server changes only whether the tab
  can answer.
- **Resume** (SC-22). Reports persist in the session; `run-start` with the same `run_id` resumes, and
  the pointer file finds the session from a new terminal session.
- **Cleanup.** A run's data lives until another run starts in the same session. Sessions sit under
  self-ignoring `.quirk/brainstorm/` or `.quirk/sdd/`.

## Testing strategy

Traces to the success line in [Decisions Locked](logic.md#decisions-locked).

- `tests/test_companion_runstate.py`: RUN.json, report and question validation (every field and the
  unknown-key rule), resume vs replace on `run-start`, the pointer file, `report` dropping on a held
  lock within 1 s, `answer` first-wins under concurrency, tab check-in throttling.
- `tests/test_companion_runfold.py`: for every scenario fixture, `fold(scenario) == view`; plus unit
  cases for levels, chains, blocked-by, gaps, the mismatch grace window, and stale.
- `tests/test_companion_gitwatch.py`: a temp repo with a worktree whose config sets
  `core.fsmonitor` and a hook to scripts that write a marker file; polling and the diff route never
  create the marker. Unlisted worktrees are not read. Facts for unreported, committed, merged and
  running tasks.
- `tests/test_companion_run_server.py` (helper style of `tests/test_companion_app_server.py:98-219`):
  every new subcommand's JSON and exit codes; `run-*` events (token 403, 409 refused, 409 answered,
  duplicate); `next` returning run events; snapshot `run` and rev/204 behavior; the diff route;
  `await` tab-quiet and no-server; idle rule while a run is live.
- `APP` `pnpm run check`: `check-run.ts` renders every view fixture through `RunView` with
  `react-dom/server` and asserts the scenario's key text (header counts, "blocked by T7", mismatch
  text, banner order, "Answered in orca ask"); layout invariants (chain members adjacent, no two node
  boxes overlap, every dependency edge points left to right, no band or "Level" text); template
  freshness.
- `APP` `pnpm run e2e` gains `e2e/run-view.ts`: a real server with a scripted run fed by `report`;
  answer a question in the tab while `next` receives it; stop a chain through the confirm; open the
  diff page in a new tab while the run view keeps updating; stale greying with a shortened threshold
  via the env override `QUIRK_RUN_STALE_AFTER_S` on the server process.
- `tests/test_sdd_live_view_skill.py`: `SDD/SKILL.md` names `live-view.md` and `--no-view`;
  `live-view.md` names `run-start`, `report`, `ask`, `await`, `answer`, `next`, `orca ask cancel` and
  `sdd/<run_id>/<task id>`. `tests/test_brainstorming_companion_first.py` gains the "Starting SDD in
  this tab" pin.
- Existing pins pass unchanged. The PR gate is `python3 -m pytest -q`; CI has no Node, so the pnpm
  checks are local gates in every task that touches `APP`.

## Non-goals

Traces to [Scope and non-goals](logic.md#scope-and-non-goals).

- A run view for executing-plans, and browsing past runs. Both are deferred in the logic spec.
- Push transport. Polling at 1 s is enough for one local tab.
- Changing SDD's scheduling, retry or review rules, or adding pause and skip.
- Sequence-numbered reports. Gaps are detected from impossible transitions and git facts.
- Running the pnpm checks in CI.
