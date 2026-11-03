export type ReplayEvent = {
  id: string
  /** Milliseconds from the start of the replay. */
  at: number
  /** "click", "navigation" and "error" get marks on the lane; any string may feed a tab. */
  kind: string
  label: string
  detail?: string
  tone?: "error"
  /** Click position as percent of the frame; moves the cursor. */
  point?: { x: number; y: number }
}

export type ReplaySnapshot<S = unknown> = {
  id: string
  at: number
  url: string
  state: S
}

export type ReplayRecording<S = unknown> = {
  id: string
  user: string
  meta?: string
  whenLabel?: string
  durationMs: number
  snapshots: ReplaySnapshot<S>[]
  events: ReplayEvent[]
}

export type ReplayTab = {
  id: string
  label: string
  kinds: string[]
  emptyTitle?: string
  emptyDescription?: string
}

export type ReplayMarker = {
  id: string
  kind: string
  at: number
  percent: number
}
