import { useMemo, useRef, useState, type MouseEvent } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ChevronRightIcon } from "lucide-react"

import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

import { buildRows } from "./tree-model"
import { TruncatedText } from "./truncated-text"
import type { InspectorItem } from "./types"

function RenameField({
  value,
  onFinish,
}: {
  value: string
  onFinish: (next: string | null, refocus: boolean) => void
}) {
  const done = useRef(false)
  const finish = (next: string | null, refocus: boolean) => {
    if (done.current) return
    done.current = true
    onFinish(next, refocus)
  }

  return (
    <Input
      autoFocus
      aria-label="Rename item"
      defaultValue={value}
      className="h-5 min-w-0 flex-1 rounded-sm px-1 py-0 text-sm md:text-sm"
      onFocus={(event) => event.currentTarget.select()}
      onClick={(event) => event.stopPropagation()}
      onDoubleClick={(event) => event.stopPropagation()}
      onBlur={(event) => finish(event.currentTarget.value, false)}
      onKeyDown={(event) => {
        event.stopPropagation()
        if (event.key === "Enter") {
          event.preventDefault()
          finish(event.currentTarget.value, true)
        } else if (event.key === "Escape") {
          event.preventDefault()
          finish(null, true)
        }
      }}
    />
  )
}

/**
 * Indented, collapsible list of items with a roving tab stop. Reports
 * selection intent through `onSelect` along with the rows currently visible
 * (collapsed descendants excluded); the owner decides what is selected.
 * Arrow keys move the selection, left/right fold a row, F2 renames it.
 */
export function ItemTree<T extends InspectorItem>({
  items,
  selectedIds,
  onSelect,
  onRename,
}: {
  items: T[]
  selectedIds: string[]
  onSelect: (
    id: string,
    mode: "replace" | "range" | "toggle",
    visibleIds: string[]
  ) => void
  onRename?: (id: string, title: string) => void
}) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(
    () => new Set()
  )
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [focusId, setFocusId] = useState<string | null>(null)
  const rowEls = useRef(new Map<string, HTMLElement>())

  const rows = useMemo(() => buildRows(items, collapsed), [items, collapsed])
  const visibleIds = useMemo(() => rows.map((row) => row.item.id), [rows])
  const selected = useMemo(() => new Set(selectedIds), [selectedIds])
  const tabStopId =
    rows.find((row) => row.item.id === focusId)?.item.id ??
    rows.find((row) => selected.has(row.item.id))?.item.id ??
    rows[0]?.item.id

  const setFolded = (id: string, folded: boolean) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (folded) next.add(id)
      else next.delete(id)
      return next
    })

  const treeRef = useHotkeys<HTMLDivElement>(
    ["up", "down", "left", "right", "f2"],
    (event) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const id = target.closest<HTMLElement>("[data-item-id]")?.dataset.itemId
      const index = rows.findIndex((row) => row.item.id === id)
      if (id === undefined || index < 0) return
      const row = rows[index]
      event.preventDefault()

      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        const next = rows[index + (event.key === "ArrowDown" ? 1 : -1)]
        if (!next) return
        onSelect(next.item.id, "replace", visibleIds)
        rowEls.current.get(next.item.id)?.focus()
      } else if (event.key === "ArrowLeft") {
        if (row.hasChildren && row.expanded) setFolded(id, true)
      } else if (event.key === "ArrowRight") {
        if (row.hasChildren && !row.expanded) setFolded(id, false)
      } else if (event.key === "F2" && onRename) {
        setRenamingId(id)
      }
    }
  )

  const finishRename = (id: string, next: string | null, refocus: boolean) => {
    setRenamingId(null)
    const title = next?.trim()
    const current = items.find((item) => item.id === id)
    if (title && current && title !== current.title) onRename?.(id, title)
    if (refocus) rowEls.current.get(id)?.focus()
  }

  const modeOf = (event: MouseEvent) =>
    event.shiftKey
      ? "range"
      : event.metaKey || event.ctrlKey
        ? "toggle"
        : "replace"

  return (
    <ScrollArea className="h-full [&_[data-slot=scroll-area-viewport]>div]:block!">
      <div
        ref={treeRef}
        role="tree"
        aria-label="Items"
        aria-multiselectable="true"
        className="flex flex-col gap-px p-1.5"
      >
        {rows.map(({ item, depth, hasChildren, expanded }) => {
          const isSelected = selected.has(item.id)
          return (
            <div
              key={item.id}
              ref={(el) => {
                if (el) rowEls.current.set(item.id, el)
                else rowEls.current.delete(item.id)
              }}
              role="treeitem"
              aria-level={depth + 1}
              aria-selected={isSelected}
              aria-expanded={hasChildren ? expanded : undefined}
              data-item-id={item.id}
              tabIndex={item.id === tabStopId ? 0 : -1}
              onFocus={() => setFocusId(item.id)}
              onClick={(event) => onSelect(item.id, modeOf(event), visibleIds)}
              onDoubleClick={() => onRename && setRenamingId(item.id)}
              style={{ paddingLeft: 4 + depth * 14 }}
              className={cn(
                "flex h-7 cursor-default items-center gap-1 rounded-md pr-2 text-sm outline-none select-none focus-visible:ring-2 focus-visible:ring-ring",
                isSelected ? "bg-primary/10 font-medium" : "hover:bg-muted"
              )}
            >
              <span
                aria-hidden
                className="grid size-4 shrink-0 place-items-center text-muted-foreground"
                onClick={(event) => {
                  if (!hasChildren) return
                  event.stopPropagation()
                  setFolded(item.id, expanded)
                }}
              >
                {hasChildren ? (
                  <ChevronRightIcon
                    className={cn(
                      "size-3 transition-transform",
                      expanded && "rotate-90"
                    )}
                  />
                ) : null}
              </span>
              <span
                aria-hidden
                className={cn(
                  "grid size-4 shrink-0 place-items-center rounded-sm text-[10px] leading-none font-semibold uppercase",
                  isSelected
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {item.type.charAt(0)}
              </span>
              {renamingId === item.id ? (
                <RenameField
                  value={item.title}
                  onFinish={(next, refocus) =>
                    finishRename(item.id, next, refocus)
                  }
                />
              ) : (
                <TruncatedText text={item.title} className="flex-1" />
              )}
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
