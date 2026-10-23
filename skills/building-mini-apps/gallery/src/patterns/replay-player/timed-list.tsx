import { useEffect, useMemo, useRef, useState } from "react"
import {
  ArrowLeftRightIcon,
  CircleIcon,
  FlameIcon,
  MapPinIcon,
  MousePointerClickIcon,
  PlayIcon,
  TerminalIcon,
  type LucideIcon,
} from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { activeIndex, filterEntries, formatClock } from "./playback"
import type { ReplayEvent } from "./types"

const ICONS: Record<string, LucideIcon> = {
  click: MousePointerClickIcon,
  navigation: MapPinIcon,
  error: FlameIcon,
  console: TerminalIcon,
  network: ArrowLeftRightIcon,
}

// the scroll container is the rows' offset parent, so offsetTop is already relative to it
function rowInView(container: HTMLElement, row: HTMLElement) {
  const top = row.offsetTop
  return (
    top >= container.scrollTop &&
    top + row.offsetHeight <= container.scrollTop + container.clientHeight
  )
}

/** Entries in time order that follow the playhead and seek when an entry's time is clicked. */
export function TimedList({
  entries,
  time,
  onSeek,
  label,
  emptyTitle = "Nothing to show",
  emptyDescription,
}: {
  entries: ReplayEvent[]
  time: number
  onSeek: (ms: number) => void
  label: string
  emptyTitle?: string
  emptyDescription?: string
}) {
  const [query, setQuery] = useState("")
  const [away, setAway] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const rowRefs = useRef(new Map<string, HTMLLIElement>())
  const ownScroll = useRef(false)

  const shown = useMemo(() => filterEntries(entries, query), [entries, query])
  const current = activeIndex(shown, time)
  const currentId = current === -1 ? null : shown[current].id

  const scrollToCurrent = () => {
    const container = containerRef.current
    const row = currentId ? rowRefs.current.get(currentId) : undefined
    if (!container || !row || rowInView(container, row)) return
    const top = row.offsetTop
    const target =
      top < container.scrollTop
        ? top
        : top + row.offsetHeight - container.clientHeight
    if (target === container.scrollTop) return
    ownScroll.current = true
    container.scrollTop = Math.max(0, target)
  }

  useEffect(() => {
    if (!away) scrollToCurrent()
    // follows the playhead only when the current entry or the list changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId, shown, away])

  const onScroll = () => {
    if (ownScroll.current) {
      ownScroll.current = false
      return
    }
    const container = containerRef.current
    const row = currentId ? rowRefs.current.get(currentId) : undefined
    if (!container || !row) return
    setAway(!rowInView(container, row))
  }

  const seek = (at: number) => {
    setAway(false)
    onSeek(at)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 px-2 pb-2">
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`Filter ${label.toLowerCase()}`}
          aria-label={`Filter ${label.toLowerCase()}`}
          className="h-7 text-xs"
        />
      </div>
      <div className="relative min-h-0 flex-1">
        {shown.length === 0 ? (
          query.trim() ? (
            <EmptyState
              title={`No entries match "${query.trim()}"`}
              action={
                <Button variant="outline" size="sm" onClick={() => setQuery("")}>
                  Clear filter
                </Button>
              }
            />
          ) : (
            <EmptyState title={emptyTitle} description={emptyDescription} />
          )
        ) : (
          <div
            ref={containerRef}
            onScroll={onScroll}
            className="relative h-full overflow-y-auto"
          >
            <ul aria-label={label} className="flex flex-col">
              {shown.map((entry, index) => {
                const Icon = ICONS[entry.kind] ?? CircleIcon
                const isCurrent = index === current
                const future = index > current
                const rule = future && index === current + 1
                return (
                  <li
                    key={entry.id}
                    ref={(node) => {
                      if (node) rowRefs.current.set(entry.id, node)
                      else rowRefs.current.delete(entry.id)
                    }}
                    aria-current={isCurrent ? "true" : undefined}
                    className={cn(
                      "flex items-start gap-2 border-t px-2 py-1.5",
                      rule ? "border-t-primary" : "border-t-border",
                      isCurrent && "bg-[var(--mini-accent-soft)]",
                      future && "text-muted-foreground"
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted",
                        entry.tone === "error" || entry.kind === "error"
                          ? "text-destructive"
                          : "text-foreground"
                      )}
                    >
                      <Icon className="size-3" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          "truncate text-sm font-medium",
                          (entry.tone === "error" || entry.kind === "error") &&
                            "text-destructive"
                        )}
                      >
                        {entry.label}
                      </p>
                      {entry.detail ? (
                        <p
                          title={entry.detail}
                          className="truncate text-xs text-muted-foreground font-[family-name:var(--mini-font-data)]"
                        >
                          {entry.detail}
                        </p>
                      ) : null}
                    </div>
                    <Button
                      variant="ghost"
                      size="xs"
                      aria-label={`Seek to ${formatClock(entry.at)}, ${entry.label}`}
                      onClick={() => seek(entry.at)}
                      className="shrink-0 tabular-nums"
                    >
                      <PlayIcon aria-hidden />
                      {formatClock(entry.at)}
                    </Button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
        {away && shown.length > 0 ? (
          <Button
            size="xs"
            variant="secondary"
            onClick={() => {
              setAway(false)
              scrollToCurrent()
            }}
            className="absolute bottom-2 left-1/2 -translate-x-1/2 shadow-sm ring-1 ring-border"
          >
            Jump to current time
          </Button>
        ) : null}
      </div>
    </div>
  )
}
