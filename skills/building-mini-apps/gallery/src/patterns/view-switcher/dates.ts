const ISO = /^\d{4}-\d{2}-\d{2}$/

export function isIsoDate(value: unknown): value is string {
  return typeof value === "string" && ISO.test(value)
}

export function toIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function fromIso(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number)
  return new Date(year, month - 1, day)
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function addMonths(date: Date, count: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + count, 1)
}

/** Six Sunday-first weeks covering `month`, so the grid never changes height. */
export function monthGrid(month: Date): Date[] {
  const first = startOfMonth(month)
  return Array.from(
    { length: 42 },
    (_, i) =>
      new Date(first.getFullYear(), first.getMonth(), 1 - first.getDay() + i)
  )
}

export function formatDay(iso: string): string {
  if (!isIsoDate(iso)) return iso
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
  }).format(fromIso(iso))
}

export function formatMonth(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
  }).format(date)
}

export function weekdayLabels(): string[] {
  const format = new Intl.DateTimeFormat(undefined, { weekday: "short" })
  return Array.from({ length: 7 }, (_, i) =>
    format.format(new Date(2024, 0, 7 + i))
  )
}
