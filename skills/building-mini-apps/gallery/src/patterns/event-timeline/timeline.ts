import type { TimelineEntry, TimelineFilter, TimelineOrder, TimelineRow } from "./types"

/** Distinct entry types in first-seen order, for the type filter. */
export function entryTypes(entries: TimelineEntry[]): string[] {
  return [...new Set(entries.map((entry) => entry.type))]
}

const TYPE_OPTION_PREFIX = "type:"

/** The type select's item value for a type key; never empty, so a key of "" stays selectable. */
export function typeOptionValue(key: string): string {
  return TYPE_OPTION_PREFIX + key
}

/** The type key behind a value made by `typeOptionValue`, or null for any other value. */
export function typeFromOptionValue(value: string): string | null {
  return value.startsWith(TYPE_OPTION_PREFIX) ? value.slice(TYPE_OPTION_PREFIX.length) : null
}

/** The label to show for a type key: the configured label, else the key, else "No type" for an empty key. */
export function typeLabel(key: string, label?: string): string {
  return label || key || "No type"
}

/** Entries matching the type (when given) and containing the query in category, message, detail or type. */
export function filterEntries(entries: TimelineEntry[], { query, type }: TimelineFilter): TimelineEntry[] {
  const needle = query.trim().toLowerCase()
  return entries.filter((entry) => {
    if (type !== null && entry.type !== type) return false
    if (!needle) return true
    return [entry.category, entry.message, entry.detail ?? "", entry.type].some((text) =>
      text.toLowerCase().includes(needle)
    )
  })
}

/** A sorted copy. Entries with equal times keep their input order oldest first, and newest first is the exact mirror. */
export function sortEntries(entries: TimelineEntry[], order: TimelineOrder): TimelineEntry[] {
  const oldest = entries
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => a.entry.time - b.entry.time || a.index - b.index)
    .map(({ entry }) => entry)
  return order === "newest" ? oldest.reverse() : oldest
}

/**
 * The rows to draw: filtered, ordered entries and, when `playhead` is a finite
 * number, one divider between the entries the playhead has reached (time at or
 * before it) and those after it. Entries after the playhead are flagged `after`;
 * the last reached entry among the filtered ones is `current`.
 */
export function buildRows(
  entries: TimelineEntry[],
  options: TimelineFilter & { order: TimelineOrder; playhead?: number }
): TimelineRow[] {
  const { order, playhead } = options
  const ordered = sortEntries(filterEntries(entries, options), order)
  if (ordered.length === 0) return []
  if (playhead === undefined || !Number.isFinite(playhead)) {
    return ordered.map((entry) => ({ kind: "entry", entry, after: false, current: false }))
  }

  const reached = (entry: TimelineEntry) => entry.time <= playhead
  const reachedInOrder = ordered.filter(reached)
  const currentId = (order === "newest" ? reachedInOrder[0] : reachedInOrder.at(-1))?.id
  const rows: TimelineRow[] = ordered.map((entry) => ({
    kind: "entry",
    entry,
    after: !reached(entry),
    current: entry.id === currentId,
  }))

  const afterCount = ordered.filter((entry) => !reached(entry)).length
  const dividerAt = order === "newest" ? afterCount : ordered.length - afterCount
  rows.splice(dividerAt, 0, { kind: "playhead", time: playhead })
  return rows
}

/** Milliseconds as mm:ss, or h:mm:ss from one hour; negative and non-finite values read as zero. */
export function formatOffset(ms: number): string {
  const total = Number.isFinite(ms) && ms > 0 ? Math.floor(ms / 1000) : 0
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, "0")
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`
}
