import { useEffect, useRef, useState, type JSX, type RefObject } from 'react'
import { formatElapsed } from './format'
import type { RunAttempt, RunStatus, RunTask, RunView } from './types'

const FALLBACK_WIDTH = 880
const MIN_WIDTH = 320
const NARROW_WIDTH = 560
const RIGHT_PAD = 16
const ROW_H = 28
const BAR_H = 14
const AXIS_H = 26
const MIN_SEG_W = 3
const CHAR_W = 6.6
const QUEUED_W = 40
const TICK_STEPS_S = [10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400, 21600, 43200, 86400]

interface Row {
  task: RunTask
  firstStart: number | null
}

const OUTCOME_STATUS: Record<string, RunStatus> = {
  passed: 'passed',
  failed: 'failed',
  stopped: 'stopped',
  skipped: 'skipped',
  queued: 'queued',
  retry: 'retrying',
}

const IN_PROGRESS = new Set<RunStatus>(['running', 'retrying', 'needs-you'])

const LEGEND_ORDER: [RunStatus, string][] = [
  ['running', 'running'],
  ['retrying', 'retrying'],
  ['needs-you', 'needs you'],
  ['passed', 'passed'],
  ['failed', 'failed'],
  ['stopped', 'stopped'],
  ['skipped', 'skipped'],
  ['queued', 'queued'],
]

/** Colour key of one attempt: its outcome once it ended, else the task's own in-progress status. */
function segmentStatus(task: RunTask, attempt: RunAttempt): RunStatus {
  if (attempt.outcome !== undefined) return OUTCOME_STATUS[attempt.outcome] ?? 'running'
  return IN_PROGRESS.has(task.status) ? task.status : 'running'
}

function outcomeKey(attempt: RunAttempt): string {
  return attempt.outcome ?? 'running'
}

function fit(text: string, chars: number): string {
  if (chars <= 1) return ''
  return text.length > chars ? `${text.slice(0, chars - 1)}…` : text
}

/** Smallest step from a fixed ladder that keeps the gridlines across `spanS` seconds at or under `maxTicks`. */
function tickStep(spanS: number, maxTicks: number): number {
  return TICK_STEPS_S.find((step) => spanS / step <= maxTicks) ?? TICK_STEPS_S[TICK_STEPS_S.length - 1]
}

function tickLabel(seconds: number): string {
  if (seconds === 0) return '0'
  if (seconds % 3600 === 0) return `+${seconds / 3600}h`
  if (seconds % 60 === 0) return `+${seconds / 60}m`
  return `+${seconds}s`
}

function useWidth(): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(FALLBACK_WIDTH)
  useEffect(() => {
    const node = ref.current
    if (!node || typeof ResizeObserver === 'undefined') return
    const measure = () => {
      const next = Math.floor(node.clientWidth)
      if (next > 0) setWidth(next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

/**
 * Waterfall of task attempts on a shared time axis, drawn at true pixel size: one row per task, a bar per attempt,
 * and connectors along dependency and ordering edges. The open attempt reaches `serverNow` (ms), or the run's end once it has ended.
 */
export function Timeline({ run, serverNow }: { run: RunView; serverNow: number }): JSX.Element {
  const [wrapRef, measured] = useWidth()
  const started: Row[] = run.tasks
    .filter((task) => task.attempts.length > 0)
    .map((task) => ({ task, firstStart: Math.min(...task.attempts.map((attempt) => attempt.start)) }))
    .sort((a, b) => (a.firstStart as number) - (b.firstStart as number))

  if (started.length === 0) return <p className="run-timeline-empty" data-run-part="timeline">No task has started yet.</p>

  const queued: Row[] = run.tasks.filter((task) => task.attempts.length === 0).map((task) => ({ task, firstStart: null }))
  const rows = [...started, ...queued]
  const width = Math.max(MIN_WIDTH, measured)
  const labelW = width < NARROW_WIDTH ? 140 : 220
  const plotL = labelW
  const plotR = width - RIGHT_PAD

  const t0 = (started[0].firstStart as number) * 1000
  let latestEnd = t0
  for (const { task } of started) {
    for (const attempt of task.attempts) if (attempt.end !== undefined) latestEnd = Math.max(latestEnd, attempt.end * 1000)
  }
  const tEnd = run.ended ? Math.max(latestEnd, run.ended.at * 1000) : Math.max(serverNow, latestEnd)
  const span = Math.max(tEnd - t0, 1000)
  const x = (ms: number) => plotL + ((ms - t0) / span) * (plotR - plotL)
  const rowIndex = new Map(rows.map((row, index) => [row.task.id, index]))
  const rowCenter = (id: string) => AXIS_H + (rowIndex.get(id) as number) * ROW_H + ROW_H / 2
  const taskById = new Map(run.tasks.map((task) => [task.id, task]))
  const firstStartMs = (task: RunTask) => Math.min(...task.attempts.map((attempt) => attempt.start)) * 1000
  const lastEndMs = (task: RunTask) =>
    Math.max(...task.attempts.map((attempt) => (attempt.end === undefined ? tEnd : attempt.end * 1000)))

  const shown = new Set<RunStatus>()
  for (const { task } of started) for (const attempt of task.attempts) shown.add(segmentStatus(task, attempt))
  const height = AXIS_H + rows.length * ROW_H + 4
  const plotBottom = height - 4

  const stepS = tickStep(span / 1000, 8)
  const ticks: number[] = []
  for (let s = 0; s * 1000 <= span; s += stepS) ticks.push(s)

  const links = run.edges.filter((edge) => {
    const from = taskById.get(edge.from)
    const to = taskById.get(edge.to)
    return from !== undefined && to !== undefined && from.attempts.length > 0 && to.attempts.length > 0
  })
  const nowX = x(tEnd)

  return (
    <div className="run-timeline-wrap" ref={wrapRef}>
      <ul className="run-timeline-legend" aria-label="Segment colours">
        {LEGEND_ORDER.filter(([status]) => shown.has(status)).map(([status, label]) => (
          <li key={status} className="run-timeline-legend-item">
            <span className="run-legend-swatch" data-status={status} aria-hidden="true" />
            {label}
          </li>
        ))}
      </ul>
      <svg
        className="run-timeline"
        data-run-part="timeline"
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="img"
        aria-label="Task attempts over time"
      >
        <g className="run-timeline-axis">
          <line x1={plotL} x2={plotR} y1={AXIS_H} y2={AXIS_H} />
          {ticks.map((s) => {
            const tx = x(t0 + s * 1000)
            return (
              <g key={s} className="run-timeline-tick" data-tick={s}>
                <line className="run-timeline-vgrid" x1={tx} x2={tx} y1={AXIS_H} y2={plotBottom} />
                <line x1={tx} x2={tx} y1={AXIS_H - 4} y2={AXIS_H} />
                <text x={tx} y={AXIS_H - 9} textAnchor={s === 0 ? 'start' : 'middle'}>
                  {tickLabel(s)}
                </text>
              </g>
            )
          })}
        </g>
        {rows.map(({ task }, index) => {
          const y = AXIS_H + index * ROW_H
          return <line key={task.id} className="run-timeline-grid" x1={0} x2={plotR} y1={y + ROW_H} y2={y + ROW_H} />
        })}
        <g className="run-timeline-links">
          {links.map((edge) => {
            const from = taskById.get(edge.from) as RunTask
            const to = taskById.get(edge.to) as RunTask
            const x1 = x(lastEndMs(from))
            const x2 = x(firstStartMs(to))
            const y1 = rowCenter(from.id)
            const y2 = rowCenter(to.id)
            const bend = Math.min(x1 + 6, Math.max(x1, (x1 + x2) / 2))
            return (
              <g
                key={`${edge.kind}:${edge.from}>${edge.to}`}
                className={`run-timeline-link run-timeline-link--${edge.kind}`}
                data-from={edge.from}
                data-to={edge.to}
              >
                <path d={`M${x1},${y1} H${bend} V${y2} H${x2 - 1}`} fill="none" />
                <path className="run-timeline-arrow" d={`M${x2},${y2} l-5,-3 v6 z`} />
              </g>
            )
          })}
        </g>
        {rows.map(({ task, firstStart }, index) => {
          const y = AXIS_H + index * ROW_H
          const titleChars = Math.floor((labelW - 12) / CHAR_W) - task.id.length - 1
          return (
            <g key={task.id} className="run-timeline-row" data-task={task.id} data-queued={firstStart === null ? 'true' : undefined}>
              <text className="run-timeline-label" x={0} y={y + ROW_H / 2} dominantBaseline="central">
                <title>{`${task.id} ${task.title}`}</title>
                <tspan className="run-timeline-id">{task.id}</tspan>
                <tspan>{` ${fit(task.title, titleChars)}`}</tspan>
              </text>
              {firstStart === null ? (
                <QueuedMark task={task} x={Math.min(nowX, plotR - QUEUED_W)} y={y} plotR={plotR} />
              ) : (
                <>
                  {task.attempts.map((attempt) => {
                    const start = attempt.start * 1000
                    const end = attempt.end === undefined ? tEnd : attempt.end * 1000
                    const left = x(start)
                    const barW = Math.max(MIN_SEG_W, x(Math.max(end, start)) - left)
                    const key = outcomeKey(attempt)
                    const status = segmentStatus(task, attempt)
                    return (
                      <rect
                        key={attempt.n}
                        className={`run-timeline-seg run-timeline-seg--${status}`}
                        data-attempt={attempt.n}
                        data-outcome={key}
                        data-status={status}
                        data-open={attempt.outcome === undefined ? 'true' : undefined}
                        x={left}
                        y={y + (ROW_H - BAR_H) / 2}
                        width={barW}
                        height={BAR_H}
                        rx={3}
                      >
                        <title>{`${task.id} try ${attempt.n}: ${attempt.outcome === undefined ? status : key}, ${formatElapsed(end - start)}`}</title>
                      </rect>
                    )
                  })}
                  <Elapsed
                    text={formatElapsed(lastEndMs(task) - firstStartMs(task))}
                    first={x(firstStartMs(task))}
                    last={Math.max(x(lastEndMs(task)), x(firstStartMs(task)) + MIN_SEG_W)}
                    y={y + ROW_H / 2}
                    plotR={plotR}
                  />
                </>
              )}
            </g>
          )
        })}
        {!run.ended && (
          <g className="run-timeline-now">
            <line x1={nowX} x2={nowX} y1={AXIS_H} y2={plotBottom} />
            <text x={Math.min(nowX, plotR - 12)} y={AXIS_H + 11} textAnchor={nowX > plotR - 24 ? 'end' : 'middle'}>
              now
            </text>
          </g>
        )}
      </svg>
    </div>
  )
}

function Elapsed({ text, first, last, y, plotR }: { text: string; first: number; last: number; y: number; plotR: number }): JSX.Element {
  const width = text.length * CHAR_W
  const flip = last + 4 + width > plotR
  // a bar that runs to the right edge carries its time inside, clear of the connector arrowheads at its start
  const inside = flip && last - first > width + 12
  const x = inside ? last - 6 : flip ? first - 4 : last + 4
  return (
    <text
      className={inside ? 'run-timeline-elapsed run-timeline-elapsed--inside' : 'run-timeline-elapsed'}
      x={x}
      y={y}
      textAnchor={flip ? 'end' : 'start'}
      dominantBaseline="central"
    >
      {text}
    </text>
  )
}

function QueuedMark({ task, x, y, plotR }: { task: RunTask; x: number; y: number; plotR: number }): JSX.Element {
  const note = task.blocked_by.length > 0 ? `blocked by ${task.blocked_by.join(', ')}` : 'queued'
  const flip = x + QUEUED_W + 6 + note.length * CHAR_W > plotR
  return (
    <>
      <rect className="run-timeline-queued" x={x} y={y + (ROW_H - BAR_H) / 2} width={QUEUED_W} height={BAR_H} rx={3} />
      <text className="run-timeline-elapsed" x={flip ? x - 6 : x + QUEUED_W + 6} y={y + ROW_H / 2} textAnchor={flip ? 'end' : 'start'} dominantBaseline="central">
        {note}
      </text>
    </>
  )
}
