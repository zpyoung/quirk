import { useCallback, useEffect, useMemo, useState } from "react"

import { useCollection } from "@/lib/mini/store"

import {
  activateGroup,
  closeOthers,
  closeTab,
  freshLayout,
  initialState,
  navigate,
  newTab,
  normalizeLayout,
  openItem,
  reopenTab,
  selectTab,
  setMode,
  split,
  toggleSidebar,
  type WorkspaceState,
} from "./layout"
import type { OpenHow, PaneMode, WorkspaceLayout } from "./types"

export const DEFAULT_LAYOUT_STORE = "workspace-panes-layout"

/**
 * Tab, group and sidebar state persisted in the `storeName` collection as one
 * record. A missing or malformed stored layout falls back to one group with
 * one empty tab; "loading" lasts until the stored layout has been read.
 */
export function useWorkspaceLayout(storeName: string = DEFAULT_LAYOUT_STORE) {
  const seed = useMemo(() => [freshLayout()], [])
  const { items, status, replaceAll } = useCollection<WorkspaceLayout>(storeName, seed)
  const stored = items[0]
  const base = useMemo(
    () => initialState(status === "ready" ? normalizeLayout(stored) : seed[0]),
    [status, stored, seed]
  )
  const [local, setLocal] = useState<WorkspaceState>()
  const state = local ?? base

  const unsaved = local?.layout
  useEffect(() => {
    if (unsaved) replaceAll([unsaved]).catch(() => undefined)
  }, [unsaved, replaceAll])

  const apply = useCallback(
    (change: (current: WorkspaceState) => WorkspaceState) => {
      if (status === "loading") return
      setLocal((current) => change(current ?? base))
    },
    [status, base]
  )

  return {
    layout: state.layout,
    status: status === "loading" ? ("loading" as const) : ("ready" as const),
    focusRequest: state.focus,
    closedCount: state.closed.length,
    history: state.history,
    openItem: (id: string, how: OpenHow) => apply((s) => openItem(s, id, how)),
    closeTab: (tabId: string) => apply((s) => closeTab(s, tabId)),
    closeOthers: (tabId: string) => apply((s) => closeOthers(s, tabId)),
    reopenTab: () => apply(reopenTab),
    newTab: () => apply(newTab),
    split: (tabId?: string) => apply((s) => split(s, tabId)),
    setMode: (tabId: string, mode: PaneMode) => apply((s) => setMode(s, tabId, mode)),
    toggleSidebar: () => apply(toggleSidebar),
    selectTab: (tabId: string) => apply((s) => selectTab(s, tabId)),
    activateGroup: (groupId: string) => apply((s) => activateGroup(s, groupId)),
    goBack: (tabId: string) => apply((s) => navigate(s, tabId, "back")),
    goForward: (tabId: string) => apply((s) => navigate(s, tabId, "forward")),
  }
}
