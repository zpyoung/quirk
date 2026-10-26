import type { ReplayEvent, ReplayMarker, ReplaySnapshot } from "./types"

export const MARKER_KINDS = ["click", "navigation", "error"]
export const SPEEDS = [0.5, 1, 2, 4]
export const RIPPLE_MS = 700

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/** The value stored under `key` itself, never one inherited from Object.prototype ("constructor", "toString"). */
export function ownValue<T>(record: Record<string, T>, key: string): T | undefined {
  return Object.hasOwn(record, key) ? record[key] : undefined
}

/**
 * Scroll offset that keeps the followed row in view, or null when it already is.
 * With no row (playhead before the first entry) the list returns to the top.
 */
export function followScrollTop(
  scrollTop: number,
  clientHeight: number,
  row: { top: number; height: number } | null
): number | null {
  if (!row) return scrollTop === 0 ? null : 0
  if (row.top >= scrollTop && row.top + row.height <= scrollTop + clientHeight) {
    return null
  }
  const target =
    row.top < scrollTop ? row.top : row.top + row.height - clientHeight
  const next = Math.max(0, target)
  return next === scrollTop ? null : next
}

/** Stable sort by `at`, so callers may pass events and snapshots in any order. */
export function sortByTime<T extends { at: number }>(items: T[]): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => a.item.at - b.item.at || a.index - b.index)
    .map(({ item }) => item)
}

/** Time after playing `elapsedMs` of wall clock at `speed`; stops at the end. */
export function advance(
  time: number,
  elapsedMs: number,
  speed: number,
  durationMs: number
): { time: number; ended: boolean } {
  const next = time + elapsedMs * speed
  if (next >= durationMs) return { time: durationMs, ended: true }
  return { time: Math.max(0, next), ended: false }
}

export function seekBy(time: number, deltaMs: number, durationMs: number): number {
  return clamp(time + deltaMs, 0, durationMs)
}

/** The last snapshot at or before `time`, or the first one when the playhead is before all of them. Expects snapshots sorted by `at`. */
export function snapshotAt<S>(
  snapshots: ReplaySnapshot<S>[],
  time: number
): ReplaySnapshot<S> | undefined {
  let found: ReplaySnapshot<S> | undefined
  for (const snapshot of snapshots) {
    if (snapshot.at <= time) found = snapshot
    else break
  }
  return found ?? snapshots[0]
}

/** Time of the first click, navigation or error strictly after `time`, or the end when none is left. */
export function nextEventTime(
  events: ReplayEvent[],
  time: number,
  durationMs: number
): number {
  let best = durationMs
  for (const event of events) {
    if (!MARKER_KINDS.includes(event.kind)) continue
    if (event.at > time && event.at < best) best = event.at
  }
  return best
}

export function markerPositions(
  events: ReplayEvent[],
  durationMs: number
): ReplayMarker[] {
  if (durationMs <= 0) return []
  return sortByTime(events.filter((event) => MARKER_KINDS.includes(event.kind))).map(
    (event) => ({
      id: event.id,
      kind: event.kind,
      at: event.at,
      percent: clamp(event.at / durationMs, 0, 1) * 100,
    })
  )
}

/** Index of the last entry at or before `time`, or -1. Expects entries sorted by `at`. */
export function activeIndex(entries: ReplayEvent[], time: number): number {
  let found = -1
  for (let i = 0; i < entries.length; i++) {
    if (entries[i].at <= time) found = i
    else break
  }
  return found
}

/** Where the cursor sits: the latest click with a point at or before `time`. */
export function cursorAt(
  events: ReplayEvent[],
  time: number
): { x: number; y: number; ageMs: number } | undefined {
  let latest: ReplayEvent | undefined
  for (const event of events) {
    if (event.kind !== "click" || !event.point || event.at > time) continue
    if (!latest || event.at >= latest.at) latest = event
  }
  if (!latest?.point) return undefined
  return { x: latest.point.x, y: latest.point.y, ageMs: time - latest.at }
}

export function countByKind(events: ReplayEvent[], kind: string): number {
  return events.filter((event) => event.kind === kind).length
}

export function stepSpeed(speed: number, direction: 1 | -1): number {
  const index = SPEEDS.indexOf(speed)
  const from = index === -1 ? SPEEDS.indexOf(1) : index
  return SPEEDS[clamp(from + direction, 0, SPEEDS.length - 1)]
}

export function formatSpeed(speed: number): string {
  return `${speed}×`
}

export function formatClock(ms: number, withMillis = false): string {
  const safe = Math.max(0, ms)
  const totalSeconds = Math.floor(safe / 1000)
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0")
  const seconds = String(totalSeconds % 60).padStart(2, "0")
  if (!withMillis) return `${minutes}:${seconds}`
  return `${minutes}:${seconds}.${String(Math.floor(safe % 1000)).padStart(3, "0")}`
}

export function filterEntries(entries: ReplayEvent[], query: string): ReplayEvent[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return entries
  return entries.filter((entry) =>
    `${entry.label} ${entry.detail ?? ""}`.toLowerCase().includes(needle)
  )
}

export function isPlayable(recording: {
  durationMs: number
  snapshots: unknown[]
}): boolean {
  return recording.durationMs > 0 && recording.snapshots.length > 0
}
