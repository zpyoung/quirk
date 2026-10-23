# span-waterfall

A tree of timed rows beside one shared time axis: each row has a duration bar placed by its start and length, empty stretches are squeezed into a marked band, failing rows carry an error badge, and clicking a row opens a side panel that squeezes the timeline instead of covering it. It was studied in Sentry.

## When to use

Use it when the user reads one run that nests steps inside steps and needs to see where the time went:

- A build or deploy pipeline: stages, jobs and steps with their timings, one failing step flagged, a long wait for approval squeezed out of the way.
- A project plan: tasks and subtasks on a shared timeline, with a panel for the owner, notes and attributes of one task.
- A recipe or event run-of-show: courses, prep steps and overlaps laid out against the clock.
- A batch-import or sync run: phases and per-file steps, with the slow or failed ones easy to spot.

Do not use it when:

- The rows have no start and length, only a status or a date: use `list-peek` for a list with a detail panel.
- The detail is a few lines that belong under the row and nothing needs a shared axis: use `expand-in-place`.
- The entries are a flat, time-ordered log with no nesting and no durations: use `event-timeline`.
- The user compares many runs as a table with a small bar per row: use `bulk-select`, and open one run in this pattern.
- The panel is a property editor for a selected object, not a read-only view of a span: use `inspector`.
- The data is stack frames, not timed steps: use `stack-trace`.
- The user watches a live set of things and acts on what needs them: use `command-center`.

## Anatomy

```
+-----------------------------------------------------------------------------+
| ship-web #482                     Spans 35  Errors 3  Total 11m 40s  Queue 1s | header
| Release pipeline                                                            | ~64px
| (o) pipeline (o) setup (o) check (o) build (o) ship        [Compress gaps]  | legend
| [ Search in trace                                  ]  2 of 5      [^] [v]   | search ~44px
+--------------------------+-----------+-----------------------+--+-----------+
| Operation                | runner [P]| 0ms   2m  //3m 20s//  10m | Close  check.case - checkout flow
+--------------------------+-----------+---------------------------+-----------+
| 12 v pipeline.run - ship | -         | ======================== 11m 40s | Span
| |-1 > setup.checkout - ..| build-p-1 | = 4.2s                    | ID: s17 [copy]
| | `- . setup.fetch - ... | build-p-1 | = 3.4s                    | [!] 1 error
| |-4 v check.e2e - brow.. | build-p-4 |        =======  1m 58s    | check.case
| | |- . check.case - chk  | build-p-4 |        == [!1] 41.2s      | 41.2s  6% of trace
| | `- . check.case - ret  | build-p-4 |           === 38.4s       | Attributes [search]
| ...                      |           |            hatched band   |  runner  build-p-4 [P]
+--------------------------+-----------+---------------------------+-----------+
   tree ~36% of the waterfall   pinned     timeline (rest)           panel ~40%
   (waterfall ~60% while the panel is open)
```

- **Header:** a title and subtitle supplied by the app, then stat blocks the block computes (Spans, Errors, Total duration) followed by any pills the app passes (a queue time, a cache state), and the Compress gaps toggle. The toggle appears only when the trace has a gap long enough to compress.
- **Legend:** one swatch and name per operation category present in the data. Color is never the only cue, since every row also prints its op.
- **Search row:** a text input labeled "Search in trace" spanning the width, a match counter, and previous and next buttons. Matching rows get a tint and the rest dim.
- **Tree column:** about 36% of the waterfall width, with an 11rem floor. Each row is about 28px tall with alternating shading. A row shows indent guides (a vertical line per ancestor level that continues while that ancestor has later siblings, and an elbow into the row), then a collapse pill with the direct-child count and a chevron, or a dot on a leaf, then the op in bold, an em dash and the description. Long descriptions truncate at the column edge.
- **Pinned columns:** between the tree and the timeline, one column per pinned attribute, 8rem each. The header shows the attribute key and a pin button that unpins it. A span without the attribute shows a dash.
- **Time axis:** a sticky header row over the timeline with ticks and labels at round values, optional marker flags at their time with a dashed guide the full height of the rows, and a hatched band where a gap was squeezed, with a pill over it giving the hidden duration. Ticks stay clear of the pill.
- **Duration bar:** one per row, placed by start offset and sized by duration, colored by the span's op category through `--chart-1` to `--chart-5`. The duration label sits right of the bar, left of it when the bar ends past 70% of the axis, and inside the bar, right-aligned, when it also starts in the first quarter (a root bar that spans the whole axis). A span with no length draws a 2px tick. A span with errors shows an error badge (icon and count) at the bar's start, and its tree text turns to the error color.
- **Selected row:** outlined across the full row width. The outline stays when the panel closes.
- **Span panel:** about 40% of the waterfall width, to the right of a drag handle. Header: a Close button and a tab-style label with the span's swatch, op and description. Body, top to bottom: a "Span" title, the span ID with a copy button, an error card when the span has errors, the op with its duration, self time and share of the trace, the description in a code box with a copy button, the most frequent op categories among its descendants as percent chips, a General block (start offset, parent link), and an Attributes list with a search box and a pin button per attribute. The body scrolls inside the panel.
- **Narrow windows (under 560px of block width):** the panel covers the waterfall instead of splitting it, with no drag handle. Close returns to the tree.

## Interaction

Keys act while focus is on the tree or on the page body, never while typing in the search box, the attribute search or any other input, textarea or contenteditable. The map is our design: no source shows keys for the waterfall (Unseen in the sentry study note).

| Key | Does | Notes |
|-----|------|-------|
| ArrowDown | Selects the next visible span | With nothing selected, selects the first. Stops at the last row. If the panel is open it swaps to the new span (our design). |
| ArrowUp | Selects the previous visible span | With nothing selected, selects the last. Stops at the first row. Same panel rule. |
| ArrowRight | Expands the selected span if it is collapsed; otherwise selects its first child | Our design, the usual tree rule. A leaf does nothing. |
| ArrowLeft | Collapses the selected span if it is expanded; otherwise selects its parent | Our design. A root with no parent does nothing. |
| Enter | Opens the panel on the selected span | Our design. Does nothing with no selection. |
| Esc | Closes the panel | Our design. The selected row keeps its outline and focus stays on the tree. |
| Home / End | Selects the first / last visible span | Our design. |
| Click row | Selects it, outlines it and opens the panel; with the panel open, swaps its content in place | S13-span-panel.png, S13-span-panel-second-span.png. Focus moves to the tree. |
| Click collapse pill | Collapses or expands that subtree; descendants leave or return and the rows below move | S13-trace-collapse-children.png. The pill is not a tab stop. If the selected span was inside the subtree, the collapsed span becomes the selection (our design); otherwise selection and panel are unchanged. |
| Click the Parent link in the panel | Selects the parent span, expanding collapsed ancestors; the panel swaps | Our design. |
| Click Close | Closes the panel and restores the full-width timeline | S13-trace-waterfall-panel-closed.png. The row keeps its outline. |
| Drag the handle | Resizes the panel | Our design. The handle is a focusable separator; its own arrow keys resize in steps and the tree's keys ignore it. The range is 25% to 65% of the waterfall. |
| Click Pin on an attribute | Adds or removes a column for that attribute key | S11-pin-attribute.png, S11-pinned-columns.png. The pin is a toggle button that reports pressed. |
| Click a pinned column's pin | Unpins that column | Our design. |
| Type in search | Marks every span whose op, description, ID or an attribute value contains the text, case-insensitive | S11-trace-view.png, S13-trace-waterfall.png. The counter reads "N matches" or "No matches". |
| Enter / Shift+Enter in search | Selects the next / previous match and scrolls it into view; expands collapsed ancestors; the panel swaps if it is open | Our design. |
| Previous / next match buttons | The same as Shift+Enter and Enter | Arrows beside the search box in S11-trace-view.png. Their job there is related traces, so this use is our design. |
| Esc in search | Clears the text; with no text, moves focus to the tree | Our design. |
| ArrowDown in search | Moves focus to the tree and selects the first span if none is selected | Our design. |
| Compress gaps toggle | Squeezes or restores the idle bands | S11-time-compression.png. The docs name the control but not where it lives or any key, so the button is our design. |
| Tab | Search, toggles and buttons in reading order, then the tree as one stop, then the handle and the panel | Our design. Rows are not tab stops; arrow keys move between them. |

**Focus rules.**

- The tree is one focusable `treegrid`. The selected row is exposed through `aria-activedescendant`, so selecting, opening and closing the panel never move focus off it.
- Opening the panel by click or Enter keeps focus on the tree. Tab goes on into the panel; Esc inside the panel closes it and returns focus to the tree. Esc in the attribute search clears that text first.
- Rows carry `aria-level`, `aria-expanded` when they have children, and `aria-selected`.
- An error is an icon and a count with text, and a squeezed gap is a labeled band, so neither relies on color.
- If the selected span vanishes from the data, the selection clears and the panel closes. A collapsed parent hides its descendants but keeps its own selection.

| State | Shows |
|-------|-------|
| Loading | `LoadingState` "Loading trace" in place of the tree. The title row stays. Keys do nothing. |
| Error | `ErrorState` with the message and a Retry button when `onRetry` is given. |
| Empty (no spans) | `EmptyState` "No spans in this trace" in place of the tree. No panel. |
| No search matches | The counter reads "No matches", every row dims, the tree stays. Enter in search does nothing. |
| Panel open | The tree and axis keep their layout but narrow; the timeline keeps its proportions, so bars shrink with it. The selected row stays in view. |
| Pinned column, missing value | A dash in that row's cell. |
| Zero-length span | A 2px tick and a "0ms" label. |
| Very long description | Truncates at the tree column edge; the full text is in the row's `title` and in the panel. |
| Orphan span (parent not in the data) or several roots | Rendered as an extra root, in start order. Duplicate IDs keep the first span. |
| Trace with no idle gap | No band and no Compress gaps toggle. |
| Many spans | The tree scrolls under a sticky axis row. Not virtualized; fine to a few hundred rows. |

**Timeline math.** A gap is a stretch where no leaf span (a span with no children in the data) is running, longer than `gapThresholdMs` (default 20% of the trace). A parent span that covers it does not close it, because the parent's bar simply crosses the band. Each gap is drawn at 5% of the axis (less when there are many) and the rest of the axis is divided between the remaining time in proportion. Ticks use 1, 2 or 5 times a power of ten at about five per axis, are placed per visible stretch, and are dropped when they would sit under a band's pill or closer than 10% of the axis to the previous tick.

## Borrow / Leave out

Borrow:

- A two-column waterfall: the tree on the left, the axis and bars on the right, rows 24 to 28px tall with alternating shading and a sticky axis header (S11-trace-view.png, S13-trace-waterfall.png).
- Each parent row shows a rounded pill with its child count and a chevron; clicking it collapses that subtree and the chevron turns (S11-trace-view.png, S13-trace-collapse-children.png).
- Indent guides as vertical lines with elbows, and a dot-and-line connector on leaf rows (S11-trace-view.png, S11-time-compression.png).
- The op in bold, an em dash, then the description, truncated at the column edge (S11-trace-view.png).
- Bars placed by start offset, sized by duration and colored by op category, with the duration printed beside the bar so thin bars stay readable, and a 1px tick for a zero-length span (S11-trace-view.png, S11-time-compression.png).
- An error badge with a count on the bar and error text in the tree (S11-trace-view.png, S11-pinned-columns.png).
- Marker flags on the axis with a dashed guide line (S11-trace-view.png, S13-trace-waterfall.png).
- Time compression: an empty stretch becomes a narrow hatched band labeled with the hidden duration, and later spans resume at their true offsets (S11-time-compression.png).
- A header with identity and stat blocks: Spans, Errors, Root duration (S11-trace-view.png, S13-trace-waterfall.png, S6-t0016.png).
- A full-width "Search in trace" row above the waterfall (S11-trace-view.png, S13-trace-waterfall.png).
- Clicking a row outlines it and opens a panel of about 40% of the waterfall that squeezes the tree and axis; clicking another row swaps the panel in place; Close restores the full width and the row keeps its outline (S13-span-panel.png, S13-span-panel-second-span.png, S13-trace-waterfall-panel-closed.png).
- The panel's content order: Close and a tab-style span label, a title with a copyable ID, related-issue cards, the op and duration, the description in a code box, the most frequent child ops as percent chips, and a searchable Attributes tree with its own scrollbar (S13-span-panel.png, S11-trace-view.png).
- A duration chip that compares the span with an average (S13-span-panel-second-span.png). Ours shows share of the trace and self time, which need no history.
- Pinning an attribute adds a column between the tree and the timeline, with the key and a pin icon in its header and a dash for rows without it (S11-pin-attribute.png, S11-pinned-columns.png).

Leave out:

- Sentry's colors, icons, wordmark and copy, and the project avatars on rows: colors come from the app's chart tokens and rows show only the op.
- Web vitals (LCP, FCP, INP, CLS, TTFB) as colored pass or fail pills and jump-to-vital zoom (S11-trace-view.png, S11 text). The app can pass its own pills and markers.
- Related-issue cards with offending SQL, "View Summary", "More Samples", "Open in Explore", and links to other traces with Previous and Next trace buttons (S13-span-panel.png, S11 text). They need a real backend.
- Autogrouped collapsed groups with a count badge (S5-t0064.png) and thin ticks for collapsed siblings at the far right (S5-t0092.png): a collapsed row keeps its own bar and hides its descendants.
- The minimap scroll strip, Reset Zoom, the layout toggle, the JSON view, the focus-on-span button and pinned span tabs (S6-t0016.png, S5-t0064.png, S11-trace-view.png). Panning is native scrolling; the axis does not zoom.
- Orphan transactions drawn with dashed connectors and error-only rows linked to Issue Details (S11 text): an orphan span becomes a root.
- A shareable URL for the highlighted row and persistence of highlights across navigation (S11 text). The host can control `selectedId` itself.
- The compare-with-average slower pill, which needs history.

## Block API

Files in `gallery/src/patterns/span-waterfall/`: `registry-item.json`, `index.ts`, `types.ts`, `waterfall.ts`, `time-axis.tsx`, `duration-bar.tsx`, `collapse-pill.tsx`, `span-panel.tsx`, `span-waterfall.tsx`, `demo.tsx`.

```ts
CONTRACT: type Span = {
  id: string
  parentId: string | null              // null, or an ID not in the data, makes a root
  op: string                           // "test.case"; the part before the first dot is the color category
  description: string
  start: number                        // ms; any origin, the axis starts at the earliest start
  duration: number                     // ms; negative values count as 0
  errors?: string[]                    // one message per error; the count is the badge
  attributes?: Record<string, string>  // shown in the panel and available to pin
}

CONTRACT: type WaterfallStat = { label: string; value: string; tone?: "default" | "bad" }
CONTRACT: type WaterfallMarker = { label: string; at: number }   // same origin as Span.start

CONTRACT: type SpanWaterfallProps = {
  spans: Span[]
  status?: "loading" | "ready" | "error"             // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  title?: string
  subtitle?: string
  stats?: WaterfallStat[]                            // blocks after the computed Spans, Errors and Total duration
  markers?: WaterfallMarker[]
  gapThresholdMs?: number                            // default 20% of the trace duration
  defaultCompressed?: boolean                        // default true
  defaultPinnedKeys?: string[]
  pinnedKeys?: string[]                              // controlled; omit for internal state
  onPinnedKeysChange?: (keys: string[]) => void
  selectedId?: string | null                         // controlled; omit for internal state
  onSelectedIdChange?: (id: string | null) => void
  panelOpen?: boolean                                // controlled; omit for internal state
  onPanelOpenChange?: (open: boolean) => void
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

CONTRACT: SpanWaterfall(props: SpanWaterfallProps): JSX.Element
CONTRACT: TimeAxis(props: { scale: Scale; markers?: WaterfallMarker[] }): JSX.Element        // header row: ticks, marker flags, gap pills
CONTRACT: TimeGuides(props: { scale: Scale; markers?: WaterfallMarker[] }): JSX.Element      // full-height lines and gap hatching behind the rows
CONTRACT: DurationBar(props: { left: number; width: number; color: string; label: string; errors?: number; className?: string }): JSX.Element
CONTRACT: CollapsePill(props: { count: number; expanded: boolean; onToggle: () => void; label: string }): JSX.Element
CONTRACT: SpanPanel(props: { span: Span; spans: Span[]; palette: Palette; origin: number; total: number; pinnedKeys: string[]; onTogglePin: (key: string) => void; onSelectParent: (id: string) => void; onClose: () => void }): JSX.Element

CONTRACT: flattenTree(spans: Span[], collapsed: ReadonlySet<string>): TreeRow[]
CONTRACT: type TreeRow = { span: Span; depth: number; childCount: number; expanded: boolean; isLast: boolean; guides: boolean[]; parentId: string | null }
CONTRACT: ancestorIds(spans: Span[], id: string): string[]
CONTRACT: traceBounds(spans: Span[]): { origin: number; end: number }
CONTRACT: findGaps(spans: Span[], thresholdMs?: number): Array<{ from: number; to: number }>
CONTRACT: createScale(spans: Span[], options?: { gapThresholdMs?: number; compress?: boolean }): Scale
CONTRACT: type Scale = { origin: number; end: number; duration: number; hidden: number; position: (t: number) => number; gaps: Array<{ from: number; to: number; at: number; width: number }>; ticks: Array<{ t: number; at: number; label: string }> }
CONTRACT: matchSpanIds(spans: Span[], query: string): string[]
CONTRACT: selfTime(spans: Span[], id: string): number
CONTRACT: opShares(spans: Span[], id: string, top?: number): Array<{ category: string; share: number }>
CONTRACT: opCategory(op: string): string
CONTRACT: opPalette(spans: Span[]): Palette           // category -> 1..5, by first appearance
CONTRACT: formatDuration(ms: number): string
```

`index.ts` exports `SpanWaterfall`, `TimeAxis`, `TimeGuides`, `DurationBar`, `CollapsePill`, `SpanPanel`, the functions above, and the types `Span`, `SpanWaterfallProps`, `WaterfallStat`, `WaterfallMarker`, `TreeRow`, `Scale` and `Palette`. `waterfall.ts` has no React and takes every input as a parameter, so tree flattening, gap compression, tick choice, search and the duration math can be run without a browser.

Uses from the base:

- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for all body states. `useCollection` in the demo only; the block takes `spans` and `status` as props and does not read the store.
- `useHotkeys` from `react-hotkeys-hook` for the tree keys, with form-tag filtering on, enabled only while the status is ready and the tree has rows.
- shadcn components, all pre-installed: `button`, `input`, `scroll-area` and `resizable`. No new dependencies; `resizable` brings `react-resizable-panels`, which the gallery already installs.
- Colors only through theme tokens and `var(--chart-1)` to `var(--chart-5)`. The block draws bars and the axis with divs and no chart library.

`demo.tsx` default-exports `Demo`: one release pipeline run of 35 spans ("ship-web #482", invented) stored through `useCollection("span-waterfall-demo", seed)`. It has five operation categories (pipeline, setup, check, build, ship), a 3-minute wait for approval that the axis squeezes into a hatched band, three errors on two spans (a browser test that timed out and a health probe with two 503s), a zero-length span, one very long description, a marker at the build start, and a `runner` attribute on most spans, pinned at the start, so pinning has something to show. A "State preview (demo only)" button group (live, empty, loading, error) forces each state; the empty state offers "Restore sample trace". A plain-text footer lists the key hints.

## Sources

[sentry study note](../apps/sentry.md). The key map, the resize handle, the narrow-window cover, the compression math and the search match rules are not from a source.

- **Waterfall layout, two columns, row height, sticky axis, alternating rows:** `S11-trace-view.png`, `S13-trace-waterfall.png`, `S6-t0016.png`, `S5-t0064.png`.
- **Child-count pill with chevron, collapse of a subtree:** `S11-trace-view.png`, `S13-trace-collapse-children.png`, `S5-t0092.png`.
- **Indent guides, leaf connectors, op in bold then description:** `S11-trace-view.png`, `S11-time-compression.png`.
- **Bars by start and duration, colored by op, label beside the bar, thin tick for short spans:** `S11-trace-view.png`, `S11-time-compression.png`, `S5-t0064.png`.
- **Error badge on the bar and error text in the tree:** `S11-trace-view.png`, `S11-pinned-columns.png`, `S6-t0016.png`.
- **Axis ticks and marker flags with dashed guides:** `S11-trace-view.png`, `S13-trace-waterfall.png`, `S5-t0064.png`.
- **Time compression band and its label:** `S11-time-compression.png`, S11 text (Time compression).
- **Header stats:** `S11-trace-view.png`, `S13-trace-waterfall.png`, `S6-t0016.png`.
- **Search in trace row:** `S11-trace-view.png`, `S13-trace-waterfall.png`, `S5-t0064.png`.
- **Click outlines a row and opens a panel of about 40% that squeezes the timeline:** `S13-span-panel.png`, `S11-trace-view.png`, `S5-t0064.png`.
- **Swapping the panel in place, Close restoring full width, outline kept:** `S13-span-panel-second-span.png`, `S13-trace-waterfall-panel-closed.png`.
- **Panel contents and its own scrollbar:** `S13-span-panel.png`, `S11-trace-view.png`, `S5-t0092.png`.
- **Pinned attribute columns:** `S11-pin-attribute.png`, `S11-pinned-columns.png`, S11 text (Pinning attributes).
- **Orphans, multiple roots and a short tree still rendering:** S11 text (Troubleshooting), `S5-t0092.png`.
- **Our design:** every key, expand-or-select-child and collapse-or-select-parent, Home and End, the keyboard panel swap, the resize handle and its 25% to 65% range, the 560px cover, leaf-based gap detection with its 20% default threshold and 5% band width, the Compress gaps toggle, search matching on attributes and Enter to step, the self time and share chips, the pin toggle in the panel and the unpin button in the column header, controlled `selectedId`, `panelOpen` and `pinnedKeys`, and every state's wording.
