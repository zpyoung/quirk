import type { RunView } from './types'

export interface NodeBox {
  id: string
  x: number
  y: number
  w: number
  h: number
  level: number
  chain?: string
}

/** `d` is an SVG path; `joined` marks same-chain neighbours drawn as a link glyph between touching cards. */
export interface EdgePath {
  from: string
  to: string
  kind: 'dep' | 'order'
  d: string
  joined: boolean
}

export interface GraphLayout {
  nodes: NodeBox[]
  edges: EdgePath[]
  width: number
  height: number
}

export interface LayoutOptions {
  nodeW?: number
  nodeH?: number
  colGap?: number
  rowGap?: number
}

const PAD = 24

/** A column cell: one task, or the run of same-chain tasks that must stay stacked and touching. */
interface Unit {
  ids: string[]
  plan: number
  y: number
}

const round = (n: number) => Math.round(n * 100) / 100

/**
 * Lays the run out as columns by level. Chain members stack with no gap in chain order; other rows are ordered
 * by two barycenter sweeps over dependency edges, ties broken by plan order. Pure and deterministic.
 */
export function layoutRun(run: RunView, opts: LayoutOptions = {}): GraphLayout {
  const w = opts.nodeW ?? 230
  const h = opts.nodeH ?? 96
  const colGap = opts.colGap ?? 90
  const rowGap = opts.rowGap ?? 28

  const plan = new Map(run.tasks.map((task, index) => [task.id, index]))
  const levels = [...new Set(run.tasks.map((task) => task.level))].sort((a, b) => a - b)
  const columnOf = new Map(levels.map((level, index) => [level, index]))
  const taskColumn = new Map(run.tasks.map((task) => [task.id, columnOf.get(task.level) ?? 0]))

  const chainRank = new Map<string, number>()
  for (const chain of run.chains) chain.tasks.forEach((id, index) => chainRank.set(id, index))
  const rankOf = (id: string) => chainRank.get(id) ?? plan.get(id) ?? 0

  const columns: Unit[][] = levels.map(() => [])
  const chainUnits = new Map<string, Unit>()
  for (const task of run.tasks) {
    const column = taskColumn.get(task.id) ?? 0
    const key = task.chain === undefined ? undefined : `${column}:${task.chain}`
    const existing = key === undefined ? undefined : chainUnits.get(key)
    if (existing) {
      existing.ids.push(task.id)
      continue
    }
    const unit: Unit = { ids: [task.id], plan: plan.get(task.id) ?? 0, y: 0 }
    if (key !== undefined) chainUnits.set(key, unit)
    columns[column].push(unit)
  }
  for (const unit of chainUnits.values()) {
    unit.ids.sort((a, b) => rankOf(a) - rankOf(b) || (plan.get(a) ?? 0) - (plan.get(b) ?? 0))
    unit.plan = Math.min(...unit.ids.map((id) => plan.get(id) ?? 0))
  }

  const unitHeight = (unit: Unit) => unit.ids.length * h
  const stack = (column: Unit[]) => {
    let y = 0
    for (const unit of column) {
      unit.y = y
      y += unitHeight(unit) + rowGap
    }
  }
  columns.forEach(stack)

  const deps = run.edges.filter((edge) => edge.kind === 'dep' && plan.has(edge.from) && plan.has(edge.to))
  const unitOf = new Map<string, Unit>()
  columns.forEach((column) => column.forEach((unit) => unit.ids.forEach((id) => unitOf.set(id, unit))))
  const centre = (id: string) => {
    const unit = unitOf.get(id)!
    return unit.y + unit.ids.indexOf(id) * h + h / 2
  }

  const sweep = (column: Unit[], neighbours: (id: string) => string[]) => {
    const key = new Map<Unit, number>()
    for (const unit of column) {
      const ys = unit.ids.flatMap((id) => neighbours(id).map(centre))
      key.set(unit, ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : unit.y + unitHeight(unit) / 2)
    }
    column.sort((a, b) => key.get(a)! - key.get(b)! || a.plan - b.plan)
    stack(column)
  }
  const before = (id: string) =>
    deps.filter((e) => e.to === id && (taskColumn.get(e.from) ?? 0) < (taskColumn.get(id) ?? 0)).map((e) => e.from)
  const after = (id: string) =>
    deps.filter((e) => e.from === id && (taskColumn.get(e.to) ?? 0) > (taskColumn.get(id) ?? 0)).map((e) => e.to)
  for (let c = 1; c < columns.length; c++) sweep(columns[c], before)
  for (let c = columns.length - 2; c >= 0; c--) sweep(columns[c], after)

  const colHeights = columns.map((column) => (column.length ? column[column.length - 1].y + unitHeight(column[column.length - 1]) : 0))
  const innerHeight = Math.max(0, ...colHeights)
  const boxes = new Map<string, NodeBox>()
  columns.forEach((column, c) => {
    const offset = (innerHeight - colHeights[c]) / 2
    for (const unit of column) {
      unit.ids.forEach((id, index) => {
        const task = run.tasks[plan.get(id)!]
        boxes.set(id, {
          id,
          x: PAD + c * (w + colGap),
          y: round(PAD + offset + unit.y + index * h),
          w,
          h,
          level: task.level,
          ...(task.chain === undefined ? {} : { chain: task.chain }),
        })
      })
    }
  })

  const edges: EdgePath[] = []
  for (const edge of run.edges) {
    const from = boxes.get(edge.from)
    const to = boxes.get(edge.to)
    if (!from || !to) continue
    edges.push({ from: edge.from, to: edge.to, kind: edge.kind, ...edgeGeometry(edge.kind, from, to) })
  }

  const nodes = run.tasks.map((task) => boxes.get(task.id)!)
  const columnsUsed = levels.length
  return {
    nodes,
    edges,
    width: columnsUsed === 0 ? PAD * 2 : PAD * 2 + columnsUsed * w + (columnsUsed - 1) * colGap,
    height: PAD * 2 + innerHeight,
  }
}

function edgeGeometry(kind: 'dep' | 'order', from: NodeBox, to: NodeBox): { d: string; joined: boolean } {
  const sameColumn = from.x === to.x
  if (kind === 'order' && sameColumn && from.chain !== undefined && from.chain === to.chain) {
    const upper = from.y <= to.y ? from : to
    const lower = upper === from ? to : from
    if (upper.y + upper.h === lower.y) {
      const cx = upper.x + upper.w / 2
      const seam = lower.y
      return { d: `M${round(cx - 6)},${round(seam - 3)} L${round(cx)},${round(seam + 3)} L${round(cx + 6)},${round(seam - 3)}`, joined: true }
    }
  }
  const y1 = from.y + from.h / 2
  const y2 = to.y + to.h / 2
  if (to.x >= from.x + from.w) {
    const x1 = from.x + from.w
    const x2 = to.x
    const dx = Math.max(24, (x2 - x1) / 2)
    return { d: `M${x1},${round(y1)} C${round(x1 + dx)},${round(y1)} ${round(x2 - dx)},${round(y2)} ${x2},${round(y2)}`, joined: false }
  }
  // target is not to the right (same column, not touching): loop out on the right side and back in
  const x1 = from.x + from.w
  const x2 = to.x + to.w
  const out = Math.max(from.x, to.x) + from.w + 36
  return { d: `M${x1},${round(y1)} C${out},${round(y1)} ${out},${round(y2)} ${x2},${round(y2)}`, joined: false }
}
