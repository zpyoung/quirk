import { useMemo, useRef, useState, type RefObject } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

import { itemStatus } from "./attention"
import { ageText } from "./format"
import { ItemDetail, StatusLabel } from "./item-detail"
import type { AttentionItem, ItemAction, Tile, Urgency } from "./types"

const GROUPS: Array<{ urgency: Urgency; label: string }> = [
  { urgency: "now", label: "Now" },
  { urgency: "later", label: "Later" },
]

function openedAt(item: AttentionItem): number {
  for (let i = item.timeline.length - 1; i >= 0; i--) {
    const { type, at } = item.timeline[i]
    if (type === "opened" || type === "reopened") return at
  }
  return item.timeline[0]?.at ?? 0
}

function useQueueHotkeys(
  root: RefObject<HTMLElement | null>,
  keys: string,
  run: (event: KeyboardEvent) => void,
  enabled: boolean
) {
  useHotkeys(
    keys,
    (event) => {
      if (event.target instanceof Node && root.current?.contains(event.target))
        run(event)
    },
    { enabled }
  )
}

/**
 * Items that need the user, Now before Later and newest first. Keys, active
 * only while focus is inside the queue and not in a field: j/k move, a
 * acknowledges, s snoozes, r resolves, Enter expands.
 */
export function AttentionQueue({
  items,
  tiles,
  now,
  onAct,
  onOpenTile,
}: {
  items: AttentionItem[]
  tiles: Tile[]
  now: number
  onAct(itemId: string, action: ItemAction): void
  onOpenTile(id: string): void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [snoozeFor, setSnoozeFor] = useState<string | null>(null)

  const groups = useMemo(
    () =>
      GROUPS.map(({ urgency, label }) => ({
        urgency,
        label,
        items: items
          .filter((item) => {
            const status = itemStatus(item, now)
            return (
              item.urgency === urgency &&
              (status === "open" || status === "acknowledged")
            )
          })
          .sort((a, b) => openedAt(b) - openedAt(a)),
      })).filter((group) => group.items.length > 0),
    [items, now]
  )
  const flat = groups.flatMap((group) => group.items)
  const selected = flat.find((item) => item.id === selectedId) ?? flat[0]

  const focusRow = (id: string | undefined) => {
    if (!id) return
    requestAnimationFrame(() => {
      rootRef.current
        ?.querySelector<HTMLElement>(
          `[data-item-id="${CSS.escape(id)}"] [data-queue-row]`
        )
        ?.focus()
    })
  }

  const moveSelection = (to: AttentionItem | undefined) => {
    if (!to) return
    setSelectedId(to.id)
    if (expandedId !== null) setExpandedId(to.id)
    focusRow(to.id)
  }

  const neighbourOf = (item: AttentionItem) => {
    const index = flat.findIndex((candidate) => candidate.id === item.id)
    return flat[index + 1] ?? flat[index - 1]
  }

  const act = (item: AttentionItem, action: ItemAction) => {
    if (action.type !== "acknowledge") {
      const next = neighbourOf(item)
      setSelectedId(next?.id ?? null)
      if (expandedId === item.id) setExpandedId(null)
      focusRow(next?.id)
    }
    setSnoozeFor(null)
    onAct(item.id, action)
  }

  const keysEnabled = flat.length > 0 && snoozeFor === null
  const step = (delta: number) => {
    if (!selected) return
    const index = flat.findIndex((item) => item.id === selected.id)
    moveSelection(flat[Math.min(flat.length - 1, Math.max(0, index + delta))])
  }

  useQueueHotkeys(rootRef, "j", () => step(1), keysEnabled)
  useQueueHotkeys(rootRef, "k", () => step(-1), keysEnabled)
  useQueueHotkeys(
    rootRef,
    "a",
    () => selected && act(selected, { type: "acknowledge" }),
    keysEnabled
  )
  useQueueHotkeys(
    rootRef,
    "r",
    () => selected && act(selected, { type: "resolve" }),
    keysEnabled
  )
  useQueueHotkeys(
    rootRef,
    "s",
    (event) => {
      if (!selected) return
      event.preventDefault()
      setSelectedId(selected.id)
      setExpandedId(selected.id)
      setSnoozeFor(selected.id)
    },
    keysEnabled
  )
  useQueueHotkeys(
    rootRef,
    "enter",
    (event) => {
      if (selected && event.target === rootRef.current) {
        setExpandedId((open) => (open === selected.id ? null : selected.id))
      }
    },
    keysEnabled
  )

  if (flat.length === 0) {
    return (
      <div
        ref={rootRef}
        tabIndex={-1}
        data-queue-root
        className="h-full outline-none"
      >
        <EmptyState title="Nothing needs you" />
      </div>
    )
  }

  return (
    <div
      ref={rootRef}
      tabIndex={-1}
      data-queue-root
      className="flex h-full min-h-0 flex-col outline-none"
    >
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-3 p-2">
          {groups.map((group) => (
            <section key={group.urgency} aria-label={`${group.label} items`}>
              <h3 className="mb-1 flex items-center gap-1.5 px-1 text-xs font-medium text-muted-foreground">
                {group.label}
                <Badge
                  variant={
                    group.urgency === "now" ? "destructive" : "secondary"
                  }
                >
                  {group.items.length}
                </Badge>
              </h3>
              <ul className="flex flex-col gap-1">
                {group.items.map((item) => {
                  const expanded = expandedId === item.id
                  const isSelected = selected?.id === item.id
                  const tile = tiles.find(
                    (candidate) => candidate.id === item.tileId
                  )
                  return (
                    <li
                      key={item.id}
                      data-item-id={item.id}
                      aria-current={isSelected ? "true" : undefined}
                      className={cn(
                        "rounded-md border bg-card",
                        isSelected &&
                          "border-(--mini-accent) bg-(--mini-accent-soft)"
                      )}
                    >
                      <button
                        type="button"
                        data-queue-row
                        aria-expanded={expanded}
                        onFocus={() => setSelectedId(item.id)}
                        onClick={() => {
                          setSelectedId(item.id)
                          setExpandedId(expanded ? null : item.id)
                        }}
                        className="flex w-full items-start gap-1.5 rounded-md p-2 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                      >
                        {expanded ? (
                          <ChevronDownIcon
                            aria-hidden
                            className="mt-0.5 size-3.5 shrink-0"
                          />
                        ) : (
                          <ChevronRightIcon
                            aria-hidden
                            className="mt-0.5 size-3.5 shrink-0"
                          />
                        )}
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="text-sm font-medium">
                            {item.title}
                          </span>
                          <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                            <StatusLabel status={itemStatus(item, now)} />
                            <span>
                              {ageText(Math.max(0, now - openedAt(item)))} ago
                            </span>
                          </span>
                        </span>
                      </button>
                      {expanded ? (
                        <div className="border-t px-2 py-2">
                          <ItemDetail
                            item={item}
                            tile={tile}
                            now={now}
                            showKeys
                            onAct={(action) => act(item, action)}
                            onOpenTile={onOpenTile}
                            snoozeOpen={snoozeFor === item.id}
                            onSnoozeOpenChange={(open) =>
                              setSnoozeFor(open ? item.id : null)
                            }
                          />
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
