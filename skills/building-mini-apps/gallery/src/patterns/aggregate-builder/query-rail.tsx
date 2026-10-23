import type { Ref } from "react"
import { RotateCcwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import { AggregatePicker } from "./aggregate-picker"
import {
  aggregateLabel,
  availableAggregates,
  coerceVisualize,
  fieldByKey,
  fieldsFor,
} from "./aggregate"
import { FieldPicker, type FieldOption } from "./field-picker"
import type {
  AggregateFn,
  AggregateQuery,
  FieldSchema,
  GroupSortBy,
  ResultsTab,
  SortDir,
} from "./types"

const ROWS_VALUE = "__rows"

const DIRECTIONS: FieldOption[] = [
  { value: "desc", label: "Desc" },
  { value: "asc", label: "Asc" },
]

function Heading({ id, children }: { id: string; children: string }) {
  return (
    <h3 id={id} className="mb-1.5 text-xs font-medium text-foreground">
      {children}
    </h3>
  )
}

/**
 * The left rail: Visualize (aggregate and field), Group By and Sort By. Edits go out as patches to
 * the query; `tab` decides which sort the Sort By controls edit and whether Group By applies.
 */
export function QueryRail({
  schema,
  query,
  tab,
  disabled,
  canReset,
  onChange,
  onReset,
  aggregateRef,
  groupRef,
  sortRef,
}: {
  schema: FieldSchema
  query: AggregateQuery
  tab: ResultsTab
  disabled?: boolean
  canReset: boolean
  onChange: (patch: Partial<AggregateQuery>) => void
  onReset: () => void
  aggregateRef?: Ref<HTMLButtonElement>
  groupRef?: Ref<HTMLButtonElement>
  sortRef?: Ref<HTMLButtonElement>
}) {
  const { visualize } = query
  const fieldOptions = fieldsFor(visualize.fn, schema).map<FieldOption>((field) => ({
    value: field.key,
    label: field.label,
    kind: field.kind,
  }))
  const rowLabel = schema.rowLabel ?? "rows"
  const groupFields = schema.fields
    .filter((field) => field.kind === "text")
    .map<FieldOption>((field) => ({ value: field.key, label: field.label, kind: "text" }))
  const groupingApplies = tab === "aggregates"
  const groupField = fieldByKey(schema, query.groupBy)

  let sortOptions: FieldOption[]
  let sortBy: string
  let sortDir: SortDir
  if (tab === "samples") {
    sortOptions = schema.fields.map((field) => ({
      value: field.key,
      label: field.label,
      kind: field.kind,
    }))
    sortBy = query.sampleSort.by
    sortDir = query.sampleSort.dir
  } else {
    sortOptions = [{ value: "value", label: aggregateLabel(visualize, schema) }]
    if (visualize.fn !== "count") {
      sortOptions.push({ value: "count", label: `count(${rowLabel})` })
    }
    if (groupField) sortOptions.push({ value: "group", label: groupField.label })
    sortBy = query.groupSort.by
    sortDir = query.groupSort.dir
  }

  const changeAggregate = (fn: AggregateFn) =>
    onChange({ visualize: coerceVisualize({ fn, field: visualize.field }, schema) })

  const changeSort = (patch: { by?: string; dir?: SortDir }) => {
    if (tab === "samples") {
      onChange({ sampleSort: { ...query.sampleSort, ...patch } })
    } else {
      onChange({
        groupSort: {
          by: (patch.by as GroupSortBy | undefined) ?? query.groupSort.by,
          dir: patch.dir ?? query.groupSort.dir,
        },
      })
    }
  }

  return (
    <div className="flex flex-col gap-5 p-3" role="group" aria-label="Query">
      <section aria-labelledby="aggregate-builder-visualize">
        <Heading id="aggregate-builder-visualize">Visualize</Heading>
        <div className="grid grid-cols-2 gap-2">
          <AggregatePicker
            value={visualize.fn}
            onChange={changeAggregate}
            options={availableAggregates(schema)}
            disabled={disabled}
            triggerRef={aggregateRef}
          />
          {visualize.fn === "count" ? (
            <FieldPicker
              label="Field"
              value={ROWS_VALUE}
              onChange={() => {}}
              options={[{ value: ROWS_VALUE, label: rowLabel }]}
              disabled
            />
          ) : (
            <FieldPicker
              label="Field"
              value={visualize.field ?? null}
              onChange={(field) =>
                onChange({ visualize: { fn: visualize.fn, field: field ?? undefined } })
              }
              options={fieldOptions}
              disabled={disabled}
            />
          )}
        </div>
      </section>

      <section aria-labelledby="aggregate-builder-group">
        <Heading id="aggregate-builder-group">Group by</Heading>
        <FieldPicker
          label="Group by field"
          value={query.groupBy}
          onChange={(field) => onChange({ groupBy: field })}
          options={groupFields}
          noneLabel="None"
          disabled={disabled || !groupingApplies}
          triggerRef={groupRef}
        />
        {groupingApplies ? null : (
          <p className="mt-1 text-xs text-muted-foreground">
            Samples are not grouped. Switch to Aggregates to group.
          </p>
        )}
      </section>

      <section aria-labelledby="aggregate-builder-sort">
        <Heading id="aggregate-builder-sort">Sort by</Heading>
        <div className="grid grid-cols-[minmax(0,1fr)_5rem] gap-2">
          <FieldPicker
            label="Sort by field"
            value={sortBy}
            onChange={(by) => by && changeSort({ by })}
            options={sortOptions}
            disabled={disabled}
            triggerRef={sortRef}
          />
          <FieldPicker
            label="Sort direction"
            value={sortDir}
            onChange={(dir) => dir && changeSort({ dir: dir as SortDir })}
            options={DIRECTIONS}
            disabled={disabled}
          />
        </div>
      </section>

      {canReset ? (
        <Button variant="outline" size="sm" onClick={onReset} className="self-start">
          <RotateCcwIcon aria-hidden />
          Reset
        </Button>
      ) : null}
    </div>
  )
}
