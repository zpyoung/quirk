import { format, isToday, isTomorrow } from "date-fns"

import type { TimelineEvent } from "./types"

export function clock(at: number): string {
  return format(at, "HH:mm")
}

export function exactTime(at: number): string {
  return format(at, "d MMM yyyy, HH:mm:ss")
}

/** Compact age such as "3 h" or "2 d"; anything under a minute reads "under a minute". */
export function ageText(ms: number): string {
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return "under a minute"
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} h`
  return `${Math.floor(hours / 24)} d`
}

function untilText(until: number): string {
  if (isToday(until)) return clock(until)
  if (isTomorrow(until)) return `tomorrow ${clock(until)}`
  return format(until, "EEE d MMM HH:mm")
}

export function eventText(event: TimelineEvent): string {
  switch (event.type) {
    case "opened":
      return "Opened"
    case "flagged-again":
      return "Flagged again"
    case "acknowledged":
      return "Acknowledged"
    case "snoozed": {
      const until =
        event.until === undefined ? "" : ` until ${untilText(event.until)}`
      return `Snoozed${until}${event.note ? `, ${event.note}` : ""}`
    }
    case "snooze-ended":
      return "Snooze ended"
    case "cleared":
      return event.text ?? "Cleared"
    case "resolved":
      return "Resolved"
    case "reopened":
      return "Reopened"
  }
}
