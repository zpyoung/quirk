import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { fetchDiff, postRunEvent } from '../src/run/api'
import { countsLine, formatElapsed, pickPage, serverOffsetMs, staleSince, staleText, taskElapsedMs } from '../src/run/format'
import { RunPage } from '../src/run/run-view'
import type { RunStatus, RunTask, RunView } from '../src/run/types'
import type { Boot, Snapshot } from '../src/types'

const failures: string[] = []
const check = (ok: boolean, message: string) => {
  if (!ok) failures.push(message)
}

const boot: Boot = { token: 't', session: 's' }
const T0 = 1_800_000_000

const task = (id: string, status: RunStatus, extra: Partial<RunTask> = {}): RunTask => ({
  id,
  title: `Task ${id}`,
  level: 1,
  status,
  attempt: 1,
  attempts: [],
  files: 0,
  ready: true,
  blocked_by: [],
  downstream: [],
  labels: [],
  mismatch: null,
  ...extra,
})

const baseRun = (extra: Partial<RunView> = {}): RunView => ({
  run_id: 'r1',
  branch: 'feature/live-view',
  started_at: T0,
  counts: {},
  last_update_at: T0 + 10,
  stale: null,
  stale_after_s: 180,
  now: T0 + 20,
  tasks: [],
  edges: [],
  chains: [],
  rounds: [],
  questions: [],
  ...extra,
})

const liveRun = (extra: Partial<RunView> = {}): RunView =>
  baseRun({
    counts: { passed: 1, running: 1, queued: 1 },
    tasks: [
      task('T1', 'passed', { started_at: T0, ended_at: T0 + 5 }),
      task('T2', 'running', { started_at: T0 + 6, downstream: ['T3'] }),
      task('T3', 'queued', { ready: false, blocked_by: ['T2'] }),
    ],
    edges: [{ from: 'T2', to: 'T3', kind: 'dep' }],
    ...extra,
  })

const snapshot = (run: RunView): Snapshot => ({
  rev: 1, mode: 'app', step: null, step_state: 'open', status: null, stages: [], decisions: [], chat: [], threads: [],
  review_registered: false, run,
})
const page = (run: RunView, paused = false) =>
  renderToStaticMarkup(createElement(RunPage, { snapshot: snapshot(run), boot, paused }))

// header counts, branch and title
{
  const html = page(liveRun())
  check(html.includes('Quirk run'), 'header lacks "Quirk run"')
  check(html.includes('feature/live-view'), 'header lacks the branch')
  check(html.includes('1 of 3 passed · 1 running · 1 queued'), 'header lacks the counts line')
  check(html.includes('data-stub="graph"'), 'a live run does not render the graph')
  check(!html.includes('data-stale'), 'a fresh run is marked stale')
}

// preflight: header and status line only
{
  const html = page(baseRun({ status_text: 'Preflight: checking backends' }))
  check(html.includes('Preflight: checking backends'), 'preflight lacks the status line')
  check(!html.includes('data-stub="graph"'), 'preflight rendered the graph')
  check(!html.includes('data-stub="timeline"'), 'preflight rendered the timeline')
}

// ended run renders the summary instead of the live layout
{
  const run = liveRun({ ended: { at: T0 + 100, outcome: 'clean', next_step: 'merge' } })
  const html = page(run)
  check(html.includes('data-stub="summary"'), 'an ended run does not render the summary')
  check(!html.includes('data-stub="graph"'), 'an ended run still renders the graph')
  const stopped = page(run, true)
  check(!stopped.includes('Lost connection to the companion'), 'an ended run shows the live connection-lost text')
}

// connection lost on a live run
{
  check(page(liveRun(), true).includes('Lost connection to the companion'), 'a paused live run lacks the connection-lost text')
  check(!page(liveRun(), false).includes('Lost connection'), 'a connected run shows the connection-lost text')
}

// stale run: 240 s since the last update against a 180 s threshold
{
  const html = page(liveRun({ last_update_at: T0, now: T0 + 240 }))
  check(html.includes('data-stale="true"'), 'a stale run lacks data-stale')
  check(html.includes('No update for 4 min'), 'a stale run lacks the stale text')
  check(!html.includes('data-stale') || !page(liveRun({ last_update_at: T0 + 100, now: T0 + 240 })).includes('data-stale'), 'a run under the threshold is stale')
}

// wording from the previous wave design must not appear
{
  const html = [page(liveRun()), page(baseRun({ status_text: 'x' })), page(liveRun({ ended: { at: T0 + 9, outcome: 'clean' } }))].join('')
  check(!/Level|Wave/.test(html), 'the rendered view mentions a level or a wave')
}

// open question: the newest question's task shows in the banner stub
{
  const html = page(liveRun({
    questions: [{ id: 'q1', task: 'T2', prompt: 'Which?', options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }], asked_at: T0 + 8, state: 'open' }],
  }))
  check(html.includes('data-stub="banner"'), 'an open question does not render the banner')
}

// reviews section only when rounds exist
{
  const withRounds = page(liveRun({ rounds: [{ id: 'cp1', kind: 'checkpoint', title: 'Checkpoint 1', covers: ['T1'], findings: [] }] }))
  check(withRounds.includes('data-stub="reviews"'), 'rounds do not render Reviews')
  check(!page(liveRun()).includes('data-stub="reviews"'), 'Reviews renders without rounds')
}

// format helpers against the contract examples
check(formatElapsed(40_000) === '0m 40s', `formatElapsed(40s) = ${formatElapsed(40_000)}`)
check(formatElapsed(151_000) === '2m 31s', `formatElapsed(151s) = ${formatElapsed(151_000)}`)
check(formatElapsed(3_720_000) === '1h 02m', `formatElapsed(62m) = ${formatElapsed(3_720_000)}`)
check(formatElapsed(-5) === '0m 00s', `formatElapsed(negative) = ${formatElapsed(-5)}`)
check(formatElapsed(5_000) === '0m 05s', `formatElapsed(5s) = ${formatElapsed(5_000)}`)
check(countsLine(baseRun()) === '', 'countsLine of zero tasks is not empty')
check(countsLine(liveRun()) === '1 of 3 passed · 1 running · 1 queued', `countsLine = ${countsLine(liveRun())}`)
{
  const run = baseRun({
    tasks: [task('a', 'passed'), task('b', 'needs-you'), task('c', 'failed'), task('d', 'retrying'), task('e', 'stopped'), task('f', 'skipped'), task('g', 'missing')],
  })
  check(
    countsLine(run) === '1 of 7 passed · 1 retrying · 1 needs you · 1 failed · 1 stopped · 1 skipped · 1 missing',
    `countsLine order = ${countsLine(run)}`,
  )
}
check(staleText(240) === 'No update for 4 min', `staleText(240) = ${staleText(240)}`)
check(staleText(45) === 'No update for 45s', `staleText(45) = ${staleText(45)}`)
check(staleText(125) === 'No update for 2 min', `staleText(125) = ${staleText(125)}`)

// clock helpers
{
  const run = liveRun({ last_update_at: T0, now: T0 + 240 })
  check(serverOffsetMs(run, (T0 + 40) * 1000) === 200_000, 'serverOffsetMs is not run.now - client now')
  check(staleSince(run, run.now * 1000) === 240, `staleSince = ${staleSince(run, run.now * 1000)}`)
  check(staleSince(liveRun({ last_update_at: T0, now: T0 + 100 }), (T0 + 100) * 1000) === null, 'staleSince under the threshold is not null')
  check(staleSince(liveRun({ last_update_at: T0, ended: { at: T0, outcome: 'clean' } }), (T0 + 999) * 1000) === null, 'staleSince of an ended run is not null')
  const t = task('T9', 'running', { started_at: T0 })
  check(taskElapsedMs(t, (T0 + 12) * 1000) === 12_000, 'taskElapsedMs of a running task')
  check(taskElapsedMs(task('T9', 'passed', { started_at: T0, ended_at: T0 + 3 }), (T0 + 99) * 1000) === 3_000, 'taskElapsedMs freezes at ended_at')
  check(taskElapsedMs(task('T9', 'queued'), T0 * 1000) === null, 'taskElapsedMs of a never-started task is not null')
}

// routing decision
check(pickPage('?view=diff&task=T1', false) === 'diff', 'view=diff does not pick the diff page')
check(pickPage('?view=diff&task=T1', true) === 'diff', 'view=diff with a run does not pick the diff page')
check(pickPage('?view=findings&round=cp1', true) === 'findings', 'view=findings does not pick the findings page')
check(pickPage('', true) === 'run', 'a run does not pick the run page')
check(pickPage('', false) === 'brainstorm', 'no run does not pick the brainstorm page')
check(pickPage('?view=diff', true) === 'run', 'view=diff without a task does not fall through')
check(pickPage('?view=findings', false) === 'brainstorm', 'view=findings without a round does not fall through')

// postRunEvent maps status codes
const reply = (status: number, body?: unknown): typeof fetch =>
  (async () => new Response(body === undefined ? null : JSON.stringify(body), { status })) as typeof fetch
{
  const answer = { question: 'q1', source: 'orca' as const, pick: 'a', label: 'A', at: T0 }
  const r204 = await postRunEvent(boot, 'run-stop', { task: 'T1' }, reply(204))
  check(r204.kind === 'ok', `204 -> ${r204.kind}`)
  const dup = await postRunEvent(boot, 'run-stop', { task: 'T1' }, reply(200, { duplicate: true }))
  check(dup.kind === 'duplicate', `200 duplicate -> ${dup.kind}`)
  const refused = await postRunEvent(boot, 'run-retry', { task: 'T1' }, reply(409, { refused: 'passed' }))
  check(refused.kind === 'refused' && refused.reason === 'passed', `409 refused -> ${JSON.stringify(refused)}`)
  const answered = await postRunEvent(boot, 'run-answer', { question: 'q1', pick: 'a' }, reply(409, { answered: answer }))
  check(answered.kind === 'answered' && answered.answer.label === 'A', `409 answered -> ${JSON.stringify(answered)}`)
  const server = await postRunEvent(boot, 'run-stop', { task: 'T1' }, reply(500))
  check(server.kind === 'error', `500 -> ${server.kind}`)
  const bad = await postRunEvent(boot, 'run-stop', { task: 'T1' }, reply(400, { error: 'x' }))
  check(bad.kind === 'error', `400 -> ${bad.kind}`)
}

// request shape and retry with one client_id
{
  const seen: { url: string; token: string | null; clientId: string; type: string }[] = []
  let calls = 0
  const flaky = (async (url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body))
    seen.push({ url: String(url), token: new Headers(init?.headers).get('X-Quirk-Token'), clientId: body.client_id, type: body.type })
    calls += 1
    if (calls < 3) throw new TypeError('network')
    return new Response(null, { status: 204 })
  }) as typeof fetch
  const result = await postRunEvent(boot, 'run-retry', { task: 'T2' }, flaky)
  check(result.kind === 'ok', `retry after network errors -> ${result.kind}`)
  check(seen.length === 3, `network errors were attempted ${seen.length} times, expected 3`)
  check(new Set(seen.map((s) => s.clientId)).size === 1 && seen[0].clientId.length > 0, 'a retry changed the client_id')
  check(seen[0].url === '/_quirk/app/event' && seen[0].token === 't' && seen[0].type === 'run-retry', 'request url, token or type is wrong')
  const down = await postRunEvent(boot, 'run-stop', { task: 'T1' }, (async () => { throw new TypeError('down') }) as typeof fetch)
  check(down.kind === 'error', `a dead network -> ${down.kind}`)
}

// fetchDiff
{
  const diff = { task: 'T1', base: 'abc', head: null, source: 'worktree', files: [], truncated: false }
  let url = ''
  const spy = (async (u: RequestInfo | URL) => {
    url = String(u)
    return new Response(JSON.stringify(diff), { status: 200 })
  }) as typeof fetch
  const ok = await fetchDiff('T 1', spy)
  check(ok?.base === 'abc', 'fetchDiff did not return the diff')
  check(url === '/_quirk/run/diff?task=T%201', `fetchDiff url = ${url}`)
  check((await fetchDiff('T1', reply(404))) === null, 'fetchDiff 404 is not null')
  check((await fetchDiff('T1', (async () => { throw new TypeError('x') }) as typeof fetch)) === null, 'fetchDiff network error is not null')
}

if (failures.length) {
  console.error(`run-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log('run-check passed: run view composition, routing, format helpers and run event posting.')
}
