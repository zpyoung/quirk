import { serializeToken } from "./query"
import type { QueryKey } from "./types"

export type Suggestion =
  | { kind: "key"; label: string; hint?: string; word: string }
  | { kind: "value"; label: string; word: string }
  | { kind: "recent"; label: string; query: string }
  | { kind: "text"; label: string; word: string }

export type SuggestionSection = { id: string; label: string; items: Suggestion[] }

/** `hint` is a line of guidance shown when the section list cannot say what to type next. */
export type SuggestionList = { sections: SuggestionSection[]; hint?: string }

const TYPE_LABELS: Record<QueryKey["type"], string> = { choice: "Choice", number: "Number", text: "Text" }
const MAX_RECENT = 5
const KEY_WORD = /^(-?)([A-Za-z_][A-Za-z0-9_.]*):([\s\S]*)$/

/**
 * What the popover offers for the word being typed. A known `key:` switches to that key's values;
 * anything else lists keys (recent searches first when the whole draft is empty) and, once something
 * is typed, a plain text search row.
 */
export function suggest(input: {
  word: string
  keys: QueryKey[]
  recent: string[]
  draftEmpty: boolean
}): SuggestionList {
  const { word, keys, recent, draftEmpty } = input

  const head = KEY_WORD.exec(word)
  const def = head ? keys.find((k) => k.key.toLowerCase() === head[2].toLowerCase()) : undefined
  if (head && def) {
    const partial = head[3].replace(/^"/, "").toLowerCase()
    const items: Suggestion[] = (def.values ?? [])
      .filter((value) => value.toLowerCase().includes(partial))
      .map((value) => ({
        kind: "value",
        label: value,
        word: serializeToken({ key: def.key, op: "eq", value, negated: head[1] === "-" }),
      }))
    if (items.length > 0) {
      return { sections: [{ id: "values", label: `Values for ${def.key}`, items }] }
    }
    const hint =
      def.type === "choice"
        ? "No matching value"
        : def.type === "number"
          ? "Type a number, optionally after <, >, <= or >=, then press Space or Enter"
          : "Type a value, then press Space or Enter"
    return { sections: [], hint }
  }

  const sections: SuggestionSection[] = []
  if (word === "" && draftEmpty && recent.length > 0) {
    sections.push({
      id: "recent",
      label: "Recent searches",
      items: recent.slice(0, MAX_RECENT).map((query) => ({ kind: "recent", label: query, query })),
    })
  }

  const negated = word.startsWith("-")
  const term = word.slice(negated ? 1 : 0).toLowerCase()
  const matching = keys
    .filter((k) => k.key.toLowerCase().includes(term))
    .sort((a, b) => Number(b.key.toLowerCase().startsWith(term)) - Number(a.key.toLowerCase().startsWith(term)))
  const byType = new Map<QueryKey["type"], QueryKey[]>()
  for (const k of matching) byType.set(k.type, [...(byType.get(k.type) ?? []), k])
  for (const [type, group] of byType) {
    sections.push({
      id: type,
      label: TYPE_LABELS[type],
      items: group.map((k) => ({
        kind: "key",
        label: k.key,
        hint: k.hint,
        word: `${negated ? "-" : ""}${k.key}:`,
      })),
    })
  }

  if (word !== "") {
    sections.push({
      id: "raw",
      label: "Text search",
      items: [{ kind: "text", label: `"${word}"`, word }],
    })
  }
  return { sections }
}

export function flatten(list: SuggestionList): Suggestion[] {
  return list.sections.flatMap((section) => section.items)
}
