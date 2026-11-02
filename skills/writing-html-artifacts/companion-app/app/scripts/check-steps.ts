import { readdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ShellView } from '../src/shell'
import type { Actions, Snapshot, Status, Step } from '../src/types'
import { StepArea } from '../src/views/step-area'

const appRoot = fileURLToPath(new URL('../', import.meta.url))
const fixtureDir = resolve(appRoot, '../fixtures/steps/valid')

const failures: string[] = []
const fail = (where: string, message: string) => failures.push(`${where}: ${message}`)
const same = (actual: unknown[], expected: unknown[], what: string) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) fail('design paragraphs', `${what}: got ${JSON.stringify(actual)}`)
}

const actions: Actions = {
  submit: async () => 'ok',
  send: async () => 'ok',
  saveDraft: async () => 'ok',
}

function snapshot(step: Step | null, extra: Partial<Snapshot> = {}): Snapshot {
  return {
    rev: 1,
    mode: 'app',
    step,
    step_state: 'open',
    status: null,
    stages: [
      { id: 'context', state: 'done' },
      { id: 'questions', state: 'current' },
    ],
    decisions: [{ id: 'd1', stage: 'context', area: 'scope', label: 'Scope', value: 'Narrow', status: 'assumed' }],
    chat: [],
    threads: [],
    review_registered: false,
    ...extra,
  }
}

function render(snap: Snapshot): string {
  return renderToStaticMarkup(createElement(StepArea, { snapshot: snap, token: 'tok', actions }))
}

function renderShell(snap: Snapshot): string {
  return renderToStaticMarkup(
    createElement(ShellView, { snapshot: snap, token: 'tok', actions, paused: false, submittedStepId: null, openStage: null, onOpenStage: () => {} }),
  )
}

/** Markup for each block whose id starts with `prefix`, each running to the next block id of any kind in `stopAt`. */
function blockChunks(html: string, prefix: string, stopAt: string): string[] {
  const marker = `data-block-id="${prefix}`
  const out: string[] = []
  let at = html.indexOf(marker)
  while (at !== -1) {
    const next = html.indexOf(stopAt, at + marker.length)
    out.push(html.slice(at, next === -1 ? undefined : next))
    at = html.indexOf(marker, at + marker.length)
  }
  return out
}

interface FixtureStep {
  kind: string
  title: string
  questions?: {
    id: string
    type: 'single' | 'multi' | 'text'
    recommended?: string
    options?: { id: string; label: string }[]
  }[]
}

function checkQuestions(name: string, fixture: FixtureStep, html: string) {
  if (/<input[^>]*\schecked[\s=>]/.test(html)) fail(name, 'an option input is rendered checked')
  for (const question of fixture.questions ?? []) {
    const where = `${name} question ${question.id}`
    const block = blockChunks(html, `question:${question.id}"`, 'data-block-id="question:')[0] ?? ''
    if (!block) {
      fail(where, 'no data-block-id="question:<id>" block')
      continue
    }
    if (question.type === 'text') {
      if (!/<textarea/.test(block)) fail(where, 'text question has no textarea')
      if (/type="(radio|checkbox)"/.test(block)) fail(where, 'text question renders option inputs')
      continue
    }
    if (!new RegExp(`<label[^>]*for="[^"]*-other"[^>]*>Other</label>\\s*<input[^>]*type="text"`).test(block)) {
      fail(where, 'no Other text input')
    }
    if (question.recommended) {
      const options = blockChunks(block, `option:${question.id}/`, 'data-block-id="')
      if (!options[0]?.includes(`option:${question.id}/${question.recommended}"`)) fail(where, 'recommended option is not rendered first')
      if (!options[0]?.includes('(Recommended)')) fail(where, 'first option is not labeled "(Recommended)"')
      if (options.slice(1).some((chunk) => chunk.includes('(Recommended)'))) fail(where, 'a non-recommended option is labeled "(Recommended)"')
    }
    if (!/>Skip</.test(block)) fail(where, 'no Skip control')
  }
}

function checkKind(name: string, step: FixtureStep, html: string) {
  const has = (needle: RegExp | string, what: string) => {
    if (typeof needle === 'string' ? !html.includes(needle) : !needle.test(html)) fail(name, `missing ${what}`)
  }
  switch (step.kind) {
    case 'approaches':
      has('data-block-id="approach:', 'approach block ids')
      has('type="radio"', 'approach radio inputs')
      break
    case 'design-section':
      has(/Design \d+ of \d+/, '"Design N of M"')
      has('Looks right', 'Looks right control')
      has('Needs changes', 'Needs changes control')
      has('data-block-id="section:', 'section block ids')
      break
    case 'spec-review':
      has(/Sign off|\/_quirk\/review\?t=tok/, 'Sign off button or review iframe')
      break
    case 'edit-card':
      has('Confirm and redo', 'Confirm and redo button')
      has('Cancel', 'Cancel button')
      break
    case 'hand-off':
      has('data-block-id="choice:', 'choice block ids')
      has('Recommended', 'recommended marker')
      break
    default:
      break
  }
}

const files = (await readdir(fixtureDir)).filter((f) => f.endsWith('.json')).sort()
if (!files.length) fail('fixtures', `no fixtures found in ${fixtureDir}`)

for (const file of files) {
  const fixture = JSON.parse(await readFile(resolve(fixtureDir, file), 'utf8')) as FixtureStep
  const step = { ...fixture, id: `step-${file}`, nonce: 'nonce-1' } as unknown as Step
  let html = ''
  try {
    html = render(snapshot(step))
    renderShell(snapshot(step))
  } catch (error) {
    fail(file, `render threw: ${error instanceof Error ? error.message : String(error)}`)
    continue
  }
  if (!html.includes(`data-step-kind="${fixture.kind}"`)) fail(file, 'step view did not render')
  if (fixture.kind === 'questions') checkQuestions(file, fixture, html)
  else checkKind(file, fixture, html)
  const changed = (fixture as { changed?: { summary: string; blocks: string[] } }).changed
  if (changed) {
    if (!html.includes('What changed')) fail(file, 'missing the "What changed" banner')
    for (const block of changed.blocks) {
      if (!new RegExp(`data-block-id="${block}"[^>]*data-changed="true"|data-changed="true"[^>]*data-block-id="${block}"`).test(html)) {
        fail(file, `block ${block} is not highlighted`)
      }
    }
  }
}

// design paragraphs carry `section:<id>/p<n>`, 0-based in document order, from markdown, agent HTML and the diagram alike
{
  const section = (sections: unknown[], changed?: { summary: string; blocks: string[] }) =>
    render(snapshot({ id: 'sd', nonce: 'n', v: 1, kind: 'design-section', stage: 'design', title: 'T', index: 1, total: 1, sections, ...(changed ? { changed } : {}) } as unknown as Step))
  const ids = (html: string) => [...html.matchAll(/data-block-id="(section:[^"]*\/p\d+)"/g)].map((m) => m[1])
  const md = ['First paragraph.', '- a\n- b', '1. one\n2. two', '```\ncode\n```', '> quoted', '| h |\n|---|\n| c |', '## Heading', 'Last **one**.'].join('\n\n')
  const mdHtml = section([{ id: 'arch', title: 'Arch', body_md: md }])
  same(ids(mdHtml), ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'].map((p) => `section:arch/${p}`), 'markdown block ids')
  if (!/<p data-block-id="section:arch\/p0">First paragraph\.<\/p>/.test(mdHtml)) fail('design paragraphs', 'p0 is not the first paragraph')
  if (!/<li>a<\/li>/.test(mdHtml)) fail('design paragraphs', 'list items must not take block ids')
  same(ids(section([{ id: 'arch', title: 'Arch', body_md: md }])), ids(mdHtml), 'ids are not stable across renders')

  const agentHtml = '<p>One</p>\n<!-- note -->\n<ul><li><p>nested</p></li></ul><div class="a>b" data-x="1"><p>inner</p></div><q-flow summary="s"><span data-q-flow-node="a">A</span></q-flow><script>if (a < b) {}</script><img src="x"><table><tr><td>c</td></tr></table>'
  const htmlOnly = section([{ id: 'data', title: 'Data', body_html: agentHtml }])
  same(ids(htmlOnly), ['p0', 'p1', 'p2', 'p3', 'p4'].map((p) => `section:data/${p}`), 'agent HTML block ids')
  if (!/<q-flow data-block-id="section:data\/p3" summary="s">/.test(htmlOnly)) fail('design paragraphs', 'the q-flow container is not numbered')
  if (!/<div data-block-id="section:data\/p2" class="a>b" data-x="1">/.test(htmlOnly)) fail('design paragraphs', 'a div with ">" in an attribute is not numbered whole')

  const mixed = section([{ id: 'x', title: 'X', body_md: 'a\n\nb', body_html: '<p>c</p><p data-commentable="own">d</p>', diagram: 'graph LR; A-->B' }])
  same(ids(mixed), ['p0', 'p1', 'p2', 'p4'].map((p) => `section:x/${p}`), 'markdown, agent HTML and diagram numbering')
  if (!/data-commentable="own"/.test(mixed) || /data-block-id="section:x\/p3"/.test(mixed)) fail('design paragraphs', 'an agent-marked block must keep its own id')

  const marked = section([{ id: 'arch', title: 'Arch', body_md: 'a\n\nb' }], { summary: 's', blocks: ['section:arch/p1'] })
  if (!/data-block-id="section:arch\/p1" data-changed="true"/.test(marked)) fail('design paragraphs', 'a changed paragraph is not highlighted')
  if (/data-block-id="section:arch\/p0" data-changed/.test(marked)) fail('design paragraphs', 'an unchanged paragraph is highlighted')
}

const waitingStatus: Status = { text: 'Checking approaches', progress: '2/3', interruptible: true, started_at: new Date().toISOString() }
const waiting = render(snapshot(null, { status: waitingStatus }))
if (!waiting.includes('Continue without the rest')) fail('waiting', 'no "Continue without the rest" button when interruptible')
if (!waiting.includes('2 of 3')) fail('waiting', 'progress is not shown as "2 of 3"')
if (!waiting.includes('Checking approaches')) fail('waiting', 'status text is missing')
const quiet = render(snapshot(null, { status: { ...waitingStatus, interruptible: false } }))
if (quiet.includes('Continue without the rest')) fail('waiting', 'Continue button shown when not interruptible')
const submitted = render(snapshot({ ...(JSON.parse(await readFile(resolve(fixtureDir, 'questions-single.json'), 'utf8')) as object), id: 's', nonce: 'n' } as unknown as Step, { step_state: 'submitted', status: waitingStatus }))
if (!submitted.includes('Continue without the rest')) fail('waiting', 'a submitted step does not show the waiting view')

if (failures.length) {
  console.error(`steps-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log(`steps-check passed: ${files.length} step fixtures plus waiting views rendered.`)
}
