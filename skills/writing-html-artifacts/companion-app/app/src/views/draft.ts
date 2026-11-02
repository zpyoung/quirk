import type { Draft } from '../types'

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, v]) => v !== undefined)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, v]) => [k, canonical(v)]),
    )
  }
  return value
}

/** The draft's content as a string that is equal exactly when the content is equal, whatever the object identity or key order. */
export function draftKey(value: Draft): string {
  return JSON.stringify(canonical(value))
}

export interface DraftGate {
  /**
   * Whether `value` is worth posting for `stepId`. The first value seen for a step is the restored state
   * and is never posted; after that only content that differs from the last one posted is.
   */
  wants(stepId: string, value: Draft): boolean
  /** Records that `value` was posted for `stepId`. */
  sent(stepId: string, value: Draft): void
}

export function createDraftGate(): DraftGate {
  let stepId: string | null = null
  let last: string | null = null
  return {
    wants(id, value) {
      if (id !== stepId) {
        stepId = id
        last = draftKey(value)
        return false
      }
      return draftKey(value) !== last
    },
    sent(id, value) {
      stepId = id
      last = draftKey(value)
    },
  }
}

/** The pick saved in `draft`, only when it names one of `ids`; otherwise nothing is selected. */
export function restorePick(draft: Draft | null | undefined, ids: readonly string[]): string {
  const pick = draft?.pick
  return typeof pick === 'string' && ids.includes(pick) ? pick : ''
}

/** The draft for a view with one pick and a comment; an empty pick is left out. */
export function pickDraft(pick: string, comment: string): Draft {
  return pick ? { answers: {}, comment, pick } : { answers: {}, comment }
}
