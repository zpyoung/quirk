import { useEffect, useRef } from "react"
import { CheckIcon, ChevronDownIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

import type { TabGroup } from "./types"

type TabStripProps = {
  group: TabGroup
  titleOf: (itemId: string | null) => string
  mutedOf?: (itemId: string | null) => boolean
  onSelect: (tabId: string) => void
  onClose: (tabId: string) => void
  onNew: () => void
  onSplit?: (tabId: string) => void
  onCloseOthers?: (tabId: string) => void
}

/** Scrolling strip of a group's tabs with a "+" button and a menu listing every tab. */
export function TabStrip({
  group,
  titleOf,
  mutedOf,
  onSelect,
  onClose,
  onNew,
  onSplit,
  onCloseOthers,
}: TabStripProps) {
  const activeRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest", inline: "nearest" })
  }, [group.activeTabId, group.tabs.length])

  return (
    <div className="flex h-[38px] shrink-0 items-center border-b bg-sidebar/50">
      <div
        role="tablist"
        aria-label="Open tabs"
        className="flex h-full min-w-0 flex-1 overflow-x-auto [scrollbar-width:none]"
      >
        {group.tabs.map((tab) => {
          const active = tab.tabId === group.activeTabId
          const title = titleOf(tab.itemId)
          const muted = mutedOf?.(tab.itemId) ?? false
          return (
            <ContextMenu key={tab.tabId}>
              <ContextMenuTrigger asChild>
                <div
                  ref={active ? activeRef : undefined}
                  className={cn(
                    "relative flex h-full w-[155px] shrink-0 items-center border-r text-xs",
                    active ? "bg-background text-foreground" : "text-muted-foreground hover:bg-accent/50"
                  )}
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={active}
                    data-tab-id={tab.tabId}
                    title={title}
                    onClick={() => onSelect(tab.tabId)}
                    className={cn(
                      "h-full min-w-0 flex-1 truncate px-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      muted && "italic opacity-70"
                    )}
                  >
                    {title}
                  </button>
                  {active ? (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className="mr-1 shrink-0"
                      aria-label={`Close ${title}`}
                      onClick={() => onClose(tab.tabId)}
                    >
                      <XIcon />
                    </Button>
                  ) : null}
                </div>
              </ContextMenuTrigger>
              <ContextMenuContent>
                {onSplit ? (
                  <ContextMenuItem onSelect={() => onSplit(tab.tabId)}>Split right</ContextMenuItem>
                ) : null}
                <ContextMenuItem onSelect={() => onClose(tab.tabId)}>Close</ContextMenuItem>
                {onCloseOthers ? (
                  <>
                    <ContextMenuSeparator />
                    <ContextMenuItem
                      disabled={group.tabs.length < 2}
                      onSelect={() => onCloseOthers(tab.tabId)}
                    >
                      Close others
                    </ContextMenuItem>
                  </>
                ) : null}
              </ContextMenuContent>
            </ContextMenu>
          )
        })}
      </div>
      <Button variant="ghost" size="icon-sm" aria-label="New tab" onClick={onNew}>
        <PlusIcon />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="List all tabs" className="mr-1">
            <ChevronDownIcon />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-56"
          onCloseAutoFocus={(event) => event.preventDefault()}
        >
          {group.tabs.map((tab) => (
            <DropdownMenuItem key={tab.tabId} onSelect={() => onSelect(tab.tabId)}>
              <span className="min-w-0 flex-1 truncate">{titleOf(tab.itemId)}</span>
              {tab.tabId === group.activeTabId ? <CheckIcon /> : null}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
