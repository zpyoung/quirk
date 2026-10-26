import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { PanelLeftIcon, PanelRightIcon } from "lucide-react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

import { ItemTree } from "./item-tree"
import { PropertiesPanel } from "./properties-panel"
import { buildRows } from "./tree-model"
import type { InspectorItem, InspectorProps, SelectMode } from "./types"

const UNDO_MS = 5000
const EMPTY_SET: ReadonlySet<string> = new Set()
const PANEL_FIELDS =
  '[data-region="panel"] [data-panel-body] :is(input, [role="combobox"], [role="checkbox"], button):not(:disabled)'

type Overlay<T> = { token: number; ids: string[]; patch: Partial<T> }

function describeError(cause: unknown) {
  return cause instanceof Error ? cause.message : String(cause)
}

function DockToggle({
  label,
  shortcut,
  pressed,
  onClick,
  children,
}: {
  label: string
  shortcut?: string
  pressed: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          aria-pressed={pressed}
          onClick={onClick}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {label}
        {shortcut ? <Kbd className="ml-2">{shortcut}</Kbd> : null}
      </TooltipContent>
    </Tooltip>
  )
}

function Workspace<T extends InspectorItem>({
  items: sourceItems,
  schema,
  selectedIds: controlledIds,
  onSelectionChange,
  onUpdate,
  onRemove,
  onRename,
  renderCanvas,
  pageView,
  emptyView,
}: InspectorProps<T>) {
  const [ownIds, setOwnIds] = useState<string[]>([])
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [allHidden, setAllHidden] = useState(false)
  const [removing, setRemoving] = useState<ReadonlySet<string>>(EMPTY_SET)
  const [overlays, setOverlays] = useState<Overlay<T>[]>([])
  const [anchorId, setAnchorId] = useState<string | null>(null)
  const canvasEl = useRef<HTMLDivElement>(null)
  const tokens = useRef(0)
  const finalizers = useRef(new Set<() => void>())

  // optimistic edits and not-yet-committed removals sit over the app's items so the UI never flashes stale values
  const items = useMemo(() => {
    if (removing.size === 0 && overlays.length === 0) return sourceItems
    return sourceItems
      .filter((item) => !removing.has(item.id))
      .map((item) =>
        overlays.reduce(
          (acc, overlay) =>
            overlay.ids.includes(item.id) ? { ...acc, ...overlay.patch } : acc,
          item
        )
      )
  }, [sourceItems, removing, overlays])

  const byId = useMemo(
    () => new Map(items.map((item) => [item.id, item])),
    [items]
  )
  const orderedIds = useMemo(
    () => buildRows(items, EMPTY_SET).map((row) => row.item.id),
    [items]
  )
  const rawIds = controlledIds ?? ownIds
  const selectedIds = useMemo(
    () => rawIds.filter((id) => byId.has(id)),
    [rawIds, byId]
  )
  const selected = useMemo(
    () => selectedIds.flatMap((id) => byId.get(id) ?? []),
    [selectedIds, byId]
  )

  const setSelection = useCallback(
    (ids: string[]) => {
      if (controlledIds === undefined) setOwnIds(ids)
      onSelectionChange?.(ids)
    },
    [controlledIds, onSelectionChange]
  )

  const select = (id: string, mode: SelectMode) => {
    setAnchorId(id)
    if (mode === "toggle") {
      setSelection(
        selectedIds.includes(id)
          ? selectedIds.filter((x) => x !== id)
          : [...selectedIds, id]
      )
    } else {
      setSelection([id])
    }
  }

  const selectFromTree = (
    id: string,
    mode: "replace" | "range" | "toggle",
    visibleIds: string[]
  ) => {
    if (mode !== "range") return select(id, mode)
    const from = visibleIds.indexOf(anchorId ?? selectedIds.at(-1) ?? id)
    const to = visibleIds.indexOf(id)
    if (from < 0 || to < 0) return select(id, "replace")
    setSelection(visibleIds.slice(Math.min(from, to), Math.max(from, to) + 1))
  }

  const write = useCallback(
    async (
      ids: string[],
      patch: Partial<T>,
      task: () => void | Promise<void>,
      failure: string
    ) => {
      const token = ++tokens.current
      setOverlays((prev) => [...prev, { token, ids, patch }])
      try {
        await task()
      } catch (cause) {
        toast.error(failure, { description: describeError(cause) })
      } finally {
        setOverlays((prev) => prev.filter((overlay) => overlay.token !== token))
      }
    },
    []
  )

  const update = (patch: Partial<T>) => {
    const ids = selectedIds
    void write(ids, patch, () => onUpdate(ids, patch), "Could not save changes")
  }

  const rename = onRename
    ? (id: string, title: string) =>
        void write(
          [id],
          { title } as unknown as Partial<T>,
          () => onRename(id, title),
          "Could not rename"
        )
    : undefined

  const removeSelected = (root: HTMLElement | null, restoreFocus: boolean) => {
    if (!onRemove || selectedIds.length === 0) return
    const ids = selectedIds
    const gone = new Set(ids)
    const remaining = orderedIds.filter((id) => !gone.has(id))
    const firstIndex = Math.min(...ids.map((id) => orderedIds.indexOf(id)))
    const focusTarget = remaining[Math.min(firstIndex, remaining.length - 1)]

    setRemoving((prev) => new Set([...prev, ...ids]))
    setSelection([])
    if (restoreFocus && focusTarget !== undefined) {
      requestAnimationFrame(() =>
        root
          ?.querySelector<HTMLElement>(
            `[data-region="tree"] [data-item-id="${CSS.escape(focusTarget)}"]`
          )
          ?.focus()
      )
    }

    const release = () =>
      setRemoving((prev) => new Set([...prev].filter((id) => !gone.has(id))))
    const finalize = () => {
      window.clearTimeout(timer)
      finalizers.current.delete(finalize)
      toast.dismiss(toastId)
      void (async () => {
        try {
          await onRemove(ids)
        } catch (cause) {
          toast.error("Could not remove", { description: describeError(cause) })
        } finally {
          release()
        }
      })()
    }
    const timer = window.setTimeout(finalize, UNDO_MS)
    finalizers.current.add(finalize)

    const first = byId.get(ids[0])?.title ?? "item"
    const toastId = toast(
      ids.length === 1 ? `Removed "${first}"` : `Removed ${ids.length} items`,
      {
        duration: UNDO_MS,
        action: {
          label: "Undo",
          onClick: () => {
            window.clearTimeout(timer)
            finalizers.current.delete(finalize)
            release()
            setSelection(ids)
          },
        },
      }
    )
  }

  useEffect(() => {
    const pending = finalizers.current
    return () => [...pending].forEach((finalize) => finalize())
  }, [])

  const rootRef = useHotkeys<HTMLDivElement>(
    ["escape", "delete", "backspace", "enter", "meta+a", "ctrl+a"],
    (event) => {
      const root = event.currentTarget
      const target = event.target
      if (!(root instanceof HTMLElement) || !(target instanceof Element)) return
      const inTree = target.closest('[data-region="tree"]') !== null
      if (!inTree && target.closest('[data-region="canvas"]') === null) return

      if (event.key === "Enter") {
        if (!inTree) return
        event.preventDefault()
        const field = root.querySelector<HTMLElement>(PANEL_FIELDS)
        field?.focus()
        if (field instanceof HTMLInputElement) field.select()
      } else if (event.key === "Escape") {
        if (selectedIds.length > 0) setSelection([])
      } else if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault()
        removeSelected(root, inTree)
      } else {
        event.preventDefault()
        setSelection(orderedIds)
      }
    }
  )

  useHotkeys("shift+backslash", () => {
    setAllHidden(!allHidden)
    // hiding the tree can drop focus on the body, where Esc and Delete no longer reach the workspace
    if (!allHidden) {
      requestAnimationFrame(() => {
        if (document.activeElement === document.body) canvasEl.current?.focus()
      })
    }
  })

  const onPanelKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const target = event.target
    if (event.key !== "Escape" || !(target instanceof HTMLInputElement)) return
    if (!event.currentTarget.contains(target)) return
    const primary = selectedIds.at(-1)
    if (primary === undefined) return
    event.currentTarget
      .closest<HTMLElement>("[data-inspector]")
      ?.querySelector<HTMLElement>(
        `[data-region="tree"] [data-item-id="${CSS.escape(primary)}"]`
      )
      ?.focus()
  }

  const showLeft = leftOpen && !allHidden
  const showRight = rightOpen && (!allHidden || selectedIds.length > 0)
  const toggleLeft = () => {
    if (allHidden) setAllHidden(false)
    setLeftOpen(allHidden ? true : !leftOpen)
  }
  const toggleRight = () => {
    if (allHidden) setAllHidden(false)
    setRightOpen(allHidden ? true : !rightOpen)
  }

  const hoverFromTree = (target: EventTarget) => {
    const id =
      target instanceof Element
        ? target.closest<HTMLElement>("[data-item-id]")?.dataset.itemId
        : undefined
    setHoverId(id ?? null)
  }

  return (
    <div
      ref={rootRef}
      data-inspector
      className="flex h-full min-h-0 flex-col bg-background"
    >
      <div className="flex h-9 shrink-0 items-center gap-1 border-b px-2">
        <DockToggle
          label="Toggle item tree"
          pressed={showLeft}
          onClick={toggleLeft}
        >
          <PanelLeftIcon />
        </DockToggle>
        <DockToggle
          label="Toggle properties panel"
          pressed={showRight}
          onClick={toggleRight}
        >
          <PanelRightIcon />
        </DockToggle>
        <span className="ml-auto text-xs text-muted-foreground">
          Hide docks <Kbd>⇧</Kbd> <Kbd>\</Kbd>
        </span>
      </div>
      <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
        {showLeft ? (
          <>
            <ResizablePanel
              id="tree"
              defaultSize="20%"
              minSize="140px"
              maxSize="40%"
            >
              <div
                data-region="tree"
                className="h-full min-h-0"
                onPointerOver={(event) => hoverFromTree(event.target)}
                onPointerLeave={() => setHoverId(null)}
              >
                {items.length === 0 ? (
                  <EmptyState title="No items" />
                ) : (
                  <ItemTree
                    items={items}
                    selectedIds={selectedIds}
                    onSelect={selectFromTree}
                    onRename={rename}
                  />
                )}
              </div>
            </ResizablePanel>
            <ResizableHandle />
          </>
        ) : null}
        <ResizablePanel id="canvas" minSize="20%">
          <div
            ref={canvasEl}
            data-region="canvas"
            role="region"
            aria-label="Canvas"
            tabIndex={-1}
            className="relative h-full min-w-0 overflow-auto outline-none"
          >
            {items.length === 0
              ? (emptyView ?? <EmptyState title="Nothing to inspect yet" />)
              : renderCanvas({
                  items,
                  selectedIds,
                  hoverId,
                  select,
                  hover: setHoverId,
                })}
          </div>
        </ResizablePanel>
        {showRight ? (
          <>
            <ResizableHandle />
            <ResizablePanel
              id="panel"
              defaultSize="22%"
              minSize="200px"
              maxSize="45%"
            >
              <div
                data-region="panel"
                data-mini="panel"
                role="region"
                aria-label="Properties"
                className="h-full min-h-0"
                onKeyDown={onPanelKeyDown}
              >
                <PropertiesPanel
                  selected={selected}
                  schema={schema}
                  onChange={update}
                  pageView={pageView}
                />
              </div>
            </ResizablePanel>
          </>
        ) : null}
      </ResizablePanelGroup>
    </div>
  )
}

/**
 * Three-dock editor: item tree, canvas slot and a properties panel that follows
 * the selection. Owns selection, hover, dock visibility and the shortcuts; the
 * app owns the data and applies changes through `onUpdate`, `onRemove` and
 * `onRename`. Removals wait out an undo toast before `onRemove` is called.
 */
export function Inspector<T extends InspectorItem>(props: InspectorProps<T>) {
  const { status = "ready", error, onRetry } = props

  if (status === "loading") {
    return (
      <div className="h-full min-h-0">
        <LoadingState label="Loading items" />
      </div>
    )
  }
  if (status === "error") {
    return (
      <div className="h-full min-h-0">
        <ErrorState
          error={error ?? new Error("The items could not be loaded.")}
          onRetry={onRetry}
        />
      </div>
    )
  }
  return <Workspace {...props} />
}
