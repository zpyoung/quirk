import type { LucideIcon } from "lucide-react"

export type TimelineLevel = "debug" | "info" | "warning" | "error"

export type TimelineOrder = "newest" | "oldest"

export type TimelineEntry = {
  id: string
  /** Milliseconds. Entries and the playhead share one scale; the host decides what zero means. */
  time: number
  /** Key into the `types` prop; also what the type filter lists. */
  type: string
  category: string
  level: TimelineLevel
  message: string
  /** Optional second line in the data font, such as a path or selector. */
  detail?: string
  /** Marks the failing moment: it gets the error look and a rule on its older side. */
  isError?: boolean
}

export type TimelineType = {
  label: string
  icon: LucideIcon
  /** Picks `--chart-<tone>` for the icon circle; plain muted when omitted. */
  tone?: 1 | 2 | 3 | 4 | 5
}

export type TimelineFilter = { query: string; type: string | null }

export type TimelineRow =
  | { kind: "entry"; entry: TimelineEntry; after: boolean; current: boolean }
  | { kind: "playhead"; time: number }
