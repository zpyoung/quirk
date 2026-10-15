import type { Approach, FlowBox } from '../../../compare-types'
import {
  ACCENT,
  ArrowDefs,
  DiagramFrame,
  INK,
  KIND_LABEL,
  LegendStrip,
  MAX_ACCENTS,
  MUTED,
  RULE,
  boxProps,
  elbowPath,
  kindStyle,
  legendHeight,
  longestUnbreakable,
  markerUrl,
  useDiagramId,
  wrapIdentifier,
  TextLines,
  type LegendItem,
} from './diagram-kit'

const PAD = 16
const HEADER_H = 28
const GAP = 40
const CHAR = 6.2
const LINE_H = 13
const TAG_H = 22

type Placed = { box: FlowBox; col: number; row: number; lines: string[]; accent: boolean }

/**
 * One approach's process as lanes (rows, first-appearance order) by flow stages (columns): each box is
 * styled new / changed / reused, and connectors follow the boxes stage by stage.
 */
export function ProcessFlow({ approach, flowStages, approachLabel }: { approach: Approach; flowStages: string[]; approachLabel: string }) {
  const prefix = useDiagramId('flow')
  const boxes = approach.flow
  if (!boxes || boxes.length === 0) return null

  const stages = [...flowStages]
  for (const box of boxes) if (!stages.includes(box.stage)) stages.push(box.stage)
  const lanes: string[] = []
  for (const box of boxes) if (!lanes.includes(box.lane)) lanes.push(box.lane)

  const nodeW = Math.min(220, Math.max(136, Math.ceil(Math.max(...boxes.map((box) => longestUnbreakable(box.text))) * CHAR + 20)))
  const maxChars = Math.floor((nodeW - 20) / CHAR)
  const laneChars = 14
  const laneLabelW = Math.max(96, Math.ceil(Math.max(...lanes.map((lane) => longestUnbreakable(lane))) * 7 + 24))
  let accentsLeft = MAX_ACCENTS
  const placed: Placed[] = boxes
    .map((box, order) => ({ box, order }))
    .sort((a, b) => stages.indexOf(a.box.stage) - stages.indexOf(b.box.stage) || a.order - b.order)
    .map(({ box }) => {
      const accent = !!box.focal && accentsLeft > 0
      if (accent) accentsLeft -= 1
      return { box, col: stages.indexOf(box.stage), row: lanes.indexOf(box.lane), lines: wrapIdentifier(box.text, maxChars), accent }
    })

  const nodeH = TAG_H + Math.max(...placed.map((node) => node.lines.length)) * LINE_H + 14
  const rowH = nodeH + 36
  const colW = nodeW + GAP
  const gridW = laneLabelW + stages.length * colW
  const gridH = HEADER_H + lanes.length * rowH

  const used = new Set<NodeKindKey>(placed.map((node) => node.box.kind))
  const legend: LegendItem[] = []
  if (used.has('new')) legend.push({ label: 'New code', swatch: 'box', kind: 'new' })
  if (used.has('changed')) legend.push({ label: 'Changed', swatch: 'box', kind: 'changed' })
  if (used.has('reused')) legend.push({ label: 'Reused as is', swatch: 'box', kind: 'reused' })
  if (placed.some((node) => node.accent)) legend.push({ label: `Unique to ${approachLabel}`, swatch: 'box', kind: 'new', accent: true })
  legend.push({ label: 'Flow order', swatch: 'line', marker: 'muted' })

  const width = Math.max(gridW + PAD * 2, 520)
  const legendY = PAD + gridH + 24
  const height = legendY + legendHeight(legend, width - PAD * 2) + PAD

  const nodeX = (col: number) => PAD + laneLabelW + col * colW + GAP / 2
  const nodeY = (row: number) => PAD + HEADER_H + row * rowH + (rowH - nodeH) / 2
  const midY = (row: number) => nodeY(row) + nodeH / 2

  const connectors = placed.slice(1).map((to, index) => {
    const from = placed[index]!
    if (to.col === from.col) {
      const down = to.row > from.row
      const x = nodeX(from.col) + nodeW / 2
      const y1 = down ? nodeY(from.row) + nodeH : nodeY(from.row)
      const y2 = down ? nodeY(to.row) : nodeY(to.row) + nodeH
      return `M${x},${y1} V${y2}`
    }
    const x1 = nodeX(from.col) + nodeW
    const x2 = nodeX(to.col)
    return elbowPath(x1, midY(from.row), x2, midY(to.row), x2 - GAP / 2)
  })

  const title = `${approachLabel}: process flow`
  const desc = `Process flow for ${approachLabel} across ${stages.join(', ')}. ${placed.map((node) => `${node.box.stage}, ${node.box.lane} lane: ${node.box.text} (${node.box.kind}${node.box.focal ? ', focal' : ''})`).join('; ')}.`

  return (
    <DiagramFrame prefix={prefix} width={width} height={height} title={title} desc={desc} scrollLabel={title}>
      <ArrowDefs prefix={prefix} keys={['muted']} />

      {lanes.map((lane, row) => {
        const y = PAD + HEADER_H + row * rowH
        const laneLines = wrapIdentifier(lane, laneChars)
        return (
          <g key={lane}>
            <line x1={PAD} y1={y} x2={PAD + gridW} y2={y} stroke={RULE} strokeWidth={1} />
            <TextLines lines={laneLines} x={PAD + 4} y={y + rowH / 2 - ((laneLines.length - 1) * 12) / 2 + 4} size={11} lineHeight={12} fill={MUTED} weight={600} />
          </g>
        )
      })}
      <line x1={PAD} y1={PAD + gridH} x2={PAD + gridW} y2={PAD + gridH} stroke={RULE} strokeWidth={1} />
      {stages.map((stage, col) => (
        <text key={stage} x={nodeX(col) + nodeW / 2} y={PAD + 16} textAnchor="middle" fontSize={11} fontWeight={600} fill={INK}>
          {`${col + 1} · ${stage}`}
        </text>
      ))}

      {connectors.map((d, index) => (
        <path key={index} d={d} fill="none" stroke={MUTED} strokeWidth={1.2} markerEnd={markerUrl(prefix, 'muted')} />
      ))}

      {placed.map(({ box, col, row, lines, accent }) => (
        <g key={`${box.stage}-${box.lane}`} transform={`translate(${nodeX(col)} ${nodeY(row)})`}>
          <rect width={nodeW} height={nodeH} rx={6} {...boxProps(kindStyle(box.kind, accent))} />
          <text x={10} y={15} fontSize={9} fontWeight={600} letterSpacing="0.12em" fill={accent ? ACCENT : MUTED}>
            {KIND_LABEL[box.kind]}
          </text>
          <TextLines lines={lines} x={10} y={TAG_H + 12} size={11} lineHeight={LINE_H} fill={INK} />
        </g>
      ))}

      <LegendStrip prefix={prefix} items={legend} x={PAD} y={legendY} width={width - PAD * 2} />
    </DiagramFrame>
  )
}

type NodeKindKey = FlowBox['kind']
