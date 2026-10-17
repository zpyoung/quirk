# Design reference

Read this before filling a template's slots. It is the house design standard for every page this skill builds. A template's `rules.md` adds to it; see [templates](templates.md). Companion screens follow section 12 on top of the rest; see [companion](companion.md).

## 1. Scope and precedence

When two instructions disagree, the higher one wins:

1. The user's own words in this conversation.
2. The project's tokens and the chosen template's `rules.md`.
3. This reference.

Rules in this file are defaults, not laws. Break one only when a higher source asks for it, and say so in the delivery note.

Stay in Markdown, and do not build a page, when:

- the answer is under about 30 lines of prose with no table, chart, or interaction
- the reader will paste it into a ticket, a chat message, or a commit
- the user asked for a document or a file format (`.md`, `.docx`, `.pdf`), not a page

When an answer has shape (a comparison, a dashboard, a flow, a table someone will sort) and the user did not ask for a page, offer one in a single line and build only on a yes.

## 2. Direction brief

Write these three lines before opening a slot. Put them in your reply, not in the page.

```
Subject and audience: <what the page is about> for <who reads it and what they already know>
One job: <the single thing the reader should be able to do or decide after 60 seconds>
Specific detail: <one thing only this subject has: a real number, a unit, a name, a shape>
```

- The one job decides what goes above the fold. Everything that does not serve it moves lower, into `<details>`, or out. It also decides the page shape; see section 8.
- The specific detail becomes the page's one distinctive element: a unit-aware axis, a domain term as the heading, a real example in the lede. It replaces decoration.
- If you cannot fill the third line, you have not read the source material enough. Go back to it.

## 3. Banned tells

These are the marks of a default model-generated page. Each has a replacement. **Three or more tells on one page means rebuild it, not patch it.**

| Tell | Replace with |
|---|---|
| Inter as the face | the `--q-font-sans` system stack; for character, use weight and size contrast, not a webfont |
| Space Grotesk as the "fix" for Inter | the same system stack; a second default face is still a default |
| Purple or indigo gradients | one flat accent from `--q-color-accent`; no gradient on any surface |
| Gradient text | solid `--q-color-text`; emphasis through weight |
| Gray rounded card grids with shadows | a list, a table, or sections separated by a 1px `--q-color-border` rule |
| Full-bleed gradient hero | a plain header: h1, one-sentence lede, the summary |
| Emoji section headers | text headings; an inline SVG with `<title>` only if the icon carries meaning |
| Glassmorphism (blur, translucent panels) | opaque `--q-color-surface` |
| Everything centered | left-aligned text; center only a single short title or an empty state |
| Four-stat hero row on a page that is not a dashboard | state the one number that matters in a sentence; put the rest in a table |
| Decorative icon dividers | a `<hr>` or whitespace |
| One radius on every element | the radius scale in section 7: `sm` for controls, `md` for panels, `pill` for tags |
| Wide letter-spacing on uppercase eyebrows | sentence-case label, normal tracking, `--q-color-text-muted` |
| Fake "Live" or "New" pulse badges | omit; a real status uses text and a semantic color, with no animation |
| Thick colored left border on a rounded card | a callout with a full 1px border and an icon or label, or no box |
| `01 / 02 / 03` markers without a real sequence | an `<ol>` when the order matters; headings when it does not |

How to apply this:

- Check the finished page against the whole table, not only the rows you were thinking about.
- A tell is allowed when the user or a project template asks for it. Section 1 precedence applies.
- Do not swap a banned tell for a neighbor. Replacing one listed default with a near variant of it (a different gradient, a slightly rounder card) is the same tell.

## 4. Tokens

Use the `--q-*` variables. Never write a hex, `rgb()`, or `hsl()` color, a pixel font size, or a font stack in slot content when a token exists. The theme switches light and dark by redefining the variables, so a hard-coded color breaks one theme.

The house theme defines:

| Group | Variables |
|---|---|
| Color | `--q-color-bg`, `--q-color-surface`, `--q-color-text`, `--q-color-text-muted`, `--q-color-border`, `--q-color-accent`, `--q-color-accent-text`, `--q-color-good`, `--q-color-warn`, `--q-color-critical`, `--q-color-focus` |
| Font | `--q-font-sans`, `--q-font-mono`, `--q-font-display` |
| Size | `--q-size-body`, `--q-size-small`, `--q-size-h1`, `--q-size-h2`, `--q-size-h3`, `--q-size-h4` |
| Space | `--q-space-1` through `--q-space-8`, on a 4px base |
| Radius | `--q-radius-sm` (4px), `--q-radius-md` (6px), `--q-radius-pill` (999px) |

Rules for using them:

- Every color is a light/dark pair, so `var(--q-color-text)` is correct in both themes with no extra CSS.
- `--q-color-accent-text` is the text color to put on an accent-filled surface. Do not use `--q-color-text` there.
- Spacing comes from `--q-space-*`. Do not invent 13px or 22px gaps.
- Plain elements (`h1`, `p`, `table`, `button`, `input`, `details`) are already styled through Simple.css, mapped to these tokens by the theme. Write semantic HTML and add CSS only for what it lacks.
- A project or user token file can change any value. Because you reference the variables, the page follows without edits.
- The font tokens are system stacks. Do not add `@font-face`, a `url()` font, or a font `<link>`; external font references fail the offline static check, and system stacks cover every theme.
- Chart series colors are the `--q-color-chart-1` to `--q-color-chart-8` tokens. If you need another color the roles do not cover, define it once as a local custom property in the page's own `<style>` as a light/dark pair, using the same media-query structure the theme uses. Do not scatter literals.
- Code highlighting colors are the `--q-color-syntax-keyword`, `-string`, `-number`, `-comment` and `-name` tokens. `q-code` and `q-diff` apply them, so set them in a token file to rebrand code, not in the page.

## 5. Type

- Body text is 16 to 18px (`--q-size-body`), line-height 1.5 to 1.6.
- Prose fills its column. Do not cap it with `max-width`; the page's 1440px cap and the shape's columns set the line length.
- Use one scale ratio, 1.25 or 1.333, for headings. Use the `--q-size-h1` to `--q-size-h4` tokens and do not add a fifth heading size.
- `--q-size-small` is for captions, table footers, and metadata only. It is not a way to fit more text.
- Numbers in tables, stat readouts, and anything that updates: `font-variant-numeric: tabular-nums`.
- Headings are sentence case, weight 600 to 700, and carry the hierarchy. Do not make hierarchy with color alone.
- System font stacks only. `--q-font-display` is a system stack too; the theme applies it to `h1` through `h4`, so leave heading fonts to the theme and do not set it elsewhere.
- Code and identifiers use `--q-font-mono`. Do not set whole paragraphs in mono.
- Left-align prose. Justified text and centered paragraphs both hurt at narrow widths.

## 6. Color and themes

- Define 4 to 6 named roles and use only those. The house roles are bg, surface, text (with text-muted), border, and accent. That is the whole palette for chrome.
- Use one accent. It marks the primary action and the current selection. A second accent hue is a sign a semantic color is being misused.
- Semantic colors (`good`, `warn`, `critical`) are separate from the accent. Use them only for status. Never use `critical` for a button that is merely important.
- Contrast: 4.5:1 for text, 3:1 for large text (24px and up, or 18.66px bold), UI boundaries, icons, and focus rings.
- Check both themes separately. A pair that passes in light can fail in dark near the threshold (4.43:1 against 4.5:1 is a failure).
- Never carry meaning by color alone. Pair it with text, an icon with a `<title>`, a pattern, or position.
- Do not stack text on an image or gradient. If you must, put it on an opaque surface.
- Muted text (`--q-color-text-muted`) still needs 4.5:1 on its background. Do not lower its opacity further.
- The theme follows the OS and has a toggle in the chrome. Do not build a second toggle, and do not read `matchMedia` to restyle in JS; the CSS variables already switch. The only JS that needs the theme is canvas-drawn content, which listens for the `quirk-theme` event (section 9).

## 7. Shape and depth

- Radius scale: `sm` 4px for inputs, buttons, and code spans; `md` 6px for panels and callouts; `pill` for tags and badges only. Elements nested inside a rounded container get a smaller radius than the container.
- A card is a box with a border or surface fill. Use one only to separate content that would otherwise run together, or to group a repeatable item the reader scans (a flag, a run, an incident). A page of cards is a tell; see section 3.
- Do not put a card inside a card.
- At most one shadow level on the whole page, used only for things that float over content (a dialog, a menu, a tooltip). Flat surfaces get a 1px `--q-color-border`, not a shadow.
- Separate sections with spacing first (`--q-space-6` or larger), a 1px rule second, and a background change last.
- Borders are 1px. A 2px or thicker border is reserved for the focus ring.

## 8. Page shapes

Pick the shape from the direction brief, write it in the source header's `layout` field, and name it to the user before building. The build places the regions and one shared stylesheet (`theme/layout.css`) sets every width and breakpoint, so do not write grid or width CSS in a slot; the layout check fails it. Where the field and the slots go is in [templates](templates.md).

| Shape | Use when | Summary slot holds | At desktop width |
|---|---|---|---|
| `explainer` | findings with their evidence, or a how-it-works page or write-up | the answer or findings under the h1 | one column of prose with full-width figures, charts, tables and code |
| `longform` | long prose with notes on its phrases | the answer or findings under the h1 | prose fills the column; `q-sidenote` phrases are highlighted and open their note on hover |
| `tool` | a calculator, estimator or converter | the live result, in an `aria-live` region | inputs on the left, the result beside them from 900px, sticky |
| `comparison` | picking between options | the recommendation line: the pick and the one reason | `q-compare` with options as columns and criteria as rows |
| `dashboard` | status and metrics | the headline metric, top left, with its unit and comparison period | fluid width; a `q-grid` of titled `q-panel` items |
| `reference` | a runbook or reference read by section | a one-line purpose under the h1 | the section list as a left pane from 900px, content on the right |

Widths and breakpoints, measured on the viewport:

- **Width cap.** Page content is at most 1440px and centered, in every shape except `dashboard`, which is fluid. A `q-compare` may widen past 1440px when its options do not fit and nothing sits beside the column; next to a nav rail or pane it scrolls inside its own box instead.
- **Prose** fills its column in every shape, the summary included, as do tables, charts, graphs, code, diffs and boards.
- **Nav rail.** From 1100px the generated section nav is a sticky rail on the left that scrolls on its own when it is taller than the screen. Below 1100px it is a collapsed "On this page" menu ahead of `main`. It appears at 5 or more h2 sections, and always on `reference`, where it is the left pane from 900px and a collapsed "Sections" menu below that. A `"nav"` header field of `on` or `off` overrides the h2 count.
- **Tool.** From 900px the result sits beside the inputs. Below that it sits directly under them.
- **Notes.** A `q-sidenote` highlights its words at every width; the note opens below them on hover or keyboard focus, and a tap keeps it open.
- **Dashboard columns.** A `q-grid` is 1 column at 700px and below, 2 columns from 701px, 4 from 1100px and 6 from 1800px.
- **Comparison on a phone.** `q-compare` becomes one block per option at 700px and below, the recommended one first.
- **Phone.** At 375px every shape is one column in DOM order and does not scroll horizontally.
- **Print.** One column in DOM order: the nav as a plain list after the summary, notes inline, masthead controls hidden.

Notes that apply to every shape:

- The h1 names the subject, not the format. "Checkout latency, week 41", not "Report".
- Put the date or data source under the h1 in `--q-size-small`.
- Do not center the whole layout. The stylesheet centers the container; left-align its contents.
- Tables that are wider than the screen scroll inside their own `overflow-x: auto` wrapper, never the page.
- Sticky headers only when the page is longer than three screens. The sticky rail and result are the exception; each stays shorter than one screen or scrolls on its own.

## 9. Tables and data visualization

### Tables

- Every table has a `<caption>` that says what it is, `<th scope="col">` or `<th scope="row">` on every header, and a `<thead>`.
- Right-align numeric columns, left-align text, and use `tabular-nums` on both. Put the unit in the column header, not in each cell.
- Sortable columns use `<q-table>`, which adds the sort button and `aria-sort`; see [components](components.md).
- Zebra striping is optional. Never use it with row borders as well.
- Cap a table at 12 visible rows before offering search, a filter, or `<details>` for the rest.

### Choosing a chart

| Question | Chart |
|---|---|
| How do values compare across categories | horizontal bar, sorted by value |
| How does a value change over time | line, with at most 5 lines |
| What share of a whole | a single stacked bar, or a table; a pie only for 2 to 3 slices |
| How are two measures related | scatter |
| How is a measure distributed | histogram |
| Exact values matter more than shape | a table, no chart |

### Drawing it

- Label directly: put the series name at the end of its line or on its bar. Use a legend only when direct labels collide.
- Bars start at zero. Lines may start elsewhere but the axis must say so.
- No dual axes. Two measures with different units get two charts stacked on a shared x axis.
- No 3D, no gradient fills, no drop shadows, no animated entry that delays reading the value.
- Categorical series: 5 to 8 at most, using the `--q-color-chart-1` to `--q-color-chart-8` tokens (an Okabe-Ito palette, tuned per theme to pass 3:1 against the chart background).
- Sequential data (a heatmap, a density): one hue, light to dark, with the scale shown. Diverging data needs a meaningful midpoint.
- More than 8 series means the chart is wrong. Group the tail into "Other", filter, or use a table.

### Chart.js

Bar, line and area charts use `<q-chart>` and sortable tables use `<q-table>`; the elements supply the accessible label, the table view and the theme rebuild. Attributes and examples are in [components](components.md).

Scatter and histogram charts stay hand-written Chart.js, so they need these by hand:

- A `<canvas>` with `role="img"` and an `aria-label` that states the finding, in a fixed-height wrapper (`maintainAspectRatio: false`, `animation: false`), followed by a table view: a `<details>` holding the same data as a real table.
- Colors read from the page's custom properties with `getComputedStyle`, and the chart rebuilt on the `quirk-theme` event (fired on `document`, `detail: {mode, effective}`). Re-read the properties inside the handler.
- When it reads data through `window.quirkData()`, `window.quirkData.onChange(callback)` re-renders it after the viewer picks a different file.

### Diagrams and graphs

- Reach for `<q-flow>` when the reader will explore a graph: follow an upstream and downstream path through a system, open a node to read its detail, or focus one subsystem group. Reach for Mermaid when a static picture does the job, for sequence diagrams and state charts, and inside Markdown documents.
- Never write coordinates in `<q-flow>`; pass `kinds`, `groups`, `nodes` and `edges` as JSON data and let the element lay the graph out and build its "Graph as a list" disclosure.
- Reuse the same `kinds` names and `--q-color-chart-*` numbers (1 to 8) across artifacts (for example `ui`: 1, `worker`: 2, `database`: 3, `queue`: 4) so node categories keep the same color from page to page.
## 10. Interaction and motion

- Every interaction you build is declared in the source file's `interactions` list, because verify and the delivery note refer to it.
- Prefer native behavior: `<details>`, `<dialog>`, form controls, `:target`, CSS `:has()`. Reach for Alpine only for state those cannot hold.
- Build your own element when the content needs one that neither native HTML nor [components](components.md) has, such as a step-through of an algorithm or a clickable state diagram. Do not bend a kit element into a job it was not made for. Your element must follow these rules:
  - Its name does not start with `q-`. That prefix belongs to the kit, and the kit check fails any `q-` tag it does not know.
  - Colors, spacing, type and radii come from the `--q-*` tokens, so it switches with the theme.
  - It renders in the light DOM. The static checks read the page's HTML, and they cannot see inside a shadow root.
  - It lays out its own contents, not the page. Grid is allowed on the element and inside it: in a rule whose selector ends on the element or reaches into it with a descendant or child combinator, or in a `style=""` on the element or anything inside it. Floats, columns and any width of 400px or 25rem or more still fail the layout check there. A name starting with `q-` or `wa-` belongs to a library and gets no grid exemption. Put the element in a `q-grid` or `q-panel` to sit it beside other content.
  - Its script and styles are inline in the source, like everything else on an offline page.
  - It meets section 11, and anything it lets the reader do goes in the `interactions` list.
- A readout that changes because of an input updates in place and is announced; see section 11.
- At most one orchestrated moment per page: a single entrance for the summary, or one transition when a view changes. No scroll-jacking, parallax, staggered card reveals, or ambient looping animation. The one exception is `<q-flow>`'s traveling pulse along a focused node's path, which loops only while a node is focused and stops as soon as focus clears.
- Motion lasts 150 to 250ms, uses `ease-out`, and animates only `opacity` and `transform` (plus `<q-flow>`'s SVG pulse mask while a node is focused).
- Wrap all motion in `@media (prefers-reduced-motion: no-preference)`, so the default is none. Do not animate on reduced motion; `<q-flow>` shows a thicker static line with arrowheads instead.
- Hover is never the only way to reach something. Touch and keyboard users get the same content.
- Controls show a state for hover, focus, active, and disabled. A disabled control says why nearby.
- State that matters (a filter, a selected tab) is reflected in the URL hash only if the user will share the page; otherwise keep it in memory.

## 11. Accessibility floor

A page that misses any item here is not finished.

- [ ] Exactly one `<h1>`; headings descend without skipping a level
- [ ] Landmarks: one `<main>`, a `<header>`, and `<nav>` if there is navigation; the template chrome supplies what it can, and you check the rest
- [ ] Every control has an accessible name (visible `<label>`, `aria-label`, or its text)
- [ ] Buttons are `<button>`, navigation is `<a href>`; no `div` or `span` with a click handler
- [ ] Visible focus on every interactive element: 2px outline, 2px offset, `--q-color-focus`, 3:1 against the background. Never `outline: none` without a replacement
- [ ] Meaning never depends on color alone
- [ ] Inline SVG that conveys information has `role="img"` and a `<title>`; decorative SVG has `aria-hidden="true"`
- [ ] Charts follow section 9; every chart has a table view
- [ ] Readouts that change from user input sit in an element with `aria-live="polite"`
- [ ] Collapsible content uses `<details>` and `<summary>`, not a custom toggle
- [ ] Touch targets are at least 44px tall at 375px
- [ ] `<html lang>` is set and link text makes sense out of context ("Read the run log", not "here")
- [ ] The page reads in the order it is written: tab order and DOM order match, with no positive `tabindex`
- [ ] Zoom to 200% does not clip or overlap content

## 12. Companion page kit

Companion screens are questions, not documents. Build them from the `companion` template through `screen.json`; the protocol is in [companion](companion.md).

- **State the question as the header.** The `question` field is a complete question in sentence case: "Which layout fits the dashboard?". The `title` is two or three words.
- **Offer 2 to 4 options.** One option is not a question and five or more is a survey. A screen that only shows something still offers choices about it ("Looks right", "Change the spacing", "Start over").
- **Each option has a short label and a one-line description.** The description says the consequence, not the feature.
- **Pick the fidelity the question needs.** Use a wireframe (boxes, labels, `--q-color-border`, no color) for layout, flow, and structure questions. Use a polished mockup (real tokens, real type, real copy) only for questions about look: color, density, typography. Never polish a question about structure.
- **One new screen per question.** Do not reuse a screen for a second question and do not stack two questions on one screen. Every `show` makes a new file and supersedes the last.
- Put mockups in an option's `html` or in `content`. Keep them under about 60 lines; if a mockup needs more, the question is two questions.
- Set `select` to `single` for a choice and `multi` for a "which of these apply". Never use `multi` when you will pick one yourself afterward.
- Use `diagram` (Mermaid) for flows and relationships, and a wireframe for anything spatial.
- Everything in sections 3 to 7 and 11 still applies to the screen.

## 13. Copy rules

- Sentence case everywhere: headings, buttons, table headers, tabs. Capitalize proper nouns only.
- Name buttons by their action: "Save changes", "Export CSV", "Run comparison". Not "Submit", "OK", or "Click here".
- Specific over clever. "Median checkout latency fell 22% after the cache change" beats "Faster than ever".
- Numbers carry units and a comparison: "412 ms, down from 530 ms in week 40".
- Write the lede as the conclusion, then the evidence.
- No filler openers ("In today's fast-paced world"), no marketing adjectives (seamless, robust, powerful), no exclamation marks.
- Empty states say what is missing and what to do next. Error messages say what happened and how to fix it, next to the field.
- Use the reader's terms from the source material. Do not rename the user's domain.
- Dates are absolute ("13 Oct 2026"), not "yesterday"; numbers over 9,999 get thousands separators.

## 14. Verify checklist

Run these on the final file, in this order. Any edit after verify means run verify again. Script paths are relative to the skill directory.

### What the tools check

`scripts/quirk_html.py check FILE` (static, runs on every build):

- [ ] `header`: the `quirk-html-artifact` header is present and complete
- [ ] `license`: every inlined library has a license comment
- [ ] `checksum`: every library block matches its recorded hash
- [ ] `external-refs`: no external scripts, styles, fonts, images or fetches in offline mode
- [ ] `size`: under 2 MB (warning) and 10 MB (failure)

`scripts/quirk_html.py verify FILE` (browser, when one is reachable):

- [ ] `console`: no `console.error` and no uncaught page error in any run
- [ ] `viewports`: screenshots at 375x800 and 1280x800, in light and dark; at 375px the page does not scroll horizontally
- [ ] `themes`: sampled text reaches 4.5:1 (3:1 at 24px and up) in both themes
- [ ] `network`: zero requests in offline mode

`scripts/quirk_html.py note FILE` builds the delivery note and reports `verify_stale: true` when the file changed after verify. If it is true, run verify again.

### What the tools cannot check

Open each screenshot yourself. Verify proves the page loads and is legible; it does not prove it is good.

- [ ] The direction brief's one job is clear in the first screen at 1280px and at 375px
- [ ] No three tells from section 3 are present
- [ ] Hierarchy reads without color: squint and the h1, the summary, and the sections still stand out
- [ ] Charts show the finding, labels are not clipped, and every chart has a table view
- [ ] Every control in the `interactions` list works when you use it, not only when the page loads
- [ ] Copy follows section 13; no placeholder text, no lorem ipsum, no invented numbers
- [ ] Focus is visible and the tab order matches the reading order
- [ ] Both themes look intentional, not merely legible
- [ ] The delivery note's claims (size, libraries, mode, verify result) match what you saw

If verify returns `not-browser-verified`, say so in the note and list the static checks that passed. Do not install a browser to get around it.
