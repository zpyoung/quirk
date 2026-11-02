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
   *
   * Saves for one step never overlap: while one is in flight a newer `save` only replaces the single pending
   * value, which is posted once the in-flight one settles and only if it still differs from what the server
   * last took. Every caller waiting on a step resolves with the result of the last post made for it.
   */
  save(stepId: string, value: Draft, post: DraftPost): Promise<PostResult>
}

type DraftPost = (stepId: string, value: Draft) => Promise<PostResult>

interface Pending {
  value: Draft
  post: DraftPost
  waiters: ((result: PostResult) => void)[]
}

export function createDraftGate(): DraftGate {
  let stepId: string | null = null
  let last: string | null = null
  const inFlight = new Map<string, { pending: Pending | null }>()

  async function drain(id: string, flight: { pending: Pending | null }, first: { value: Draft; post: DraftPost }): Promise<PostResult> {
    const waiters: ((result: PostResult) => void)[] = []
    let result: PostResult = 'error'
    try {
      let current = first
      for (;;) {
        result = await current.post(id, current.value)
        // a save for a step the form left is moot
        if (result !== 'error' && id === stepId) last = draftKey(current.value)
        const next = flight.pending
        flight.pending = null
        if (!next) break
        waiters.push(...next.waiters)
        if (result === 'superseded' || id !== stepId) break
        if (draftKey(next.value) === last) {
          result = 'ok'
          break
        }
        current = next
      }
      return result
    } finally {
      inFlight.delete(id)
      const rest = flight.pending as Pending | null
      if (rest) waiters.push(...rest.waiters)
      for (const resolve of waiters) resolve(result)
    }
  }

  return {
    wants(id, value) {
      if (id !== stepId) {
        stepId = id
        last = draftKey(value)
        return false
      }
      return draftKey(value) !== last
    },
    save(id, value, post) {
      const flight = inFlight.get(id)
      if (!flight) {
        const started = { pending: null as Pending | null }
        inFlight.set(id, started)
        return drain(id, started, { value, post })
      }
      return new Promise<PostResult>((resolve) => {
        const waiters = flight.pending ? [...flight.pending.waiters, resolve] : [resolve]
        flight.pending = { value, post, waiters }
      })
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
