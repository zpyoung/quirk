/** Bars for a histogram drawn in a 100 by 24 viewBox; every non-zero value gets a visible bar. */
export function trendBars(values: number[]): {
  peak: number
  bars: Array<{ x: number; width: number; height: number }>
} {
  const peak = values.reduce((max, value) => Math.max(max, value), 0)
  if (values.length === 0) return { peak, bars: [] }
  const slot = 100 / values.length
  const bars = values.map((value, index) => ({
    x: index * slot + slot * 0.15,
    width: slot * 0.7,
    height: value <= 0 || peak <= 0 ? 0 : Math.max(1, (value / peak) * 24),
  }))
  return { peak, bars }
}

/** Short count for a table cell: 999, 1.1K, 21K, 1.2M. */
export function formatCount(value: number): string {
  const n = Math.max(0, Math.round(value))
  if (n < 1000) return String(n)
  const units: Array<[string, number]> = [
    ["M", 1_000_000],
    ["K", 1000],
  ]
  for (const [suffix, size] of units) {
    if (n < size) continue
    const scaled = n / size
    const rounded =
      scaled < 10 ? Math.round(scaled * 10) / 10 : Math.round(scaled)
    if (suffix === "K" && rounded >= 1000) return "1M"
    return `${rounded}${suffix}`
  }
  return String(n)
}
