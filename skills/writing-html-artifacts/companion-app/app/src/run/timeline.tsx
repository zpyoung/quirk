import type { JSX } from 'react'
import { formatElapsed } from './format'
import type { RunAttempt, RunStatus, RunTask, RunView } from './types'

const WIDTH = 880
const LABEL_W = 200
const PLOT_L = LABEL_W
const PLOT_R = WIDTH - 16
const ROW_H = 30
const BAR_H = 16
const TOP = 8
const AXIS_H = 28
const TICKS = 4
const MIN_SEG_W = 2
const TITLE_CHARS = 22

interface Row {
  task: RunTask
  firstStart: number
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

function shorten(text: string): string {
  return text.length > TITLE_CHARS ? `${text.slice(0, TITLE_CHARS - 1)}…` : text
}

/** One row per started task on a shared time axis; the open attempt reaches `serverNow` (ms), or the run's end once it has ended. */
export function Timeline({ run, serverNow }: { run: RunView; serverNow: number }): JSX.Element {
  const rows: Row[] = run.tasks
    .filter((task) => task.attempts.length > 0)
    .map((task) => ({ task, firstStart: Math.min(...task.attempts.map((attempt) => attempt.start)) }))
    .sort((a, b) => a.firstStart - b.firstStart)

  if (rows.length === 0) return <p className="run-timeline-empty" data-run-part="timeline">No task has started yet.</p>

  const t0 = rows[0].firstStart * 1000
  let latestEnd = t0
  for (const { task } of rows) {
    for (const attempt of task.attempts) if (attempt.end !== undefined) latestEnd = Math.max(latestEnd, attempt.end * 1000)
  }
  const tEnd = run.ended ? Math.max(latestEnd, run.ended.at * 1000) : Math.max(serverNow, latestEnd)
  const span = Math.max(tEnd - t0, 1000)
  const x = (ms: number) => PLOT_L + ((ms - t0) / span) * (PLOT_R - PLOT_L)
  const shown = new Set<RunStatus>()
  for (const { task } of rows) for (const attempt of task.attempts) shown.add(segmentStatus(task, attempt))
  const height = TOP + rows.length * ROW_H + AXIS_H
  const axisY = TOP + rows.length * ROW_H

  return (
    <div className="run-timeline-wrap">
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
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        role="img"
        aria-label="Task attempts over time"
      >
        {rows.map(({ task }, index) => {
          const y = TOP + index * ROW_H
          return (
            <g key={task.id} className="run-timeline-row" data-task={task.id}>
              <line className="run-timeline-grid" x1={PLOT_L} x2={PLOT_R} y1={y + ROW_H} y2={y + ROW_H} />
              <text className="run-timeline-label" x={0} y={y + ROW_H / 2} dominantBaseline="central">
                <title>{`${task.id} ${task.title}`}</title>
                <tspan className="run-timeline-id">{task.id}</tspan>
                <tspan>{` ${shorten(task.title)}`}</tspan>
              </text>
              {task.attempts.map((attempt) => {
                const start = attempt.start * 1000
                const end = attempt.end === undefined ? tEnd : attempt.end * 1000
                const left = x(start)
                const width = Math.max(MIN_SEG_W, x(Math.max(end, start)) - left)
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
                    width={width}
                    height={BAR_H}
                    rx={3}
                  >
                    <title>{`${task.id} try ${attempt.n}: ${attempt.outcome === undefined ? status : key}, ${formatElapsed(end - start)}`}</title>
                  </rect>
                )
              })}
            </g>
          )
        })}
        <g className="run-timeline-axis">
          <line x1={PLOT_L} x2={PLOT_R} y1={axisY} y2={axisY} />
          {Array.from({ length: TICKS + 1 }, (_, i) => {
            const tx = PLOT_L + ((PLOT_R - PLOT_L) * i) / TICKS
            const anchor = i === 0 ? 'start' : i === TICKS ? 'end' : 'middle'
            return (
              <g key={i}>
                <line x1={tx} x2={tx} y1={axisY} y2={axisY + 5} />
                <text x={tx} y={axisY + 18} textAnchor={anchor}>
                  {formatElapsed((span * i) / TICKS)}
                </text>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
