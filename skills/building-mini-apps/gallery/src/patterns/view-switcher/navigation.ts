import type { Column } from "./grouping"
import type { Rec } from "./fields"
import type { Layout } from "./types"

export type Direction = "up" | "down" | "left" | "right"

export interface NavContext {
  layout: Layout
  results: Rec[]
  columns: Column[]
  /** Records that have a date, in date order. */
  dated: Rec[]
}

/** Record ids in the order the arrow keys walk them. */
export function navIds({
  layout,
  results,
  columns,
  dated,
}: NavContext): string[] {
  if (layout === "board")
    return columns.flatMap((c) => c.items.map((i) => i.id))
  if (layout === "calendar") return dated.map((i) => i.id)
  return results.map((i) => i.id)
}

/** The record the arrow key lands on, or `activeId` itself when the key has nowhere to go. */
export function nextRecord(
  ctx: NavContext,
  activeId: string | null,
  dir: Direction
): string | null {
  const all = navIds(ctx)
  if (all.length === 0) return null
  if (activeId === null || !all.includes(activeId)) return all[0]

  if (dir === "up" || dir === "down") {
    const column =
      ctx.layout === "board"
        ? ctx.columns.find((c) => c.items.some((i) => i.id === activeId))
        : undefined
    const lane = column ? column.items.map((i) => i.id) : all
    const index = lane.indexOf(activeId) + (dir === "down" ? 1 : -1)
    return lane[Math.min(lane.length - 1, Math.max(0, index))]
  }

  if (ctx.layout !== "board") return activeId
  const filled = ctx.columns.filter((c) => c.items.length > 0)
  const from = filled.findIndex((c) => c.items.some((i) => i.id === activeId))
  const target = filled[from + (dir === "right" ? 1 : -1)]
  if (!target) return activeId
  const row = filled[from].items.findIndex((i) => i.id === activeId)
  return target.items[Math.min(row, target.items.length - 1)].id
}
