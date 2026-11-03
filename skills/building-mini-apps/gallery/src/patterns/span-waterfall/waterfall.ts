import type { Palette, Scale, ScaleGap, Span, TreeRow } from "./types"

const GAP_SHARE = 0.05
const GAP_SHARE_CAP = 0.4
const TICK_TARGET = 5
const TICK_MIN_SPACING = 0.1
const GAP_LABEL_CLEARANCE = 0.05
const DEFAULT_GAP_FRACTION = 0.2
const NO_ROWS_HIDDEN: ReadonlySet<string> = new Set()

type Tree = {
  byId: Map<string, Span>
  roots: Span[]
  kids: Map<string, Span[]>
}

const lengthOf = (span: Span) => (span.duration > 0 ? span.duration : 0)
const startOf = (span: Span) => (Number.isFinite(span.start) ? span.start : 0)
const endOf = (span: Span) => startOf(span) + lengthOf(span)

/**
 * Parent links to a tree. A span whose parent is missing or itself becomes a
 * root, a duplicate ID keeps the first span, and a cycle is broken by promoting
 * its first span to a root, so every span appears exactly once.
 */
function buildTree(spans: Span[]): Tree {
  const byId = new Map<string, Span>()
  for (const span of spans) if (!byId.has(span.id)) byId.set(span.id, span)

  const raw = new Map<string, Span[]>()
  const roots: Span[] = []
  for (const span of byId.values()) {
    const parent = span.parentId
    if (parent !== null && parent !== span.id && byId.has(parent)) {
      raw.set(parent, [...(raw.get(parent) ?? []), span])
    } else {
      roots.push(span)
    }
  }
  const byStart = (a: Span, b: Span) => startOf(a) - startOf(b)
  roots.sort(byStart)
  for (const list of raw.values()) list.sort(byStart)

  const visited = new Set<string>()
  const kids = new Map<string, Span[]>()
  const visit = (span: Span) => {
    visited.add(span.id)
    const list: Span[] = []
    for (const child of raw.get(span.id) ?? []) {
      if (visited.has(child.id)) continue
      list.push(child)
      visit(child)
    }
    kids.set(span.id, list)
  }
  for (const root of roots) visit(root)
  for (const span of byId.values()) {
    if (!visited.has(span.id)) {
      roots.push(span)
      visit(span)
    }
  }
  return { byId, roots, kids }
}

/**
 * Visible rows in depth-first order, children in start order. `guides[level]`
 * says whether the indent line at that level continues below the row; the last
 * entry is the row's own elbow.
 */
export function flattenTree(spans: Span[], collapsed: ReadonlySet<string>): TreeRow[] {
  const { roots, kids } = buildTree(spans)
  const rows: TreeRow[] = []
  const walk = (span: Span, depth: number, lastFlags: boolean[], parentId: string | null) => {
    const children = kids.get(span.id) ?? []
    const expanded = children.length > 0 && !collapsed.has(span.id)
    rows.push({
      span,
      depth,
      childCount: children.length,
      expanded,
      isLast: depth === 0 ? true : lastFlags[depth - 1],
      guides: lastFlags.map((last) => !last),
      parentId,
    })
    if (!expanded) return
    children.forEach((child, index) =>
      walk(child, depth + 1, [...lastFlags, index === children.length - 1], span.id)
    )
  }
  roots.forEach((root) => walk(root, 0, [], null))
  return rows
}

/** IDs from the span's parent up to its root; empty for a root or an unknown ID. */
export function ancestorIds(spans: Span[], id: string): string[] {
  const { byId } = buildTree(spans)
  const out: string[] = []
  const seen = new Set<string>([id])
  let current = byId.get(id)
  while (current && current.parentId !== null && byId.has(current.parentId)) {
    if (seen.has(current.parentId)) break
    seen.add(current.parentId)
    out.push(current.parentId)
    current = byId.get(current.parentId)
  }
  return out
}

/** Earliest start and latest end across all spans; both 0 for no spans. */
export function traceBounds(spans: Span[]): { origin: number; end: number } {
  if (spans.length === 0) return { origin: 0, end: 0 }
  let origin = Infinity
  let end = -Infinity
  for (const span of spans) {
    origin = Math.min(origin, startOf(span))
    end = Math.max(end, endOf(span))
  }
  return { origin, end }
}

/**
 * Idle stretches longer than `thresholdMs` (default 20% of the trace): time
 * where no leaf span runs. A parent that covers the stretch does not fill it.
 */
export function findGaps(
  spans: Span[],
  thresholdMs?: number
): Array<{ from: number; to: number }> {
  const { origin, end } = traceBounds(spans)
  const threshold = thresholdMs ?? (end - origin) * DEFAULT_GAP_FRACTION
  const { byId, kids } = buildTree(spans)
  const leaves = [...byId.values()].filter((span) => (kids.get(span.id) ?? []).length === 0)
  const busy = (leaves.length > 0 ? leaves : [...byId.values()])
    .map((span) => ({ from: startOf(span), to: endOf(span) }))
    .sort((a, b) => a.from - b.from)
  if (busy.length === 0) return []

  const gaps: Array<{ from: number; to: number }> = []
  let cursor = origin
  for (const interval of busy) {
    if (interval.from - cursor > threshold) gaps.push({ from: cursor, to: interval.from })
    cursor = Math.max(cursor, interval.to)
  }
  if (end - cursor > threshold) gaps.push({ from: cursor, to: end })
  return gaps
}

function niceStep(raw: number): number {
  if (!(raw > 0)) return 1
  const power = 10 ** Math.floor(Math.log10(raw))
  const fraction = raw / power
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10
  return nice * power
}

type Segment = { kind: "time" | "gap"; from: number; to: number; at: number; width: number }

/**
 * Maps time to a 0..1 axis position. With `compress`, each idle gap found by
 * `findGaps` takes a fixed slice of the axis and the rest is shared by the
 * remaining time in proportion. Ticks are round values placed per visible
 * stretch and kept clear of each gap's label.
 */
export function createScale(
  spans: Span[],
  options: { gapThresholdMs?: number; compress?: boolean } = {}
): Scale {
  const { origin, end } = traceBounds(spans)
  const duration = end - origin
  const found = options.compress === false ? [] : findGaps(spans, options.gapThresholdMs)
  const hidden = found.reduce((sum, gap) => sum + (gap.to - gap.from), 0)
  const visible = duration - hidden
  const compressed = found.length > 0 && visible > 0

  const segments: Segment[] = []
  if (compressed) {
    const gapWidth = Math.min(GAP_SHARE, GAP_SHARE_CAP / found.length)
    const timeShare = 1 - found.length * gapWidth
    let cursor = origin
    let at = 0
    for (const gap of found) {
      if (gap.from > cursor) {
        const width = ((gap.from - cursor) / visible) * timeShare
        segments.push({ kind: "time", from: cursor, to: gap.from, at, width })
        at += width
      }
      segments.push({ kind: "gap", from: gap.from, to: gap.to, at, width: gapWidth })
      at += gapWidth
      cursor = gap.to
    }
    if (end > cursor) {
      segments.push({ kind: "time", from: cursor, to: end, at, width: ((end - cursor) / visible) * timeShare })
    }
  } else {
    segments.push({ kind: "time", from: origin, to: end, at: 0, width: 1 })
  }

  const position = (t: number): number => {
    if (duration <= 0) return 0
    const clamped = Math.min(end, Math.max(origin, t))
    const segment = segments.find((s) => clamped <= s.to) ?? segments[segments.length - 1]
    const length = segment.to - segment.from
    if (length <= 0) return segment.at
    return segment.at + ((clamped - segment.from) / length) * segment.width
  }

  const ticks: Scale["ticks"] = []
  if (duration <= 0) {
    ticks.push({ t: origin, at: 0, label: formatDuration(0) })
  } else {
    const step = niceStep((compressed ? visible : duration) / TICK_TARGET)
    const candidates: Array<{ t: number; at: number }> = []
    for (const segment of segments) {
      if (segment.kind !== "time") continue
      let k = Math.ceil((segment.from - origin) / step - 1e-9)
      for (let t = origin + k * step; t <= segment.to + 1e-9; t = origin + ++k * step) {
        candidates.push({ t, at: position(t) })
      }
    }
    candidates.sort((a, b) => a.at - b.at)
    const gapSegments = segments.filter((segment) => segment.kind === "gap")
    const nearGap = (at: number) =>
      gapSegments.some(
        (gap) => at > gap.at - GAP_LABEL_CLEARANCE && at < gap.at + gap.width + GAP_LABEL_CLEARANCE
      )
    let lastAt = -Infinity
    for (const candidate of candidates) {
      if (nearGap(candidate.at) || candidate.at - lastAt < TICK_MIN_SPACING) continue
      lastAt = candidate.at
      ticks.push({ ...candidate, label: formatDuration(candidate.t - origin) })
    }
  }

  const gaps: ScaleGap[] = segments
    .filter((s) => s.kind === "gap")
    .map(({ from, to, at, width }) => ({ from, to, at, width }))

  return { origin, end, duration, hidden: compressed ? hidden : 0, position, gaps, ticks }
}

/** Span IDs in tree order whose op, description, ID or an attribute value contains `query`. */
export function matchSpanIds(spans: Span[], query: string): string[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return []
  return flattenTree(spans, NO_ROWS_HIDDEN)
    .map((row) => row.span)
    .filter((span) =>
      [span.op, span.description, span.id, ...Object.values(span.attributes ?? {})].some((text) =>
        text.toLowerCase().includes(needle)
      )
    )
    .map((span) => span.id)
}

/** Duration minus the time covered by direct children, clipped to the span itself. */
export function selfTime(spans: Span[], id: string): number {
  const { byId, kids } = buildTree(spans)
  const span = byId.get(id)
  if (!span) return 0
  const from = startOf(span)
  const to = endOf(span)
  const covered = (kids.get(id) ?? [])
    .map((child) => ({ from: Math.max(from, startOf(child)), to: Math.min(to, endOf(child)) }))
    .filter((interval) => interval.to > interval.from)
    .sort((a, b) => a.from - b.from)
  let union = 0
  let cursor = from
  for (const interval of covered) {
    const begin = Math.max(cursor, interval.from)
    if (interval.to > begin) union += interval.to - begin
    cursor = Math.max(cursor, interval.to)
  }
  return Math.max(0, lengthOf(span) - union)
}

/** Op categories among a span's descendants as shares of their count, largest first, the tail folded into "Other". */
export function opShares(
  spans: Span[],
  id: string,
  top = 3
): Array<{ category: string; share: number }> {
  const { kids } = buildTree(spans)
  const counts = new Map<string, number>()
  let total = 0
  const walk = (parent: string) => {
    for (const child of kids.get(parent) ?? []) {
      const category = opCategory(child.op)
      counts.set(category, (counts.get(category) ?? 0) + 1)
      total += 1
      walk(child.id)
    }
  }
  walk(id)
  if (total === 0) return []
  const sorted = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const shown = sorted.slice(0, top).map(([category, count]) => ({ category, share: count / total }))
  const rest = sorted.slice(top).reduce((sum, [, count]) => sum + count, 0)
  return rest > 0 ? [...shown, { category: "Other", share: rest / total }] : shown
}

/** The part of an op before its first dot: "test.case" belongs to "test". */
export function opCategory(op: string): string {
  const head = op.trim().split(".")[0]
  return head || "other"
}

/** Chart token slot 1 to 5 per category, by first appearance in tree order, so a few categories never share a color. */
export function opPalette(spans: Span[]): Palette {
  const palette = new Map<string, number>()
  for (const { span } of flattenTree(spans, NO_ROWS_HIDDEN)) {
    const category = opCategory(span.op)
    if (!palette.has(category)) palette.set(category, (palette.size % 5) + 1)
  }
  return palette
}

/** "0ms", "28.2ms", "11.78s", "3m 20s". Negative and non-finite values read as 0. */
export function formatDuration(ms: number): string {
  const value = Number.isFinite(ms) && ms > 0 ? ms : 0
  const rounded = Number(value.toFixed(2))
  if (rounded < 1000) return `${rounded}ms`
  const seconds = Number((value / 1000).toFixed(2))
  if (seconds < 60) return `${seconds}s`
  let minutes = Math.floor(value / 60_000)
  let rest = Math.round((value - minutes * 60_000) / 1000)
  if (rest === 60) {
    minutes += 1
    rest = 0
  }
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`
}
