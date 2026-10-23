import type {
  AggregateFn,
  AggregateQuery,
  AggregateRow,
  FieldDef,
  FieldSchema,
  SortDir,
  Visualize,
} from "./types"

export type AggregateDef = {
  fn: AggregateFn
  label: string
  group: "Count" | "Statistics" | "Percentiles"
  /** What field the function reads: none (count), any kind of field, or a number field. */
  needs: "none" | "any" | "number"
}

export const AGGREGATES: AggregateDef[] = [
  { fn: "count", label: "Count", group: "Count", needs: "none" },
  { fn: "count_unique", label: "Count unique", group: "Count", needs: "any" },
  { fn: "sum", label: "Sum", group: "Statistics", needs: "number" },
  { fn: "avg", label: "Average", group: "Statistics", needs: "number" },
  { fn: "min", label: "Minimum", group: "Statistics", needs: "number" },
  { fn: "max", label: "Maximum", group: "Statistics", needs: "number" },
  { fn: "p50", label: "p50 (median)", group: "Percentiles", needs: "number" },
  { fn: "p75", label: "p75", group: "Percentiles", needs: "number" },
  { fn: "p95", label: "p95", group: "Percentiles", needs: "number" },
  { fn: "p99", label: "p99", group: "Percentiles", needs: "number" },
]

/** Stroke dash per chart slot, so series stay distinct when chart colors are close. */
export const SERIES_DASHES: (string | undefined)[] = [undefined, "6 3", "2 3", "9 3 2 3", "1 4"]

export const NO_VALUE_LABEL = "(none)"
export const ALL_ROWS_LABEL = "All rows"
/** Chart series cap: the top four groups plus "Other" fill the five chart tokens. */
export const MAX_SERIES = 5

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
export const INTERVAL_PRESETS = [
  MINUTE,
  5 * MINUTE,
  15 * MINUTE,
  HOUR,
  3 * HOUR,
  6 * HOUR,
  12 * HOUR,
  DAY,
]
export const AUTO_BUCKETS = 60
export const MAX_BUCKETS = 240

export function aggregateDef(fn: AggregateFn): AggregateDef {
  return AGGREGATES.find((def) => def.fn === fn) ?? AGGREGATES[0]
}

export function fieldByKey(schema: FieldSchema, key: string | null | undefined) {
  return key ? schema.fields.find((field) => field.key === key) : undefined
}

/** Fields the function can read: none for count, any non-time field for count unique, number fields otherwise. */
export function fieldsFor(fn: AggregateFn, schema: FieldSchema): FieldDef[] {
  const { needs } = aggregateDef(fn)
  if (needs === "none") return []
  if (needs === "any") return schema.fields.filter((field) => field.kind !== "time")
  return schema.fields.filter((field) => field.kind === "number")
}

export function availableAggregates(schema: FieldSchema): AggregateDef[] {
  return AGGREGATES.filter(
    (def) => def.needs === "none" || fieldsFor(def.fn, schema).length > 0
  )
}

/** Keeps the field when it still applies to `fn`, otherwise takes the first that does. */
export function coerceVisualize(visualize: Visualize, schema: FieldSchema): Visualize {
  const available = availableAggregates(schema)
  const fn = available.some((def) => def.fn === visualize.fn)
    ? visualize.fn
    : "count"
  const candidates = fieldsFor(fn, schema)
  if (candidates.length === 0) return { fn }
  const field = candidates.some((f) => f.key === visualize.field)
    ? visualize.field
    : candidates[0].key
  return { fn, field }
}

export function defaultQuery(schema: FieldSchema): AggregateQuery {
  return {
    visualize: { fn: "count" },
    groupBy: null,
    sampleSort: { by: schema.timeField, dir: "desc" },
    groupSort: { by: "value", dir: "desc" },
    chart: "bar",
    interval: null,
  }
}

/** Repairs a query against the schema so a stale field key never reaches the views. */
export function normalizeQuery(query: AggregateQuery, schema: FieldSchema): AggregateQuery {
  const base = defaultQuery(schema)
  const groupField = fieldByKey(schema, query.groupBy)
  const groupBy = groupField?.kind === "text" ? groupField.key : null
  const sampleSort = fieldByKey(schema, query.sampleSort?.by)
    ? query.sampleSort
    : base.sampleSort
  const redundant =
    (query.groupSort?.by === "group" && groupBy === null) ||
    (query.groupSort?.by === "count" && query.visualize?.fn === "count")
  const groupSort = query.groupSort && !redundant ? query.groupSort : base.groupSort
  const interval =
    typeof query.interval === "number" && query.interval > 0 && Number.isFinite(query.interval)
      ? query.interval
      : null
  return {
    visualize: coerceVisualize(query.visualize ?? base.visualize, schema),
    groupBy,
    sampleSort,
    groupSort,
    chart: query.chart === "line" ? "line" : "bar",
    interval,
  }
}

export function sameQuery(a: AggregateQuery, b: AggregateQuery): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

/** The row's value when it is a finite number, otherwise null. */
export function numberAt(row: AggregateRow, key: string): number | null {
  const value = row[key]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

/** Linear interpolation between ranks; `sorted` ascending, `p` from 0 to 1. */
export function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null
  const position = Math.min(1, Math.max(0, p)) * (sorted.length - 1)
  const low = Math.floor(position)
  const high = Math.ceil(position)
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low)
}

/** What a bucket or group with no values shows: zero for additive counts, null (a gap) for the rest. */
export function emptyValue(fn: AggregateFn): number | null {
  return fn === "count" || fn === "count_unique" || fn === "sum" ? 0 : null
}

export function aggregateValue(
  rows: AggregateRow[],
  visualize: Visualize
): number | null {
  const { fn, field } = visualize
  if (fn === "count") return rows.length
  if (!field) return emptyValue(fn)
  if (fn === "count_unique") {
    const seen = new Set<string>()
    for (const row of rows) {
      const value = row[field]
      if (value !== null && value !== undefined && value !== "") seen.add(String(value))
    }
    return seen.size
  }
  const values: number[] = []
  for (const row of rows) {
    const value = numberAt(row, field)
    if (value !== null) values.push(value)
  }
  if (values.length === 0) return emptyValue(fn)
  if (fn === "sum") return values.reduce((a, b) => a + b, 0)
  if (fn === "avg") return values.reduce((a, b) => a + b, 0) / values.length
  if (fn === "min") return Math.min(...values)
  if (fn === "max") return Math.max(...values)
  values.sort((a, b) => a - b)
  return percentile(values, Number(fn.slice(1)) / 100)
}

/** Aggregates add up across groups, so a stacked bar total means something. */
export function isAdditive(fn: AggregateFn): boolean {
  return fn === "count" || fn === "sum"
}

export function aggregateLabel(visualize: Visualize, schema: FieldSchema): string {
  if (visualize.fn === "count") return `count(${schema.rowLabel ?? "rows"})`
  return `${visualize.fn}(${visualize.field ?? ""})`
}

/** Unit of the aggregate's value: the field's own, except for the counts. */
export function aggregateUnit(visualize: Visualize, schema: FieldSchema): string | undefined {
  if (visualize.fn === "count" || visualize.fn === "count_unique") return undefined
  return fieldByKey(schema, visualize.field)?.unit
}

export type GroupRow<T extends AggregateRow = AggregateRow> = {
  /** Group value, or "" when there is no grouping. */
  key: string
  label: string
  value: number | null
  count: number
  /** Chart color slot, 0 to MAX_SERIES - 1; the last slot is "Other" when groups overflow. */
  slot: number
  rows: T[]
}

export function groupLabelOf(row: AggregateRow, key: string): string {
  const value = row[key]
  return value === null || value === undefined || value === "" ? NO_VALUE_LABEL : String(value)
}

function compareNullable(a: number | null, b: number | null, dir: SortDir): number {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return dir === "asc" ? a - b : b - a
}

/** One row per group value (a single "All rows" group without grouping), sorted by `query.groupSort`. */
export function buildGroups<T extends AggregateRow>(
  rows: T[],
  query: AggregateQuery
): GroupRow<T>[] {
  const buckets = new Map<string, T[]>()
  for (const row of rows) {
    const key = query.groupBy ? groupLabelOf(row, query.groupBy) : ""
    const list = buckets.get(key)
    if (list) list.push(row)
    else buckets.set(key, [row])
  }
  const { by, dir } = query.groupSort
  const groups = [...buckets].map(([key, members]) => ({
    key,
    label: query.groupBy ? key : ALL_ROWS_LABEL,
    value: aggregateValue(members, query.visualize),
    count: members.length,
    slot: 0,
    rows: members,
  }))
  groups.sort((a, b) => {
    let order: number
    if (by === "group") order = a.label.localeCompare(b.label) * (dir === "asc" ? 1 : -1)
    else if (by === "count") order = compareNullable(a.count, b.count, dir)
    else order = compareNullable(a.value, b.value, dir)
    return order || a.label.localeCompare(b.label)
  })
  const overflow = groups.length > MAX_SERIES
  groups.forEach((group, index) => {
    group.slot = overflow ? Math.min(index, MAX_SERIES - 1) : index
  })
  return groups
}

export function sortSamples<T extends AggregateRow>(
  rows: T[],
  sort: AggregateQuery["sampleSort"],
  schema: FieldSchema
): T[] {
  const field = fieldByKey(schema, sort.by)
  const sorted = [...rows]
  const sign = sort.dir === "asc" ? 1 : -1
  sorted.sort((a, b) => {
    let order = 0
    if (field?.kind === "text") {
      order = groupLabelOf(a, sort.by).localeCompare(groupLabelOf(b, sort.by)) * sign
    } else if (field) {
      order = compareNullable(numberAt(a, sort.by), numberAt(b, sort.by), sort.dir)
    }
    return order || a.id.localeCompare(b.id)
  })
  return sorted
}

export function maxOf(rows: AggregateRow[], key: string): number {
  let max = 0
  for (const row of rows) max = Math.max(max, numberAt(row, key) ?? 0)
  return max
}

export function bucketStart(time: number, interval: number): number {
  return Math.floor(time / interval) * interval
}

function bucketsBetween(min: number, max: number, interval: number): number {
  return Math.floor(max / interval) - Math.floor(min / interval) + 1
}

/**
 * The bucket size to use for rows spanning `min` to `max`. Auto picks the smallest preset giving at
 * most AUTO_BUCKETS buckets; a requested size steps up through the presets until it gives at most
 * MAX_BUCKETS.
 */
export function resolveInterval(
  min: number,
  max: number,
  requested: number | null,
  presets: number[] = INTERVAL_PRESETS
): number {
  const limit = requested === null ? AUTO_BUCKETS : MAX_BUCKETS
  const from = requested ?? 0
  const candidates = presets.filter((preset) => preset >= from)
  if (requested !== null && !presets.includes(requested)) candidates.unshift(requested)
  for (const candidate of candidates) {
    if (bucketsBetween(min, max, candidate) <= limit) return candidate
  }
  return Math.max(DAY, Math.ceil((max - min + 1) / limit / DAY) * DAY)
}

/** Tick values from zero up to a round maximum at or above `max`. */
export function niceTicks(max: number, target = 4): number[] {
  if (!(max > 0) || !Number.isFinite(max)) return [0, 1]
  const raw = max / target
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= raw) ??
    10 * magnitude
  const count = Math.ceil(max / step - 1e-9)
  return Array.from({ length: count + 1 }, (_, i) => Number((i * step).toPrecision(12)))
}

export type ChartSeries = {
  key: string
  label: string
  slot: number
  values: (number | null)[]
}

export type ChartModel = {
  /** Start time of each bucket, ascending and continuous. */
  buckets: number[]
  interval: number
  series: ChartSeries[]
  yTicks: number[]
  yMax: number
  stacked: boolean
  /** Rows that had a valid time and so landed in a bucket. */
  rowCount: number
  hasValues: boolean
}

/**
 * Buckets rows over time into one series per group slot. `groups` null (or a single group) draws
 * one series over all rows; otherwise each slot becomes a series, and slots shared by several
 * groups ("Other") re-aggregate the union of their rows. Null when no row has a valid time.
 */
export function buildChart<T extends AggregateRow>(
  rows: T[],
  query: AggregateQuery,
  schema: FieldSchema,
  groups: GroupRow<T>[] | null
): ChartModel | null {
  const timed = rows.filter((row) => numberAt(row, schema.timeField) !== null)
  if (timed.length === 0) return null
  let min = Infinity
  let max = -Infinity
  for (const row of timed) {
    const time = numberAt(row, schema.timeField) as number
    min = Math.min(min, time)
    max = Math.max(max, time)
  }
  const interval = resolveInterval(min, max, query.interval)
  const first = bucketStart(min, interval)
  const count = bucketsBetween(min, max, interval)
  const buckets = Array.from({ length: count }, (_, i) => first + i * interval)

  const sources: { key: string; label: string; slot: number; rows: T[] }[] = []
  if (!groups || groups.length <= 1) {
    sources.push({
      key: groups?.[0]?.key ?? "",
      label: groups?.[0]?.label ?? aggregateLabel(query.visualize, schema),
      slot: 0,
      rows: timed,
    })
  } else {
    const overflow = groups.length > MAX_SERIES
    for (const group of groups) {
      const isOther = overflow && group.slot === MAX_SERIES - 1
      const existing = sources.find((source) => source.slot === group.slot)
      if (existing) for (const row of group.rows) existing.rows.push(row)
      else
        sources.push({
          key: isOther ? "other" : group.key,
          label: isOther ? "Other" : group.label,
          slot: group.slot,
          rows: [...group.rows],
        })
    }
  }

  const series: ChartSeries[] = sources.map((source) => {
    const perBucket: T[][] = Array.from({ length: count }, () => [])
    for (const row of source.rows) {
      const time = numberAt(row, schema.timeField)
      if (time === null) continue
      perBucket[Math.floor(time / interval) - Math.floor(first / interval)].push(row)
    }
    return {
      key: source.key,
      label: source.label,
      slot: source.slot,
      values: perBucket.map((members) =>
        members.length === 0
          ? emptyValue(query.visualize.fn)
          : aggregateValue(members, query.visualize)
      ),
    }
  })

  const stacked = query.chart === "bar" && series.length > 1 && isAdditive(query.visualize.fn)
  let top = 0
  for (let i = 0; i < count; i++) {
    if (stacked) {
      top = Math.max(top, series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0))
    } else {
      for (const s of series) top = Math.max(top, s.values[i] ?? 0)
    }
  }
  const yTicks = niceTicks(top)
  return {
    buckets,
    interval,
    series,
    yTicks,
    yMax: yTicks[yTicks.length - 1],
    stacked,
    rowCount: timed.length,
    hasValues: series.some((s) => s.values.some((value) => value !== null)),
  }
}

export function formatNumber(value: number): string {
  const abs = Math.abs(value)
  const trim = (n: number) => Number(n.toFixed(1)).toString()
  if (abs >= 1_000_000) return `${trim(value / 1_000_000)}M`
  if (abs >= 10_000) return `${trim(value / 1000)}k`
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: abs >= 100 ? 0 : abs >= 10 ? 1 : 2,
  }).format(value)
}

export function formatValue(value: number | null, unit?: string): string {
  if (value === null) return "—"
  return unit ? `${formatNumber(value)} ${unit}` : formatNumber(value)
}

export function formatInterval(interval: number): string {
  if (interval % DAY === 0) return interval === DAY ? "1 day" : `${interval / DAY} days`
  if (interval % HOUR === 0) return interval === HOUR ? "1 hour" : `${interval / HOUR} hours`
  const minutes = interval / MINUTE
  return minutes === 1 ? "1 minute" : `${Number(minutes.toFixed(1))} minutes`
}

const DAY_FORMAT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" })
const CLOCK_FORMAT = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

/** "Oct 21" for day buckets; a clock time otherwise, with the date added when `withDate`. */
export function formatBucket(time: number, interval: number, withDate: boolean): string {
  const date = new Date(time)
  if (interval >= DAY) return DAY_FORMAT.format(date)
  const clock = CLOCK_FORMAT.format(date)
  return withDate ? `${DAY_FORMAT.format(date)} ${clock}` : clock
}

export function formatDateTime(time: number): string {
  const date = new Date(time)
  return `${DAY_FORMAT.format(date)} ${CLOCK_FORMAT.format(date)}`
}
