import type { RunEdge, RunView } from './types'

export interface NodeBox {
  id: string
  x: number
  y: number
  w: number
  h: number
  level: number
  chain?: string
}

/** `d` is an SVG path with rounded orthogonal corners; it leaves the source and enters the target on a straight horizontal run. */
export interface EdgePath {
  from: string
  to: string
  kind: 'dep' | 'order'
  d: string
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
  /** Space between columns; the room an edge has to turn between a source and a target. */
  colGap?: number
  /** Space between two nodes in one column. */
  rowGap?: number
}

const PAD = 24

const CORNER_RADIUS = 8
/** Shortest straight run into or out of a node, once the corner is rounded, that still reads as an arrow pointing at it. */
export const MIN_STUB = 24
/** The polyline stub at each node: `CANVAS_EDGE_STUB` in the kit, which leaves MIN_STUB straight after the corner radius. */
export const EDGE_STUB = MIN_STUB + CORNER_RADIUS

interface Pt {
  x: number
  y: number
}

const round = (n: number) => Math.round(n * 100) / 100

const same = (a: number, b: number) => Math.abs(a - b) < 1e-3

/** Drops repeated and collinear points so every remaining segment is a real run. */
function simplify(pts: Pt[]): Pt[] {
  const out: Pt[] = []
  for (const p of pts) {
    const last = out[out.length - 1]
    if (last && same(last.x, p.x) && same(last.y, p.y)) continue
    out.push(p)
  }
  for (let i = out.length - 2; i > 0; i--) {
    const a = out[i - 1]
    const b = out[i]
    const c = out[i + 1]
    if ((same(a.x, b.x) && same(b.x, c.x)) || (same(a.y, b.y) && same(b.y, c.y))) out.splice(i, 1)
  }
  return out
}

/** The `roundedFlowPath` of the kit: a polyline with each corner rounded by up to `radius`. */
function roundedPath(pts: Pt[], radius = CORNER_RADIUS): string {
  const fmt = (p: Pt) => `${round(p.x)} ${round(p.y)}`
  let d = `M ${fmt(pts[0])}`
  for (let i = 1; i < pts.length - 1; i++) {
    const p0 = pts[i - 1]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const len1 = Math.hypot(p1.x - p0.x, p1.y - p0.y)
    const len2 = Math.hypot(p2.x - p1.x, p2.y - p1.y)
    const r = Math.min(radius, len1 / 2, len2 / 2)
    if (r <= 0) {
      d += ` L ${fmt(p1)}`
      continue
    }
    const enter = { x: p1.x + ((p0.x - p1.x) / len1) * r, y: p1.y + ((p0.y - p1.y) / len1) * r }
    const leave = { x: p1.x + ((p2.x - p1.x) / len2) * r, y: p1.y + ((p2.y - p1.y) / len2) * r }
    d += ` L ${fmt(enter)} Q ${fmt(p1)} ${fmt(leave)}`
  }
  return `${d} L ${fmt(pts[pts.length - 1])}`
}

/**
 * The orthogonal route from the right side of `from` at height `ys` to the left side of `to` at height `yt`.
 * Both ends keep a straight horizontal stub. A target in a later column turns once in the gap before it;
 * a target in the same column loops out right of the source, runs through the row gap, and comes in from the left.
 */
function routeStubbed(from: NodeBox, to: NodeBox, ys: number, yt: number, lane = 0, rowGap = 28): Pt[] {
  const x1 = from.x + from.w
  const x2 = to.x
  if (x2 - x1 >= 2 * EDGE_STUB) {
    if (same(ys, yt)) return [{ x: x1, y: ys }, { x: x2, y: yt }]
    const turn = Math.min(Math.max((x1 + x2) / 2 + lane, x1 + EDGE_STUB), x2 - EDGE_STUB)
    return simplify([{ x: x1, y: ys }, { x: turn, y: ys }, { x: turn, y: yt }, { x: x2, y: yt }])
  }
  const below = to.y + to.h / 2 > from.y + from.h / 2
  const seam = below ? from.y + from.h + rowGap / 2 : from.y - rowGap / 2
  return simplify([
    { x: x1, y: ys },
    { x: x1 + EDGE_STUB, y: ys },
    { x: x1 + EDGE_STUB, y: seam },
    { x: x2 - EDGE_STUB, y: seam },
    { x: x2 - EDGE_STUB, y: yt },
    { x: x2, y: yt },
  ])
}

/** Heights along a node's side for `count` edges, spread evenly so no two edges share a point. */
const spread = (box: NodeBox, count: number, index: number) => round(box.y + (box.h * (index + 1)) / (count + 1))

/** Offset, in units, of an edge's vertical run within the gap, so edges into one target do not stack on one line. */
const laneOffset = (count: number, index: number) => Math.max(-4, Math.min(4, (index - (count - 1) / 2) * 2))

/**
 * Gives every edge its start and end height on the source's right side and the target's left side,
 * ordered by where the other end sits so edges rarely cross, then routes it.
 */
function routeEdges(edges: RunEdge[], boxes: Map<string, NodeBox>, rowGap: number): { edge: RunEdge; pts: Pt[] }[] {
  const live = edges.filter((e) => boxes.has(e.from) && boxes.has(e.to))
  const centre = (id: string) => boxes.get(id)!.y + boxes.get(id)!.h / 2
  const incoming = new Map<string, number[]>()
  const outgoing = new Map<string, number[]>()
  live.forEach((edge, i) => {
    incoming.set(edge.to, [...(incoming.get(edge.to) ?? []), i])
    outgoing.set(edge.from, [...(outgoing.get(edge.from) ?? []), i])
  })
  const endIndex = new Map<number, [number, number]>()
  const startIndex = new Map<number, [number, number]>()
  for (const list of incoming.values()) {
    list.sort((a, b) => centre(live[a].from) - centre(live[b].from) || a - b)
    list.forEach((edge, k) => endIndex.set(edge, [k, list.length]))
  }
  for (const list of outgoing.values()) {
    list.sort((a, b) => centre(live[a].to) - centre(live[b].to) || a - b)
    list.forEach((edge, k) => startIndex.set(edge, [k, list.length]))
  }
  return live.map((edge, i) => {
    const from = boxes.get(edge.from)!
    const to = boxes.get(edge.to)!
    const [sk, sn] = startIndex.get(i)!
    const [ek, en] = endIndex.get(i)!
    return { edge, pts: routeStubbed(from, to, spread(from, sn, sk), spread(to, en, ek), laneOffset(en, ek), rowGap) }
  })
}

/** A column cell: one task, or the run of same-chain tasks that stay together in chain order. */
interface Unit {
  ids: string[]
  plan: number
  y: number
}

/**
 * Lays the run out as columns by level, synchronously: the first paint and the server-side checks use it.
 * Chain members sit together in chain order with the normal row gap; other rows are ordered by two barycenter
 * sweeps over dependency edges, ties broken by plan order. Edges keep straight stubs at both ends and spread
 * along the node sides. Pure and deterministic. `elkLayoutRun` replaces it once the layout library has loaded.
 */
export function layoutRun(run: RunView, opts: LayoutOptions = {}): GraphLayout {
  const w = opts.nodeW ?? 248
  const h = opts.nodeH ?? 96
  const colGap = opts.colGap ?? 72
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

  const unitHeight = (unit: Unit) => unit.ids.length * h + (unit.ids.length - 1) * rowGap
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
    return unit.y + unit.ids.indexOf(id) * (h + rowGap) + h / 2
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
          y: round(PAD + offset + unit.y + index * (h + rowGap)),
          w,
          h,
          level: task.level,
          ...(task.chain === undefined ? {} : { chain: task.chain }),
        })
      })
    }
  })

  const nodes = run.tasks.map((task) => boxes.get(task.id)!)
  const columnsUsed = levels.length
  return {
    nodes,
    edges: routeEdges(run.edges, boxes, rowGap).map(({ edge, pts }) => ({ from: edge.from, to: edge.to, kind: edge.kind, d: roundedPath(pts) })),
    width: columnsUsed === 0 ? PAD * 2 : PAD * 2 + columnsUsed * w + (columnsUsed - 1) * colGap,
    height: PAD * 2 + innerHeight,
  }
}

/** A key that changes only when the task set, levels, chains or edges do, never on a status tick. */
export function runStructureKey(run: RunView): string {
  return JSON.stringify([
    run.tasks.map((t) => [t.id, t.level, t.chain ?? null]),
    run.edges.map((e) => [e.from, e.to, e.kind]),
    run.chains.map((c) => [c.id, c.tasks]),
  ])
}

interface ElkPoint {
  x: number
  y: number
}
interface ElkSection {
  startPoint?: ElkPoint
  endPoint?: ElkPoint
  bendPoints?: ElkPoint[]
}
interface ElkNode {
  id: string
  x?: number
  y?: number
  width?: number
  height?: number
  layoutOptions?: Record<string, string>
  children?: ElkNode[]
  edges?: { id: string; sources: string[]; targets: string[]; sections?: ElkSection[] }[]
}

/** The constructor `flow.bundle.js` leaves on `window.quirkFlow.ELK`. */
export type ElkConstructor = new () => { layout(graph: ElkNode): Promise<ElkNode> }

/** True when a point list leaves `from` and enters `to` on straight horizontal stubs of at least EDGE_STUB. */
function hasStubs(pts: Pt[], from: NodeBox, to: NodeBox): boolean {
  if (pts.length < 2) return false
  const first = pts[0]
  const second = pts[1]
  const last = pts[pts.length - 1]
  const prev = pts[pts.length - 2]
  return (
    same(first.x, from.x + from.w) &&
    same(first.y, second.y) &&
    second.x - first.x >= EDGE_STUB - 1e-3 &&
    same(last.x, to.x) &&
    same(prev.y, last.y) &&
    last.x - prev.x >= EDGE_STUB - 1e-3
  )
}

/**
 * Lays the run out with ELK, the way `q-flow` does: layered, left to right, orthogonal routing, a 32-unit stub
 * at every node, and spacing wide enough that no two nodes touch. Dependency and ordering edges are both laid
 * out, so a chain's tasks are separate cards joined by an ordering arrow. Resolves to the same shape as
 * `layoutRun`; an edge ELK routes without proper stubs is re-routed rather than drawn crooked.
 */
export async function elkLayoutRun(run: RunView, ELK: ElkConstructor, opts: LayoutOptions = {}): Promise<GraphLayout> {
  const w = opts.nodeW ?? 248
  const h = opts.nodeH ?? 96
  const betweenLayers = opts.colGap ?? 72
  const nodeNode = opts.rowGap ?? 28

  const ids = new Set(run.tasks.map((t) => t.id))
  const seen = new Set<string>()
  const edges = run.edges.filter((e) => {
    const key = `${e.kind}:${e.from}>${e.to}`
    if (e.from === e.to || !ids.has(e.from) || !ids.has(e.to) || seen.has(key)) return false
    seen.add(key)
    return true
  })

  const graph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.json.shapeCoords': 'ROOT',
      'elk.json.edgeCoords': 'ROOT',
      'elk.layered.spacing.nodeNodeBetweenLayers': String(betweenLayers),
      'elk.spacing.nodeNode': String(nodeNode),
      'elk.spacing.edgeNode': '24',
      'elk.layered.spacing.edgeNodeBetweenLayers': String(EDGE_STUB),
      'elk.spacing.nodeSelfLoop': String(EDGE_STUB),
    },
    children: run.tasks.map((t) => ({ id: t.id, width: w, height: h })),
    edges: edges.map((e, i) => ({ id: `e${i}`, sources: [e.from], targets: [e.to] })),
  }
  const laidOut = await new ELK().layout(graph)

  const placed = new Map((laidOut.children ?? []).map((c) => [c.id, c]))
  const routed = new Map((laidOut.edges ?? []).map((e) => [e.id, e]))
  let minX = Infinity
  let minY = Infinity
  const raw = new Map<string, NodeBox>()
  for (const task of run.tasks) {
    const c = placed.get(task.id)
    if (c?.x === undefined || c.y === undefined) throw new Error(`ELK did not place ${task.id}`)
    raw.set(task.id, { id: task.id, x: c.x, y: c.y, w, h, level: task.level, ...(task.chain === undefined ? {} : { chain: task.chain }) })
    minX = Math.min(minX, c.x)
    minY = Math.min(minY, c.y)
  }

  const paths = edges.map((e, i) => {
    let pts: Pt[] = []
    for (const section of routed.get(`e${i}`)?.sections ?? []) {
      if (section.startPoint && pts.length === 0) pts.push(section.startPoint)
      pts.push(...(section.bendPoints ?? []))
      if (section.endPoint) pts.push(section.endPoint)
    }
    return { e, pts: simplify(pts) }
  })
  // one bad route re-routes every edge over ELK's node positions, so the spread along each side stays consistent
  if (paths.some(({ e, pts }) => !hasStubs(pts, raw.get(e.from)!, raw.get(e.to)!))) {
    routeEdges(edges, raw, nodeNode).forEach(({ pts }, i) => {
      paths[i].pts = pts
    })
  }

  let maxX = -Infinity
  let maxY = -Infinity
  for (const box of raw.values()) {
    maxX = Math.max(maxX, box.x + box.w)
    maxY = Math.max(maxY, box.y + box.h)
  }
  for (const { pts } of paths) {
    for (const p of pts) {
      minX = Math.min(minX, p.x)
      minY = Math.min(minY, p.y)
      maxX = Math.max(maxX, p.x)
      maxY = Math.max(maxY, p.y)
    }
  }
  if (!Number.isFinite(minX)) return { nodes: [], edges: [], width: PAD * 2, height: PAD * 2 }

  const dx = PAD - minX
  const dy = PAD - minY
  const nodes = run.tasks.map((t) => {
    const b = raw.get(t.id)!
    return { ...b, x: round(b.x + dx), y: round(b.y + dy) }
  })
  return {
    nodes,
    edges: paths.map(({ e, pts }) => ({
      from: e.from,
      to: e.to,
      kind: e.kind,
      d: roundedPath(pts.map((p) => ({ x: round(p.x + dx), y: round(p.y + dy) }))),
    })),
    width: round(maxX - minX + 2 * PAD),
    height: round(maxY - minY + 2 * PAD),
  }
}

export interface View {
  cx: number
  cy: number
  z: number
}

export interface Size {
  w: number
  h: number
}

export const MIN_ZOOM = 0.2
export const MAX_ZOOM = 3
const MAX_FIT_ZOOM = 1.25

/** The zoom at which the whole layout fits the container; never floored, so a large graph still fits. */
export function fitZoom(layout: GraphLayout, size: Size): number {
  return Math.min(size.w / layout.width, size.h / layout.height, MAX_FIT_ZOOM)
}

/** Lowest zoom a wheel or button may reach: the usual floor, or the fit zoom when the graph needs less. */
export function zoomFloor(layout: GraphLayout, size: Size): number {
  return Math.min(MIN_ZOOM, fitZoom(layout, size))
}

export function clampZoom(z: number, floor: number = MIN_ZOOM): number {
  return Math.min(MAX_ZOOM, Math.max(floor, z))
}

/** The on-screen size in px of text drawn at `fontPx` user units once the view sits at the fit zoom. */
export function effectiveFontPx(layout: GraphLayout, size: Size, fontPx: number): number {
  return fontPx * fitZoom(layout, size)
}

/** True when the view has been panned or zoomed off the fit view, beyond a few px of drift. */
export function isZoomedAway(view: View, layout: GraphLayout, size: Size): boolean {
  const fit = fitView(layout, size)
  if (Math.abs(view.z / fit.z - 1) > 0.02) return true
  return Math.hypot(view.cx - fit.cx, view.cy - fit.cy) * view.z > 6
}

/** The view that shows every node box, centred. */
export function fitView(layout: GraphLayout, size: Size): View {
  return { cx: layout.width / 2, cy: layout.height / 2, z: fitZoom(layout, size) }
}

export function viewBoxOf(view: View, size: Size): { x: number; y: number; w: number; h: number } {
  const w = size.w / view.z
  const h = size.h / view.z
  return { x: view.cx - w / 2, y: view.cy - h / 2, w, h }
}

export interface Rect {
  left: number
  top: number
  right: number
  bottom: number
}

export type CardPlacement = { mode: 'beside'; left: number; top: number } | { mode: 'dock' }

export const CARD_WIDTH = 352
export const CARD_GAP = 14
export const CARD_MARGIN = 8
export const DOCK_BELOW = 640

/**
 * Places the question card in container pixels. Beside the node when it fits (right side first, then left),
 * clamped on both axes to the container; docked full-width at the bottom when the container is under
 * DOCK_BELOW wide or narrower than the card plus the node.
 */
export function placeCard(node: Rect, container: Size, card: Size): CardPlacement {
  const nodeWidth = node.right - node.left
  if (container.w < DOCK_BELOW || container.w < card.w + nodeWidth) return { mode: 'dock' }
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, Math.max(lo, hi)))
  let left = node.right + CARD_GAP
  if (left + card.w > container.w - CARD_MARGIN) left = node.left - CARD_GAP - card.w
  left = clamp(left, CARD_MARGIN, container.w - card.w - CARD_MARGIN)
  const top = clamp(node.top, CARD_MARGIN, container.h - card.h - CARD_MARGIN)
  return { mode: 'beside', left, top }
}

/**
 * Places the question card for a node box in layout units under the current view, so every pan or zoom
 * moves the card with its node. `cardH` is the card's measured height; it is capped to what the panel can hold.
 */
export function placeCardForView(view: View, size: Size, box: { x: number; y: number; w: number; h: number }, cardH: number): CardPlacement {
  const vb = viewBoxOf(view, size)
  const left = (box.x - vb.x) * view.z
  const top = (box.y - vb.y) * view.z
  const card = { w: Math.min(CARD_WIDTH, size.w - 2 * CARD_MARGIN), h: Math.min(cardH, size.h - 2 * CARD_MARGIN) }
  return placeCard({ left, top, right: left + box.w * view.z, bottom: top + box.h * view.z }, size, card)
}

export type WheelIntent = 'zoom' | 'scroll'

/**
 * What a wheel event over the graph means. Only ctrl or meta zooms (a trackpad pinch arrives as ctrl+wheel),
 * so a plain wheel keeps scrolling the page instead of being captured by the graph.
 */
export function wheelIntent(event: { ctrlKey: boolean; metaKey: boolean; deltaY: number }): WheelIntent {
  return (event.ctrlKey || event.metaKey) && event.deltaY !== 0 ? 'zoom' : 'scroll'
}

export const PANEL_MIN_H = 360

/** The graph panel's height in px: the viewport space left below the panel's top edge, never under PANEL_MIN_H. */
export function panelHeight(viewportH: number, top: number): number {
  return Math.max(PANEL_MIN_H, Math.floor(viewportH - top))
}
