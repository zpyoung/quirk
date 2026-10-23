import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type RefObject,
} from "react"
import { flushSync } from "react-dom"
import { useHotkeys } from "react-hotkeys-hook"
import { toast } from "sonner"
import { EyeIcon, Loader2Icon, PlusIcon, XIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Kbd } from "@/components/ui/kbd"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useCollection, type Collection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"

import { CellEditor } from "./cell-editor"
import { PendingPreview } from "./pending-preview"
import type { PendingChange, StagedColumn } from "./types"
import { useStagedEdits, type StagedRow } from "./use-staged-edits"

export type StagedTableProps<T extends { id: string; title: string }> = {
  collection: string
  columns: StagedColumn<T>[]
  seed?: T[]
  newItem: (id: string) => T
  rowLabel?: (item: T) => string
  onCommitted?: (changes: PendingChange<T>[]) => void
  onCommitError?: (error: Error, failed: PendingChange<T>[]) => void
}

type StagedStore<T extends { id: string }> = Pick<
  Collection<T>,
  "items" | "status" | "error" | "add" | "update" | "remove"
>

type Cell = { id: string; col: string }

const GUTTER = 44
const DEFAULT_WIDTH = 160
const NEW_TINT = "bg-[oklch(0.95_0.05_150)] dark:bg-[oklch(0.3_0.05_150)]"
const REMOVED_TINT = "bg-[oklch(0.95_0.04_25)] dark:bg-[oklch(0.3_0.05_25)]"

const sameCell = (a: Cell | null, b: Cell | null) => !!a && !!b && a.id === b.id && a.col === b.col
const textOf = (value: unknown) => (value === undefined || value === null ? "" : String(value))
const toError = (cause: unknown) => (cause instanceof Error ? cause : new Error(String(cause)))

function useTableHotkeys(
  root: RefObject<HTMLElement | null>,
  keys: string,
  run: (event: KeyboardEvent) => void,
  enabled: boolean
) {
  useHotkeys(
    keys,
    (event) => {
      if (event.target instanceof Node && root.current?.contains(event.target)) run(event)
    },
    { enabled }
  )
}

/** Edits the rows of a `useCollection` collection in a grid and applies them only on commit. */
export function StagedTable<T extends { id: string; title: string }>({
  collection,
  seed,
  ...rest
}: StagedTableProps<T>) {
  const store = useCollection<T>(collection, seed)
  return <StagedTableView {...rest} store={store} />
}

/** The table without its store binding, so a caller can hand it any store state. */
export function StagedTableView<T extends { id: string; title: string }>({
  columns,
  newItem,
  rowLabel,
  onCommitted,
  onCommitError,
  store,
}: Omit<StagedTableProps<T>, "collection" | "seed"> & { store: StagedStore<T> }) {
  const edits = useStagedEdits(store.items)
  const { rows, changes } = edits
  const ready = store.status === "ready"

  const [active, setActive] = useState<Cell | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [editing, setEditing] = useState<Cell | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [committing, setCommitting] = useState(false)

  const root = useRef<HTMLDivElement>(null)
  const cancelButton = useRef<HTMLButtonElement>(null)
  const focusRequest = useRef(false)
  const anchor = useRef<string | null>(null)
  const draft = useRef<string | undefined>(undefined)
  const latest = useRef({ changes, items: store.items, editing })
  useLayoutEffect(() => {
    latest.current = { changes, items: store.items, editing }
  })

  const labelOf = rowLabel ?? ((item: T) => item.title)
  const nameOf = (item: T) => labelOf(item).trim() || item.id
  const editable = columns.filter((column) => !column.readOnly)
  const columnByKey = useMemo(() => new Map(columns.map((c) => [c.key as string, c])), [columns])
  const rowIndex = useMemo(() => new Map(rows.map((row, i) => [row.item.id, i])), [rows])
  const selectedIds = useMemo(() => selected.filter((id) => rowIndex.has(id)), [selected, rowIndex])
  const firstCell: Cell | null = rows.length > 0 && columns.length > 0
    ? { id: rows[0].item.id, col: columns[0].key }
    : null
  const cursor = active && rowIndex.has(active.id) ? active : firstCell

  const updateCells = changes.reduce(
    (sum, change) => sum + (change.kind === "update" ? Object.keys(change.patch).length : 0),
    0
  )
  const newCount = changes.filter((c) => c.kind === "add").length
  const removedCount = changes.filter((c) => c.kind === "remove").length
  const pending = updateCells + newCount + removedCount
  const idle = ready && !committing
  const hasPending = idle && pending > 0

  const focusCell = useCallback((cell: Cell | null) => {
    if (!cell || !root.current) return
    root.current
      .querySelector<HTMLElement>(`[data-row-id="${CSS.escape(cell.id)}"][data-col="${CSS.escape(cell.col)}"]`)
      ?.focus()
  }, [])

  useEffect(() => {
    if (!focusRequest.current || editing) return
    focusRequest.current = false
    focusCell(cursor)
  })

  const goTo = (cell: Cell) => {
    focusRequest.current = true
    anchor.current = cell.id
    setActive(cell)
    setSelected([cell.id])
  }

  const startEdit = (cell: Cell | null): boolean => {
    if (!cell || !idle) return false
    const row = rows[rowIndex.get(cell.id) ?? -1]
    const column = columnByKey.get(cell.col)
    if (!row || row.state === "removed" || !column || column.readOnly) return false
    draft.current = undefined
    focusRequest.current = true
    setActive(cell)
    setSelected([cell.id])
    setEditing(cell)
    return true
  }

  const acceptEdit = (cell: Cell, raw: string | undefined) => {
    const column = columnByKey.get(cell.col)
    if (column && raw !== undefined) {
      let value: unknown = raw
      if (column.type === "number") value = raw.trim() === "" ? undefined : Number(raw)
      if (value !== undefined && !(typeof value === "number" && !Number.isFinite(value))) {
        edits.setCell(cell.id, column.key, value as T[keyof T])
      }
    }
    focusRequest.current = true
    setEditing((current) => (sameCell(current, cell) ? null : current))
  }

  const acceptAndNext = (cell: Cell, raw: string) => {
    acceptEdit(cell, raw)
    const at = editable.findIndex((column) => column.key === cell.col)
    const next = editable[at + 1]
    if (next) startEdit({ id: cell.id, col: next.key })
  }

  const cancelEdit = (cell: Cell) => {
    focusRequest.current = true
    setEditing((current) => (sameCell(current, cell) ? null : current))
  }

  const addRow = () => {
    if (!idle) return
    const item = newItem(crypto.randomUUID())
    edits.addRow(item)
    const first = editable[0]
    if (first) {
      const cell = { id: item.id, col: first.key }
      draft.current = undefined
      focusRequest.current = true
      setActive(cell)
      setSelected([item.id])
      setEditing(cell)
    } else if (columns[0]) {
      goTo({ id: item.id, col: columns[0].key })
    }
  }

  const duplicateSelected = () => {
    if (!idle || selectedIds.length === 0) return
    const copies = selectedIds.flatMap((id) => {
      const row = rows[rowIndex.get(id) ?? -1]
      if (!row || row.state === "removed") return []
      const copyId = crypto.randomUUID()
      return [{ ...newItem(copyId), ...row.item, id: copyId }]
    })
    if (copies.length === 0) return
    copies.forEach((copy) => edits.addRow(copy))
    focusRequest.current = true
    setSelected(copies.map((copy) => copy.id))
    setActive({ id: copies[0].id, col: cursor?.col ?? columns[0].key })
  }

  const removeSelected = () => {
    if (!idle || selectedIds.length === 0) return
    const dropped = new Set(
      selectedIds.filter((id) => rows[rowIndex.get(id) ?? -1]?.state === "new")
    )
    const survivors = rows.filter((row) => !dropped.has(row.item.id))
    selectedIds.forEach((id) => edits.removeRow(id))
    if (dropped.size > 0 && survivors.length > 0 && cursor) {
      const at = Math.min(rowIndex.get(cursor.id) ?? 0, survivors.length - 1)
      goTo({ id: survivors[at].item.id, col: cursor.col })
    }
  }

  const setActiveEmpty = () => {
    const column = cursor && columnByKey.get(cursor.col)
    const row = cursor && rows[rowIndex.get(cursor.id) ?? -1]
    if (!idle || !cursor || !column || column.readOnly || !row || row.state === "removed") return
    edits.setCell(cursor.id, column.key, (column.type === "number" ? 0 : "") as T[keyof T])
  }

  const commit = async () => {
    const { changes: queued, items } = latest.current
    if (!ready || committing || queued.length === 0) return
    setCommitting(true)
    setPreviewOpen(false)
    const written: PendingChange<T>[] = []
    let failure: Error | undefined
    for (const change of queued) {
      try {
        if (change.kind === "update") await store.update(change.id, change.patch)
        else if (change.kind === "add") await store.add(change.item)
        else await store.remove(change.id)
        written.push(change)
      } catch (cause) {
        failure = toError(cause)
        break
      }
    }
    edits.settle(written)
    setCommitting(false)
    focusRequest.current = true
    if (failure) {
      const failed = queued.slice(written.length)
      const first = failed[0]
      const subject = first.kind === "add" ? first.item : items.find((i) => i.id === first.id)
      toast.error(`Could not save ${subject ? `"${nameOf(subject)}"` : "a change"}: ${failure.message}`)
      onCommitError?.(failure, failed)
    } else {
      onCommitted?.(written)
    }
  }

  const requestCommit = () => {
    if (editing) {
      const cell = editing
      flushSync(() => acceptEdit(cell, draft.current))
    }
    void commit()
  }

  const requestDiscard = () => {
    if (!hasPending) return
    setPreviewOpen(false)
    setConfirmOpen(true)
  }

  const confirmDiscard = () => {
    edits.discard()
    setConfirmOpen(false)
  }

  const selectCell = (cell: Cell) => {
    anchor.current = cell.id
    setActive(cell)
    setSelected([cell.id])
  }

  const selectRow = (id: string, event: MouseEvent) => {
    const col = cursor?.col ?? columns[0]?.key
    if (!col) return
    setActive({ id, col })
    if (event.shiftKey && anchor.current && rowIndex.has(anchor.current)) {
      const [from, to] = [rowIndex.get(anchor.current)!, rowIndex.get(id)!].sort((a, b) => a - b)
      setSelected(rows.slice(from, to + 1).map((row) => row.item.id))
      return
    }
    anchor.current = id
    setSelected((current) =>
      event.metaKey || event.ctrlKey
        ? current.includes(id)
          ? current.filter((x) => x !== id)
          : [...current, id]
        : [id]
    )
  }

  const move = (event: KeyboardEvent) => {
    if (!cursor || rows.length === 0) return
    event.preventDefault()
    const r = rowIndex.get(cursor.id) ?? 0
    const c = Math.max(0, columns.findIndex((column) => column.key === cursor.col))
    const dr = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0
    const dc = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0
    const nextRow = Math.min(rows.length - 1, Math.max(0, r + dr))
    const nextCol = Math.min(columns.length - 1, Math.max(0, c + dc))
    goTo({ id: rows[nextRow].item.id, col: columns[nextCol].key })
  }

  const jump = (event: KeyboardEvent) => {
    if (!cursor || rows.length === 0) return
    event.preventDefault()
    const target = event.key === "ArrowUp" ? rows[0] : rows[rows.length - 1]
    goTo({ id: target.item.id, col: cursor.col })
  }

  const tableLive = idle && !editing && !confirmOpen
  useTableHotkeys(root, "up,down,left,right", move, tableLive)
  useTableHotkeys(root, "mod+up,mod+down", jump, tableLive)
  useTableHotkeys(
    root,
    "enter",
    (event) => {
      if (startEdit(cursor)) event.preventDefault()
    },
    tableLive
  )
  useTableHotkeys(
    root,
    "tab",
    (event) => {
      if (selectedIds.length > 0 && startEdit(cursor)) event.preventDefault()
    },
    tableLive
  )
  useTableHotkeys(root, "esc", () => setSelected([]), tableLive)
  useTableHotkeys(root, "delete,backspace", removeSelected, tableLive)

  const global = idle && !confirmOpen
  useHotkeys("mod+s", requestCommit, { enableOnFormTags: true, preventDefault: true })
  useHotkeys("mod+shift+p", () => hasPending && setPreviewOpen((open) => !open), {
    enabled: global,
    preventDefault: true,
  })
  useHotkeys("mod+i", addRow, { enabled: global, preventDefault: true })
  useHotkeys("mod+d", duplicateSelected, { enabled: global, preventDefault: true })
  useHotkeys("mod+shift+delete,mod+shift+backspace", requestDiscard, { enabled: global, preventDefault: true })

  const restoreFocus = (event: Event) => {
    event.preventDefault()
    if (!latest.current.editing) return focusCell(cursor)
    // closing the menu steals focus from an editor opened by its Edit item
    root.current?.querySelector<HTMLElement>("textarea, input, [data-slot=select-trigger]")?.focus()
  }

  const menuTarget = (event: MouseEvent) => {
    const el = (event.target as HTMLElement).closest<HTMLElement>("[data-row-id]")
    if (!el) return event.stopPropagation()
    const id = el.dataset.rowId!
    const col = el.dataset.col ?? columns[0]?.key
    if (!col) return
    setActive({ id, col })
    if (!selectedIds.includes(id)) {
      anchor.current = id
      setSelected([id])
    }
  }

  const gridWidth = GUTTER + columns.reduce((sum, c) => sum + (c.width ?? DEFAULT_WIDTH), 0)
  const header = (
    <TableHeader>
      <TableRow className="hover:bg-transparent">
        <TableHead className="sticky top-0 z-10 h-8 bg-background px-0 text-center text-xs font-normal text-muted-foreground shadow-[inset_0_-1px_0_var(--border)]">
          #
        </TableHead>
        {columns.map((column) => (
          <TableHead
            key={column.key}
            className="sticky top-0 z-10 h-8 bg-background px-2 text-xs shadow-[inset_0_-1px_0_var(--border)]"
          >
            {column.label}
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  )
  const colgroup = (
    <colgroup>
      <col style={{ width: GUTTER }} />
      {columns.map((column) => (
        <col key={column.key} style={{ width: column.width ?? DEFAULT_WIDTH }} />
      ))}
    </colgroup>
  )
  const tableClass = "table-fixed border-collapse text-sm"

  let body
  if (store.status === "error") {
    body = (
      <ErrorState
        error={store.error ?? new Error("Could not load rows")}
        onRetry={() => window.location.reload()}
      />
    )
  } else if (store.status === "loading" || rows.length === 0) {
    body = (
      <>
        <div className="overflow-hidden border-b">
          <table className={tableClass} style={{ width: gridWidth }}>
            {colgroup}
            {header}
          </table>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {store.status === "loading" ? (
            <LoadingState label="Loading rows" />
          ) : (
            <EmptyState
              title="No rows yet"
              description="Add a row to start a batch of changes."
              action={
                <Button size="sm" onClick={addRow}>
                  <PlusIcon /> Add row
                </Button>
              }
            />
          )}
        </div>
      </>
    )
  } else {
    body = (
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <div className="relative min-h-0 flex-1" onContextMenuCapture={menuTarget}>
            <ScrollArea className="h-full">
              <table
                role="grid"
                aria-label="Editable table"
                aria-rowcount={rows.length}
                className={tableClass}
                style={{ width: gridWidth }}
              >
                {colgroup}
                {header}
                <TableBody>
                  {rows.map((row, index) => (
                    <GridRow
                      key={row.item.id}
                      row={row}
                      index={index}
                      columns={columns}
                      selected={selectedIds.includes(row.item.id)}
                      cursor={cursor}
                      editing={editing}
                      onSelectRow={selectRow}
                      onSelectCell={selectCell}
                      onFocusCell={setActive}
                      onStartEdit={startEdit}
                      onDraft={(text) => (draft.current = text)}
                      onAccept={acceptEdit}
                      onNext={acceptAndNext}
                      onCancel={cancelEdit}
                    />
                  ))}
                </TableBody>
              </table>
              <ScrollBar orientation="horizontal" />
            </ScrollArea>
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent onCloseAutoFocus={restoreFocus}>
          <ContextMenuItem onSelect={() => startEdit(cursor)}>
            Edit <ContextMenuShortcut>Return</ContextMenuShortcut>
          </ContextMenuItem>
          <ContextMenuItem onSelect={duplicateSelected}>
            Duplicate <ContextMenuShortcut>⌘D</ContextMenuShortcut>
          </ContextMenuItem>
          <ContextMenuItem onSelect={setActiveEmpty}>Set empty</ContextMenuItem>
          <ContextMenuSeparator />
          <ContextMenuItem variant="destructive" onSelect={removeSelected}>
            Delete <ContextMenuShortcut>Delete</ContextMenuShortcut>
          </ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>
    )
  }

  const breakdown = [
    updateCells > 0 && `${updateCells} changed`,
    newCount > 0 && `${newCount} new`,
    removedCount > 0 && `${removedCount} removed`,
  ].filter(Boolean)

  return (
    <>
      <div ref={root} className="flex h-full min-h-0 flex-col bg-background text-foreground">
        <div role="toolbar" aria-label="Pending changes" className="flex items-center gap-1.5 border-b px-2 py-1.5">
          <Button variant="outline" size="sm" disabled={!hasPending} onClick={requestDiscard}>
            <XIcon /> Discard
          </Button>
          <Popover open={previewOpen && hasPending} onOpenChange={setPreviewOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" disabled={!hasPending}>
                <EyeIcon /> Preview
              </Button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              className="w-[min(30rem,calc(100vw-2rem))]"
              onCloseAutoFocus={restoreFocus}
            >
              <PendingPreview
                changes={changes}
                items={store.items}
                columns={columns}
                onCommit={() => void commit()}
                onDiscard={requestDiscard}
              />
            </PopoverContent>
          </Popover>
          <Button size="sm" disabled={!hasPending} onClick={requestCommit}>
            Commit <Kbd>⌘S</Kbd>
          </Button>
          <span role="status" className="ml-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            {committing ? (
              <>
                <Loader2Icon className="size-3.5 animate-spin" aria-hidden /> Committing…
              </>
            ) : (
              `${pending} pending`
            )}
          </span>
          <Button variant="ghost" size="sm" className="ml-auto" disabled={!idle} onClick={addRow}>
            <PlusIcon /> Add row
          </Button>
        </div>

        {body}

        <div className="flex items-center justify-between border-t px-3 py-1 text-xs text-muted-foreground">
          <span>
            {store.status === "loading"
              ? "Loading rows"
              : rows.length === 0
                ? "0 rows"
                : `${selectedIds.length} of ${rows.length} rows selected`}
          </span>
          <span>{breakdown.join(" · ")}</span>
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent
          showCloseButton={false}
          onOpenAutoFocus={(event) => {
            event.preventDefault()
            cancelButton.current?.focus()
          }}
          onCloseAutoFocus={restoreFocus}
        >
          <DialogHeader>
            <DialogTitle>Discard {pending} pending {pending === 1 ? "change" : "changes"}?</DialogTitle>
            <DialogDescription>This cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button ref={cancelButton} variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDiscard}>
              Discard
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function GridRow<T extends { id: string; title: string }>({
  row,
  index,
  columns,
  selected,
  cursor,
  editing,
  onSelectRow,
  onSelectCell,
  onFocusCell,
  onStartEdit,
  onDraft,
  onAccept,
  onNext,
  onCancel,
}: {
  row: StagedRow<T>
  index: number
  columns: StagedColumn<T>[]
  selected: boolean
  cursor: Cell | null
  editing: Cell | null
  onSelectRow(id: string, event: MouseEvent): void
  onSelectCell(cell: Cell): void
  onFocusCell(cell: Cell): void
  onStartEdit(cell: Cell): boolean
  onDraft(text: string): void
  onAccept(cell: Cell, text: string): void
  onNext(cell: Cell, text: string): void
  onCancel(cell: Cell): void
}) {
  const { item, state } = row
  const removed = state === "removed"

  return (
    <TableRow
      aria-selected={selected}
      className="h-[30px] even:bg-muted/30"
    >
      <TableCell
        data-row-id={item.id}
        className={cn(
          "p-0 text-center text-xs text-muted-foreground",
          selected && "shadow-[inset_3px_0_0_var(--mini-accent)]"
        )}
      >
        <button
          type="button"
          tabIndex={-1}
          aria-label={`Select row ${index + 1}`}
          className="h-[30px] w-full cursor-default tabular-nums"
          onClick={(event) => onSelectRow(item.id, event)}
        >
          {index + 1}
        </button>
      </TableCell>
      {columns.map((column) => {
        const cell: Cell = { id: item.id, col: column.key }
        const isActive = sameCell(cursor, cell)
        const isEditing = sameCell(editing, cell) && !removed && !column.readOnly
        const text = textOf(item[column.key])
        const tint =
          state === "new"
            ? NEW_TINT
            : removed
              ? REMOVED_TINT
              : row.changedKeys.has(column.key)
                ? "bg-(--mini-pending)"
                : selected
                  ? "bg-accent"
                  : ""
        return (
          <StagedCell
            key={column.key}
            cell={cell}
            tip={text}
            isActive={isActive}
            isEditing={isEditing}
            className={cn(tint, removed && "text-muted-foreground line-through")}
            onSelect={() => onSelectCell(cell)}
            onFocusCell={() => onFocusCell(cell)}
            onStartEdit={() => onStartEdit(cell)}
          >
            {isEditing ? (
              <div className="p-0.5">
                <CellEditor
                  key={`${cell.id}:${cell.col}`}
                  type={column.type ?? "text"}
                  options={column.options ?? []}
                  label={column.label}
                  value={text}
                  onDraft={onDraft}
                  onAccept={(next) => onAccept(cell, next)}
                  onNext={(next) => onNext(cell, next)}
                  onCancel={() => onCancel(cell)}
                />
              </div>
            ) : (
              <div
                data-cell-text
                className={cn(
                  "truncate px-2 leading-[30px]",
                  column.readOnly && "text-muted-foreground",
                  column.type === "number" && "tabular-nums"
                )}
              >
                {text === "" && state === "new" && column.placeholder ? (
                  <span className="text-muted-foreground/70 italic">{column.placeholder}</span>
                ) : (
                  text
                )}
              </div>
            )}
          </StagedCell>
        )
      })}
    </TableRow>
  )
}

function StagedCell({
  cell,
  tip,
  isActive,
  isEditing,
  className,
  onSelect,
  onFocusCell,
  onStartEdit,
  children,
}: {
  cell: Cell
  tip: string
  isActive: boolean
  isEditing: boolean
  className?: string
  onSelect(): void
  onFocusCell(): void
  onStartEdit(): void
  children: React.ReactNode
}) {
  const [hovered, setHovered] = useState(false)
  const [truncated, setTruncated] = useState(false)
  const measure = (el: HTMLElement) => {
    const inner = el.querySelector<HTMLElement>("[data-cell-text]")
    setTruncated(!!inner && inner.scrollWidth > inner.clientWidth)
  }

  return (
    <Tooltip open={hovered && truncated && !isEditing} onOpenChange={setHovered}>
      <TooltipTrigger asChild>
        <TableCell
          role="gridcell"
          data-row-id={cell.id}
          data-col={cell.col}
          tabIndex={isActive ? 0 : -1}
          className={cn(
            "overflow-hidden p-0 outline-none",
            "focus:outline-2 focus:-outline-offset-2 focus:outline-(--mini-accent)",
            className
          )}
          onPointerEnter={(event) => measure(event.currentTarget)}
          onFocus={(event) => {
            measure(event.currentTarget)
            onFocusCell()
          }}
          onClick={onSelect}
          onDoubleClick={onStartEdit}
        >
          {children}
        </TableCell>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm break-words">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}
