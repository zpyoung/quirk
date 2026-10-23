import type { ReactNode } from "react"

export type BulkSelectRow = { id: string }

export type BulkSelectColumn<T> = {
  id: string
  header?: ReactNode
  width?: string
  align?: "start" | "end"
  cell: (item: T) => ReactNode
}

export type BulkSelectAction = {
  id: string
  label: string
  icon?: ReactNode
  onSelect: (ids: string[]) => void
  disabledReason?: string
  overflow?: boolean
}

export const CHECKBOX_COLUMN = "2.75rem"
