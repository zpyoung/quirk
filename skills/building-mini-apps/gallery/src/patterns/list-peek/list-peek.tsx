import {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ChevronDownIcon, ChevronUpIcon, XIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export type ListPeekItem = { id: string; title: string }

export type ListPeekProps<T extends ListPeekItem> = {
  items: T[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  renderPeek: (item: T) => ReactNode
  renderLead?: (item: T) => ReactNode
  renderMeta?: (item: T) => ReactNode
  groupBy?: (item: T) => string
  filterText?: (item: T) => string
  onOpen?: (item: T) => void
  highlightedId?: string | null
  onHighlightedIdChange?: (id: string | null) => void
  peekOpen?: boolean
  onPeekOpenChange?: (open: boolean) => void
  holdThresholdMs?: number
  autoFocus?: boolean
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

type Section<T> = { name: string | null; rows: T[] }

const heldFor = (since: number) => performance.now() - since

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

function toSections<T extends ListPeekItem>(rows: T[], groupBy?: (item: T) => string): Section<T>[] {
  if (!groupBy) return [{ name: null, rows }]
  const byName = new Map<string, T[]>()
  for (const row of rows) {
    const name = groupBy(row)
    byName.set(name, [...(byName.get(name) ?? []), row])
  }
  return [...byName].map(([name, grouped]) => ({ name, rows: grouped }))
}

const INTERACTIVE =
  "a,button,input,select,textarea,summary,[role=button],[role=link],[contenteditable=true]"

/**
 * Dense list with a keyboard highlight and a read-only side panel ("peek") that
 * follows it. Clicking a row highlights it and toggles the peek; Enter and
 * double-click call `onOpen`, and the host decides what opening means. Takes data
 * as props and never reads the store. Keys act when focus is on the page body or
 * inside this block, never while typing in an input. `autoFocus` focuses the list
 * on mount, for hosts that remount the block after a full view.
 */
export function ListPeek<T extends ListPeekItem>({
  items,
  status = "ready",
  error,
  onRetry,
  renderPeek,
  renderLead,
  renderMeta,
  groupBy,
  filterText,
  onOpen,
  highlightedId: highlightedProp,
  onHighlightedIdChange,
  peekOpen: peekOpenProp,
  onPeekOpenChange,
  holdThresholdMs = 250,
  autoFocus = false,
  emptyTitle = "Nothing here yet",
  emptyAction,
  "aria-label": ariaLabel = "Items",
}: ListPeekProps<T>) {
  const uid = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const hoveredId = useRef<string | null>(null)
  const pressStart = useRef<number | null>(null)
  const previousOrder = useRef<string[]>([])

  const [filter, setFilter] = useState("")
  const [highlightedId, setHighlightedId] = useControllable<string | null>(
    highlightedProp,
    null,
    onHighlightedIdChange
  )
  const [peekOpen, setPeekOpen] = useControllable(peekOpenProp, false, onPeekOpenChange)

  const ready = status === "ready"
  const sections = useMemo(() => {
    const query = filter.trim().toLowerCase()
    const matching = query
      ? items.filter((item) =>
          (filterText ? filterText(item) : item.title).toLowerCase().includes(query)
        )
      : items
    return toSections(matching, groupBy)
  }, [items, filter, filterText, groupBy])
  const rows = useMemo(() => sections.flatMap((section) => section.rows), [sections])
  const activeIndex = rows.findIndex((row) => row.id === highlightedId)
  const active = activeIndex === -1 ? undefined : rows[activeIndex]
  const showPeek = ready && peekOpen && active !== undefined
  const keysOn = ready && items.length > 0

  const rowDomId = (id: string) => `${uid}-row-${encodeURIComponent(id)}`
  const focusList = () => listRef.current?.focus({ preventScroll: true })

  const closePeek = () => {
    const focusInPanel = panelRef.current?.contains(document.activeElement)
    setPeekOpen(false)
    if (focusInPanel) focusList()
  }

  const clickedControl = (event: ReactMouseEvent<HTMLElement>) => {
    const control = (event.target as Element).closest(INTERACTIVE)
    return control !== null && control !== event.currentTarget && event.currentTarget.contains(control)
  }

  const onRowClick = (event: ReactMouseEvent<HTMLElement>, item: T) => {
    if (clickedControl(event)) return
    focusList()
    // the second click of a double-click must not undo the first click's toggle
    if (event.detail > 1) {
      setHighlightedId(item.id)
    } else if (item.id === highlightedId && peekOpen) {
      closePeek()
    } else {
      setHighlightedId(item.id)
      setPeekOpen(true)
    }
  }

  const onRowDoubleClick = (event: ReactMouseEvent<HTMLElement>, item: T) => {
    if (clickedControl(event)) return
    setHighlightedId(item.id)
    onOpen?.(item)
  }

  const highlightByKey = (id: string) => {
    setHighlightedId(id)
    if (document.activeElement !== listRef.current) focusList()
  }

  const move = (to: "next" | "previous" | "first" | "last") => {
    if (rows.length === 0) return
    let index: number
    if (to === "first") index = 0
    else if (to === "last") index = rows.length - 1
    else if (activeIndex === -1) index = to === "next" ? 0 : rows.length - 1
    else index = Math.min(rows.length - 1, Math.max(0, activeIndex + (to === "next" ? 1 : -1)))
    highlightByKey(rows[index].id)
  }

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) return true
    return target instanceof Node && rootRef.current?.contains(target) === true
  }
  const inPanel = (event: KeyboardEvent) =>
    event.target instanceof Node && panelRef.current?.contains(event.target) === true

  const releaseSpace = () => {
    const startedAt = pressStart.current
    pressStart.current = null
    if (startedAt !== null && heldFor(startedAt) >= holdThresholdMs) closePeek()
  }
  const releaseOnBlur = useEffectEvent(() => releaseSpace())
  useEffect(() => {
    const onBlur = () => releaseOnBlur()
    window.addEventListener("blur", onBlur)
    return () => window.removeEventListener("blur", onBlur)
  }, [])

  const navigate = (event: KeyboardEvent, to: Parameters<typeof move>[0]) => {
    if (!inScope(event) || inPanel(event)) return
    event.preventDefault()
    move(to)
  }
  useHotkeys("j,down", (event) => navigate(event, "next"), { enabled: keysOn })
  useHotkeys("k,up", (event) => navigate(event, "previous"), { enabled: keysOn })
  useHotkeys("home", (event) => navigate(event, "first"), { enabled: keysOn })
  useHotkeys("end", (event) => navigate(event, "last"), { enabled: keysOn })

  useHotkeys(
    "space",
    (event) => {
      if (event.type === "keyup") return releaseSpace()
      if (!inScope(event) || inPanel(event)) return
      const target = active ?? rows.find((row) => row.id === hoveredId.current)
      if (!target) return
      event.preventDefault()
      if (event.repeat) return
      if (peekOpen) {
        pressStart.current = null
        closePeek()
        return
      }
      if (!active) highlightByKey(target.id)
      setPeekOpen(true)
      pressStart.current = performance.now()
    },
    { enabled: keysOn, keydown: true, keyup: true }
  )

  useHotkeys(
    "enter",
    (event) => {
      if (!onOpen || !active || !inScope(event) || inPanel(event)) return
      event.preventDefault()
      onOpen(active)
    },
    { enabled: keysOn }
  )

  useHotkeys(
    "slash",
    (event) => {
      if (!inScope(event)) return
      event.preventDefault()
      inputRef.current?.focus()
    },
    { enabled: ready }
  )

  useHotkeys(
    "esc",
    (event) => {
      if (!inScope(event)) return
      if (inPanel(event)) {
        if (peekOpen) {
          event.preventDefault()
          closePeek()
        }
        return
      }
      if (filter) {
        event.preventDefault()
        setFilter("")
      } else if (peekOpen) {
        event.preventDefault()
        closePeek()
      } else if (highlightedId !== null) {
        event.preventDefault()
        setHighlightedId(null)
      }
    },
    { enabled: ready }
  )

  const reconcile = useEffectEvent(() => {
    if (!ready) return
    if (highlightedId !== null && !rows.some((row) => row.id === highlightedId)) {
      const removed = !items.some((item) => item.id === highlightedId)
      const at = previousOrder.current.indexOf(highlightedId)
      const neighbour = removed && at !== -1 ? rows[Math.min(at, rows.length - 1)] : undefined
      setHighlightedId(neighbour?.id ?? null)
      if (peekOpen) setPeekOpen(false)
    } else if (peekOpen && highlightedId === null) {
      setPeekOpen(false)
    }
    previousOrder.current = rows.map((row) => row.id)
  })
  useEffect(() => reconcile(), [rows, highlightedId, peekOpen, ready])

  useEffect(() => {
    if (!showPeek) return
    const list = listRef
    // the panel's focused control is removed with it, which would drop focus to the body
    return () => {
      if (document.activeElement === document.body) list.current?.focus({ preventScroll: true })
    }
  }, [showPeek])

  useEffect(() => {
    if (autoFocus) listRef.current?.focus({ preventScroll: true })
  }, [autoFocus])

  useEffect(() => {
    if (highlightedId === null) return
    const element = document.getElementById(`${uid}-row-${encodeURIComponent(highlightedId)}`)
    element?.scrollIntoView({ block: "nearest" })
  }, [highlightedId, uid])

  const onFilterKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault()
      if (filter) setFilter("")
      else {
        event.currentTarget.blur()
        focusList()
      }
    } else if (event.key === "ArrowDown") {
      event.preventDefault()
      if (rows.length > 0) {
        setHighlightedId(rows[0].id)
        focusList()
      }
    }
  }

  const count = filter.trim()
    ? `${rows.length} of ${items.length} items`
    : `${items.length} ${items.length === 1 ? "item" : "items"}`

  let listArea: ReactNode
  if (status === "loading") {
    listArea = <LoadingState label="Loading items" />
  } else if (status === "error") {
    listArea = <ErrorState error={error ?? new Error("Unknown error")} onRetry={onRetry} />
  } else if (items.length === 0) {
    listArea = (
      <EmptyState
        title={emptyTitle}
        description="Items you add will show up here."
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
    listArea = (
      <EmptyState
        title={`No items match "${filter.trim()}"`}
        description="Try a different word, or clear the filter."
        action={
          <Button variant="outline" size="sm" onClick={() => setFilter("")}>
            Clear filter
          </Button>
        }
      />
    )
  } else {
    const renderRow = (item: T) => {
      const highlighted = item.id === highlightedId
      return (
        <div
          key={item.id}
          id={rowDomId(item.id)}
          role="option"
          data-mini="row"
          aria-selected={highlighted}
          title={item.title}
          onClick={(event) => onRowClick(event, item)}
          onDoubleClick={(event) => onRowDoubleClick(event, item)}
          onMouseEnter={() => {
            hoveredId.current = item.id
          }}
          onMouseLeave={() => {
            if (hoveredId.current === item.id) hoveredId.current = null
          }}
          className={cn(
            "flex h-10 cursor-default select-none items-center gap-3 border-b border-border/60 px-3",
            highlighted ? "bg-accent" : "hover:bg-accent/50"
          )}
        >
          {renderLead ? (
            <span className="w-16 shrink-0 truncate text-xs text-muted-foreground tabular-nums">
              {renderLead(item)}
            </span>
          ) : null}
          <span className="min-w-0 flex-1 truncate">{item.title}</span>
          {renderMeta ? (
            <span className="min-w-12 max-w-[40%] shrink-[100] truncate text-xs text-muted-foreground">
              {renderMeta(item)}
            </span>
          ) : null}
        </div>
      )
    }

    listArea = (
      <div
        ref={listRef}
        role="listbox"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-activedescendant={active ? rowDomId(active.id) : undefined}
        className="h-full overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50"
      >
        {sections.map((section, index) =>
          section.name === null ? (
            section.rows.map(renderRow)
          ) : (
            <div key={section.name} role="group" aria-labelledby={`${uid}-group-${index}`}>
              <div
                id={`${uid}-group-${index}`}
                data-mini="group-header"
                className="flex h-9 items-center gap-2 border-b border-border/60 bg-muted/60 px-3 text-xs font-medium"
              >
                <span className="truncate">{section.name}</span>
                <span className="text-muted-foreground tabular-nums">{section.rows.length}</span>
              </div>
              {section.rows.map(renderRow)}
            </div>
          )
        )}
      </div>
    )
  }

  const step = (delta: 1 | -1) => {
    const target = rows[activeIndex + delta]
    if (target) setHighlightedId(target.id)
  }

  return (
    <div ref={rootRef} className="@container flex h-full min-h-0 flex-col bg-background text-sm">
      <div className="flex h-11 shrink-0 items-center gap-3 border-b px-3">
        <Input
          ref={inputRef}
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          onKeyDown={onFilterKeyDown}
          disabled={!ready}
          placeholder="Filter (press /)"
          aria-label="Filter items"
          className="h-8 max-w-64"
        />
        <span
          aria-live="polite"
          className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums"
        >
          {ready ? count : ""}
        </span>
      </div>
      <div className="relative flex min-h-0 flex-1">
        <div className="min-h-0 min-w-0 flex-1">{listArea}</div>
        {showPeek ? (
          <aside
            ref={panelRef}
            aria-label="Preview"
            data-mini="panel"
            className="flex min-h-0 w-[42%] shrink-0 flex-col border-l bg-background @max-[720px]:absolute @max-[720px]:inset-0 @max-[720px]:z-10 @max-[720px]:w-full @max-[720px]:border-l-0"
          >
            <div className="flex h-11 shrink-0 items-center gap-1 border-b px-3">
              <span
                aria-live="polite"
                className="mr-auto text-xs text-muted-foreground tabular-nums"
              >
                {activeIndex + 1} / {rows.length}
              </span>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Previous item"
                aria-disabled={activeIndex === 0}
                className="aria-disabled:opacity-40"
                onClick={() => step(-1)}
              >
                <ChevronUpIcon aria-hidden />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Next item"
                aria-disabled={activeIndex === rows.length - 1}
                className="aria-disabled:opacity-40"
                onClick={() => step(1)}
              >
                <ChevronDownIcon aria-hidden />
              </Button>
              <Button variant="ghost" size="icon-xs" aria-label="Close preview" onClick={closePeek}>
                <XIcon aria-hidden />
              </Button>
            </div>
            <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:block!">
              <div className="p-4 break-words">{renderPeek(active)}</div>
            </ScrollArea>
          </aside>
        ) : null}
      </div>
    </div>
  )
}
