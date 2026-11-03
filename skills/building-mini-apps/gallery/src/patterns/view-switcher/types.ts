export type Layout = "table" | "board" | "list" | "calendar"

/** Date values are "YYYY-MM-DD" strings. */
export type FieldType = "text" | "select" | "date" | "number"

/** `options` is required for select; its order is the sort and column order. */
export interface FieldDef<T> {
  key: Extract<keyof T, string>
  label: string
  type: FieldType
  options?: string[]
}

export type FilterOp =
  | "contains"
  | "is"
  | "isNot"
  | "anyOf"
  | "onOrBefore"
  | "onOrAfter"
  | "gte"
  | "lte"

export interface FilterRule {
  field: string
  op: FilterOp
  value: string | string[]
}

export interface SortRule {
  field: string
  dir: "asc" | "desc"
}

export interface ViewConfig {
  id: string
  name: string
  layout: Layout
  filters: FilterRule[]
  sort?: SortRule
  groupBy?: string
  dateField?: string
  /** Saved search text; read and saved only when `trackUnsaved` is on. */
  query?: string
}
