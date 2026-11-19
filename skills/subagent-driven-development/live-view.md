# Live View Protocol

The live view shows an SDD run in the visual companion's browser tab. SDD reports what it already
does and relays questions and tab actions. It never changes scheduling, retries, gates or review.
Every companion call below can fail without consequence: carry on either way.

`$COMPANION` is `<skills dir>/writing-html-artifacts/scripts/companion.py`; quote it. Every
subcommand prints one JSON object. Ignore a `{"dropped": ...}` result from `report`.

## 1. Opt out

With `--no-view` in the skill arguments, start nothing and call no companion subcommand. The flag
never reaches the companion. Questions use the Failure routing gate in SKILL.md unchanged.

## 2. Find or create the session

Pick the first that applies, before the preflight card:

1. The session a brainstorm handed off (it sent "Starting SDD in this tab" and kept the tab).
2. The pointer `<repo>/.quirk/sdd/<branch-slug>.json`, whose `session` field is the session of an
   earlier run on this branch; use it to resume.
3. A new session directory `.quirk/sdd/<branch-slug>`.

`branch-slug` is the branch name with every run of characters outside `A-Za-z0-9._-` replaced by `-`.

COMMAND:
```bash
python3 "$COMPANION" start "$SESSION" --app
```

Print the `url` once, unless a hand-off tab is already open. If `start` fails, print one terminal
line saying why, turn the view off for the run, and use `orca ask` only.

## 3. Register the run

Call `run-start` twice with a `RUN.json` (`v: 1`, `run_id`, `repo`, `branch`, `branch_pattern`
`"sdd/{run}/{task}"`, `base`, `tasks`).

1. At preflight, with `tasks: []` and `base` set to `RUN_BASE`. The header and `status` lines show
   while the preflight card is open.
2. After decomposition, with the plan: each task has `id`, `title`, `deps` and `order_after`. The
   same `run_id` resumes the stored run and fills its empty task list.

COMMAND:
```bash
python3 "$COMPANION" run-start "$SESSION" "$RUN_JSON"
```

Name every task and fixer branch `sdd/<run_id>/<task id>`, so the watcher can find a task SDD has
not reported yet.

## 4. Report each event

After SDD appends a line to its event log, send one `report` for it when the table gives a kind.

COMMAND:
```bash
python3 "$COMPANION" report "$SESSION" '{"kind":"dispatch","task":"T1","attempt":1,"branch":"sdd/r1/T1","worktree":"...","base":"..."}'
```

| Event-log kind | Report kind and fields |
|---|---|
| `dispatch` | `dispatch` `{task, attempt, branch, worktree, base}` |
| `return` | `return` `{task, attempt, word}`, where `word` is `DONE`, `NEEDS_CONTEXT`, `BLOCKED`, `FAILED` or `none` |
| `accept` | none |
| `commit` | `commit` `{task, commit}` (this is the accepted and committed report) |
| `merge` | `merge` `{task, head}` |
| `gate` | `status` `{text}` naming the gate and its result |
| `checkpoint-open` | `round-open` `{round, round_kind: "checkpoint" or "final", title, covers}` |
| `checkpoint-close` | `round-close` `{round, outcome: "clean", "fixes" or "blocked", findings}` |
| `hold` | `hold` `{task, round}` |
| `rework`, `merge-as-is` | none |
| `supersede` | `supersede` `{task, round, reason}` |
| `stop` | `stop` `{task, reason, by: "sdd"}` |

Some outcomes have a report kind but no event-log line of their own. Report them when they happen:

- `retry` `{task, attempt, reason}`, with `attempt` the new attempt number
- `fail` `{task, reason}` when a task is out of retries
- `skip` `{task, reason}` when a task will never run
- `task-add` `{task, round}` for a fix task, with the task in RUN.json shape
- `status` `{text}` for preflight steps and the final gate
- `action` and `run-end`, described below

An invalid report exits 2 with `{"error", "field"}`. Fix the call and carry on.

## 5. Ask through the view

Every Tier 1 and Tier 2 question goes through `ask`. The question file mirrors an `orca ask`
`select`, so one file serves both.

| Question JSON | `orca ask` select spec |
|---|---|
| `id` | `id` |
| `prompt` | `question` |
| `header` | `header` |
| `options[]` `value`, `label`, `description` | the same fields |
| `default` | `default` |

Add `task` (the task id) when the question belongs to one task, and `recommended` when SDD has a
recommendation.

COMMAND:
```bash
python3 "$COMPANION" ask "$SESSION" "$QUESTION_JSON"
# {"question": "q1", "tab_seen_ago": 2.1, "fallback": false}
```

Then:

1. `fallback: true` means no tab is watching. Post the same question to `orca ask` now, and also
   run `await` in the background.
2. `fallback: false`: run `await` in the background and carry on with independent work.
3. `{"status": "tab-quiet"}` means the tab went quiet while the question was open. Post the question
   to `orca ask`, then run `await` again with `--quiet-after 0` so it fires only once.
4. The first answer wins. Record an `orca ask` answer with `answer --source orca`. If the tab
   answered first, run `orca ask cancel` on the copy.
5. A Tier 2 timeout keeps its default from SKILL.md. Record it with `answer --source sdd`.

COMMAND:
```bash
python3 "$COMPANION" await "$SESSION" "$QID" --timeout 600
python3 "$COMPANION" answer "$SESSION" "$QID" --source orca --pick "$VALUE"
python3 "$COMPANION" answer "$SESSION" "$QID" --source sdd --pick "$DEFAULT"
```

`answer` exits 1 with `"already": true` when another source won. Use the answer it returns.
`await` exits 2 with `no-server`: fall back to `orca ask` alone for that question.

## 6. Listen for tab actions

Keep one background listener for the whole run, so a tab action wakes the orchestrator. Restart it
with the latest cursor each time it returns.

COMMAND:
```bash
python3 "$COMPANION" next "$SESSION" --after "$CURSOR" --timeout 43200
```

Apply each `run-stop` and `run-retry` event at the next scheduling pass. Report `action`
`{seq, outcome: "applied" or "declined", reason?}` first, using the event's `seq`.

- `run-stop` on a task: report `action`, then `stop` `{task, reason, by: "user"}` for the task and
  each downstream task that has not passed. Never report `stop` for a task that already failed:
  the failed anchor keeps its status.
- `run-retry` on a failed task: report `action`, then `retry` and `dispatch` with the next attempt
  number. A retry from the tab is a fresh attempt beyond SDD's own retry budget, so it does not
  count against that budget.
- Decline with a `reason` when the task has already passed, or the run has ended.

## 7. End

After Step 10, report `run-end` `{outcome: "clean", "blocked" or "stopped", next_step?: "merge",
"pr" or "keep"}`. Do not run `stop`: the server stays up so the tab keeps the summary readable.

COMMAND:
```bash
python3 "$COMPANION" report "$SESSION" '{"kind":"run-end","outcome":"clean","next_step":"merge"}'
```
