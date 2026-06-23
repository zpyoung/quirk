# Visual Companion Guide

Browser-based visual companion for showing idea-landscapes, option/cluster maps, comparison matrices, diagrams, and mockups during an exploration session.

It runs on the shared **Agent Isles** bridge (`isles live`) — the same one the `brainstorming` skill uses. You author **Markdown screens** with small interactive islands instead of hand-writing HTML. Agent Isles renders the newest screen, shows it in the browser, and captures clicks back to you as JSONL events.

## When to Use

Decide per-question, not per-session. The test: **would the user understand this better by seeing it than reading it?**

**Use the browser** when the content itself is visual:

- **Idea-landscapes / cluster maps** — directions grouped by theme, the shape of the option space
- **Comparison matrices** — directions laid out across dimensions (qualitative notes, not scores), with no winner declared
- **Mind maps** — branching exploration of a topic, tangents preserved
- **Architecture / concept diagrams** — system components, data flow, relationship maps (Mermaid/D2 supported)
- **Side-by-side visual comparisons** — two directions rendered next to each other

**Use the terminal** when the content is text or tabular:

- **Scoping questions** — depth, recency, constraints, what the exploration serves
- **Conceptual A/B/C choices** — picking between approaches described in words
- **Tradeoff prose** — counter-arguments, challenge notes, open questions
- **Anything where the answer is words**, not a visual preference

A question *about* a visual topic is not automatically a visual question. "What should we research about layout systems?" is conceptual — use the terminal. "Which of these idea-cluster maps captures the space better?" is visual — use the browser.

## How It Works

`isles live <dir>` watches a directory for **Markdown** files and serves the **newest one** (by modification time) to the browser, auto-switching when you write a newer screen. You write `.md` screens to the screen directory; the user sees the rendered result and clicks to select options; selections are appended to `<dir>/state/events` (JSONL) that you read on your next turn.

You author **standard Markdown plus Agent Isles islands**. The renderer adds the page chrome, theme, dark mode, a live header/footer, and all interactive infrastructure — you never hand-write `<html>`, CSS, or `<script>`. Selection wiring is built into the islands; there is **no `onclick`/`data-choice`/`toggleSelect`** to manage.

## Requirements

The companion is launched through the Quirk bridge, which finds an Agent Isles runner automatically (in order):

1. repo-local `node_modules/.bin/isles`,
2. `isles` on `PATH`,
3. an explicit `npx` fallback (`github:zpyoung/agent-isles`, which currently carries `live`).

The npx fallback needs Node + `npx` available and will download Agent Isles on first use. If none of these resolve, the bridge prints a clear error instead of launching — fall back to terminal-only exploration and tell the user Agent Isles isn't available.

Throughout this guide, the bridge is invoked as `python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py"` (the exploring-ideas skill ships inside the Quirk plugin, so the bridge lives at the plugin root).

## Starting a Session

Pick a screen directory **inside the user's project** so screens persist and survive restarts. Use a unique session subdirectory, e.g. `.quirk/exploring-ideas/session-1/`:

```bash
SCREEN_DIR=".quirk/exploring-ideas/session-1"
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR"
# Prints one line of JSON, e.g.:
# {"type":"server-started","pid":92913,"port":53143,"host":"127.0.0.1",
#  "url":"http://localhost:53143","screen_dir":".../session-1","state_dir":".../session-1/state"}
```

The server **self-backgrounds**: the command prints the server-info JSON and returns immediately, so you do NOT need `run_in_background`. Save `url`, `screen_dir`, and `state_dir` from the JSON. Tell the user to open the `url`.

**Finding connection info later:** the same JSON is written to `<screen_dir>/state/server-info`. If the server has shut down, `<screen_dir>/state/server-stopped` exists instead.

**Persistence & git:** screens stay in `.quirk/exploring-ideas/` for later reference. Remind the user to add `.quirk/` to `.gitignore` if it isn't already.

**Remote/containerized setups:** if the printed URL is unreachable from the user's browser, relaunch binding a non-loopback host and control the printed hostname:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR" --host 0.0.0.0 --url-host localhost
```

The server auto-exits after 30 minutes of inactivity (tune with `--idle-timeout <minutes>`).

## The Loop

1. **Write a Markdown screen** to a new file in `screen_dir`:
   - Use semantic filenames: `idea-landscape.md`, `option-matrix.md`, `clusters.md`.
   - **Never reuse filenames** — each screen gets a fresh file. The newest by mtime is served.
   - Use the Write tool — **never use cat/heredoc** (dumps noise into the terminal).
   - If the server has stopped (`state/server-stopped` exists, or `state/server-info` is gone), relaunch it before writing.

2. **Tell the user what to expect and end your turn:**
   - Remind them of the URL (every step, not just the first).
   - Give a brief text summary of what's on screen (e.g., "Showing 5 idea clusters for the topic").
   - Ask them to respond in the terminal: "Take a look and let me know which directions resonate. Click to flag any you'd like to go deeper on."

3. **On your next turn** — after the user responds:
   - Read `<state_dir>/events` if it exists — JSONL of the user's browser clicks (see format below).
   - Merge with the user's terminal text. The terminal message is primary; events provide structured interaction data.

4. **Iterate or advance** — if feedback changes the current screen, write a new file (e.g. `idea-landscape-v2.md`). Only move on when the current screen is understood.

5. **Unload when returning to the terminal** — when the next step doesn't need the browser, push a waiting screen to clear stale content:

   ```markdown
   <!-- filename: waiting.md (or waiting-2.md, etc.) -->
   ## Continuing in the terminal…
   ```

6. Repeat until done.

## Authoring Screens

Write a normal Markdown document. Reach for islands only where richer UI helps.

### Selectable options (the core interaction)

Wrap `<agent-choice>` rows in an `<agent-option-set>`. Each choice needs a stable `id` (used as the event `choice`) and a short `title` (used as the event `text`); the body is the visible description.

```markdown
## Which directions should we go deeper on?

These are exploratory, not ranked — flag the ones that intrigue you.

<agent-option-set data-multiselect>
  <agent-choice id="behavioral-profile" title="Behavioral auto-profile">Build the profile from usage, no forms</agent-choice>
  <agent-choice id="docs-as-game" title="Docs as a game">Onboarding as a mystery to solve</agent-choice>
  <agent-choice id="finish-tool" title="Project-ending tool">Optimize for escape velocity, not retention</agent-choice>
</agent-option-set>
```

**Multi-select** (shown above with `data-multiselect`) suits idea-landscapes well — the user can flag several directions to explore further. The footer shows the count. Selecting one choice in a single-select set deselects its siblings. Add `selected` to a choice only for an initial selection.

### Idea-gate co-creation (keep / drop / deeper)

This is the browser surface for **Checkpoint 2 — the idea-landscape co-creation gate** (`--involve medium+`; see `references/interaction-model.md`). It reuses the same `<agent-option-set>` component — no new model. Render the directions surfaced by the first ideation pass as multi-select cards, one card per direction, each carrying its insight-pairing line:

```markdown
## Which directions should we keep exploring?

Exploratory, not ranked — flag the ones to keep, and tell me in the terminal what to drop or add.

<agent-option-set data-multiselect>
  <agent-choice id="behavioral-profile" title="Behavioral auto-profile">Build the profile from usage, no forms · *why it might work:* removes the blank-form drop-off</agent-choice>
  <agent-choice id="docs-as-game" title="Docs as a game">Onboarding as a mystery to solve · *why it might work:* curiosity beats compliance</agent-choice>
  <agent-choice id="finish-tool" title="Project-ending tool">Optimize for escape velocity, not retention · *why it might work:* trust compounds into referrals</agent-choice>
</agent-option-set>
```

- **Selected = keep / go-deeper; unselected = candidate to drop.** Read the final `selected` set from the `events` JSONL (see [Browser Events Format](#browser-events-format)) and merge it with the user's terminal text — the terminal is primary and is where **add-your-own** and explicit drops arrive (the browser has no free-text input).
- **No ranking, ever** — multi-select flags interest without ordering. Do not add scores, stars, or a "best" affordance; that would breach the no-winner gate in the browser too.
- After reading selections, run the **re-ideate loop** (drop / expand / ideate-added / one short refill pass), then push a fresh screen or unload to the terminal for the challenge pass.

### Other islands

- `<agent-decision verdict="deferred|needs-review" title="…">` — non-convergent status cards, for challenge-note callouts only. **Never** use the convergent verdicts (`go` / `approved` / `rejected` / `ship-with-guardrails`) — they declare a winner or an approved answer and breach the HARD-GATE.
- `<agent-risk level="low|medium|high|critical" title="…">` — risk/blocker callouts (handy for challenge notes).
- More components and exact attributes: Agent Isles `docs/component-vocabulary.md`.

### Maps, matrices, and diagrams

- For comparison matrices, use plain Markdown tables (directions × dimensions) — keep "no winner declared" intact.
- For idea-cluster maps, mind maps, and concept diagrams, use Mermaid or D2 fenced code blocks.
- Keep visuals simple — focus on the shape of the option space, not pixel-perfect design.

## Browser Events Format

Clicks are recorded to `<state_dir>/events`, one JSON object per line. The file is cleared automatically when you push a newer screen.

```jsonl
{"type":"click","choice":"docs-as-game","text":"Docs as a game","timestamp":1780956565,"selected":["docs-as-game"]}
{"type":"click","choice":"finish-tool","text":"Project-ending tool","timestamp":1780956570,"selected":["docs-as-game","finish-tool"]}
```

- `choice` / `text` come from the clicked `<agent-choice>`'s `id` / `title`.
- `selected` is the full set of currently-selected choice ids (most useful in multi-select).
- The last event is typically the final selection, but the click sequence can reveal hesitation worth asking about.

If `<state_dir>/events` doesn't exist, the user didn't interact with the browser — use only their terminal text.

## Design Tips

- **Scale fidelity to the question** — a cluster map for shape, a matrix for trade-offs.
- **Explain the question on each screen** — "Which directions intrigue you?" not just "Pick one".
- **Iterate before advancing** — if feedback changes the current screen, write a new version.
- **2–4 options (or a handful of clusters) max** per screen.
- **Never declare a winner on screen** — the gate applies in the browser too.

## File Naming

- Semantic names: `idea-landscape.md`, `option-matrix.md`, `clusters.md`.
- Never reuse filenames — each screen is a new file.
- For iterations, append a version suffix: `idea-landscape-v2.md`.
- Newest file by modification time is served.

## Cleaning Up

```bash
python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live "$SCREEN_DIR" --stop
```

Screens persist in `.quirk/exploring-ideas/` for later reference. The server also auto-exits after its idle timeout.

## Reference

- Component vocabulary and exact island attributes: Agent Isles `docs/component-vocabulary.md`.
- Bridge options: `python3 "$CLAUDE_PLUGIN_ROOT/bin/agent_isles.py" live --help`.
