/** Formats "N/M" (or a two-number array or {done,total}) progress as "N of M"; anything else is shown as given. */
export function formatProgress(progress: unknown): string | null {
  if (progress === null || progress === undefined || progress === '') return null
  if (typeof progress === 'string') {
    const match = /^\s*(\d+)\s*(?:\/|of)\s*(\d+)\s*$/.exec(progress)
    return match ? `${match[1]} of ${match[2]}` : progress
  }
  if (Array.isArray(progress) && progress.length === 2) return `${progress[0]} of ${progress[1]}`
  if (typeof progress === 'object') {
    const { done, total } = progress as { done?: unknown; total?: unknown }
    if (typeof done === 'number' && typeof total === 'number') return `${done} of ${total}`
  }
  return String(progress)
}

/** Parses a start time given as ISO text or epoch seconds or milliseconds; null when it is not a time. */
export function startedAtMs(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value < 1e11 ? value * 1000 : value
  if (typeof value === 'string' && value) {
    const parsed = Date.parse(value)
    if (!Number.isNaN(parsed)) return parsed
    const numeric = Number(value)
    if (Number.isFinite(numeric)) return numeric < 1e11 ? numeric * 1000 : numeric
  }
  return null
}

export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return minutes ? `${minutes}m ${String(seconds).padStart(2, '0')}s` : `${seconds}s`
}

/** Drops a trailing "(Recommended)" an agent typed into a label, since the shell shows its own Recommended tag. */
export function stripRecommended(label: string): string {
  return label.replace(/\s*\(recommended\)\s*$/i, '')
}
