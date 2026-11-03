import type { ReactNode } from "react"

export type PaletteItem = { id: string; title: string }

export type PaletteAction<T extends PaletteItem> = {
  id: string
  /** End with "…" when `children` is set. */
  title: string
  run?: (item: T) => void | Promise<void>
  /** Runs once on a multi-item target. Without it, `run` is called for each item in order. */
  runMany?: (items: T[]) => void | Promise<void>
  /** Opens a sub-menu; `run` is ignored. */
  children?: PaletteAction<T>[]
  /** react-hotkeys-hook form, e.g. "mod+shift+f". */
  shortcut?: string
  /** Drawn in red and separated from the other actions. */
  destructive?: boolean
  /** Groups rows under a separator while the panel filter is empty. */
  section?: string
  /** Footer text while `run` is in flight. */
  pending?: string
  /** Toast on success; omit for none. */
  successMessage?: string
}

export type ActionPaletteProps<T extends PaletteItem> = {
  items: T[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  /**
   * First action is the primary (↵), second the secondary (⌘↵). `selection` is the whole
   * target: the checked items, or just `[item]` when nothing is checked.
   */
  getActions: (item: T, selection: T[]) => PaletteAction<T>[]
  getSubtitle?: (item: T) => string | undefined
  /** Right-aligned type label. */
  getMeta?: (item: T) => string | undefined
  /** Extra words matched besides the title. */
  getSearchText?: (item: T) => string
  /** Row group heading, shown while the query is empty. */
  getSection?: (item: T) => string | undefined
  /** Enables the "Create “…”" row when nothing matches. */
  onCreate?: (query: string) => void
  placeholder?: string
  footerLabel?: string
  emptyState?: { title: string; description?: string; action?: ReactNode }
  /** Checked item ids. Passing it, or `onSelectedIdsChange`, turns on the multi-item target. */
  selectedIds?: string[]
  onSelectedIdsChange?: (ids: string[]) => void
}

export type ActionPanelProps<T extends PaletteItem> = {
  item: T
  /** The whole target. With two or more, the header shows a "N selected" chip. */
  items?: T[]
  actions: PaletteAction<T>[]
  /** Sub-menu chain to open drilled into, outermost first. */
  initialPath?: PaletteAction<T>[]
  onClose: () => void
  onRun: (action: PaletteAction<T>) => void
}
