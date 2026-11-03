import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { layoutRun, type GraphLayout, type NodeBox } from '../src/run/layout'
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

const emptyHtml = renderToStaticMarkup(createElement(RunGraph, { run: view([], []), ...props }))
check(emptyHtml.includes('<svg'), 'an empty run still renders an svg')

if (failures.length) {
  console.error(`run-graph-check failed:\n- ${failures.join('\n- ')}`)
  process.exitCode = 1
} else {
  console.log('run-graph-check passed: layout is deterministic and non-overlapping, and the graph renders every task state.')
}
