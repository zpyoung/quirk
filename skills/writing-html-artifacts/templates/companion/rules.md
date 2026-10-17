# Companion template rules

Read after section 12 of the [design reference](../../references/design-reference.md) and the [companion guide](../../references/companion.md). You do not write this template's slots by hand: `scripts/companion.py show` fills them from `screen.json`, so these rules say what to put in that file.

## What the skeleton gives you

- A masthead with the theme toggle and the `title` as a small `<h1>`, then the `question` as the page's `<h2>`.
- `content`, then the option cards, then a note field and the Proceed button. Do not add your own buttons, links to other screens or a second note field.
- A "superseded" banner that appears when a newer screen replaces this one. Controls lock themselves.
- All behavior comes from the inlined `companion.js`. A screen with its own `<script>` that calls `fetch` fails the static check.

## Page shape

- `layout` is an optional `screen.json` key, one of the six shapes (`explainer`, `longform`, `tool`, `comparison`, `dashboard`, `reference`). `show` validates it and exits 2 on any other value.
- Naming one widens the screen from 960px to 1440px, and `dashboard` to fluid. A screen with no `layout` stays at 960px. Name one only when the question needs the room; most screens do not.
- Screens have no `summary` slot: the `question` is the summary. The layout check does not run on screens, because `content` and option `html` draw mockups of other layouts.
- One example screen per shape is in `examples/<shape>.screen.json`. The key's details are in the [companion guide](../../references/companion.md#screen-width-and-layout).

## Writing `screen.json`

- `question` is one complete sentence in sentence case. `title` is two or three words.
- `options` holds 2 to 4 entries. `id` matches `[a-z0-9-]{1,40}` and is unique on the screen; the agent reads it back, so make it meaningful (`two-col`, not `a`).
- `description` is one line that says the consequence of choosing the option.
- `select` is `single` for a choice (radio cards) and `multi` for "which of these apply" (toggle cards).

## Mockups

- Option `html` and `content` are static markup, shown as-is. Kit elements (`q-*`) go in `content` or in an option's `html` exactly as written. No `<button>`, `<a>`, `<input>` or `<form>` in an option's `html`: it sits inside the option's own button, and nested controls break the card. For the same reason, only kit elements whose entry in [components](../../references/components.md) says "Companion option html: allowed" (the non-interactive ones) may appear in an option's `html`; interactive ones go in `content`. This is a rule, not a check.
- Style mockups with inline `style` and the `--q-*` custom properties so they follow the light and dark theme. No external images, fonts or stylesheets; offline rules apply, and `show` rejects any `http:`, `https:` or `//` load.
- Wireframes (boxes and labels in `--q-color-border`) for structure questions; real tokens and copy only for questions about look.
- Keep a mockup under about 60 lines. An option's `html` is a thumbnail, so give it a fixed height (around 72px); put larger comparisons in `content`.

## Diagrams

- `diagram` is Mermaid source for a static diagram. The screen loads Mermaid from the companion server at `/_quirk/lib/mermaid/<version>/mermaid.min.js`; it is never inlined, so a diagram screen stays small.
- The diagram renders above the options and follows the light and dark theme. Keep it to what the question needs: one flow or one relationship map. When the user needs to pan, zoom or click through a graph on the screen, put `<q-flow>` or `<q-schema>` in `content` instead (never in an option's `html`, because both are interactive).
