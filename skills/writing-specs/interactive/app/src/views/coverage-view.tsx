import { Banner } from '@astryxdesign/core/Banner'
import { Heading } from '@astryxdesign/core/Heading'
import { Link } from '@astryxdesign/core/Link'
import { VStack } from '@astryxdesign/core/Layout'
import { Table, pixel, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { coverageGaps, type ViewId } from '../review-state'
import type { ViewProps } from './view-props'

type Gap = ReturnType<typeof coverageGaps>[number]

const FIX_LABEL: Partial<Record<ViewId, string>> = { scenarios: 'Scenarios', risks: 'Risks' }
const GAP_COLOR: Partial<Record<ViewId, 'red' | 'orange'>> = { scenarios: 'red', risks: 'orange' }
const GAP_KIND: Partial<Record<ViewId, string>> = { scenarios: 'Missing scenario', risks: 'Risk gap' }

/** The in-scope requirements, assumptions, and blind spots still missing backup, each linking to the tab where the gap closes. */
export function CoverageView({ spec, state, onNavigate }: ViewProps) {
  const gaps = coverageGaps(spec, state)
  const requirementById = new Map(spec.requirements.map((requirement) => [requirement.id, requirement]))

  const columns: TableColumn<Gap>[] = [
    {
      key: 'gap',
      header: 'Gap',
      width: proportional(3),
      renderCell: (row) => {
        const requirement = row.id.startsWith('req-') ? requirementById.get(row.id.slice(4)) : undefined
        return (
          <VStack gap={0.5}>
            <Text>{row.text}</Text>
            {requirement ? <Text type="supporting">{requirement.area}</Text> : null}
          </VStack>
        )
      },
    },
    {
      key: 'kind',
      header: 'Kind',
      width: pixel(150),
      renderCell: (row) => <Token size="sm" color={GAP_COLOR[row.view] ?? 'orange'} label={GAP_KIND[row.view] ?? row.view} />,
    },
    {
      key: 'fix',
      header: 'Fix it on',
      width: pixel(140),
      renderCell: (row) => <Link onClick={() => onNavigate(row.view)}>{`${FIX_LABEL[row.view] ?? row.view} tab`}</Link>,
    },
  ]

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>Coverage gaps</Heading>
        <Text type="supporting" as="p">
          In-scope requirements and open risks that are still missing backup. Follow the link to the tab where the gap gets closed.
        </Text>
      </VStack>
      <Banner
        status={gaps.length === 0 ? 'success' : 'warning'}
        title={gaps.length === 0 ? 'No coverage gaps' : `${gaps.length} coverage gap${gaps.length === 1 ? '' : 's'} to close`}
        collapsible={false}
      />
      {gaps.length > 0 ? <Table data={gaps} columns={columns} idKey="id" verticalAlign="middle" dividers="rows" hasHover /> : null}
    </VStack>
  )
}
