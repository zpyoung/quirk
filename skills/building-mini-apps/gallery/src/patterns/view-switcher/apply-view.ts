import { textOf, valueOf, withTitle, type Field, type Rec } from "./fields"
import type { FieldDef, FilterRule, ViewConfig } from "./types"

function matches(item: Rec, rule: FilterRule, field: Field): boolean {
  const have = textOf(valueOf(item, field.key))
  const wants = Array.isArray(rule.value)
    ? rule.value
    : rule.value === ""
      ? []
      : [rule.value]
  // a rule with no value yet is inert so a half-built filter never empties the view
  if (wants.length === 0) return true
  switch (rule.op) {
    case "contains":
      return wants.some((w) => have.toLowerCase().includes(w.toLowerCase()))
    case "is":
    case "anyOf":
      return wants.includes(have)
    case "isNot":
      return !wants.includes(have)
    case "onOrBefore":
      return have !== "" && have <= wants[0]
    case "onOrAfter":
      return have !== "" && have >= wants[0]
    case "gte":
      return have !== "" && Number(have) >= Number(wants[0])
    case "lte":
      return have !== "" && Number(have) <= Number(wants[0])
  }
}

function compare(field: Field, a: string, b: string): number {
  if (field.type === "select") {
    const options = field.options ?? []
    const rank = (v: string) => {
      const i = options.indexOf(v)
      return i === -1 ? options.length : i
    }
    return rank(a) - rank(b)
  }
  if (field.type === "number") return Number(a) - Number(b)
  return a < b ? -1 : a > b ? 1 : 0
}

/**
 * Filters, searches and sorts `items` for one view without touching the input.
 * Filter rules are ANDed, search matches the title and text fields, and empty
 * values sort last in either direction.
 */
export function applyView<T extends { id: string; title: string }>(
  items: T[],
  view: ViewConfig,
  fields: FieldDef<T>[],
  query = ""
): T[] {
  const defs = withTitle(fields)
  const rules = view.filters.flatMap((rule) => {
    const field = defs.find((f) => f.key === rule.field)
    return field ? [{ rule, field }] : []
  })
  const needle = query.trim().toLowerCase()
  const searchable = defs.filter((f) => f.type === "text")

  const kept = items.filter(
    (item) =>
      rules.every(({ rule, field }) => matches(item, rule, field)) &&
      (needle === "" ||
        searchable.some((f) =>
          textOf(valueOf(item, f.key)).toLowerCase().includes(needle)
        ))
  )

  const sortField = view.sort && defs.find((f) => f.key === view.sort?.field)
  if (!view.sort || !sortField) return kept
  const sign = view.sort.dir === "desc" ? -1 : 1
  return [...kept].sort((a, b) => {
    const av = textOf(valueOf(a, sortField.key))
    const bv = textOf(valueOf(b, sortField.key))
    if (av === "" || bv === "") return av === bv ? 0 : av === "" ? 1 : -1
    return sign * compare(sortField, av, bv)
  })
}
