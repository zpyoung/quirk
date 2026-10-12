import type { ReactNode } from 'react'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Table, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { Tooltip } from '@astryxdesign/core/Tooltip'
import type { Approach, Band, CompareViewProps, Slice } from '../../compare-types'
import { POINT_MAP, pointsFor } from '../../compare-state'

const BANDS: Band[] = ['v1', 'fast-follow', 'optional']
const BAND_LABEL: Record<Band, string> = { v1: 'v1', 'fast-follow': 'fast-follow', optional: 'optional' }
const INK = 'var(--color-text-primary)'
const SEGMENT_FILL = 'var(--color-background-blue)'
const SEGMENT_EDGE = 'var(--color-border-blue)'

const midpoint = (slice: Slice) => (POINT_MAP[slice.size][0] + POINT_MAP[slice.size][1]) / 2
const pointsLabel = (slice: Slice) => {
  const [low, high] = POINT_MAP[slice.size]
  return low === high ? `${low}` : `${low}-${high}`
}
const rangeLabel = ([low, high]: [number, number]) => (low === high ? `${low} pts` : `${low}-${high} pts`)
const segmentLabel = (slice: Slice) => `${slice.name} · ${slice.size} = ${pointsLabel(slice)} pts · ${slice.area} · ${BAND_LABEL[slice.band]}`

function orderedSlices(approach: Approach): Slice[] {
  return BANDS.flatMap((band) => approach.slices.filter((slice) => slice.band === band))
}

function segmentStyle(band: Band): React.CSSProperties {
  switch (band) {
    case 'v1':
      return { background: SEGMENT_FILL, border: `1px solid ${SEGMENT_EDGE}` }
    case 'fast-follow':
      return {
        background: `repeating-linear-gradient(45deg, ${SEGMENT_FILL} 0 4px, transparent 4px 8px)`,
        border: `1px solid ${SEGMENT_EDGE}`,
      }
    case 'optional':
      return { background: 'transparent', border: `1.5px dashed ${SEGMENT_EDGE}` }
  }
}

function LegendSwatch({ band, label }: { band: Band; label: string }) {
  return (
    <HStack gap={1} align="center">
      <span aria-hidden="true" style={{ display: 'inline-block', width: 28, height: 14, borderRadius: 3, ...segmentStyle(band) }} />
      <Text type="supporting">{label}</Text>
    </HStack>
  )
}

function EffortBar({ approach, scale }: { approach: Approach; scale: number }) {
  const slices = orderedSlices(approach)
  if (!slices.length) return <Text type="supporting">No slices provided.</Text>
  return (
    <div role="list" aria-label={`Approach ${approach.id} effort by slice`} style={{ display: 'flex', gap: 2, width: '100%' }}>
      {slices.map((slice) => (
        <div key={slice.id} role="listitem" style={{ flex: `0 0 calc(${(midpoint(slice) / scale) * 100}% - 2px)`, minWidth: 0 }}>
          <Tooltip content={segmentLabel(slice)}>
            <div
              role="img"
              tabIndex={0}
              aria-label={segmentLabel(slice)}
              style={{ ...segmentStyle(slice.band), height: 32, borderRadius: 4, boxSizing: 'border-box', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK, fontSize: 11, fontWeight: 600 }}
            >
              <span style={{ background: 'var(--color-background-card)', padding: '0 4px', borderRadius: 3 }}>{slice.size}</span>
            </div>
          </Tooltip>
        </div>
      ))}
    </div>
  )
}

type AreaRow = { area: string; cells: Record<string, string> }

function AreaTable({ approaches }: { approaches: Approach[] }) {
  const areas = [...new Set(approaches.flatMap((approach) => approach.slices.map((slice) => slice.area)))]
  const rows: AreaRow[] = areas.map((area) => ({
    area,
    cells: Object.fromEntries(
      approaches.map((approach) => [
        approach.id,
        approach.slices
          .filter((slice) => slice.area === area)
          .map((slice) => `${slice.name} (${slice.size}, ${BAND_LABEL[slice.band]})`)
          .join('; '),
      ]),
    ),
  }))
  const columns: TableColumn<AreaRow>[] = [
    { key: 'area', header: 'Work area', width: proportional(1), renderCell: (row) => <Text type="label">{row.area}</Text> },
    ...approaches.map((approach): TableColumn<AreaRow> => ({
      key: `approach-${approach.id}`,
      header: `Approach ${approach.id}`,
      width: proportional(2),
      renderCell: (row) => (row.cells[approach.id] ? <Text>{row.cells[approach.id]}</Text> : <Text type="supporting">No slice</Text>),
    })),
  ]
  return <Table data={rows} columns={columns} idKey="area" verticalAlign="top" dividers="rows" />
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <VStack gap={0}>
      <Text type="label" color="secondary">{label}</Text>
      {children}
    </VStack>
  )
}

/** Effort in points taken from each proponent's own size labels, one bar per approach. Nothing here is a coordinator estimate. */
export function EffortView(props: CompareViewProps) {
  const approaches = props.comparison.approaches.filter((approach) => props.approaches.includes(approach.id))
  const scale = Math.max(1, ...approaches.map((approach) => approach.slices.reduce((sum, slice) => sum + midpoint(slice), 0)))

  return (
    <VStack gap={3}>
      <VStack gap={1}>
        <Heading level={2}>Effort</Heading>
        <Text type="supporting">Bar segments are slices, sized by the midpoint of the proponent's own size label (S 2, M 3, L 5, XL 8). Bars share one scale. Point ranges beside each bar cover v1 only.</Text>
        <HStack gap={3} wrap="wrap" align="center">
          <LegendSwatch band="v1" label="v1 (solid)" />
          <LegendSwatch band="fast-follow" label="fast-follow (hatched)" />
          <LegendSwatch band="optional" label="optional (dashed outline)" />
        </HStack>
      </VStack>

      {approaches.map((approach) => {
        const v1 = pointsFor(approach, 'v1')
        const followUp = pointsFor(approach, 'fast-follow')
        const optional = pointsFor(approach, 'optional')
        return (
          <Card key={approach.id} padding={2}>
            <VStack gap={2}>
              <HStack gap={2} align="center" wrap="wrap">
                <Heading level={3}>{`Approach ${approach.id} · ${approach.title}`}</Heading>
                <Token size="sm" color="blue" label={`v1 ${rangeLabel(v1)}`} />
                {followUp[1] > 0 ? <Token size="sm" color="default" label={`fast-follow ${rangeLabel(followUp)}`} /> : null}
                {optional[1] > 0 ? <Token size="sm" color="default" label={`optional ${rangeLabel(optional)}`} /> : null}
              </HStack>
              <EffortBar approach={approach} scale={scale} />
              <Row label="Critical path">
                {approach.criticalPath ? <Text>{approach.criticalPath}</Text> : <Text type="supporting">not stated</Text>}
              </Row>
              {approach.effortGaps?.length ? (
                <Row label="Gaps the coordinator noticed">
                  <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                    {approach.effortGaps.map((gap, index) => <li key={index}><Text>{gap}</Text></li>)}
                  </ul>
                </Row>
              ) : null}
            </VStack>
          </Card>
        )
      })}

      <Collapsible trigger="Work areas side by side" defaultIsOpen={false}>
        <AreaTable approaches={approaches} />
      </Collapsible>
    </VStack>
  )
}
