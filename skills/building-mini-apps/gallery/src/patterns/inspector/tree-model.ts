import type { InspectorItem } from "./types"

export type TreeRow<T extends InspectorItem> = {
  item: T
  depth: number
  hasChildren: boolean
  expanded: boolean
}

/** Flattens items into visible rows in display order; an item whose parent is missing becomes a root. */
export function buildRows<T extends InspectorItem>(
  items: T[],
  collapsed: ReadonlySet<string>
): TreeRow<T>[] {
  const ids = new Set(items.map((item) => item.id))
  const children = new Map<string, T[]>()
  const roots: T[] = []
  for (const item of items) {
    const parent = item.parentId
    if (parent && parent !== item.id && ids.has(parent)) {
      const siblings = children.get(parent)
      if (siblings) siblings.push(item)
      else children.set(parent, [item])
    } else {
      roots.push(item)
    }
  }

  const rows: TreeRow<T>[] = []
  const visit = (item: T, depth: number) => {
    const kids = children.get(item.id) ?? []
    const expanded = !collapsed.has(item.id)
    rows.push({ item, depth, hasChildren: kids.length > 0, expanded })
    if (expanded) for (const kid of kids) visit(kid, depth + 1)
  }
  for (const root of roots) visit(root, 0)
  return rows
}
