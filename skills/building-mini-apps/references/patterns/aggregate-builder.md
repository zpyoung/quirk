# aggregate-builder

A query builder over rows: a left rail picks what to visualize (an aggregate function and a field), how to group, and how to sort, and the result shows as a chart over time buckets with one series per group, above a table with Samples (the raw rows) and Aggregates (one row per group) tabs. It was studied in Sentry.

## When to use

Use it when the user has a log of timestamped rows and wants to ask "how much, how many or how slow, split by what" without writing a query:

- An expense log: sum of amount grouped by category per week, with the raw expenses under the chart.
- A delivery or courier log: p95 delivery minutes grouped by zone per hour.
- A build or job history: average duration grouped by job per day, with the slowest runs in the samples.
- A workout or time-tracking log: total hours grouped by project per day.

The rows need a time field, at least one numeric field and, for grouping, at least one text field. The caller passes rows already filtered and a schema that names the fields.

Do not use it when:

- The user narrows the rows with typed filters: use `query-tokens` above it. This block aggregates the rows it is given and has no filter box.
- The page only reports fixed numbers and nothing on it needs the picking controls: use the `writing-html-artifacts` skill, or `command-center` when the numbers are live tiles that need acting on.
- The rows are one request's timed steps in a tree: use `span-waterfall`.
- The user scans records and peeks at one: use `list-peek`.
- The user edits cells in a grid: use `staged-table-edit`.
- The same records need a table, a board and a calendar: use `view-switcher`.

## Anatomy

```
+------------------------------------------------------------------------------+
| VISUALIZE            |  p95(minutes) by zone              [Line|Bar] [1 hour v]|
| [p95 v] [minutes v]  |  60|        .-.                      --- Harbor        |
|                      |  40|   .-.-'   '-.   .-.             --- Old Town      |
| GROUP BY             |  20|--'           '-'   '--           --- Uptown        |
| [zone            v]  |   0+------------------------------   --- Other         |
|                      |    Oct 21     Oct 22     Oct 23     412 rows, 49 buckets|
| SORT BY              +-----------------------------------------------------+
| [p95(minutes) v][Desc]|  [Samples] [Aggregates]                              |
|                      |  zone       p95(minutes)  count(deliveries)           |
| [Reset]              |  [] Hillcrest   58.2          61                      |
|                      |  [] Uptown      47.9          88                      |
|                      |  [] Harbor      31.4         120                      |
+----------------------+------------------------------------------------------+
|    rail ~36%         |                results ~64%                          |
+------------------------------------------------------------------------------+
```

- **Rail:** about 36% of the block, three sections. Visualize holds the aggregate picker and the field picker side by side. Group By holds a field picker with a "None" choice. Sort By holds a field picker and an Asc/Desc picker. A Reset button appears only when the query differs from its starting point.
- **Chart header:** the aggregate written as `fn(field)` at the left, then a Line/Bar toggle and an interval picker at the right. The title adds "by <group field>" when grouping applies.
- **Chart:** inline SVG, about 11rem tall, with a y axis from zero, an x axis of time labels, and one series per group colored by the chart tokens. At most five series: the top four groups plus "Other", which re-aggregates every remaining group's rows together. A legend under the header lists the series, and a footnote under the plot says how many rows and buckets it shows.
- **Chart cursor:** a vertical marker with a small box listing every series' value in that bucket. The pointer or the Left/Right keys move it.
- **Tabs:** Samples and Aggregates. Samples lists raw rows, one per line, with the bar field (a duration, for example) drawn as a proportional bar in its cell. Aggregates lists one row per group, starting with a color swatch that matches its chart series, then the aggregate value and the row count.
- **Column headers:** the active sort shows an arrow and `aria-sort`; clicking a header sorts by it and clicking again flips the direction.
- **Narrow containers (under about 42rem wide):** the rail stacks above the results and uses the full width.

## Interaction

The blueprint's key map gives this pattern no keys, and no source shows any, so every key is our design. Keys fire only when focus is on the page body or inside the block, and never while typing in an input, textarea or contenteditable. The chart (a slider) and the Line/Bar toggle take no text, so the keys also work while either has focus. The block binds neither ⌘K (action-palette) nor `/` (query-tokens), and never ⌘N, ⌘T, ⌘W or ⌘L.

| Key | Does | Notes |
|-----|------|-------|
| `v` | Focuses the aggregate picker | Our design. |
| `g` | Focuses the Group By picker | Our design. Does nothing while Group By is disabled (Samples tab). |
| `s` | Focuses the Sort By field picker | Our design. |
| `1` / `2` | Shows the Samples / Aggregates tab | Our design. |
| `c` | Switches the chart between Line and Bar | Our design. |
| Left / Right | Moves the chart cursor one bucket | Only while the chart has focus. Our design. |
| Home / End | Moves the chart cursor to the first / last bucket | Only while the chart has focus. Our design. |
| Esc | Clears the chart cursor | Only while the chart has focus. Our design. Moving focus off the chart also clears it. |
| Hover chart | Shows the cursor and the value box for the bucket under the pointer | Seen in S5-t0104. Leaving the chart clears it. |
| Click column header | Sorts by that column; a second click flips the direction | The header arrow is seen in S5-t0040; the click is our design. |
| Click a sample's ID | Calls `onOpenRow(row)` | Only when `onOpenRow` is given; the ID is a button then. The host decides what opening means. Our design. |

The pickers are Radix selects: Enter, Space or Down opens one, arrows move, Enter chooses, Esc closes. On a focused picker the block's own letter and digit keys are not typeahead, so `g` pressed on the aggregate picker jumps to Group By and never changes the aggregate.

**Rules the controls follow.**

- Changing the aggregate keeps the field when it still applies; otherwise it takes the first field that does. Count has no field and shows the schema's row label ("deliveries") in a disabled field picker. Count unique takes any field. Sum, average, minimum, maximum and the percentiles take numeric fields only.
- Group By offers text fields. It is disabled on the Samples tab and says so in text next to it: "Switch to Aggregates to group." The Samples chart is one series.
- Sort By edits the sort of the tab you are on. Samples sorts by any field (default: the time field, newest first). Aggregates sorts by the aggregate value (default, highest first), by the row count (not offered when the aggregate is the count), or by the group name (offered only when grouped). Each tab remembers its own sort.
- The chart's top groups are the first rows of the Aggregates table in its current sort, so the chart and the table always agree on who is colored.
- Percentiles use linear interpolation between ranks. Rows whose field is not a finite number are skipped for numeric aggregates. A bucket with no values draws as a gap for average, minimum, maximum and the percentiles, and as zero for count, count unique and sum.
- The interval defaults to "Auto", the smallest preset that gives at most 60 buckets. A chosen interval that would give more than 240 buckets steps up to the next preset.
- Stacking: bars stack for count and sum, which add up across groups, and sit side by side for the other aggregates. Lines never stack. Series are told apart by a dash pattern as well as by color, so a style whose chart colors are close still reads.

| State | Shows |
|-------|-------|
| Empty (no rows) | The rail stays; `EmptyState` fills the results area with a hint and an optional `emptyAction` button. |
| Loading | The rail stays, disabled; `LoadingState` fills the results area. Keys do nothing. |
| Error | The rail stays, disabled; `ErrorState` with the message and a Retry button when `onRetry` is given. |
| No valid time on any row | The chart area says no row has a time; the tables still work. |
| An aggregate with no values (every row's field is blank) | The chart says there are no values for `fn(field)`; the table cells show a dash. |
| One bucket | The chart draws single points and one bar instead of a line. |
| Many rows | Samples shows the first `sampleLimit` rows (default 100) and says "Showing the first 100 of 1400 deliveries". Aggregates lists every group. Not virtualized; fine to a few thousand rows. |
| A group with no value in a bucket | A gap in its line, so a missing reading is never drawn as zero. |

## Borrow / Leave out

Borrow:

- A rail of query controls at about 36% of the content beside a chart over a table (S13-traces-explorer.png).
- Visualize as an aggregate picker and a field picker; changing the aggregate retitles the chart and redraws it (S5-t0048.png).
- Group By greyed out on the Samples tab, with the reason given instead of the control hidden (S5-t0044.png).
- Sort By as a field plus a direction, with an arrow on the sorted column header (S5-t0040.png).
- A chart header with the aggregate as a title and chart-type and interval controls (S5-t0040.png, S13-traces-explorer.png).
- One series per group, a legend of the top groups plus "Other", and a hover box listing every group's value in that bucket with a vertical marker (S5-t0104.png).
- An Aggregates table with a swatch that matches each chart series, sorted by the aggregate descending (S5-t0104.png).
- A dense samples table with right-aligned durations (S5-t0040.png) and a proportional bar cell (S13-trace-samples.png).
- A footnote under the chart that says how much data it shows (S5-t0040.png).

Leave out:

- The search bar and the project, environment and date pickers above the rail: the caller filters rows, and `query-tokens` is the pattern for typed filters.
- Add Series, Add Chart and Add Equation: the block has one aggregate. Stacked charts, one per series, are not built.
- Save as, Compare Queries, the Suggested Queries card and starred queries: saving a query is `view-switcher`'s revision and is not part of this block.
- Edit Table and the Trace Samples tab: the table shows the schema's fields as given.
- The collapse arrow on the rail seam: the rail stacks on narrow containers instead.
- "Extrapolated from N samples": the block aggregates every row it is given, so there is nothing to extrapolate.
- The studied app's purple, its fonts and its icons: colors come from the theme and chart tokens.
- Span, trace and transaction vocabulary: field names, labels and units come from the caller's schema.

## Block API

Files in `gallery/src/patterns/aggregate-builder/`: `registry-item.json`, `index.ts`, `types.ts`, `aggregate.ts`, `field-picker.tsx`, `aggregate-picker.tsx`, `query-rail.tsx`, `series-chart.tsx`, `results-table.tsx`, `aggregate-builder.tsx`, `demo.tsx`.

```
CONTRACT: type AggregateRow = { id: string } & Record<string, unknown>

CONTRACT: type FieldDef = {
  key: string                       // property read from each row
  label: string
  kind: "number" | "text" | "time"  // time fields hold epoch milliseconds
  unit?: string                     // shown after values and in headers, e.g. "min"
}

CONTRACT: type FieldSchema = {
  fields: FieldDef[]                // table columns, in this order
  timeField: string                 // the key that buckets rows on the chart
  barField?: string                 // numeric key drawn as a bar in the Samples table
  rowLabel?: string                 // what count counts; default "rows"
}

CONTRACT: type AggregateFn =
  "count" | "count_unique" | "sum" | "avg" | "min" | "max" | "p50" | "p75" | "p95" | "p99"

CONTRACT: type AggregateQuery = {
  visualize: { fn: AggregateFn; field?: string }   // field is omitted for count
  groupBy: string | null                           // a text field's key
  sampleSort: { by: string; dir: "asc" | "desc" }  // by is a field key
  groupSort: { by: "value" | "count" | "group"; dir: "asc" | "desc" }
  chart: "line" | "bar"
  interval: number | null                          // bucket size in ms; null is auto
}

CONTRACT: type ResultsTab = "samples" | "aggregates"

CONTRACT: AggregateBuilder<T extends AggregateRow>(props: AggregateBuilderProps<T>): JSX.Element

CONTRACT: type AggregateBuilderProps<T extends AggregateRow> = {
  rows: T[]
  schema: FieldSchema
  status?: "loading" | "ready" | "error"           // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  query?: AggregateQuery                           // controlled; omit for internal state
  onQueryChange?: (query: AggregateQuery) => void
  initialQuery?: Partial<AggregateQuery>           // starting point for internal state and for Reset
  tab?: ResultsTab                                 // controlled; omit for internal state, default "samples"
  onTabChange?: (tab: ResultsTab) => void
  onOpenRow?: (row: T) => void                     // makes each sample's ID a button
  sampleLimit?: number                             // default 100
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}
```

`aggregate.ts` is plain TypeScript with no React. It exports, among others, `AGGREGATES`, `defaultQuery`, `normalizeQuery`, `aggregateValue`, `percentile`, `buildGroups`, `sortSamples`, `buildChart`, `resolveInterval`, `niceTicks`, `formatNumber` and `formatBucket`. Every function takes its inputs as arguments, so none reads the clock.

`index.ts` exports `AggregateBuilder`, `AggregatePicker`, `FieldPicker`, the pure functions above, and the types `AggregateBuilderProps`, `AggregateRow`, `AggregateQuery`, `AggregateFn`, `FieldDef`, `FieldSchema` and `ResultsTab`. `demo.tsx` default-exports `Demo`.

Uses from the base:

- `useCollection` in the demo only; `AggregateBuilder` takes `rows` and `status` as props and does not read the store.
- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for the results area.
- `useHotkeys` from `react-hotkeys-hook` for all keys. The block's keys are bound only while focus is on the page body or inside the block; the chart's keys use the hook's ref form, so they act only while the chart has focus.
- shadcn components, all pre-installed: `select`, `tabs`, `table`, `toggle-group`, `button`. No new dependencies.

Built inside the block: the field picker (a select of fields with a kind icon, an optional "None" choice and a disabled state; the rail also uses it for the sort direction and the chart uses it for the interval) and the aggregate picker (a select of the aggregate functions in Count, Statistics and Percentiles groups). Both stay in this block; a pattern that needs one copies it.

`demo.tsx` renders neither `AppShell` nor a toaster. It shows a delivery log of 1400 invented deliveries over two days, stored with `useCollection("aggregate-builder-demo", seed)`. Fields: `timestamp`, `courier`, `zone`, `vehicle`, `minutes` (the bar field), `km` and `items`. Evening deliveries run slower and a few outliers make the percentiles worth reading. Clicking a sample's ID shows that delivery's summary in a line under the block. A "State preview (demo only)" button group (live, empty, loading, error) forces each state; the empty state offers "Restore sample deliveries", and Retry in the error state returns to live. A "Reset sample data" button rewrites the seed. A plain-text footer lists the key hints.

## Sources

[sentry study note](../apps/sentry.md). Bucket math, percentile method, the top-four-plus-Other rule, keys and every state are not from a source.

- **Rail beside a chart over a table, rail about 36% of the content:** `S13-traces-explorer.png`. An earlier frame shows a narrower rail (about 15% of the window, `S5-t0040.png`); the 36% share is the one built.
- **Visualize as aggregate and field pickers, chart retitles on change:** `S5-t0048.png`, `S13-traces-explorer.png`.
- **Group By disabled on Samples with an explanation:** `S5-t0044.png`. The study shows the reason as a hover tooltip; ours is visible text so keyboard users get it (our design).
- **Help on the Group By label:** `S5-t0056.png` shows a hover tooltip; not built.
- **Sort By as field plus direction, arrow on the sorted header:** `S5-t0040.png`, `S13-traces-explorer.png`.
- **Chart header with title, chart type and interval:** `S5-t0040.png`, `S13-traces-explorer.png`.
- **Chart over the date range with a short x axis and a stepped y axis, bar for counts and line for averages:** `S5-t0040.png`, `S13-traces-explorer.png`.
- **One series per group, legend of top groups plus Other, hover box with every group's value, vertical marker:** `S5-t0104.png`.
- **Aggregates table with a matching swatch, sorted by the aggregate descending:** `S5-t0104.png`.
- **Samples table, dense rows, right-aligned duration:** `S5-t0040.png`, `S5-t0088.png`.
- **Duration bar cell:** `S13-trace-samples.png`, where a trace's timeline is a bar proportional to its duration; applied here to a numeric field of a raw row.
- **Footnote under the chart about the data shown:** `S5-t0040.png`, `S5-t0080.png`, with different wording (rows and buckets, not an extrapolation).
- **Pager under a short table:** `S5-t0088.png`; replaced by the row limit note (our design).
- **Our design:** every key, the chart cursor and its keyboard control, the per-tab sorts and their options, clickable column headers, the top-four-plus-Other series rule and re-aggregating Other from its rows, dash patterns, stacking rules, the auto interval and its bucket caps, linear-interpolation percentiles, gaps for empty buckets, the Reset button, `onOpenRow`, the row limit, the narrow layout, and all the empty, loading and error states.
