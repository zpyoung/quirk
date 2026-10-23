import type { PaletteItem } from "./types"

/** Adds `id` to `ids`, or removes it when present. */
export function toggleId(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((existing) => existing !== id) : [...ids, id]
}

/** `ids` plus every id of `order` between `from` and `to`, inclusive, in either direction. */
export function selectRange(ids: string[], order: string[], from: string, to: string): string[] {
  const start = order.indexOf(from)
  const end = order.indexOf(to)
  if (start < 0 || end < 0) return ids
  const [low, high] = start <= end ? [start, end] : [end, start]
  const next = [...ids]
  for (const id of order.slice(low, high + 1)) {
    if (!next.includes(id)) next.push(id)
  }
  return next
}

/** The items whose ids are checked, in `items` order. Ids with no matching item are ignored. */
export function resolveTargets<T extends PaletteItem>(items: T[], ids: string[]): T[] {
  if (ids.length === 0) return []
  const checked = new Set(ids)
  return items.filter((item) => checked.has(item.id))
}

export function selectionLabel(count: number): string {
  return `${count} selected`
}
