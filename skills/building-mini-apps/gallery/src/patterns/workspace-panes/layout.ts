import type {
  OpenHow,
  PaneMode,
  TabGroup,
  WorkspaceLayout,
  WorkspaceTab,
} from "./types"

const RECENT_LIMIT = 10
const CLOSED_LIMIT = 10

export type ClosedTab = { itemId: string; mode: PaneMode }
export type TabHistory = { back: (string | null)[]; forward: (string | null)[] }
export type FocusKind = "tab" | "pane" | "empty"

/** Layout plus the session-only state that never reaches storage. */
export type WorkspaceState = {
  layout: WorkspaceLayout
  closed: ClosedTab[]
  history: Record<string, TabHistory>
  focus?: { kind: FocusKind; nonce: number }
}

const newId = () => crypto.randomUUID()

function emptyTab(): WorkspaceTab {
  return { tabId: newId(), itemId: null, mode: "structured" }
}

export function freshLayout(): WorkspaceLayout {
  const tab = emptyTab()
  const groupId = newId()
  return {
    id: "layout",
    groups: [{ groupId, tabs: [tab], activeTabId: tab.tabId }],
    activeGroupId: groupId,
    sidebarOpen: true,
    recent: [],
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const isTab = (value: unknown): value is WorkspaceTab =>
  isRecord(value) &&
  typeof value.tabId === "string" &&
  (value.itemId === null || typeof value.itemId === "string") &&
  (value.mode === "structured" || value.mode === "raw")

const isGroup = (value: unknown): value is TabGroup =>
  isRecord(value) &&
  typeof value.groupId === "string" &&
  typeof value.activeTabId === "string" &&
  Array.isArray(value.tabs) &&
  value.tabs.length > 0 &&
  value.tabs.every(isTab) &&
  value.tabs.some((t) => t.tabId === value.activeTabId)

/** Returns the stored layout when it is well formed, otherwise a fresh one-group layout. */
export function normalizeLayout(stored: unknown): WorkspaceLayout {
  const candidate = isRecord(stored) ? stored : undefined
  const groups = candidate?.groups
  if (
    !Array.isArray(groups) ||
    (groups.length !== 1 && groups.length !== 2) ||
    !groups.every(isGroup) ||
    !groups.some((g) => g.groupId === candidate?.activeGroupId)
  ) {
    return freshLayout()
  }
  return {
    id: "layout",
    groups,
    activeGroupId: candidate!.activeGroupId as string,
    sidebarOpen: candidate!.sidebarOpen !== false,
    recent: Array.isArray(candidate!.recent)
      ? candidate!.recent.filter((id): id is string => typeof id === "string")
      : [],
  }
}

export function initialState(layout: WorkspaceLayout): WorkspaceState {
  return { layout, closed: [], history: {} }
}

export function activeGroupOf(layout: WorkspaceLayout): TabGroup {
  return layout.groups.find((g) => g.groupId === layout.activeGroupId) ?? layout.groups[0]
}

export function activeTabOf(layout: WorkspaceLayout): WorkspaceTab {
  const group = activeGroupOf(layout)
  return group.tabs.find((t) => t.tabId === group.activeTabId) ?? group.tabs[0]
}

export function findTab(layout: WorkspaceLayout, tabId: string) {
  for (const group of layout.groups) {
    const tab = group.tabs.find((t) => t.tabId === tabId)
    if (tab) return { group, tab }
  }
  return undefined
}

function replaceGroup(layout: WorkspaceLayout, next: TabGroup): WorkspaceLayout {
  return { ...layout, groups: layout.groups.map((g) => (g.groupId === next.groupId ? next : g)) }
}

function withFocus(state: WorkspaceState, kind: FocusKind): WorkspaceState {
  return { ...state, focus: { kind, nonce: (state.focus?.nonce ?? 0) + 1 } }
}

function pushRecent(recent: string[], itemId: string | null): string[] {
  if (!itemId) return recent
  return [itemId, ...recent.filter((id) => id !== itemId)].slice(0, RECENT_LIMIT)
}

function insertTab(
  layout: WorkspaceLayout,
  group: TabGroup,
  tab: WorkspaceTab
): WorkspaceLayout {
  const at = group.tabs.findIndex((t) => t.tabId === group.activeTabId) + 1
  const tabs = [...group.tabs.slice(0, at), tab, ...group.tabs.slice(at)]
  return {
    ...replaceGroup(layout, { ...group, tabs, activeTabId: tab.tabId }),
    activeGroupId: group.groupId,
    recent: pushRecent(layout.recent, tab.itemId),
  }
}

/** Puts `tab` in a new group on the right, or in the other group when two already exist. */
function placeInSplit(layout: WorkspaceLayout, sourceGroupId: string, tab: WorkspaceTab): WorkspaceLayout {
  if (layout.groups.length === 1) {
    const group: TabGroup = { groupId: newId(), tabs: [tab], activeTabId: tab.tabId }
    return {
      ...layout,
      groups: [...layout.groups, group],
      activeGroupId: group.groupId,
      recent: pushRecent(layout.recent, tab.itemId),
    }
  }
  const other = layout.groups.find((g) => g.groupId !== sourceGroupId) ?? layout.groups[1]
  return insertTab(layout, other, tab)
}

function omitHistory(history: Record<string, TabHistory>, tabIds: string[]) {
  return Object.fromEntries(Object.entries(history).filter(([id]) => !tabIds.includes(id)))
}

export function newTab(state: WorkspaceState): WorkspaceState {
  const layout = insertTab(state.layout, activeGroupOf(state.layout), emptyTab())
  return withFocus({ ...state, layout }, "empty")
}

export function openItem(state: WorkspaceState, itemId: string, how: OpenHow): WorkspaceState {
  const { layout } = state
  if (how === "here") {
    const group = activeGroupOf(layout)
    const tab = activeTabOf(layout)
    if (tab.itemId === itemId) return withFocus(state, "pane")
    const tabs = group.tabs.map((t) => (t.tabId === tab.tabId ? { ...t, itemId } : t))
    const past = state.history[tab.tabId] ?? { back: [], forward: [] }
    return withFocus(
      {
        ...state,
        layout: {
          ...replaceGroup(layout, { ...group, tabs }),
          recent: pushRecent(layout.recent, itemId),
        },
        history: { ...state.history, [tab.tabId]: { back: [...past.back, tab.itemId], forward: [] } },
      },
      "pane"
    )
  }
  const mode = activeTabOf(layout).mode
  const tab: WorkspaceTab = { tabId: newId(), itemId, mode }
  if (how === "tab") {
    return withFocus({ ...state, layout: insertTab(layout, activeGroupOf(layout), tab) }, "pane")
  }
  return withFocus({ ...state, layout: placeInSplit(layout, layout.activeGroupId, tab) }, "pane")
}

export function split(state: WorkspaceState, tabId?: string): WorkspaceState {
  const { layout } = state
  const source = tabId
    ? findTab(layout, tabId)
    : { group: activeGroupOf(layout), tab: activeTabOf(layout) }
  if (!source) return state
  const copy: WorkspaceTab = { tabId: newId(), itemId: source.tab.itemId, mode: source.tab.mode }
  return withFocus({ ...state, layout: placeInSplit(layout, source.group.groupId, copy) }, "pane")
}

export function selectTab(state: WorkspaceState, tabId: string): WorkspaceState {
  const found = findTab(state.layout, tabId)
  if (!found) return state
  const { group } = found
  if (state.layout.activeGroupId === group.groupId && group.activeTabId === tabId) return state
  return withFocus(
    {
      ...state,
      layout: {
        ...replaceGroup(state.layout, { ...group, activeTabId: tabId }),
        activeGroupId: group.groupId,
      },
    },
    "tab"
  )
}

export function activateGroup(state: WorkspaceState, groupId: string): WorkspaceState {
  if (state.layout.activeGroupId === groupId) return state
  if (!state.layout.groups.some((g) => g.groupId === groupId)) return state
  return { ...state, layout: { ...state.layout, activeGroupId: groupId } }
}

export function closeTab(state: WorkspaceState, tabId: string): WorkspaceState {
  const found = findTab(state.layout, tabId)
  if (!found) return state
  const { group, tab } = found
  const { layout } = state
  const closed = tab.itemId
    ? [{ itemId: tab.itemId, mode: tab.mode }, ...state.closed].slice(0, CLOSED_LIMIT)
    : state.closed
  const history = omitHistory(state.history, [tabId])

  if (group.tabs.length === 1) {
    if (layout.groups.length === 2) {
      const remaining = layout.groups.find((g) => g.groupId !== group.groupId)!
      return withFocus(
        { ...state, layout: { ...layout, groups: [remaining], activeGroupId: remaining.groupId }, closed, history },
        "tab"
      )
    }
    if (tab.itemId === null) return state
    const fresh = emptyTab()
    return withFocus(
      { ...state, layout: replaceGroup(layout, { ...group, tabs: [fresh], activeTabId: fresh.tabId }), closed, history },
      "tab"
    )
  }

  const at = group.tabs.findIndex((t) => t.tabId === tabId)
  const tabs = group.tabs.filter((t) => t.tabId !== tabId)
  const activeTabId =
    group.activeTabId === tabId ? tabs[Math.min(at, tabs.length - 1)].tabId : group.activeTabId
  return withFocus(
    {
      ...state,
      layout: { ...replaceGroup(layout, { ...group, tabs, activeTabId }), activeGroupId: group.groupId },
      closed,
      history,
    },
    "tab"
  )
}

export function closeOthers(state: WorkspaceState, tabId: string): WorkspaceState {
  const found = findTab(state.layout, tabId)
  if (!found) return state
  const { group, tab } = found
  const dropped = group.tabs.filter((t) => t.tabId !== tabId)
  const closed = [
    ...dropped.flatMap((t) => (t.itemId ? [{ itemId: t.itemId, mode: t.mode }] : [])),
    ...state.closed,
  ].slice(0, CLOSED_LIMIT)
  const history = omitHistory(state.history, dropped.map((t) => t.tabId))
  return withFocus(
    {
      ...state,
      layout: {
        ...replaceGroup(state.layout, { ...group, tabs: [tab], activeTabId: tab.tabId }),
        activeGroupId: group.groupId,
      },
      closed,
      history,
    },
    "tab"
  )
}

export function reopenTab(state: WorkspaceState): WorkspaceState {
  const [last, ...closed] = state.closed
  if (!last) return state
  const tab: WorkspaceTab = { tabId: newId(), itemId: last.itemId, mode: last.mode }
  const layout = insertTab(state.layout, activeGroupOf(state.layout), tab)
  return withFocus({ ...state, layout, closed }, "pane")
}

export function setMode(state: WorkspaceState, tabId: string, mode: PaneMode): WorkspaceState {
  const found = findTab(state.layout, tabId)
  if (!found || found.tab.mode === mode) return state
  const tabs = found.group.tabs.map((t) => (t.tabId === tabId ? { ...t, mode } : t))
  return withFocus(
    { ...state, layout: replaceGroup(state.layout, { ...found.group, tabs }) },
    "pane"
  )
}

export function toggleSidebar(state: WorkspaceState): WorkspaceState {
  return { ...state, layout: { ...state.layout, sidebarOpen: !state.layout.sidebarOpen } }
}

export function navigate(state: WorkspaceState, tabId: string, direction: "back" | "forward"): WorkspaceState {
  const found = findTab(state.layout, tabId)
  const past = state.history[tabId]
  if (!found || !past) return state
  const from = direction === "back" ? past.back : past.forward
  if (from.length === 0) return state
  const target = from[from.length - 1]
  const rest = from.slice(0, -1)
  const pushed = [...(direction === "back" ? past.forward : past.back), found.tab.itemId]
  const history: TabHistory =
    direction === "back" ? { back: rest, forward: pushed } : { back: pushed, forward: rest }
  const tabs = found.group.tabs.map((t) => (t.tabId === tabId ? { ...t, itemId: target } : t))
  return withFocus(
    {
      ...state,
      layout: {
        ...replaceGroup(state.layout, { ...found.group, tabs }),
        recent: pushRecent(state.layout.recent, target),
      },
      history: { ...state.history, [tabId]: history },
    },
    "pane"
  )
}
