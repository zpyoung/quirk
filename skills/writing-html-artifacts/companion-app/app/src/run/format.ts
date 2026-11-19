import { useEffect, useState } from 'react'
import type { RunStatus, RunTask, RunView } from './types'

const COUNT_LABELS: [RunStatus, string][] = [
  ['running', 'running'],
  ['retrying', 'retrying'],
  ['needs-you', 'needs you'],
  ['failed', 'failed'],
  ['queued', 'queued'],
  ['stopped', 'stopped'],
  ['skipped', 'skipped'],
  ['missing', 'missing'],
]

const pad2 = (n: number) => String(n).padStart(2, '0')

/** Elapsed time as "2m 31s", or "1h 02m" from an hour up; negative input reads as zero. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (hours > 0) return `${hours}h ${pad2(minutes)}m`
  return `${minutes}m ${pad2(total % 60)}s`
}

/** Header counts such as "1 of 3 passed · 1 running"; empty for a run with no tasks. */
export function countsLine(run: RunView): string {
  if (run.tasks.length === 0) return ''
  const tally = new Map<RunStatus, number>()
  for (const task of run.tasks) tally.set(task.status, (tally.get(task.status) ?? 0) + 1)
  const parts = [`${tally.get('passed') ?? 0} of ${run.tasks.length} passed`]
  for (const [status, label] of COUNT_LABELS) {
    const n = tally.get(status) ?? 0
    if (n > 0) parts.push(`${n} ${label}`)
  }
  return parts.join(' · ')
}

export function staleText(seconds: number): string {
  if (seconds < 60) return `No update for ${Math.floor(seconds)}s`
  return `No update for ${Math.floor(seconds / 60)} min`
}

/** Server clock minus client clock, captured when a snapshot arrives. */
export function serverOffsetMs(run: RunView, clientNowMs: number): number {
  return run.now * 1000 - clientNowMs
}

/** Seconds since the last update once it passes the stale threshold; null for a fresh or ended run, or one with no update yet. */
export function staleSince(run: RunView, serverNowMs: number): number | null {
  if (run.ended) return null
  if (run.last_update_at === null || run.last_update_at === undefined) return null
  const seconds = Math.floor(serverNowMs / 1000 - run.last_update_at)
  return seconds > run.stale_after_s ? seconds : null
}

/** Time a task has run so far, frozen at its end; null when it never started. */
export function taskElapsedMs(task: RunTask, serverNowMs: number): number | null {
  if (task.started_at === undefined) return null
  const end = task.ended_at === undefined ? serverNowMs : task.ended_at * 1000
  return Math.max(0, end - task.started_at * 1000)
}

/** Date.now(), re-rendering the caller every `intervalMs`. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

export type PageKind = 'diff' | 'findings' | 'run' | 'brainstorm'

/**
 * Chooses the page from the query string and whether the snapshot carries a run. Lives here, not in App.tsx,
 * because the check scripts run under node and cannot load App's theme import; App re-exports it.
 */
export function pickPage(search: string, hasRun: boolean): PageKind {
  const params = new URLSearchParams(search)
  const view = params.get('view')
  if (view === 'diff' && params.get('task')) return 'diff'
  if (view === 'findings' && params.get('round')) return 'findings'
  return hasRun ? 'run' : 'brainstorm'
}
