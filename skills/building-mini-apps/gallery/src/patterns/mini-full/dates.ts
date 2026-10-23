export const WEEKDAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"]

const pad = (n: number) => String(n).padStart(2, "0")

export function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

export function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n, d.getHours(), d.getMinutes())
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

/** Same day-of-month `n` months away, clamped to the target month's last day. */
export function addMonths(d: Date, n: number): Date {
  const first = new Date(d.getFullYear(), d.getMonth() + n, 1)
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate()
  return new Date(first.getFullYear(), first.getMonth(), Math.min(d.getDate(), last))
}

export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function isSameDay(a: Date, b: Date): boolean {
  return dayKey(a) === dayKey(b)
}

export function isSameMonth(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
}

/** Six Monday-first weeks (42 days) covering `month`. */
export function monthDays(month: Date): Date[] {
  const first = startOfMonth(month)
  const offset = (first.getDay() + 6) % 7
  return Array.from({ length: 42 }, (_, i) =>
    new Date(first.getFullYear(), first.getMonth(), 1 - offset + i)
  )
}

export function formatTime(d: Date): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function formatMonth(d: Date): string {
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" })
}

export function formatDayLong(d: Date): string {
  return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" })
}

export function formatDayShort(d: Date): string {
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
}

/** All-day means local midnight with no end, or an end at or past the next midnight. */
export function isAllDay(start: Date, end: Date | undefined): boolean {
  if (start.getHours() !== 0 || start.getMinutes() !== 0) return false
  return !end || end.getTime() >= addDays(startOfDay(start), 1).getTime()
}

/** Date header such as "TODAY 10/22", "TOMORROW 10/23" or "FRI 10/24". */
export function formatHeader(d: Date, now: Date): string {
  const md = `${d.getMonth() + 1}/${d.getDate()}`
  const diff = Math.round((startOfDay(d).getTime() - startOfDay(now).getTime()) / 86_400_000)
  if (diff === 0) return `TODAY ${md}`
  if (diff === 1) return `TOMORROW ${md}`
  return `${d.toLocaleDateString(undefined, { weekday: "short" }).toUpperCase()} ${md}`
}
