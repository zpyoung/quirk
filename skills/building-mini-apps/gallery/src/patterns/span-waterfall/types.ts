export type Span = {
  id: string
  parentId: string | null
  op: string
  description: string
  start: number
  duration: number
  errors?: string[]
  attributes?: Record<string, string>
}

export type WaterfallStat = {
  label: string
  value: string
  tone?: "default" | "bad"
}

export type WaterfallMarker = { label: string; at: number }

export type TreeRow = {
  span: Span
  depth: number
  childCount: number
  expanded: boolean
  isLast: boolean
  guides: boolean[]
  parentId: string | null
}

export type ScaleGap = { from: number; to: number; at: number; width: number }

export type ScaleTick = { t: number; at: number; label: string }

export type Scale = {
  origin: number
  end: number
  duration: number
  hidden: number
  position: (t: number) => number
  gaps: ScaleGap[]
  ticks: ScaleTick[]
}

export type Palette = ReadonlyMap<string, number>
