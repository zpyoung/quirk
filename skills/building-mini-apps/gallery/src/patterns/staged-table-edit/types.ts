export type StagedColumn<T> = {
  key: keyof T & string
  label: string
  type?: "text" | "number" | "select"
  options?: string[]
  width?: number
  readOnly?: boolean
  placeholder?: string
}

export type PendingChange<T> =
  | { kind: "update"; id: string; patch: Partial<T> }
  | { kind: "add"; item: T }
  | { kind: "remove"; id: string }
