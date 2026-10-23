import { useEffect, useRef, useState, type ReactNode } from "react"
import { PlusIcon } from "lucide-react"
import { useHotkeys } from "react-hotkeys-hook"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Tabs, TabsContent } from "@/components/ui/tabs"

import { applyView } from "./apply-view"
import { addMonths, fromIso, isIsoDate, startOfMonth, toIso } from "./dates"
import { FilterChips } from "./filter-chips"
import {
  defaultRule,
  pickField,
  textOf,
  valueOf,
  withTitle,
  type Rec,
} from "./fields"
import { buildColumns } from "./grouping"
import { BoardLayout } from "./board-layout"
import { CalendarLayout } from "./calendar-layout"
import { ListLayout } from "./list-layout"
import type { CreateDefaults, LayoutProps } from "./layout-shared"
import { TableLayout } from "./table-layout"
import { navIds, nextRecord, type NavContext } from "./navigation"
import { RecordPanel } from "./record-panel"
import { TabStrip } from "./tab-strip"
import { Toolbar } from "./toolbar"
import type { FieldDef, Layout, ViewConfig } from "./types"
import { useActiveViewId, useDrafts, useViews } from "./use-views"
import { effectiveView, savePatch } from "./view-draft"

export interface ViewSwitcherProps<T extends { id: string; title: string }> {
  items: T[]
  /** Fields beyond id and title, which are always shown. */
  fields: FieldDef<T>[]
  /** Views persist through `useCollection<ViewConfig>(`${storageKey}-views`, defaultViews)`. */
  storageKey: string
  /** Defaults to one table view named "All". */
  defaultViews?: ViewConfig[]
  /** Singular name used in "New task" and the empty states. Defaults to "record". */
  noun?: string
  /** Status of `items`. */
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  /** Defaults carry the column's group value or the day's date. */
  onCreate?: (defaults: Partial<T>) => void
  /** Panel edits; omit to make the panel read-only. */
  onUpdate?: (id: string, patch: Partial<T>) => void
  /** Shows a Delete button with a confirm dialog. */
  onDelete?: (id: string) => void
  /** Replaces the default property list in the panel. */
  renderPanel?: (item: T, ctx: { close: () => void }) => ReactNode
  /** Controlled mode for the active view. */
  activeViewId?: string
  onActiveViewChange?: (id: string) => void
  /**
   * Off by default. On, query, sort and filters become a per-view draft: a dot
   * marks the view and Save, Save as new view and Reset appear until it is saved.
   */
  trackUnsaved?: boolean
  /** Called after a successful write; only with `trackUnsaved`. */
  onViewSaved?: (view: ViewConfig, how: "save" | "save-as-new") => void
}

const LAYOUT_NAMES: Record<Layout, string> = {
  table: "Table",
  board: "Board",
  list: "List",
  calendar: "Calendar",
}

const OVERLAYS = [
  '[role="dialog"][data-state="open"]',
  '[role="menu"][data-state="open"]',
  '[role="listbox"][data-state="open"]',
].join(",")

function overlayOpen(): boolean {
  return document.querySelector(OVERLAYS) !== null
}

function elementOf(event: KeyboardEvent): HTMLElement | null {
  return event.target instanceof HTMLElement ? event.target : null
}

function plural(noun: string, count: number) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`
}

/**
 * One set of records shown through named view tabs (table, board, list,
 * calendar), each keeping its own filter and sort, with a record opening in a
 * docked side panel. The host owns the records; views are stored here.
 */
export function ViewSwitcher<T extends { id: string; title: string }>(
  props: ViewSwitcherProps<T>
) {
  const {
    items,
    fields,
    storageKey,
    noun = "record",
    status = "ready",
    error,
    onRetry,
    onCreate,
    onUpdate,
    onDelete,
    renderPanel,
    trackUnsaved: tracking = false,
  } = props

  const defs = withTitle(fields)
  const viewsApi = useViews(storageKey, props.defaultViews)
  const { views } = viewsApi
  const [saved, setActive] = useActiveViewId(
    storageKey,
    views,
    props.activeViewId,
    props.onActiveViewChange
  )
  const draftsApi = useDrafts(views)
  const viewFor = (v: ViewConfig) =>
    tracking ? effectiveView(v, draftsApi.drafts[v.id]) : v
  const view = viewFor(saved)

  const [sharedQuery, setSharedQuery] = useState("")
  const query = tracking ? (view.query ?? "") : sharedQuery
  function setQuery(next: string) {
    if (tracking) draftsApi.patch(saved.id, { query: next })
    else setSharedQuery(next)
  }
  const [activeRecordId, setActiveRecordId] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [filterOpen, setFilterOpen] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)
  const [month, setMonth] = useState(() => startOfMonth(new Date()))

  const contentRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const openerRef = useRef<string | null>(null)
  const focusRequest = useRef<string | null>(null)
  const pendingCreate = useRef<Set<string> | null>(null)
  const overlayAtEscape = useRef(false)

  const loading = status === "loading" || viewsApi.loading
  const ready = status === "ready" && !viewsApi.loading
  const results = applyView(items, view, fields, query)

  const groupField =
    view.layout === "board"
      ? pickField(defs, view.groupBy, "select")
      : undefined
  const dateField =
    view.layout === "calendar"
      ? pickField(defs, view.dateField, "date")
      : undefined
  const columns = groupField ? buildColumns(results, groupField) : []
  const dated = dateField
    ? results
        .filter((r) => isIsoDate(valueOf(r, dateField.key)))
        .sort((a, b) =>
          textOf(valueOf(a, dateField.key)).localeCompare(
            textOf(valueOf(b, dateField.key))
          )
        )
    : []
  const undated = dateField ? results.filter((r) => !dated.includes(r)) : []
  const nav: NavContext = { layout: view.layout, results, columns, dated }
  const ids = navIds(nav)
  const activeId =
    activeRecordId !== null && ids.includes(activeRecordId)
      ? activeRecordId
      : null
  const tabStopId = activeId ?? ids[0] ?? null

  const panelItem =
    ready && openId !== null ? items.find((i) => i.id === openId) : undefined

  function findRecord(id: string): HTMLElement | null {
    return (
      contentRef.current?.querySelector<HTMLElement>(
        `[data-record-id="${CSS.escape(id)}"]`
      ) ?? null
    )
  }

  function openRecord(id: string) {
    openerRef.current = id
    setActiveRecordId(id)
    setOpenId(id)
  }

  function closePanel(restoreFocus: boolean) {
    const focused = document.activeElement
    // a blur commits a half-typed property edit before the panel unmounts
    if (focused instanceof HTMLElement && panelRef.current?.contains(focused))
      focused.blur()
    setOpenId(null)
    if (!restoreFocus) return
    const opener = openerRef.current
    requestAnimationFrame(() =>
      ((opener ? findRecord(opener) : null) ?? contentRef.current)?.focus()
    )
  }

  function moveActive(id: string | null) {
    if (id === null) return
    focusRequest.current = id
    setActiveRecordId(id)
    if (view.layout === "calendar" && dateField) {
      const record = dated.find((r) => r.id === id)
      const value = record ? textOf(valueOf(record, dateField.key)) : ""
      if (isIsoDate(value)) setMonth(startOfMonth(fromIso(value)))
    }
  }

  function switchTo(target: ViewConfig) {
    if (target.id === view.id) return
    setActive(target.id)
    const next = viewFor(target)
    const kept = new Set(
      applyView(items, next, fields, tracking ? (next.query ?? "") : query).map(
        (i) => i.id
      )
    )
    if (openId !== null && !kept.has(openId)) closePanel(false)
    if (activeRecordId !== null && !kept.has(activeRecordId))
      setActiveRecordId(null)
  }

  function updateView(patch: Partial<Omit<ViewConfig, "id">>) {
    if (!tracking) {
      void viewsApi.update(view.id, patch)
      return
    }
    const { filters, sort, ...immediate } = patch
    if ("filters" in patch || "sort" in patch)
      draftsApi.patch(saved.id, {
        ...("filters" in patch ? { filters } : {}),
        ...("sort" in patch ? { sort } : {}),
      })
    if (Object.keys(immediate).length > 0)
      void viewsApi.update(saved.id, immediate)
  }

  async function saveView() {
    const draft = draftsApi.drafts[saved.id]
    if (!draft) return
    const merged = effectiveView(saved, draft)
    if (await viewsApi.update(saved.id, savePatch(merged))) {
      draftsApi.clear(saved.id, draft)
      props.onViewSaved?.(merged, "save")
    }
  }

  async function saveAsNewView(): Promise<boolean> {
    const merged = effectiveView(saved, draftsApi.drafts[saved.id])
    const next: ViewConfig = {
      ...merged,
      id: crypto.randomUUID(),
      name: `${saved.name} copy`,
      filters: merged.filters.map((r) => ({
        ...r,
        value: Array.isArray(r.value) ? [...r.value] : r.value,
      })),
      sort: merged.sort && { ...merged.sort },
      query: merged.query ? merged.query : undefined,
    }
    const added = await viewsApi.add(next)
    if (added) {
      draftsApi.clear(saved.id)
      switchTo(next)
      props.onViewSaved?.(next, "save-as-new")
    }
    return added
  }

  async function addView(layout: Layout): Promise<boolean> {
    const next: ViewConfig = {
      id: crypto.randomUUID(),
      name: LAYOUT_NAMES[layout],
      layout,
      filters: [],
      groupBy: pickField(defs, undefined, "select")?.key,
      dateField: pickField(defs, undefined, "date")?.key,
    }
    const added = await viewsApi.add(next)
    if (added) switchTo(next)
    return added
  }

  async function duplicateView(id: string): Promise<boolean> {
    const source = views.find((v) => v.id === id)
    if (!source) return false
    const next: ViewConfig = {
      ...source,
      id: crypto.randomUUID(),
      name: `${source.name} copy`,
      filters: source.filters.map((r) => ({
        ...r,
        value: Array.isArray(r.value) ? [...r.value] : r.value,
      })),
      sort: source.sort && { ...source.sort },
    }
    const added = await viewsApi.add(next)
    if (added) switchTo(next)
    return added
  }

  async function deleteView(id: string) {
    if (views.length <= 1) return
    const index = views.findIndex((v) => v.id === id)
    const neighbour = views[index + 1] ?? views[index - 1]
    if (await viewsApi.remove(id)) {
      draftsApi.clear(id)
      switchTo(neighbour)
    }
  }

  function requestCreate(defaults: CreateDefaults) {
    if (!onCreate) return
    const known = new Set(items.map((i) => i.id))
    pendingCreate.current = known
    // a create that never arrives must not adopt some later, unrelated record
    window.setTimeout(() => {
      if (pendingCreate.current === known) pendingCreate.current = null
    }, 3000)
    const clean = Object.fromEntries(
      Object.entries(defaults).filter(([, v]) => v !== undefined)
    )
    onCreate(clean as unknown as Partial<T>)
  }

  function createDefaults(): CreateDefaults {
    if (groupField) {
      const column =
        columns.find((c) => c.items.some((i) => i.id === activeId)) ??
        columns[0]
      return column ? { [groupField.key]: column.value || undefined } : {}
    }
    if (dateField) {
      const current = dated.find((r) => r.id === activeId)
      const value = current ? textOf(valueOf(current, dateField.key)) : ""
      const today = new Date()
      const sameMonth =
        today.getFullYear() === month.getFullYear() &&
        today.getMonth() === month.getMonth()
      return {
        [dateField.key]: isIsoDate(value)
          ? value
          : toIso(sameMonth ? today : month),
      }
    }
    return {}
  }

  function resetView() {
    draftsApi.clear(saved.id)
  }

  function clearFilters() {
    updateView({ filters: [] })
    setQuery("")
  }

  function handleDelete(id: string) {
    openerRef.current = null
    closePanel(true)
    onDelete?.(id)
  }

  useEffect(() => {
    const request = focusRequest.current
    if (request !== null && request === activeId) {
      focusRequest.current = null
      findRecord(request)?.focus()
    }
  })

  useEffect(() => {
    const waiting = pendingCreate.current
    if (!waiting) return
    const created = items.find((i) => !waiting.has(i.id))
    if (created) {
      openerRef.current = created.id
      setActiveRecordId(created.id)
      setOpenId(created.id)
      pendingCreate.current = null
    }
  }, [items])

  useEffect(() => {
    // Radix closes a popover on the capture phase, so by the time the Escape hotkey runs it is already gone
    const record = (e: KeyboardEvent) => {
      if (e.key === "Escape") overlayAtEscape.current = overlayOpen()
    }
    document.addEventListener("keydown", record, true)
    return () => document.removeEventListener("keydown", record, true)
  }, [])

  const anywhere = (e: KeyboardEvent) =>
    !overlayOpen() && !elementOf(e)?.closest('[role="combobox"]')
  const inContent = (e: KeyboardEvent) => {
    const target = elementOf(e)
    return (
      anywhere(e) &&
      target !== null &&
      (target === document.body ||
        contentRef.current?.contains(target) === true ||
        target.hasAttribute("data-panel-title"))
    )
  }
  const onRecord = (e: KeyboardEvent) => {
    const target = elementOf(e)
    return (
      anywhere(e) &&
      target !== null &&
      (target === document.body ||
        target === contentRef.current ||
        target.closest("[data-record-id]") !== null)
    )
  }
  const keys = { useKey: true }

  useHotkeys(
    "1,2,3,4,5,6,7,8,9",
    (e) => {
      const target = views[Number(e.key) - 1]
      if (!target) return
      e.preventDefault()
      switchTo(target)
    },
    { ...keys, enabled: anywhere }
  )
  useHotkeys(
    "[,]",
    (e) => {
      e.preventDefault()
      const index = views.findIndex((v) => v.id === view.id)
      const step = e.key === "]" ? 1 : -1
      switchTo(views[(index + step + views.length) % views.length])
    },
    { ...keys, enabled: anywhere }
  )
  useHotkeys(
    "up,down",
    (e) => {
      e.preventDefault()
      moveActive(nextRecord(nav, activeId, e.key === "ArrowUp" ? "up" : "down"))
    },
    { ...keys, enabled: (e) => ready && inContent(e) }
  )
  useHotkeys(
    "left,right",
    (e) => {
      e.preventDefault()
      moveActive(
        nextRecord(nav, activeId, e.key === "ArrowLeft" ? "left" : "right")
      )
    },
    {
      ...keys,
      enabled: (e) => ready && view.layout === "board" && inContent(e),
    }
  )
  useHotkeys(
    "enter",
    (e) => {
      const fromTarget = elementOf(e)
        ?.closest("[data-record-id]")
        ?.getAttribute("data-record-id")
      const id = fromTarget ?? activeId
      if (!id) return
      e.preventDefault()
      openRecord(id)
    },
    { ...keys, enabled: (e) => ready && onRecord(e) }
  )
  useHotkeys(
    "esc",
    () => {
      if (overlayAtEscape.current) return
      const search = searchRef.current
      if (search && document.activeElement === search) {
        if (query !== "") return setQuery("")
        search.blur()
      }
      if (panelItem) closePanel(true)
      else setActiveRecordId(null)
    },
    { ...keys, enableOnFormTags: true }
  )
  useHotkeys(
    "f",
    (e) => {
      e.preventDefault()
      setFilterOpen(true)
    },
    { ...keys, enabled: (e) => !loading && anywhere(e) }
  )
  useHotkeys(
    "s",
    (e) => {
      e.preventDefault()
      setSortOpen(true)
    },
    { ...keys, enabled: (e) => !loading && anywhere(e) }
  )
  useHotkeys(
    "/",
    (e) => {
      e.preventDefault()
      searchRef.current?.focus()
    },
    { ...keys, enabled: (e) => ready && items.length >= 3 && anywhere(e) }
  )
  useHotkeys(
    "n",
    (e) => {
      e.preventDefault()
      requestCreate(createDefaults())
    },
    { ...keys, enabled: (e) => ready && onCreate !== undefined && anywhere(e) }
  )
  useHotkeys(
    "t",
    (e) => {
      e.preventDefault()
      setMonth(startOfMonth(new Date()))
    },
    { ...keys, enabled: (e) => view.layout === "calendar" && anywhere(e) }
  )
  useHotkeys(
    "shift+left,shift+right",
    (e) => {
      e.preventDefault()
      setMonth((m) => addMonths(m, e.key === "ArrowRight" ? 1 : -1))
    },
    { ...keys, enabled: (e) => view.layout === "calendar" && anywhere(e) }
  )

  const layoutProps: LayoutProps = {
    items: results,
    fields: defs,
    view,
    noun,
    activeId,
    tabStopId,
    openId: panelItem ? openId : null,
    onOpen: openRecord,
    onActivate: setActiveRecordId,
    onCreate: onCreate ? requestCreate : undefined,
  }

  let content: ReactNode
  if (loading) {
    content = <LoadingState label={`Loading ${noun}s`} />
  } else if (status === "error") {
    content = (
      <ErrorState
        error={error ?? new Error(`Couldn't load the ${noun}s.`)}
        onRetry={onRetry}
      />
    )
  } else if (items.length === 0) {
    content = (
      <EmptyState
        title={`No ${noun}s yet`}
        description={
          onCreate
            ? `Create the first ${noun} to see it in every view.`
            : undefined
        }
        action={
          onCreate ? (
            <Button size="sm" onClick={() => requestCreate({})}>
              <PlusIcon />
              New {noun}
            </Button>
          ) : undefined
        }
      />
    )
  } else if (results.length === 0) {
    content = (
      <EmptyState
        title={`No ${noun}s match`}
        description={`${items.length} hidden by filters`}
        action={
          <Button variant="outline" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    )
  } else if (view.layout === "board") {
    content = <BoardLayout {...layoutProps} />
  } else if (view.layout === "calendar") {
    content = (
      <CalendarLayout {...layoutProps} month={month} onMonthChange={setMonth} />
    )
  } else if (view.layout === "list") {
    content = <ListLayout {...layoutProps} />
  } else {
    content = <TableLayout {...layoutProps} />
  }

  const showFooter = ready && items.length > 0

  return (
    <div className="relative flex h-full min-h-0 w-full overflow-hidden bg-background">
      <Tabs
        value={view.id}
        onValueChange={(id) => {
          const target = views.find((v) => v.id === id)
          if (target) switchTo(target)
        }}
        activationMode="manual"
        className="min-h-0 min-w-0 flex-1 gap-0"
      >
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b px-3 py-1.5">
          <TabStrip
            views={views}
            activeId={view.id}
            disabled={loading}
            fields={defs}
            onSelect={(id) => {
              const target = views.find((v) => v.id === id)
              if (target) switchTo(target)
            }}
            onAdd={addView}
            onRename={(id, name) => viewsApi.update(id, { name })}
            onDuplicate={duplicateView}
            onDelete={(id) => void deleteView(id)}
            unsaved={
              tracking
                ? {
                    ids: draftsApi.dirtyIds,
                    onSave: () => void saveView(),
                    onSaveAsNew: saveAsNewView,
                    onReset: resetView,
                  }
                : undefined
            }
          />
          <Toolbar
            view={view}
            fields={defs}
            disabled={loading}
            showSearch={ready && (items.length >= 3 || (tracking && query !== ""))}
            query={query}
            searchRef={searchRef}
            filterOpen={filterOpen}
            sortOpen={sortOpen}
            onQueryChange={setQuery}
            onFilterOpenChange={setFilterOpen}
            onSortOpenChange={setSortOpen}
            onViewChange={updateView}
          />
        </div>
        {view.filters.length > 0 ? (
          <FilterChips
            rules={view.filters}
            fields={defs}
            disabled={loading}
            onEdit={() => setFilterOpen(true)}
            onRemove={(index) =>
              updateView({
                filters: view.filters.filter((_, i) => i !== index),
              })
            }
            onAdd={() => {
              updateView({ filters: [...view.filters, defaultRule(defs[0])] })
              setFilterOpen(true)
            }}
          />
        ) : null}
        <TabsContent
          ref={contentRef}
          value={view.id}
          tabIndex={-1}
          className="min-h-0 flex-1 overflow-hidden"
        >
          {content}
        </TabsContent>
        {showFooter ? (
          <div className="flex h-9 shrink-0 items-center justify-between border-t px-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-3">
              <span>
                {results.length === items.length
                  ? plural(noun, results.length)
                  : `${results.length} of ${plural(noun, items.length)}`}
              </span>
              {undated.length > 0 ? (
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="ghost" size="xs">
                      No date ({undated.length})
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent align="start" className="w-64 gap-1 p-1.5">
                    <p className="px-1 text-xs font-medium">No date</p>
                    {undated.map((item) => (
                      <Button
                        key={item.id}
                        variant="ghost"
                        size="sm"
                        className="justify-start"
                        title={item.title}
                        onClick={() => openRecord(item.id)}
                      >
                        <span className="truncate">{item.title}</span>
                      </Button>
                    ))}
                  </PopoverContent>
                </Popover>
              ) : null}
            </div>
            {onCreate ? (
              <Button
                variant="ghost"
                size="xs"
                onClick={() => requestCreate(createDefaults())}
              >
                <PlusIcon />
                New {noun}
              </Button>
            ) : null}
          </div>
        ) : null}
      </Tabs>
      {panelItem ? (
        <RecordPanel
          item={panelItem}
          fields={defs}
          noun={noun}
          panelRef={panelRef}
          onClose={() => closePanel(true)}
          onUpdate={
            onUpdate
              ? (id, patch) => onUpdate(id, patch as unknown as Partial<T>)
              : undefined
          }
          onDelete={onDelete ? handleDelete : undefined}
          renderPanel={
            renderPanel
              ? (_record: Rec, ctx) => renderPanel(panelItem, ctx)
              : undefined
          }
        />
      ) : null}
    </div>
  )
}
