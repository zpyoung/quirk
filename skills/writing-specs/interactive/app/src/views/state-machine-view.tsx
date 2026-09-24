import { useState, type ReactNode } from 'react'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Heading } from '@astryxdesign/core/Heading'
import { Table, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { activeBlindSpots } from '../review-state'
import type { BlindSpot, StateMachine, StateMachineTransition } from '../spec-types'
import { StateMachineDetailDialog } from './state-machine-detail'
import { StateMachineDiagram, ACCENT, MUTED, OFF } from './state-machine-diagram'
import { builtColor, builtLabel, nodeLabels, useMachineLayout, type StateMachineSelection, type TableRow } from './state-machine-model'
import { ClaudeField, ClaudeWroteToken, ItemReference } from './shared'
import type { ViewProps } from './view-props'

// A stable identity so the layout effect doesn't re-run every render when no state machine is defined.
const EMPTY_MACHINE: StateMachine = { states: [], transitions: [] }

function ReqIds({ ids }: { ids: string[] }) {
  return ids.length > 0 ? <Text>{ids.join(', ')}</Text> : <Text type="supporting">—</Text>
}

function ArrowSwatch({ color, dashed }: { color: string; dashed?: boolean }) {
  return (
    <svg width={28} height={12} viewBox="0 0 28 12" aria-hidden="true">
      <line x1={1} y1={6} x2={19} y2={6} stroke={color} strokeWidth={1.5} strokeDasharray={dashed ? '4,3' : undefined} />
      <polygon points="17,2 26,6 17,10" fill={color} />
    </svg>
  )
}

function ChipSwatch({ active }: { active: boolean }) {
  return (
    <svg width={28} height={16} viewBox="0 0 28 16" aria-hidden="true">
      <rect x={2} y={1} width={24} height={14} rx={4} fill={active ? 'var(--color-error-muted)' : 'var(--color-background-card)'} stroke={active ? 'var(--color-error)' : OFF} strokeDasharray={active ? undefined : '3,2'} />
    </svg>
  )
}

function LegendItem({ children, label }: { children: ReactNode; label: string }) {
  return (
    <HStack gap={1} align="center">
      {children}
      <Text type="supporting">{label}</Text>
    </HStack>
  )
}

function Legend() {
  return (
    <HStack gap={4} align="center" wrap="wrap">
      <Text type="label" color="secondary">Legend</Text>
      <LegendItem label="Spec rule, in scope"><ArrowSwatch color={MUTED} /></LegendItem>
      <LegendItem label="Out of scope, not built"><ArrowSwatch color={OFF} dashed /></LegendItem>
      <LegendItem label="Transition into or out of a focal state"><ArrowSwatch color={ACCENT} /></LegendItem>
      <LegendItem label="Blind spot, click for details"><ChipSwatch active /></LegendItem>
      <LegendItem label="Blind spot cleared by your scope"><ChipSwatch active={false} /></LegendItem>
    </HStack>
  )
}

/** The spec's state machine, its transitions, and its blind spots, so the reviewer can check the states directly against the spec. */
export function StateMachineView(props: ViewProps) {
  const [selection, setSelection] = useState<StateMachineSelection | null>(null)
  const { spec, state } = props
  const machine = spec.views?.stateMachine
  const { layout, error } = useMachineLayout(machine ?? EMPTY_MACHINE)
  if (!machine) return null
  const labels = nodeLabels(machine)
  const relevantBlindSpots = spec.blindSpots.filter((spot) => machine.transitions.some((transition) => transition.blindSpot === spot.id))
  const activeIds = new Set(activeBlindSpots(state, spec).map((spot) => spot.id))

  const columns: TableColumn<TableRow<StateMachineTransition>>[] = [
    { key: 'from', header: 'From', width: proportional(2), renderCell: (row) => <Text>{labels.get(row.from) ?? row.from}</Text> },
    {
      key: 'event',
      header: 'Event',
      width: proportional(4),
      renderCell: (row) => (
        <VStack gap={0.5}>
          <Text>{row.event}</Text>
          <HStack><ClaudeWroteToken /></HStack>
        </VStack>
      ),
    },
    { key: 'to', header: 'To', width: proportional(2), renderCell: (row) => <Text>{labels.get(row.to) ?? row.to}</Text> },
    { key: 'reqs', header: 'Requirements', width: proportional(2), renderCell: (row) => <ReqIds ids={row.reqs} /> },
    {
      key: 'built',
      header: 'Built?',
      width: proportional(2),
      renderCell: (row) => <Token size="sm" color={builtColor(spec, state, row)} label={builtLabel(spec, state, row)} />,
    },
  ]

  const blindSpotColumns: TableColumn<TableRow<BlindSpot>>[] = [
    { key: 'id', header: 'ID', width: proportional(1), renderCell: (row) => <Text type="label">{row.id}</Text> },
    {
      key: 'what',
      header: 'What diverges',
      width: proportional(4),
      renderCell: (row) => (
        <VStack gap={0.5}>
          <Text weight="medium">{row.title}</Text>
          <ClaudeField label="Detail">{row.detail}</ClaudeField>
        </VStack>
      ),
    },
    {
      key: 'sources',
      header: 'Derived from',
      width: proportional(2),
      renderCell: (row) => (
        <VStack gap={1}>
          {row.sources.map((id) => <ItemReference key={id} spec={spec} id={id} />)}
        </VStack>
      ),
    },
    {
      key: 'active',
      header: 'Active now?',
      width: proportional(2),
      renderCell: (row) => {
        const active = activeIds.has(row.id)
        return <Token size="sm" color={active ? 'red' : 'gray'} label={active ? 'Active' : 'Cleared by your placement'} />
      },
    },
  ]

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>State machine</Heading>
        <Text type="supporting" as="p">
          What the states show as events happen, drawn from the spec's transitions. Each arrow is a spec rule, labelled with the requirements behind
          it, and turns dashed grey when you move those requirements out of scope. Chips mark blind spots, where two views of the system disagree;
          click any arrow or chip to open its details, and the full lists are below the diagram.
        </Text>
      </VStack>

      {layout ? (
        <VStack gap={2}>
          <StateMachineDiagram machine={machine} spec={spec} state={state} layout={layout} onSelect={setSelection} />
          <Legend />
        </VStack>
      ) : (
        <Card padding={2}>
          <Text type="supporting" role="status">{error ? 'Diagram layout unavailable. Use the tables below.' : 'Calculating diagram…'}</Text>
        </Card>
      )}

      <VStack gap={1}>
        <Heading level={3}>Transitions</Heading>
        <Text type="supporting" as="p">Every arrow in the diagram, as a row. &quot;Built?&quot; follows your current scope board.</Text>
        <Table data={machine.transitions} columns={columns} idKey="id" verticalAlign="top" dividers="rows" />
      </VStack>

      {relevantBlindSpots.length > 0 ? (
        <VStack gap={1}>
          <Heading level={3}>Blind spots</Heading>
          <Text type="supporting" as="p">Where this state machine&apos;s display and the underlying system disagree, accepted by the spec rather than fixed.</Text>
          <Table data={relevantBlindSpots} columns={blindSpotColumns} idKey="id" verticalAlign="top" dividers="rows" />
        </VStack>
      ) : null}

      <StateMachineDetailDialog machine={machine} selection={selection} viewProps={props} onSelect={setSelection} />
    </VStack>
  )
}
