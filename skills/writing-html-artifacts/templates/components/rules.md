# Components template rules

Read after the [design reference](../../references/design-reference.md). These rules add to it for pages built from `components`, which loads Web Awesome and Alpine.

## Layout

- The skeleton gives you the page: a masthead with the theme toggle and the `<h1>` (from `title`), then the page shape you named. Do not write an `<h1>` or a second theme toggle in a slot.
- Name the shape in the header's `layout` field. All six work in this template; the one-per-shape examples are in `examples/<shape>.src.html`, and widths and breakpoints are in section 8 of the [design reference](../../references/design-reference.md).
- **`summary` is required.** Write a `<!-- slot: summary -->` slot holding what the shape's summary is (see the table in section 8). For most shapes that is a one-paragraph `class="q-lede"` conclusion. Do not repeat it at the top of `main`.
- Open `main` with a source or scope line (`class="q-meta"`), then the components in `<section aria-labelledby="...">` blocks with `<h2>` headings.
- Do not write grid or fixed-width CSS in a slot. Use `q-grid`, `q-panel`, `q-sidenote` or `q-compare` from [components](../../references/components.md); the layout check fails hand-written layout CSS. The section nav is generated, so do not write a table of contents.
- Helper classes the skeleton defines: `q-lede`, `q-meta`, `q-stack` (a vertical stack with `--q-space-4` gaps), `q-chart` (a wrapper for Mermaid diagrams), `q-table-wrap`, and `num` on `th` and `td` for right-aligned numbers.
- Prose, tables and charts fill the column.

## Web Awesome

- Use the `<wa-*>` elements for what plain HTML lacks (tabs, dialog, select, switch, button). For tabs with no form controls, `q-tabs` avoids loading Web Awesome. Use native elements such as `<details>` and `<table>` for everything else, and `wa-dialog` for dialogs.
- Every control has a visible `label` or an `aria-label`. A `wa-dialog` has a `label` attribute, which is its title.
- The theme maps Web Awesome's color variables onto the `--q-*` tokens, so components follow light and dark themes. Do not set `--wa-*` colors or hard-coded colors in the page.
- Web Awesome events: use the native `change` and `input` events for form components, `wa-tab-show` for tabs, `wa-after-hide` for a dialog. Read values from `event.target`.
- `<wa-icon name="...">` works offline for the vendored set: `check`, `chevron-down`, `chevron-left`, `chevron-right`, `circle-check`, `gear`, `info`, `magnifying-glass`, `minus`, `plus`, `star`, `user`, `warning`, `xmark`, plus the aliases `circle-info` (`info`) and `triangle-exclamation` (`warning`). Any other name renders empty, so use a text label, or inline SVG with a `<title>`, for anything else. Give an icon-only control an `aria-label`.
- Keep state in Alpine (`x-data`, registered with `alpine:init`), and keep it small. A readout that changes with the controls sits in an `aria-live="polite"` element.

## Charts and tables

- Bar, line and area charts use `<q-chart>`, sortable tables use `<q-table>`, and every flowchart and explorable service or data-flow graph uses `<q-flow>`, including decisions (`shape: "decision"`), retries (`loop: true`) and steps that are their own process (`shape: "subprocess"`, optional `flow`); every data model, entity-relationship diagram and class diagram uses `<q-schema>` (`notation="class"`); every sequence diagram uses `<q-sequence>` (call, reply and async messages, alt, opt, loop and par fragments, traces); reuse `kinds` names and chart colors across artifacts, and keep Mermaid for state charts. Attributes and examples are in [components](../../references/components.md).
- Scatter and histogram charts stay hand-written Chart.js, under section 9 of the design reference. The theme toggle also sets the `wa-dark` class on `<html>`, so components and charts switch together.

## Scripts and data

- Slot scripts run before the library scripts, and Alpine starts before `chrome.js` defines `window.quirkData`. Call `quirkData()` and draw charts after the window `load` event.
- Declare every interaction you build in the source header's `interactions` list.
- No `fetch`, `XMLHttpRequest`, `WebSocket` or `EventSource` in offline mode.
