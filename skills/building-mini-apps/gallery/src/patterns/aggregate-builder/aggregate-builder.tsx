import { useMemo, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import {
  aggregateLabel,
  aggregateUnit,
  buildChart,
  buildGroups,
  defaultQuery,
  fieldByKey,
  maxOf,
  normalizeQuery,
  sameQuery,
  sortSamples,
} from "./aggregate"
import { QueryRail } from "./query-rail"
import { ResultsTable } from "./results-table"
import { SeriesChart } from "./series-chart"
import type {
  AggregateQuery,
  AggregateRow,
  FieldSchema,
  GroupSortBy,
  ResultsTab,
} from "./types"

// the chart is role=slider and the line/bar toggle is role=radio; the hook skips both unless listed
const KEY_TARGET_ROLES = ["slider", "radio"] as const

export type AggregateBuilderProps<T extends AggregateRow> = {
  rows: T[]
  schema: FieldSchema
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  /** Controlled query; omit for internal state. */
  query?: AggregateQuery
  onQueryChange?: (query: AggregateQuery) => void
  /** Starting point for internal state and for Reset. */
  initialQuery?: Partial<AggregateQuery>
  /** Controlled tab; omit for internal state (starts on "samples"). */
  tab?: ResultsTab
  onTabChange?: (tab: ResultsTab) => void
  /** Makes each sample's ID a button that calls this. */
  onOpenRow?: (row: T) => void
  sampleLimit?: number
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

/**
 * A rail of Visualize, Group by and Sort by controls driving a chart over time buckets and a
 * Samples / Aggregates table. Aggregation is pure over `rows` and `schema`; the block never reads
 * a store.
 */
export function AggregateBuilder<T extends AggregateRow>({
  rows,
  schema,
  status = "ready",
  error,
  onRetry,
  query: controlledQuery,
  onQueryChange,
  initialQuery,
  tab: controlledTab,
  onTabChange,
  onOpenRow,
  sampleLimit = 100,
  emptyTitle = "No rows to chart",
  emptyAction,
  "aria-label": ariaLabel = "Aggregate builder",
}: AggregateBuilderProps<T>) {
  const rootRef = useRef<HTMLDivElement>(null)
  const aggregateRef = useRef<HTMLButtonElement>(null)
  const groupRef = useRef<HTMLButtonElement>(null)
  const sortRef = useRef<HTMLButtonElement>(null)

  const base = normalizeQuery({ ...defaultQuery(schema), ...initialQuery }, schema)
  const [internalQuery, setInternalQuery] = useState(base)
  const [internalTab, setInternalTab] = useState<ResultsTab>("samples")
  const rawQuery = controlledQuery ?? internalQuery
  const query = useMemo(() => normalizeQuery(rawQuery, schema), [rawQuery, schema])
  const tab = controlledTab ?? internalTab

  const update = (patch: Partial<AggregateQuery>) => {
    const next = normalizeQuery({ ...query, ...patch }, schema)
    setInternalQuery(next)
    onQueryChange?.(next)
  }
  const changeTab = (next: ResultsTab) => {
    setInternalTab(next)
    onTabChange?.(next)
  }

  const onSort = (by: string) => {
    if (tab === "samples") {
      const same = query.sampleSort.by === by
      const kind = fieldByKey(schema, by)?.kind
      update({
        sampleSort: {
          by,
          dir: same
            ? query.sampleSort.dir === "asc" ? "desc" : "asc"
            : kind === "text" ? "asc" : "desc",
        },
      })
    } else {
      const same = query.groupSort.by === by
      update({
        groupSort: {
          by: by as GroupSortBy,
          dir: same
            ? query.groupSort.dir === "asc" ? "desc" : "asc"
            : by === "group" ? "asc" : "desc",
        },
      })
    }
  }

  const ready = status === "ready" && rows.length > 0
  const groupingApplies = tab === "aggregates" && query.groupBy !== null

  const samples = useMemo(
    () => sortSamples(rows, query.sampleSort, schema),
    [rows, query.sampleSort, schema]
  )
  const groups = useMemo(
    () => buildGroups(rows, { ...query, groupBy: tab === "aggregates" ? query.groupBy : null }),
    [rows, query, tab]
  )
  const chart = useMemo(
    () => buildChart(rows, query, schema, groups),
    [rows, query, schema, groups]
  )
  const barMax = schema.barField ? maxOf(rows, schema.barField) : 0

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) return true
    return target instanceof Node && rootRef.current?.contains(target) === true
  }
  useHotkeys(
    "v",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      aggregateRef.current?.focus()
    },
    { enabled: ready, enableOnFormTags: KEY_TARGET_ROLES }
  )
  useHotkeys(
    "g",
    (event) => {
      if (!inScope(event) || tab !== "aggregates") return
      event.preventDefault()
      groupRef.current?.focus()
    },
    { enabled: ready, enableOnFormTags: KEY_TARGET_ROLES }
  )
  useHotkeys(
    "s",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      sortRef.current?.focus()
    },
    { enabled: ready, enableOnFormTags: KEY_TARGET_ROLES }
  )
  useHotkeys(
    "1,2",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      changeTab(event.key === "1" ? "samples" : "aggregates")
    },
    { enabled: ready, enableOnFormTags: KEY_TARGET_ROLES }
  )
  useHotkeys(
    "c",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      update({ chart: query.chart === "bar" ? "line" : "bar" })
    },
    { enabled: ready, enableOnFormTags: KEY_TARGET_ROLES }
  )

  const groupField = fieldByKey(schema, query.groupBy)
  const title = `${aggregateLabel(query.visualize, schema)}${
    groupingApplies && groupField ? ` by ${groupField.label.toLowerCase()}` : ""
  }`

  let results
  if (status === "loading") {
    results = <LoadingState label="Loading rows" />
  } else if (status === "error") {
    results = <ErrorState error={error ?? new Error("The rows could not be loaded.")} onRetry={onRetry} />
  } else if (rows.length === 0) {
    results = (
      <EmptyState
        title={emptyTitle}
        description="Rows appear here once the log has entries."
        action={
          emptyAction ? (
            <Button size="sm" variant="outline" onClick={emptyAction.onClick}>
              {emptyAction.label}
            </Button>
          ) : undefined
        }
      />
    )
  } else {
    results = (
      <>
        <SeriesChart
          model={chart}
          title={title}
          unit={aggregateUnit(query.visualize, schema)}
          query={query}
          onChange={update}
          noValuesLabel={`No values for ${aggregateLabel(query.visualize, schema)}`}
        />
        <ResultsTable
          tab={tab}
          onTabChange={changeTab}
          schema={schema}
          query={query}
          samples={samples}
          groups={groups}
          sampleLimit={sampleLimit}
          barMax={barMax}
          onSort={onSort}
          onOpenRow={onOpenRow}
        />
      </>
    )
  }

  return (
    <div
      ref={rootRef}
      role="region"
      aria-label={ariaLabel}
      className="@container h-full min-h-0 bg-background text-foreground"
    >
      <div
        className={cn(
          "grid h-full min-h-[30rem] grid-cols-1",
          "@2xl:grid-cols-[36%_minmax(0,1fr)]"
        )}
      >
        <div className="min-w-0 border-b @2xl:overflow-auto @2xl:border-r @2xl:border-b-0">
          <QueryRail
            schema={schema}
            query={query}
            tab={tab}
            disabled={status !== "ready"}
            canReset={!sameQuery(query, base)}
            onChange={update}
            onReset={() => update(base)}
            aggregateRef={aggregateRef}
            groupRef={groupRef}
            sortRef={sortRef}
          />
        </div>
        <div className="min-w-0 @2xl:overflow-auto">{results}</div>
      </div>
    </div>
  )
}
