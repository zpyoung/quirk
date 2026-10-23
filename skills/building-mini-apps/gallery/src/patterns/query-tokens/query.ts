import type { Query, QueryToken, TokenOp } from "./types"

export const EMPTY_QUERY: Query = { tokens: [], text: "" }

type Word = { raw: string; start: number; open: boolean }

type ParseOptions = { keys?: string[] }

const HEAD = /^(-?)([A-Za-z_][A-Za-z0-9_.]*):(>=|<=|>|<)?/
const OPS: Record<string, TokenOp> = { ">": "gt", ">=": "gte", "<": "lt", "<=": "lte" }
const SYMBOLS: Record<TokenOp, string> = { eq: "", gt: ">", gte: ">=", lt: "<", lte: "<=" }

/** Splits on whitespace outside double quotes. An unterminated quote runs to the end and marks the word open. */
function lex(input: string): Word[] {
  const words: Word[] = []
  let i = 0
  while (i < input.length) {
    if (/\s/.test(input[i])) {
      i++
      continue
    }
    const start = i
    let open = false
    while (i < input.length) {
      const c = input[i]
      if (open) {
        if (c === "\\" && (input[i + 1] === '"' || input[i + 1] === "\\")) i += 2
        else {
          if (c === '"') open = false
          i++
        }
      } else if (/\s/.test(c)) break
      else {
        if (c === '"') open = true
        i++
      }
    }
    words.push({ raw: input.slice(start, i), start, open })
  }
  return words
}

/** Removes quotes and unescapes `\"` and `\\` inside them. */
function decode(raw: string): string {
  let out = ""
  let open = false
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i]
    if (open) {
      if (c === "\\" && (raw[i + 1] === '"' || raw[i + 1] === "\\")) {
        out += raw[i + 1]
        i++
      } else if (c === '"') open = false
      else out += c
    } else if (c === '"') open = true
    else out += c
  }
  return out
}

function toToken(raw: string, keys?: string[]): QueryToken | null {
  const head = HEAD.exec(raw)
  if (!head) return null
  const rest = raw.slice(head[0].length)
  if (rest === "") return null
  let key = head[2]
  if (keys) {
    const known = keys.find((k) => k.toLowerCase() === key.toLowerCase())
    if (known === undefined) return null
    key = known
  }
  return { key, op: head[3] ? OPS[head[3]] : "eq", value: decode(rest), negated: head[1] === "-" }
}

/** Splits `input` into chips (words that are `key:value`, `-key:value` or `key:<n`) and free text. */
export function parseQuery(input: string, options: ParseOptions = {}): Query {
  const tokens: QueryToken[] = []
  const text: string[] = []
  for (const { raw } of lex(input)) {
    const token = toToken(raw, options.keys)
    if (token) tokens.push(token)
    else text.push(decode(raw))
  }
  return { tokens, text: text.join(" ") }
}

function quoteIf(value: string, needsQuote: boolean): string {
  return needsQuote ? `"${value.replace(/[\\"]/g, "\\$&")}"` : value
}

export function serializeToken(token: QueryToken): string {
  const value = quoteIf(token.value, token.value === "" || /[\s"\\]|^[<>]/.test(token.value))
  return `${token.negated ? "-" : ""}${token.key}:${SYMBOLS[token.op]}${value}`
}

/** Free text as the input shows it: words that would read as a chip or break the quoting are quoted. */
export function serializeText(text: string): string {
  return text
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      const head = HEAD.exec(word)
      const lookalike = head !== null && word.length > head[0].length
      return quoteIf(word, lookalike || /["\\]/.test(word))
    })
    .join(" ")
}

/** Chips first, then the free text; `parseQuery` of the result gives the same query back. */
export function serializeQuery(query: Query): string {
  return [...query.tokens.map(serializeToken), serializeText(query.text)].filter(Boolean).join(" ")
}

/**
 * Reads what the input holds. Finished `key:value` words become chips; the word still being
 * typed (no whitespace after it yet) stays in `rest` unless `final` is set.
 */
export function parseDraft(
  draft: string,
  options: ParseOptions & { final?: boolean } = {}
): { tokens: QueryToken[]; rest: string } {
  const words = lex(draft)
  const last = words[words.length - 1]
  const typing = !options.final && last !== undefined && (last.open || !/\s$/.test(draft))
  const tokens: QueryToken[] = []
  const kept: string[] = []
  words.forEach((word, index) => {
    if (typing && index === words.length - 1) return kept.push(word.raw)
    const token = toToken(word.raw, options.keys)
    if (token) tokens.push(token)
    else kept.push(word.raw)
  })
  const trailing = !typing && kept.length > 0 && /\s$/.test(draft)
  return { tokens, rest: kept.join(" ") + (trailing ? " " : "") }
}

/** The free text a draft holds, decoded the way `parseQuery` would. */
export function draftText(draft: string): string {
  return lex(draft)
    .map((word) => decode(word.raw))
    .join(" ")
}

/** The raw word still being typed, or "" when the draft is empty or ends in whitespace. */
export function typingWord(draft: string): string {
  const last = lex(draft).pop()
  return last && (last.open || !/\s$/.test(draft)) ? last.raw : ""
}

/** Swaps the word being typed for `replacement`, or appends it when the draft ends in whitespace. */
export function replaceLastWord(draft: string, replacement: string): string {
  const last = lex(draft).pop()
  if (!last || (!last.open && /\s$/.test(draft))) return draft + replacement
  return draft.slice(0, last.start) + replacement
}

export function opLabel(token: QueryToken): string {
  if (token.op === "eq") return token.negated ? "is not" : "is"
  return `${token.negated ? "not " : ""}${SYMBOLS[token.op]}`
}

export function describeToken(token: QueryToken): string {
  return `${token.key} ${opLabel(token)} ${token.value}`
}

const numeric = (value: string | number): number | null => {
  if (typeof value === "string" && value.trim() === "") return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function sameValue(actual: string | number, wanted: string): boolean {
  const a = numeric(actual)
  const b = numeric(wanted)
  if (a !== null && b !== null) return a === b
  return String(actual).toLowerCase() === wanted.toLowerCase()
}

/**
 * Whether a record's value for `token.key` passes the chip. A list matches when any entry does.
 * A comparison against a non-number never matches; a negated chip inverts the result, so a missing value passes it.
 */
export function matchesToken(
  token: QueryToken,
  actual: string | number | readonly (string | number)[] | undefined
): boolean {
  const values = actual === undefined ? [] : typeof actual === "object" ? actual : [actual]
  const wanted = numeric(token.value)
  const hit = values.some((value) => {
    if (token.op === "eq") return sameValue(value, token.value)
    const n = numeric(value)
    if (n === null || wanted === null) return false
    if (token.op === "gt") return n > wanted
    if (token.op === "gte") return n >= wanted
    if (token.op === "lt") return n < wanted
    return n <= wanted
  })
  return token.negated ? !hit : hit
}

/** True when every word of `text` appears in one of `fields`, ignoring case. */
export function matchesText(text: string, ...fields: string[]): boolean {
  const haystack = fields.join(" ").toLowerCase()
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

/** `href` with `param` set to the query, or removed when it is empty. Only the search part changes; the hash is kept. */
export function searchWithQuery(href: string, param: string, query: Query): string {
  const url = new URL(href)
  const serialized = serializeQuery(query)
  if (serialized) url.searchParams.set(param, serialized)
  else url.searchParams.delete(param)
  return url.toString()
}

export function queryFromSearch(search: string, param: string, options: ParseOptions = {}): Query | null {
  const value = new URLSearchParams(search).get(param)
  return value === null ? null : parseQuery(value, options)
}
