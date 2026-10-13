# Report template rules

Read after the [design reference](../../references/design-reference.md). These rules add to it for pages built from `report`.

## Layout

- The skeleton gives you the page: a masthead with the theme toggle and the `<h1>` (from `title`), then `<main>` in a 960px column. Do not write an `<h1>` or a second theme toggle in a slot.
- `main` holds the body. Open with one paragraph that states the conclusion (`class="q-lede"`), then a line for the data source or date (`class="q-meta"`), then a "Findings" section of 3 to 5 one-sentence facts, then the evidence.
- Wrap each section in `<section aria-labelledby="...">` with an `<h2>`. Sections are separated by spacing, not boxes.
- `aside` is optional. When you use it, the slot content is the whole element: `<aside aria-label="About these numbers">`. At 900px and up it sits right of `main`; below that it follows `main`. Use it for definitions and caveats, not for navigation.
- Prose is capped at 70ch by the skeleton. Tables and charts fill the column.

## Helper classes the skeleton defines

| Class | Use |
|---|---|
| `q-lede` | the opening conclusion paragraph |
| `q-meta` | source and date line, small and muted |
| `q-chart` | fixed-height wrapper around a chart `<canvas>` or Mermaid diagram |
| `q-table-wrap` | wrapper that scrolls a wide table inside itself, never the page |
| `num` (on `th`, `td`) | right-aligned tabular numbers |
| `q-sort` | the `<button>` inside a sortable column header; pair it with `aria-sort` on the `<th>` |

## Charts

- Every chart `<canvas>` has `role="img"` and an `aria-label` that states the finding, not the chart type.
- Every chart is followed by a table view: a `<details>` with a `<summary>` and a real `<table>` (with `<caption>`, `<thead>`, `<th scope>`) holding the same numbers.
- Put the canvas in a `q-chart` wrapper and set `maintainAspectRatio: false` and `animation: false`.
- Read colors with `getComputedStyle(document.documentElement).getPropertyValue('--q-color-accent')` and rebuild the chart in a `quirk-theme` listener on `document`. The event's detail is `{mode, effective}`.
- Mermaid diagrams go in a `q-chart` wrapper with a text description beside them.

## Scripts and data

- Slot scripts run before the library scripts, and Alpine starts before `chrome.js` defines `window.quirkData`. Register components with `document.addEventListener('alpine:init', ...)` and call `quirkData()` and draw charts once the window `load` event has fired.
- Read data only through `window.quirkData()`. Use the source header's `data` field to embed it; do not paste data into a script.
- Declare every interaction you build in the source header's `interactions` list.
- No `fetch`, `XMLHttpRequest`, `WebSocket` or `EventSource` in offline mode.
