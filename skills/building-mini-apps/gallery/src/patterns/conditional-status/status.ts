import type {
  ConditionInput,
  ConditionKind,
  DurationUnit,
  Hold,
  HoldData,
  InputValue,
  StatusEvent,
  StatusGroup,
  StatusModel,
  StatusRecord,
  Transition,
} from "./types"

const UNIT_MS: Record<DurationUnit, number> = {
  minutes: 60_000,
  hours: 3_600_000,
  days: 86_400_000,
}

export function durationMs(amount: number, unit: DurationUnit): number {
  return amount * UNIT_MS[unit]
}

/** Orders release names such as "2.9.0" and "2.10.0" by their numbers; negative when `a` is older. */
export function compareReleases(a: string, b: string): number {
  return a.localeCompare(b, "en", { numeric: true })
}

/** A fresh record in the model's open state. */
export function initialStatus(
  model: StatusModel,
  now: number,
  release?: string
): StatusRecord {
  return {
    v: 1,
    state: model.open,
    since: now,
    occurrences: 0,
    users: 0,
    ...(release === undefined ? {} : { release }),
  }
}

/** The message to show for a bad picker value, or null when the value is acceptable. */
export function validateInput(
  input: ConditionInput,
  value: InputValue | undefined
): string | null {
  switch (input.type) {
    case "count": {
      const min = input.min ?? 1
      if (typeof value !== "number" || !Number.isInteger(value) || value < min) {
        return `Enter a whole number of ${min} or more`
      }
      if (input.max !== undefined && value > input.max) {
        return `Enter ${input.max} or fewer`
      }
      return null
    }
    case "duration":
      return typeof value === "number" && Number.isFinite(value) && value > 0
        ? null
        : "Enter a length of time above zero"
    case "choice":
      return typeof value === "string" && input.options.includes(value)
        ? null
        : "Choose one"
    case "text":
      return typeof value === "string" && value.trim() !== ""
        ? null
        : "Enter a value"
  }
}

function kindOf(model: StatusModel, id: string): ConditionKind | undefined {
  return model.kinds.find((kind) => kind.id === id)
}

/** The group whose condition the record currently holds. */
export function holdGroup(
  record: StatusRecord,
  model: StatusModel
): StatusGroup | undefined {
  const kind = record.hold ? kindOf(model, record.hold.kind) : undefined
  return kind ? model.groups.find((group) => group.id === kind.group) : undefined
}

/** What the primary half of a group's split button does for these records: undo, or apply the primary condition. */
export function primaryEvent(
  records: StatusRecord[],
  group: StatusGroup,
  model: StatusModel
): StatusEvent {
  const allHold =
    records.length > 0 &&
    records.every((record) => holdGroup(record, model)?.id === group.id)
  return allHold
    ? { type: "clear" }
    : { type: "choose", kind: group.primary }
}

/** The condition's own wording for the row's second line, or null with no known hold. */
export function holdText(
  record: StatusRecord,
  model: StatusModel,
  now: number
): string | null {
  if (!record.hold) return null
  const kind = kindOf(model, record.hold.kind)
  if (!kind) return null
  return kind.describe?.(record.hold, { now, record }) ?? kind.label
}

function sameData(a: HoldData, b: HoldData): boolean {
  const keys = Object.keys(b)
  return keys.every((key) => a[key] === b[key])
}

function withoutHold(record: StatusRecord): StatusRecord {
  const copy = { ...record }
  delete copy.hold
  return copy
}

function moved(
  record: StatusRecord,
  to: string,
  reason: string,
  now: number
): { record: StatusRecord; transition: Transition } {
  const transition: Transition = { at: now, from: record.state, to, reason }
  return {
    record: { ...withoutHold(record), state: to, since: now, last: transition },
    transition,
  }
}

function choose(
  record: StatusRecord,
  event: Extract<StatusEvent, { type: "choose" }>,
  model: StatusModel,
  now: number
) {
  const kind = kindOf(model, event.kind)
  if (!kind) throw new Error(`Unknown condition: ${event.kind}`)
  let value = event.value
  if (kind.input) {
    if (typeof value === "string" && kind.input.type === "text") {
      value = value.trim()
    }
    const problem = validateInput(kind.input, value)
    if (problem) throw new RangeError(problem)
  } else {
    value = undefined
  }
  const base = withoutHold(record)
  const hold: Hold = {
    kind: kind.id,
    at: now,
    ...(value === undefined ? {} : { value }),
    data: kind.start?.(value, { now, record: base }) ?? {},
  }
  const reason = kind.describe?.(hold, { now, record: base }) ?? kind.label
  const transition: Transition = {
    at: now,
    from: record.state,
    to: kind.enters,
    reason,
  }
  return {
    record: { ...base, state: kind.enters, since: now, hold, last: transition },
    transition,
  }
}

/**
 * Returns the next status for one event, and the transition when the state
 * changed or a condition was chosen or cleared. Pure: `now` is a parameter, and
 * the same record object comes back when nothing changed, so callers can compare
 * references and skip the write. Throws on a `choose` for an unknown condition or
 * with a value its input rejects; check with `validateInput` first.
 */
export function nextStatus(
  record: StatusRecord,
  event: StatusEvent,
  model: StatusModel,
  now: number
): { record: StatusRecord; transition: Transition | null } {
  if (event.type === "choose") return choose(record, event, model, now)
  if (event.type === "clear") {
    if (!record.hold && record.state === model.open) {
      return { record, transition: null }
    }
    return moved(record, model.open, "Reopened", now)
  }

  let next = record
  if (event.type === "occurrence") {
    const count = Math.max(0, Math.floor(event.count ?? 1))
    const users = Math.max(0, Math.floor(event.newUsers ?? 0))
    if (count > 0 || users > 0) {
      next = {
        ...next,
        occurrences: next.occurrences + count,
        users: next.users + users,
      }
    }
  }
  if (
    event.type === "release" &&
    (next.release === undefined ||
      compareReleases(event.version, next.release) > 0)
  ) {
    next = { ...next, release: event.version }
  }

  const hold = next.hold
  const kind = hold ? kindOf(model, hold.kind) : undefined
  if (!hold || !kind?.watch) return { record: next, transition: null }

  const verdict = kind.watch(hold, event, { now, record: next })
  if (verdict?.trip) {
    const to = kind.trips ?? model.open
    const reason = verdict.reason ?? `${kind.label}: condition met`
    return moved(next, to, reason, now)
  }
  if (verdict?.data && !sameData(hold.data, verdict.data)) {
    next = {
      ...next,
      hold: { ...hold, data: { ...hold.data, ...verdict.data } },
    }
  }
  return { record: next, transition: null }
}
