import { formatDay, isIsoDate } from "./dates"
import type { FieldType, FilterOp, FilterRule } from "./types"

/** Non-generic view of a FieldDef, which is how every internal module reads fields. */
export interface Field {
  key: string
  label: string
  type: FieldType
  options?: string[]
}

export interface Rec {
  id: string
  title: string
}

export const TITLE_FIELD: Field = { key: "title", label: "Title", type: "text" }

export function withTitle(fields: readonly Field[]): Field[] {
  return [TITLE_FIELD, ...fields]
}

export function valueOf(item: Rec, key: string): unknown {
  return (item as unknown as Record<string, unknown>)[key]
}

export function textOf(value: unknown): string {
  return value === undefined || value === null ? "" : String(value)
}

/** Human text for a stored value; "" when the field is unset. */
export function displayValue(field: Field, raw: unknown): string {
  const text = textOf(raw)
  return field.type === "date" && isIsoDate(text) ? formatDay(text) : text
}

/** The field named `key` if it has the wanted type, else the first field of that type. */
export function pickField(
  fields: readonly Field[],
  key: string | undefined,
  type: FieldType
) {
  return (
    fields.find((f) => f.key === key && f.type === type) ??
    fields.find((f) => f.type === type)
  )
}

export const OPS_BY_TYPE: Record<FieldType, FilterOp[]> = {
  text: ["contains", "is", "isNot"],
  select: ["anyOf", "is", "isNot"],
  date: ["is", "onOrBefore", "onOrAfter"],
  number: ["is", "gte", "lte"],
}

export const OP_LABEL: Record<FilterOp, string> = {
  contains: "contains",
  is: "is",
  isNot: "is not",
  anyOf: "is any of",
  onOrBefore: "is on or before",
  onOrAfter: "is on or after",
  gte: "is at least",
  lte: "is at most",
}

export function defaultRule(field: Field): FilterRule {
  const op = OPS_BY_TYPE[field.type][0]
  return { field: field.key, op, value: op === "anyOf" ? [] : "" }
}

export function describeRule(
  rule: FilterRule,
  fields: readonly Field[]
): string {
  const field = fields.find((f) => f.key === rule.field)
  const values = Array.isArray(rule.value)
    ? rule.value
    : rule.value
      ? [rule.value]
      : []
  const shown = values
    .map((v) => (field ? displayValue(field, v) : v))
    .join(", ")
  return `${field?.label ?? rule.field} ${OP_LABEL[rule.op]} ${shown || "..."}`
}
