# Tech spec: companion-first brainstorming

**Status**: Reviewed. Tier gate fired because the work crosses subsystems (companion server, a new app,
the interactive spec page, the brainstorming skill) and touches well over 3 source files.
**Logic spec**: [logic.md](logic.md), which owns the why and the behavior. This document owns where
the work goes and what must hold.

Paths are relative to the repo root. `SK` = `skills/writing-html-artifacts`, `IS` =
`skills/writing-specs/interactive`, `BS` = `skills/brainstorming`.

## Architecture

The work adds an **app mode** to the existing companion server. Today's **screen mode** (one
question per `screen.json`) stays byte-for-byte compatible, because `quirk:exploring-ideas` and 100
tests depend on it ([Conceptual model](logic.md#conceptual-model)).

| Unit | Location | Role |
|---|---|---|
| Companion server | `SK/scripts/companion.py` | Gains app-mode subcommands and `/_quirk/app/*` routes. One process still serves one session. |
| App-mode state | `SK/scripts/htmlkit/appstate.py` (new) | Session state on disk: steps, status, decisions, chat, threads, drafts, events. Pure functions plus atomic writes, so the server and the CLI share it. |
| Step contract | `SK/scripts/htmlkit/steps.py` (new) | Validates step JSON (`v: 1`) and rejects unknown kinds and fields. |
| Shell app source | `SK/companion-app/app/` (new pnpm project) | React 19 + Vite + vite-plugin-singlefile + `@astryxdesign/core` 0.6.2, mirroring `IS/app/`. |
| Shell app build | `SK/companion-app/shell.html` (new, committed) | The single built file the server serves at `GET /` in app mode. |
| Review page | `IS/app/src/**`, `IS/review-template.html` | Gains post-back when served by the companion. The download path stays as the fallback. |
| Skill | `BS/SKILL.md`, `BS/visual-companion.md`, `BS/references/essential-coverage.md` | Rewritten companion-first; the terminal flow survives as `--terminal` and the fallback. |

Data moves like this. The agent calls CLI subcommands that write state files. The tab polls one
snapshot route and posts events. The agent blocks on `next` until a user event arrives
([Data flow](logic.md#data-flow)).

## Code references

Traces to [Scope and non-goals](logic.md#scope-and-non-goals).

**Modify**

- `SK/scripts/companion.py`
  - `_build_parser` (907): add the subcommands under [CLI contract](#cli-contract).
  - `_cmd_start` (594): add `--app` and record `mode` in `server-info`. Read the previous
    `server-info` port **before** the existing clearing (around 554 and 603) and try it before
    falling back to port 0. The session token lives in `state/token`. It is written once on the
    first `start --app` and reused on every restart, so an open tab's POSTs keep working.
  - `_next_screen_number` (645): generalize it to take a directory and a glob, so `step` numbers
    `state/steps/NNNN-<kind>.json` with the same `NNNN-` scheme. Screen-mode callers keep their
    current arguments and behavior.
  - `_Handler.do_GET` (381) and `do_POST` (395): add the app routes. All of them still run through
    `_guard` (371).
  - `_serve_screen` (403): in app mode, serve `shell.html` with the session token injected.
  - `_Server` (292): app-state writes do not use an in-process lock. Every app-state writer,
    whether a server thread or a CLI process, takes an exclusive `fcntl.flock` on
    `state/app.lock`. The server and the `step`, `status`, `decide`, `say` and `reply` processes
    write the same files, so only an inter-process lock prevents lost updates.
  - `live_server_info` (192) and `_answers_as_companion` (170): unchanged. `/_quirk/state` keeps
    `{screen, nonce}` in app mode too.
- `SK/scripts/htmlkit/checks.py`: no change. The shell is not run through `run_checks`, because it
  is a prebuilt app and not a tier-1 page.
- `SK/scripts/htmlkit/create.py:43` `NOT_A_BASE`: unchanged, since the shell is not a template.
- `IS/app/src/views/sign-off-view.tsx` (`download` 121-132) and
  `IS/app/src/views/compare/challenge-tray.tsx` (`exportChallenges` 50-67): route both through one
  new `deliverExport(data, filename)` in `IS/app/src/deliver-export.ts`.
- `IS/review-template.html`: emitted by `vite build` from `IS/app/review-template.html`
  (`outDir: '..'`); rebuild with `pnpm run build` in `IS/app`.
- `IS/../interactive-logic-spec.md` (the "render loop" no-network line at line 35, and each
  "when the reviewer says they exported" step): add the companion route.
- `BS/SKILL.md`, `BS/visual-companion.md`, `BS/references/essential-coverage.md`: see
  [Skill rewrite](#skill-rewrite).
- One-line updates: `skills/adhd/SKILL.md:145`, `skills/adhd/reference/when-to-use.md:75`,
  `SK/SKILL.md:3` and `:141`, `SK/references/companion.md:3` (plus a new "App mode" section),
  `README.md:76-79`.

**Create**

- `SK/scripts/htmlkit/appstate.py`, `SK/scripts/htmlkit/steps.py`
- `IS/app/src/deliver-export.ts`
- `SK/companion-app/app/` (`package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`,
  `vite.config.ts`, `tsconfig.json`, `shell-template.html`, `src/**`, `scripts/check-*.ts`)
- `SK/companion-app/shell.html` (built output)
- `SK/companion-app/fixtures/steps/*.json`, with one valid fixture per step kind plus invalid ones
- `tests/test_companion_app_server.py`, `tests/test_companion_app_steps.py`,
  `tests/test_brainstorming_companion_first.py`

## CLI contract

Traces to [Data flow](logic.md#data-flow) and [Edits, chat and comments](logic.md#edits-chat-and-comments).

Every subcommand prints exactly one JSON object and uses exit codes `0` ok, `1` not-ok/timeout, `2`
usage or no server, the same as today (`_emit` 120, `EXIT_*` 50). App-mode subcommands on a
screen-mode session exit 2 with `{"error":"session is not in app mode"}`, and the reverse holds too.

CONTRACT:
```
companion.py start  SESSION --app [existing flags]        -> server-started + {"mode":"app"}
companion.py step   SESSION STEP.json                       -> {"step": id, "nonce", "url"}         exit 2 invalid step
companion.py status SESSION --text T [--stage S] [--progress N/M] [--interruptible | --clear]
                                                            -> {"status": {...}}
companion.py decide SESSION DECISIONS.json                  -> {"decisions": n}   (full replace)
companion.py say    SESSION (--text T | --file F) [--from agent|user]  -> {"chat": seq}
companion.py reply  SESSION THREAD_ID --text T [--resolve addressed|not-addressed] -> {"thread": id}
companion.py review SESSION REVIEW_HTML                     -> {"review_url": "/_quirk/review"}
companion.py next   SESSION [--after SEQ] [--timeout 110]   -> {"events":[...], "cursor": SEQ}   exit 1 timeout
companion.py snapshot SESSION                               -> the same JSON the tab receives
```

- `step` assigns `NNNN-<kind>` ids from the existing counter (`_next_screen_number` 645), mints a
  nonce, writes `state/steps/<id>.json`, and atomically rewrites `state/current.json` as
  `{screen, nonce, shown_at, mode:"app"}`.
- `next` returns every user event with `seq > cursor`. Drafts are never returned. It also marks any
  returned chat messages as delivered (see Chat). A timeout re-run with the same cursor loses
  nothing. The skill runs `next` in the background with a long `--timeout`, so the completion
  notification wakes the agent. The 110 s default stays for foreground use.
- `say --from user` records terminal-typed input as the user's chat message (SC-16).
- Each subcommand has these error cases:
  - `step`: an invalid step exits 2 with `{"error", "field"}`, and nothing becomes current.
  - `decide`: malformed JSON or an invalid decision exits 2, and the previous list stays.
  - `reply`: an unknown `THREAD_ID` exits 2.
  - `review`: a missing or unreadable `REVIEW_HTML` exits 2.
  - `status --progress`: a value that isn't `N/M` exits 2.
  - App-state subcommands (`step`, `status`, `decide`, `say`, `reply`, `review`) work whether or
    not the server is running, because they write disk state. `next` exits 2 with
    `{"status":"no-server"}` when the server is dead, the same as `wait`.
- **Counters.** `rev` (the snapshot revision) and `seq` (shared by user events and chat entries)
  are stored in `state/counters.json` and changed only under `state/app.lock`. Both are monotonic
  across restarts, because they live on disk.

## HTTP contract

Traces to [Data flow](logic.md#data-flow) and [Edges and fallback](logic.md#edges-and-fallback).

All routes run through `_guard` (Host and Origin), so a foreign `Origin` or `Host` is still 403.
Every app `POST` also requires the header `X-Quirk-Token: <session token>`, or it gets 403.

CONTRACT:
```
GET  /                         app mode: shell.html with token injected; screen mode unchanged
GET  /_quirk/state             unchanged {screen, nonce} (+ "mode" in app mode)
GET  /_quirk/app/snapshot?rev=R  200 snapshot when rev != R; 204 when unchanged
POST /_quirk/app/event         204 accepted | 200 {"duplicate":true} | 409 {"superseded":true} | 400 | 403
GET  /_quirk/review            the registered review.html, served verbatim; 404 if none
POST /_quirk/review/export     200 {"path": ...} | 400 bad kind/shape | 403 | 413 over 2 MiB
GET  /_quirk/lib/...           unchanged (kit, chartjs, flow, highlightjs, mermaid via libraries.json)
```

- Body limits: `/_quirk/app/event` uses the existing 64 KiB `MAX_BODY` and drain logic.
  `/_quirk/review/export` allows 2 MiB, because exports embed the full review state.
- Every event body carries a client-generated `client_id`. The server dedupes on it, so a retried
  POST returns `{"duplicate":true}` and writes nothing.
- `submit` and `edit-decision` events carry the current step `nonce` and get 409 when it is stale.
  `chat`, `comment`, `draft`, `continue` and `edit-request` need only the token, because they stay
  valid across steps.

## Data models

Traces to [Conceptual model](logic.md#conceptual-model) and [Decisions Locked](logic.md#decisions-locked).

SCHEMA (step, `v: 1`; unknown keys or kinds are rejected, as in `load_screen` 666):
```
common: v:1, kind, stage: "context"|"gray-areas"|"questions"|"approaches"|"design"|"spec"|"hand-off",
        title, intro_md?, intro_html?, changed?: {summary, blocks: [block_id]}
questions:      questions[1..4]: {id, type:"single"|"multi"|"text", prompt, header?, recommended?: option_id,
                  options[2..4]?: {id, label, description?, preview_html?}, content_html?, diagram?}
                  (every single/multi question always shows an Other box; text questions have no options)
approaches:     approaches[2..3]: {id, title, summary_md, recommended: bool, pros[], cons[],
                  sources[]: {title, url}, content_html?}
design-section: index, total, sections[1..3]: {id, title, body_md?, body_html?, diagram?}
spec-review:    format:"markdown", spec_path, sections[]: {id, title, body_md}
              | format:"interactive"   (iframe src "/_quirk/review?t=<token>")
edit-card:      decision_id, from, to, invalidates[]: {label, step_id?}, origin:"rail"|"chat"
hand-off:       choices[2..3]: {id, label, description, recommended: bool}
done:           message_md
```
Ids match `[a-z0-9-]{1,40}` (`OPTION_ID` 62). A `questions` step has at most one `recommended` per
question. The recommendation is rendered labeled and first, and never preselected.

SCHEMA (user event, appended to `state/app-events` as JSONL with a server-assigned `seq`):
```
{seq, type, step?, client_id, timestamp, payload}
submit         payload by step kind (comment?:str allowed on all):
                 questions       {answers: {qid: {selected?:[oid], other?:str, text?:str, skipped?:true}}}
                 approaches      {pick: approach_id}
                 design-section  {verdict: "looks-right"|"needs-changes"}
                 spec-review     {verdict: "sign-off"|"changes"}   (markdown format only; interactive uses review-export)
                 hand-off        {pick: choice_id}
                 done            (no submit)
continue       payload: {}
chat           payload: {text}
comment        payload: {block_id, text, thread_id?}         (new thread when thread_id absent)
edit-request   payload: {decision_id, to?:str, note?:str}
edit-decision  payload: {decision: "confirm"|"cancel"}
review-export  payload: {path, kind, stage?, signed?}        (written by the server, not posted)
draft          payload: {answers, comment?}                  (stored in state/drafts/<step>.json, never in app-events)
```

SCHEMA (decision, the item in `state/decisions.json`; the agent replaces the whole list via `decide`):
```
{id, stage, area, label, value, status: "confirmed"|"assumed"|"open", note?}
```
`status:"assumed"` renders as "assumed, fast-tracked", the logic spec's tag.

SCHEMA (snapshot):
```
{rev, mode:"app", step: <step>|null, step_state: "open"|"submitted", status: {text, stage?, progress?, interruptible, started_at}|null,
 stages: [{id, state:"done"|"current"|"todo"}], decisions:[...], chat:[{seq, from, text, timestamp, delivered}],
 threads:[{id, block_id, step, messages:[{from, text, timestamp}], resolution?}], draft?, review_registered: bool}
```
`rev` increases on every state write. The shell shows the waiting view when `step_state` is
`submitted` or `step` is null; there is no authored waiting step.

**Thread pointers in chat** (SC-14). The server owns these. When a `comment` event opens a new
thread, the server appends a chat entry `{seq, from:"system", kind:"thread", thread_id, text: <the
first 80 characters of the comment>}` under the same lock. The shell renders it as a one-line link
that scrolls to the thread and opens it. Agent replies go into the thread only, never into chat.

**Block ids** for comments are derived deterministically by the shell:
`question:<qid>`, `option:<qid>/<oid>`, `approach:<id>`, `section:<id>`, `section:<id>/p<n>`,
`spec:<section_id>`, `node:<step>/<n>/<node_id>`. The last one covers diagram n in the step, with
the node id taken from `data-q-flow-node` or `data-q-schema-entity`. Agent-authored HTML may add
`data-commentable="<id>"` on any element.

## Shell app

Behavior comes from [Behavior and scenarios](logic.md#behavior-and-scenarios). The technical
contracts are:

- **Transport.** Poll `/_quirk/app/snapshot?rev=` every 1 s, and immediately on `visibilitychange`
  to visible. After 3 failed polls in a row, show "Paused, reconnecting" and keep polling with
  backoff capped at 5 s. Never reload the page.
- **Drafts.** Post `draft` debounced at 500 ms. Restore from `snapshot.draft` on load.
- **Ready signal** (SC-5). When a new step id arrives while `document.hidden`, set the title to
  "(1) Your turn", swap the favicon to a canvas-drawn badge, and play one short WebAudio tone. Reset
  all three on `focus`. If audio is blocked before the first user gesture, skip the tone silently.
- **Kit and diagrams.** When step HTML contains `<q-` tags, load these as classic scripts from
  `/_quirk/lib/`, in order: chartjs, highlightjs and flow when needed (the `kitcheck.needs*` rules),
  then kit. Load the mermaid script only for a `diagram` field, and run it per node. Mount each
  agent HTML block keyed by step id plus block id, so React never re-renders kit internals (the
  rule at `SK/templates/app/rules.md:53-56`).
- **Theme.** Import the Astryx reset and the theme, plus generated `--q-*` tokens, the same way as
  `SK/templates/app/project/src/theme.css`. Keep `data-theme` on `<html>` and dispatch `quirk-theme`
  when it changes. Never import `SK/theme/base.css`.
- **Comment pins.** Use one capture-phase click listener on the step root. A pin affordance appears
  on hover and focus for any element with a block id. It must never sit inside an option card's
  button, because nested controls break the card (`SK/templates/companion/rules.md`).
- **Rendering user text.** Chat, comments, Other boxes and notes are always rendered as text, never
  as HTML.

## Interactive review post-back

Traces to SC-9 under [Main path](logic.md#main-path).

- `deliverExport(data, filename)`: if `location.pathname === '/_quirk/review'`, it POSTs to
  `/_quirk/review/export` with the token from the query string (`?t=`). On 200 it runs the existing
  `onExport` bookkeeping and shows "Sent to the agent". On failure it falls back to the existing
  Blob download. Off-companion behavior is unchanged.
- The server validates `kind` as `quirk-logic-spec-decisions` (`isDecisionExport`,
  `IS/app/src/review-state.ts:169`) or `quirk-approach-comparison-challenges`. It writes
  `<spec_dir>/<slug>-decisions-<stamp>.json` or `-challenges-<stamp>.json` atomically, where
  `spec_dir` is the directory of the registered `review.html`. It then appends a `review-export`
  event. `render_spec.py find-export` already scans the spec folder, so `check-export`, `fold` and
  `reapprove` run unchanged.

## Skill rewrite

Traces to [Scope and non-goals](logic.md#scope-and-non-goals) and [Edges and fallback](logic.md#edges-and-fallback).

- When the user picks Continue without the rest (SC-4), the skill text tells the agent to stop the
  outstanding researchers and mark their options "(research pending)" in the spec's Industry
  Insights.

- `BS/SKILL.md` stays at or under 400 lines (`BODY_LINE_BUDGET`). It keeps 12 checklist steps.
  Step 3 becomes **Start the companion** (with `--terminal` and the fallback). Steps 4-5 and 8-12
  say "on screen" rather than naming `AskUserQuestion`. Every pinned string listed in
  [Testing strategy](#testing-strategy) survives verbatim.
- The `AskUserQuestion` and orca ask blocks in Gray Areas Step 0 and Step 1 move to a short
  "Terminal flow" section, as the shape used by `--terminal` and the fallback. Their pinned labels
  ("Find gray areas", "Use the standard set (Recommended)", "Add adhd areas") remain, and the same
  labels are used on screen.
- `BS/visual-companion.md` becomes the app-mode protocol: start, step, status, decide, say, reply,
  review, next, and the loop. It drops the per-question browser-or-terminal rule and the consent
  offer. It must not contain `CLAUDE_PLUGIN_ROOT` (`tests/test_isles_removed.py`).
- `BS/references/essential-coverage.md` keeps "never an option inside an `AskUserQuestion` call"
  and adds that the fast-track is never an option on a companion question either. It is triggered
  by a chat steer.

## DO-NOT-CHANGE fences

These protect [Scope and non-goals](logic.md#scope-and-non-goals) ("exploring-ideas keeps today's companion").

- **Screen-mode CLI and routes** (`start` without `--app`, `show`, `wait`, `events`, `stop`;
  `GET /`, `POST /_quirk/event`; `load_screen`; `companion.js`). exploring-ideas and
  `tests/test_html_companion.py` pin them, and that file must pass unchanged.
- **`/_quirk/state` returning `{screen, nonce}`.** The liveness probe `_answers_as_companion` (170)
  and the waiting page depend on it. App mode may add keys, never remove these.
- **`state/events` schema and append-only rule.** `wait` and screen-mode tests read it. App events
  go to the separate `state/app-events`.
- **`_guard` on every route, and the `libraries.json` whitelist for `/_quirk/lib`.** These are the
  server's only access control.
- **The review export shapes (`Export` in `IS/app/src/spec-types.ts:352`, `createCompareExport`) and
  `render_spec.py` subcommands.** The fold pipeline and about 2,200 lines of tests depend on them.
  Post-back delivers the same JSON, unmodified.
- **`SK/vendor/kit/1.0.0/kit.js`.** It is checksum-pinned and edited only through `pins.py stamp`,
  and this work needs no kit change.
- **Brainstorming pinned strings.** These are listed under Testing strategy, because the elicitation
  and adhd tests encode decisions from earlier specs.

## Always / Ask / Never

**Always**

- Write state with `htmlkit.fsutil.atomic_write`.
- Append JSONL under a lock.
- Print one JSON object per subcommand.
- Validate steps before they become current.
- Render user text as text.
- Keep screen mode working.

**Ask**

- Before adding any runtime dependency beyond those in `IS/app/package.json`, ask, except a
  markdown renderer, which is pre-approved (markdown-it).
- Before changing a pinned test rather than satisfying it, ask.

**Never**

- Accept an app `POST` without the token.
- Add network fetches beyond same-origin `/_quirk/*`.
- Inline the 5.4 MB Mermaid into `shell.html`.
- Change export JSON shapes.
- Commit a stale `shell.html` or `review-template.html`.

## Cross-cutting

Traces to [Edges and fallback](logic.md#edges-and-fallback).

- **Security.** The server binds loopback by default. The session token is minted once with
  `secrets.token_urlsafe(24)` on the first `start --app`, stored in `state/token` (mode 0600), and
  injected into the shell. The shell appends it as `?t=` on the review iframe `src`. It adds CSRF
  protection on top of the Origin check. Agent HTML stays unsanitized, as today.
- **Restart** (SC-18). `start --app` on a session with saved state reuses it and its token, and
  tries the previous port first. If that port is taken, the new URL goes into the chat log and the
  terminal. The open tab cannot follow a port change, so the tab only picks up where it was when
  the port can be reused, per SC-18 (b) in the logic spec's 2026-11-02 amendment.
- **Fallback** (SC-19). `start` failing (no python3, a bind error, exit 2) is the skill's trigger
  for the terminal flow.

## Testing strategy

Traces to the done criterion in [Decisions Locked](logic.md#decisions-locked).

- `tests/test_companion_app_server.py`: a foreground server on port 0, using the
  `tests/test_html_companion.py` helper style. It covers:
  - every subcommand's JSON and exit codes;
  - the token 403 and the Origin/Host 403 on app routes;
  - 409 on a stale-nonce `submit`, and `client_id` dedupe;
  - drafts never returned by `next`;
  - the `next` cursor and timeout re-run losing nothing;
  - `rev` changes, and the 204 on an unchanged snapshot;
  - review export validation, the written file name and the 2 MiB limit;
  - restart restoring state and reusing the port;
  - a screen-mode session refusing app subcommands.
- `tests/test_companion_app_steps.py`: every fixture in `SK/companion-app/fixtures/steps/`
  validates or fails as named, and unknown kinds and keys are rejected.
- `SK/companion-app/app` `pnpm run check`: typecheck, a render of every step fixture with
  `react-dom/server`, and template freshness, meaning a byte-compare of a fresh build against the
  committed `shell.html`, the same as `IS/app/scripts/check-template.ts`.
- **Browser smoke**, `pnpm run e2e` using the Playwright already installed for `SK/scripts/verify`.
  It starts a real app-mode server and walks through these steps:
  1. answer a batch with a skip and an Other;
  2. a refresh keeps the draft;
  3. a background tab gets the "(1) Your turn" title;
  4. post a chat message;
  5. pin a comment to an approach card and to a q-flow node;
  6. stop and restart the server, then check that it reconnects.
- `IS/app` `pnpm run check` passes after the rebuild. `tests/test_golden_renders.py`,
  `tests/test_interactive_logic_spec.py` and `tests/test_compare_stage.py` pass unchanged.
- `tests/test_brainstorming_companion_first.py` checks that:
  - `SKILL.md` names `--terminal`, "Start the companion" and the app-mode subcommands;
  - `SKILL.md` no longer contains "Offer visual companion" or "own message, no other content";
  - `visual-companion.md` no longer contains "Decide per-question".
- Existing pins must pass unchanged:
  - `tests/test_brainstorming_elicitation.py`: the 400-line budget, `12. **Transition to
    implementation**`, `Essential-coverage\ncheck`, the altitude strings, and the forbidden cadence
    strings;
  - `tests/test_brainstorming_adhd_offer.py`;
  - `tests/test_writing_specs_skill.py`, where the links and anchors must resolve;
  - `tests/test_isles_removed.py`.
- The full suite gate is `python3 -m pytest -q`. CI has no Node, so the pnpm checks are local gates
  that every task's acceptance runs.

## Build phases

These follow [Decisions Locked](logic.md#decisions-locked) ("chat and comments last").

1. Server app-mode core: state, steps, CLI, HTTP. No chat or threads yet.
2. The shell app: rail, step kinds, waiting, Decisions panel, ready signal, reconnect, diagrams,
   drafts, build and checks.
3. Interactive review post-back, and the rubric doc updates.
4. The skill rewrite and its tests, plus the one-line doc updates.
5. Chat and comments: `say`, `reply`, the chat, comment and edit-request events, the chat panel,
   pins, edit cards from chat, and the e2e flows.

## Non-goals

- exploring-ideas adopting app mode, and execution progress in the companion. Both are deferred in
  the logic spec.
- Push transport (SSE or WebSocket). Polling at 1 s is enough for one local tab.
- Multi-tab or multi-user sessions. The last tab wins, and there is no conflict resolution.
- Sanitizing agent-authored HTML.
- Running the pnpm checks in CI.
