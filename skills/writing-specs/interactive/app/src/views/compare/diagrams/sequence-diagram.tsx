import type { Approach, SequenceMessage } from '../../../compare-types'
import {
  ArrowDefs,
  DiagramFrame,
  INK,
  LegendStrip,
  MAX_ACCENTS,
  MaskedLabel,
  MUTED,
  OFF,
  TextLines,
  ACCENT,
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
  type MarkerKey,
} from './diagram-kit'

const PAD = 16
const ROW_H = 36
const LABEL_SIZE = 10
const SELF_LOOP_W = 40

type Row = { message: SequenceMessage; from: number; to: number; accent: boolean }

const STROKE: Record<SequenceMessage['kind'], { color: string; dash?: string; marker: MarkerKey }> = {
  call: { color: INK, marker: 'ink' },
  return: { color: MUTED, dash: '5,4', marker: 'muted' },
  async: { color: MUTED, dash: '5,4', marker: 'open' },
  focal: { color: ACCENT, marker: 'accent' },
}

/** One approach's runtime messages: participants as columns, one 36px row per message, in array order. */
export function SequenceDiagram({ approach, approachLabel }: { approach: Approach; approachLabel: string }) {
  const prefix = useDiagramId('seq')
  const sequence = approach.sequence
  if (!sequence || sequence.participants.length === 0) return null

  const { participants } = sequence
  let accentsLeft = MAX_ACCENTS
  const rows: Row[] = []
  for (const message of sequence.messages) {
    const from = participants.indexOf(message.from)
    const to = participants.indexOf(message.to)
    if (from < 0 || to < 0) continue
    const accent = message.kind === 'focal' && accentsLeft > 0
    if (accent) accentsLeft -= 1
    rows.push({ message, from, to, accent })
  }

  const nameLines = participants.map((name) => wrapIdentifier(name, 16))
  const boxW = Math.min(200, Math.max(112, Math.ceil(Math.max(...participants.map((name) => longestUnbreakable(name))) * 7.4 + 24)))
  const headerH = Math.max(32, Math.max(...nameLines.map((lines) => lines.length)) * 14 + 16)

  let spacing = Math.max(boxW + 16, 150)
  for (const row of rows) {
    const span = Math.abs(row.to - row.from)
    if (span > 0) spacing = Math.max(spacing, Math.ceil((textWidth(row.message.label, LABEL_SIZE) + 32) / span))
  }
  spacing = Math.min(spacing, 320)

  const selfLabelExtra = Math.max(0, ...rows.filter((row) => row.from === row.to && row.from === participants.length - 1).map((row) => SELF_LOOP_W + 14 + textWidth(row.message.label, LABEL_SIZE)))
  const xs = participants.map((_, index) => PAD + boxW / 2 + index * spacing)
  const bodyW = boxW + (participants.length - 1) * spacing
  const width = Math.max(PAD * 2 + bodyW + selfLabelExtra, 520)

  const firstY = PAD + headerH + 30
  const rowY = (index: number) => firstY + index * ROW_H
  const lifelineEnd = (rows.length ? rowY(rows.length - 1) : firstY) + 20

  const kinds = new Set(rows.map((row) => row.message.kind))
  const legend: LegendItem[] = []
  if (kinds.has('call')) legend.push({ label: 'Call', swatch: 'line', marker: 'ink' })
  if (kinds.has('return')) legend.push({ label: 'Return', swatch: 'line', dashed: true, marker: 'muted' })
  if (kinds.has('async')) legend.push({ label: 'Async', swatch: 'line', dashed: true, marker: 'open' })
  if (rows.some((row) => row.accent)) legend.push({ label: `Step unique to ${approachLabel}`, swatch: 'line', accent: true, marker: 'accent' })

  const legendY = lifelineEnd + 28
  const height = legend.length ? legendY + legendHeight(legend, width - PAD * 2) + PAD : lifelineEnd + PAD

  const title = `${approachLabel}: runtime sequence`
  const desc = `Runtime sequence for ${approachLabel} between ${participants.join(', ')}. ${rows.map((row, index) => `${index + 1}. ${row.message.from} to ${row.message.to}: ${row.message.label} (${row.message.kind})`).join('; ')}.`

  return (
    <DiagramFrame prefix={prefix} width={width} height={height} title={title} desc={desc} scrollLabel={title}>
      <ArrowDefs prefix={prefix} keys={['ink', 'muted', 'open', 'accent']} />

      {xs.map((x, index) => (
        <line key={participants[index]} x1={x} y1={PAD + headerH} x2={x} y2={lifelineEnd} stroke={OFF} strokeWidth={1} strokeDasharray="4,4" />
      ))}

      {rows.map((row, index) => {
        const y = rowY(index)
        const x1 = xs[row.from]!
        const x2 = xs[row.to]!
        const style = row.message.kind === 'focal' && !row.accent ? STROKE.call : STROKE[row.message.kind]
        const d =
          row.from === row.to
            ? roundedPath([{ x: x1, y: y - 8 }, { x: x1 + SELF_LOOP_W, y: y - 8 }, { x: x1 + SELF_LOOP_W, y: y + 8 }, { x: x1, y: y + 8 }])
            : `M${x1},${y} H${x2}`
        return <path key={index} d={d} fill="none" stroke={style.color} strokeWidth={row.accent ? 1.8 : 1.2} strokeDasharray={style.dash} markerEnd={markerUrl(prefix, style.marker)} />
      })}

      {rows.map((row, index) => {
        const y = rowY(index)
        const x1 = xs[row.from]!
        const x2 = xs[row.to]!
        const color = row.accent ? ACCENT : MUTED
        return row.from === row.to ? (
          <MaskedLabel key={index} x={x1 + SELF_LOOP_W} y={y} text={row.message.label} color={color} placement="right" size={LABEL_SIZE} />
        ) : (
          <MaskedLabel key={index} x={(x1 + x2) / 2} y={y} text={row.message.label} color={color} size={LABEL_SIZE} />
        )
      })}

      {participants.map((name, index) => (
        <g key={name} transform={`translate(${xs[index]! - boxW / 2} ${PAD})`}>
          <rect width={boxW} height={headerH} rx={6} {...boxProps(kindStyle('new'))} />
          <TextLines lines={nameLines[index]!} x={boxW / 2} y={headerH / 2 - ((nameLines[index]!.length - 1) * 14) / 2 + 4} size={12} lineHeight={14} fill={INK} weight={600} anchor="middle" />
        </g>
      ))}

      {legend.length ? <LegendStrip prefix={prefix} items={legend} x={PAD} y={legendY} width={width - PAD * 2} /> : null}
    </DiagramFrame>
  )
}
