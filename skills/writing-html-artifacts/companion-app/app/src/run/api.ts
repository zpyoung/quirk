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

export type OpenInOrcaResult =
  | { kind: 'opened'; action: 'switched' | 'created' }
  | { kind: 'failed'; message: string }

const OPEN_ERRORS: Record<number, string> = {
  403: 'This tab is no longer allowed to do that. Reload the page.',
  409: 'This run has been replaced. Reload the page.',
  404: 'This task has no worktree to open.',
  410: 'That worktree no longer exists.',
}

/** Asks the server to open the task's worktree in Orca; every failure comes back as a plain-words message. */
export async function openInOrca(
  boot: Boot,
  runId: string,
  task: string,
  fetchImpl: typeof fetch = defaultFetch,
): Promise<OpenInOrcaResult> {
  try {
    const response = await fetchImpl('/_quirk/run/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Quirk-Token': boot.token },
      body: JSON.stringify({ run_id: runId, task }),
    })
    const body = await readJson(response)
    if (response.status === 200 && (body?.action === 'switched' || body?.action === 'created')) {
      return { kind: 'opened', action: body.action }
    }
    if (response.status === 503) return { kind: 'failed', message: "Orca isn't installed or isn't on the PATH." }
    if (response.status === 502) {
      const detail = typeof body?.detail === 'string' && body.detail ? ` (${body.detail})` : ''
      return { kind: 'failed', message: `Orca couldn't open it. Is Orca running?${detail}` }
    }
    return { kind: 'failed', message: OPEN_ERRORS[response.status] ?? 'Could not open it in Orca.' }
  } catch {
    return { kind: 'failed', message: 'Could not reach the companion server. Check the connection and try again.' }
  }
}
