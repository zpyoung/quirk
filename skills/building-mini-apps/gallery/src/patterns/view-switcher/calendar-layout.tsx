import { useMemo } from "react"
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

import {
  addMonths,
  formatDay,
  formatMonth,
  isIsoDate,
  monthGrid,
  startOfMonth,
  toIso,
  weekdayLabels,
} from "./dates"
import { pickField, textOf, valueOf, type Rec } from "./fields"
import { recordClasses, recordProps, type LayoutProps } from "./layout-shared"

const CARDS_PER_DAY = 3

function Chip({
  layout,
  item,
  tabStopId,
}: {
  layout: LayoutProps
  item: Rec
  tabStopId: string | null
}) {
  return (
    <button
      type="button"
      {...recordProps(layout, item.id, tabStopId)}
      title={item.title}
      className={cn(
        "block w-full cursor-pointer truncate rounded border bg-card px-1.5 py-0.5 text-left text-[11px] leading-4 hover:bg-accent/50",
        recordClasses
      )}
    >
      {item.title}
    </button>
  )
}

export interface CalendarLayoutProps extends LayoutProps {
  month: Date
  onMonthChange(month: Date): void
}

export function CalendarLayout(props: CalendarLayoutProps) {
  const {
    items,
    fields,
    view,
    noun,
    month,
    onMonthChange,
    onCreate,
    tabStopId,
  } = props
  const dateField = pickField(fields, view.dateField, "date")
  const weekdays = useMemo(() => weekdayLabels(), [])
  const days = useMemo(() => monthGrid(month), [month])

  const byDay = useMemo(() => {
    const map = new Map<string, Rec[]>()
    if (!dateField) return map
    for (const item of items) {
      const value = textOf(valueOf(item, dateField.key))
      if (isIsoDate(value)) map.set(value, [...(map.get(value) ?? []), item])
    }
    return map
  }, [items, dateField])

  if (!dateField) {
    return (
      <EmptyState
        title="Calendar needs a date field"
        description="Add a field that holds a date to place records on the month grid."
      />
    )
  }

  // a Tab stop hidden behind "+N more" would leave the grid unreachable
  const visibleIds = days.flatMap((d) =>
    (byDay.get(toIso(d)) ?? []).slice(0, CARDS_PER_DAY).map((i) => i.id)
  )
  const stop =
    tabStopId && visibleIds.includes(tabStopId)
      ? tabStopId
      : (visibleIds[0] ?? null)
  const today = toIso(new Date())

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-9 shrink-0 items-center gap-1 px-3">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Previous month"
          onClick={() => onMonthChange(addMonths(month, -1))}
        >
          <ChevronLeftIcon />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Next month"
          onClick={() => onMonthChange(addMonths(month, 1))}
        >
          <ChevronRightIcon />
        </Button>
        <h3 aria-live="polite" className="px-1 text-sm font-medium">
          {formatMonth(month)}
        </h3>
        <Button
          variant="outline"
          size="xs"
          className="ml-auto"
          onClick={() => onMonthChange(startOfMonth(new Date()))}
        >
          Today
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <ol
          className="grid min-w-[42rem] grid-cols-7 border-t"
          aria-label={formatMonth(month)}
        >
          {weekdays.map((name) => (
            <li
              key={name}
              aria-hidden
              className="sticky top-0 z-10 border-b bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground"
            >
              {name}
            </li>
          ))}
          {days.map((day) => {
            const iso = toIso(day)
            const records = byDay.get(iso) ?? []
            const inMonth = day.getMonth() === month.getMonth()
            const weekend = day.getDay() === 0 || day.getDay() === 6
            const extra = records.slice(CARDS_PER_DAY)
            return (
              <li
                key={iso}
                className={cn(
                  "group/day flex min-h-[6.5rem] min-w-0 flex-col gap-1 border-r border-b p-1 [&:nth-child(7n+7)]:border-r-0",
                  weekend && "bg-muted/40",
                  !inMonth && "bg-muted/20"
                )}
              >
                <div className="flex h-5 items-center justify-between">
                  <time
                    dateTime={iso}
                    className={cn(
                      "flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] tabular-nums",
                      iso === today
                        ? "bg-primary font-medium text-primary-foreground"
                        : inMonth
                          ? "text-foreground"
                          : "text-muted-foreground/60"
                    )}
                  >
                    {day.getDate()}
                  </time>
                  {onCreate ? (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className="opacity-0 group-focus-within/day:opacity-100 group-hover/day:opacity-100"
                      aria-label={`New ${noun} on ${iso}`}
                      onClick={() => onCreate({ [dateField.key]: iso })}
                    >
                      <PlusIcon />
                    </Button>
                  ) : null}
                </div>
                <div
                  className={cn(
                    "flex flex-col gap-0.5",
                    !inMonth && "opacity-60"
                  )}
                >
                  {records.slice(0, CARDS_PER_DAY).map((item) => (
                    <Chip
                      key={item.id}
                      layout={props}
                      item={item}
                      tabStopId={stop}
                    />
                  ))}
                  {extra.length > 0 ? (
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className="rounded px-1.5 text-left text-[11px] text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
                        >
                          +{extra.length} more
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-56 gap-1 p-1.5">
                        <p className="px-1 text-xs font-medium">
                          {formatDay(iso)}
                        </p>
                        {extra.map((item) => (
                          <Chip
                            key={item.id}
                            layout={props}
                            item={item}
                            tabStopId={item.id}
                          />
                        ))}
                      </PopoverContent>
                    </Popover>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
