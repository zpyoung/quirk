import { useCallback, useEffect, useRef, useState } from 'react'
import type { Boot, PostResult, Snapshot } from './types'

export const POLL_MS = 1000
export const BACKOFF_CAP_MS = 5000
export const FAILURES_BEFORE_PAUSE = 3
const POST_RETRIES = 3

/** Posts one event, retrying network errors with the same client_id so the server can dedupe. */
export async function postEvent(
  boot: Boot,
  type: string,
  payload: Record<string, unknown>,
  scope: { nonce?: string; step?: string } = {},
): Promise<PostResult> {
  const body = JSON.stringify({
    client_id: crypto.randomUUID(),
    type,
    ...(scope.nonce ? { nonce: scope.nonce } : {}),
    ...(scope.step ? { step: scope.step } : {}),
    payload,
  })
  for (let attempt = 0; attempt <= POST_RETRIES; attempt += 1) {
    try {
      const response = await fetch('/_quirk/app/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Quirk-Token': boot.token },
        body,
      })
      if (response.status === 409) return 'superseded'
      return response.ok ? 'ok' : 'error'
    } catch {
      if (attempt === POST_RETRIES) return 'error'
      await new Promise((resolve) => setTimeout(resolve, 200 * (attempt + 1)))
    }
  }
  return 'error'
}

const recoveredListeners = new Set<() => void>()

/** Calls `listener` each time the snapshot feed succeeds after failing; returns the unsubscribe function. */
export function onTransportRecovered(listener: () => void): () => void {
  recoveredListeners.add(listener)
  return () => {
    recoveredListeners.delete(listener)
  }
}

export function backoffDelay(failures: number): number {
  if (failures < FAILURES_BEFORE_PAUSE) return POLL_MS
  return Math.min(BACKOFF_CAP_MS, POLL_MS * 2 ** (failures - FAILURES_BEFORE_PAUSE + 1))
}

export interface SnapshotFeed {
  snapshot: Snapshot | null
  paused: boolean
  /** Fetches immediately, for a superseded step or a tab that just became visible. */
  refresh(): void
}

/** Polls the snapshot route: every second, at once on becoming visible, and with capped backoff after repeated failures. */
export function useSnapshotFeed(enabled: boolean): SnapshotFeed {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [paused, setPaused] = useState(false)
  const rev = useRef<string>('')
  const failures = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inFlight = useRef(false)
  const alive = useRef(true)
  const pollRef = useRef<() => Promise<void>>(async () => {})

  const schedule = useCallback((delay: number) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => void pollRef.current(), delay)
  }, [])

  pollRef.current = async () => {
    if (!alive.current || inFlight.current) return
    inFlight.current = true
    try {
      const response = await fetch(`/_quirk/app/snapshot?rev=${encodeURIComponent(rev.current)}`, { cache: 'no-store' })
      if (!alive.current) return
      if (response.status === 200) {
        const next = (await response.json()) as Snapshot
        rev.current = String(next.rev)
        setSnapshot(next)
      } else if (response.status !== 204) {
        throw new Error(`snapshot returned ${response.status}`)
      }
      const recovered = failures.current > 0
      failures.current = 0
      setPaused(false)
      if (recovered) for (const listener of [...recoveredListeners]) listener()
    } catch {
      if (!alive.current) return
      failures.current += 1
      if (failures.current >= FAILURES_BEFORE_PAUSE) setPaused(true)
    } finally {
      inFlight.current = false
      if (alive.current) schedule(backoffDelay(failures.current))
    }
  }

  const refresh = useCallback(() => {
    clearTimeout(timer.current)
    void pollRef.current()
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    alive.current = true
    void pollRef.current()
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive.current = false
      clearTimeout(timer.current)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [enabled, refresh])

  return { snapshot, paused, refresh }
}
