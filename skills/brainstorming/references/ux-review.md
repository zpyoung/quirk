# UX review

The UX review is the checklist step between *Propose approaches* and *Present design*. You build a clickable mock of the chosen approach, the user clicks through it and pins comments, and no design section is written until they pick Looks right or Skip review. The approved behavior is in `docs/quirk/specs/2026-11-03-ux-review-step/logic.md`; the commands and schemas are in `tech.md` beside it. `$COMPANION` and `$SESSION` are as in [visual-companion.md](../visual-companion.md).

## When it runs

It runs automatically for UI work, and the user can skip it from the review screen at any point.

- UI means a screen a person uses (web, app or desktop pages, components, dialogs, flows) or a generated page (HTML reports, dashboards, companion or artifact pages).
- Terminal UIs and CLI output don't count. A brainstorm that only touches those, or an API with no screens, sees no UX review stage, question, chat line or mock.
- Decide at domain detection. For UI work, say once in the chat that a clickable mock comes after the approach pick and can be skipped from the review screen, and record a decision with stage `ux-review` through `decide` at that moment (label `UX review`, value `runs after the approach pick`); that is what adds the *UX review* stage to the rail. Don't ask whether to run it.

## Writing the screen inventory

Write the inventory before the mock. It is the list the mock must cover and the list the spec cites later.

- One entry per screen of the chosen approach, with its purpose and its states: default, empty, loading, error, plus any state the approach adds. The first state is the default.
- A state a screen genuinely doesn't have goes in `skipped_states` with a reason, so the mock can say so.
- List the elements a reviewer might comment on, each with a `pin` key and the repo component it would use. Look the components up in the repo before naming them.
- An element with no matching component is a **gap** (`component: null`). Each gap becomes an open question in the spec.
- When the repo has no component library, set `ui_layer` to `false`. The components column then reads "none (no UI layer)" and no gaps are raised.

Save it as JSON with the Write tool and pass it to `mock --screens`. The shape is the `SCHEMA:` screens file in `tech.md`:

```json
{
  "ui_layer": true,
  "screens": [
    {
      "id": "saved-exports",
      "title": "Saved exports",
      "purpose": "List the exports a user saved and start a new one.",
      "states": ["default", "empty"],
      "skipped_states": [{"state": "error", "reason": "the list is served from a local cache"}],
      "elements": [
        {"pin": "new-export-btn", "label": "New export", "component": "Button"},
        {"pin": "date-range", "label": "Date range", "component": null}
      ]
    }
  ]
}
```

Ids are `[a-z0-9-]{1,40}`, the first screen is the entry screen, and pin keys are unique within a screen and match `[a-z0-9][a-z0-9._-]{0,79}`.

## Writing the mock

The mock is one HTML file that shows every inventory screen in every state, styled to be reviewed and never shipped. The companion injects the review UI around it, so the file holds product screens only: no toolbar, no verdict buttons, no pin UI.

**Look and content**

- Neutral house style: greys and one accent, system fonts, no brand palette. Color and polish pull review toward style and away from flow.
- Real, specific content (names, dates, counts, plausible copy). No lorem ipsum.
- Reflow at 390px, because the viewport toggle only changes the frame width.

**Structure and keys**

- Every screen is an element with `data-screen="<screen-id>"`. Each state variant inside it is a child with `data-state="<state-id>"`. The harness shows the child that matches its state switcher.
- Everything a reviewer might comment on has a unique `data-pin="<key>"` within its screen. The keys in the inventory's `elements` are the ones to use.
- Keys stay the same across versions. A pin follows its key when the element moves, and is marked orphaned when the key disappears, so never rename a key to tidy up. Only drop a key when the element is really gone.

**Navigation and interaction**

- Route with hash links only: `<a href="#/saved-exports">`. An empty hash means the first inventory screen. Every inventory screen must be reachable through the mock's own navigation.
- A path you didn't build shows a visible "Not in this mock" note that the mock renders itself, never a dead link or a silent no-op. The harness doesn't add these.
- Make the key interactions work: dialogs open and close, tabs switch, forms accept input and show a canned result.
- No network calls, no real data, no storage beyond the page's own state.

**Building it.** Follow [writing-html-artifacts](../../writing-html-artifacts/SKILL.md). Use tier 1 (`quirk_html.py build`) by default, because it needs no Node and avoids build failures. Use tier 2 (`build-app`) only when a screen's interaction needs it, and fall back to tier 1 when `build-app` exits 3. While you build, set the status line to the progress, for example `Building mock: 3 of 5 screens` with `--stage ux-review --progress 3/5`.

## Registering a version

Register every version before showing it. The companion keeps its own copy, so editing your file later never changes a version under review.

```bash
python3 "$COMPANION" mock "$SESSION" "$SESSION/mock/v1.html" --version 1 --screens "$SESSION/mock/screens.json"
python3 "$COMPANION" mock "$SESSION" "$SESSION/mock/v2.html" --version 2 --screens "$SESSION/mock/screens.json" --changed "$SESSION/mock/changed-v2.json"
```

- Versions count up from 1. Registering the latest version again replaces it; skipping a number is an error.
- `--changed` takes `{"changed": ["new-export-btn", ...]}`: the pin keys of elements you changed since the previous version. The harness outlines them when the user turns on Show changes. Leave it off for v1.
- Exit 2 prints `{"error", "field"}`. Fix the named input and register again.
- Then send the step, with `stage: "ux-review"`, and wait for events as usual:

```json
{"v": 1, "kind": "mock-review", "stage": "ux-review", "title": "Review the saved-exports mock", "version": 1}
```

## The review loop

The user's verdict decides the next move, and the loop has no round cap. They can leave it at any time with Skip review.

1. Send the `mock-review` step for the newest version. The user clicks through in Interact mode and pins comments in Comment mode.
2. Each pin arrives as a `comment` event whose `block_id` is `mock:v<N>/<screen>/<state>/<pin-key>/x<pct>-y<pct>`. Answer it with `reply` in its thread when you can, and always before the verdict is acted on.
3. On **Needs changes**, the submit event carries the overall comment plus `visited` and `marks`. Reply in every open pin's thread with exactly one outcome:
   - Changed: reply saying what changed and use `--resolve addressed`.
   - Declined: reply with the reason and use `--resolve not-addressed`.
   - Open question: reply that it is carried into design, and don't resolve the thread.
4. Write the next version with the changes, register it with `--changed` listing the pin keys you touched, and send a new `mock-review` step for it.
5. Repeat from step 1.

Replying looks like this:

```bash
python3 "$COMPANION" reply "$SESSION" THREAD_ID --text "Moved to the header on mobile." --resolve addressed
```

**Sign-off rule: never close the step while any pin lacks a reply.** When the user picks **Looks right** and a pin is unanswered, reply to it first and carry it into design as an open question, then close the step. A pin whose element was removed in a newer version stays in its thread and is not re-anchored.

On **Looks right**, keep the final version number, the inventory and the pin history for the spec. Record the sign-off with `decide`, and keep every gap and every open-question pin as an open item for the spec.

## Skip review

Skip review is always allowed and moves the brainstorm straight to the design sections.

- Record "UX review: skipped at v<N>" in the decisions (`decide`), so Decisions Locked carries it.
- Each pin still open becomes an open question, listed in the first design section that touches it.
- Export nothing and copy nothing to the spec folder.

## After sign-off

The signed-off mock feeds the design sections and the spec.

- Design sections cite screens by name ("Saved exports, empty") instead of re-describing layouts. Pins carried as open questions are listed in the first design section that touches them.
- When the logic spec is written, export the final version next to it:

  ```bash
  python3 "$COMPANION" mock-export "$SESSION" --version 3 --out docs/quirk/specs/<date-slug>/mock
  ```

  It writes `mock.html` (the harness in offline mode, opens from disk), `screens.md` (the inventory with components and gaps) and `review.json` (every pin, its replies and its outcome).
- The spec's Screens section and per-screen acceptance items are required by the [logic-spec rubric](../../writing-specs/logic-spec.md). Gaps become open questions.
- The mock is the visual target. Execution rebuilds it in the project's stack and never lifts mock code.

## Terminal flow

With `--terminal`, or when the companion can't run, there are no pins and no `mock-review` step. The state switcher, viewport toggle and screen list still work.

1. Write the inventory and the mock as above, then register the version: `mock "$SESSION" ... --version N --screens ...`. Both commands work without a server.
2. Export it into the session folder: `mock-export "$SESSION" --version N --out "$SESSION/mock-vN"`.
3. Print the path of the exported `mock.html`.
4. Ask the verdict through `orca ask`, or `AskUserQuestion` when `orca ask` isn't available, with three options: Looks right, Needs changes (free text for what to change), Skip review.
5. On Needs changes, write the next version from the free text and ask again. On Looks right or Skip review, carry on as in the sections above.
