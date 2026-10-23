import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { Loader2Icon, MoreHorizontalIcon, SearchIcon } from "lucide-react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { ActionPanel } from "./action-panel"
import { ShortcutKeys } from "./shortcut-keys"
import type { ActionPaletteProps, PaletteAction, PaletteItem } from "./types"

const RENDER_CAP = 200
const CREATE_ID = "__create__"

type Group<T> = { heading?: string; items: T[] }

function flattenActions<T extends PaletteItem>(actions: PaletteAction<T>[]): PaletteAction<T>[] {
  return actions.flatMap((action) => [action, ...flattenActions(action.children ?? [])])
}

function pathTo<T extends PaletteItem>(
  actions: PaletteAction<T>[],
  id: string
): PaletteAction<T>[] | undefined {
  for (const action of actions) {
    if (action.id === id) return [action]
    const below = pathTo(action.children ?? [], id)
    if (below) return [action, ...below]
  }
  return undefined
}

function isTextField(element: EventTarget | null): boolean {
  return (
    element instanceof HTMLElement &&
    (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName))
  )
}

/**
 * Searchable list with one selected row and a ⌘K panel of actions for it.
 * The search input keeps focus; the selection moves through aria-activedescendant.
 */
export function ActionPalette<T extends PaletteItem>({
  items,
  status = "ready",
  error,
  onRetry,
  getActions,
  getSubtitle,
  getMeta,
  getSearchText,
  getSection,
  onCreate,
  placeholder = "Search…",
  footerLabel,
  emptyState = { title: "Nothing here yet", description: "Add the first item to see it here." },
}: ActionPaletteProps<T>) {
  const baseId = useId()
  const [query, setQuery] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [panel, setPanel] = useState<{
    itemId: string
    path: PaletteAction<T>[]
    nonce: number
  } | null>(null)
  const [pending, setPending] = useState<string[]>([])
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const trimmed = query.trim()
  const filtering = trimmed.length > 0
  const ready = status === "ready"

  const matches = filtering ? rank(items, trimmed, getSearchText) : groupBySection(items, getSection)
  const visible = matches.slice(0, RENDER_CAP)
  const showCreate = ready && Boolean(onCreate) && filtering && matches.length === 0
  const rowIds = ready ? (showCreate ? [CREATE_ID] : visible.map((item) => item.id)) : []
  const activeId = selectedId !== null && rowIds.includes(selectedId) ? selectedId : rowIds[0]
  const selectedItem = visible.find((item) => item.id === activeId)
  const actions = selectedItem ? getActions(selectedItem) : []
  const canOpen = ready && actions.length > 0
  const panelOpen = canOpen && panel?.itemId === activeId
  const optionId = (id: string) => `${baseId}-${id}`

  useEffect(() => {
    if (activeId !== undefined) {
      document.getElementById(`${baseId}-${activeId}`)?.scrollIntoView({ block: "nearest" })
    }
  }, [activeId, baseId])

  const closePanel = useCallback(() => {
    setPanel(null)
    inputRef.current?.focus()
    // a click outside moves focus to the body after this handler returns
    setTimeout(() => {
      if (document.activeElement === document.body) inputRef.current?.focus()
    }, 0)
  }, [])

  async function run(item: T, action: PaletteAction<T>) {
    if (action.children) {
      const path = pathTo(getActions(item), action.id) ?? [action]
      setSelectedId(item.id)
      setPanel((open) => ({ itemId: item.id, path, nonce: (open?.nonce ?? 0) + 1 }))
      return
    }
    closePanel()
    setSelectedId(item.id)
    if (!action.run) return
    const label = action.pending
    if (label) setPending((labels) => [...labels, label])
    try {
      await action.run(item)
      if (action.successMessage) toast.success(action.successMessage)
    } catch (cause) {
      toast.error(cause instanceof Error && cause.message ? cause.message : `${action.title} failed`)
    } finally {
      if (label) {
        setPending((labels) => {
          const index = labels.indexOf(label)
          return index < 0 ? labels : labels.filter((_, i) => i !== index)
        })
      }
    }
  }

  function runAt(index: number) {
    if (!selectedItem) return
    const action = actions[index]
    if (action && (action.run || action.children)) void run(selectedItem, action)
  }

  function move(delta: number) {
    if (rowIds.length === 0 || activeId === undefined) return
    const next = Math.min(rowIds.length - 1, Math.max(0, rowIds.indexOf(activeId) + delta))
    setSelectedId(rowIds[next])
  }

  function changeQuery(value: string) {
    setQuery(value)
    setSelectedId(null)
  }

  function togglePanel() {
    if (panelOpen) closePanel()
    else if (canOpen && activeId !== undefined) setPanel({ itemId: activeId, path: [], nonce: 0 })
  }

  function toggleRowPanel(item: T) {
    if (panelOpen && activeId === item.id) {
      closePanel()
      return
    }
    setSelectedId(item.id)
    setPanel({ itemId: item.id, path: [], nonce: 0 })
  }

  useHotkeys("mod+k", togglePanel, { enableOnFormTags: true, preventDefault: true })

  const searchHotkeyRef = useHotkeys<HTMLInputElement>(
    "enter, mod+enter, up, down, escape",
    (_event, handler) => {
      switch (handler.hotkey) {
        case "enter":
          if (showCreate) onCreate?.(trimmed)
          else runAt(0)
          break
        case "mod+enter":
          runAt(1)
          break
        case "up":
          move(-1)
          break
        case "down":
          move(1)
          break
        case "escape":
          if (query) changeQuery("")
          break
      }
    },
    { enableOnFormTags: true, preventDefault: true }
  )

  const setInputRef = useCallback(
    (element: HTMLInputElement | null) => {
      inputRef.current = element
      return searchHotkeyRef(element)
    },
    [searchHotkeyRef]
  )

  useHotkeys("slash", () => inputRef.current?.focus(), { preventDefault: true })

  const chords = new Map<string, PaletteAction<T>>()
  for (const action of flattenActions(actions)) {
    const key = action.shortcut?.toLowerCase()
    if (key && !chords.has(key)) chords.set(key, action)
  }
  useHotkeys(
    [...chords.keys()],
    (_event, handler) => {
      const action = chords.get(handler.hotkey)
      if (selectedItem && action) void run(selectedItem, action)
    },
    {
      enabled: chords.size > 0,
      enableOnFormTags: true,
      preventDefault: true,
      ignoreEventWhen: (event) =>
        isTextField(event.target) && !rootRef.current?.contains(event.target as Node),
    }
  )

  const sections = toGroups(visible, filtering, getSection)
  const primary = showCreate ? `Create “${trimmed}”` : actions[0]?.title

  let listArea: ReactNode
  if (status === "loading") {
    listArea = <LoadingState label="Loading items" />
  } else if (status === "error") {
    listArea = <ErrorState error={error ?? new Error("Could not load items")} onRetry={onRetry} />
  } else {
    listArea = (
      <>
        {items.length === 0 ? (
          <EmptyState
            title={emptyState.title}
            description={emptyState.description}
            action={emptyState.action}
          />
        ) : null}
        <div
          id={`${baseId}-list`}
          role="listbox"
          aria-label="Results"
          className={cn(rowIds.length === 0 && "hidden")}
        >
          {showCreate ? (
            <Row
              id={optionId(CREATE_ID)}
              selected={activeId === CREATE_ID}
              onSelect={() => setSelectedId(CREATE_ID)}
              title={`Create “${trimmed}”`}
            />
          ) : null}
          {sections.map((group, index) => (
            <div
              key={group.heading ?? `group-${index}`}
              role="group"
              aria-label={group.heading}
            >
              {group.heading ? (
                <div
                  aria-hidden
                  className="px-3 pt-2 pb-1 text-xs font-medium text-muted-foreground"
                >
                  {group.heading}
                </div>
              ) : null}
              {group.items.map((item) => (
                <Row
                  key={item.id}
                  id={optionId(item.id)}
                  selected={activeId === item.id}
                  onSelect={() => setSelectedId(item.id)}
                  title={item.title}
                  subtitle={getSubtitle?.(item)}
                  meta={getMeta?.(item)}
                  actionsLabel={getActions(item).length > 0 ? `Actions for ${item.title}` : undefined}
                  actionsOpen={panelOpen && activeId === item.id}
                  onToggleActions={() => toggleRowPanel(item)}
                />
              ))}
            </div>
          ))}
        </div>
        {items.length > 0 && matches.length === 0 ? (
          <p role="status" className="px-3 py-4 text-center text-sm text-muted-foreground">
            No results for “{trimmed}”
          </p>
        ) : null}
        {matches.length > RENDER_CAP ? (
          <p className="px-3 py-2 text-center text-xs text-muted-foreground">
            Showing {RENDER_CAP} of {matches.length}. Keep typing to narrow
          </p>
        ) : null}
      </>
    )
  }

  return (
    <div
      ref={rootRef}
      className="relative flex h-full min-h-80 flex-col overflow-hidden rounded-lg border bg-card text-card-foreground"
    >
      <div className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
        <SearchIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <Input
          ref={setInputRef}
          autoFocus
          role="combobox"
          aria-label={placeholder.replace(/…$/, "")}
          aria-expanded={rowIds.length > 0}
          aria-controls={`${baseId}-list`}
          aria-activedescendant={activeId === undefined ? undefined : optionId(activeId)}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={query}
          onChange={(event) => changeQuery(event.target.value)}
          className="h-9 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
      </div>

      <ScrollArea
        className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:block!"
        onMouseDown={(event) => {
          if (event.target !== inputRef.current) event.preventDefault()
        }}
      >
        {listArea}
      </ScrollArea>

      <footer className="flex h-10 shrink-0 items-center justify-between gap-3 border-t px-3 text-xs text-muted-foreground">
        <div className="flex min-w-0 items-center gap-2" role="status">
          {pending.length > 0 ? (
            <>
              <Loader2Icon className="size-3.5 shrink-0 animate-spin" aria-hidden />
              <span className="truncate">{pending[pending.length - 1]}</span>
            </>
          ) : footerLabel ? (
            <span className="truncate">{footerLabel}</span>
          ) : null}
        </div>
        {ready && primary ? (
          <div className="flex shrink-0 items-center gap-3">
            <span className="flex items-center gap-1.5">
              <span className="max-w-40 truncate">{primary}</span>
              <ShortcutKeys shortcut="enter" />
            </span>
            {canOpen ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    data-action-palette-toggle
                    aria-expanded={panelOpen}
                    aria-label="Actions"
                    onClick={togglePanel}
                    className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
                  >
                    Actions
                    <ShortcutKeys shortcut="mod+k" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Show actions for the selected row</TooltipContent>
              </Tooltip>
            ) : null}
          </div>
        ) : null}
      </footer>

      {panelOpen && selectedItem ? (
        <ActionPanel
          key={`${selectedItem.id}:${panel?.nonce ?? 0}`}
          item={selectedItem}
          actions={actions}
          initialPath={panel?.path}
          onClose={closePanel}
          onRun={(action) => void run(selectedItem, action)}
        />
      ) : null}
    </div>
  )
}

function Row({
  id,
  selected,
  onSelect,
  title,
  subtitle,
  meta,
  actionsLabel,
  actionsOpen,
  onToggleActions,
}: {
  id: string
  selected: boolean
  onSelect: () => void
  title: string
  subtitle?: string
  meta?: string
  actionsLabel?: string
  actionsOpen?: boolean
  onToggleActions?: () => void
}) {
  return (
    <div
      role="none"
      className={cn(
        "group/row mx-1 flex h-11 items-center rounded-md text-sm",
        selected && "bg-muted"
      )}
    >
      <div
        id={id}
        role="option"
        aria-selected={selected}
        onClick={onSelect}
        className="flex h-full min-w-0 flex-1 items-center gap-3 pl-3"
      >
        <span className="max-w-[65%] min-w-0 shrink-0 truncate font-medium" title={title}>
          {title}
        </span>
        {subtitle ? (
          <span className="min-w-0 flex-1 truncate text-muted-foreground" title={subtitle}>
            {subtitle}
          </span>
        ) : (
          <span className="flex-1" />
        )}
        {meta ? (
          <Badge variant="secondary" className="shrink-0">
            {meta}
          </Badge>
        ) : null}
      </div>
      {actionsLabel ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          data-action-palette-toggle
          aria-label={actionsLabel}
          aria-expanded={actionsOpen}
          tabIndex={selected ? 0 : -1}
          onClick={onToggleActions}
          className={cn(
            "mx-1.5 text-muted-foreground",
            !selected && "opacity-0 group-focus-within/row:opacity-100 group-hover/row:opacity-100"
          )}
        >
          <MoreHorizontalIcon aria-hidden />
        </Button>
      ) : (
        <span className="w-3 shrink-0" />
      )}
    </div>
  )
}

function rank<T extends PaletteItem>(
  items: T[],
  query: string,
  getSearchText?: (item: T) => string
): T[] {
  const needle = query.toLowerCase()
  const scored: { item: T; score: number }[] = []
  for (const item of items) {
    const title = item.title.toLowerCase()
    if (title.startsWith(needle)) scored.push({ item, score: 0 })
    else if (title.includes(needle)) scored.push({ item, score: 1 })
    else if (getSearchText?.(item).toLowerCase().includes(needle)) scored.push({ item, score: 2 })
  }
  return scored.sort((a, b) => a.score - b.score).map(({ item }) => item)
}

function groupBySection<T extends PaletteItem>(
  items: T[],
  getSection?: (item: T) => string | undefined
): T[] {
  if (!getSection) return items
  return toGroups(items, false, getSection).flatMap((group) => group.items)
}

function toGroups<T extends PaletteItem>(
  items: T[],
  filtering: boolean,
  getSection?: (item: T) => string | undefined
): Group<T>[] {
  if (filtering || !getSection) return [{ items }]
  const groups = new Map<string | undefined, Group<T>>()
  for (const item of items) {
    const heading = getSection(item)
    const group = groups.get(heading) ?? { heading, items: [] }
    group.items.push(item)
    groups.set(heading, group)
  }
  return [...groups.values()]
}
