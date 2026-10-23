import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  applyItemAction,
  endExpiredSnoozes,
  evaluateRules,
  initialRuleMemory,
} from "./attention"
import type {
  AttentionItem,
  FlagRule,
  ItemAction,
  RefreshState,
  RuleMemory,
  Tile,
  TimelineEvent,
} from "./types"

const TICK_MS = 30_000
const DEFAULT_REFRESH_MS = 30_000

const toError = (cause: unknown) =>
  cause instanceof Error ? cause : new Error(String(cause))

/**
 * Per-item write lane: `confirmed` is the timeline last known to be stored and
 * `queued` holds the events of each write not yet settled, oldest first.
 */
type Lane = {
  confirmed: TimelineEvent[]
  queued: TimelineEvent[][]
  tail: Promise<void>
}

function timelineOf(lane: Lane): TimelineEvent[] {
  return [...lane.confirmed, ...lane.queued.flat()]
}

function reportWrite(what: string, cause: unknown) {
  toast.error(`Couldn't ${what}`, { description: toError(cause).message })
}

/**
 * Wires a command center to its data: opens, appends to and resolves items as
 * tiles change, returns snoozed items when their time passes, and runs the
 * optional refresh loop. Pass `tiles` and `items` together: rule memory is
 * seeded from the first non-empty `tiles`, so items must already be loaded then.
 * `rules` should be a stable array.
 */
export function useCommandCenter(opts: {
  tiles: Tile[]
  items: AttentionItem[]
  rules: FlagRule[]
  onTileUpdate: (id: string, patch: Partial<Tile>) => Promise<void>
  onItemAdd: (item: AttentionItem) => Promise<void>
  onItemUpdate: (
    id: string,
    patch: Pick<AttentionItem, "timeline">
  ) => Promise<void>
  onRefresh?: (
    signal: AbortSignal
  ) => Promise<Array<Pick<Tile, "id"> & Partial<Tile>>>
  refreshMs?: number
}): {
  now: number
  announcement: string
  refresh: RefreshState
  pause(): void
  resume(): void
  retry(): void
  act(itemId: string, action: ItemAction): void
} {
  const { tiles, items, rules, refreshMs = DEFAULT_REFRESH_MS } = opts
  const hasRefresh = opts.onRefresh !== undefined

  const [now, setNow] = useState(() => Date.now())
  const [announcement, setAnnouncement] = useState("")
  const [paused, setPaused] = useState(false)
  const [refresh, setRefresh] = useState<RefreshState>(() =>
    hasRefresh ? { state: "live", at: Date.now() } : { state: "none" }
  )

  const latest = useRef({ ...opts })
  const itemsRef = useRef(items)
  const lanes = useRef(new Map<string, Lane>())
  const pendingAdds = useRef(new Map<string, AttentionItem>())
  const announceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  )
  const memory = useRef<RuleMemory | null>(null)
  const evaluating = useRef(false)
  const dirty = useRef(false)
  const inflight = useRef<AbortController | null>(null)
  const applying = useRef(false)
  const lastSuccess = useRef<number | undefined>(undefined)

  useEffect(() => {
    latest.current = opts
  })
  const setTimeline = useCallback((id: string, timeline: TimelineEvent[]) => {
    itemsRef.current = itemsRef.current.map((candidate) =>
      candidate.id === id ? { ...candidate, timeline } : candidate
    )
  }, [])

  // props lag the writes in flight, so unsettled timelines and adds are laid back over each snapshot
  useEffect(() => {
    const unsaved: AttentionItem[] = []
    for (const added of pendingAdds.current.values()) {
      if (items.some((item) => item.id === added.id)) {
        pendingAdds.current.delete(added.id)
      } else {
        unsaved.push(added)
      }
    }
    itemsRef.current = [...items, ...unsaved].map((item) => {
      const lane = lanes.current.get(item.id)
      return lane ? { ...item, timeline: timelineOf(lane) } : item
    })
  }, [items])

  useEffect(
    () => () => {
      clearTimeout(announceTimer.current)
    },
    []
  )

  // one write at a time per item, each built on the last confirmed timeline, so a failed write drops only its own events
  const appendEvents = useCallback(
    (id: string, events: TimelineEvent[]): Promise<void> => {
      const item = itemsRef.current.find((candidate) => candidate.id === id)
      if (!item || events.length === 0) return Promise.resolve()
      let lane = lanes.current.get(id)
      if (!lane) {
        lane = {
          confirmed: item.timeline,
          queued: [],
          tail: Promise.resolve(),
        }
        lanes.current.set(id, lane)
      }
      const owner = lane
      owner.queued.push(events)
      setTimeline(id, timelineOf(owner))

      const write = owner.tail.then(async () => {
        const timeline = [...owner.confirmed, ...events]
        let failed = true
        try {
          await latest.current.onItemUpdate(id, { timeline })
          owner.confirmed = timeline
          failed = false
        } finally {
          owner.queued.shift()
          if (owner.queued.length === 0) lanes.current.delete(id)
          if (failed) setTimeline(id, timelineOf(owner))
        }
      })
      owner.tail = write.catch(() => undefined)
      return write
    },
    [setTimeline]
  )

  const announceReturned = useCallback((ids: string[]) => {
    const names = ids.map((id) => {
      const item = itemsRef.current.find((candidate) => candidate.id === id)
      const tile = latest.current.tiles.find(
        (candidate) => candidate.id === item?.tileId
      )
      return tile?.name ?? item?.title ?? ""
    })
    // blank first so a repeat of the same text is still a change the live region announces
    setAnnouncement("")
    clearTimeout(announceTimer.current)
    announceTimer.current = setTimeout(
      () => setAnnouncement(names.map((name) => `${name} is back`).join(". ")),
      100
    )
  }, [])

  const evaluate = useCallback(async () => {
    if (evaluating.current) {
      dirty.current = true
      return
    }
    evaluating.current = true
    try {
      do {
        dirty.current = false
        const current = latest.current
        if (current.tiles.length === 0) break
        const at = Date.now()
        memory.current = {
          ...initialRuleMemory(itemsRef.current, current.rules, current.tiles),
          ...memory.current,
        }
        const result = evaluateRules({
          tiles: current.tiles,
          items: itemsRef.current,
          rules: current.rules,
          previous: memory.current,
          now: at,
          newId: () => crypto.randomUUID(),
        })
        for (const item of result.add) pendingAdds.current.set(item.id, item)
        itemsRef.current = [...itemsRef.current, ...result.add]
        const writes: Array<{
          ruleId: string | undefined
          done: Promise<void>
        }> = [
          ...result.add.map((item) => ({
            ruleId: item.ruleId,
            done: current.onItemAdd(item).catch((cause: unknown) => {
              pendingAdds.current.delete(item.id)
              itemsRef.current = itemsRef.current.filter(
                (candidate) => candidate.id !== item.id
              )
              throw cause
            }),
          })),
          ...result.append.map(({ id, events }) => ({
            ruleId: itemsRef.current.find((candidate) => candidate.id === id)
              ?.ruleId,
            done: appendEvents(id, events),
          })),
        ]
        const outcomes = await Promise.allSettled(writes.map((w) => w.done))
        const next: RuleMemory = { ...result.memory }
        let failure: PromiseRejectedResult | undefined
        outcomes.forEach((outcome, index) => {
          if (outcome.status !== "rejected") return
          failure ??= outcome
          const ruleId = writes[index].ruleId
          if (ruleId === undefined) return
          // a rule whose write failed keeps its old memory so its edge fires again; siblings advance
          const kept = memory.current?.[ruleId]
          if (kept) next[ruleId] = kept
          else delete next[ruleId]
        })
        memory.current = next
        if (failure) reportWrite("update the needs-you queue", failure.reason)
      } while (dirty.current)
    } finally {
      evaluating.current = false
    }
  }, [appendEvents])

  useEffect(() => {
    void evaluate()
  }, [tiles, rules, now, evaluate])

  useEffect(() => {
    function tick() {
      const at = Date.now()
      setNow(at)
      const ended = endExpiredSnoozes(itemsRef.current, at)
      if (ended.length === 0) return
      announceReturned(ended.map(({ id }) => id))
      for (const { id, events } of ended) {
        appendEvents(id, events).catch((cause: unknown) =>
          reportWrite("return a snoozed item", cause)
        )
      }
    }
    const timer = setInterval(tick, TICK_MS)
    const onVisible = () => {
      if (document.visibilityState === "visible") tick()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [appendEvents, announceReturned])

  const runRefresh = useCallback(async () => {
    const onRefresh = latest.current.onRefresh
    if (!onRefresh || inflight.current || applying.current) return
    const controller = new AbortController()
    inflight.current = controller
    try {
      const patches = await onRefresh(controller.signal)
      if (controller.signal.aborted) return
      const at = Date.now()
      applying.current = true
      let failure: PromiseRejectedResult | undefined
      try {
        const outcomes = await Promise.allSettled(
          patches.map((patch) =>
            latest.current.onTileUpdate(patch.id, {
              ...patch,
              updatedAt: patch.updatedAt ?? at,
            })
          )
        )
        failure = outcomes.find(
          (outcome): outcome is PromiseRejectedResult =>
            outcome.status === "rejected"
        )
      } finally {
        applying.current = false
      }
      if (failure) {
        reportWrite("apply the refresh", failure.reason)
        if (controller.signal.aborted) return
        setRefresh({
          state: "stale",
          since: lastSuccess.current,
          error: toError(failure.reason),
        })
        return
      }
      if (controller.signal.aborted) return
      lastSuccess.current = at
      setRefresh({ state: "live", at })
    } catch (cause) {
      if (controller.signal.aborted) return
      setRefresh({
        state: "stale",
        since: lastSuccess.current,
        error: toError(cause),
      })
    } finally {
      if (inflight.current === controller) inflight.current = null
    }
  }, [])

  useEffect(() => {
    if (!hasRefresh || paused) return
    lastSuccess.current ??= Date.now()
    const first = setTimeout(() => void runRefresh(), 0)
    const timer = setInterval(() => void runRefresh(), refreshMs)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
      inflight.current?.abort()
      inflight.current = null
    }
  }, [hasRefresh, paused, refreshMs, runRefresh])

  const pause = useCallback(() => {
    if (!hasRefresh) return
    inflight.current?.abort()
    inflight.current = null
    setPaused(true)
    setRefresh({ state: "paused", at: lastSuccess.current })
  }, [hasRefresh])

  const resume = useCallback(() => {
    if (!hasRefresh) return
    setPaused(false)
    setRefresh({ state: "live", at: lastSuccess.current ?? Date.now() })
  }, [hasRefresh])

  const retry = useCallback(() => {
    void runRefresh()
  }, [runRefresh])

  const act = useCallback(
    (itemId: string, action: ItemAction) => {
      const item = itemsRef.current.find((candidate) => candidate.id === itemId)
      if (!item) return
      const at = Date.now()
      setNow(at)
      // an elapsed snooze ends before the action lands, so the next tick never has to find it
      const ended = endExpiredSnoozes([item], at).flatMap(
        ({ events }) => events
      )
      if (ended.length > 0) announceReturned([itemId])
      const settled = { ...item, timeline: [...item.timeline, ...ended] }
      appendEvents(itemId, [
        ...ended,
        ...applyItemAction(settled, action, at),
      ]).catch((cause: unknown) => reportWrite("save that change", cause))
    },
    [appendEvents, announceReturned]
  )

  return { now, announcement, refresh, pause, resume, retry, act }
}
