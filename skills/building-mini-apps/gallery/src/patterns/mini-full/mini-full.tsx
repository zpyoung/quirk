import { useEffect, useRef, useState, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { toast } from "sonner"
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Separator } from "@/components/ui/separator"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import {
  addDays,
  addMonths,
  dayKey,
  formatDayLong,
  formatMonth,
  isSameDay,
  startOfDay,
  startOfMonth,
} from "./dates"
import { FullMonth } from "./full-month"
import { MonthGrid } from "./month-grid"
import { parseEntry, withDefaultEnd, type ParsedEntry } from "./parse"
import { ParsePreview, QuickAdd } from "./quick-add"
import { UpcomingList } from "./upcoming-list"

export type MiniFullProps<T> = {
  items: T[]
  status: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  getStart: (item: T) => Date | undefined
  getEnd?: (item: T) => Date | undefined
  getTag?: (item: T) => string | undefined
  fromEntry: (entry: ParsedEntry) => Omit<T, "id">
  onAdd: (item: Omit<T, "id">) => Promise<void>
  onRemove?: (id: string) => Promise<void>
  parse?: (text: string, now: Date) => ParsedEntry
  tags?: string[]
  renderRow?: (item: T, ctx: { selected: boolean; past: boolean }) => ReactNode
  mode?: "mini" | "full"
  onModeChange?: (mode: "mini" | "full") => void
  defaultDurationMinutes?: number
  emptyHint?: string
}

type View = "list" | "month"

function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(timer)
  }, [])
  return now
}

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

function IconButton({ label, onClick, children }: { label: string; onClick(): void; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} onClick={onClick}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

/**
 * A quick-add panel (input, live parse card, month grid, upcoming list) that
 * expands into a full view of the same items. The app owns the data: pass
 * `items` and persist through `onAdd` / `onRemove`. A parsed entry with no date
 * lands all-day on the selected date. Dimmed means ended before now; an item
 * is all-day when it starts at local midnight with no end.
 */
export function MiniFull<T extends { id: string; title: string }>({
  items,
  status,
  error,
  onRetry,
  getStart,
  getEnd,
  getTag,
  fromEntry,
  onAdd,
  onRemove,
  parse,
  tags,
  renderRow,
  mode: modeProp,
  onModeChange,
  defaultDurationMinutes = 30,
  emptyHint,
}: MiniFullProps<T>) {
  const now = useNow()
  const today = startOfDay(now)
  const [text, setText] = useState("")
  const [selectedId, setSelectedId] = useState<string>()
  const [selectedDate, setSelectedDate] = useState(today)
  const [month, setMonth] = useState(() => startOfMonth(today))
  const [innerMode, setInnerMode] = useState<"mini" | "full">("mini")
  const [view, setView] = useState<View>("list")
  const [filter, setFilter] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const pendingFocus = useRef<string | null>(null)
  const submitting = useRef(false)

  const mode = modeProp ?? innerMode
  function setMode(next: "mini" | "full") {
    if (modeProp === undefined) setInnerMode(next)
    onModeChange?.(next)
  }

  const prevMode = useRef(mode)
  useEffect(() => {
    if (prevMode.current === "full" && mode === "mini") inputRef.current?.focus()
    prevMode.current = mode
  }, [mode])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (pendingFocus.current === null || pendingFocus.current !== selectedId) return
    panelRef.current
      ?.querySelector<HTMLElement>(`[data-row-id="${CSS.escape(pendingFocus.current)}"]`)
      ?.focus()
    pendingFocus.current = null
  }, [selectedId])

  const ready = status === "ready"
  const parsed = text ? (parse ? parse(text, now) : parseEntry(text, now, tags)) : undefined
  const entry = withDefaultEnd(parsed ?? { title: "", allDay: true, matches: [] }, defaultDurationMinutes)

  const dated = (ready ? items : [])
    .flatMap((item) => {
      const start = getStart(item)
      return start ? [{ item, start }] : []
    })
    .sort((a, b) => a.start.getTime() - b.start.getTime())
  const marked = new Map<string, number>()
  for (const { start } of dated) marked.set(dayKey(start), (marked.get(dayKey(start)) ?? 0) + 1)
  const upcoming = dated.filter(({ start }) => start >= today).length
  const needle = filter.trim().toLowerCase()
  const matchesFilter = (item: T) => !needle || item.title.toLowerCase().includes(needle)
  const filtered = items.filter(matchesFilter)
  const visible = dated.filter(({ item }) => matchesFilter(item))
  const activeId = visible.some(({ item }) => item.id === selectedId) ? selectedId : undefined

  function selectDate(d: Date) {
    setSelectedDate(startOfDay(d))
    setMonth(startOfMonth(d))
    setSelectedId(undefined)
  }

  function selectItem(id: string) {
    setSelectedId(id)
    const start = getStart(items.find((i) => i.id === id)!)
    if (start) {
      setSelectedDate(startOfDay(start))
      setMonth(startOfMonth(start))
    }
  }

  function openItem(id: string) {
    selectItem(id)
    setMode("full")
  }

  function topDateChanged(d: Date) {
    setSelectedDate(d)
    setMonth(startOfMonth(d))
    setSelectedId((id) => {
      const start = id ? getStart(items.find((i) => i.id === id)!) : undefined
      return start && isSameDay(start, d) ? id : undefined
    })
  }

  async function submit() {
    if (!ready || submitting.current || !entry.title.trim()) return
    const submitted = text
    const filled: ParsedEntry = entry.start
      ? entry
      : { ...entry, start: startOfDay(selectedDate), allDay: true }
    submitting.current = true
    try {
      await onAdd(fromEntry(filled))
      setText((current) => (current === submitted ? "" : current))
      selectDate(filled.start!)
    } catch (cause) {
      toast.error(`Could not add "${filled.title}": ${message(cause)}`)
    } finally {
      submitting.current = false
      inputRef.current?.focus()
    }
  }

  async function removeSelected() {
    const index = visible.findIndex(({ item }) => item.id === activeId)
    if (index < 0 || !onRemove) return
    const { item } = visible[index]
    const neighbor = visible[index + 1] ?? visible[index - 1]
    try {
      await onRemove(item.id)
    } catch (cause) {
      toast.error(`Could not remove "${item.title}": ${message(cause)}`)
      return
    }
    const rest = Object.fromEntries(
      Object.entries(item).filter(([key]) => key !== "id")
    ) as Omit<T, "id">
    toast(`Removed "${item.title}"`, {
      action: {
        label: "Undo",
        onClick: () => {
          onAdd(rest).catch((cause) => toast.error(`Could not restore: ${message(cause)}`))
        },
      },
    })
    if (neighbor) {
      pendingFocus.current = neighbor.item.id
      selectItem(neighbor.item.id)
    } else {
      setSelectedId(undefined)
    }
  }

  function moveSelection(step: 1 | -1) {
    if (visible.length === 0) return
    const index = visible.findIndex(({ item }) => item.id === activeId)
    let next: number
    if (index >= 0) next = Math.min(Math.max(index + step, 0), visible.length - 1)
    else if (step === 1) next = Math.max(visible.findIndex(({ start }) => start >= selectedDate), 0)
    else next = visible.length - 1
    const id = visible[next].item.id
    pendingFocus.current = id
    if (id === activeId) {
      panelRef.current?.querySelector<HTMLElement>(`[data-row-id="${CSS.escape(id)}"]`)?.focus()
      return
    }
    selectItem(id)
  }

  function insertDate(d: Date) {
    const md = `${d.getMonth() + 1}/${d.getDate()}`
    const plain = parseEntry(md, now).start
    const token = plain && isSameDay(plain, d) ? md : `${md}/${d.getFullYear()}`
    selectDate(d)
    setText((current) => (current.trim() ? `${current.trim()} ${token} ` : `${token} `))
    requestAnimationFrame(() => {
      const input = inputRef.current
      input?.focus()
      input?.setSelectionRange(input.value.length, input.value.length)
    })
  }

  function step(direction: 1 | -1) {
    selectDate(view === "month" ? addMonths(selectedDate, direction) : addDays(selectedDate, direction))
  }

  const fullMonthView = mode === "full" && view === "month"
  useHotkeys("n", () => inputRef.current?.focus(), { preventDefault: true })
  useHotkeys("e", () => setMode(mode === "full" ? "mini" : "full"), { preventDefault: true })
  useHotkeys("t", () => selectDate(today), { preventDefault: true })
  useHotkeys("up", () => moveSelection(-1), { preventDefault: true })
  useHotkeys("down", () => moveSelection(1), { preventDefault: true })
  useHotkeys("left", () => selectDate(addMonths(selectedDate, -1)), {
    preventDefault: true,
    enabled: fullMonthView,
  })
  useHotkeys("right", () => selectDate(addMonths(selectedDate, 1)), {
    preventDefault: true,
    enabled: fullMonthView,
  })
  useHotkeys("backspace,delete", () => void removeSelected(), {
    preventDefault: true,
    enabled: activeId !== undefined && onRemove !== undefined,
  })

  function listRegion(className?: string): ReactNode {
    if (status === "loading") return <LoadingState label="Loading items" />
    if (status === "error") {
      return <ErrorState error={error ?? new Error("Could not load items")} onRetry={onRetry} />
    }
    if (items.length === 0) {
      return (
        <EmptyState
          title="Nothing here yet"
          description={emptyHint ?? 'Type something like "dentist tomorrow 10-11" and press Enter.'}
        />
      )
    }
    return (
      <UpcomingList
        className={className}
        items={filtered}
        getStart={getStart}
        getEnd={getEnd}
        getTag={getTag}
        renderRow={renderRow}
        selectedId={activeId}
        selectedDate={selectedDate}
        today={now}
        onSelect={selectItem}
        onOpen={openItem}
        onTopDateChange={topDateChanged}
      />
    )
  }

  const panel = (
    <div className="flex h-full min-h-0 flex-col gap-2 p-2">
      <QuickAdd
        value={text}
        onChange={setText}
        onSubmit={() => void submit()}
        entry={entry}
        disabled={!ready}
        tags={tags}
        inputRef={inputRef}
      />
      {text ? (
        <ParsePreview entry={entry} onSubmit={() => void submit()} disabled={!ready} />
      ) : (
        <div className="shrink-0">
          <div className="mb-1 flex items-center justify-between pl-1">
            <span className="text-sm font-medium">{formatMonth(month)}</span>
            <div className="flex">
              <IconButton label="Previous month" onClick={() => setMonth(addMonths(month, -1))}>
                <ChevronLeftIcon />
              </IconButton>
              <IconButton label="Next month" onClick={() => setMonth(addMonths(month, 1))}>
                <ChevronRightIcon />
              </IconButton>
            </div>
          </div>
          <MonthGrid
            month={month}
            selected={selectedDate}
            marked={marked}
            today={now}
            onSelectDate={selectDate}
            onDoubleClickDate={insertDate}
          />
        </div>
      )}
      <Separator />
      <div className="-mx-1 flex min-h-0 flex-1 flex-col">{listRegion()}</div>
      <Separator />
      <div className="flex shrink-0 items-center justify-between gap-2">
        <Button
          variant="ghost"
          size="sm"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setMode(mode === "full" ? "mini" : "full")}
        >
          {mode === "full" ? "Collapse" : "Expand"}
          <Kbd>e</Kbd>
        </Button>
        <span className="text-xs text-muted-foreground tabular-nums">{upcoming} upcoming</span>
        <Button variant="outline" size="xs" onClick={() => selectDate(today)}>
          Today
        </Button>
      </div>
    </div>
  )

  return (
    <div
      className={cn(
        "flex h-full min-h-0",
        mode === "mini" ? "mx-auto max-h-[560px] w-[320px] rounded-lg border" : "w-full"
      )}
    >
      <aside
        ref={panelRef}
        aria-label="Quick add panel"
        style={mode === "full" ? { width: "22%", minWidth: 280 } : undefined}
        className={cn(
          "min-h-0 shrink-0 bg-sidebar text-sidebar-foreground",
          mode === "mini" ? "w-full rounded-lg" : "border-r"
        )}
      >
        {panel}
      </aside>
      {mode === "full" ? (
        <section aria-label="Full view" className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-11 shrink-0 items-center gap-2 border-b px-3">
            <IconButton label={view === "month" ? "Previous month" : "Previous day"} onClick={() => step(-1)}>
              <ChevronLeftIcon />
            </IconButton>
            <Button variant="outline" size="sm" onClick={() => selectDate(today)}>
              Today
            </Button>
            <IconButton label={view === "month" ? "Next month" : "Next day"} onClick={() => step(1)}>
              <ChevronRightIcon />
            </IconButton>
            <h2 className="min-w-0 truncate text-sm font-medium">
              {view === "month" ? formatMonth(month) : formatDayLong(selectedDate)}
            </h2>
            <ToggleGroup
              type="multiple"
              variant="outline"
              size="sm"
              value={[view]}
              onValueChange={(next) => {
                const picked = next.find((v) => v !== view)
                if (picked) setView(picked as View)
              }}
              aria-label="View"
              rovingFocus={false}
              className="ml-auto"
            >
              <ToggleGroupItem value="list" aria-label="List view">
                List
              </ToggleGroupItem>
              <ToggleGroupItem value="month" aria-label="Month view">
                Month
              </ToggleGroupItem>
            </ToggleGroup>
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Find"
              aria-label="Filter items"
              className="w-36"
            />
          </div>
          <div className="flex min-h-0 flex-1 flex-col">
            {view === "list"
              ? listRegion("p-2")
              : status !== "ready" || items.length === 0
                ? listRegion()
                : (
                  <FullMonth
                    month={month}
                    selected={selectedDate}
                    items={filtered}
                    getStart={getStart}
                    getEnd={getEnd}
                    selectedId={activeId}
                    previewDate={entry.start}
                    today={now}
                    onSelectDate={selectDate}
                    onSelectItem={selectItem}
                    onDoubleClickDate={insertDate}
                  />
                )}
          </div>
        </section>
      ) : null}
    </div>
  )
}
