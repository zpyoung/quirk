import { Banner } from '@astryxdesign/core/Banner'
import { Heading } from '@astryxdesign/core/Heading'
import { Link } from '@astryxdesign/core/Link'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Table, pixel, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { traceMatrix, type NonGoalRow, type TraceRow } from '../review-state'
import type { ViewProps } from './view-props'

const KIND_LABEL: Record<TraceRow['kind'], string> = { scenario: 'Scenario', constraint: 'Constraint' }

/** `CONTRACT:` the trace matrix — one row per approved stage-1 item, linking each to the non-withdrawn requirements derived from it (see Trace matrix). */
export function CoverageView({ spec, onNavigate, onOpenRequirement }: ViewProps) {
  const { rows, nonGoals } = traceMatrix(spec)
  const gapCount = rows.filter((row) => row.status === 'gap').length

  const openRequirement = (id: string) => {
    onOpenRequirement(id)
    onNavigate('board')
  }

  const columns: TableColumn<TraceRow>[] = [
    { key: 'id', header: 'ID', width: pixel(110), renderCell: (row) => <Text type="label">{row.id}</Text> },
    { key: 'kind', header: 'Kind', width: pixel(110), renderCell: (row) => <Token size="sm" label={KIND_LABEL[row.kind]} /> },
    { key: 'text', header: 'Text', width: proportional(3), renderCell: (row) => <Text>{row.text}</Text> },
    {
      key: 'requirements',
      header: 'Derived requirements',
      width: proportional(2),
      renderCell: (row) =>
        row.requirementIds.length > 0 ? (
          <HStack gap={1} wrap="wrap">
            {row.requirementIds.map((id) => <Link key={id} onClick={() => openRequirement(id)}>{id}</Link>)}
          </HStack>
        ) : (
          <Text type="supporting">None</Text>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      width: pixel(110),
      renderCell: (row) => <Token size="sm" color={row.status === 'covered' ? 'green' : 'red'} label={row.status === 'covered' ? 'Covered' : 'Gap'} />,
    },
  ]

  const nonGoalColumns: TableColumn<NonGoalRow>[] = [
    { key: 'id', header: 'ID', width: pixel(110), renderCell: (row) => <Text type="label">{row.id}</Text> },
    { key: 'kind', header: 'Kind', width: pixel(110), renderCell: (row) => <Token size="sm" label={KIND_LABEL[row.kind]} /> },
    { key: 'text', header: 'Text', width: proportional(3), renderCell: (row) => <Text>{row.text}</Text> },
    { key: 'reason', header: 'Reason', width: proportional(2), renderCell: (row) => <Text type="supporting">{row.reason}</Text> },
  ]

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>Coverage</Heading>
        <Text type="supporting" as="p">
          Every approved scenario and constraint, and which requirements derive from it. A gap means nothing on the board traces back to it yet.
        </Text>
      </VStack>
      <Banner
        status={gapCount === 0 ? 'success' : 'warning'}
        title={gapCount === 0 ? 'Every approved item is derived' : `${gapCount} approved item${gapCount === 1 ? '' : 's'} not yet derived`}
        collapsible={false}
      />
      <Table data={rows} columns={columns} idKey="id" verticalAlign="middle" dividers="rows" hasHover />
      <VStack gap={2}>
        <Heading level={3}>Not derived (non-goals)</Heading>
        <Text type="supporting" as="p">Dropped scenarios and rejected constraints, with the reason each was left out.</Text>
        {nonGoals.length > 0 ? (
          <Table data={nonGoals} columns={nonGoalColumns} idKey="id" verticalAlign="middle" dividers="rows" />
        ) : (
          <Text type="supporting">Nothing was dropped or rejected.</Text>
        )}
      </VStack>
    </VStack>
  )
}
