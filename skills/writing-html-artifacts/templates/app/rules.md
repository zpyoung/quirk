# App template rules

Read after the [design reference](../../references/design-reference.md). These rules add to it for pages built from `app`, the tier-2 template: a React project you edit as source and bundle to one HTML file.

## Workflow

- Build with `scripts/quirk_html.py build-app <slug> --title "..." --layout <shape> --signal "<why tier 2>"`. The first build copies `project/` and then the `example/` overlay to `.quirk/html/<slug>/`, installs, builds and writes `.quirk/html/<slug>.html`.
- Edit the files under `.quirk/html/<slug>/src/`, then run `build-app <slug>` again. The source folder is never overwritten, so your edits are safe. Title, layout, mode and signal are saved in `quirk-app.json` there; pass a flag again to change one.
- Exit 3 means tier 2 is unavailable here (no Node, no pnpm, a failed install or a failed build). Write a tier-1 source instead and list what you cut. Do not retry in a loop.
- The install runs `pnpm install --frozen-lockfile --ignore-scripts`. Add a dependency only when the app needs it, with an exact version, and regenerate `pnpm-lock.yaml` with `pnpm install` in the source folder first.

## What the scaffold gives you

| File | Role |
|---|---|
| `src/routes.tsx` | the `views` list: one `{path, label, component, summary, aside?}` per view; each becomes a tab and a hash route. Edit this first |
| `src/App.tsx` | page shell, view tabs, theme toggle and the router; renders each view inside `PageLayout`; rarely needs edits |
| `src/PageLayout.tsx` | the region wrapper: summary, the section nav, the view as `main`, and the report aside, in the same DOM order and markup as a tier-1 page |
| `src/theme.css` | imports `src/quirk-tokens.css` and `src/quirk-layout.css` and adds the `q-table-wrap` and `q-data-grid` classes |
| `src/quirk-tokens.css` | the merged house, user, project and template tokens as `--q-*` variables for light and dark; every build rewrites it, so put brand changes in a tokens file, not here |
| `src/quirk-layout.css` | a copy of the skill's shared page-shape stylesheet; every build rewrites it |
| `src/quirk-page.ts` | exports the layout name from `quirk-app.json`, read by `PageLayout`; every build rewrites it |
| `src/theme.ts` | `useThemeMode`, `setThemeMode`; the toggle shares the `quirk-theme` storage key with tier-1 pages |
| `src/main.tsx` | mounts the app inside a `QueryClientProvider` |

- **Never edit `quirk-layout.css` or `quirk-page.ts` by hand**, as with `quirk-tokens.css`. Change the shape with `--layout` or the `layout` field in `quirk-app.json`, then rebuild. The default is `report`.
- The page `<h1>` is the `--title` you gave. Do not render another `<h1>`; start views at `Heading level={2}`.
- Routing uses hash history so it works from `file://`. Keep views statically imported: no `React.lazy`, no route-level code splitting. The bundle is one chunk by design.
- Shared state goes in the query cache (see `useFlags` in the example) or a context at the root. Do not keep it in a view that unmounts when the tab changes.

## Page shape

- Every view needs a `summary` in `routes.tsx`: the JSX that fills the shape's summary region (the table in section 8 of the [design reference](../../references/design-reference.md)). `PageLayout` places it, so do not render it again inside the view. Pass `aside` only on a `report` app; any other shape ignores it.
- The view's own component is the `main` region. `PageLayout` builds the section nav from its rendered h2 and h3 headings at run time, with the same rules as a tier-1 page: at 5 or more h2s, and always on `reference`. Headings inside `q-panel`, `q-compare`, `q-tabs` and `q-board` are not listed.
- Arrange content with `q-grid`, `q-panel`, `q-sidenote` and `q-compare` from [components](../../references/components.md), written in JSX. Do not write `display: grid`, `grid-template-*` or a fixed width in a `.css` file or a `style={{...}}` object under `src/`: the layout check runs over those sources on every build, fails the build (exit 1) and names the file and line.
- Rename nothing in `theme.css`: the scaffold's table class is `q-data-grid`, so `q-grid` always means the layout element.
- One example per shape is in `examples/<shape>/`. Each overlay holds a `quirk-app.json` with its `layout` and its own `routes.tsx`.

## Components

- Import Astryx per subpath: `import { Button } from '@astryxdesign/core/Button'`. Never import from the package root.
- Use Astryx for layout, controls and feedback (`VStack`, `HStack`, `Button`, `Switch`, `TextInput`, `NumberInput`, `Banner`, `Badge`). Use plain markup for tables: TanStack Table gives the model, you write the `<table>`.
- Every control needs a `label`; use `isLabelHidden` when a column header already names it. A control inside a table cell names its row, for example "Enable new-checkout".
- Style with the `--q-*` variables, never hard-coded colors, so light and dark both work. A `q-table-wrap` around any wide table keeps the page from scrolling sideways at 375px.

## Tables

- Keep `features`, `columns` and fallback data at module scope or in a `useMemo`, as the TanStack Table v9 docs require. A new array each render re-runs the row model.
- Declare features with `tableFeatures({})` and add only the ones you use. Edits go through the shared state, not through the table's own copy of the data.

## Kit elements

- Write `q-*` elements (`q-chart`, `q-stat`, `q-table`, `q-tabs`, `q-board` and the rest) in a view's JSX and the build inlines the kit, and Chart.js for `q-chart`. The attributes and markup each one takes are in [the component reference](../../references/components.md); the build's `kit` check fails an unknown tag, a missing required attribute or a bad literal value, naming the `src/` file and line.
- Use `className`, not `class`.
- Keep a `q-*` element's direct children stable. Change rows or attributes, or give the element a `key` to remount it, because the element builds its own DOM from those children.
- Never let React re-render `q-board` cards: the board owns card placement and saves it.

## Modes and network

- Offline (the default): the bundle makes no network requests. Do not call `fetch`, `XMLHttpRequest`, `WebSocket` or `EventSource`; verify fails the page if any request leaves the file.
- Connected: pass `--mode connected` when the app reads live data. The static check then only fails external `<script src>`, `<link href>`, `@import` and font `url()`.
- Embed data in the source (a `.json` file imported by a view) rather than loading it at run time. `window.quirkData()` is tier 1 only.

## Before you hand it over

- Run `verify` on the built file. The scaffold passes the console, viewport, contrast and network checks; keep it that way when you change views.
- The file is large (React, Astryx and TanStack together), so expect the over-2 MB size warning. It is not a failure.
