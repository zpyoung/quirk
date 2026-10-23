import type { ReactNode } from "react"

export type ExpandItem = {
  id: string
  title: string
  notes?: string
  done?: boolean
}

/** One optional field of an item: an icon in the strip while empty, a row in the card once set. */
export type ExpandField<T extends ExpandItem> = {
  /** Unique within the list; also the identity used for strip order. */
  key: string
  /** Tooltip, editor label and row label. */
  label: string
  /** Supplied by the app; the block ships no icon set. */
  icon: ReactNode
  /** False means the field shows as a strip icon and has no row. */
  isSet(item: T): boolean
  /** Value shown in the filled row. */
  display(item: T): ReactNode
  /** Patch that empties the field. */
  clear(item: T): Partial<T>
  /** Rendered inside the field's popover; `onChange` saves immediately. */
  Editor(props: {
    item: T
    onChange(patch: Partial<T>): void
    onClose(): void
  }): ReactNode
  /** Trailing glyph on the collapsed row while the field is set. */
  glyph?: ReactNode
}
