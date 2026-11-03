import { useEffect, useRef, useState, type JSX, type KeyboardEvent } from 'react'
import { formatElapsed, taskElapsedMs } from './format'
import type { NodeBox } from './layout'
import type { RunStatus, RunTask } from './types'

export interface TaskNodeProps {
  task: RunTask
  box: NodeBox
  serverNow: number
  selected: boolean
  onSelect(id: string): void
  /** Reports which node's mismatch tooltip should show; the graph draws it above every card. */
  onTip?(id: string | null): void
}

export const STATUS_WORD: Record<RunStatus, string> = {
  queued: 'queued',
  running: 'running',
  'needs-you': 'needs you',
  retrying: 'retrying',
  passed: 'passed',
  failed: 'failed',
  skipped: 'skipped',
  stopped: 'stopped',
  missing: 'missing',
}

const STATUS_GLYPH: Record<RunStatus, string> = {
  queued: '○',
  running: '▶',
  'needs-you': '?',
  retrying: '↻',
  passed: '✓',
  failed: '✕',
  skipped: '–',
  stopped: '■',
  missing: '…',
}

const REASON_STATUSES = new Set<RunStatus>(['failed', 'stopped', 'skipped', 'retrying'])
const RADIUS = 8
const CHIP_H = 20
const STRIPE_W = 5

const filesText = (n: number) => (n === 1 ? '1 file' : `${n} files`)
const clip = (text: string, max: number) => (text.length <= max ? text : `${text.slice(0, Math.max(1, max - 1))}…`)
const chipWidth = (text: string) => Math.ceil(text.length * 7.4 + 14)

function cardPath(w: number, h: number): string {
  const r = RADIUS
  return `M${r},0 H${w - r} A${r},${r} 0 0 1 ${w},${r} V${h - r} A${r},${r} 0 0 1 ${w - r},${h} H${r} A${r},${r} 0 0 1 0,${h - r} V${r} A${r},${r} 0 0 1 ${r},0 Z`
}

interface Chip {
  text: string
  kind: 'pending' | 'try' | 'label'
}

function chipsFor(task: RunTask): Chip[] {
  const chips: Chip[] = []
  if (task.pending_action) chips.push({ text: task.pending_action === 'stop' ? 'Stop requested' : 'Retry requested', kind: 'pending' })
  if (task.attempt > 1) chips.push({ text: `try ${task.attempt}`, kind: 'try' })
  for (const label of task.labels) chips.push({ text: label, kind: 'label' })
  return chips
}

function tooltipLines(text: string, width = 40): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(/\s+/)) {
    if (line && line.length + word.length + 1 > width) {
      lines.push(line)
      line = word
    } else {
      line = line ? `${line} ${word}` : word
    }
  }
  if (line) lines.push(line)
  return lines
}

/** Wrapped lines of the mismatch tooltip, shared with the graph so the tip drawn above the cards matches. */
export const mismatchLines = (text: string) => tooltipLines(text)

/** One task as a card: status colour and glyph, live elapsed, files, attempt, labels and the mismatch mark. */
export function TaskNode({ task, box, serverNow, selected, onSelect, onTip }: TaskNodeProps): JSX.Element {
  const { w, h } = box
  const elapsed = taskElapsedMs(task, serverNow)
  const status = task.status
  const showReason = task.reason !== undefined && REASON_STATUSES.has(status)

  const [flash, setFlash] = useState(0)
  const previous = useRef(status)
  useEffect(() => {
    if (previous.current !== status) setFlash((n) => n + 1)
    previous.current = status
  }, [status])

  const meta = [task.id]
  if (elapsed !== null) meta.push(formatElapsed(elapsed))
  if (task.files > 0) meta.push(filesText(task.files))

  const chips = chipsFor(task)
  const shown: { chip: Chip; x: number }[] = []
  let cursor = 14
  const room = w - 14
  for (const chip of chips) {
    const width = chipWidth(chip.text)
    const remaining = chips.length - shown.length - 1
    const reserve = remaining > 0 ? chipWidth(`+${remaining}`) + 4 : 0
    if (cursor + width + reserve > room && shown.length > 0) break
    if (cursor + width > room) break
    shown.push({ chip, x: cursor })
    cursor += width + 4
  }
  const hidden = chips.length - shown.length

  const label = [
    `${task.id} ${task.title}`,
    STATUS_WORD[status],
    elapsed === null ? null : formatElapsed(elapsed),
    task.files > 0 ? filesText(task.files) : null,
    task.attempt > 1 ? `try ${task.attempt}` : null,
    task.reason ?? null,
    ...task.labels,
    task.pending_action ? `${task.pending_action === 'stop' ? 'Stop' : 'Retry'} requested` : null,
    task.mismatch ? `Mismatch: ${task.mismatch.text}` : null,
    task.ready ? null : 'waiting on dependencies',
  ]
    .filter(Boolean)
    .join(', ')

  const onKeyDown = (event: KeyboardEvent<SVGGElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(task.id)
    }
  }
  const shape = cardPath(w, h)

  return (
    <g
      className="run-node"
      data-task={task.id}
      data-status={status}
      data-ready={task.ready ? 'true' : 'false'}
      data-selected={selected ? 'true' : undefined}
      data-attempt={task.attempt > 1 ? String(task.attempt) : undefined}
      transform={`translate(${box.x} ${box.y})`}
      tabIndex={0}
      role="button"
      aria-label={label}
      aria-pressed={selected}
      onClick={() => onSelect(task.id)}
      onKeyDown={onKeyDown}
      onFocus={() => task.mismatch && onTip?.(task.id)}
      onBlur={() => task.mismatch && onTip?.(null)}
    >
      <title>{label}</title>
      <path className="run-node-card" d={shape} />
      {status === 'needs-you' ? <path className="run-node-pulse" d={shape} /> : null}
      {flash > 0 ? <path key={flash} className="run-node-flash" d={shape} /> : null}
      <rect className="run-node-stripe" x={0} y={2} width={STRIPE_W} height={h - 4} />
      {status === 'running' ? (
        <svg className="run-node-shimmer" x={0} y={2} width={STRIPE_W} height={h - 4} aria-hidden="true">
          <rect className="run-node-sweep" x={0} y={0} width={STRIPE_W} height={h * 0.45} />
        </svg>
      ) : null}
      <text className="run-node-title" x={16} y={26}>
        {clip(task.title, Math.floor((w - 60) / 8.8))}
      </text>
      <text className="run-node-meta" x={16} y={46}>
        {clip(meta.join(' · '), Math.floor((w - 32) / 8.2))}
      </text>
      {showReason ? (
        <text className="run-node-reason" x={16} y={63}>
          {clip(task.reason ?? '', Math.floor((w - 32) / 6.4))}
        </text>
      ) : null}
      <g className="run-node-status" transform={`translate(${w - 20} 20)`} aria-hidden="true">
        {status === 'retrying' ? <circle className="run-node-ring" r={10} /> : <circle className="run-node-dot" r={10} />}
        <text className="run-node-glyph" textAnchor="middle" dy="0.35em">
          {STATUS_GLYPH[status]}
        </text>
      </g>
      {shown.map(({ chip, x }) => (
        <g key={`${chip.kind}-${chip.text}`} className="run-node-chip" data-kind={chip.kind} transform={`translate(${x} ${h - CHIP_H - 8})`}>
          <rect width={chipWidth(chip.text)} height={CHIP_H} rx={CHIP_H / 2} />
          <text x={chipWidth(chip.text) / 2} y={CHIP_H / 2} textAnchor="middle" dy="0.35em">
            {chip.text}
          </text>
        </g>
      ))}
      {hidden > 0 ? (
        <g className="run-node-chip" data-kind="more" transform={`translate(${cursor} ${h - CHIP_H - 8})`}>
          <rect width={chipWidth(`+${hidden}`)} height={CHIP_H} rx={CHIP_H / 2} />
          <text x={chipWidth(`+${hidden}`) / 2} y={CHIP_H / 2} textAnchor="middle" dy="0.35em">
            {`+${hidden}`}
          </text>
        </g>
      ) : null}
      {task.mismatch ? (
        <g
          className="run-node-mark"
          transform={`translate(${w - 4} 4)`}
          onPointerEnter={() => onTip?.(task.id)}
          onPointerLeave={() => onTip?.(null)}
        >
          <title>{task.mismatch.text}</title>
          <circle r={10} />
          <text textAnchor="middle" dy="0.35em">
            !
          </text>
        </g>
      ) : null}
    </g>
  )
}
