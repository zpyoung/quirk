# Report template rules

Read after the [design reference](../../references/design-reference.md). These rules add to it for pages built from `report`.

## Layout

- The skeleton gives you the page: a masthead with the theme toggle and the `<h1>` (from `title`), then the page shape you named. Do not write an `<h1>` or a second theme toggle in a slot.
- Name the shape in the header's `layout` field. All six work in this template; the one-per-shape examples are in `examples/<shape>.src.html`, and widths and breakpoints are in section 8 of the design reference.
- **`summary` is required.** Write a `<!-- slot: summary -->` slot that holds what the shape's summary is (the table in the [design reference](../../references/design-reference.md) section 8). For `explainer` that is the conclusion paragraph (`class="q-lede"`). It is the first thing after the `<h1>`; do not repeat it as the first paragraph of `main`.
- `main` holds the body. Open with a line for the data source or date (`class="q-meta"`), then a "Findings" section of 3 to 5 one-sentence facts, then the evidence. Other shapes follow their own examples.
- Do not write grid or fixed-width CSS in a slot. Use `q-grid`, `q-panel`, `q-sidenote` or `q-compare` from [components](../../references/components.md); the layout check fails hand-written layout CSS.
- The section nav is generated. Do not write a table of contents.
- Wrap each section in `<section aria-labelledby="...">` with an `<h2>`. Sections are separated by spacing, not boxes.
- Put definitions and caveats, such as how the numbers were counted, in a last section of `main`. No shape has a side column for them.
- Prose, tables, charts, code, diffs and boards fill the column.

## Helper classes the skeleton defines

| Class | Use |
|---|---|
| `q-lede` | the opening conclusion paragraph |
| `q-meta` | source and date line, small and muted |
| `q-chart` | fixed-height wrapper around a Mermaid diagram (Chart.js charts use the `<q-chart>` element) |
| `q-table-wrap` | wrapper that scrolls a wide table inside itself, never the page |
| `num` (on `th`, `td`) | right-aligned tabular numbers |

## Charts and tables

- Bar, line and area charts use `<q-chart>`, sortable tables use `<q-table>`, and explorable graphs of services, pipelines or data flows use `<q-flow>`. Attributes and examples are in [components](../../references/components.md); the element supplies the accessible label, the fallback view and the theme rebuild. Reuse the same `kinds` names and `--q-color-chart-*` numbers across artifacts.
- `<q-flow>` is the tool for every flowchart on an HTML page, including decisions (`shape: "decision"`), retries (`loop: true`) and steps that are their own process (`shape: "subprocess"`, optional `flow`). Mermaid diagrams go in a `q-chart` wrapper with a text description beside them; use Mermaid for state charts and sequence and ER diagrams.
- Scatter and histogram charts stay hand-written Chart.js, under section 9 of the design reference.

## Scripts and data

- Slot scripts run before the library scripts, and Alpine starts before `chrome.js` defines `window.quirkData`. Register components with `document.addEventListener('alpine:init', ...)` and call `quirkData()` and draw charts once the window `load` event has fired.
- Read data only through `window.quirkData()`. Use the source header's `data` field to embed it; do not paste data into a script.
- Declare every interaction you build in the source header's `interactions` list.
- No `fetch`, `XMLHttpRequest`, `WebSocket` or `EventSource` in offline mode.
