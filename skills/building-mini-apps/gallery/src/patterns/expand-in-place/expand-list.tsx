import { useEffect, useRef, useState, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { AlignLeftIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Kbd } from "@/components/ui/kbd"
import { useCollection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"
import { ExpandCard } from "./expand-card"
import type { ExpandField, ExpandItem } from "./types"

function toError(cause: unknown): Error {
  return cause instanceof Error ? cause : new Error(String(cause))
}

function defaultOnError(error: Error) {
  toast.error("Could not save changes", { description: error.message })
}

function ExpandRow<T extends ExpandItem>({
  item,
  fields,
  selected,
  tabbable,
  renderRow,
  registerButton,
  onSelect,
  onOpen,
  onToggleDone,
}: {
  item: T
  fields: ExpandField<T>[]
  selected: boolean
  tabbable: boolean
  renderRow?: (item: T) => ReactNode
  registerButton(element: HTMLButtonElement | null): void
  onSelect(): void
  onOpen(): void
  onToggleDone(done: boolean): void
}) {
  const setFields = fields.filter((field) => field.isSet(item))
  const name = item.title || "Untitled"
  return (
    <li
      data-item-id={item.id}
      data-mini="row"
      data-active={selected ? "" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 py-1 hover:bg-muted/60",
        selected && "bg-muted"
      )}
    >
      <Checkbox
        aria-label={`Mark "${name}" done`}
        checked={item.done === true}
        onCheckedChange={(checked) => onToggleDone(checked === true)}
      />
      <button
        ref={registerButton}
        type="button"
        data-expand-row
        tabIndex={tabbable ? 0 : -1}
        aria-current={selected ? "true" : undefined}
        aria-expanded={false}
        onFocus={onSelect}
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-sm text-left text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span
          className={cn(
            "min-w-0 flex-1 truncate",
            item.done && "text-muted-foreground line-through",
            !item.title && "text-muted-foreground italic"
          )}
        >
          {renderRow ? renderRow(item) : name}
        </span>
        {item.notes || setFields.length > 0 ? (
          <span className="flex shrink-0 items-center gap-1.5 text-muted-foreground [&_svg]:size-3.5">
            {item.notes ? <AlignLeftIcon aria-hidden /> : null}
            {setFields.map((field) => (
              <span key={field.key} aria-hidden>
                {field.glyph}
              </span>
            ))}
            <span className="sr-only">
              {[item.notes ? "Has notes" : null, ...setFields.map((field) => field.label)]
                .filter(Boolean)
                .join(", ")}
            </span>
          </span>
        ) : null}
      </button>
    </li>
  )
}

/**
 * Single-column list whose rows open in place into an `ExpandCard`, one at a
 * time. Owns row selection, which card is open and the list hotkeys, and saves
 * every edit through the base collection store as it is typed.
 */
export function ExpandList<T extends ExpandItem>({
  collection,
  seed,
  fields,
  newItem,
  renderRow,
  emptyTitle = "Nothing here yet",
  onError = defaultOnError,
}: {
  collection: string
  seed?: T[]
  fields: ExpandField<T>[]
  newItem(): T
  renderRow?: (item: T) => ReactNode
  emptyTitle?: string
  onError?: (error: Error) => void
}) {
  const { items, status, error, add, update, remove } = useCollection<T>(collection, seed)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [freshId, setFreshId] = useState<string | null>(null)
  const [failedSaves, setFailedSaves] = useState(0)
  const rowButtons = useRef(new Map<string, HTMLButtonElement>())
  const refocusId = useRef<string | null>(null)
  // the store publishes an edit only after its write lands, so props lag what the user already typed
  const typedTitles = useRef(new Map<string, string>())

  const ready = status === "ready"
  const selected = items.some((item) => item.id === selectedId) ? selectedId : null
  const openItem = items.find((item) => item.id === openId)

  function guard(write: Promise<void>) {
    write.catch((cause: unknown) => {
      onError(toError(cause))
      setFailedSaves((count) => count + 1)
    })
  }

  /** Closes the open card, dropping a never-titled new item, and returns the row that should take focus. */
  function closeOpenCard(): string | null {
    if (openId === null) return null
    const closing = items.find((item) => item.id === openId)
    const title = typedTitles.current.get(openId) ?? closing?.title ?? ""
    typedTitles.current.delete(openId)
    setOpenId(null)
    if (openId !== freshId) return openId
    setFreshId(null)
    if (title.trim() !== "") return openId
    // the remove queues behind any title write still in flight, so it lands last
    guard(remove(openId))
    if (!closing) return items[items.length - 1]?.id ?? null
    const index = items.indexOf(closing)
    return (items[index - 1] ?? items[index + 1])?.id ?? null
  }

  function saveEdit(id: string, patch: Partial<T>) {
    if (typeof patch.title === "string") typedTitles.current.set(id, patch.title)
    guard(update(id, patch))
  }

  function collapse() {
    const focusId = closeOpenCard()
    refocusId.current = focusId
    setSelectedId(focusId)
  }

  function openRow(id: string) {
    if (id === openId) return
    closeOpenCard()
    refocusId.current = null
    setSelectedId(id)
    setOpenId(id)
  }

  function addItem() {
    if (!ready) return
    const created = newItem()
    closeOpenCard()
    refocusId.current = null
    typedTitles.current.set(created.id, created.title)
    setFreshId(created.id)
    setSelectedId(created.id)
    setOpenId(created.id)
    add(created).catch((cause: unknown) => {
      onError(toError(cause))
      typedTitles.current.delete(created.id)
      setOpenId(null)
      setFreshId(null)
    })
  }

  function moveSelection(step: 1 | -1) {
    if (items.length === 0) return
    const index = selected === null ? -1 : items.findIndex((item) => item.id === selected)
    const target =
      index === -1
        ? items[step === 1 ? 0 : items.length - 1]
        : items[Math.min(items.length - 1, Math.max(0, index + step))]
    setSelectedId(target.id)
    rowButtons.current.get(target.id)?.focus()
  }

  const latest = useRef({ collapse, openRow, addItem, moveSelection })
  useEffect(() => {
    latest.current = { collapse, openRow, addItem, moveSelection }
  })

  useEffect(() => {
    if (openId !== null || refocusId.current === null) return
    const button = rowButtons.current.get(refocusId.current)
    if (!button) return
    button.focus()
    refocusId.current = null
  }, [openId, items])

  const browsing = ready && openId === null
  useHotkeys("down", () => latest.current.moveSelection(1), { enabled: browsing, preventDefault: true })
  useHotkeys("up", () => latest.current.moveSelection(-1), { enabled: browsing, preventDefault: true })
  useHotkeys(
    "enter",
    (event) => {
      // a focused row button opens itself through its click
      if ((event.target as Element).closest("button, a, [role=checkbox]")) return
      if (selected !== null) latest.current.openRow(selected)
    },
    { enabled: browsing && selected !== null }
  )
  useHotkeys(
    "n",
    (event) => {
      if ((event.target as Element).closest("[role=dialog]")) return
      latest.current.addItem()
    },
    { enabled: ready, preventDefault: true }
  )

  let body: ReactNode
  if (status === "loading") {
    body = <LoadingState label="Loading items" />
  } else if (status === "error") {
    body = (
      <ErrorState
        error={error ?? new Error("Could not load items")}
        onRetry={() => window.location.reload()}
      />
    )
  } else if (items.length === 0 && openId === null) {
    body = (
      <EmptyState
        title={emptyTitle}
        description="Press N to add an item"
        action={
          <Button size="sm" onClick={addItem}>
            <PlusIcon /> Add item
          </Button>
        }
      />
    )
  } else {
    const firstId = items[0]?.id
    body = (
      <ul aria-label="Items" className="flex flex-col">
        {items.map((item) =>
          item.id === openItem?.id ? (
            <li key={item.id} data-item-id={item.id}>
              <ExpandCard
                key={failedSaves}
                item={item}
                fields={fields}
                onChange={(patch) => saveEdit(item.id, patch)}
                onClose={() => latest.current.collapse()}
              />
            </li>
          ) : (
            <ExpandRow
              key={item.id}
              item={item}
              fields={fields}
              selected={item.id === selected}
              tabbable={selected === null ? item.id === firstId : item.id === selected}
              renderRow={renderRow}
              registerButton={(element) => {
                if (element) rowButtons.current.set(item.id, element)
                else rowButtons.current.delete(item.id)
              }}
              onSelect={() => setSelectedId(item.id)}
              onOpen={() => openRow(item.id)}
              onToggleDone={(done) => guard(update(item.id, { done } as Partial<T>))}
            />
          )
        )}
      </ul>
    )
  }

  return (
    <div className="flex min-h-full flex-col">
      <div className="mx-auto w-full max-w-[820px] flex-1 px-6 py-4">{body}</div>
      <div className="sticky bottom-0 border-t bg-background/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[820px] items-center justify-between px-6 py-2">
          {openId === null ? (
            <Button variant="ghost" size="sm" disabled={!ready} onClick={addItem}>
              <PlusIcon /> New item <Kbd>N</Kbd>
            </Button>
          ) : (
            <Button variant="ghost" size="sm" onClick={collapse}>
              Done <Kbd>⌘↵</Kbd>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
