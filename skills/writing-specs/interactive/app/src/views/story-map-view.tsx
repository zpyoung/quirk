import { Banner } from '@astryxdesign/core/Banner'
import { ClickableCard } from '@astryxdesign/core/ClickableCard'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, VStack } from '@astryxdesign/core/Layout'
import { Table, pixel, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { GROUP_LABEL, placedRequirements } from '../review-state'
import type { Placement, Requirement } from '../spec-types'
import { GROUP_COLOR } from './shared'
import type { ViewProps } from './view-props'

type Row = { scope: 'in' | 'out' }
type Placed = { requirement: Requirement; placement: Placement }

function RequirementChip({ requirement, placement, onOpen }: { requirement: Requirement; placement: Placement; onOpen: (id: string) => void }) {
  return (
    <ClickableCard label={`${requirement.id}: ${requirement.summary}`} onClick={() => onOpen(requirement.id)} padding={1} width="100%">
      <VStack gap={0.5}>
        <Text type="label">{requirement.id}</Text>
        <Text type="supporting">{requirement.summary}</Text>
        {placement !== 'out' ? <Token size="sm" color={GROUP_COLOR[requirement.group]} label={GROUP_LABEL[requirement.group]} /> : null}
      </VStack>
    </ClickableCard>
  )
}

function Cell({ area, scope, placed, onOpen }: { area: string; scope: Row['scope']; placed: Placed[]; onOpen: (id: string) => void }) {
  const items = placed.filter(({ requirement, placement }) => requirement.area === area && (scope === 'out' ? placement === 'out' : placement !== 'out'))
  if (items.length === 0) return <Text type="supporting">Nothing here</Text>
  return (
    <VStack gap={1}>
      {items.map(({ requirement, placement }) => (
        <RequirementChip key={requirement.id} requirement={requirement} placement={placement} onOpen={onOpen} />
      ))}
    </VStack>
  )
}

/** A Jeff Patton style story map: journey steps as columns, in scope and out of scope as rows, checking whether the spec covers the whole journey. */
export function StoryMapView({ spec, state, onOpenRequirement }: ViewProps) {
  const storyMap = spec.views?.storyMap
  if (!storyMap) return null
  const placed = placedRequirements(spec, state)
  const gapAreas = new Set(
    storyMap.journey.filter((step) => !placed.some(({ requirement, placement }) => requirement.area === step.area && placement !== 'out')).map((step) => step.area),
  )
  const rowCount = (scope: Row['scope']) => placed.filter(({ placement }) => (scope === 'out' ? placement === 'out' : placement !== 'out')).length

  const areaColumn = (area: string, label: string, isJourney: boolean, isFirstCrossCutting = false): TableColumn<Row> => ({
    key: area,
    header: (
      <Card variant={isJourney ? (gapAreas.has(area) ? 'orange' : 'default') : 'gray'} padding={1}>
        <VStack gap={0.5}>
          {isFirstCrossCutting ? <Token size="sm" color="gray" label="Cross-cutting" /> : null}
          <Text type="label">{label}</Text>
        </VStack>
      </Card>
    ),
    width: pixel(220),
    renderCell: (row) => <Cell area={area} scope={row.scope} placed={placed} onOpen={onOpenRequirement} />,
  })

  const columns: TableColumn<Row>[] = [
    {
      key: 'scope',
      header: 'Scope',
      width: pixel(180),
      renderCell: (row) => (
        <Card variant={row.scope === 'in' ? 'green' : 'muted'} padding={2}>
          <VStack gap={0.5}>
            <Heading level={4}>{row.scope === 'in' ? 'In scope' : 'Out of scope'}</Heading>
            <Token size="sm" label={`${rowCount(row.scope)} requirement${rowCount(row.scope) === 1 ? '' : 's'}`} />
          </VStack>
        </Card>
      ),
    },
    ...storyMap.journey.map((step) => areaColumn(step.area, step.label, true)),
    { key: 'divider', header: <Divider orientation="vertical" />, width: pixel(24), renderCell: () => <Divider orientation="vertical" /> },
    ...storyMap.crossCutting.map((area, index) => areaColumn(area, area, false, index === 0)),
  ]

  const rows: Row[] = [{ scope: 'in' }, { scope: 'out' }]

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>Story map</Heading>
        <Text type="supporting" as="p">
          Columns follow the journey a user takes, left to right, with cross-cutting concerns after the divider. The top row is in scope, tagged with its
          group; the bottom row is deliberately out of scope. Click any card to see its details.
        </Text>
      </VStack>
      <Banner
        status={gapAreas.size === 0 ? 'success' : 'warning'}
        title={`The spec covers ${storyMap.journey.length - gapAreas.size} of ${storyMap.journey.length} journey steps`}
        description={
          gapAreas.size === 0
            ? 'Every journey step has at least one in-scope requirement.'
            : `Not covered: ${storyMap.journey.filter((step) => gapAreas.has(step.area)).map((step) => step.label).join(', ')}.`
        }
        collapsible={false}
      />
      <Table data={rows} columns={columns} idKey="scope" verticalAlign="top" dividers="grid" />
    </VStack>
  )
}
