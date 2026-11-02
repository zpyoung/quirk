import type { Draft, PostResult } from '../types'

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
   * Whether `value` still needs saving for `stepId`. The first value seen for a step is the restored state
   * and is never saved; after that only content that differs from the last one the server settled is.
   */
  wants(stepId: string, value: Draft): boolean
  /**
   * Saves `value` through `post` and records it as settled only when the server took it (`ok`) or the step
   * had already moved on (`superseded`, which retrying cannot fix). An `error` leaves the draft pending, so
   * `wants` stays true for it until a later save succeeds.
   */
  save(stepId: string, value: Draft, post: (stepId: string, value: Draft) => Promise<PostResult>): Promise<PostResult>
}

export function createDraftGate(): DraftGate {
  let stepId: string | null = null
  let last: string | null = null
  let issued = 0
  return {
    wants(id, value) {
      if (id !== stepId) {
        stepId = id
        last = draftKey(value)
        return false
      }
      return draftKey(value) !== last
    },
    async save(id, value, post) {
      issued += 1
      const ticket = issued
      const result = await post(id, value)
      // a later save for the same gate owns the settled state, and a save for a step the form left is moot
      if (result !== 'error' && ticket === issued && id === stepId) last = draftKey(value)
      return result
    },
  }
}

const RETRY_BASE_MS = 1000
const RETRY_CAP_MS = 16_000

/** Wait before retrying a draft save after `failures` consecutive failures (1-based): 1 s doubling to a 16 s cap. */
export function retryDelay(failures: number): number {
  return Math.min(RETRY_CAP_MS, RETRY_BASE_MS * 2 ** Math.max(0, failures - 1))
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
