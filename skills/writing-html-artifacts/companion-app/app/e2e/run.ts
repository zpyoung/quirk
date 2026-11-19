/**
 * End-to-end check of the companion's app mode: a real server (python3 companion.py start --app, real
 * built shell, no override), driven with the same CLI the brainstorming agent uses, and a real Chromium.
 *
 * Usage: pnpm run e2e   (from companion-app/app)
 * Exit codes: 0 every scenario passed, 1 a scenario failed, 3 no browser could be launched.
 * Never downloads a browser; it only drives one that is already installed.
 */
import { execFile } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Browser, type BrowserContext, type Locator, type Page } from 'playwright-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../../../..')
const COMPANION = path.join(REPO, 'skills/writing-html-artifacts/scripts/companion.py')
const EVENT_PATH = '/_quirk/app/event'
const SETTLE_MS = 1500
/** Kit diagrams load a large script and lay out in the page; on a busy machine that takes tens of seconds. */
const DIAGRAM_MS = 60_000

interface CliResult {
  code: number
  out: any
  stderr: string
}

let session = ''
let cursor = 0

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

function same(actual: unknown, expected: unknown, what: string): void {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  assert(a === e, `${what}: expected ${e}, got ${a}`)
}

/** Runs one companion subcommand; the CLI prints exactly one JSON object whatever the exit code. */
function cli(...args: (string | number)[]): Promise<CliResult> {
  const env = { ...process.env }
  delete env.QUIRK_COMPANION_SHELL
  return new Promise((resolve, reject) => {
    execFile('python3', [COMPANION, ...args.map(String)], { env, timeout: 120_000 }, (error, stdout, stderr) => {
      const code = error ? (typeof error.code === 'number' ? error.code : 1) : 0
      try {
        resolve({ code, out: JSON.parse(stdout.trim()), stderr })
      } catch {
        reject(new Error(`companion ${args.join(' ')} printed no JSON (exit ${code}): ${stdout} ${stderr}`))
      }
    })
  })
}

async function cliOk(...args: (string | number)[]): Promise<any> {
  const result = await cli(...args)
  assert(result.code === 0, `companion ${args[0]} exited ${result.code}: ${JSON.stringify(result.out)} ${result.stderr}`)
  return result.out
}

let fileCount = 0
async function writeJson(name: string, value: unknown): Promise<string> {
  fileCount += 1
  const file = path.join(path.dirname(path.dirname(path.dirname(session))), `${name}-${fileCount}.json`)
  await writeFile(file, JSON.stringify(value), 'utf8')
  return file
}

async function step(spec: Record<string, unknown>): Promise<{ step: string; nonce: string }> {
  return cliOk('step', session, await writeJson('step', { v: 1, ...spec }))
}

async function decide(decisions: unknown[]): Promise<void> {
  await cliOk('decide', session, await writeJson('decisions', decisions))
}

/** Events the user produced since the last call; the cursor moves so each event is returned once. */
async function nextEvents(timeoutSeconds = 8): Promise<any[]> {
  const out = await cliOk('next', session, '--after', cursor, '--timeout', timeoutSeconds)
  cursor = out.cursor
  return out.events
}

async function launchBrowser(): Promise<Browser | null> {
  const candidates: [string, Parameters<typeof chromium.launch>[0]][] = [
    ['chrome', { channel: 'chrome' }],
    ['msedge', { channel: 'msedge' }],
  ]
  if (process.env.CHROME_PATH) candidates.push(['CHROME_PATH', { executablePath: process.env.CHROME_PATH }])
  let bundled: string | null = null
  try {
    bundled = chromium.executablePath()
  } catch {
    bundled = null
  }
  if (bundled && existsSync(bundled)) candidates.push(['chromium', { executablePath: bundled }])
  for (const [label, options] of candidates) {
    try {
      const browser = await chromium.launch({ headless: true, ...options })
      console.log(`browser: ${label}`)
      return browser
    } catch (error) {
      console.error(`browser ${label} did not launch: ${String((error as Error).message).split('\n')[0]}`)
    }
  }
  return null
}

const questionsStep = (extra: Record<string, unknown> = {}) => ({
  kind: 'questions',
  stage: 'questions',
  title: 'Scope',
  questions: [
    {
      id: 'scope',
      type: 'single',
      prompt: 'How wide?',
      recommended: 'narrow',
      options: [
        { id: 'wide', label: 'Option wide', description: 'Everything' },
        { id: 'narrow', label: 'Option narrow', description: 'Just the core' },
        { id: 'mid', label: 'Option mid' },
      ],
    },
    {
      id: 'extras',
      type: 'multi',
      prompt: 'Which extras?',
      options: [
        { id: 'docs', label: 'Option docs' },
        { id: 'tests', label: 'Option tests' },
      ],
    },
    { id: 'notes', type: 'text', prompt: 'Anything else we should know?' },
  ],
  ...extra,
})

const approachesStep = () => ({
  kind: 'approaches',
  stage: 'approaches',
  title: 'Approaches',
  approaches: [
    { id: 'a', title: 'Approach a', summary_md: 'First **way**.', recommended: false },
    { id: 'b', title: 'Approach b', summary_md: 'Second way.', recommended: true, pros: ['fast'], cons: ['new'] },
    { id: 'c', title: 'Approach c', summary_md: 'Third way.', recommended: false },
  ],
})

const designStep = (extra: Record<string, unknown> = {}) => ({
  kind: 'design-section',
  stage: 'design',
  title: 'Design',
  index: 1,
  total: 3,
  sections: [
    { id: 'arch', title: 'Architecture', body_md: 'Two services.' },
    { id: 'data', title: 'Data', body_md: 'One table.' },
  ],
  ...extra,
})

const FLOW_HTML = `<q-flow summary="Orders flow from checkout to the ledger." direction="right">
  <script type="application/json">
  {
    "nodes": [
      {"id": "checkout", "label": "Checkout"},
      {"id": "ledger", "label": "Ledger"}
    ],
    "edges": [
      {"from": "checkout", "to": "ledger", "label": "order.created"}
    ]
  }
  </script>
</q-flow>`

const TALL_FLOW_HTML = `<q-flow summary="Four steps top to bottom." direction="down">
  <script type="application/json">
  {
    "nodes": [
      {"id": "plan", "label": "Plan"},
      {"id": "build", "label": "Build"},
      {"id": "review", "label": "Review"},
      {"id": "merge", "label": "Merge"}
    ],
    "edges": [
      {"from": "plan", "to": "build"},
      {"from": "build", "to": "review"},
      {"from": "review", "to": "merge"}
    ]
  }
  </script>
</q-flow>`

const MINI_FLOW_HTML = `<q-flow summary="Two services." direction="right">
  <script type="application/json">
  {
    "nodes": [
      {"id": "svc-a", "label": "Service A"},
      {"id": "svc-b", "label": "Service B"}
    ],
    "edges": [{"from": "svc-a", "to": "svc-b", "label": "calls"}]
  }
  </script>
</q-flow>`

const THREAD_TEXT = 'Is B really cheaper?'
let approachThreadId = ''

/** Hovers or focuses a block, clicks its Comment pin, and posts `text` from the popover. */
async function commentOn(page: Page, block: Locator, text: string): Promise<void> {
  await block.hover()
  const pin = page.locator('.comment-pin')
  await pin.waitFor({ state: 'visible', timeout: 5000 })
  assert(await pin.evaluate((el) => el.parentElement?.closest('button, label, [role="button"]') == null), 'the Comment pin sits inside a button or label')
  await pin.click()
  const popover = page.locator('.thread-popover')
  await popover.waitFor({ state: 'visible', timeout: 5000 })
  await popover.getByLabel('Add a comment').fill(text)
  await popover.getByRole('button', { name: 'Comment', exact: true }).click()
  await popover.locator('.thread-text', { hasText: text }).waitFor({ timeout: 10_000 })
}

interface Env {
  context: BrowserContext
  url: string
  /** Every draft event the page posted, in order, across all pages of the context. */
  drafts: string[]
}

async function openPage(env: Env): Promise<{ page: Page; consoleErrors: string[] }> {
  const page = await env.context.newPage()
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`))
  await page.goto(env.url)
  return { page, consoleErrors }
}

async function waitForStep(page: Page, id: string): Promise<void> {
  await page.locator(`[data-step-id="${id}"]`).waitFor({ state: 'visible', timeout: 15_000 })
}

async function submitPick(page: Page, pick: string): Promise<void> {
  await page.locator(`.approach-card input[value="${pick}"]`).check()
  await page.getByRole('button', { name: 'Submit pick' }).click()
  await page.getByRole('heading', { name: 'Working on it' }).waitFor({ timeout: 10_000 })
}

/** Where the runner keeps its scoped temp files: the temp root that also holds the step JSON files. */
function scratchRoot(): string {
  return path.dirname(path.dirname(path.dirname(session)))
}

/** A three-screen mock that routes by plain `#/<screen>` links, like an agent-written mock does. */
function exportsMockHtml(version: number): string {
  const newExport = version === 1 ? '<button data-pin="new-export" class="btn">New export</button>' : ''
  const rowText = version === 1 ? 'Q3 report.csv' : 'Q3 report.csv (scheduled)'
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>Exports mock v${version}</title>
<style>body{font:16px system-ui;margin:0;padding:16px}nav a{margin-right:16px}.btn{padding:8px 12px}section>div>*{margin:8px 0}</style>
</head><body>
<nav><a href="#/exports">Exports</a><a href="#/saved">Saved</a><a href="#/detail">Detail</a></nav>
<section data-screen="exports">
  <div data-state="default"><h1>Exports</h1>${newExport}<div data-pin="export-row">${rowText}</div></div>
  <div data-state="empty"><h1>Exports</h1><p data-pin="empty-msg">No exports yet.</p></div>
</section>
<section data-screen="saved">
  <div data-state="default"><h1>Saved exports</h1><ul data-pin="saved-list"><li>Weekly.csv</li></ul></div>
</section>
<section data-screen="detail">
  <div data-state="default"><h1>Export detail</h1><p data-pin="detail-title">Q3 report.csv, 12 KB</p></div>
</section>
<script>
function route() {
  var id = location.hash.replace(/^#\\//, '') || 'exports'
  document.querySelectorAll('[data-screen]').forEach(function (s) { s.hidden = s.getAttribute('data-screen') !== id })
}
window.addEventListener('hashchange', route)
route()
</script>
</body></html>`
}

function exportsScreens(version: number): unknown {
  const exportsElements: unknown[] = [{ pin: 'export-row', label: 'Export row', component: 'Row' }]
  if (version === 1) exportsElements.unshift({ pin: 'new-export', label: 'New export button', component: 'Button' })
  return {
    ui_layer: true,
    screens: [
      { id: 'exports', title: 'Exports', purpose: 'List recent exports', states: ['default', 'empty'], elements: exportsElements },
      { id: 'saved', title: 'Saved exports', purpose: 'Exports kept for later', states: ['default'], elements: [{ pin: 'saved-list', label: 'Saved list', component: 'List' }] },
      { id: 'detail', title: 'Export detail', purpose: 'One export in full', states: ['default'], elements: [{ pin: 'detail-title', label: 'Title', component: null }] },
    ],
  }
}

let mockFileCount = 0
async function registerMock(version: number, changed?: string[]): Promise<void> {
  mockFileCount += 1
  const dir = scratchRoot()
  const html = path.join(dir, `mock-v${version}-${mockFileCount}.html`)
  await writeFile(html, exportsMockHtml(version), 'utf8')
  const args: (string | number)[] = ['mock', session, html, '--version', version, '--screens', await writeJson('mock-screens', exportsScreens(version))]
  if (changed) args.push('--changed', await writeJson('mock-changed', { changed }))
  await cliOk(...args)
}

const PIN_ID_V1 = /^mock:v1\/exports\/default\/new-export\/x([0-9]{1,3})-y([0-9]{1,3})$/

type Scenario = (env: Env) => Promise<void>

const scenarios: [string, Scenario][] = [
  [
    'a. question batch',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(questionsStep())
        await waitForStep(page, s.step)
        same(await page.locator('input:checked').count(), 0, 'preselected options')
        const scope = page.locator('[data-block-id="question:scope"]')
        const labels = await scope.locator('.option-label').allInnerTexts()
        assert(labels[0]?.includes('Option narrow') && labels[0].includes('(Recommended)'), `recommended option not first: ${JSON.stringify(labels)}`)
        same(await page.getByText('(Recommended)').count(), 1, 'number of Recommended tags')
        assert(!labels.slice(1).some((label) => label.includes('(Recommended)')), 'a non-recommended option is labeled Recommended')

        await scope.locator('input[value="wide"]').check()
        await page.locator('[data-block-id="question:extras"]').getByLabel('Other').fill('Custom extra')
        await page.locator('[data-block-id="question:notes"]').getByRole('button', { name: 'Skip' }).click()
        await page.getByLabel('Comment on this batch (optional)').fill('Looks fine overall')
        await page.getByRole('button', { name: 'Submit answers' }).click()
        await page.getByRole('heading', { name: 'Working on it' }).waitFor({ timeout: 10_000 })

        const events = await nextEvents()
        same(events.map((e) => e.type), ['submit'], 'event types')
        const payload = events[0].payload
        same(payload.answers.scope, { selected: ['wide'] }, 'single answer')
        same(payload.answers.extras, { other: 'Custom extra' }, 'multi answer')
        same(payload.answers.notes, { skipped: true }, 'skipped text answer')
        same(payload.comment, 'Looks fine overall', 'batch comment')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'b. draft survives refresh',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(questionsStep())
        await waitForStep(page, s.step)
        const other = () => page.locator('[data-block-id="question:extras"]').getByLabel('Other')
        await other().fill('half typed thought')
        await sleep(SETTLE_MS)
        await page.reload()
        await waitForStep(page, s.step)
        const restored = await other().inputValue()
        same(restored, 'half typed thought', 'restored Other text')

        const before = env.drafts.length
        await sleep(4000)
        const resent = env.drafts.length - before
        assert(resent <= 1, `the restored draft was posted ${resent} times in 4 s of idle`)
      } finally {
        await page.close()
      }
    },
  ],
  [
    'c. approach pick survives refresh',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(approachesStep())
        await waitForStep(page, s.step)
        await page.locator('.approach-card input[value="c"]').check()
        await sleep(SETTLE_MS)
        await page.reload()
        await waitForStep(page, s.step)
        assert(await page.locator('.approach-card input[value="c"]').isChecked(), 'the picked approach is not restored')
        same(await page.locator('input:checked').count(), 1, 'checked radios after restore')
        await page.getByRole('button', { name: 'Submit pick' }).click()
        await page.getByRole('heading', { name: 'Working on it' }).waitFor({ timeout: 10_000 })
        const events = await nextEvents()
        same(events.map((e) => e.type), ['submit'], 'event types')
        same(events[0].payload, { pick: 'c' }, 'submit payload')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'd. ready signal',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const first = await step(approachesStep())
        await waitForStep(page, first.step)
        const originalTitle = await page.title()
        assert(originalTitle !== '(1) Your turn', 'the title already shows the ready signal')
        // string scripts: a function body would be wrapped with a tsx helper the page does not have
        await page.evaluate(`(() => {
          Object.defineProperty(document, 'hidden', { configurable: true, get: () => true })
          Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
          document.dispatchEvent(new Event('visibilitychange'))
        })()`)
        const second = await step(designStep())
        await page.waitForFunction(`document.title === '(1) Your turn'`, null, { timeout: 15_000 })
        await waitForStep(page, second.step)
        await page.evaluate(`(() => {
          delete document.hidden
          delete document.visibilityState
          document.dispatchEvent(new Event('visibilitychange'))
          window.dispatchEvent(new Event('focus'))
        })()`)
        await page.waitForFunction(`document.title === ${JSON.stringify(originalTitle)}`, null, { timeout: 5000 })
      } finally {
        await page.close()
      }
    },
  ],
  [
    'e. waiting view and Continue',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(approachesStep())
        await waitForStep(page, s.step)
        await submitPick(page, 'a')
        same((await nextEvents()).map((e) => e.type), ['submit'], 'event types after submit')

        await cliOk('status', session, '--text', 'Checking 3 approaches', '--progress', '2/3', '--interruptible')
        await page.getByText('Checking 3 approaches').waitFor({ timeout: 10_000 })
        await page.getByText('2 of 3').waitFor({ timeout: 5000 })
        await page.getByRole('button', { name: 'Continue without the rest' }).click()
        const events = await nextEvents()
        same(events.map((e) => e.type), ['continue'], 'event types after Continue')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'f. design needs changes, then a revision',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(designStep())
        await waitForStep(page, s.step)
        await page.getByLabel('Comment (optional)').fill('Split the data section')
        await page.getByRole('button', { name: 'Needs changes' }).click()
        await page.getByRole('heading', { name: 'Working on it' }).waitFor({ timeout: 10_000 })
        const events = await nextEvents()
        same(events.map((e) => e.type), ['submit'], 'event types')
        same(events[0].payload, { verdict: 'needs-changes', comment: 'Split the data section' }, 'verdict payload')

        const revision = await step(designStep({ changed: { summary: 'Split the data section in two', blocks: ['section:data'] } }))
        await waitForStep(page, revision.step)
        const banner = page.locator('.changed-banner')
        await banner.waitFor({ timeout: 10_000 })
        const text = await banner.innerText()
        assert(text.includes('What changed') && text.includes('Split the data section in two'), `changed banner text: ${text}`)
        same(await page.locator('[data-block-id="section:data"]').getAttribute('data-changed'), 'true', 'changed marker on the listed block')
        same(await page.locator('[data-block-id="section:arch"]').getAttribute('data-changed'), null, 'changed marker on an untouched block')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'g. rail edit becomes an edit card',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(designStep())
        await decide([
          { id: 'storage', stage: 'questions', area: 'Data', label: 'Storage', value: 'SQL', status: 'confirmed' },
          { id: 'shape', stage: 'approaches', area: 'Shape', label: 'Shape', value: 'Approach b', status: 'confirmed' },
        ])
        await waitForStep(page, s.step)
        await page.locator('.rail-button', { hasText: 'Questions' }).click()
        const item = page.locator('[data-decision-id="storage"]')
        await item.waitFor({ timeout: 10_000 })
        await item.getByRole('button', { name: /Change/ }).click()
        await item.getByLabel('New value').fill('Files')
        await item.getByLabel('Note (optional)').fill('Easier to ship')
        await item.getByRole('button', { name: 'Request change' }).click()
        const events = await nextEvents()
        same(events.map((e) => e.type), ['edit-request'], 'event types')
        same(events[0].payload, { decision_id: 'storage', to: 'Files', note: 'Easier to ship' }, 'edit-request payload')

        const card = await step({
          kind: 'edit-card',
          stage: 'design',
          title: 'Change storage',
          decision_id: 'storage',
          from: 'SQL',
          to: 'Files',
          invalidates: [{ label: 'Design' }],
          origin: 'rail',
        })
        await waitForStep(page, card.step)
        await page.getByRole('button', { name: 'Confirm and redo' }).click()
        const decisions = await nextEvents()
        same(decisions.map((e) => e.type), ['edit-decision'], 'event types after confirm')
        same(decisions[0].payload, { decision: 'confirm' }, 'edit-decision payload')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'h. reconnect after server restart',
    async (env) => {
      const { page } = await openPage(env)
      try {
        const s = await step(questionsStep())
        await waitForStep(page, s.step)
        await page.evaluate(`window.__e2eMarker = 'still-here'`)
        const stopped = await cliOk('stop', session)
        same(stopped, { stopped: true }, 'stop result')
        await page.getByText('Paused, reconnecting').waitFor({ timeout: 30_000 })

        const restarted = await cliOk('start', session, '--app')
        same(restarted.url, env.url, 'url after restart')
        await page.getByText('Paused, reconnecting').waitFor({ state: 'detached', timeout: 30_000 })
        same(await page.evaluate(`window.__e2eMarker`), 'still-here', 'window marker (page was reloaded)')
        await waitForStep(page, s.step)
      } finally {
        await page.close()
      }
    },
  ],
  [
    'i. diagrams render',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        const mermaid = await step({
          kind: 'questions',
          stage: 'questions',
          title: 'Diagram question',
          questions: [
            {
              id: 'flow',
              type: 'single',
              prompt: 'Does the flow look right?',
              diagram: 'graph TD; A-->B',
              options: [
                { id: 'yes', label: 'Yes' },
                { id: 'no', label: 'No' },
              ],
            },
          ],
        })
        await waitForStep(page, mermaid.step)
        await page.locator('[data-block-id="question:flow"] figure.diagram svg').first().waitFor({ timeout: DIAGRAM_MS })

        const kit = await step({
          kind: 'questions',
          stage: 'questions',
          title: 'Flow question',
          questions: [
            {
              id: 'kit',
              type: 'single',
              prompt: 'Does this flow look right?',
              content_html: FLOW_HTML,
              options: [
                { id: 'yes', label: 'Yes' },
                { id: 'no', label: 'No' },
              ],
            },
          ],
        })
        await waitForStep(page, kit.step)
        await page.locator('[data-block-id="question:kit"] q-flow svg').first().waitFor({ timeout: DIAGRAM_MS })

        // a wide window is where a fluid agent svg blows up and where a cap would clip a kit diagram
        await page.setViewportSize({ width: 2400, height: 1000 })
        const sizing = await step({
          kind: 'design-section',
          stage: 'design',
          title: 'Sizing',
          index: 1,
          total: 1,
          sections: [
            { id: 'fluid', title: 'Fluid picture', body_html: '<svg viewBox="0 0 300 64" width="100%"><rect width="300" height="64"/></svg>' },
            { id: 'tall', title: 'Tall flow', body_html: TALL_FLOW_HTML },
          ],
        })
        // the flow layout holds the main thread for seconds before the step paints
        await page.locator(`[data-step-id="${sizing.step}"]`).waitFor({ state: 'visible', timeout: DIAGRAM_MS })
        const fluid = await page.locator('[data-block-id="section:fluid"] svg').first().boundingBox()
        assert(fluid && fluid.width <= 640.5, `fluid svg not capped at 40rem: ${JSON.stringify(fluid)}`)
        const tall = page.locator('[data-block-id="section:tall"] q-flow svg').first()
        await tall.waitFor({ timeout: DIAGRAM_MS })
        const flowBox = await tall.boundingBox()
        assert(flowBox && flowBox.height > 200, `kit flow svg collapsed: ${JSON.stringify(flowBox)}`)
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'j. chat round trip',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        const s = await step(questionsStep())
        await waitForStep(page, s.step)
        const log = page.getByRole('log')
        await page.getByLabel('Message', { exact: true }).fill('<b>bold</b>')
        await page.getByRole('button', { name: 'Send' }).click()
        const mine = log.locator('.chat-entry[data-from="user"]', { hasText: '<b>bold</b>' })
        await mine.waitFor({ timeout: 10_000 })
        same(await log.locator('b').count(), 0, 'bold elements created from user text')
        assert((await mine.innerText()).includes('Queued'), 'the sent message has no Queued marker')
        same(await page.getByLabel('Message', { exact: true }).inputValue(), '', 'composer after a successful send')

        const events = await nextEvents()
        same(events.map((e) => e.type), ['chat'], 'event types')
        same(events[0].payload, { text: '<b>bold</b>' }, 'chat payload')
        await mine.getByText('Queued').waitFor({ state: 'detached', timeout: 3000 })

        await cliOk('say', session, '--text', 'Because B keeps undo.')
        const agent = log.locator('.chat-entry[data-from="agent"]', { hasText: 'Because B keeps undo.' })
        await agent.waitFor({ timeout: 10_000 })
        assert(!(await agent.innerText()).includes('Queued'), 'an agent message shows Queued')

        await cliOk('say', session, '--from', 'user', '--text', 'typed in terminal')
        await log.locator('.chat-entry[data-from="user"]', { hasText: 'typed in terminal' }).waitFor({ timeout: 10_000 })

        await page.getByLabel('Message', { exact: true }).fill('line one')
        await page.getByLabel('Message', { exact: true }).press('Shift+Enter')
        await page.getByLabel('Message', { exact: true }).pressSequentially('line two')
        same(await page.getByLabel('Message', { exact: true }).inputValue(), 'line one\nline two', 'Shift+Enter newline')
        await page.getByLabel('Message', { exact: true }).press('Enter')
        await log.locator('.chat-entry[data-from="user"]', { hasText: 'line two' }).waitFor({ timeout: 10_000 })
        same((await nextEvents()).map((e) => e.payload.text), ['line one\nline two'], 'Enter sends the multi-line message')
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'k. comment on an approach card',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        const s = await step(approachesStep())
        await waitForStep(page, s.step)
        const card = page.locator('[data-block-id="approach:b"]')
        await card.locator('input[type="radio"]').focus()
        await page.locator('.comment-pin').waitFor({ state: 'visible', timeout: 5000 })
        await commentOn(page, card, THREAD_TEXT)

        const events = await nextEvents()
        same(events.map((e) => e.type), ['comment'], 'event types')
        same(events[0].payload.block_id, 'approach:b', 'comment block id')
        same(events[0].payload.text, THREAD_TEXT, 'comment text')
        approachThreadId = events[0].payload.thread_id
        assert(typeof approachThreadId === 'string' && approachThreadId, 'the comment event has no thread_id')

        const log = page.getByRole('log')
        const pointer = log.locator('.chat-pointer')
        await pointer.waitFor({ timeout: 10_000 })
        same((await pointer.innerText()).trim(), `Comment: ${THREAD_TEXT}`, 'pointer text')
        same(await pointer.evaluate((el) => (el.closest('li')?.getBoundingClientRect().height ?? 999) < 60), true, 'pointer is one line')

        await cliOk('reply', session, approachThreadId, '--text', 'Fixed in the revision', '--resolve', 'addressed')
        const popover = page.locator('.thread-popover')
        await popover.getByText('Fixed in the revision').waitFor({ timeout: 10_000 })
        await popover.getByText('Addressed', { exact: true }).waitFor({ timeout: 5000 })
        same(await log.getByText('Fixed in the revision').count(), 0, 'agent reply shown in the chat log')

        await popover.getByRole('button', { name: 'Close' }).click()
        await popover.waitFor({ state: 'detached', timeout: 5000 })
        await page.evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
        await pointer.click()
        await popover.waitFor({ state: 'visible', timeout: 5000 })
        await popover.getByText('Fixed in the revision').waitFor({ timeout: 5000 })
        const box = await card.boundingBox()
        const viewport = page.viewportSize()
        assert(box && viewport && box.y + box.height > 0 && box.y < viewport.height, 'the pointer did not scroll the card into view')
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'l. comment on a diagram node',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        const s = await step({
          kind: 'questions',
          stage: 'questions',
          title: 'Service question',
          questions: [
            {
              id: 'svc',
              type: 'single',
              prompt: 'Are these the right services?',
              content_html: MINI_FLOW_HTML,
              options: [
                { id: 'yes', label: 'Yes' },
                { id: 'no', label: 'No' },
              ],
            },
          ],
        })
        await waitForStep(page, s.step)
        const node = page.locator('q-flow [data-q-flow-node="svc-a"]')
        await node.waitFor({ timeout: DIAGRAM_MS })
        await commentOn(page, node, 'Should A own the queue?')
        const events = await nextEvents()
        same(events.map((e) => e.type), ['comment'], 'event types')
        same(events[0].payload.block_id, `node:${s.step}/0/svc-a`, 'diagram node block id')
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'm. thread survives a revision',
    async (env) => {
      const { page } = await openPage(env)
      try {
        assert(approachThreadId, 'scenario k did not leave a thread')
        const revision = await step({ ...approachesStep(), changed: { summary: 'Reworded B', blocks: ['approach:b'] } })
        await waitForStep(page, revision.step)
        const badge = page.locator('.comment-badge[data-for-block="approach:b"]')
        await badge.waitFor({ state: 'visible', timeout: 10_000 })
        same((await badge.innerText()).trim(), '1', 'badge count')
        same(await page.locator('.comment-badge[data-for-block="approach:a"]').count(), 0, 'badge on an approach without threads')
        await badge.click()
        const popover = page.locator('.thread-popover')
        await popover.getByText(THREAD_TEXT).waitFor({ timeout: 5000 })
        await popover.getByText('Addressed', { exact: true }).waitFor({ timeout: 5000 })
      } finally {
        await page.close()
      }
    },
  ],
  [
    'n. comment on a design paragraph',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        const s = await step(
          designStep({
            sections: [{ id: 'arch', title: 'Architecture', body_md: 'Two services talk over a queue.\n\nThe ledger is the single writer.' }],
          }),
        )
        await waitForStep(page, s.step)
        same(await page.locator('[data-block-id^="section:arch/p"]').count(), 2, 'paragraph blocks in the section')
        const second = page.locator('[data-block-id="section:arch/p1"]')
        same((await second.innerText()).trim(), 'The ledger is the single writer.', 'second paragraph text')
        await commentOn(page, second, 'Who guards the writer?')
        const events = await nextEvents()
        same(events.map((e) => e.type), ['comment'], 'event types')
        same(events[0].payload.block_id, 'section:arch/p1', 'comment block id')
        same(events[0].payload.text, 'Who guards the writer?', 'comment text')
        await page.locator('.comment-badge[data-for-block="section:arch/p1"]').waitFor({ state: 'attached', timeout: 10_000 })
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
  [
    'o. mock review: pin, revise, sign off',
    async (env) => {
      const { page, consoleErrors } = await openPage(env)
      try {
        await registerMock(1)
        const mockStep = (version: number) => step({ kind: 'mock-review', stage: 'ux-review', title: `Exports mock v${version}`, version })
        const s1 = await mockStep(1)
        await waitForStep(page, s1.step)

        const shellFrame = page.locator('iframe.mock-frame')
        const src = (await shellFrame.getAttribute('src')) ?? ''
        const token = new URL(src, env.url).searchParams.get('t') ?? ''
        assert(src.startsWith('/_quirk/mock/1?t=') && token, `unexpected mock iframe src: ${src}`)
        const harness = page.frameLocator('iframe.mock-frame')
        const mock = harness.frameLocator('#mock-frame')
        const current = (title: string) => harness.locator('.screen-item.current .title', { hasText: title })
        await harness.locator('#version-chip', { hasText: 'Mock v1' }).waitFor({ timeout: 15_000 })
        await current('Exports').waitFor({ timeout: 10_000 })

        // an in-mock link moves the rail
        await mock.locator('a[href="#/saved"]').click()
        await current('Saved exports').waitFor({ timeout: 5000 })
        await mock.locator('a[href="#/exports"]').click()
        await current('Exports').waitFor({ timeout: 5000 })

        // state switcher shows the empty variant
        await mock.locator('[data-screen="exports"] [data-state="default"]').waitFor({ state: 'visible', timeout: 5000 })
        await harness.locator('#state-switch button', { hasText: 'empty' }).click()
        await mock.locator('[data-screen="exports"] [data-state="empty"]').waitFor({ state: 'visible', timeout: 5000 })
        await mock.locator('[data-screen="exports"] [data-state="default"]').waitFor({ state: 'hidden', timeout: 5000 })

        // mobile viewport is 390px wide
        await harness.locator('#vp-mobile').click()
        await sleep(300)
        const mobile = await harness.locator('#mock-frame').boundingBox()
        assert(mobile && Math.abs(mobile.width - 390) <= 1, `mobile frame width: ${JSON.stringify(mobile)}`)
        same(await mock.locator('body').evaluate(() => window.innerWidth), 390, 'inner window width in mobile')
        await harness.locator('#vp-desktop').click()
        await harness.locator('#state-switch button', { hasText: 'default' }).click()
        await mock.locator('[data-screen="exports"] [data-state="default"]').waitFor({ state: 'visible', timeout: 5000 })

        // pin a comment on a keyed element
        await harness.locator('#mode-comment').click()
        await mock.locator('[data-pin="new-export"]').click()
        const note = harness.locator('.note-pop')
        await note.waitFor({ state: 'visible', timeout: 5000 })
        await note.getByLabel('Comment', { exact: true }).fill('Make this button primary')
        await note.getByRole('button', { name: 'Send', exact: true }).click()
        await note.waitFor({ state: 'detached', timeout: 10_000 })
        const commentEvents = await nextEvents()
        same(commentEvents.map((e) => e.type), ['comment'], 'event types after the pin')
        const pinned = commentEvents[0].payload
        assert(typeof pinned.block_id === 'string' && PIN_ID_V1.test(pinned.block_id), `pin block id: ${pinned.block_id}`)
        same(pinned.text, 'Make this button primary', 'pin text')
        const threadId = pinned.thread_id
        assert(typeof threadId === 'string' && threadId, 'the pin comment has no thread_id')
        await harness.locator('#layer-pins .pin').waitFor({ state: 'visible', timeout: 10_000 })

        // Needs changes
        await harness.locator('#verdict').getByRole('button', { name: 'Needs changes', exact: true }).click()
        await harness.locator('#verdict').getByLabel('Overall comment (optional)').fill('Tighten the header')
        await harness.locator('#verdict').getByRole('button', { name: 'Send: needs changes' }).click()
        const verdictEvents = await nextEvents()
        same(verdictEvents.map((e) => e.type), ['submit'], 'event types after Needs changes')
        const verdict = verdictEvents[0].payload
        same(verdict.verdict, 'needs-changes', 'verdict')
        same(verdict.comment, 'Tighten the header', 'verdict comment')
        assert(Array.isArray(verdict.visited) && verdict.visited.includes('exports') && verdict.visited.includes('saved'), `visited: ${JSON.stringify(verdict.visited)}`)
        await harness.locator('#verdict').waitFor({ state: 'hidden', timeout: 10_000 })

        // the agent answers, then registers v2 without the pinned key and with another key changed
        await cliOk('reply', session, threadId, '--text', 'Dropped the button from the list', '--resolve', 'addressed')
        await registerMock(2, ['export-row'])
        const s2 = await mockStep(2)
        await waitForStep(page, s2.step)
        await harness.locator('#version-chip', { hasText: 'Mock v2' }).waitFor({ timeout: 15_000 })

        // v1 pin is orphaned: listed, not drawn on any element
        const orphan = harness.locator('.pin-row', { has: harness.locator('.badge.warn', { hasText: 'element removed in v2' }) })
        await orphan.waitFor({ state: 'visible', timeout: 15_000 })
        await harness.locator('.rail h2', { hasText: 'Orphaned pins' }).waitFor({ timeout: 5000 })
        assert((await orphan.innerText()).includes('new-export'), 'the orphaned row does not name the removed key')
        same(await harness.locator('#layer-pins .pin').count(), 0, 'pins drawn in v2')
        await harness.locator('#mode-comment').waitFor({ state: 'visible', timeout: 5000 })

        // Show changes outlines the changed element
        await harness.locator('#show-changes').check()
        const outline = harness.locator('#layer-changes .box.changed')
        await outline.waitFor({ state: 'visible', timeout: 5000 })
        same(await outline.count(), 1, 'changed outlines')
        const target = await mock.locator('[data-pin="export-row"]').boundingBox()
        const frameBox = await harness.locator('#mock-frame').boundingBox()
        const drawn = await outline.boundingBox()
        assert(target && frameBox && drawn, 'missing a bounding box for the change outline')
        assert(
          Math.abs(drawn.x - target.x) <= 1 && Math.abs(drawn.y - target.y) <= 1 && Math.abs(drawn.width - target.width) <= 1 && Math.abs(drawn.height - target.height) <= 1,
          `the change outline ${JSON.stringify(drawn)} is not on the changed element ${JSON.stringify(target)}`,
        )
        same(await mock.locator('[data-pin="new-export"]').count(), 0, 'removed element still in v2')

        // Looks right with one screen unvisited needs a confirm
        await mock.locator('a[href="#/saved"]').click()
        await current('Saved exports').waitFor({ timeout: 5000 })
        const bar = harness.locator('#verdict')
        await bar.getByRole('button', { name: 'Looks right', exact: true }).click()
        const confirmText = await bar.locator('.panel').innerText()
        assert(confirmText.includes('Export detail') && !confirmText.includes('Saved exports'), `confirm panel text: ${confirmText}`)
        const quiet = await cli('next', session, '--after', cursor, '--timeout', 1)
        same(quiet.out.status, 'timeout', 'no event before the confirm click')
        await bar.getByRole('button', { name: 'Confirm: looks right' }).click()
        const signoff = await nextEvents()
        same(signoff.map((e) => e.type), ['submit'], 'event types after Looks right')
        same(signoff[0].payload.verdict, 'looks-right', 'sign-off verdict')
        same(signoff[0].payload.visited, ['exports', 'saved'], 'sign-off visited')

        // export is a single file with no token in it
        const outDir = await mkdtemp(path.join(scratchRoot(), 'mock-export-'))
        const exported = await cliOk('mock-export', session, '--version', 2, '--out', outDir)
        same(exported.files.map((f: string) => path.basename(f)).sort(), ['mock.html', 'review.json', 'screens.md'], 'exported files')
        for (const file of exported.files) assert(existsSync(file), `missing exported file ${file}`)
        const exportedHtml = await readFile(path.join(outDir, 'mock.html'), 'utf8')
        assert(!exportedHtml.includes(token), 'mock.html contains the session token')
        same(consoleErrors, [], 'console errors')
      } finally {
        await page.close()
      }
    },
  ],
]

async function main(): Promise<number> {
  const browser = await launchBrowser()
  if (!browser) {
    console.error('no browser available: install Chrome or Edge, or set CHROME_PATH to a Chromium executable')
    return 3
  }
  const root = await mkdtemp(path.join(tmpdir(), 'quirk-e2e-'))
  session = path.join(root, '.quirk', 'brainstorm', 'e2e')
  await mkdir(path.dirname(session), { recursive: true })
  let started = false
  const results: [string, string | null][] = []
  try {
    const info = await cliOk('start', session, '--app')
    started = true
    assert(info.mode === 'app' && typeof info.url === 'string', `unexpected start output: ${JSON.stringify(info)}`)
    console.log(`server: ${info.url}`)
    const context = await browser.newContext()
    const drafts: string[] = []
    context.on('request', (request) => {
      if (request.method() !== 'POST' || !request.url().endsWith(EVENT_PATH)) return
      try {
        if (JSON.parse(request.postData() ?? '{}').type === 'draft') drafts.push(request.postData() ?? '')
      } catch {
        // not JSON: not a draft
      }
    })
    const env: Env = { context, url: info.url, drafts }
    for (const [name, run] of scenarios) {
      try {
        await run(env)
        results.push([name, null])
        console.log(`PASS ${name}`)
      } catch (error) {
        const message = String((error as Error).message ?? error).split('\n')[0]
        results.push([name, message])
        console.log(`FAIL ${name}: ${message}`)
      }
    }
  } catch (error) {
    results.push(['setup', String((error as Error).message ?? error)])
    console.log(`FAIL setup: ${(error as Error).message}`)
  } finally {
    await browser.close().catch(() => {})
    if (started) await cli('stop', session).catch(() => {})
    await rm(root, { recursive: true, force: true }).catch(() => {})
  }
  const failed = results.filter(([, error]) => error !== null)
  console.log(`\n${results.length - failed.length} of ${scenarios.length} scenarios passed`)
  return failed.length || results.length < scenarios.length ? 1 : 0
}

process.exit(await main())
