import { Button } from "@/components/ui/button"

import type { PendingChange, StagedColumn } from "./types"

function show(value: unknown): string {
  const text = value === undefined || value === null ? "" : String(value)
  return text === "" ? "(empty)" : text
}

type Line = { id: string; name: string; field: string; detail: string }

/**
 * Lists each pending change on one line, in the order edited, with Discard and
 * Commit at the bottom. Render it inside a popover or any other container.
 */
export function PendingPreview<T extends { id: string; title: string }>({
  changes,
  items,
  columns,
  onCommit,
  onDiscard,
}: {
  changes: PendingChange<T>[]
  items: T[]
  columns: StagedColumn<T>[]
  onCommit(): void
  onDiscard(): void
}) {
  const nameOf = (item: T) => item.title.trim() || item.id
  const stored = new Map(items.map((item) => [item.id, item]))
  const labelOf = new Map(columns.map((column) => [column.key as string, column.label]))

  const lines: Line[] = changes.flatMap((change): Line[] => {
    if (change.kind === "add") {
      return [{ id: `add:${change.item.id}`, name: nameOf(change.item), field: "", detail: "new row" }]
    }
    const item = stored.get(change.id)
    if (!item) return []
    if (change.kind === "remove") {
      return [{ id: `remove:${change.id}`, name: nameOf(item), field: "", detail: "removed" }]
    }
    return (Object.keys(change.patch) as (keyof T & string)[]).map((key) => ({
      id: `update:${change.id}:${key}`,
      name: nameOf(item),
      field: labelOf.get(key) ?? key,
      detail: `${show(item[key])} → ${show(change.patch[key])}`,
    }))
  })

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium">
        {lines.length} {lines.length === 1 ? "change" : "changes"}
      </p>
      <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto text-xs">
        {lines.map((line) => (
          <li key={line.id} className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1.4fr)] gap-2">
            <span className="truncate font-medium">{line.name}</span>
            <span className="text-muted-foreground">{line.field}</span>
            <span className="truncate text-muted-foreground">{line.detail}</span>
          </li>
        ))}
      </ul>
      <div className="flex justify-end gap-2 border-t pt-2">
        <Button variant="outline" size="sm" onClick={onDiscard}>
          Discard
        </Button>
        <Button size="sm" onClick={onCommit}>
          Commit
        </Button>
      </div>
    </div>
  )
}
