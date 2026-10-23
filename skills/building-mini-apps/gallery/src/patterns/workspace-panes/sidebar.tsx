import { useState, type RefObject } from "react"
import { PanelLeftCloseIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

import { ItemList } from "./item-list"
import type { OpenHow, WorkspaceItem } from "./types"

type SidebarProps<T extends WorkspaceItem> = {
  items: T[]
  loading: boolean
  activeId?: string
  filterRef: RefObject<HTMLInputElement | null>
  onOpen: (id: string, how: OpenHow) => void
  onCreate?: () => void
  onCollapse: () => void
  badge?: (item: T) => string | undefined
  tooltip?: (item: T) => string | undefined
}

export function Sidebar<T extends WorkspaceItem>({
  items,
  loading,
  activeId,
  filterRef,
  onOpen,
  onCreate,
  onCollapse,
  badge,
  tooltip,
}: SidebarProps<T>) {
  const [query, setQuery] = useState("")
  const needle = query.trim().toLowerCase()
  const shown = needle ? items.filter((i) => i.title.toLowerCase().includes(needle)) : items

  let list
  if (loading) {
    list = (
      <div role="status" className="flex flex-col gap-2 p-3">
        <span className="sr-only">Loading items</span>
        {[0, 1, 2, 3, 4].map((n) => (
          <Skeleton key={n} className="h-4 w-full" />
        ))}
      </div>
    )
  } else if (items.length === 0) {
    list = (
      <EmptyState
        title="No items yet"
        action={
          onCreate ? (
            <Button size="sm" variant="outline" onClick={onCreate}>
              New item
            </Button>
          ) : undefined
        }
      />
    )
  } else if (shown.length === 0) {
    list = <p className="p-3 text-xs text-muted-foreground">No items match.</p>
  } else {
    list = (
      <ItemList items={shown} activeId={activeId} onOpen={onOpen} badge={badge} tooltip={tooltip} />
    )
  }

  return (
    <nav aria-label="Items" className="flex h-full w-56 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-1 p-2">
        <Input
          ref={filterRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setQuery("")
              event.currentTarget.blur()
            }
          }}
          placeholder="Filter"
          aria-label="Filter items"
          className="h-7 text-xs"
        />
        <Button variant="ghost" size="icon-sm" aria-label="Hide sidebar" onClick={onCollapse}>
          <PanelLeftCloseIcon />
        </Button>
      </div>
      <Separator />
      {list}
      <Separator />
      <p className="px-3 py-1.5 text-xs text-muted-foreground">
        {loading ? "" : needle ? `${shown.length} of ${items.length} items` : `${items.length} items`}
      </p>
    </nav>
  )
}
