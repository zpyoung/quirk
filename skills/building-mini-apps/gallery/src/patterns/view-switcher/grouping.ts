import { textOf, valueOf, type Field, type Rec } from "./fields"

export interface Column {
  /** "" for the column of records with no (or an unlisted) value. */
  value: string
  label: string
  items: Rec[]
}

/** One column per option, in option order, plus a "No <field>" column only when it has records. */
export function buildColumns(items: Rec[], field: Field): Column[] {
  const options = field.options ?? []
  const columns: Column[] = options.map((value) => ({
    value,
    label: value,
    items: [],
  }))
  const none: Column = {
    value: "",
    label: `No ${field.label.toLowerCase()}`,
    items: [],
  }
  for (const item of items) {
    const value = textOf(valueOf(item, field.key))
    const column = columns.find((c) => c.value === value) ?? none
    column.items.push(item)
  }
  return none.items.length > 0 ? [...columns, none] : columns
}
