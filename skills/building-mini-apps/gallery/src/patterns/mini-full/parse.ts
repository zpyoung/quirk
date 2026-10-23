import { addDays, startOfDay } from "./dates"

export type ParsedEntry = {
  title: string
  start?: Date
  end?: Date
  allDay: boolean
  tag?: string
  matches: { field: "when" | "tag"; from: number; to: number }[]
}

const WEEKDAYS: [RegExp, number][] = [
  [/^sun/, 0],
  [/^mon/, 1],
  [/^tue/, 2],
  [/^wed/, 3],
  [/^thu/, 4],
  [/^fri/, 5],
  [/^sat/, 6],
]

const TAG = /(?<=^|\s)\/([a-z][\w-]*)/gi
const TIME_RANGE =
  /(?<![\w:/])(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\w:/])/i
const TIME_AT = /(?<![\w:/])at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\w:/])/i
const TIME_MERIDIEM = /(?<![\w:/])(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?![\w:/])/i
const DATE_MD = /(?<![\w/])(?:on\s+)?(\d{1,2})\/(\d{1,2})(?:\/(\d{4}|\d{2}))?(?![\w/])/i
const DATE_WORD =
  /(?<!\w)(?:on\s+|next\s+)?(today|tomorrow|tmrw|sunday|sun|monday|mon|tuesday|tues|tue|wednesday|wed|thursday|thurs|thur|thu|friday|fri|saturday|sat)(?!\w)/i

type Range = { from: number; to: number }

function hourOf(h: number, meridiem: string | undefined): number | undefined {
  if (h > 23) return undefined
  const m = meridiem?.toLowerCase()
  if (m) {
    if (h < 1 || h > 12) return undefined
    return (h % 12) + (m === "pm" ? 12 : 0)
  }
  // a bare 1-6 reads as afternoon ("3-4"), 7-12 as morning
  return h >= 1 && h <= 6 ? h + 12 : h
}

function claim(masked: string, range: Range): string {
  return masked.slice(0, range.from) + "\u0001".repeat(range.to - range.from) + masked.slice(range.to)
}

function rangeOf(m: RegExpExecArray): Range {
  return { from: m.index, to: m.index + m[0].length }
}

/**
 * Reads a date, a time or time range, and a `/tag` out of free text. Text in
 * double quotes is never parsed. A time without a date means today; neither
 * means `start` is undefined. `end` is only set when the text gives one.
 */
export function parseEntry(text: string, now: Date = new Date(), tags?: string[]): ParsedEntry {
  let work = text.replace(/"[^"]*"/g, (q) => "\u0000".repeat(q.length))
  const matches: ParsedEntry["matches"] = []
  const claimed: Range[] = []
  const take = (range: Range, field: "when" | "tag") => {
    claimed.push(range)
    matches.push({ field, ...range })
    work = claim(work, range)
  }

  let tag: string | undefined
  for (const m of work.matchAll(TAG)) {
    const name = m[1].toLowerCase()
    if (tags && tags.length > 0 && !tags.some((t) => t.toLowerCase() === name)) continue
    tag = tags?.find((t) => t.toLowerCase() === name) ?? name
    take(rangeOf(m), "tag")
    break
  }

  let minutes: { start: number; end?: number } | undefined
  const range = TIME_RANGE.exec(work)
  if (range) {
    const startMer = range[3] ?? range[6]
    const endMer = range[6] ?? range[3]
    const h1 = hourOf(Number(range[1]), startMer)
    const h2 = hourOf(Number(range[4]), endMer)
    const m1 = Number(range[2] ?? 0)
    const m2 = Number(range[5] ?? 0)
    if (h1 !== undefined && h2 !== undefined && m1 < 60 && m2 < 60) {
      let end: number | undefined = h2 * 60 + m2
      const start = h1 * 60 + m1
      if (end <= start) end += 12 * 60
      if (end <= start || end > 24 * 60) end = undefined
      minutes = { start, end }
      take(rangeOf(range), "when")
    }
  }
  if (!minutes) {
    const single = TIME_AT.exec(work) ?? TIME_MERIDIEM.exec(work)
    if (single) {
      const h = hourOf(Number(single[1]), single[3])
      const min = Number(single[2] ?? 0)
      if (h !== undefined && min < 60) {
        minutes = { start: h * 60 + min }
        take(rangeOf(single), "when")
      }
    }
  }

  const today = startOfDay(now)
  let day: Date | undefined
  const md = DATE_MD.exec(work)
  if (md) {
    const month = Number(md[1])
    const date = Number(md[2])
    let year = today.getFullYear()
    if (md[3]) year = md[3].length === 2 ? 2000 + Number(md[3]) : Number(md[3])
    let candidate = new Date(year, month - 1, date)
    const valid = (d: Date) => d.getMonth() === month - 1 && d.getDate() === date
    if (valid(candidate)) {
      if (!md[3] && candidate < today) candidate = new Date(year + 1, month - 1, date)
      if (valid(candidate)) {
        day = candidate
        take(rangeOf(md), "when")
      }
    }
  }
  if (!day) {
    const word = DATE_WORD.exec(work)
    if (word) {
      const w = word[1].toLowerCase()
      if (w === "today") day = today
      else if (w === "tomorrow" || w === "tmrw") day = addDays(today, 1)
      else {
        const target = WEEKDAYS.find(([re]) => re.test(w))![1]
        day = addDays(today, ((target - today.getDay() + 6) % 7) + 1)
      }
      take(rangeOf(word), "when")
    }
  }

  if (!day && minutes) day = today

  const title = text
    .split("")
    .map((ch, i) => (claimed.some((r) => i >= r.from && i < r.to) ? " " : ch))
    .join("")
    .replace(/"/g, "")
    .replace(/\s+/g, " ")
    .trim()

  if (!day) return { title, allDay: true, tag, matches }
  if (!minutes) return { title, start: day, allDay: true, tag, matches }

  const at = (m: number) => new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, m)
  return {
    title,
    start: at(minutes.start),
    end: minutes.end === undefined ? undefined : at(minutes.end),
    allDay: false,
    tag,
    matches,
  }
}

/** Fills the default length for a timed entry that gave a start and no end. */
export function withDefaultEnd(entry: ParsedEntry, minutes: number): ParsedEntry {
  if (entry.allDay || !entry.start || entry.end) return entry
  return { ...entry, end: new Date(entry.start.getTime() + minutes * 60_000) }
}
