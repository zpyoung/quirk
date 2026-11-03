import { readFileSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  CARD_MARGIN, CARD_WIDTH, effectiveFontPx, fitView, fitZoom, isZoomedAway, layoutRun, MIN_ZOOM, PANEL_MIN_H, panelHeight, placeCard, placeCardForView,
  viewBoxOf, wheelIntent, zoomFloor,
  type GraphLayout, type NodeBox, type Rect, type Size,
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

function overlaps(a: NodeBox, b: NodeBox): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
}

function checkLayout(name: string, run: RunView): GraphLayout {
  const layout = layoutRun(run)
  check(JSON.stringify(layout) === JSON.stringify(layoutRun(run)), `${name}: layout is not deterministic`)
  check(layout.nodes.length === run.tasks.length, `${name}: expected one box per task`)
  const byId = new Map(layout.nodes.map((n) => [n.id, n]))
  for (let i = 0; i < layout.nodes.length; i++) {
    for (let j = i + 1; j < layout.nodes.length; j++) {
      if (overlaps(layout.nodes[i], layout.nodes[j])) failures.push(`${name}: ${layout.nodes[i].id} overlaps ${layout.nodes[j].id}`)
    }
  }
  for (const edge of run.edges.filter((e) => e.kind === 'dep')) {
    const from = byId.get(edge.from)
    const to = byId.get(edge.to)
    check(!!from && !!to && from.x + from.w <= to.x, `${name}: dep ${edge.from}->${edge.to} does not run left to right`)
  }
  for (const node of layout.nodes) {
    const task = run.tasks.find((t) => t.id === node.id)
    check(task?.level === node.level, `${name}: ${node.id} level mismatch`)
  }
  check(layout.nodes.every((n) => n.x + n.w <= layout.width && n.y + n.h <= layout.height), `${name}: nodes exceed the layout size`)
  check(layout.edges.length === run.edges.length, `${name}: expected one path per edge`)
  return layout
}

const layout = checkLayout('sample', sample)
const box = (id: string) => layout.nodes.find((n) => n.id === id)!
const t4 = box('T4')
const t5 = box('T5')
check(t4.x === t5.x && t4.level === t5.level, 'chain members must share a column')
check(t5.y === t4.y + t4.h, 'chain members must touch, in chain order')
check(t4.chain === 'c1' && t5.chain === 'c1', 'chain id is carried on the boxes')
const join = layout.edges.find((e) => e.from === 'T4' && e.to === 'T5')
check(join?.joined === true && join.kind === 'order', 'T4 -> T5 must be a joined order edge')
const cross = layout.edges.find((e) => e.from === 'T2' && e.to === 'T11')
check(cross?.joined === false && cross.kind === 'order' && cross.d.length > 0, 'cross-column order edge is a plain path')
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
  gcBoxes.every((b, i) => i === 0 || (b.x === gcBoxes[0].x && b.y === gcBoxes[i - 1].y + gcBoxes[i - 1].h)),
  'generated: chain members are adjacent in order',
)

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
