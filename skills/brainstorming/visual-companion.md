# Visual Companion Guide (App Mode)

The companion's app mode runs a whole brainstorm inside one browser tab. You send the tab one **step** at a time (a question batch, approach cards, a design section, a spec review), the user's answers, chat messages and comments come back as **events**, and you post a live status line while you work. The terminal stays quiet.

`companion.py` keeps the session's state on disk (steps, decisions, chat, comment threads, drafts), so a refresh, a closed tab or a restarted server loses nothing. The full contract (step schema, event schema, HTTP routes, exit codes) is the CLI contract, HTTP contract and Data models sections of `docs/quirk/specs/2026-11-02-companion-first-brainstorming/tech.md`. This file is the working protocol. The one-question screen mode (`show`, `wait`) is unchanged and belongs to `quirk:exploring-ideas`; do not use it here.

## Requirements

Python 3 only. If `python3` is missing, or `start` fails (exit 2, a bind error, a port the browser can't reach), the companion can't run: say why once in the terminal and run the terminal flow in [SKILL.md](SKILL.md#terminal-flow).

**Finding the script.** This skill's directory is the one holding its `SKILL.md`; the host shows it when the skill loads. The companion is:

```
<this skill's directory>/../writing-html-artifacts/scripts/companion.py
```

Below, `$COMPANION` stands for that path; set it in your shell command and quote it. Every subcommand prints exactly one JSON object and exits `0` ok, `1` timeout, `2` usage error or no server.

## Starting the session

Use a session directory **inside the user's project** under `.quirk/brainstorm/`, with a unique name such as `session-1`:

```bash
SESSION=".quirk/brainstorm/session-1"
python3 "$COMPANION" start "$SESSION" --app
# {"type":"server-started","pid":92913,"port":53143,"url":"http://127.0.0.1:53143","mode":"app", ...}
```

The server detaches, so `start` returns at once and needs no `run_in_background`. **Print the `url` in the terminal and do not open a browser**; the user opens it themselves. `start` is idempotent for a live server.

**Remote or containerized setups.** The server binds `127.0.0.1`. When the user asks for remote access, or the URL is unreachable from their browser, add `--host 0.0.0.0 --allow-host <the name and port the browser uses>`, because the server answers 403 to any other `Host` header. **This exposes the session to anyone who can reach the port**, so use it only on a trusted network and only when the user agrees. A live server keeps its host flags: `stop` it first.

The server exits after 30 minutes with no request (`--idle-minutes N` tunes it). An open tab polls every second, so it stays alive while the tab is open.

## Sending a step

Write the step to a JSON file with the Write tool (never cat or a heredoc, which dumps noise into the terminal), then send it:

```bash
python3 "$COMPANION" step "$SESSION" "$SESSION/layout.json"
# {"step":"0004-questions","nonce":"...","url":"..."}
```

The open tab switches to it in place. A background tab gets the "(1) Your turn" title, a favicon badge and a sound. An invalid step exits `2` with `{"error","field"}` and nothing becomes current: fix the field and send again. Never reuse a step; each `step` call creates a new numbered one, so revise by sending a new step.

Every step has `v: 1`, `kind`, `stage` (`context`, `gray-areas`, `questions`, `approaches`, `design`, `spec` or `hand-off`) and `title`, plus optional `intro_md` or `intro_html`. Unknown keys and kinds are rejected. Ids match `[a-z0-9-]{1,40}`.

| Kind | Body | The user does |
|---|---|---|
| `questions` | 1 to 4 questions: `type` (`single`, `multi`, `text`), `prompt`, optional `header`, `recommended` (an option id), 2 to 4 `options` (`label`, `description`, `preview_html`), per-question `content_html` or Mermaid `diagram` | answers, skips, comments, submits once |
| `approaches` | 2 to 3 cards: `title`, `summary_md`, `recommended`, `pros`, `cons`, `sources` (`title`, `url`) | picks one, optionally with a comment |
| `design-section` | `index`, `total`, 1 to 3 `sections` (`title`, `body_md` or `body_html`, Mermaid `diagram`) | Looks right, or Needs changes plus a comment |
| `spec-review` | `format: "markdown"` with `spec_path` and `sections`; or `format: "interactive"` | comments per section and signs off, or uses the review page |
| `edit-card` | `decision_id`, `from`, `to`, `invalidates` (`label`, `step_id`), `origin` (`rail` or `chat`) | Confirms or cancels |
| `hand-off` | 2 to 3 `choices` (`label`, `description`, `recommended`) | picks the execution skill |
| `done` | `message_md` | nothing; the tab can close |

Rules that hold for every step:

- **Recommended means labeled and first, never preselected.** The shell renders the option marked by `recommended` first, with its own "(Recommended)" tag, so leave that suffix out of the label. Each answer stays a deliberate pick. Every `single` or `multi` question shows its own Other box, `text` questions carry no options, and the batch has one comment box. Skipping is always allowed.
- **A revision sets `changed`** (`{summary, blocks}`): the shell highlights the named blocks and shows your one-line summary of what changed.
- **Show options visually** whenever they differ in anything the user could see or feel. See [Showing options](#showing-options).

## Showing options

Default to a picture. When the options in a question differ visibly (layout, density, a state, how something moves or responds), give **every** option a `preview_html`; the shell then lays that question's options out as a side-by-side gallery instead of a list. Keep text-only options for choices with nothing to see, such as a policy or a default. A question-level `content_html` or `diagram` shows what all the options share, such as the structure they plug into. `diagram` takes Mermaid source only; put a `<q-flow>`, `<q-schema>` or `<q-sequence>` in `content_html` (or a design section's `body_html`), because the shell rejects HTML in `diagram`.

What a preview can hold, cheapest first:

- **A static mockup.** Inline HTML styled with the `--q-color-*` and `--q-space-*` tokens so it follows the theme, inline SVG, or an `<img>` with a `data:` URI. Draw an SVG's `viewBox` in real pixels and set `width` to the viewBox width, never `100%`: a fluid SVG scales to the column, so a 300-unit diagram on a wide screen renders its text several times too big. The shell still shrinks it on narrow screens. Show the real content the user will see (task names, statuses, counts), not lorem ipsum.
- **Motion,** for anything that changes over time: a status ticking from running to passed, a row arriving, a fix loop retrying. Put a `<style>` block with `@keyframes` in the preview. The shell stops animations for users who ask for reduced motion, so the final frame must make sense on its own.
- **Interaction,** when the difference is in how it feels to use. Kit elements (`q-tabs`, `q-board`, `q-flow`, `q-chart`, `q-compare`, `q-table`) are interactive and load on their own. For anything that needs script, use `<iframe sandbox="allow-scripts" srcdoc="...">` with a set `height`, because a `<script>` placed directly in `preview_html` never runs. An iframe does not inherit the page's theme, so give it colors that work in both schemes.

A `<style>` block applies to the whole page, so scope every selector and keyframe name under a class unique to the step, such as `.s3-board`. Users can comment on any block, so label the nodes and options you expect them to react to. Which diagram fits which job is in the writing-html-artifacts components reference.

Example, a first question batch (the adhd offer and the gray-area pick together):

```json
{
  "v": 1, "kind": "questions", "stage": "gray-areas", "title": "What to clarify first",
  "questions": [
    {"id": "find-areas", "type": "single", "header": "Find gray areas",
     "prompt": "Want me to run adhd to surface non-obvious decision areas for this request?",
     "recommended": "standard",
     "options": [
       {"id": "standard", "label": "Use the standard set (Recommended)", "description": "Catalog areas only. No extra cost."},
       {"id": "adhd", "label": "Add adhd areas", "description": "Spend 5-10x to surface ambiguities the catalog misses, added on top."}]},
    {"id": "areas", "type": "multi", "header": "Gray areas",
     "prompt": "Which of these areas should we clarify before designing?",
     "options": [{"id": "layout-style", "label": "Layout style", "description": "Cards, list or grid changes how results scan."},
                 {"id": "empty-state", "label": "Empty state", "description": "What a new user sees first."}]}
  ]
}
```

## Waiting and acting on events

Run `next` **in the background** (`run_in_background: true`) with a long timeout, so its completion wakes you when the user acts. Keep the `cursor` it returns and pass it as `--after` next time.

```bash
python3 "$COMPANION" next "$SESSION" --after "$CURSOR" --timeout 1800
# {"events":[{"seq":12,"type":"submit","step":"0004-questions","payload":{...}}], "cursor":12}
```

- Exit `1` is a timeout. Re-run with the same cursor; nothing is lost.
- Exit `2` with `{"status":"no-server"}` means the server stopped (see Restarts).
- Keep one `next` outstanding at a time. Drafts (half-typed answers) are never returned.

Events, and what each one means for you:

| Event | Payload | Act |
|---|---|---|
| `submit` | by step kind: `questions` `{answers: {qid: {selected, other, text, skipped}}}`, `approaches` `{pick}`, `design-section` `{verdict}`, `spec-review` `{verdict: "sign-off"\|"changes"}`, `hand-off` `{pick}`; plus an optional `comment` | record the decisions and send the next step. A skip is logged as an open item, and re-asked only if a later step depends on it. |
| `continue` | `{}` | "Continue without the rest" during research: stop the outstanding researchers, proceed with what returned, and mark the unfinished options "(research pending)" in the spec's Industry Insights |
| `chat` | `{text}` | answer with `say`; leave the current step untouched. A chat message that changes a decision gets an edit card, never a silent change. |
| `comment` | `{block_id, text, thread_id?}` | answer with `reply` |
| `edit-request` | `{decision_id, to?, note?}` | send an `edit-card` (below) |
| `edit-decision` | `{decision: "confirm"\|"cancel"}` | on `confirm`, apply the change; on `cancel`, change nothing and send the interrupted step again |
| `review-export` | `{path, kind, stage?, signed?}` | an interactive review export, already written to the spec folder; continue the interactive rubric |

Typed terminal input wins over the tab. Treat it as the user's answer, echo it into the chat with `python3 "$COMPANION" say "$SESSION" --from user --text "..."`, and update the step to match.

## While you work

Right after an event wakes you, set the status line, because the tab shows the waiting view until the next step arrives:

```bash
python3 "$COMPANION" status "$SESSION" --text "Checking 3 approaches against real-world reports, 2 of 3 done" --stage approaches --progress 2/3 --interruptible
```

- One plain line: the activity, counts and elapsed time are shown for you. Name the operation ("Reading recent commits"), never "Thinking".
- Add `--interruptible` only during research, where Continue without the rest makes sense. `status --clear` removes the line.
- Chat messages and comments sent now show as queued. Answer them as soon as you are free.

## Recording decisions

After each answered step, replace the Decisions panel's list with `decide`, which takes a JSON file holding the full list:

```bash
python3 "$COMPANION" decide "$SESSION" "$SESSION/decisions.json"
# {"decisions": 7}
```

Each decision is `{id, stage, area, label, value, status, note?}` with `status` `confirmed`, `assumed` or `open`. `assumed` is a fast-tracked decision, shown as "assumed, fast-tracked". Skipped questions go in as `open`. The list is the source for the spec's Decisions Locked section, so keep it complete and current.

## Chat and threads

- **Chat is your whole voice.** Anything you would have said in the terminal goes through `say`:

  ```bash
  python3 "$COMPANION" say "$SESSION" --text "Context done. I found the export module and two prior formats."
  ```

  Use `--file F` for longer text. Chat text and comments render as plain text, so skip markup.
- **Reply in the thread.** A `comment` event opens a thread pinned to its block (the thread id is on the event, and `snapshot` lists every thread). Answer with `python3 "$COMPANION" reply "$SESSION" THREAD_ID --text "..."`. When a revision addresses the comment, add `--resolve addressed`; use `--resolve not-addressed` when you decided against it.
- **Edits go through an edit card.** For a rail Change or a chat request, send an `edit-card` step naming the decision, the old and new values, and everything it invalidates, then wait for `edit-decision`. On `confirm`, update `decide` and redo only the invalidated work.

## Interactive spec review

When the user chose the interactive spec format, register the review page and send a `spec-review` step with `format: "interactive"`:

```bash
python3 "$COMPANION" review "$SESSION" path/to/review.html
# {"review_url": "/_quirk/review"}
```

The page opens inside the tab and posts each stage's export straight back as a `review-export` event, with no downloaded file. A signed stage-2 export is the final approval, as in the interactive rubric. A markdown spec uses `format: "markdown"` instead: the user's Sign off is the review gate's approval, and per-section comments (block ids like `spec:<section_id>`) get `reply`.

## Restarts and recovery

State persists on disk, and `snapshot` prints exactly what the tab sees:

```bash
python3 "$COMPANION" snapshot "$SESSION"
```

If `next` reports `no-server`, or the tab shows "Paused, reconnecting", run `start "$SESSION" --app` again. It reuses the saved session and token and tries the previous port first. **When the port is the same, the open tab picks up where it was. When the new `url` differs, print it in the terminal**: an open tab can't follow a port change, and opening the new URL restores the step, drafts, chat and threads. App-state subcommands (`step`, `status`, `decide`, `say`, `reply`, `review`) write to disk and work even when the server is down.

## The loop

1. `start --app` once; print the URL.
2. Send a `step`.
3. Run `next` in the background and end your turn, or do independent work.
4. On wake, read the events and act on each (table above). Run `status` before any slow work.
5. Run `decide` with the updated list.
6. Send the next `step`, then `next` again with the cursor.

Finish with a `hand-off` step, then a `done` step, then clean up:

```bash
python3 "$COMPANION" stop "$SESSION"
# {"stopped": true}
```

`stopped: false` means no server was running. The session directory stays in `.quirk/brainstorm/` for reference, and that folder is self-ignored by git.
