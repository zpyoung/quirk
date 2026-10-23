import {
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ArrowDownIcon, ArrowUpIcon, LocateFixedIcon, SearchIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { EntryRow } from "./entry-row"
import { PlayheadDivider } from "./playhead-divider"
import {
  buildRows,
  entryTypes,
  formatOffset,
  typeFromOptionValue,
  typeLabel,
  typeOptionValue,
} from "./timeline"
import type { TimelineEntry, TimelineOrder, TimelineType } from "./types"

export type EventTimelineProps = {
  entries: TimelineEntry[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  types?: Record<string, TimelineType>
  defaultOrder?: TimelineOrder
  playhead?: number
  onSeek?: (time: number) => void
  formatTime?: (time: number) => string
  errorLabel?: string
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

// type keys are prefixed into option values (see typeOptionValue), so this can never collide with one
const ANY_TYPE = "any"
const FOLLOW_PADDING = 48

/**
 * Time-ordered list of typed entries with search, a type filter and an order
 * control. With a finite `playhead` it dims later entries, draws a divider at the
 * playhead and scrolls to follow it until the user scrolls the divider out of
 * view; `onSeek` turns each time into a seek button. Takes data as props and
 * never reads the store. Keys act when focus is on the page body or inside this
 * block, never while typing in an input.
 */
export function EventTimeline({
  entries,
  status = "ready",
  error,
  onRetry,
  types = {},
  defaultOrder = "newest",
  playhead,
  onSeek,
  formatTime = formatOffset,
  errorLabel = "This event",
  emptyTitle = "No activity yet",
  emptyAction,
  "aria-label": ariaLabel = "Timeline",
}: EventTimelineProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const programmaticTop = useRef<number | null>(null)

  const [query, setQuery] = useState("")
  const [type, setType] = useState<string | null>(null)
  const [order, setOrder] = useState<TimelineOrder>(defaultOrder)
  const [following, setFollowing] = useState(true)

  const ready = status === "ready"
  const usable = ready && entries.length > 0
  const typeKeys = useMemo(() => entryTypes(entries), [entries])
  const activeType = type !== null && typeKeys.includes(type) ? type : null
  const filtering = query.trim() !== "" || activeType !== null
  const hasPlayhead = playhead !== undefined && Number.isFinite(playhead)

  const rows = useMemo(
    () => (usable ? buildRows(entries, { query, type: activeType, order, playhead }) : []),
    [usable, entries, query, activeType, order, playhead]
  )
  const entryCount = rows.filter((row) => row.kind === "entry").length
  const hasDivider = rows.some((row) => row.kind === "playhead")

  const findDivider = () =>
    scrollerRef.current?.querySelector<HTMLElement>('[data-mini="playhead"]') ?? null

  const reveal = useEffectEvent(() => {
    const scroller = scrollerRef.current
    const divider = findDivider()
    if (!scroller || !divider) return
    const box = divider.getBoundingClientRect()
    const top = box.top - scroller.getBoundingClientRect().top + scroller.scrollTop
    let next = scroller.scrollTop
    if (top < scroller.scrollTop + FOLLOW_PADDING) {
      next = top - FOLLOW_PADDING
    } else if (top + box.height > scroller.scrollTop + scroller.clientHeight - FOLLOW_PADDING) {
      next = top + box.height - scroller.clientHeight + FOLLOW_PADDING
    }
    const before = scroller.scrollTop
    scroller.scrollTop = Math.max(0, next)
    // the scroll event this fires must not read as the user scrolling away
    if (scroller.scrollTop !== before) programmaticTop.current = scroller.scrollTop
  })

  const dividerInView = () => {
    const scroller = scrollerRef.current
    const divider = findDivider()
    if (!scroller || !divider) return false
    const area = scroller.getBoundingClientRect()
    const box = divider.getBoundingClientRect()
    return box.bottom > area.top && box.top < area.bottom
  }

  useEffect(() => {
    if (hasDivider && following) reveal()
  }, [rows, hasDivider, following])

  // a playhead that moves into view by itself ends the detached state, which scroll events alone would miss
  useEffect(() => {
    const scroller = scrollerRef.current
    const divider = findDivider()
    if (!scroller || !divider) return
    const observer = new IntersectionObserver(
      (observed) => {
        if (observed.some((item) => item.isIntersecting)) setFollowing(true)
      },
      { root: scroller }
    )
    observer.observe(divider)
    return () => observer.disconnect()
  }, [rows])

  const onScroll = () => {
    const scroller = scrollerRef.current
    if (!scroller) return
    const own = programmaticTop.current
    programmaticTop.current = null
    if (own !== null && Math.abs(scroller.scrollTop - own) < 2) return
    if (findDivider()) setFollowing(dividerInView())
  }

  // following flips on, and the effect above scrolls
  const jumpToPlayhead = () => setFollowing(true)

  const seek = (time: number) => {
    onSeek?.(time)
    setFollowing(true)
  }

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) return true
    if (!(target instanceof Element) || !rootRef.current?.contains(target)) return false
    // the select trigger has its own type-ahead, which these letters would fight
    return target.closest('[role="combobox"]') === null
  }
  useHotkeys(
    "slash",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      inputRef.current?.focus()
    },
    { enabled: usable }
  )
  useHotkeys(
    "o",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      setOrder((current) => (current === "newest" ? "oldest" : "newest"))
    },
    { enabled: usable }
  )
  useHotkeys(
    "p",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      jumpToPlayhead()
    },
    { enabled: usable && hasDivider }
  )

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Escape") return
    event.preventDefault()
    if (query) setQuery("")
    else {
      event.currentTarget.blur()
      scrollerRef.current?.focus({ preventScroll: true })
    }
  }

  const clearFilters = () => {
    setQuery("")
    setType(null)
  }

  const count = filtering
    ? `${entryCount} of ${entries.length} entries`
    : `${entries.length} ${entries.length === 1 ? "entry" : "entries"}`

  let body
  if (status === "loading") {
    body = <LoadingState label="Loading timeline" />
  } else if (status === "error") {
    body = <ErrorState error={error ?? new Error("Unknown error")} onRetry={onRetry} />
  } else if (entries.length === 0) {
    body = (
      <EmptyState
        title={emptyTitle}
        description="Entries will show up here in time order."
        action={
          emptyAction ? (
            <Button variant="outline" size="sm" onClick={emptyAction.onClick}>
              {emptyAction.label}
            </Button>
          ) : undefined
        }
      />
    )
  } else if (rows.length === 0) {
    const parts = [
      query.trim() ? `"${query.trim()}"` : null,
      activeType !== null ? typeLabel(activeType, types[activeType]?.label) : null,
    ].filter((part) => part !== null)
    body = (
      <EmptyState
        title={`No entries match ${parts.join(" in ")}`}
        description="Try a different word or type, or clear the filters."
        action={
          <Button variant="outline" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    )
  } else {
    body = (
      <ol
        className="relative m-0 p-0 before:absolute before:top-6 before:bottom-6 before:left-[26px] before:w-px before:bg-border"
      >
        {rows.map((row) =>
          row.kind === "playhead" ? (
            <PlayheadDivider key="playhead" time={formatTime(row.time)} />
          ) : (
            <EntryRow
              key={row.entry.id}
              entry={row.entry}
              type={types[row.entry.type]}
              time={formatTime(row.entry.time)}
              order={order}
              after={row.after}
              current={row.current}
              errorLabel={errorLabel}
              onSeek={onSeek ? seek : undefined}
            />
          )
        )}
      </ol>
    )
  }

  const OrderIcon = order === "newest" ? ArrowDownIcon : ArrowUpIcon

  return (
    <div ref={rootRef} className="flex h-full min-h-0 flex-col bg-background text-sm">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-3 py-2">
        <div className="relative min-w-40 max-w-72 flex-1">
          <SearchIcon
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onSearchKeyDown}
            disabled={!usable}
            placeholder="Search entries (press /)"
            aria-label="Search entries"
            className="h-8 pl-8"
          />
        </div>
        <Select
          value={activeType === null ? ANY_TYPE : typeOptionValue(activeType)}
          onValueChange={(value) => setType(typeFromOptionValue(value))}
          disabled={!usable}
        >
          <SelectTrigger size="sm" aria-label="Filter by type" className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY_TYPE}>Any type</SelectItem>
            {typeKeys.map((key) => (
              <SelectItem key={key} value={typeOptionValue(key)}>
                {typeLabel(key, types[key]?.label)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          disabled={!usable}
          title="Switch order (o)"
          onClick={() => setOrder(order === "newest" ? "oldest" : "newest")}
        >
          <OrderIcon aria-hidden />
          {order === "newest" ? "Newest first" : "Oldest first"}
        </Button>
        <span aria-live="polite" className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">
          {usable ? count : ""}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollerRef}
          role="region"
          tabIndex={0}
          aria-label={ariaLabel}
          onScroll={onScroll}
          className="h-full overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50"
        >
          {body}
        </div>
        {hasPlayhead && hasDivider && !following ? (
          <Button
            size="sm"
            variant="secondary"
            onClick={jumpToPlayhead}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 shadow-md"
          >
            <LocateFixedIcon aria-hidden />
            Jump to playhead
          </Button>
        ) : null}
      </div>
    </div>
  )
}
