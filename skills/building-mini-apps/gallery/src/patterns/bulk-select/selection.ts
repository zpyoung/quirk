export type SelectionState = "none" | "some" | "all"

/** Whether none, some or all of `rowCount` visible rows are selected. */
export function selectionState(
  selectedCount: number,
  rowCount: number
): SelectionState {
  if (selectedCount <= 0 || rowCount <= 0) return "none"
  return selectedCount >= rowCount ? "all" : "some"
}

/** `selected` reduced to ids present in `order`, deduplicated, in row order. */
export function pruneSelection(order: string[], selected: string[]): string[] {
  const chosen = new Set(selected)
  return order.filter((id) => chosen.has(id))
}

/** Adds `id` to the selection if absent, removes it if present; result is in row order. */
export function toggleId(
  order: string[],
  selected: string[],
  id: string
): string[] {
  const chosen = new Set(selected)
  if (chosen.has(id)) chosen.delete(id)
  else chosen.add(id)
  return order.filter((rowId) => chosen.has(rowId))
}

/**
 * Selects (`on`) or deselects every row from `anchorId` to `targetId`, both
 * included, in either direction. An id missing from `order` leaves the
 * selection as it was.
 */
export function setRange(
  order: string[],
  selected: string[],
  anchorId: string,
  targetId: string,
  on: boolean
): string[] {
  const from = order.indexOf(anchorId)
  const to = order.indexOf(targetId)
  if (from === -1 || to === -1) return pruneSelection(order, selected)
  const chosen = new Set(selected)
  for (const id of order.slice(Math.min(from, to), Math.max(from, to) + 1)) {
    if (on) chosen.add(id)
    else chosen.delete(id)
  }
  return order.filter((id) => chosen.has(id))
}

/** The row after or before `current`, stopping at the ends; with no current row, the first or last. */
export function nextHighlight(
  order: string[],
  current: string | null,
  direction: "next" | "previous"
): string | null {
  if (order.length === 0) return null
  const index = current === null ? -1 : order.indexOf(current)
  if (index === -1)
    return direction === "next" ? order[0] : order[order.length - 1]
  const target = Math.min(
    order.length - 1,
    Math.max(0, index + (direction === "next" ? 1 : -1))
  )
  return order[target]
}

/**
 * Where the highlight goes when `id` leaves the table: the row now sitting at
 * its old position, or the last row, or nothing when the table is empty.
 */
export function neighbourAfterRemoval(
  previousOrder: string[],
  order: string[],
  id: string
): string | null {
  if (order.length === 0) return null
  const at = previousOrder.indexOf(id)
  if (at === -1) return null
  return order[Math.min(at, order.length - 1)]
}
