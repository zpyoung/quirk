import {
  Fragment,
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ChevronDownIcon, ChevronUpIcon, FoldHorizontalIcon, PinIcon, TriangleAlertIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { cn } from "@/lib/utils"

import { CollapsePill } from "./collapse-pill"
import { DurationBar } from "./duration-bar"
import { SpanPanel } from "./span-panel"
import { TimeAxis, TimeGuides } from "./time-axis"
import type { Span, TreeRow, WaterfallMarker, WaterfallStat } from "./types"
import {
  ancestorIds,
  createScale,
  findGaps,
  flattenTree,
  formatDuration,
  matchSpanIds,
  opCategory,
  opPalette,
} from "./waterfall"

export type SpanWaterfallProps = {
  spans: Span[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  title?: string
  subtitle?: string
  stats?: WaterfallStat[]
  markers?: WaterfallMarker[]
  gapThresholdMs?: number
  defaultCompressed?: boolean
  defaultPinnedKeys?: string[]
  pinnedKeys?: string[]
  onPinnedKeysChange?: (keys: string[]) => void
  selectedId?: string | null
  onSelectedIdChange?: (id: string | null) => void
  panelOpen?: boolean
  onPanelOpenChange?: (open: boolean) => void
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

const NARROW_BELOW = 560
const PINNED_WIDTH_REM = 8
const NO_SPANS: ReadonlySet<string> = new Set()

/** State that follows `value` when the parent passes one and is held locally otherwise. */
function useControllable<T>(
  value: T | undefined,
  initial: T,
  onChange?: (next: T) => void
): [T, (next: T) => void] {
  const [inner, setInner] = useState(initial)
  const controlled = value !== undefined
  const set = (next: T) => {
    if (!controlled) setInner(next)
    onChange?.(next)
  }
  return [controlled ? value : inner, set]
}

function IndentGuides({ row }: { row: TreeRow }) {
  return (
    <>
      {row.guides.map((continues, level) => {
        const elbow = level === row.depth - 1
        return (
          <span key={level} aria-hidden className="relative h-full w-4 shrink-0">
            {continues || elbow ? (
              <span
                className="absolute top-0 left-1/2 w-px bg-border"
                style={{ height: continues ? "100%" : "50%" }}
              />
            ) : null}
            {elbow ? <span className="absolute top-1/2 left-1/2 h-px w-1/2 bg-border" /> : null}
          </span>
        )
      })}
    </>
  )
}

/**
 * Tree of timed rows beside one shared time axis, with a read-only side panel
 * that squeezes the timeline. Takes data as props and never reads the store.
 * Keys act while focus is on the tree or the page body, never while typing.
 */
export function SpanWaterfall({
  spans,
  status = "ready",
  error,
  onRetry,
  title,
  subtitle,
  stats = [],
  markers,
  gapThresholdMs,
  defaultCompressed = true,
  defaultPinnedKeys,
  pinnedKeys: pinnedProp,
  onPinnedKeysChange,
  selectedId: selectedProp,
  onSelectedIdChange,
  panelOpen: panelProp,
  onPanelOpenChange,
  emptyTitle = "No spans in this trace",
  emptyAction,
  "aria-label": ariaLabel = "Trace waterfall",
}: SpanWaterfallProps) {
  const uid = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const panelWrapRef = useRef<HTMLDivElement>(null)

  const [query, setQuery] = useState("")
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(NO_SPANS)
  const [compress, setCompress] = useState(defaultCompressed)
  const [narrow, setNarrow] = useState(false)
  const [pinned, setPinned] = useControllable<string[]>(pinnedProp, defaultPinnedKeys ?? [], onPinnedKeysChange)
  const [selectedId, setSelectedId] = useControllable<string | null>(selectedProp, null, onSelectedIdChange)
  const [panelOpen, setPanelOpen] = useControllable(panelProp, false, onPanelOpenChange)

  const ready = status === "ready"
  const rows = useMemo(() => flattenTree(spans, collapsed), [spans, collapsed])
  const fullRows = useMemo(() => flattenTree(spans, NO_SPANS), [spans])
  const scale = useMemo(
    () => createScale(spans, { gapThresholdMs, compress }),
    [spans, gapThresholdMs, compress]
  )
  const hasGaps = useMemo(() => findGaps(spans, gapThresholdMs).length > 0, [spans, gapThresholdMs])
  const palette = useMemo(() => opPalette(spans), [spans])
  const matches = useMemo(() => matchSpanIds(spans, query), [spans, query])
  const matchSet = useMemo(() => new Set(matches), [matches])
  const searching = query.trim() !== ""

  const selectedSpan = useMemo(
    () => (selectedId === null ? undefined : fullRows.find((row) => row.span.id === selectedId)?.span),
    [fullRows, selectedId]
  )
  const activeIndex = rows.findIndex((row) => row.span.id === selectedId)
  const showPanel = ready && panelOpen && selectedSpan !== undefined
  const keysOn = ready && rows.length > 0

  const rowDomId = (id: string) => `${uid}-row-${encodeURIComponent(id)}`
  const focusGrid = () => gridRef.current?.focus({ preventScroll: true })

  const errorTotal = useMemo(
    () => fullRows.reduce((sum, row) => sum + (row.span.errors?.length ?? 0), 0),
    [fullRows]
  )

  useEffect(() => {
    const element = rootRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < NARROW_BELOW))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const reconcile = useEffectEvent(() => {
    if (!ready) return
    if (selectedId !== null && selectedSpan === undefined) setSelectedId(null)
    if (panelOpen && selectedId === null) setPanelOpen(false)
  })
  useEffect(() => reconcile(), [selectedSpan, selectedId, panelOpen, ready])

  useEffect(() => {
    if (selectedId === null) return
    document.getElementById(`${uid}-row-${encodeURIComponent(selectedId)}`)?.scrollIntoView({ block: "nearest" })
  }, [selectedId, rows, uid])

  const closePanel = () => {
    const focusInPanel = panelWrapRef.current?.contains(document.activeElement)
    setPanelOpen(false)
    if (focusInPanel) focusGrid()
  }

  const select = (id: string) => {
    setSelectedId(id)
    if (document.activeElement === document.body) focusGrid()
  }

  const toggleCollapsed = (id: string) => {
    const collapsing = !collapsed.has(id)
    const next = new Set(collapsed)
    if (collapsing) next.add(id)
    else next.delete(id)
    setCollapsed(next)
    if (collapsing && selectedId !== null && ancestorIds(spans, selectedId).includes(id)) {
      setSelectedId(id)
    }
  }

  const jumpTo = (id: string) => {
    const hidden = ancestorIds(spans, id).filter((ancestor) => collapsed.has(ancestor))
    if (hidden.length > 0) {
      const next = new Set(collapsed)
      hidden.forEach((ancestor) => next.delete(ancestor))
      setCollapsed(next)
    }
    setSelectedId(id)
  }

  const stepMatch = (delta: 1 | -1) => {
    if (matches.length === 0) return
    const at = selectedId === null ? -1 : matches.indexOf(selectedId)
    const index =
      at === -1 ? (delta === 1 ? 0 : matches.length - 1) : (at + delta + matches.length) % matches.length
    jumpTo(matches[index])
  }

  const togglePin = (key: string) =>
    setPinned(pinned.includes(key) ? pinned.filter((item) => item !== key) : [...pinned, key])

  const fromTree = (event: KeyboardEvent) =>
    event.target === document.body ||
    event.target === document.documentElement ||
    event.target === gridRef.current

  const move = (to: "next" | "previous" | "first" | "last") => {
    if (rows.length === 0) return
    let index: number
    if (to === "first") index = 0
    else if (to === "last") index = rows.length - 1
    else if (activeIndex === -1) index = to === "next" ? 0 : rows.length - 1
    else index = Math.min(rows.length - 1, Math.max(0, activeIndex + (to === "next" ? 1 : -1)))
    select(rows[index].span.id)
  }

  const navigate = (event: KeyboardEvent, to: Parameters<typeof move>[0]) => {
    if (!fromTree(event)) return
    event.preventDefault()
    move(to)
  }
  useHotkeys("down", (event) => navigate(event, "next"), { enabled: keysOn })
  useHotkeys("up", (event) => navigate(event, "previous"), { enabled: keysOn })
  useHotkeys("home", (event) => navigate(event, "first"), { enabled: keysOn })
  useHotkeys("end", (event) => navigate(event, "last"), { enabled: keysOn })

  useHotkeys(
    "left",
    (event) => {
      if (!fromTree(event)) return
      event.preventDefault()
      const row = rows[activeIndex]
      if (!row) return
      if (row.expanded) toggleCollapsed(row.span.id)
      else if (row.parentId !== null) select(row.parentId)
    },
    { enabled: keysOn }
  )
  useHotkeys(
    "right",
    (event) => {
      if (!fromTree(event)) return
      event.preventDefault()
      const row = rows[activeIndex]
      if (!row) return
      if (row.childCount > 0 && !row.expanded) toggleCollapsed(row.span.id)
      else if (row.expanded) select(rows[activeIndex + 1].span.id)
    },
    { enabled: keysOn }
  )
  useHotkeys(
    "enter",
    (event) => {
      if (!fromTree(event) || selectedSpan === undefined) return
      event.preventDefault()
      setPanelOpen(true)
    },
    { enabled: keysOn }
  )
  useHotkeys(
    "esc",
    (event) => {
      if (!fromTree(event)) return
      event.preventDefault()
      closePanel()
    },
    { enabled: ready && panelOpen }
  )

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault()
      stepMatch(event.shiftKey ? -1 : 1)
    } else if (event.key === "Escape") {
      event.preventDefault()
      if (query) setQuery("")
      else {
        event.currentTarget.blur()
        focusGrid()
      }
    } else if (event.key === "ArrowDown") {
      event.preventDefault()
      if (selectedId === null && rows.length > 0) setSelectedId(rows[0].span.id)
      focusGrid()
    }
  }

  const matchText = !searching
    ? ""
    : matches.length === 0
      ? "No matches"
      : selectedId !== null && matches.includes(selectedId)
        ? `${matches.indexOf(selectedId) + 1} of ${matches.length}`
        : `${matches.length} ${matches.length === 1 ? "match" : "matches"}`

  const columns = ["minmax(11rem, 36%)", ...pinned.map(() => `${PINNED_WIDTH_REM}rem`), "minmax(10rem, 1fr)"].join(" ")
  const minWidth = `calc(21rem + ${pinned.length * PINNED_WIDTH_REM}rem)`

  let body
  if (status === "loading") {
    body = <LoadingState label="Loading trace" />
  } else if (status === "error") {
    body = <ErrorState error={error ?? new Error("Unknown error")} onRetry={onRetry} />
  } else if (spans.length === 0) {
    body = (
      <EmptyState
        title={emptyTitle}
        description="Spans will show up here once the run reports them."
        action={
          emptyAction ? (
            <Button variant="outline" size="sm" onClick={emptyAction.onClick}>
              {emptyAction.label}
            </Button>
          ) : undefined
        }
      />
    )
  } else {
    body = (
      <div
        ref={gridRef}
        role="treegrid"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-rowcount={rows.length + 1}
        aria-activedescendant={activeIndex === -1 || selectedId === null ? undefined : rowDomId(selectedId)}
        className="h-full overflow-auto bg-background outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset"
      >
        <div className="grid" style={{ gridTemplateColumns: columns, minWidth }}>
          <div
            role="row"
            aria-rowindex={1}
            className="sticky top-0 z-20 grid grid-cols-subgrid border-b bg-background"
            style={{ gridRow: 1, gridColumn: "1 / -1" }}
          >
            <div role="columnheader" className="flex items-center px-3 text-xs font-medium text-muted-foreground">
              Operation
            </div>
            {pinned.map((key) => (
              <div
                key={key}
                role="columnheader"
                className="flex min-w-0 items-center gap-1 border-l px-2 text-xs font-medium"
              >
                <span className="truncate">{key}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Unpin ${key}`}
                  onClick={() => togglePin(key)}
                >
                  <PinIcon className="fill-current" aria-hidden />
                </Button>
              </div>
            ))}
            <div role="columnheader" className="min-w-0 border-l">
              <TimeAxis scale={scale} markers={markers} />
            </div>
          </div>

          <div
            aria-hidden
            className="pointer-events-none relative"
            style={{ gridRow: `2 / ${rows.length + 2}`, gridColumn: "-2 / -1" }}
          >
            <TimeGuides scale={scale} markers={markers} />
          </div>

          {rows.map((row, index) => {
            const { span } = row
            const selected = span.id === selectedId
            const matched = matchSet.has(span.id)
            const errorCount = span.errors?.length ?? 0
            const start = scale.position(span.start)
            const end = scale.position(span.start + Math.max(0, span.duration))
            return (
              <div
                key={span.id}
                id={rowDomId(span.id)}
                role="row"
                data-mini="row"
                aria-rowindex={index + 2}
                aria-level={row.depth + 1}
                aria-expanded={row.childCount > 0 ? row.expanded : undefined}
                aria-selected={selected}
                title={`${span.op} - ${span.description}`}
                onClick={() => {
                  focusGrid()
                  setSelectedId(span.id)
                  setPanelOpen(true)
                }}
                className={cn(
                  "relative grid h-7 scroll-mt-10 cursor-default grid-cols-subgrid items-center text-xs select-none",
                  matched ? "bg-[var(--mini-accent-soft)]" : index % 2 === 1 && "bg-muted/40",
                  searching && !matched && "opacity-50",
                  selected && "outline-2 -outline-offset-2 outline-primary"
                )}
                style={{ gridRow: index + 2, gridColumn: "1 / -1" }}
              >
                <div
                  role="gridcell"
                  className={cn("flex h-full min-w-0 items-center pr-2 pl-2", errorCount > 0 && "text-destructive")}
                >
                  <IndentGuides row={row} />
                  {row.childCount > 0 ? (
                    <CollapsePill
                      count={row.childCount}
                      expanded={row.expanded}
                      label={`${row.expanded ? "Collapse" : "Expand"} ${row.childCount} ${row.childCount === 1 ? "child" : "children"} of ${span.op}`}
                      onToggle={() => toggleCollapsed(span.id)}
                    />
                  ) : (
                    <span aria-hidden className="mr-2 ml-0.5 size-1 shrink-0 rounded-full bg-border" />
                  )}
                  <span className="min-w-0 flex-1 truncate">
                    <span className="font-semibold">{span.op}</span>
                    <span className={errorCount > 0 ? undefined : "text-muted-foreground"}>
                      {" — "}
                      {span.description}
                    </span>
                  </span>
                </div>
                {pinned.map((key) => (
                  <div
                    key={key}
                    role="gridcell"
                    className="h-full min-w-0 truncate border-l px-2 leading-7 text-muted-foreground"
                  >
                    {span.attributes?.[key] ?? "–"}
                  </div>
                ))}
                <div role="gridcell" className="h-full min-w-0 overflow-hidden border-l">
                  <DurationBar
                    left={start}
                    width={end - start}
                    color={`var(--chart-${palette.get(opCategory(span.op)) ?? 1})`}
                    label={formatDuration(span.duration)}
                    errors={errorCount}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const hasSpans = ready && spans.length > 0

  const panel = showPanel ? (
    <div ref={panelWrapRef} className="h-full min-h-0">
      <SpanPanel
        span={selectedSpan}
        spans={spans}
        palette={palette}
        origin={scale.origin}
        total={scale.duration}
        pinnedKeys={pinned}
        onTogglePin={togglePin}
        onSelectParent={(id) => jumpTo(id)}
        onClose={closePanel}
      />
    </div>
  ) : null

  return (
    <div ref={rootRef} className="flex h-full min-h-0 flex-col bg-background text-sm">
      <header className="flex shrink-0 flex-col gap-2 border-b px-3 py-2">
        <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
          <div className="min-w-0">
            {title ? <h2 className="truncate text-base font-semibold">{title}</h2> : null}
            {subtitle ? <p className="truncate text-xs text-muted-foreground">{subtitle}</p> : null}
          </div>
          {hasSpans ? (
            <dl className="ml-auto flex flex-wrap items-end gap-x-5 gap-y-1">
              <div>
                <dt className="text-[11px] text-muted-foreground">Spans</dt>
                <dd className="text-sm font-semibold tabular-nums">{fullRows.length}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-muted-foreground">Errors</dt>
                <dd
                  className={cn(
                    "flex items-center gap-1 text-sm font-semibold tabular-nums",
                    errorTotal > 0 && "text-destructive"
                  )}
                >
                  {errorTotal > 0 ? <TriangleAlertIcon className="size-3.5" aria-hidden /> : null}
                  {errorTotal}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-muted-foreground">Total duration</dt>
                <dd className="text-sm font-semibold tabular-nums">{formatDuration(scale.duration)}</dd>
              </div>
              {stats.map((stat) => (
                <div key={stat.label}>
                  <dt className="text-[11px] text-muted-foreground">{stat.label}</dt>
                  <dd
                    className={cn(
                      "flex items-center gap-1 text-sm font-semibold tabular-nums",
                      stat.tone === "bad" && "text-destructive"
                    )}
                  >
                    {stat.tone === "bad" ? <TriangleAlertIcon className="size-3.5" aria-hidden /> : null}
                    {stat.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
        {hasSpans ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <ul aria-label="Operation colors" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              {[...palette].map(([category, slot]) => (
                <li key={category} className="flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="size-2.5 rounded-sm"
                    style={{ backgroundColor: `var(--chart-${slot})` }}
                  />
                  {category}
                </li>
              ))}
            </ul>
            {hasGaps ? (
              <Button
                type="button"
                size="xs"
                variant={compress ? "secondary" : "outline"}
                aria-pressed={compress}
                onClick={() => setCompress(!compress)}
                className="ml-auto"
              >
                <FoldHorizontalIcon aria-hidden />
                Compress gaps
              </Button>
            ) : null}
          </div>
        ) : null}
      </header>
      {hasSpans ? (
        <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2">
          <Input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onSearchKeyDown}
            placeholder="Search in trace"
            aria-label="Search in trace"
            className="h-8"
          />
          <span aria-live="polite" className="w-20 shrink-0 text-xs text-muted-foreground tabular-nums">
            {matchText}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label="Previous match"
            disabled={matches.length === 0}
            onClick={() => stepMatch(-1)}
          >
            <ChevronUpIcon aria-hidden />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label="Next match"
            disabled={matches.length === 0}
            onClick={() => stepMatch(1)}
          >
            <ChevronDownIcon aria-hidden />
          </Button>
        </div>
      ) : null}
      <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
        <ResizablePanel id="waterfall" minSize="30%">
          <div className="relative h-full min-h-0">
            {body}
            {narrow && panel ? <div className="absolute inset-0 z-30 bg-background">{panel}</div> : null}
          </div>
        </ResizablePanel>
        {!narrow && panel ? (
          <Fragment>
            <ResizableHandle withHandle aria-label="Resize span panel" />
            <ResizablePanel id="span-panel" defaultSize="40%" minSize="25%" maxSize="65%">
              {panel}
            </ResizablePanel>
          </Fragment>
        ) : null}
      </ResizablePanelGroup>
    </div>
  )
}
