export type Scalar = string | number | boolean
export type HoldData = Record<string, Scalar>
export type InputValue = string | number
export type DurationUnit = "minutes" | "hours" | "days"

/** The small input a condition needs. A duration's value is in milliseconds. */
export type ConditionInput =
  | {
      type: "count"
      label: string
      unit: string
      min?: number
      max?: number
      default?: number
    }
  | { type: "duration"; label: string; default?: number; unit?: DurationUnit }
  | { type: "choice"; label: string; options: string[] }
  | { type: "text"; label: string; placeholder?: string }

/** The condition in force: its id, when it began, what the user entered, and data it keeps for itself. */
export type Hold = {
  kind: string
  at: number
  value?: InputValue
  data: HoldData
}

export type Transition = {
  at: number
  from: string
  to: string
  reason: string
}

/** Plain JSON, stored with the item. `v` is the record format version. */
export type StatusRecord = {
  v: 1
  state: string
  since: number
  occurrences: number
  users: number
  release?: string
  hold?: Hold
  last?: Transition
}

export type StatusEvent =
  | { type: "choose"; kind: string; value?: InputValue }
  | { type: "clear" }
  | { type: "occurrence"; count?: number; newUsers?: number; release?: string }
  | { type: "release"; version: string; commits?: string[] }
  | { type: "signal"; name: string }
  | { type: "time" }

/** `record` already counts the event being watched. */
export type ConditionContext = { now: number; record: StatusRecord }

/** Holds functions, so models are passed as a prop and never stored. */
export type ConditionKind = {
  id: string
  group: string
  label: string
  hint?: string
  /** State the item takes when this is chosen. */
  enters: string
  /** State it takes when the condition is met; defaults to the model's open state. */
  trips?: string
  /** False leaves the condition to the primary half of its split button. */
  inMenu?: boolean
  input?: ConditionInput
  start?: (value: InputValue | undefined, ctx: ConditionContext) => HoldData
  watch?: (
    hold: Hold,
    event: StatusEvent,
    ctx: ConditionContext
  ) => { trip?: boolean; reason?: string; data?: HoldData } | void
  describe?: (hold: Hold, ctx: ConditionContext) => string
}

export type Tone = "neutral" | "good" | "warn" | "bad" | "muted"
export type StateIcon =
  | "open"
  | "done"
  | "regressed"
  | "archived"
  | "escalating"
  | "snoozed"
export type StateDef = { label: string; tone: Tone; icon?: StateIcon }

/** One split button: `primary` is the kind its primary half applies. */
export type StatusGroup = {
  id: string
  label: string
  undoLabel: string
  menuLabel: string
  primary: string
  key?: string
}

export type StatusModel = {
  open: string
  states: Record<string, StateDef>
  groups: StatusGroup[]
  kinds: ConditionKind[]
  /** Nouns shown beside the running totals on a row, such as "events". */
  counters?: { occurrences?: string; users?: string }
}

export type StatusItem = {
  id: string
  title: string
  meta?: string
  status: StatusRecord
}
