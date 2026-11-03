/** One status tile. Times are epoch milliseconds. */
export type Tile = {
  id: string
  section: string
  name: string
  kind: "toggle" | "level" | "target" | "sensor"
  on?: boolean
  value?: number
  unit?: string
  target?: number
  text?: string
  onLabel?: string
  offLabel?: string
  /** Verb for turning the tile on, as in "Lock" for `Lock Front door?`. */
  onVerb?: string
  offVerb?: string
  sensitive?: boolean
  updatedAt: number
  staleAfterMs?: number
  staleOpensItem?: boolean
  history?: number[]
}

export type Urgency = "now" | "later"

/** Holds functions, so rules are passed as a prop and never stored. */
export type FlagRule = {
  id: string
  tileId: string
  title: string
  urgency: Urgency
  test: (tile: Tile) => boolean
  /** A change in this key while `test` stays true flags the rule again. */
  occurrence?: (tile: Tile) => string
}

export type TimelineEvent = {
  at: number
  type:
    | "opened"
    | "flagged-again"
    | "acknowledged"
    | "snoozed"
    | "snooze-ended"
    | "cleared"
    | "resolved"
    | "reopened"
  until?: number
  note?: string
  text?: string
}

/** `v` is the timeline format version; readers treat a missing `v` as 1. */
export type AttentionItem = {
  v: 1
  id: string
  title: string
  urgency: Urgency
  tileId?: string
  ruleId?: string
  timeline: TimelineEvent[]
}

export type ItemStatus = "open" | "acknowledged" | "snoozed" | "resolved"

export type ItemAction =
  | { type: "acknowledge" }
  | { type: "snooze"; until: number; note?: string }
  | { type: "resolve" }

export type RefreshState =
  | { state: "none" }
  | { state: "live"; at: number }
  | { state: "paused"; at?: number }
  | { state: "stale"; since?: number; error: Error }

export type RuleMemory = Record<string, { on: boolean; occurrence?: string }>

/** A badge in the summary row; with `tileId` it opens that tile's details. */
export type Summary = { id: string; label: string; tileId?: string }
