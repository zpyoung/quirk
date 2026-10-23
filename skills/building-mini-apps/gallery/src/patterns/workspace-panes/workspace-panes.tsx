import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from "react"
import { PanelLeftOpenIcon } from "lucide-react"
import { useHotkeys } from "react-hotkeys-hook"

import { ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"

import { EmptyPane } from "./empty-pane"
import { activeGroupOf, activeTabOf } from "./layout"
import { Pane } from "./pane"
import { Sidebar } from "./sidebar"
import { TabStrip } from "./tab-strip"
import type { TabGroup, WorkspaceItem } from "./types"
import { DEFAULT_LAYOUT_STORE, useWorkspaceLayout } from "./use-workspace-layout"

export type WorkspacePanesProps<T extends WorkspaceItem> = {
  items: T[]
  status: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  renderStructured: (item: T, api: { update: (patch: Partial<T>) => Promise<void> }) => ReactNode
  toRaw: (item: T) => string
  parseRaw: (raw: string, item: T) => T
  onChange: (next: T) => Promise<void>
  onCreate?: () => Promise<string | void>
  badge?: (item: T) => string | undefined
  tooltip?: (item: T) => string | undefined
  storeName?: string
  maxContentWidth?: number
}

const NARROW_QUERY = "(min-width: 720px)"

function subscribeWide(listener: () => void) {
  const query = window.matchMedia(NARROW_QUERY)
  query.addEventListener("change", listener)
  return () => query.removeEventListener("change", listener)
}

const isWide = () => window.matchMedia(NARROW_QUERY).matches

const countWords = (text: string) => text.split(/\s+/).filter(Boolean).length

/**
 * Sidebar of records, tabs in one or two side-by-side groups, and a
 * Structured | Raw view of each record. The host owns the records; only the
 * layout is stored, in the `storeName` collection.
 */
export function WorkspacePanes<T extends WorkspaceItem>({
  items,
  status,
  error,
  onRetry,
  renderStructured,
  toRaw,
  parseRaw,
  onChange,
  onCreate,
  badge,
  tooltip,
  storeName = DEFAULT_LAYOUT_STORE,
  maxContentWidth = 560,
}: WorkspacePanesProps<T>) {
  const ws = useWorkspaceLayout(storeName)
  const wide = useSyncExternalStore(subscribeWide, isWide)
  const rootRef = useRef<HTMLDivElement>(null)
  const filterRef = useRef<HTMLInputElement>(null)
  const handledFocus = useRef(0)

  const ready = status === "ready" && ws.status === "ready"
  const { layout } = ws
  const activeGroup = activeGroupOf(layout)
  const activeTab = activeTabOf(layout)
  const byId = useMemo(() => new Map(items.map((item) => [item.id, item])), [items])
  const hasItems = items.length > 0
  const shownItemId = hasItems ? activeTab.itemId : null
  const activeItem = shownItemId ? byId.get(shownItemId) : undefined
  const groups: TabGroup[] = wide ? layout.groups : [activeGroup]

  useEffect(() => {
    const request = ws.focusRequest
    if (!request || request.nonce === handledFocus.current) return
    handledFocus.current = request.nonce
    const scope = `[data-group-id="${activeGroup.groupId}"]`
    const root = rootRef.current
    if (!root) return
    let target: HTMLElement | null = null
    if (request.kind === "tab") {
      target = root.querySelector(`${scope} [data-tab-id="${activeGroup.activeTabId}"]`)
    } else if (request.kind === "empty") {
      target = root.querySelector(`${scope} [data-empty-link]`)
    }
    target ??=
      root.querySelector(`${scope} textarea[data-raw-editor]`) ??
      root.querySelector(`${scope} [data-pane-body]`)
    target?.focus()
  }, [ws.focusRequest, activeGroup])

  const create = onCreate
    ? async () => {
        const id = await onCreate()
        if (id) ws.openItem(id, "here")
      }
    : undefined

  function focusFilter() {
    if (!layout.sidebarOpen) ws.toggleSidebar()
    requestAnimationFrame(() => filterRef.current?.focus())
  }

  function switchTo(index: number) {
    const tab = activeGroup.tabs[index]
    if (tab) ws.selectTab(tab.tabId)
  }

  function step(delta: number) {
    const at = activeGroup.tabs.findIndex((t) => t.tabId === activeGroup.activeTabId)
    const count = activeGroup.tabs.length
    switchTo((at + delta + count) % count)
  }

  function splitActive() {
    if (wide) ws.split()
    else ws.newTab()
  }

  const base = { preventDefault: true, enabled: ready }
  const alsoInRaw = {
    ...base,
    enableOnFormTags: ["textarea"] as const,
    ignoreEventWhen: (event: KeyboardEvent) =>
      event.target instanceof HTMLTextAreaElement && !event.target.hasAttribute("data-raw-editor"),
  }

  useHotkeys("alt+t", () => ws.newTab(), alsoInRaw)
  useHotkeys("alt+w", () => ws.closeTab(activeGroup.activeTabId), alsoInRaw)
  useHotkeys("alt+e", () => ws.setMode(activeTab.tabId, activeTab.mode === "raw" ? "structured" : "raw"), {
    ...alsoInRaw,
    enabled: ready && !!activeItem,
  })
  useHotkeys("alt+bracketright", () => step(1), alsoInRaw)
  useHotkeys("alt+bracketleft", () => step(-1), alsoInRaw)
  useHotkeys("alt+shift+t", () => ws.reopenTab(), base)
  useHotkeys(
    "alt+1,alt+2,alt+3,alt+4,alt+5,alt+6,alt+7,alt+8",
    (event) => switchTo(Number(event.code.slice(-1)) - 1),
    base
  )
  useHotkeys("alt+9", () => switchTo(activeGroup.tabs.length - 1), base)
  useHotkeys("alt+backslash", splitActive, base)
  useHotkeys("alt+b", () => ws.toggleSidebar(), base)
  useHotkeys("alt+o", focusFilter, base)
  useHotkeys("alt+n", () => void create?.().catch(() => undefined), { ...base, enabled: ready && !!create })

  if (status === "error") {
    return (
      <div className="h-full">
        <ErrorState error={error ?? new Error("Could not load items")} onRetry={onRetry} />
      </div>
    )
  }

  const titleOf = (itemId: string | null) => {
    if (!itemId || !hasItems) return "New tab"
    return byId.get(itemId)?.title ?? "Deleted"
  }
  const isDeleted = (itemId: string | null) => !!itemId && hasItems && !byId.has(itemId)

  const sidebar = layout.sidebarOpen ? (
    <Sidebar
      items={items}
      loading={!ready}
      activeId={shownItemId ?? undefined}
      filterRef={filterRef}
      onOpen={ws.openItem}
      onCreate={create ? () => void create().catch(() => undefined) : undefined}
      onCollapse={ws.toggleSidebar}
      badge={badge}
      tooltip={tooltip}
    />
  ) : (
    <div className="flex w-9 shrink-0 flex-col items-center border-r bg-sidebar py-2">
      <Button variant="ghost" size="icon-sm" aria-label="Show sidebar" onClick={ws.toggleSidebar}>
        <PanelLeftOpenIcon />
      </Button>
    </div>
  )

  const rawText = activeItem ? toRaw(activeItem) : ""

  return (
    <div ref={rootRef} className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex min-h-0 flex-1">
        {sidebar}
        <div className="min-w-0 flex-1">
          {!ready ? (
            <LoadingState label="Loading workspace" />
          ) : (
            <ResizablePanelGroup
              key={groups.map((g) => g.groupId).join()}
              orientation="horizontal"
            >
              {groups.map((group, index) => {
                const tab = group.tabs.find((t) => t.tabId === group.activeTabId) ?? group.tabs[0]
                const itemId = hasItems ? tab.itemId : null
                const item = itemId ? byId.get(itemId) : undefined
                const trail = ws.history[tab.tabId]
                return (
                  <Fragment key={group.groupId}>
                    {index > 0 ? <ResizableHandle withHandle aria-label="Resize groups" /> : null}
                    <ResizablePanel id={group.groupId} minSize="15%">
                      <section
                        aria-label={`Group ${index + 1}`}
                        data-group-id={group.groupId}
                        onPointerDownCapture={() => ws.activateGroup(group.groupId)}
                        onFocusCapture={() => ws.activateGroup(group.groupId)}
                        className="flex h-full min-w-0 flex-col"
                      >
                        <TabStrip
                          group={group}
                          titleOf={titleOf}
                          mutedOf={isDeleted}
                          onSelect={ws.selectTab}
                          onClose={ws.closeTab}
                          onNew={() => {
                            ws.activateGroup(group.groupId)
                            ws.newTab()
                          }}
                          onSplit={wide ? ws.split : undefined}
                          onCloseOthers={ws.closeOthers}
                        />
                        <Pane
                          key={`${tab.tabId}:${tab.itemId}`}
                          item={item}
                          deleted={isDeleted(tab.itemId)}
                          mode={tab.mode}
                          maxContentWidth={maxContentWidth}
                          canBack={!!trail?.back.length}
                          canForward={!!trail?.forward.length}
                          canReopen={ws.closedCount > 0}
                          onBack={() => ws.goBack(tab.tabId)}
                          onForward={() => ws.goForward(tab.tabId)}
                          onMode={(mode) => ws.setMode(tab.tabId, mode)}
                          onSplit={() => ws.split(tab.tabId)}
                          onClose={() => ws.closeTab(tab.tabId)}
                          onReopen={ws.reopenTab}
                          renderStructured={renderStructured}
                          toRaw={toRaw}
                          parseRaw={parseRaw}
                          onChange={onChange}
                          empty={
                            <EmptyPane
                              hasItems={hasItems}
                              recent={layout.recent.flatMap((id) => {
                                const found = byId.get(id)
                                return found ? [{ id, title: found.title }] : []
                              })}
                              onCreate={create ? () => void create().catch(() => undefined) : undefined}
                              onGoTo={focusFilter}
                              onOpen={(id) => ws.openItem(id, "here")}
                              onClose={() => ws.closeTab(tab.tabId)}
                            />
                          }
                        />
                      </section>
                    </ResizablePanel>
                  </Fragment>
                )
              })}
            </ResizablePanelGroup>
          )}
        </div>
      </div>
      {ready && activeItem ? (
        <p className="shrink-0 border-t px-3 py-1 text-right text-xs text-muted-foreground">
          {countWords(rawText)} words, {rawText.length} characters
        </p>
      ) : null}
    </div>
  )
}
