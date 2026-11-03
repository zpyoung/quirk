# Tech spec: UX review step with clickable mocks

**Status**: Draft · Logic spec: [logic.md](logic.md)

Paths below use `SK` = `skills/writing-html-artifacts`, `S` = `SK/scripts`, `A` = `SK/companion-app/app`, `H` = `SK/companion-app/harness`. All paths are relative to the repository root.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Unit | Files | Role |
|---|---|---|
| Step contract | `S/htmlkit/steps.py`, `S/htmlkit/appstate.py`, `S/companion.py` (submit validation only) | New step kind `mock-review` and rail stage `ux-review`; mock-review verdicts |
| Mock registry | `S/htmlkit/appstate.py`, `S/companion.py` | `mock` and `mock-export` subcommands, `state/mocks/` storage, `GET /_quirk/mock/<N>` route that serves the harness with the mock embedded |
| Harness | `H/mock-harness.html`, `H/harness-core.js` | The quirk-owned review page: an outer page holding the toolbar, screen rail, pins and verdict bar, around an inner `srcdoc` iframe holding the agent's mock. Runs in `app` mode (served) and `offline` mode (exported file) |
| Shell view | `A/src/types.ts`, `A/src/views/mock-review.tsx`, `A/src/views/step-area.tsx`, `A/src/theme.css`, `SK/companion-app/shell.html` (built) | Renders a `mock-review` step as a full-height iframe of `/_quirk/mock/<N>?t=<token>` |
| Skill text | `skills/brainstorming/SKILL.md`, `skills/brainstorming/visual-companion.md`, `skills/brainstorming/references/ux-review.md` (new) | When the step runs, the loop, the mock-writing guide |
| Spec and execution text | `skills/writing-specs/logic-spec.md`, `skills/writing-specs/interactive-logic-spec.md`, `skills/subagent-driven-development/SKILL.md`, `skills/executing-plans/SKILL.md` | Screens section and the source-of-truth rule |

Why the harness wraps the mock instead of being injected into it: the viewport toggle must change the mock's real layout width, which only an iframe whose width the harness controls can do. The inner frame uses `srcdoc` without `sandbox`, so it shares the outer page's origin (in both `http://` and `file://`), and the harness reads and annotates its DOM directly with no `postMessage`.

Technologies: Python 3 stdlib server (`http.server`), plain browser JavaScript for the harness (no build step), React 19 + Vite + `vite-plugin-singlefile` for the shell (existing).

## Code references

Back-links: [Conceptual model](logic.md#conceptual-model).

- `S/htmlkit/steps.py:14` `STEP_KINDS`, `:15` `STAGES`, `:21` `COMMON_KEYS`, `:22` `KIND_KEYS`, `:310` `KIND_BUILDERS`, `:320` `validate_step(raw) -> dict`. Reuse the helpers `_id`, `_string`, `_check_keys`.
- `S/htmlkit/appstate.py:27` `STAGES` (second copy, used by `write_step` at `:170` and `snapshot()` at `:430`), `:371` `add_comment`, `:399` `reply`, `:418` `set_review`, `:423` `review_path` (the pattern the mock registry mirrors).
- `S/companion.py:82` `BLOCK_ID`, `:83` `TOKEN_HEADER`, `:85` `SHELL_PLACEHOLDER`, `:91` `VERDICTS`, `:433` `_guard`, `:443` `do_GET`, `:490` `_serve_shell` (the boot-injection pattern to copy), `:515` `_serve_review`, `:607` `_check_token`, `:839` `_submit_problem`, `:1353` `_cmd_step`, `:1404` `_cmd_review`, parser near `:1574`.
- `A/src/types.ts:1` `STAGES`, `:4` `STAGE_LABELS`, `:90` `Step` union, `:102` `StepKind`, `:159` `Snapshot`.
- `A/src/views/step-area.tsx:35` `renderStep` switch; `A/src/views/spec.tsx:12` (the interactive-review iframe pattern to copy); `A/src/theme.css:608` `.review-frame`.
- `A/scripts/check-steps.ts` (renders every valid fixture; needs a `mock-review` case), `A/scripts/check-template.ts` (fails if the committed `shell.html` is stale), `A/package.json` `check` script, `A/e2e/run.ts` (Playwright against a real server).
- Fixtures: `SK/companion-app/fixtures/steps/valid/`, `SK/companion-app/fixtures/steps/invalid/` plus `invalid/expected.json`.
- Brainstorming: `skills/brainstorming/SKILL.md` Checklist lines 26-37 (new item goes between item 8 and item 9), digraph edge `"Propose 2-3 approaches" -> "Present design sections"` (line 65), "Start the companion" bullets (lines 91-92), Domain Detection table (lines 152-164), Terminal flow (line 331). `skills/brainstorming/visual-companion.md` stage list (line 46), step-kind table (lines 48-56), submit-event table (line 113).
- Specs and execution: `skills/writing-specs/logic-spec.md` required-sections list (lines 20-26); `skills/writing-specs/interactive-logic-spec.md` stage-1 content (lines 9-19); `skills/subagent-driven-development/SKILL.md` end of Step 3 (after line 173); `skills/executing-plans/SKILL.md` Step 1 (around line 54).

## Contracts & interfaces

### Step kind `mock-review`

Back-links: [Main path](logic.md#main-path), [SC-6](logic.md#main-path).

- `STEP_KINDS` gains `"mock-review"` after `"approaches"`. `STAGES` (all three copies: `steps.py`, `appstate.py`, `types.ts`) gains `"ux-review"` between `"approaches"` and `"design"`; `STAGE_LABELS["ux-review"] = "UX review"`.
- `KIND_KEYS["mock-review"] = {"version"}`. `version` is a positive integer, not a bool. Field errors use the key name (`version`).
- `_cmd_step` additionally rejects a `mock-review` step whose `version` is not registered: exit 2, `{"error", "field": "version"}`.
- Submit payload: `{verdict, comment?, visited?, marks?}`. `VERDICTS["mock-review"] = ("looks-right", "needs-changes", "skip")`. `visited` and `marks` are optional lists of at most 200 screen ids, each matching the screen-id regex below. Any other key is a 400.

### `mock` subcommand

Back-links: [What a mock must do](logic.md#what-a-mock-must-do), [SC-4](logic.md#main-path).

`COMMAND:`
```
python3 companion.py mock SESSION MOCK_HTML --version N --screens SCREENS_JSON [--changed CHANGED_JSON]
```

- Prints `{"version": N, "mock_url": "/_quirk/mock/N"}` and exits 0. Works whether or not the server is running.
- Exit 2 with `{"error", "field"?}` when: `MOCK_HTML` is unreadable, not UTF-8, or larger than 5 MiB; `SCREENS_JSON` or `CHANGED_JSON` fails the schema below; `N` is not `1` for the first registration, or not equal to the latest version or latest + 1 afterwards.
- Copies the HTML to `state/mocks/v<N>.html` (so later edits to the agent's file never change a version under review) and records the version in `state/mocks.json`, both with `atomic_write`. Re-registering the latest version replaces it. Without `--changed`, `changed` is empty (Show changes outlines nothing).
- The snapshot gains `"mocks": {"latest": <int|null>, "versions": [<int>, ...]}`.

### `mock-export` subcommand

Back-links: [What the signed-off mock feeds](logic.md#what-the-signed-off-mock-feeds), [SC-13](logic.md#what-the-signed-off-mock-feeds), [SC-15](logic.md#edges-and-fallback).

`COMMAND:`
```
python3 companion.py mock-export SESSION --version N --out DIR
```

- Writes `DIR/mock.html` (the harness in `offline` mode with version N embedded), `DIR/screens.md` (the inventory as markdown: one table per screen with states, skipped states with reasons, elements with components; then a Gaps list), and `DIR/review.json` (schema below). Prints `{"files": [<abs paths>]}`.
- Works without a server. Exit 2 for an unknown version or an unwritable `DIR`.
- This is also the terminal-flow path: the agent registers with `mock`, exports to the session folder, and prints the `mock.html` path.

### Route `GET /_quirk/mock/<N>`

Back-links: [When it runs](logic.md#when-it-runs), [Key decisions](logic.md#key-decisions-and-rationale).

- App mode only; `_guard` first. Requires query `t` equal to the session token (constant-time compare); otherwise 403 `{"error": "bad token"}`. Unknown `N` is 404. A harness template missing or without exactly one boot placeholder is 500 `{"error": "mock harness missing"}`.
- Serves `H/mock-harness.html` (override path with env `QUIRK_MOCK_HARNESS`, for tests) with the boot placeholder replaced by the boot JSON (schema below), `<` escaped as `<`. Content-Type `text/html; charset=utf-8`, via `_reply` (keeps `no-store`, `nosniff`).
- `mock-export` uses the same template-filling function with `mode: "offline"` and no token.

### Harness boot and placeholders

`CONFIG:` the template contains exactly one `<script id="quirk-mock-boot" type="application/json">null</script>`. The harness core (`H/harness-core.js`) is inlined into the template at fill time, replacing exactly one `<!--quirk-harness-core-->` comment, so the served and exported pages are both single files.

### Harness behaviour

Back-links: [Conceptual model](logic.md#conceptual-model), [SC-5](logic.md#main-path), [SC-7](logic.md#main-path), [SC-9 to SC-12](logic.md#revisions-and-pins).

- Reads boot JSON; sets the inner iframe's `srcdoc` to `mock_html` after inserting `<base href="about:srcdoc">` as the first child of the mock's `<head>` (creating one if absent). Without it a `srcdoc` document resolves `href="#/x"` against the harness URL, so an in-mock link navigates the frame away to a cross-origin document and every DOM access throws. Mode `app`: polls `GET /_quirk/app/snapshot?rev=` every 1 s (same as the shell) for `threads`, `step`, `step_state`, `mocks`.
- **Navigation.** The mock routes by `#/<screen-id>`. The harness listens for `hashchange` on the inner window (re-attached on every inner `load`) and reads `location.hash` to know the current screen; an empty hash means the first inventory screen. It marks the current screen visited. A rail click sets the inner `location.hash`. A screen not in the inventory shows a warning chip, not an error. The mock renders its own "Not in this mock" notes (mock-writing guide); the harness does not.
- **States.** Inside the current `[data-screen="<id>"]`, the harness shows the `[data-state]` child matching the switcher and sets `hidden` on the others. The first entry of `states` is the default. Skipped states are listed under the switcher with their reasons.
- **Viewport.** Inner frame width 100% (desktop) or 390 px (mobile).
- **Comment mode** (app mode, latest version, current step is `mock-review` for this version and `step_state` is `open`): hover outlines the nearest ancestor with `data-pin` and shows its component name from the inventory (or "gap" / nothing); click opens a note; send posts a `comment` event with the pin block id. Elements without `data-pin` cannot be pinned (the harness says so).
- **Pins.** For each thread whose `block_id` parses as a pin: same version → drawn at the element plus percentage offset; older version and the key exists in the current screen/state → drawn re-anchored with a "from vX" badge; older version and the key is missing → listed in the rail as orphaned "element removed in v<current>", never drawn on another element; newer version → hidden. A resolved thread shows its last agent message.
- **Versions.** Picker lists `mocks.versions`; picking one navigates to `/_quirk/mock/<M>?t=<token>`. Any version other than `mocks.latest` is read-only: no comment mode, no verdict bar.
- **Show changes.** Outlines every element whose `data-pin` is in `changed`.
- After a submit the snapshot's `step_state` is `submitted`, so comment mode and the verdict bar lock until the agent sends the next `mock-review` step. That is intended.
- **Verdict bar** (same conditions as comment mode): Looks right (if any inventory screen is unvisited, list them and require one confirm click), Needs changes (optional overall comment), Skip review. Posts a `submit` event with the step's `nonce` and `step` id from the snapshot and payload `{verdict, comment?, visited, marks}`.
- **Offline mode:** rail, states, viewport, Show changes and the screen list work; comment mode, pins and verdict bar are absent; a banner names the version and says the mock is not the product.
- App-mode POSTs go to `/_quirk/app/event` with header `X-Quirk-Token` and body `{client_id, type, nonce?, step?, payload}`, the same shape as `A/src/transport.ts:10` `postEvent`, retrying network errors with the same `client_id`.

### Shell view

Back-links: [SC-4](logic.md#main-path).

- `renderStep` gains `case 'mock-review'` → `views/mock-review.tsx`: inside `StepFrame`, an `<iframe className="mock-frame" title="Mock review" src="/_quirk/mock/<version>?t=<token>">` with no `sandbox`, height `calc(100vh - 10rem)`, min-height 32rem. No shell `VerdictBar`: the harness owns the verdict.
- The rebuilt `SK/companion-app/shell.html` is committed in the same task.

## Data models

Back-links: [Glossary](logic.md#glossary).

`SCHEMA:` screens file (`--screens`), shared by the server (validation, `screens.md`), the harness (rail, switcher, hover labels) and the skill guide.
```
{
  "ui_layer": bool,                         // false → no component column, no gaps (SC-16)
  "screens": [                              // 1..50, ids unique, first is the entry screen
    {
      "id": str,                            // screen-id regex
      "title": str,                         // 1..80 chars
      "purpose": str,                       // 1..200 chars
      "states": [str, ...],                 // 1..8 state ids, unique; first is the default
      "skipped_states": [{"state": str, "reason": str}],   // optional
      "elements": [                         // optional, pin keys unique within the screen
        {"pin": str, "label": str, "component": str | null}
      ]
    }
  ]
}
```
A **gap** is an element with `component: null` while `ui_layer` is true.

`SCHEMA:` changed file (`--changed`): `{"changed": [pin-key, ...]}` (at most 500).

`SCHEMA:` `state/mocks.json`: `{"versions": {"<N>": {"file": "mocks/v<N>.html", "screens": <screens>, "changed": [pin-key], "registered_at": <iso8601>}}}`.

`SCHEMA:` boot JSON: `{"mode": "app"|"offline", "version": int, "latest": int, "versions": [int], "token"?: str, "screens": <screens>, "changed": [pin-key], "mock_html": str}`.

`SCHEMA:` `review.json`: `{"version": int, "exported_at": iso8601, "pins": [{"thread_id": str, "version": int, "screen": str, "state": str, "pin": str, "messages": [{"from": str, "text": str, "timestamp": str}], "resolution": "addressed"|"not-addressed"|null}]}`. Only threads whose block id parses as a pin are included.

`REGEX:` ids
```
screen-id, state-id:  ^[a-z0-9-]{1,40}$
pin-key:              ^[a-z0-9][a-z0-9._-]{0,79}$
pin block id:         ^mock:v([1-9][0-9]{0,3})/([a-z0-9-]{1,40})/([a-z0-9-]{1,40})/([a-z0-9][a-z0-9._-]{0,79})/x([0-9]{1,3})-y([0-9]{1,3})$
```
The pin block id always fits the existing `BLOCK_ID` pattern (at most 200 chars, allowed charset). `x` and `y` are integer percentages (0-100) of the element's box.

## DO-NOT-CHANGE fences

Back-links: [Scope and non-goals](logic.md#scope-and-non-goals).

- **Screen mode** (`start` without `--app`, `show`, `wait`, `events`, `GET /` in screen mode, `POST /_quirk/event`, `load_screen`, `companion.js`). exploring-ideas depends on it; `tests/test_html_companion.py` must pass unchanged.
- **`/_quirk/review` and `/_quirk/review/export`, `REVIEW_KINDS`, and the review export JSON shapes.** The interactive spec review relies on them; the mock route is separate.
- **`BLOCK_ID` and comment-event validation.** Pins must fit the existing comment path, which is what makes them ordinary threads.
- **`_guard` on every route and the `libraries.json` whitelist.** They are the server's only access control.
- **`SK/vendor/kit/1.0.0/kit.js`** is checksum-pinned; no kit change is needed.
- **Existing step kinds' schemas and verdicts.** Other brainstorm steps and their fixtures must validate unchanged.
- **Pinned brainstorming strings** listed under Testing strategy, except the checklist item number pin, which moves deliberately.

## Always / Ask / Never

- **Always:** write state with `atomic_write`; print one JSON object per subcommand with exit codes 0/1/2; validate before anything becomes current; render user and agent text as text in the harness (no `innerHTML` with thread text); keep the three `STAGES` copies identical; rebuild and commit `shell.html` with any `A/src` change.
- **Ask:** before adding any runtime dependency (the harness is dependency-free JavaScript); before changing a pinned test other than the contract-constant and checklist-number pins named here.
- **Never:** accept an app POST without the token; serve `/_quirk/mock/<N>` without the token; add network fetches beyond same-origin `/_quirk/*`; let the harness move a pin onto an element whose key differs; give the inner iframe a `sandbox` attribute (it would break same-origin DOM access).

## Cross-cutting

- **Security.** The token in `GET /_quirk/mock/<N>?t=` is the same token the shell already embeds in its interactive-review iframe URL. The mock HTML is agent-authored and runs same-origin with the harness, so it can read the token; that matches the existing trust model (agent-authored step HTML already renders inside the shell). Exported `mock.html` contains no token.
- **Rollback.** Sessions without a registered mock behave exactly as before; removing the step kind leaves stored sessions readable except for `mock-review` steps.
- **Size.** The 5 MiB mock cap keeps `mock.html` exports reasonable to commit.

## Testing strategy

- `tests/test_companion_app_steps.py`: update the contract-constant pins; valid fixture `valid/mock-review.json`; invalid fixtures for a missing, zero, bool and string `version` with `expected.json` entries.
- `tests/test_companion_appstate.py`: stage list pin; mock registry round trip; snapshot `mocks` field.
- `tests/test_companion_mock.py` (new): `mock` subcommand success and every exit-2 case; version sequencing; copy immutability; `step` rejects an unregistered version; route 403 without or with a bad token, 404 unknown version, 500 missing template, boot JSON injected once and `<` escaped; foreign Origin 403; `mock-export` writes three files, offline boot has no token, `review.json` contains only pin threads with resolutions; submit verdict validation (`skip` accepted, unknown key 400, `visited` id validation).
- `A/scripts/check-steps.ts`: a `mock-review` case asserting the iframe `src` and `data-step-kind`.
- `A/scripts/check-harness.ts` (new, added to `pnpm run check`): pure-logic tests for `H/harness-core.js`: pin block id parse/format round trip and rejection of malformed ids; pin placement decision (same version, re-anchored, orphaned, hidden); unvisited-screens list; gap derivation.
- `A/e2e/run.ts`: one mock-review scenario against a real server, with a mock that navigates by plain `<a href="#/...">` links: register v1, click an in-mock link and verify the rail follows, send the step, switch state and viewport, pin a comment, submit Needs changes; register v2 without the pinned key and with a changed key; verify the orphaned listing and the change outline; submit Looks right with an unvisited screen and confirm. Exit 3 (no browser) is reported, not treated as a pass.
- `tests/test_brainstorming_elicitation.py`: the "12. **Transition to implementation**" pin becomes "13."; all other brainstorming pins stay satisfied; `SKILL.md` stays within its 400-line budget.
- `tests/test_writing_specs_skill.py` must pass unchanged (cross-file links resolve).

## Non-goals

Back-links: [Scope and non-goals](logic.md#scope-and-non-goals).

Teammate review, design-tool export, accessibility audit, real data, terminal-UI mocks, a screen-diff step, hosted publishing. Also not covered here: changing writing-html-artifacts' builder or templates (the guide tells the agent to build mocks with the existing tier-1 `build` or tier-2 `build-app` commands, whose output is already self-contained).
