# Logic spec: the `writing-html-artifacts` component kit

**Status**: Draft, 2026-10-14

A kit of eight custom elements (`q-tabs`, `q-chart`, `q-stat`, `q-table`, `q-timeline`, `q-code`,
`q-diff`, `q-board`) that agents drop into pages built by `writing-html-artifacts`. Today the
template rules make the agent hand-wire every chart (aria-label, table view, theme colors, rebuild on
theme change, sizing) and every sortable table (Alpine `sortBy` and `ariaSort` code). The kit moves
that wiring into elements, so the agent writes plain HTML with a q-* wrapper and the page gets the
behavior right by construction.

Derived from the research summary in this session (agent-UI catalogs, Reddit and HN practitioner
threads, and web-component design for LLM authors) and from the built skill at
`skills/writing-html-artifacts/`, specified in
[the writing-html-artifacts logic spec](../2026-10-13-writing-html-artifacts/logic.md).

## Conceptual model

The kit is a first-party library inside `writing-html-artifacts`. It has three parts that share one
source of truth:

- **The catalog** has one entry per element: its tag, a one-line "Use when" description, its
  attributes (required or optional, allowed values), the child structure it expects, and a short
  example.
- **`kit.js` and `kit.css`** hold the eight light-DOM custom elements and their styles. They depend on
  nothing except Chart.js, which only `q-chart` uses.
- **Three readers of the catalog**: the build's `kit` static check, the generated components
  reference the agent reads, and the per-element example pages.

Every element enhances HTML the agent already wrote. It adds behavior and presentation and never
hides content it cannot rebuild. When the script does not run, the reader sees a styled table, stacked
sections, a list, or a `<pre>`.

The kit complements Web Awesome; it does not replace it. Web Awesome keeps form controls, dialogs and
menus in the `components` template. The kit covers data and display, plus tabs, so a `report` page
can have tabs without loading Web Awesome.

## Data flow

1. **Authoring.** The agent writes `<slug>.src.html` using q-* tags, guided by the generated
   components reference.
2. **Inclusion.** At build time the source text is scanned. If `<q-` appears anywhere, including
   inside script strings, the whole kit is inlined, whatever the template's `optional_libraries`
   say. If `<q-chart` appears, Chart.js is inlined too. The kit has a version in `libraries.json` like
   the vendored libraries, so a rebuild keeps the version recorded in the page header unless
   `--upgrade` is passed.
3. **Static check.** A new `kit` check reads the catalog and fails the build (exit 1) on any of these:
   - an unknown q-* tag
   - a missing required attribute
   - an attribute value outside its allowed set
   - a missing required child, such as a `q-chart` with neither a `<table>` nor `data-from`, or a
     `q-stat` without its definition line
   - an inline chart table with more than 8 series
   - a `q-diff-note` pointing at a file or line not present in its diff
4. **In the reader's browser.** The kit script runs at the end of `<body>`. Each element upgrades in
   place. Data elements read their child table, or wait for `quirkData()` and re-render on
   `quirkData.onChange`. Theme-sensitive elements re-render on the `quirk-theme` event. `q-chart`
   merges any raw options first and applies its guarantees last.
5. **Tier 2 and the companion.** The React app template ships the same kit and uses the elements in
   JSX. The companion page inlines the kit so a screen can show q-* elements. Both run the same
   catalog check.

## Key decisions and rationale

- **Light DOM, plain custom elements.** Page CSS written by the agent reaches the elements directly,
  and the wrapped HTML stays readable without JS. Shadow DOM would force `::part` theming. Lit was
  rejected because its first render replaces the host's children, which breaks wrapping real HTML,
  and its docs discourage light-DOM rendering.
- **One file, inlined whole.** Per-element inclusion would save little, since Chart.js (about 200 KB)
  dwarfs the kit, and it brings documented failure modes: tags created in JS go undetected,
  dependencies between elements must be declared, and definition order matters. A text scan for
  `<q-` errs toward including the kit.
- **The catalog drives docs and checks.** The agent's reference and the static check read the same
  entries, so they cannot drift. This follows json-render and A2UI, which generate the agent's prompt
  from a constrained catalog.
- **Scalar attributes for configuration, child HTML for data.** LLMs mis-escape JSON inside
  attributes. The one JSON surface is the `q-chart` raw-options block in a child
  `<script type="application/json">`, where escaping is ordinary.
- **The kit's guarantees beat raw options.** Theme colors, the aria-label, the table view, sizing and
  disabled animation always apply, so the escape hatch cannot break dark mode or accessibility.
- **`q-chart` drives the vendored Chart.js.** It reuses a pinned, verified library and removes the
  most hand-wiring. A small SVG sparkline serves `q-stat`, which does not need Chart.js.
- **Fail at build time.** Misuse is a static-check failure the agent sees and fixes, like the
  existing header and size checks. It is not a runtime error box for the reader to find.
- **`q-stat` requires a definition line.** The research found dashboards showing misleading
  percentages because the period and denominator were missing.
- **The board saves to localStorage and says so.** The user chose persistence across reloads. The
  visible "Saved in this browser only" line keeps readers from mistaking it for shared state.

## Behavior

### Shared behavior

- Every element uses the `--q-*` tokens, follows light and dark themes including the `wa-dark` class
  sync, fits a 360px-wide viewport without page-level horizontal scroll, and prints sensibly.
- The kit's elements need no Alpine. Pages may still use Alpine around them.
- Pages that hand-write Chart.js, Alpine or `wa-*` without q-* tags build exactly as before.

### `q-tabs`

- Wraps `<section>`s that each open with a heading. The headings become the tab labels.
- Follows the APG tabs pattern: arrow keys, Home and End, `aria-selected`, focusable panels.
- Printing shows every panel. Without JS the sections stack.

### `q-chart`

- Draws a bar, line, area or donut chart from its child `<table>`, or from `data-from` bound to a
  `quirkData()` field. Attributes choose the type, the x column, the y columns, stacked and
  horizontal.
- A required `summary` attribute states the finding and becomes the aria-label.
- The source table moves into a "Table view" `<details>` below the chart. Bound data renders that
  table too.
- Colors come from the Okabe-Ito tokens. Long category labels wrap or truncate, with the full text in
  the tooltip.
- Raw Chart.js options go in a child `<script type="application/json">` and are merged before the
  guarantees.
- Bound data with more than 8 series shows the table instead of a chart, with a note saying why.

### `q-stat`

- Shows a label, a value, a signed delta, and a required definition line (period and denominator).
- `direction="up-good"` or `"down-good"` decides whether a rise is colored good or bad.
- Optional `points` draw an SVG sparkline, hidden from assistive tech because the delta and
  definition carry the meaning in text.
- Adjacent `q-stat` elements form a responsive row.

### `q-table`

- Wraps a real `<table>`. Each column header becomes a sort `<button>` with `aria-sort`. Columns
  marked `num` sort numerically.
- Past 12 rows a filter box appears, with an "n of m rows" readout.
- The header row is sticky. The table scrolls sideways inside its own wrapper, never the page.
- With `data-from`, it builds the rows from `quirkData()`.

### `q-timeline`

- Wraps an `<ol>` whose items each hold a `<time datetime>`, and draws a rail with markers.
- Each item may carry a tone: neutral, success, warning or danger.

### `q-code`

- Wraps `<pre><code>` and adds a copy button and an optional filename label.
- When the clipboard is blocked, it selects the text and tells the reader to copy it by hand.
- No syntax highlighting.

### `q-diff`

- Wraps a `<pre>` holding unified diff text and renders file headers, added and removed lines, and
  line numbers.
- `q-diff-note` children with `file` and `line` attributes appear under that line.
- Without JS the raw diff shows, followed by the notes as a list.

### `q-board`

- Wraps column `<section>`s, each with a heading and a `<ul>` of cards. An `id` is required.
- Cards move by pointer drag (mouse and touch), by Alt plus arrow keys, and by a "Move to…" control on
  each card. The keyboard and control paths are the non-drag alternative WCAG 2.5.7 requires.
- The layout is saved to localStorage under the page slug and board id. A visible line reads "Saved
  in this browser only."
- "Reset" restores the authored layout. "Copy as Markdown" exports the current one.
- When a rebuild changes the authored cards, a saved layout that no longer matches is discarded and
  the authored layout shows.

### Scenarios

- **A report with KPIs and a trend.** The agent writes three `q-stat`s and a `q-chart` around a small
  table. The build inlines the kit and Chart.js. The reader sees cards and a chart that switch theme
  together, and can open the table view.
- **A chart from a data file.** The header names `timings.csv`. A `q-chart data-from="timings"`
  renders after `quirkData()` resolves, and redraws when the reader picks a different file.
- **A misspelled tag.** The agent writes `<q-stats>`. The build fails the `kit` check naming the tag
  and the line, and the agent fixes the source.
- **Raw options that fight the theme.** The agent's JSON block sets a hard-coded grid color. The
  chart uses the theme color anyway, because the guarantees apply last.
- **A triage board.** The reader drags two cards, reloads, and sees them where they left them. They
  copy the board as Markdown and paste it to an agent.
- **No JS.** The kit script is stripped or fails. Every example still reads as tables, sections,
  lists and preformatted text.

## Scope and non-goals

**In scope**

- The eight elements and `q-diff-note`, the catalog, `kit.js`, `kit.css`, and the `kit` check.
- Automatic inclusion, with Chart.js added for `q-chart`, and the kit pinned in `libraries.json`.
- A generated `references/components.md`, linked from `SKILL.md` and both templates' `rules.md`.
- Removing from the `report` and `components` rules files, and from design reference section 9, the
  hand-wiring rules the kit now owns. Section 9 keeps its chart-choice and drawing rules and points
  to `q-chart`.
- Tier-2 app template and companion integration.

**Non-goals**

- Replacing Web Awesome form controls, dialogs or menus.
- Shadow DOM, Alpine coupling, per-element inclusion, or a size budget beyond the existing 2 MB
  warning.
- Syntax highlighting in `q-code`.
- Shared or server-side board state.
- Scatter and histogram charts, which stay hand-written Chart.js.
- A filter bar driving several elements, Gantt charts, carousels and date pickers.

**Done means**

- Each element has an example page that passes build and browser verify, in light and dark, at phone
  width.
- Each example still reads correctly with the kit script removed.
- The `report` and `components` rules files no longer carry the hand-wiring rules the kit owns.

## Decisions Locked

**Meaning and process**

- "Share components" means a shared component kit for every template.
- Standard gray areas only; adhd not run.

**Relationship to Web Awesome**

- The kit complements Web Awesome; it does not replace or wrap it.
- The kit ships its own light-DOM `q-tabs`.
- `q-chart` drives the vendored Chart.js, plus an own-SVG sparkline.
- Kit elements are plain custom elements with no Alpine dependency.

**Authoring shape**

- Data comes from a child table or a `quirkData()` binding.
- Before upgrade, the wrapped HTML shows, styled.
- Configuration is scalar attributes plus a raw-options JSON escape hatch on `q-chart`.
- Unknown tags and bad attributes fail the build's static check.

**First set**

- Ship all of `q-chart`, `q-stat`, `q-table`, `q-timeline`, `q-code`, `q-diff`, `q-board`, with
  `q-tabs`.
- The kit's guarantees win over raw options.
- `q-table` adds sort, a filter box and a sticky header.
- `q-stat` requires a definition line.

**Templates and integration**

- The kit is included automatically when the source uses a q-* tag.
- Tier 2 uses the kit.
- Companion screens can use kit elements.
- Board moves are saved in localStorage.
- Diff annotations are child note elements pointing at a file and line.

**Success and docs**

- Success: example pages pass verify in both themes at phone width, read correctly without the
  script, and the rules files shrink.
- No fixed size budget.
- The components reference is generated from the catalog.

**Approach**

- One hand-written vanilla file, inlined whole when any q-* tag appears.

## Industry Insights

- Agent-UI catalogs agree on a small core: buttons, inputs, tabs, dialogs, cards and badges appear
  in nearly all of them. Charts and tables appear in the dashboard libraries. No catalog ships a
  timeline, diff or kanban, though Claude Code's artifact docs list all three as common builds.
  ([A2UI](https://a2ui.org/specification/v0.9-a2ui/),
  [json-render](https://json-render.dev/docs/api/shadcn),
  [Claude Code artifacts](https://code.claude.com/docs/en/artifacts))
- Constrained catalogs that generate the agent's prompt are the dominant pattern for reliable
  generated UI. ([json-render](https://json-render.dev/docs),
  [A2UI catalogs](https://a2ui.org/concepts/catalogs/))
- Tremor's chart shape (`data`, `index`, `categories`) and Charts.css's table-as-data both keep
  chart input simple; the table form also degrades to readable markup.
  ([Tremor](https://www.tremor.so/docs/visualizations/bar-chart),
  [Charts.css](https://chartscss.org/docs/usage/))
- HTML web components should wrap real HTML; an empty custom element is meaningless without JS.
  ([Jim Nielsen](https://blog.jim-nielsen.com/2023/html-web-components/),
  [Jeremy Keith](https://adactio.com/journal/20618))
- LLMs mis-escape quotes in JSON strings, which argues against JSON in attributes.
  ([OpenAI forum](https://community.openai.com/t/how-do-i-ensure-that-json-mode-properly-escapes-quotation-marks/619138))
- Light-DOM vanilla custom elements test easily with ordinary DOM queries. Cloud Four moved most
  components from Lit to vanilla light DOM.
  ([Cloud Four](https://cloudfour.com/thinks/testing-html-light-dom-web-components-easier-than-expected/))
- Lit replaces a host's existing children on first render and its docs call light-DOM rendering
  "generally not recommended." ([lit-html #736](https://github.com/Polymer/lit-html/issues/736),
  [Lit shadow DOM docs](https://lit.dev/docs/components/shadow-dom/))
- Usage-based inclusion misses tags in shadow roots and JS-built markup, and needs hand-declared
  dependencies. ([Shoelace #1857](https://github.com/shoelace-style/shoelace/discussions/1857),
  [11ty WebC](https://www.11ty.dev/docs/languages/webc/))
- `customElements.define` throws on a duplicate name, so every define needs a guard.
  ([Spectrum registry conflicts](https://opensource.adobe.com/spectrum-web-components/registry-conflicts/))
- Chart.js must destroy the previous instance before redrawing on the same canvas.
  ([geneshki](https://geneshki.com/how-i-made-chart-js-sane-by-wrapping-it-in-a-web-component/))
- Drag interactions need a single-pointer, non-drag alternative, and the APG rearrangeable listbox
  shows a keyboard pattern. Native HTML5 drag does not start from touch, so pointer events are the
  safer base. ([WCAG 2.5.7](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html),
  [APG listbox](https://www.w3.org/WAI/ARIA/apg/patterns/listbox/examples/listbox-rearrangeable/))
- The strongest practitioner complaint about AI-built dashboards is inconsistent, "vibe coded"
  styling, followed by chart labels overflowing and wrong sizing.
  ([r/ClaudeAI dashboard thread](https://www.reddit.com/r/ClaudeAI/comments/1wxnkuc/i_used_claude_to_build_a_dashboard_that/),
  [r/ClaudeAI chart help](https://www.reddit.com/r/ClaudeAI/comments/1wb7q6r/chart_help/))
- A dashboard showing +11.9% when the real figure was +265% motivates the required definition line on
  `q-stat`. Single source.
  ([r/vibecoding](https://www.reddit.com/r/vibecoding/comments/1wopz01/my_app_store_dashboard_said_119_the_real_number/))
- Reddit coverage was thin: search could not reach reddit.com directly and a mirror failed on about
  half the queries. No source compared LLM error rates across attributes, JSON and child HTML.

## Deferred Ideas

- An agent eval building the same prompts with and without the kit, compared on check failures and
  verify results.
- A filter bar that drives several elements at once.
- Syntax highlighting for `q-code`.
- Scatter and histogram support in `q-chart`.
- `[tech-spec]` How verify proves the no-JS fallback, for example a render with the kit script
  stripped.
- `[tech-spec]` How the tier-2 template gets the kit: copied into the project or referenced from the
  skill.
- `[tech-spec]` How the companion's `screen.json` carries kit markup and how the companion runs the
  catalog check.
- `[tech-spec]` The catalog's file format and how the components reference is generated from it.
- `[tech-spec]` The exact attribute names for each element.

## Glossary

- **Kit**: the eight q-* elements, `q-diff-note`, their stylesheet, and the catalog.
- **Catalog**: the single list of kit elements with their descriptions, attributes, child rules and
  examples. The check, the reference and the examples read it.
- **Guarantees**: the `q-chart` settings raw options cannot override: theme colors, aria-label, table
  view, sizing and disabled animation.
- **Upgrade**: the moment a kit element's script runs and enhances the HTML it wraps.
- **Wrapped HTML**: the plain markup inside a kit element that the reader sees before upgrade or
  without JS.
- **Definition line**: the text on a `q-stat` stating the period and denominator of its value.
- **`kit` check**: the static check that validates q-* usage against the catalog at build time.

## Status & amendments

**Status**: Draft, 2026-10-14. Awaiting user review.

**Amendments**

None yet.
