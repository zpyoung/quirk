import { useMemo } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Table, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { Certainty, CustomCell, CustomColumn, CustomView as CustomViewData, LogicSpec, ReviewState } from '../spec-types'
import { effectivePlacement } from '../review-state'
import { escapeRegExp, ItemRef } from './item-links'
import { CertaintyToken, SpecMarkdown } from './shared'
import type { ViewProps } from './view-props'

type Row = CustomViewData['rows'][number]

function cellText(cell: CustomCell | undefined): { text: string; certainty?: Certainty } | null {
  if (cell === undefined || Array.isArray(cell)) return null
  return typeof cell === 'string' ? { text: cell } : cell
}

function cellItems(cell: CustomCell | undefined): string[] {
  return Array.isArray(cell) ? cell : []
}

/** Every piece of an item's text a quote could come from. */
function quotableText(spec: LogicSpec, id: string): string | null {
  const scenario = spec.scenarios.find((item) => item.id === id)
  if (scenario) return [scenario.given, scenario.when, scenario.then, ...scenario.alternatives].join('\n')
  const requirement = spec.requirements.find((item) => item.id === id)
  if (requirement) return [requirement.text, requirement.summary, requirement.detail].join('\n')
  const constraint = spec.constraints.find((item) => item.id === id)
  if (constraint) return constraint.text
  const behavior = spec.behaviors.find((item) => item.id === id)
  if (behavior) return [behavior.rule, behavior.detail ?? ''].join('\n')
  const assumption = spec.assumptions.find((item) => item.id === id)
  if (assumption) return [assumption.claim, assumption.basis, assumption.meaning].join('\n')
  const spot = spec.blindSpots.find((item) => item.id === id)
  if (spot) return [spot.title, spot.detail].join('\n')
  return null
}

/** `<...>` in a quote is a placeholder matching any text; `render_spec.py` applies the same rule when it warns. */
export function quotePattern(text: string): RegExp {
  const parts = text.split(/<[^>]+>/).map(escapeRegExp)
  return new RegExp(parts.join('.+?'))
}

/** Items that a quote cell's row points at but that word the quote differently. */
export function quoteDrift(spec: LogicSpec, column: CustomColumn, row: Row): string[] {
  const text = cellText(row.cells[column.key])?.text
  if (!text || !column.checkedAgainst) return []
  const pattern = quotePattern(text)
  return cellItems(row.cells[column.checkedAgainst]).filter((id) => {
    const source = quotableText(spec, id)
    return source !== null && !pattern.test(source)
  })
}

function ItemsCell({ ids, spec, state }: { ids: string[]; spec: LogicSpec; state: ReviewState }) {
  if (ids.length === 0) return <Text type="supporting">—</Text>
  return (
    <HStack gap={1} wrap="wrap">
      {ids.map((id) => {
        const requirement = spec.requirements.find((item) => item.id === id)
        // follow the scope board, so a view never reads as if an out-of-scope requirement still applies
        const isOut = requirement !== undefined && effectivePlacement(state, requirement) === 'out'
        return (
          <Text key={id} type={isOut ? 'supporting' : undefined}>
            <ItemRef id={id} />{isOut ? ' (out of scope)' : ''}
          </Text>
        )
      })}
    </HStack>
  )
}

function renderCell(column: CustomColumn, row: Row, spec: LogicSpec, state: ReviewState, drift: string[]) {
  const cell = row.cells[column.key]
  if (column.type === 'items') return <ItemsCell ids={cellItems(cell)} spec={spec} state={state} />
  const value = cellText(cell)
  if (!value) return <Text type="supporting">—</Text>
  const certainty = value.certainty ? <HStack><CertaintyToken certainty={value.certainty} /></HStack> : null
  if (column.type === 'status') {
    const color = column.statuses && Object.hasOwn(column.statuses, value.text) ? column.statuses[value.text] : 'default'
    return <VStack gap={1}><HStack><Token size="sm" color={color} label={value.text} /></HStack>{certainty}</VStack>
  }
  if (column.type === 'quote') {
    return (
      <VStack gap={1}>
        <Text weight="semibold">{value.text}</Text>
        {drift.length ? (
          <HStack gap={1} align="center" wrap="wrap">
            <Token size="sm" color="orange" label="Worded differently" />
            <Text type="supporting">{`in ${drift.join(', ')}`}</Text>
          </HStack>
        ) : null}
        {certainty}
      </VStack>
    )
  }
  return (
    <VStack gap={1}>
      {column.type === 'markdown' ? <SpecMarkdown compact>{value.text}</SpecMarkdown> : <Text>{value.text}</Text>}
      {certainty}
    </VStack>
  )
}

/** One task-specific table defined entirely by the spec's data; every custom view renders through this. */
export function CustomView({ spec, state, viewId }: ViewProps & { viewId: string }) {
  const view = spec.views?.custom?.find((item) => item.id === viewId)
  const drift = useMemo(() => {
    const byCell = new Map<string, string[]>()
    for (const column of view?.columns ?? []) {
      if (column.type !== 'quote') continue
      for (const row of view?.rows ?? []) {
        const ids = quoteDrift(spec, column, row)
        if (ids.length) byCell.set(`${column.key}\u0000${row.id}`, ids)
      }
    }
    return byCell
  }, [spec, view])
  if (!view) return null
  const driftRows = drift.size
  const columns: TableColumn<Row>[] = view.columns.map((column) => ({
    key: column.key,
    header: column.label,
    width: proportional(column.type === 'items' || column.type === 'status' ? 1 : 2),
    renderCell: (row) => renderCell(column, row, spec, state, drift.get(`${column.key}\u0000${row.id}`) ?? []),
  }))
  return (
    <VStack gap={4}>
      <VStack gap={2}>
        <Heading level={2}>{view.title}</Heading>
        {view.intro ? <SpecMarkdown>{view.intro}</SpecMarkdown> : null}
      </VStack>
      {driftRows > 0 ? (
        <Banner
          status="warning"
          title={`${driftRows} quote${driftRows === 1 ? ' is' : 's are'} worded differently where used`}
          description="Pick one wording, then dispute or update the items that differ."
          collapsible={false}
        />
      ) : null}
      <Table data={view.rows} columns={columns} idKey="id" verticalAlign="top" dividers="rows" />
    </VStack>
  )
}
