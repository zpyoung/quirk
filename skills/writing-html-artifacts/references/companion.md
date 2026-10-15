# Companion

The companion is a local page that shows the user one question at a time in a browser and sends their clicks back. Brainstorming and exploring-ideas use it for visual questions. Read this before starting a session. For screen design, see section 12 of the [design reference](design-reference.md); for custom branding of screens, see [templates](templates.md).

Script paths below are relative to the skill directory, the one holding this skill's `SKILL.md`. Every command prints exactly one JSON object to stdout; diagnostics go to stderr.

## The loop

1. **Start once** per session: `scripts/companion.py start SESSION_DIR`. Keep the printed `url`; give it to the user. A second `start` for a live session reuses the server.
2. **Show per question**: write a `screen.json` and run `scripts/companion.py show SESSION_DIR SCREEN.json`. One question per screen.
3. **Wait**: `scripts/companion.py wait SESSION_DIR`. It blocks until the user clicks Proceed on the current screen.
4. **On exit 1 (timeout), re-run `wait`.** The host's tool limit is 120 s and the default timeout is 110 s, so a timeout is normal. No click is lost; the events file is append-only.
5. **Read the result**: `proceed` holds the final selection and note; `clicks` holds every click on this screen in order, so you can see what the user considered and changed.
6. **Terminal input outranks clicks.** If the user types something in the terminal, act on that, not on the page's selection. Clicks are a convenience, not an instruction that overrides the user's words.
7. Record decisions in the spec or plan. Screens and events are transient and are not the record.
8. **Stop** with `scripts/companion.py stop SESSION_DIR` when the session ends. The server also stops itself when idle.

`SESSION_DIR` lives under `.quirk/brainstorm/`, for example `.quirk/brainstorm/2026-10-13-dashboard/`. That directory is self-ignored by git, so nothing in it is ever committed.

## Commands

```
companion.py start SESSION_DIR [--host 127.0.0.1] [--allow-host HOST[:PORT]]... [--port 0] [--idle-minutes 30] [--foreground]
companion.py show  SESSION_DIR SCREEN.json [--project-dir DIR]
companion.py wait  SESSION_DIR [--timeout 110]
companion.py events SESSION_DIR [--screen ID]
companion.py stop  SESSION_DIR
```

| Command | Prints | Exit codes |
|---|---|---|
| `start` | `{"type": "server-started", "pid", "port", "host", "allowed_hosts", "url", "screen_dir", "state_dir"}` | `0` started or reused; `2` the server wrote no `server-info` within 10 s |
| `show` | `{"screen", "nonce", "url", "checks"}` | `0` shown; `1` a static check failed (the screen is written but not made current); `2` malformed `screen.json` or missing session |
| `wait` | `{"proceed": <event>, "clicks": [<event>, ...]}` | `0` proceed received; `1` timeout, stdout `{"status": "timeout", "screen"}`, stderr says to re-run; `2` no live server, stdout `{"status": "no-server"}` |
| `events` | `{"events": [...]}` | `0` |
| `stop` | `{"stopped": bool}` | `0`, with `stopped: false` when no server was running |

Flags:

- `start --host`: bind address, default `127.0.0.1`. `--allow-host HOST[:PORT]`: also accept this `Host` header; repeatable, recorded in `server-info` as `allowed_hosts`. A bare `HOST` allows any port, `HOST:PORT` that exact pair. `--port`: `0` picks a free port. `--idle-minutes`: shutdown after this much inactivity, default 30. `--foreground`: run in the current process instead of detaching, mainly for tests.
- `show --project-dir`: where to find project tokens and templates; defaults to the git toplevel of the current directory.
- `wait --timeout`: seconds to block, default 110.
- `events --screen ID`: only events for that screen, for example `0003-layout`.

`wait` exit 2 means no live server: `server-info` is missing or unparseable, `server-stopped` exists, the pid is dead, or the recorded port does not answer as the companion. A dead pid also gets `server-stopped` with reason `stale`; a live pid that fails the probe does not, so one failed probe never marks a healthy server dead. Run `start` again, then `show` the current question again.

## `screen.json`

```json
{
  "title": "Layout",
  "question": "Which layout fits the dashboard?",
  "select": "single",
  "options": [
    { "id": "two-col", "label": "Two column", "description": "Filters left, results right", "html": "<optional mockup>" },
    { "id": "stacked", "label": "Stacked", "description": "Filters above results" }
  ],
  "content": "<optional freeform HTML: mockup, comparison, notes>",
  "diagram": "<optional Mermaid source>",
  "layout": "<optional page shape, for example dashboard>"
}
```

- `title` is short and becomes the page `<title>`. `question` is the header the user reads.
- `select` is `single` or `multi`.
- `options` has 2 to 4 entries. Each `id` is unique and matches `[a-z0-9-]{1,40}`. `label` is what the user clicks, `description` says the consequence, and `html` is an optional per-option mockup.
- `content` is freeform HTML shown with the question. `diagram` is Mermaid source; the screen loads the server-hosted Mermaid build only when `diagram` is set.
- `layout` is optional, one of the seven page shapes: `report`, `explainer`, `longform`, `tool`, `comparison`, `dashboard`, `reference`. Any other value is a malformed `screen.json` (`show` exits 2, and the error lists the seven). See [Screen width and layout](#screen-width-and-layout).
- A screen that only shows something still offers 2 to 4 options about it.
- `content` and option `html` are served exactly as written. Do not paste untrusted text into them.
- Kit `q-*` elements go in `content` or an option's `html` unchanged; only non-interactive ones may go in `html` (see the companion rules and [components](components.md)).

## Screen width and layout

A screen is 960px wide unless it names a `layout`. Name one when the question is about a wide thing: a dashboard's panels, a comparison table, a reference page. The screen then widens to 1440px, and a `dashboard` screen is fluid.

- The `layout` key only sizes the screen. Its question, options and Proceed button stay in the same order, and there is no `summary` slot: the `question` is the summary.
- The layout check does not run on screens. The `html` and `content` you write draw mockups of other layouts, so inline `display:grid` and fixed widths are fine there.
- Name the shape the screen is about only when it needs the width. A screen about a form's field order stays unnamed.
- The same `layout` is written into the screen's generated source header, so a screen is built like any other page of that shape.

The example screens, one per shape, are in `templates/companion/examples/<shape>.screen.json`: `report`, `explainer`, `longform`, `tool`, `comparison`, `dashboard` and `reference`. Copy the closest one.

## Event record

`state/events` is JSONL, one record per accepted event. `wait` and `events` return these records.

```json
{"type": "click", "screen": "0003-layout", "nonce": "<token>", "choice": "two-col", "text": "Two column", "selected": ["two-col"], "note": null, "timestamp": 1760356800.5}
```

- `type` is `click` (an option toggled) or `proceed` (the Proceed button).
- `choice` is the option id for a click, and `null` for proceed. `selected` is the whole selection at that moment, and `note` is the optional text field.
- `wait` returns the first `proceed` for the current screen at or after the time that screen was shown, plus that screen's clicks.

## Stale screens

- Every `show` mints a new nonce and makes a new file. Filenames are `screens/NNNN-<slug>.html` with a zero-padded counter and are never reused.
- A click from an older screen is rejected with 409. The old tab shows a "superseded" banner and disables its controls within about 2 seconds, so the user knows to switch to the new tab.
- A stale click never appears in `events`, so you cannot mistake it for an answer to the current question.

## Idle shutdown

- With no HTTP request and no `show` for `--idle-minutes` (default 30), the server writes `state/server-stopped` with reason `idle` and exits.
- `stop` and a termination signal write reasons `stop` and `signal`.
- After a stop, `wait` exits 2. Start a new server with `start`.

## Session directory

| Path | Contents |
|---|---|
| `screens/NNNN-<slug>.html` | each built screen |
| `state/current.json` | `{"screen", "nonce", "shown_at"}` for the current screen |
| `state/server-info` | the `server-started` JSON |
| `state/server-stopped` | `{"reason": "idle" or "stop" or "signal" or "stale", "at"}`, present once the server has exited |
| `state/events` | the event stream |
| `state/server.log` | server output, for debugging |

## Security

- The server binds `127.0.0.1` by default. Only the local machine can reach it.
- **`--host 0.0.0.0` exposes the session to the network.** Use it only for a remote container the user asked for, and tell the user the URL is open to anyone who can reach that address.
- **Remote or container use needs `--allow-host`.** The server answers 403 to any `Host` header that is not the bound address, loopback or an own interface address on the bound port, or an `--allow-host` entry. Pass `--host 0.0.0.0 --allow-host <the name and port the browser uses>`; for a port mapping such as 8080 to 3000, use `--allow-host localhost:8080`. A browser omits a default port from the `Host` header, so for a port 80 or 443 mapping use a bare `HOST`, because `HOST:80` never matches. The expected `Origin` is derived from the accepted `Host`.
- **`start` reuses a live server only when the host flags agree.** Plain `start` with no `--host` or `--allow-host` reuses it. A `--host` or `--allow-host` set that differs from the live server's recorded `host` and `allowed_hosts` exits 2 with a JSON error. To switch to remote access, run `stop`, then `start --host 0.0.0.0 --allow-host ...`.
- A request that stalls mid-body is dropped after 10 s.
- Events need the current screen's nonce, and the server rejects a foreign `Origin` or `Host` with 403, malformed JSON or a body over 64 KB with 400.
- The server serves only the current screen, its state, and the vendored library files named in `libraries.json`. Nothing else on disk is reachable.
- Screen HTML is not sanitized. Write it yourself, and do not include secrets: it is visible to anyone with the URL.
