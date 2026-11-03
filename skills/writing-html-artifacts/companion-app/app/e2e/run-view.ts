/**
 * End-to-end check of the SDD run view: a real server (python3 companion.py start --app, real built shell)
 * fed by the same CLI the SDD skill uses (run-start, report, ask, answer, await, next), a temp git repo as the
 * run's repo, and a real Chromium. The server runs with QUIRK_RUN_STALE_AFTER_S=5 so staleness is reachable.
 *
 * Usage: pnpm run e2e:run   (from companion-app/app)
 * Exit codes: 0 every scenario passed, 1 a scenario failed, 3 no browser could be launched.
 * Never downloads a browser; it only drives one that is already installed.
 * Scenarios share one run and run in order: each builds on the state the previous one left.
 */
import { execFile } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, mkdtemp, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../../../..')
const COMPANION = path.join(REPO, 'skills/writing-html-artifacts/scripts/companion.py')
const STALE_AFTER_S = 5
const STEP_MS = 15_000

interface CliResult {
  code: number
  out: any
  stderr: string
}

let session = ''
let root = ''
let repoDir = ''
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
function cli(args: (string | number)[], extraEnv: Record<string, string> = {}): Promise<CliResult> {
  const env = { ...process.env, ...extraEnv }
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
  const result = await cli(args)
  assert(result.code === 0, `companion ${args[0]} exited ${result.code}: ${JSON.stringify(result.out)} ${result.stderr}`)
  return result.out
}

const GIT_ENV = {
  GIT_AUTHOR_NAME: 't',
  GIT_AUTHOR_EMAIL: 't@example.com',
  GIT_COMMITTER_NAME: 't',
  GIT_COMMITTER_EMAIL: 't@example.com',
  GIT_CONFIG_GLOBAL: '/dev/null',
}

function git(cwd: string, ...args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile('git', ['-C', cwd, ...args], { env: { ...process.env, ...GIT_ENV } }, (error, stdout, stderr) => {
      if (error) reject(new Error(`git ${args.join(' ')} failed: ${stderr}`))
      else resolve(stdout.trim())
    })
  })
}

let fileCount = 0
async function writeJson(name: string, value: unknown): Promise<string> {
  fileCount += 1
  const file = path.join(root, `${name}-${fileCount}.json`)
  await writeFile(file, JSON.stringify(value), 'utf8')
  return file
}

const BRANCH = 'feat/e2e-run'
const RUN_ID = 'e2e'
let baseSha = ''

const task = (id: string, deps: string[] = []) => ({ id, title: `Task ${id}`, deps, order_after: [] as string[] })

async function runStart(tasks: ReturnType<typeof task>[]): Promise<any> {
  const doc = { v: 1, run_id: RUN_ID, repo: repoDir, branch: BRANCH, branch_pattern: 'sdd/{run}/{task}', base: baseSha, tasks }
  return cliOk('run-start', session, await writeJson('run', doc))
}

async function report(payload: Record<string, unknown>): Promise<any> {
  const out = await cliOk('report', session, JSON.stringify(payload))
  assert(typeof out.n === 'number', `report was dropped: ${JSON.stringify(out)}`)
  return out
}

async function ask(question: Record<string, unknown>): Promise<any> {
  return cliOk('ask', session, await writeJson('question', question))
}

/** Events the tab produced since the last call; the cursor moves so each event is returned once. */
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

interface Env {
  context: BrowserContext
  url: string
  /** The run page; opened by scenario a and kept for the scenarios after it. */
  page: Page
  pageErrors: string[]
  loads: { count: number }
}

const node = (page: Page, id: string) => page.locator(`.run-node[data-task="${id}"]`)

async function waitStatus(page: Page, id: string, status: string): Promise<void> {
  await page.locator(`.run-node[data-task="${id}"][data-status="${status}"]`).waitFor({ timeout: STEP_MS })
}

type Scenario = (env: Env) => Promise<void>

const T1_FILE = 't1-work.txt'
const wtT1 = () => path.join(root, 'wt-T1')

const scenarios: [string, Scenario][] = [
  [
    'a. preflight, then the plan, without a reload',
    async (env) => {
      const first = await runStart([])
      same(first, { run: RUN_ID, resumed: false, url: env.url }, 'run-start result')
      await report({ kind: 'status', text: 'Preflight: checking backends' })

      const page = env.page
      page.on('load', () => (env.loads.count += 1))
      await page.goto(env.url)
      await page.locator('.run-branch', { hasText: BRANCH }).waitFor({ timeout: STEP_MS })
      await page.locator('.run-status-line', { hasText: 'Preflight: checking backends' }).waitFor({ timeout: STEP_MS })
      same(await page.locator('.run-node').count(), 0, 'nodes during preflight')

      const plan = await runStart([task('T1'), task('T2', ['T1']), task('T3', ['T1']), task('T4', ['T2', 'T3'])])
      same(plan.resumed, true, 'second run-start resumes')
      await page.locator('.run-node').nth(3).waitFor({ timeout: STEP_MS })
      same(await page.locator('.run-node').count(), 4, 'nodes after the plan')
      same((await page.locator('.run-counts').innerText()).trim(), '0 of 4 passed · 4 queued', 'header counts')
      for (const [from, to] of [['T1', 'T2'], ['T1', 'T3'], ['T2', 'T4'], ['T3', 'T4']]) {
        same(await page.locator(`path.run-edge[data-from="${from}"][data-to="${to}"]`).count(), 1, `edge ${from} to ${to}`)
      }
      same(env.loads.count, 1, 'page load events (the plan must arrive without a reload)')
    },
  ],
  [
    'b. dispatch shows running, commit shows passed',
    async (env) => {
      const page = env.page
      await git(repoDir, 'worktree', 'add', '-q', '-b', `sdd/${RUN_ID}/T1`, wtT1(), BRANCH)
      await writeFile(path.join(wtT1(), T1_FILE), 'one\n', 'utf8')
      await report({ kind: 'dispatch', task: 'T1', attempt: 1, branch: `sdd/${RUN_ID}/T1`, worktree: wtT1(), base: baseSha })
      await waitStatus(page, 'T1', 'running')
      await page.locator('.run-counts', { hasText: '1 running' }).waitFor({ timeout: STEP_MS })

      await git(wtT1(), 'add', '-A')
      await git(wtT1(), 'commit', '-q', '-m', 'T1 work')
      await report({ kind: 'commit', task: 'T1', commit: await git(wtT1(), 'rev-parse', 'HEAD') })
      await waitStatus(page, 'T1', 'passed')
      same((await page.locator('.run-counts .sr-only').textContent())?.trim(), '1 of 4 passed · 3 queued', 'header counts after the commit')
    },
  ],
  [
    'c. a question answered in the tab reaches await; a second answer loses',
    async (env) => {
      const page = env.page
      const asked = await ask({
        id: 'q-pick',
        task: 'T2',
        header: 'T2 scope',
        prompt: 'T2 wrote outside its scope. Widen or re-plan?',
        options: [
          { value: 'widen', label: 'Widen scope' },
          { value: 'replan', label: 'Re-plan the task' },
        ],
        recommended: 'widen',
      })
      same(asked.question, 'q-pick', 'ask result')
      const item = page.locator('.run-banner-item[data-kind="open"]', { hasText: 'T2 wrote outside its scope' })
      await item.waitFor({ timeout: STEP_MS })
      await waitStatus(page, 'T2', 'needs-you')

      await item.getByRole('button', { name: 'Show on graph' }).click()
      const card = page.locator('[data-run-part="question-card"][data-question="q-pick"]')
      await card.waitFor({ state: 'visible', timeout: STEP_MS })

      const waiting = cli(['await', session, 'q-pick', '--quiet-after', 0, '--timeout', 10])
      await card.getByLabel('Re-plan the task').check()
      await card.getByRole('button', { name: 'Send' }).click()
      const result = await waiting
      same(result.code, 0, 'await exit code')
      same(result.out.answered?.source, 'tab', 'await answer source')
      same(result.out.answered?.pick, 'replan', 'await answer pick')
      await card.locator('.run-card-note', { hasText: 'Sent: Re-plan the task. SDD will act on it at its next step.' }).waitFor({ timeout: STEP_MS })

      const late = await cli(['answer', session, 'q-pick', '--source', 'orca', '--pick', 'widen'])
      same(late.code, 1, 'second answer exit code')
      same(late.out.already, true, 'second answer already flag')
      same(late.out.answered?.source, 'tab', 'the winning answer stays the tab')
      // the card also closes itself 4 s after the answer, so a click that misses it is not a failure
      await card.getByRole('button', { name: 'Close' }).click({ timeout: 2_000 }).catch(() => undefined)
      await card.waitFor({ state: 'detached', timeout: STEP_MS })
    },
  ],
  [
    'd. an answer given in orca ask shows in the tab',
    async (env) => {
      const page = env.page
      await ask({
        id: 'q-orca',
        task: 'T3',
        header: 'T3 contract',
        prompt: 'T3 needs a field T1 renamed. Update the contract?',
        options: [
          { value: 'update', label: 'Update the contract' },
          { value: 'replan', label: 'Re-plan the task' },
        ],
      })
      await page.locator('.run-banner-item[data-kind="open"]', { hasText: 'T3 needs a field' }).waitFor({ timeout: STEP_MS })
      const won = await cli(['answer', session, 'q-orca', '--source', 'orca', '--pick', 'update'])
      same(won.code, 0, 'orca answer exit code')
      await page
        .locator('.run-banner-item[data-kind="answered"]', { hasText: 'Answered in orca ask: Update the contract' })
        .waitFor({ timeout: STEP_MS })
      same(await page.locator('.run-banner-item[data-kind="open"]').count(), 0, 'open banner items after both answers')
    },
  ],
  [
    'e. stop chain from a failed task',
    async (env) => {
      const page = env.page
      await report({ kind: 'fail', task: 'T2', reason: 'tests red' })
      await waitStatus(page, 'T2', 'failed')
      await node(page, 'T2').click()
      const drawer = page.locator('[data-run-part="drawer"][data-task="T2"]')
      await drawer.waitFor({ state: 'visible', timeout: STEP_MS })
      await drawer.getByRole('button', { name: 'Stop chain' }).click()
      const dialog = page.getByRole('dialog')
      await dialog.waitFor({ state: 'visible', timeout: STEP_MS })
      const text = await dialog.innerText()
      assert(text.includes('T4'), `the confirm does not list T4: ${text}`)
      assert(text.includes('T1') && text.includes('committed'), `the confirm does not name the committed predecessor: ${text}`)
      await dialog.getByRole('button', { name: 'Stop chain' }).click()

      let stop: any = null
      for (let i = 0; i < 3 && !stop; i += 1) stop = (await nextEvents(10)).find((event) => event.type === 'run-stop')
      assert(stop, 'next returned no run-stop event')
      same(stop.payload, { task: 'T2', run_id: RUN_ID }, 'run-stop payload')
      await node(page, 'T2').locator('.run-node-chip', { hasText: 'Stop requested' }).waitFor({ timeout: STEP_MS })
    },
  ],
  [
    'f. the diff opens in a new page while the run page keeps updating',
    async (env) => {
      const page = env.page
      await node(page, 'T1').click()
      const drawer = page.locator('[data-run-part="drawer"][data-task="T1"]')
      await drawer.waitFor({ state: 'visible', timeout: STEP_MS })
      const opened = env.context.waitForEvent('page', { timeout: STEP_MS })
      await drawer.getByRole('link', { name: 'Diff' }).click()
      const diff = await opened
      try {
        await diff.waitForLoadState('load')
        assert(diff.url().endsWith('/?view=diff&task=T1'), `diff page url: ${diff.url()}`)
        await diff.locator('.run-diff-path', { hasText: T1_FILE }).waitFor({ timeout: STEP_MS })

        await report({ kind: 'status', text: 'Checkpoint 1 running' })
        await page.locator('.run-status-line', { hasText: 'Checkpoint 1 running' }).waitFor({ timeout: STEP_MS })
        assert(await diff.locator('.run-diff-path', { hasText: T1_FILE }).isVisible(), 'the diff page lost its content')
      } finally {
        await diff.close()
      }
    },
  ],
  [
    'g. stale after silence, cleared by one report',
    async (env) => {
      const page = env.page
      await report({ kind: 'status', text: 'Checkpoint 1 running' })
      await page.locator('.run-view:not([data-stale])').waitFor({ timeout: STEP_MS })
      await sleep((STALE_AFTER_S + 1) * 1000)
      await page.locator('.run-view[data-stale="true"]').waitFor({ timeout: STEP_MS })
      await page.locator('.run-stale', { hasText: 'No update for' }).waitFor({ timeout: STEP_MS })

      await report({ kind: 'status', text: 'Checkpoint 1 done' })
      await page.locator('.run-view:not([data-stale])').waitFor({ timeout: STEP_MS })
      same(await page.locator('.run-stale').count(), 0, 'stale text after a fresh report')
    },
  ],
  [
    'h. the summary survives the companion stopping',
    async (env) => {
      const page = env.page
      await report({ kind: 'run-end', outcome: 'stopped', next_step: 'keep' })
      const summary = page.locator('[data-run-part="summary"]')
      await summary.waitFor({ state: 'visible', timeout: STEP_MS })
      await summary.getByRole('heading', { name: 'Run stopped' }).waitFor({ timeout: STEP_MS })
      same(await page.locator('.run-node').count(), 0, 'graph nodes after the run ended')
      same(env.pageErrors, [], 'page errors')

      const stopped = await cliOk('stop', session)
      same(stopped, { stopped: true }, 'stop result')
      await page.getByText('The companion has stopped; this is the final state.').waitFor({ timeout: 30_000 })
      assert(await summary.isVisible(), 'the summary went away when the companion stopped')
    },
  ],
]

async function main(): Promise<number> {
  const browser = await launchBrowser()
  if (!browser) {
    console.error('no browser available: install Chrome or Edge, or set CHROME_PATH to a Chromium executable')
    return 3
  }
  root = await realpath(await mkdtemp(path.join(tmpdir(), 'quirk-e2e-run-')))
  session = path.join(root, '.quirk', 'sdd', 'e2e')
  repoDir = path.join(root, 'repo')
  await mkdir(path.dirname(session), { recursive: true })
  let started = false
  const results: [string, string | null][] = []
  try {
    await mkdir(repoDir)
    await git(repoDir, 'init', '-q', '-b', 'main')
    await writeFile(path.join(repoDir, 'README.md'), 'hello\n', 'utf8')
    await git(repoDir, 'add', '-A')
    await git(repoDir, 'commit', '-q', '-m', 'init')
    await git(repoDir, 'branch', BRANCH)
    baseSha = await git(repoDir, 'rev-parse', BRANCH)

    const start = await cli(['start', session, '--app'], { QUIRK_RUN_STALE_AFTER_S: String(STALE_AFTER_S) })
    assert(start.code === 0, `start exited ${start.code}: ${JSON.stringify(start.out)} ${start.stderr}`)
    started = true
    const info = start.out
    assert(info.mode === 'app' && typeof info.url === 'string', `unexpected start output: ${JSON.stringify(info)}`)
    console.log(`server: ${info.url}`)

    const context = await browser.newContext()
    const page = await context.newPage()
    const pageErrors: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))
    const env: Env = { context, url: info.url, page, pageErrors, loads: { count: 0 } }
    for (const [name, run] of scenarios) {
      try {
        await run(env)
        results.push([name, null])
        console.log(`PASS ${name}`)
      } catch (error) {
        const message = String((error as Error).message ?? error).split('\n').slice(0, 3).join(' | ')
        results.push([name, message])
        console.log(`FAIL ${name}: ${message}`)
      }
    }
  } catch (error) {
    results.push(['setup', String((error as Error).message ?? error)])
    console.log(`FAIL setup: ${(error as Error).message}`)
  } finally {
    await browser.close().catch(() => {})
    if (started) await cli(['stop', session]).catch(() => {})
    await rm(root, { recursive: true, force: true }).catch(() => {})
  }
  const failed = results.filter(([, error]) => error !== null)
  console.log(`\n${results.length - failed.length} of ${scenarios.length} scenarios passed`)
  return failed.length || results.length < scenarios.length ? 1 : 0
}

process.exit(await main())
