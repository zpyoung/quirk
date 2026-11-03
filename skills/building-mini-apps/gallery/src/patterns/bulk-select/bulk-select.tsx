import {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

import { ActionBar } from "./action-bar"
import { IndeterminateCheckbox } from "./indeterminate-checkbox"
import {
  neighbourAfterRemoval,
  nextHighlight,
  pruneSelection,
  selectionState,
  setRange,
  toggleId,
} from "./selection"
import {
  CHECKBOX_COLUMN,
  type BulkSelectAction,
  type BulkSelectColumn,
  type BulkSelectRow,
} from "./types"

export type BulkSelectProps<T extends BulkSelectRow> = {
  items: T[]
  columns: BulkSelectColumn<T>[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  actions?: BulkSelectAction[]
  selectedIds?: string[]
  onSelectedIdsChange?: (ids: string[]) => void
  highlightedId?: string | null
  onHighlightedIdChange?: (id: string | null) => void
  onOpen?: (item: T) => void
  rowHeight?: number
  minWidth?: string
  rowLabel?: (item: T) => string
  selectionNoun?: string
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

const PLACEHOLDER_ROWS = 6

const INTERACTIVE =
  "a,button,input,select,textarea,summary,[role=button],[role=link],[role=checkbox],[contenteditable=true]"

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

/**
 * Dense table of multi-line rows with a keyboard highlight and row selection.
 * While any row is selected the column header becomes an action bar in place.
 * The selection is exposed through `selectedIds` / `onSelectedIdsChange` so a
 * host can hand it to another pattern. Takes data as props and never reads the
 * store. Keys act when focus is on the page body or inside this block, never
 * while typing in an input. Columns, actions and cells are the caller's.
 */
export function BulkSelect<T extends BulkSelectRow>({
  items,
  columns,
  status = "ready",
  error,
  onRetry,
  actions = [],
  selectedIds: selectedProp,
  onSelectedIdsChange,
  highlightedId: highlightedProp,
  onHighlightedIdChange,
  onOpen,
  rowHeight = 84,
  minWidth = "44rem",
  rowLabel,
  selectionNoun = "row",
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  "aria-label": ariaLabel = "Table",
}: BulkSelectProps<T>) {
  const uid = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const anchorRef = useRef<string | null>(null)
  const previousOrder = useRef<string[]>([])

  const [selectedIds, setSelectedIds] = useControllable<string[]>(
    selectedProp,
    [],
    onSelectedIdsChange
  )
  const [highlightedId, setHighlightedId] = useControllable<string | null>(
    highlightedProp,
    null,
    onHighlightedIdChange
  )

  const ready = status === "ready"
  const order = useMemo(() => items.map((item) => item.id), [items])
  const selected = useMemo(
    () => pruneSelection(order, selectedIds),
    [order, selectedIds]
  )
  const chosen = useMemo(() => new Set(selected), [selected])
  const state = selectionState(selected.length, order.length)
  const showBar = ready && selected.length > 0
  const keysOn = ready && items.length > 0
  const highlightedItem = items.find((item) => item.id === highlightedId)

  const rowDomId = (id: string) => `${uid}-row-${encodeURIComponent(id)}`
  const focusGrid = () => gridRef.current?.focus({ preventScroll: true })
  const template = `${CHECKBOX_COLUMN} ${columns
    .map((column) => column.width ?? "minmax(0, 1fr)")
    .join(" ")}`

  const toggleRow = (id: string, shift: boolean) => {
    const anchor = anchorRef.current
    const next =
      shift && anchor !== null && anchor !== id && order.includes(anchor)
        ? setRange(order, selected, anchor, id, !chosen.has(id))
        : toggleId(order, selected, id)
    anchorRef.current = id
    setSelectedIds(next)
    setHighlightedId(id)
    focusGrid()
  }

  const toggleAll = () => {
    anchorRef.current = null
    setSelectedIds(state === "all" ? [] : [...order])
    focusGrid()
  }

  const highlightByKey = (id: string | null) => {
    if (id === null) return
    setHighlightedId(id)
    if (document.activeElement !== gridRef.current) focusGrid()
  }

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement)
      return true
    return target instanceof Node && rootRef.current?.contains(target) === true
  }
  const onTable = (event: KeyboardEvent) => {
    const target = event.target
    return (
      target === document.body ||
      target === document.documentElement ||
      target === gridRef.current
    )
  }

  const navigate = (event: KeyboardEvent, direction: "next" | "previous") => {
    if (!inScope(event) || event.defaultPrevented) return
    event.preventDefault()
    highlightByKey(nextHighlight(order, highlightedId, direction))
  }
  useHotkeys("j,down", (event) => navigate(event, "next"), { enabled: keysOn })
  useHotkeys("k,up", (event) => navigate(event, "previous"), {
    enabled: keysOn,
  })

  useHotkeys(
    "x",
    (event) => {
      if (!inScope(event) || highlightedId === null || !highlightedItem) return
      event.preventDefault()
      toggleRow(highlightedId, false)
    },
    { enabled: keysOn }
  )

  useHotkeys(
    "enter",
    (event) => {
      if (!onOpen || !highlightedItem || !onTable(event)) return
      event.preventDefault()
      onOpen(highlightedItem)
    },
    { enabled: keysOn }
  )

  useHotkeys(
    "esc",
    (event) => {
      if (!inScope(event) || event.defaultPrevented) return
      if (selected.length > 0) {
        event.preventDefault()
        anchorRef.current = null
        setSelectedIds([])
      } else if (highlightedId !== null) {
        event.preventDefault()
        setHighlightedId(null)
      }
    },
    { enabled: ready }
  )

  const reconcile = useEffectEvent(() => {
    if (!ready) return
    if (selected.length !== selectedIds.length) setSelectedIds(selected)
    if (anchorRef.current !== null && !order.includes(anchorRef.current))
      anchorRef.current = null
    if (highlightedId !== null && !order.includes(highlightedId)) {
      setHighlightedId(
        neighbourAfterRemoval(previousOrder.current, order, highlightedId)
      )
    }
    previousOrder.current = order
  })
  useEffect(() => reconcile(), [order, selectedIds, highlightedId, ready])

  useEffect(() => {
    if (highlightedId === null) return
    document
      .getElementById(`${uid}-row-${encodeURIComponent(highlightedId)}`)
      ?.scrollIntoView({ block: "nearest" })
  }, [highlightedId, uid])

  const clickedControl = (event: ReactMouseEvent<HTMLElement>) => {
    const target = event.target as Element
    if (!event.currentTarget.contains(target)) return true
    const control = target.closest(INTERACTIVE)
    return control !== null && control !== event.currentTarget
  }

  const onRowClick = (event: ReactMouseEvent<HTMLElement>, item: T) => {
    if (clickedControl(event)) return
    setHighlightedId(item.id)
    focusGrid()
  }

  const onRowDoubleClick = (event: ReactMouseEvent<HTMLElement>, item: T) => {
    if (clickedControl(event)) return
    setHighlightedId(item.id)
    onOpen?.(item)
  }

  const headerChecked =
    state === "all" ? true : state === "some" ? "mixed" : false

  let body
  if (status === "error") {
    body = (
      <ErrorState
        error={error ?? new Error("Unknown error")}
        onRetry={onRetry}
      />
    )
  } else if (ready && items.length === 0) {
    body = (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
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
    const countLabel = `${selected.length} ${selected.length === 1 ? selectionNoun : `${selectionNoun}s`} selected`
    body = (
      <>
        <div className="flex min-h-0 flex-1 overflow-x-auto">
          <div
            ref={gridRef}
            role="grid"
            tabIndex={0}
            aria-label={ariaLabel}
            aria-multiselectable
            aria-busy={status === "loading"}
            aria-rowcount={items.length + 1}
            aria-colcount={columns.length + 1}
            aria-activedescendant={
              highlightedItem ? rowDomId(highlightedItem.id) : undefined
            }
            className="flex min-w-0 flex-1 flex-col outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset"
            style={{ minWidth }}
          >
            <div role="rowgroup" className="shrink-0 border-b bg-muted/40">
              {showBar ? (
                <div role="row" aria-rowindex={1}>
                  <div role="gridcell" aria-colspan={columns.length + 1}>
                    <ActionBar
                      actions={actions}
                      selectedIds={selected}
                      selectionState={state}
                      noun={selectionNoun}
                      onToggleAll={toggleAll}
                    />
                  </div>
                </div>
              ) : (
                <div
                  role="row"
                  aria-rowindex={1}
                  data-mini="header"
                  className="grid h-10 items-center text-xs font-medium text-muted-foreground"
                  style={{ gridTemplateColumns: template }}
                >
                  <div role="columnheader" className="flex justify-center">
                    <IndeterminateCheckbox
                      checked={headerChecked}
                      onToggle={toggleAll}
                      label="Select all rows"
                      disabled={!ready}
                    />
                  </div>
                  {columns.map((column) => (
                    <div
                      key={column.id}
                      role="columnheader"
                      className={cn(
                        "min-w-0 truncate px-3",
                        column.align === "end" && "text-right"
                      )}
                    >
                      {column.header}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div role="rowgroup" className="min-h-0 flex-1 overflow-y-auto">
              {ready ? (
                items.map((item, index) => {
                  const isSelected = chosen.has(item.id)
                  const isHighlighted = item.id === highlightedId
                  return (
                    <div
                      key={item.id}
                      id={rowDomId(item.id)}
                      role="row"
                      aria-rowindex={index + 2}
                      aria-selected={isSelected}
                      data-mini="row"
                      onClick={(event) => onRowClick(event, item)}
                      onDoubleClick={(event) => onRowDoubleClick(event, item)}
                      className={cn(
                        "grid cursor-default items-center border-b border-border/60 select-none",
                        isSelected
                          ? "bg-[var(--mini-accent-soft)]"
                          : isHighlighted
                            ? "bg-accent"
                            : "hover:bg-accent/50",
                        isHighlighted &&
                          "shadow-[inset_2px_0_0_0_var(--primary)]"
                      )}
                      style={{
                        gridTemplateColumns: template,
                        height: rowHeight,
                      }}
                    >
                      <div role="gridcell" className="flex justify-center">
                        <IndeterminateCheckbox
                          checked={isSelected}
                          tabIndex={-1}
                          onToggle={({ shiftKey }) =>
                            toggleRow(item.id, shiftKey)
                          }
                          label={`Select ${rowLabel ? rowLabel(item) : item.id}`}
                        />
                      </div>
                      {columns.map((column) => (
                        <div
                          key={column.id}
                          role="gridcell"
                          data-mini="cell"
                          className={cn(
                            "flex min-w-0 flex-col justify-center px-3",
                            column.align === "end" &&
                              "items-end text-right tabular-nums"
                          )}
                        >
                          {column.cell(item)}
                        </div>
                      ))}
                    </div>
                  )
                })
              ) : (
                <>
                  <div className="sr-only">
                    <LoadingState label="Loading rows" />
                  </div>
                  {Array.from({ length: PLACEHOLDER_ROWS }, (_, index) => (
                    <div
                      key={index}
                      aria-hidden
                      data-mini="placeholder-row"
                      className="grid items-center border-b border-border/60"
                      style={{
                        gridTemplateColumns: template,
                        height: rowHeight,
                      }}
                    >
                      <div />
                      {columns.map((column, columnIndex) => (
                        <div key={column.id} className="px-3">
                          {columnIndex === 0 ? (
                            <Skeleton
                              className="w-[90%]"
                              style={{ height: Math.max(12, rowHeight - 28) }}
                            />
                          ) : (
                            <Skeleton className="h-5 w-3/4 max-w-20" />
                          )}
                        </div>
                      ))}
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
        <div aria-live="polite" className="sr-only">
          {showBar ? countLabel : ""}
        </div>
      </>
    )
  }

  return (
    <div
      ref={rootRef}
      className="@container flex h-full min-h-0 flex-col bg-background text-sm"
    >
      {body}
    </div>
  )
}
