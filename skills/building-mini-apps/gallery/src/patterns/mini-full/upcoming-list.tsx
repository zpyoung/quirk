import { useEffect, useRef, type ReactNode } from "react"

import { cn } from "@/lib/utils"

import { addDays, dayKey, formatHeader, formatTime, isAllDay, startOfDay } from "./dates"

export type RowContext = { selected: boolean; past: boolean }

type Group<T> = { key: string; date: Date; items: T[] }

function timeLabel(start: Date, end: Date | undefined): string {
  if (isAllDay(start, end)) return "All-day"
  return end ? `${formatTime(start)}-${formatTime(end)}` : formatTime(start)
}

/**
 * Items in time order under date headers; past items are dimmed. A row is a
 * button: click selects, double-click or Enter opens. When `selectedDate`
 * changes the list scrolls to that date's header, and when the user scrolls it
 * reports the topmost header through `onTopDateChange`.
 */
export function UpcomingList<T extends { id: string; title: string }>({
  items,
  getStart,
  getEnd,
  getTag,
  selectedId,
  selectedDate,
  onSelect,
  onOpen,
  onTopDateChange,
  renderRow,
  today = new Date(),
  className,
}: {
  items: T[]
  getStart: (item: T) => Date | undefined
  getEnd?: (item: T) => Date | undefined
  getTag?: (item: T) => string | undefined
  selectedId?: string
  selectedDate?: Date
  onSelect(id: string): void
  onOpen(id: string): void
  onTopDateChange?(d: Date): void
  renderRow?: (item: T, ctx: RowContext) => ReactNode
  today?: Date
  className?: string
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const lastUserInput = useRef(-Infinity)
  const pointerHeld = useRef(false)
  const lastReported = useRef<string | null>(null)
  const todayKey = dayKey(today)
  const selectedKey = selectedDate ? dayKey(selectedDate) : undefined

  const groups = (() => {
    const dated = items
      .map((item) => ({ item, start: getStart(item) }))
      .filter((x): x is { item: T; start: Date } => x.start !== undefined)
      .sort((a, b) => a.start.getTime() - b.start.getTime())
    const byDay = new Map<string, Group<T>>()
    for (const { item, start } of dated) {
      const key = dayKey(start)
      const group = byDay.get(key) ?? { key, date: startOfDay(start), items: [] }
      group.items.push(item)
      byDay.set(key, group)
    }
    if (byDay.size > 0 && !byDay.has(todayKey)) {
      byDay.set(todayKey, { key: todayKey, date: startOfDay(today), items: [] })
    }
    return [...byDay.values()].sort((a, b) => a.key.localeCompare(b.key))
  })()
  const signature = groups.map((g) => `${g.key}:${g.items.map((i) => i.id).join(",")}`).join("|")

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    if (selectedKey !== undefined && lastReported.current === selectedKey) {
      lastReported.current = null
      return
    }
    const row = selectedId
      ? root.querySelector<HTMLElement>(`[data-row-id="${CSS.escape(selectedId)}"]`)
      : null
    if (row) {
      row.scrollIntoView({ block: "nearest" })
      return
    }
    if (selectedKey === undefined) return
    const sections = [...root.querySelectorAll<HTMLElement>("[data-date]")]
    const header = sections.find((s) => s.dataset.date! >= selectedKey) ?? sections.at(-1)
    if (header) {
      root.scrollTop += header.getBoundingClientRect().top - root.getBoundingClientRect().top
    }
  }, [selectedKey, selectedId, signature])

  useEffect(() => {
    const release = () => {
      if (pointerHeld.current) lastUserInput.current = performance.now()
      pointerHeld.current = false
    }
    window.addEventListener("pointerup", release)
    return () => window.removeEventListener("pointerup", release)
  }, [])

  const noteUserInput = () => {
    lastUserInput.current = performance.now()
  }

  function onScroll() {
    const root = rootRef.current
    // layout shifts and programmatic scrolls also fire scroll events; only react to the user's own
    if (!root || !onTopDateChange) return
    if (!pointerHeld.current && performance.now() - lastUserInput.current > 300) return
    const top = root.getBoundingClientRect().top
    const sections = root.querySelectorAll<HTMLElement>("[data-date]")
    for (const section of sections) {
      if (section.getBoundingClientRect().bottom > top + 1) {
        const key = section.dataset.date!
        if (key !== selectedKey) {
          lastReported.current = key
          const [y, m, d] = key.split("-").map(Number)
          onTopDateChange(new Date(y, m - 1, d))
        }
        return
      }
    }
  }

  const now = today.getTime()

  return (
    <div
      ref={rootRef}
      onScroll={onScroll}
      onWheel={noteUserInput}
      onTouchMove={noteUserInput}
      onPointerDown={(e) => {
        // a press on the scroller itself is a scrollbar drag; presses on rows are not scrolling
        if (e.target === e.currentTarget) pointerHeld.current = true
      }}
      className={cn("min-h-0 flex-1 overflow-y-auto", className)}
    >
      {groups.map((group) => (
        <section key={group.key} data-date={group.key} aria-label={formatHeader(group.date, today)}>
          <h3
            data-mini="group-header"
            className={cn(
              "px-2 pt-2 pb-1 text-[0.65rem] font-medium tracking-wide text-muted-foreground",
              group.key < todayKey && "opacity-60"
            )}
          >
            {formatHeader(group.date, today)}
          </h3>
          {group.items.length === 0 ? (
            <p className="px-2 py-1 text-xs text-[var(--mini-accent)]">No items today</p>
          ) : (
            <ul>
              {group.items.map((item) => {
                const start = getStart(item)!
                const end = getEnd?.(item)
                const selected = item.id === selectedId
                const past = (end ?? (isAllDay(start, end) ? addDays(group.date, 1) : start)).getTime() < now
                const tag = getTag?.(item)
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      data-row-id={item.id}
                      data-mini="row"
                      aria-current={selected ? "true" : undefined}
                      onClick={() => onSelect(item.id)}
                      onDoubleClick={() => onOpen(item.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault()
                          onOpen(item.id)
                        }
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-2 text-left text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        "h-[var(--mini-row-height)] hover:bg-accent",
                        selected && "bg-accent text-accent-foreground",
                        past && "opacity-60"
                      )}
                    >
                      {renderRow ? (
                        renderRow(item, { selected, past })
                      ) : (
                        <>
                          <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-[var(--mini-accent)]" />
                          <span className="w-[6.25rem] shrink-0 text-muted-foreground tabular-nums">
                            {timeLabel(start, end)}
                          </span>
                          <span className="min-w-0 flex-1 truncate">{item.title}</span>
                          {tag ? <span className="shrink-0 text-muted-foreground">{tag}</span> : null}
                        </>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
