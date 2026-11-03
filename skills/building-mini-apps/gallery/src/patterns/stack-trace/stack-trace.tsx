import { useId, useMemo, useRef, useState, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import {
  ArrowDownUpIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"

import { CodeExcerpt } from "./code-excerpt"
import {
  defaultOpenFrameId,
  effectiveView,
  foldFrames,
  isExpandable,
  type TraceRow,
} from "./frames"
import type { FrameOrder, FrameView, StackException, StackFrame } from "./types"

export type StackTraceProps = {
  exceptions: StackException[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  defaultView?: FrameView
  defaultOrder?: FrameOrder
  onViewChange?: (view: FrameView) => void
  onOrderChange?: (order: FrameOrder) => void
  emptyTitle?: string
  "aria-label"?: string
}

type Section = {
  exception: StackException
  open: boolean
  rows: TraceRow[]
  fallback: boolean
}

const frameKey = (exceptionId: string, frameId: string) =>
  `fr|${exceptionId}|${frameId}`
const foldKey = (exceptionId: string, id: string) => `fo|${exceptionId}|${id}`
const exceptionKey = (exceptionId: string) => `ex|${exceptionId}`

const FOCUS_RING =
  "outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/60"

function framePlace(frame: StackFrame) {
  if (frame.lineNo === undefined) return null
  return frame.colNo === undefined
    ? `line ${frame.lineNo}`
    : `line ${frame.lineNo}:${frame.colNo}`
}

function FrameHeader({
  frame,
  expandable,
  open,
  panelId,
  domId,
  navKey,
  tabStop,
  onFocus,
  onToggle,
  folded,
}: {
  frame: StackFrame
  expandable: boolean
  open: boolean
  panelId: string
  domId: string
  navKey: string
  tabStop: boolean
  onFocus: (key: string) => void
  onToggle: () => void
  folded: boolean
}) {
  const path = frame.filename || frame.module || "unknown"
  const place = framePlace(frame)
  const content = (
    <>
      <span
        title={frame.filename || frame.module}
        className="max-w-full min-w-0 truncate font-mono text-xs"
      >
        {path}
      </span>
      {frame.function || place ? (
        <span className="min-w-0 truncate text-xs text-muted-foreground">
          {frame.function ? (
            <>
              in <span className="font-mono">{frame.function}</span>
            </>
          ) : null}
          {frame.function && place ? " at " : null}
          {place}
        </span>
      ) : null}
      <span className="ml-auto flex shrink-0 items-center gap-2">
        {frame.inApp ? (
          <Badge variant="secondary" className="font-normal">
            In app
          </Badge>
        ) : null}
        {expandable ? (
          <ChevronDownIcon
            aria-hidden
            className={cn(
              "size-4 text-muted-foreground transition-transform",
              open && "rotate-180"
            )}
          />
        ) : (
          <span className="size-4" aria-hidden />
        )}
      </span>
    </>
  )
  const className = cn(
    "flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-0.5 px-3 text-left",
    folded ? "min-h-7 py-1" : "min-h-8 py-1.5",
    frame.inApp ? "text-foreground" : "text-muted-foreground",
    expandable && "cursor-pointer hover:bg-accent/50",
    FOCUS_RING
  )
  if (!expandable) {
    return (
      <div
        id={domId}
        data-nav-key={navKey}
        tabIndex={tabStop ? 0 : -1}
        onFocus={() => onFocus(navKey)}
        className={className}
      >
        {content}
      </div>
    )
  }
  return (
    <button
      type="button"
      id={domId}
      data-nav-key={navKey}
      tabIndex={tabStop ? 0 : -1}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      onFocus={() => onFocus(navKey)}
      onClick={onToggle}
      className={className}
    >
      {content}
    </button>
  )
}

/**
 * Collapsible stack frames for one or more chained exceptions. Relevant frames
 * open to a numbered source excerpt, runs of library frames fold into one row,
 * and the view and order can be switched. Takes data as props and never reads the
 * store. Arrow keys, Home and End move focus between rows when focus is on the
 * page body or inside the list, never while typing in an input; Enter and Space
 * toggle the focused row.
 */
export function StackTrace({
  exceptions,
  status = "ready",
  error,
  onRetry,
  defaultView = "relevant",
  defaultOrder = "newest",
  onViewChange,
  onOrderChange,
  emptyTitle = "No stack trace",
  "aria-label": ariaLabel = "Stack trace",
}: StackTraceProps) {
  const uid = useId()
  const listRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<FrameView>(defaultView)
  const [order, setOrder] = useState<FrameOrder>(defaultOrder)
  const [frameOpen, setFrameOpen] = useState<ReadonlyMap<string, boolean>>(
    new Map()
  )
  const [exceptionOpen, setExceptionOpen] = useState<
    ReadonlyMap<string, boolean>
  >(new Map())
  const [openFolds, setOpenFolds] = useState<ReadonlySet<string>>(new Set())
  const [activeKey, setActiveKey] = useState<string | null>(null)

  const ready = status === "ready"

  const sections = useMemo<Section[]>(
    () =>
      exceptions.map((exception) => {
        const own = new Set(
          [...openFolds]
            .filter((key) => key.startsWith(`fo|${exception.id}|`))
            .map((key) => key.slice(`fo|${exception.id}|`.length))
        )
        return {
          exception,
          open: exceptionOpen.get(exceptionKey(exception.id)) ?? true,
          rows: foldFrames(exception.frames, view, order, own),
          fallback:
            view === "relevant" &&
            exception.frames.length > 0 &&
            effectiveView(exception.frames, view) === "full",
        }
      }),
    [exceptions, view, order, openFolds, exceptionOpen]
  )

  const navKeys = useMemo(
    () =>
      sections.flatMap(({ exception, open, rows }) => [
        exceptionKey(exception.id),
        ...(open
          ? rows.map((row) =>
              row.kind === "fold"
                ? foldKey(exception.id, row.id)
                : frameKey(exception.id, row.frame.id)
            )
          : []),
      ]),
    [sections]
  )
  const tabStopKey =
    activeKey !== null && navKeys.includes(activeKey) ? activeKey : navKeys[0]
  const domId = (key: string) => `${uid}-${encodeURIComponent(key)}`

  const changeView = (next: FrameView) => {
    setView(next)
    onViewChange?.(next)
  }
  const flipOrder = () => {
    const next: FrameOrder = order === "newest" ? "oldest" : "newest"
    setOrder(next)
    onOrderChange?.(next)
  }

  const toggleFrame = (key: string, open: boolean) =>
    setFrameOpen((prev) => new Map(prev).set(key, !open))
  const toggleException = (key: string, open: boolean) =>
    setExceptionOpen((prev) => new Map(prev).set(key, !open))
  const toggleFold = (key: string) =>
    setOpenFolds((prev) => {
      const next = new Set(prev)
      if (!next.delete(key)) next.add(key)
      return next
    })

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement)
      return true
    return target instanceof Node && listRef.current?.contains(target) === true
  }

  const move = (
    event: KeyboardEvent,
    to: "next" | "previous" | "first" | "last"
  ) => {
    if (!inScope(event) || navKeys.length === 0) return
    event.preventDefault()
    const current =
      event.target instanceof Element
        ? event.target.closest<HTMLElement>("[data-nav-key]")?.dataset.navKey
        : undefined
    const at = current === undefined ? -1 : navKeys.indexOf(current)
    let index: number
    if (to === "first") index = 0
    else if (to === "last") index = navKeys.length - 1
    else if (at === -1) index = to === "next" ? 0 : navKeys.length - 1
    else
      index = Math.min(
        navKeys.length - 1,
        Math.max(0, at + (to === "next" ? 1 : -1))
      )
    document.getElementById(domId(navKeys[index]))?.focus()
  }

  const keysOn = ready && navKeys.length > 0
  useHotkeys("down", (event) => move(event, "next"), { enabled: keysOn })
  useHotkeys("up", (event) => move(event, "previous"), { enabled: keysOn })
  useHotkeys("home", (event) => move(event, "first"), { enabled: keysOn })
  useHotkeys("end", (event) => move(event, "last"), { enabled: keysOn })

  if (status === "loading") return <LoadingState label="Loading stack trace" />
  if (status === "error") {
    return (
      <ErrorState
        error={error ?? new Error("Unknown error")}
        onRetry={onRetry}
      />
    )
  }
  if (exceptions.length === 0) {
    return (
      <EmptyState title={emptyTitle} description="This event has no frames." />
    )
  }

  const renderRow = (exception: StackException, row: TraceRow): ReactNode => {
    if (row.kind === "fold") {
      const key = foldKey(exception.id, row.id)
      const noun = row.count === 1 ? "frame" : "frames"
      return (
        <li key={key} className="border-t border-border first:border-t-0">
          <button
            type="button"
            id={domId(key)}
            data-nav-key={key}
            tabIndex={key === tabStopKey ? 0 : -1}
            aria-expanded={row.open}
            onFocus={() => setActiveKey(key)}
            onClick={() => toggleFold(key)}
            className={cn(
              "flex min-h-7 w-full items-center gap-2 bg-muted/50 px-3 py-1 text-left text-xs text-muted-foreground italic hover:bg-muted",
              FOCUS_RING
            )}
          >
            {row.open ? (
              <ChevronDownIcon aria-hidden className="size-3.5" />
            ) : (
              <ChevronRightIcon aria-hidden className="size-3.5" />
            )}
            {row.open ? "Hide" : "Show"} {row.count} more {noun}
          </button>
        </li>
      )
    }

    const { frame, folded } = row
    const key = frameKey(exception.id, frame.id)
    const expandable = isExpandable(frame)
    const open =
      expandable &&
      (frameOpen.get(key) ?? frame.id === defaultOpenFrameId(exception.frames))
    const panelId = `${domId(key)}-source`
    const place = framePlace(frame)
    return (
      <li
        key={key}
        className={cn(
          "border-t border-border first:border-t-0",
          folded && "bg-muted/30"
        )}
      >
        <FrameHeader
          frame={frame}
          expandable={expandable}
          open={open}
          panelId={panelId}
          domId={domId(key)}
          navKey={key}
          tabStop={key === tabStopKey}
          onFocus={setActiveKey}
          onToggle={() => toggleFrame(key, open)}
          folded={folded}
        />
        {open && frame.contextLines ? (
          <div id={panelId}>
            <CodeExcerpt
              lines={frame.contextLines}
              failingLine={frame.lineNo}
              label={`Source of ${frame.filename}${place ? `, ${place}` : ""}`}
            />
          </div>
        ) : null}
      </li>
    )
  }

  return (
    <div
      className="@container flex min-w-0 flex-col gap-3 text-sm"
      role="region"
      aria-label={ariaLabel}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          spacing={0}
          value={view}
          onValueChange={(next) => {
            if (next === "relevant" || next === "full") changeView(next)
          }}
          aria-label="Frames shown"
        >
          <ToggleGroupItem value="relevant">Most relevant</ToggleGroupItem>
          <ToggleGroupItem value="full">Full</ToggleGroupItem>
        </ToggleGroup>
        <Button
          variant="outline"
          size="sm"
          onClick={flipOrder}
          aria-label={`Frame order: ${order === "newest" ? "newest" : "oldest"} first. Switch to ${order === "newest" ? "oldest" : "newest"} first.`}
        >
          <ArrowDownUpIcon aria-hidden />
          {order === "newest" ? "Newest first" : "Oldest first"}
        </Button>
      </div>

      {exceptions.length > 1 ? (
        <p className="text-xs text-muted-foreground">
          There are {exceptions.length} chained exceptions
        </p>
      ) : null}

      <div ref={listRef} className="flex flex-col gap-4">
        {sections.map(({ exception, open, rows, fallback }) => {
          const headKey = exceptionKey(exception.id)
          const listId = `${domId(headKey)}-frames`
          const detail = [
            exception.mechanism,
            exception.handled === undefined
              ? undefined
              : exception.handled
                ? "handled"
                : "unhandled",
          ]
            .filter(Boolean)
            .join(" · ")
          return (
            <section key={exception.id} className="flex min-w-0 flex-col gap-2">
              <button
                type="button"
                id={domId(headKey)}
                data-nav-key={headKey}
                tabIndex={headKey === tabStopKey ? 0 : -1}
                aria-expanded={open}
                aria-controls={open ? listId : undefined}
                onFocus={() => setActiveKey(headKey)}
                onClick={() => toggleException(headKey, open)}
                className={cn(
                  "flex min-w-0 items-baseline gap-2 rounded-md px-1 py-1 text-left hover:bg-accent/50",
                  FOCUS_RING
                )}
              >
                {open ? (
                  <ChevronDownIcon
                    aria-hidden
                    className="size-4 shrink-0 self-center"
                  />
                ) : (
                  <ChevronRightIcon
                    aria-hidden
                    className="size-4 shrink-0 self-center"
                  />
                )}
                <span className="shrink-0 font-semibold">{exception.type}</span>
                {exception.value ? (
                  <span
                    title={exception.value}
                    className="min-w-0 truncate text-muted-foreground"
                  >
                    {exception.value}
                  </span>
                ) : null}
                {detail ? (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {detail}
                  </span>
                ) : null}
              </button>
              {open ? (
                exception.frames.length === 0 ? (
                  <p className="px-3 text-xs text-muted-foreground">
                    No frames recorded
                  </p>
                ) : (
                  <>
                    {fallback ? (
                      <p className="px-3 text-xs text-muted-foreground">
                        No in-app frames, showing every frame
                      </p>
                    ) : null}
                    <ol
                      id={listId}
                      aria-labelledby={domId(headKey)}
                      className="overflow-hidden rounded-md border border-border bg-card"
                    >
                      {rows.map((row) => renderRow(exception, row))}
                    </ol>
                  </>
                )
              ) : null}
            </section>
          )
        })}
      </div>
    </div>
  )
}
