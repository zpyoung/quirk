import type { ReactNode } from "react"

export type InspectorItem = {
  id: string
  title: string
  type: string
  parentId?: string | null
}

export type FieldDef<T> = {
  key: keyof T & string
  label: string
  kind: "text" | "number" | "select" | "toggle" | "popover"
  options?: { value: string; label: string }[]
  unit?: string
  min?: number
  max?: number
  step?: number
  renderEditor?: (value: unknown, set: (v: unknown) => void) => ReactNode
}

export type SectionDef<T> = {
  id: string
  title: string
  fields: FieldDef<T>[]
  optional?: boolean
}

export type InspectorSchema<T extends InspectorItem> = Record<
  T["type"],
  SectionDef<T>[]
>

export type SelectMode = "replace" | "toggle"

export type InspectorProps<T extends InspectorItem> = {
  items: T[]
  schema: InspectorSchema<T>
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  selectedIds?: string[]
  onSelectionChange?: (ids: string[]) => void
  onUpdate: (ids: string[], patch: Partial<T>) => void | Promise<void>
  onRemove?: (ids: string[]) => void | Promise<void>
  onRename?: (id: string, title: string) => void | Promise<void>
  renderCanvas: (ctx: {
    items: T[]
    selectedIds: string[]
    hoverId: string | null
    select: (id: string, mode: SelectMode) => void
    hover: (id: string | null) => void
  }) => ReactNode
  pageView?: ReactNode
  emptyView?: ReactNode
}
