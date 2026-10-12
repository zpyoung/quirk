import type { Approach, SchemaRef, Table } from '../../../compare-types'
import {
  ArrowDefs,
  DiagramFrame,
  HIGHLIGHT,
  INK,
  LegendStrip,
  MUTED,
  RULE,
  TextLines,
  boxProps,
  kindStyle,
  legendHeight,
  longestUnbreakable,
  markerUrl,
  roundedPath,
  textWidth,
  useDiagramId,
  wrapIdentifier,
  type LegendItem,
  type NodeKind,
  type Point,
} from './diagram-kit'

const PAD = 16
const GRID_COLS = 3
const COL_GAP = 72
const ROW_GAP = 56
const NAME_SIZE = 11
const TYPE_SIZE = 10
const NAME_CHAR = NAME_SIZE * 0.6
const ROW_MIN = 24
const ATTACH_STEP = 8
const LANE_STEP = 10

const STATUS_KIND: Record<Table['status'], NodeKind> = { new: 'new', changed: 'changed', existing: 'reused' }
const STATUS_TAG: Record<Table['status'], string> = { new: 'NEW', changed: 'CHANGED', existing: 'EXISTING' }
const STATUS_LEGEND: Record<Table['status'], string> = { new: 'New table', changed: 'Changed table', existing: 'Existing table' }

type RowLayout = { name: string; typeText: string; lines: string[]; y: number; h: number; highlight: boolean }
type TableLayout = { table: Table; col: number; gridRow: number; x: number; y: number; w: number; h: number; headerH: number; headerLines: string[]; rows: RowLayout[]; more: string | null }
type Endpoint = { tableIndex: number; rowCenter: number; side: 'L' | 'R' }

function typeLabel(column: Table['columns'][number]): string {
  return column.chip ? `${column.type} · ${column.chip}` : column.type
}

/** Offsets for n attach points sharing one edge row: a single point stays centred, two sit at +-8, more spread by 8. */
function attachOffsets(count: number): number[] {
  const step = count === 2 ? ATTACH_STEP * 2 : ATTACH_STEP
  return Array.from({ length: count }, (_, index) => (index - (count - 1) / 2) * step)
}

/**
 * One approach's tables in a 3-column grid (array order) with orthogonal rounded connectors for each ref.
 * A ref leaves its source row's right edge when the target is right of or level with it, else the left edge.
 */
export function SchemaDiagram({ approach, approachLabel }: { approach: Approach; approachLabel: string }) {
  const prefix = useDiagramId('schema')
  const schema = approach.schema
  if (!schema || schema.tables.length === 0) return null

  const { tables, refs } = schema
  const gridCols = Math.min(GRID_COLS, tables.length)

  let tableW = 232
  for (const table of tables) {
    const tag = textWidth(STATUS_TAG[table.status], 9) + 12
    tableW = Math.max(tableW, longestUnbreakable(table.name) * 12 * 0.6 + tag + 24)
    for (const column of table.columns) {
      const typeW = textWidth(typeLabel(column), TYPE_SIZE)
      const wanted = Math.min(320, textWidth(column.name, NAME_SIZE) + typeW + 32)
      tableW = Math.max(tableW, wanted, longestUnbreakable(column.name) * NAME_CHAR + typeW + 32)
    }
  }
  tableW = Math.ceil(Math.min(tableW, 400))

  const layouts: TableLayout[] = tables.map((table, index) => {
    const tag = textWidth(STATUS_TAG[table.status], 9) + 12
    const headerLines = wrapIdentifier(table.name, Math.floor((tableW - 24 - tag) / (12 * 0.6)))
    const headerH = Math.max(32, headerLines.length * 15 + 17)
    let y = headerH
    const rows: RowLayout[] = table.columns.map((column) => {
      const typeText = typeLabel(column)
      const lines = wrapIdentifier(column.name, Math.floor((tableW - 32 - textWidth(typeText, TYPE_SIZE)) / NAME_CHAR))
      const h = Math.max(ROW_MIN, lines.length * 13 + 11)
      const row = { name: column.name, typeText, lines, y, h, highlight: !!column.highlight }
      y += h
      return row
    })
    const more = table.moreColumns ? table.moreColumns : null
    if (more) y += ROW_MIN
    return { table, col: index % GRID_COLS, gridRow: Math.floor(index / GRID_COLS), x: 0, y: 0, w: tableW, h: y, headerH, headerLines, rows, more }
  })

  const gridRows = Math.ceil(tables.length / GRID_COLS)
  const rowTop: number[] = []
  const rowBottom: number[] = []
  let cursor = PAD
  for (let r = 0; r < gridRows; r++) {
    const rowHeight = Math.max(...layouts.filter((layout) => layout.gridRow === r).map((layout) => layout.h))
    rowTop.push(cursor)
    rowBottom.push(cursor + rowHeight)
    cursor += rowHeight + ROW_GAP
  }
  for (const layout of layouts) {
    layout.x = PAD + layout.col * (tableW + COL_GAP)
    layout.y = rowTop[layout.gridRow]!
  }
  const gridBottom = rowBottom[gridRows - 1]!
  const gridW = gridCols * tableW + (gridCols - 1) * COL_GAP
  const gutterX = (gap: number) => PAD + (gap + 1) * tableW + gap * COL_GAP + COL_GAP / 2

  const tableIndex = new Map(tables.map((table, index) => [table.name, index]))
  type Resolved = { ref: SchemaRef; from: Endpoint; to: Endpoint }
  const resolved: Resolved[] = []
  for (const ref of refs) {
    const fromIndex = tableIndex.get(ref.from[0])
    const toIndex = tableIndex.get(ref.to[0])
    if (fromIndex === undefined || toIndex === undefined) continue
    const fromLayout = layouts[fromIndex]!
    const toLayout = layouts[toIndex]!
    const fromRow = fromLayout.rows.find((row) => row.name === ref.from[1])
    const toRow = toLayout.rows.find((row) => row.name === ref.to[1])
    if (!fromRow || !toRow) continue
    const rightward = toLayout.col >= fromLayout.col
    const arrivesLeft = toLayout.col > fromLayout.col
    resolved.push({
      ref,
      from: { tableIndex: fromIndex, rowCenter: fromLayout.y + fromRow.y + ROW_MIN / 2 + (fromRow.h - ROW_MIN) / 2, side: rightward ? 'R' : 'L' },
      to: { tableIndex: toIndex, rowCenter: toLayout.y + toRow.y + ROW_MIN / 2 + (toRow.h - ROW_MIN) / 2, side: arrivesLeft ? 'L' : 'R' },
    })
  }

  const rowKey = (endpoint: Endpoint, column: string) => `${endpoint.tableIndex}|${column}|${endpoint.side}`
  const groups = new Map<string, Endpoint[]>()
  const addToGroup = (endpoint: Endpoint, column: string) => {
    const key = rowKey(endpoint, column)
    groups.set(key, [...(groups.get(key) ?? []), endpoint])
  }
  for (const { ref, from, to } of resolved) {
    addToGroup(from, ref.from[1])
    addToGroup(to, ref.to[1])
  }
  const attachY = new Map<Endpoint, number>()
  for (const group of groups.values()) {
    const offsets = attachOffsets(group.length)
    group.forEach((endpoint, index) => attachY.set(endpoint, endpoint.rowCenter + offsets[index]!))
  }

  const gapUsers = new Map<number, number[]>()
  const gapsFor = (item: Resolved): { adjacent: number | null; source: number; target: number } => {
    const fromCol = layouts[item.from.tableIndex]!.col
    const toCol = layouts[item.to.tableIndex]!.col
    const distance = Math.abs(toCol - fromCol)
    if (distance <= 1) {
      const gap = toCol === fromCol ? fromCol : Math.min(fromCol, toCol)
      return { adjacent: gap, source: gap, target: gap }
    }
    return { adjacent: null, source: toCol > fromCol ? fromCol : fromCol - 1, target: toCol > fromCol ? toCol - 1 : toCol }
  }
  resolved.forEach((item, index) => {
    const gaps = gapsFor(item)
    for (const gap of new Set([gaps.source, gaps.target])) gapUsers.set(gap, [...(gapUsers.get(gap) ?? []), index])
  })
  const lanePos = (gap: number, index: number) => {
    const users = gapUsers.get(gap) ?? [index]
    return gutterX(gap) + (users.indexOf(index) - (users.length - 1) / 2) * LANE_STEP
  }

  let channelCount = 0
  const connectors = resolved.map((item, index) => {
    const fromLayout = layouts[item.from.tableIndex]!
    const toLayout = layouts[item.to.tableIndex]!
    const x1 = item.from.side === 'R' ? fromLayout.x + tableW : fromLayout.x
    const x2 = item.to.side === 'L' ? toLayout.x : toLayout.x + tableW
    const y1 = attachY.get(item.from)!
    const y2 = attachY.get(item.to)!
    const gaps = gapsFor(item)
    const points: Point[] = [{ x: x1, y: y1 }]
    if (gaps.adjacent !== null) {
      const vx = lanePos(gaps.adjacent, index)
      points.push({ x: vx, y: y1 }, { x: vx, y: y2 })
    } else {
      const upper = Math.min(fromLayout.gridRow, toLayout.gridRow)
      const channelY = rowBottom[upper]! + ROW_GAP / 2 + channelCount * LANE_STEP
      channelCount += 1
      const ax = lanePos(gaps.source, index)
      const bx = lanePos(gaps.target, index)
      points.push({ x: ax, y: y1 }, { x: ax, y: channelY }, { x: bx, y: channelY }, { x: bx, y: y2 })
    }
    points.push({ x: x2, y: y2 })
    return { d: roundedPath(points), kind: item.ref.kind }
  })

  const width = Math.max(PAD * 2 + gridW + COL_GAP / 2 + LANE_STEP * 2, 520)
  const legend: LegendItem[] = []
  for (const status of ['new', 'changed', 'existing'] as const) {
    if (tables.some((table) => table.status === status)) legend.push({ label: STATUS_LEGEND[status], swatch: 'box', kind: STATUS_KIND[status] })
  }
  if (tables.some((table) => table.columns.some((column) => column.highlight))) legend.push({ label: 'New or changed column', swatch: 'tint', fill: HIGHLIGHT })
  if (resolved.some((item) => item.ref.kind === 'fk')) legend.push({ label: 'Foreign key', swatch: 'line', marker: 'muted' })
  if (resolved.some((item) => item.ref.kind === 'json')) legend.push({ label: 'JSON reference', swatch: 'line', dashed: true, marker: 'muted' })

  const legendY = gridBottom + 32
  const height = legendY + legendHeight(legend, width - PAD * 2) + PAD

  const title = `${approachLabel}: schema`
  const desc = `Schema for ${approachLabel}. ${tables.map((table) => `${table.name} (${table.status}): ${table.columns.map((column) => `${column.name} ${typeLabel(column)}${column.highlight ? ', highlighted' : ''}`).join(', ')}${table.moreColumns ? `; ${table.moreColumns}` : ''}`).join('. ')}.${resolved.length ? ` References: ${resolved.map((item) => `${item.ref.from.join('.')} to ${item.ref.to.join('.')} (${item.ref.kind === 'fk' ? 'foreign key' : 'JSON reference'})`).join('; ')}.` : ''}`

  return (
    <DiagramFrame prefix={prefix} width={width} height={height} title={title} desc={desc} scrollLabel={title}>
      <ArrowDefs prefix={prefix} keys={['muted']} />

      {connectors.map((connector, index) => (
        <path key={index} d={connector.d} fill="none" stroke={MUTED} strokeWidth={1.2} strokeDasharray={connector.kind === 'json' ? '5,4' : undefined} markerEnd={markerUrl(prefix, 'muted')} />
      ))}

      {layouts.map((layout) => (
        <g key={layout.table.name} transform={`translate(${layout.x} ${layout.y})`}>
          <rect width={layout.w} height={layout.h} rx={6} {...boxProps(kindStyle(STATUS_KIND[layout.table.status]))} />
          <TextLines lines={layout.headerLines} x={12} y={21} size={12} lineHeight={15} fill={INK} weight={600} />
          <text x={layout.w - 12} y={17} textAnchor="end" fontSize={9} fontWeight={600} letterSpacing="0.12em" fill={MUTED}>
            {STATUS_TAG[layout.table.status]}
          </text>
          <line x1={0} y1={layout.headerH} x2={layout.w} y2={layout.headerH} stroke={RULE} strokeWidth={1} />
          {layout.rows.map((row) => (
            <g key={row.name} transform={`translate(0 ${row.y})`}>
              {row.highlight ? <rect x={1} y={0} width={layout.w - 2} height={row.h} fill={HIGHLIGHT} /> : null}
              <TextLines lines={row.lines} x={12} y={16} size={NAME_SIZE} lineHeight={13} fill={INK} />
              <text x={layout.w - 12} y={16} textAnchor="end" fontSize={TYPE_SIZE} fill={MUTED}>
                {row.typeText}
              </text>
            </g>
          ))}
          {layout.more ? (
            <text x={12} y={layout.h - 8} fontSize={10} fontStyle="italic" fill={MUTED}>
              {layout.more}
            </text>
          ) : null}
        </g>
      ))}

      <LegendStrip prefix={prefix} items={legend} x={PAD} y={legendY} width={width - PAD * 2} />
    </DiagramFrame>
  )
}
