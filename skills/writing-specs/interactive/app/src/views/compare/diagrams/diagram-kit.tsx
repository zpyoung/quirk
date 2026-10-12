import { useId, type ReactNode } from 'react'
import { ScrollableArea } from '@astryxdesign/core/ScrollableArea'

export const MASK = 'var(--color-background-card)'
export const INK = 'var(--color-text-primary)'
export const MUTED = 'var(--color-text-secondary)'
export const OFF = 'var(--color-text-disabled)'
export const ACCENT = 'var(--color-text-orange)'
export const SURFACE = 'var(--color-background-surface)'
export const TINT = 'var(--color-background-muted)'
export const ACCENT_TINT = 'var(--color-background-orange)'
export const HIGHLIGHT = 'var(--color-background-blue)'
export const RULE = 'var(--color-border)'

export const CORNER_RADIUS = 8
export const LABEL_GAP = 6
export const MAX_ACCENTS = 2

export type Point = { x: number; y: number }
export type NodeKind = 'new' | 'changed' | 'reused'

/** Rough text advance for the diagram font; deliberately a little wide so boxes never clip. */
export function textWidth(text: string, size: number): number {
  return text.length * size * 0.6
}

/**
 * Wraps a label to at most `maxChars` per line, breaking only at whitespace or just after an "_",
 * so identifiers like `archive_entry_id` split between words and never inside one.
 * A word with no break point stays whole and may exceed `maxChars`.
 */
export function wrapIdentifier(text: string, maxChars: number): string[] {
  const pieces: { text: string; joined: boolean }[] = []
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const segments = word.match(/[^_]*_|[^_]+$/g) ?? [word]
    segments.forEach((segment, index) => pieces.push({ text: segment, joined: index > 0 }))
  }
  const lines: string[] = []
  let current = ''
  for (const piece of pieces) {
    const glue = current && !piece.joined ? ' ' : ''
    if (current && current.length + glue.length + piece.text.length > maxChars) {
      lines.push(current)
      current = piece.text
    } else {
      current += glue + piece.text
    }
  }
  if (current) lines.push(current)
  return lines.length ? lines : ['']
}

/** The longest run of characters that wrapIdentifier cannot split. */
export function longestUnbreakable(text: string): number {
  let longest = 0
  for (const word of text.split(/\s+/).filter(Boolean)) {
    for (const segment of word.match(/[^_]*_|[^_]+$/g) ?? [word]) longest = Math.max(longest, segment.length)
  }
  return longest
}

/** An orthogonal polyline with every interior corner rounded to `radius` (clamped to half the shorter adjoining run). */
export function roundedPath(points: Point[], radius = CORNER_RADIUS): string {
  const pts = points.filter((point, index) => index === 0 || point.x !== points[index - 1]!.x || point.y !== points[index - 1]!.y)
  const first = pts[0]
  if (!first) return ''
  let d = `M${fmt(first.x)},${fmt(first.y)}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]!
    const point = pts[i]!
    const next = pts[i + 1]
    if (!next) {
      d += ` L${fmt(point.x)},${fmt(point.y)}`
      continue
    }
    const inLen = Math.abs(point.x - prev.x) + Math.abs(point.y - prev.y)
    const outLen = Math.abs(next.x - point.x) + Math.abs(next.y - point.y)
    const r = Math.min(radius, inLen / 2, outLen / 2)
    const inDx = Math.sign(point.x - prev.x)
    const inDy = Math.sign(point.y - prev.y)
    const outDx = Math.sign(next.x - point.x)
    const outDy = Math.sign(next.y - point.y)
    d += ` L${fmt(point.x - inDx * r)},${fmt(point.y - inDy * r)} Q${fmt(point.x)},${fmt(point.y)} ${fmt(point.x + outDx * r)},${fmt(point.y + outDy * r)}`
  }
  return d
}

function fmt(value: number): string {
  return String(Math.round(value * 100) / 100)
}

/** Horizontal-vertical-horizontal connector from (x1,y1) to (x2,y2), bending at `xMid`; a straight run when the endpoints share a y. */
export function elbowPath(x1: number, y1: number, x2: number, y2: number, xMid: number, radius = CORNER_RADIUS): string {
  if (y1 === y2) return `M${fmt(x1)},${fmt(y1)} H${fmt(x2)}`
  return roundedPath([{ x: x1, y: y1 }, { x: xMid, y: y1 }, { x: xMid, y: y2 }, { x: x2, y: y2 }], radius)
}

/** Stable, selector-safe id prefix unique to one rendered diagram. */
export function useDiagramId(kind: string): string {
  return `dg-${kind}-${useId().replace(/[^a-zA-Z0-9]/g, '')}`
}

export type MarkerKey = 'ink' | 'muted' | 'open' | 'accent'

export function markerUrl(prefix: string, key: MarkerKey): string {
  return `url(#${prefix}-m-${key})`
}

const MARKER_COLOR: Record<MarkerKey, string> = { ink: INK, muted: MUTED, open: MUTED, accent: ACCENT }

/** Arrow markers for one diagram instance; ids carry the instance prefix so two diagrams on a page never collide. */
export function ArrowDefs({ prefix, keys }: { prefix: string; keys: MarkerKey[] }) {
  return (
    <defs>
      {keys.map((key) => (
        <marker key={key} id={`${prefix}-m-${key}`} markerWidth={8} markerHeight={6} refX={7} refY={3} orient="auto" markerUnits="userSpaceOnUse">
          {key === 'open' ? <polyline points="0 0, 8 3, 0 6" fill="none" stroke={MARKER_COLOR[key]} strokeWidth={1.2} /> : <polygon points="0 0, 8 3, 0 6" fill={MARKER_COLOR[key]} />}
        </marker>
      ))}
    </defs>
  )
}

export type BoxStyle = { fill: string; stroke: string; strokeWidth: number; dash?: string }

/** new = solid stroke, changed = tinted fill, reused = dashed stroke; `accent` swaps in the accent stroke. */
export function kindStyle(kind: NodeKind, accent = false): BoxStyle {
  const base: BoxStyle = kind === 'new' ? { fill: SURFACE, stroke: INK, strokeWidth: 1.5 } : kind === 'changed' ? { fill: TINT, stroke: INK, strokeWidth: 1 } : { fill: SURFACE, stroke: MUTED, strokeWidth: 1, dash: '5,4' }
  return accent ? { ...base, stroke: ACCENT, strokeWidth: 2 } : base
}

export const KIND_LABEL: Record<NodeKind, string> = { new: 'NEW', changed: 'CHANGED', reused: 'REUSED' }

/**
 * A label that sits on its connector's line without touching it: an opaque mask the page background shows
 * through nowhere, whose edge stays `gap` px clear of the line at `y`. `above` centres on `x` over the line;
 * `right` starts `gap` px right of `x`, vertically centred on `y`.
 */
export function MaskedLabel({ x, y, text, color = MUTED, placement = 'above', size = 10, gap = LABEL_GAP }: { x: number; y: number; text: string; color?: string; placement?: 'above' | 'right'; size?: number; gap?: number }) {
  const width = textWidth(text, size) + 8
  const height = size + 6
  const left = placement === 'above' ? x - width / 2 : x + gap
  const top = placement === 'above' ? y - gap - height : y - height / 2
  return (
    <g>
      <rect x={left} y={top} width={width} height={height} rx={3} fill={MASK} />
      <text x={left + width / 2} y={top + height / 2 + size * 0.35} textAnchor="middle" fontSize={size} fill={color}>
        {text}
      </text>
    </g>
  )
}

export type LegendItem = { label: string; swatch: 'box' | 'tint' | 'line'; kind?: NodeKind; accent?: boolean; dashed?: boolean; marker?: MarkerKey; fill?: string }

const SWATCH_W = 28
const LEGEND_ROW = 20

/** Lays legend items left to right, wrapping to a new row when the next item would pass `width`; returns the placed items and total height. */
export function layoutLegend(items: LegendItem[], width: number): { placed: { item: LegendItem; x: number; y: number }[]; height: number } {
  const placed: { item: LegendItem; x: number; y: number }[] = []
  let x = 0
  let row = 0
  for (const item of items) {
    const w = SWATCH_W + 8 + textWidth(item.label, 10) + 20
    if (x > 0 && x + w > width) {
      x = 0
      row += 1
    }
    placed.push({ item, x, y: row * LEGEND_ROW })
    x += w
  }
  return { placed, height: (row + 1) * LEGEND_ROW }
}

/** The encodings a diagram actually uses, keyed so a reader never has to infer dash or tint meaning. */
export function LegendStrip({ prefix, items, x, y, width }: { prefix: string; items: LegendItem[]; x: number; y: number; width: number }) {
  const { placed } = layoutLegend(items, width)
  return (
    <g transform={`translate(${x} ${y})`}>
      <line x1={0} y1={-8} x2={width} y2={-8} stroke={RULE} strokeWidth={1} />
      {placed.map(({ item, x: ix, y: iy }) => (
        <g key={item.label} transform={`translate(${ix} ${iy + 10})`}>
          {item.swatch === 'line' ? (
            <path d={`M0,0 H${SWATCH_W - 2}`} fill="none" stroke={item.accent ? ACCENT : item.marker === 'ink' ? INK : MUTED} strokeWidth={1.2} strokeDasharray={item.dashed ? '5,4' : undefined} markerEnd={item.marker ? markerUrl(prefix, item.marker) : undefined} />
          ) : item.swatch === 'tint' ? (
            <rect x={0} y={-6} width={SWATCH_W - 8} height={12} rx={2} fill={item.fill ?? HIGHLIGHT} stroke={RULE} strokeWidth={1} />
          ) : (
            <rect x={0} y={-6} width={SWATCH_W - 8} height={12} rx={2} {...boxProps(kindStyle(item.kind ?? 'new', item.accent))} />
          )}
          <text x={SWATCH_W + 8} y={3} fontSize={10} fill={MUTED}>
            {item.label}
          </text>
        </g>
      ))}
    </g>
  )
}

export function legendHeight(items: LegendItem[], width: number): number {
  return layoutLegend(items, width).height
}

export function boxProps(style: BoxStyle) {
  return { fill: style.fill, stroke: style.stroke, strokeWidth: style.strokeWidth, strokeDasharray: style.dash }
}

/** Shared SVG shell: accessible name and description first, an opaque backdrop so label masks match, and an inline scroller for wide diagrams. */
export function DiagramFrame({ prefix, width, height, title, desc, scrollLabel, children }: { prefix: string; width: number; height: number; title: string; desc: string; scrollLabel: string; children: ReactNode }) {
  return (
    <ScrollableArea axis="inline" label={scrollLabel}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${prefix}-title ${prefix}-desc`} fontFamily="inherit" style={{ display: 'block' }}>
        <title id={`${prefix}-title`}>{title}</title>
        <desc id={`${prefix}-desc`}>{desc}</desc>
        <rect width={width} height={height} fill={MASK} />
        {children}
      </svg>
    </ScrollableArea>
  )
}

/** Wrapped label lines as <text> rows anchored at `x`, baseline of the first row at `y`. */
export function TextLines({ lines, x, y, size, lineHeight, fill, weight, anchor = 'start' }: { lines: string[]; x: number; y: number; size: number; lineHeight: number; fill: string; weight?: number; anchor?: 'start' | 'middle' | 'end' }) {
  return (
    <>
      {lines.map((line, index) => (
        <text key={index} x={x} y={y + index * lineHeight} fontSize={size} fontWeight={weight} fill={fill} textAnchor={anchor}>
          {line}
        </text>
      ))}
    </>
  )
}
