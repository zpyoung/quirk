# Visual Companion Guide

Browser-based visual brainstorming companion for showing mockups, diagrams, and options.

It runs on **Agent Isles** (`isles live`): you author **Markdown screens** with small interactive
islands instead of hand-writing HTML. Agent Isles renders the newest screen, shows it in the
browser, and captures clicks back to you as JSONL events.

## When to Use

Decide per-question, not per-session. The test: **would the user understand this better by seeing it than reading it?**

**Use the browser** when the content itself is visual:

- **UI mockups** — wireframes, layouts, navigation structures, component designs
- **Architecture diagrams** — system components, data flow, relationship maps (Mermaid/D2 supported)
- **Side-by-side visual comparisons** — comparing two layouts, two color schemes, two design directions
- **Design polish** — when the question is about look and feel, spacing, visual hierarchy
- **Spatial relationships** — state machines, flowcharts, entity relationships rendered as diagrams

**Use the terminal** when the content is text or tabular:

- **Requirements and scope questions** — "what does X mean?", "which features are in scope?"
- **Conceptual A/B/C choices** — picking between approaches described in words
- **Tradeoff lists** — pros/cons, comparison tables
- **Technical decisions** — API design, data modeling, architectural approach selection
- **Clarifying questions** — anything where the answer is words, not a visual preference

A question *about* a UI topic is not automatically a visual question. "What kind of wizard do you want?" is conceptual — use the terminal. "Which of these wizard layouts feels right?" is visual — use the browser.

## How It Works

`isles live <dir>` watches a directory for **Markdown** files and serves the **newest one** (by
modification time) to the browser, auto-switching when you write a newer screen. You write `.md`
screens to the screen directory; the user sees the rendered result and clicks to select options;
selections are appended to `<dir>/state/events` (JSONL) that you read on your next turn.

You author **standard Markdown plus Agent Isles islands**. The renderer adds the page chrome,
theme, dark mode, a live header/footer, and all interactive infrastructure — you never hand-write
`<html>`, CSS, or `<script>`. Selection wiring is built into the islands; there is **no
`onclick`/`data-choice`/`toggleSelect`** to manage.

## Requirements

The companion is launched through the Quirk bridge, which finds an Agent Isles runner
automatically (in order):

1. repo-local `node_modules/.bin/isles`,
2. `isles` on `PATH`,
3. an explicit `npx` fallback (`github:zpyoung/agent-isles`, which currently carries `live`).

The npx fallback needs Node + `npx` available and will download Agent Isles on first use. If none
of these resolve, the bridge prints a clear error instead of launching — fall back to terminal-only
brainstorming and tell the user Agent Isles isn't available.

Throughout this guide, the bridge is invoked as
`python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py"` (the brainstorming skill ships inside the Quirk
plugin, so the bridge lives at the plugin root).

## Starting a Session

Pick a screen directory **inside the user's project** so screens persist and survive restarts.
Use a unique session subdirectory, e.g. `.quirk/brainstorm/session-1/`:

```bash
SCREEN_DIR=".quirk/brainstorm/session-1"
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR"
# Prints one line of JSON, e.g.:
# {"type":"server-started","pid":92913,"port":53143,"host":"127.0.0.1",
#  "url":"http://localhost:53143","screen_dir":".../session-1","state_dir":".../session-1/state"}
```

The server **self-backgrounds**: the command prints the server-info JSON and returns immediately,
so you do NOT need `run_in_background`. Save `url`, `screen_dir`, and `state_dir` from the JSON.
Tell the user to open the `url`.

**Finding connection info later:** the same JSON is written to `<screen_dir>/state/server-info`.
If the server has shut down, `<screen_dir>/state/server-stopped` exists instead.

**Persistence & git:** screens stay in `.quirk/brainstorm/` for later reference. Remind the user to
add `.quirk/` to `.gitignore` if it isn't already.

**Remote/containerized setups:** if the printed URL is unreachable from the user's browser, relaunch
binding a non-loopback host and control the printed hostname:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR" --host 0.0.0.0 --url-host localhost
```

The server auto-exits after 30 minutes of inactivity (tune with `--idle-timeout <minutes>`).

## The Loop

1. **Write a Markdown screen** to a new file in `screen_dir`:
   - Use semantic filenames: `platform.md`, `visual-style.md`, `layout.md`
   - **Never reuse filenames** — each screen gets a fresh file. The newest by mtime is served.
   - Use the Write tool — **never use cat/heredoc** (dumps noise into the terminal).
   - If the server has stopped (`state/server-stopped` exists, or `state/server-info` is gone),
     relaunch it before writing.

2. **Tell the user what to expect and end your turn:**
   - Remind them of the URL (every step, not just the first).
   - Give a brief text summary of what's on screen (e.g., "Showing 3 layout options for the homepage").
   - Ask them to respond in the terminal: "Take a look and let me know what you think. Click to select an option if you'd like."

3. **On your next turn** — after the user responds:
   - Read `<state_dir>/events` if it exists — JSONL of the user's browser clicks (see format below).
   - Merge with the user's terminal text. The terminal message is primary; events provide structured
     interaction data.

4. **Iterate or advance** — if feedback changes the current screen, write a new file (e.g.
   `layout-v2.md`). Only move to the next question when the current one is validated.

5. **Unload when returning to the terminal** — when the next step doesn't need the browser, push a
   waiting screen to clear stale content so the user isn't staring at a resolved choice:

   ```markdown
   <!-- filename: waiting.md (or waiting-2.md, etc.) -->
   ## Continuing in the terminal…
   ```

6. Repeat until done.

## Advancing with a Proceed button (no terminal round-trip)

By default (step 2 above) you end your turn and the user types in the terminal to advance. To let a
**browser click** advance you instead, add an `<agent-proceed>` button to the screen and block on it
with the bridge `wait` command. The tighter loop is: **write screen → `wait` → continue**.

1. Author the screen with options plus a Proceed button (the button stays disabled until a choice is
   selected):

   ```markdown
   <agent-option-set>
     <agent-choice id="single-column" title="Single column">Focused reading</agent-choice>
     <agent-choice id="two-column" title="Two column">Sidebar + main</agent-choice>
   </agent-option-set>

   <agent-proceed></agent-proceed>
   ```

2. Instead of ending your turn, **block on the click**:

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" wait "$SCREEN_DIR" --timeout 600
   ```

   It blocks until the user clicks Proceed, then prints the proceed record and exits 0:

   ```json
   {"type":"proceed","choice":null,"text":"Proceed →","timestamp":1781015420,"selected":["two-column"]}
   ```

   Read `selected` and continue. On **timeout it exits 1** — fall back to asking in the terminal. Still
   remind the user of the URL and what's on screen before you call `wait`, so they know to click.

This is opt-in: the plain click-then-terminal loop above still applies when you don't add a Proceed
button, or when Agent Isles is unavailable. (Phase 2 will swap the file poll for a native Claude Code
channel so the agent truly sleeps until the click — same `proceed` record, no `wait` code change.)

## Authoring Screens

Write a normal Markdown document. Reach for islands only where richer UI helps.

### Selectable options (the core interaction)

Wrap `<agent-choice>` rows in an `<agent-option-set>`. Each choice needs a stable `id` (used as the
event `choice`) and a short `title` (used as the event `text`); the body is the visible description.

```markdown
## Which homepage layout?

Consider readability and visual hierarchy.

<agent-option-set>
  <agent-choice id="single-column" title="Single column">Focused, linear reading experience</agent-choice>
  <agent-choice id="two-column" title="Two column">Sidebar nav beside main content</agent-choice>
</agent-option-set>
```

**Multi-select:** add `data-multiselect` on the `<agent-option-set>`. Each click toggles a choice;
the footer shows the count.

```markdown
<agent-option-set data-multiselect>
  <agent-choice id="risks" title="Risks">Show risk callouts</agent-choice>
  <agent-choice id="timeline" title="Timeline">Show timeline context</agent-choice>
</agent-option-set>
```

Selecting one choice in a single-select set deselects its siblings. Add `selected` to a choice only
for an initial selection (at most one in single-select sets).

### Other islands

- `<agent-decision verdict="go|approved|rejected|deferred|needs-review|ship-with-guardrails" title="…">` — scannable decision cards.
- `<agent-risk level="low|medium|high|critical" title="…">` — risk/blocker callouts.
- `<agent-proceed label="Proceed →">` — a commit/advance button. Disabled until the user selects an
  option; add `allow-empty` for a standalone Continue button on a screen with no options. Lets a
  browser click advance you with no terminal round-trip — see "Advancing with a Proceed button" below.
- More components and exact attributes: Agent Isles `docs/component-vocabulary.md`.

### Mockups and diagrams

- For wireframes/layout mockups, use plain Markdown structure plus Bootstrap markup (cards, grids)
  inline where you need richer layout.
- For architecture diagrams, flowcharts, and state machines, use Mermaid or D2 fenced code blocks.
- Keep mockups simple — focus on layout and structure, not pixel-perfect design. Use real content
  (e.g. actual images) when it materially affects the design judgment.

## Browser Events Format

Clicks are recorded to `<state_dir>/events`, one JSON object per line. The file is cleared
automatically when you push a newer screen.

```jsonl
{"type":"click","choice":"two-column","text":"Two column","timestamp":1780956565,"selected":["two-column"]}
{"type":"click","choice":"single-column","text":"Single column","timestamp":1780956570,"selected":["single-column"]}
```

- `choice` / `text` come from the clicked `<agent-choice>`'s `id` / `title`.
- `selected` is the full set of currently-selected choice ids (most useful in multi-select).
- The last event is typically the final selection, but the click sequence can reveal hesitation
  worth asking about.

If `<state_dir>/events` doesn't exist, the user didn't interact with the browser — use only their
terminal text.

## Design Tips

- **Scale fidelity to the question** — wireframes for layout, polish for polish questions.
- **Explain the question on each screen** — "Which layout feels more professional?" not just "Pick one".
- **Iterate before advancing** — if feedback changes the current screen, write a new version.
- **2–4 options max** per screen.

## File Naming

- Semantic names: `platform.md`, `visual-style.md`, `layout.md`.
- Never reuse filenames — each screen is a new file.
- For iterations, append a version suffix: `layout-v2.md`, `layout-v3.md`.
- Newest file by modification time is served.

## Cleaning Up

```bash
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR" --stop
```

Screens persist in `.quirk/brainstorm/` for later reference. The server also auto-exits after its
idle timeout.

## Reference

- Component vocabulary and exact island attributes: Agent Isles `docs/component-vocabulary.md`.
- Bridge options: `python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live --help`.
