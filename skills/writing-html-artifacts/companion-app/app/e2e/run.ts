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
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../../../..')
const COMPANION = path.join(REPO, 'skills/writing-html-artifacts/scripts/companion.py')
const EVENT_PATH = '/_quirk/app/event'
const SETTLE_MS = 1500

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
        await page.locator('[data-block-id="question:flow"] figure.diagram svg').first().waitFor({ timeout: 10_000 })

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
        await page.locator('[data-block-id="question:kit"] q-flow svg').first().waitFor({ timeout: 10_000 })
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
