import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { runInThisContext } from 'node:vm'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  CARD_MARGIN, CARD_WIDTH, effectiveFontPx, elkLayoutRun, fitView, fitZoom, isZoomedAway, layoutRun, MIN_STUB, MIN_ZOOM, PANEL_MIN_H, panelHeight, placeCard,
  placeCardForView, runStructureKey, viewBoxOf, wheelIntent, zoomFloor,
  type ElkConstructor, type GraphLayout, type NodeBox, type Rect, type Size,
} from '../src/run/layout'
import { RunGraph } from '../src/run/graph'
import type { RunEdge, RunStatus, RunTask, RunView } from '../src/run/types'

const failures: string[] = []
const check = (ok: boolean, what: string) => {
  if (!ok) failures.push(what)
}

function task(id: string, level: number, status: RunStatus, over: Partial<RunTask> = {}): RunTask {
  return {
    id, title: `Task ${id}`, level, status, attempt: 1, attempts: [], files: 0, ready: true, blocked_by: [],
    downstream: [], labels: [], mismatch: null, ...over,
  }
}

function view(tasks: RunTask[], edges: RunEdge[], chains: RunView['chains'] = []): RunView {
  return {
    run_id: 'r1', branch: 'sdd/r1', started_at: 100, counts: {}, last_update_at: 100, stale: null, stale_after_s: 180,
    now: 200, tasks, edges, chains, rounds: [], questions: [],
  }
}

const sample = view(
  [
    task('T1', 1, 'passed', { started_at: 100, ended_at: 130, files: 3 }),
    task('T2', 2, 'running', { started_at: 140, files: 1 }),
    task('T3', 2, 'passed', { started_at: 135, ended_at: 150 }),
    task('T4', 3, 'queued', { chain: 'c1', ready: false }),
    task('T5', 3, 'queued', { chain: 'c1', ready: false, labels: ['fix T3 · CP1'] }),
    task('T6', 1, 'passed', {
      mismatch: { sdd: 'running', git: 'merged', text: 'SDD says running but git shows it merged' },
    }),
    task('T7', 1, 'failed', { reason: 'tests failed after 2 tries' }),
    task('T8', 2, 'retrying', { attempt: 2, started_at: 150 }),
    task('T9', 2, 'needs-you', { question: 'q1' }),
    task('T10', 2, 'queued', { ready: false, blocked_by: ['T7'], labels: ['blocked by T7'] }),
    task('T11', 4, 'queued', { ready: false, pending_action: 'retry' }),
  ],
  [
    { from: 'T1', to: 'T2', kind: 'dep' },
    { from: 'T1', to: 'T3', kind: 'dep' },
    { from: 'T2', to: 'T4', kind: 'dep' },
    { from: 'T3', to: 'T4', kind: 'dep' },
    { from: 'T4', to: 'T5', kind: 'order' },
    { from: 'T6', to: 'T8', kind: 'dep' },
    { from: 'T6', to: 'T9', kind: 'dep' },
    { from: 'T7', to: 'T10', kind: 'dep' },
    { from: 'T5', to: 'T11', kind: 'dep' },
    { from: 'T2', to: 'T11', kind: 'order' },
  ],
  [{ id: 'c1', tasks: ['T4', 'T5'] }],
)

/** Smallest gap between two boxes: the larger axis gap when they overlap on one axis, the corner distance otherwise. */
function boxGap(a: NodeBox, b: NodeBox): number {
  const dx = Math.max(a.x - (b.x + b.w), b.x - (a.x + a.w))
  const dy = Math.max(a.y - (b.y + b.h), b.y - (a.y + a.h))
  return dx > 0 && dy > 0 ? Math.hypot(dx, dy) : Math.max(dx, dy)
}

interface Pt {
  x: number
  y: number
}

/** The points a path visits: M and L end points, and the end point of each Q. */
function pathPoints(d: string): Pt[] {
  const pts: Pt[] = []
  for (const [, , args] of d.matchAll(/([MLQ])\s*([^MLQ]*)/g)) {
    const n = args.trim().split(/[\s,]+/).map(Number)
    pts.push({ x: n[n.length - 2], y: n[n.length - 1] })
  }
  return pts
}

const near = (a: number, b: number) => Math.abs(a - b) < 0.01

function checkGeometry(name: string, run: RunView, layout: GraphLayout) {
  check(layout.nodes.length === run.tasks.length, `${name}: expected one box per task`)
  const byId = new Map(layout.nodes.map((n) => [n.id, n]))
  let tightest = Infinity
  for (let i = 0; i < layout.nodes.length; i++) {
    for (let j = i + 1; j < layout.nodes.length; j++) {
      const gap = boxGap(layout.nodes[i], layout.nodes[j])
      tightest = Math.min(tightest, gap)
      if (gap < 16) failures.push(`${name}: ${layout.nodes[i].id} and ${layout.nodes[j].id} are ${gap.toFixed(1)} apart, under 16`)
    }
  }
  for (const edge of run.edges) {
    const from = byId.get(edge.from)
    const to = byId.get(edge.to)
    check(edge.kind === 'order' || (!!from && !!to && from.x + from.w <= to.x), `${name}: dep ${edge.from}->${edge.to} does not run left to right`)
  }
  for (const node of layout.nodes) {
    const task = run.tasks.find((t) => t.id === node.id)
    check(task?.level === node.level, `${name}: ${node.id} level mismatch`)
  }
  check(layout.nodes.every((n) => n.x + n.w <= layout.width && n.y + n.h <= layout.height), `${name}: nodes exceed the layout size`)
  check(layout.edges.length === run.edges.length, `${name}: expected one path per edge`)

  const ends = new Map<string, string>()
  for (const edge of layout.edges) {
    const label = `${name}: ${edge.kind} ${edge.from}->${edge.to}`
    const from = byId.get(edge.from)
    const to = byId.get(edge.to)
    const pts = pathPoints(edge.d)
    if (!from || !to || pts.length < 2) {
      failures.push(`${label} has no usable path`)
      continue
    }
    const [first, second] = pts
    const last = pts[pts.length - 1]
    const prev = pts[pts.length - 2]
    check(near(first.x, from.x + from.w) && first.y > from.y && first.y < from.y + from.h, `${label} must start on the source's right side`)
    check(near(first.y, second.y) && second.x - first.x >= MIN_STUB - 0.01, `${label} must leave on a horizontal run of at least ${MIN_STUB}`)
    check(near(last.x, to.x) && last.y > to.y && last.y < to.y + to.h, `${label} must end on the target's left side`)
    check(near(prev.y, last.y) && last.x - prev.x >= MIN_STUB - 0.01, `${label} must enter on a horizontal run of at least ${MIN_STUB}`)
    const key = `${edge.to}@${last.x},${last.y}`
    const other = ends.get(key)
    check(other === undefined, `${name}: ${edge.from}->${edge.to} and ${other} share an end point on ${edge.to}`)
    ends.set(key, `${edge.from}->${edge.to}`)
  }
  return tightest
}

function checkLayout(name: string, run: RunView): GraphLayout {
  const layout = layoutRun(run)
  check(JSON.stringify(layout) === JSON.stringify(layoutRun(run)), `${name}: layout is not deterministic`)
  checkGeometry(name, run, layout)
  return layout
}

const layout = checkLayout('sample', sample)
const box = (id: string) => layout.nodes.find((n) => n.id === id)!
const t4 = box('T4')
const t5 = box('T5')
check(t4.x === t5.x && t4.level === t5.level, 'chain members must share a column')
check(t5.y >= t4.y + t4.h + 16, 'chain members are separate cards with a gap, in chain order')
check(t4.chain === 'c1' && t5.chain === 'c1', 'chain id is carried on the boxes')
const join = layout.edges.find((e) => e.from === 'T4' && e.to === 'T5')
check(join?.kind === 'order' && join.d.length > 0, 'T4 -> T5 is an ordering edge with its own path')
check(!('joined' in (join ?? {})), 'edges no longer carry a joined flag')
const cross = layout.edges.find((e) => e.from === 'T2' && e.to === 'T11')
check(cross?.kind === 'order' && cross.d.length > 0, 'cross-column order edge is a plain path')
check(box('T1').x < box('T2').x && box('T2').x < box('T4').x && box('T4').x < box('T11').x, 'columns follow levels left to right')

// a wider generated run exercises ordering and overlap at scale
const gen: RunTask[] = []
const genEdges: RunEdge[] = []
let seed = 7
const rnd = (n: number) => {
  seed = (seed * 1103515245 + 12345) % 2147483648
  return seed % n
}
for (let i = 1; i <= 40; i++) {
  const deps: string[] = []
  const lvl = i <= 5 ? 1 : 1 + Math.min(5, Math.floor((i - 1) / 7))
  if (lvl > 1) {
    const pool = gen.filter((t) => t.level < lvl)
    for (let k = 0; k < 1 + rnd(2); k++) {
      const dep = pool[rnd(pool.length)]
      if (!deps.includes(dep.id)) deps.push(dep.id)
    }
  }
  const level = deps.length ? 1 + Math.max(...deps.map((d) => gen.find((t) => t.id === d)!.level)) : 1
  gen.push(task(`G${i}`, level, 'queued', { chain: i % 9 === 0 ? 'gc' : undefined }))
  for (const d of deps) genEdges.push({ from: d, to: `G${i}`, kind: 'dep' })
}
const chained = gen.filter((t) => t.chain === 'gc')
for (const t of chained) t.level = chained[0].level
for (let i = 1; i < chained.length; i++) genEdges.push({ from: chained[i - 1].id, to: chained[i].id, kind: 'order' })
const genRun = view(gen, genEdges.filter((e) => e.kind === 'order' || gen.find((t) => t.id === e.to)!.level > gen.find((t) => t.id === e.from)!.level), [
  { id: 'gc', tasks: chained.map((t) => t.id) },
])
const genLayout = checkLayout('generated', genRun)
const gcBoxes = chained.map((t) => genLayout.nodes.find((n) => n.id === t.id)!)
check(
  gcBoxes.every((b, i) => i === 0 || (b.x === gcBoxes[0].x && b.y > gcBoxes[i - 1].y)),
  'generated: chain members share a column in chain order',
)

// the 11-task demo run: its dependencies, and T6 -> T7 as an ordering edge in one chain
const demoSpec: [string, number, string[]][] = [
  ['T1', 1, []], ['T2', 1, []], ['T3', 1, []], ['T4', 2, ['T1', 'T2', 'T3']], ['T5', 1, []], ['T6', 2, ['T5']], ['T7', 2, ['T5']],
  ['T8', 2, ['T5']], ['T9', 3, ['T4', 'T6', 'T7', 'T8']], ['T10', 1, []], ['CP1-F1', 2, ['T10']],
]
const demoRun = view(
  demoSpec.map(([id, level]) => task(id, level, 'queued', id === 'T6' || id === 'T7' ? { chain: 'c1' } : {})),
  [
    ...demoSpec.flatMap(([id, , deps]) => deps.map((dep): RunEdge => ({ from: dep, to: id, kind: 'dep' }))),
    { from: 'T6', to: 'T7', kind: 'order' },
  ],
  [{ id: 'c1', tasks: ['T6', 'T7'] }],
)
checkLayout('demo', demoRun)

// ELK: load the vendored bundle the way the browser does, then lay the same runs out
const flowBundle = fileURLToPath(new URL('../../../vendor/flow/0.12.0/flow.bundle.js', import.meta.url))
const scope = globalThis as unknown as { window?: unknown; quirkFlow?: { ELK: ElkConstructor } }
scope.window = globalThis
runInThisContext(readFileSync(flowBundle, 'utf8'), { filename: flowBundle })
const ELK = scope.quirkFlow!.ELK
delete scope.window

async function checkElk(name: string, run: RunView): Promise<GraphLayout> {
  const laid = await elkLayoutRun(run, ELK)
  check(JSON.stringify(laid) === JSON.stringify(await elkLayoutRun(run, ELK)), `${name}: elk layout is not deterministic`)
  checkGeometry(name, run, laid)
  const byId = new Map(laid.nodes.map((n) => [n.id, n]))
  for (const edge of run.edges) {
    check(byId.get(edge.from)!.x + byId.get(edge.from)!.w < byId.get(edge.to)!.x, `${name}: ${edge.kind} ${edge.from}->${edge.to} runs left to right`)
  }
  for (const edge of laid.edges) {
    const pts = pathPoints(edge.d)
    for (let i = 0; i + 1 < pts.length; i++) {
      const [a, b] = [pts[i], pts[i + 1]]
      const crossed = laid.nodes.find(
        (n) => n.id !== edge.from && n.id !== edge.to && Math.max(a.x, b.x) > n.x && Math.min(a.x, b.x) < n.x + n.w && Math.max(a.y, b.y) > n.y && Math.min(a.y, b.y) < n.y + n.h,
      )
      check(!crossed, `${name}: ${edge.from}->${edge.to} runs through ${crossed?.id}`)
    }
  }
  check(laid.nodes.every((n) => n.x >= 0 && n.y >= 0) && laid.edges.every((e) => pathPoints(e.d).every((p) => p.x >= 0 && p.y >= 0 && p.x <= laid.width && p.y <= laid.height)), `${name}: nodes and edges stay inside the layout size`)
  return laid
}

const elkDemo = await checkElk('elk demo', demoRun)
check(elkDemo.edges.some((e) => e.kind === 'order' && e.from === 'T6' && e.to === 'T7'), 'elk demo: the T6 -> T7 ordering edge is laid out')
const t7Gap = boxGap(elkDemo.nodes.find((n) => n.id === 'T6')!, elkDemo.nodes.find((n) => n.id === 'T7')!)
check(t7Gap >= 16, 'elk demo: T6 and T7 are separate, untouching cards')
const incomingT9 = elkDemo.edges.filter((e) => e.to === 'T9').map((e) => pathPoints(e.d).at(-1)!.y)
check(new Set(incomingT9).size === incomingT9.length && incomingT9.length === 4, 'elk demo: the four edges into T9 enter at four different points')
await checkElk('elk generated', genRun)
check(JSON.stringify(await elkLayoutRun(view([], []), ELK)) === JSON.stringify({ nodes: [], edges: [], width: 48, height: 48 }), 'elk: an empty run lays out nothing')

// a layout engine that routes edges crookedly still yields straight stubs
const crooked: ElkConstructor = class {
  async layout(graph: Parameters<InstanceType<ElkConstructor>['layout']>[0]) {
    const spot: Record<string, [number, number]> = { A: [20, 20], B: [320, 20], C: [320, 150], D: [620, 20] }
    const children = (graph.children ?? []).map((c) => ({ ...c, x: spot[c.id][0], y: spot[c.id][1] }))
    const at = new Map(children.map((c) => [c.id, c]))
    return {
      ...graph,
      children,
      edges: (graph.edges ?? []).map((e) => {
        const a = at.get(e.sources[0])!
        const b = at.get(e.targets[0])!
        return { ...e, sections: [{ id: 's', startPoint: { x: a.x! + 248, y: a.y! + 30 }, endPoint: { x: b.x!, y: b.y! + 70 } }] }
      }),
    }
  }
}
const crookedRun = view(
  [task('A', 1, 'queued'), task('B', 2, 'queued'), task('C', 2, 'queued'), task('D', 3, 'queued')],
  [{ from: 'A', to: 'B', kind: 'dep' }, { from: 'A', to: 'C', kind: 'dep' }, { from: 'B', to: 'D', kind: 'dep' }, { from: 'C', to: 'D', kind: 'order' }],
)
checkGeometry('crooked engine', crookedRun, await elkLayoutRun(crookedRun, crooked))

// only a change to the task set, levels, chains or edges changes the structure key
const ticked = view(sample.tasks.map((t) => ({ ...t, status: 'passed' as const, files: 9 })), sample.edges, sample.chains)
check(runStructureKey(ticked) === runStructureKey(sample), 'a status tick keeps the structure key')
check(runStructureKey(view(sample.tasks, [...sample.edges, { from: 'T1', to: 'T11', kind: 'dep' }], sample.chains)) !== runStructureKey(sample), 'a new edge changes the structure key')
check(runStructureKey(view(sample.tasks.slice(1), sample.edges, sample.chains)) !== runStructureKey(sample), 'a removed task changes the structure key')

const empty = layoutRun(view([], []))
check(empty.nodes.length === 0 && empty.edges.length === 0, 'empty run lays out nothing')

const props = { serverNow: 200_000, selected: null, focus: null, cardTask: null, card: null, stale: false, onSelect: () => {} }
const html = renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props }))
for (const t of sample.tasks) check(html.includes(`>${t.id}<`) || html.includes(t.id), `markup is missing ${t.id}`)
check(html.includes('data-status="failed"'), 'markup is missing data-status="failed"')
const paths = html.match(/<path\b[^>]*>/g) ?? []
const fromT7 = paths.filter((p) => p.includes('data-from="T7"'))
check(fromT7.length > 0 && fromT7.every((p) => p.includes('data-failed="true"')), "T7's outgoing edge must carry data-failed")
check(paths.filter((p) => p.includes('data-from="T1"')).every((p) => !p.includes('data-failed')), 'only failed tasks mark edges failed')
check(html.includes('try 2'), 'markup is missing the "try 2" badge')
check(html.includes('SDD says running but git shows it merged'), 'markup is missing the mismatch text')
check(html.includes('blocked by T7'), 'markup is missing the "blocked by T7" label')
check(html.includes('Retry requested'), 'markup is missing the pending-action chip')
check(html.includes('3 files'), 'markup is missing the files count')
check(html.includes('data-ready="false"'), 'markup is missing data-ready="false"')
check(html.includes('data-run-part="graph"') && html.startsWith('<div class="run-graph-root"'), 'the outermost element must carry data-run-part="graph"')
check(html.includes('role="img"') && html.includes('aria-label='), 'the svg needs role="img" and an aria-label')
check(html.includes('tabindex="0"'), 'node groups must be focusable')
check(!/Level|Wave/.test(html), 'markup must not show Level or Wave text')
check(!/joined|run-edge-join/.test(html) && !/joined|run-edge-join/.test(readFileSync(new URL('../src/run/graph.css', import.meta.url), 'utf8')), 'the joined-card markup and styles are gone')
check(paths.every((p) => !p.includes('data-from') || p.includes('marker-end=')), 'every edge carries an arrowhead')
check(!html.includes('data-stale="true"'), 'a fresh run must not render data-stale')

const staleHtml = renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props, stale: true }))
check(staleHtml.includes('data-stale="true"'), 'stale must render data-stale="true"')

const selectedHtml = renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props, selected: 'T2' }))
check(selectedHtml.includes('data-selected="true"'), 'the selected node must carry data-selected="true"')

const cardHtml = renderToStaticMarkup(
  createElement(RunGraph, { run: sample, ...props, cardTask: 'T9', card: createElement('div', { id: 'the-card' }, 'ask') }),
)
check(cardHtml.includes('id="the-card"'), 'cardTask must render the card overlay')
check(!renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props, card: createElement('b', null, 'x') })).includes('<b>x</b>'), 'no card without cardTask')

// Fit must show every node box, even for a graph that needs a zoom below the wheel floor
const bigTasks: RunTask[] = []
const bigEdges: RunEdge[] = []
for (let i = 1; i <= 60; i++) {
  const level = 1 + Math.floor((i - 1) / 3)
  bigTasks.push(task(`B${i}`, level, 'queued'))
  if (level > 1) bigEdges.push({ from: `B${i - 3}`, to: `B${i}`, kind: 'dep' })
}
const bigLayout = checkLayout('big', view(bigTasks, bigEdges))
await checkElk('elk big', view(bigTasks, bigEdges))
for (const size of [{ w: 960, h: 520 }, { w: 400, h: 300 }, { w: 1600, h: 900 }]) {
  const fitted = fitView(bigLayout, size)
  const vb = viewBoxOf(fitted, size)
  const holdsAll = bigLayout.nodes.every(
    (n) => n.x >= vb.x - 1e-6 && n.y >= vb.y - 1e-6 && n.x + n.w <= vb.x + vb.w + 1e-6 && n.y + n.h <= vb.y + vb.h + 1e-6,
  )
  check(holdsAll, `fit ${size.w}x${size.h}: viewBox must contain every node box`)
  check(fitted.z === fitZoom(bigLayout, size), `fit ${size.w}x${size.h}: zoom is the fit zoom, unclamped`)
  check(zoomFloor(bigLayout, size) <= fitted.z, `fit ${size.w}x${size.h}: the zoom floor must not sit above the fit zoom`)
}
check(fitView(bigLayout, { w: 960, h: 520 }).z < MIN_ZOOM, 'the 60-task graph needs a fit zoom below the usual floor')
check(zoomFloor(bigLayout, { w: 960, h: 520 }) === fitView(bigLayout, { w: 960, h: 520 }).z, 'the floor drops to the fit zoom when Fit needs less')
check(zoomFloor(layout, { w: 960, h: 520 }) === MIN_ZOOM, 'the floor stays at the usual minimum when the graph fits above it')

// card placement stays inside the container
const inside = (rect: Rect, c: Size) => rect.left >= 0 && rect.top >= 0 && rect.right <= c.w && rect.bottom <= c.h
const cardSize = { w: CARD_WIDTH, h: 260 }
const wide = { w: 1100, h: 560 }
const nodeAt = (left: number, top: number, w = 230, h = 96): Rect => ({ left, top, right: left + w, bottom: top + h })
for (const [name, node] of [
  ['centre', nodeAt(400, 200)],
  ['right edge', nodeAt(900, 200)],
  ['left edge', nodeAt(10, 200)],
  ['off the left', nodeAt(-300, 100)],
  ['off the right', nodeAt(1300, 100)],
  ['above', nodeAt(400, -500)],
  ['below', nodeAt(400, 900)],
] as const) {
  const placed = placeCard(node, wide, cardSize)
  check(placed.mode === 'beside', `card ${name}: a wide container places the card beside the node`)
  if (placed.mode === 'beside') {
    const rect = { left: placed.left, top: placed.top, right: placed.left + cardSize.w, bottom: placed.top + cardSize.h }
    check(inside(rect, wide), `card ${name}: the card must sit inside the container`)
    check(placed.left >= CARD_MARGIN, `card ${name}: the card keeps its margin`)
  }
}
const flipped = placeCard(nodeAt(900, 200), wide, cardSize)
check(flipped.mode === 'beside' && flipped.left + cardSize.w <= 900, 'a node near the right edge flips the card to its left')
const sideways = placeCard(nodeAt(100, 200), wide, cardSize)
check(sideways.mode === 'beside' && sideways.left >= 330, 'a node with room on the right keeps the card on its right')
check(placeCard(nodeAt(100, 100), { w: 600, h: 500 }, cardSize).mode === 'dock', 'under 640 px wide the card docks')
check(placeCard(nodeAt(100, 100, 400), { w: 700, h: 500 }, cardSize).mode === 'dock', 'a container narrower than the card plus the node docks the card')
check(placeCard(nodeAt(100, 100), { w: 640, h: 500 }, cardSize).mode === 'beside', 'a 640 px container that holds card and node places beside')

// a plain wheel scrolls the page; only ctrl or meta zooms (trackpad pinch arrives as ctrl+wheel)
check(wheelIntent({ ctrlKey: false, metaKey: false, deltaY: 120 }) === 'scroll', 'a plain wheel scrolls the page')
check(wheelIntent({ ctrlKey: false, metaKey: false, deltaY: -120 }) === 'scroll', 'a plain wheel up scrolls the page')
check(wheelIntent({ ctrlKey: true, metaKey: false, deltaY: -4 }) === 'zoom', 'ctrl+wheel zooms')
check(wheelIntent({ ctrlKey: false, metaKey: true, deltaY: 100 }) === 'zoom', 'meta+wheel zooms')
check(wheelIntent({ ctrlKey: true, metaKey: false, deltaY: 0 }) === 'scroll', 'a wheel with no vertical delta never zooms')

// the card follows its node: the same node under a moved view gets a different placement, always inside the panel
const cardPanel: Size = { w: 1100, h: 560 }
const t9 = box('T9')
const t9Fit = { cx: t9.x + t9.w / 2, cy: t9.y + t9.h / 2, z: 1 }
const placedAt = (v: { cx: number; cy: number; z: number }) => placeCardForView(v, cardPanel, t9, 260)
const centred = placedAt(t9Fit)
check(centred.mode === 'beside', 'a centred node places the card beside it')
const panned = placedAt({ ...t9Fit, cy: t9Fit.cy + 120 })
check(centred.mode === 'beside' && panned.mode === 'beside' && panned.top < centred.top, 'panning the view up moves the card up with its node')
const nodeLeftOf = (v: { cx: number; cy: number; z: number }) => (t9.x - viewBoxOf(v, cardPanel).x) * v.z
const zoomedOut = placedAt({ ...t9Fit, z: 0.5 })
check(zoomedOut.mode === 'beside' && centred.mode === 'beside' && zoomedOut.left !== centred.left, 'zooming the view moves the card with the node')
check(
  zoomedOut.mode === 'beside' &&
    (zoomedOut.left >= nodeLeftOf({ ...t9Fit, z: 0.5 }) + t9.w * 0.5 || zoomedOut.left + CARD_WIDTH <= nodeLeftOf({ ...t9Fit, z: 0.5 })),
  'the card sits beside the zoomed node box, not on it',
)
for (const v of [t9Fit, { ...t9Fit, cy: t9Fit.cy - 900 }, { ...t9Fit, cx: t9Fit.cx + 900, z: 2 }, { ...t9Fit, z: 0.3 }]) {
  const placed = placeCardForView(v, cardPanel, t9, 260)
  check(placed.mode === 'beside' && placed.top >= CARD_MARGIN && placed.top + 260 <= cardPanel.h - CARD_MARGIN, 'the card stays inside the visible panel vertically')
}
check(placeCardForView(t9Fit, { w: 500, h: 560 }, t9, 260).mode === 'dock', 'a narrow panel docks the card whatever the view')

// the panel takes the viewport space left below its top edge, with a floor
check(panelHeight(720, 250) === 470, 'the panel takes the viewport height left below its top edge')
check(panelHeight(720, 600) === PANEL_MIN_H, 'the panel never drops below the floor')
check(panelHeight(1440, 300) === 1140, 'a tall window gives the panel the room it has')
check(panelHeight(720, 250.6) === 469, 'the panel height is a whole number of px')

// dependency edges never take a dash, whatever the status pair
const statuses: RunStatus[] = ['queued', 'running', 'retrying', 'passed', 'failed', 'needs-you', 'skipped']
const pairTasks: RunTask[] = []
const pairEdges: RunEdge[] = []
for (const a of statuses) {
  for (const b of statuses) {
    pairTasks.push(task(`${a}>${b}:s`, 1, a), task(`${a}>${b}:t`, 2, b))
    pairEdges.push({ from: `${a}>${b}:s`, to: `${a}>${b}:t`, kind: 'dep' })
  }
}
const pairHtml = renderToStaticMarkup(createElement(RunGraph, { run: view(pairTasks, pairEdges), ...props }))
const depPaths = (pairHtml.match(/<path\b[^>]*>/g) ?? []).filter((p) => p.includes('data-kind="dep"'))
check(depPaths.length === pairEdges.length, 'every status pair renders a dep edge')
check(depPaths.every((p) => !/dash|style=/.test(p)), 'no dep edge carries a dash attribute or inline style')
check(depPaths.some((p) => p.includes('data-flow="true"')), 'a passed task feeding a running one still marks its edge active')
const css = readFileSync(new URL('../src/run/graph.css', import.meta.url), 'utf8')
for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
  const [, selector, body] = rule
  const dashValue = /stroke-dasharray:\s*([^;]+)/.exec(body)?.[1].trim()
  const dashed = dashValue !== undefined && dashValue !== 'none'
  if (dashed && selector.includes('.run-edge') && !selector.includes("[data-kind='order']")) {
    failures.push(`graph.css: ${selector.trim()} dashes an edge that is not an order edge`)
  }
}
check(!/run-flow/.test(css), 'graph.css: the dashed flow animation is gone')

// text stays legible at the default fit: sizes come from the stylesheet, scaled by the fit zoom of the 11-task demo
const cssFont = (selector: string): number => {
  for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const [, sel, body] = rule
    if (sel.trim().split(/\s*,\s*/).some((part) => part.endsWith(selector))) {
      const size = /font-size:\s*([\d.]+)px/.exec(body)?.[1]
      if (size) return Number(size)
    }
  }
  return 0
}
const panel: Size = { w: 1232, h: 576 }
const titlePx = effectiveFontPx(layout, panel, cssFont('.run-node-title'))
const metaPx = effectiveFontPx(layout, panel, cssFont('.run-node-meta'))
const chipPx = effectiveFontPx(layout, panel, cssFont('.run-node-chip text'))
check(titlePx >= 14, `node titles must be at least 14 px at the default fit, got ${titlePx.toFixed(1)}`)
check(metaPx >= 12, `node meta must be at least 12 px at the default fit, got ${metaPx.toFixed(1)}`)
check(chipPx >= 12, `node chips must be at least 12 px at the default fit, got ${chipPx.toFixed(1)}`)
check(fitZoom(layout, panel) >= 0.9, 'the 11-task demo fits near zoom 1, not shrunk to fit')
check(layout.width * fitZoom(layout, panel) >= panel.w * 0.9, 'the demo fit uses at least 90% of the panel width')
check(effectiveFontPx(layout, { w: 1232, h: 100_000 }, 10) === 10 * Math.min(1232 / layout.width, 1.25), 'effectiveFontPx scales by the fit zoom')

// accessible names pluralise the file count
const labels = [...html.matchAll(/aria-label="([^"]*)"/g)].map((m) => m[1])
check(labels.some((l) => l.startsWith('T2 ') && /, 1 file(,|$)/.test(l)), 'a task with one file is announced as "1 file"')
check(labels.every((l) => !/\b1 files\b/.test(l)) && !html.includes('1 files'), 'no label says "1 files"')
check(labels.some((l) => l.startsWith('T1 ') && l.includes('3 files')), 'several files stay plural in the label')

// the running effect is a dot pulse and a faint accent-bar sweep, never a gradient over the card body
check(!html.includes('run-shimmer-grad') && !css.includes('run-shimmer-grad'), 'the card-wide shimmer gradient is gone')
const shimmerSvg = /<svg class="run-node-shimmer"[^>]*>/.exec(html)?.[0] ?? ''
check(/width="5"/.test(shimmerSvg), 'the running sweep is confined to the 5-unit accent bar')
check(!/url\(/.test(html.slice(html.indexOf('run-node-shimmer'), html.indexOf('run-node-shimmer') + 300)), 'the sweep paints no gradient')
const sweepRules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([, sel]) => /sweep|shimmer/.test(sel))
check(sweepRules.length > 0 && sweepRules.every(([, sel, body]) => !/gradient|url\(/.test(body) && !/run-node-card/.test(sel)), 'shimmer rules target only the accent element')
const sweepFrames = /@keyframes run-sweep\s*\{([\s\S]*?)\n\}\n/.exec(css)?.[1] ?? ''
const sweepOpacities = [...sweepFrames.matchAll(/opacity:\s*([\d.]+)/g)].map((m) => Number(m[1]))
check(sweepOpacities.length > 0 && Math.max(...sweepOpacities) <= 0.08, 'the sweep never exceeds 8% opacity')
check(/\.run-node\[data-status='running'\] \.run-node-dot\s*\{[^}]*animation:/.test(css), 'a running card pulses its status dot')
check(/prefers-reduced-motion[\s\S]*\.run-graph \*[\s\S]*animation:\s*none/.test(css), 'reduced motion stops every graph animation')

// the panel height comes from the measured offset, and the wheel hint is shown statically under reduced motion
check(/\.run-graph\s*\{[^}]*height:\s*var\(--run-graph-h/.test(css), 'the graph height reads the measured --run-graph-h')
check(/prefers-reduced-motion[\s\S]*\.run-graph-hint[\s\S]*animation:\s*none/.test(css), 'reduced motion shows the wheel hint without animation')
check(!html.includes('Use ⌘ or Ctrl + scroll to zoom'), 'the wheel hint stays hidden until the first plain wheel')

// Show all appears only while the view is away from fit
const showAll = (h: string) => h.includes('Show all')
check(!showAll(html), 'Show all is hidden at the fit view')
const defaultSize: Size = { w: 960, h: 520 }
const fitted = fitView(layout, defaultSize)
check(!showAll(renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props, initialView: fitted }))), 'Show all is hidden when the view equals fit')
const zoomedIn = { cx: box('T9').x + box('T9').w / 2, cy: box('T9').y + box('T9').h / 2, z: 1.6 }
const awayHtml = renderToStaticMarkup(createElement(RunGraph, { run: sample, ...props, initialView: zoomedIn }))
check(showAll(awayHtml), 'Show all appears when the view is zoomed away from fit')
check(awayHtml.indexOf('Show all') < awayHtml.indexOf('<svg'), 'Show all sits in the control group')
check(isZoomedAway(zoomedIn, layout, defaultSize) && !isZoomedAway(fitted, layout, defaultSize), 'isZoomedAway separates zoomed views from the fit view')
check(isZoomedAway({ ...fitted, cx: fitted.cx + 200 }, layout, defaultSize), 'a panned view counts as away from fit')
check(!isZoomedAway({ ...fitted, cx: fitted.cx + 1 }, layout, defaultSize), 'sub-pixel drift is not away from fit')
check(/\.run-graph-tools\s*\{[^}]*z-index:\s*(\d+)/.test(css) && Number(/\.run-graph-tools\s*\{[^}]*z-index:\s*(\d+)/.exec(css)![1]) > Number(/\.run-graph-card\s*\{[^}]*z-index:\s*(\d+)/.exec(css)![1]), 'the control group stays above the card overlay')

const emptyHtml = renderToStaticMarkup(createElement(RunGraph, { run: view([], []), ...props }))
check(emptyHtml.includes('<svg'), 'an empty run still renders an svg')

if (failures.length) {
  console.error(`run-graph-check failed:\n- ${failures.join('\n- ')}`)
  process.exitCode = 1
} else {
  console.log('run-graph-check passed: layout is deterministic and non-overlapping, and the graph renders every task state.')
}
