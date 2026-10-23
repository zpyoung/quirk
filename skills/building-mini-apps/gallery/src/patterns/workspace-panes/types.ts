/** The minimum shape of a record shown in the workspace. */
export type WorkspaceItem = { id: string; title: string }

export type PaneMode = "structured" | "raw"

/** One open view. `itemId` null is the empty pane; the same record may be open in several tabs. */
export type WorkspaceTab = { tabId: string; itemId: string | null; mode: PaneMode }

export type TabGroup = { groupId: string; tabs: WorkspaceTab[]; activeTabId: string }

/** Persisted layout. `groups` always holds one or two entries. */
export type WorkspaceLayout = {
  id: "layout"
  groups: TabGroup[]
  activeGroupId: string
  sidebarOpen: boolean
  recent: string[]
}

export type OpenHow = "here" | "tab" | "split"
