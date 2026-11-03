export type TokenOp = "eq" | "gt" | "gte" | "lt" | "lte"

export type QueryToken = {
  key: string
  op: TokenOp
  value: string
  negated: boolean
}

/** `text` is the free words joined by single spaces. */
export type Query = { tokens: QueryToken[]; text: string }

export type QueryKey = {
  key: string
  type: "choice" | "number" | "text"
  hint?: string
  values?: string[]
}
