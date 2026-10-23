import { addDays, nextMonday, set, startOfDay } from "date-fns"

import type {
  AttentionItem,
  FlagRule,
  ItemAction,
  ItemStatus,
  RuleMemory,
  Tile,
  TimelineEvent,
} from "./types"

const DAY_MS = 86_400_000
const HOUR_MS = 3_600_000

const DECIDING = new Set<TimelineEvent["type"]>([
  "opened",
  "reopened",
  "acknowledged",
  "snoozed",
  "snooze-ended",
  "resolved",
  "cleared",
])

function lastDeciding(item: AttentionItem): TimelineEvent | undefined {
  for (let i = item.timeline.length - 1; i >= 0; i--) {
    if (DECIDING.has(item.timeline[i].type)) return item.timeline[i]
  }
  return undefined
}

function isResolved(item: AttentionItem): boolean {
  const type = lastDeciding(item)?.type
  return type === "resolved" || type === "cleared"
}

/** Derives an item's status from its timeline; status is never stored. */
export function itemStatus(item: AttentionItem, now: number): ItemStatus {
  const last = lastDeciding(item)
  switch (last?.type) {
    case "acknowledged":
      return "acknowledged"
    case "snoozed":
      return (last.until ?? 0) > now ? "snoozed" : "open"
    case "resolved":
    case "cleared":
      return "resolved"
    default:
      return "open"
  }
}

export function isStale(tile: Tile, now: number): boolean {
  return (
    tile.staleAfterMs !== undefined && now - tile.updatedAt > tile.staleAfterMs
  )
}

/** The words for a tile's state; the tile, dialog, cleared text and confirm copy share it. */
export function stateText(tile: Tile): string {
  const unit = tile.unit ?? ""
  switch (tile.kind) {
    case "toggle":
      return tile.on ? (tile.onLabel ?? "On") : (tile.offLabel ?? "Off")
    case "level":
      return tile.on ? `${tile.value ?? 0}${unit}` : (tile.offLabel ?? "Off")
    case "target":
      return `${tile.value ?? 0}${unit} · target ${tile.target ?? 0}${unit}`
    case "sensor":
      return tile.text ?? `${tile.value ?? 0}${unit}`
  }
}

type ActiveRule = {
  id: string
  tileId: string
  title: string
  urgency: FlagRule["urgency"]
  test: (tile: Tile) => boolean
  occurrence?: (tile: Tile) => string
}

function staleRuleId(tileId: string): string {
  return `stale:${tileId}`
}

function withStaleRules(
  rules: FlagRule[],
  tiles: Tile[],
  now: number
): ActiveRule[] {
  const synthetic: ActiveRule[] = tiles
    .filter((tile) => tile.staleOpensItem)
    .map((tile) => ({
      id: staleRuleId(tile.id),
      tileId: tile.id,
      title: `${tile.name} has not reported`,
      urgency: "later",
      test: (t) => isStale(t, now),
    }))
  return [...rules, ...synthetic]
}

function openedAt(item: AttentionItem): number {
  return item.timeline[0]?.at ?? 0
}

function latestItemFor(
  items: AttentionItem[],
  ruleId: string
): AttentionItem | undefined {
  let latest: AttentionItem | undefined
  for (const item of items) {
    if (
      item.ruleId === ruleId &&
      (!latest || openedAt(item) >= openedAt(latest))
    )
      latest = item
  }
  return latest
}

function resolvedAt(item: AttentionItem): number {
  return lastDeciding(item)?.at ?? 0
}

/**
 * Compares each rule's condition with what `previous` remembers and returns the
 * items to add, the events to append to existing items, and the next memory.
 * A flag is an edge: it fires when a condition turns true or its occurrence key
 * changes while true, never on every evaluation.
 */
export function evaluateRules(input: {
  tiles: Tile[]
  items: AttentionItem[]
  rules: FlagRule[]
  previous: RuleMemory
  now: number
  newId: () => string
}): {
  add: AttentionItem[]
  append: Array<{ id: string; events: TimelineEvent[] }>
  memory: RuleMemory
} {
  const { tiles, items, rules, previous, now, newId } = input
  const add: AttentionItem[] = []
  const append: Array<{ id: string; events: TimelineEvent[] }> = []
  const memory: RuleMemory = { ...previous }

  for (const rule of withStaleRules(rules, tiles, now)) {
    const tile = tiles.find((t) => t.id === rule.tileId)
    if (!tile) continue

    const on = rule.test(tile)
    const occurrence = rule.occurrence?.(tile)
    const before = previous[rule.id] ?? { on: false }
    const fires = on && (!before.on || before.occurrence !== occurrence)
    const latest = latestItemFor(items, rule.id)

    if (fires) {
      if (latest && !isResolved(latest)) {
        append.push({
          id: latest.id,
          events: [{ at: now, type: "flagged-again" }],
        })
      } else if (latest && now - resolvedAt(latest) < DAY_MS) {
        append.push({ id: latest.id, events: [{ at: now, type: "reopened" }] })
      } else {
        add.push({
          v: 1,
          id: newId(),
          title: rule.title,
          urgency: rule.urgency,
          tileId: tile.id,
          ruleId: rule.id,
          timeline: [{ at: now, type: "opened" }],
        })
      }
    } else if (before.on && !on && latest && !isResolved(latest)) {
      append.push({
        id: latest.id,
        events: [
          {
            at: now,
            type: "cleared",
            text: `Cleared: ${tile.name} ${stateText(tile).toLowerCase()}`,
          },
        ],
      })
    }

    memory[rule.id] = { on, occurrence }
  }

  return { add, append, memory }
}

/** Returns the events an action adds, or none when the current status does not allow it. */
export function applyItemAction(
  item: AttentionItem,
  action: ItemAction,
  now: number
): TimelineEvent[] {
  const status = itemStatus(item, now)
  switch (action.type) {
    case "acknowledge":
      return status === "open" ? [{ at: now, type: "acknowledged" }] : []
    case "snooze": {
      if (status !== "open" && status !== "acknowledged") return []
      if (action.until <= now) return []
      const note = action.note?.trim()
      return [
        {
          at: now,
          type: "snoozed",
          until: action.until,
          ...(note ? { note } : {}),
        },
      ]
    }
    case "resolve":
      return status === "resolved" ? [] : [{ at: now, type: "resolved" }]
  }
}

/** Appends one `snooze-ended` per elapsed snooze, stamped at the snooze's own end time. */
export function endExpiredSnoozes(
  items: AttentionItem[],
  now: number
): Array<{ id: string; events: TimelineEvent[] }> {
  const ended: Array<{ id: string; events: TimelineEvent[] }> = []
  for (const item of items) {
    const last = lastDeciding(item)
    if (
      last?.type === "snoozed" &&
      last.until !== undefined &&
      last.until <= now
    ) {
      ended.push({
        id: item.id,
        events: [{ at: last.until, type: "snooze-ended" }],
      })
    }
  }
  return ended
}

/**
 * Memory for a fresh mount. A rule counts as already true when its latest item
 * is unresolved or was resolved by hand, so a reload never re-flags something
 * the user dismissed while the condition still held.
 */
export function initialRuleMemory(
  items: AttentionItem[],
  rules: FlagRule[],
  tiles: Tile[]
): RuleMemory {
  const memory: RuleMemory = {}
  for (const rule of withStaleRules(rules, tiles, 0)) {
    const tile = tiles.find((t) => t.id === rule.tileId)
    if (!tile) continue
    const latest = latestItemFor(items, rule.id)
    const on =
      !!latest &&
      (!isResolved(latest) || lastDeciding(latest)?.type === "resolved")
    memory[rule.id] = { on, occurrence: rule.occurrence?.(tile) }
  }
  return memory
}

/** Preset snooze times relative to `now`; "This evening" is omitted after 17:00. */
export function snoozePresets(
  now: number
): Array<{ label: string; until: number }> {
  const today = new Date(now)
  const at = (date: Date, hours: number) =>
    set(date, { hours, minutes: 0, seconds: 0, milliseconds: 0 })
  const presets: Array<{ label: string; until: number }> = [
    { label: "1 hour", until: now + HOUR_MS },
  ]
  if (today.getHours() < 17) {
    presets.push({ label: "This evening", until: at(today, 18).getTime() })
  }
  presets.push(
    {
      label: "Tomorrow morning",
      until: at(addDays(startOfDay(today), 1), 8).getTime(),
    },
    { label: "Next week", until: at(nextMonday(today), 8).getTime() }
  )
  return presets
}
