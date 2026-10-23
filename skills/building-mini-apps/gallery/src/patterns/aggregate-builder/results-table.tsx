import type { ReactNode } from "react"
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import {
  MAX_SERIES,
  SERIES_DASHES,
  aggregateLabel,
  aggregateUnit,
  fieldByKey,
  formatDateTime,
  formatNumber,
  formatValue,
  groupLabelOf,
  numberAt,
  timeAt,
  type GroupRow,
} from "./aggregate"
import type {
  AggregateQuery,
  AggregateRow,
  FieldDef,
  FieldSchema,
  ResultsTab,
  SortDir,
} from "./types"

const slotColor = (slot: number) => `var(--chart-${slot + 1})`
const NUMERIC = "text-right font-[family-name:var(--mini-font-data)] tabular-nums"

function SortHead({
  label,
  active,
  dir,
  align,
  onSort,
}: {
  label: string
  active: boolean
  dir: SortDir
  align?: "right"
  onSort: () => void
}) {
  const Arrow = dir === "asc" ? ArrowUpIcon : ArrowDownIcon
  return (
    <TableHead
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={cn(align === "right" && "text-right")}
    >
      <button
        type="button"
        onClick={onSort}
        className={cn(
          "inline-flex items-center gap-1 rounded-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
        )}
      >
        {label}
        {active ? <Arrow className="size-3" aria-hidden /> : null}
      </button>
    </TableHead>
  )
}

function columnLabel(field: FieldDef): string {
  return field.unit ? `${field.label} (${field.unit})` : field.label
}

function cellFor(field: FieldDef, row: AggregateRow, barMax: number, isBar: boolean): ReactNode {
  if (field.kind === "time") {
    const time = timeAt(row, field.key)
    return time === null ? "—" : formatDateTime(time)
  }
  if (field.kind === "number") {
    const value = numberAt(row, field.key)
    if (value === null) return "—"
    if (!isBar) return formatNumber(value)
    const share = barMax > 0 ? Math.min(100, (value / barMax) * 100) : 0
    return (
      <span className="inline-flex items-center justify-end gap-2">
        <span>{formatNumber(value)}</span>
        <span aria-hidden className="h-2 w-14 overflow-hidden rounded-sm bg-muted">
          <span className="block h-full bg-(--chart-1)" style={{ width: `${share}%` }} />
        </span>
      </span>
    )
  }
  return groupLabelOf(row, field.key)
}

/**
 * The Samples and Aggregates tabs. Samples lists raw rows with the schema's bar field drawn as a
 * bar; Aggregates lists one row per group with a swatch matching its chart series. Headers sort.
 */
export function ResultsTable<T extends AggregateRow>({
  tab,
  onTabChange,
  schema,
  query,
  samples,
  groups,
  sampleLimit,
  barMax,
  onSort,
  onOpenRow,
}: {
  tab: ResultsTab
  onTabChange: (tab: ResultsTab) => void
  schema: FieldSchema
  query: AggregateQuery
  samples: T[]
  groups: GroupRow<T>[]
  sampleLimit: number
  barMax: number
  /** `by` is a field key on Samples and "value", "count" or "group" on Aggregates. */
  onSort: (by: string) => void
  onOpenRow?: (row: T) => void
}) {
  const shown = samples.slice(0, sampleLimit)
  const { visualize } = query
  const groupField = fieldByKey(schema, query.groupBy)
  const unit = aggregateUnit(visualize, schema)
  const overflow = groups.length > MAX_SERIES
  const rowLabel = schema.rowLabel ?? "rows"

  return (
    <Tabs
      value={tab}
      onValueChange={(next) => onTabChange(next as ResultsTab)}
      className="gap-0"
    >
      <div className="flex items-center border-y px-3 py-1.5">
        <TabsList variant="line" aria-label="Results">
          <TabsTrigger value="samples">Samples</TabsTrigger>
          <TabsTrigger value="aggregates">Aggregates</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="samples" className="m-0">
        <Table className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              {schema.fields.map((field) => (
                <SortHead
                  key={field.key}
                  label={columnLabel(field)}
                  active={query.sampleSort.by === field.key}
                  dir={query.sampleSort.dir}
                  align={field.kind === "number" ? "right" : undefined}
                  onSort={() => onSort(field.key)}
                />
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-[family-name:var(--mini-font-data)] text-xs">
                  {onOpenRow ? (
                    <button
                      type="button"
                      onClick={() => onOpenRow(row)}
                      className="rounded-sm underline-offset-2 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      {row.id}
                    </button>
                  ) : (
                    row.id
                  )}
                </TableCell>
                {schema.fields.map((field) => (
                  <TableCell
                    key={field.key}
                    className={cn(
                      "max-w-36 truncate",
                      field.kind === "number" && NUMERIC,
                      field.kind === "time" && "whitespace-nowrap text-muted-foreground"
                    )}
                  >
                    {cellFor(field, row, barMax, field.key === schema.barField)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="px-3 py-2 text-xs text-muted-foreground">
          {samples.length > shown.length
            ? `Showing the first ${shown.length} of ${samples.length} ${rowLabel}`
            : `${samples.length} ${rowLabel}`}
        </p>
      </TabsContent>

      <TabsContent value="aggregates" className="m-0">
        <Table className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <span className="sr-only">Chart color</span>
              </TableHead>
              {groupField ? (
                <SortHead
                  label={groupField.label}
                  active={query.groupSort.by === "group"}
                  dir={query.groupSort.dir}
                  onSort={() => onSort("group")}
                />
              ) : (
                <TableHead>Group</TableHead>
              )}
              <SortHead
                label={aggregateLabel(visualize, schema)}
                active={query.groupSort.by === "value"}
                dir={query.groupSort.dir}
                align="right"
                onSort={() => onSort("value")}
              />
              {visualize.fn === "count" ? null : (
                <SortHead
                  label={`count(${rowLabel})`}
                  active={query.groupSort.by === "count"}
                  dir={query.groupSort.dir}
                  align="right"
                  onSort={() => onSort("count")}
                />
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((group) => (
              <TableRow key={group.key || "all"}>
                <TableCell>
                  <svg
                    width="18"
                    height="8"
                    aria-hidden
                    className="block"
                  >
                    <title>
                      {overflow && group.slot === MAX_SERIES - 1
                        ? "Drawn as Other in the chart"
                        : "Chart color"}
                    </title>
                    {query.chart === "line" ? (
                      <line
                        x1="0"
                        x2="18"
                        y1="4"
                        y2="4"
                        strokeWidth="2"
                        strokeDasharray={SERIES_DASHES[group.slot]}
                        style={{ stroke: slotColor(group.slot) }}
                      />
                    ) : (
                      <rect width="18" height="8" rx="1" style={{ fill: slotColor(group.slot) }} />
                    )}
                  </svg>
                </TableCell>
                <TableCell className="max-w-48 truncate">{group.label}</TableCell>
                <TableCell className={NUMERIC}>{formatValue(group.value, unit)}</TableCell>
                {visualize.fn === "count" ? null : (
                  <TableCell className={NUMERIC}>{formatNumber(group.count)}</TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="px-3 py-2 text-xs text-muted-foreground">
          {groups.length} {groups.length === 1 ? "group" : "groups"}
          {overflow ? `. The ${groups.length - MAX_SERIES + 1} lowest are drawn as Other.` : ""}
        </p>
      </TabsContent>
    </Tabs>
  )
}
