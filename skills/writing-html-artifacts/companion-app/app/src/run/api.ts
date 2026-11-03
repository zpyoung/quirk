import type { Boot } from '../types'
import type { RunAnswer, RunDiff } from './types'

const POST_RETRIES = 3

export type RunPostResult =
  | { kind: 'ok' }
  | { kind: 'duplicate' }
  | { kind: 'refused'; reason: string }
  | { kind: 'answered'; answer: RunAnswer }
  | { kind: 'error' }

const defaultFetch: typeof fetch = (input, init) => fetch(input, init)

async function readJson(response: Response): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await response.json()
    return body && typeof body === 'object' ? (body as Record<string, unknown>) : null
  } catch {
    return null
  }
}

async function classify(response: Response): Promise<RunPostResult> {
  if (response.status === 204) return { kind: 'ok' }
  const body = await readJson(response)
  if (response.status === 200 && body?.duplicate === true) return { kind: 'duplicate' }
  if (response.status === 409 && body) {
    if (typeof body.refused === 'string') return { kind: 'refused', reason: body.refused }
    if (body.answered && typeof body.answered === 'object') return { kind: 'answered', answer: body.answered as RunAnswer }
  }
  return { kind: 'error' }
}

/** Posts one run event; network errors retry with the same client_id so the server can dedupe. */
export async function postRunEvent(
  boot: Boot,
  type: 'run-answer' | 'run-stop' | 'run-retry',
  payload: Record<string, unknown>,
  fetchImpl: typeof fetch = defaultFetch,
): Promise<RunPostResult> {
  const body = JSON.stringify({ client_id: crypto.randomUUID(), type, payload })
  for (let attempt = 0; attempt <= POST_RETRIES; attempt += 1) {
    try {
      const response = await fetchImpl('/_quirk/app/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Quirk-Token': boot.token },
        body,
      })
      return await classify(response)
    } catch {
      if (attempt === POST_RETRIES) return { kind: 'error' }
      await new Promise((resolve) => setTimeout(resolve, 200 * (attempt + 1)))
    }
  }
  return { kind: 'error' }
}

/** Fetches one task's diff; an unknown task, a missing run or any failure is null. */
export async function fetchDiff(task: string, fetchImpl: typeof fetch = defaultFetch): Promise<RunDiff | null> {
  try {
    const response = await fetchImpl(`/_quirk/run/diff?task=${encodeURIComponent(task)}`, { cache: 'no-store' })
    if (response.status !== 200) return null
    return (await response.json()) as RunDiff
  } catch {
    return null
  }
}
