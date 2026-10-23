import { cn } from "@/lib/utils"

import {
  WEEKDAY_LETTERS,
  dayKey,
  formatDayLong,
  isSameDay,
  isSameMonth,
  monthDays,
} from "./dates"

/**
 * Compact Monday-first month. `marked` maps `dayKey` to an item count (up to
 * three dots show). Today is a filled circle, `selected` is outlined, and days
 * outside `month` are dimmed.
 */
export function MonthGrid({
  month,
  selected,
  marked,
  onSelectDate,
  onDoubleClickDate,
  today = new Date(),
}: {
  month: Date
  selected: Date
  marked: Map<string, number>
  onSelectDate(d: Date): void
  onDoubleClickDate?(d: Date): void
  today?: Date
}) {
  const days = monthDays(month)

  return (
    <div role="group" aria-label="Month" className="grid grid-cols-7 gap-y-0.5 text-center">
      {WEEKDAY_LETTERS.map((letter, i) => (
        <span key={i} aria-hidden className="py-0.5 text-[0.65rem] text-muted-foreground">
          {letter}
        </span>
      ))}
      {days.map((day) => {
        const count = marked.get(dayKey(day)) ?? 0
        const inMonth = isSameMonth(day, month)
        const isToday = isSameDay(day, today)
        const isSelected = isSameDay(day, selected)
        return (
          <button
            key={dayKey(day)}
            type="button"
            tabIndex={inMonth ? 0 : -1}
            aria-label={`${formatDayLong(day)}${count ? `, ${count} item${count === 1 ? "" : "s"}` : ""}`}
            aria-pressed={isSelected}
            aria-current={isToday ? "date" : undefined}
            onClick={() => onSelectDate(day)}
            onDoubleClick={() => onDoubleClickDate?.(day)}
            className={cn(
              "mx-auto flex size-8 flex-col items-center justify-center gap-0.5 rounded-full text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring",
              !inMonth && "text-muted-foreground/50",
              isToday && "bg-primary font-medium text-primary-foreground",
              isSelected && "ring-1 ring-foreground/60 ring-offset-1 ring-offset-sidebar",
              !isToday && "hover:bg-accent"
            )}
          >
            <span className="leading-none">{day.getDate()}</span>
            <span className="flex h-1 gap-0.5" aria-hidden>
              {Array.from({ length: Math.min(count, 3) }, (_, i) => (
                <span
                  key={i}
                  className={cn(
                    "size-1 rounded-full",
                    isToday ? "bg-primary-foreground" : "bg-[var(--mini-accent)]"
                  )}
                />
              ))}
            </span>
          </button>
        )
      })}
    </div>
  )
}
