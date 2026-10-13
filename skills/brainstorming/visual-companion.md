# Visual Companion Guide

Browser-based visual brainstorming companion for showing mockups, diagrams, and options.

You describe each screen in a small `screen.json`; `companion.py` builds it into a single offline
HTML page, serves the newest one from a local Python server, and records the user's clicks as
JSONL events you read back. You never hand-write HTML, CSS, or JavaScript. Full protocol details
(routes, exit codes, state files, check results) are in
`../writing-html-artifacts/references/companion.md`, relative to this file.

## When to Use

Decide per-question, not per-session. The test: **would the user understand this better by seeing it than reading it?**

**Use the browser** when the content itself is visual:

- **UI mockups** — wireframes, layouts, navigation structures, component designs
- **Architecture diagrams** — system components, data flow, state machines, entity relationships (Mermaid)
- **Side-by-side visual comparisons** — two layouts, two color schemes, two design directions
- **Design polish** — look and feel, spacing, visual hierarchy

**Use the terminal** when the content is text or tabular:

- **Requirements and scope questions** — "what does X mean?", "which features are in scope?"
- **Conceptual A/B/C choices** and **tradeoff lists** — approaches described in words, pros/cons
- **Technical decisions** — API design, data modeling, architectural approach selection
- **Clarifying questions** — anything where the answer is words, not a visual preference

A question *about* a UI topic is not automatically a visual question. "What kind of wizard do you want?" is conceptual — use the terminal. "Which of these wizard layouts feels right?" is visual — use the browser.

## How It Works

`companion.py` has five subcommands, each printing exactly one JSON object to stdout (diagnostics
go to stderr): `start` launches a detached local server for a session, `show` builds a screen from
your spec and makes it current, `wait` blocks until the user clicks Proceed, `events` prints the
recorded events, and `stop` stops the server.

Every screen shows your question, 2 to 4 option cards (single or multi select), a note field, and
a Proceed button. Each option toggle posts a `click` event; Proceed posts a `proceed` event with
the current selection and note. Events append to `<session>/state/events`.

## Requirements

Python 3 only: no Node, npm, or network step. If `python3` is unavailable, fall back to
terminal-only brainstorming and tell the user.

**Finding the script.** This skill's directory is the one holding its `SKILL.md`; the host shows
it when the skill loads. The companion is:

```
<this skill's directory>/../writing-html-artifacts/scripts/companion.py
```

Below, `$COMPANION` stands for that path; set it in your shell command and quote it.

## Starting a Session

Use a session directory **inside the user's project** under `.quirk/brainstorm/`, with a unique
name such as `session-1`:

```bash
SESSION=".quirk/brainstorm/session-1"
python3 "$COMPANION" start "$SESSION"
# {"type":"server-started","pid":92913,"port":53143,"host":"127.0.0.1","allowed_hosts":[],"url":"http://127.0.0.1:53143",
#  "screen_dir":".../session-1/screens","state_dir":".../session-1/state"}
```

The server detaches itself and `start` returns at once, so you do NOT need `run_in_background`.
`start` is idempotent: a live server for the session is reused. Tell the user to open the `url`.

**Later:** the same JSON is in `<session>/state/server-info`; if the server has shut down,
`<session>/state/server-stopped` exists instead. Screens persist in `.quirk/brainstorm/`, which is
self-ignored by git.

**Remote or containerized setups:** the server binds `127.0.0.1` by default. If that URL is
unreachable from the user's browser, add `--host 0.0.0.0` and
`--allow-host <the name and port the browser uses>`, because the server answers 403 to any other
`Host` header. For a port mapping such as 8080 to 3000, use `--allow-host localhost:8080`. A browser
omits a default port from the `Host` header, so for a port 80 or 443 mapping use a bare host name with
no port. A running server keeps the settings it started with: `start` with different host flags
exits 2, so run `stop` first, then `start --host 0.0.0.0 --allow-host ...`.
**This exposes the session on the network: anyone who can reach the port can read the screens and
send events.** Use it only on a trusted network and only when the user agrees.

The server exits after 30 minutes without a request or a `show` (tune with `--idle-minutes N`).

## The Loop

1. **Write a `screen.json`** (see Authoring Screens) with the Write tool. Never use cat or a
   heredoc; it dumps noise into the terminal. Give each spec a semantic name such as
   `layout.json`.

2. **Show it:**

   ```bash
   python3 "$COMPANION" show "$SESSION" "$SESSION/layout.json"
   # {"screen":"0003-layout","nonce":"...","url":"...","checks":{...}}
   ```

   - Exit `1` means a static check failed. The screen is written but NOT made current, and
     `checks` says why. Fix the spec and show again.
   - Exit `2` means a malformed `screen.json` or a missing session. If the server stopped, run
     `start` again first.
   - **Never reuse a screen.** Each `show` creates a new numbered screen (`NNNN-<slug>.html`);
     to change one, edit the spec and show it again.

3. **Tell the user what to expect and end your turn:**
   - Remind them of the URL (every step, not just the first).
   - Briefly summarize what's on screen ("Showing 3 layout options for the homepage") and ask
     them to respond in the terminal, clicking an option if they like.

4. **On your next turn**, read the events:

   ```bash
   python3 "$COMPANION" events "$SESSION" --screen 0003-layout
   # {"events":[{"type":"click","screen":"0003-layout","choice":"two-col", ...}]}
   ```

   Merge them with the user's terminal text. **Terminal input outranks clicks**: if the two
   disagree, the terminal message wins, and the clicks are context about what they explored.

5. **Iterate or advance.** If feedback changes the screen, show a new one; move on only when the
   current question is validated.

6. **Unload when returning to the terminal.** When the next step doesn't need the browser, show a
   short "continuing in the terminal" screen (it still needs 2 to 4 options) so the user isn't
   staring at a resolved choice. Repeat until done.

## Advancing with a Proceed button (no terminal round-trip)

Every screen has a Proceed button, so you can skip the "end your turn and wait for the user to
type" step. The tighter loop is: **show, `wait`, continue**.

```bash
python3 "$COMPANION" wait "$SESSION"
```

`wait` blocks until the user clicks Proceed on the current screen, then prints:

```json
{"proceed": {"type":"proceed","screen":"0003-layout","choice":null,"text":"Proceed","selected":["two-col"],"note":"keep the sidebar narrow","timestamp":1781015420.4},
 "clicks": [{"type":"click","choice":"two-col","selected":["two-col"], "...": "..."}]}
```

Read `proceed.selected` and `proceed.note`, then continue. `clicks` holds the click events for
this screen in order.

- **Exit codes.** `0` is the payload above. `1` is a timeout (`{"status":"timeout","screen":...}`):
  **re-run `wait`**, since the events file is append-only and nothing is lost between runs. `2`
  is no live server (`{"status":"no-server"}`): run `start` again, then `show` the screen again.
- **Timeout.** The default 110 seconds sits under a host's 120-second tool limit, so a timeout is
  a clean exit 1 you can re-run. If you raise `--timeout`, raise the tool's own timeout above it.
- **Stale screens.** `wait` returns only a Proceed for the screen that was current when it
  started. When you `show` a newer screen, an open older tab gets a "superseded" banner, its
  controls turn off, and the server rejects its clicks, so a stale click can't advance you.
- **Terminal outranks clicks** here too. If the user types while you are blocked in `wait`, treat
  the typed text as the answer.

Remind the user of the URL and what's on screen before you call `wait`.

## Authoring Screens

A `screen.json` looks like this:

```json
{
  "title": "Homepage layout",
  "question": "Which homepage layout fits a reading-first product?",
  "select": "single",
  "options": [
    {"id": "single-col", "label": "Single column", "description": "Focused, linear reading"},
    {"id": "two-col", "label": "Two column", "description": "Sidebar nav beside main content",
     "html": "<div style=\"display:flex;gap:8px\"><nav>Nav</nav><main>Content</main></div>"}
  ],
  "content": "<p>Optional notes, a comparison, or a larger mockup.</p>",
  "diagram": "flowchart LR\n  A[Landing] --> B[Article]"
}
```

- `title` is short and becomes the page `<title>`. `question` is what the user is deciding.
- `select` is `"single"` (picking one deselects the others) or `"multi"` (each click toggles).
- `options` has **2 to 4 entries**. Each `id` is stable and matches `[a-z0-9-]{1,40}`; it comes
  back as the event `choice`. `label` comes back as `text`. `description` and `html` are optional;
  `html` is a small mockup shown inside the card.
- `content` is optional freeform HTML above the options: a mockup, a comparison, notes.
- `diagram` is optional Mermaid source, rendered with the companion's built-in Mermaid build. It
  works offline.
- A screen that only shows something still offers choices about it ("Looks right", "Needs changes").

Keep mockups simple: layout and structure, not pixel-perfect design.

## Browser Events Format

Events are recorded to `<session>/state/events`, one JSON object per line. The file is append-only
and is never cleared, so filter by `screen` (`events --screen ID` does this) rather than assuming
the last lines belong to the current screen.

```jsonl
{"type":"click","screen":"0003-layout","nonce":"...","choice":"two-col","text":"Two column","selected":["two-col"],"note":null,"timestamp":1781015415.2}
{"type":"proceed","screen":"0003-layout","nonce":"...","choice":null,"text":"Proceed","selected":["two-col"],"note":"keep the sidebar narrow","timestamp":1781015420.4}
```

- `choice` / `text` come from the toggled option's `id` / `label`. On a `proceed`, `choice` is null.
- `selected` is the full set of currently selected option ids (most useful in multi-select).
- `note` is whatever the user typed in the note field, or null.
- The click sequence can reveal hesitation worth asking about. With no events for the screen, use
  only the user's terminal text.

## Design Tips

- **Scale fidelity to the question.** Wireframes for layout, polish for polish questions.
- **Explain the question on each screen.** "Which layout feels more professional?" beats "Pick one".
- **Iterate before advancing.** If feedback changes the screen, show a new version; never reuse one.
- **2 to 4 options per screen.** More than that belongs in the terminal as a list.

## Cleaning Up

```bash
python3 "$COMPANION" stop "$SESSION"
# {"stopped": true}
```

`stopped: false` just means no server was running. Screens persist in `.quirk/brainstorm/` for
later reference, and the server also exits on its own after the idle timeout.
