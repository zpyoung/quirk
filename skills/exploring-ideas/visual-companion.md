# Visual Companion Guide

Browser-based visual companion for showing idea-landscapes, option/cluster maps, comparison matrices, diagrams, and mockups during an exploration session.

It is the same `companion.py` the `brainstorming` skill uses. You describe each screen in a small `screen.json`; the companion builds it into a single offline HTML page, serves the newest one from a local Python server, and records the user's clicks as JSONL events you read back. You never hand-write HTML, CSS, or JavaScript. Full protocol details (routes, exit codes, state files, check results) are in `../writing-html-artifacts/references/companion.md`, relative to this file.

## When to Use

Decide per-question, not per-session. The test: **would the user understand this better by seeing it than reading it?**

**Use the browser** when the content itself is visual:

- **Idea-landscapes / cluster maps** — directions grouped by theme, the shape of the option space
- **Comparison matrices** — directions laid out across dimensions (qualitative notes, not scores), with no winner declared
- **Mind maps** — branching exploration of a topic, tangents preserved
- **Architecture / concept diagrams** — system components, data flow, relationship maps (Mermaid)
- **Side-by-side visual comparisons** — two directions rendered next to each other

**Use the terminal** when the content is text or tabular:

- **Scoping questions** — depth, recency, constraints, what the exploration serves
- **Conceptual A/B/C choices** and **tradeoff prose** — approaches, counter-arguments, challenge notes, open questions
- **Anything where the answer is words**, not a visual preference

A question *about* a visual topic is not automatically a visual question. "What should we research about layout systems?" is conceptual — use the terminal. "Which of these idea-cluster maps captures the space better?" is visual — use the browser.

## How It Works

`companion.py` has five subcommands, each printing exactly one JSON object to stdout (diagnostics go to stderr): `start` launches a detached local server for a session, `show` builds a screen from your spec and makes it current, `wait` blocks until the user clicks Proceed, `events` prints the recorded events, and `stop` stops the server.

Every screen shows your question, 2 to 4 option cards (single or multi select), a note field, and a Proceed button. Each option toggle posts a `click` event; Proceed posts a `proceed` event with the current selection and note. Events append to `<session>/state/events`.

## Requirements

Python 3 only: no Node, npm, or network step. If `python3` is unavailable, fall back to terminal-only exploration and tell the user.

**Finding the script.** This skill's directory is the one holding its `SKILL.md`; the host shows it when the skill loads. The companion is:

```
<this skill's directory>/../writing-html-artifacts/scripts/companion.py
```

Below, `$COMPANION` stands for that path; set it in your shell command and quote it.

## Starting a Session

Use a session directory **inside the user's project** under `.quirk/brainstorm/` (shared with the `brainstorming` skill), named like `explore-1` so exploration sessions stay distinct:

```bash
SESSION=".quirk/brainstorm/explore-1"
python3 "$COMPANION" start "$SESSION"
# {"type":"server-started","pid":92913,"port":53143,"host":"127.0.0.1","allowed_hosts":[],"url":"http://127.0.0.1:53143",
#  "screen_dir":".../explore-1/screens","state_dir":".../explore-1/state"}
```

The server detaches itself and `start` returns at once, so you do NOT need `run_in_background`. `start` is idempotent: a live server for the session is reused. Tell the user to open the `url`.

**Later:** the same JSON is in `<session>/state/server-info`; if the server has shut down, `<session>/state/server-stopped` exists instead. Screens persist in `.quirk/brainstorm/`, which is self-ignored by git.

**Remote or containerized setups:** the server binds `127.0.0.1` by default. If that URL is unreachable from the user's browser, add `--host 0.0.0.0` and `--allow-host <the name and port the browser uses>`, because the server answers 403 to any other `Host` header. For a port mapping such as 8080 to 3000, use `--allow-host localhost:8080`. A browser omits a default port from the `Host` header, so for a port 80 or 443 mapping use a bare host name with no port. A running server keeps the settings it started with: `start` with different host flags exits 2, so run `stop` first, then `start --host 0.0.0.0 --allow-host ...`. **This exposes the session on the network: anyone who can reach the port can read the screens and send events.** Use it only on a trusted network and only when the user agrees.

The server exits after 30 minutes without a request or a `show` (tune with `--idle-minutes N`).

## The Loop

1. **Write a `screen.json`** (see Authoring Screens) with the Write tool, never cat or a heredoc. Give each spec a semantic name such as `idea-landscape.json`.

2. **Show it:**

   ```bash
   python3 "$COMPANION" show "$SESSION" "$SESSION/idea-landscape.json"
   # {"screen":"0002-idea-landscape","nonce":"...","url":"...","checks":{...}}
   ```

   - Exit `1` means a static check failed. The screen is written but NOT made current, and `checks` says why. Fix the spec and show again.
   - Exit `2` means a malformed `screen.json` or a missing session. If the server stopped, run `start` again first.
   - **Never reuse a screen.** Each `show` creates a new numbered screen (`NNNN-<slug>.html`); to change one, edit the spec and show it again.

3. **Tell the user what to expect and end your turn:**
   - Remind them of the URL (every step, not just the first).
   - Briefly summarize what's on screen ("Showing 5 idea clusters for the topic") and ask them to respond in the terminal: "Let me know which directions resonate. Click to flag any you'd like to go deeper on."

4. **On your next turn**, read the events:

   ```bash
   python3 "$COMPANION" events "$SESSION" --screen 0002-idea-landscape
   ```

   Merge them with the user's terminal text. **Terminal input outranks clicks**: if the two disagree, the terminal message wins, and the clicks are context about what they explored.

5. **Iterate or advance.** If feedback changes the screen, show a new one; move on only when it is understood. A newer `show` makes an open older tab display a "superseded" banner and rejects its clicks, so stale clicks never reach you.

6. **Unload when returning to the terminal.** Show a short "continuing in the terminal" screen (it still needs 2 to 4 options) so the user isn't staring at a resolved choice. Repeat until done.

**Optional: block on Proceed.** Instead of ending your turn at step 3, run `python3 "$COMPANION" wait "$SESSION"`. It returns `{"proceed": <event>, "clicks": [...]}` when the user clicks Proceed on the current screen. Exit `1` is a timeout (110 s default, under a host's 120 s tool limit): re-run `wait`, since nothing is lost. Exit `2` means no live server: `start` and `show` again. If the user types while you are blocked, the typed text is the answer.

## Authoring Screens

A `screen.json` looks like this:

```json
{
  "title": "Directions to go deeper on",
  "question": "Which directions should we go deeper on?",
  "select": "multi",
  "options": [
    {"id": "behavioral-profile", "label": "Behavioral auto-profile", "description": "Build the profile from usage, no forms"},
    {"id": "docs-as-game", "label": "Docs as a game", "description": "Onboarding as a mystery to solve"},
    {"id": "finish-tool", "label": "Project-ending tool", "description": "Optimize for escape velocity, not retention"}
  ],
  "content": "<p>Exploratory, not ranked. Flag the ones that intrigue you.</p>",
  "diagram": "flowchart LR\n  A[Onboarding] --> B[Profile]"
}
```

- `title` is short and becomes the page `<title>`. `question` is what the user is deciding.
- `select` is `"multi"` (each click toggles) or `"single"` (picking one deselects the others). Idea-landscapes are usually `"multi"`: the user can flag several directions to explore further.
- `options` has **2 to 4 entries**. Each `id` is stable and matches `[a-z0-9-]{1,40}`; it comes back as the event `choice`. `label` comes back as `text`. `description` and `html` (a small mockup inside the card) are optional.
- `content` is optional freeform HTML above the options: a comparison matrix, notes, a larger visual.
- `diagram` is optional Mermaid source (idea-cluster maps, mind maps, concept diagrams), rendered offline.
- A screen that only shows something still offers choices about it ("Looks right", "Needs changes").

For comparison matrices, put a plain HTML table (directions by dimensions) in `content` and keep "no winner declared" intact.

### Idea-gate co-creation (go-deeper flags)

This is the browser surface for **Checkpoint 2, the idea-landscape co-creation gate** (`--involve medium+`; see `references/interaction-model.md`). It is an ordinary multi-select screen. Render the directions from the first ideation pass as options, one per direction, each `description` carrying its insight-pairing line:

```json
{
  "title": "Go deeper",
  "question": "Which directions should I go deeper on?",
  "select": "multi",
  "content": "<p>Exploratory, not ranked. Flag the ones to expand. Tell me in the terminal what to drop or add; everything else stays.</p>",
  "options": [
    {"id": "behavioral-profile", "label": "Behavioral auto-profile", "description": "Build the profile from usage, no forms. Why it might work: removes the blank-form drop-off"},
    {"id": "docs-as-game", "label": "Docs as a game", "description": "Onboarding as a mystery to solve. Why it might work: curiosity beats compliance"}
  ]
}
```

- **The browser carries one signal: go-deeper.** A multi-select screen yields a single `selected[]`, so it maps to exactly one action: the directions to **expand**. Don't overload it with keep/drop semantics.
- **Unselected is not dropped.** Keep is the default: a direction the user didn't click stays in the landscape. Never discard directions just because they were left unselected.
- **Drop and add-your-own come from the terminal.** The note field is free text but not a structured drop list, so explicit drops ("kill #2") and new directions arrive as terminal text, which is primary. Merge that text with the go-deeper set.
- **No ranking, ever.** Multi-select flags interest without ordering. Don't add scores, stars, or a "best" affordance; that would breach the no-winner gate in the browser too.
- A screen holds at most 4 options. For a larger landscape, show clusters as options, or split the directions across screens and keep the full numbered list in the terminal.
- After reading the go-deeper set and terminal text, run the **re-ideate loop** (drop / expand / ideate-added / one short refill pass), then show a fresh screen or unload to the terminal for the challenge pass.

### Status callouts

Challenge notes and open questions belong in `content` as plain HTML, worded as non-convergent status ("deferred", "needs review"). **Never** write "approved", "recommended", or "winner" on screen: it declares an answer and breaches the HARD-GATE.

## Browser Events Format

Events are recorded to `<session>/state/events`, one JSON object per line. The file is append-only and never cleared, so filter by `screen` (`events --screen ID` does this).

```jsonl
{"type":"click","screen":"0002-idea-landscape","nonce":"...","choice":"docs-as-game","text":"Docs as a game","selected":["docs-as-game"],"note":null,"timestamp":1781015415.2}
{"type":"click","screen":"0002-idea-landscape","nonce":"...","choice":"finish-tool","text":"Project-ending tool","selected":["docs-as-game","finish-tool"],"note":null,"timestamp":1781015418.9}
{"type":"proceed","screen":"0002-idea-landscape","nonce":"...","choice":null,"text":"Proceed","selected":["docs-as-game","finish-tool"],"note":null,"timestamp":1781015420.4}
```

- `choice` / `text` come from the toggled option's `id` / `label`. On a `proceed`, `choice` is null.
- `selected` is the full set of currently selected option ids (most useful in multi-select).
- `note` is whatever the user typed in the note field, or null.
- With no events for the screen, the user didn't interact with the browser. Use only their terminal text.

## Design Tips

- **Scale fidelity to the question.** A cluster map for shape, a matrix for trade-offs.
- **Explain the question on each screen.** "Which directions intrigue you?" beats "Pick one".
- **Iterate before advancing.** If feedback changes the screen, show a new version; never reuse one.
- **2 to 4 options per screen.**
- **Never declare a winner on screen.** The gate applies in the browser too.

## Cleaning Up

```bash
python3 "$COMPANION" stop "$SESSION"
```

`{"stopped": false}` just means no server was running. Screens persist in `.quirk/brainstorm/` for later reference, and the server also exits on its own after the idle timeout.
