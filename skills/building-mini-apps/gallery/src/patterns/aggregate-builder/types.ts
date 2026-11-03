/** A caller row: an `id` plus whatever fields the schema names. Time fields hold epoch milliseconds. */
export type AggregateRow = { id: string } & Record<string, unknown>

export type FieldKind = "number" | "text" | "time"

export type FieldDef = {
  /** Property read from each row. */
  key: string
  label: string
  kind: FieldKind
  /** Shown after values and in column headers, e.g. "min". */
  unit?: string
}

export type FieldSchema = {
  /** Table columns, in this order. */
  fields: FieldDef[]
  /** The key that places each row in a chart bucket. */
  timeField: string
  /** Numeric key drawn as a proportional bar in the Samples table. */
  barField?: string
  /** What `count` counts; default "rows". */
  rowLabel?: string
}

export type AggregateFn =
  | "count"
  | "count_unique"
  | "sum"
  | "avg"
  | "min"
  | "max"
  | "p50"
  | "p75"
  | "p95"
  | "p99"

export type Visualize = { fn: AggregateFn; field?: string }

export type SortDir = "asc" | "desc"
export type GroupSortBy = "value" | "count" | "group"

export type AggregateQuery = {
  visualize: Visualize
  /** Key of a text field, or null for no grouping. */
  groupBy: string | null
  /** Sort of the Samples tab; `by` is a field key. */
  sampleSort: { by: string; dir: SortDir }
  /** Sort of the Aggregates tab. */
  groupSort: { by: GroupSortBy; dir: SortDir }
  chart: "line" | "bar"
  /** Bucket size in milliseconds; null picks one from the data. */
  interval: number | null
}

export type ResultsTab = "samples" | "aggregates"
