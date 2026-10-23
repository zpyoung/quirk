import { cn } from "@/lib/utils"

import {
  dayKey,
  formatDayLong,
  formatTime,
  isAllDay,
  isSameDay,
  isSameMonth,
  monthDays,
} from "./dates"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/**
 * Large month for the full view: one truncated line per item in each day cell,
 * at most three, with no overflow count. `previewDate` outlines the date the
 * quick-add text currently resolves to.
 */
export function FullMonth<T extends { id: string; title: string }>({
  month,
  selected,
  items,
  getStart,
  getEnd,
  selectedId,
  previewDate,
  today,
  onSelectDate,
  onSelectItem,
  onDoubleClickDate,
}: {
  month: Date
  selected: Date
  items: T[]
  getStart: (item: T) => Date | undefined
  getEnd?: (item: T) => Date | undefined
  selectedId?: string
  previewDate?: Date
  today: Date
  onSelectDate(d: Date): void
  onSelectItem(id: string): void
  onDoubleClickDate(d: Date): void
}) {
  const byDay = new Map<string, { item: T; start: Date }[]>()
  for (const item of items) {
    const start = getStart(item)
    if (!start) continue
    const key = dayKey(start)
    byDay.set(key, [...(byDay.get(key) ?? []), { item, start }])
  }
  for (const list of byDay.values()) list.sort((a, b) => a.start.getTime() - b.start.getTime())

  return (
    <div className="grid h-full min-h-0 grid-cols-7 grid-rows-[auto_repeat(6,minmax(0,1fr))] border-t border-l">
      {WEEKDAYS.map((name) => (
        <div key={name} className="border-r border-b px-2 py-1 text-xs text-muted-foreground">
          {name}
        </div>
      ))}
      {monthDays(month).map((day) => {
        const entries = byDay.get(dayKey(day)) ?? []
        const inMonth = isSameMonth(day, month)
        const isToday = isSameDay(day, today)
        const isSelected = isSameDay(day, selected)
        const isPreview = previewDate !== undefined && isSameDay(day, previewDate)
        return (
          <div
            key={dayKey(day)}
            className={cn(
              "flex min-h-0 flex-col gap-0.5 overflow-hidden border-r border-b p-1",
              !inMonth && "bg-muted/40 text-muted-foreground",
              isSelected && "bg-[var(--mini-accent-soft)]",
              isPreview && "outline-1 -outline-offset-1 outline-dashed outline-[var(--mini-accent)]"
            )}
          >
            <button
              type="button"
              aria-label={formatDayLong(day)}
              aria-pressed={isSelected}
              aria-current={isToday ? "date" : undefined}
              onClick={() => onSelectDate(day)}
              onDoubleClick={() => onDoubleClickDate(day)}
              className={cn(
                "flex size-6 shrink-0 items-center justify-center self-start rounded-full text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isToday ? "bg-primary font-medium text-primary-foreground" : "hover:bg-accent"
              )}
            >
              {day.getDate()}
            </button>
            {entries.slice(0, 3).map(({ item, start }) => {
              const end = getEnd?.(item)
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-current={item.id === selectedId ? "true" : undefined}
                  onClick={() => onSelectItem(item.id)}
                  className={cn(
                    "w-full shrink-0 truncate rounded px-1 text-left text-[0.7rem] leading-5 outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                    item.id === selectedId && "bg-accent font-medium"
                  )}
                >
                  {isAllDay(start, end) ? "" : `${formatTime(start)} `}
                  {item.title}
                </button>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
