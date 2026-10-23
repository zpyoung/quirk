import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import type { OpenHow, WorkspaceItem } from "./types"

type ItemListProps<T extends WorkspaceItem> = {
  items: T[]
  activeId?: string
  onOpen: (id: string, how: OpenHow) => void
  badge?: (item: T) => string | undefined
  tooltip?: (item: T) => string | undefined
}

function howOf(event: React.MouseEvent): OpenHow {
  if (event.metaKey || event.ctrlKey) return event.altKey ? "split" : "tab"
  return "here"
}

function Row<T extends WorkspaceItem>({
  item,
  active,
  onOpen,
  badge,
  tooltip,
}: Omit<ItemListProps<T>, "items" | "activeId"> & { item: T; active: boolean }) {
  const hover = tooltip?.(item)
  const label = badge?.(item)
  const row = (
    <button
      type="button"
      aria-current={active ? "true" : undefined}
      onClick={(event) => onOpen(item.id, howOf(event))}
      className={cn(
        "flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-1 text-left text-xs outline-none hover:border-border focus-visible:ring-2 focus-visible:ring-ring",
        active && "bg-sidebar-accent font-medium"
      )}
    >
      <span className="min-w-0 flex-1 truncate" title={hover ? undefined : item.title}>
        {item.title}
      </span>
      {label ? (
        <Badge variant="secondary" className="h-4 shrink-0 px-1.5 text-[10px]">
          {label}
        </Badge>
      ) : null}
    </button>
  )
  if (!hover) return row
  return (
    <Tooltip delayDuration={700}>
      <TooltipTrigger asChild>{row}</TooltipTrigger>
      <TooltipContent side="right" className="flex-col items-start gap-0.5">
        <span className="font-medium">{item.title}</span>
        <span>{hover}</span>
      </TooltipContent>
    </Tooltip>
  )
}

/** One plain row per record; click opens here, Mod-click in a new tab, Mod+Alt-click in a new group. */
export function ItemList<T extends WorkspaceItem>({
  items,
  activeId,
  onOpen,
  badge,
  tooltip,
}: ItemListProps<T>) {
  return (
    <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:!block">
      <ul aria-label="Items" className="flex flex-col gap-px p-1">
        {items.map((item) => (
          <li key={item.id}>
            <Row
              item={item}
              active={item.id === activeId}
              onOpen={onOpen}
              badge={badge}
              tooltip={tooltip}
            />
          </li>
        ))}
      </ul>
    </ScrollArea>
  )
}
